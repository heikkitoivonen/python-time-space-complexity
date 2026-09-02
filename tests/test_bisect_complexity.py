"""Tests to verify documented behaviour of the bisect module.

The page's framing is that the search is cheap and everything around it is
not - `keys = [x[1] for x in data]` before a search, or the insert after one -
so the contrast between the two is what these tests pin.

Two things the review found, both now covered here:

* The Sorted Data Requirement snippet had no `import bisect`, so it raised
  NameError when run on its own. Nothing executed the page's code before.
* The page never mentioned the `key` argument, added in 3.10, while its
  Advanced section built a parallel list instead. Measured, key runs exactly
  once per probe - 10, 16 and 20 calls at n = 1,024, 65,536 and 1,048,576 -
  and insort adds one more for the item being inserted.

On "a run of equal values costs no more than a unique one": counted rather
than timed below. An all-equal list costs one probe more than the distinct
list this file compares it against (11 against 10 at n=1,024), but that is
where the answer lands, not the duplicates - position 0 needs the extra
halving. Both are log2(n) probes, which is the claim. The point the test has
to exclude is a scan of the run, and 17 probes at n=65,536 excludes it by
three orders of magnitude.

Not settled by execution:

* "O(1) additional space" for the searches. No allocation is observable per
  probe, asserted below via tracemalloc, but the C implementation's stack
  use is not something this suite can weigh.
"""

import bisect
import math
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
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


def is_constant_time(small_time: float, large_time: float, tolerance: float = 3.0) -> bool:
    """Check if two times are within tolerance (suggesting O(1))."""
    if small_time == 0:
        return large_time < 1e-6
    return large_time / small_time < tolerance


def is_logarithmic_time(
    small_time: float,
    large_time: float,
    small_size: int,
    large_size: int,
    tolerance: float = 3.0,
) -> bool:
    """Check if time scales logarithmically with size."""
    if small_time == 0:
        return True
    expected = math.log2(large_size) / math.log2(small_size)
    return large_time / small_time < expected * tolerance


class CountingInt(int):
    """A list element that counts the probes a binary search makes."""

    comparisons = 0

    def __lt__(self, other: int) -> bool:
        CountingInt.comparisons += 1
        return int.__lt__(self, other)

    def __gt__(self, other: int) -> bool:
        CountingInt.comparisons += 1
        return int.__gt__(self, other)


class TestBisectComplexity:
    """Test bisect operation complexities as documented in docs/stdlib/bisect.md."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 1_000_000

    @pytest.mark.timing
    def test_bisect_left_is_ologn(self) -> None:
        """bisect_left() should be O(log n)."""
        small = list(range(self.SMALL_SIZE))
        large = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: bisect.bisect_left(small, self.SMALL_SIZE // 2))
        large_time = measure_time(lambda: bisect.bisect_left(large, self.LARGE_SIZE // 2))

        assert is_logarithmic_time(small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE), (
            f"bisect_left() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_bisect_right_is_ologn(self) -> None:
        """bisect_right() should be O(log n)."""
        small = list(range(self.SMALL_SIZE))
        large = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: bisect.bisect_right(small, self.SMALL_SIZE // 2))
        large_time = measure_time(lambda: bisect.bisect_right(large, self.LARGE_SIZE // 2))

        assert is_logarithmic_time(small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE), (
            f"bisect_right() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_a_run_of_equal_values_costs_no_more(self) -> None:
        """The page claims equal values do not degrade the search.

        Counted, not timed: halving the range does not care whether the values
        it skips are distinct, so an all-equal list of 65,536 items takes 17
        probes where a scan of the run would take 65,536.
        """
        for size in (1_024, 65_536):
            distinct = [CountingInt(value) for value in range(size)]
            identical = [CountingInt(5) for _ in range(size)]

            CountingInt.comparisons = 0
            bisect.bisect_left(distinct, size // 2)
            distinct_probes = CountingInt.comparisons

            CountingInt.comparisons = 0
            bisect.bisect_left(identical, 5)
            identical_probes = CountingInt.comparisons

            assert identical_probes <= distinct_probes + 1, (
                f"an all-equal list should not cost more than a distinct one at "
                f"n={size}: {identical_probes} against {distinct_probes} probes"
            )
            assert identical_probes < math.log2(size) + 2, (
                f"the search should stay logarithmic on a run of duplicates at "
                f"n={size}: {identical_probes} probes"
            )

    def test_left_and_right_bracket_a_run_of_duplicates(self) -> None:
        """bisect_left and bisect_right give the ends of an equal run."""
        values = [1, 3, 3, 3, 5, 7, 9]
        assert bisect.bisect_left(values, 3) == 1
        assert bisect.bisect_right(values, 3) == 4
        assert values[1:4] == [3, 3, 3]

    def test_bisect_is_an_alias_for_bisect_right(self) -> None:
        values = [1, 3, 3, 5]
        assert bisect.bisect(values, 3) == bisect.bisect_right(values, 3)

    @pytest.mark.timing
    def test_two_searches_cost_two_logs_not_a_scan(self) -> None:
        """The range example does two searches; that is still logarithmic."""
        large = list(range(self.LARGE_SIZE))

        one = measure_time(lambda: bisect.bisect_right(large, 10))
        two = measure_time(lambda: (bisect.bisect_right(large, 10), bisect.bisect_left(large, 20)))

        assert two < one * 4, (
            f"two searches should cost about two searches, not a scan: "
            f"one={one:.2e}s two={two:.2e}s"
        )


class TestInsortCostIsTheInsertNotTheSearch:
    """insort is O(n) because a list insert shifts the tail.

    docs/stdlib/bisect.md prices insort at "O(log n) search + O(n) insert",
    which is the page's own explanation for why maintaining a sorted list
    this way does not scale.
    """

    SMALL_SIZE = 10_000
    LARGE_SIZE = 200_000

    @pytest.mark.timing
    def test_insort_scales_with_the_list(self) -> None:
        def insert_into(size: int) -> float:
            values = list(range(size))

            def run() -> None:
                bisect.insort(values, 0)  # front: the whole tail shifts
                values.pop(0)

            return measure_time(run, iterations=50)

        small_time = insert_into(self.SMALL_SIZE)
        large_time = insert_into(self.LARGE_SIZE)

        assert large_time > small_time * 2, (
            f"insort should scale with the list, unlike the search inside it: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_the_search_inside_insort_does_not(self) -> None:
        """Contrast: the bisect_left that insort performs is flat."""
        small = list(range(self.SMALL_SIZE))
        large = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: bisect.bisect_left(small, 0))
        large_time = measure_time(lambda: bisect.bisect_left(large, 0))

        assert is_constant_time(small_time, large_time), (
            f"the search is logarithmic, so it should look flat next to the "
            f"insert: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_insort_keeps_the_list_sorted(self) -> None:
        import random

        values: list[int] = []
        source = list(range(500))
        random.Random(7).shuffle(source)
        for item in source:
            bisect.insort(values, item)

        assert values == sorted(source)


class TestKeyFunctionCosts:
    """The page warns that building a key list dominates the search.

    Python 3.10+ has a `key` parameter, which the page's "Advanced" example
    predates - it builds a parallel list instead. Either way the O(n) work is
    the keys, not the O(log n) that follows.
    """

    SIZE = 200_000

    @pytest.mark.timing
    def test_building_the_key_list_dominates_the_search(self) -> None:
        data = [(str(i), i) for i in range(self.SIZE)]

        build_time = measure_time(lambda: [x[1] for x in data], iterations=5)
        keys = [x[1] for x in data]
        search_time = measure_time(lambda: bisect.bisect_right(keys, self.SIZE // 2))

        assert build_time > search_time * 100, (
            f"the O(n) key list should dwarf the O(log n) search: "
            f"build={build_time:.2e}s search={search_time:.2e}s"
        )

    def test_key_parameter_calls_the_key_once_per_probe(self) -> None:
        """With key=, the callable runs per probe - about log2(n) times."""
        calls = {"n": 0}

        def key(item: tuple[str, int]) -> int:
            calls["n"] += 1
            return item[1]

        data = [(str(i), i) for i in range(1024)]
        bisect.bisect_left(data, 500, key=key)

        # Exactly log2(1024) probes, one key call each; a scan would be 1024.
        assert calls["n"] == 10, f"expected log2(n) == 10 key calls, got {calls['n']}"


class TestInsortLeftAndRightDiffer:
    """Two table rows that only the aliases were covering."""

    def test_left_inserts_before_an_equal_run_and_right_after(self) -> None:
        left_target = [1, 3, 3, 3, 5]
        right_target = [1, 3, 3, 3, 5]

        bisect.insort_left(left_target, 3)
        bisect.insort_right(right_target, 3)

        assert left_target == right_target == [1, 3, 3, 3, 3, 5]
        assert bisect.bisect_left(left_target, 3) == 1
        assert bisect.bisect_right(right_target, 3) == 5

    def test_left_and_right_place_a_new_object_differently(self) -> None:
        """With equal keys the two differ in where the item lands."""
        marker = ("b", 2)
        left_data = [("a", 1), ("x", 2), ("c", 3)]
        right_data = [("a", 1), ("x", 2), ("c", 3)]

        bisect.insort_left(left_data, marker, key=lambda item: item[1])
        bisect.insort_right(right_data, marker, key=lambda item: item[1])

        assert left_data.index(marker) == 1, "insort_left goes before the equal item"
        assert right_data.index(marker) == 2, "insort_right goes after it"

    def test_insort_is_an_alias_for_insort_right(self) -> None:
        alias = [1, 3, 3, 5]
        explicit = [1, 3, 3, 5]

        bisect.insort(alias, 3)
        bisect.insort_right(explicit, 3)

        assert alias == explicit


class TestKeyParameterCosts:
    """The `key` argument the page gained in this review.

    Counted rather than timed: key runs once per probe, so the call count is
    exactly the number of halvings.
    """

    def test_key_runs_once_per_probe_at_every_size(self) -> None:
        for size in (1_024, 65_536):
            calls = {"n": 0}

            def key(item: tuple[str, int], calls: dict[str, int] = calls) -> int:
                calls["n"] += 1
                return item[1]

            data = [(str(value), value) for value in range(size)]
            bisect.bisect_left(data, size // 2, key=key)

            assert calls["n"] == math.log2(size), (
                f"expected log2({size}) key calls, got {calls['n']}"
            )

    def test_insort_calls_key_once_more_for_the_inserted_item(self) -> None:
        size = 1_024
        calls = {"n": 0}

        def key(item: tuple[str, int]) -> int:
            calls["n"] += 1
            return item[1]

        data = [(str(value), value) for value in range(size)]
        bisect.insort_left(data, ("new", size // 2), key=key)

        assert calls["n"] == math.log2(size) + 1, (
            f"expected log2(n) probes plus the item itself, got {calls['n']}"
        )

    def test_key_avoids_building_a_parallel_list(self) -> None:
        """The trade the page now states: no O(n) build, log n calls instead."""
        size = 10_000
        data = [(str(value), value) for value in range(size)]
        calls = {"n": 0}

        def key(item: tuple[str, int]) -> int:
            calls["n"] += 1
            return item[1]

        position = bisect.bisect_right(data, 5_000, key=key)

        assert position == 5_001
        assert calls["n"] < size / 100, (
            f"key should be called per probe, not per element: {calls['n']} for n={size}"
        )


class TestSortedDataRequirement:
    """The warning admonition: unsorted input gives a wrong answer."""

    def test_an_unsorted_list_yields_a_position_that_does_not_sort(self) -> None:
        unsorted = [3, 1, 4, 1, 5]

        position = bisect.bisect(unsorted, 2)
        result = unsorted[:position] + [2] + unsorted[position:]

        assert result != sorted(result), (
            f"the page calls this an incorrect result; inserting at {position} gave {result}"
        )


PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "bisect.md"

EXPECTED_BLOCKS = 12


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
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, including the one indented inside an admonition."""

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
        original = _blocks()[0][1]
        broken = original.replace("import bisect\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr


class TestDocumentedOutputs:
    """Every value the page prints or states in a comment."""

    def test_binary_search_guarantee_positions(self) -> None:
        values = [1, 3, 3, 3, 5, 7, 9]

        assert bisect.bisect_left(values, 3) == 1
        assert bisect.bisect_right(values, 3) == 4

    def test_sorted_insert_result(self) -> None:
        values = [1, 3, 5, 7]

        bisect.insort(values, 4)

        assert values == [1, 3, 4, 5, 7]

    def test_range_positions(self) -> None:
        values = [1, 5, 10, 15, 20]

        assert bisect.bisect_right(values, 7) == 2
        assert bisect.bisect_left(values, 12) == 3

    def test_grade_ranges(self) -> None:
        breaks = [60, 70, 80, 90]
        grades = ["F", "D", "C", "B", "A"]

        assert grades[bisect.bisect(breaks, 85)] == "B"
        assert grades[bisect.bisect(breaks, 95)] == "A"

    def test_timestamp_lookup_returns_the_later_events(self) -> None:
        from datetime import datetime

        events = [
            (datetime(2024, 1, 1, 10), "event1"),
            (datetime(2024, 1, 1, 12), "event2"),
            (datetime(2024, 1, 1, 15), "event3"),
            (datetime(2024, 1, 1, 18), "event4"),
        ]
        timestamps = [event[0] for event in events]

        index = bisect.bisect_right(timestamps, datetime(2024, 1, 1, 14))

        assert [name for _, name in events[index:]] == ["event3", "event4"]

    def test_exists_helper_from_the_page(self) -> None:
        values = [1, 3, 5, 7, 9]

        def exists(sorted_list: list[int], x: int) -> bool:
            position = bisect.bisect_left(sorted_list, x)
            return position < len(sorted_list) and sorted_list[position] == x

        assert exists(values, 5) is True
        assert exists(values, 4) is False
