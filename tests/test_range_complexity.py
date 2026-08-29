"""Tests for the int/float divergence in range, documented in docs/builtins/range.md.

`range` is the one built-in sequence whose membership test is not a search.
`999_999 in range(1_000_000)` solves `start + step*k == value` for an integer
k and answers in constant time. That shortcut is the whole reason the
complexity table prices `in`, `index()` and `count()` at O(1).

It only applies to integers. Hand the same operations a float and CPython
falls back to `_PySequence_IterSearch`, which walks the range one value at a
time - O(n), and measurably so: on this machine a float membership test over
a million elements is around 80,000 times slower than the int it compares
equal to.

Two things make the divergence easy to get wrong, and both are pinned below:

* the answer does not change, only the cost. `2.0 in range(3)` is True, it
  just gets there the slow way, so nothing in a test suite or a type checker
  will point at the code that does it
* the fast path is `PyLong_CheckExact() || PyBool_Check()`. `bool` is special
  cased and gets the shortcut, but any other `int` subclass does not - it
  scans, exactly like a float

The constructor draws the line in a different place, and rejects the float
outright rather than converting it, even when the value is whole.

Nor will a type checker save you. typeshed types `index()` and `count()` as
taking an int, so those calls need a `type: ignore` below - but
`__contains__` takes an object, so `2.0 in range(10)` type checks cleanly.
The one form that is silently O(n) is the one nothing warns about.
"""

import time
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest


def trimmed_mean(samples: list[float], trim_fraction: float = 0.1) -> float:
    """Return the trimmed mean to reduce outlier impact."""
    if not samples:
        return 0.0
    if trim_fraction <= 0:
        return sum(samples) / len(samples)
    k = int(len(samples) * trim_fraction)
    if len(samples) - 2 * k <= 0:
        return sum(samples) / len(samples)
    samples = sorted(samples)
    core = samples[k : len(samples) - k]
    return sum(core) / len(core)


def measure_time(func: Callable[[], Any], iterations: int = 100) -> float:
    """Measure trimmed mean time for a function over multiple iterations."""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return trimmed_mean(times)


def best_time(func: Callable[[], Any], repeats: int = 3) -> float:
    """Return the fastest of several runs, for operations too slow to repeat."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def is_constant_time(small_time: float, large_time: float, tolerance: float = 3.0) -> bool:
    """Check if two times are within tolerance (suggesting O(1))."""
    if small_time == 0:
        return large_time < 1e-6
    return large_time / small_time < tolerance


def is_linear_time(
    small_time: float,
    large_time: float,
    size_ratio: float,
    tolerance: float = 3.0,
) -> bool:
    """Check if time scales linearly with size."""
    if small_time == 0:
        return True
    return large_time / small_time < size_ratio * tolerance


class _MyInt(int):
    """An int subclass, which is not what CPython's fast path checks for."""


class _Indexable:
    """An object usable as a range bound through __index__."""

    def __index__(self) -> int:
        return 5


class TestConstructorRequiresIntegers:
    """range() rejects floats outright - it does not convert them.

    docs/builtins/range.md prices construction at O(1) for every form, which
    holds, but the argument has to be an integer to get there at all.
    """

    def test_whole_float_is_still_rejected(self) -> None:
        # 3.0 == 3, and range() still refuses it.
        with pytest.raises(TypeError, match="cannot be interpreted as an integer"):
            range(3.0)  # type: ignore[arg-type]

    def test_fractional_float_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="cannot be interpreted as an integer"):
            range(3.5)  # type: ignore[arg-type]

    def test_float_step_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="cannot be interpreted as an integer"):
            range(0, 10, 2.0)  # type: ignore[arg-type]

    def test_bool_is_accepted_as_an_int(self) -> None:
        assert list(range(True)) == [0]

    def test_index_protocol_is_accepted(self) -> None:
        # Not an int, but it can become one, so the constructor takes it.
        assert list(range(_Indexable())) == [0, 1, 2, 3, 4]


class TestMembershipIsConstantOnlyForIntegers:
    """`in` is O(1) for an exact int and O(n) for anything else.

    The complexity table's footnote on `in` is the claim under test.
    """

    SMALL_SIZE = 100_000
    LARGE_SIZE = 1_000_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    @pytest.mark.timing
    def test_int_membership_is_constant_time(self) -> None:
        small, large = range(self.SMALL_SIZE), range(self.LARGE_SIZE)

        small_time = measure_time(lambda: (self.SMALL_SIZE - 1) in small)
        large_time = measure_time(lambda: (self.LARGE_SIZE - 1) in large)

        assert is_constant_time(small_time, large_time), (
            f"int membership should solve an equation, not scan: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_float_membership_scales_with_the_range(self) -> None:
        small, large = range(self.SMALL_SIZE), range(self.LARGE_SIZE)

        small_time = best_time(lambda: float(self.SMALL_SIZE - 1) in small)
        large_time = best_time(lambda: float(self.LARGE_SIZE - 1) in large)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"float membership should scan: {small_time:.2e}s vs {large_time:.2e}s"
        )
        assert large_time > small_time * 3, (
            "a ten times longer range should cost visibly more for a float"
        )

    @pytest.mark.timing
    def test_float_is_dramatically_slower_than_the_equal_int(self) -> None:
        values = range(self.LARGE_SIZE)
        target = self.LARGE_SIZE - 1
        assert float(target) == target, "the two lookups must be for equal values"

        int_time = best_time(lambda: target in values)
        float_time = best_time(lambda: float(target) in values)

        assert float_time > int_time * 100, (
            f"same value, same answer, different algorithm: "
            f"int={int_time:.2e}s float={float_time:.2e}s"
        )


class TestOnlyExactIntsAndBoolsTakeTheFastPath:
    """The check is PyLong_CheckExact() or PyBool_Check().

    bool is special cased, so it gets the shortcut. Every other int subclass
    scans, which the table's "int/bool" wording does not lead you to expect.
    """

    SIZE = 1_000_000

    @pytest.mark.timing
    def test_bool_takes_the_fast_path(self) -> None:
        values = range(self.SIZE)

        bool_time = measure_time(lambda: True in values)
        int_time = measure_time(lambda: 1 in values)

        assert is_constant_time(int_time, bool_time), (
            f"bool is special cased alongside int: int={int_time:.2e}s bool={bool_time:.2e}s"
        )

    @pytest.mark.timing
    def test_int_subclass_does_not(self) -> None:
        values = range(self.SIZE)
        target = self.SIZE - 1

        int_time = best_time(lambda: target in values)
        subclass_time = best_time(lambda: _MyInt(target) in values)

        assert subclass_time > int_time * 100, (
            f"an int subclass scans like a float: int={int_time:.2e}s subclass={subclass_time:.2e}s"
        )

    def test_int_subclass_still_answers_correctly(self) -> None:
        assert _MyInt(5) in range(10)
        assert _MyInt(15) not in range(10)


class TestIndexAndCountSplitTheSameWay:
    """index() and count() carry the same footnote, and the same behaviour."""

    SIZE = 200_000

    @pytest.mark.timing
    def test_index_is_constant_for_an_int(self) -> None:
        values = range(self.SIZE)

        early = measure_time(lambda: values.index(1))
        late = measure_time(lambda: values.index(self.SIZE - 1))

        assert is_constant_time(early, late), (
            f"index() should solve for k, not search: {early:.2e}s vs {late:.2e}s"
        )

    @pytest.mark.timing
    def test_index_scans_for_a_float(self) -> None:
        values = range(self.SIZE)

        int_time = best_time(lambda: values.index(self.SIZE - 1))
        float_time = best_time(
            lambda: values.index(float(self.SIZE - 1))  # type: ignore[arg-type]
        )

        assert float_time > int_time * 100, (
            f"index() falls back to a scan for a float: int={int_time:.2e}s float={float_time:.2e}s"
        )

    @pytest.mark.timing
    def test_count_scans_for_a_float(self) -> None:
        values = range(self.SIZE)

        int_time = best_time(lambda: values.count(self.SIZE - 1))
        float_time = best_time(
            lambda: values.count(float(self.SIZE - 1))  # type: ignore[arg-type]
        )

        assert float_time > int_time * 100, (
            f"count() falls back to a scan for a float: int={int_time:.2e}s float={float_time:.2e}s"
        )


class TestTheSlowPathStillGivesTheRightAnswer:
    """Only the cost changes. That is what makes the divergence easy to miss."""

    def test_whole_float_is_a_member(self) -> None:
        assert 2.0 in range(3)

    def test_fractional_float_is_not(self) -> None:
        assert 2.5 not in range(3)

    def test_index_accepts_a_whole_float(self) -> None:
        assert range(10).index(2.0) == 2  # type: ignore[arg-type]

    def test_index_rejects_a_fractional_float(self) -> None:
        with pytest.raises(ValueError, match="not in"):
            range(10).index(2.5)  # type: ignore[arg-type]

    def test_count_accepts_a_whole_float(self) -> None:
        assert range(10).count(2.0) == 1  # type: ignore[arg-type]
        assert range(10).count(2.5) == 0  # type: ignore[arg-type]

    def test_other_numeric_types_compare_equal_too(self) -> None:
        # Fraction and Decimal take the same scan as float, for the same
        # reason: neither is an exact int.
        assert Fraction(2, 1) in range(3)
        assert Decimal("2") in range(3)
        assert Fraction(5, 2) not in range(3)

    @pytest.mark.timing
    def test_a_missing_float_still_costs_a_full_scan(self) -> None:
        # The worst case for the slow path is an answer of False: every value
        # has to be compared before the range can say no.
        size = 200_000
        values = range(size)

        present = best_time(lambda: float(size - 1) in values)
        absent = best_time(lambda: -1.0 in values)

        assert is_constant_time(present, absent, tolerance=3.0), (
            f"both walk the whole range: present={present:.2e}s absent={absent:.2e}s"
        )
