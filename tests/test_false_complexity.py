"""Tests for docs/builtins/false.md.

`False` is the static `_Py_FalseStruct` in Objects/boolobject.c, one of the two
instances of `bool`. Every row of the page's table acts on that object, so its
O(1) bounds hold by construction: there is no size variable to grow, and no
timing test is needed. What the tests settle is what the rows and the prose say
beyond the bound - which object an operation returns, which operands it calls or
evaluates, how the compiler treats the keyword - by identity checks, bytecode
inspection and call counters, which need no tolerance.

Measurement scope:

* one object: `bool()`, `bool(x)` for falsy built-in values and a falsy
  `__bool__`, `1 > 2`, `1 == 2`, `'a' in 'xyz'` and `not True` return `False`
  itself;
  `type(False)` is `bool`, a subclass of `int`; calling `bool.__new__` with
  `0` and pickling, `copy.copy()` and `copy.deepcopy()` return the singleton;
* the keyword: assigning to `False` is a SyntaxError; `False` compiles to a
  constant, with no LOAD_NAME, LOAD_GLOBAL, LOAD_FAST or LOAD_DEREF
  instruction, in module and function bodies; a namespace whose
  `__builtins__` maps 'False' to another object still reads the singleton;
* three tests for False over [False, 0, 0.0, None, '', [], ()]: `not v` is true
  for all, `v is False` only for False, `v == False` for False, 0 and 0.0; a
  `__eq__` that answers True makes `x == False` true and is called once, while
  `x is False` calls nothing;
* integer behaviour: `int(False)` is 0, `False + False` is the int 0, and
  `sum()` over booleans counts the True ones; `hash(False)` is 0 and equals
  `hash(0)` and `hash(0.0)`; `{False: 'no', 0: 'zero'}` is one entry whose key
  is `False` and whose value is 'zero', and in the reverse order the key is
  the int 0; a set of `False`, `0` and `0.0` has the one member `False`;
* `str(False)` and `repr(False)` are 'False' and return the same string
  object on every call; allocation inside the call is not traced;
* short-circuiting: `False and f()` calls a counting `f` zero times and is
  False; `False or y` calls it once and returns its result by identity;
* `~False` is -1 and `~True` is -2, and each emits a DeprecationWarning
  exactly when `sys.version_info >= (3, 12)`, on whichever interpreter runs
  the test;
* every fenced Python block runs in its own subprocess with warnings as
  errors, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The cost of `x`'s truth test in `not x` and `bool(x)` is `x`'s type's; the
  page links bool() for it, and tests/test_bool_func_complexity.py measures it.
  The O(1) for `x == False` on built-in values holds because each compares
  against a fixed-size zero; it is not timed.
* The O(n) annotations in the examples are the cost of one O(1) test per item
  in a list comprehension or `sum()`; the examples pin results only.
* `False or y` is checked for returning `y` by identity, not for whether `y`'s
  own truth test runs.
"""

from __future__ import annotations

import builtins
import copy
import dis
import operator
import pathlib
import pickle
import re
import subprocess
import sys
import textwrap
import warnings
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "false.md"
EXPECTED_BLOCKS = 4

FALSY_VALUES: list[object] = [False, 0, 0.0, None, "", [], ()]
NAME_LOADS = {"LOAD_NAME", "LOAD_GLOBAL", "LOAD_FAST", "LOAD_DEREF"}


class Falsy:
    """An object whose `__bool__` answers False and counts its calls."""

    def __init__(self) -> None:
        self.calls = 0

    def __bool__(self) -> bool:
        self.calls += 1
        return False


class TestOneObject:
    """Intro, The Singleton, and rows `bool()`, `bool(x)` and `type(False)`:
    every route returns the one `False` object."""

    @pytest.mark.parametrize("value", [0, 0.0, "", b"", [], (), {}, set(), range(0), None])
    def test_bool_of_a_falsy_builtin_is_the_singleton(self, value: object) -> None:
        assert bool(value) is False

    def test_bool_with_no_argument_is_false(self) -> None:
        make_bool: Any = bool
        assert make_bool() is False

    def test_bool_of_a_custom_falsy_object_is_the_singleton(self) -> None:
        value = Falsy()

        assert bool(value) is False

        assert value.calls == 1

    def test_builtin_comparisons_return_the_singleton(self) -> None:
        one, two = 1, 2
        assert (one > two) is False
        assert (one == two) is False
        assert ("a" in "xyz") is False
        assert (not True) is False

    def test_the_type_is_bool_a_subclass_of_int(self) -> None:
        flag = False
        assert type(flag) is bool
        assert isinstance(False, int)
        assert issubclass(bool, int)

    def test_constructing_and_copying_return_the_singleton(self) -> None:
        assert bool.__new__(bool, 0) is False
        assert copy.copy(False) is False
        assert copy.deepcopy(False) is False

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_a_pickle_round_trip_returns_the_singleton(self, protocol: int) -> None:
        assert pickle.loads(pickle.dumps(False, protocol=protocol)) is False


class TestKeyword:
    """Row `False` and the intro: a keyword compiled to a constant, with no
    name lookup, that cannot be assigned or shadowed."""

    @pytest.mark.parametrize(
        "source", ["False = 1", "False += 1", "for False in []: pass", "def f(False): pass"]
    )
    def test_assignment_is_a_syntax_error(self, source: str) -> None:
        with pytest.raises(SyntaxError):
            compile(source, "<test>", "exec")

    def test_assignment_message_names_false(self) -> None:
        with pytest.raises(SyntaxError, match="cannot assign to False"):
            compile("False = 1", "<test>", "exec")

    def test_module_code_loads_a_constant(self) -> None:
        code = compile("x = False", "<test>", "exec")
        instructions = list(dis.get_instructions(code))

        assert not NAME_LOADS & {i.opname for i in instructions}
        assert any(i.opname == "LOAD_CONST" and i.argval is False for i in instructions)

    def test_function_code_loads_no_name(self) -> None:
        def returns_false() -> bool:
            return False

        instructions = list(dis.get_instructions(returns_false))

        assert not NAME_LOADS & {i.opname for i in instructions}
        assert "False" not in returns_false.__code__.co_names
        assert any(
            i.opname in {"LOAD_CONST", "RETURN_CONST"} and i.argval is False for i in instructions
        )
        assert returns_false() is False

    def test_shadowed_builtins_do_not_change_it(self) -> None:
        namespace: dict[str, Any] = {"__builtins__": {"False": "shadow"}}

        exec("result = False", namespace)

        assert namespace["result"] is False
        assert getattr(builtins, "False") is False


class TestTestingForFalse:
    """Rows `x is False`, `x == False` and `not x`, and Testing for False."""

    def test_not_is_true_for_every_falsy_value(self) -> None:
        assert [v for v in FALSY_VALUES if not v] == FALSY_VALUES

    def test_is_false_matches_only_false(self) -> None:
        matched = [v for v in FALSY_VALUES if v is False]

        assert len(matched) == 1
        assert matched[0] is False

    def test_eq_false_matches_false_and_the_zeros(self) -> None:
        matched = [v for v in FALSY_VALUES if operator.eq(v, False)]

        assert matched == [False, 0, 0.0]
        assert [type(v) for v in matched] == [bool, int, float]

    def test_none_does_not_equal_false(self) -> None:
        assert operator.eq(None, False) is False

    def test_an_operand_eq_can_answer_and_is_calls_nothing(self) -> None:
        class EqualsEverything:
            calls = 0

            def __eq__(self, other: object) -> bool:
                EqualsEverything.calls += 1
                return True

            __hash__ = object.__hash__

        value = EqualsEverything()

        assert (value is False) is False
        assert EqualsEverything.calls == 0
        assert operator.eq(value, False) is True
        assert EqualsEverything.calls == 1


class TestInteger:
    """Rows `int(False)`, `False + False` and `hash(False)`, and False as an
    Integer."""

    def test_int_and_arithmetic(self) -> None:
        assert int(False) == 0
        assert type(int(False)) is int
        total = False + False
        assert total == 0
        assert type(total) is int

    def test_sum_counts_the_true_ones(self) -> None:
        data = [3, -1, 4, -1, 5]
        assert sum(x < 0 for x in data) == 2

    def test_hash_is_zero_like_the_zeros(self) -> None:
        assert hash(False) == 0
        assert hash(False) == hash(0) == hash(0.0)

    def test_false_and_zero_are_one_dict_key(self) -> None:
        pairs: list[tuple[object, str]] = [(False, "no"), (0, "zero")]
        table = dict(pairs)

        assert len(table) == 1
        (key,) = table
        assert key is False
        assert table[0] == "zero"

    def test_the_first_key_inserted_is_kept(self) -> None:
        pairs: list[tuple[object, str]] = [(0, "zero"), (False, "no")]
        table = dict(pairs)

        (key,) = table
        assert key == 0
        assert type(key) is int
        assert table[False] == "no"

    def test_false_and_the_zeros_are_one_set_member(self) -> None:
        members: list[object] = [False, 0, 0.0]
        (member,) = set(members)
        assert member is False


class TestStrRepr:
    """Row `str(False)`, `repr(False)`."""

    def test_text(self) -> None:
        assert str(False) == "False"
        assert repr(False) == "False"

    def test_each_call_returns_the_same_string(self) -> None:
        assert str(False) is str(False)
        assert repr(False) is str(False)


class TestShortCircuit:
    """Rows `False and y` and `False or y`, and Short-Circuiting."""

    def test_and_does_not_evaluate_y(self) -> None:
        calls = 0

        def expensive() -> list[int]:
            nonlocal calls
            calls += 1
            return [1]

        flag = False
        assert (flag and expensive()) is False
        assert calls == 0

    def test_or_returns_y_itself(self) -> None:
        payload = [1, 2, 3]
        calls = 0

        def expensive() -> list[int]:
            nonlocal calls
            calls += 1
            return payload

        flag = False
        result = flag or expensive()

        assert calls == 1
        assert result is payload


class TestInvert:
    """Row `~False` and Version Notes: the int -1, with a DeprecationWarning
    from 3.12."""

    @pytest.mark.parametrize(("flag", "expected"), [(False, -1), (True, -2)])
    def test_invert_returns_an_int_and_warns_from_3_12(self, flag: bool, expected: int) -> None:
        value: Any = flag
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = ~value

        assert result == expected
        assert type(result) is int
        deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecations) == (1 if sys.version_info >= (3, 12) else 0)

    def test_not_is_the_negation(self) -> None:
        assert (not False) is True
        assert ~int(False) == -1


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-W", "error", script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs with warnings as errors, under the interpreter running
    the tests."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "table = {False" in source)
        broken = block.replace("assert table == {False: 'zero'}", "assert table == {0: 'no'}", 1)
        assert broken != block, "the mutation did not change the dict assertion"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
