"""Tests to verify documented time complexity of collections module types.

These tests use timing measurements to verify that operations scale
according to their documented complexity.
"""

import time
from collections import (
    ChainMap,
    Counter,
    OrderedDict,
    UserDict,
    UserList,
    UserString,
    defaultdict,
    deque,
    namedtuple,
)
from typing import Any, Callable


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
        end = time.perf_counter()
        times.append(end - start)
    return trimmed_mean(times)


def is_constant_time(small_time: float, large_time: float, tolerance: float = 3.0) -> bool:
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


class TestDequeComplexity:
    """Test deque operation complexities as documented in docs/stdlib/deque.md."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_append_is_o1(self) -> None:
        """append() should be O(1)."""
        small_deque: deque[int] = deque()
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        def append_small() -> None:
            small_deque.append(0)
            small_deque.pop()

        def append_large() -> None:
            large_deque.append(0)
            large_deque.pop()

        small_time = measure_time(append_small)
        large_time = measure_time(append_large)

        assert is_constant_time(small_time, large_time), (
            f"append() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_appendleft_is_o1(self) -> None:
        """appendleft() should be O(1)."""
        small_deque: deque[int] = deque()
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        def appendleft_small() -> None:
            small_deque.appendleft(0)
            small_deque.popleft()

        def appendleft_large() -> None:
            large_deque.appendleft(0)
            large_deque.popleft()

        small_time = measure_time(appendleft_small)
        large_time = measure_time(appendleft_large)

        assert is_constant_time(small_time, large_time), (
            f"appendleft() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_pop_is_o1(self) -> None:
        """pop() should be O(1)."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        def pop_small() -> None:
            val = small_deque.pop()
            small_deque.append(val)

        def pop_large() -> None:
            val = large_deque.pop()
            large_deque.append(val)

        small_time = measure_time(pop_small)
        large_time = measure_time(pop_large)

        assert is_constant_time(small_time, large_time), (
            f"pop() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_popleft_is_o1(self) -> None:
        """popleft() should be O(1)."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        def popleft_small() -> None:
            val = small_deque.popleft()
            small_deque.appendleft(val)

        def popleft_large() -> None:
            val = large_deque.popleft()
            large_deque.appendleft(val)

        small_time = measure_time(popleft_small)
        large_time = measure_time(popleft_large)

        assert is_constant_time(small_time, large_time), (
            f"popleft() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_index_ends_is_o1(self) -> None:
        """Indexing at ends should be O(1)."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: (small_deque[0], small_deque[-1]))
        large_time = measure_time(lambda: (large_deque[0], large_deque[-1]))

        assert is_constant_time(small_time, large_time), (
            f"End indexing appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_index_middle_is_on(self) -> None:
        """Indexing in middle should be O(n) due to block structure."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        small_mid = self.SMALL_SIZE // 2
        large_mid = self.LARGE_SIZE // 2

        small_time = measure_time(lambda: small_deque[small_mid], iterations=50)
        large_time = measure_time(lambda: large_deque[large_mid], iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"Middle indexing doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_len_is_o1(self) -> None:
        """len() should be O(1)."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: len(small_deque))
        large_time = measure_time(lambda: len(large_deque))

        assert is_constant_time(small_time, large_time), (
            f"len() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_extend_is_ok(self) -> None:
        """extend() should be O(k) where k = len(iterable)."""
        base_deque: deque[int] = deque()
        small_extend = list(range(self.SMALL_SIZE))
        large_extend = list(range(self.LARGE_SIZE))

        def extend_small() -> None:
            base_deque.clear()
            base_deque.extend(small_extend)

        def extend_large() -> None:
            base_deque.clear()
            base_deque.extend(large_extend)

        small_time = measure_time(extend_small, iterations=100)
        large_time = measure_time(extend_large, iterations=100)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"extend() doesn't scale linearly: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_extendleft_is_ok(self) -> None:
        """extendleft() should be O(k) where k = len(iterable)."""
        base_deque: deque[int] = deque()
        small_extend = list(range(self.SMALL_SIZE))
        large_extend = list(range(self.LARGE_SIZE))

        def extendleft_small() -> None:
            base_deque.clear()
            base_deque.extendleft(small_extend)

        def extendleft_large() -> None:
            base_deque.clear()
            base_deque.extendleft(large_extend)

        small_time = measure_time(extendleft_small, iterations=100)
        large_time = measure_time(extendleft_large, iterations=100)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"extendleft() doesn't scale linearly: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_rotate_is_ok(self) -> None:
        """rotate(k) should be O(k)."""
        dq: deque[int] = deque(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: dq.rotate(10), iterations=200)
        large_time = measure_time(lambda: dq.rotate(1000), iterations=200)

        assert is_linear_time(small_time, large_time, 100), (
            f"rotate() doesn't scale linearly with k: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_clear_is_on(self) -> None:
        """clear() should be O(n)."""

        def measure_clear(size: int) -> float:
            times = []
            for _ in range(40):
                dq = deque(range(size))
                start = time.perf_counter()
                dq.clear()
                end = time.perf_counter()
                times.append(end - start)
            return sum(times) / len(times)

        small_time = measure_clear(self.SMALL_SIZE)
        large_time = measure_clear(self.LARGE_SIZE)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"clear() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_copy_is_on(self) -> None:
        """copy() should be O(n)."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_deque.copy(), iterations=100)
        large_time = measure_time(lambda: large_deque.copy(), iterations=100)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"copy() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_count_is_on(self) -> None:
        """count() should be O(n)."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_deque.count(0), iterations=50)
        large_time = measure_time(lambda: large_deque.count(0), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"count() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_in_membership_is_on(self) -> None:
        """'in' membership should be O(n)."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        nonexistent = -1

        small_time = measure_time(lambda: nonexistent in small_deque, iterations=50)
        large_time = measure_time(lambda: nonexistent in large_deque, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"'in' doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_reverse_is_on(self) -> None:
        """reverse() should be O(n)."""
        small_deque: deque[int] = deque(range(self.SMALL_SIZE))
        large_deque: deque[int] = deque(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_deque.reverse(), iterations=50)
        large_time = measure_time(lambda: large_deque.reverse(), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"reverse() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestNamedTupleComplexity:
    """Test namedtuple operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_attribute_access_is_o1(self) -> None:
        """Field access should be O(1)."""
        Point = namedtuple("Point", ["x", "y"])
        small_pt = Point(1, 2)
        large_pt = Point(1, 2)

        small_time = measure_time(lambda: small_pt.x)
        large_time = measure_time(lambda: large_pt.x)

        assert is_constant_time(small_time, large_time), (
            f"namedtuple attribute access appears non-constant: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_asdict_is_on(self) -> None:
        """_asdict() should be O(n) in number of fields."""
        SmallNT = namedtuple("SmallNT", [f"f{i}" for i in range(10)])
        LargeNT = namedtuple("LargeNT", [f"f{i}" for i in range(1000)])
        small_nt = SmallNT(*range(10))
        large_nt = LargeNT(*range(1000))

        small_time = measure_time(lambda: small_nt._asdict(), iterations=50)
        large_time = measure_time(lambda: large_nt._asdict(), iterations=50)

        assert is_linear_time(small_time, large_time, 100), (
            f"_asdict() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestChainMapComplexity:
    """Test ChainMap operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000

    def test_lookup_is_o1_avg(self) -> None:
        """Lookup should be O(1) average (first mapping)."""
        small_map = ChainMap({i: i for i in range(self.SMALL_SIZE)})
        large_map = ChainMap({i: i for i in range(self.LARGE_SIZE)})

        small_time = measure_time(lambda: small_map[self.SMALL_SIZE - 1], iterations=200)
        large_time = measure_time(lambda: large_map[self.LARGE_SIZE - 1], iterations=200)

        assert is_constant_time(small_time, large_time), (
            f"ChainMap lookup appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestCounterComplexity:
    """Test Counter operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

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


class TestOrderedDictComplexity:
    """Test OrderedDict operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000

    def test_get_is_o1_avg(self) -> None:
        """Key lookup should be O(1) average."""
        small_od = OrderedDict((i, i) for i in range(self.SMALL_SIZE))
        large_od = OrderedDict((i, i) for i in range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_od[self.SMALL_SIZE - 1], iterations=200)
        large_time = measure_time(lambda: large_od[self.LARGE_SIZE - 1], iterations=200)

        assert is_constant_time(small_time, large_time), (
            f"OrderedDict lookup appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_move_to_end_is_o1(self) -> None:
        """move_to_end() should be O(1) average."""
        small_od = OrderedDict((i, i) for i in range(self.SMALL_SIZE))
        large_od = OrderedDict((i, i) for i in range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_od.move_to_end(self.SMALL_SIZE - 1), iterations=200)
        large_time = measure_time(lambda: large_od.move_to_end(self.LARGE_SIZE - 1), iterations=200)

        assert is_constant_time(small_time, large_time), (
            f"move_to_end() appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestDefaultDictComplexity:
    """Test defaultdict operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000

    def test_missing_key_is_o1_avg(self) -> None:
        """Missing key access should be O(1) average."""
        small_dd: defaultdict[int, int] = defaultdict(int, {i: i for i in range(self.SMALL_SIZE)})
        large_dd: defaultdict[int, int] = defaultdict(int, {i: i for i in range(self.LARGE_SIZE)})

        small_time = measure_time(lambda: small_dd[self.SMALL_SIZE + 1], iterations=200)
        large_time = measure_time(lambda: large_dd[self.LARGE_SIZE + 1], iterations=200)

        assert is_constant_time(small_time, large_time), (
            f"defaultdict missing-key access appears non-constant: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )


class TestUserDictComplexity:
    """Test UserDict operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000

    def test_get_is_o1_avg(self) -> None:
        """UserDict key lookup should be O(1) average."""
        small_ud = UserDict({i: i for i in range(self.SMALL_SIZE)})
        large_ud = UserDict({i: i for i in range(self.LARGE_SIZE)})

        small_time = measure_time(lambda: small_ud[self.SMALL_SIZE - 1], iterations=200)
        large_time = measure_time(lambda: large_ud[self.LARGE_SIZE - 1], iterations=200)

        assert is_constant_time(small_time, large_time), (
            f"UserDict lookup appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestUserListComplexity:
    """Test UserList operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_len_is_o1(self) -> None:
        """len() should be O(1)."""
        small_ul = UserList(range(self.SMALL_SIZE))
        large_ul = UserList(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: len(small_ul))
        large_time = measure_time(lambda: len(large_ul))

        assert is_constant_time(small_time, large_time), (
            f"UserList len appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_count_is_on(self) -> None:
        """count() should be O(n)."""
        small_ul = UserList(range(self.SMALL_SIZE))
        large_ul = UserList(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: small_ul.count(0), iterations=50)
        large_time = measure_time(lambda: large_ul.count(0), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"UserList count doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestUserStringComplexity:
    """Test UserString operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_len_is_o1(self) -> None:
        """len() should be O(1)."""
        small_us = UserString("a" * self.SMALL_SIZE)
        large_us = UserString("a" * self.LARGE_SIZE)

        small_time = measure_time(lambda: len(small_us))
        large_time = measure_time(lambda: len(large_us))

        assert is_constant_time(small_time, large_time), (
            f"UserString len appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_count_is_on(self) -> None:
        """count() should be O(n)."""
        small_us = UserString("a" * self.SMALL_SIZE)
        large_us = UserString("a" * self.LARGE_SIZE)

        small_time = measure_time(lambda: small_us.count("a"), iterations=50)
        large_time = measure_time(lambda: large_us.count("a"), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"UserString count doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
