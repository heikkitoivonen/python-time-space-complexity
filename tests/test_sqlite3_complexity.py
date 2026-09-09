"""Tests to verify documented behaviour of the sqlite3 module.

docs/stdlib/sqlite3.md had five rows, one of them "Varies", for a module with
206 public names on 3.14. Most of what a query costs belongs to SQLite's planner
rather than to Python, so the page names the two things the module itself
controls, and these tests measure them.

* **Statements are cached.** Re-executing one SQL text costs 972ns on 3.10 and
  1,056ns on 3.14; a fresh text each time costs 2,840ns and 2,815ns. The
  connection keeps the last `cached_statements` compiled, so parameter
  placeholders are a performance argument as well as a safety one.
* **`sqlite3.Row` looks a column up by scanning the names.** On a three-column
  row the first and last differ by little; on a sixty-column row the first name
  costs 34-45ns and the last 579-615ns, about seventeen times. Index access is
  flat at 29-41ns either way.

The planner claims are asserted through `EXPLAIN QUERY PLAN`, which says SEARCH
or SCAN in as many words - no tolerance, and it is SQLite's own answer rather
than a timing inference. The timings behind it, on 50,000 rows: 1.67us by
rowid, 1.48ms scanning for an unindexed name, and 1.9-2.0us once an index
exists - about 750 times.

Fetching separates by allocation rather than by clock: 20,000 rows collected
with `fetchall()` peak at 7.6-7.8MB, the same rows streamed through the cursor
at 426-1,097 bytes, and `fetchmany(100)` at 5.6-6.9KB.

Not settled here:

* Durability. Every measurement uses `:memory:`, so no commit here pays for an
  fsync. What a commit costs on real storage is the filesystem's.
* SQLite's own bounds. The B-tree descent and the page cache are the library's,
  documented by SQLite; the page cites them rather than re-deriving them.
`Error.sqlite_errorcode` and `sqlite_errorname` are 3.11+, and `version` and
`version_info` were deprecated in 3.12 but only removed in 3.14 - they stay
reachable through a module `__getattr__` in between, so the check uses
`hasattr` rather than `dir()`.

The constant families are counted rather than listed: 37 authorizer codes on
every version, plus 103 result codes and 12 `SQLITE_LIMIT_*` from 3.11 and 16
`SQLITE_DBCONFIG_*` from 3.12 - not 3.11, which is where a first pass put
them.

* `executemany` against a loop of `execute`. It is 1.4-1.7x on 5,000 inserts,
  which is real but too close to leave as a threshold on a shared runner.

Axes not varied: WAL mode, concurrent connections, `detect_types` beyond one
adapter/converter round trip, and blob I/O through `sqlite3.Blob`.
"""

import inspect
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
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sqlite3.md"

EXPECTED_BLOCKS = 8

# The 3.10 constant set: authorizer action codes plus the four return values.
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

# Documented, but not present on every supported version, as
# (first version that has it, first version that does not).
VERSION_GATED = {
    "Blob": ((3, 11), None),
    "LEGACY_TRANSACTION_CONTROL": ((3, 12), None),
    "enable_shared_cache": (None, (3, 12)),
    "version": (None, (3, 14)),
    "version_info": (None, (3, 14)),
}

# The phrase each gated row has to carry.
VERSION_MARKERS = {
    "Blob": "Python 3.11+",
    "LEGACY_TRANSACTION_CONTROL": "Python 3.12+",
    "enable_shared_cache": "Removed in Python 3.12",
    "version": "removed in Python 3.14",
    "version_info": "removed in Python 3.14",
}

# A public submodule, so `inspect.ismodule` filters it out of the name sweep.
SUBMODULES = {"dbapi2"}


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


def _public_names() -> set[str]:
    """Everything public in `sqlite3` that is not an imported module."""
    return {
        name
        for name in dir(sqlite3)
        if not name.startswith("_") and not inspect.ismodule(getattr(sqlite3, name))
    }


def _documented_names() -> set[str]:
    """Every `sqlite3.<name>` the Complexity Reference tables mention."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("## Complexity Reference")
    end = text.index("\n## Connecting and Executing", start)
    return set(re.findall(r"sqlite3\.([A-Za-z_][A-Za-z0-9_]*)", text[start:end]))


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


class TestEveryPublicNameIsDocumented:
    """The tables have to name every public attribute of `sqlite3`.

    The constants are covered by family rather than one row each - 168 of the
    206 names on 3.14 are `SQLITE_*` integers - so the check has two halves:
    every other name appears by name, and every constant falls into one of the
    four documented families.
    """

    @staticmethod
    def _plain(names: set[str]) -> set[str]:
        return {name for name in names if not name.startswith("SQLITE_")}

    def test_no_plain_name_is_missing_from_the_tables(self) -> None:
        missing = sorted(self._plain(_public_names()) - _documented_names())

        assert not missing, f"{len(missing)} public names absent from the tables: {missing}"

    def test_the_tables_name_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        allowed = _public_names() | set(VERSION_GATED) | SUBMODULES

        unknown = sorted(_documented_names() - allowed)

        assert not unknown, f"the tables name attributes sqlite3 does not have: {unknown}"

    def test_the_submodule_is_documented_and_real(self) -> None:
        assert SUBMODULES <= _documented_names()
        assert inspect.ismodule(sqlite3.dbapi2)  # type: ignore[attr-defined]

    def test_every_constant_falls_into_a_documented_family(self) -> None:
        constants = {name for name in _public_names() if name.startswith("SQLITE_")}

        limits = {name for name in constants if name.startswith("SQLITE_LIMIT_")}
        dbconfig = {name for name in constants if name.startswith("SQLITE_DBCONFIG_")}
        authorizer = constants & AUTHORIZER_CODES
        results = constants - limits - dbconfig - authorizer

        assert authorizer == AUTHORIZER_CODES, "the authorizer family should be complete"
        assert len(limits | dbconfig | authorizer | results) == len(constants)

        # 37 on 3.10; 3.11 adds the result codes and the limit categories, 3.12
        # the dbconfig switches. The counts have been stable since each landed.
        assert len(limits) == (12 if sys.version_info >= (3, 11) else 0)
        assert len(results) == (103 if sys.version_info >= (3, 11) else 0)
        assert len(dbconfig) == (16 if sys.version_info >= (3, 12) else 0)

    def test_the_family_counts_match_the_page(self) -> None:
        """So a release that adds a constant fails here rather than drifting."""
        text = PAGE.read_text(encoding="utf-8")

        assert "| 37 |" in text, "the authorizer family row should say 37"
        assert "| 103 |" in text, "the result-code family row should say 103"
        assert "| 12 |" in text, "the limit family row should say 12"
        assert "| 16 |" in text, "the dbconfig family row should say 16"

    def test_the_family_table_names_each_of_the_four(self) -> None:
        text = PAGE.read_text(encoding="utf-8")

        for marker in (
            "Authorizer action codes",
            "Result and error codes",
            "`SQLITE_LIMIT_*`",
            "`SQLITE_DBCONFIG_*`",
        ):
            assert marker in text, f"no family row for {marker}"

    def test_the_version_gated_names_say_so(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        for name, expected in sorted(VERSION_MARKERS.items()):
            owning = [row for row in rows if f"sqlite3.{name}" in row]
            assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
            assert expected in owning[0], f"the {name} row should say {expected}: {owning[0]}"

    def test_the_gated_names_match_this_interpreter(self) -> None:
        """`hasattr`, not `dir()`: a deprecated name is reachable but hidden.

        `sqlite3.version` is absent from `dir()` from 3.12 while a module
        `__getattr__` still answers for it, and only 3.14 takes it away.
        """
        current = sys.version_info[:2]
        for name, (introduced, removed) in VERSION_GATED.items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                present = hasattr(sqlite3, name)

            expected = (introduced is None or current >= introduced) and (
                removed is None or current < removed
            )
            assert present is expected, f"{name} on {current}: expected {expected}"

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        assert 70 <= len(_public_names()) <= 215, (
            f"sqlite3 has {len(_public_names())} public names; re-run the coverage audit"
        )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"connect", "Connection", "Cursor", "Row", "Error"} <= documented
        thinned = documented - {"complete_statement"}
        assert self._plain(_public_names()) - thinned == {"complete_statement"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestStatementsAreCached:
    """`execute()` skips the compile for SQL text the connection has seen."""

    def test_the_same_text_gives_the_same_answer(self, rows: sqlite3.Connection) -> None:
        for wanted in range(5):
            found = rows.execute("SELECT name FROM t WHERE id = ?", (wanted,)).fetchone()
            assert found == (f"n{wanted}",)

    def test_the_cache_size_is_a_connection_argument(self) -> None:
        connection = sqlite3.connect(":memory:", cached_statements=8)
        try:
            assert connection.execute("SELECT 1").fetchone() == (1,)
        finally:
            connection.close()

    @pytest.mark.timing
    def test_a_reused_statement_is_cheaper_than_a_fresh_one(self, rows: sqlite3.Connection) -> None:
        counter = [0]

        def fresh() -> None:
            counter[0] += 1
            rows.execute(f"SELECT {counter[0]}").fetchone()

        cached_ns = best_ns(lambda: rows.execute("SELECT 1").fetchone(), inner=50)
        fresh_ns = best_ns(fresh, inner=20)

        ratio = fresh_ns / cached_ns
        assert ratio > 1.5, (
            f"a fresh statement cost x{ratio:.2f} a cached one "
            f"({cached_ns:.0f}ns to {fresh_ns:.0f}ns)"
        )


class TestIndexesDecideThePlan:
    """The SELECT rows, asserted through SQLite's own EXPLAIN QUERY PLAN.

    SEARCH means a B-tree descent, SCAN means the whole table - so the claim is
    read off the planner rather than inferred from a clock.
    """

    @staticmethod
    def _plan(connection: sqlite3.Connection, sql: str, parameters: tuple[Any, ...]) -> str:
        row = connection.execute(f"EXPLAIN QUERY PLAN {sql}", parameters).fetchone()
        return str(row[3])

    def test_the_rowid_is_searched(self, rows: sqlite3.Connection) -> None:
        plan = self._plan(rows, "SELECT * FROM t WHERE id = ?", (4_999,))

        assert "SEARCH" in plan, plan

    def test_an_unindexed_column_is_scanned(self, rows: sqlite3.Connection) -> None:
        plan = self._plan(rows, "SELECT * FROM t WHERE name = ?", ("n4999",))

        assert "SCAN" in plan, plan

    def test_an_index_turns_the_scan_into_a_search(self, rows: sqlite3.Connection) -> None:
        rows.execute("CREATE INDEX idx_name ON t(name)")

        plan = self._plan(rows, "SELECT * FROM t WHERE name = ?", ("n4999",))

        assert "SEARCH" in plan, plan

    def test_a_delete_inherits_the_same_split(self, rows: sqlite3.Connection) -> None:
        assert "SEARCH" in self._plan(rows, "DELETE FROM t WHERE id = ?", (1,))
        assert "SCAN" in self._plan(rows, "DELETE FROM t WHERE name = ?", ("n1",))

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
        assert ratio > 10, (
            f"the index was worth x{ratio:.2f} ({scan_ns:.0f}ns to {search_ns:.0f}ns) "
            "over 5,000 rows"
        )


class TestFetchingHoldsWhatYouAskFor:
    """`fetchall()` | O(r·c) | O(r·c) against iteration's O(c)."""

    @pytest.fixture
    def payloads(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, payload TEXT)")
        connection.executemany(
            "INSERT INTO t VALUES (?, ?)", [(i, "x" * 100) for i in range(20_000)]
        )
        yield connection
        connection.close()

    def test_all_three_forms_see_the_same_rows(self, payloads: sqlite3.Connection) -> None:
        assert len(payloads.execute("SELECT * FROM t").fetchall()) == 20_000
        assert sum(1 for _ in payloads.execute("SELECT * FROM t")) == 20_000
        assert len(payloads.execute("SELECT * FROM t").fetchmany(100)) == 100

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

    def test_fetchone_returns_none_at_the_end(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            cursor = connection.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
            assert cursor.fetchone() is None
        finally:
            connection.close()


class TestRowLookupByNameScans:
    """`sqlite3.Row['name']` | O(c) | O(1), against `row[i]`'s O(1)."""

    @pytest.fixture
    def wide(self) -> Iterator[sqlite3.Row]:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        columns = ", ".join(f"c{index} INTEGER" for index in range(60))
        connection.execute(f"CREATE TABLE wide ({columns})")
        connection.execute(f"INSERT INTO wide VALUES ({','.join('?' * 60)})", tuple(range(60)))
        row = connection.execute("SELECT * FROM wide").fetchone()
        yield row
        connection.close()

    def test_both_forms_reach_the_same_value(self, wide: sqlite3.Row) -> None:
        assert wide[0] == 0
        assert wide["c0"] == 0
        assert wide[59] == 59
        assert wide["c59"] == 59

    def test_names_are_matched_case_insensitively(self, wide: sqlite3.Row) -> None:
        assert wide["C0"] == 0
        assert wide["C59"] == 59

    def test_keys_are_the_column_names(self, wide: sqlite3.Row) -> None:
        assert wide.keys() == [f"c{index}" for index in range(60)]

    def test_an_unknown_name_raises(self, wide: sqlite3.Row) -> None:
        with pytest.raises(IndexError):
            wide["nope"]

    @pytest.mark.timing
    def test_the_last_column_costs_more_than_the_first_by_name(self, wide: sqlite3.Row) -> None:
        first_ns = best_ns(lambda: wide["c0"], inner=200)
        last_ns = best_ns(lambda: wide["c59"], inner=200)

        ratio = last_ns / first_ns
        assert ratio > 3, (
            f"the sixtieth column cost x{ratio:.2f} the first "
            f"({first_ns:.0f}ns to {last_ns:.0f}ns); the row claims a scan"
        )

    @pytest.mark.timing
    def test_index_access_is_flat(self, wide: sqlite3.Row) -> None:
        first_ns = best_ns(lambda: wide[0], inner=200)
        last_ns = best_ns(lambda: wide[59], inner=200)

        ratio = last_ns / first_ns
        assert ratio < 2, (
            f"indexing the sixtieth column cost x{ratio:.2f} the first "
            f"({first_ns:.0f}ns to {last_ns:.0f}ns); tuple indexing is O(1)"
        )


class TestTransactions:
    """The connection context manager commits or rolls back, and does not
    close."""

    def test_it_commits_on_success(self, rows: sqlite3.Connection) -> None:
        with rows:
            rows.execute("INSERT INTO t VALUES (?, ?, ?)", (99_999, "new", 1))

        assert rows.execute("SELECT name FROM t WHERE id = ?", (99_999,)).fetchone() == ("new",)

    def test_it_rolls_back_on_an_exception(self, rows: sqlite3.Connection) -> None:
        before = rows.execute("SELECT count(*) FROM t").fetchone()[0]

        with pytest.raises(RuntimeError):
            with rows:
                rows.execute("INSERT INTO t VALUES (?, ?, ?)", (99_999, "new", 1))
                raise RuntimeError("abandon")

        assert rows.execute("SELECT count(*) FROM t").fetchone()[0] == before

    def test_it_does_not_close_the_connection(self, rows: sqlite3.Connection) -> None:
        with rows:
            pass

        assert rows.execute("SELECT 1").fetchone() == (1,)


class TestAdaptersAndConverters:
    """One dict entry each; the callables then run per value."""

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
            connection.execute("CREATE TABLE places (location point)")
            connection.execute("INSERT INTO places VALUES (?)", (Point(1.0, 2.0),))

            restored = connection.execute("SELECT location FROM places").fetchone()[0]

            assert (restored.x, restored.y) == (1.0, 2.0)
        finally:
            connection.close()
            sqlite3.adapters.pop((Point, sqlite3.PrepareProtocol), None)
            sqlite3.converters.pop("POINT", None)

    def test_the_registries_are_plain_dicts(self) -> None:
        assert isinstance(sqlite3.adapters, dict)
        assert isinstance(sqlite3.converters, dict)

    def test_the_dbapi_constructors_are_datetime_classes(self) -> None:
        import datetime

        assert sqlite3.Date is datetime.date
        assert sqlite3.Timestamp is datetime.datetime  # type: ignore[attr-defined]
        assert sqlite3.DateFromTicks(0).year == datetime.date.fromtimestamp(0).year


class TestErrors:
    """The DB-API hierarchy, and the result code carried on the exception."""

    def test_the_hierarchy(self) -> None:
        assert issubclass(sqlite3.IntegrityError, sqlite3.DatabaseError)
        assert issubclass(sqlite3.DatabaseError, sqlite3.Error)
        assert issubclass(sqlite3.InterfaceError, sqlite3.Error)
        assert issubclass(sqlite3.Error, Exception)

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
        assert isinstance(sqlite3.sqlite_version, str)
        assert sqlite3.sqlite_version_info == tuple(
            int(part) for part in sqlite3.sqlite_version.split(".")
        )

    def test_complete_statement_wants_the_semicolon(self) -> None:
        assert sqlite3.complete_statement("SELECT 1;") is True
        assert sqlite3.complete_statement("SELECT 1") is False

    def test_the_parse_flags_are_distinct_bits(self) -> None:
        assert sqlite3.PARSE_DECLTYPES != sqlite3.PARSE_COLNAMES
        assert sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES != sqlite3.PARSE_DECLTYPES


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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=180,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, and every one of them uses `:memory:` so the suite
    leaves no database files behind."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_no_block_opens_a_database_on_disk(self) -> None:
        for line, source in _blocks():
            if "connect(" in source:
                assert "':memory:'" in source, f"{PAGE.name}:{line} connects to a file"

    def test_every_block_runs(self, tmp_path: Any) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: Any) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import sqlite3\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
