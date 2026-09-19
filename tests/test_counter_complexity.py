"""Tests to verify documented behaviour of Counter, per docs/stdlib/counter.md.

The table, counting patterns, selection and arithmetic are covered here.

Measurement scope:

* Subtracting absent keys creates negative counts, growing the stored key set.
* Constructor and update calls with lists and iterators delegate once to the
  same CPython counting helper and produce the same counts as a Python loop.
  Per-key increments do not call that helper.
* Timing tests vary input size with fixed-cost keys and counts.

Not settled here: relative speed of bulk counting and Python counting loops
across workloads and interpreters; neither method has a universal speed ranking.
"""

from __future__ import annotations

import heapq
import importlib
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Any

import pytest

from tests.collection_timing import is_linear_time, measure_time


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


SAMPLE = [index % 1_000 for index in range(200_000)]


class TestSubtractAllocates:
    """The table said O(1) space; subtract() can add keys."""

    def test_subtracting_an_absent_key_creates_it(self) -> None:
        counter = Counter(a=1)
        counter.subtract(Counter(b=5))

        assert "b" in counter, "the key did not exist before the subtraction"
        assert counter["b"] == -5

    def test_space_grows_with_the_argument(self) -> None:
        counter = Counter(a=1)
        counter.subtract({f"k{index}": 1 for index in range(500)})

        assert len(counter) == 501, "one entry per key subtracted, not O(1)"

    def test_negative_counts_are_kept(self) -> None:
        """Unlike the arithmetic operators, which drop non-positive counts."""
        counter = Counter(a=1)
        counter.subtract(Counter(a=5))
        assert counter["a"] == -4

        assert (Counter(a=1) - Counter(a=5)) == Counter(), "the operator drops it"

    def test_a_missing_key_reads_as_zero_without_being_created(self) -> None:
        """Contrast: a plain lookup does not allocate."""
        counter = Counter(a=1)
        assert counter["absent"] == 0
        assert "absent" not in counter


class TestCountingPaths:
    """Observe bulk helper dispatch and counts without a wall-clock ranking."""

    @pytest.mark.parametrize("via_update", [False, True])
    @pytest.mark.parametrize("iterator", [False, True])
    def test_bulk_counting_delegates_once_and_matches_a_loop(
        self, monkeypatch: pytest.MonkeyPatch, via_update: bool, iterator: bool
    ) -> None:
        helpers = importlib.import_module("_collections")
        collections_module = importlib.import_module("collections")
        original = collections_module._count_elements
        assert original is helpers._count_elements
        calls = []

        def record(mapping: Any, items: Any) -> None:
            calls.append((mapping, items))
            original(mapping, items)

        monkeypatch.setattr(collections_module, "_count_elements", record)
        data = [1, 2, 2, 3, 3, 3]
        source = iter(data) if iterator else data
        if via_update:
            result = Counter()
            result.update(source)
        else:
            result = Counter(source)

        assert len(calls) == 1
        assert calls[0][0] is result
        assert calls[0][1] is source
        assert result == {1: 1, 2: 2, 3: 3}

        calls.clear()
        incremental: Counter[int] = Counter()
        manual: defaultdict[int, int] = defaultdict(int)
        for value in data:
            incremental[value] += 1
            manual[value] += 1
        assert calls == []
        assert incremental == manual == result


class TestCounterIsADictSubclass:
    """The page listed space-constrained environments under "not good for"."""

    def test_it_costs_about_what_the_dict_would(self) -> None:
        counter = Counter(SAMPLE)
        plain = dict(counter)

        assert abs(sys.getsizeof(counter) - sys.getsizeof(plain)) < 1_000, (
            f"Counter {sys.getsizeof(counter)} vs dict {sys.getsizeof(plain)}"
        )

    @pytest.mark.timing
    def test_lookup_is_constant_time(self) -> None:
        small = Counter(range(1_000))
        large = Counter(range(1_000_000))

        small_time = best_time(lambda: [small[500] for _ in range(10_000)])
        large_time = best_time(lambda: [large[500_000] for _ in range(10_000)])

        assert large_time < small_time * 3, (
            f"lookup is a dict lookup: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_construction_is_linear(self) -> None:
        small = list(range(100_000))
        large = list(range(1_000_000))

        small_time = best_time(lambda: Counter(small), repeats=3)
        large_time = best_time(lambda: Counter(large), repeats=3)

        assert large_time < small_time * 30, (
            f"Counter() should be linear: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestCounterComplexity:
    """Test Counter operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    @pytest.mark.timing
    def test_update_is_on(self) -> None:
        """update(iterable) should be O(n)."""
        small_items = list(range(self.SMALL_SIZE))
        large_items = list(range(self.LARGE_SIZE))

        small_counter = Counter()
        large_counter = Counter()

        small_time = measure_time(lambda: small_counter.update(small_items), iterations=20)
        large_time = measure_time(lambda: large_counter.update(large_items), iterations=20)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"Counter update doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestCounterOperations:
    """Counter growth and selection behavior.

    Small-k selection uses a bounded heap. Ascending counts require a
    replacement for every item after initialization; descending counts require
    none. Operation counts establish this input-shape difference independently
    of the relative wall-clock speed of heap selection and a full sort.
    """

    SIZE = 200_000

    def _counter(self, size: int) -> Counter:
        return Counter({f"k{index}": index for index in range(size)})

    @pytest.mark.parametrize("size", [10, 1000])
    @pytest.mark.parametrize("distinct", [2, 10])
    def test_construction_consumes_items_and_stores_distinct_keys(
        self, size: int, distinct: int
    ) -> None:
        items = iter(index % distinct for index in range(size))
        counter = Counter(items)
        assert list(items) == []
        assert len(counter) == distinct
        assert counter == dict.fromkeys(range(distinct), size // distinct)

    @pytest.mark.timing
    def test_heap_path_beats_sorting_on_realistic_data(self) -> None:
        """Compare k=10 against a full sort on 200,000 seeded random counts.

        This measures one input distribution and fixed k, not a universal
        ranking for ordered counts or other k/n ratios.
        """
        import random

        rng = random.Random(7)
        counter = Counter({f"k{i}": rng.randrange(self.SIZE) for i in range(self.SIZE)})

        sorted_time = measure_time(counter.most_common, iterations=3)
        heap_time = measure_time(lambda: counter.most_common(10), iterations=3)

        assert heap_time < sorted_time, (
            f"on random counts the heap should win: k=10 {heap_time:.2e}s all {sorted_time:.2e}s"
        )

    @pytest.mark.parametrize("ascending", [True, False])
    @pytest.mark.parametrize("k", [2, 10, 64])
    def test_count_order_controls_heap_replacements(
        self, monkeypatch: pytest.MonkeyPatch, ascending: bool, k: int
    ) -> None:
        """Count replacements at 128 and 8,192 distinct fixed-width counts.

        Strictly rising counts replace the heap root n-k times; falling counts
        replace it zero times. Heap size stays k and both orders return the
        same top-k items. This does not compare elapsed time with sorting.
        """
        replacements = 0
        original = heapq.heapreplace
        original_heapify = heapq.heapify
        heap_sizes: list[int] = []

        def heapify(heap: list[Any]) -> None:
            heap_sizes.append(len(heap))
            original_heapify(heap)

        def replace(heap: list[Any], item: Any) -> Any:
            nonlocal replacements
            replacements += 1
            assert len(heap) == k
            return original(heap, item)

        monkeypatch.setattr(heapq, "heapreplace", replace)
        monkeypatch.setattr(heapq, "heapify", heapify)
        for size in (128, 8192):
            counts = range(size) if ascending else range(size - 1, -1, -1)
            counter = Counter({f"k{count}": count for count in counts})
            replacements = 0
            heap_sizes.clear()
            result = counter.most_common(k)
            assert heap_sizes == [k]
            assert replacements == (size - k if ascending else 0)
            assert result == [(f"k{count}", count) for count in range(size - 1, size - k - 1, -1)]

    def test_most_common_returns_what_it_claims(self) -> None:
        counter = Counter("aaabbc")
        assert counter.most_common(1) == [("a", 3)]
        assert counter.most_common() == [("a", 3), ("b", 2), ("c", 1)]

    @pytest.mark.timing
    def test_total_is_on(self) -> None:
        small, large = self._counter(1_000), self._counter(100_000)

        small_time = measure_time(small.total, iterations=20)
        large_time = measure_time(large.total, iterations=20)

        assert is_linear_time(small_time, large_time, 100), (
            f"total() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.parametrize("size", [10, 1000])
    @pytest.mark.parametrize("count", [0, 5])
    def test_elements_visits_keys_lazily_and_repeats_positive_counts(
        self, size: int, count: int
    ) -> None:
        """Count key visits separately from the number of elements yielded."""
        visited = []

        class ObservedCounter(Counter):
            # A generator observes consumption instead of returning a dict view.
            def items(self):  # pyright: ignore[reportIncompatibleMethodOverride]
                for key, value in super().items():
                    visited.append(key)
                    yield key, value

        counter = ObservedCounter(dict.fromkeys(range(size), count))
        counter[-1] = -2
        elements = counter.elements()
        assert visited == []
        assert list(elements) == [key for key in range(size) for _ in range(count)]
        assert visited == [*range(size), -1]

    def test_total_includes_zero_and_negative_counts(self) -> None:
        assert Counter(a=3, b=0, c=-1).total() == 2

    @pytest.mark.parametrize("size", [10, 1000])
    def test_copy_preserves_every_key_and_shares_count_objects(self, size: int) -> None:
        count = 10**30
        counter = Counter(dict.fromkeys(range(size), count))
        copied = counter.copy()
        assert copied is not counter and copied == counter
        assert len(copied) == size
        assert all(copied[key] is counter[key] for key in counter)

    def test_fromkeys_is_unsupported(self) -> None:
        with pytest.raises(NotImplementedError):
            Counter.fromkeys(["a", "b"])

    @pytest.mark.timing
    def test_addition_is_linear_in_the_keys(self) -> None:
        small, large = self._counter(1_000), self._counter(100_000)

        small_time = measure_time(lambda: small + small, iterations=5)
        large_time = measure_time(lambda: large + large, iterations=5)

        assert is_linear_time(small_time, large_time, 100), (
            f"Counter addition doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_addition_drops_non_positive_counts(self) -> None:
        assert Counter(a=1) + Counter(a=-1) == Counter()
        assert (Counter(a=1) - Counter(a=5)) == Counter()
