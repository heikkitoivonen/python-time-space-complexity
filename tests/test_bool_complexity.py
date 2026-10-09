"""Tests for docs/builtins/bool.md.

`bool` is PyBool_Type in Objects/boolobject.c: a subclass of int whose only two
instances are the static objects True and False, each a one-digit int. The
table's operations act on those two values, so their O(1) bounds hold by
construction: there is no size variable to grow. What the tests settle is what
the rows and the prose say beyond the bound - which object an operation
returns, what type it is, how many truth tests and operand evaluations a
logical operator makes, and that a built-in truth test does not scan its
operand. Those are observed directly (identity, a counting `__bool__`, a call
counter); only the built-in truth test needs a stopwatch.

Measurement scope:

* only two instances: bool(x), comparisons and `&`, `|`, `^` on bool operands
  return the True or False object itself; bool cannot be subclassed;
* operator results: every bool pair gives the int result for `+`, `-`, `*`, a
  bool for `&`, `|`, `^`, and `~` gives the int -2 or -1; hash(), int() and
  str() give 1/0, the int 1/0 and "True"/"False", and repeated str() calls
  return the same string object;
* mixed operands: `&`, `|`, `^` with a bool and a non-bool int return an int,
  in both operand orders;
* `~` on a bool warns with DeprecationWarning from 3.12 and is silent before;
* `and`, `or`, `not`: one truth test of the operand they examine, the right
  operand not evaluated once the left decides, and an operand returned as is;
* custom objects: `__bool__` is used and `__len__` is not called when both
  exist, `__len__` is used without `__bool__`, and an object with neither is
  truthy;
* built-in truth tests are O(1): bool() of a list, tuple, set, frozenset or dict
  holding 1,000 counting items makes no item truth test, and the time of bool()
  on a str, list and int moves by less than x5 from 10 to 1,000,000 characters,
  items or 30-bit digits, where a scan would grow x100,000;
* aggregation: an `and`/`or` chain stops at the deciding condition, while
  all()/any() over a list literal evaluate every condition first;
* bitwise `&` evaluates its right side when the left is False;
* the `and`/`or` conditional idiom falls through to the else value when the
  true value is falsy;
* every fenced block runs in a subprocess with warnings as errors. The asserts
  in a block pin its stated values; the two blocks of bare `if ...: pass`
  statements (Boolean Context and Boolean Aggregation) are pinned by
  TestStatedTruthValues and TestAggregation.

Not settled here:

* "the language guarantees" two instances is a documentation fact (the
  Python reference's standard type hierarchy and the bool() docs); the tests
  check that CPython honours it, not that every implementation does.
* The cost of evaluating an operand, and of a custom `__bool__` or `__len__`,
  is the caller's; the page names it once and the tests hold it at O(1).
* The built-in truth-test timing covers str, list and int, and the item-count
  check covers list, tuple, set, frozenset and dict. The other built-ins
  (bytes, range, float, dict views and the rest) are not measured.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import timeit
import warnings
from collections.abc import Callable

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "bool.md"
EXPECTED_BLOCKS = 8
BOOLS = (False, True)
PAIRS = [(a, b) for a in BOOLS for b in BOOLS]


class Counted:
    """An object whose truth tests are counted."""

    tests = 0

    def __init__(self, truthy: bool) -> None:
        self.truthy = truthy

    def __bool__(self) -> bool:
        Counted.tests += 1
        return self.truthy


def fastest_ns(statement: str, namespace: dict[str, object], number: int = 20_000) -> float:
    """Fastest of several runs of `statement`, in nanoseconds per call."""
    timer = timeit.Timer(statement, globals=namespace)
    return min(timer.repeat(repeat=7, number=number)) / number * 1e9


class TestOnlyTwoInstances:
    """Intro and Boolean Caching: True and False are the only two instances,
    and bool(x) returns x itself for a bool."""

    @pytest.mark.parametrize("value", BOOLS)
    def test_bool_of_a_bool_is_the_same_object(self, value: bool) -> None:
        assert bool(value) is value

    def test_conversions_and_comparisons_return_the_two_objects(self) -> None:
        one, zero = 1, 0
        assert (one > zero) is True
        assert bool(one) is True
        assert bool([]) is False

    @pytest.mark.parametrize(("a", "b"), PAIRS)
    def test_bitwise_operators_return_the_two_objects(self, a: bool, b: bool) -> None:
        assert (a & b) is (a and b)
        assert (a | b) is (a or b)
        assert (a ^ b) is (a != b)

    def test_bool_cannot_be_subclassed(self) -> None:
        with pytest.raises(TypeError):
            type("MyBool", (bool,), {})

    def test_bool_is_an_int_subclass(self) -> None:
        assert issubclass(bool, int)
        assert True == 1 and False == 0  # noqa: E712
        flag, one = True, 1
        assert type(flag) is bool and type(one) is int


class TestOperatorResults:
    """Operations table: what each row's operator returns on bool operands."""

    @pytest.mark.parametrize(("a", "b"), PAIRS)
    def test_arithmetic_returns_an_int(self, a: bool, b: bool) -> None:
        for result, expected in ((a + b, int(a) + int(b)), (a - b, int(a) - int(b))):
            assert type(result) is int
            assert result == expected
        assert type(a * b) is int
        assert a * b == int(a) * int(b)
        assert True + True == 2

    @pytest.mark.parametrize(("a", "b"), PAIRS)
    def test_comparisons_follow_the_ints(self, a: bool, b: bool) -> None:
        x, y = int(a), int(b)
        assert (a < b) is (x < y) and (a > b) is (x > y)
        assert (a <= b) is (x <= y) and (a >= b) is (x >= y)
        assert (a == b) is (x == y) and (a != b) is (x != y)

    @pytest.mark.parametrize("value", BOOLS)
    def test_bitwise_with_a_non_bool_int_returns_an_int(self, value: bool) -> None:
        other = 2
        pairs = ((value & other, other & value), (value | other, other | value))
        pairs += ((value ^ other, other ^ value),)
        for result, swapped in pairs:
            assert type(result) is int and type(swapped) is int
            assert result == swapped
        assert (value & other) == 0
        assert (value | other) == (value ^ other) == int(value) + 2

    def test_hash_int_and_str(self) -> None:
        assert (hash(True), hash(False)) == (1, 0)
        assert type(int(True)) is int and int(True) == 1 and int(False) == 0
        assert (str(True), str(False)) == ("True", "False")

    @pytest.mark.parametrize("value", BOOLS)
    def test_repeated_str_calls_return_the_same_string(self, value: bool) -> None:
        assert str(value) is str(value)

    @pytest.mark.parametrize(("value", "expected"), [(True, -2), (False, -1)])
    def test_invert_returns_an_int_not_the_negation(self, value: bool, expected: int) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = ~value
        assert type(result) is int
        assert result == expected


class TestInvertDeprecation:
    """Version Notes: `~` on a bool warns from 3.12."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the warning starts in 3.12")
    def test_invert_warns_from_3_12(self) -> None:
        value = True
        with pytest.warns(DeprecationWarning, match="Bitwise inversion"):
            _ = ~value

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="the warning starts in 3.12")
    def test_invert_is_silent_before_3_12(self) -> None:
        value = True
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert ~value == -2


class TestLogicalOperators:
    """Logical Operations table: one truth test of the operand examined, the
    right operand skipped once the left decides, an operand returned as is."""

    def test_and_stops_at_a_falsy_left_operand(self) -> None:
        Counted.tests = 0
        left = Counted(False)
        evaluated: list[str] = []

        result = left and evaluated.append("right")

        assert result is left
        assert Counted.tests == 1
        assert evaluated == []

    def test_or_stops_at_a_truthy_left_operand(self) -> None:
        Counted.tests = 0
        left = Counted(True)
        evaluated: list[str] = []

        result = left or evaluated.append("right")

        assert result is left
        assert Counted.tests == 1
        assert evaluated == []

    def test_a_deciding_right_operand_is_returned_untested(self) -> None:
        Counted.tests = 0
        right = Counted(False)
        assert (Counted(True) and right) is right
        assert (Counted(False) or right) is right
        assert Counted.tests == 2, "only the left operands were truth-tested"

    def test_not_makes_one_truth_test(self) -> None:
        Counted.tests = 0
        assert (not Counted(False)) is True
        assert Counted.tests == 1


class TestCustomObjectTruth:
    """Boolean Context row: `__bool__` if defined, else `__len__`; truthy if
    neither."""

    def test_bool_wins_over_len(self) -> None:
        calls: list[str] = []

        class Both:
            def __bool__(self) -> bool:
                calls.append("bool")
                return False

            def __len__(self) -> int:
                calls.append("len")
                return 1

        assert bool(Both()) is False
        assert calls == ["bool"]

    def test_len_is_used_without_bool(self) -> None:
        class Sized:
            def __len__(self) -> int:
                return 0

        assert bool(Sized()) is False

    def test_neither_is_truthy(self) -> None:
        class Plain:
            pass

        assert bool(Plain()) is True


class TestBuiltinTruthTestIsConstant:
    """Intro and Boolean Context example: a truth test is O(1) for the
    built-in types - a container's length is read, its items are not tested."""

    @pytest.mark.parametrize("kind", [list, tuple, set, frozenset, dict.fromkeys])
    def test_containers_test_no_item(self, kind: type) -> None:
        items = [Counted(False) for _ in range(1_000)]
        container = kind(items)
        Counted.tests = 0

        assert bool(container) is True
        assert Counted.tests == 0

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "build",
        [
            pytest.param(lambda size: "x" * size, id="str"),
            pytest.param(lambda size: [0] * size, id="list"),
            pytest.param(lambda size: 1 << (30 * size), id="int"),
        ],
    )
    def test_time_does_not_grow_with_size(self, build: Callable[[int], object]) -> None:
        small_ns = fastest_ns("bool(value)", {"value": build(10)})
        large_ns = fastest_ns("bool(value)", {"value": build(1_000_000)})

        ratio = large_ns / small_ns
        assert ratio < 5, f"bool() at size 1,000,000 costs x{ratio:.1f} size 10"


class TestStatedTruthValues:
    """Boolean Context table and example: the truth value each row states."""

    def test_stated_truth_values(self) -> None:
        falsy: list[object] = [False, 0, 0.0, 0j, "", [], None]
        truthy: list[object] = [True, 1, -1, 0.5, "hello", "0", [1, 2, 3]]
        assert [bool(value) for value in falsy] == [False] * len(falsy)
        assert [bool(value) for value in truthy] == [True] * len(truthy)


class TestAggregation:
    """Boolean Aggregation: a chain stops at the deciding condition; all() and
    any() over a list literal evaluate every condition first."""

    @staticmethod
    def recorder(calls: list[int]) -> Callable[[int], bool]:
        def positive(value: int) -> bool:
            calls.append(value)
            return value > 0

        return positive

    def test_and_chain_stops_at_the_first_false_condition(self) -> None:
        calls: list[int] = []
        positive = self.recorder(calls)
        x, y, z = 1, -2, 3

        assert not (positive(x) and positive(y) and positive(z))
        assert calls == [1, -2]

    def test_or_chain_stops_at_the_first_true_condition(self) -> None:
        calls: list[int] = []
        positive = self.recorder(calls)
        x, y, z = 1, -2, 3

        assert positive(x) or positive(y) or positive(z)
        assert calls == [1]

    def test_all_and_any_over_a_list_evaluate_every_condition(self) -> None:
        calls: list[int] = []
        positive = self.recorder(calls)
        x, y, z = 1, -2, 3

        assert all([positive(x), positive(y), positive(z)]) is False  # noqa: C419
        assert calls == [1, -2, 3]
        calls.clear()
        assert any([positive(x), positive(y), positive(z)]) is True  # noqa: C419
        assert calls == [1, -2, 3]


class TestShortCircuitOptimization:
    """Performance Characteristics and Avoid list: `&` evaluates both sides."""

    def test_bitwise_and_evaluates_the_right_side(self) -> None:
        calls: list[str] = []

        def operation() -> bool:
            calls.append("called")
            return True

        condition = False
        assert (condition and operation()) is False
        assert calls == []
        assert (condition & operation()) is False
        assert calls == ["called"]


class TestConditionalIdiom:
    """Conditional Expressions: `c and t or f` is wrong when t is falsy."""

    def test_falsy_true_value_falls_through(self) -> None:
        condition = True
        assert (condition and "yes" or "no") == "yes"
        assert (condition and 0 or "no") == "no"
        assert (0 if condition else "no") == 0


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
        block = next(source for _, source in _blocks() if "expensive_function()" in source)
        broken = block.replace(
            "x = False and expensive_function()", "x = True and expensive_function()", 1
        )
        assert broken != block, "the mutation did not change the left operand"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
