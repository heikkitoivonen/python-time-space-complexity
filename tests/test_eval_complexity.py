"""Tests for docs/builtins/eval.md.

eval() is builtin_eval_impl in Python/bltinmodule.c. A str or bytes source is
compiled in 'eval' mode on every call and the code object run; a code object
is run directly. Before either, the namespaces are resolved: an explicit
`globals` dict is used as given, with `__builtins__` added if missing, and
with no namespaces inside a function the frame's local variables are copied
into a dict: a fresh one on 3.13+, the frame's own on 3.11 and 3.12.
Linearity in the source is settled by traced allocation and
one timing test over two tenfold steps; the cost of copying the locals by
timing at two sizes; the behaviour rows by observation: an audit hook counts
compilations, and namespaces, modes and errors are read from what eval()
returns or raises.

Measurement scope:

* space: tracemalloc's peak for eval() of a list display of 2,000 and 20,000
  names grows between x5 and x20, for a str and a bytes source; a constant
  bound predicts x1 and a quadratic one x100;
* time: list displays of 1,000, 10,000 and 100,000 names, each tenfold step
  costing between x3 and x50; a quadratic bound predicts x100 per step;
* no cache: the `compile` audit event fires on every eval() of a string,
  100 times for 100 calls, and never for eval() of a code object;
* globals: one eval() of a code object against a globals dict of 10 and of
  100,000 entries costs within x3, so the namespace's size is not a term;
  `__builtins__` is inserted into an empty dict, `locals()` inside the
  expression is the globals dict when only globals is given, a ChainMap is
  accepted as locals and rejected as globals;
* locals copy: eval() of a compiled `0` in a function with 1,000 and 10,000
  local variables, called from a plain loop in that function. On 3.13+ the
  tenfold step costs more than x40 (measured x86 to x92 on 3.13.16 and
  3.14.8, aarch64): _PyEval_GetFrameLocals() builds the dict with
  PyDict_Update() from a FrameLocalsProxy whose lookups scan the code's local
  names. On 3.11 and 3.12 it costs between x5 and x40 (measured x15 to x17 on 3.11.17
  and 3.12.15), as PyFrame_FastToLocalsWithError() copies each local once;
  O(v) predicts x10 and O(v^2) x100. With 10,000 locals, passing `{}` as
  globals is more than x10 cheaper than the copy (measured x52 to x58 on
  3.11 and 3.12, over x7,000 on 3.13+), and its traced peak stays under
  10,000 bytes where the copy's exceeds 100,000;
* code objects: 'exec'-mode code runs and eval() returns None; code with a
  free variable raises TypeError;
* errors: a statement and an empty string raise SyntaxError; leading spaces
  and tabs are skipped; an undefined name raises NameError when evaluated;
* globals and locals are accepted as keywords on 3.13+ and rejected on
  3.11 and 3.12;
* ast.literal_eval() accepts literals and containers and rejects a call;
* every fenced block runs in its own subprocess, and a mutated assertion in
  one of them is asserted to fail.

Not settled here:

* The Invalid source row is an upper bound: compilation stops at the first
  error. Only the exception is asserted.
* ast.literal_eval()'s O(n) for a string is measured in
  tests/test_ast_complexity.py; only what it accepts is asserted here.
* The expression's own cost belongs to the expression; only expressions of
  linear cost (a list display of names) are measured.
* Not varied: expression shape for the scaling tests (one flat list display),
  identifier length, and constant values. Chains the grammar nests, such as
  `a + b + c + ...`, hit the parser's recursion limits as tests/
  test_compile_complexity.py records.
* "An empty or restricted __builtins__ does not make eval() safe" is a
  security property, not a cost; nothing here tries to escape a namespace.
* The locals copy is measured only in a plain function; class bodies and
  module level pass their namespace dict without copying, and are not timed.
"""

from __future__ import annotations

import ast
import collections
import contextlib
import gc
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "eval.md"
EXPECTED_BLOCKS = 6


def display(names: int) -> str:
    """A flat list display of `names` copies of the name x."""
    return "[" + "x, " * names + "]"


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


def run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def with_locals(count: int, call: str, times: int = 1) -> Callable[[], Any]:
    """A function with `count` local variables that runs `call` `times` times
    in a plain loop, so the call runs in the function's own frame, and returns
    the last result. `call` may use `code`, a compiled `0`."""
    body = "".join(f"    v{i} = {i}\n" for i in range(count))
    loop = f"    for _ in range({times}):\n        result = {call}\n    return result\n"
    namespace: dict[str, Any] = {"code": compile("0", "<expr>", "eval")}
    exec(f"def f():\n{body}{loop}", namespace)
    return namespace["f"]


class TestEvaluatingAStringIsLinear:
    """Row: eval(source) with a str or bytes source - O(n) plus the
    expression's cost."""

    NAMESPACE = {"x": 1}

    @pytest.mark.serial
    @pytest.mark.parametrize("form", ["str", "bytes"])
    def test_peak_space_grows_with_the_source(self, form: str) -> None:
        def evaluating(names: int) -> Callable[[], Any]:
            text = display(names)
            source = text.encode() if form == "bytes" else text
            return lambda: eval(source, self.NAMESPACE)

        small = traced_peak(evaluating(2_000))
        large = traced_peak(evaluating(20_000))

        ratio = large / small
        assert 5 < ratio < 20, f"{form}: x{ratio:.1f} for x10 the names"

    @pytest.mark.timing
    def test_time_grows_linearly_with_the_source(self) -> None:
        sizes = [1_000, 10_000, 100_000]
        times = [best_time(lambda s=display(k): eval(s, self.NAMESPACE)) for k in sizes]

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(3 < step < 50 for step in steps), [f"x{step:.1f}" for step in steps]


class TestEveryStringIsCompiled:
    """Rows: eval(source) compiles on every call; eval(code) never does."""

    def test_the_audit_hook_sees_each_compilation(self) -> None:
        # An audit hook cannot be removed, so it is installed in a child.
        child = textwrap.dedent(
            """
            import sys
            events = []
            sys.addaudithook(
                lambda event, args: events.append(args[1]) if event == "compile" else None
            )
            x = 3
            for _ in range(100):
                eval("x ** 2")
            assert events.count("<string>") == 100, events
            code = compile("x ** 2", "<expr>", "eval")
            before = len(events)
            for _ in range(100):
                eval(code)
            assert events[before:] == [], events[before:]
            print("ok")
            """
        )

        result = run_python(child)

        assert result.returncode == 0, result.stderr
        assert result.stdout == "ok\n"


class TestNamespaces:
    """Rows: eval(source, globals) and eval(source, globals, locals) - O(1)
    on top; globals must be a dict and gains __builtins__, locals defaults
    to it and may be any mapping."""

    @pytest.mark.timing
    def test_the_size_of_globals_is_not_a_term(self) -> None:
        code = compile("x", "<expr>", "eval")

        def evaluating(entries: int) -> Callable[[], Any]:
            namespace: dict[str, Any] = {f"v{i}": i for i in range(entries)}
            namespace["x"] = 1
            return lambda: [eval(code, namespace) for _ in range(1_000)]

        small = best_time(evaluating(10))
        large = best_time(evaluating(100_000))

        assert large / small < 3, f"x{large / small:.1f} for x10,000 the entries"

    def test_builtins_are_added_to_an_empty_dict(self) -> None:
        namespace: dict[str, Any] = {}

        assert eval("len('abc')", namespace) == 3
        assert "__builtins__" in namespace

    def test_locals_defaults_to_globals(self) -> None:
        namespace: dict[str, Any] = {}

        assert eval("locals() is globals()", namespace) is True

    def test_locals_may_be_any_mapping(self) -> None:
        layers = collections.ChainMap({"a": 1}, {"b": 2})

        assert eval("a + b", {}, layers) == 3
        with pytest.raises(TypeError, match="dict"):
            eval("a", layers)  # type: ignore[arg-type]

    def test_keywords_are_accepted_from_313(self) -> None:
        def call() -> Any:
            return eval("x + y", globals={"x": 1}, locals={"y": 2})  # type: ignore[call-arg]

        if sys.version_info >= (3, 13):
            assert call() == 3
        else:
            with pytest.raises(TypeError):
                call()


class TestInsideAFunctionTheLocalsAreCopied:
    """Row: eval(source) inside a function, without globals - O(v^2) on
    3.13+, O(v) on 3.11 and 3.12; passing globals skips the copy."""

    @pytest.mark.timing
    def test_the_copy_grows_with_the_locals(self) -> None:
        small = best_time(with_locals(1_000, "eval(code)", times=20), repeats=3)
        large = best_time(with_locals(10_000, "eval(code)", times=20), repeats=3)

        ratio = large / small
        if sys.version_info >= (3, 13):
            assert ratio > 40, f"x{ratio:.1f} for x10 the locals; O(v^2) predicts x100"
        else:
            assert 5 < ratio < 40, f"x{ratio:.1f} for x10 the locals; O(v) predicts x10"

    @pytest.mark.timing
    def test_passing_globals_skips_the_copy(self) -> None:
        copying = best_time(with_locals(10_000, "eval(code)", times=20), repeats=3)
        explicit = best_time(with_locals(10_000, "eval(code, {})", times=20), repeats=3)

        ratio = copying / explicit
        assert ratio > 10, f"copying the 10,000 locals costs only x{ratio:.1f}"

    @pytest.mark.serial
    def test_only_the_copy_allocates_with_the_locals(self) -> None:
        copying = with_locals(10_000, "eval(code)")
        explicit = with_locals(10_000, "eval(code, {})")

        assert traced_peak(copying) > 100_000
        assert traced_peak(explicit) < 10_000

    def test_the_expression_sees_the_locals(self) -> None:
        assert with_locals(3, "eval('v0 + v1 + v2')")() == 3


class TestCodeObjects:
    """Row: eval(code) - no compilation; 'exec'-mode code returns None, code
    with free variables raises TypeError."""

    def test_exec_mode_code_runs_and_returns_none(self) -> None:
        namespace: dict[str, Any] = {}

        assert eval(compile("x = 5", "<s>", "exec"), namespace) is None
        assert namespace["x"] == 5

    def test_free_variables_are_rejected(self) -> None:
        def outer() -> Callable[[], int]:
            z = 5

            def inner() -> int:
                return z

            return inner

        with pytest.raises(TypeError, match="free variables"):
            eval(outer().__code__)


class TestErrors:
    """Row: Invalid source - SyntaxError for a statement or an empty string;
    leading spaces and tabs are skipped; an undefined name raises NameError
    only when evaluated."""

    @pytest.mark.parametrize("source", ["x = 5", "", "import os"])
    def test_non_expressions_are_syntax_errors(self, source: str) -> None:
        with pytest.raises(SyntaxError):
            eval(source)

    def test_leading_spaces_and_tabs_are_skipped(self) -> None:
        assert eval(" \t 1 + 1") == 2

    def test_names_are_resolved_when_evaluated(self) -> None:
        code = compile("undefined_name", "<s>", "eval")

        with pytest.raises(NameError, match="undefined_name"):
            eval(code, {})


class TestLiteralEval:
    """Safer Alternatives: ast.literal_eval() builds only literal values; an
    expression such as __import__('os') raises ValueError."""

    def test_literals_are_accepted(self) -> None:
        assert ast.literal_eval("[1, 2, 3]") == [1, 2, 3]
        assert ast.literal_eval("{'a': 1}") == {"a": 1}

    @pytest.mark.parametrize("source", ["__import__('os')", "x"])
    def test_other_expressions_are_rejected(self, source: str) -> None:
        with pytest.raises(ValueError, match="malformed"):
            ast.literal_eval(source)


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
