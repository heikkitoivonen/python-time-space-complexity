"""Tests for docs/builtins/debug.md.

The page prices `__debug__` as a compile-time substitution rather than a
lookup, and prices the code it guards at nothing once optimization is on.
Both are settled by reading the code object the compiler produced - its
constants, its name tables and the length of its bytecode - and by counting
calls that a guarded expression would have made. Neither needs a tolerance.
`compile(optimize=)` supplies the levels in process; a subprocess started
with `-O` and `-OO` confirms that the interpreter flag does the same thing
end to end.

Measurement scope:

* The name is asserted to leave `co_names` empty and its value to sit in
  `co_consts`, where the same identifier written as `builtins.__debug__`
  puts both `builtins` and `__debug__` into `co_names`. That is the whole of
  the "no lookup at run time" claim, and it needs no stopwatch.
* `builtins.__debug__` is asserted equal to the flag, accepted by
  `setattr()`, and read by nothing: after setting it to `False`, code
  compiled afterwards still evaluates the name to `True`.
* Every binding form - assignment, `del`, a parameter, a keyword argument,
  `import ... as`, `for`, `class`, `except ... as`, the walrus and an
  attribute of another object - raises `SyntaxError` at compile time, while
  a subscript, a `global` declaration and an attribute *load* compile.
* An assertion's condition is a counting call: it runs once at `optimize=0`
  and not at all at `optimize=1` or `2`. Its message is a second counting
  call behind a condition that is also a call, so the compiler cannot decide
  the branch; it is built on failure only. A dropped assertion is asserted
  to leave the code object matching the one the source without the
  statement produces across every field that describes its work -
  which is the page's "not compiled" rather than merely "smaller". Six
  fields are compared at `optimize=1` and at `2` - `co_code`, `co_consts`,
  `co_stacksize`, `co_varnames`, `co_names` and `co_nlocals` - and
  `co_linetable` is asserted to differ, since the two sources put `return`
  on different lines. Nothing here compares `co_flags`, `co_cellvars` or
  `co_freevars`, which this example does not exercise. An assertion whose
  condition binds a name with `:=` is covered on both sides: while nothing
  reads the name the local goes with the statement on every supported
  version, and when later code does read it the name stays local, the
  binding goes, and calling the function raises `UnboundLocalError` where
  the same source without the statement resolves a module global. A second
  assignment to that name turns the error into a different answer instead,
  1 against 2. A name read from an enclosing function keeps its cell and
  free variable entries, and a `yield` keeps the function a generator whose
  first `next()` raises `StopIteration` with the return value, the yield
  having gone. Those are the ways dropping an assertion differs from never
  writing it, which is why the page stops at what is not evaluated rather
  than promising the code object of a source without the statement. A name
  bound in the *message* is kept the same way as one bound in the condition,
  and is unbound at every level, the message being reached only on failure.
  A `global` or `nonlocal` declaration sends the binding elsewhere: the
  module or enclosing name is 1 at the default level and stays 9 at both
  optimized ones, with no unbound local anywhere.
  Truth-testing the condition is part of what is dropped, shown with a
  counting `__bool__` at both optimized levels.
* An `if __debug__:` block of one statement at least halves the bytecode
  between the levels, and one of 200 statements goes from over 500 bytes to
  under 20, while `co_names`, `co_varnames` and `co_nlocals` are identical at
  both - which is the page's claim that the locals keep their slots. The
  dropped guard is also asserted *not* to match the code object of a
  function written without the block, which is what separates it from a
  dropped assertion. A counting call inside the block is asserted never to
  run at `optimize=1`.
* `sys.flags.optimize`, `__debug__`, `__doc__`, whether `assert False`
  raised, and whether a `compile(..., optimize=-1)` inside that process kept
  its assertion are read back from subprocesses started with no flag, `-O`
  and `-OO`. That last field is where `optimize=-1` is shown to follow the
  interpreter's own flag rather than the parent's.
* The two version boundaries are asserted on both sides of their release:
  `del x.__debug__` compiles below 3.14 and raises `SyntaxError` from it,
  and `ast.parse(optimize=1)` raises `TypeError` below 3.13 and returns a
  `Constant` from it.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `c`, `m` and `b`, the cost of an assertion's condition, its message and a
  guarded block, are the caller's own expressions in time and in space. The
  tests settle when each is evaluated, never how much it costs. A descriptor
  named `__debug__` is asserted to run, for the same reason: what an
  attribute of that name costs is the object's business.
* How much dearer the module lookup is than the constant. It is a constant
  factor, around a quarter on the pinned interpreter, which is too small to
  assert and too machine-specific to put on the page; what the page claims
  of that form is that it is a lookup and that it can disagree, and both are
  observed.
* Which constants a guarded function keeps in `co_consts` moves across the
  supported range: 3.14 holds the folded `True` or `False`, 3.13 keeps
  neither once the branch is resolved, and 3.10 keeps `True` at the default
  level only. Nothing here asserts on that tuple beyond the reader function,
  whose folded `True` is present on every supported version and is checked
  by identity, so an integer const cannot satisfy it.
* The page's claim that the constant is folded "when the code is compiled"
  is observed through `compile()` and through the interpreter's own flag.
  Neither says anything about a module imported from a cached `.pyc`, which
  is written per optimization level and is not exercised.
* The substitution itself is read from the AST preprocessor in
  Python/ast_preprocess.c on 3.14 and from its predecessors on the older
  branches; the tests observe the result, not the pass that performs it.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import pathlib
import re
import subprocess
import sys
import textwrap
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "debug.md"
EXPECTED_BLOCKS = 8

GUARDED = (
    "def check(data):\n"
    "    if __debug__:\n"
    "        total = sum(data)\n"
    "        assert total >= 0\n"
    "    return len(data)\n"
)


def compiled(source: str, level: int) -> dict[str, Any]:
    """Execute `source` compiled at one optimization level, and return its namespace."""
    namespace: dict[str, Any] = {}
    exec(compile(source, "<test>", "exec", optimize=level), namespace)
    return namespace


def run_python(script: str, *flags: str) -> str:
    """Run `script` in a fresh interpreter with the given flags."""
    result = subprocess.run(
        [sys.executable, *flags, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=True,
    )
    return result.stdout.strip()


class TestTheNameIsNotLookedUp:
    """`__debug__` | O(1) | O(1): folded into the code object, so `co_names`
    stays empty and nothing is resolved at run time."""

    @staticmethod
    def reads_the_constant() -> bool:
        return __debug__

    @staticmethod
    def reads_the_module() -> Any:
        # typeshed does not declare the name on the module, hence the ignores below.
        return builtins.__debug__  # type: ignore[attr-defined]

    def test_the_value_is_a_constant_and_the_name_is_gone(self) -> None:
        code = self.reads_the_constant.__code__

        assert code.co_names == (), f"the name survived compilation as {code.co_names}"
        assert any(value is True for value in code.co_consts), (
            f"the value was not folded in: {code.co_consts}"
        )
        assert self.reads_the_constant() is True

    def test_going_through_the_module_resolves_names_instead(self) -> None:
        """The same identifier, written as an attribute, is looked up."""
        code = self.reads_the_module.__code__

        assert "builtins" in code.co_names
        assert "__debug__" in code.co_names
        assert self.reads_the_module() is True


class TestTheBuiltinsEntryIsDecorative:
    """`builtins.__debug__` | O(1) | O(1): a dict lookup, set once at startup
    and read by nothing."""

    @pytest.fixture(autouse=True)
    def _restore(self) -> Iterator[None]:
        original = builtins.__debug__  # type: ignore[attr-defined]
        yield
        setattr(builtins, "__debug__", original)

    def test_it_starts_out_matching_the_flag(self) -> None:
        assert builtins.__debug__ is (sys.flags.optimize == 0)  # type: ignore[attr-defined]
        assert vars(builtins)["__debug__"] is builtins.__debug__  # type: ignore[attr-defined]

    def test_setting_it_changes_nothing_that_reads_the_name(self) -> None:
        setattr(builtins, "__debug__", False)

        assert builtins.__debug__ is False  # type: ignore[attr-defined]
        assert compiled("value = __debug__", 0)["value"] is True, (
            "a compilation after the assignment consulted the module"
        )
        assert __debug__ is True

    def test_an_attribute_of_that_name_on_another_object_is_ordinary(self) -> None:
        """Reading one is ordinary syntax; only binding one is refused - which
        is why this test has to reach for `setattr()` to set it."""

        class Holder:
            pass

        assert compile("x.__debug__", "<test>", "eval") is not None
        with pytest.raises(AttributeError):
            _ = Holder().__debug__  # type: ignore[attr-defined]

        setattr(Holder, "__debug__", "anything")  # noqa: B010 - the plain form is a SyntaxError
        assert Holder().__debug__ == "anything"  # type: ignore[attr-defined]

        # The O(1) in that row is for a stored attribute; a descriptor of the
        # same name runs like any other, which is why the row says so.
        with_property = type("P", (), {"__debug__": property(lambda self: "from a property")})
        assert with_property().__debug__ == "from a property"  # type: ignore[attr-defined]


BINDINGS = [
    "__debug__ = False",
    "del __debug__",
    "def f(__debug__): pass",
    "def f(*, __debug__=1): pass",
    "f(__debug__=1)",
    "import sys as __debug__",
    "from sys import path as __debug__",
    "for __debug__ in []: pass",
    "class __debug__: pass",
    "with open('x') as __debug__: pass",
    "try:\n    pass\nexcept ValueError as __debug__:\n    pass",
    "(__debug__ := 1)",
    "x.__debug__ = 1",
    "lambda __debug__: 0",
    "def __debug__(): pass",
    "async def __debug__(): pass",
]


class TestTheNameCannotBeBound:
    """The `SyntaxError` row: every binding form is refused when the code is
    compiled, an attribute of another object included."""

    @pytest.mark.parametrize("statement", BINDINGS)
    def test_binding_it_is_a_syntax_error(self, statement: str) -> None:
        with pytest.raises(SyntaxError, match="__debug__"):
            compile(statement, "<test>", "exec")

    @pytest.mark.parametrize(
        "statement", ["d['__debug__'] = 1", "global __debug__", "x.__debug__", "__debug__"]
    )
    def test_what_is_not_a_binding_still_compiles(self, statement: str) -> None:
        assert compile(statement, "<test>", "exec") is not None

    def test_it_is_an_identifier_not_a_keyword(self) -> None:
        import keyword

        assert not keyword.iskeyword("__debug__")
        assert keyword.iskeyword("True")
        # A keyword is refused by the parser, with a different message.
        with pytest.raises(SyntaxError, match="invalid syntax"):
            compile("x.True = 1", "<test>", "exec")

    def test_only_four_of_the_six_constants_are_protected(self) -> None:
        for protected in ("True", "False", "None", "__debug__"):
            with pytest.raises(SyntaxError):
                compile(f"{protected} = 67", "<test>", "exec")

        namespace = compiled(
            "NotImplemented = 67\nEllipsis = 68\nresult = (NotImplemented, Ellipsis)", 0
        )
        assert namespace["result"] == (67, 68)


class TestAssertionsDisappear:
    """`assert cond` | O(c), and O(1) under `-O`: the statement is not
    compiled, so the condition is never evaluated."""

    SOURCE = "assert condition(), 'never built'\n"

    def counter(self) -> tuple[Callable[[], bool], list[int]]:
        calls: list[int] = []

        def condition() -> bool:
            calls.append(1)
            return True

        return condition, calls

    @pytest.mark.parametrize(("level", "expected"), [(0, 1), (1, 0), (2, 0)])
    def test_the_condition_runs_only_when_the_statement_is_compiled(
        self, level: int, expected: int
    ) -> None:
        condition, calls = self.counter()

        exec(compile(self.SOURCE, "<test>", "exec", optimize=level), {"condition": condition})

        assert len(calls) == expected

    def test_truth_testing_the_condition_is_part_of_what_is_dropped(self) -> None:
        """`c` covers the conversion to bool, which is the caller's code too."""

        class Counting:
            def __init__(self) -> None:
                self.calls = 0

            def __bool__(self) -> bool:
                self.calls += 1
                return True

        kept = Counting()
        exec(compile("assert cond", "<test>", "exec", optimize=0), {"cond": kept})
        assert kept.calls == 1

        for level in (1, 2):
            dropped = Counting()
            exec(compile("assert cond", "<test>", "exec", optimize=level), {"cond": dropped})
            assert dropped.calls == 0, f"__bool__ ran at optimize={level}"

    def test_the_message_is_built_on_failure_only(self) -> None:
        """The condition is a call, not a literal, so the compiler cannot
        decide the branch and the message is reached at run time or not."""
        built: list[int] = []

        def message() -> str:
            built.append(1)
            return "failed"

        source = "assert holds(), message()"
        namespace: dict[str, Any] = {"message": message, "holds": lambda: True}

        exec(compile(source, "<test>", "exec"), namespace)
        assert built == []

        namespace["holds"] = lambda: False
        with pytest.raises(AssertionError, match="failed"):
            exec(compile(source, "<test>", "exec"), namespace)
        assert built == [1]

    FIELDS = ("co_code", "co_consts", "co_stacksize", "co_varnames", "co_names", "co_nlocals")

    def test_the_statement_leaves_no_bytecode_behind(self) -> None:
        """Not merely smaller: what the source without the statement gives.

        For a statement that binds nothing, closes over nothing and yields
        nothing - the cases that leave something behind have their own tests.
        Six fields survive the comparison; the line-number table does not,
        and cannot, since the two sources put `return` on different lines.
        """
        source = "def f(x):\n    assert x > 0, 'bad'\n    return x\n"
        without = "def f(x):\n    return x\n"

        kept = compiled(source, 0)["f"].__code__
        never_written = compiled(without, 0)["f"].__code__

        for level in (1, 2):
            dropped = compiled(source, level)["f"].__code__

            assert len(dropped.co_code) < len(kept.co_code)
            assert "bad" in kept.co_consts and "bad" not in dropped.co_consts
            for field in self.FIELDS:
                assert getattr(dropped, field) == getattr(never_written, field), (field, level)
            assert dropped.co_linetable != never_written.co_linetable

    @pytest.mark.parametrize("level", [1, 2])
    def test_a_name_the_assertion_bound_and_nothing_reads_goes_with_it(self, level: int) -> None:
        """A walrus inside an assertion is the shape that could leave a local
        behind, the way a dropped `if __debug__:` block does. While nothing
        else reads the name, it does not."""
        source = "def f():\n    assert (saved := 1)\n    return 0\n"
        without = "def f():\n    return 0\n"

        kept = compiled(source, 0)["f"].__code__
        dropped = compiled(source, level)["f"].__code__
        never_written = compiled(without, 0)["f"].__code__

        assert kept.co_varnames == ("saved",)
        assert dropped.co_varnames == never_written.co_varnames == ()
        assert dropped.co_code == never_written.co_code

    @pytest.mark.parametrize("level", [1, 2])
    def test_a_name_something_reads_stays_local_and_unassigned(self, level: int) -> None:
        """Where dropping an assertion is not the same as never having written
        it: the symbol table keeps the name local for the whole function, and
        only the binding goes."""
        source = "def f():\n    assert (saved := 1)\n    return saved\n"
        without = "def f():\n    return saved\n"

        assert compiled(source, 0)["f"]() == 1
        optimized = compiled(source, level)["f"]
        assert optimized.__code__.co_varnames == ("saved",)
        with pytest.raises(UnboundLocalError, match="saved"):
            optimized()

        # Written out instead, the name is a global, and resolves to one.
        namespace = compiled(without, 0)
        namespace["saved"] = "from the module"
        assert namespace["f"].__code__.co_varnames == ()
        assert namespace["f"].__code__.co_names == ("saved",)
        assert namespace["f"]() == "from the module"

    @pytest.mark.parametrize("level", [1, 2])
    def test_another_assignment_turns_the_error_into_a_different_answer(self, level: int) -> None:
        """The quieter half of the same effect, and the reason the page warns
        about binding at all rather than about one exception."""
        source = "def f():\n    saved = 2\n    assert (saved := 1)\n    return saved\n"

        assert compiled(source, 0)["f"]() == 1
        assert compiled(source, level)["f"]() == 2

    @pytest.mark.parametrize("level", [1, 2])
    def test_a_declaration_sends_the_binding_somewhere_else(self, level: int) -> None:
        """The qualification on that row: `global` and `nonlocal` decide where
        the name lives, so the dropped binding leaves the declared one alone
        rather than an unbound local."""
        declared_global = (
            "saved = 9\ndef f():\n    global saved\n    assert (saved := 1)\n    return saved\n"
        )
        declared_nonlocal = (
            "def outer():\n    saved = 9\n    def inner():\n        nonlocal saved\n"
            "        assert (saved := 1)\n        return saved\n    return inner\n"
        )

        checked = compiled(declared_global, 0)
        assert checked["f"]() == 1 and checked["saved"] == 1
        optimized = compiled(declared_global, level)
        assert optimized["f"]() == 9 and optimized["saved"] == 9

        assert compiled(declared_nonlocal, 0)["outer"]()() == 1
        assert compiled(declared_nonlocal, level)["outer"]()() == 9

    @pytest.mark.parametrize("level", [1, 2])
    def test_a_yield_inside_an_assertion_still_makes_a_generator(self, level: int) -> None:
        """A second thing the symbol table keeps: dropping the statement does
        not drop what it made the function."""
        source = "def f():\n    assert (yield True)\n    return 1\n"
        without = "def f():\n    return 1\n"

        assert inspect.isgeneratorfunction(compiled(source, 0)["f"])
        assert not inspect.isgeneratorfunction(compiled(without, 0)["f"])

        optimized = compiled(source, level)["f"]
        assert inspect.isgeneratorfunction(optimized)
        with pytest.raises(StopIteration) as stop:
            next(optimized())  # the yield is gone, so it finishes at once
        assert stop.value.value == 1

    @pytest.mark.parametrize("level", [1, 2])
    def test_the_message_binds_names_too(self, level: int) -> None:
        """Which is why the page names the statement, not its condition. The
        message is reached only on failure, so this one is unbound at every
        level rather than only the optimized ones."""
        source = "def f():\n    assert True, (saved := 1)\n    return saved\n"

        for candidate in (0, level):
            function = compiled(source, candidate)["f"]
            assert function.__code__.co_varnames == ("saved",)
            with pytest.raises(UnboundLocalError, match="saved"):
                function()

    @pytest.mark.parametrize("level", [1, 2])
    def test_a_name_read_from_an_enclosing_function_stays_a_closure(self, level: int) -> None:
        """A reference made only by an assertion keeps the enclosing cell and
        the inner free variable at every level; writing the function without
        the assertion leaves both empty."""
        source = "def outer(value):\n    def inner():\n        assert value\n        return 1\n    return inner\n"
        without = "def outer(value):\n    def inner():\n        return 1\n    return inner\n"

        for candidate in (0, level):
            outer = compiled(source, candidate)["outer"]
            assert outer.__code__.co_cellvars == ("value",)
            assert outer(True).__code__.co_freevars == ("value",)

        never_written = compiled(without, 0)["outer"]
        assert never_written.__code__.co_cellvars == ()
        assert never_written(True).__code__.co_freevars == ()

    def test_optimize_minus_one_follows_the_interpreters_flag(self) -> None:
        source = "def f(x):\n    assert x > 0\n    return x\n"

        followed = compiled(source, -1)["f"].__code__
        explicit = compiled(source, sys.flags.optimize)["f"].__code__

        assert len(followed.co_code) == len(explicit.co_code)


class TestGuardedBlocksAreDropped:
    """`if __debug__:` | O(b), and O(1) under `-O`: the branch is dead at
    compile time, but its names keep their entries in the code object."""

    def test_the_bytecode_goes_and_the_name_tables_stay(self) -> None:
        kept = compiled(GUARDED, 0)["check"].__code__
        dropped = compiled(GUARDED, 1)["check"].__code__

        assert len(dropped.co_code) < len(kept.co_code) / 2, (
            f"{len(kept.co_code)} bytes became {len(dropped.co_code)}"
        )
        assert dropped.co_names == kept.co_names
        assert dropped.co_varnames == kept.co_varnames
        assert dropped.co_nlocals == kept.co_nlocals

        # ... and so, unlike a dropped assert, it is not what never writing
        # the block would have produced.
        never_written = compiled("def check(data):\n    return len(data)\n", 0)["check"].__code__
        assert never_written.co_nlocals < dropped.co_nlocals
        assert never_written.co_code != dropped.co_code

    def test_a_large_block_leaves_almost_nothing(self) -> None:
        body = "".join(f"        x{index} = {index}\n" for index in range(200))
        source = f"def g():\n    if __debug__:\n{body}    return 1\n"

        kept = compiled(source, 0)["g"].__code__
        dropped = compiled(source, 1)["g"].__code__

        assert len(kept.co_code) > 500, f"the block compiled to {len(kept.co_code)} bytes"
        assert len(dropped.co_code) < 20, f"the dropped block left {len(dropped.co_code)} bytes"
        assert dropped.co_nlocals == kept.co_nlocals == 200

    def test_the_block_does_not_run_when_it_is_dropped(self) -> None:
        calls: list[int] = []
        source = "def g():\n    if __debug__:\n        work()\n    return 1\n"

        for level, expected in ((0, 1), (1, 0)):
            calls.clear()
            namespace: dict[str, Any] = {"work": lambda: calls.append(1)}
            exec(compile(source, "<test>", "exec", optimize=level), namespace)

            assert namespace["g"]() == 1
            assert len(calls) == expected


class TestTheInterpreterFlag:
    """`sys.flags.optimize` | O(1): what `-O` and `-OO` set, end to end."""

    SCRIPT = (
        "import sys\n"
        "def documented():\n"
        "    'a docstring'\n"
        "raised = False\n"
        "try:\n"
        "    assert False, 'boom'\n"
        "except AssertionError:\n"
        "    raised = True\n"
        # optimize=-1 takes the level from the flag this process was started with.
        "inherited = compile(\"assert x, 'kept'\", '<s>', 'exec', optimize=-1)\n"
        "print(sys.flags.optimize, __debug__, documented.__doc__ is not None, raised,\n"
        "      'kept' in inherited.co_consts)\n"
    )

    @pytest.mark.parametrize(
        ("flags", "expected"),
        [
            ((), "0 True True True True"),
            (("-O",), "1 False True False False"),
            (("-OO",), "2 False False False False"),
        ],
    )
    def test_each_level_end_to_end(self, flags: tuple[str, ...], expected: str) -> None:
        assert run_python(self.SCRIPT, *flags) == expected

    def test_the_default_level_is_what_these_tests_run_at(self) -> None:
        assert sys.flags.optimize == 0
        assert __debug__ is True


class TestVersionBoundaries:
    """The two entries in Version Notes, asserted on both sides."""

    def test_deleting_the_attribute_became_a_syntax_error_in_3_14(self) -> None:
        if sys.version_info >= (3, 14):
            with pytest.raises(SyntaxError, match="__debug__"):
                compile("del x.__debug__", "<test>", "exec")
        else:
            assert compile("del x.__debug__", "<test>", "exec") is not None

    def test_assigning_to_the_attribute_was_always_refused(self) -> None:
        with pytest.raises(SyntaxError, match="__debug__"):
            compile("x.__debug__ = 1", "<test>", "exec")

    def test_ast_parse_replaces_the_name_from_3_13(self) -> None:
        if sys.version_info >= (3, 13):
            node = ast.parse("__debug__", optimize=1).body[0].value  # type: ignore[attr-defined,call-arg]
            assert isinstance(node, ast.Constant) and node.value is False
        else:
            with pytest.raises(TypeError):
                ast.parse("__debug__", optimize=1)  # type: ignore[call-arg]

        default = ast.parse("__debug__").body[0].value  # type: ignore[attr-defined]
        assert isinstance(default, ast.Name)


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
    """Each block runs in its own subprocess, so the one that assigns to
    `builtins.__debug__` cannot reach the others."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "co_names == ()" in s)
        mutated = source.replace("co_names == ()", "co_names == ('x',)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
