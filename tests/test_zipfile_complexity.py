"""Tests for docs/stdlib/zipfile.md.

The page prices the module around the central directory: opening reads it,
closing after a change writes it, and member data is touched only by the
operations that read or write a member. Most claims are settled by counting
the bytes a wrapped file object reads or writes, which separates "the
directory" from "the data" with no tolerance; space claims by traced
allocation; the `zipfile.Path` index and scans by counting calls and the names
an iterator takes. Two claims need a stopwatch: `getinfo()` against
`namelist()`, and `ZipExtFile.readline()`.

Measurement scope:

* Opening in mode `'r'` reads the same number of bytes whether ten members
  hold 10 bytes or 1 MB each, and 100x the members (100 to 10,000) reads more
  than 50x the bytes and peaks at more than 20x the allocation. Mode `'w'`
  reads nothing from a 10,000-member archive and truncates it on disk; mode
  `'a'` reads more than 50x the bytes for 100x the members.
* `close()` after one added member writes more than 50x the bytes for 100x
  the existing members (10 to 1,000 and 100 to 10,000), and the bytes before
  the old central directory are unchanged, so member data is not rewritten. In
  mode `'r'`, and in mode `'a'` with nothing changed, it writes nothing;
  assigning `comment` alone makes it write the directory in mode `'a'`, and
  not in mode `'r'`.
* `infolist()` is the same list object on every call and after
  `namelist()`, which is a new list each time. `getinfo()` is timed at 100
  and 100,000 members and asserted to stay within 3x; `namelist()` over the
  same pair is asserted above 100x.
* `open()` reads fewer than 1,000 bytes of a 4 MB member. `read()` peaks
  above the member's 4 MB; reading the same member in 4,096-byte chunks peaks
  under 256 KB, stored and deflated. `readline()` on one line of 10,000 and
  1,000,000 bytes is timed: 100x the line costs under 400x, where a
  quadratic scan would cost about 10,000x.
* `seek()` on a stored member reads no bytes forward or backward on 3.12+;
  before 3.12 it reads at least the distance. On a deflated, incompressible
  4 MB member a forward seek of 3 MB reads at least 3 MB, and a backward seek
  to 1 MB reads at least 1 MB, so it restarts from the start; a backward seek
  of five bytes within what the last read buffered reads nothing.
* `write(filename)` of a 20 MB file to an archive on disk peaks under 1 MB,
  stored and deflated. Writing 20 MB through `open(name, 'w')` in 64 KiB
  pieces peaks under 1 MB. `writestr()` of a 4 MB `str` peaks above 4 MB,
  and of the same bytes, stored, under 64 KB: the encoded copy is the `str`
  case's cost. A member written through `open(name, 'w')` is absent from
  `namelist()` until its stream closes.
* `extract()` of a 20 MB member and `testzip()` over it peak under 4 MB.
  `extractall()` without `members` calls `namelist()` once and creates
  missing parent directories. `testzip()` returns `None` for a sound archive
  and, with the second and third of three members altered, the second's name.
  With two entries under one name, altering the first leaves `testzip()`
  returning `None`, and altering the last makes it return the name.
* `is_zipfile()` reads the same number of bytes, under 1,000, from archives of
  10 and 10,000 members, and the same from one whose members hold 1 MB each;
  on 3.14+ it restores a file object's position. It is `False` for other
  data.
* `ZipInfo.from_file()` succeeds with the built-in `open` replaced by one that
  raises, so it does not read the file. `ZipInfo` fields are asserted against
  what was written. `ZipInfo.compress_level` is asserted on 3.13+ to be the
  archive's `compresslevel`, and `ZipInfo._for_archive()` on 3.14+ to copy
  the archive's compression.
* `zipfile.Path` builds its name index once for a read-mode archive across
  many `exists()`, `is_file()` and `joinpath()` calls, and once per call on a
  writable one; the index-building helper is counted. Five `iterdir()` calls
  build no name list on a read-mode archive whose index exists, and five on a
  writable one. `iterdir()` on a directory of 20 entries, and `glob()` for a
  pattern with one match, are handed a counting iterable in place of the name
  list of 210 names and take every name. `is_dir()` is asserted to
  follow a trailing slash, and `joinpath()` to add one only for a directory in
  the archive. A read-mode `ZipFile` given to `Path` is asserted to return
  the same `namelist()` object afterwards, with implied directories in it.
  Version-gated attributes are asserted on the versions that have them;
  `is_symlink()` on an entry with symlink mode bits is `False` on 3.12 and
  `True` from 3.13.
* `PyZipFile.writepy()` on a package with a subpackage adds one `.pyc` per
  module, recursively.
* The exception aliases are asserted identical, `ZIP_STORED` the default,
  `LargeZipFile` raised for a ZIP64-sized member with `allowZip64=False`, and
  `BadZipFile` for other data and for a failed CRC. `ZIP_ZSTANDARD` is
  asserted on 3.14+.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* `PyZipFile.writepy()` is priced O(e log e + s) time and O(e + s) space by
  reading Lib/zipfile/__init__.py: each directory is listed and sorted, and each
  module's `.pyc` is written by `write()`. Compilation by `py_compile` is left
  out of the bound, as the page says, and is not measured.
* `testzip()` is priced O(n + t) from source: one `open()` per entry plus
  its data. Only the data term's memory is measured.
* Only archives without an archive comment are measured. With a comment,
  opening and `is_zipfile()` search up to 64 KiB at the end of the file for
  the end record, a bounded read the page folds into O(1).
* Opening sorts the members by header offset to bound each one's data. The
  sort is linear on a central directory already in offset order, which is
  what `zipfile` and ordinary tools write; only such archives are measured.
* `ZipExtFile.read1()` and `peek()` take `read()`'s bound from
  Lib/zipfile/__init__.py: `peek()` calls `read()`, and `read1()` the same
  decompression step `read()` loops over. They are not measured separately.
* Encrypted members, ZIP64 archives, `ZIP_BZIP2`, `ZIP_LZMA` and
  `ZIP_ZSTANDARD` data, non-seekable output streams and long member names are
  not varied. Names and directory depth are held short, as the page's cost
  model assumes.
* `zipfile.CompleteDirs`, `zipfile.LZMACompressor`,
  `zipfile.LZMADecompressor`, `zipfile.compressor_names` and `zipfile.main`
  are internals or the command line, outside the documented API, and are not
  priced; nor are the undocumented attributes `ZipFile.fp`,
  `ZipInfo.FileHeader`, `ZipInfo.orig_filename`, `ZipInfo.compress_level` and
  `ZipExtFile.raw`. The page audit lists `ZipInfo._for_archive` as documented
  but unresolved; the method exists on 3.14, and its row is tested above.
"""

from __future__ import annotations

import builtins
import io
import os
import pathlib
import random
import re
import stat
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
import zipfile
from collections.abc import Callable, Iterator
from typing import Any, Literal

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "zipfile.md"
EXPECTED_BLOCKS = 11


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


class CountingBytesIO(io.BytesIO):
    """A BytesIO that counts the bytes read from it and written to it."""

    bytes_read = 0
    bytes_written = 0

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        self.bytes_read += len(data)
        return data

    def write(self, data: Any) -> int:
        written = super().write(data)
        self.bytes_written += written
        return written


class CountingIterable:
    """An iterable over names that records how many were taken."""

    def __init__(self, names: list[str]) -> None:
        self._names = names
        self.taken = 0

    def __iter__(self) -> Iterator[str]:
        for name in self._names:
            self.taken += 1
            yield name


def archive_bytes(members: int, size: int = 10, compression: int = zipfile.ZIP_STORED) -> bytes:
    """An archive of `members` entries of `size` bytes each, spread over ten folders."""
    buffer = io.BytesIO()
    payload = b"x" * size
    with zipfile.ZipFile(buffer, "w", compression) as archive:
        for index in range(members):
            archive.writestr(f"d{index % 10}/f{index}.txt", payload)
    return buffer.getvalue()


def random_bytes(size: int) -> bytes:
    return random.Random(size).randbytes(size)


class TestOpeningReadsTheDirectory:
    """`ZipFile(file, 'r')` | O(n) | O(n), and no member data.

    Bytes read are counted, so "the directory" and "the data" separate by
    orders of magnitude with no tolerance.
    """

    @staticmethod
    def _bytes_read_opening(data: bytes, mode: Literal["r", "w", "a"] = "r") -> int:
        source = CountingBytesIO(data)
        zipfile.ZipFile(source, mode)
        return source.bytes_read

    def test_member_size_does_not_change_what_opening_reads(self) -> None:
        small = self._bytes_read_opening(archive_bytes(10, size=10))
        large = self._bytes_read_opening(archive_bytes(10, size=1_000_000))

        assert small == large, f"opening read {small} bytes for 10 B members, {large} for 1 MB"

    def test_opening_reads_the_directory_of_every_member(self) -> None:
        few = self._bytes_read_opening(archive_bytes(100))
        many = self._bytes_read_opening(archive_bytes(10_000))

        assert many > few * 50, f"100x the members read {few} then {many} bytes"

    def test_opening_holds_one_entry_per_member(self) -> None:
        few, many = archive_bytes(100), archive_bytes(10_000)

        few_peak = peak_bytes(lambda: zipfile.ZipFile(io.BytesIO(few)))
        many_peak = peak_bytes(lambda: zipfile.ZipFile(io.BytesIO(many)))

        assert many_peak > few_peak * 20, f"100x the members peaked {few_peak} then {many_peak}"
        assert len(zipfile.ZipFile(io.BytesIO(many)).infolist()) == 10_000

    def test_write_mode_reads_nothing_and_truncates(self, tmp_path: pathlib.Path) -> None:
        assert self._bytes_read_opening(archive_bytes(10_000), "w") == 0

        path = tmp_path / "existing.zip"
        path.write_bytes(archive_bytes(100))
        zipfile.ZipFile(path, "w").close()

        assert zipfile.ZipFile(path).namelist() == []

    def test_append_mode_reads_the_directory(self) -> None:
        few = self._bytes_read_opening(archive_bytes(100), "a")
        many = self._bytes_read_opening(archive_bytes(10_000), "a")

        assert many > few * 50, f"100x the members read {few} then {many} bytes in 'a'"


class TestClosingWritesTheDirectory:
    """`ZipFile.close()` | O(n) | O(1): the whole central directory after a change.

    Bytes written by `close()` alone are counted.
    """

    @staticmethod
    def _close_after_adding_one(existing: int) -> tuple[int, bytes, bytes]:
        before = archive_bytes(existing)
        target = CountingBytesIO(before)
        archive = zipfile.ZipFile(target, "a")
        archive.writestr("new.txt", b"new")
        target.bytes_written = 0
        archive.close()
        return target.bytes_written, before, target.getvalue()

    @pytest.mark.parametrize("few", [10, 100])
    def test_close_writes_every_members_entry(self, few: int) -> None:
        small, _, _ = self._close_after_adding_one(few)
        large, _, _ = self._close_after_adding_one(few * 100)

        assert large > small * 50, f"100x the members: close() wrote {small} then {large}"

    def test_appending_leaves_member_data_alone(self) -> None:
        _, before, after = self._close_after_adding_one(1_000)
        directory_start = before.index(b"PK\x01\x02")

        assert after[:directory_start] == before[:directory_start]
        assert zipfile.ZipFile(io.BytesIO(after)).namelist()[-1] == "new.txt"

    def test_an_unchanged_archive_writes_nothing(self) -> None:
        for mode in ("r", "a"):
            target = CountingBytesIO(archive_bytes(100))
            zipfile.ZipFile(target, mode).close()

            assert target.bytes_written == 0, f"close() in {mode!r} wrote {target.bytes_written}"

    def test_a_read_mode_comment_is_not_written(self) -> None:
        target = CountingBytesIO(archive_bytes(100))
        archive = zipfile.ZipFile(target)
        archive.comment = b"note"
        archive.close()

        assert target.bytes_written == 0
        assert zipfile.ZipFile(target).comment == b""

    def test_assigning_the_comment_rewrites_the_directory(self) -> None:
        target = CountingBytesIO(archive_bytes(100))
        archive = zipfile.ZipFile(target, "a")
        archive.comment = b"note"
        archive.close()

        assert target.bytes_written > 100 * 46
        assert zipfile.ZipFile(target).comment == b"note"


class TestListingAndLookup:
    """`namelist()` O(n), `infolist()` O(1), `getinfo()` O(1)."""

    def test_infolist_is_the_archives_own_list(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(100)))
        first = archive.infolist()

        assert archive.namelist() is not archive.namelist(), "namelist() is a new list"
        assert archive.infolist() is first
        assert peak_bytes(archive.infolist) < 1_000

    def test_getinfo_raises_key_error_for_a_missing_name(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(10)))

        assert archive.getinfo("d3/f3.txt").filename == "d3/f3.txt"
        with pytest.raises(KeyError, match="missing"):
            archive.getinfo("missing")

    @pytest.mark.timing
    def test_getinfo_does_not_grow_with_the_archive_and_namelist_does(self) -> None:
        few = zipfile.ZipFile(io.BytesIO(archive_bytes(100)))
        many = zipfile.ZipFile(io.BytesIO(archive_bytes(100_000)))

        lookup_few = best_ns(lambda: few.getinfo("d5/f55.txt"), inner=1_000)
        lookup_many = best_ns(lambda: many.getinfo("d5/f55.txt"), inner=1_000)
        list_few = best_ns(few.namelist, inner=100)
        list_many = best_ns(many.namelist, inner=3)

        assert lookup_many < lookup_few * 3, (
            f"getinfo cost {lookup_few:.0f}ns then {lookup_many:.0f}ns for 1,000x the members"
        )
        assert list_many > list_few * 100, (
            f"namelist cost {list_few:.0f}ns then {list_many:.0f}ns for 1,000x the members"
        )


class TestReadingMembers:
    """`open()` O(1), `read()` O(m) memory, a chunked stream O(k) memory."""

    SIZE = 4_000_000

    def _archive(self, compression: int) -> tuple[CountingBytesIO, bytes]:
        payload = random_bytes(self.SIZE)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression) as archive:
            archive.writestr("member", payload)
        return CountingBytesIO(buffer.getvalue()), payload

    def test_open_reads_only_the_local_header(self) -> None:
        source, _ = self._archive(zipfile.ZIP_DEFLATED)
        archive = zipfile.ZipFile(source)
        source.bytes_read = 0

        with archive.open("member"):
            opened = source.bytes_read

        assert opened < 1_000, f"open() read {opened} bytes of a {self.SIZE}-byte member"

    @pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
    def test_read_holds_the_member_and_a_stream_holds_a_chunk(self, compression: int) -> None:
        source, payload = self._archive(compression)
        archive = zipfile.ZipFile(source)

        def stream() -> None:
            with archive.open("member") as handle:
                while handle.read(4096):
                    pass

        whole = peak_bytes(lambda: archive.read("member"))
        chunked = peak_bytes(stream)

        assert whole > self.SIZE, f"read() peaked at {whole} for a {self.SIZE}-byte member"
        assert chunked < 256_000, f"a 4,096-byte chunk loop peaked at {chunked}"
        assert archive.read("member") == payload

    @pytest.mark.timing
    @pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
    def test_readline_is_linear_in_the_line(self, compression: int) -> None:
        def cost(length: int) -> float:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression) as archive:
                archive.writestr("line", b"a" * length + b"\n")
            archive = zipfile.ZipFile(buffer)

            def one_line() -> None:
                with archive.open("line") as handle:
                    assert len(handle.readline()) == length + 1

            return best_ns(one_line)

        short, long = cost(10_000), cost(1_000_000)

        assert long < short * 400, (
            f"100x the line cost {short:.0f}ns then {long:.0f}ns; linear is ~100x"
        )


class TestSeeking:
    """`ZipExtFile.seek()` | O(1) stored (3.12+), O(d) compressed.

    Bytes read from the archive during each seek are counted.
    """

    SIZE = 4_000_000

    def _seek_reads(self, compression: int) -> tuple[int, int]:
        payload = random_bytes(self.SIZE)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression) as archive:
            archive.writestr("member", payload)
        source = CountingBytesIO(buffer.getvalue())
        with zipfile.ZipFile(source).open("member") as handle:
            handle.read(10)
            source.bytes_read = 0
            handle.seek(3_000_000)
            forward = source.bytes_read
            source.bytes_read = 0
            handle.seek(1_000_000)
            backward = source.bytes_read
            assert handle.read(4) == payload[1_000_000:1_000_004]
        return forward, backward

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="fast stored seek is 3.12+")
    def test_a_stored_member_seeks_without_reading(self) -> None:
        assert self._seek_reads(zipfile.ZIP_STORED) == (0, 0)

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="3.12+ seeks stored members")
    def test_a_stored_member_reads_through_before_3_12(self) -> None:
        forward, backward = self._seek_reads(zipfile.ZIP_STORED)

        assert forward >= 2_990_000
        assert backward >= 1_000_000

    def test_a_compressed_member_decompresses_what_it_skips(self) -> None:
        forward, backward = self._seek_reads(zipfile.ZIP_DEFLATED)

        assert forward >= 3_000_000, f"a 3 MB forward seek read {forward} bytes"
        assert backward >= 1_000_000, f"a backward seek to 1 MB read {backward} bytes"

    def test_a_backward_seek_inside_the_buffer_reads_nothing(self) -> None:
        payload = random_bytes(100_000)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("member", payload)
        source = CountingBytesIO(buffer.getvalue())
        with zipfile.ZipFile(source).open("member") as handle:
            handle.read(10)
            source.bytes_read = 0
            handle.seek(5)

            assert source.bytes_read == 0
            assert handle.read(5) == payload[5:10]


class TestWriting:
    """`write()` streams, `writestr()` holds the data, `open(name, 'w')` streams."""

    SIZE = 20_000_000

    @pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
    def test_write_streams_a_file_from_disk(self, tmp_path: pathlib.Path, compression: int) -> None:
        source = tmp_path / "source.bin"
        source.write_bytes(random_bytes(self.SIZE))

        with zipfile.ZipFile(tmp_path / "out.zip", "w", compression) as archive:
            peak = peak_bytes(lambda: archive.write(source, "member"))

        assert peak < 1_000_000, f"write() of a {self.SIZE}-byte file peaked at {peak}"
        assert zipfile.ZipFile(tmp_path / "out.zip").getinfo("member").file_size == self.SIZE

    @pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
    def test_a_write_stream_holds_one_piece(self, tmp_path: pathlib.Path, compression: int) -> None:
        payload = random_bytes(self.SIZE)
        pieces = [payload[start : start + 65_536] for start in range(0, self.SIZE, 65_536)]

        with zipfile.ZipFile(tmp_path / "out.zip", "w", compression) as archive:

            def stream() -> None:
                with archive.open("member", "w") as handle:
                    for piece in pieces:
                        handle.write(piece)

            peak = peak_bytes(stream)

        assert peak < 1_000_000, f"streaming {self.SIZE} bytes peaked at {peak}"

    def test_a_str_is_encoded_to_a_copy(self, tmp_path: pathlib.Path) -> None:
        text = "x" * 4_000_000
        data = text.encode()

        with zipfile.ZipFile(tmp_path / "out.zip", "w") as archive:
            text_peak = peak_bytes(lambda: archive.writestr("text", text))
            bytes_peak = peak_bytes(lambda: archive.writestr("bytes", data))

        assert text_peak > 4_000_000, f"writestr(str) peaked at {text_peak}"
        assert bytes_peak < 64_000, f"writestr(bytes), stored, peaked at {bytes_peak}"

    def test_a_write_stream_joins_the_directory_when_closed(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(), "w")
        handle = archive.open("member", "w")
        handle.write(b"data")

        assert archive.namelist() == []
        handle.close()
        assert archive.namelist() == ["member"]

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="ZipFile.mkdir is 3.11+")
    def test_mkdir_adds_an_empty_directory_entry(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            maker: Any = archive
            maker.mkdir("folder")

        info = zipfile.ZipFile(buffer).getinfo("folder/")
        assert info.is_dir() and info.file_size == 0

    def test_a_duplicate_name_is_a_second_entry(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("name", b"first")
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr("name", b"second")

        archive = zipfile.ZipFile(buffer)
        assert archive.namelist() == ["name", "name"]
        assert archive.read("name") == b"second"


class TestExtractingAndTesting:
    """`extract()` O(m) time, O(1) memory; `extractall()` O(n) memory; `testzip()`."""

    SIZE = 20_000_000

    def _big_archive(self, tmp_path: pathlib.Path) -> zipfile.ZipFile:
        path = tmp_path / "big.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("member", random_bytes(self.SIZE))
        return zipfile.ZipFile(path)

    def test_extract_and_testzip_stream(self, tmp_path: pathlib.Path) -> None:
        archive = self._big_archive(tmp_path)
        out = tmp_path / "out"

        extract_peak = peak_bytes(lambda: archive.extract("member", out))
        test_peak = peak_bytes(archive.testzip)

        assert extract_peak < 4_000_000, f"extract() peaked at {extract_peak}"
        assert test_peak < 4_000_000, f"testzip() peaked at {test_peak}"
        assert (out / "member").stat().st_size == self.SIZE

    def test_extractall_takes_one_namelist_and_makes_directories(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(50)))
        calls: list[int] = []
        original = zipfile.ZipFile.namelist

        def counting(self: zipfile.ZipFile) -> list[str]:
            calls.append(1)
            return original(self)

        monkeypatch.setattr(zipfile.ZipFile, "namelist", counting)
        archive.extractall(tmp_path)

        assert calls == [1]
        assert len(list(tmp_path.rglob("*.txt"))) == 50
        assert (tmp_path / "d3" / "f13.txt").read_bytes() == b"x" * 10

    @staticmethod
    def _corrupt(data: bytearray, info: zipfile.ZipInfo) -> None:
        """Flip the first data byte of a stored member."""
        data[info.header_offset + 30 + len(info.filename)] ^= 0xFF

    def test_testzip_names_the_first_bad_member(self) -> None:
        data = bytearray(archive_bytes(3, size=100))
        assert zipfile.ZipFile(io.BytesIO(bytes(data))).testzip() is None

        infos = zipfile.ZipFile(io.BytesIO(bytes(data))).infolist()
        self._corrupt(data, infos[2])
        self._corrupt(data, infos[1])

        assert zipfile.ZipFile(io.BytesIO(bytes(data))).testzip() == "d1/f1.txt"
        with pytest.raises(zipfile.BadZipFile, match="CRC"):
            zipfile.ZipFile(io.BytesIO(bytes(data))).read("d2/f2.txt")

    def test_testzip_checks_only_the_last_duplicate(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive, warnings.catch_warnings():
            warnings.simplefilter("ignore")
            archive.writestr("name", b"a" * 100)
            archive.writestr("name", b"b" * 100)
        data = bytearray(buffer.getvalue())

        first, last = zipfile.ZipFile(io.BytesIO(bytes(data))).infolist()
        self._corrupt(data, first)
        assert zipfile.ZipFile(io.BytesIO(bytes(data))).testzip() is None

        self._corrupt(data, last)
        assert zipfile.ZipFile(io.BytesIO(bytes(data))).testzip() == "name"


class TestIsZipfileReadsTheEnd:
    """`zipfile.is_zipfile(filename)` | O(1) | O(1): the end record, not the members."""

    @staticmethod
    def _read_by_check(data: bytes) -> tuple[bool, int]:
        source = CountingBytesIO(data)
        source.seek(5)
        result = zipfile.is_zipfile(source)
        if sys.version_info >= (3, 14):
            assert source.tell() == 5, "is_zipfile moved the file position"
        return result, source.bytes_read

    def test_the_bytes_read_do_not_depend_on_the_archive(self) -> None:
        few = self._read_by_check(archive_bytes(10))
        many = self._read_by_check(archive_bytes(10_000))
        large = self._read_by_check(archive_bytes(10, size=1_000_000))

        assert few == many == large, f"read {few}, {many} and {large}"
        assert few[0] is True and few[1] < 1_000

    def test_other_data_is_not_a_zip_file(self) -> None:
        assert self._read_by_check(b"not an archive" * 100)[0] is False


class TestZipInfo:
    """`ZipInfo` construction, `from_file()`, `is_dir()` and parsed fields: O(1)."""

    def test_from_file_does_not_open_the_file(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "file.bin"
        path.write_bytes(b"x" * 1_000)

        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("from_file opened the file")

        monkeypatch.setattr(builtins, "open", refuse)
        monkeypatch.setattr(io, "open", refuse)
        info = zipfile.ZipInfo.from_file(path, "file.bin")

        assert info.file_size == 1_000
        assert not info.is_dir()
        assert zipfile.ZipInfo("folder/").is_dir()

    def test_fields_come_from_the_directory(self) -> None:
        info = zipfile.ZipInfo("member.txt", date_time=(2020, 5, 17, 12, 30, 10))
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(info, b"hello" * 100, compress_type=zipfile.ZIP_DEFLATED)

        parsed = zipfile.ZipFile(buffer).getinfo("member.txt")
        assert parsed.date_time == (2020, 5, 17, 12, 30, 10)
        assert parsed.file_size == 500
        assert parsed.compress_type == zipfile.ZIP_DEFLATED
        assert parsed.compress_size < parsed.file_size
        assert parsed.header_offset == 0

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="compress_level is 3.13+")
    def test_compress_level_is_the_level_written_with(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("member", b"x" * 100)
            written: Any = archive.infolist()[0]

        assert written.compress_level == 9

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="_for_archive is 3.14+")
    def test_for_archive_takes_the_archives_compression(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(), "w", zipfile.ZIP_DEFLATED, compresslevel=3)
        info: Any = zipfile.ZipInfo("name")

        assert info._for_archive(archive) is info
        assert info.compress_type == zipfile.ZIP_DEFLATED
        assert info.compress_level == 3


class TestPathIndexesOnce:
    """`zipfile.Path` lookups | O(n) first, then O(1); `iterdir()` and `glob()` O(n).

    The helper that lists implied directories is counted, and a counting
    iterable stands in for the name list the scans walk.
    """

    @staticmethod
    def _archive(mode: Literal["r", "a"] = "r") -> zipfile.ZipFile:
        buffer = io.BytesIO(archive_bytes(200))
        return zipfile.ZipFile(buffer, mode)

    @staticmethod
    def _count_index_builds(monkeypatch: pytest.MonkeyPatch) -> list[int]:
        path_module: Any = sys.modules[zipfile.Path.__module__]
        builds: list[int] = []
        original = path_module.CompleteDirs._implied_dirs

        def counting(names: Any) -> Any:
            builds.append(1)
            return original(names)

        monkeypatch.setattr(path_module.CompleteDirs, "_implied_dirs", staticmethod(counting))
        return builds

    def test_a_read_mode_archive_is_indexed_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        builds = self._count_index_builds(monkeypatch)
        root = zipfile.Path(self._archive())

        assert builds == []
        for index in range(50):
            assert (root / f"d{index % 10}" / f"f{index}.txt").is_file()
            assert (root / f"d{index % 10}").exists()

        assert len(builds) == 1, f"{len(builds)} index builds over 150 lookups"

    def test_a_writable_archive_is_indexed_on_every_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        builds = self._count_index_builds(monkeypatch)
        root = zipfile.Path(self._archive("a"))

        for index in range(10):
            assert (root / f"d{index}").exists()

        assert len(builds) >= 20, f"{len(builds)} index builds over 10 joins and 10 checks"

    def test_iterdir_reuses_the_read_mode_name_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        builds = self._count_index_builds(monkeypatch)
        folder = zipfile.Path(self._archive()) / "d3"
        builds.clear()

        for _ in range(5):
            assert len(list(folder.iterdir())) == 20

        assert builds == [], f"{len(builds)} name-list builds over 5 iterdir() calls"

    def test_iterdir_rebuilds_the_name_list_when_writable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        builds = self._count_index_builds(monkeypatch)
        folder = zipfile.Path(self._archive("a")) / "d3"
        builds.clear()

        for _ in range(5):
            assert len(list(folder.iterdir())) == 20

        assert len(builds) == 5, f"{len(builds)} name-list builds over 5 iterdir() calls"

    def test_iterdir_takes_every_name_for_a_small_directory(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(200)))
        folder = zipfile.Path(archive) / "d3"
        names = CountingIterable(list(archive.namelist()))
        wrapped: Any = folder.root
        wrapped.namelist = lambda: names

        children = list(folder.iterdir())

        assert len(children) == 20
        assert names.taken == len(names._names) > 200

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="Path.glob is 3.12+")
    def test_glob_takes_every_name(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(200)))
        root: Any = zipfile.Path(archive)
        names = CountingIterable(list(archive.namelist()))
        root.root.namelist = lambda: names

        matches = root.glob("d3/f3.txt")

        assert names.taken == 0, "glob() is lazy"
        assert [match.at for match in matches] == ["d3/f3.txt"]
        assert names.taken == len(names._names)

    def test_is_dir_follows_the_trailing_slash(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(20)))
        root = zipfile.Path(archive)

        assert (root / "d1").at == "d1/"
        assert (root / "d1").is_dir()
        assert (root / "absent").at == "absent"
        assert not (root / "absent").is_dir()
        absent_folder = zipfile.Path(archive, "absent/")
        assert absent_folder.is_dir() and not absent_folder.exists()

    def test_a_read_mode_zipfile_starts_caching(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(20)))
        assert archive.namelist() is not archive.namelist()

        zipfile.Path(archive)

        assert isinstance(archive, zipfile.ZipFile) and type(archive) is not zipfile.ZipFile
        assert archive.namelist() is archive.namelist()
        assert "d1/" in archive.namelist()

    def test_a_filename_is_opened(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.zip"
        path.write_bytes(archive_bytes(20))
        root = zipfile.Path(path)

        assert isinstance(root.root, zipfile.ZipFile)
        assert (root / "d2" / "f12.txt").read_bytes() == b"x" * 10
        assert (root / "d2" / "f12.txt").read_text(encoding="utf-8") == "x" * 10
        assert root.joinpath("d2").name == "d2"
        parent: Any = (root / "d2" / "f12.txt").parent
        assert parent.at == "d2/"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="stem and suffixes are 3.11+")
    def test_name_parts(self) -> None:
        member: Any = zipfile.Path(zipfile.ZipFile(io.BytesIO(archive_bytes(20))), "d2/f12.txt")

        assert (member.stem, member.suffix, member.suffixes) == ("f12", ".txt", [".txt"])

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="match, relative_to, is_symlink 3.12+")
    def test_string_only_operations(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.zip"
        path.write_bytes(archive_bytes(20))
        root: Any = zipfile.Path(path)
        member = root / "d2" / "f12.txt"

        assert member.match("*.txt")
        assert member.relative_to(root / "d2") == "f12.txt"
        assert member.is_symlink() is False

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="is_symlink is 3.12+")
    def test_is_symlink_reads_the_mode_bits_from_3_13(self) -> None:
        link = zipfile.ZipInfo("link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(link, b"target")
        member: Any = zipfile.Path(zipfile.ZipFile(buffer), "link")

        assert member.is_symlink() is (sys.version_info >= (3, 13))


class TestPyZipFile:
    """`PyZipFile.writepy()` adds a compiled module per source, recursively."""

    def test_a_package_is_added_recursively(self, tmp_path: pathlib.Path) -> None:
        package = tmp_path / "pkg"
        (package / "sub").mkdir(parents=True)
        for relative in ("__init__.py", "mod.py", "sub/__init__.py", "sub/leaf.py"):
            (package / relative).write_text("VALUE = 1\n", encoding="utf-8")

        buffer = io.BytesIO()
        with zipfile.PyZipFile(buffer, "w") as archive:
            archive.writepy(str(package))

        names = sorted(zipfile.ZipFile(buffer).namelist())
        assert names == [
            "pkg/__init__.pyc",
            "pkg/mod.pyc",
            "pkg/sub/__init__.pyc",
            "pkg/sub/leaf.pyc",
        ]


class TestConstantsAndExceptions:
    """Compression constants, the `BadZipFile` aliases and `LargeZipFile`."""

    def test_the_aliases_are_one_class(self) -> None:
        legacy: Any = zipfile

        assert zipfile.error is zipfile.BadZipFile
        assert legacy.BadZipfile is zipfile.BadZipFile

    def test_stored_is_the_default(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("member", b"x" * 1_000)

        assert archive.compression == zipfile.ZIP_STORED
        assert zipfile.ZipFile(buffer).getinfo("member").compress_type == zipfile.ZIP_STORED

    def test_the_methods_are_distinct(self) -> None:
        methods = {
            zipfile.ZIP_STORED,
            zipfile.ZIP_DEFLATED,
            zipfile.ZIP_BZIP2,
            zipfile.ZIP_LZMA,
        }
        assert len(methods) == 4

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="ZIP_ZSTANDARD is 3.14+")
    def test_zstandard_is_a_method(self) -> None:
        module: Any = zipfile

        assert module.ZIP_ZSTANDARD == 93

    def test_large_zip_file_without_zip64(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(), "w", allowZip64=False)
        info = zipfile.ZipInfo("huge")
        info.file_size = zipfile.ZIP64_LIMIT + 1

        with pytest.raises(zipfile.LargeZipFile):
            archive.open(info, "w")

    def test_other_data_is_a_bad_zip_file(self) -> None:
        with pytest.raises(zipfile.BadZipFile):
            zipfile.ZipFile(io.BytesIO(b"not an archive" * 100))

    def test_printdir_writes_a_line_per_member(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(25)))
        out = io.StringIO()
        archive.printdir(out)

        assert len(out.getvalue().splitlines()) == 26

    def test_setpassword_sets_the_default(self) -> None:
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes(1)))
        archive.setpassword(b"secret")

        assert archive.pwd == b"secret"


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
    its own result; the blocks that touch disk do so under a temporary
    directory they create."""

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
        line, source = next((n, s) for n, s in _blocks() if "payload[10:13]" in s)
        mutated = source.replace("payload[10:13]", "payload[11:14]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
