"""Tests to verify documented time complexity of Python builtins.

These tests use timing measurements to verify that operations scale
according to their documented complexity. They are not meant to be
precise benchmarks, but rather sanity checks that O(1) operations
don't become O(n), etc.
"""

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


class TestListComplexity:
    """Test list operation complexities as documented in docs/builtins/list.md."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_len_is_o1(self) -> None:
        """len() should be O(1) - direct lookup."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: len(small_list))
        large_time = measure_time(lambda: len(large_list))

        assert is_constant_time(small_time, large_time), (
            f"len() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_index_access_is_o1(self) -> None:
        """list[i] should be O(1) - direct indexing."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_list[self.SMALL_SIZE // 2])
        large_time = measure_time(lambda: large_list[self.LARGE_SIZE // 2])

        assert is_constant_time(small_time, large_time), (
            f"Index access appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_append_is_o1_amortized(self) -> None:
        """append() should be O(1) amortized."""
        small_list: list[int] = []
        large_list: list[int] = []

        def append_many_small() -> None:
            for i in range(100):
                small_list.append(i)

        def append_many_large() -> None:
            for i in range(100):
                large_list.append(i)

        small_time = measure_time(append_many_small, iterations=10)
        small_list.clear()

        for _ in range(self.LARGE_SIZE):
            large_list.append(0)

        large_time = measure_time(append_many_large, iterations=10)

        assert is_constant_time(small_time, large_time, tolerance=5.0), (
            f"append() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_pop_last_is_o1(self) -> None:
        """pop() (last element) should be O(1)."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        def pop_and_restore_small() -> None:
            val = small_list.pop()
            small_list.append(val)

        def pop_and_restore_large() -> None:
            val = large_list.pop()
            large_list.append(val)

        small_time = measure_time(pop_and_restore_small)
        large_time = measure_time(pop_and_restore_large)

        assert is_constant_time(small_time, large_time), (
            f"pop() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_pop_first_is_on(self) -> None:
        """pop(0) should be O(n) - must shift all elements."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        def pop_first_small() -> None:
            val = small_list.pop(0)
            small_list.append(val)

        def pop_first_large() -> None:
            val = large_list.pop(0)
            large_list.append(val)

        small_time = measure_time(pop_first_small, iterations=50)
        large_time = measure_time(pop_first_large, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"pop(0) doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
        assert large_time > small_time * 2, (
            f"pop(0) should be slower for larger list: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_insert_at_beginning_is_on(self) -> None:
        """insert(0, x) should be O(n) - must shift all elements."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        def insert_first_small() -> None:
            small_list.insert(0, 0)
            small_list.pop(0)

        def insert_first_large() -> None:
            large_list.insert(0, 0)
            large_list.pop(0)

        small_time = measure_time(insert_first_small, iterations=50)
        large_time = measure_time(insert_first_large, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"insert(0, x) doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
        assert large_time > small_time * 2, (
            f"insert(0, x) should be slower for larger list: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_in_membership_is_on(self) -> None:
        """'in' membership should be O(n) - linear search."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        nonexistent = -1

        small_time = measure_time(lambda: nonexistent in small_list, iterations=50)
        large_time = measure_time(lambda: nonexistent in large_list, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"'in' doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
        assert large_time > small_time * 2, (
            f"'in' should be slower for larger list: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_index_search_is_on(self) -> None:
        """list.index(x) should be O(n) - linear search."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        last_small = self.SMALL_SIZE - 1
        last_large = self.LARGE_SIZE - 1

        small_time = measure_time(lambda: small_list.index(last_small), iterations=50)
        large_time = measure_time(lambda: large_list.index(last_large), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"index() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
        assert large_time > small_time * 2, (
            f"index() should be slower for larger list: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_count_is_on(self) -> None:
        """list.count(x) should be O(n) - linear scan."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_list.count(0), iterations=50)
        large_time = measure_time(lambda: large_list.count(0), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"count() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_copy_is_on(self) -> None:
        """list.copy() should be O(n) - shallow copy."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_list.copy(), iterations=50)
        large_time = measure_time(lambda: large_list.copy(), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"copy() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_reverse_is_on(self) -> None:
        """list.reverse() should be O(n) - in-place reversal."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_list.reverse(), iterations=50)
        large_time = measure_time(lambda: large_list.reverse(), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"reverse() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_clear_is_on(self) -> None:
        """list.clear() should be O(n) - deallocate memory."""

        def measure_clear(size: int) -> float:
            times = []
            for _ in range(20):
                lst = list(range(size))
                start = time.perf_counter()
                lst.clear()
                end = time.perf_counter()
                times.append(end - start)
            return sum(times) / len(times)

        small_time = measure_clear(self.SMALL_SIZE)
        large_time = measure_clear(self.LARGE_SIZE)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"clear() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_extend_is_ok(self) -> None:
        """extend(iterable) should be O(k) where k = len(iterable)."""
        base_list: list[int] = []
        small_extend = list(range(self.SMALL_SIZE))
        large_extend = list(range(self.LARGE_SIZE))

        def extend_small() -> None:
            base_list.clear()
            base_list.extend(small_extend)

        def extend_large() -> None:
            base_list.clear()
            base_list.extend(large_extend)

        small_time = measure_time(extend_small, iterations=50)
        large_time = measure_time(extend_large, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"extend() doesn't scale linearly with iterable size: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_slice_is_ok(self) -> None:
        """Slicing should be O(k) where k = slice length."""
        large_list = list(range(self.LARGE_SIZE))

        small_slice_time = measure_time(
            lambda: large_list[: self.SMALL_SIZE], iterations=50
        )
        large_slice_time = measure_time(
            lambda: large_list[: self.LARGE_SIZE], iterations=50
        )

        assert is_linear_time(small_slice_time, large_slice_time, self.SIZE_RATIO), (
            f"Slicing doesn't scale linearly with slice size: "
            f"{small_slice_time:.2e}s vs {large_slice_time:.2e}s"
        )
