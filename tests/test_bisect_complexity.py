"""Tests to verify documented time complexity of bisect module operations.

docs/stdlib/bisect.md is the only algorithmic stdlib page in this repo with
no test file, and its claims are the kind worth checking: that the searches
are logarithmic, that a long run of equal values does not degrade them, and
that the O(n) in `insort` comes from shifting the list, not from searching it.

The page's own framing is that the search is cheap and everything around it
is not - `keys = [x[1] for x in data]` before a search, or the insert after
one - so the contrast between the two is what these tests pin.
"""

import bisect
import time
from collections.abc import Callable
from typing import Any


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
    import math

    if small_time == 0:
        return True
    expected = math.log2(large_size) / math.log2(small_size)
    return large_time / small_time < expected * tolerance


class TestBisectComplexity:
    """Test bisect operation complexities as documented in docs/stdlib/bisect.md."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 1_000_000

    def test_bisect_left_is_ologn(self) -> None:
        """bisect_left() should be O(log n)."""
        small = list(range(self.SMALL_SIZE))
        large = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: bisect.bisect_left(small, self.SMALL_SIZE // 2))
        large_time = measure_time(lambda: bisect.bisect_left(large, self.LARGE_SIZE // 2))

        assert is_logarithmic_time(small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE), (
            f"bisect_left() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"
        )

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

        Halving the range does not care whether the values it skips are
        distinct, so a list of a million identical items searches as fast as
        a million distinct ones.
        """
        distinct = list(range(self.LARGE_SIZE))
        identical = [5] * self.LARGE_SIZE

        distinct_time = measure_time(lambda: bisect.bisect_left(distinct, self.LARGE_SIZE // 2))
        identical_time = measure_time(lambda: bisect.bisect_left(identical, 5))

        assert is_constant_time(distinct_time, identical_time), (
            f"an all-equal list should not slow the search: "
            f"distinct={distinct_time:.2e}s identical={identical_time:.2e}s"
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
        random.shuffle(source)
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

        # log2(1024) == 10; a scan would be 1024.
        assert calls["n"] <= 20, f"expected about log2(n) key calls, got {calls['n']}"
