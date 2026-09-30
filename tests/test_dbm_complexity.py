"""Tests for docs/stdlib/dbm.md.

This file settles the page's `dbm.sqlite3` rows, the claims around them and the
version note, and runs the page's self-contained examples. The `dbm.sqlite3`
backend stores each pair as a row of one SQLite table with a unique key, so
the page prices single-key operations as indexed lookups and whole-database
operations as scans. Those bounds are settled by timing two databases of
1,000 and 100,000 keys, built directly through `sqlite3` in the file
`dbm.sqlite3.open()` creates so that the build does not pay one commit per
key; space by traced allocation against a 10,000,000-byte value; and the
behavioural notes by observation.

Measurement scope:

* `dbm.sqlite3.open()` costs under 3x at 100x the keys, and a lookup, and a
  delete followed by a store of the same key, each cost under 5x there: a scan
  would cost about 100x. `len()` costs more than 10x at 100x the keys, measured
  as the fastest of five calls on one open database, so a cached count would
  have made it flat.
* Reading the 10,000,000-byte value, and `key in db` for its key, each peak
  above 9,000,000 traced bytes, where the same calls for a one-byte value peak
  under 100,000: `in` fetches the value it does not return.
* Iterating 100,000 keys without keeping them peaks under 100,000 bytes; the
  same database's `keys()` peaks above 1,000,000.
* `items()` and `values()` over 50 keys are observed through SQLite's trace
  callback on the connection `dbm.sqlite3` opens: at least one `SELECT` per key,
  where one query for the whole walk would be one.
* A store is visible through a second handle on the same file before the
  first handle is closed. The write-ahead log file exists and is non-empty
  after 100 stores, and is gone after `close()`, and a new handle reads back
  exactly the 100 pairs stored.
* The v term in the delete and store rows covers the value removed: in a
  timing test, deleting a 64,000,000-byte value, and replacing one with a
  single byte, each cost more than 5x the same operation on a one-byte value.
* `dbm.sqlite3.error` is a subclass of `OSError`; opening a missing file
  read-only raises it, and `except dbm.error` catches it.
* On 3.13+ `dbm.open(path, "c")` for a new file makes a database that
  `dbm.whichdb()` reports as `dbm.sqlite3`; before 3.13 the module does not
  exist. A `dbm.ndbm` database has `clear()` exactly from 3.13, where that
  backend is built.
* Which backends iterate: on every version a `dbm.ndbm` database is not
  iterable and has no `items()` or `values()` attribute while its `keys()`
  lists every key, and a `dbm.dumb` database iterates, and its `items()` is a
  list.
* `dbm.dumb` is O(n) to open and to delete from. Opening a database of 20,000
  keys peaks at more than 5x one of 200 (the whole key index is read into a
  dict). In a timing test, deleting one key from 20,000 costs more than 5x
  deleting one from 200, because each delete rewrites the index file.
* Every fenced Python block runs in its own subprocess and working directory
  on every version, except the SQLite block, which is about `dbm.sqlite3` and
  is skipped before 3.13. The iteration example checks the backend
  `dbm.whichdb()` reports and asserts `TypeError` from `iter()` where the
  backend is not iterable, so it holds on every version. A mutated assertion
  in it is asserted to make the block fail.

Not settled here:

* The rest of the page's generic table - the per-backend single-key bounds
  other than `dbm.dumb`'s delete - and the `dbm.gnu` table. `dbm.gnu` cannot be
  imported on this project's builds (CPython has no `_gdbm` without the GDBM
  library), so its rows - `open()`, `open_flags`, `error`, the cached `len()`,
  `firstkey()`/`nextkey()`, `keys()`, `reorganize()`, `sync()`, `clear()` and
  `close()` - are read from the official documentation and
  Modules/_gdbmmodule.c on each supported version, not measured. The O(1)
  average single-key bound, `open()` reading the bucket directory into
  memory, and the per-walk, sync and disk costs are the GDBM library's own,
  not CPython's, and can vary with the library version.
* The log n in the `dbm.sqlite3` lookup, store and delete rows is SQLite's
  B-tree depth; the timings exclude a scan but cannot tell O(log n) from O(1).
  Likewise the `items()` row's n log n is one lookup per key, observed as a
  count of statements, not timed. The O(w) close is SQLite's checkpoint of
  its write-ahead log; the test shows the log is folded into the database on
  close, not how that cost scales.
* Only short keys are used, and one large value; key length is not varied.
* `dbm.ndbm.error.winerror` and `dbm.sqlite3.error.winerror`, which the audit
  lists for classification, are `OSError` attributes inherited by both
  exception classes, not `dbm` APIs.
"""

from __future__ import annotations

import dbm
import dbm.dumb
import importlib
import importlib.util
import pathlib
import re
import sqlite3
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "dbm.md"
EXPECTED_BLOCKS = 16
HAS_SQLITE_BACKEND = sys.version_info >= (3, 13)


def importable_ndbm() -> Any:
    if sys.platform == "win32":
        pytest.skip("platform: Windows builds have no dbm.ndbm")
    try:
        return importlib.import_module("dbm.ndbm")
    except ImportError:
        pytest.skip("missing ndbm: this build has no ndbm")


SQLITE_ONLY = pytest.mark.skipif(not HAS_SQLITE_BACKEND, reason="dbm.sqlite3 is 3.13+")
BIG = 10_000_000


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
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


def sqlite_backend() -> Any:
    return importlib.import_module("dbm.sqlite3")


def build(path: pathlib.Path, keys: int) -> pathlib.Path:
    """A dbm.sqlite3 file holding `keys` short pairs plus b"big" and b"small"."""
    with sqlite_backend().open(path, "c"):
        pass
    connection = sqlite3.connect(path)
    try:
        (table,) = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchone()
        columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
        assert columns == ["key", "value"], columns
        rows = [(b"k%d" % i, b"v") for i in range(keys)]
        rows += [(b"big", b"x" * BIG), (b"small", b"x")]
        connection.executemany(f'INSERT INTO "{table}" VALUES (?, ?)', rows)
        connection.commit()
    finally:
        connection.close()
    return path


@pytest.fixture(scope="module")
def databases(tmp_path_factory: pytest.TempPathFactory) -> tuple[pathlib.Path, pathlib.Path]:
    if not HAS_SQLITE_BACKEND:
        pytest.skip("version: dbm.sqlite3 is 3.13+")
    directory = tmp_path_factory.mktemp("dbm")
    return build(directory / "small.sqlite", 1_000), build(directory / "large.sqlite", 100_000)


@SQLITE_ONLY
class TestSingleKeyOperationsAreIndexed:
    """`open()` O(1); `db[key]`, `del db[key]` O(log n + v): no scan of the keys."""

    @pytest.mark.timing
    def test_opening_does_not_follow_the_keys(
        self, databases: tuple[pathlib.Path, pathlib.Path]
    ) -> None:
        small, large = databases
        backend = sqlite_backend()

        def opening(path: pathlib.Path) -> Callable[[], None]:
            return lambda: backend.open(path, "r").close()

        ratio = best_ns(opening(large)) / best_ns(opening(small))

        assert ratio < 3, f"100x the keys cost x{ratio:.1f} to open"

    @pytest.mark.timing
    def test_a_lookup_does_not_follow_the_keys(
        self, databases: tuple[pathlib.Path, pathlib.Path]
    ) -> None:
        backend = sqlite_backend()
        small, large = (backend.open(path, "r") for path in databases)
        try:
            ratio = best_ns(lambda: large[b"k500"]) / best_ns(lambda: small[b"k500"])
        finally:
            small.close()
            large.close()

        assert ratio < 5, f"100x the keys cost x{ratio:.1f} per lookup"

    @pytest.mark.timing
    def test_a_delete_does_not_follow_the_keys(
        self, databases: tuple[pathlib.Path, pathlib.Path]
    ) -> None:
        backend = sqlite_backend()
        small, large = (backend.open(path, "w") for path in databases)

        def replacing(db: Any) -> Callable[[], None]:
            def step() -> None:
                del db[b"k500"]
                db[b"k500"] = b"v"

            return step

        try:
            ratio = best_ns(replacing(large)) / best_ns(replacing(small))
        finally:
            small.close()
            large.close()

        assert ratio < 5, f"100x the keys cost x{ratio:.1f} per delete and store"


@SQLITE_ONLY
class TestRemovingAValueCostsItsLength:
    """`del db[key]` and replacing `db[key]`: the v term includes the old value."""

    @pytest.mark.timing
    @pytest.mark.parametrize("operation", ["delete", "replace"])
    def test_a_large_old_value_costs_more_to_remove(
        self, tmp_path: pathlib.Path, operation: str
    ) -> None:
        db = sqlite_backend().open(tmp_path / "values.sqlite", "c")

        def cost(size: int) -> float:
            best: float | None = None
            for _ in range(3):
                db[b"key"] = b"x" * size
                start = time.perf_counter_ns()
                if operation == "delete":
                    del db[b"key"]
                else:
                    db[b"key"] = b"y"
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        try:
            cost(1)
            ratio = cost(64_000_000) / cost(1)
        finally:
            db.close()

        assert ratio > 5, f"a 64 MB old value cost only x{ratio:.1f} to {operation}"


@SQLITE_ONLY
class TestReadsCostTheValue:
    """`db[key]` and `key in db`: O(v) space, and `in` fetches the value."""

    @pytest.mark.serial
    @pytest.mark.parametrize("probe", ["subscript", "contains"])
    def test_the_peak_follows_the_value(
        self, databases: tuple[pathlib.Path, pathlib.Path], probe: str
    ) -> None:
        db = sqlite_backend().open(databases[0], "r")
        try:

            def read(key: bytes) -> Callable[[], Any]:
                return (lambda: db[key]) if probe == "subscript" else (lambda: key in db)

            read(b"small")()
            small = peak_bytes(read(b"small"))
            big = peak_bytes(read(b"big"))
        finally:
            db.close()

        assert small < 100_000, f"a one-byte value peaked at {small} B"
        assert big > 9_000_000, f"a {BIG}-byte value peaked at only {big} B"


@SQLITE_ONLY
class TestWholeDatabaseOperationsScan:
    """`len(db)` O(n), iteration O(n) time and O(1) space, `keys()` O(n) space."""

    @pytest.mark.timing
    def test_len_counts_the_keys_on_every_call(
        self, databases: tuple[pathlib.Path, pathlib.Path]
    ) -> None:
        backend = sqlite_backend()
        small, large = (backend.open(path, "r") for path in databases)
        try:
            ratio = best_ns(lambda: len(large)) / best_ns(lambda: len(small))
        finally:
            small.close()
            large.close()

        assert ratio > 10, f"100x the keys cost only x{ratio:.1f} per len()"

    @pytest.mark.serial
    def test_iteration_streams_and_keys_builds_a_list(
        self, databases: tuple[pathlib.Path, pathlib.Path]
    ) -> None:
        db = sqlite_backend().open(databases[1], "r")

        def walk() -> None:
            for _ in db:
                pass

        try:
            walk()
            streamed = peak_bytes(walk)
            listed = peak_bytes(db.keys)
        finally:
            db.close()

        assert streamed < 100_000, f"iterating 100,000 keys peaked at {streamed} B"
        assert listed > 1_000_000, f"keys() of 100,000 keys peaked at only {listed} B"


@SQLITE_ONLY
class TestItemsLooksUpEachKey:
    """`items()` and `values()`: one lookup per key on top of the key scan."""

    @pytest.fixture
    def statements(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        seen: list[str] = []
        real_connect = sqlite3.connect

        def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            connection = real_connect(*args, **kwargs)
            connection.set_trace_callback(seen.append)
            return connection

        monkeypatch.setattr(sqlite3, "connect", connect)
        return seen

    @pytest.mark.parametrize("view", ["items", "values"])
    def test_one_select_per_key(
        self, tmp_path: pathlib.Path, statements: list[str], view: str
    ) -> None:
        with sqlite_backend().open(tmp_path / "fifty.sqlite", "c") as db:
            for index in range(50):
                db[b"k%d" % index] = b"v"
            statements.clear()

            walked = list(getattr(db, view)())
            selects = [text for text in statements if text.lstrip().upper().startswith("SELECT")]

        assert len(walked) == 50
        assert len(selects) >= 50, f"{len(selects)} SELECT statements for 50 keys"


@SQLITE_ONLY
class TestWritesAndClose:
    """A store is committed immediately; `close()` folds the write-ahead log back."""

    def test_a_store_is_visible_to_another_handle_before_close(
        self, tmp_path: pathlib.Path
    ) -> None:
        backend = sqlite_backend()
        path = tmp_path / "shared.sqlite"
        writer = backend.open(path, "c")
        try:
            writer[b"key"] = b"value"
            with backend.open(path, "w") as reader:
                assert reader[b"key"] == b"value"
        finally:
            writer.close()

    def test_close_folds_the_write_ahead_log_into_the_file(self, tmp_path: pathlib.Path) -> None:
        backend = sqlite_backend()
        path = tmp_path / "wal.sqlite"
        log = tmp_path / "wal.sqlite-wal"
        db = backend.open(path, "c")
        for index in range(100):
            db[b"%d" % index] = b"x" * 100
        assert log.exists() and log.stat().st_size > 0, "the stores went to the log"

        db.close()

        assert not log.exists()
        with backend.open(path, "r") as reopened:
            assert dict(reopened.items()) == {b"%d" % i: b"x" * 100 for i in range(100)}


@SQLITE_ONLY
class TestErrors:
    """`dbm.sqlite3.error`: an `OSError`, caught by `except dbm.error`."""

    def test_a_missing_file_opened_read_only_raises_it(self, tmp_path: pathlib.Path) -> None:
        backend = sqlite_backend()
        assert issubclass(backend.error, OSError)

        with pytest.raises(dbm.error) as caught:
            backend.open(tmp_path / "missing.sqlite")

        assert isinstance(caught.value, backend.error)


class TestBackendsDiffer:
    """Which backends iterate, and `dbm.dumb`'s O(n) open and delete."""

    def test_ndbm_lists_keys_but_does_not_iterate(self, tmp_path: pathlib.Path) -> None:
        ndbm = importable_ndbm()
        with ndbm.open(str(tmp_path / "ndbm"), "c") as db:
            db[b"a"] = b"1"
            db[b"b"] = b"2"
            assert sorted(db.keys()) == [b"a", b"b"]
            with pytest.raises(TypeError):
                iter(db)
            assert not hasattr(db, "items") and not hasattr(db, "values")

    def test_dumb_iterates_and_its_items_is_a_list(self, tmp_path: pathlib.Path) -> None:
        with dbm.dumb.open(str(tmp_path / "dumb"), "c") as db:
            db[b"a"] = b"1"
            db[b"b"] = b"2"
            assert sorted(db) == [b"a", b"b"]
            items = db.items()
            assert isinstance(items, list)
            assert sorted(items) == [(b"a", b"1"), (b"b", b"2")]

    @staticmethod
    def _dumb(path: pathlib.Path, keys: int) -> str:
        with dbm.dumb.open(str(path), "n") as db:
            db.update({b"k%d" % i: b"v" for i in range(keys)})
        return str(path)

    @pytest.mark.serial
    def test_opening_reads_the_whole_index(self, tmp_path: pathlib.Path) -> None:
        small = self._dumb(tmp_path / "small", 200)
        large = self._dumb(tmp_path / "large", 20_000)
        dbm.dumb.open(small, "r").close()

        def opening(path: str) -> Callable[[], None]:
            return lambda: dbm.dumb.open(path, "r").close()

        small_peak, large_peak = peak_bytes(opening(small)), peak_bytes(opening(large))

        assert large_peak > 5 * small_peak, f"100x the keys: {small_peak} B, {large_peak} B"

    @pytest.mark.timing
    def test_a_delete_rewrites_the_index(self, tmp_path: pathlib.Path) -> None:
        def delete_cost(path: str) -> float:
            db = dbm.dumb.open(path, "w")
            try:
                best: float | None = None
                for _ in range(5):
                    start = time.perf_counter_ns()
                    del db[b"k1"]
                    elapsed = time.perf_counter_ns() - start
                    db[b"k1"] = b"v"
                    best = elapsed if best is None else min(best, elapsed)
                assert best is not None
                return best
            finally:
                db.close()

        small = self._dumb(tmp_path / "small", 200)
        large = self._dumb(tmp_path / "large", 20_000)
        ratio = delete_cost(large) / delete_cost(small)

        assert ratio > 5, f"100x the keys cost only x{ratio:.1f} per delete"


class TestVersionNotes:
    """Python 3.13+: `dbm.sqlite3` is added and is `dbm.open()`'s first choice
    for a new database, and `dbm.ndbm` databases gain `clear()`."""

    def test_the_sqlite_backend_exists_from_313(self) -> None:
        assert (importlib.util.find_spec("dbm.sqlite3") is not None) == HAS_SQLITE_BACKEND

    @SQLITE_ONLY
    def test_dbm_open_creates_a_sqlite_database(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "default"
        with dbm.open(str(path), "c") as db:
            db[b"key"] = b"value"

        assert dbm.whichdb(str(path)) == "dbm.sqlite3"

    def test_ndbm_gains_clear_in_313(self, tmp_path: pathlib.Path) -> None:
        ndbm = importable_ndbm()
        with ndbm.open(str(tmp_path / "ndbm"), "c") as db:
            assert hasattr(db, "clear") == HAS_SQLITE_BACKEND


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


def _skipped(source: str) -> bool:
    return "dbm.sqlite3.open" in source and not HAS_SQLITE_BACKEND


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, so the
    database files one block creates cannot reach another."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_runnable_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if _skipped(source):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == (EXPECTED_BLOCKS if HAS_SQLITE_BACKEND else EXPECTED_BLOCKS - 1)
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "== b'Bob'" in s)
        mutated = source.replace("== b'Bob'", "== b'Eve'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
