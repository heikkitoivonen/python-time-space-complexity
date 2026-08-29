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


class TestChainMapScalesWithMapCount:
    """The ChainMap table is written in the number of maps, not their size.

    TestChainMapComplexity above varies the size of a single mapping, which
    leaves the table's actual claims - access O(n), `in` O(n), len() O(N) -
    untested.
    """

    FEW_MAPS = 2
    MANY_MAPS = 200
    KEYS_PER_MAP = 100

    def _chain(self, map_count: int) -> ChainMap:
        return ChainMap(
            *[
                {f"k{index}_{key}": key for key in range(self.KEYS_PER_MAP)}
                for index in range(map_count)
            ]
        )

    def test_lookup_scales_with_the_number_of_maps(self) -> None:
        """A key in the last map is found only after searching the rest."""
        few, many = self._chain(self.FEW_MAPS), self._chain(self.MANY_MAPS)
        few_key = f"k{self.FEW_MAPS - 1}_50"
        many_key = f"k{self.MANY_MAPS - 1}_50"

        few_time = measure_time(lambda: few[few_key], iterations=200)
        many_time = measure_time(lambda: many[many_key], iterations=200)

        assert many_time > few_time * 3, (
            f"lookup should search map by map: {self.FEW_MAPS} maps "
            f"{few_time:.2e}s, {self.MANY_MAPS} maps {many_time:.2e}s"
        )

    def test_a_miss_visits_every_map(self) -> None:
        few, many = self._chain(self.FEW_MAPS), self._chain(self.MANY_MAPS)

        few_time = measure_time(lambda: "absent" in few, iterations=200)
        many_time = measure_time(lambda: "absent" in many, iterations=200)

        assert many_time > few_time * 3, (
            f"a miss is the worst case for `in`: {few_time:.2e}s vs {many_time:.2e}s"
        )

    def test_len_builds_a_union_of_every_key(self) -> None:
        """The table's O(N) in total keys, not O(1) like a dict's len()."""
        few, many = self._chain(self.FEW_MAPS), self._chain(self.MANY_MAPS)

        few_time = measure_time(lambda: len(few), iterations=20)
        many_time = measure_time(lambda: len(many), iterations=20)

        assert many_time > few_time * 10, (
            f"len() unions every key: {few_time:.2e}s vs {many_time:.2e}s"
        )

    def test_lookup_finds_the_first_match(self) -> None:
        first = {"shared": "first", "only_first": 1}
        second = {"shared": "second", "only_second": 2}
        chained = ChainMap(first, second)

        assert chained["shared"] == "first"
        assert chained["only_second"] == 2

    def test_writes_go_to_the_first_map_only(self) -> None:
        first: dict[str, int] = {}
        second = {"key": 1}
        chained = ChainMap(first, second)

        chained["key"] = 99

        assert first == {"key": 99}
        assert second == {"key": 1}, "the underlying map is untouched"


class TestCounterOperations:
    """The Counter table rows that had no test.

    most_common() is the interesting one: the O(n log k) bound is right, and
    it is still the slower choice for any k above 1.
    """

    SIZE = 200_000

    def _counter(self, size: int) -> Counter:
        return Counter({f"k{index}": index for index in range(size)})

    def test_construction_is_on(self) -> None:
        small_items = list(range(1_000))
        large_items = list(range(100_000))

        small_time = measure_time(lambda: Counter(small_items), iterations=10)
        large_time = measure_time(lambda: Counter(large_items), iterations=10)

        assert is_linear_time(small_time, large_time, 100), (
            f"Counter() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_heap_path_beats_sorting_on_realistic_data(self) -> None:
        """most_common(k) is the faster choice on data that looks like data.

        An earlier version of this file asserted the opposite, having
        benchmarked only counts that increase in iteration order - the one
        ordering that defeats the heap. On random counts the heap wins by
        roughly eight times, because nlargest settles on a high threshold
        early and stops replacing, while Timsort has no runs to exploit.
        """
        import random

        rng = random.Random(7)
        counter = Counter({f"k{i}": rng.randrange(self.SIZE) for i in range(self.SIZE)})

        sorted_time = measure_time(counter.most_common, iterations=3)
        heap_time = measure_time(lambda: counter.most_common(10), iterations=3)

        assert heap_time < sorted_time, (
            f"on random counts the heap should win: k=10 {heap_time:.2e}s all {sorted_time:.2e}s"
        )

    def test_heap_path_loses_when_counts_rise_in_iteration_order(self) -> None:
        """The adversarial ordering, kept because it is what misled us.

        Every element beats the current top, so each one costs a
        heapreplace; meanwhile the input is already sorted, which is
        Timsort's best case. Benchmarking only this shape is how the docs
        came to claim that passing k never pays.
        """
        counter = self._counter(self.SIZE)  # counts 0, 1, 2, ... in order

        sorted_time = measure_time(counter.most_common, iterations=3)
        heap_time = measure_time(lambda: counter.most_common(10), iterations=3)

        assert heap_time > sorted_time, (
            f"ascending counts are the heap's worst case: k=10 {heap_time:.2e}s "
            f"all {sorted_time:.2e}s"
        )

    def test_most_common_returns_what_it_claims(self) -> None:
        counter = Counter("aaabbc")
        assert counter.most_common(1) == [("a", 3)]
        assert counter.most_common() == [("a", 3), ("b", 2), ("c", 1)]

    def test_total_is_on(self) -> None:
        small, large = self._counter(1_000), self._counter(100_000)

        small_time = measure_time(small.total, iterations=20)
        large_time = measure_time(large.total, iterations=20)

        assert is_linear_time(small_time, large_time, 100), (
            f"total() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_elements_is_lazy_to_create(self) -> None:
        """The table: O(1) init, O(total) to iterate."""
        counter = self._counter(self.SIZE)

        create_time = measure_time(counter.elements, iterations=20)
        drain_time = measure_time(lambda: sum(1 for _ in Counter("aaab").elements()))

        assert create_time < drain_time * 50, (
            f"elements() should not do the work up front: {create_time:.2e}s"
        )

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


class TestNamedTupleCreationCosts:
    """The table's "Creation | O(1)" is about instances, not the class.

    Building the class execs generated source and costs about thirty times
    what an instance does, so it belongs at import time, not in a loop.
    """

    def test_building_the_class_costs_far_more_than_an_instance(self) -> None:
        point_class = namedtuple("Point", ["x", "y", "z"])

        class_time = measure_time(lambda: namedtuple("Point", ["x", "y", "z"]), iterations=20)
        instance_time = measure_time(lambda: point_class(1, 2, 3), iterations=200)

        assert class_time > instance_time * 10, (
            f"namedtuple() generates and execs a class: class={class_time:.2e}s "
            f"instance={instance_time:.2e}s"
        )

    def test_instance_creation_does_not_scale_with_field_count(self) -> None:
        few = namedtuple("Few", ["a", "b"])
        many = namedtuple("Many", [f"f{index}" for index in range(50)])
        many_values = tuple(range(50))

        few_time = measure_time(lambda: few(1, 2), iterations=200)
        many_time = measure_time(lambda: many(*many_values), iterations=200)

        assert many_time < few_time * 10, (
            f"a wider namedtuple is still a tuple: few={few_time:.2e}s many={many_time:.2e}s"
        )
