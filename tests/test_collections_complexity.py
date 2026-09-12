"""Tests for ChainMap, UserDict, UserList and UserString in collections.md.

Timing tests vary mapping size or map count with fixed-cost keys and values.
"""

from collections import ChainMap, UserDict, UserList, UserString

import pytest

from tests.collection_timing import is_constant_time, is_linear_time, measure_time


class TestChainMapComplexity:
    """Test ChainMap operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000

    @pytest.mark.timing
    def test_lookup_is_o1_avg(self) -> None:
        """Lookup should be O(1) average (first mapping)."""
        small_map = ChainMap({i: i for i in range(self.SMALL_SIZE)})
        large_map = ChainMap({i: i for i in range(self.LARGE_SIZE)})

        small_time = measure_time(lambda: small_map[self.SMALL_SIZE - 1], iterations=200)
        large_time = measure_time(lambda: large_map[self.LARGE_SIZE - 1], iterations=200)

        assert is_constant_time(small_time, large_time), (
            f"ChainMap lookup appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )


class TestUserDictComplexity:
    """Test UserDict operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000

    @pytest.mark.timing
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

    @pytest.mark.timing
    def test_len_is_o1(self) -> None:
        """len() should be O(1)."""
        small_ul = UserList(range(self.SMALL_SIZE))
        large_ul = UserList(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: len(small_ul))
        large_time = measure_time(lambda: len(large_ul))

        assert is_constant_time(small_time, large_time), (
            f"UserList len appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
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

    @pytest.mark.timing
    def test_len_is_o1(self) -> None:
        """len() should be O(1)."""
        small_us = UserString("a" * self.SMALL_SIZE)
        large_us = UserString("a" * self.LARGE_SIZE)

        small_time = measure_time(lambda: len(small_us))
        large_time = measure_time(lambda: len(large_us))

        assert is_constant_time(small_time, large_time), (
            f"UserString len appears non-constant: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
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

    @pytest.mark.timing
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

    @pytest.mark.timing
    def test_a_miss_visits_every_map(self) -> None:
        few, many = self._chain(self.FEW_MAPS), self._chain(self.MANY_MAPS)

        few_time = measure_time(lambda: "absent" in few, iterations=200)
        many_time = measure_time(lambda: "absent" in many, iterations=200)

        assert many_time > few_time * 3, (
            f"a miss is the worst case for `in`: {few_time:.2e}s vs {many_time:.2e}s"
        )

    @pytest.mark.timing
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
