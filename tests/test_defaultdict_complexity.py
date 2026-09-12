"""Lookup tests for docs/stdlib/defaultdict.md.

Mapping size varies with integer keys and an int default factory.
"""

from collections import defaultdict
from typing import Any

import pytest

from tests.collection_timing import is_constant_time, measure_time


class TestDefaultDictComplexity:
    """Test defaultdict operation complexities."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000

    @pytest.mark.parametrize("size", [10, 1000])
    def test_copy_retains_factory_and_shares_values(self, size: int) -> None:
        original = defaultdict(list, {key: [key] for key in range(size)})
        copied = original.copy()
        assert copied is not original and copied == original
        assert len(copied) == size
        assert copied.default_factory is list
        assert all(copied[key] is original[key] for key in original)

    def test_factory_can_be_disabled_without_affecting_existing_keys(self) -> None:
        mapping = defaultdict(list, present=[1])
        mapping.default_factory = None
        assert mapping["present"] == [1]
        with pytest.raises(KeyError):
            mapping["missing"]
        assert "missing" not in mapping

    @pytest.mark.timing
    def test_missing_key_is_o1_avg(self) -> None:
        """Missing key access should be O(1) average."""
        small_dd: defaultdict[int, int] = defaultdict(int, {i: i for i in range(self.SMALL_SIZE)})
        large_dd: defaultdict[int, int] = defaultdict(int, {i: i for i in range(self.LARGE_SIZE)})

        def miss(mapping: defaultdict[int, int]) -> None:
            assert -1 not in mapping
            mapping[-1]
            del mapping[-1]

        small_time = measure_time(lambda: miss(small_dd), iterations=200)
        large_time = measure_time(lambda: miss(large_dd), iterations=200)

        assert is_constant_time(small_time, large_time), (
            f"defaultdict missing-key access appears non-constant: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )


class TestDefaultdictIncrementIsTwoOperations:
    """An increment performs a get and a set.

    On a missing key the factory also supplies and stores the initial value.
    """

    def test_existing_key_does_a_get_and_a_set(self) -> None:
        counts = _CountingDefaultDict(int)
        counts["k"] = 0
        counts.gets = counts.sets = 0

        counts["k"] += 1

        assert (counts.gets, counts.sets) == (1, 1)

    def test_missing_key_also_pays_for_the_factory(self) -> None:
        """The factory's insert is real work, counted or not.

        Counting __setitem__ is not the way to see it: between 3.14.2 and
        3.14.7, defaultdict.__missing__ stopped routing its insert through a
        subclass's __setitem__, so that instrument reads 1 on some versions
        and 2 on others while the dict ends up holding the factory's value
        either way. Observe the factory and the stored value instead, which
        every version agrees on.
        """
        calls = 0

        def factory() -> int:
            nonlocal calls
            calls += 1
            return 0

        # A bare missing lookup: the factory runs, and its value is stored
        # rather than merely returned.
        probe = _CountingDefaultDict(factory)
        probe["k"]

        assert calls == 1, "a missing key runs the factory"
        assert dict(probe) == {"k": 0}, "and the factory's value is stored, not just returned"

        # The documented expression pays for that on top of its own get and
        # store, which test_existing_key_does_a_get_and_a_set pins at one each.
        counts = _CountingDefaultDict(factory)
        counts["k"] += 1

        assert calls == 2, "the increment's missing key runs the factory too"
        assert counts.gets == 1
        assert dict(counts) == {"k": 1}, "and the increment stores over the factory's value"


class _CountingDefaultDict(defaultdict):  # type: ignore[type-arg]
    """A defaultdict that counts the dict operations performed on it."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.gets = 0
        self.sets = 0

    def __getitem__(self, key: Any) -> Any:
        self.gets += 1
        return super().__getitem__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        self.sets += 1
        super().__setitem__(key, value)
