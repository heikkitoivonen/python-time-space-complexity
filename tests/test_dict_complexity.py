"""Tests for docs/builtins/dict.md and docs/builtins/dict_func.md.

These cover the rows and paragraphs that pin the dict page to the official
CPython time-complexity table: iteration, `|` and `|=`, `update()` iterating
its argument, and the hash table that deletion does not shrink. They also
cover the dict page's rows beyond that table: collisions, `popitem()`,
removing the oldest key, equality and the views. The lookup rows are timed in
tests/test_builtin_complexity.py.

Measurement scope:

* Deletion is observed through `sys.getsizeof()`: a dict of 200,000 int keys
  keeps its size after all but 10 are removed with `del` or with `pop()`.
* The walking operations are timed on that sparse dict against a fresh dict
  holding the same 10 keys: iteration, `items()`, `values()`, `reversed()`,
  `copy()`, `dict(d)`,
  `other.update(d)`, `d | {}` and `d == twin` must each cost more than 50x
  (locally they cost thousands of times more). `len()` and a lookup are held
  under 5x, so the gap is the table walk and not the dict being larger in
  memory.
* `copy()` is asserted to give a compact dict (under 1/100 of the sparse
  one's size) with the same keys in the same order. Inserting fresh keys is
  asserted to rebuild the sparse dict at its current size before 200,000
  insertions, each deleted again so that the dict keeps 10 items. The rebuild
  is sized for the items present, so it shrinks the table only when the
  insertions have not refilled it.
* `d | other` is asserted to return a new dict and leave `d` unchanged,
  `d |= other` to keep the object, and `update()` to take every item of a
  counting iterator of pairs.
* Lookups count `__eq__` calls on keys with a fixed `__hash__`: with distinct
  hashes a lookup makes one comparison at 100 and at 1,000 keys; with one
  shared hash it makes exactly n.
* `popitem()` is asserted LIFO and to raise `KeyError` when empty. After the
  newest 199,000 of 200,000 keys are deleted, draining the 1,000 left with
  `popitem()` is held under 20x one `list(d)` walk; a scan per call would
  cost about 1,000x.
* Removing the oldest key with `del d[next(iter(d))]` is timed draining 2,000
  and 32,000 items: the dict must cost more than x64 (quadratic predicts
  x256) and `OrderedDict.popitem(last=False)` less than x64 (linear predicts
  x16).
* `d == other` makes no value comparison when the lengths differ, and one per
  value when they are equal (1,000 items).
* Views are asserted live. `value in d.values()` makes 1,000 comparisons to
  find the last of 1,000 values; `(k, v) in d.items()` one hash and one key
  comparison. `view & other` and `view.isdisjoint(other)` on a 10-key dict's
  `keys()` view, and on its `items()` view against an `items()` view, are
  run against 1,000 counted objects that `other` holds. They hash none of
  them when `other` is a set or a `keys()` or `items()` view, and all of them
  when it is a list or a `values()` view, so the smaller operand is iterated
  only in the first case. `|`, `-`, `^` and `&` are checked to return a new
  `set`, not timed; `d | pairs` raises `TypeError` and `d |= pairs` does not.
* `dict.fromkeys()` is asserted to share one value object, and `get()` and
  `setdefault()` to hash a counted key once where `key in d` then `d[key]`
  hashes it twice.
* Every fenced Python block on both pages runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* The collision counts cover successful lookups, with a fresh key equal to
  the last one inserted, when every key hashes to 1. Failed lookups and keys
  whose hashes differ but land on the same slot were not counted.
* How many insertions a sparse dict takes before it resizes depends on the
  free slots left in its table; only that it happens is asserted.
* The view set operations were observed only with `other` the larger
  operand; `items()` views were run only against an `items()` view.
* The O(n²) front-removal measurement inserts nothing while draining; mixed
  with insertions, periodic resizes compact the table and bound the scan.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

DOCS = pathlib.Path(__file__).parent.parent / "docs" / "builtins"
PAGES = {"dict.md": 7, "dict_func.md": 6}

PEAK = 200_000
KEPT = 10


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 3) -> float:
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


def sparse_dict(method: str = "del") -> dict[int, int]:
    """A dict that held PEAK keys and now holds KEPT."""
    d = {i: i for i in range(PEAK)}
    for i in range(KEPT, PEAK):
        if method == "del":
            del d[i]
        else:
            d.pop(i)
    return d


class TestDeletingDoesNotShrinkTheTable:
    @pytest.mark.parametrize("method", ["del", "pop"])
    def test_the_table_keeps_its_size(self, method: str) -> None:
        full = sys.getsizeof({i: i for i in range(PEAK)})
        d = sparse_dict(method)
        assert len(d) == KEPT
        assert sys.getsizeof(d) == full

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "name",
        ["iterate", "items", "values", "reversed", "copy", "dict()", "other.update", "or", "eq"],
    )
    def test_walking_costs_the_former_size(self, name: str) -> None:
        operations: dict[str, Callable[[dict[int, int]], Any]] = {
            "iterate": list,
            "items": lambda d: list(d.items()),
            "values": lambda d: list(d.values()),
            "reversed": lambda d: list(reversed(d)),
            "copy": lambda d: d.copy(),
            "dict()": dict,
            "other.update": lambda d: {}.update(d),
            "or": lambda d: d | {},
            "eq": lambda d: d == {i: i for i in range(KEPT)},
        }
        op = operations[name]
        sparse, fresh = sparse_dict(), {i: i for i in range(KEPT)}
        sparse_ns = best_ns(lambda: op(sparse))
        fresh_ns = best_ns(lambda: op(fresh))
        assert sparse_ns > fresh_ns * 50, f"{name}: {fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["len", "lookup"])
    def test_len_and_lookups_are_unaffected(self, name: str) -> None:
        operations: dict[str, Callable[[dict[int, int]], Any]] = {
            "len": len,
            "lookup": lambda d: d[KEPT - 1],
        }
        op = operations[name]
        sparse, fresh = sparse_dict(), {i: i for i in range(KEPT)}
        sparse_ns = best_ns(lambda: op(sparse), inner=10_000)
        fresh_ns = best_ns(lambda: op(fresh), inner=10_000)
        assert sparse_ns < fresh_ns * 5, f"{name}: {fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"

    def test_copy_is_compact(self) -> None:
        d = sparse_dict()
        copied = d.copy()
        assert sys.getsizeof(copied) * 100 < sys.getsizeof(d)
        assert list(copied) == list(d)

    def test_insertions_eventually_resize(self) -> None:
        d = sparse_dict()
        full = sys.getsizeof(d)
        for key in range(PEAK, 2 * PEAK):
            d[key] = key
            del d[key]
            if sys.getsizeof(d) != full:
                break
        assert len(d) == KEPT
        assert sys.getsizeof(d) * 100 < full, "an insertion must eventually rebuild the table"


class CountingPairs:
    """An iterator of (key, value) pairs that counts how many were taken."""

    def __init__(self, count: int) -> None:
        self._pairs = iter([(i, i) for i in range(count)])
        self.taken = 0

    def __iter__(self) -> Iterator[tuple[int, int]]:
        return self

    def __next__(self) -> tuple[int, int]:
        pair = next(self._pairs)
        self.taken += 1
        return pair


class TestMerging:
    def test_or_builds_a_new_dict(self) -> None:
        d = {"a": 1}
        merged = d | {"b": 2}
        assert merged == {"a": 1, "b": 2} and merged is not d
        assert d == {"a": 1}

    def test_ior_updates_in_place(self) -> None:
        d = {"a": 1}
        same = d
        d |= {"b": 2}
        assert d is same and d == {"a": 1, "b": 2}

    def test_update_takes_every_item_of_an_iterable(self) -> None:
        pairs = CountingPairs(1_000)
        d: dict[int, int] = {}
        d.update(pairs)
        assert pairs.taken == 1_000 and len(d) == 1_000

    def test_iteration_follows_insertion_order(self) -> None:
        d = {"c": 1, "a": 2, "b": 3}
        assert list(d) == ["c", "a", "b"]


# dict.md: lookups, popitem, removing the oldest key, equality and views.


class Counted:
    """A key or value whose hash is fixed and whose __hash__ and __eq__ calls are counted."""

    hashes = 0
    comparisons = 0

    def __init__(self, name: int, hash_value: int | None = None) -> None:
        self.name = name
        self.hash_value = name if hash_value is None else hash_value

    def __hash__(self) -> int:
        Counted.hashes += 1
        return self.hash_value

    def __eq__(self, other: object) -> bool:
        Counted.comparisons += 1
        return isinstance(other, Counted) and self.name == other.name

    @classmethod
    def reset(cls) -> None:
        cls.hashes = 0
        cls.comparisons = 0


class TestLookupsCompareOnlyMatchingHashes:
    """A lookup is one comparison with spread hashes and O(n) when every key collides."""

    @pytest.mark.parametrize("size", [100, 1_000])
    def test_spread_hashes_cost_one_comparison(self, size: int) -> None:
        d = {Counted(i): i for i in range(size)}
        Counted.reset()
        assert d[Counted(size - 1)] == size - 1
        assert Counted.comparisons == 1

    @pytest.mark.parametrize("size", [100, 1_000])
    def test_colliding_keys_are_compared_in_turn(self, size: int) -> None:
        d = {Counted(i, 1): i for i in range(size)}
        Counted.reset()
        assert d[Counted(size - 1, 1)] == size - 1
        assert Counted.comparisons == size


class TestPopitem:
    """popitem() is LIFO, raises KeyError when empty, and is amortized O(1).

    After the newest 199,000 of 200,000 keys are deleted, the first popitem()
    skips their slots and later calls do not, so draining the 1,000 left costs
    about one walk of the table. A per-call scan would cost 1,000 walks; the
    drain is held under 20.
    """

    def test_last_in_first_out(self) -> None:
        d = {"a": 1, "b": 2}
        d["c"] = 3
        assert d.popitem() == ("c", 3)
        assert d.popitem() == ("b", 2)

    def test_empty_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            {}.popitem()

    @pytest.mark.timing
    def test_draining_after_tail_deletions_walks_the_table_once(self) -> None:
        kept = 1_000

        def tail_deleted() -> dict[int, int]:
            d = {i: i for i in range(PEAK)}
            for i in range(kept, PEAK):
                del d[i]
            return d

        def drain(d: dict[int, int]) -> None:
            while d:
                d.popitem()

        dicts = iter([tail_deleted() for _ in range(5)])
        drain_ns = best_ns(lambda: drain(next(dicts)), repeats=5, inner=1)
        walked = tail_deleted()
        walk_ns = best_ns(lambda: list(walked))
        assert drain_ns < walk_ns * 20, f"walk {walk_ns:.0f}ns, drain {drain_ns:.0f}ns"


class TestRemovingTheOldestItem:
    """`del d[next(iter(d))]` in a loop is O(n²); OrderedDict.popitem(last=False) is O(n).

    Draining 2,000 and 32,000 items: quadratic predicts x256 and linear x16.
    The dict must cost more than x64 and the OrderedDict less than x64
    (locally about x290 and x19).
    """

    @staticmethod
    def drain_dict(size: int) -> int:
        d = dict.fromkeys(range(size))
        start = time.perf_counter_ns()
        for _ in range(size):
            del d[next(iter(d))]
        return time.perf_counter_ns() - start

    @staticmethod
    def drain_ordereddict(size: int) -> int:
        from collections import OrderedDict

        d = OrderedDict.fromkeys(range(size))
        start = time.perf_counter_ns()
        for _ in range(size):
            d.popitem(last=False)
        return time.perf_counter_ns() - start

    @pytest.mark.timing
    def test_dict_front_removal_is_quadratic(self) -> None:
        small = min(self.drain_dict(2_000) for _ in range(3))
        large = min(self.drain_dict(32_000) for _ in range(3))
        assert large > small * 64, f"x{large / small:.1f}"

    @pytest.mark.timing
    def test_ordereddict_front_removal_is_linear(self) -> None:
        small = min(self.drain_ordereddict(2_000) for _ in range(3))
        large = min(self.drain_ordereddict(32_000) for _ in range(3))
        assert large < small * 64, f"x{large / small:.1f}"

    def test_ordereddict_pops_the_oldest(self) -> None:
        from collections import OrderedDict

        od = OrderedDict.fromkeys("abc")
        assert od.popitem(last=False) == ("a", None)


class TestEquality:
    """`d == other` ignores order and compares nothing when the lengths differ."""

    def test_order_is_ignored(self) -> None:
        assert {"a": 1, "b": 2} == {"b": 2, "a": 1}

    def test_different_lengths_compare_no_values(self) -> None:
        a = {i: Counted(i) for i in range(1_000)}
        b = {i: Counted(i) for i in range(999)}
        Counted.reset()
        assert a != b
        assert Counted.comparisons == 0

    def test_equal_lengths_compare_each_value(self) -> None:
        a = {i: Counted(i) for i in range(1_000)}
        b = {i: Counted(i) for i in range(1_000)}
        Counted.reset()
        assert a == b
        assert Counted.comparisons == 1_000


class TestViews:
    """Views are live and O(1) to make; `&` and isdisjoint() iterate the smaller set.

    A set or list of 1,000 counted objects is combined with the keys view of a
    10-key dict. Every element of `other` that the operation iterates is
    looked up in the dict, so it is hashed once: 0 hashes means `other` was not
    iterated, and 1,000 means it was.
    """

    def test_views_are_live(self) -> None:
        d = {"a": 1}
        keys, values, items = d.keys(), d.values(), d.items()
        d["b"] = 2
        assert list(keys) == ["a", "b"] and list(values) == [1, 2]
        assert list(items) == [("a", 1), ("b", 2)]
        assert keys.mapping["b"] == 2

    def test_mapping_is_read_only(self) -> None:
        d = {"a": 1}
        with pytest.raises(TypeError):
            d.keys().mapping["a"] = 2  # type: ignore[index]

    def test_values_membership_scans(self) -> None:
        d = {i: Counted(i) for i in range(1_000)}
        Counted.reset()
        assert Counted(999) in d.values()
        assert Counted.comparisons == 1_000

    def test_items_membership_is_one_lookup(self) -> None:
        d = {Counted(i): i for i in range(1_000)}
        Counted.reset()
        assert (Counted(999), 999) in d.items()
        assert Counted.hashes == 1 and Counted.comparisons == 1

    @staticmethod
    def large_other(kind: str) -> Any:
        """1,000 counted objects, none equal to the keys 0-9, in the given container."""
        objects = [Counted(i + 10) for i in range(1_000)]
        containers: dict[str, Callable[[], Any]] = {
            "set": lambda: set(objects),
            "list": lambda: objects,
            "keys view": lambda: dict.fromkeys(objects).keys(),
            "items view": lambda: dict.fromkeys(objects, 0).items(),
            "values view": lambda: dict(enumerate(objects)).values(),
        }
        return containers[kind]()

    # Iterating `other` hashes each element once; a set or a keys or items view
    # is not iterated when it is the larger operand.
    ITERATED = {"set": 0, "list": 1_000, "keys view": 0, "items view": 0, "values view": 1_000}

    @pytest.mark.parametrize("kind", list(ITERATED))
    def test_intersection_iterates_other_only_when_it_must(self, kind: str) -> None:
        d = dict.fromkeys(range(10))
        view = d.items() if kind == "items view" else d.keys()
        other = self.large_other(kind)
        Counted.reset()
        assert view & other == set()
        assert Counted.hashes == self.ITERATED[kind]

    @pytest.mark.parametrize("kind", list(ITERATED))
    def test_isdisjoint_iterates_other_only_when_it_must(self, kind: str) -> None:
        d = dict.fromkeys(range(10))
        view = d.items() if kind == "items view" else d.keys()
        other = self.large_other(kind)
        Counted.reset()
        assert view.isdisjoint(other)
        assert Counted.hashes == self.ITERATED[kind]

    def test_set_operations_return_new_sets(self) -> None:
        keys = {"a": 1, "b": 2}.keys()
        results = [keys | ["c"], keys - ["a"], keys ^ {"b", "c"}, keys & {"a"}]
        assert results == [{"a", "b", "c"}, {"b"}, {"a", "c"}, {"a"}]
        assert all(type(result) is set for result in results)


class TestMergeOperands:
    """`d | other` needs a dict; `|=` and update() take any mapping or iterable of pairs."""

    def test_or_rejects_pairs(self) -> None:
        with pytest.raises(TypeError):
            _ = {"a": 1} | [("b", 2)]  # type: ignore[operator]

    def test_ior_accepts_pairs(self) -> None:
        d = {"a": 1}
        d |= [("b", 2)]
        assert d == {"a": 1, "b": 2}


class TestSingleLookupMethods:
    """fromkeys() shares one value; get() and setdefault() hash the key once."""

    def test_fromkeys_shares_the_value(self) -> None:
        d = dict.fromkeys("abc", [])
        assert d["a"] is d["b"] is d["c"]

    def test_get_hashes_once_where_in_then_index_hashes_twice(self) -> None:
        d = {Counted(1): "one"}
        key = Counted(1)
        Counted.reset()
        assert d.get(key) == "one"
        assert Counted.hashes == 1
        Counted.reset()
        assert key in d and d[key] == "one"
        assert Counted.hashes == 2

    def test_setdefault_hashes_once(self) -> None:
        d: dict[Counted, list[int]] = {}
        key = Counted(1)
        Counted.reset()
        d.setdefault(key, []).append(1)
        assert Counted.hashes == 1 and d[key] == [1]


def _blocks(page: str) -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = (DOCS / page).read_text(encoding="utf-8").splitlines()
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
    @pytest.mark.parametrize(("page", "expected"), PAGES.items())
    def test_the_page_has_the_expected_blocks(self, page: str, expected: int) -> None:
        assert len(_blocks(page)) == expected

    @pytest.mark.parametrize("page", PAGES)
    def test_every_block_runs(self, page: str, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in _blocks(page):
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{page}:{line}\n{result.stderr.strip()}")
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        target = "assert sys.getsizeof(d) == full"
        line, source = next((n, s) for n, s in _blocks("dict.md") if target in s)
        mutated = source.replace(target, "assert sys.getsizeof(d) < full", 1)

        assert mutated != source, f"the mutation matched nothing in dict.md:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0


# ---------------------------------------------------------------------------
# docs/builtins/dict_func.md
#
# The constructor rows are settled by counting over 1,000 keys: a key class
# that counts its `__hash__` calls shows one hash per pair for an iterable of
# pairs, none for a dict source, whose stored hashes are reused, and two per
# key for a non-dict mapping (one in its own `__getitem__`, one to insert). A
# mapping that counts its `keys()` and `__getitem__` calls shows one and n.
# The sparse-source cost of `dict(d)` is the "dict()" case of
# TestDeletingDoesNotShrinkTheTable above.
#
# The O(n**2) worst case is counted for an iterable of pairs: n keys that all
# hash alike take exactly n(n - 1)/2 `__eq__` calls, at 100 and 1,000 keys.
# A dict source and keyword arguments are not tested under collisions.
#
# That a list of pairs built first holds every pair as well as the dict is a
# tracemalloc peak over 50,000 string keys and large ints: `dict(list(zip()))`
# peaks over 1.5x `dict(zip())` (about 2.2x on 3.15). Key and value sizes were
# not varied.
# ---------------------------------------------------------------------------


class CountingKey:
    """A key that counts how often it is hashed."""

    hashes = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        CountingKey.hashes += 1
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CountingKey) and self.value == other.value


class CollidingKey:
    """A key whose every instance hashes to the same value; counts `__eq__` calls."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return 1

    def __eq__(self, other: object) -> bool:
        CollidingKey.comparisons += 1
        return self is other


class CountingMapping:
    """A non-dict mapping that counts calls to `keys()` and `__getitem__`."""

    def __init__(self, data: dict[Any, Any]) -> None:
        self.data = data
        self.keys_calls = 0
        self.lookups = 0

    def keys(self) -> Any:
        self.keys_calls += 1
        return self.data.keys()

    def __getitem__(self, key: Any) -> Any:
        self.lookups += 1
        return self.data[key]


class TestDictConstructorInsertsEachItemOnce:
    """`dict(iterable)`, `dict(d)` and `dict(mapping)` are O(n): each item is taken once."""

    def test_pairs_hash_each_key_once(self) -> None:
        pairs = [(CountingKey(i), i) for i in range(1_000)]
        CountingKey.hashes = 0
        d = dict(pairs)
        assert len(d) == 1_000 and CountingKey.hashes == 1_000

    def test_a_dict_source_reuses_its_stored_hashes(self) -> None:
        source = {CountingKey(i): i for i in range(1_000)}
        CountingKey.hashes = 0
        copied = dict(source)
        assert copied == source and copied is not source
        assert CountingKey.hashes == 0

    def test_a_mapping_is_read_through_keys_and_getitem(self) -> None:
        source = CountingMapping({CountingKey(i): i for i in range(1_000)})
        CountingKey.hashes = 0
        d = dict(source)
        assert d == source.data
        assert source.keys_calls == 1 and source.lookups == 1_000
        assert CountingKey.hashes == 2_000  # one for each lookup in data, one to insert

    def test_the_copy_is_shallow(self) -> None:
        key, inner = CountingKey(1), []
        source = {key: inner}
        copied = dict(source)
        assert next(iter(copied)) is key and copied[key] is inner


class TestDictConstructorArgumentOrder:
    """A repeated key keeps its first position and last value; keywords apply last."""

    def test_a_repeated_key_keeps_its_first_position(self) -> None:
        pairs = [("a", 1), ("b", 2), ("a", 3)]
        d = dict(pairs)
        assert list(d.items()) == [("a", 3), ("b", 2)]

    def test_keywords_replace_the_source_values(self) -> None:
        source = {"a": 1, "b": 2}
        d = dict(source, a=3, c=4)
        assert list(d.items()) == [("a", 3), ("b", 2), ("c", 4)]
        assert source == {"a": 1, "b": 2}

    def test_keyword_keys_must_be_strings(self) -> None:
        keywords: dict[Any, str] = {1: "one"}
        with pytest.raises(TypeError, match="keywords must be strings"):
            dict(**keywords)

    def test_non_string_keys_pass_positionally(self) -> None:
        source = {1: "one"}
        assert dict(source) == source


class TestDictConstructorWorstCase:
    """Keys that all hash alike make each insertion O(n), so construction is O(n**2)."""

    @pytest.mark.parametrize("count", [100, 1_000])
    def test_colliding_keys_compare_with_every_earlier_key(self, count: int) -> None:
        pairs = [(CollidingKey(i), i) for i in range(count)]
        CollidingKey.comparisons = 0
        d = dict(pairs)
        assert len(d) == count
        assert CollidingKey.comparisons == count * (count - 1) // 2


class TestDictConstructorFromALazyIterable:
    """A list of pairs built first holds every pair as well as the dict."""

    def test_a_list_of_pairs_raises_the_peak(self) -> None:
        keys = [f"key{i}" for i in range(50_000)]
        values = [10**20 + i for i in range(50_000)]

        def peak(build: Callable[[], Any]) -> int:
            tracemalloc.start()
            try:
                build()
                return tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()

        lazy = peak(lambda: dict(zip(keys, values, strict=True)))
        eager = peak(lambda: dict(list(zip(keys, values, strict=True))))
        assert eager > lazy * 1.5, f"{lazy} vs {eager}"
