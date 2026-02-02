"""Tests to verify documented time complexity of heapq module operations.

These tests use timing measurements to verify that operations scale
according to their documented complexity.
"""

import heapq
import math
import time
from typing import Any, Callable


def measure_time(func: Callable[[], Any], iterations: int = 100) -> float:
    """Measure average time for a function over multiple iterations."""
    start = time.perf_counter()
    for _ in range(iterations):
        func()
    end = time.perf_counter()
    return (end - start) / iterations


def is_constant_time(
    small_time: float, large_time: float, tolerance: float = 3.0
) -> bool:
    """Check if two times are within tolerance (suggesting O(1))."""
    if small_time == 0:
        return large_time < 1e-6
    ratio = large_time / small_time
    return ratio < tolerance


def is_linear_time(
    small_time: float,
    large_time: float,
    size_ratio: float,
    tolerance: float = 3.0,
) -> bool:
    """Check if time scales linearly with size."""
    if small_time == 0:
        return True
    ratio = large_time / small_time
    expected_ratio = size_ratio
    return ratio < expected_ratio * tolerance


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
    ratio = large_time / small_time
    expected_ratio = math.log2(large_size) / math.log2(small_size)
    return ratio < expected_ratio * tolerance


class TestHeapqComplexity:
    """Test heapq operation complexities as documented in docs/stdlib/heapq.md."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_heapify_is_on(self) -> None:
        """heapify() should be O(n)."""
        small_list = list(range(self.SMALL_SIZE, 0, -1))
        large_list = list(range(self.LARGE_SIZE, 0, -1))

        def heapify_small() -> None:
            lst = small_list.copy()
            heapq.heapify(lst)

        def heapify_large() -> None:
            lst = large_list.copy()
            heapq.heapify(lst)

        small_time = measure_time(heapify_small, iterations=50)
        large_time = measure_time(heapify_large, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"heapify() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_heappush_is_ologn(self) -> None:
        """heappush() should be O(log n)."""
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapq.heapify(small_heap)
        heapq.heapify(large_heap)

        def push_small() -> None:
            heapq.heappush(small_heap, 0)
            heapq.heappop(small_heap)

        def push_large() -> None:
            heapq.heappush(large_heap, 0)
            heapq.heappop(large_heap)

        small_time = measure_time(push_small)
        large_time = measure_time(push_large)

        assert is_logarithmic_time(
            small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE
        ), f"heappush() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"

    def test_heappop_is_ologn(self) -> None:
        """heappop() should be O(log n)."""
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapq.heapify(small_heap)
        heapq.heapify(large_heap)

        def pop_small() -> None:
            val = heapq.heappop(small_heap)
            heapq.heappush(small_heap, val)

        def pop_large() -> None:
            val = heapq.heappop(large_heap)
            heapq.heappush(large_heap, val)

        small_time = measure_time(pop_small)
        large_time = measure_time(pop_large)

        assert is_logarithmic_time(
            small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE
        ), f"heappop() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"

    def test_heappushpop_is_ologn(self) -> None:
        """heappushpop() should be O(log n)."""
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapq.heapify(small_heap)
        heapq.heapify(large_heap)

        def pushpop_small() -> None:
            val = heapq.heappushpop(small_heap, -1)
            heapq.heappush(small_heap, val)

        def pushpop_large() -> None:
            val = heapq.heappushpop(large_heap, -1)
            heapq.heappush(large_heap, val)

        small_time = measure_time(pushpop_small)
        large_time = measure_time(pushpop_large)

        assert is_logarithmic_time(
            small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE, tolerance=5.0
        ), (
            f"heappushpop() doesn't appear O(log n): "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_heapreplace_is_ologn(self) -> None:
        """heapreplace() should be O(log n)."""
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapq.heapify(small_heap)
        heapq.heapify(large_heap)

        def replace_small() -> None:
            val = heapq.heapreplace(small_heap, -1)
            heapq.heappush(small_heap, val)
            heapq.heappop(small_heap)

        def replace_large() -> None:
            val = heapq.heapreplace(large_heap, -1)
            heapq.heappush(large_heap, val)
            heapq.heappop(large_heap)

        small_time = measure_time(replace_small)
        large_time = measure_time(replace_large)

        assert is_logarithmic_time(
            small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE
        ), (
            f"heapreplace() doesn't appear O(log n): "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_nlargest_scales_with_n(self) -> None:
        """nlargest(k, iterable) should be O(N log k) where N = iterable length."""
        small_data = list(range(self.SMALL_SIZE))
        large_data = list(range(self.LARGE_SIZE))
        k = 10

        small_time = measure_time(lambda: heapq.nlargest(k, small_data), iterations=50)
        large_time = measure_time(lambda: heapq.nlargest(k, large_data), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"nlargest() doesn't scale linearly with N: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_nsmallest_scales_with_n(self) -> None:
        """nsmallest(k, iterable) should be O(N log k) where N = iterable length."""
        small_data = list(range(self.SMALL_SIZE))
        large_data = list(range(self.LARGE_SIZE))
        k = 10

        small_time = measure_time(
            lambda: heapq.nsmallest(k, small_data), iterations=50
        )
        large_time = measure_time(
            lambda: heapq.nsmallest(k, large_data), iterations=50
        )

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"nsmallest() doesn't scale linearly with N: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_nlargest_scales_with_k(self) -> None:
        """nlargest with larger k should be slower (O(N log k))."""
        data = list(range(self.LARGE_SIZE))

        small_k_time = measure_time(lambda: heapq.nlargest(10, data), iterations=20)
        large_k_time = measure_time(lambda: heapq.nlargest(1000, data), iterations=20)

        assert large_k_time > small_k_time, (
            f"nlargest() should be slower with larger k: "
            f"k=10: {small_k_time:.2e}s vs k=1000: {large_k_time:.2e}s"
        )

    def test_merge_scales_with_total_items(self) -> None:
        """merge() should scale with total items O(n log k)."""
        small_lists = [list(range(i, i + 100)) for i in range(10)]
        large_lists = [list(range(i, i + 10000)) for i in range(10)]

        def merge_small() -> None:
            list(heapq.merge(*small_lists))

        def merge_large() -> None:
            list(heapq.merge(*large_lists))

        small_time = measure_time(merge_small, iterations=50)
        large_time = measure_time(merge_large, iterations=50)

        assert is_linear_time(small_time, large_time, 100), (
            f"merge() doesn't scale linearly with total items: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_heap_maintains_invariant(self) -> None:
        """Verify heap property is maintained after operations."""
        import random

        data = list(range(1000))
        random.shuffle(data)

        heap: list[int] = []
        for item in data:
            heapq.heappush(heap, item)

        sorted_result = []
        while heap:
            sorted_result.append(heapq.heappop(heap))

        assert sorted_result == sorted(data), "Heap did not maintain sorted order"

    def test_heapify_produces_valid_heap(self) -> None:
        """Verify heapify produces valid min-heap."""
        import random

        data = list(range(1000))
        random.shuffle(data)

        heapq.heapify(data)

        for i in range(len(data)):
            left = 2 * i + 1
            right = 2 * i + 2
            if left < len(data):
                assert data[i] <= data[left], f"Heap violated at {i} vs left {left}"
            if right < len(data):
                assert data[i] <= data[right], f"Heap violated at {i} vs right {right}"
