"""Tests for docs/stdlib/csv.md.

The page prices the module a row at a time: a reader holds the row it just
parsed, a writer renders one line before handing it to the sink, and only
`Sniffer` walks a whole sample. Laziness and per-row space are settled by
traced allocation, which separates the states by orders of magnitude and needs
no tolerance; the dictionary dimensions are settled by holding one variable
fixed while the other grows; dialect and attribute rows are settled by
observation.

Measurement scope:

* `csv.reader()` is a counting iterator that is asserted untouched by
  construction, and a `tracemalloc` peak over 100,000 lines: building the
  reader peaks under 5 KB, one `next()` under 100 KB, and `list(reader)` over
  5 MB. `DictReader()` peaks under 5 KB over 50,000 rows with the stream at
  offset 0 afterwards, so the header is not read at construction; the
  `fieldnames` object is the same on a second access.
* `writerow()` builds the whole line before writing it: the peak rises across
  rows of 10, 1,000 and 100,000 ten-character fields and exceeds 500 KB for
  the 1.1 MB line. `writerows()` over 200 such rows of 11,000 characters peaks
  under four times one row, and `DictWriter.writerows()` over 200 dictionaries
  rendering to 10,003 characters peaks under four times one row, against a
  batch of two million characters. The sink keeps only the last line written,
  so it can add one row to either peak and never the batch. That
  `DictWriter.writerows()` is lazy is observed directly: a generator of
  dictionaries and a recording sink show each row written before the next
  dictionary is taken.
* `DictReader.fieldnames`, `DictWriter.writeheader()` and
  `DictWriter.writerow()` hold the field count at two while each string grows
  from 1,000 to 100,000 characters; allocation grows more than 20x and, in a
  timing test, so does time. `DictWriter.writerow()` is then held at about
  20,000 rendered characters while the field count goes from 2 to 20,000:
  allocation grows more than 10x and, in a timing test, time more than 3x,
  which is the m term. Parsing uses a fresh reader each time; writers reuse
  their buffer after a warm-up; inputs and the sink are prepared outside the
  measurement.
* Ragged short rows hold the input at one field while the header grows from
  10 to 10,000 names; the returned dictionary has one entry per header name,
  every missing one the same `restval` object, and the per-row peak grows
  more than 20x. Header creation and field-name hashing happen before the
  measurement.
* `Sniffer.sniff()` is a peak that grows more than 4x from a 100-line sample
  to a 5,000-line one, and a timing test in which 10x the sample costs more
  than 4x. `has_header()` is observed to call `sniff()` once and to take
  exactly 23 strings from a 1,001-row sample, which bounds what it reads
  after the sniff; that the 21 rows between the header and the stop row are
  the ones typed is read from Lib/csv.py. A timing test bounds it under 2x
  `sniff()` on that sample, which excludes a second pass as costly as the
  first. `has_header()` is asserted `True` with a text header over numeric
  rows and `False` without one. `preferred` is asserted
  to decide between two delimiters that fit a sample equally, in its order,
  on a reordered instance.
* `reader.line_num` is 3 after two rows from a file whose first row spans
  two lines, and 1 after the same row supplied as one string, so it counts
  strings taken from the input. `reader.dialect` and `writer.dialect` are
  `_csv.Dialect` instances, the same object on every access, carrying the
  values the reader or writer was built with, `strict` included.
* A `Dialect` subclass's attributes are copied at construction: a reader or
  writer built before the class's delimiter changes keeps the old one, one
  built after gets the new one, a subclass setting `strict` reaches the built
  dialect of both, and a two-character delimiter raises `TypeError` when the
  reader is built rather than on the first row, and `csv.Error` when the
  subclass is instantiated.
* The `QUOTE_*` flags are asserted by output on a two-field row; the two that
  3.12 added are guarded on `sys.version_info`. `QUOTE_NONE` is asserted to
  escape a delimiter with `escapechar` set and to raise `csv.Error` without
  it. `field_size_limit()` is
  asserted to return the previous value, to raise `csv.Error` on a field one
  character over it, and to admit that field once raised.
* Registration is asserted by `list_dialects()` and `get_dialect()` on each
  side of `register_dialect()` and `unregister_dialect()`, after asserting
  the test's name is not already registered, and the built-in three by their
  presence and attributes.
* Every fenced Python block runs in its own subprocess, so the dialect
  registry and the field size limit cannot leak between them, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Treating field-name hashing and comparison as O(1) is a cost-model
  assumption for data rows; arbitrary key costs are outside those bounds.
* Whether `sniff()` stays linear on adversarial input. It runs regex
  alternations over the whole sample, and only well-formed delimited text is
  measured.
* The O(m + k) and O(m + h) bounds are read from Lib/csv.py's projection and
  missing-field loops and Modules/_csv.c's per-character parsing and
  rendering. The tests show each variable moves the cost of the operation it
  is varied on, not that the two add: k and h for `fieldnames`,
  `writeheader()` and `writerow()`, m for short `DictReader` rows and for
  `DictWriter.writerow()`. `writeheader()` is not varied in m.
* Non-UTF-8 encodings, embedded newlines beyond one round trip, custom
  conversion costs and error-message lengths are not varied.
"""

from __future__ import annotations

import csv
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
EXPECTED_BLOCKS = 13


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


class LastLineSink:
    """A file-like object that keeps only the last line written."""

    last: str = ""

    def write(self, text: str) -> int:
        self.last = text
        return len(text)


class CountingIterator:
    """An iterator that records how many strings have been taken from it."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = iter(lines)
        self.taken = 0

    def __iter__(self) -> CountingIterator:
        return self

    def __next__(self) -> str:
        line = next(self._lines)
        self.taken += 1
        return line


class Pipes(csv.Dialect):
    delimiter = "|"
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = "\n"
    quoting = csv.QUOTE_MINIMAL


class TestReadingIsLazy:
    """`csv.reader` | O(1) | O(1) to build, then O(k) per row.

    Measured by traced allocation, so the three states separate by orders of
    magnitude with no tolerance to choose.
    """

    LINES = [f"a{index},b{index},c{index}" for index in range(100_000)]

    def test_building_a_reader_reads_nothing(self) -> None:
        source = CountingIterator(self.LINES)

        peak = peak_bytes(lambda: csv.reader(source))

        assert source.taken == 0, f"csv.reader() took {source.taken} strings at construction"
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


class TestReaderAndWriterAttributes:
    """`reader.line_num` counts source lines; `reader.dialect` and
    `writer.dialect` are the validated object built with the reader or writer."""

    def test_line_num_counts_lines_taken_from_a_file_not_rows(self) -> None:
        reader = csv.reader(io.StringIO('"x\ny",z\nq,r\n'))

        rows = list(reader)

        assert len(rows) == 2
        assert reader.line_num == 3

    def test_line_num_counts_strings_taken_not_newlines(self) -> None:
        reader = csv.reader(['"x\ny",z'])

        assert list(reader) == [["x\ny", "z"]]
        assert reader.line_num == 1

    def test_line_num_starts_at_zero_and_advances_per_step(self) -> None:
        reader = csv.reader(["a,b", "c,d"])

        assert reader.line_num == 0
        next(reader)
        assert reader.line_num == 1

    def test_the_dialect_attribute_carries_what_was_asked_for(self) -> None:
        reader = csv.reader([], delimiter=";", strict=True)
        writer = csv.writer(io.StringIO(), delimiter="\t")

        assert type(reader.dialect).__module__ == type(writer.dialect).__module__ == "_csv"
        assert reader.dialect is reader.dialect
        assert writer.dialect is writer.dialect
        assert reader.dialect.delimiter == ";"
        assert reader.dialect.strict is True
        assert writer.dialect.delimiter == "\t"
        assert writer.dialect.strict is False


class TestWritingHoldsOneRow:
    """`writerow` | O(k) | O(k), and `writerows` | O(n·k) | O(k).

    The row is rendered whole before it is written, which is where the space
    goes; the batch form repeats that and never holds more than one line.
    """

    def test_the_peak_tracks_the_row_not_the_call(self) -> None:
        peaks: dict[int, int] = {}
        for fields in (10, 1_000, 100_000):
            writer = csv.writer(LastLineSink())
            row = ["v" * 10] * fields
            writer.writerow(row)  # warm
            peaks[fields] = peak_bytes(lambda w=writer, r=row: w.writerow(r))  # type: ignore[misc]

        assert peaks[100_000] > peaks[1_000] > peaks[10]
        assert peaks[100_000] > 500_000, f"a 1.1 MB line peaked at {peaks[100_000]} bytes"

    def test_writerows_peaks_at_the_widest_row_not_the_batch(self) -> None:
        sink = LastLineSink()
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

        # The private attribute is where the laziness shows.
        assert reader._fieldnames is None  # type: ignore[attr-defined]  # noqa: SLF001

    def test_construction_allocates_nothing_for_the_file(self) -> None:
        # The stream is built outside the measurement; wrapping it is what is measured.
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
    render, `extrasaction` decides what a surplus key costs, and `writerows`
    holds one projected row at a time."""

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

    def test_writerows_writes_every_dictionary(self) -> None:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["a", "b"])

        writer.writerows([{"a": 1, "b": 2}, {"b": 4, "a": 3}])

        assert buffer.getvalue() == "1,2\r\n3,4\r\n"

    def test_writerows_takes_one_dictionary_per_row_written(self) -> None:
        events: list[str] = []

        class RecordingSink:
            def write(self, text: str) -> int:
                events.append("write")
                return len(text)

        def dictionaries() -> Iterator[dict[str, int]]:
            for index in range(3):
                events.append(f"take {index}")
                yield {"a": index}

        csv.DictWriter(RecordingSink(), fieldnames=["a"]).writerows(dictionaries())

        assert events == ["take 0", "write", "take 1", "write", "take 2", "write"]

    def test_writerows_peaks_at_the_widest_row_not_the_batch(self) -> None:
        sink = LastLineSink()
        writer = csv.DictWriter(sink, fieldnames=["a", "b"])
        rows = [{"a": "v" * 5_000, "b": "w" * 5_000} for _ in range(200)]
        writer.writerows(rows)  # warm

        peak = peak_bytes(lambda: writer.writerows(rows))

        one_row = len(sink.last)
        assert peak < one_row * 4, (
            f"DictWriter.writerows peaked at {peak} for a {one_row}-char row "
            f"and a {one_row * len(rows)}-char batch"
        )


class TestDictionaryTextLengths:
    """Vary row/header characters at a fixed field count, then the field count
    at a fixed rendered length, so each term of O(m + k) moves on its own."""

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

    @classmethod
    def writerow_of(cls, fields: int, width: int) -> tuple[Callable[[], Any], int]:
        """A warmed `DictWriter.writerow` over `fields` fields of `width` characters."""
        names = [f"f{index}" for index in range(fields)]
        writer = csv.DictWriter(cls.Sink(), names)
        row = dict.fromkeys(names, "x" * width)
        rendered = writer.writerow(row)
        return partial(writer.writerow, row), rendered

    NARROW = (2, 10_000)  # two fields, 20,003 rendered characters
    WIDE = (20_000, 0)  # twenty thousand empty fields, 20,001 rendered characters

    def test_field_count_controls_allocation_at_fixed_rendered_length(self) -> None:
        narrow, narrow_length = self.writerow_of(*self.NARROW)
        wide, wide_length = self.writerow_of(*self.WIDE)
        assert abs(narrow_length - wide_length) < 10

        peaks = [peak_bytes(narrow), peak_bytes(wide)]

        assert peaks[1] > peaks[0] * 10, f"10,000x the fields at one rendered length: {peaks}"

    @pytest.mark.timing
    def test_field_count_controls_time_at_fixed_rendered_length(self) -> None:
        narrow, _ = self.writerow_of(*self.NARROW)
        wide, _ = self.writerow_of(*self.WIDE)

        durations = [best_ns(narrow, inner=5), best_ns(wide, inner=5)]
        ratio = durations[1] / durations[0]

        assert ratio > 3, f"10,000x the fields at one rendered length: {durations} ns, x{ratio:.2f}"

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
    three are always present; a `Dialect` subclass's attributes are copied,
    and validated, when a reader or writer is built."""

    @pytest.fixture(autouse=True)
    def _unregister(self) -> Iterator[None]:
        assert "pipes" not in csv.list_dialects(), "'pipes' is registered by something else"
        yield
        if "pipes" in csv.list_dialects():
            csv.unregister_dialect("pipes")

    @pytest.fixture(autouse=True)
    def _restore_pipes(self) -> Iterator[None]:
        original = Pipes.delimiter
        yield
        Pipes.delimiter = original

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
        assert {"excel", "excel-tab", "unix"} <= set(csv.list_dialects())
        assert csv.excel.delimiter == ","
        assert csv.excel_tab.delimiter == "\t"
        assert csv.unix_dialect.quoting == csv.QUOTE_ALL
        assert issubclass(csv.excel, csv.Dialect)

    def test_an_invalid_dialect_is_rejected_when_the_writer_is_built(self) -> None:
        with pytest.raises((csv.Error, TypeError)):
            csv.writer(io.StringIO(), delimiter="too long")

    def test_a_subclass_s_attributes_are_copied_when_the_reader_is_built(self) -> None:
        before = csv.reader(io.StringIO("a|b;c\n"), dialect=Pipes)

        Pipes.delimiter = ";"
        after = csv.reader(io.StringIO("a|b;c\n"), dialect=Pipes)

        assert before.dialect.delimiter == "|"
        assert next(before) == ["a", "b;c"]
        assert next(after) == ["a|b", "c"]

    def test_a_subclass_s_attributes_are_copied_when_the_writer_is_built(self) -> None:
        before_sink, after_sink = io.StringIO(), io.StringIO()
        before = csv.writer(before_sink, dialect=Pipes)

        Pipes.delimiter = ";"
        after = csv.writer(after_sink, dialect=Pipes)
        before.writerow(["a", "b"])
        after.writerow(["a", "b"])

        assert before_sink.getvalue() == "a|b\n"
        assert after_sink.getvalue() == "a;b\n"

    def test_a_subclass_can_supply_strict(self) -> None:
        class Strict(Pipes):
            strict = True

        assert csv.reader([], dialect=Strict).dialect.strict is True
        assert csv.writer(io.StringIO(), dialect=Strict).dialect.strict is True
        assert csv.reader([], dialect=Pipes).dialect.strict is False

    def test_a_subclass_is_validated_when_the_reader_is_built(self) -> None:
        class Broken(Pipes):
            delimiter = "ab"

        with pytest.raises(TypeError, match="delimiter"):
            csv.reader(io.StringIO("a,b\n"), dialect=Broken)

    def test_instantiating_a_broken_subclass_raises_csv_error(self) -> None:
        class Broken(Pipes):
            delimiter = "ab"

        with pytest.raises(csv.Error, match="delimiter"):
            Broken()

    def test_every_format_attribute_reaches_the_built_dialect(self) -> None:
        writer = csv.writer(
            io.StringIO(),
            delimiter=";",
            quotechar="'",
            escapechar="\\",
            doublequote=False,
            skipinitialspace=True,
            lineterminator="\n",
            quoting=csv.QUOTE_ALL,
            strict=True,
        )

        dialect = writer.dialect
        assert (dialect.delimiter, dialect.quotechar, dialect.escapechar) == (";", "'", "\\")
        assert (dialect.doublequote, dialect.skipinitialspace, dialect.strict) == (
            False,
            True,
            True,
        )
        assert (dialect.lineterminator, dialect.quoting) == ("\n", csv.QUOTE_ALL)


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
        with pytest.raises(csv.Error, match="need to escape"):
            csv.writer(io.StringIO(), quoting=csv.QUOTE_NONE).writerow(["a,b"])

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="added in 3.12")
    def test_the_two_added_in_312(self) -> None:
        assert self.render(csv.QUOTE_STRINGS) == '"a b",42'  # type: ignore[attr-defined]
        assert self.render(csv.QUOTE_NOTNULL) == '"a b","42"'  # type: ignore[attr-defined]


class TestSnifferWalksTheWholeSample:
    """`sniff` and `has_header` | O(s) | O(s) | s = sample length; `preferred`
    decides between delimiters that fit equally."""

    @staticmethod
    def _sample(lines: int) -> str:
        return "".join(f"a{index};b{index};c{index}\n" for index in range(lines))

    @staticmethod
    def _headed_sample(rows: int) -> str:
        """A text header over numeric rows, the shape `has_header()` says yes to."""
        return "name;age;city\n" + "".join(f"{i};{i * 2};{i * 3}\n" for i in range(rows))

    def test_it_finds_the_delimiter(self) -> None:
        dialect = csv.Sniffer().sniff("name;age;city\nAlice;30;NYC\n")

        assert dialect.delimiter == ";"

    def test_has_header_distinguishes_the_two_shapes(self) -> None:
        with_header = "name;age;city\nAlice;30;NYC\nBob;25;LA\n"
        without = "1;2;3\n4;5;6\n7;8;9\n"

        assert csv.Sniffer().has_header(with_header) is True
        assert csv.Sniffer().has_header(without) is False

    def test_has_header_sniffs_once_and_types_a_bounded_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sample = self._headed_sample(1_000)
        sniffs: list[str] = []
        original_sniff = csv.Sniffer.sniff
        original_reader = csv.reader
        taken: list[int] = []

        def counting_sniff(self: csv.Sniffer, text: str, delimiters: Any = None) -> Any:
            sniffs.append(text)
            return original_sniff(self, text, delimiters)

        def counting_reader(source: Any, *args: Any, **kwargs: Any) -> Any:
            counting = CountingIterator(list(source))
            taken.append(0)
            reader = original_reader(counting, *args, **kwargs)

            def rows() -> Iterator[list[str]]:
                for row in reader:
                    taken[-1] = counting.taken
                    yield row

            return rows()

        monkeypatch.setattr(csv.Sniffer, "sniff", counting_sniff)
        monkeypatch.setattr(csv, "reader", counting_reader)

        assert csv.Sniffer().has_header(sample) is True
        assert sniffs == [sample]
        assert taken == [23], f"has_header took {taken} strings from a 1,001-row sample"

    def test_preferred_breaks_a_tie_in_its_order(self) -> None:
        ambiguous = "a;b,c\nd;e,f\ng;h,i\n"
        sniffer = csv.Sniffer()

        assert sniffer.preferred.index(",") < sniffer.preferred.index(";")
        assert sniffer.sniff(ambiguous).delimiter == ","

        sniffer.preferred = [";", ","]

        assert sniffer.sniff(ambiguous).delimiter == ";"
        assert csv.Sniffer().sniff(ambiguous).delimiter == ",", "the change is per instance"

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
    def test_has_header_costs_little_beyond_the_sniff_it_calls(self) -> None:
        sample = self._headed_sample(1_000)

        sniff_ns = best_ns(lambda: csv.Sniffer().sniff(sample), inner=3)
        header_ns = best_ns(lambda: csv.Sniffer().has_header(sample), inner=3)

        assert header_ns < sniff_ns * 2, (
            f"has_header cost {header_ns:.0f}ns against sniff's {sniff_ns:.0f}ns; "
            "a second pass as costly as the sniff would double it"
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
    """Each block runs in its own subprocess, so the dialect registry and the
    field size limit cannot leak between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "reader.line_num == 3" in s)
        mutated = source.replace("reader.line_num == 3", "reader.line_num == 2", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
