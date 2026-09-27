"""Tests for docs/stdlib/shelve.md.

The page prices a shelf as a thin layer over a `dbm` database: each operation
is a stated number of backend calls plus one pickle or unpickle, and only
iteration, `popitem()`, `clear()` and the writeback cache do more. Those
counts are settled by observation, not timing: the backend is wrapped in a
recording mapping that counts every call and the keys each `keys()` call
returned, and `shelve.Pickler` and `shelve.Unpickler` are replaced by
counting subclasses. Per-value space is settled by traced allocation over an
in-memory shelf, so disk I/O plays no part.

Measurement scope:

* `shelf[key]` makes one backend lookup and one unpickle, and two reads of a
  list are different objects; with `writeback=True` a cached key makes neither and is
  the same object. `shelf[key] = value` makes one pickle and one backend
  store, and the backend holds the pickled bytes immediately with and without
  `writeback`. `del` makes one backend delete and drops the cache entry.
  `key in shelf` makes one membership test and no unpickle; `get()` makes a
  membership test plus a read when the key is present, and only the test
  when it is absent. Reading and storing a 1,000,000-byte value peaks more
  than 20x above a 10,000-byte one.
* `len(shelf)` is one backend `len()`. On `dbm.ndbm`, `len()` after a write
  is timed at 1,000 and 32,000 keys and must grow more than 8x (it measures
  near 32x); a cached count would not grow. The timed call includes the one
  store that invalidates the count.
* `dbm.sqlite3` (3.13+), `dbm.ndbm` and `dbm.dumb`, where importable, return
  `keys()` as a list of every key. Taking the first key of a shelf calls the
  backend's `keys()` once, before anything is yielded, and `shelf.keys()`
  makes no backend call at all. Iterating `items()` and `values()` over 20
  keys makes 20 lookups and 20 unpickles. `popitem()` over 50 keys lists all
  50 to remove one, and unpickles one value.
* `Shelf.clear()` over 50 keys calls the backend's `keys()` 51 times, listing
  50 + 49 + ... + 0 keys, and unpickles all 50 values. `shelve.open()`'s
  shelf does the same before 3.13; from 3.13.0 it calls the backend's
  `clear()` once, lists no keys and unpickles nothing, so a value whose class
  no longer exists is cleared on 3.13+ and makes `clear()` raise before it.
  The two sides are guarded on `sys.version_info` and were run on 3.12.14
  and 3.14.7; the change is gh-107089, first tagged in v3.13.0. On
  `dbm.sqlite3` and `dbm.dumb` the backend's `clear()` makes one `__delitem__`
  per key; reopening with `flag='n'` makes none and leaves the shelf empty.
* A new shelf's backend is asserted to be the first importable of
  `dbm.sqlite3` (3.13+ only), `dbm.gnu`, `dbm.ndbm` and `dbm.dumb`. A
  `dbm.dumb` file is reopened as `dbm.dumb`, and reopened with `flag='n'` as
  an empty database of the default backend's type.
* With `writeback=True`, reading ten keys caches all ten, and `sync()`
  pickles and stores all ten, although none changed, then empties the cache
  and calls the backend's `sync()`. Without `writeback`, reads cache nothing
  and `sync()` pickles nothing. `close()` syncs, closes the backend once,
  makes later reads raise `ValueError`, and is harmless a second time.
* Building a `Shelf` or a `BsdDbShelf` makes no backend call. `BsdDbShelf`'s
  five cursor methods are run over a fake cursor object: each makes one
  cursor call and one unpickle and returns a decoded key. None of the
  importable `dbm` backends has `first()` or `set_location()`.
* Every fenced Python block runs in its own subprocess and temporary working
  directory, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* What one backend lookup, store, delete, `len()` or `clear()` costs, beyond
  the `dbm.ndbm` count above; that is the dbm page's subject. `dbm.gnu` is
  not built into the interpreters this project tests with, so its `keys()`
  returning a list and its `clear()` removing keys one at a time are read
  from Modules/_gdbmmodule.c; `dbm.ndbm`'s `clear()` loop is read from
  Modules/_dbmmodule.c.
* Pickling and unpickling being linear in the pickle is the page's cost
  model, not measured here; values with custom `__reduce__` or `__setstate__`
  cost what those methods cost.
* Key encoding is treated as O(1); key length is not varied.
* Durability after a crash, and concurrent access from several processes,
  are backend properties the page does not claim.
"""

from __future__ import annotations

import dbm
import dbm.dumb
import importlib
import os
import pathlib
import pickle
import re
import shelve
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator, MutableMapping
from types import ModuleType
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "shelve.md"
EXPECTED_BLOCKS = 6


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


def importable(name: str) -> ModuleType | None:
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def dbm_backends() -> list[ModuleType]:
    """The dbm backends this interpreter can import."""
    names = ["dbm.sqlite3", "dbm.gnu", "dbm.ndbm", "dbm.dumb"]
    return [module for module in map(importable, names) if module is not None]


class RecordingMapping(MutableMapping[bytes, bytes]):
    """A backend wrapper that records every call made to it."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls: list[str] = []
        self.listed: list[int] = []

    def __getitem__(self, key: bytes) -> bytes:
        self.calls.append("getitem")
        return self.inner[key]

    def __setitem__(self, key: bytes, value: bytes) -> None:
        self.calls.append("setitem")
        self.inner[key] = value

    def __delitem__(self, key: bytes) -> None:
        self.calls.append("delitem")
        del self.inner[key]

    def __contains__(self, key: object) -> bool:
        self.calls.append("contains")
        return key in self.inner

    def __iter__(self) -> Iterator[bytes]:
        self.calls.append("iter")
        return iter(self.inner)

    def __len__(self) -> int:
        self.calls.append("len")
        return len(self.inner)

    def keys(self) -> list[bytes]:  # type: ignore[override]
        """Like every dbm backend, a list of every key."""
        self.calls.append("keys")
        keys = list(self.inner.keys())
        self.listed.append(len(keys))
        return keys

    def clear(self) -> None:
        self.calls.append("clear")
        self.inner.clear()

    def sync(self) -> None:
        self.calls.append("sync")

    def close(self) -> None:
        self.calls.append("close")

    def count(self, name: str) -> int:
        return self.calls.count(name)


class Counters:
    """Counts of the pickles and unpickles shelve makes."""

    def __init__(self) -> None:
        self.pickles = 0
        self.unpickles = 0


@pytest.fixture
def counters(monkeypatch: pytest.MonkeyPatch) -> Counters:
    counts = Counters()

    class CountingPickler(pickle.Pickler):
        def dump(self, obj: Any) -> None:
            counts.pickles += 1
            super().dump(obj)

    class CountingUnpickler(pickle.Unpickler):
        def load(self) -> Any:
            counts.unpickles += 1
            return super().load()

    monkeypatch.setattr(shelve, "Pickler", CountingPickler)
    monkeypatch.setattr(shelve, "Unpickler", CountingUnpickler)
    return counts


def recorded_shelf(items: int = 0, *, writeback: bool = False) -> tuple[Any, RecordingMapping]:
    """An in-memory shelf of `items` keys whose backend records its calls."""
    backend = RecordingMapping({})
    shelf: Any = shelve.Shelf(backend, writeback=writeback)
    for index in range(items):
        shelf[f"k{index}"] = index
    backend.calls.clear()
    return shelf, backend


class TestOpeningAShelf:
    """`shelve.open()`, `DbfilenameShelf`, `Shelf` and `BsdDbShelf` are O(1)
    wrappers; the backend `dbm.open()` picks is what the file is."""

    def test_open_returns_a_dbfilename_shelf(self, tmp_path: pathlib.Path) -> None:
        with shelve.open(str(tmp_path / "data")) as shelf:
            assert isinstance(shelf, shelve.DbfilenameShelf)

    def test_a_new_shelf_gets_the_first_available_backend(self, tmp_path: pathlib.Path) -> None:
        names = ["dbm.gnu", "dbm.ndbm", "dbm.dumb"]
        if sys.version_info >= (3, 13):
            names.insert(0, "dbm.sqlite3")
        expected = next(name for name in names if importable(name) is not None)
        path = str(tmp_path / "data")

        with shelve.open(path) as shelf:
            shelf["a"] = 1

        assert dbm.whichdb(path) == expected

    def test_an_existing_file_keeps_its_backend(self, tmp_path: pathlib.Path) -> None:
        path = str(tmp_path / "data")
        database: Any = dbm.dumb.open(path, "c")
        with shelve.Shelf(database) as shelf:
            shelf["answer"] = 42

        reopened: Any = shelve.open(path)
        with reopened as shelf:
            assert isinstance(shelf.dict, dbm.dumb._Database)  # noqa: SLF001
            assert shelf["answer"] == 42

    def test_flag_n_replaces_an_existing_backend_with_the_default(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = str(tmp_path / "data")
        database: Any = dbm.dumb.open(path, "c")
        with shelve.Shelf(database) as shelf:
            shelf["answer"] = 42
        default: Any = shelve.open(str(tmp_path / "fresh"))
        default_type = type(default.dict)
        default.close()

        replaced: Any = shelve.open(path, flag="n")
        with replaced as shelf:
            assert type(shelf.dict) is default_type
            assert len(shelf) == 0

    def test_flag_n_starts_empty(self, tmp_path: pathlib.Path) -> None:
        path = str(tmp_path / "data")
        with shelve.open(path) as shelf:
            shelf.update({"a": 1, "b": 2})

        with shelve.open(path, flag="n") as shelf:
            assert len(shelf) == 0

    def test_wrapping_makes_no_backend_call(self) -> None:
        backend = RecordingMapping({b"k": pickle.dumps(1)})

        shelves = [shelve.Shelf(backend), shelve.BsdDbShelf(backend)]

        assert backend.calls == []
        assert len(shelves) == 2  # kept alive: collecting a shelf closes its backend

    def test_no_dbm_backend_has_cursor_methods(self, tmp_path: pathlib.Path) -> None:
        for module in dbm_backends():
            database = module.open(str(tmp_path / module.__name__), "n")
            try:
                assert not hasattr(database, "first"), module.__name__
                assert not hasattr(database, "set_location"), module.__name__
            finally:
                database.close()


class TestReadsUnpickleACopy:
    """`shelf[key]` | O(v) | O(v): one lookup and a fresh unpickled copy,
    except a writeback cache hit, which is the same object for O(1)."""

    def test_each_read_is_one_lookup_and_one_unpickle(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(1)

        first = shelf["k0"]
        second = shelf["k0"]

        assert first == second == 0
        assert backend.count("getitem") == 2
        assert counters.unpickles == 2

    def test_each_read_is_a_new_copy(self) -> None:
        shelf, _ = recorded_shelf()
        shelf["list"] = [1, 2]

        assert shelf["list"] is not shelf["list"]
        shelf["list"].append(3)
        assert shelf["list"] == [1, 2]

    def test_a_writeback_cache_hit_touches_nothing(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(1, writeback=True)
        first = shelf["k0"]
        backend.calls.clear()
        counters.unpickles = 0

        assert shelf["k0"] is first
        assert backend.calls == []
        assert counters.unpickles == 0

    @pytest.mark.parametrize("operation", ["read", "store"])
    def test_the_peak_follows_the_value(self, operation: str) -> None:
        peaks = []
        for size in (10_000, 1_000_000):
            shelf, _ = recorded_shelf()
            value = b"x" * size
            shelf["k"] = value
            shelf["k"]  # warm
            if operation == "read":
                peaks.append(peak_bytes(lambda s=shelf: s["k"]))  # type: ignore[misc]
            else:
                peaks.append(peak_bytes(lambda s=shelf, v=value: s.__setitem__("k", v)))  # type: ignore[misc]

        assert peaks[1] > peaks[0] * 20, f"100x the value: {peaks}"


class TestStoresAreWrittenThrough:
    """`shelf[key] = value` pickles and stores at once; `del`, `in` and `get`
    make the backend calls their rows name."""

    @pytest.mark.parametrize("writeback", [False, True])
    def test_a_store_reaches_the_backend_at_once(self, writeback: bool, counters: Counters) -> None:
        shelf, backend = recorded_shelf(writeback=writeback)

        shelf["k"] = [1, 2]

        assert counters.pickles == 1
        assert backend.calls == ["setitem"]
        assert pickle.loads(backend.inner[b"k"]) == [1, 2]

    def test_a_delete_is_one_backend_delete_and_drops_the_cache(self) -> None:
        shelf, backend = recorded_shelf(1, writeback=True)
        shelf["k0"]
        backend.calls.clear()

        del shelf["k0"]

        assert backend.calls == ["delitem"]
        assert shelf.cache == {}

    def test_membership_unpickles_nothing(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(1)

        assert "k0" in shelf
        assert "missing" not in shelf

        assert backend.calls == ["contains", "contains"]
        assert counters.unpickles == 0

    def test_get_reads_only_when_the_key_is_present(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(1)

        assert shelf.get("missing", "none") == "none"
        assert backend.calls == ["contains"]
        assert counters.unpickles == 0

        assert shelf.get("k0") == 0
        assert backend.calls == ["contains", "contains", "getitem"]
        assert counters.unpickles == 1

    def test_pop_and_setdefault(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(1)

        assert shelf.pop("k0") == 0
        assert backend.calls == ["getitem", "delitem"]
        backend.calls.clear()

        assert shelf.setdefault("new", 5) == 5
        assert backend.calls == ["getitem", "setitem"]
        backend.calls.clear()

        assert shelf.setdefault("new", 6) == 5
        assert backend.calls == ["getitem"]
        assert counters.unpickles == 2

    def test_update_is_one_store_per_item(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf()

        shelf.update({f"k{index}": index for index in range(10)})

        assert backend.calls == ["setitem"] * 10
        assert counters.pickles == 10


class TestLenIsTheBackends:
    """`len(shelf)` | O(1) | one backend `len()`; `dbm.ndbm` counts its keys
    again after every write."""

    def test_len_is_one_backend_call(self) -> None:
        shelf, backend = recorded_shelf(5)

        assert len(shelf) == 5
        assert backend.calls == ["len"]

    @pytest.mark.timing
    def test_ndbm_counts_its_keys_after_a_write(self, tmp_path: pathlib.Path) -> None:
        ndbm = importable("dbm.ndbm")
        if ndbm is None:
            pytest.skip("dbm.ndbm is not built into this interpreter")
        durations = []
        for size in (1_000, 32_000):
            database = ndbm.open(str(tmp_path / f"n{size}"), "n")
            try:
                for index in range(size):
                    database[b"k%d" % index] = b"v"

                def length_after_a_write(db: Any = database) -> int:
                    db[b"k0"] = b"w"
                    return len(db)

                durations.append(best_ns(length_after_a_write))
            finally:
                database.close()

        ratio = durations[1] / durations[0]
        assert ratio > 8, f"32x the keys: {durations} ns, x{ratio:.1f}; a cached count gives x1"


class TestIterationBuildsTheKeyList:
    """Iterating | O(n) | O(n): the backend's whole key list comes first;
    `items()` and `values()` add a lookup and an unpickle per key, and
    `popitem()` pays for the list to find one key."""

    def test_every_backend_returns_its_keys_as_a_list(self, tmp_path: pathlib.Path) -> None:
        backends = dbm_backends()
        assert backends, "no dbm backend could be imported"
        for module in backends:
            database = module.open(str(tmp_path / module.__name__), "n")
            try:
                for index in range(5):
                    database[b"k%d" % index] = b"v"
                keys = database.keys()
                assert type(keys) is list, module.__name__
                assert len(keys) == 5, module.__name__
            finally:
                database.close()

    def test_the_first_key_costs_the_whole_list(self, tmp_path: pathlib.Path) -> None:
        backend = RecordingMapping(dbm.dumb.open(str(tmp_path / "data"), "n"))
        with shelve.Shelf(backend) as shelf:
            for index in range(100):
                shelf[f"k{index}"] = index
            backend.calls.clear()

            first = next(iter(shelf))

            assert first.startswith("k")
            assert backend.calls == ["keys"]
            assert backend.listed == [100]

    def test_keys_is_a_view_that_calls_nothing(self) -> None:
        shelf, backend = recorded_shelf(5)

        view = shelf.keys()

        assert type(view).__name__ == "KeysView"
        assert backend.calls == []
        assert sorted(view) == [f"k{index}" for index in range(5)]

    @pytest.mark.parametrize("view", ["items", "values"])
    def test_items_and_values_read_every_key(self, view: str, counters: Counters) -> None:
        shelf, backend = recorded_shelf(20)

        values = list(getattr(shelf, view)())

        assert len(values) == 20
        assert backend.count("keys") == 1
        assert backend.count("getitem") == 20
        assert counters.unpickles == 20

    def test_popitem_lists_every_key_to_remove_one(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(50)

        key, value = shelf.popitem()

        assert value == int(key[1:])
        assert backend.listed == [50]
        assert backend.count("delitem") == 1
        assert counters.unpickles == 1


class Vanishing:
    """A class removed from its module after pickling, so it cannot be loaded."""


class TestClear:
    """`Shelf.clear()` | O(n² + V): a `popitem()` per key. `DbfilenameShelf
    .clear()` is one backend `clear()` from 3.13 and `Shelf.clear()` before."""

    KEYS = 50

    def test_shelf_clear_relists_the_keys_per_removal(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(self.KEYS)

        shelf.clear()

        assert len(backend.inner) == 0
        assert backend.listed == list(range(self.KEYS, -1, -1))
        assert counters.unpickles == self.KEYS

    def _recorded_dbfilename_shelf(self, tmp_path: pathlib.Path) -> tuple[Any, RecordingMapping]:
        shelf: Any = shelve.open(str(tmp_path / "data"))
        for index in range(self.KEYS):
            shelf[f"k{index}"] = index
        backend = RecordingMapping(shelf.dict)
        shelf.dict = backend
        return shelf, backend

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the backend's clear() is 3.13+")
    def test_dbfilename_clear_is_one_backend_clear(
        self, tmp_path: pathlib.Path, counters: Counters
    ) -> None:
        shelf, backend = self._recorded_dbfilename_shelf(tmp_path)
        try:
            shelf.clear()

            assert backend.calls == ["clear"]
            assert backend.listed == []
            assert counters.unpickles == 0
            assert len(shelf) == 0
        finally:
            shelf.close()

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="3.13+ calls the backend's clear()")
    def test_dbfilename_clear_is_shelf_clear_before_313(
        self, tmp_path: pathlib.Path, counters: Counters
    ) -> None:
        shelf, backend = self._recorded_dbfilename_shelf(tmp_path)
        try:
            shelf.clear()

            assert backend.count("clear") == 0
            assert backend.listed == list(range(self.KEYS, -1, -1))
            assert counters.unpickles == self.KEYS
        finally:
            shelf.close()

    def test_an_unloadable_value_blocks_clear_only_before_313(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with shelve.open(str(tmp_path / "data")) as shelf:
            shelf["gone"] = Vanishing()
            monkeypatch.delattr(sys.modules[__name__], "Vanishing")

            if sys.version_info >= (3, 13):
                shelf.clear()
                assert len(shelf) == 0
            else:
                with pytest.raises(AttributeError, match="Vanishing"):
                    shelf.clear()

    @pytest.mark.parametrize("name", ["dbm.sqlite3", "dbm.dumb"])
    def test_backend_clear_deletes_key_by_key_and_flag_n_does_not(
        self, name: str, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = importable(name)
        if module is None:
            pytest.skip(f"{name} is not available")
        database_class: Any = module._Database  # noqa: SLF001
        deletes: list[bytes] = []
        original = database_class.__delitem__

        def counting_delitem(self: Any, key: bytes) -> None:
            deletes.append(key)
            original(self, key)

        monkeypatch.setattr(database_class, "__delitem__", counting_delitem)
        path = str(tmp_path / "data")
        database = module.open(path, "n")
        for index in range(self.KEYS):
            database[b"k%d" % index] = b"v"

        database.clear()
        assert len(deletes) == self.KEYS
        for index in range(self.KEYS):
            database[b"k%d" % index] = b"v"
        database.close()
        deletes.clear()

        database = module.open(path, "n")
        try:
            assert len(database) == 0
            assert deletes == []
        finally:
            database.close()


class TestWriteback:
    """`Shelf.cache` | O(w) space; `sync()` and `close()` | O(w): every key
    read or stored is cached and re-pickled, changed or not."""

    def test_reads_fill_the_cache_only_with_writeback(self) -> None:
        plain, _ = recorded_shelf(10)
        cached, _ = recorded_shelf(10, writeback=True)
        cached.cache.clear()  # the stores cached their values; start from reads alone

        for index in range(10):
            plain[f"k{index}"]
            cached[f"k{index}"]

        assert plain.cache == {}
        assert sorted(cached.cache) == sorted(f"k{index}" for index in range(10))

    def test_deleting_or_clearing_drops_cached_entries(self) -> None:
        shelf, _ = recorded_shelf(3, writeback=True)

        del shelf["k0"]
        assert sorted(shelf.cache) == ["k1", "k2"]
        shelf.clear()
        assert shelf.cache == {}

    def test_sync_repickles_every_cached_entry(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(10, writeback=True)
        shelf.cache.clear()
        for index in range(10):
            shelf[f"k{index}"]
        backend.calls.clear()
        counters.pickles = 0

        shelf.sync()

        assert counters.pickles == 10
        assert backend.calls == ["setitem"] * 10 + ["sync"]
        assert shelf.cache == {}

    def test_sync_without_writeback_pickles_nothing(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(10)
        for index in range(10):
            shelf[f"k{index}"]
        backend.calls.clear()
        counters.pickles = 0

        shelf.sync()

        assert counters.pickles == 0
        assert backend.calls == ["sync"]

    def test_close_syncs_closes_and_then_refuses(self, counters: Counters) -> None:
        shelf, backend = recorded_shelf(3, writeback=True)
        counters.pickles = 0

        shelf.close()

        assert counters.pickles == 3
        assert backend.count("sync") == 1
        assert backend.count("close") == 1
        with pytest.raises(ValueError, match="closed shelf"):
            shelf["k0"]
        shelf.close()
        assert backend.count("close") == 1

    def test_leaving_a_with_block_closes(self) -> None:
        shelf, backend = recorded_shelf(1)

        with shelf:
            pass

        assert backend.count("close") == 1


class FakeCursorDatabase(dict[bytes, bytes]):
    """The cursor interface `BsdDbShelf` expects, over sorted keys."""

    def __init__(self, items: dict[bytes, bytes]) -> None:
        super().__init__(items)
        self.order = sorted(items)
        self.position = 0
        self.cursor_calls = 0

    def _pair(self) -> tuple[bytes, bytes]:
        self.cursor_calls += 1
        key = self.order[self.position]
        return key, self[key]

    def first(self) -> tuple[bytes, bytes]:
        self.position = 0
        return self._pair()

    def last(self) -> tuple[bytes, bytes]:
        self.position = len(self.order) - 1
        return self._pair()

    def __next__(self) -> tuple[bytes, bytes]:
        self.position += 1
        return self._pair()

    def previous(self) -> tuple[bytes, bytes]:
        self.position -= 1
        return self._pair()

    def set_location(self, key: bytes) -> tuple[bytes, bytes]:
        self.position = self.order.index(key)
        return self._pair()


class TestBsdDbShelf:
    """`BsdDbShelf` cursor methods | O(v): one cursor call and one unpickle."""

    def test_each_cursor_method_is_one_step_and_one_unpickle(self, counters: Counters) -> None:
        database = FakeCursorDatabase({b"a": pickle.dumps(1), b"b": pickle.dumps(2)})
        shelf: Any = shelve.BsdDbShelf(database)

        assert shelf.first() == ("a", 1)
        assert shelf.next() == ("b", 2)
        assert shelf.previous() == ("a", 1)
        assert shelf.last() == ("b", 2)
        assert shelf.set_location(b"a") == ("a", 1)

        assert database.cursor_calls == 5
        assert counters.unpickles == 5


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
    """Each block runs in its own subprocess and working directory, creates
    its shelves in a temporary directory, and asserts its own result."""

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
            assert os.listdir(workdir) == ["block.py"], f"{PAGE.name}:{line} left files behind"

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        target = "shelf['scores'] == [95, 87, 92, 100]"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "shelf['scores'] == [95, 87, 92]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
