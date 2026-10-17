"""Tests for docs/builtins/range.md.

A range stores `start`, `stop`, `step` and its length and computes each item
on demand, so the page's distinctive claim is that most operations do not
depend on the length. The strongest evidence for that needs no stopwatch: a
range of 10**20 items cannot be walked in any test run, so every operation
that answers on one does not walk it. The search fallback for arguments that
are not an exact `int` or a `bool` is settled by counting the `__eq__` calls of
a probe object, and its cost against the int path by timing.

The rows for `len()`, `r[k]` and `x in r` are also timed by
`TestRangeComplexity` in tests/test_builtin_complexity.py.

Measurement scope:

* Construction: a whole float, a fractional float and a float step raise
  `TypeError`; a step of 0 raises `ValueError`; a `bool` and an object with
  `__index__` are accepted. Building `range(10)` and `range(10**18)` (both
  machine-sized bounds) costs under 3x apart. `start`, `stop` and `step` are
  the arguments as ints: `range(0, 10, 3).stop` is 10, and a `bool` or
  `__index__` argument is stored as an exact `int`.
* Operations on `range(10**20)`, which no test could walk: `r[-1]`, a step-2
  slice, `10**19 in r`, `index()` and `count()` of an int, `==` with an
  equal range built from other arguments, `hash()`, `bool()`, and the first
  item of `reversed()` all answer (an empty range is false); `len()` raises `OverflowError` because the
  length exceeds `sys.maxsize`.
* `len()` of a five-item range over bounds of 1,000 and 100,000 decimal
  digits costs the same (under 3x), while building those two ranges costs
  more than 10x: the length is stored at construction. Indexing and an int
  membership test on the 100,000-digit bounds each cost more than 10x what
  they do on the 1,000-digit bounds, which is the page's note that wide
  bounds make the arithmetic rows cost more.
* The search fallback, counted with a probe whose `__eq__` counts its calls
  over `range(1_000)`: `in` and `index()` make 6 calls to find 5 and stop;
  `count()` makes 1,000. An `int` subclass with a counting `__eq__` makes 6
  calls for `in`. An absent `True`, `False` and int are answered on ranges
  of about 10**20 items, one with a negative step, so they are not searched; a
  `bool` argument and negative-step ranges give the int path's answers.
* `in` with an int costs the same on 100,000 and 1,000,000 items, under 3x;
  with a float it grows between 3x and 30x, and costs over 100x the equal
  int. An `int` subclass costs over 100x the int. `True` absent from ranges
  of 1,000 and 1,000,000 items starting at 2 costs the same, under 3x.
* `index()` and `count()` of the last int cost the same on 1,000 and
  10,000,000 items, under 3x; of the last item as a float they grow between
  3x and 30x from 20,000 to 200,000 items and cost over 100x the int at
  200,000. A float present at the end and one absent cost within 3x of each
  other, both full scans. Whole floats, `Fraction` and `Decimal` give the
  same answers as ints.
* `r[i:j]` is a range and costs the same over 1,000 and 10,000,000 items,
  under 3x. `==` between equal distinct ranges of 10 and 10,000,000 items
  costs the same, under 3x; `range(0) == range(5, 5)`, `range(0, 10, 3) ==
  range(0, 11, 3)` and their hashes match; a range is never equal to the
  list of its items; ordering comparisons raise `TypeError`.
* Iterating a 1,000,000-item range traces a peak under 4 KiB and no more
  than 1 KiB above a 10,000-item range, after one warm-up walk. `list()` of 1,000,000 items traces over 50x the peak of
  10,000. `min()` and `max()` over 1,000,000 items cost between 10x and
  1,000x what they do over 10,000.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* How fast the cost of wide bounds grows is not asserted, only that it grows:
  the membership test divides by `step`, and the width of `step` against the
  bounds was not varied. Iterating a range whose items do not fit in a
  machine word, and `index()` or `count()` on one, were not timed.
* The source behind every bound, `Objects/rangeobject.c`, gives the same
  growth class on every release from 3.11.14 to 3.15.0, so the page has no
  version notes; the `ValueError` message of `index()` changes in 3.14, and
  the tests match only "not in".
"""

from __future__ import annotations

import operator
import pathlib
import sys
import time
import tracemalloc
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

from tests.page_examples import DOCS, failing_blocks, python_blocks, run_block

PAGE = DOCS / "builtins" / "range.md"
EXPECTED_BLOCKS = 5

HUGE = 10**20


def trimmed_mean(samples: list[float], trim_fraction: float = 0.1) -> float:
    """Return the trimmed mean to reduce outlier impact."""
    k = int(len(samples) * trim_fraction)
    core = sorted(samples)[k : len(samples) - k] or samples
    return sum(core) / len(core)


def measure_time(func: Callable[[], Any], iterations: int = 100) -> float:
    """Trimmed mean time of a fast operation over many iterations."""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return trimmed_mean(times)


def best_time(func: Callable[[], Any], repeats: int = 3) -> float:
    """Fastest of several runs, for operations too slow to repeat."""
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


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak traced allocation, in bytes, while `func` runs."""
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class _MyInt(int):
    """An int subclass, which is not what CPython's fast path checks for."""


class _CountedInt(int):
    """An int subclass whose `__eq__` counts its calls; as a subclass it is
    asked first when an exact int compares with it."""

    calls = 0
    __hash__ = int.__hash__

    def __eq__(self, other: object) -> bool:
        _CountedInt.calls += 1
        return int(self) == other


class _Indexable:
    """An object usable as a range bound through __index__."""

    def __index__(self) -> int:
        return 5


class _Probe:
    """Compares equal to one int and counts every comparison made with it."""

    calls = 0
    __hash__ = None  # type: ignore[assignment]

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        _Probe.calls += 1
        return other == self.value


class TestConstruction:
    """`range(stop)`, `range(start, stop[, step])` | O(1): integer arguments only."""

    def test_whole_float_is_still_rejected(self) -> None:
        with pytest.raises(TypeError, match="cannot be interpreted as an integer"):
            range(3.0)  # type: ignore[arg-type]

    def test_fractional_float_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="cannot be interpreted as an integer"):
            range(3.5)  # type: ignore[arg-type]

    def test_float_step_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="cannot be interpreted as an integer"):
            range(0, 10, 2.0)  # type: ignore[arg-type]

    def test_a_zero_step_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not be zero"):
            range(0, 10, 0)

    def test_bool_is_accepted_as_an_int(self) -> None:
        assert list(range(True)) == [0]

    def test_index_protocol_is_accepted(self) -> None:
        assert list(range(_Indexable())) == [0, 1, 2, 3, 4]

    def test_the_arguments_are_kept_as_ints(self) -> None:
        r = range(0, 10, 3)
        assert (r.start, r.stop, r.step) == (0, 10, 3)
        assert list(r) == [0, 3, 6, 9]
        assert type(range(True).stop) is int and range(True).stop == 1
        assert type(range(_Indexable()).stop) is int and range(_Indexable()).stop == 5

    @pytest.mark.timing
    def test_building_costs_the_same_whatever_the_length(self) -> None:
        small = measure_time(lambda: range(10))
        large = measure_time(lambda: range(10**18))
        assert is_constant_time(small, large), f"{small:.2e}s vs {large:.2e}s"


class TestNothingWalksTheRange:
    """Indexing, slicing, int search, `==`, `hash()`, `bool()` and `reversed()`
    answer on a range of 10**20 items, which no test could walk."""

    def test_indexing_and_slicing(self) -> None:
        r = range(HUGE)
        assert r[-1] == HUGE - 1
        assert r[::2] == range(0, HUGE, 2)

    def test_searching_for_an_int(self) -> None:
        r = range(HUGE)
        assert 10**19 in r
        assert r.index(10**19) == 10**19
        assert r.count(10**19) == 1

    def test_equality_hashing_and_truth(self) -> None:
        r = range(HUGE)
        twin = range(0, HUGE, 1)
        assert r is not twin and r == twin
        assert hash(r) == hash(twin)
        assert bool(r)
        assert not range(0) and not range(5, 5)

    def test_reversed_starts_at_the_end(self) -> None:
        assert next(reversed(range(HUGE))) == HUGE - 1

    def test_len_raises_beyond_maxsize(self) -> None:
        assert HUGE > sys.maxsize
        with pytest.raises(OverflowError):
            len(range(HUGE))


class TestTheLengthIsStored:
    """`len()` | O(1): computed once when the range is built, then read.

    Bounds of 1,000 and 100,000 decimal digits make computing the length
    cost something - comparing and subtracting the bounds reads every digit -
    so building such a range scales with the digits, while `len()` of a
    five-item range over them costs the same at both widths. The bounds are
    built outside the timing.
    """

    @pytest.mark.timing
    def test_len_does_not_recompute_from_the_bounds(self) -> None:
        narrow_base, wide_base = 10**1_000, 10**100_000
        narrow_stop, wide_stop = narrow_base + 5, wide_base + 5
        narrow, wide = range(narrow_base, narrow_stop), range(wide_base, wide_stop)

        reading = measure_time(lambda: len(wide)) / measure_time(lambda: len(narrow))
        building = best_time(lambda: range(wide_base, wide_stop), repeats=7) / best_time(
            lambda: range(narrow_base, narrow_stop), repeats=7
        )

        assert len(narrow) == len(wide) == 5
        assert reading < 3, f"len() over 100x wider bounds cost x{reading:.2f}"
        assert building > 10, f"building over 100x wider bounds cost only x{building:.2f}"


class TestWideBoundsCostMore:
    """Bounds thousands of digits long make the arithmetic rows cost more."""

    @pytest.mark.timing
    def test_indexing_and_int_membership_grow_with_the_digits(self) -> None:
        narrow_base, wide_base = 10**1_000, 10**100_000
        narrow = range(narrow_base, narrow_base + 1_000)
        wide = range(wide_base, wide_base + 1_000)
        narrow_item, wide_item = narrow_base + 500, wide_base + 500

        for name, on_narrow, on_wide in (
            ("r[k]", lambda: narrow[500], lambda: wide[500]),
            ("x in r", lambda: narrow_item in narrow, lambda: wide_item in wide),
        ):
            ratio = best_time(on_wide, repeats=7) / best_time(on_narrow, repeats=7)
            assert ratio > 10, f"{name} over 100x wider bounds cost only x{ratio:.2f}"


class TestSearchFallsBackForOtherTypes:
    """`x in r`, `index()`, `count()` | O(1) for an exact int or bool, O(n) otherwise.

    A probe that is not an int is compared with the items one at a time; its
    `__eq__` counts the comparisons, so the scan is observed directly.
    """

    def test_in_stops_at_the_match(self) -> None:
        _Probe.calls = 0
        assert _Probe(5) in range(1_000)
        assert _Probe.calls == 6

    def test_index_stops_at_the_match(self) -> None:
        _Probe.calls = 0
        assert range(1_000).index(_Probe(5)) == 5  # type: ignore[arg-type]
        assert _Probe.calls == 6

    def test_count_reads_every_item(self) -> None:
        _Probe.calls = 0
        assert range(1_000).count(_Probe(5)) == 1  # type: ignore[arg-type]
        assert _Probe.calls == 1_000

    def test_an_int_subclass_is_searched_too(self) -> None:
        _CountedInt.calls = 0
        assert _CountedInt(5) in range(1_000)
        assert _CountedInt.calls == 6

    def test_an_exact_int_or_bool_is_not(self) -> None:
        assert True not in range(2, HUGE)
        assert range(2, HUGE).count(False) == 0
        assert -1 not in range(HUGE, 0, -1)
        assert range(10).index(True) == 1
        assert range(10).count(False) == 1
        assert True in range(10, 0, -1)
        assert range(10, 0, -2).index(4) == 3
        assert 5 not in range(10, 0, -2)


class TestMembershipIsConstantOnlyForIntegers:
    """`in` is O(1) for an exact int or a bool and O(n) for anything else."""

    SMALL_SIZE = 100_000
    LARGE_SIZE = 1_000_000

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

        assert small_time * 3 < large_time < small_time * 30, (
            f"float membership should scan: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_float_is_far_slower_than_the_equal_int(self) -> None:
        values = range(self.LARGE_SIZE)
        target = self.LARGE_SIZE - 1
        assert float(target) == target

        int_time = best_time(lambda: target in values)
        float_time = best_time(lambda: float(target) in values)

        assert float_time > int_time * 100, f"int={int_time:.2e}s float={float_time:.2e}s"

    @pytest.mark.timing
    def test_bool_takes_the_fast_path(self) -> None:
        """An absent bool, so a scan would have to read the whole range: in
        ranges of 1,000 and 1,000,000 items starting at 2 it costs the same."""
        small, large = range(2, 1_002), range(2, 2 + self.LARGE_SIZE)

        small_time = measure_time(lambda: True in small)
        large_time = measure_time(lambda: True in large)

        assert is_constant_time(small_time, large_time), (
            f"bool is special cased alongside int: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_an_int_subclass_costs_far_more_than_the_int(self) -> None:
        values = range(self.LARGE_SIZE)
        target = self.LARGE_SIZE - 1

        int_time = best_time(lambda: target in values)
        subclass_time = best_time(lambda: _MyInt(target) in values)

        assert subclass_time > int_time * 100, f"int={int_time:.2e}s subclass={subclass_time:.2e}s"

    def test_int_subclass_still_answers_correctly(self) -> None:
        assert _MyInt(5) in range(10)
        assert _MyInt(15) not in range(10)


class TestIndexAndCountSplitTheSameWay:
    """index() and count() take the int path for an int and scan for a float."""

    SMALL_SIZE = 20_000
    SIZE = 200_000

    @pytest.mark.timing
    def test_index_and_count_of_an_int_cost_the_same_whatever_the_length(self) -> None:
        small, large = range(1_000), range(10_000_000)

        for name, on_small, on_large in (
            ("index", lambda: small.index(999), lambda: large.index(9_999_999)),
            ("count", lambda: small.count(999), lambda: large.count(9_999_999)),
        ):
            small_time, large_time = measure_time(on_small), measure_time(on_large)
            assert is_constant_time(small_time, large_time), (
                f"{name}(): {small_time:.2e}s vs {large_time:.2e}s"
            )

    @pytest.mark.timing
    def test_index_and_count_of_a_float_scale_with_the_range(self) -> None:
        small, large = range(self.SMALL_SIZE), range(self.SIZE)
        small_last, large_last = float(self.SMALL_SIZE - 1), float(self.SIZE - 1)

        for name, on_small, on_large in (
            ("index", lambda: small.index(small_last), lambda: large.index(large_last)),  # type: ignore[arg-type]
            ("count", lambda: small.count(small_last), lambda: large.count(large_last)),  # type: ignore[arg-type]
        ):
            small_time, large_time = best_time(on_small), best_time(on_large)
            assert small_time * 3 < large_time < small_time * 30, (
                f"{name}(): {small_time:.2e}s vs {large_time:.2e}s"
            )

    @pytest.mark.timing
    def test_index_and_count_of_a_float_cost_far_more_than_an_int(self) -> None:
        values = range(self.SIZE)
        last = self.SIZE - 1

        for name, with_int, with_float in (
            ("index", lambda: values.index(last), lambda: values.index(float(last))),  # type: ignore[arg-type]
            ("count", lambda: values.count(last), lambda: values.count(float(last))),  # type: ignore[arg-type]
        ):
            int_time, float_time = best_time(with_int), best_time(with_float)
            assert float_time > int_time * 100, (
                f"{name}(): int={int_time:.2e}s float={float_time:.2e}s"
            )


class TestTheSlowPathStillGivesTheRightAnswer:
    """Only the cost changes, which is what makes the fallback easy to miss."""

    def test_whole_float_is_a_member(self) -> None:
        assert 2.0 in range(3)
        assert 2.5 not in range(3)

    def test_index_and_count_accept_a_whole_float(self) -> None:
        assert range(10).index(2.0) == 2  # type: ignore[arg-type]
        assert range(10).count(2.0) == 1  # type: ignore[arg-type]
        assert range(10).count(2.5) == 0  # type: ignore[arg-type]

    def test_index_rejects_an_absent_value(self) -> None:
        with pytest.raises(ValueError, match="not in"):
            range(10).index(2.5)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="not in"):
            range(10).index(20)

    def test_other_numeric_types_compare_equal_too(self) -> None:
        assert Fraction(2, 1) in range(3)
        assert Decimal("2") in range(3)
        assert Fraction(5, 2) not in range(3)

    @pytest.mark.timing
    def test_a_missing_float_still_costs_a_full_scan(self) -> None:
        size = 200_000
        values = range(size)

        present = best_time(lambda: float(size - 1) in values)
        absent = best_time(lambda: -1.0 in values)

        assert present / 3 < absent < present * 3, (
            f"both walk the whole range: present={present:.2e}s absent={absent:.2e}s"
        )


class TestSlicingIsConstant:
    """`r[i:j]`, `r[i:j:s]` | O(1) | O(1): a new range, whatever it covers."""

    def test_a_slice_is_a_range(self) -> None:
        values = range(10, 100, 5)

        assert values[1:4] == range(15, 30, 5)
        assert values[::-2] == range(95, 5, -10)
        assert type(values[2:]) is range

    @pytest.mark.timing
    def test_a_slice_costs_the_same_whatever_it_covers(self) -> None:
        small, large = range(1_000), range(10_000_000)

        small_time = measure_time(lambda: small[1:-1])
        large_time = measure_time(lambda: large[1:-1])

        assert is_constant_time(small_time, large_time), (
            f"slicing appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestEqualityAndHashing:
    """`r == other`, `hash(r)` | O(1): equal when they give the same items."""

    def test_ranges_are_equal_by_their_items(self) -> None:
        assert range(0) == range(5, 5)
        assert range(0, 10, 3) == range(0, 11, 3)
        assert range(0, 10, 3) != range(0, 13, 3)

    def test_equal_ranges_hash_alike(self) -> None:
        assert hash(range(0)) == hash(range(5, 5))
        assert hash(range(0, 10, 3)) == hash(range(0, 11, 3))

    def test_a_range_never_equals_a_list_or_tuple(self) -> None:
        assert range(3) != [0, 1, 2]
        assert range(3) != (0, 1, 2)

    def test_ranges_are_not_ordered(self) -> None:
        left: Any = range(3)
        right: Any = range(4)
        for compare in (operator.lt, operator.le, operator.gt, operator.ge):
            with pytest.raises(TypeError):
                compare(left, right)

    @pytest.mark.timing
    def test_equality_costs_the_same_whatever_the_length(self) -> None:
        small, small_twin = range(10), range(0, 10, 1)
        large, large_twin = range(10_000_000), range(0, 10_000_000, 1)

        small_time = measure_time(lambda: small == small_twin)
        large_time = measure_time(lambda: large == large_twin)

        assert is_constant_time(small_time, large_time), f"{small_time:.2e}s vs {large_time:.2e}s"


class TestIterationHoldsOneItem:
    """Iterating `r` | O(n) | O(1); `list(r)` | O(n) | O(n)."""

    def test_iterating_allocates_nothing_that_grows(self) -> None:
        def walk(values: range) -> None:
            for _ in values:
                pass

        walk(range(1_000))
        small = traced_peak(lambda: walk(range(10_000)))
        large = traced_peak(lambda: walk(range(1_000_000)))
        assert large < 4 * 1024 and large <= small + 1024, f"{small} vs {large} bytes"

    def test_a_list_holds_every_item(self) -> None:
        small = traced_peak(lambda: list(range(10_000)))
        large = traced_peak(lambda: list(range(1_000_000)))
        assert large > small * 50, f"{small} vs {large} bytes"


class TestMinAndMaxIterate:
    """`min(r)`, `max(r)` | O(n): the builtins walk every item; the ends are
    `r[0]` and `r[-1]`."""

    def test_the_ends_are_the_extremes(self) -> None:
        values = range(10, 100, 5)

        assert min(values) == values[0] == 10
        assert max(values) == values[-1] == 95

    @pytest.mark.timing
    def test_min_and_max_scale_with_the_range(self) -> None:
        small, large = range(10_000), range(1_000_000)

        for name, function in (("min", min), ("max", max)):
            small_time = best_time(lambda function=function: function(small), repeats=5)
            large_time = best_time(lambda function=function: function(large), repeats=5)

            assert large_time > small_time * 10, (
                f"{name}() over 100x the range cost x{large_time / small_time:.1f}"
            )
            assert large_time < small_time * 1_000, (
                f"{name}() over 100x the range cost x{large_time / small_time:.1f}"
            )


class TestDocumentedExamples:
    """Each block runs in its own interpreter and defines every name it uses."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PAGE)) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PAGE, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_failing_assertion(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(PAGE) if "assert 51 not in r" in s)
        mutated = source.replace("assert 51 not in r", "assert 51 in r", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0
