"""Tests for docs/builtins/list.md.

The page prices a list as a dynamic array of references: indexing and
replacing one slot are O(1), and every operation that opens or closes a gap
moves the elements after it, so its cost is the length of the tail rather than
the length of the list. Those tail terms are settled by timing the same
operation near the front and near the end of one large list, which separates
O(n - k) from O(1) by orders of magnitude. Each such sample runs on a fresh copy
made outside the timer, so only the operation itself is timed. Comparison
counts settle `min()`, `max()`, the comparisons, `index()` with bounds and the
adaptive sort without a stopwatch; traced allocation settles the slice and
`reversed()` space bounds.

The rows for `len()`, `l[k]`, `append()`, `pop()`, `pop(0)`, `insert(0, x)`,
`in`, `index()`, `count()`, `copy()`, `reverse()`, `clear()`, `extend()`,
slicing and the random-input sort are covered by `TestListComplexity` in
tests/test_builtin_complexity.py; this file covers the rest of the table and
the page's examples.

Measurement scope:

* `l[k] = x` costs under 3x as much on a 1,000,000-element list as on a
  1,000-element one.
* `del l[k]`: on a 1,000,000-element list, 200 deletions at k = 0 cost over
  100x per call what 200 at k = n - 2 do (about x6,700 on 3.15.0, aarch64).
  A deletion at n - 2 followed by the insertion that restores it costs under
  3x as much on that list as on a 1,000-element one, so the cost follows
  n - k and not n.
* `l[i:j] = t` at i = 0 of a 1,000,000-element list: a ten-element `t`
  replacing ten elements costs over 100x less than an eleven-element one, and
  the same-length case costs under 3x as much as on a 1,000-element list. An
  eleven-element `t` at i = n - 12 costs over 100x less than at i = 0, which
  is the n - i term. Inserting 100,000 elements at the end of a 1,000-element
  list costs over 20x what 1,000 do, which is the len(t) term. Space: replacing w elements with an
  iterator of w elements peaks over 50x higher at w = 100,000 than at w =
  1,000, and over 1 MB at w = 100,000 (the removed references plus the copied
  iterator).
* `del l[i:j]` of ten elements at i = 0 of a 1,000,000-element list costs over
  100x what it does at i = n - 12. Deleting 100,000 elements peaks over 50x higher than
  deleting 1,000, and over 500 KB.
* `l[i:j:s] = t` replacing five elements costs under 3x as much on a
  1,000,000-element list as on a 1,000-element one; on the 1,000,000-element
  list, replacing 100,000 elements with step 2 costs over 20x, and peaks over
  50x higher, than replacing 1,000. A `t` of the wrong length raises
  `ValueError` and leaves the list unchanged. `del l[0:20:2]` and
  `del l[18::-2]` on a 1,000,000-element list each cost over 100x what
  `del l[-22:-2:2]` does, so a negative step is priced from the lowest index it
  selects. Deleting 100,000 elements with step 2 peaks over 50x higher than
  deleting 1,000, and over 500 KB.
* `l1 + l2` returns a new list. With 1,000-element operands as the base, a
  100,000-element left or right operand costs over 20x more, and 100x both
  operands peaks over 50x higher.
* `l * k`: the result has n·k elements, and 100x k at n = 100, or
  100x n at k = 10, costs over 20x more. `l *= k` keeps the object, `l *= 0`
  empties it, and from n = 100, k = 10, either 100x k or 100x n costs over 20x
  more. `l += t` keeps the
  object and accepts an iterator. Starting from 1,000 elements, batches of
  20 `+=` operations with 1,000, 10,000 and 100,000 added elements per call
  cost between 3x and 30x per tenfold step (linear predicts 10x, quadratic
  100x). The initial list copy and final list destruction are outside the
  timer; growth and resizing within each batch are included.
* With elements that count `==`, `<` and `>` and are equal only as distinct
  objects: lists of 1,000 and 1,001 elements compare no elements for `==` or
  `!=`; two equal 1,000-element lists compare 1,000, and 1 when the first
  pair differs. `<`, `<=`, `>` and `>=` between a 10- and a 1,000-element list
  with an equal prefix compare 10. `l.index(x, 500, 510)` for a missing `x`
  compares 10 elements of a 1,000-element list.
* `reversed(l)` traces the same peak, under 1 KB, on a 1,000- and a
  1,000,000-element list, and an element replaced after the iterator is made
  shows up when it is walked.
* `min()` and `max()` make exactly n - 1 comparisons on 1,000 elements.
  Iteration costs the same per step on a 1,000- and a 1,000,000-element list
  (the first 1,000 steps, under 3x apart).
* `sort()` makes under 2n comparisons on 10,000 sorted and 10,000 strictly
  descending elements (n - 1 on 3.11 to 3.15), against over 8n on a random
  permutation of the same size. Sorting 1,000 random ints calls `key` exactly
  1,000 times and a `functools.cmp_to_key()` comparison over 5,000 times.
  1,000 pairs sorted on one of ten keys keep their input order within a key.
* `append()` resizes a list under 200 times over 1,000,000 appends. Going
  from 100,000 to 1,000,000 appends adds fewer than twice the resizes that
  going from 10,000 to 100,000 does (and that is more than 5), so each tenfold
  adds about the same number: a fixed growth step would add about ten times
  as many. Resizes are counted as changes in `sys.getsizeof()`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The "amortized" qualifiers on `insert(k, x)`, `pop()`, `pop(k)` and the
  length-changing slice assignment: the occasional resize is an allocator
  `realloc`, whose cost the tests do not isolate. A shrinking `pop()` that reallocates is read from
  Objects/listobject.c (`list_resize`), not measured.
* `extend(t)` paying the cost of iterating `t` is a statement about the
  caller's iterable, not the list.
* Element comparison and `key` cost are held at O(1) by the cost model;
  element types are small ints or a one-attribute class. Descending input with duplicate
  keys is not tested: at 10,000 and 100,000 elements it takes about 5
  comparisons per element on 3.11 and 1.5 on 3.13 and 3.15, so it stays
  linear in both, by a different constant.
"""

from __future__ import annotations

import functools
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from itertools import islice, pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "list.md"
EXPECTED_BLOCKS = 5

SMALL = 1_000
LARGE = 1_000_000


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 20) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def best_ns_on_copy(
    source: list[int], operation: Callable[[list[int]], Any], count: int, repeats: int = 5
) -> float:
    """Fastest of `repeats` runs of `count` calls on a fresh copy, in ns per call.

    The copy is made outside the timer, so nothing but `operation` is timed.
    """
    best: float | None = None
    for _ in range(repeats):
        data = source.copy()
        start = time.perf_counter_ns()
        for _ in range(count):
            operation(data)
        elapsed = (time.perf_counter_ns() - start) / count
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class Counted:
    """An element whose `<`, `>` and `==` comparisons are counted."""

    comparisons = 0

    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value

    def __lt__(self, other: Counted) -> bool:
        Counted.comparisons += 1
        return self.value < other.value

    def __gt__(self, other: Counted) -> bool:
        Counted.comparisons += 1
        return self.value > other.value

    def __eq__(self, other: object) -> bool:
        Counted.comparisons += 1
        return isinstance(other, Counted) and self.value == other.value

    __hash__ = None  # type: ignore[assignment]


class TestSetItemIsConstant:
    """`l[k] = x` | O(1): replacing one slot does not depend on the length."""

    @pytest.mark.timing
    def test_a_thousand_times_the_length_costs_the_same(self) -> None:
        small = list(range(SMALL))
        large = list(range(LARGE))

        small_ns = best_ns(lambda: small.__setitem__(SMALL // 2, 1), inner=1_000)
        large_ns = best_ns(lambda: large.__setitem__(LARGE // 2, 1), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"1,000x the length cost x{ratio:.1f}: {small_ns:.0f} vs {large_ns:.0f} ns"
        )


class TestDeleteItemMovesTheTail:
    """`del l[k]` | O(n-k): the elements after k move, the ones before do not."""

    @pytest.mark.timing
    def test_the_front_costs_far_more_than_the_end(self) -> None:
        data = list(range(LARGE))

        def front(items: list[int]) -> None:
            del items[0]

        def end(items: list[int]) -> None:
            del items[-2]

        front_ns = best_ns_on_copy(data, front, 200)
        end_ns = best_ns_on_copy(data, end, 200)

        assert front_ns > end_ns * 100, (
            f"k = 0 should shift the whole list: {front_ns:.0f} vs {end_ns:.0f} ns at k = n - 2"
        )

    @pytest.mark.timing
    def test_near_the_end_the_length_does_not_matter(self) -> None:
        # Each sample deletes and re-inserts at n - 2; both are O(1) there.
        small = list(range(SMALL))
        large = list(range(LARGE))

        def near_end(data: list[int]) -> Callable[[], None]:
            k = len(data) - 2

            def step() -> None:
                del data[k]
                data.insert(k, 0)

            return step

        small_ns = best_ns(near_end(small), inner=1_000)
        large_ns = best_ns(near_end(large), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"n - k = 2 on 1,000x the length cost x{ratio:.1f}: {small_ns:.0f} vs {large_ns:.0f} ns"
        )


class TestSliceAssignmentHasTwoCases:
    """`l[i:j] = t` | O(j-i) if len(t) == j-i, otherwise O(n-i+len(t)).

    An equal-length replacement overwrites in place; any other length moves
    everything after j. The tests hold all but one term fixed.
    """

    TEN = list(range(10))
    ELEVEN = list(range(11))

    @pytest.mark.timing
    def test_equal_length_is_far_cheaper_than_one_more_element(self) -> None:
        data = list(range(LARGE))

        def same(items: list[int]) -> None:
            items[0:10] = self.TEN

        def longer(items: list[int]) -> None:
            items[0:10] = self.ELEVEN

        same_ns = best_ns_on_copy(data, same, 200)
        longer_ns = best_ns_on_copy(data, longer, 200)

        assert longer_ns > same_ns * 100, (
            f"a length change at i = 0 should move the tail: {same_ns:.0f} vs {longer_ns:.0f} ns"
        )

    @pytest.mark.timing
    def test_equal_length_does_not_depend_on_the_list(self) -> None:
        small = list(range(SMALL))
        large = list(range(LARGE))

        small_ns = best_ns(lambda: small.__setitem__(slice(0, 10), self.TEN), inner=1_000)
        large_ns = best_ns(lambda: large.__setitem__(slice(0, 10), self.TEN), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"1,000x the length cost x{ratio:.1f}: {small_ns:.0f} vs {large_ns:.0f} ns"
        )

    @pytest.mark.timing
    def test_a_length_change_costs_the_tail_after_i(self) -> None:
        data = list(range(LARGE))

        def front(items: list[int]) -> None:
            items[0:10] = self.ELEVEN

        def end(items: list[int]) -> None:
            items[-12:-2] = self.ELEVEN

        front_ns = best_ns_on_copy(data, front, 200)
        end_ns = best_ns_on_copy(data, end, 200)

        assert front_ns > end_ns * 100, (
            f"i = 0 should move the whole tail: {front_ns:.0f} vs {end_ns:.0f} ns at i = n - 12"
        )

    @pytest.mark.timing
    def test_a_length_change_costs_the_new_elements(self) -> None:
        # A short list keeps the n - i term, and the resize that growing it
        # triggers, small next to len(t).
        data = list(range(SMALL))
        few = list(range(1_000))
        many = list(range(100_000))

        def append_slice(items: list[int]) -> Callable[[list[int]], None]:
            def step(target: list[int]) -> None:
                target[SMALL:SMALL] = items

            return step

        few_ns = best_ns_on_copy(data, append_slice(few), 1, repeats=20)
        many_ns = best_ns_on_copy(data, append_slice(many), 1, repeats=20)

        ratio = many_ns / few_ns
        assert ratio > 20, (
            f"100x len(t) at the end cost only x{ratio:.1f}: {few_ns:.0f} vs {many_ns:.0f} ns"
        )

    def test_space_follows_the_replaced_and_new_elements(self) -> None:
        def replace(width: int) -> int:
            data = list(range(LARGE))
            items = list(range(width))
            return peak_bytes(lambda: data.__setitem__(slice(0, width), iter(items)))

        narrow = replace(1_000)
        wide = replace(100_000)

        assert wide > narrow * 50, f"100x the slice peaked x{wide / narrow:.1f}: {narrow} vs {wide}"
        assert wide > 1_000_000, f"replacing 100,000 elements peaked at only {wide} bytes"


class TestDeleteSliceMovesTheTail:
    """`del l[i:j]` | O(n-i) time, O(j-i) space: everything after j moves left,
    and the removed references are held until the list is consistent again."""

    @pytest.mark.timing
    def test_the_front_costs_far_more_than_the_end(self) -> None:
        data = list(range(LARGE))

        def front(items: list[int]) -> None:
            del items[0:10]

        def end(items: list[int]) -> None:
            del items[-12:-2]

        front_ns = best_ns_on_copy(data, front, 200)
        end_ns = best_ns_on_copy(data, end, 200)

        assert front_ns > end_ns * 100, (
            f"i = 0 should move the whole tail: {front_ns:.0f} vs {end_ns:.0f} ns at i = n - 12"
        )

    def test_space_follows_the_deleted_width(self) -> None:
        def delete(width: int) -> int:
            data = list(range(LARGE))
            return peak_bytes(lambda: data.__delitem__(slice(0, width)))

        narrow = delete(1_000)
        wide = delete(100_000)

        assert wide > narrow * 50, f"100x the width peaked x{wide / narrow:.1f}: {narrow} vs {wide}"
        assert wide > 500_000, f"deleting 100,000 elements peaked at only {wide} bytes"


class TestRepetitionScalesWithBothFactors:
    """`l * k` | O(nk): the result holds n·k references, and both factors move
    the cost."""

    def test_the_result_has_n_times_k_elements(self) -> None:
        base = list(range(100))
        assert len(base * 1_000) == 100_000
        assert (base * 3)[200:] == base

    @pytest.mark.timing
    def test_a_hundred_times_k_costs_far_more(self) -> None:
        base = list(range(100))

        few_ns = best_ns(lambda: base * 10, inner=100)
        many_ns = best_ns(lambda: base * 1_000)

        ratio = many_ns / few_ns
        assert ratio > 20, f"100x k cost only x{ratio:.1f}: {few_ns:.0f} vs {many_ns:.0f} ns"

    @pytest.mark.timing
    def test_a_hundred_times_n_costs_far_more(self) -> None:
        short = list(range(10))
        long = list(range(1_000))

        short_ns = best_ns(lambda: short * 10, inner=100)
        long_ns = best_ns(lambda: long * 10)

        ratio = long_ns / short_ns
        assert ratio > 20, f"100x n cost only x{ratio:.1f}: {short_ns:.0f} vs {long_ns:.0f} ns"


class TestIterationAndMinMax:
    """`for x in l` | O(n), O(1) per step; `min(l)`, `max(l)` | O(n), n-1 comparisons."""

    def test_min_and_max_compare_n_minus_one_times(self) -> None:
        values = [Counted(value) for value in random.Random(7).sample(range(10_000), SMALL)]

        Counted.comparisons = 0
        min(values)
        min_comparisons = Counted.comparisons
        Counted.comparisons = 0
        max(values)
        max_comparisons = Counted.comparisons

        assert (min_comparisons, max_comparisons) == (SMALL - 1, SMALL - 1)

    @pytest.mark.timing
    def test_a_step_costs_the_same_on_a_longer_list(self) -> None:
        small = list(range(SMALL))
        large = list(range(LARGE))

        def first_thousand(data: list[int]) -> Callable[[], None]:
            def walk() -> None:
                for _ in islice(data, SMALL):
                    pass

            return walk

        small_ns = best_ns(first_thousand(small), inner=100)
        large_ns = best_ns(first_thousand(large), inner=100)

        ratio = large_ns / small_ns
        assert ratio < 3, f"1,000 steps cost x{ratio:.1f} on 1,000x the length"


class TestSortIsAdaptive:
    """`sort()` | O(n log n); sorted or reverse-sorted input takes only O(n) comparisons."""

    SIZE = 10_000

    def comparisons(self, values: list[int]) -> int:
        items = [Counted(value) for value in values]
        Counted.comparisons = 0
        items.sort()
        assert [item.value for item in items] == sorted(values)
        return Counted.comparisons

    def test_sorted_and_reverse_sorted_input_take_linear_comparisons(self) -> None:
        ascending = self.comparisons(list(range(self.SIZE)))
        descending = self.comparisons(list(range(self.SIZE, 0, -1)))
        shuffled = self.comparisons(random.Random(42).sample(range(self.SIZE), self.SIZE))

        assert ascending < 2 * self.SIZE, f"sorted input took {ascending:,} comparisons"
        assert descending < 2 * self.SIZE, f"reverse-sorted input took {descending:,} comparisons"
        assert shuffled > 8 * self.SIZE, f"random input took only {shuffled:,} comparisons"


class TestAppendResizesGeometrically:
    """`append(x)` | O(1) amortized: each resize reserves room in proportion to
    the length, so the number of resizes grows with log n and not with n."""

    @staticmethod
    def resizes(count: int) -> int:
        data: list[int] = []
        changes = 0
        last = sys.getsizeof(data)
        for value in range(count):
            data.append(value)
            size = sys.getsizeof(data)
            if size != last:
                changes += 1
                last = size
        return changes

    def test_each_tenfold_adds_about_the_same_number_of_resizes(self) -> None:
        hundredth = self.resizes(LARGE // 100)
        tenth = self.resizes(LARGE // 10)
        full = self.resizes(LARGE)

        first, second = tenth - hundredth, full - tenth
        assert full < 200, f"{full} resizes over 1,000,000 appends"
        assert 5 < first and second < 2 * first, (
            f"10,000 -> 100,000 added {first} resizes, 100,000 -> 1,000,000 added {second}"
        )


class TestExtendedSlices:
    """`l[i:j:s] = t` | O(m); `del l[i:j:s]` | O(n-i) time, O(m) space, where the
    slice selects m elements and i is the lowest index it selects."""

    @pytest.mark.timing
    def test_assignment_does_not_depend_on_the_list(self) -> None:
        five = list(range(5))

        def assign(items: list[int]) -> None:
            items[0:10:2] = five

        small_ns = best_ns_on_copy(list(range(SMALL)), assign, 2_000)
        large_ns = best_ns_on_copy(list(range(LARGE)), assign, 2_000)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"1,000x the length cost x{ratio:.1f}: {small_ns:.0f} vs {large_ns:.0f} ns"
        )

    @pytest.mark.timing
    def test_assignment_costs_the_selected_elements(self) -> None:
        data = list(range(LARGE))
        few = list(range(1_000))
        many = list(range(100_000))

        def assign(items: list[int]) -> Callable[[list[int]], None]:
            def step(target: list[int]) -> None:
                target[0 : 2 * len(items) : 2] = items

            return step

        few_ns = best_ns_on_copy(data, assign(few), 1, repeats=20)
        many_ns = best_ns_on_copy(data, assign(many), 1, repeats=20)

        ratio = many_ns / few_ns
        assert ratio > 20, f"100x m cost only x{ratio:.1f}: {few_ns:.0f} vs {many_ns:.0f} ns"

    def test_assignment_space_follows_the_selected_elements(self) -> None:
        def assign(count: int) -> int:
            data = list(range(LARGE))
            items = list(range(count))
            return peak_bytes(lambda: data.__setitem__(slice(0, 2 * count, 2), iter(items)))

        narrow = assign(1_000)
        wide = assign(100_000)

        assert wide > narrow * 50, f"100x m peaked x{wide / narrow:.1f}: {narrow} vs {wide}"

    def test_assignment_needs_exactly_the_slice_length(self) -> None:
        data = list(range(8))
        with pytest.raises(ValueError, match="size 2 to extended slice of size 4"):
            data[::2] = [0, 0]
        assert data == list(range(8))

    @pytest.mark.timing
    def test_deletion_at_the_front_costs_far_more_than_at_the_end(self) -> None:
        data = list(range(LARGE))

        def front(items: list[int]) -> None:
            del items[0:20:2]

        def end(items: list[int]) -> None:
            del items[-22:-2:2]

        def front_backwards(items: list[int]) -> None:
            del items[18::-2]

        front_ns = best_ns_on_copy(data, front, 200)
        backwards_ns = best_ns_on_copy(data, front_backwards, 200)
        end_ns = best_ns_on_copy(data, end, 200)

        assert front_ns > end_ns * 100, (
            f"i = 0 should move the whole tail: {front_ns:.0f} vs {end_ns:.0f} ns at i = n - 22"
        )
        assert backwards_ns > end_ns * 100, (
            f"a negative step down to index 0 should move the whole tail: "
            f"{backwards_ns:.0f} vs {end_ns:.0f} ns"
        )

    def test_deletion_space_follows_the_slice_length(self) -> None:
        def delete(count: int) -> int:
            data = list(range(LARGE))
            return peak_bytes(lambda: data.__delitem__(slice(0, 2 * count, 2)))

        narrow = delete(1_000)
        wide = delete(100_000)

        assert wide > narrow * 50, f"100x the slice peaked x{wide / narrow:.1f}: {narrow} vs {wide}"
        assert wide > 500_000, f"deleting 100,000 elements peaked at only {wide} bytes"


class TestInPlaceOperators:
    """`l += t` | same as `l.extend(t)`, same object; `l *= k` | O(nk), in place,
    and k <= 0 clears the list."""

    def test_plus_equals_extends_the_same_object(self) -> None:
        data = [1, 2]
        alias = data
        data += iter([3, 4])
        assert data is alias and data == [1, 2, 3, 4]

    @pytest.mark.timing
    def test_plus_equals_costs_the_added_elements(self) -> None:
        def add(items: list[int]) -> Callable[[list[int]], None]:
            def step(data: list[int]) -> None:
                data += items

            return step

        source = list(range(SMALL))
        durations = [
            best_ns_on_copy(source, add(list(range(size))), count=20, repeats=7)
            for size in (1_000, 10_000, 100_000)
        ]
        ratios = [after / before for before, after in pairwise(durations)]

        assert all(3 < ratio < 30 for ratio in ratios), f"+=: {durations} ns, x{ratios}"

    def test_times_equals_repeats_the_same_object(self) -> None:
        data = [1, 2, 3]
        alias = data
        data *= 4
        assert data is alias and data == [1, 2, 3] * 4
        data *= 0
        assert data is alias and data == []

    @pytest.mark.timing
    def test_times_equals_costs_n_times_k(self) -> None:
        base = list(range(100))

        def repeat(k: int) -> Callable[[list[int]], None]:
            def step(data: list[int]) -> None:
                data *= k

            return step

        few_ns = best_ns_on_copy(base, repeat(10), 1, repeats=50)
        many_ns = best_ns_on_copy(base, repeat(1_000), 1, repeats=50)
        long_ns = best_ns_on_copy(list(range(10_000)), repeat(10), 1, repeats=50)

        ratio = many_ns / few_ns
        assert ratio > 20, f"100x k cost only x{ratio:.1f}: {few_ns:.0f} vs {many_ns:.0f} ns"
        ratio = long_ns / few_ns
        assert ratio > 20, f"100x n cost only x{ratio:.1f}: {few_ns:.0f} vs {long_ns:.0f} ns"


class TestComparisonsStopEarly:
    """`l1 == l2` | O(n), O(1) when the lengths differ; `<`, `<=`, `>`, `>=` |
    O(min(len(l1), len(l2))). Equal elements are distinct objects, so the
    identity shortcut never answers for `==`."""

    @staticmethod
    def counted(values: range) -> list[Counted]:
        return [Counted(value) for value in values]

    def test_different_lengths_compare_no_elements(self) -> None:
        short, long = self.counted(range(1_000)), self.counted(range(1_001))
        Counted.comparisons = 0
        assert short != long and not short == long
        assert Counted.comparisons == 0

    def test_equal_lengths_stop_at_the_first_unequal_pair(self) -> None:
        left, right = self.counted(range(1_000)), self.counted(range(1_000))
        Counted.comparisons = 0
        assert left == right
        assert Counted.comparisons == 1_000

        right[0] = Counted(-1)
        Counted.comparisons = 0
        assert left != right
        assert Counted.comparisons == 1

    def test_ordering_compares_the_shorter_length(self) -> None:
        short, long = self.counted(range(10)), self.counted(range(1_000))
        for compare in (
            lambda: short < long,
            lambda: short <= long,
            lambda: long > short,
            lambda: long >= short,
        ):
            Counted.comparisons = 0
            assert compare()
            assert Counted.comparisons == 10


class TestIndexWithBoundsSearchesTheRegion:
    """`l.index(x, i, j)` | O(j-i): only `l[i:j]` is compared."""

    def test_a_missing_value_compares_j_minus_i_elements(self) -> None:
        data = [Counted(value) for value in range(1_000)]
        Counted.comparisons = 0
        with pytest.raises(ValueError):
            data.index(Counted(-1), 500, 510)
        assert Counted.comparisons == 10


class TestConcatenationBuildsANewList:
    """`l1 + l2` | O(len(l1)+len(l2)) time and space: a new list holding both."""

    def test_the_result_is_a_new_list_of_both_lengths(self) -> None:
        left, right = list(range(3)), list(range(3, 5))
        result = left + right
        assert result == [0, 1, 2, 3, 4]
        assert result is not left and left == [0, 1, 2]

    @pytest.mark.timing
    def test_each_operand_moves_the_cost(self) -> None:
        short = list(range(1_000))
        long = list(range(100_000))

        both_short_ns = best_ns(lambda: short + short, inner=100)
        long_left_ns = best_ns(lambda: long + short)
        long_right_ns = best_ns(lambda: short + long)

        for name, ns in (("left", long_left_ns), ("right", long_right_ns)):
            ratio = ns / both_short_ns
            assert ratio > 20, f"a 100x {name} operand cost only x{ratio:.1f}"

    def test_space_follows_both_operands(self) -> None:
        short = list(range(1_000))
        long = list(range(100_000))

        small = peak_bytes(lambda: short + short)
        large = peak_bytes(lambda: long + long)

        assert large > small * 50, f"100x the operands peaked x{large / small:.1f}"


class TestReversedIsLazy:
    """`reversed(l)` | O(1) time and space: it allocates the same iterator for
    any length, and walks the list only as it is consumed."""

    def test_the_iterator_does_not_grow_with_the_list(self) -> None:
        small = list(range(SMALL))
        large = list(range(LARGE))

        small_peak = peak_bytes(lambda: reversed(small))
        large_peak = peak_bytes(lambda: reversed(large))

        assert large_peak <= small_peak < 1_024, f"{small_peak} vs {large_peak} bytes"

    def test_walking_it_reads_the_list_as_it_goes(self) -> None:
        data = list(range(SMALL))
        walker = reversed(data)
        data[0] = -1
        assert list(walker) == [*range(SMALL - 1, 0, -1), -1]


class TestSortIsStable:
    """`sort()` is stable: elements with equal keys keep their order."""

    def test_equal_keys_keep_their_input_order(self) -> None:
        pairs = [(value % 10, index) for index, value in enumerate(range(1_000, 0, -1))]
        pairs.sort(key=lambda pair: pair[0])
        for (key, index), (next_key, next_index) in pairwise(pairs):
            assert key < next_key or index < next_index


class TestSortKeyIsCalledOncePerElement:
    """`key` is called once per element; a `cmp_to_key` comparison function once
    per comparison, which is far more than n on random input."""

    SIZE = 1_000

    def test_key_and_comparison_call_counts(self) -> None:
        values = random.Random(3).sample(range(10 * self.SIZE), self.SIZE)
        key_calls = 0
        compare_calls = 0

        def key(value: int) -> int:
            nonlocal key_calls
            key_calls += 1
            return value

        def compare(left: int, right: int) -> int:
            nonlocal compare_calls
            compare_calls += 1
            return left - right

        by_key, by_compare = values.copy(), values.copy()
        by_key.sort(key=key)
        by_compare.sort(key=functools.cmp_to_key(compare))

        assert by_key == by_compare == sorted(values)
        assert key_calls == self.SIZE
        assert compare_calls > 5 * self.SIZE, f"only {compare_calls:,} comparisons"


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
        line, source = next((n, s) for n, s in _blocks() if "lst[0] == -1" in s)
        mutated = source.replace("lst[0] == -1", "lst[0] == 0", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
