"""Tests for docs/builtins/compile.md.

compile() is builtin_compile_impl in Python/bltinmodule.c. A str or bytes
source goes through the tokenizer and PEG parser to an AST, then the symbol
table and code generator; an `ast` tree skips the parser and is converted and
validated first; `ast.PyCF_ONLY_AST` returns after parsing. Linearity is
settled by traced allocation, which needs no tolerance, and by one timing test
over two tenfold steps; the behaviour rows are settled by observation: an
audit hook counts compilations, and modes, flags and optimization levels are
read from what the compiled code does.

Measurement scope:

* space: tracemalloc's peak for compiling 2,000 and 20,000 statements of
  `x = y + 1` grows between x5 and x20 for a str source, a bytes source,
  `ast.PyCF_ONLY_AST` and an `ast` tree passed back in; a constant bound
  predicts x1 and a quadratic one x100;
* time: 1,000, 10,000 and 100,000 such statements, each tenfold step costing
  between x3 and x50 (measured x8 to x22 on CPython 3.10, 3.12 and 3.14,
  aarch64). A quadratic bound predicts x100 per step;
* no source-to-code cache: the `compile` audit event fires once per
  compile() call, twice for the same source compiled twice, which also gives
  two distinct code objects; `eval()` and `exec()` of a string fire it on
  every call and `eval()` or `exec()` of a code object never;
* constant folding has size limits: `'a' * 10**8` compiles with a traced
  peak under 100,000 bytes and no constant longer than 4,096 items, while
  `'a' * 10` is folded to one constant. Folding `+` has no cap of its own:
  `'a' * 4000 + 'b' * 4000` folds to one 8,000-character constant;
* modes: `'eval'` rejects a statement, `'single'` prints a non-None
  expression's value, prints nothing for None or an assignment, and rejects
  two statements;
* `ast.PyCF_ONLY_AST` returns a tree equal to ast.parse()'s; a tree passed
  back compiles; a hand-built node without line numbers raises TypeError until
  ast.fix_missing_locations() fills them in, and a located tree with a Store
  context where Load is required raises ValueError; a hand-built
  `ast.Constant` holding a tuple of 10,000, 100,000 and 1,000,000 items
  costs between x3 and x50 per tenfold step (measured x9 to x12 on 3.10 and
  3.14), so its items count towards t;
* optimize: level 0 keeps asserts, docstrings and a true `__debug__`; level 1
  drops asserts and makes `__debug__` false; level 2 also drops docstrings;
  `-1` follows `python -O` and `-OO`, checked in subprocesses;
* flags: this module's `from __future__ import annotations` reaches a
  compile() it calls, so annotations stay strings, and `dont_inherit=True`
  drops it; passing the flag explicitly applies it with inheritance
  disabled;
* nesting: 200 nested brackets compile and 201 raise SyntaxError; 99 nested
  blocks compile and 100 raise IndentationError; chains of 100,000 `+`
  operands or `elif` branches raise RecursionError or MemoryError in a
  subprocess, while 100,000 separate `if` statements compile;
* errors: a SyntaxError carries the filename and line given; a `nonlocal`
  with no binding is a SyntaxError; an undefined name compiles and raises
  NameError when run;
* every fenced block runs in its own subprocess, and a mutated assertion in
  one of them is asserted to fail.

Not settled here:

* The Invalid source row is an upper bound: compile() stops at the first
  error, so a failure costs at most what success would. Only the exception is
  asserted.
* The eval(string) and exec(string) rows add O(n) to the code's own cost; the
  audit test shows the compilation happens on every call, and
  tests/test_builtin_claims.py times exec() of source against a code object.
  The code's own cost belongs to the code.
* `t` is at most proportional to n for a tree from ast.parse(), and smaller
  where n is mostly a long literal or whitespace; a hand-built tree has no
  source length, which is why its row uses t.
* The tokenizer caps (MAXLEVEL 200 brackets, MAXINDENT 100 levels) are the
  same in Parser/tokenizer.h or Parser/lexer/state.h from v3.10.19 to
  v3.14.2. The chain lengths at which the parser stack or compiler recursion
  gives out are not pinned; only 100,000 is asserted to fail.
* Not varied: statement shape for the scaling tests (one assignment of a
  binary operation per line), identifier length, and constant values. The
  compiler deduplicates constants in dictionaries, so constants chosen to
  collide in hash are outside the inputs measured here, as are deep trees of
  string-literal concatenations, which constant folding joins while
  compiling.
* The nesting tests run on CPython with its default recursion limit and
  thread stack size; the 100,000-link chains are asserted to raise rather
  than crash on each platform CI runs.
"""

from __future__ import annotations

import ast
import contextlib
import gc
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "compile.md"
EXPECTED_BLOCKS = 9

STATEMENT = "x = y + 1\n"


def source(statements: int) -> str:
    return STATEMENT * statements


@contextlib.contextmanager
def gc_disabled() -> Iterator[None]:
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """The fastest of several runs, the least noisy estimate."""
    times: list[float] = []
    with gc_disabled():
        for _ in range(repeats):
            start = time.perf_counter()
            func()
            times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc sees while `func` runs, after one warm-up call."""
    func()
    with gc_disabled():
        tracemalloc.start()
        try:
            func()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    return peak


def run_python(
    code: str, *argv: str, options: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *options, "-c", code, *argv],
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,
        check=False,
    )


FORMS: dict[str, Callable[[int], Callable[[], Any]]] = {
    "str": lambda k: lambda s=source(k): compile(s, "<s>", "exec"),
    "bytes": lambda k: lambda b=source(k).encode(): compile(b, "<s>", "exec"),
    "only_ast": lambda k: lambda s=source(k): compile(s, "<s>", "exec", ast.PyCF_ONLY_AST),
    "tree": lambda k: lambda t=ast.parse(source(k)): compile(t, "<s>", "exec"),
}


class TestCompilingIsLinear:
    """Rows: compile() of a str or bytes source, `ast.PyCF_ONLY_AST`, and an
    `ast` tree - O(n) or O(t) time and space."""

    @pytest.mark.serial
    @pytest.mark.parametrize("form", list(FORMS))
    def test_peak_space_grows_with_the_source(self, form: str) -> None:
        small = traced_peak(FORMS[form](2_000))
        large = traced_peak(FORMS[form](20_000))

        ratio = large / small
        assert 5 < ratio < 20, f"{form}: x{ratio:.1f} for x10 the statements"

    @pytest.mark.timing
    def test_time_grows_linearly_with_the_source(self) -> None:
        sizes = [1_000, 10_000, 100_000]
        times = [best_time(FORMS["str"](k)) for k in sizes]

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(3 < step < 50 for step in steps), [f"x{step:.1f}" for step in steps]

    @pytest.mark.timing
    def test_a_tuple_constant_counts_its_items(self) -> None:
        def compiling(items: int) -> Callable[[], Any]:
            value: Any = tuple(range(items))  # typeshed omits tuple constants
            tree = ast.fix_missing_locations(ast.Expression(body=ast.Constant(value=value)))
            return lambda: compile(tree, "<ast>", "eval")

        times = [best_time(compiling(k)) for k in (10_000, 100_000, 1_000_000)]

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(3 < step < 50 for step in steps), [f"x{step:.1f}" for step in steps]

    def test_the_forms_agree(self) -> None:
        text = source(3)
        tree = compile(text, "<s>", "exec", ast.PyCF_ONLY_AST)

        assert isinstance(tree, ast.Module)
        assert ast.dump(tree) == ast.dump(ast.parse(text))
        for code in (
            compile(text, "<s>", "exec"),
            compile(text.encode(), "<s>", "exec"),
            compile(tree, "<s>", "exec"),
        ):
            namespace: dict[str, Any] = {"y": 41}
            exec(code, namespace)
            assert namespace["x"] == 42


class TestNothingIsCached:
    """Row: no cache - and the Running the result rows: eval() or exec() of a
    string compiles it on every call; of a code object, never."""

    def test_every_call_compiles(self) -> None:
        # An audit hook cannot be removed, so it is installed in a child.
        child = textwrap.dedent(
            """
            import sys
            events = []
            sys.addaudithook(
                lambda event, args: events.append(args[1]) if event == "compile" else None
            )
            first = compile("x ** 2", "<twice>", "eval")
            second = compile("x ** 2", "<twice>", "eval")
            assert first is not second
            assert events.count("<twice>") == 2
            x = 3
            for _ in range(10):
                eval("x ** 2")
            assert events.count("<string>") == 10
            for _ in range(10):
                exec("y = x ** 2")
            assert events.count("<string>") == 20
            statement = compile("y = x", "<exec>", "exec")
            before = len(events)
            for _ in range(10):
                eval(first)
                exec(statement)
            assert events[before:] == [], events[before:]
            print("ok")
            """
        )

        result = run_python(child)

        assert result.returncode == 0, result.stderr
        assert result.stdout == "ok\n"


class TestConstantFoldingIsCapped:
    """Row: compile() - a short expression such as 'a' * 10**8 is left for
    run time rather than built while compiling."""

    @pytest.mark.serial
    def test_a_large_product_is_not_built(self) -> None:
        text = "x = 'a' * 10**8"

        peak = traced_peak(lambda: compile(text, "<s>", "exec"))
        code = compile(text, "<s>", "exec")

        assert peak < 100_000, peak
        assert all(len(c) <= 4_096 for c in code.co_consts if isinstance(c, (str, tuple)))

    def test_a_long_concatenation_is_bounded_by_its_operands(self) -> None:
        code = compile("x = 'a' * 4000 + 'b' * 4000", "<s>", "exec")

        assert "a" * 4000 + "b" * 4000 in code.co_consts

    def test_a_small_product_is_folded(self) -> None:
        code = compile("x = 'a' * 10", "<s>", "exec")

        assert "a" * 10 in code.co_consts


class TestModes:
    """Row: mode - 'exec' takes statements, 'eval' one expression, 'single'
    one interactive statement whose expression values, other than None, are
    printed."""

    def test_eval_takes_one_expression(self) -> None:
        assert eval(compile("2 + 3", "<s>", "eval")) == 5
        with pytest.raises(SyntaxError):
            compile("x = 1", "<s>", "eval")

    def test_single_prints_expression_values(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile("1 + 1", "<s>", "single"), {})
            exec(compile("None", "<s>", "single"), {})
            exec(compile("x = 5", "<s>", "single"), {})

        assert output.getvalue() == "2\n"

    def test_single_rejects_two_statements(self) -> None:
        with pytest.raises(SyntaxError, match="multiple statements"):
            compile("x = 1\ny = 2", "<s>", "single")


class TestTrees:
    """Row: compile() of an ast tree - validated first; nodes built by hand
    need line numbers, which ast.fix_missing_locations() fills in."""

    def test_a_transformed_tree_compiles(self) -> None:
        tree = ast.parse("total = price * count")
        assign = tree.body[0]
        assert isinstance(assign, ast.Assign) and isinstance(assign.value, ast.BinOp)
        assign.value.op = ast.Add()

        namespace: dict[str, Any] = {"price": 3, "count": 4}
        exec(compile(tree, "<ast>", "exec"), namespace)

        assert namespace["total"] == 7

    def test_a_hand_built_node_needs_locations(self) -> None:
        tree = ast.Module(
            body=[ast.Expr(value=ast.Constant(value=1))],
            type_ignores=[],
        )

        with pytest.raises(TypeError, match="lineno"):
            compile(tree, "<ast>", "exec")

        compile(ast.fix_missing_locations(tree), "<ast>", "exec")

    def test_a_located_but_invalid_tree_is_rejected(self) -> None:
        tree = ast.fix_missing_locations(ast.Expression(body=ast.Name(id="x", ctx=ast.Store())))

        with pytest.raises(ValueError, match="Load context"):
            compile(tree, "<ast>", "eval")


class TestOptimizationLevels:
    """Row: optimize - -1 follows -O; 1 removes asserts and makes __debug__
    false; 2 also removes docstrings."""

    SOURCE = 'def f():\n    "doc"\n    assert False\n    return __debug__\n'

    def run(self, optimize: int) -> tuple[str | None, bool | str]:
        namespace: dict[str, Any] = {}
        exec(compile(self.SOURCE, "<s>", "exec", optimize=optimize), namespace)
        try:
            result = namespace["f"]()
        except AssertionError:
            result = "assert"
        return namespace["f"].__doc__, result

    def test_each_level(self) -> None:
        assert self.run(0) == ("doc", "assert")
        assert self.run(1) == ("doc", False)
        assert self.run(2) == (None, False)

    @pytest.mark.parametrize(("optimize", "debug"), [(0, True), (1, False), (2, False)])
    def test_debug_follows_the_level(self, optimize: int, debug: bool) -> None:
        assert eval(compile("__debug__", "<s>", "eval", optimize=optimize)) is debug

    def test_minus_one_follows_the_interpreter(self) -> None:
        child = f"exec(compile({self.SOURCE!r}, '<s>', 'exec'))\nprint(f.__doc__, f())"

        for options, expected in ((("-O",), "doc False\n"), (("-OO",), "None False\n")):
            result = run_python(child, options=options)
            assert result.returncode == 0, result.stderr
            assert result.stdout == expected
        unoptimized = run_python(child)
        assert unoptimized.returncode != 0
        assert "AssertionError" in unoptimized.stderr


class TestFutureFlags:
    """Row: flags, dont_inherit - the caller's future imports apply by
    default; dont_inherit=True uses flags alone. This module imports
    `annotations` from __future__."""

    SOURCE = "def f(x: int): pass"

    def annotations(self, **options: Any) -> dict[str, Any]:
        namespace: dict[str, Any] = {}
        exec(compile(self.SOURCE, "<s>", "exec", **options), namespace)
        return namespace["f"].__annotations__

    def test_the_callers_future_imports_are_inherited(self) -> None:
        assert self.annotations() == {"x": "int"}

    def test_dont_inherit_drops_them(self) -> None:
        assert self.annotations(dont_inherit=True) == {"x": int}

    def test_an_explicit_flag_applies_with_inheritance_disabled(self) -> None:
        import __future__

        flag = __future__.annotations.compiler_flag
        assert self.annotations(flags=flag, dont_inherit=True) == {"x": "int"}


class TestNestingLimits:
    """Limits on Nesting: 200 brackets and 99 indentation levels compile, one
    more raises; a chain of 100,000 links raises RecursionError or
    MemoryError where 100,000 separate statements compile."""

    def test_the_bracket_cap(self) -> None:
        compile("x = " + "(" * 200 + "1" + ")" * 200, "<s>", "exec")
        with pytest.raises(SyntaxError, match="too many nested parentheses"):
            compile("x = " + "(" * 201 + "1" + ")" * 201, "<s>", "exec")

    @staticmethod
    def nested_blocks(depth: int) -> str:
        return "".join(" " * i + "if x:\n" for i in range(depth)) + " " * depth + "pass\n"

    def test_the_indentation_cap(self) -> None:
        compile(self.nested_blocks(99), "<s>", "exec")
        with pytest.raises(IndentationError, match="too many levels of indentation"):
            compile(self.nested_blocks(100), "<s>", "exec")

    CHILD = textwrap.dedent(
        """
        import sys
        kind = sys.argv[1]
        if kind == "plus":
            text = "x = " + " + ".join(["y"] * 100_000)
        elif kind == "elif":
            text = "if a == 0: pass\\n" + "".join(f"elif a == {i}: pass\\n" for i in range(100_000))
        else:
            text = "".join(f"if a == {i}: pass\\n" for i in range(100_000))
        try:
            compile(text, "<s>", "exec")
        except (RecursionError, MemoryError) as error:
            print(type(error).__name__)
        else:
            print("compiled")
        """
    )

    @pytest.mark.parametrize("kind", ["plus", "elif"])
    def test_a_long_chain_exhausts_the_stack(self, kind: str) -> None:
        result = run_python(self.CHILD, kind)

        assert result.returncode == 0 and result.stdout.strip() in {
            "RecursionError",
            "MemoryError",
        }, (
            result.returncode,
            result.stdout,
            result.stderr[-500:],
        )

    def test_flat_statements_compile(self) -> None:
        result = run_python(self.CHILD, "flat")

        assert result.returncode == 0, result.stderr[-500:]
        assert result.stdout == "compiled\n"


class TestErrors:
    """Row: Invalid source - SyntaxError carries filename and line, scoping
    errors included; an undefined name is not an error until the code runs."""

    def test_syntax_error_names_the_file_and_line(self) -> None:
        with pytest.raises(SyntaxError) as caught:
            compile("ok = 1\ntotal = ", "settings.py", "exec")

        assert caught.value.filename == "settings.py"
        assert caught.value.lineno == 2

    def test_a_scoping_error_is_a_syntax_error(self) -> None:
        with pytest.raises(SyntaxError, match="nonlocal"):
            compile("def f():\n    nonlocal missing\n", "<s>", "exec")

    def test_names_are_resolved_at_run_time(self) -> None:
        code = compile("undefined_function()", "<s>", "exec")

        with pytest.raises(NameError, match="undefined_function"):
            exec(code, {})


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, block in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(block, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, block = next((n, s) for n, s in _blocks() if "compiled.count" in s)
        mutated = block.replace(
            'assert compiled.count("<expr>") == 1', 'assert compiled.count("<expr>") == 100', 1
        )

        assert mutated != block, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
