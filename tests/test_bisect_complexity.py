"""Tests for docs/stdlib/bisect.md.

The page prices every search by its probes - one element read, one `key`
call and one `<` comparison each - and every insort by the list insert that
follows the search. Probes are counted on a virtual sequence whose
`__getitem__` records each read, so the logarithmic bound is settled by
observation at sizes no real list could reach, with no tolerance. Only the
insert's O(n) needs a stopwatch, and there the gap between a front insert
and an end insert is orders of magnitude.

Measurement scope:

* Probes: on virtual sequences (indexable, not lists) of 2**10, 2**20 and
  2**40 items, the most
  reads any of five targets (before the start, at it, inside, at the last
  item, past the end) costs `bisect_left` and `bisect_right` is exactly
  floor(log2 n) + 1: 11, 21 and 41. An all-equal sequence searched for the
  equal value stays within the same bound for both functions. `lo` and `hi`
  bounding 16 items of a 2**40-item sequence cost at most 5 reads. Each
  read is compared exactly once, at 4,096 items for three targets.
* `key`: called once per read, on the very object read (by identity), at
  1,024 and 65,536 items;
  never called on `x` by the searches, which compare `x` as given, so a
  record passed as `x` beside an integer key raises `TypeError`. `insort_left`
  and `insort_right` call it on `x` once, then once per read.
* Space: a search over 10,000- and 1,000,000-item lists traces a peak under
  1 KB at both sizes (the returned index is an int object, so the peak is
  small, not zero), and an insort into a 1,000,000-item list with a free
  slot does too.
* Insert: the fastest of seven runs of 100 front insorts grows more than
  20x from 10,000 to 1,000,000 items, where the 100x size step predicts
  100x for O(n) and about 1.5x for O(log n); end inserts on the same lists
  grow under 5x. Each run times 100 inserts into a fresh
  list built outside the timer with room for all of them already allocated,
  so neither a removal nor a storage resize is measured. `insort_left`
  and `insort_right` on a non-list sequence call its `insert()` once, with
  the searched position.
* Batch: inserting k items in descending order one `insort` at a time grows
  more than 80x from k = 2,000 to 32,000, where O(k²) predicts 256x and
  O(k log k) about 22x. The list starts empty, so the n in O(k·(n + k)) is
  not varied; it is the per-insert O(n) measured above.
* `bisect` and `insort` are the same objects as `bisect_right` and
  `insort_right`; the left and right variants are asserted by position on
  an equal run and by where an equal-keyed record lands.
* Unsorted input returns a position without raising; on [3, 1, 4, 1, 5]
  inserting 2 there leaves the list unsorted.
* Building a 50,000-item key list costs more than 100x the one search it
  precedes, the fastest of three runs against the fastest of seven.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Treating one comparison and one key call as O(1) is a cost-model
  assumption; a costlier `__lt__` or key multiplies the probe count, which
  is what is measured.
* The O((n + k) log(n + k)) batch sort is `list.sort()`'s bound, priced on
  docs/builtins/list.md and not re-measured here.
* An insort into a full list grows the list's storage, as any
  `list.insert()` does; that is the list's cost, priced on
  docs/builtins/list.md, and the space test uses a list with a free slot.
* Element types and key costs are not varied for the insert timing, and the
  timing uses lists only.
"""

from __future__ import annotations

import bisect
import math
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "bisect.md"
EXPECTED_BLOCKS = 8

SEARCHES = (bisect.bisect_left, bisect.bisect_right)


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


class CountingInt(int):
    """An int that counts every `<` it takes part in, from either side."""

    comparisons = 0

    def __lt__(self, other: object) -> bool:
        CountingInt.comparisons += 1
        return int.__lt__(self, other)  # type: ignore[arg-type]

    def __gt__(self, other: object) -> bool:
        CountingInt.comparisons += 1
        return int.__gt__(self, other)  # type: ignore[arg-type]


class VirtualSequence:
    """A sorted sequence of `size` items that records every item read.

    It is not a list: item i is a fresh `CountingInt(i)`, or
    `CountingInt(constant)` for every index when one is given, and `insert()`
    only records its arguments.
    """

    def __init__(self, size: int, constant: int | None = None) -> None:
        self.size = size
        self.constant = constant
        self.read: list[CountingInt] = []
        self.inserts: list[tuple[int, object]] = []

    @property
    def reads(self) -> int:
        return len(self.read)

    def __len__(self) -> int:
        return self.size

    def __getitem__(self, index: int) -> CountingInt:
        item = CountingInt(index if self.constant is None else self.constant)
        self.read.append(item)
        return item

    def insert(self, index: int, item: object) -> None:
        self.inserts.append((index, item))


def most_reads(search: Callable[..., int], size: int) -> int:
    """The most reads `search` makes over five targets spanning the sequence."""
    worst = 0
    for target in (-1, 0, size // 3, size - 1, size):
        sequence = VirtualSequence(size)
        search(sequence, target)
        worst = max(worst, sequence.reads)
    return worst


class TestSearchesAreLogarithmic:
    """`bisect_left`, `bisect_right` | O(log n) | O(1).

    Counted reads and comparisons, not time: a halving search reads
    floor(log2 n) + 1 items at most and compares each once, and a scan would
    read n.
    """

    @pytest.mark.parametrize("search", SEARCHES, ids=lambda f: f.__name__)
    def test_reads_are_one_per_halving(self, search: Callable[..., int]) -> None:
        for exponent in (10, 20, 40):
            size = 2**exponent

            reads = most_reads(search, size)

            assert reads == exponent + 1, f"{search.__name__} read {reads} items of 2**{exponent}"

    @pytest.mark.parametrize("search", SEARCHES, ids=lambda f: f.__name__)
    def test_one_comparison_per_read(self, search: Callable[..., int]) -> None:
        for target in (0, 1_000, 4_095):
            sequence = VirtualSequence(4_096)
            CountingInt.comparisons = 0

            search(sequence, target)

            assert CountingInt.comparisons == sequence.reads, (
                f"{search.__name__} made {CountingInt.comparisons} comparisons "
                f"over {sequence.reads} reads"
            )

    @pytest.mark.parametrize("search", SEARCHES, ids=lambda f: f.__name__)
    def test_a_run_of_duplicates_is_searched_the_same_way(self, search: Callable[..., int]) -> None:
        for exponent in (10, 20):
            sequence = VirtualSequence(2**exponent, constant=5)

            search(sequence, 5)

            assert sequence.reads <= exponent + 1, (
                f"{search.__name__} read {sequence.reads} items of an equal run of 2**{exponent}"
            )

    def test_extra_memory_does_not_grow_with_the_list(self) -> None:
        for size in (10_000, 1_000_000):
            values = list(range(size))
            bisect.bisect_left(values, 5)

            for search in SEARCHES:
                peak = peak_bytes(partial(search, values, size // 3))
                assert peak < 1_000, f"{search.__name__} traced {peak} bytes at n={size}"


class TestLeftAndRight:
    """The two variants differ only at a run of equal items."""

    def test_left_lands_before_the_run_and_right_after(self) -> None:
        values = [1, 3, 3, 3, 5, 7, 9]

        assert bisect.bisect_left(values, 3) == 1
        assert bisect.bisect_right(values, 3) == 4
        assert bisect.bisect_left(values, 4) == bisect.bisect_right(values, 4) == 4

    def test_with_a_key_the_run_is_of_equal_keys(self) -> None:
        records = [("a", 1), ("b", 2), ("c", 2), ("d", 3)]

        def count(record: tuple[str, int]) -> int:
            return record[1]

        assert bisect.bisect_left(records, 2, key=count) == 1
        assert bisect.bisect_right(records, 2, key=count) == 3

    def test_insort_left_and_right_place_an_equal_record_either_side(self) -> None:
        marker = ("new", 2)
        left = [("a", 1), ("old", 2), ("c", 3)]
        right = list(left)

        bisect.insort_left(left, marker, key=lambda record: record[1])
        bisect.insort_right(right, marker, key=lambda record: record[1])

        assert left.index(marker) == 1
        assert right.index(marker) == 2

    def test_the_short_names_are_the_right_variants(self) -> None:
        assert bisect.bisect is bisect.bisect_right
        assert bisect.insort is bisect.insort_right


class TestLoAndHi:
    """`lo` and `hi` bound the slice searched, and the cost follows it."""

    @pytest.mark.parametrize(
        ("search", "expected"),
        ((bisect.bisect_left, 2**30 + 7), (bisect.bisect_right, 2**30 + 8)),
        ids=("bisect_left", "bisect_right"),
    )
    def test_the_cost_follows_the_slice_not_the_sequence(
        self, search: Callable[..., int], expected: int
    ) -> None:
        sequence = VirtualSequence(2**40)

        position = search(sequence, 2**30 + 7, lo=2**30, hi=2**30 + 16)

        assert position == expected
        assert sequence.reads <= 5, f"{search.__name__} read {sequence.reads} items"

    def test_the_answer_is_clamped_to_the_slice(self) -> None:
        values = list(range(100))

        assert bisect.bisect_left(values, 90, lo=10, hi=20) == 20
        assert bisect.bisect_right(values, 5, lo=10, hi=20) == 10

    def test_a_negative_lo_raises(self) -> None:
        for function in (*SEARCHES, bisect.insort_left, bisect.insort_right):
            with pytest.raises(ValueError, match="lo must be non-negative"):
                function([1, 2], 1, lo=-1)


INSORTS = (bisect.insort_left, bisect.insort_right)


class TestKeyIsCalledPerProbe:
    """`key` is applied to each item read, never to `x` by a search, and to
    `x` once by an insort."""

    @pytest.mark.parametrize("search", SEARCHES, ids=lambda f: f.__name__)
    def test_one_key_call_per_read_on_the_item_read(self, search: Callable[..., int]) -> None:
        for size in (1_024, 65_536):
            sequence = VirtualSequence(size)
            seen: list[object] = []

            def key(item: int, seen: list[object] = seen) -> int:
                seen.append(item)
                return item

            search(sequence, size // 3, key=key)

            assert len(seen) == sequence.reads <= math.log2(size) + 1
            assert all(a is b for a, b in zip(seen, sequence.read, strict=True))

    def test_a_search_does_not_call_key_on_x(self) -> None:
        records = [("a", 1), ("b", 3), ("c", 5)]
        arguments: list[tuple[str, int]] = []

        def key(record: tuple[str, int]) -> int:
            arguments.append(record)
            return record[1]

        assert bisect.bisect_right(records, 4, key=key) == 2
        assert all(argument in records for argument in arguments)

        with pytest.raises(TypeError):
            bisect.bisect_right(records, ("d", 4), key=key)

    @pytest.mark.parametrize("insort", INSORTS, ids=lambda f: f.__name__)
    def test_insort_calls_key_on_x_once_then_once_per_read(
        self, insort: Callable[..., None]
    ) -> None:
        sequence = VirtualSequence(1_024)
        item = CountingInt(300)
        arguments: list[object] = []

        def key(value: int) -> int:
            arguments.append(value)
            return value

        insort(sequence, item, key=key)

        assert arguments[0] is item
        assert all(a is b for a, b in zip(arguments[1:], sequence.read, strict=True))
        assert len(arguments) == sequence.reads + 1


class TestInsortCostIsTheInsert:
    """`insort_left`, `insort_right` | O(n) | O(1): an O(log n) search, then
    `a.insert()`, which shifts a list's tail."""

    @pytest.mark.timing
    def test_a_front_insert_grows_with_the_list(self) -> None:
        def cost(size: int, at_front: bool) -> float:
            item = -1 if at_front else size + 1
            best: float | None = None
            for _ in range(7):
                values = list(range(size + 100))
                del values[size:]  # keeps the capacity for the 100 inserts
                start = time.perf_counter_ns()
                for _ in range(100):
                    bisect.insort(values, item)
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        front = cost(1_000_000, True) / cost(10_000, True)
        end = cost(1_000_000, False) / cost(10_000, False)

        assert front > 20, f"a front insort grew only {front:.1f}x over a 100x size step"
        assert end < 5, f"an end insort grew {end:.1f}x over a 100x size step"

    @pytest.mark.parametrize(
        ("insort", "expected"),
        ((bisect.insort_left, 0), (bisect.insort_right, 4)),
        ids=("left", "right"),
    )
    def test_a_non_list_gets_one_insert_at_the_searched_position(
        self, insort: Callable[..., None], expected: int
    ) -> None:
        sequence = VirtualSequence(4, constant=3)

        insort(sequence, 3)

        assert sequence.inserts == [(expected, 3)]

    def test_insort_keeps_the_list_sorted(self) -> None:
        source = list(range(500))
        random.Random(7).shuffle(source)
        values: list[int] = []

        for item in source:
            bisect.insort(values, item)

        assert values == sorted(source)

    def test_an_insert_into_a_free_slot_allocates_little(self) -> None:
        values = list(range(1_000_000))
        values.pop(0)

        peak = peak_bytes(lambda: bisect.insort(values, -1))

        assert peak < 1_000, f"insort traced {peak} bytes"
        assert values[0] == -1


class TestBatchInsertion:
    """k inserts one at a time cost O(k·(n + k)); extending and sorting once
    gives the same list."""

    @pytest.mark.timing
    def test_k_inserts_grow_quadratically(self) -> None:
        def cost(k: int) -> float:
            items = list(range(k, 0, -1))

            def run() -> None:
                values: list[int] = []
                for item in items:
                    bisect.insort(values, item)

            return best_ns(run, repeats=3)

        growth = cost(32_000) / cost(2_000)

        assert growth > 80, f"16x the inserts cost only {growth:.1f}x"

    def test_extend_and_sort_gives_the_same_list(self) -> None:
        start = [1, 3, 5, 7, 9]
        items = [8, 2, 6, 4]
        one_at_a_time = list(start)
        for item in items:
            bisect.insort(one_at_a_time, item)

        batch = [*start, *items]
        batch.sort()

        assert batch == one_at_a_time


class TestUnsortedInput:
    """Nothing checks the order: unsorted input gives a wrong answer, not an
    error."""

    def test_an_unsorted_list_yields_a_position_that_does_not_sort(self) -> None:
        unsorted = [3, 1, 4, 1, 5]

        position = bisect.bisect(unsorted, 2)
        result = unsorted[:position] + [2] + unsorted[position:]

        assert result != sorted(result)


class TestRebuildingKeysDwarfsTheSearch:
    """Building a key list for a single search is O(n) for an O(log n)
    answer: at 50,000 items the list comprehension is asserted over 100x the
    search it precedes."""

    @pytest.mark.timing
    def test_building_the_keys_dwarfs_the_search(self) -> None:
        size = 50_000
        data = [(str(i), i) for i in range(size)]
        keys = [item[1] for item in data]

        rebuild = best_ns(lambda: [item[1] for item in data], repeats=3)
        search = best_ns(lambda: bisect.bisect_left(keys, size // 2))

        assert rebuild > search * 100, (
            f"the O(n) rebuild dwarfs the O(log n) search it precedes: "
            f"rebuild={rebuild:.0f}ns search={search:.0f}ns"
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
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
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
        line, source = next((n, s) for n, s in _blocks() if "(left, right) == (1, 4)" in s)
        mutated = source.replace("(left, right) == (1, 4)", "(left, right) == (1, 3)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
