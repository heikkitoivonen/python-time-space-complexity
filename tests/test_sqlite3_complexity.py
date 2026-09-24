"""Tests for docs/stdlib/sqlite3.md.

The page separates the module's own work - compiling, binding, converting and
building rows - from what SQLite's planner does with a query. The module's
rows are settled by observation wherever SQLite exposes a hook for it: an
authorizer runs only while a statement compiles, so counting its calls shows
the statement cache; a progress handler counts virtual-machine steps, so it
shows how much of a query a fetch runs; a trace callback shows which
statements a Python call issued. Query rows are read off `EXPLAIN QUERY PLAN`.
Allocation claims use traced peaks, and only the Blob, `close()`, binding and
index rows need a stopwatch.

Measurement scope:

* Statement cache: with an authorizer counting compiles, one SQL text run ten
  times compiles once and ten distinct texts compile ten times. Running a set
  of distinct `SELECT i` texts and then running them all again recompiles
  nothing at the default size - 128 texts on 3.11+, 100 on 3.10 - and
  recompiles something at one more. 3.11+ evicts the least recently used,
  3.10 the least used; only the capacity is on the page. `executescript()`
  compiles its statement again on every run. After `set_authorizer()`, a
  statement compiled before it compiles once more and then hits the cache;
  `set_authorizer()` with 10,000 statements held costs more than 50x
  the call with 10 (about 1,300x on the dev box).
* `connect()` succeeds on a 14,000-byte file that is not a database and the
  first statement raises `DatabaseError`, so the file is checked only then.
* `close()` over 100 against 10,000 cached statements (`cached_statements`
  raised to fit) costs more than 20x (about 110x measured), with the statements
  prepared outside the timing. Uncommitted rows in a file database are gone
  after `close()`.
* Commit: a trace callback records no statement for `commit()` outside a
  transaction and `COMMIT` inside one. Setting `isolation_level = None`, and
  `autocommit = True` on 3.12+, closes an open transaction with a traced
  `COMMIT`. `executescript()` issues `COMMIT` for an open transaction before
  its own statement. The durability cost of a commit is measured in
  tests/test_stdlib_claims.py on a file database.
* Fetching: a fixed `SELECT x FROM t WHERE x = 0` fetch runs more than 50x the
  VM steps at 10,000 rows as at 100, for every fetch form and for a fixed-SQL
  script. One-column TEXT and BLOB rows of 1,000 and 1,000,000 bytes retain
  more than 100x the traced memory. `fetchall()` over 20,000 100-character
  rows peaks more than 100x iteration's peak, and `fetchmany(100)` under a
  hundredth of `fetchall()`. On 3.10, `execute()` converts the first row and
  each fetch the row after; on 3.11+ each fetch converts its own row, observed
  by a counting `text_factory`.
* Binding: 1 KB against 1 MB of TEXT or BLOB with one parameter, through
  `execute()` and `executemany()`, with SQL that returns or stores only
  `typeof(?)`: more than 5x the time. A `bytearray` changed after binding does
  not change the fetched value, so SQLite holds a copy.
* `executemany()` takes one parameter set, runs it, then takes the next, seen
  by a generator and a registered SQL function logging into one list. A
  SELECT raises `ProgrammingError`.
* `description` is the same object on every access and after `fetchall()`, a
  fresh equal object after re-executing a cached statement, and seven-tuples
  of which six fields are `None`, over 1 and 100 columns of 10- and
  1,000-character names.
* `Row`: a `str` subclass counting `__eq__` makes 1 comparison for the first
  of 60 columns and 60 for the last, including for an ASCII case mismatch; a
  non-ASCII case mismatch raises `IndexError`. `keys()` is a new list each
  call. `Row(cursor, data)` over a 100,000-item tuple peaks under 1 KB.
  Equal rows compare and hash equal.
* Converters: one registered as `wibble` after `execute()` does not apply to
  the rows that execution returns and does apply, through a `WiBbLe` column,
  to the next `execute()`, so the lookup is per execution and ignores case.
  NULL, empty TEXT and empty BLOB values come back as `None` and never reach
  the converter. `PARSE_COLNAMES` converts through a `"v [shout]"` alias.
* Callbacks: a function registered with `create_function()` runs once per row
  over 1,000 rows; an aggregate's `step()` runs once per row and `finalize()`
  once per group over 1,000 rows in 10 groups; a collation sorting 1,000 rows
  is called between 999 and 2 * 1,000 * log2(1,000) times. The authorizer is
  not called again for a cached statement. `interrupt()` from a progress
  handler raises `OperationalError`.
* `backup(pages=10)` on a database of P pages calls `progress` ceil(P / 10)
  times, the last with 0 remaining. `iterdump()` over 20,000 and 200,000 rows
  peaks at under 100 KB both times, while `list()` of it peaks more than 100x
  higher at 200,000; statements are counted for one table. `serialize()`
  grows past 1 MB for 1 MB of rows and `deserialize()` round-trips it.
* Blob (3.11+): on a 20,000,000-byte blob, a fresh handle's first 100-byte
  read at the end costs more than 20x one at the start (about 220x measured),
  while repeated reads through one handle cost within 3x at both ends, and
  `blobopen()` on it costs within 3x of `blobopen()` on a 100-byte blob. A
  stepped slice returning 10 bytes of a 4,000,000-byte span peaks over
  4,000,000 bytes. A write past the end raises `ValueError`.
* Query rows: `EXPLAIN QUERY PLAN` shows SEARCH for a rowid or indexed lookup,
  SCAN without an index, a temporary B-tree for ORDER BY without one,
  `COVERING INDEX` when the index holds every column read and plain
  `USING INDEX` when it does not; an index on the column is timed more than
  10x faster than the scan over 5,000 rows. `LIMIT 1` on a scan of 5,000 rows
  runs under a fiftieth of the VM steps of the unlimited query. UPDATE over
  20,000 rows: five indexes on other columns leave it within 3x of an
  unindexed table, and changing an indexed column costs more than 3x. INSERT
  cost with five indexes is measured in tests/test_complexity_caveats.py.
* Version-gated names are checked with `hasattr` on this interpreter against
  the version their row names, and `sqlite3.version` is asserted to warn on
  3.12 and 3.13; the constant families are counted by prefix
  against the 37, 103, 12 and 16 on the page.
* Every fenced block runs in its own subprocess; the Blob and `serialize()`
  blocks are skipped where the interpreter lacks `blobopen()` or
  `serialize()`, and a mutated assertion in one block is asserted to fail.

Not settled here:

* Query costs beyond the plan: B-tree depth as O(log n), a sort as
  O(r log r), one table lookup per match through a non-covering index, and
  O((1 + i) log n) per changed row are SQLite's documented structure, not
  measured growth. That changing the rowid updates every index is SQLite's
  index layout, not measured. Partial indexes are not considered.
* `iterdump()`'s schema term e is read from Lib/sqlite3/dump.py, which
  fetches the CREATE statements into lists; the tests use one table and vary
  only its rows. Commit cost in dirty pages, WAL, busy
  timeouts and concurrent connections are not measured.
* Compile cost as a function of SQL text or join count, and SQLite's own
  workspace, are outside the tests; so are `sqlite3.complete_statement()`'s
  O(q), which is read from SQLite's tokenizer, and `blobopen()`'s O(log n),
  which is the rowid lookup.
* `enable_load_extension()` and `load_extension()` depend on a build that
  allows extensions and on the extension loaded; nothing is loaded here.
* `SQLITE_DBCONFIG_*` presence depends on the SQLite headers of the build, so
  only a subset of the 16 known names is required; a runtime SQLite version
  need not match those headers.
* The `sqlite3.dump` module the audit discovers is the private helper behind
  `iterdump()`, not a public API.
* The first-reach walk in a Blob is SQLite's overflow-page chain; only the
  20 MB zero blob is measured, reached by a read, not by a write, and not at
  other page sizes. SQLite's own page list for the walk is native memory that
  tracemalloc cannot see, as is all of SQLite's workspace.
* `row == other` and `hash(row)` are O(c + v) from Modules/_sqlite/row.c,
  which compares and hashes the description and value tuples; only equality
  of two small rows is asserted.
"""

from __future__ import annotations

import math
import pathlib
import re
import sqlite3
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sqlite3.md"
EXPECTED_BLOCKS = 13

# The 3.10 constant set: authorizer action codes, the three authorizer return
# values, and SQLITE_DONE.
AUTHORIZER_CODES = {
    "SQLITE_ALTER_TABLE",
    "SQLITE_ANALYZE",
    "SQLITE_ATTACH",
    "SQLITE_CREATE_INDEX",
    "SQLITE_CREATE_TABLE",
    "SQLITE_CREATE_TEMP_INDEX",
    "SQLITE_CREATE_TEMP_TABLE",
    "SQLITE_CREATE_TEMP_TRIGGER",
    "SQLITE_CREATE_TEMP_VIEW",
    "SQLITE_CREATE_TRIGGER",
    "SQLITE_CREATE_VIEW",
    "SQLITE_CREATE_VTABLE",
    "SQLITE_DELETE",
    "SQLITE_DENY",
    "SQLITE_DETACH",
    "SQLITE_DONE",
    "SQLITE_DROP_INDEX",
    "SQLITE_DROP_TABLE",
    "SQLITE_DROP_TEMP_INDEX",
    "SQLITE_DROP_TEMP_TABLE",
    "SQLITE_DROP_TEMP_TRIGGER",
    "SQLITE_DROP_TEMP_VIEW",
    "SQLITE_DROP_TRIGGER",
    "SQLITE_DROP_VIEW",
    "SQLITE_DROP_VTABLE",
    "SQLITE_FUNCTION",
    "SQLITE_IGNORE",
    "SQLITE_INSERT",
    "SQLITE_OK",
    "SQLITE_PRAGMA",
    "SQLITE_READ",
    "SQLITE_RECURSIVE",
    "SQLITE_REINDEX",
    "SQLITE_SAVEPOINT",
    "SQLITE_SELECT",
    "SQLITE_TRANSACTION",
    "SQLITE_UPDATE",
}

DBCONFIG_NAMES = {
    "SQLITE_DBCONFIG_DEFENSIVE",
    "SQLITE_DBCONFIG_DQS_DDL",
    "SQLITE_DBCONFIG_DQS_DML",
    "SQLITE_DBCONFIG_ENABLE_FKEY",
    "SQLITE_DBCONFIG_ENABLE_FTS3_TOKENIZER",
    "SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION",
    "SQLITE_DBCONFIG_ENABLE_QPSG",
    "SQLITE_DBCONFIG_ENABLE_TRIGGER",
    "SQLITE_DBCONFIG_ENABLE_VIEW",
    "SQLITE_DBCONFIG_LEGACY_ALTER_TABLE",
    "SQLITE_DBCONFIG_LEGACY_FILE_FORMAT",
    "SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE",
    "SQLITE_DBCONFIG_RESET_DATABASE",
    "SQLITE_DBCONFIG_TRIGGER_EQP",
    "SQLITE_DBCONFIG_TRUSTED_SCHEMA",
    "SQLITE_DBCONFIG_WRITABLE_SCHEMA",
}

# Documented names that not every supported version has, as
# (owner, name, first version with it, first version without it, row marker).
VERSION_GATED: list[tuple[Any, str, tuple[int, int] | None, tuple[int, int] | None, str]] = [
    (sqlite3, "Blob", (3, 11), None, "Python 3.11+"),
    (sqlite3, "LEGACY_TRANSACTION_CONTROL", (3, 12), None, "Python 3.12+"),
    (sqlite3, "enable_shared_cache", None, (3, 12), "Removed in Python 3.12"),
    (sqlite3, "version", None, (3, 14), "removed in Python 3.14"),
    (sqlite3.Connection, "create_window_function", (3, 11), None, "Python 3.11+"),
    (sqlite3.Connection, "blobopen", (3, 11), None, "Python 3.11+"),
    (sqlite3.Connection, "setlimit", (3, 11), None, "Python 3.11+"),
    (sqlite3.Connection, "getconfig", (3, 12), None, "Python 3.12+"),
    (sqlite3.Connection, "autocommit", (3, 12), None, "Python 3.12+"),
]

needs_blob = pytest.mark.skipif(
    not hasattr(sqlite3.Connection, "blobopen"), reason="Connection.blobopen is Python 3.11+"
)


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
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


def count_compiles(connection: sqlite3.Connection) -> list[int]:
    """Install an authorizer and return the list of SELECT actions it sees.

    SQLite consults the authorizer only while compiling. The callers compile
    simple SELECTs, each of which produces exactly one SELECT action.
    """
    selects: list[int] = []

    def authorizer(action: int, *details: Any) -> int:
        if action == sqlite3.SQLITE_SELECT:
            selects.append(action)
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorizer)
    return selects


def trace(connection: sqlite3.Connection) -> list[str]:
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    return statements


@pytest.fixture
def rows() -> Iterator[sqlite3.Connection]:
    """A five-thousand-row table in memory, closed afterwards."""
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    connection.executemany(
        "INSERT INTO t VALUES (?, ?, ?)", [(i, f"n{i}", i % 100) for i in range(5_000)]
    )
    connection.commit()
    yield connection
    connection.close()


class TestVersionGatedNames:
    """Each gated row carries its version, and this interpreter agrees."""

    def test_each_gated_row_names_its_version(self) -> None:
        table_rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]
        for owner, name, _, _, marker in VERSION_GATED:
            prefix = "sqlite3" if owner is sqlite3 else "Connection"
            subject = re.compile(rf"`{prefix}\.{name}[`(]")
            owning = [row for row in table_rows if subject.search(row.split("|")[1])]
            assert len(owning) == 1, f"expected one row naming {prefix}.{name}: {owning}"
            assert marker in owning[0], f"the {name} row should say {marker}"

    @pytest.mark.skipif(
        not (3, 12) <= sys.version_info < (3, 14), reason="deprecated on 3.12 and 3.13 only"
    )
    def test_version_warns_before_its_removal(self) -> None:
        with pytest.warns(DeprecationWarning):
            sqlite3.version  # noqa: B018

    def test_the_gated_names_match_this_interpreter(self) -> None:
        """`hasattr`, not `dir()`: `sqlite3.version` is absent from `dir()`
        from 3.12 while a module `__getattr__` still answers for it."""
        current = sys.version_info[:2]
        for owner, name, introduced, removed, _ in VERSION_GATED:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                present = hasattr(owner, name)
            expected = (introduced is None or current >= introduced) and (
                removed is None or current < removed
            )
            assert present is expected, f"{name} on {current}: expected {expected}"


class TestConstantFamilies:
    """The four `SQLITE_*` families and their counts on the page."""

    @staticmethod
    def _constants() -> set[str]:
        return {name for name in dir(sqlite3) if name.startswith("SQLITE_")}

    def test_every_constant_falls_into_a_family(self) -> None:
        constants = self._constants()
        limits = {name for name in constants if name.startswith("SQLITE_LIMIT_")}
        dbconfig = {name for name in constants if name.startswith("SQLITE_DBCONFIG_")}
        authorizer = constants & AUTHORIZER_CODES
        results = constants - limits - dbconfig - authorizer

        assert authorizer == AUTHORIZER_CODES
        assert len(limits) == (12 if sys.version_info >= (3, 11) else 0)
        assert len(results) == (103 if sys.version_info >= (3, 11) else 0)
        assert dbconfig <= DBCONFIG_NAMES, f"unreviewed: {dbconfig - DBCONFIG_NAMES}"
        if sys.version_info < (3, 12):
            assert not dbconfig
        assert all(isinstance(getattr(sqlite3, name), int) for name in constants)

    def test_the_counts_match_the_page(self) -> None:
        text = PAGE.read_text(encoding="utf-8")

        assert "Authorizer codes and `SQLITE_DONE`, 37 names" in text
        assert "Result codes, 103 names" in text
        assert "Limit categories, 12 names" in text
        assert f"Configuration options, up to {len(DBCONFIG_NAMES)} names" in text


class TestConnectDefersTheCheck:
    """`connect()` opens the file; SQLite checks it is a database only at the
    first statement."""

    def test_a_non_database_file_fails_on_the_first_statement(self, tmp_path: Any) -> None:
        path = tmp_path / "junk.db"
        path.write_bytes(b"not a database" * 1_000)

        connection = sqlite3.connect(path)
        try:
            with pytest.raises(sqlite3.DatabaseError):
                connection.execute("SELECT 1")
        finally:
            connection.close()


class TestStatementCache:
    """Up to 128 compiled statements by SQL text (100 on 3.10), counted by an
    authorizer, which SQLite consults only while compiling."""

    def test_one_text_compiles_once(self, rows: sqlite3.Connection) -> None:
        selects = count_compiles(rows)

        for wanted in range(10):
            rows.execute("SELECT name FROM t WHERE id = ?", (wanted,)).fetchone()

        assert len(selects) == 1

    def test_distinct_texts_compile_every_time(self, rows: sqlite3.Connection) -> None:
        selects = count_compiles(rows)

        for wanted in range(10):
            rows.execute(f"SELECT name FROM t WHERE id = {wanted}").fetchone()

        assert len(selects) == 10

    @staticmethod
    def _recompiles_after(texts: int, **kwargs: Any) -> int:
        connection = sqlite3.connect(":memory:", **kwargs)
        try:
            selects = count_compiles(connection)
            sql = [f"SELECT {i}" for i in range(texts)]
            for text in sql:
                connection.execute(text).fetchone()
            before = len(selects)
            for text in sql:
                connection.execute(text).fetchone()
            return len(selects) - before
        finally:
            connection.close()

    def test_the_default_capacity(self) -> None:
        capacity = 128 if sys.version_info >= (3, 11) else 100

        assert self._recompiles_after(capacity) == 0
        assert self._recompiles_after(capacity + 1) > 0

    def test_the_capacity_is_a_connection_argument(self) -> None:
        assert self._recompiles_after(8, cached_statements=8) == 0
        assert self._recompiles_after(9, cached_statements=8) > 0

    def test_the_page_gives_both_defaults(self) -> None:
        text = PAGE.read_text(encoding="utf-8")

        assert "cached_statements=128" in text
        assert "`cached_statements` defaults to 100 on Python 3.10" in text
        assert "up to 128 compiled statements (100 on Python 3.10)" in text

    def test_setting_an_authorizer_expires_compiled_statements(
        self, rows: sqlite3.Connection
    ) -> None:
        rows.execute("SELECT name FROM t WHERE id = 1").fetchone()

        selects = count_compiles(rows)
        rows.execute("SELECT name FROM t WHERE id = 1").fetchone()
        rows.execute("SELECT name FROM t WHERE id = 1").fetchone()

        assert len(selects) == 1, "the cached statement should compile once more, then hit"

    @pytest.mark.timing
    def test_setting_an_authorizer_grows_with_the_statements_held(self) -> None:
        def set_ns(statements: int) -> float:
            connection = sqlite3.connect(":memory:", cached_statements=statements)
            try:
                for i in range(statements):
                    connection.execute(f"SELECT {i}")
                allow = lambda *details: sqlite3.SQLITE_OK  # noqa: E731
                return best_ns(lambda: connection.set_authorizer(allow), repeats=5)
            finally:
                connection.close()

        small = set_ns(10)
        large = set_ns(10_000)

        ratio = large / small
        assert ratio > 50, f"1,000x the statements cost x{ratio:.1f} ({small:.0f}ns)"

    def test_executescript_compiles_on_every_run(self, rows: sqlite3.Connection) -> None:
        selects = count_compiles(rows)

        rows.executescript("SELECT name FROM t WHERE id = 1;")
        first = len(selects)
        rows.executescript("SELECT name FROM t WHERE id = 1;")

        assert first == 1
        assert len(selects) == 2


class TestClose:
    """`Connection.close()` | O(s): it finalizes each cached statement."""

    @staticmethod
    def _close_ns(statements: int) -> float:
        best: float | None = None
        for _ in range(5):
            connection = sqlite3.connect(":memory:", cached_statements=max(statements, 1))
            for i in range(statements):
                connection.execute(f"SELECT {i}")
            start = time.perf_counter_ns()
            connection.close()
            elapsed = float(time.perf_counter_ns() - start)
            best = elapsed if best is None else min(best, elapsed)
        assert best is not None
        return best

    @pytest.mark.timing
    def test_close_grows_with_the_cache(self) -> None:
        small = self._close_ns(100)
        large = self._close_ns(10_000)

        ratio = large / small
        assert ratio > 20, f"100x the statements cost x{ratio:.1f} to close ({small:.0f}ns)"

    def test_uncommitted_changes_are_lost(self, tmp_path: Any) -> None:
        path = tmp_path / "db.sqlite"
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE t (a)")
        connection.commit()
        connection.execute("INSERT INTO t VALUES (1)")
        connection.close()

        reopened = sqlite3.connect(path)
        try:
            assert reopened.execute("SELECT count(*) FROM t").fetchone() == (0,)
        finally:
            reopened.close()


class TestTransactions:
    """Commit is a no-op outside a transaction; several setters commit."""

    def test_commit_outside_a_transaction_issues_nothing(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            issued = trace(connection)
            connection.commit()
            connection.rollback()
            assert issued == []

            connection.execute("CREATE TABLE t (a)")
            connection.execute("INSERT INTO t VALUES (1)")
            assert connection.in_transaction
            connection.commit()
            assert issued[-1] == "COMMIT"
            assert not connection.in_transaction
        finally:
            connection.close()

    @pytest.mark.parametrize("setter", ["isolation_level", "autocommit"])
    def test_switching_to_autocommit_commits(self, setter: str) -> None:
        if setter == "autocommit" and sys.version_info < (3, 12):
            pytest.skip("Connection.autocommit is Python 3.12+")
        connection = sqlite3.connect(":memory:")
        try:
            issued = trace(connection)
            connection.execute("CREATE TABLE t (a)")
            connection.execute("INSERT INTO t VALUES (1)")
            assert connection.in_transaction

            if setter == "isolation_level":
                connection.isolation_level = None
            else:
                connection.autocommit = True  # type: ignore[attr-defined]

            assert issued[-1] == "COMMIT"
            assert not connection.in_transaction
        finally:
            connection.close()

    def test_executescript_commits_first(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            issued = trace(connection)
            connection.execute("CREATE TABLE t (a)")
            connection.execute("INSERT INTO t VALUES (1)")

            connection.executescript("SELECT 1;")

            assert issued[-2:] == ["COMMIT", "SELECT 1;"]
        finally:
            connection.close()

    def test_the_context_manager_commits_rolls_back_and_stays_open(
        self, rows: sqlite3.Connection
    ) -> None:
        with rows:
            rows.execute("INSERT INTO t VALUES (?, ?, ?)", (99_999, "new", 1))
        assert rows.execute("SELECT name FROM t WHERE id = 99999").fetchone() == ("new",)

        with pytest.raises(RuntimeError):
            with rows:
                rows.execute("INSERT INTO t VALUES (?, ?, ?)", (99_998, "gone", 1))
                raise RuntimeError("abandon")
        assert rows.execute("SELECT count(*) FROM t WHERE id = 99998").fetchone() == (0,)

        assert rows.execute("SELECT 1").fetchone() == (1,)


class TestConnectionShortcuts:
    """`Connection.execute()` makes a cursor and returns it."""

    def test_each_call_returns_a_new_cursor(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            first = connection.execute("SELECT 1")
            second = connection.execute("SELECT 1")
            assert isinstance(first, sqlite3.Cursor)
            assert first is not second
            assert first.connection is connection
        finally:
            connection.close()

    def test_a_cursor_copies_row_factory_when_created(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            before = connection.cursor()
            connection.row_factory = sqlite3.Row
            after = connection.cursor()

            assert before.row_factory is None
            assert after.row_factory is sqlite3.Row
            assert type(before.execute("SELECT 1 AS a").fetchone()) is tuple
        finally:
            connection.close()

    def test_the_exception_classes_are_reachable_from_a_connection(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            assert connection.Error is sqlite3.Error
            assert connection.IntegrityError is sqlite3.IntegrityError
        finally:
            connection.close()


class TestIndexesDecideThePlan:
    """The query rows, asserted through SQLite's own EXPLAIN QUERY PLAN:
    SEARCH is a B-tree descent, SCAN the whole table."""

    @staticmethod
    def _plan(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...] = ()) -> str:
        found = connection.execute(f"EXPLAIN QUERY PLAN {sql}", parameters).fetchall()
        return " ".join(str(row[3]) for row in found)

    def test_the_rowid_is_searched(self, rows: sqlite3.Connection) -> None:
        assert "SEARCH" in self._plan(rows, "SELECT * FROM t WHERE id = ?", (4_999,))

    def test_an_unindexed_column_is_scanned(self, rows: sqlite3.Connection) -> None:
        assert "SCAN" in self._plan(rows, "SELECT * FROM t WHERE name = ?", ("n4999",))

    def test_an_index_turns_the_scan_into_a_search(self, rows: sqlite3.Connection) -> None:
        rows.execute("CREATE INDEX idx_name ON t(name)")

        assert "SEARCH" in self._plan(rows, "SELECT * FROM t WHERE name = ?", ("n4999",))

    def test_a_covering_index_is_named_as_such(self, rows: sqlite3.Connection) -> None:
        rows.execute("CREATE INDEX idx_name ON t(name)")

        covering = self._plan(rows, "SELECT name FROM t WHERE name = ?", ("n1",))
        other = self._plan(rows, "SELECT * FROM t WHERE name = ?", ("n1",))

        assert "COVERING INDEX" in covering, covering
        assert "USING INDEX" in other and "COVERING" not in other, other

    def test_a_limit_stops_a_scan_early(self, rows: sqlite3.Connection) -> None:
        def steps(sql: str) -> int:
            count = 0

            def progress() -> int:
                nonlocal count
                count += 1
                return 0

            rows.set_progress_handler(progress, 1)
            try:
                rows.execute(sql).fetchall()
            finally:
                rows.set_progress_handler(None, 0)
            return count

        limited = steps("SELECT * FROM t WHERE age = 1 LIMIT 1")
        full = steps("SELECT * FROM t WHERE age = 1")

        assert limited * 50 < full, (limited, full)

    def test_order_by_without_an_index_sorts(self, rows: sqlite3.Connection) -> None:
        assert "TEMP B-TREE" in self._plan(rows, "SELECT * FROM t ORDER BY name")
        rows.execute("CREATE INDEX idx_name ON t(name)")
        assert "TEMP B-TREE" not in self._plan(rows, "SELECT * FROM t ORDER BY name")

    def test_update_and_delete_inherit_the_same_split(self, rows: sqlite3.Connection) -> None:
        assert "SEARCH" in self._plan(rows, "DELETE FROM t WHERE id = ?", (1,))
        assert "SCAN" in self._plan(rows, "DELETE FROM t WHERE name = ?", ("n1",))
        assert "SEARCH" in self._plan(rows, "UPDATE t SET age = 0 WHERE id = ?", (1,))
        assert "SCAN" in self._plan(rows, "UPDATE t SET age = 0 WHERE name = ?", ("n1",))

    @pytest.mark.timing
    def test_the_index_is_worth_what_the_plan_says(self, rows: sqlite3.Connection) -> None:
        scan_ns = best_ns(
            lambda: rows.execute("SELECT * FROM t WHERE name = ?", ("n4999",)).fetchone(),
            inner=3,
        )
        rows.execute("CREATE INDEX idx_name ON t(name)")
        search_ns = best_ns(
            lambda: rows.execute("SELECT * FROM t WHERE name = ?", ("n4999",)).fetchone(),
            inner=20,
        )

        ratio = scan_ns / search_ns
        assert ratio > 10, f"the index was worth x{ratio:.2f} over 5,000 rows"


class TestUpdateTouchesOnlyChangedIndexes:
    """UPDATE pays for the indexes on the columns it changes, not the rest.

    20,000 rows; every row updated. Five indexes on b..f leave an update of the
    unindexed column a within 3x of the same update on an unindexed table,
    while updating the indexed b costs more than 3x updating a (about 15x on
    the dev box).
    """

    @staticmethod
    def _update_s(column: str, indexes: int) -> float:
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("CREATE TABLE t (a, b, c, d, e, f)")
            for position, indexed in enumerate("bcdef"[:indexes]):
                connection.execute(f"CREATE INDEX i{position} ON t({indexed})")
            connection.executemany(
                "INSERT INTO t VALUES (?, ?, ?, ?, ?, ?)", ((i,) * 6 for i in range(20_000))
            )
            best: float | None = None
            for _ in range(3):
                start = time.perf_counter()
                connection.execute(f"UPDATE t SET {column} = {column} + 1")
                elapsed = time.perf_counter() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best
        finally:
            connection.close()

    @pytest.mark.timing
    def test_an_unindexed_column_skips_the_indexes(self) -> None:
        bare = self._update_s("a", 0)
        indexed_table = self._update_s("a", 5)
        indexed_column = self._update_s("b", 5)

        assert indexed_table < bare * 3, (bare, indexed_table)
        assert indexed_column > indexed_table * 3, (indexed_table, indexed_column)


class TestFetchingHoldsWhatYouAskFor:
    """Fixed-width values isolate the retained row-count dimension."""

    @pytest.fixture
    def payloads(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, payload TEXT)")
        connection.executemany(
            "INSERT INTO t VALUES (?, ?)", [(i, "x" * 100) for i in range(20_000)]
        )
        yield connection
        connection.close()

    def test_fetchall_holds_the_result_and_iteration_does_not(
        self, payloads: sqlite3.Connection
    ) -> None:
        collected = peak_bytes(lambda: payloads.execute("SELECT * FROM t").fetchall())
        streamed = peak_bytes(lambda: sum(1 for _ in payloads.execute("SELECT * FROM t")))

        assert collected > 1_000_000, f"fetchall peaked at only {collected} bytes"
        assert streamed * 100 < collected, f"streaming peaked at {streamed} bytes"

    def test_fetchmany_holds_the_batch(self, payloads: sqlite3.Connection) -> None:
        batch = peak_bytes(lambda: payloads.execute("SELECT * FROM t").fetchmany(100))
        collected = peak_bytes(lambda: payloads.execute("SELECT * FROM t").fetchall())

        assert batch < collected / 100

    def test_fetchmany_defaults_to_arraysize(self, payloads: sqlite3.Connection) -> None:
        cursor = payloads.execute("SELECT id FROM t")
        assert cursor.arraysize == 1
        assert len(cursor.fetchmany()) == 1
        cursor.arraysize = 500
        assert len(cursor.fetchmany()) == 500

    def test_fetchone_returns_none_at_the_end(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            cursor = connection.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
            assert cursor.fetchone() is None
        finally:
            connection.close()

    @pytest.mark.parametrize(
        "operation", ["script", "fetchone", "fetchmany", "fetchall", "iterate"]
    )
    def test_fixed_sql_does_more_work_as_the_table_grows(self, operation: str) -> None:
        """Each fetch runs the query to the next row, so a fetch returning one
        row scans every nonmatching row after it."""
        work = []
        for count in (100, 10_000):
            connection = sqlite3.connect(":memory:")
            try:
                connection.execute("CREATE TABLE t (x INTEGER)")
                connection.executemany("INSERT INTO t VALUES (?)", ((i,) for i in range(count)))
                steps = 0

                def progress() -> int:
                    nonlocal steps
                    steps += 1
                    return 0

                if operation == "script":
                    connection.set_progress_handler(progress, 1)
                    connection.executescript("SELECT sum(x) FROM t;")
                else:
                    cursor = connection.execute("SELECT x FROM t WHERE x = 0")
                    connection.set_progress_handler(progress, 1)
                    if operation == "fetchone":
                        assert cursor.fetchone() == (0,)
                    elif operation == "fetchmany":
                        assert cursor.fetchmany(1) == [(0,)]
                    elif operation == "fetchall":
                        assert cursor.fetchall() == [(0,)]
                    else:
                        assert next(cursor) == (0,)
                work.append(steps)
                connection.set_progress_handler(None, 0)
            finally:
                connection.close()
        assert work[1] > work[0] * 50, work

    @pytest.mark.parametrize("operation", ["fetchone", "fetchmany", "fetchall", "iterate"])
    @pytest.mark.parametrize("kind", [str, bytes])
    def test_one_column_payload_controls_fetch_allocation(self, operation: str, kind: type) -> None:
        retained = []
        connection = sqlite3.connect(":memory:")
        try:
            for length in (1_000, 1_000_000):
                value = "x" * length if kind is str else b"x" * length
                cursor = connection.execute("SELECT ? UNION ALL SELECT ?", (value, value))
                tracemalloc.start()
                try:
                    if operation == "fetchone":
                        result = cursor.fetchone()
                    elif operation == "fetchmany":
                        result = cursor.fetchmany(1)
                    elif operation == "fetchall":
                        result = cursor.fetchall()
                    else:
                        result = next(cursor)
                    retained.append(tracemalloc.get_traced_memory()[0])
                finally:
                    tracemalloc.stop()
                row = result[0] if operation in ("fetchmany", "fetchall") else result
                assert len(row) == 1 and row[0] == value
                assert row[0] is not value
        finally:
            connection.close()
        assert retained[1] > retained[0] * 100, retained

    def test_rows_convert_one_step_early_on_310_only(self) -> None:
        connection = sqlite3.connect(":memory:")
        conversions = []

        def text_factory(raw: bytes) -> str:
            conversions.append(len(raw))
            return raw.decode("utf-8")

        connection.text_factory = text_factory
        try:
            cursor = connection.execute("SELECT 'first' UNION ALL SELECT 'second'")
            assert conversions == ([5] if sys.version_info < (3, 11) else [])
            assert cursor.fetchone() == ("first",)
            assert conversions == ([5, 6] if sys.version_info < (3, 11) else [5])
            assert cursor.fetchall() == [("second",)]
            assert conversions == [5, 6]
        finally:
            connection.close()


class TestBinding:
    """`execute()` and `executemany()` pay for the bound bytes, one set at a
    time."""

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", [str, bytes])
    @pytest.mark.parametrize("many", [False, True])
    def test_binding_cost_grows_at_fixed_parameter_count(self, kind: type, many: bool) -> None:
        """SQL returns or stores only the fixed-size type name, so result
        copying and table storage do not grow with the parameter bytes."""
        times = []
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("CREATE TABLE t (v TEXT)")
            cursor = connection.cursor()
            for length in (1_000, 1_000_000):
                value = "x" * length if kind is str else b"x" * length
                params = (value,)
                sets = [params] * 3
                if many:
                    call = partial(cursor.executemany, "INSERT INTO t VALUES (typeof(?))", sets)
                else:
                    call = partial(cursor.execute, "SELECT typeof(?)", params)
                call()
                times.append(best_ns(call, inner=10))
        finally:
            connection.close()
        assert times[1] > times[0] * 5, times

    def test_binding_copies_mutable_blob_contents(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            for length in (1_000, 1_000_000):
                value = bytearray(b"x" * length)
                cursor = connection.execute("SELECT ?", (value,))
                value[:] = b"y" * length
                assert cursor.fetchone() == (b"x" * length,)
        finally:
            connection.close()

    def test_executemany_takes_one_set_at_a_time(self) -> None:
        log: list[tuple[str, int]] = []
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("CREATE TABLE t (a)")
            connection.create_function("record", 1, lambda v: log.append(("run", v)) or v)

            def sets() -> Iterator[tuple[int]]:
                for i in range(3):
                    log.append(("take", i))
                    yield (i,)

            connection.executemany("INSERT INTO t VALUES (record(?))", sets())

            assert log == [
                ("take", 0),
                ("run", 0),
                ("take", 1),
                ("run", 1),
                ("take", 2),
                ("run", 2),
            ]
        finally:
            connection.close()

    def test_executemany_refuses_a_query(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            with pytest.raises(sqlite3.ProgrammingError):
                connection.executemany("SELECT ?", [(1,)])
        finally:
            connection.close()


class TestDescription:
    """Built by `execute()`, the same tuple on each access."""

    @pytest.mark.parametrize("count", [1, 100])
    @pytest.mark.parametrize("name_length", [10, 1_000])
    def test_execution_builds_it_and_access_reuses_it(self, count: int, name_length: int) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            names = [f"c{i}" + "x" * name_length for i in range(count)]
            sql = "SELECT " + ", ".join(f'1 AS "{name}"' for name in names)
            cursor: Any = connection.cursor()
            assert cursor.description is None
            cursor.execute(sql)
            first: Any = cursor.description
            assert [column[0] for column in first] == names
            assert all(len(column) == 7 and column[1:] == (None,) * 6 for column in first)
            assert cursor.description is first
            cursor.fetchall()
            assert cursor.description is first
            cursor.execute(sql)
            assert cursor.description == first and cursor.description is not first
        finally:
            connection.close()


class TestRow:
    """`row[name]` compares with each column name in turn; the rest is tuple
    work on the row's values."""

    class CountingKey(str):
        comparisons = 0

        def __eq__(self, other: object) -> bool:
            type(self).comparisons += 1
            return str.__eq__(self, other)

        __hash__ = str.__hash__

    @pytest.fixture
    def wide(self) -> Iterator[sqlite3.Row]:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        columns = ", ".join(f"{index} AS c{index}" for index in range(60))
        yield connection.execute(f"SELECT {columns}").fetchone()
        connection.close()

    def _lookup(self, row: sqlite3.Row, name: str) -> tuple[Any, int]:
        self.CountingKey.comparisons = 0
        value = row[self.CountingKey(name)]
        return value, self.CountingKey.comparisons

    def test_the_first_column_takes_one_comparison(self, wide: sqlite3.Row) -> None:
        assert self._lookup(wide, "c0") == (0, 1)

    def test_the_last_column_takes_one_per_column(self, wide: sqlite3.Row) -> None:
        assert self._lookup(wide, "c59") == (59, 60)
        assert self._lookup(wide, "C59") == (59, 60)

    def test_only_ascii_letters_fold_case(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute('SELECT 1 AS "Äb", 2 AS "Cd"').fetchone()
            assert row["cD"] == 2
            with pytest.raises(IndexError):
                row["äb"]
        finally:
            connection.close()

    def test_keys_is_a_new_list_each_call(self, wide: sqlite3.Row) -> None:
        assert wide.keys() == [f"c{index}" for index in range(60)]
        assert wide.keys() is not wide.keys()

    def test_the_tuple_operations(self, wide: sqlite3.Row) -> None:
        assert wide[0] == 0 and wide[-1] == 59
        assert wide[10:13] == (10, 11, 12)
        assert len(wide) == 60
        assert list(wide) == list(range(60))

    def test_equal_rows_compare_and_hash_equal(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            first = connection.execute("SELECT 1 AS a, 2 AS b").fetchone()
            second = connection.execute("SELECT 1 AS a, 2 AS b").fetchone()
            renamed = connection.execute("SELECT 1 AS a, 2 AS c").fetchone()
            assert first == second and hash(first) == hash(second)
            assert first != renamed
        finally:
            connection.close()

    def test_construction_does_not_copy_the_values(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            cursor = connection.execute("SELECT 1")
            data = tuple(range(100_000))
            sqlite3.Row(cursor, data)

            peak = peak_bytes(lambda: sqlite3.Row(cursor, data))

            assert peak < 1_000, f"wrapping a 100,000-item tuple peaked at {peak} bytes"
        finally:
            connection.close()


class TestConversion:
    """Adapters and converters: one dict entry each, then a call per value."""

    def test_a_round_trip_through_both(self) -> None:
        class Point:
            def __init__(self, x: float, y: float) -> None:
                self.x, self.y = x, y

        sqlite3.register_adapter(Point, lambda p: f"{p.x};{p.y}")
        sqlite3.register_converter(
            "point", lambda raw: Point(*(float(part) for part in raw.split(b";")))
        )
        connection = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            assert (Point, sqlite3.PrepareProtocol) in sqlite3.adapters
            assert "POINT" in sqlite3.converters
            connection.execute("CREATE TABLE places (location point)")
            connection.execute("INSERT INTO places VALUES (?)", (Point(1.0, 2.0),))

            restored = connection.execute("SELECT location FROM places").fetchone()[0]

            assert (restored.x, restored.y) == (1.0, 2.0)
        finally:
            connection.close()
            sqlite3.adapters.pop((Point, sqlite3.PrepareProtocol), None)
            sqlite3.converters.pop("POINT", None)

    def test_converters_are_looked_up_once_per_execute(self) -> None:
        connection = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            connection.execute("CREATE TABLE t (v WiBbLe)")
            connection.executemany("INSERT INTO t VALUES (?)", [("a",), ("b",)])
            cursor = connection.execute("SELECT v FROM t")

            sqlite3.register_converter("wibble", lambda raw: b"converted")
            assert cursor.fetchall() == [("a",), ("b",)]
            assert connection.execute("SELECT v FROM t").fetchall() == [(b"converted",)] * 2
        finally:
            connection.close()
            sqlite3.converters.pop("WIBBLE", None)

    def test_null_never_reaches_a_converter(self) -> None:
        seen: list[bytes] = []
        sqlite3.register_converter("tracked", lambda raw: seen.append(raw) or raw)
        connection = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            connection.execute("CREATE TABLE t (v tracked)")
            connection.executemany("INSERT INTO t VALUES (?)", [(None,), ("a",)])

            assert connection.execute("SELECT v FROM t").fetchall() == [(None,), (b"a",)]
            assert seen == [b"a"]
        finally:
            connection.close()
            sqlite3.converters.pop("TRACKED", None)

    def test_an_empty_value_never_reaches_a_converter(self) -> None:
        seen: list[bytes] = []
        sqlite3.register_converter("tracked", lambda raw: seen.append(raw) or raw)
        connection = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        try:
            connection.execute("CREATE TABLE t (v tracked)")
            connection.executemany("INSERT INTO t VALUES (?)", [("",), (b"",), ("x",)])

            assert connection.execute("SELECT v FROM t").fetchall() == [(None,), (None,), (b"x",)]
            assert seen == [b"x"]
        finally:
            connection.close()
            sqlite3.converters.pop("TRACKED", None)

    def test_parse_colnames_converts_by_column_alias(self) -> None:
        sqlite3.register_converter("shout", lambda raw: raw.upper())
        connection = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_COLNAMES)
        try:
            row = connection.execute("SELECT 'abc' AS \"v [shout]\"").fetchone()
            assert row == (b"ABC",)
        finally:
            connection.close()
            sqlite3.converters.pop("SHOUT", None)

    def test_the_registries_and_aliases(self) -> None:
        import datetime

        assert isinstance(sqlite3.adapters, dict)
        assert isinstance(sqlite3.converters, dict)
        assert sqlite3.Date is datetime.date
        assert sqlite3.Time is datetime.time  # type: ignore[attr-defined]
        assert sqlite3.Timestamp is datetime.datetime  # type: ignore[attr-defined]
        assert sqlite3.Binary is memoryview
        assert sqlite3.DateFromTicks(0) == datetime.date.fromtimestamp(0)
        assert sqlite3.PARSE_DECLTYPES & sqlite3.PARSE_COLNAMES == 0

    def test_adapt_uses_the_registry_then_the_fallback(self) -> None:
        class Money:
            pass

        sqlite3.register_adapter(Money, lambda value: "1.00")
        try:
            adapt: Any = sqlite3.adapt
            assert adapt(Money()) == "1.00"
            assert adapt(object(), sqlite3.PrepareProtocol, "alt") == "alt"
        finally:
            sqlite3.adapters.pop((Money, sqlite3.PrepareProtocol), None)


class TestCallbacks:
    """Registration is O(1); the callable runs once per call, row or
    comparison the SQL makes."""

    @pytest.fixture
    def names(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE t (name TEXT, grp INTEGER)")
        connection.executemany(
            "INSERT INTO t VALUES (?, ?)", [(f"n{(i * 7919) % 1000}", i % 10) for i in range(1000)]
        )
        yield connection
        connection.close()

    def test_a_function_runs_once_per_row(self, names: sqlite3.Connection) -> None:
        calls: list[str] = []
        names.create_function("shout", 1, lambda text: calls.append(text) or text.upper())

        names.execute("SELECT shout(name) FROM t").fetchall()

        assert len(calls) == 1000

    def test_an_aggregate_steps_per_row_and_finalizes_per_group(
        self, names: sqlite3.Connection
    ) -> None:
        events: list[str] = []

        class Count:
            def __init__(self) -> None:
                self.total = 0

            def step(self, value: Any) -> None:
                events.append("step")
                self.total += 1

            def finalize(self) -> int:
                events.append("finalize")
                return self.total

        names.create_aggregate("tally", 1, Count)  # type: ignore[arg-type]

        result = names.execute("SELECT grp, tally(name) FROM t GROUP BY grp").fetchall()

        assert result == [(group, 100) for group in range(10)]
        assert events.count("step") == 1000
        assert events.count("finalize") == 10

    def test_a_collation_runs_once_per_comparison(self, names: sqlite3.Connection) -> None:
        comparisons: list[int] = []

        def compare(left: str, right: str) -> int:
            comparisons.append(1)
            return (left > right) - (left < right)

        names.create_collation("counted", compare)

        names.execute("SELECT name FROM t ORDER BY name COLLATE counted").fetchall()

        assert 999 <= len(comparisons) <= 2 * 1000 * math.log2(1000), len(comparisons)

    def test_the_authorizer_is_not_asked_again_for_a_cached_statement(
        self, names: sqlite3.Connection
    ) -> None:
        actions: list[int] = []
        names.set_authorizer(lambda action, *details: actions.append(action) or 0)

        names.execute("SELECT name FROM t WHERE grp = ?", (1,)).fetchall()
        compiled = len(actions)
        names.execute("SELECT name FROM t WHERE grp = ?", (2,)).fetchall()

        assert compiled > 0
        assert len(actions) == compiled

    def test_interrupt_aborts_the_running_query(self, names: sqlite3.Connection) -> None:
        names.set_progress_handler(lambda: names.interrupt() or 0, 100)
        try:
            with pytest.raises(sqlite3.OperationalError, match="interrupted"):
                names.execute("SELECT count(*) FROM t a, t b").fetchone()
        finally:
            names.set_progress_handler(None, 0)

    def test_limits_round_trip(self) -> None:
        if not hasattr(sqlite3.Connection, "setlimit"):
            pytest.skip("Connection.setlimit is Python 3.11+")
        connection: Any = sqlite3.connect(":memory:")
        try:
            category = sqlite3.SQLITE_LIMIT_SQL_LENGTH  # type: ignore[attr-defined]
            previous = connection.setlimit(category, 1_000)
            assert connection.getlimit(category) == 1_000
            assert previous >= 1_000
        finally:
            connection.close()


class TestCopyingADatabase:
    """`backup()` steps through pages; `iterdump()` yields a row at a time."""

    @staticmethod
    def _filled(rows: int, width: int = 20) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, payload TEXT)")
        connection.executemany(
            "INSERT INTO t VALUES (?, ?)", ((i, "x" * width) for i in range(rows))
        )
        connection.commit()
        return connection

    def test_backup_reports_once_per_step(self) -> None:
        source = self._filled(1_000, width=1_000)
        target = sqlite3.connect(":memory:")
        try:
            pages = source.execute("PRAGMA page_count").fetchone()[0]
            remaining: list[int] = []

            source.backup(
                target, pages=10, progress=lambda status, left, total: remaining.append(left)
            )

            assert len(remaining) == math.ceil(pages / 10)
            assert remaining[-1] == 0
            assert target.execute("SELECT count(*) FROM t").fetchone() == (1_000,)
        finally:
            source.close()
            target.close()

    def test_iterdump_yields_one_statement_per_row(self) -> None:
        connection = self._filled(100)
        try:
            statements = list(connection.iterdump())
            assert statements[0] == "BEGIN TRANSACTION;"
            assert statements[-1] == "COMMIT;"
            assert sum(s.startswith('INSERT INTO "t"') for s in statements) == 100
        finally:
            connection.close()

    def test_iterdump_memory_does_not_grow_with_the_table(self) -> None:
        peaks = []
        listed = 0
        for count in (20_000, 200_000):
            connection = self._filled(count)
            try:

                def consume(dumped: sqlite3.Connection = connection) -> None:
                    for _ in dumped.iterdump():
                        pass

                consume()
                peaks.append(peak_bytes(consume))
                if count == 200_000:
                    listed = peak_bytes(partial(list, connection.iterdump()))
            finally:
                connection.close()

        assert max(peaks) < 100_000, peaks
        assert listed > peaks[1] * 100, (listed, peaks)

    def test_serialize_returns_the_whole_database(self) -> None:
        connection: Any = self._filled(1_000, width=1_000)
        if not hasattr(connection, "serialize"):
            connection.close()
            pytest.skip("Connection.serialize needs Python 3.11+ and SQLite's serialize API")
        copy: Any = sqlite3.connect(":memory:")
        try:
            image = connection.serialize()
            assert len(image) > 1_000_000
            assert image.startswith(b"SQLite format 3\x00")

            copy.deserialize(image)
            assert copy.execute("SELECT count(*) FROM t").fetchone() == (1_000,)
        finally:
            connection.close()
            copy.close()


@needs_blob
class TestBlob:
    """`Blob` reads and writes part of a value without loading it."""

    SIZE = 20_000_000

    @pytest.fixture
    def blobs(self) -> Iterator[Any]:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE b (data BLOB)")
        connection.execute("INSERT INTO b VALUES (zeroblob(?))", (self.SIZE,))
        connection.execute("INSERT INTO b VALUES (zeroblob(100))")
        yield connection
        connection.close()

    @pytest.mark.timing
    def test_a_fresh_handle_walks_to_a_deep_offset(self, blobs: Any) -> None:
        def fresh_read(offset: int) -> Callable[[], None]:
            def read() -> None:
                with blobs.blobopen("b", "data", 1) as blob:
                    blob.seek(offset)
                    blob.read(100)

            return read

        shallow = best_ns(fresh_read(0))
        deep = best_ns(fresh_read(self.SIZE - 100))

        ratio = deep / shallow
        assert ratio > 20, f"a first read at the end cost x{ratio:.1f} one at the start"

    @pytest.mark.timing
    def test_one_handle_reads_any_offset_at_the_same_cost(self, blobs: Any) -> None:
        with blobs.blobopen("b", "data", 1) as blob:
            blob.seek(self.SIZE - 100)
            blob.read(100)

            def read_at(offset: int) -> Callable[[], Any]:
                return lambda: (blob.seek(offset), blob.read(100))

            shallow = best_ns(read_at(0), inner=200)
            deep = best_ns(read_at(self.SIZE - 100), inner=200)

        ratio = deep / shallow
        assert ratio < 3, f"a repeated read at the end cost x{ratio:.1f} one at the start"

    @pytest.mark.timing
    def test_opening_cost_does_not_grow_with_the_value(self, blobs: Any) -> None:
        large = best_ns(lambda: blobs.blobopen("b", "data", 1).close(), inner=50)
        small = best_ns(lambda: blobs.blobopen("b", "data", 2).close(), inner=50)

        ratio = large / small
        assert ratio < 3, f"opening a 20 MB blob cost x{ratio:.1f} opening a 100-byte one"

    def test_a_stepped_slice_reads_the_whole_span(self, blobs: Any) -> None:
        with blobs.blobopen("b", "data", 1) as blob:
            blob[0:10]
            span = 4_000_000

            peak = peak_bytes(lambda: blob[0 : span : span // 10])

            assert blob[0 : span : span // 10] == bytes(10)
            assert peak > span, f"a 10-byte stepped slice peaked at {peak} bytes"

    def test_length_position_and_fixed_size(self, blobs: Any) -> None:
        with blobs.blobopen("b", "data", 2) as blob:
            assert len(blob) == 100
            blob.seek(98)
            assert blob.tell() == 98
            with pytest.raises(ValueError):
                blob.write(b"abc")
            blob[0] = 7
            assert blob[0] == 7


class TestErrors:
    """The DB-API hierarchy, and the result code carried on the exception."""

    def test_the_hierarchy(self) -> None:
        assert issubclass(sqlite3.IntegrityError, sqlite3.DatabaseError)
        assert issubclass(sqlite3.DatabaseError, sqlite3.Error)
        assert issubclass(sqlite3.InterfaceError, sqlite3.Error)
        assert issubclass(sqlite3.Error, Exception)
        assert issubclass(sqlite3.Warning, Exception)

    def test_a_constraint_violation_carries_its_code(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO t VALUES (1)")

            with pytest.raises(sqlite3.IntegrityError) as caught:
                connection.execute("INSERT INTO t VALUES (1)")

            if sys.version_info >= (3, 11):
                assert caught.value.sqlite_errorname == "SQLITE_CONSTRAINT_PRIMARYKEY"
                assert caught.value.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY
            else:
                assert not hasattr(caught.value, "sqlite_errorcode")
        finally:
            connection.close()


class TestModuleMetadata:
    """The DB-API constants and the helper that is not about a query."""

    def test_the_dbapi_metadata(self) -> None:
        assert sqlite3.apilevel == "2.0"
        assert sqlite3.paramstyle == "qmark"
        assert isinstance(sqlite3.threadsafety, int)

    def test_the_version_reported_is_sqlite_s(self) -> None:
        assert sqlite3.sqlite_version_info == tuple(
            int(part) for part in sqlite3.sqlite_version.split(".")
        )

    def test_complete_statement_wants_the_semicolon(self) -> None:
        assert sqlite3.complete_statement("SELECT 1;") is True
        assert sqlite3.complete_statement("SELECT 1") is False
        assert sqlite3.complete_statement("SELECT * FROM no_such_table;") is True

    def test_the_submodule_re_exports_the_module(self) -> None:
        from sqlite3 import dbapi2

        assert dbapi2.connect is sqlite3.connect
        assert dbapi2.Row is sqlite3.Row


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


def _missing_api(source: str) -> str | None:
    """The Connection method a block needs that this interpreter lacks."""
    for name in ("blobopen", "serialize"):
        if f".{name}(" in source and not hasattr(sqlite3.Connection, name):
            return name
    return None


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
    """Each block runs in its own subprocess against `:memory:` databases, so
    adapter registrations cannot leak between them and no files are left."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_no_block_opens_a_database_on_disk(self) -> None:
        for line, source in _blocks():
            for target in re.findall(r"connect\(([^,)]*)", source):
                assert target == "':memory:'", f"{PAGE.name}:{line} connects to {target}"

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        skipped = 0
        for line, source in _blocks():
            if _missing_api(source):
                skipped += 1
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran + skipped == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next(
            (n, s) for n, s in _blocks() if "actions.count(sqlite3.SQLITE_SELECT) == 1\n" in s
        )
        mutated = source.replace(
            "actions.count(sqlite3.SQLITE_SELECT) == 1\n",
            "actions.count(sqlite3.SQLITE_SELECT) == 10\n",
            1,
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
