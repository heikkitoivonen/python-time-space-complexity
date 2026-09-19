"""Tests for docs/stdlib/collections.md.

The page prices `ChainMap` in the maps it searches and the wrappers in the
calls they forward: a read walks the chain until a map has the key, a write
touches `maps[0]` alone, `len()` and iteration visit every entry, and each
`User*` wrapper hands the operation to its `data` or, where it defines
nothing, to a `collections.abc` mixin that calls the wrapper's own hooks once
per item. Call counts on recording maps and subclasses, identity checks and
traced allocation settle nearly every row; a stopwatch is used only for the
two growth classes without a counter, the quadratic `UserDict.clear()` and
the constant `UserString.isascii()`.

Measurement scope:

* `ChainMap(*maps)` holds the maps it is given: `maps[0]` is the same object
  that was passed, and building a chain over two 100,000-entry dicts peaks
  under 5 KB. `cm[key]`, `key in cm` and `cm.get()` are counted on a chain of
  five recording dicts with one key each: a key in map i costs i
  `__getitem__` or `__contains__` calls, a miss costs five and raises
  `KeyError`, and `get()` on a hit costs i of each. `bool()` is counted at one
  `__len__` call when the first map is non-empty and five when every map is
  empty. Writes are asserted on which map changed: `cm[key] = v`, `pop()`,
  `popitem()`, `clear()`, `update()` and `|=` reach `maps[0]` and leave the
  rest equal to what they held, `del` of a key held only by a later map raises
  `KeyError`, and `setdefault()` returns a later map's value without writing.
* `len(cm)` and `iter(cm)` iterate each of five recording maps exactly once,
  and their peak allocation over a chain of 200,000 entries is more than 20x
  the peak over 2,000. Iteration order is asserted on a two-map chain with a
  shared key. `dict(cm)`, `list(cm.items())` and `list(cm.values())` on the
  five-map chain each cost 5 + 4 + 3 + 2 + 1 `__getitem__` calls, one search
  per key. `cm == dict` over 100,000 entries peaks above 1 MB, against a
  zero peak for the same two dicts compared directly.
* `new_child()` shares every existing map and puts the given map, or a fresh
  dict of the keyword arguments, in front, writing the keyword arguments into
  the given map when both are supplied; `parents` shares the maps in a new
  list; `copy()` copies `maps[0]` and shares the rest; `fromkeys()` makes a
  one-map chain; `cm | other` leaves `cm` untouched; `other | cm` is a one-map
  chain whose values follow the chain's precedence.
* `UserDict`: a recording `__setitem__` counts k calls for construction from
  a dict and from keyword arguments, k for `update()`, k for `fromkeys()`,
  zero for `|=`, n + k on the result of `|`, and n for a subclass's `copy()`;
  a plain `UserDict.copy()` has a distinct, equal `data`. `iter(ud)` is the
  dict's own iterator type, and `items()` and `values()` call a recording
  `__getitem__` once per key. `__missing__` is asserted to run for `ud[key]`
  and, on 3.12+, not for `get()`; before 3.12 `get()` returns what
  `__missing__` returns. `popitem()` removes the first key in iteration order,
  `clear()` empties the dict, and a timing test puts `clear()` on 32,000
  entries above 20x its cost on 4,000, where linear growth would give 8x.
  `ud == dict` over 100,000 entries peaks above 1 MB, against zero for
  `ud.data == dict`.
* `UserList`: construction copies a list and a `UserList` and consumes a
  generator; a recording `__init__` runs once for a slice, `copy()`, `+` and
  `*`; a recording `__getitem__` is called n + 1 times by `list(ul)` and n
  times by `list(reversed(ul))`; `count()`, `index()`, `reverse()`, `sort()`,
  `append()`, `insert()`, `pop()`, `remove()`, `clear()` and `extend()` are
  observed to call the same-named method on a recording `data`; `+=` accepts
  a generator; `==` and `<` compare against a list and against another
  `UserList`.
* `UserString`: `data` is the `str` passed in, and a non-`str` argument is
  converted with `str()`. Indexing, slicing, iteration and the eighteen
  text-returning methods return `type(us)`, a subclass included; the five
  splitting methods return plain `str` inside a `list` or `tuple`; `join()`,
  `format()` and `format_map()` return `str`, `encode()` returns `bytes`, the
  searches return `int` or `bool`, and the predicates return `bool`.
  `str(us)` is `data` itself and `hash(us)` equals `hash(data)`. `+` with a
  non-`str` operand goes through `str()`; comparisons work against a `str`
  and a `UserString`; `maketrans` is `str.maketrans`; `int()` of a
  5,000-digit `UserString` raises `ValueError` under the default digit limit
  and `float()` of the same converts. A timing test puts `isascii()` on a
  million-character string under 3x its cost on a thousand.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* Operations the wrappers forward are priced by the dict, list, str and int
  pages; the tests here show the forwarding, not the forwarded bound. The
  `O(n + k)` search row is the str page's average case, and `int(us)` is the
  int page's digit conversion.
* Key hashing and comparison are treated as O(1); an expensive `__hash__` on
  a key multiplies every mapping row.
* `UserDict.popitem()` is priced in the entries deleted before the one it
  removes. The timing test shows the quadratic total of `clear()`; that the
  per-call cost is the skipped slots is read from Objects/dictobject.c's
  iterator, which scans entries from the start of the table.
* The `deque`, `defaultdict`, `Counter`, `namedtuple` and `OrderedDict` pages
  have their own test files.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import ChainMap, UserDict, UserList, UserString
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "collections.md"
EXPECTED_BLOCKS = 6


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class RecordingDict(dict[str, int]):
    """A dict that counts the calls a ChainMap makes on it."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.getitem = 0
        self.contains = 0
        self.iterations = 0
        self.lengths = 0

    def __getitem__(self, key: str) -> int:
        self.getitem += 1
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        self.contains += 1
        return super().__contains__(key)

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        return super().__iter__()

    def __len__(self) -> int:
        self.lengths += 1
        return super().__len__()

    def reset(self) -> None:
        self.getitem = self.contains = self.iterations = self.lengths = 0


def five_maps() -> tuple[ChainMap[str, int], list[RecordingDict]]:
    """A chain of five maps, map i (1-based) holding the single key `k<i>`."""
    maps = [RecordingDict({f"k{index}": index}) for index in range(1, 6)]
    return ChainMap(*maps), maps


class TestChainMapReadsWalkTheChain:
    """`cm[key]` | O(i), `key in cm` | O(i), `cm.get()` | O(i) twice, and
    `bool(cm)` | O(n): counted on recording maps."""

    def test_construction_holds_the_maps_it_is_given(self) -> None:
        first: dict[int, int] = {index: index for index in range(100_000)}
        second: dict[int, int] = {-index: index for index in range(1, 100_000)}

        peak = peak_bytes(lambda: ChainMap(first, second))
        chain = ChainMap(first, second)

        assert chain.maps[0] is first and chain.maps[1] is second
        assert peak < 5_000, f"building a chain over 200,000 entries allocated {peak} bytes"

    @pytest.mark.parametrize("position", [1, 3, 5])
    def test_a_read_tries_maps_up_to_the_one_that_has_the_key(self, position: int) -> None:
        chain, maps = five_maps()

        assert chain[f"k{position}"] == position
        assert [m.getitem for m in maps] == [1] * position + [0] * (5 - position)

        for m in maps:
            m.reset()
        assert f"k{position}" in chain
        assert [m.contains for m in maps] == [1] * position + [0] * (5 - position)

    def test_a_miss_tries_every_map(self) -> None:
        chain, maps = five_maps()

        with pytest.raises(KeyError):
            chain["absent"]
        assert [m.getitem for m in maps] == [1] * 5

        for m in maps:
            m.reset()
        assert "absent" not in chain
        assert [m.contains for m in maps] == [1] * 5

    def test_get_searches_twice_on_a_hit(self) -> None:
        chain, maps = five_maps()

        assert chain.get("k3") == 3

        assert [m.contains for m in maps] == [1, 1, 1, 0, 0]
        assert [m.getitem for m in maps] == [1, 1, 1, 0, 0]

    def test_get_on_a_miss_searches_once_and_returns_the_default(self) -> None:
        chain, maps = five_maps()
        marker = object()

        assert chain.get("absent", marker) is marker

        assert [m.contains for m in maps] == [1] * 5
        assert [m.getitem for m in maps] == [0] * 5

    def test_truth_stops_at_the_first_non_empty_map(self) -> None:
        chain, maps = five_maps()

        assert bool(chain) is True
        assert [m.lengths for m in maps] == [1, 0, 0, 0, 0]

    def test_truth_of_an_empty_chain_checks_every_map(self) -> None:
        maps = [RecordingDict() for _ in range(5)]
        chain = ChainMap(*maps)

        assert bool(chain) is False
        assert [m.lengths for m in maps] == [1] * 5


class TestChainMapWritesReachTheFirstMap:
    """`cm[key] = v`, `del`, `pop()`, `popitem()`, `clear()`, `update()`,
    `|=` | O(1) or O(k) on `maps[0]`; `setdefault()` | O(i)."""

    @staticmethod
    def _chain() -> tuple[ChainMap[str, int], dict[str, int], dict[str, int]]:
        first = {"a": 1}
        second = {"a": 10, "b": 20}
        return ChainMap(first, second), first, second

    def test_assignment_pop_and_popitem_touch_only_the_first_map(self) -> None:
        chain, first, second = self._chain()

        chain["c"] = 3
        assert first == {"a": 1, "c": 3}
        assert chain.pop("c") == 3
        assert chain.popitem() == ("a", 1)
        assert first == {}
        assert second == {"a": 10, "b": 20}

    def test_deleting_a_key_held_only_by_a_later_map_raises(self) -> None:
        chain, first, second = self._chain()

        del chain["a"]
        assert first == {}
        with pytest.raises(KeyError, match="first mapping"):
            del chain["a"]
        assert second == {"a": 10, "b": 20}

    def test_pop_of_a_key_held_only_by_a_later_map_raises(self) -> None:
        chain, _, second = self._chain()

        with pytest.raises(KeyError, match="first mapping"):
            chain.pop("b")
        assert second == {"a": 10, "b": 20}

    def test_clear_empties_only_the_first_map(self) -> None:
        chain, first, second = self._chain()

        chain.clear()

        assert first == {}
        assert second == {"a": 10, "b": 20}
        assert chain["b"] == 20

    def test_update_and_inplace_or_write_into_the_first_map(self) -> None:
        chain, first, second = self._chain()

        chain.update({"x": 1}, y=2)
        chain |= {"z": 3}

        assert first == {"a": 1, "x": 1, "y": 2, "z": 3}
        assert second == {"a": 10, "b": 20}

    def test_setdefault_returns_a_later_value_without_writing(self) -> None:
        chain, first, second = self._chain()

        assert chain.setdefault("b", 99) == 20
        assert first == {"a": 1}

        assert chain.setdefault("c", 99) == 99
        assert first == {"a": 1, "c": 99}
        assert second == {"a": 10, "b": 20}


class TestChainMapCountingAndIterationCostEveryKey:
    """`len(cm)` | O(n + N) | O(n + N), iterating `cm` | O(n + N) | O(N), `items()`,
    `values()` and `dict(cm)` | O(n + N·n), `cm == other` | O(n + N·n + k) | O(N + k)."""

    SMALL = 1_000
    LARGE = 100_000

    @staticmethod
    def _chain(size: int) -> ChainMap[int, int]:
        return ChainMap(
            {index: index for index in range(size)}, {-index: index for index in range(1, size)}
        )

    def test_len_iterates_every_map_once(self) -> None:
        chain, maps = five_maps()

        assert len(chain) == 5

        assert [m.iterations for m in maps] == [1] * 5
        assert [m.getitem for m in maps] == [0] * 5

    def test_len_allocates_in_proportion_to_the_entries(self) -> None:
        small, large = self._chain(self.SMALL), self._chain(self.LARGE)

        small_peak = peak_bytes(lambda: len(small))
        large_peak = peak_bytes(lambda: len(large))

        assert large_peak > small_peak * 20, (
            f"len() over {2 * self.LARGE} entries peaked at {large_peak} bytes, "
            f"over {2 * self.SMALL} at {small_peak}"
        )

    def test_iter_builds_every_key_before_yielding_one(self) -> None:
        chain, maps = five_maps()

        iterator = iter(chain)

        assert [m.iterations for m in maps] == [1] * 5
        assert next(iterator) == "k5"

    def test_starting_an_iterator_allocates_in_proportion_to_the_entries(self) -> None:
        small, large = self._chain(self.SMALL), self._chain(self.LARGE)

        small_peak = peak_bytes(lambda: iter(small))
        large_peak = peak_bytes(lambda: iter(large))

        assert large_peak > small_peak * 20, (
            f"iter() over {2 * self.LARGE} entries peaked at {large_peak} bytes, "
            f"over {2 * self.SMALL} at {small_peak}"
        )

    def test_iteration_order_is_last_map_first(self) -> None:
        chain = ChainMap({"a": 1, "b": 2}, {"c": 3, "a": 0})

        assert list(chain) == ["c", "a", "b"]
        assert list(chain.keys()) == ["c", "a", "b"]

    @pytest.mark.parametrize(
        "flatten",
        [dict, lambda chain: list(chain.items()), lambda chain: list(chain.values())],
        ids=["dict", "items", "values"],
    )
    def test_flattening_searches_the_chain_once_per_key(
        self, flatten: Callable[[ChainMap[str, int]], Any]
    ) -> None:
        chain, maps = five_maps()

        flatten(chain)

        assert [m.getitem for m in maps] == [5, 4, 3, 2, 1]

    def test_dict_of_a_chain_keeps_the_first_value_for_each_key(self) -> None:
        chain = ChainMap({"a": 1, "b": 2}, {"c": 3, "a": 0})

        assert dict(chain) == {"a": 1, "b": 2, "c": 3}

    def test_equality_flattens_both_sides(self) -> None:
        chain = ChainMap({index: index for index in range(self.LARGE)})
        other = dict(chain.maps[0])

        chain_peak = peak_bytes(lambda: chain == other)
        dict_peak = peak_bytes(lambda: chain.maps[0] == other)

        assert chain == other
        assert dict_peak < 5_000, f"dict == dict allocated {dict_peak} bytes"
        assert chain_peak > 1_000_000, f"ChainMap == dict allocated only {chain_peak} bytes"


class TestChainMapDerivedChains:
    """`new_child()` | O(n + k), `parents` | O(n), `copy()` | O(m + n),
    `fromkeys()` | O(k), `cm | other` | O(m + n + k), `other | cm` | O(n + N + k)."""

    def test_new_child_shares_the_maps_and_adds_one_in_front(self) -> None:
        first, second = {"a": 1}, {"b": 2}
        chain = ChainMap(first, second)

        child = chain.new_child()

        assert child.maps[1:] == [first, second]
        assert child.maps[1] is first and child.maps[2] is second
        assert child.maps[0] == {} and child.maps[0] is not first

    def test_new_child_uses_the_given_map_and_writes_keywords_into_it(self) -> None:
        chain = ChainMap({"a": 1})
        front = {"b": 2}

        child = chain.new_child(front, c=3)  # pyright: ignore[reportCallIssue]

        assert child.maps[0] is front
        assert front == {"b": 2, "c": 3}

    def test_new_child_without_a_map_holds_the_keywords_in_a_fresh_dict(self) -> None:
        chain = ChainMap({"a": 1})

        child = chain.new_child(c=3)  # pyright: ignore[reportCallIssue]

        assert child.maps[0] == {"c": 3}
        assert chain.maps == [{"a": 1}]

    def test_parents_shares_the_maps_in_a_new_list(self) -> None:
        first, second, third = {"a": 1}, {"b": 2}, {"c": 3}
        chain = ChainMap(first, second, third)

        parents = chain.parents

        assert parents.maps == [second, third]
        assert parents.maps[0] is second and parents.maps[1] is third
        assert parents.maps is not chain.maps

    def test_copy_copies_the_first_map_and_shares_the_rest(self) -> None:
        first, second = {"a": 1}, {"b": 2}
        chain = ChainMap(first, second)

        copied = chain.copy()

        assert copied.maps[0] == first and copied.maps[0] is not first
        assert copied.maps[1] is second

    def test_fromkeys_is_a_one_map_chain(self) -> None:
        chain = ChainMap.fromkeys("ab", 0)

        assert chain.maps == [{"a": 0, "b": 0}]

    def test_or_copies_and_leaves_the_original_alone(self) -> None:
        first, second = {"a": 1}, {"b": 2}
        chain = ChainMap(first, second)

        merged = chain | {"c": 3}

        assert merged.maps[0] == {"a": 1, "c": 3}
        assert merged.maps[1] is second
        assert first == {"a": 1}

    def test_reflected_or_flattens_into_one_map(self) -> None:
        chain = ChainMap({"a": 1, "b": 2}, {"c": 3, "a": 0})

        flat = {"z": 26} | chain

        assert isinstance(flat, ChainMap)
        assert flat.maps == [{"z": 26, "c": 3, "a": 1, "b": 2}]


class RecordingUserDict(UserDict[str, int]):
    """A UserDict subclass whose hooks count their calls."""

    writes: int
    reads: int

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.writes = 0
        self.reads = 0
        super().__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: int) -> None:
        self.writes += 1
        super().__setitem__(key, value)

    def __getitem__(self, key: str) -> int:
        self.reads += 1
        return super().__getitem__(key)


class WithMissing(UserDict[str, str]):
    def __missing__(self, key: str) -> str:
        return f"default for {key}"


class TestUserDictGoesThroughItsHooks:
    """`UserDict()`, `update()`, `fromkeys()` | O(k) in `__setitem__` calls;
    `|=` | one `dict.update`; `|` | O(n + k) through `__setitem__` again;
    `copy()` | O(n); `items()`, `values()` | one `ud[key]` per key."""

    def test_construction_writes_once_per_item(self) -> None:
        from_dict = RecordingUserDict({"a": 1, "b": 2, "c": 3})
        from_keywords = RecordingUserDict(a=1, b=2)
        from_both = RecordingUserDict({"a": 1}, b=2, c=3)

        assert from_dict.writes == 3
        assert from_keywords.writes == 2
        assert from_both.writes == 3
        assert isinstance(from_dict.data, dict) and from_dict.data == {"a": 1, "b": 2, "c": 3}

    def test_update_and_fromkeys_write_once_per_item(self) -> None:
        recorded = RecordingUserDict()

        recorded.update({"a": 1, "b": 2}, c=3)
        assert recorded.writes == 3

        built = RecordingUserDict.fromkeys("xyz", 0)
        assert isinstance(built, RecordingUserDict)
        assert built.writes == 3 and built.data == {"x": 0, "y": 0, "z": 0}

    def test_inplace_or_bypasses_the_hook(self) -> None:
        recorded = RecordingUserDict({"a": 1})

        recorded |= {"b": 2, "c": 3}

        assert recorded.writes == 1
        assert recorded.data == {"a": 1, "b": 2, "c": 3}

    def test_or_feeds_the_merged_dict_back_through_the_hook(self) -> None:
        recorded = RecordingUserDict({"a": 1, "b": 2})

        merged = recorded | {"c": 3}

        assert isinstance(merged, RecordingUserDict)
        assert merged.writes == 3
        assert recorded.writes == 2

    def test_copy_of_a_subclass_refills_through_the_hook(self) -> None:
        recorded = RecordingUserDict({"a": 1, "b": 2})
        recorded.writes = 0  # the shallow copy inherits the counter

        copied = recorded.copy()

        assert type(copied) is RecordingUserDict
        assert copied.data == recorded.data and copied.data is not recorded.data
        assert copied.writes == 2
        assert recorded.writes == 0

    def test_copy_of_a_plain_userdict_copies_the_data(self) -> None:
        wrapped = UserDict({"a": 1})

        copied = wrapped.copy()

        assert type(copied) is UserDict
        assert copied.data == wrapped.data and copied.data is not wrapped.data

    def test_iteration_is_the_dicts_own(self) -> None:
        wrapped = UserDict({"a": 1, "b": 2})

        assert type(iter(wrapped)) is type(iter({}))
        assert list(wrapped) == ["a", "b"]

    def test_items_and_values_read_once_per_key(self) -> None:
        recorded = RecordingUserDict({"a": 1, "b": 2, "c": 3})

        assert list(recorded.items()) == [("a", 1), ("b", 2), ("c", 3)]
        assert recorded.reads == 3

        assert list(recorded.values()) == [1, 2, 3]
        assert recorded.reads == 6

        assert list(recorded.keys()) == ["a", "b", "c"]
        assert recorded.reads == 6

    def test_getitem_runs_missing_and_membership_does_not(self) -> None:
        wrapped = WithMissing()

        assert wrapped["x"] == "default for x"
        assert "x" not in wrapped
        assert wrapped.data == {}

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="3.12+ bypasses __missing__")
    def test_get_bypasses_missing_from_312(self) -> None:
        assert WithMissing().get("x") is None
        assert WithMissing().get("x", "fallback") == "fallback"

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="before 3.12 get() ran __missing__")
    def test_get_runs_missing_before_312(self) -> None:
        assert WithMissing().get("x") == "default for x"

    def test_pop_and_setdefault(self) -> None:
        wrapped = UserDict({"a": 1})

        assert wrapped.pop("a") == 1 and wrapped.data == {}
        assert wrapped.setdefault("b", 2) == 2
        assert wrapped.setdefault("b", 3) == 2
        assert wrapped.data == {"b": 2}


class TestUserDictEmptying:
    """`popitem()` | O(d) and `clear()` | O(n·(n + d)): the mixin pops the first key
    of a fresh iterator each time."""

    SMALL = 4_000
    LARGE = 32_000

    def test_popitem_removes_the_first_key_in_iteration_order(self) -> None:
        wrapped = UserDict({"a": 1, "b": 2, "c": 3})

        assert wrapped.popitem() == ("a", 1)
        assert wrapped.popitem() == ("b", 2)
        assert wrapped.data == {"c": 3}

    def test_clear_empties_the_dict(self) -> None:
        wrapped = UserDict({"a": 1, "b": 2})

        wrapped.clear()

        assert wrapped.data == {}

    @pytest.mark.timing
    def test_clear_grows_faster_than_the_dict(self) -> None:
        """Eight times the entries costs far more than eight times the time."""

        def clear(size: int) -> float:
            best: float | None = None
            for _ in range(3):
                wrapped = UserDict({index: index for index in range(size)})
                start = time.perf_counter_ns()
                wrapped.clear()
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        small_ns, large_ns = clear(self.SMALL), clear(self.LARGE)

        assert large_ns > small_ns * 20, (
            f"clear() on {self.LARGE} entries took {large_ns / 1e6:.1f} ms, on {self.SMALL} "
            f"{small_ns / 1e6:.1f} ms; a linear clear would be near 8x"
        )

    def test_equality_flattens_both_sides(self) -> None:
        wrapped = UserDict({index: index for index in range(100_000)})
        other = dict(wrapped.data)

        wrapped_peak = peak_bytes(lambda: wrapped == other)
        dict_peak = peak_bytes(lambda: wrapped.data == other)

        assert wrapped == other
        assert dict_peak < 5_000, f"dict == dict allocated {dict_peak} bytes"
        assert wrapped_peak > 1_000_000, f"UserDict == dict allocated only {wrapped_peak} bytes"


class RecordingList(list[int]):
    """A list that records which of its methods a UserList forwards to."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.calls: list[str] = []

    def __getattribute__(self, name: str) -> Any:
        if name in {
            "count",
            "index",
            "reverse",
            "sort",
            "append",
            "insert",
            "pop",
            "remove",
            "clear",
            "extend",
        }:
            object.__getattribute__(self, "calls").append(name)
        return object.__getattribute__(self, name)


class ConstructedList(UserList[int]):
    """A UserList subclass that counts how often it is constructed."""

    constructions = 0

    def __init__(self, initlist: Any = None) -> None:
        ConstructedList.constructions += 1
        super().__init__(initlist)


class IndexedList(UserList[int]):
    """A UserList subclass that counts `__getitem__` calls."""

    reads = 0

    def __getitem__(self, index: Any) -> Any:
        IndexedList.reads += 1
        return super().__getitem__(index)


class TestUserListForwardsAndRebuilds:
    """`UserList()` | O(k) copies; slicing, `copy()`, `+`, `*` | rebuilt
    through `__init__`; `iter()`, `reversed()` | one `ul[i]` per item; the
    named methods | forwarded to `data`."""

    def test_construction_copies_a_list_and_a_userlist_and_consumes_an_iterable(self) -> None:
        source = [1, 2, 3]

        from_list = UserList(source)
        from_userlist = UserList(from_list)
        generator = (value for value in source)
        from_generator = UserList(generator)

        assert from_list.data == source and from_list.data is not source
        assert from_userlist.data == source and from_userlist.data is not from_list.data
        assert from_generator.data == source
        assert list(generator) == []

    def test_slice_copy_add_and_mul_construct_the_subclass(self) -> None:
        ConstructedList.constructions = 0
        wrapped = ConstructedList([1, 2, 3])
        assert ConstructedList.constructions == 1

        for result in (wrapped[0:2], wrapped.copy(), wrapped + [4], wrapped * 2):
            assert type(result) is ConstructedList
        assert ConstructedList.constructions == 5
        assert type(wrapped[0]) is int

    def test_iteration_indexes_one_item_at_a_time(self) -> None:
        IndexedList.reads = 0
        wrapped = IndexedList([10, 20, 30])

        assert list(wrapped) == [10, 20, 30]
        assert IndexedList.reads == 4, "n items plus the IndexError at ul[n]"

        IndexedList.reads = 0
        assert list(reversed(wrapped)) == [30, 20, 10]
        assert IndexedList.reads == 3

    def test_named_methods_are_forwarded_to_data(self) -> None:
        wrapped = UserList([3, 1, 2])
        recording = RecordingList(wrapped.data)
        wrapped.data = recording

        wrapped.append(4)
        wrapped.insert(0, 0)
        assert wrapped.pop() == 4
        wrapped.remove(0)
        assert wrapped.count(1) == 1
        assert wrapped.index(2) == 2
        wrapped.reverse()
        wrapped.sort()
        wrapped.extend([5])
        wrapped.clear()

        assert recording.calls == [
            "append",
            "insert",
            "pop",
            "remove",
            "count",
            "index",
            "reverse",
            "sort",
            "extend",
            "clear",
        ]

    def test_inplace_add_accepts_any_iterable(self) -> None:
        wrapped = UserList([1])

        wrapped += (value for value in (2, 3))
        wrapped += UserList([4])

        assert wrapped.data == [1, 2, 3, 4]

    def test_comparisons_accept_lists_and_userlists(self) -> None:
        wrapped = UserList([1, 2])

        assert wrapped == [1, 2]
        assert wrapped == UserList([1, 2])
        assert wrapped < [1, 3]
        assert wrapped < UserList([2])


class Tagged(UserString):
    """A UserString subclass, to show the result type follows the instance."""


class TestUserStringResultTypes:
    """`UserString(seq)` | O(1) holds the str; text-returning methods |
    `type(us)`; container-returning methods | plain str inside; searches and
    predicates | plain int and bool."""

    WRAPPING = (
        "capitalize",
        "casefold",
        "lower",
        "lstrip",
        "rstrip",
        "strip",
        "swapcase",
        "title",
        "upper",
    )

    def test_a_str_is_held_and_anything_else_is_converted(self) -> None:
        source = "abc"

        assert UserString(source).data is source
        assert UserString(12).data == "12"
        assert UserString(UserString(source)).data == source

    def test_indexing_slicing_and_iteration_wrap_each_result(self) -> None:
        text = Tagged("abc")

        assert type(text[0]) is Tagged and text[0] == "a"
        assert type(text[1:]) is Tagged and text[1:] == "bc"
        characters = list(text)
        assert all(type(char) is Tagged for char in characters)
        assert characters == ["a", "b", "c"]

    def test_text_returning_methods_wrap(self) -> None:
        text = Tagged("  Ab\tc  ")

        for name in self.WRAPPING:
            assert type(getattr(text, name)()) is Tagged, name
        assert type(text.center(20)) is Tagged
        assert type(text.ljust(20)) is Tagged
        assert type(text.rjust(20)) is Tagged
        assert type(text.zfill(20)) is Tagged
        assert type(text.expandtabs()) is Tagged
        assert type(text.removeprefix("  ")) is Tagged
        assert type(text.removesuffix("  ")) is Tagged
        assert type(text.replace("A", "a")) is Tagged
        assert type(text.translate({ord("A"): "a"})) is Tagged
        assert type(text + "x") is Tagged and type("x" + text) is Tagged
        assert type(text * 2) is Tagged
        assert type(Tagged("%s") % "x") is Tagged

    def test_container_returning_methods_hold_plain_str(self) -> None:
        text = Tagged("a b\nc")

        for result in (text.split(), text.rsplit(), text.splitlines()):
            assert type(result) is list and all(type(part) is str for part in result)
        for result in (text.partition(" "), text.rpartition(" ")):
            assert type(result) is tuple and all(type(part) is str for part in result)

    def test_join_format_and_encode_return_plain_objects(self) -> None:
        text = Tagged("-")

        assert type(text.join(["a", "b"])) is str
        assert type(Tagged("{}").format(1)) is str
        assert type(Tagged("{x}").format_map({"x": 1})) is str
        assert type(text.encode()) is bytes

    def test_searches_and_predicates_return_plain_values(self) -> None:
        text = Tagged("abcabc")

        assert type(text.count("a")) is int and text.count("a") == 2
        assert type(text.find("c")) is int and text.rfind("c") == 5
        assert text.index("b") == 1 and text.rindex("b") == 4
        assert type(text.startswith("ab")) is bool and text.endswith("bc")
        assert ("bca" in text) is True
        for name in (
            "isalnum",
            "isalpha",
            "isascii",
            "isdecimal",
            "isdigit",
            "isidentifier",
            "islower",
            "isnumeric",
            "isprintable",
            "isspace",
            "istitle",
            "isupper",
        ):
            assert type(getattr(text, name)()) is bool, name

    def test_str_hash_and_comparisons(self) -> None:
        source = "abc"
        text = UserString(source)

        assert str(text) is source
        assert hash(text) == hash(source)
        assert text == "abc" and text == UserString("abc")
        assert text < "abd" and text < UserString("b")
        assert UserString(1) + 2 == "12"

    def test_maketrans_and_numeric_conversions(self) -> None:
        assert UserString.maketrans("a", "b") == str.maketrans("a", "b")
        digits = UserString("1" * 5_000)

        with pytest.raises(ValueError, match="digits"):
            int(digits)
        assert float(digits) == float("1" * 5_000)
        assert complex(UserString("1+2j")) == 1 + 2j

    @pytest.mark.timing
    def test_isascii_does_not_grow_with_the_string(self) -> None:
        short, long = UserString("a" * 1_000), UserString("a" * 1_000_000)

        short_ns = best_ns(short.isascii, inner=200)
        long_ns = best_ns(long.isascii, inner=200)

        assert long_ns < short_ns * 3, (
            f"isascii() took {long_ns:.0f}ns on a million characters and {short_ns:.0f}ns on "
            "a thousand"
        )


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


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "assert len(chain) == 3" in s)
        mutated = source.replace("assert len(chain) == 3", "assert len(chain) == 4", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
