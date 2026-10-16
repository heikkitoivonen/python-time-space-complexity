"""Tests for docs/builtins/list.md.

The page prices a list as a dynamic array of references: indexing and
replacing one slot are O(1), and every operation that opens or closes a gap
moves the elements after it, so its cost is the length of the tail rather than
the length of the list. Those tail terms are settled by timing the same
operation near the front and near the end of one large list, which separates
O(n - k) from O(1) by orders of magnitude; comparison counts settle `min()`,
`max()` and the adaptive sort without a stopwatch; traced allocation settles the
slice-assignment and slice-deletion space bounds.

The rows for `len()`, `l[k]`, `append()`, `pop()`, `pop(0)`, `insert(0, x)`,
`in`, `index()`, `count()`, `copy()`, `reverse()`, `clear()`, `extend()`,
slicing and the random-input sort are covered by `TestListComplexity` in
tests/test_builtin_complexity.py; this file covers the rest of the table and
the page's examples.

Measurement scope:

* `l[k] = x` costs under 3x as much on a 1,000,000-element list as on a
  1,000-element one.
* `del l[k]` is timed together with the `insert(k, ...)` that restores the
  list, so each sample pays the same O(n - k) shift twice. On a 1,000,000-
  element list, k = 0 costs over 100x what k = n - 2 does (about x35,000 on
  3.15.0, aarch64), and k = n - 2 costs under 3x as much on that list as on a
  1,000-element one, so the cost follows n - k and not n.
* `l[i:j] = t` at i = 0 of a 1,000,000-element list: a ten-element `t`
  replacing ten elements costs over 100x less than an eleven-element one, and
  the same-length case costs under 3x as much as on a 1,000-element list. An
  eleven-element `t` at i = n - 10 costs over 100x less than at i = 0, which
  is the n - i term. Inserting 100,000 elements at the end costs over 20x what
  1,000 do, which is the len(t) term. Space: replacing w elements with an
  iterator of w elements peaks over 50x higher at w = 100,000 than at w =
  1,000, and over 1 MB at w = 100,000 (the removed references plus the copied
  iterator).
* `del l[i:j]` of ten elements at i = 0 of a 1,000,000-element list costs over
  100x what it does at i = n - 10; each sample restores the ten elements at
  the same place. Deleting 100,000 elements peaks over 50x higher than
  deleting 1,000, and over 500 KB.
* `l * k`: the result has n·k elements, and 100x k at n = 100, or
  100x n at k = 10, costs over 20x more.
* `min()` and `max()` make exactly n - 1 comparisons on 1,000 elements.
  Iteration costs the same per step on a 1,000- and a 1,000,000-element list
  (the first 1,000 steps, under 3x apart).
* `sort()` makes under 2n comparisons on 10,000 sorted and 10,000 strictly
  descending elements (n - 1 on 3.11 to 3.15), against over 8n on a random
  permutation of the same size.
* `append()` resizes a list under 200 times over 1,000,000 appends and adds
  under 40 resizes going from 100,000 to 1,000,000 appends, as the "~log(n)"
  comment on the page says; resizes are counted as changes in
  `sys.getsizeof()`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The "amortized" qualifiers on `insert(k, x)`, `pop()` and `pop(k)`: the
  occasional resize is an allocator `realloc`, whose cost the tests do not
  isolate. A shrinking `pop()` that reallocates is read from
  Objects/listobject.c (`list_resize`), not measured.
* `extend(t)` paying the cost of iterating `t` is a statement about the
  caller's iterable, not the list.
* The fenced growth formula under "Dynamic Array Resizing" is pseudocode, not
  Python, and is read from `list_resize` in Objects/listobject.c; it is not
  executed.
* Element comparison cost is held at O(1) by the cost model; element types
  are small ints or a one-attribute class. Descending input with duplicate
  keys is not tested: at 10,000 and 100,000 elements it takes about 5
  comparisons per element on 3.11 and 1.5 on 3.13 and 3.15, so it stays
  linear in both, by a different constant.
"""

from __future__ import annotations

import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from itertools import islice
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "list.md"
EXPECTED_BLOCKS = 2

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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class Counted:
    """An element whose comparisons are counted."""

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
    """`del l[k]` | O(n-k): the elements after k move, the ones before do not.

    Each sample deletes and re-inserts at k, so it pays the O(n - k) shift twice.
    """

    @pytest.mark.timing
    def test_the_front_costs_far_more_than_the_end(self) -> None:
        data = list(range(LARGE))

        def at(k: int) -> Callable[[], None]:
            def step() -> None:
                del data[k]
                data.insert(k, 0)

            return step

        front_ns = best_ns(at(0))
        end_ns = best_ns(at(LARGE - 2))

        assert front_ns > end_ns * 100, (
            f"k = 0 should shift the whole list: {front_ns:.0f} vs {end_ns:.0f} ns at k = n - 2"
        )

    @pytest.mark.timing
    def test_near_the_end_the_length_does_not_matter(self) -> None:
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

        def same() -> None:
            data[0:10] = self.TEN

        def longer() -> None:
            data[0:10] = self.ELEVEN
            del data[10]

        same_ns = best_ns(same, inner=200)
        longer_ns = best_ns(longer)

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

        def at(i: int) -> Callable[[], None]:
            def step() -> None:
                data[i : i + 10] = self.ELEVEN
                del data[i + 10]

            return step

        front_ns = best_ns(at(0))
        end_ns = best_ns(at(LARGE - 10))

        assert front_ns > end_ns * 100, (
            f"i = 0 should move the whole tail: {front_ns:.0f} vs {end_ns:.0f} ns at i = n - 10"
        )

    @pytest.mark.timing
    def test_a_length_change_costs_the_new_elements(self) -> None:
        data = list(range(LARGE))
        few = list(range(1_000))
        many = list(range(100_000))

        def append_slice(items: list[int]) -> Callable[[], None]:
            def step() -> None:
                data[LARGE:LARGE] = items
                del data[LARGE:]

            return step

        few_ns = best_ns(append_slice(few))
        many_ns = best_ns(append_slice(many))

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
        ten = list(range(10))

        def front() -> None:
            del data[0:10]
            data[0:0] = ten

        def end() -> None:
            del data[LARGE - 10 : LARGE]
            data.extend(ten)

        front_ns = best_ns(front)
        end_ns = best_ns(end, inner=200)

        assert front_ns > end_ns * 100, (
            f"i = 0 should move the whole tail: {front_ns:.0f} vs {end_ns:.0f} ns at i = n - 10"
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
    """`sort()` | O(n log n) worst, O(n) on sorted or reverse-sorted input."""

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


class TestAppendResizesLogarithmically:
    """The page's example: appending a million elements resizes ~log(n) times."""

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

    def test_ten_times_the_appends_adds_a_constant_number_of_resizes(self) -> None:
        tenth = self.resizes(LARGE // 10)
        full = self.resizes(LARGE)

        assert full < 200, f"{full} resizes over 1,000,000 appends"
        assert full - tenth < 40, (
            f"10x the appends added {full - tenth} resizes ({tenth} -> {full})"
        )


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
