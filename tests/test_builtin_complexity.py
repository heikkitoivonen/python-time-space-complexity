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

    def test_sort_average_case(self) -> None:
        """sort() should be O(n log n) average case."""
        import random

        random.seed(42)
        small_list = [random.randint(0, 1000000) for _ in range(self.SMALL_SIZE)]
        large_list = [random.randint(0, 1000000) for _ in range(self.LARGE_SIZE)]

        def sort_small() -> None:
            lst = small_list.copy()
            lst.sort()

        def sort_large() -> None:
            lst = large_list.copy()
            lst.sort()

        small_time = measure_time(sort_small, iterations=20)
        large_time = measure_time(sort_large, iterations=20)

        # O(n log n) means large should be ~100 * log(100000)/log(1000) ~ 166x slower
        # We use a generous tolerance since timing can vary
        expected_ratio = (self.LARGE_SIZE / self.SMALL_SIZE) * (17 / 10)  # ~170x
        assert large_time < small_time * expected_ratio * 3, (
            f"sort() appears worse than O(n log n): {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_sort_best_case_already_sorted(self) -> None:
        """sort() should be O(n) for already sorted data (Timsort adaptive)."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        def sort_small() -> None:
            lst = small_list.copy()
            lst.sort()

        def sort_large() -> None:
            lst = large_list.copy()
            lst.sort()

        small_time = measure_time(sort_small, iterations=20)
        large_time = measure_time(sort_large, iterations=20)

        # For already sorted data, Timsort is O(n), so should scale linearly
        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"sort() on sorted data doesn't appear linear: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )


class TestTupleComplexity:
    """Test tuple operation complexities as documented in docs/builtins/tuple.md."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_len_is_o1(self) -> None:
        """len() should be O(1) - direct lookup."""
        small_tuple = tuple(range(self.SMALL_SIZE))
        large_tuple = tuple(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: len(small_tuple))
        large_time = measure_time(lambda: len(large_tuple))

        assert is_constant_time(small_time, large_time), (
            f"len() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_index_access_is_o1(self) -> None:
        """tuple[i] should be O(1) - direct indexing."""
        small_tuple = tuple(range(self.SMALL_SIZE))
        large_tuple = tuple(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_tuple[self.SMALL_SIZE // 2])
        large_time = measure_time(lambda: large_tuple[self.LARGE_SIZE // 2])

        assert is_constant_time(small_time, large_time), (
            f"Index access appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_in_membership_is_on(self) -> None:
        """'in' membership should be O(n) - linear search."""
        small_tuple = tuple(range(self.SMALL_SIZE))
        large_tuple = tuple(range(self.LARGE_SIZE))

        nonexistent = -1

        small_time = measure_time(lambda: nonexistent in small_tuple, iterations=50)
        large_time = measure_time(lambda: nonexistent in large_tuple, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"'in' doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
        assert large_time > small_time * 2, (
            f"'in' should be slower for larger tuple: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_index_search_is_on(self) -> None:
        """tuple.index(x) should be O(n) - linear search."""
        small_tuple = tuple(range(self.SMALL_SIZE))
        large_tuple = tuple(range(self.LARGE_SIZE))

        last_small = self.SMALL_SIZE - 1
        last_large = self.LARGE_SIZE - 1

        small_time = measure_time(lambda: small_tuple.index(last_small), iterations=50)
        large_time = measure_time(lambda: large_tuple.index(last_large), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"index() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
        assert large_time > small_time * 2, (
            f"index() should be slower for larger tuple: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_count_is_on(self) -> None:
        """tuple.count(x) should be O(n) - linear scan."""
        small_tuple = tuple(range(self.SMALL_SIZE))
        large_tuple = tuple(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_tuple.count(0), iterations=50)
        large_time = measure_time(lambda: large_tuple.count(0), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"count() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_hash_is_on(self) -> None:
        """hash() should be O(n) - iterates all elements."""
        small_tuple = tuple(range(self.SMALL_SIZE))
        large_tuple = tuple(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: hash(small_tuple), iterations=50)
        large_time = measure_time(lambda: hash(large_tuple), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"hash() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_concatenation_is_omn(self) -> None:
        """Concatenation should be O(m+n)."""
        small_tuple = tuple(range(self.SMALL_SIZE))
        large_tuple = tuple(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_tuple + small_tuple, iterations=50)
        large_time = measure_time(lambda: large_tuple + large_tuple, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"Concatenation doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_slice_is_ok(self) -> None:
        """Slicing should be O(k) where k = slice length."""
        large_tuple = tuple(range(self.LARGE_SIZE))

        small_slice_time = measure_time(
            lambda: large_tuple[: self.SMALL_SIZE], iterations=50
        )
        large_slice_time = measure_time(
            lambda: large_tuple[: self.LARGE_SIZE], iterations=50
        )

        assert is_linear_time(small_slice_time, large_slice_time, self.SIZE_RATIO), (
            f"Slicing doesn't scale linearly with slice size: "
            f"{small_slice_time:.2e}s vs {large_slice_time:.2e}s"
        )

    def test_constructor_is_on(self) -> None:
        """tuple() constructor should be O(n)."""
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: tuple(small_list), iterations=50)
        large_time = measure_time(lambda: tuple(large_list), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"tuple() constructor doesn't appear linear: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_repetition_is_on(self) -> None:
        """Repetition (t * n) should be O(n * len(t))."""
        base_tuple = tuple(range(100))

        small_time = measure_time(lambda: base_tuple * 10, iterations=50)
        large_time = measure_time(lambda: base_tuple * 1000, iterations=50)

        assert is_linear_time(small_time, large_time, 100), (
            f"Repetition doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestStrComplexity:
    """Test str operation complexities as documented in docs/builtins/str.md."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_len_is_o1(self) -> None:
        """len() should be O(1) - direct lookup."""
        small_str = "a" * self.SMALL_SIZE
        large_str = "a" * self.LARGE_SIZE

        small_time = measure_time(lambda: len(small_str))
        large_time = measure_time(lambda: len(large_str))

        assert is_constant_time(small_time, large_time), (
            f"len() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_index_access_is_o1(self) -> None:
        """str[i] should be O(1) - direct indexing."""
        small_str = "a" * self.SMALL_SIZE
        large_str = "a" * self.LARGE_SIZE

        small_time = measure_time(lambda: small_str[self.SMALL_SIZE // 2])
        large_time = measure_time(lambda: large_str[self.LARGE_SIZE // 2])

        assert is_constant_time(small_time, large_time), (
            f"Index access appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_find_is_on(self) -> None:
        """str.find() should be O(n) for substring search."""
        small_str = "a" * self.SMALL_SIZE + "b"
        large_str = "a" * self.LARGE_SIZE + "b"

        small_time = measure_time(lambda: small_str.find("b"), iterations=50)
        large_time = measure_time(lambda: large_str.find("b"), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"find() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_rfind_is_on(self) -> None:
        """str.rfind() should be O(n) for reverse substring search."""
        small_str = "b" + "a" * self.SMALL_SIZE
        large_str = "b" + "a" * self.LARGE_SIZE

        small_time = measure_time(lambda: small_str.rfind("b"), iterations=50)
        large_time = measure_time(lambda: large_str.rfind("b"), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"rfind() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_count_is_on(self) -> None:
        """str.count() should be O(n) - scans entire string."""
        small_str = "a" * self.SMALL_SIZE
        large_str = "a" * self.LARGE_SIZE

        small_time = measure_time(lambda: small_str.count("a"), iterations=50)
        large_time = measure_time(lambda: large_str.count("a"), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"count() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_replace_is_on(self) -> None:
        """str.replace() should be O(n) - single pass."""
        small_str = "a" * self.SMALL_SIZE
        large_str = "a" * self.LARGE_SIZE

        small_time = measure_time(lambda: small_str.replace("a", "b"), iterations=50)
        large_time = measure_time(lambda: large_str.replace("a", "b"), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"replace() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_split_is_on(self) -> None:
        """str.split() should be O(n) - single pass."""
        small_str = "a " * self.SMALL_SIZE
        large_str = "a " * self.LARGE_SIZE

        small_time = measure_time(lambda: small_str.split(), iterations=50)
        large_time = measure_time(lambda: large_str.split(), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"split() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_join_is_on(self) -> None:
        """str.join() should be O(n) - n = total chars."""
        small_list = ["a"] * self.SMALL_SIZE
        large_list = ["a"] * self.LARGE_SIZE

        small_time = measure_time(lambda: "".join(small_list), iterations=50)
        large_time = measure_time(lambda: "".join(large_list), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"join() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_upper_is_on(self) -> None:
        """str.upper() should be O(n) - processes each char."""
        small_str = "a" * self.SMALL_SIZE
        large_str = "a" * self.LARGE_SIZE

        small_time = measure_time(lambda: small_str.upper(), iterations=50)
        large_time = measure_time(lambda: large_str.upper(), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"upper() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_strip_is_on(self) -> None:
        """str.strip() should be O(n)."""
        small_str = " " * 100 + "a" * self.SMALL_SIZE + " " * 100
        large_str = " " * 100 + "a" * self.LARGE_SIZE + " " * 100

        small_time = measure_time(lambda: small_str.strip(), iterations=50)
        large_time = measure_time(lambda: large_str.strip(), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"strip() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_startswith_is_om(self) -> None:
        """str.startswith() should be O(m) where m = prefix length."""
        large_str = "a" * self.LARGE_SIZE
        small_prefix = "a" * 100
        large_prefix = "a" * 10000

        small_time = measure_time(
            lambda: large_str.startswith(small_prefix), iterations=100
        )
        large_time = measure_time(
            lambda: large_str.startswith(large_prefix), iterations=100
        )

        assert is_linear_time(small_time, large_time, 100), (
            f"startswith() doesn't scale with prefix: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_concatenation_is_on(self) -> None:
        """String concatenation should be O(n+m)."""
        small_str = "a" * self.SMALL_SIZE
        large_str = "a" * self.LARGE_SIZE

        small_time = measure_time(lambda: small_str + small_str, iterations=50)
        large_time = measure_time(lambda: large_str + large_str, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"Concatenation doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_slice_is_ok(self) -> None:
        """Slicing should be O(k) where k = slice length."""
        large_str = "a" * self.LARGE_SIZE

        small_slice_time = measure_time(
            lambda: large_str[: self.SMALL_SIZE], iterations=50
        )
        large_slice_time = measure_time(
            lambda: large_str[: self.LARGE_SIZE], iterations=50
        )

        assert is_linear_time(small_slice_time, large_slice_time, self.SIZE_RATIO), (
            f"Slicing doesn't scale linearly: {small_slice_time:.2e}s vs {large_slice_time:.2e}s"
        )

    def test_in_substring_is_on(self) -> None:
        """'in' substring check should be O(n)."""
        small_str = "a" * self.SMALL_SIZE + "b"
        large_str = "a" * self.LARGE_SIZE + "b"

        small_time = measure_time(lambda: "b" in small_str, iterations=50)
        large_time = measure_time(lambda: "b" in large_str, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"'in' doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_encode_is_on(self) -> None:
        """str.encode() should be O(n)."""
        small_str = "a" * self.SMALL_SIZE
        large_str = "a" * self.LARGE_SIZE

        small_time = measure_time(lambda: small_str.encode(), iterations=50)
        large_time = measure_time(lambda: large_str.encode(), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"encode() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
