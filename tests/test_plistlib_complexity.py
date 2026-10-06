"""Tests for docs/stdlib/plistlib.md.

The page prices reading by the bytes of the plist and writing by the bytes it
produces (XML) or the size of the value (binary), plus a sort per dictionary
under the default `sort_keys=True`. What each direction holds is settled by
traced allocation against a sink that keeps nothing; the sort is settled by
counting key comparisons; growth rates by timing three sizes a decade apart;
the type, UID, format and exception rows by observation.

Measurement scope:

* `load()` of an XML plist padded with 1,000 or 100,000 comments peaks under
  50 KB at both sizes, against a 1 MB input, so the parser is fed in chunks and
  holds the value rather than the file. `loads()` of 20,000 and 200,000
  distinct ints peaks between 5x and 20x apart in both formats.
* `loads()` and `dumps()` in both formats are timed on 1,000, 10,000 and
  100,000 distinct strings with `sort_keys=False`; each tenfold step is asserted
  to cost between 4x and 30x, where linear predicts 10x and quadratic 100x.
* XML `dump()` of 200,000 strings into a sink peaks under 10 KB; `dumps()` of
  the same value peaks above its own output length. A prebuilt `str` or
  `bytes` of 10,000 units peaks under 100 KB and one of 1,000,000 units
  between 1 MB and 10 MB, which is the s term.
* Key sorting: a `str` subclass counts `__lt__` on 4,096 shuffled keys. With
  `sort_keys=True` both writers make between d·log2(d)/2 and 4·d·log2(d)
  comparisons (the binary writer sorts once to table and once to write);
  `sort_keys=False` makes none. XML `dump()` of a 100,000-key dictionary peaks
  over 1 MB with the sort, between 5x and 20x the 10,000-key peak, and under
  10 KB without it.
* Binary `dump()` into a sink peaks at more than 50 bytes per object for
  10,000 and 100,000 distinct ints, growing between 5x and 20x; over 200
  distinct 100 KB blobs (20 MB) it peaks under 1 MB, so it is O(m + s), not
  O(v). The same 200 equal blobs produce under 110 KB of output, and read back
  as one object. A timing test shows 200 equal-but-distinct blobs cost over 5x
  what 200 references to one blob cost, with identical output: time follows
  the value, not n.
* `fmt=None` on a stream that cannot seek raises `io.UnsupportedOperation`;
  `fmt=FMT_XML` reads it and `fmt=FMT_BINARY` raises `InvalidFileException`.
  `dict_type` is called once per dictionary in both formats.
* Types: `tuple` and `bytearray` read back as `list` and `bytes`, XML dates
  drop microseconds and binary dates keep them on a 2024 date (binary stores
  float seconds from 2001, so distant dates lose precision; not varied), a
  non-`str` key and a `set`
  raise `TypeError`, 2**64 raises `OverflowError`. `skipkeys=True` skips a
  non-`str` key with `sort_keys=False`. With `sort_keys=True`, mixed keys
  raise `TypeError` before 3.13.16 on the 3.13 line and before 3.14.8 on the
  3.14 line (also on 3.10-3.12); from those patches, non-string keys are
  skipped and the remaining keys are sorted. Both values and key order are
  checked in each successful case.
* `UID` accepts 0 and 2**64 - 1, rejects -1 and 2**64 with `ValueError` and
  a `str` with `TypeError`,
  round-trips through the binary format, exposes `.data`, and makes the XML
  writer raise `TypeError`. `FMT_XML` and `FMT_BINARY` are `PlistFormat`
  members and `FMT_XML` is the default. `InvalidFileException` is a
  `ValueError`, raised for an unknown header, a truncated binary plist and an
  entity declaration; mismatched XML tags raise `ExpatError`.
* `loads()` of a `str` and `aware_datetime` are guarded on 3.13; before it, a
  `str` raises `TypeError`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That binary reading seeks from object to object rather than reading the
  whole file is read from `_BinaryPlistParser` in Lib/plistlib.py; only its
  requirement for a seekable stream is observed.
* Binary `dumps()` space is O(n) from Lib/plistlib.py: the writer's table
  holds one entry per object it writes (a repeated container or equal scalar
  is tabled once), and each written object costs at least one byte of output.
  The table is measured under `dump()`, not against the output length.
* Only `bytes` values are observed being shared, and two equal 100 KB
  `bytearray`s observed written twice; that `str`, numbers and dates are
  keyed by `(type, value)` and containers by identity is read from
  `_BinaryPlistWriter._flatten`.
* The timing tests bound each tenfold step between 4x and 30x, which excludes
  quadratic growth but not an extra log factor; linearity itself is read from
  the source.
* Key comparison is priced as O(1); keys sharing long prefixes compare in
  time proportional to the prefix. `dict_type` is priced as a plain `dict`.
* Nesting depth is not varied. Both writers and the binary reader recurse
  once or twice per level, so depth is bounded by the recursion limit, and the
  XML writer's indentation is part of n.
* Malformed binary input declaring sizes larger than the file, and XML with
  large runs of character data between elements, are not measured.
"""

from __future__ import annotations

import datetime
import io
import pathlib
import plistlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any, cast
from xml.parsers.expat import ExpatError

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "plistlib.md"
EXPECTED_BLOCKS = 8

FORMATS = [plistlib.FMT_XML, plistlib.FMT_BINARY]


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
    """Peak traced allocation while func runs, after one untraced warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class Sink:
    """A binary file-like object that counts what is written and keeps none of it."""

    def __init__(self) -> None:
        self.written = 0

    def write(self, data: bytes) -> int:
        self.written += len(data)
        return len(data)

    def tell(self) -> int:
        return self.written


class NoSeek(io.RawIOBase):
    """A readable stream that cannot seek, like a pipe."""

    def __init__(self, data: bytes) -> None:
        self._data = io.BytesIO(data)

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        chunk = self._data.read(len(buffer))
        buffer[: len(chunk)] = chunk
        return len(chunk)


def sink() -> Any:
    """A `Sink`, typed for the `IO[bytes]` parameter it stands in for."""
    return Sink()


def no_seek(data: bytes) -> Any:
    """A `NoSeek` over data, typed for the `IO[bytes]` parameter it stands in for."""
    return NoSeek(data)


class CountingKey(str):
    """A `str` key that counts the `<` comparisons made on it."""

    comparisons = 0

    def __lt__(self, other: object) -> bool:
        CountingKey.comparisons += 1
        return str.__lt__(self, other)  # type: ignore[arg-type]


def strings(count: int) -> list[str]:
    return [f"s{index:07d}" for index in range(count)]


class TestReadingHoldsTheValue:
    """`load()`/`loads()` | O(n) | O(n): space is the returned value, not the
    file; the stream needs to seek only for format detection or binary."""

    @staticmethod
    def padded(comments: int) -> bytes:
        return (
            b"<plist version='1.0'><array>"
            + b"<!-- padding -->" * comments
            + b"<integer>1</integer></array></plist>"
        )

    def test_xml_load_does_not_hold_the_file(self) -> None:
        peaks = []
        for comments in (1_000, 100_000):
            data = self.padded(comments)
            assert plistlib.loads(data) == [1]
            peaks.append(peak_bytes(lambda d=data: plistlib.load(io.BytesIO(d))))  # type: ignore[misc]

        assert max(peaks) < 50_000, f"a 1.6 MB XML plist of comments peaked at {peaks}"

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_loads_space_follows_the_value(self, fmt: plistlib.PlistFormat) -> None:
        peaks = []
        for count in (20_000, 200_000):
            data = plistlib.dumps(list(range(10**6, 10**6 + count)), fmt=fmt)
            peaks.append(peak_bytes(lambda d=data: plistlib.loads(d)))  # type: ignore[misc]

        ratio = peaks[1] / peaks[0]
        assert 5 < ratio < 20, f"10x the ints: peaks {peaks}, x{ratio:.1f}"

    def test_format_detection_seeks(self) -> None:
        xml = plistlib.dumps({"a": 1})

        with pytest.raises(io.UnsupportedOperation):
            plistlib.load(no_seek(xml))
        assert plistlib.load(no_seek(xml), fmt=plistlib.FMT_XML) == {"a": 1}

    def test_binary_reading_needs_a_seekable_stream(self) -> None:
        binary = plistlib.dumps({"a": 1}, fmt=plistlib.FMT_BINARY)

        with pytest.raises(plistlib.InvalidFileException):
            plistlib.load(no_seek(binary), fmt=plistlib.FMT_BINARY)
        assert plistlib.load(io.BytesIO(binary), fmt=plistlib.FMT_BINARY) == {"a": 1}

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_dict_type_is_called_once_per_dictionary(self, fmt: plistlib.PlistFormat) -> None:
        calls: list[int] = []

        def factory() -> dict[str, Any]:
            calls.append(1)
            return {}

        data = plistlib.dumps({"a": {"b": {}}, "c": [{}, 1]}, fmt=fmt)

        assert plistlib.loads(data, dict_type=cast(Any, factory)) == {"a": {"b": {}}, "c": [{}, 1]}
        assert len(calls) == 4

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="str input added in 3.13")
    def test_loads_accepts_xml_text_from_313(self) -> None:
        text = plistlib.dumps([1, 2]).decode()

        assert plistlib.loads(text) == [1, 2]  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="FMT_BINARY"):
            plistlib.loads(text, fmt=plistlib.FMT_BINARY)  # type: ignore[arg-type]

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="str input added in 3.13")
    def test_loads_rejects_text_before_313(self) -> None:
        with pytest.raises(TypeError):
            plistlib.loads(plistlib.dumps([1]).decode())  # type: ignore[arg-type]


class TestReadingAndWritingAreLinear:
    """O(n) to read either format and to write XML, O(v) to write binary: each
    tenfold step in the value costs about tenfold."""

    SIZES = (1_000, 10_000, 100_000)

    @staticmethod
    def assert_linear(name: str, durations: list[float]) -> None:
        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]
        assert all(4 < ratio < 30 for ratio in ratios), (
            f"{name}: {durations} ns across 10x steps, ratios {ratios}; "
            "linear gives about 10, quadratic 100"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_loads(self, fmt: plistlib.PlistFormat) -> None:
        payloads = [plistlib.dumps(strings(size), fmt=fmt) for size in self.SIZES]
        durations = [best_ns(lambda p=p: plistlib.loads(p)) for p in payloads]  # type: ignore[misc]

        self.assert_linear(f"loads {fmt.name}", durations)

    @pytest.mark.timing
    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_dumps(self, fmt: plistlib.PlistFormat) -> None:
        values = [strings(size) for size in self.SIZES]
        durations = [
            best_ns(lambda v=v: plistlib.dumps(v, fmt=fmt, sort_keys=False))  # type: ignore[misc]
            for v in values
        ]

        self.assert_linear(f"dumps {fmt.name}", durations)


class TestXmlDumpStreams:
    """XML `dump()` | O(n) | O(s): each element goes to `fp` as it is reached;
    `dumps()` holds the whole document."""

    def test_dump_holds_no_document(self) -> None:
        value = strings(200_000)

        dump_peak = peak_bytes(lambda: plistlib.dump(value, sink()))
        output = len(plistlib.dumps(value))
        dumps_peak = peak_bytes(lambda: plistlib.dumps(value))

        assert dump_peak < 10_000, f"dump() of a {output}-byte document peaked at {dump_peak}"
        assert dumps_peak > output, f"dumps() peaked at {dumps_peak} for {output} bytes"

    @pytest.mark.parametrize("scalar", [lambda size: "x" * size, bytes], ids=["str", "bytes"])
    def test_dump_holds_the_largest_scalar(self, scalar: Callable[[int], Any]) -> None:
        small_value, large_value = [scalar(10_000)], [scalar(1_000_000)]

        small = peak_bytes(lambda: plistlib.dump(small_value, sink()))
        large = peak_bytes(lambda: plistlib.dump(large_value, sink()))

        assert small < 100_000, f"a 10,000-unit scalar peaked at {small}"
        assert 1_000_000 < large < 10_000_000, f"a 1,000,000-unit scalar peaked at {large}"

    def test_the_default_format_is_xml(self) -> None:
        assert plistlib.dumps([]).startswith(b"<?xml")
        sink = io.BytesIO()
        plistlib.dump([], sink)
        assert sink.getvalue() == plistlib.dumps([], fmt=plistlib.FMT_XML)


class TestSortKeys:
    """`sort_keys=True` | O(d log d) per dictionary | O(d) per open dictionary;
    `sort_keys=False` writes insertion order with no comparisons."""

    KEYS = 4_096

    @pytest.fixture
    def shuffled(self) -> dict[str, int]:
        keys = [CountingKey(f"k{index:05d}") for index in range(self.KEYS)]
        random.Random(7).shuffle(keys)
        return dict.fromkeys(keys, 1)

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_sorting_makes_d_log_d_comparisons(
        self, fmt: plistlib.PlistFormat, shuffled: dict[str, int]
    ) -> None:
        CountingKey.comparisons = 0
        plistlib.dumps(shuffled, fmt=fmt)
        d_log_d = self.KEYS * 12  # log2(4096) = 12

        assert d_log_d / 2 < CountingKey.comparisons < d_log_d * 4, (
            f"{CountingKey.comparisons} comparisons for {self.KEYS} keys; d·log2(d) = {d_log_d}"
        )

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_sort_keys_false_compares_nothing(
        self, fmt: plistlib.PlistFormat, shuffled: dict[str, int]
    ) -> None:
        CountingKey.comparisons = 0
        plistlib.dumps(shuffled, fmt=fmt, sort_keys=False)

        assert CountingKey.comparisons == 0

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_the_order_written(self, fmt: plistlib.PlistFormat) -> None:
        value = {"b": 1, "a": 2, "c": 3}

        assert list(plistlib.loads(plistlib.dumps(value, fmt=fmt))) == ["a", "b", "c"]
        unsorted = plistlib.dumps(value, fmt=fmt, sort_keys=False)
        assert list(plistlib.loads(unsorted)) == ["b", "a", "c"]

    def test_the_sort_holds_the_dictionary_s_items(self) -> None:
        small = {f"k{index:06d}": index for index in range(10_000)}
        value = {f"k{index:06d}": index for index in range(100_000)}

        small_sort = peak_bytes(lambda: plistlib.dump(small, sink()))
        with_sort = peak_bytes(lambda: plistlib.dump(value, sink()))
        without = peak_bytes(lambda: plistlib.dump(value, sink(), sort_keys=False))

        assert with_sort > 1_000_000, f"sorting 100,000 items peaked at {with_sort}"
        assert 5 < with_sort / small_sort < 20, f"10x the keys: {small_sort} -> {with_sort}"
        assert without < 10_000, f"writing 100,000 items unsorted peaked at {without}"

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_skipkeys(self, fmt: plistlib.PlistFormat) -> None:
        mixed: dict[Any, Any] = {"z": 3, 2: "b", "a": 1}

        written = plistlib.dumps(mixed, fmt=fmt, skipkeys=True, sort_keys=False)
        assert list(plistlib.loads(written).items()) == [("z", 3), ("a", 1)]
        # gh-145856: filter non-string keys before sorting.
        if sys.version_info >= (3, 14, 8) or (3, 13, 16) <= sys.version_info < (3, 14):
            written = plistlib.dumps(mixed, fmt=fmt, skipkeys=True)
            assert list(plistlib.loads(written).items()) == [("a", 1), ("z", 3)]
        else:
            with pytest.raises(TypeError, match="not supported between"):
                plistlib.dumps(mixed, fmt=fmt, skipkeys=True)
        with pytest.raises(TypeError, match="keys must be strings"):
            plistlib.dumps(mixed, fmt=fmt, sort_keys=False)


class TestBinaryWriterTablesEveryObject:
    """Binary `dump()` | O(v) | O(m + s): every object is tabled before any is
    written, and every scalar is hashed so that equal ones are written once."""

    def test_the_table_grows_with_the_objects(self) -> None:
        peaks = []
        for count in (10_000, 100_000):
            value = list(range(10**6, 10**6 + count))
            peaks.append(
                peak_bytes(lambda v=value: plistlib.dump(v, sink(), fmt=plistlib.FMT_BINARY))
            )  # type: ignore[misc]
            assert peaks[-1] > count * 50, f"{count} objects peaked at {peaks[-1]}"

        assert 5 < peaks[1] / peaks[0] < 20, f"10x the objects: {peaks}"

    def test_large_data_is_not_copied(self) -> None:
        blobs = [bytes([index]) * 100_000 for index in range(200)]

        peak = peak_bytes(lambda: plistlib.dump(blobs, sink(), fmt=plistlib.FMT_BINARY))

        assert peak < 1_000_000, f"20 MB of data in 200 blobs peaked at {peak}"

    def test_equal_scalars_are_written_once_and_read_back_shared(self) -> None:
        blobs = [bytes(100_000) for _ in range(200)]
        assert blobs[0] is not blobs[1]

        data = plistlib.dumps(blobs, fmt=plistlib.FMT_BINARY)
        loaded = plistlib.loads(data)

        assert len(data) < 110_000, f"200 equal 100 KB blobs wrote {len(data)} bytes"
        assert loaded == blobs
        assert all(blob is loaded[0] for blob in loaded)

    def test_a_bytearray_is_tabled_by_identity(self) -> None:
        arrays = [bytearray(100_000) for _ in range(2)]

        data = plistlib.dumps(arrays, fmt=plistlib.FMT_BINARY)

        assert len(data) > 200_000, f"two equal 100 KB bytearrays wrote {len(data)} bytes"

    def test_xml_writes_every_copy(self) -> None:
        blobs = [bytes(1_000) for _ in range(200)]

        assert len(plistlib.dumps(blobs)) > 200 * 1_000

    @pytest.mark.timing
    def test_time_follows_the_value_not_the_output(self) -> None:
        shared = [bytes(100_000)] * 200
        distinct = [bytes(100_000) for _ in range(200)]
        shared_out = plistlib.dumps(shared, fmt=plistlib.FMT_BINARY)
        assert plistlib.dumps(distinct, fmt=plistlib.FMT_BINARY) == shared_out

        shared_ns = best_ns(lambda: plistlib.dumps(shared, fmt=plistlib.FMT_BINARY))
        distinct_ns = best_ns(lambda: plistlib.dumps(distinct, fmt=plistlib.FMT_BINARY))

        ratio = distinct_ns / shared_ns
        assert ratio > 5, (
            f"200 equal blobs cost {distinct_ns:.0f}ns, 200 references to one {shared_ns:.0f}ns "
            f"(x{ratio:.1f}), for the same {len(shared_out)}-byte output"
        )


class TestTypes:
    """What round-trips, what changes type, and what is rejected."""

    WHEN = datetime.datetime(2024, 1, 2, 3, 4, 5, 678901)

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_tuple_and_bytearray_read_back_as_list_and_bytes(
        self, fmt: plistlib.PlistFormat
    ) -> None:
        loaded = plistlib.loads(plistlib.dumps([(1, 2), bytearray(b"ab")], fmt=fmt))

        assert loaded == [[1, 2], b"ab"]
        assert type(loaded[0]) is list
        assert type(loaded[1]) is bytes

    def test_xml_dates_keep_whole_seconds(self) -> None:
        assert plistlib.loads(plistlib.dumps(self.WHEN)) == self.WHEN.replace(microsecond=0)

    def test_binary_dates_keep_microseconds(self) -> None:
        assert plistlib.loads(plistlib.dumps(self.WHEN, fmt=plistlib.FMT_BINARY)) == self.WHEN

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_what_is_rejected(self, fmt: plistlib.PlistFormat) -> None:
        with pytest.raises(TypeError):
            plistlib.dumps(cast(Any, {1: "a"}), fmt=fmt)
        with pytest.raises(TypeError):
            plistlib.dumps({"a": {1, 2}}, fmt=fmt)
        with pytest.raises(OverflowError):
            plistlib.dumps(2**64, fmt=fmt)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="aware_datetime added in 3.13")
    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_aware_datetime(self, fmt: plistlib.PlistFormat) -> None:
        utc = datetime.timezone.utc
        plus_two = datetime.timezone(datetime.timedelta(hours=2))
        aware = datetime.datetime(2024, 1, 2, 5, 4, 5, tzinfo=plus_two)

        data = plistlib.dumps(aware, fmt=fmt, aware_datetime=True)  # type: ignore[call-arg]
        loaded = plistlib.loads(data, aware_datetime=True)  # type: ignore[call-arg]

        assert loaded == aware
        assert loaded.tzinfo == utc
        assert loaded.hour == 3


class TestUID:
    """`UID(data)` | O(1) | O(1), binary only; `UID.data` is the int."""

    def test_the_range_is_checked(self) -> None:
        assert plistlib.UID(0).data == 0
        assert plistlib.UID(2**64 - 1).data == 2**64 - 1
        with pytest.raises(ValueError):
            plistlib.UID(-1)
        with pytest.raises(ValueError):
            plistlib.UID(2**64)
        with pytest.raises(TypeError):
            plistlib.UID("1")  # type: ignore[arg-type]

    def test_binary_round_trip(self) -> None:
        loaded = plistlib.loads(plistlib.dumps([plistlib.UID(7)], fmt=plistlib.FMT_BINARY))

        assert loaded == [plistlib.UID(7)]
        assert loaded[0].data == 7

    def test_xml_rejects_it(self) -> None:
        with pytest.raises(TypeError, match="UID"):
            plistlib.dumps([plistlib.UID(7)])


class TestFormatsAndExceptions:
    """`FMT_XML`/`FMT_BINARY` are `PlistFormat` members; `InvalidFileException`
    is a `ValueError` for non-plists and bad binary; bad XML is `ExpatError`."""

    def test_formats_are_enum_members(self) -> None:
        assert set(plistlib.PlistFormat) == {plistlib.FMT_XML, plistlib.FMT_BINARY}

    @pytest.mark.parametrize("fmt", FORMATS, ids=lambda f: f.name)
    def test_the_format_is_detected(self, fmt: plistlib.PlistFormat) -> None:
        assert plistlib.loads(plistlib.dumps({"a": [1]}, fmt=fmt)) == {"a": [1]}

    @pytest.mark.parametrize(
        "data",
        [
            b"not a plist",
            b"bplist00" + bytes(40),
            b'<?xml version="1.0"?><!DOCTYPE p [<!ENTITY e "x">]><plist><string>&e;</string></plist>',
        ],
        ids=["unknown header", "truncated binary", "entity declaration"],
    )
    def test_invalid_file_exception(self, data: bytes) -> None:
        assert issubclass(plistlib.InvalidFileException, ValueError)
        with pytest.raises(plistlib.InvalidFileException):
            plistlib.loads(data)

    def test_malformed_xml_raises_expat_error(self) -> None:
        with pytest.raises(ExpatError, match="mismatched tag"):
            plistlib.loads(b"<plist><array></plist>")


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
    """Each block runs in its own subprocess and working directory, and asserts
    its own result."""

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
        target = "loaded[0]['payload'] is loaded[99]['payload']"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "loaded[0]['payload'] is not loaded[99]['payload']", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
