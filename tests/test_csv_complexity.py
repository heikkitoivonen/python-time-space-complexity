"""Tests to verify documented behaviour of the csv module.

docs/stdlib/csv.md describes row-at-a-time processing. Readers retain parsed
fields, and writers build a whole formatted row before handing it to the sink:

* `writerow()` builds the entire formatted line as one string before writing
  it, so its space is O(k). Traced peak tracks the output almost
  exactly: 1,100,050 bytes for a line of 1,100,001 characters, on 3.10 and 3.14
  alike.
* `writerows()` is that in a loop. Two hundred rows of 11,000 characters peak at
  11,098 bytes - the widest row, so its space is O(k).
* `Sniffer.sniff()` is O(s) in space as well as time. Its peak rises 36 KB, 105
  KB, 411 KB for samples of 1.2 KB, 14.7 KB and 86.7 KB.

Laziness is checked by allocation rather than by timing, which needs no
tolerance: over 100,000 lines, building a reader peaks at 248-704 bytes, one
`next()` at about 17 KB, and `list(reader)` at 24-26 MB. `DictReader` is lazy
in the same way - 568 bytes to construct, because the header is not read until
`.fieldnames` is touched.

Both `Sniffer` methods are linear in the sample: x9.5 to x10.7 per 10x on 3.10
and 3.14. `has_header()` tracks `sniff()` because it calls it first and only
then types twenty rows.

Dictionary dimensions are tested independently:

* Header access, writeheader and dictionary writerow hold the field count at
  two while each string grows from 1,000 to 100,000 characters. Time grows
  92-101x on Python 3.10 and 3.14; allocation grows 38-92x. Parsing uses
  a fresh reader each time; writers reuse their buffer after a warm-up. Input
  strings and the sink are prepared outside the measurements. The sink does
  not retain output, so its storage cannot explain the allocation growth.
* Ragged rows hold the input at one field while the header grows from 10 to
  10,000 fixed-length names. Every missing name gets the same restval object;
  the returned dictionary and its allocation grow with header width. Header
  creation and initial key hashing are outside the per-row measurement.

These cases use ASCII strings, unique field names, the default dialect, and
successful rows without surplus dictionary keys. They do not vary custom
conversion costs, key hashing/comparison costs, or error-message lengths.
The O(m + k) and O(m + h) upper bounds follow Lib/csv.py's projection and
missing-field loops plus Modules/_csv.c's per-character parsing/rendering:
https://github.com/python/cpython/blob/3.10/Lib/csv.py
https://github.com/python/cpython/blob/3.14/Lib/csv.py
https://github.com/python/cpython/blob/3.14/Modules/_csv.c

Not settled here:

* Treating field-name hashing and comparison as O(1) is a cost-model assumption
  for data rows; arbitrary key costs are outside those bounds.
* Whether `sniff()` stays linear on adversarial input. It runs regex
  alternations over the whole sample, and only well-formed delimited text was
  measured.
* The `QUOTE_NOTNULL` and `QUOTE_STRINGS` rows on 3.10 and 3.11, where the
  constants do not exist. Their row is version-marked and the coverage check
  allows them to be absent.
* `csv.StringIO` is `io.StringIO` imported into the module's namespace, not part
  of its API, so the page does not give it a row.

Axes not varied: non-UTF-8 encodings, embedded newlines inside quoted fields
beyond one round trip, and dialects built by subclassing `Dialect` rather than
by keyword.
"""

import csv
import inspect
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from functools import partial
from itertools import repeat
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "csv.md"

EXPECTED_BLOCKS = 12

# Documented, but absent before 3.12. Each must carry a version marker.
ADDED_IN_312 = {"QUOTE_NOTNULL", "QUOTE_STRINGS"}

# In csv's namespace but not csv's: io.StringIO, imported for Sniffer's use.
REEXPORTS = {"StringIO"}


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
    """Everything public in `csv` that `csv` itself defines."""
    return {
        name
        for name in dir(csv)
        if not name.startswith("_") and not inspect.ismodule(getattr(csv, name))
    }


def _documented_names() -> set[str]:
    """Every `csv.<name>` the Complexity Reference table mentions."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("| Operation | Time | Space | Notes |")
    end = text.index("\n## Reading CSV Files", start)
    return set(re.findall(r"csv\.([A-Za-z_][A-Za-z0-9_]*)", text[start:end]))


class TestEveryPublicNameIsDocumented:
    """The table has to name every public attribute of `csv`.

    `dir()` rather than `__all__`, because `csv.__all__` carried `__doc__` and
    `__version__` until 3.12 and so is not a usable list of the API.
    """

    def test_no_public_name_is_missing_from_the_table(self) -> None:
        missing = sorted(_public_names() - _documented_names() - REEXPORTS)

        assert not missing, f"{len(missing)} public names absent from the table: {missing}"

    def test_the_table_names_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        unknown = sorted(_documented_names() - _public_names() - ADDED_IN_312)

        assert not unknown, f"the table names attributes csv does not have: {unknown}"

    def test_the_later_constants_carry_a_version_marker(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        for name in sorted(ADDED_IN_312):
            owning = [row for row in rows if f"csv.{name}" in row]
            assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
            assert "3.12" in owning[0], f"the {name} row should say 3.12+: {owning[0]}"

    def test_the_reexport_is_not_given_a_row(self) -> None:
        """io.StringIO is in csv's namespace but is not csv's to document."""
        assert REEXPORTS <= _public_names()
        assert not (REEXPORTS & _documented_names())

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        public = _public_names()

        assert 19 <= len(public) <= 24, (
            f"csv has {len(public)} public names; re-run the coverage audit"
        )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"reader", "writer", "DictReader", "Sniffer", "QUOTE_ALL"} <= documented
        thinned = documented - {"field_size_limit"}
        assert _public_names() - thinned - REEXPORTS == {"field_size_limit"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestReadingIsLazy:
    """`csv.reader` | O(1) | O(1) to build, then O(k) per row.

    Measured by traced allocation, so the three states separate by four orders
    of magnitude with no tolerance to choose.
    """

    LINES = [f"a{index},b{index},c{index}" for index in range(100_000)]

    def test_building_a_reader_reads_nothing(self) -> None:
        peak = peak_bytes(lambda: csv.reader(iter(self.LINES)))

        assert peak < 5_000, f"csv.reader() allocated {peak} bytes over 100,000 lines"

    def test_one_step_holds_one_row(self) -> None:
        reader = csv.reader(iter(self.LINES))

        peak = peak_bytes(lambda: next(reader))

        assert peak < 100_000, f"one next() allocated {peak} bytes"

    def test_listing_it_holds_the_whole_file(self) -> None:
        """The one operation on this page that is O(n·k) in memory."""
        peak = peak_bytes(lambda: list(csv.reader(iter(self.LINES))))

        assert peak > 5_000_000, f"list(reader) allocated only {peak} bytes"

    def test_a_reader_accepts_any_iterable_of_strings(self) -> None:
        assert list(csv.reader(["a,b", "c,d"])) == [["a", "b"], ["c", "d"]]

    def test_quoting_and_embedded_delimiters_survive(self) -> None:
        assert list(csv.reader(['"a,b",c'])) == [["a,b", "c"]]
        assert list(csv.reader(['"line1\nline2",c'])) == [["line1\nline2", "c"]]


class TestWritingHoldsOneRow:
    """`writerow` | O(k) | O(k), and `writerows` | O(n·k) | O(k).

    The row is rendered whole before it is written, which is where the space
    goes; the batch form repeats that and never holds more than one line.
    """

    class Sink:
        """A file-like object that keeps only the last line written."""

        last: str = ""

        def write(self, text: str) -> int:
            self.last = text
            return len(text)

    def test_the_peak_tracks_the_row_not_the_call(self) -> None:
        peaks: dict[int, int] = {}
        for fields in (10, 1_000, 100_000):
            sink = self.Sink()
            writer = csv.writer(sink)
            row = ["v" * 10] * fields
            writer.writerow(row)  # warm
            peaks[fields] = peak_bytes(lambda w=writer, r=row: w.writerow(r))  # type: ignore[misc]

        assert peaks[100_000] > peaks[1_000] > peaks[10]
        assert peaks[100_000] > 500_000, f"a 1.1 MB line peaked at {peaks[100_000]} bytes"

    def test_writerows_peaks_at_the_widest_row_not_the_batch(self) -> None:
        sink = self.Sink()
        writer = csv.writer(sink)
        rows = [["v" * 10] * 1_000 for _ in range(200)]
        writer.writerows(rows)  # warm

        peak = peak_bytes(lambda: writer.writerows(rows))

        one_row = len(sink.last)
        assert peak < one_row * 4, f"writerows peaked at {peak} for a {one_row}-char row"

    def test_writerows_writes_every_row(self) -> None:
        buffer = io.StringIO()

        csv.writer(buffer).writerows([["a", "b"], ["c", "d"]])

        assert buffer.getvalue() == "a,b\r\nc,d\r\n"


class TestFieldSizeLimit:
    """`field_size_limit([new_limit])`: returns the previous value, and a field
    longer than it raises rather than allocating."""

    @pytest.fixture(autouse=True)
    def _restore_limit(self) -> Iterator[None]:
        original = csv.field_size_limit()
        yield
        csv.field_size_limit(original)

    def test_an_oversized_field_raises(self) -> None:
        oversized = "x" * (csv.field_size_limit() + 1)

        with pytest.raises(csv.Error, match="field limit"):
            list(csv.reader([oversized]))

    def test_raising_the_limit_lets_it_through(self) -> None:
        limit = csv.field_size_limit()
        oversized = "x" * (limit + 1)

        csv.field_size_limit(limit * 4)

        assert len(next(csv.reader([oversized]))[0]) == limit + 1

    def test_setting_it_returns_what_it_was(self) -> None:
        original = csv.field_size_limit()

        previous = csv.field_size_limit(original * 2)

        assert previous == original
        assert csv.field_size_limit() == original * 2


class TestDictReaderIsLazyToo:
    """`DictReader(f)` | O(1) | O(1); the header arrives with `.fieldnames`."""

    DATA = "name,age,city\n" + "".join(f"a{index},{index},c{index}\n" for index in range(50_000))

    def test_construction_reads_no_header(self) -> None:
        stream = io.StringIO(self.DATA)

        reader = csv.DictReader(stream)

        # type: ignore below - the private attribute is where the laziness shows
        assert reader._fieldnames is None  # type: ignore[attr-defined]  # noqa: SLF001

    def test_construction_allocates_nothing_for_the_file(self) -> None:
        # The stream is built outside the measurement; wrapping it is what is timed.
        stream = io.StringIO(self.DATA)

        peak = peak_bytes(lambda: csv.DictReader(stream))

        assert peak < 5_000, f"DictReader() allocated {peak} bytes over 50,000 rows"
        assert stream.tell() == 0, "the header was read at construction"

    def test_touching_fieldnames_reads_exactly_one_row(self) -> None:
        reader = csv.DictReader(io.StringIO(self.DATA))

        assert reader.fieldnames == ["name", "age", "city"]
        assert next(reader)["name"] == "a0"

    def test_fieldnames_is_read_once(self) -> None:
        reader = csv.DictReader(io.StringIO(self.DATA))
        first = reader.fieldnames

        assert reader.fieldnames is first

    def test_a_surplus_field_goes_to_restkey(self) -> None:
        reader = csv.DictReader(io.StringIO("a,b\n1,2,3\n4\n"), restkey="extra", restval="?")

        assert list(reader) == [
            {"a": "1", "b": "2", "extra": ["3"]},
            {"a": "4", "b": "?"},
        ]

    def test_short_rows_grow_with_header_width(self) -> None:
        peaks = []
        missing = object()
        for width in (10, 10_000):
            fields = [f"f{index:05d}" for index in range(width)]
            reader = csv.DictReader(repeat("x\n"), fieldnames=fields, restval=missing)
            next(reader)  # populate field-name hashes outside the measurement
            peaks.append(peak_bytes(partial(next, reader)))
            row = next(reader)

            assert len(row) == width
            assert row[fields[0]] == "x"
            assert all(row[name] is missing for name in fields[1:])

        assert peaks[1] > peaks[0] * 20, f"fixed short row must allocate with header width: {peaks}"


class TestDictWriterProjectsOntoFieldnames:
    """`DictWriter`: O(m) to project a dict onto the field order, O(k) to
    render, and `extrasaction` decides what a surplus key costs."""

    def test_writeheader_and_writerow(self) -> None:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["Name", "Age"])

        writer.writeheader()
        writer.writerow({"Name": "Alice", "Age": 30})

        assert buffer.getvalue() == "Name,Age\r\nAlice,30\r\n"

    def test_a_missing_field_takes_restval(self) -> None:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["a", "b"], restval="-")

        writer.writerow({"a": "1"})

        assert buffer.getvalue() == "1,-\r\n"

    def test_a_surplus_key_raises_by_default(self) -> None:
        writer = csv.DictWriter(io.StringIO(), fieldnames=["a"])

        with pytest.raises(ValueError, match="not in fieldnames"):
            writer.writerow({"a": 1, "z": 2})

    def test_extrasaction_ignore_drops_it(self) -> None:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["a"], extrasaction="ignore")

        writer.writerow({"a": 1, "z": 2})

        assert buffer.getvalue() == "1\r\n"


class TestDictionaryTextLengths:
    """Vary row/header characters independently of the two-field count."""

    class Sink:
        """Report the rendered length without retaining the output string."""

        def write(self, text: str) -> int:
            return len(text)

    @classmethod
    def operation(cls, name: str, size: int) -> Callable[[], Any]:
        value = "x" * size
        fields = [value + "a", value + "b"]
        if name == "fieldnames":
            line = ",".join(fields) + "\n"
            return lambda: csv.DictReader([line]).fieldnames
        if name == "writeheader":
            return csv.DictWriter(cls.Sink(), fields).writeheader
        writer = csv.DictWriter(cls.Sink(), ["a", "b"])
        return partial(writer.writerow, {"a": value, "b": value})

    @pytest.mark.parametrize("name", ["fieldnames", "writeheader", "writerow"])
    def test_text_length_controls_allocation_at_fixed_field_count(self, name: str) -> None:
        peaks = []
        for size in (1000, 100_000):
            operation = self.operation(name, size)
            result = operation()  # warm writer buffers before measuring output allocation
            if name == "fieldnames":
                assert result == ["x" * size + "a", "x" * size + "b"]
            else:
                assert result == 2 * size + (5 if name == "writeheader" else 3)
            peaks.append(peak_bytes(operation))

        assert peaks[1] > peaks[0] * 20, f"{name} must allocate with text length: {peaks}"

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["fieldnames", "writeheader", "writerow"])
    def test_text_length_controls_time_at_fixed_field_count(self, name: str) -> None:
        operations = [self.operation(name, size) for size in (1000, 100_000)]
        for operation in operations:
            operation()
        durations = [best_ns(operation, inner=5) for operation in operations]
        ratio = durations[1] / durations[0]

        assert ratio > 20, f"{name}: 100x text at two fields took {durations} ns, ratio={ratio:.2f}"


class TestDialects:
    """Registration is a dict entry; lookup is a dict lookup; the built-in
    three are always present."""

    @pytest.fixture(autouse=True)
    def _unregister(self) -> Iterator[None]:
        yield
        if "pipes" in csv.list_dialects():
            csv.unregister_dialect("pipes")

    def test_registering_and_looking_up(self) -> None:
        csv.register_dialect("pipes", delimiter="|")

        assert "pipes" in csv.list_dialects()
        assert csv.get_dialect("pipes").delimiter == "|"

    def test_unregistering_removes_it(self) -> None:
        csv.register_dialect("pipes", delimiter="|")

        csv.unregister_dialect("pipes")

        with pytest.raises(csv.Error, match="unknown dialect"):
            csv.get_dialect("pipes")

    def test_the_built_in_three_are_always_registered(self) -> None:
        assert set(csv.list_dialects()) == {"excel", "excel-tab", "unix"}
        assert csv.excel.delimiter == ","
        assert csv.excel_tab.delimiter == "\t"
        assert csv.unix_dialect.quoting == csv.QUOTE_ALL
        assert issubclass(csv.excel, csv.Dialect)

    def test_an_invalid_dialect_is_rejected_when_the_writer_is_built(self) -> None:
        with pytest.raises((csv.Error, TypeError)):
            csv.writer(io.StringIO(), delimiter="too long")


class TestQuotingFlagsChangeOutputNotCost:
    """The `QUOTE_*` constants pick what gets quoted; every strategy still
    walks the row once."""

    @staticmethod
    def render(quoting: Any) -> str:
        buffer = io.StringIO()
        csv.writer(buffer, quoting=quoting).writerow(["a b", 42])
        return buffer.getvalue().strip()

    def test_the_four_that_exist_everywhere(self) -> None:
        assert self.render(csv.QUOTE_MINIMAL) == "a b,42"
        assert self.render(csv.QUOTE_ALL) == '"a b","42"'
        assert self.render(csv.QUOTE_NONNUMERIC) == '"a b",42'

    def test_quote_none_needs_an_escape_character(self) -> None:
        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_NONE, escapechar="\\")

        writer.writerow(["a,b"])

        assert buffer.getvalue().strip() == "a\\,b"

    @pytest.mark.skipif(not hasattr(csv, "QUOTE_STRINGS"), reason="3.12+")
    def test_the_two_added_in_312(self) -> None:
        assert self.render(csv.QUOTE_STRINGS) == '"a b",42'  # type: ignore[attr-defined]
        assert self.render(csv.QUOTE_NOTNULL) == '"a b","42"'  # type: ignore[attr-defined]


class TestSnifferWalksTheWholeSample:
    """`sniff` and `has_header` | O(s) | O(s) | s = sample length."""

    @staticmethod
    def _sample(lines: int) -> str:
        return "".join(f"a{index};b{index};c{index}\n" for index in range(lines))

    def test_it_finds_the_delimiter(self) -> None:
        dialect = csv.Sniffer().sniff("name;age;city\nAlice;30;NYC\n")

        assert dialect.delimiter == ";"

    def test_has_header_distinguishes_the_two_shapes(self) -> None:
        with_header = "name;age;city\nAlice;30;NYC\nBob;25;LA\n"

        assert csv.Sniffer().has_header(with_header) is True

    def test_the_peak_follows_the_sample(self) -> None:
        small = self._sample(100)
        large = self._sample(5_000)

        small_peak = peak_bytes(lambda: csv.Sniffer().sniff(small))
        large_peak = peak_bytes(lambda: csv.Sniffer().sniff(large))

        assert large_peak > small_peak * 4, (
            f"a {len(large)}-character sample peaked at {large_peak} bytes against "
            f"{small_peak} for {len(small)}; the row claims O(s) space"
        )

    @pytest.mark.timing
    def test_ten_times_the_sample_costs_far_more_than_a_constant(self) -> None:
        small = self._sample(100)
        large = self._sample(1_000)

        small_ns = best_ns(lambda: csv.Sniffer().sniff(small), inner=3)
        large_ns = best_ns(lambda: csv.Sniffer().sniff(large), inner=3)

        ratio = large_ns / small_ns
        assert ratio > 4, (
            f"10x the sample cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "a constant-time sniffer would give x1"
        )

    @pytest.mark.timing
    def test_has_header_tracks_the_sniff_it_calls(self) -> None:
        sample = "name;age;city\n" + self._sample(1_000)

        sniff_ns = best_ns(lambda: csv.Sniffer().sniff(sample), inner=3)
        header_ns = best_ns(lambda: csv.Sniffer().has_header(sample), inner=3)

        assert header_ns > sniff_ns * 0.8, (
            f"has_header cost {header_ns:.0f}ns against sniff's {sniff_ns:.0f}ns; "
            "the row says sniff dominates"
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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, in its own process so the global dialect registry and
    field size limit cannot leak between them."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

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
        broken = original.replace("import csv\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
