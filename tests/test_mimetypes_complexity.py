"""Tests for docs/stdlib/mimetypes.md.

The page prices a guess by the name passed in rather than the database, a
reverse lookup by the extensions registered for one type, and building a
database by the built-in tables plus the files read. Those are settled by
observation wherever a counter can reach the work: dictionaries that count
their lookups, extension strings that count their comparisons, a counting
`add_type`, a recording `read`, and traced allocation. A stopwatch settles only
the guess's growth with the length of the name.

Measurement scope:

* A guess makes the same small, non-zero number of table lookups against the
  built-in database and one with 100,000 extra extensions: counting
  dictionaries record at most eight lookups either way. `guess_file_type()`
  and `guess_type()` on a 1,000,000-character path peak over 500 KB of traced
  allocation, and a timing test asserts that path costs more than 5x a
  1,000-character one. The path is a single long directory
  name with one extension; the number of dots and slashes is not varied.
* `guess_all_extensions()` returns a new list, not the stored one, and
  `guess_extension()` builds that list to take its first entry; with 100,000
  extensions registered to one type, one call to either peaks over 400 KB. With `strict=False`, a str subclass that counts `__eq__`
  records at least `e_strict * e_non_standard` comparisons for 50 and 200
  distinct extensions on each side, and none with `strict=True`.
* `add_type()` compares an extension not yet registered for its type against
  every one that is: the counting subclass records exactly `e` comparisons
  for e = 10 and 1,000. Re-pointing an extension and the strict
  and non-standard tables are asserted by guesses. On 3.14+ an undotted
  extension is asserted to emit `DeprecationWarning`.
* `MimeTypes()` calls `add_type()` once per built-in entry (asserted to be
  between 100 and 400; 150 on 3.10), counted against the sizes of a fresh
  instance's two tables, then once per extension in the files passed to it.
  `init()` does the same, plus once per extension in every existing
  `knownfiles` entry: a counting `add_type` records exactly the built-in count
  plus 2,000 for a 1,000-line file of two extensions a line. A recording
  `MimeTypes.read` shows `init()` skipping a missing `knownfiles` entry, and
  `init(files)` on an existing database reading only `files`.
  `read_mime_types()` on an initialized module makes the built-in count plus
  one `add_type()` call for a one-entry file.
* The first call to a module function, or to `MimeTypes()`, runs `init()`
  exactly once, observed with `init` replaced by a counting wrapper and the
  module reset to uninitialized. `init()` drops an `add_type()` entry;
  `types_map` after `init()` is the dictionary the module's guesses read, and a
  later `init()` rebinds the name.
* `MimeTypes()` does not copy the module database: a type added to the
  module, and one read from a `knownfiles` entry, are both absent from a new
  instance. `read_mime_types()` returns a table holding the built-in `.pdf`
  and the file's entry, leaves the module database without the file's
  entry, and returns `None` for a missing file.
* `readfp()` is handed an object with only `readline()`, counted: it is called
  once per line and once more at the end. Comments and blank lines add
  nothing.
* On Linux, `read_windows_registry()` adds nothing to either table.
* The 3.11+ query-string behaviour and the 3.13+ `guess_file_type()` are
  guarded on `sys.version_info`, both sides of the 3.11 boundary asserted.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `read_windows_registry()` and the registry term of `init()` on Windows,
  O(r) in the keys under `HKEY_CLASSES_ROOT`, are read from Lib/mimetypes.py
  and Modules/_winapi.c's `_mimetypes_read_windows_registry`, which enumerate
  every key. No run this project performs is on Windows, so the test that the
  method adds nothing is skipped there rather than inverted.
* The characters term of `f`: the counts above show one `add_type()` per
  extension read, and that `readfp()` reads one line per `readline()`; that
  splitting a line is linear in its characters is read from Lib/mimetypes.py,
  and long comment lines are not measured.
* Treating a MIME type or one extension as O(1) to hash, lower and compare is
  a cost-model assumption. `add_type()`'s O(e) scan and `read()`'s O(1) price
  per registration are consistent only because real types carry a handful of
  extensions; a file listing thousands under one type is not measured.
* That passing a path to `guess_type()` is soft deprecated from 3.13 is a
  documentation status in the official `mimetypes` docs, with no warning to
  observe. That `guess_file_type()` skips the URL parse is observed with a
  counting `urllib.parse.urlparse` on 3.13+, where `guess_type()` calls it.
* Which answers the module functions give depends on the machine's
  `mime.types` files. Tests of results use a `MimeTypes` instance or entries
  written by the test itself, and assert absence only for made-up extensions
  such as `.pydemo` that no `mime.types` file is expected to carry.
"""

from __future__ import annotations

import io
import mimetypes
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "mimetypes.md"
EXPECTED_BLOCKS = 7

MODULE_STATE = (
    "_db",
    "inited",
    "knownfiles",
    "types_map",
    "common_types",
    "encodings_map",
    "suffix_map",
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


def built_in_entries() -> int:
    """b: the entries a fresh `MimeTypes` registers from the built-in tables."""
    fresh = mimetypes.MimeTypes()
    return len(fresh.types_map[True]) + len(fresh.types_map[False])


class CountingEq(str):
    """An extension that counts how often it is compared for equality."""

    comparisons = 0

    def __eq__(self, other: object) -> bool:
        CountingEq.comparisons += 1
        return str.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    __hash__ = str.__hash__


class CountingDict(dict[str, Any]):
    """A dictionary that counts membership tests and item reads."""

    lookups = 0

    def __contains__(self, key: object) -> bool:
        CountingDict.lookups += 1
        return super().__contains__(key)

    def __getitem__(self, key: str) -> Any:
        CountingDict.lookups += 1
        return super().__getitem__(key)


@pytest.fixture
def module_state() -> Iterator[None]:
    """Save the module database, hand the test a fresh one, and restore the saved one."""
    saved = {name: getattr(mimetypes, name) for name in MODULE_STATE}
    try:
        mimetypes.init()  # a fresh database, so the saved one is never mutated
        yield
    finally:
        for name, value in saved.items():
            setattr(mimetypes, name, value)


def write_types(path: pathlib.Path, lines: int, prefix: str) -> pathlib.Path:
    """A mime.types file of `lines` types with two extensions each."""
    path.write_text(
        "".join(f"application/x-{prefix}{i} {prefix}a{i} {prefix}b{i}\n" for i in range(lines)),
        encoding="utf-8",
    )
    return path


class TestAGuessFollowsTheName:
    """`guess_type` and `guess_file_type` | O(p) | O(p): a guess walks the name
    once and makes a fixed number of table lookups, whatever the table holds."""

    @staticmethod
    def lookups_for(db: mimetypes.MimeTypes, name: str) -> int:
        db.types_map = (CountingDict(db.types_map[0]), CountingDict(db.types_map[1]))
        db.encodings_map = CountingDict(db.encodings_map)
        db.suffix_map = CountingDict(db.suffix_map)
        CountingDict.lookups = 0
        db.guess_type(name, strict=False)
        return CountingDict.lookups

    def test_lookups_do_not_grow_with_the_database(self) -> None:
        small = mimetypes.MimeTypes()
        large = mimetypes.MimeTypes()
        for index in range(100_000):
            large.add_type(f"application/x-bulk{index}", f".bulk{index}")

        counts = [self.lookups_for(db, "archive.tar.gz") for db in (small, large)]

        assert 0 < counts[0] == counts[1] <= 8, f"lookups per guess: {counts}"

    @pytest.mark.parametrize("method", ["guess_type", "guess_file_type"])
    def test_a_long_name_allocates_with_its_length(self, method: str) -> None:
        if method == "guess_file_type" and sys.version_info < (3, 13):
            pytest.skip("guess_file_type is 3.13+")
        guess = getattr(mimetypes.MimeTypes(), method)
        path = "/" + "d" * 1_000_000 + "/report.pdf"

        assert guess(path) == ("application/pdf", None)
        peak = peak_bytes(lambda: guess(path))

        assert peak > 500_000, f"{method} on a 1 MB path peaked at {peak} bytes"

    @pytest.mark.timing
    @pytest.mark.parametrize("method", ["guess_type", "guess_file_type"])
    def test_a_long_name_takes_longer(self, method: str) -> None:
        if method == "guess_file_type" and sys.version_info < (3, 13):
            pytest.skip("guess_file_type is 3.13+")
        guess = getattr(mimetypes.MimeTypes(), method)
        short = "/" + "d" * 1_000 + "/report.pdf"
        long = "/" + "d" * 1_000_000 + "/report.pdf"

        durations = [best_ns(lambda p=p: guess(p), inner=5) for p in (short, long)]  # type: ignore[misc]
        ratio = durations[1] / durations[0]

        assert ratio > 5, f"{method}: 1,000x the path took {durations} ns, x{ratio:.1f}"

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="guess_file_type is 3.13+")
    def test_guess_file_type_skips_the_url_parse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.parse

        parses: list[str] = []
        original = urllib.parse.urlparse

        def counting(url: Any, *args: Any, **kwargs: Any) -> Any:
            parses.append(url)
            return original(url, *args, **kwargs)

        monkeypatch.setattr(urllib.parse, "urlparse", counting)
        db = mimetypes.MimeTypes()

        assert db.guess_file_type("dir/report.pdf") == ("application/pdf", None)  # type: ignore[attr-defined]
        assert parses == []
        assert db.guess_type("dir/report.pdf") == ("application/pdf", None)
        assert parses == ["dir/report.pdf"]

    def test_encoding_and_suffix_map(self) -> None:
        db = mimetypes.MimeTypes()

        assert db.guess_type("backup.tar.gz") == ("application/x-tar", "gzip")
        assert db.guess_type("backup.tgz") == ("application/x-tar", "gzip")
        assert db.guess_type("README") == (None, None)

    def test_a_data_url_carries_its_own_type(self) -> None:
        assert mimetypes.MimeTypes().guess_type("data:text/csv;base64,YSxi") == ("text/csv", None)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="urlparse from 3.11")
    def test_a_query_string_is_not_part_of_the_extension(self) -> None:
        db = mimetypes.MimeTypes()

        assert db.guess_type("https://example.com/logo.png?v=2") == ("image/png", None)
        assert db.guess_type("https://example.com/logo.png#top") == ("image/png", None)

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 keeps the query")
    def test_before_311_the_query_string_defeats_the_guess(self) -> None:
        db = mimetypes.MimeTypes()

        assert db.guess_type("https://example.com/logo.png?v=2") == (None, None)


class TestReverseLookupCopiesTheList:
    """`guess_all_extensions` and `guess_extension` | O(e) | O(e), and O(e²)
    time with `strict=False`."""

    def test_the_returned_list_is_a_copy(self) -> None:
        db = mimetypes.MimeTypes()
        stored = db.types_map_inv[True]["image/jpeg"]

        returned = db.guess_all_extensions("image/jpeg")

        assert returned == stored
        assert returned is not stored

    @pytest.mark.parametrize("method", ["guess_all_extensions", "guess_extension"])
    def test_one_call_allocates_the_whole_list(self, method: str) -> None:
        db = mimetypes.MimeTypes()
        # Filled directly: 100,000 add_type calls on one type would scan quadratically.
        extensions = [f".m{i}" for i in range(100_000)]
        # typeshed types the inverse map's values as str; they are lists.
        db.types_map_inv[True]["application/x-many"] = extensions  # type: ignore[assignment]
        call = getattr(db, method)

        expected = ".m0" if method == "guess_extension" else extensions
        assert call("application/x-many") == expected
        peak = peak_bytes(lambda: call("application/x-many"))

        assert peak > 400_000, f"{method} over 100,000 extensions peaked at {peak} bytes"

    def test_the_first_registered_extension_wins(self) -> None:
        db = mimetypes.MimeTypes()
        db.add_type("application/x-order", ".first")
        db.add_type("application/x-order", ".second")

        assert db.guess_extension("application/x-order") == ".first"
        assert db.guess_extension("application/x-unknown") is None

    def test_strict_extensions_come_before_non_standard_ones(self) -> None:
        db = mimetypes.MimeTypes()
        db.add_type("application/x-mixed", ".loose", strict=False)
        db.add_type("application/x-mixed", ".strict")

        assert db.guess_all_extensions("application/x-mixed", strict=False) == [".strict", ".loose"]
        assert db.guess_extension("application/x-mixed", strict=False) == ".strict"

    @pytest.mark.parametrize("width", [50, 200])
    def test_non_strict_merging_scans_the_strict_list(self, width: int) -> None:
        db = mimetypes.MimeTypes()
        for index in range(width):
            db.add_type("application/x-merge", CountingEq(f".s{index}"))
            db.add_type("application/x-merge", CountingEq(f".n{index}"), strict=False)

        CountingEq.comparisons = 0
        strict = db.guess_all_extensions("application/x-merge")
        strict_comparisons = CountingEq.comparisons
        CountingEq.comparisons = 0
        merged = db.guess_all_extensions("application/x-merge", strict=False)

        assert len(strict) == width
        assert strict_comparisons == 0
        assert len(merged) == 2 * width
        assert CountingEq.comparisons >= width * width, (
            f"{width} + {width} extensions: {CountingEq.comparisons} comparisons"
        )


class TestAddTypeScansTheTypesList:
    """`add_type` | O(e) | O(1): the new extension is compared with every
    extension already registered for the type."""

    @pytest.mark.parametrize("existing", [10, 1_000])
    def test_it_compares_once_per_registered_extension(self, existing: int) -> None:
        db = mimetypes.MimeTypes()
        for index in range(existing):
            db.add_type("application/x-scan", CountingEq(f".e{index}"))

        CountingEq.comparisons = 0
        db.add_type("application/x-scan", CountingEq(".new"))

        assert CountingEq.comparisons == existing

    def test_a_known_extension_is_re_pointed(self) -> None:
        db = mimetypes.MimeTypes()
        db.add_type("application/x-notes", ".notes", strict=False)

        assert db.guess_type("a.notes") == (None, None)
        assert db.guess_type("a.notes", strict=False) == ("application/x-notes", None)

        db.add_type("application/x-notes-v2", ".notes", strict=False)

        assert db.guess_type("a.notes", strict=False) == ("application/x-notes-v2", None)

    def test_the_pairs_are_non_standard_first(self) -> None:
        db = mimetypes.MimeTypes()
        db.add_type("application/x-loose", ".loose", strict=False)

        assert db.types_map[0][".loose"] == "application/x-loose"
        assert ".loose" not in db.types_map[1]
        assert db.types_map_inv[0]["application/x-loose"] == [".loose"]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="deprecated in 3.14")
    def test_an_undotted_extension_is_deprecated(self) -> None:
        with pytest.warns(DeprecationWarning, match="[Uu]ndotted"):
            mimetypes.MimeTypes().add_type("application/x-bare", "bare")

    def test_a_dotted_extension_does_not_warn(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            mimetypes.MimeTypes().add_type("application/x-dotted", ".dotted")


class TestBuildingADatabase:
    """`MimeTypes()`, `init()` and `read_mime_types()` | O(b + f): one
    `add_type` per built-in entry, then one per extension read."""

    @staticmethod
    def count_add_type(monkeypatch: pytest.MonkeyPatch) -> list[int]:
        calls = [0]
        original = mimetypes.MimeTypes.add_type

        def counting(self: mimetypes.MimeTypes, *args: Any, **kwargs: Any) -> None:
            calls[0] += 1
            original(self, *args, **kwargs)

        monkeypatch.setattr(mimetypes.MimeTypes, "add_type", counting)
        return calls

    def test_the_built_in_tables_are_a_couple_of_hundred_entries(self) -> None:
        assert 100 < built_in_entries() < 400

    def test_an_instance_registers_every_built_in_entry(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        b = built_in_entries()
        extra = write_types(tmp_path / "extra.types", 50, "inst")
        calls = self.count_add_type(monkeypatch)

        mimetypes.MimeTypes()
        plain = calls[0]
        calls[0] = 0
        mimetypes.MimeTypes([str(extra)])

        assert plain == b
        assert calls[0] == b + 100

    def test_init_registers_the_built_ins_and_every_known_file(
        self, module_state: None, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        b = built_in_entries()
        known = write_types(tmp_path / "known.types", 1_000, "known")
        mimetypes.knownfiles = [str(known)]
        # On Windows init() also registers the registry's entries.
        monkeypatch.setattr(mimetypes.MimeTypes, "read_windows_registry", lambda self: None)
        calls = self.count_add_type(monkeypatch)

        mimetypes.init()

        assert calls[0] == b + 2_000
        assert mimetypes.guess_type("x.knowna7") == ("application/x-known7", None)

    def test_init_skips_a_missing_file_and_later_reads_only_the_given_ones(
        self, module_state: None, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        known = write_types(tmp_path / "known.types", 1, "k")
        given = write_types(tmp_path / "given.types", 1, "g")
        mimetypes.knownfiles = [str(tmp_path / "missing.types"), str(known)]
        reads: list[str] = []
        original = mimetypes.MimeTypes.read

        def recording(self: mimetypes.MimeTypes, filename: str, strict: bool = True) -> None:
            reads.append(filename)
            original(self, filename, strict)

        monkeypatch.setattr(mimetypes.MimeTypes, "read", recording)

        mimetypes.init()
        assert reads == [str(known)]

        reads.clear()
        mimetypes.init([str(given)])
        assert reads == [str(given)]
        assert mimetypes.guess_type("x.ka0") == ("application/x-k0", None)
        assert mimetypes.guess_type("x.ga0") == ("application/x-g0", None)

    def test_an_instance_does_not_copy_the_module_database(
        self, module_state: None, tmp_path: pathlib.Path
    ) -> None:
        mimetypes.knownfiles = [str(write_types(tmp_path / "known.types", 1, "sys"))]
        mimetypes.init()
        mimetypes.add_type("application/x-module-only", ".modonly")

        db = mimetypes.MimeTypes()

        assert mimetypes.guess_type("x.sysa0") == ("application/x-sys0", None)
        assert db.guess_type("x.sysa0") == (None, None)
        assert db.guess_type("x.modonly") == (None, None)

    def test_instance_tables_are_its_own(self) -> None:
        first = mimetypes.MimeTypes()
        first.encodings_map[".zz"] = "zz"
        first.suffix_map[".tzz"] = ".tar.zz"

        second = mimetypes.MimeTypes()

        assert ".zz" not in second.encodings_map
        assert ".tzz" not in second.suffix_map
        assert first.guess_type("a.tzz") == ("application/x-tar", "zz")

    def test_read_mime_types_returns_the_built_ins_too(
        self, module_state: None, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        b = built_in_entries()
        path = tmp_path / "example.types"
        path.write_text("application/x-example  pyexample\n", encoding="utf-8")

        calls = self.count_add_type(monkeypatch)

        table = mimetypes.read_mime_types(str(path))

        assert calls[0] == b + 1
        assert table is not None
        assert table[".pyexample"] == "application/x-example"
        assert table[".pdf"] == "application/pdf"
        assert len(table) == len(mimetypes.MimeTypes().types_map[True]) + 1
        assert mimetypes.guess_type("file.pyexample") == (None, None)
        assert mimetypes.read_mime_types(str(tmp_path / "missing.types")) is None

    def test_readfp_reads_a_line_at_a_time(self) -> None:
        lines = ["# comment\n", "\n", "application/x-a  aa ab\n", "application/x-b bb # tail\n"]

        class LinesOnly:
            calls = 0

            def readline(self) -> str:
                LinesOnly.calls += 1
                return lines.pop(0) if lines else ""

        db = mimetypes.MimeTypes()
        before = len(db.types_map[True])

        db.readfp(LinesOnly())  # type: ignore[arg-type]

        assert LinesOnly.calls == 5
        assert len(db.types_map[True]) == before + 3
        assert db.guess_all_extensions("application/x-a") == [".aa", ".ab"]
        assert db.guess_all_extensions("application/x-b") == [".bb"]

    def test_readfp_strict_false_fills_the_non_standard_table(self) -> None:
        db = mimetypes.MimeTypes()

        db.readfp(io.StringIO("application/x-loose  lse\n"), strict=False)

        assert db.guess_type("a.lse") == (None, None)
        assert db.guess_type("a.lse", strict=False) == ("application/x-loose", None)

    @pytest.mark.skipif(sys.platform == "win32", reason="reads the real registry on Windows")
    def test_the_registry_reader_adds_nothing_off_windows(self) -> None:
        db = mimetypes.MimeTypes()
        sizes = (len(db.types_map[0]), len(db.types_map[1]))

        db.read_windows_registry()

        assert (len(db.types_map[0]), len(db.types_map[1])) == sizes


class TestTheModuleDatabase:
    """The first call builds the database; `init()` rebuilds it, and the
    module's tables are the database's own dictionaries."""

    @pytest.fixture(autouse=True)
    def _restore(self, module_state: None) -> None:
        return None

    @staticmethod
    def reset_and_count_init(monkeypatch: pytest.MonkeyPatch) -> list[int]:
        calls = [0]
        original = mimetypes.init

        def counting(files: Any = None) -> None:
            calls[0] += 1
            original(files)

        monkeypatch.setattr(mimetypes, "_db", None)
        monkeypatch.setattr(mimetypes, "inited", False)
        monkeypatch.setattr(mimetypes, "init", counting)
        return calls

    @pytest.mark.parametrize(
        "first_call",
        [
            lambda: mimetypes.guess_type("a.pdf"),
            lambda: mimetypes.guess_extension("application/pdf"),
            lambda: mimetypes.guess_all_extensions("application/pdf"),
            lambda: mimetypes.add_type("application/x-first", ".first"),
            mimetypes.MimeTypes,
        ],
        ids=["guess_type", "guess_extension", "guess_all_extensions", "add_type", "MimeTypes"],
    )
    def test_the_first_call_runs_init_once(
        self, monkeypatch: pytest.MonkeyPatch, first_call: Callable[[], Any]
    ) -> None:
        calls = self.reset_and_count_init(monkeypatch)

        first_call()

        assert calls == [1]
        assert mimetypes.inited is True

        mimetypes.guess_type("b.pdf")

        assert calls == [1]

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="guess_file_type is 3.13+")
    def test_guess_file_type_runs_init_too(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self.reset_and_count_init(monkeypatch)

        mimetypes.guess_file_type("a.pdf")  # type: ignore[attr-defined]

        assert calls == [1]

    def test_init_drops_add_type_entries(self) -> None:
        mimetypes.add_type("application/x-pydemo", ".pydemo")
        assert mimetypes.guess_type("file.pydemo") == ("application/x-pydemo", None)

        mimetypes.init()

        assert mimetypes.guess_type("file.pydemo") == (None, None)

    def test_the_module_tables_are_the_live_ones(self) -> None:
        mimetypes.init()
        before = mimetypes.types_map

        mimetypes.types_map[".livezz"] = "application/x-live"
        mimetypes.encodings_map[".zq"] = "zq"

        assert mimetypes.guess_type("a.livezz.zq") == ("application/x-live", "zq")

        mimetypes.init()

        assert mimetypes.types_map is not before
        assert mimetypes.guess_type("a.livezz") == (None, None)

    def test_the_module_data_names(self) -> None:
        assert isinstance(mimetypes.knownfiles, list)
        assert "/etc/mime.types" in mimetypes.knownfiles
        mimetypes.init()
        assert mimetypes.inited is True
        assert mimetypes.suffix_map[".tgz"] == ".tar.gz"
        assert mimetypes.encodings_map[".gz"] == "gzip"
        assert isinstance(mimetypes.common_types, dict)


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
    """Each block runs in its own subprocess, so the module database one block
    registers into or rebuilds cannot leak into the next, and asserts its own
    result."""

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
        target = "assert mimetypes.guess_type('file.pydemo') == (None, None)"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert mimetypes.guess_type('file.pydemo')[0]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
