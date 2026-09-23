"""Tests for docs/stdlib/tarfile.md.

The page prices a tar archive as what it is: a sequence of header blocks, each
followed by its data, with no index. Nearly every claim is settled by
observation rather than time. A `BytesIO` that counts the bytes read from it
shows which operations touch headers only and which pass through member data,
a `TarInfo` subclass that counts reads of `name` shows how much of the member
list a lookup scans, identity shows what is cached, and a traced allocation
peak separates chunked copies from whole-member reads by orders of magnitude.

Measurement scope:

* Opening with mode `'r:'` reads exactly one 512-byte block. Opening with
  `'r'` or `'r:'` reads the same number of bytes from archives of 200 and
  20,000 members of 1 KiB, under 2% of the larger: `'r'` tries each
  decompressor first, and each reads a fixed-size buffer. `'r:gz'` reads under
  64 KiB of a 2,000-member compressed archive. `is_tarfile()` reads under
  400 KiB of a 3 MB archive and returns `False`
  for 1,400 bytes of text; it restores a file object's position on 3.11+ and
  leaves it moved on 3.10. Appending (`'a'`) to an archive of 200 members of
  64 KiB reads every header, at least 200 x 512 bytes and under 2% of the
  archive, and a following `getmembers()` reads nothing more and returns all
  200.
* `getmembers()` on a plain seekable archive reads the same number of bytes
  whether its 200 members hold 1 KiB or 256 KiB each, at least one 512-byte
  block per member and under 2% of the larger archive. Through gzip, bzip2,
  lzma and, on 3.14 when `compression.zstd` imports, Zstandard, it reads over
  99% of the compressed file. It returns the same list on every call; `getnames()`
  returns a new, equal list each time.
* `getmember()` reads a member's `name` once per member it passes. Looking up
  the first of 500 and of 5,000 members reads at least 500 and 5,000 names, a
  second lookup of the same name reads exactly as many, and looking up the last
  member reads fewer than 5. With a duplicated name, the later member is
  returned.
* Iterating a `'r|'` stream of 2,000 members leaves `getmembers()` returning
  those same 2,000 objects, by identity, without reading more. On 3.13+,
  `stream=True` leaves it empty in both `'r:gz'` and `'r|gz'` modes, and
  `extractall()` still extracts every member. `next()` on a plain archive
  reads the same bytes whether the member it passes holds 1 KiB or 1 MiB;
  through gzip it reads at least the compressed size of the 1 MiB member.
* `extractfile(tarinfo)` reads no bytes until the reader is read, and then
  reads the member's size; `extractfile(name)` reads every header first.
  Reading 8 MiB in 64 KiB pieces peaks under 1 MiB of traced allocation, and
  `read()` peaks over 8 MiB. After loading a 200-member gzip archive of 64 KiB
  random members, reading the last member reads over 90% of the compressed
  file again and reading the first reads under 10%; the same reads on a plain
  archive read 64 KiB each. Iterating a 200-member gzip archive and reading
  each member as it arrives reads the compressed file at most 1.05 times. In a
  `'r|gz'` stream, reading a member the
  archive has passed raises `StreamError`. A directory has no reader.
* `extract()` of an 8 MiB member peaks under 1 MiB of traced allocation, and
  no single read of the archive exceeds 64 KiB. `extractall()` of a
  200-member gzip archive reads the compressed file at most 1.05 times;
  extracting the same members in reverse order reads it over 50 times.
  A directory member with mode 0o555 and an old mtime is extracted with its
  file inside it, and ends with that mode and mtime.
* `errorlevel` is observed with a filter that raises: an `ExtractError` is
  skipped at level 1 and raised at level 2, and a `FilterError` is skipped at
  level 0 and raised at level 1. `extraction_filter` set on an instance is
  called when a call passes none. With neither, extracting `../escape.txt`
  raises `OutsideDestinationError` on 3.14+, warns and writes it on 3.12 and
  3.13, and writes it silently on 3.10 and 3.11.
* The three filters are asserted by what they reject and rewrite: `..`
  escapes, absolute and escaping links and device files for `data_filter`;
  high and group/other write bits for `tar_filter`, which keeps ownership and
  devices; a leading `/` stripped by both; and identity for
  `fully_trusted_filter`. `FilterError.tarinfo` is the rejected member.
* `addfile()` copying an 8 MiB file object reads it in pieces of at most
  64 KiB and peaks under 1 MiB; on 3.13+ it raises `ValueError` for a
  non-empty regular file with no file object, and earlier versions accept it
  and list the member. `add()` of a directory whose files were created in reverse
  name order stores them sorted, and `recursive=False` stores the directory
  alone. Members written in `'w'` mode are listed by `getmembers()`.
  `gettarinfo()` is asserted by the size and type it reports from a path and
  from a file object. Global pax headers passed in `PAX_FORMAT` are written as
  the first block (type `g`) and read back into `pax_headers`.
* `close()` in a writing mode leaves an archive whose length is a multiple of
  10,240 bytes and that ends in two zero blocks. Round trips cover `gz`,
  `bz2` and `xz`, and `zst` on 3.14 when `compression.zstd` imports.
* `TarInfo`: `tobuf()` is 512 bytes for a short USTAR name and a larger
  multiple of 512 for a 204-character PAX name; `frombuf()` round-trips it and
  raises `HeaderError` for a corrupted checksum and an empty buffer;
  `fromtarfile()` reads the next header, long name included, from an open
  archive; `replace()` shares `pax_headers` when shallow and copies it when
  deep; each `is*()` predicate is asserted against the type constants.
* `list()` prints one name per member with `verbose=False`, only the given
  members with `members=`, and an `ls -l` style line with `verbose=True`.
* Exceptions are asserted by their hierarchy and by the calls that raise
  them: `ReadError` for bytes that are not an archive, `CompressionError` for
  an unknown compression. That it is also raised when a compression module is
  missing from the build is taken from the official documentation.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* Pricing a header, and a filter's path resolution, at O(1) is the page's
  cost model. A long name adds pax or GNU blocks in proportion to its length,
  and the filters call `os.path.realpath()`, which touches the filesystem
  once per path component.
* The `d log d` term of `extractall()` is the sort of directory members by
  name in Lib/tarfile.py, and the `e log e` term of `add()` the sort of each
  `os.listdir()` result. The tests observe that the sort happens, not its cost.
* `gettarinfo()` looks up user and group names through `pwd` and `grp`, whose
  cost depends on the system's name service; the tests do not time it.
* `LinkFallbackError` is raised only when creating a link fails and the
  fallback copy is rejected by the filter, which needs a platform where
  `os.symlink` fails. On Linux only its place in the hierarchy is asserted;
  forcing it by patching `os.symlink` would test the fallback, about which the
  page makes no claim.
* Directory attributes being set after the contents is observed through the
  final mode and mtime, not by recording the order of the calls.
* `AbsolutePathError` is raised only for a name that is still absolute once
  its leading slashes are stripped, such as a Windows drive path. Its test is
  guarded on `sys.platform == "win32"` and does not run on Linux.
* Sparse members, device files (creating them needs privileges) and
  non-default `encoding` and `errors` are not exercised.
* Undocumented names are not on the page: the `*open` class methods behind
  `open()`, the `make*`, `chown`, `chmod` and `utime` extraction hooks, the
  `HeaderError` subclasses, `ExFileObject`, the `create_*_header` and
  `get_info` helpers, `TarInfo.path`, `linkpath`, `issparse` and `tarfile`,
  the `TarFile` settings mirrored from constructor arguments, and the module's
  internal helpers and `main()`.
"""

from __future__ import annotations

import contextlib
import io
import os
import pathlib
import re
import subprocess
import sys
import tarfile
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable
from typing import Any, ClassVar

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tarfile.md"
EXPECTED_BLOCKS = 12

# tarfile.open() with a mode built at run time, which the stub overloads cannot type
open_tar: Callable[..., tarfile.TarFile] = tarfile.open

COMPRESSIONS = ["gz", "bz2", "xz"]
if sys.version_info >= (3, 14):
    with contextlib.suppress(ImportError):
        import compression.zstd  # noqa: F401

        COMPRESSIONS.append("zst")


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountingBytesIO(io.BytesIO):
    """A BytesIO that records how many bytes were read, and the largest read."""

    def __init__(self, data: bytes = b"") -> None:
        super().__init__(data)
        self.read_bytes = 0
        self.largest = 0

    def _count(self, size: int) -> int:
        self.read_bytes += size
        self.largest = max(self.largest, size)
        return size

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        self._count(len(data))
        return data

    def read1(self, size: int | None = -1) -> bytes:
        data = super().read1(size)
        self._count(len(data))
        return data

    def readinto(self, buffer: Any) -> int:
        return self._count(super().readinto(buffer))


class DiscardingSink:
    """A writable file object that keeps only the count of bytes written."""

    def __init__(self) -> None:
        self.written = 0

    def write(self, data: bytes) -> int:
        self.written += len(data)
        return len(data)

    def tell(self) -> int:
        return self.written


class CountingNames(tarfile.TarInfo):
    """A TarInfo that counts every read of its name."""

    reads: ClassVar[int] = 0

    @property
    def name(self) -> str:  # pyright: ignore[reportIncompatibleVariableOverride]
        CountingNames.reads += 1
        return self._name

    @name.setter
    def name(self, value: str) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        self._name = value


def build(
    count: int,
    size: int,
    mode: str = "w",
    *,
    names: Callable[[int], str] = "m{:05d}".format,
) -> bytes:
    """An archive of `count` members of `size` random bytes each."""
    payload = os.urandom(size)
    buffer = io.BytesIO()
    with open_tar(fileobj=buffer, mode=mode) as tar:
        for index in range(count):
            info = tarfile.TarInfo(names(index))
            info.size = size
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def member(name: str, kind: bytes = tarfile.REGTYPE, **attrs: Any) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    for key, value in attrs.items():
        setattr(info, key, value)
    return info


class TestOpeningReadsOneHeader:
    """`tarfile.open()` | O(1), `'a'` | O(n), and `is_tarfile()` | O(1)."""

    ARCHIVE = build(2_000, 1_024)

    @pytest.mark.parametrize("mode", ["r", "r:"])
    def test_opening_reads_the_same_whatever_the_size(self, mode: str) -> None:
        reads: dict[int, int] = {}
        for count in (200, 20_000):
            source = CountingBytesIO(build(count, 1_024))
            with open_tar(fileobj=source, mode=mode):
                pass
            reads[count] = source.read_bytes

        assert reads[200] == reads[20_000], reads
        assert reads[20_000] < 20_000 * 1_024 // 50

    def test_opening_uncompressed_reads_one_header(self) -> None:
        source = CountingBytesIO(self.ARCHIVE)

        with tarfile.open(fileobj=source, mode="r:"):
            pass

        assert source.read_bytes == 512

    def test_opening_a_compressed_archive_reads_its_start_only(self) -> None:
        compressed = build(2_000, 1_024, "w:gz")
        source = CountingBytesIO(compressed)

        with tarfile.open(fileobj=source, mode="r:gz"):
            pass

        assert source.read_bytes < 64 * 1024, (
            f"opening read {source.read_bytes} of {len(compressed)} compressed bytes"
        )

    def test_appending_reads_every_header_and_keeps_them(self) -> None:
        archive = build(200, 64 * 1024)
        source = CountingBytesIO(archive)

        with tarfile.open(fileobj=source, mode="a") as tar:
            after_open = source.read_bytes
            members = tar.getmembers()

            assert source.read_bytes == after_open, "getmembers() read more after 'a'"
            assert len(members) == 200
        assert 200 * 512 <= after_open < len(archive) * 0.02

    def test_is_tarfile_reads_the_first_header_only(self) -> None:
        source = CountingBytesIO(self.ARCHIVE)

        assert tarfile.is_tarfile(source)
        assert source.read_bytes < 400 * 1024
        assert not tarfile.is_tarfile(io.BytesIO(b"not an archive" * 100))

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="position restored from 3.11")
    def test_is_tarfile_restores_the_position(self) -> None:
        source = io.BytesIO(self.ARCHIVE)

        assert tarfile.is_tarfile(source)
        assert source.tell() == 0

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 behaviour")
    def test_is_tarfile_moves_the_position_on_310(self) -> None:
        source = io.BytesIO(self.ARCHIVE)

        assert tarfile.is_tarfile(source)
        assert source.tell() != 0

    def test_closing_pads_to_a_record_and_ends_in_two_zero_blocks(self) -> None:
        for count in range(1, 25):
            archive = build(count, 700)

            assert len(archive) % 10_240 == 0, f"{count} members gave {len(archive)} bytes"
            assert archive[-1_024:] == bytes(1_024)

    def test_the_constructor_reads_uncompressed_archives(self) -> None:
        with tarfile.TarFile(fileobj=io.BytesIO(build(3, 10))) as tar:
            assert tar.getnames() == ["m00000", "m00001", "m00002"]

        with pytest.raises(tarfile.ReadError):
            tarfile.TarFile(fileobj=io.BytesIO(build(3, 10, "w:gz")))


class TestListingWalksEveryHeader:
    """`getmembers()` | O(n) plain, O(B) compressed; then O(1) | O(n).

    A plain seekable archive is read header by header, so the bytes read do
    not change when the members grow; a compressed one is decompressed to its
    end, so nearly all of it is read.
    """

    def test_plain_listing_reads_headers_not_data(self) -> None:
        reads: dict[int, int] = {}
        lengths: dict[int, int] = {}
        for size in (1_024, 256 * 1_024):
            archive = build(200, size)
            source = CountingBytesIO(archive)
            with tarfile.open(fileobj=source, mode="r:") as tar:
                assert len(tar.getmembers()) == 200
            reads[size] = source.read_bytes
            lengths[size] = len(archive)

        assert reads[1_024] == reads[256 * 1_024], reads
        assert 200 * 512 <= reads[256 * 1_024] < lengths[256 * 1_024] * 0.02

    @pytest.mark.parametrize("compression", COMPRESSIONS)
    def test_compressed_listing_decompresses_everything(self, compression: str) -> None:
        archive = build(50, 64 * 1024, f"w:{compression}")
        source = CountingBytesIO(archive)

        with open_tar(fileobj=source, mode=f"r:{compression}") as tar:
            assert len(tar.getmembers()) == 50

        assert source.read_bytes > len(archive) * 0.99, (
            f"{compression}: listing read {source.read_bytes} of {len(archive)} bytes"
        )

    def test_getmembers_returns_the_same_list(self) -> None:
        with tarfile.open(fileobj=io.BytesIO(build(10, 1))) as tar:
            assert tar.getmembers() is tar.getmembers()

    def test_getnames_builds_a_new_list_each_call(self) -> None:
        with tarfile.open(fileobj=io.BytesIO(build(10, 1))) as tar:
            first, second = tar.getnames(), tar.getnames()

            assert first == second == [f"m{index:05d}" for index in range(10)]
            assert first is not second


class TestGetmemberScansEveryCall:
    """`getmember(name)` | O(n) on every call, not only the first.

    A counting `name` property shows how many members one lookup passes.
    """

    @staticmethod
    def names_read(count: int, lookup: str) -> tuple[int, int]:
        with tarfile.open(fileobj=io.BytesIO(build(count, 0)), tarinfo=CountingNames) as tar:
            tar.getmembers()
            CountingNames.reads = 0
            tar.getmember(lookup)
            first = CountingNames.reads
            CountingNames.reads = 0
            tar.getmember(lookup)
            return first, CountingNames.reads

    def test_looking_up_the_first_member_reads_every_name(self) -> None:
        for count in (500, 5_000):
            first, second = self.names_read(count, "m00000")

            assert first >= count, f"{count} members, {first} names read"
            assert second == first, f"a second lookup read {second} names, the first {first}"

    def test_the_scan_starts_from_the_end(self) -> None:
        first, _ = self.names_read(5_000, "m04999")

        assert first < 5

    def test_the_last_duplicate_wins(self) -> None:
        archive = build(3, 1, names=["same", "other", "same"].__getitem__)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            found = tar.getmember("same")

            assert found is tar.getmembers()[2]

    def test_an_unknown_name_raises_key_error(self) -> None:
        with tarfile.open(fileobj=io.BytesIO(build(3, 1))) as tar:
            with pytest.raises(KeyError):
                tar.getmember("missing")


class TestIterationCachesEveryHeader:
    """`next()` and iteration | O(1) per member plain, O(s) compressed | cached.

    Identity shows that the headers an iteration yields are the ones kept.
    """

    def test_a_stream_mode_still_keeps_every_header(self) -> None:
        source = CountingBytesIO(build(2_000, 10))

        with tarfile.open(fileobj=source, mode="r|") as tar:
            yielded = list(tar)
            read = source.read_bytes
            kept = tar.getmembers()

            assert source.read_bytes == read, "getmembers() read more after iterating"
            assert len(kept) == 2_000
            assert all(a is b for a, b in zip(yielded, kept, strict=True))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="stream= added in 3.13")
    @pytest.mark.parametrize("mode", ["r:gz", "r|gz"])
    def test_stream_true_keeps_nothing(self, mode: str, tmp_path: pathlib.Path) -> None:
        archive = build(100, 10, "w:gz")

        with open_tar(fileobj=io.BytesIO(archive), mode=mode, stream=True) as tar:
            assert sum(1 for _ in tar) == 100
            assert tar.getmembers() == []

        with open_tar(fileobj=io.BytesIO(archive), mode=mode, stream=True) as tar:
            tar.extractall(tmp_path, filter="data")
        assert len(os.listdir(tmp_path)) == 100

    def test_next_on_a_plain_archive_skips_member_data(self) -> None:
        reads: dict[int, int] = {}
        for size in (1_024, 1_024 * 1_024):
            source = CountingBytesIO(build(3, size))
            with tarfile.open(fileobj=source, mode="r:") as tar:
                tar.next()
                before = source.read_bytes
                tar.next()
                reads[size] = source.read_bytes - before

        assert reads[1_024] == reads[1_024 * 1_024], reads

    def test_next_on_a_compressed_archive_reads_through_member_data(self) -> None:
        archive = build(3, 1_024 * 1_024, "w:gz")
        source = CountingBytesIO(archive)

        with tarfile.open(fileobj=source, mode="r:gz") as tar:
            tar.next()
            before = source.read_bytes
            tar.next()

            assert source.read_bytes - before >= len(archive) // 3 - 64 * 1_024


class TestExtractfileReadsOnDemand:
    """`extractfile()` | O(1) for a TarInfo, O(n) for a name, and reading it."""

    def test_a_tarinfo_reads_nothing_until_read(self) -> None:
        source = CountingBytesIO(build(100, 4_096))

        with tarfile.open(fileobj=source, mode="r:") as tar:
            first = tar.next()
            assert first is not None
            before = source.read_bytes
            reader = tar.extractfile(first)

            assert reader is not None
            assert source.read_bytes == before
            assert len(reader.read()) == 4_096
            assert source.read_bytes - before == 4_096

    def test_a_name_reads_every_header_first(self) -> None:
        source = CountingBytesIO(build(100, 4_096))

        with tarfile.open(fileobj=source, mode="r:") as tar:
            before = source.read_bytes
            tar.extractfile("m00000")

            assert source.read_bytes - before >= 99 * 512

    def test_reading_in_pieces_holds_one_piece(self) -> None:
        size = 8 * 1_024 * 1_024
        archive = build(1, size)

        def in_pieces() -> None:
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                reader = tar.extractfile("m00000")
                assert reader is not None
                while reader.read(64 * 1_024):
                    pass

        def whole() -> None:
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                reader = tar.extractfile("m00000")
                assert reader is not None
                assert len(reader.read()) == size

        pieces_peak = peak_bytes(in_pieces)
        whole_peak = peak_bytes(whole)

        assert pieces_peak < 1_024 * 1_024, f"read(64 KiB) peaked at {pieces_peak} bytes"
        assert whole_peak > size, f"read() peaked at only {whole_peak} bytes"

    def test_going_back_in_a_compressed_archive_decompresses_again(self) -> None:
        archive = build(200, 64 * 1_024, "w:gz")
        source = CountingBytesIO(archive)

        with tarfile.open(fileobj=source, mode="r:gz") as tar:
            members = tar.getmembers()
            reads: dict[str, int] = {}
            for label, index in (("last", -1), ("first", 0)):
                before = source.read_bytes
                reader = tar.extractfile(members[index])
                assert reader is not None
                reader.read()
                reads[label] = source.read_bytes - before

        assert reads["last"] > len(archive) * 0.9, reads
        assert reads["first"] < len(archive) * 0.1, reads

    def test_reading_each_member_while_iterating_is_one_pass(self) -> None:
        archive = build(200, 16 * 1_024, "w:gz")
        source = CountingBytesIO(archive)

        with tarfile.open(fileobj=source, mode="r:gz") as tar:
            for info in tar:
                reader = tar.extractfile(info)
                assert reader is not None
                assert len(reader.read()) == 16 * 1_024

        assert source.read_bytes <= len(archive) * 1.05

    def test_a_plain_archive_seeks_straight_to_the_member(self) -> None:
        source = CountingBytesIO(build(200, 64 * 1_024))

        with tarfile.open(fileobj=source, mode="r:") as tar:
            members = tar.getmembers()
            for index in (-1, 0):
                before = source.read_bytes
                reader = tar.extractfile(members[index])
                assert reader is not None
                reader.read()

                assert source.read_bytes - before == 64 * 1_024

    def test_a_stream_cannot_go_back(self) -> None:
        with tarfile.open(fileobj=io.BytesIO(build(2, 10, "w|gz")), mode="r|gz") as tar:
            first = tar.next()
            assert first is not None
            tar.next()
            reader = tar.extractfile(first)
            assert reader is not None

            with pytest.raises(tarfile.StreamError):
                reader.read()

    def test_a_directory_has_no_reader(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            tar.addfile(member("folder", tarfile.DIRTYPE))

        buffer.seek(0)
        with tarfile.open(fileobj=buffer) as tar:
            assert tar.extractfile("folder") is None


class TestExtractionCopiesInChunks:
    """`extract()` | O(s) | O(1), and `extractall()` | one forward pass."""

    def test_extract_holds_one_chunk(self, tmp_path: pathlib.Path) -> None:
        size = 8 * 1_024 * 1_024
        source = CountingBytesIO(build(1, size))

        def extract() -> None:
            with tarfile.open(fileobj=source, mode="r:") as tar:
                tar.extract("m00000", tmp_path, filter="data")

        peak = peak_bytes(extract)

        assert peak < 1_024 * 1_024, f"extract() peaked at {peak} bytes"
        assert source.largest <= 64 * 1_024, f"one read took {source.largest} bytes"
        assert (tmp_path / "m00000").stat().st_size == size

    def test_extractall_reads_a_compressed_archive_once(self, tmp_path: pathlib.Path) -> None:
        archive = build(200, 16 * 1_024, "w:gz")
        source = CountingBytesIO(archive)

        with tarfile.open(fileobj=source, mode="r:gz") as tar:
            tar.extractall(tmp_path / "forward", filter="data")

        assert source.read_bytes <= len(archive) * 1.05

        source = CountingBytesIO(archive)
        with tarfile.open(fileobj=source, mode="r:gz") as tar:
            backwards = list(reversed(tar.getmembers()))
            tar.extractall(tmp_path / "backward", members=backwards, filter="data")

        assert source.read_bytes > len(archive) * 50, (
            f"reverse order read {source.read_bytes / len(archive):.1f}x the archive"
        )

    def test_directory_attributes_are_set_after_their_contents(
        self, tmp_path: pathlib.Path
    ) -> None:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            tar.addfile(member("locked", tarfile.DIRTYPE, mode=0o555, mtime=1_000_000))
            tar.addfile(member("locked/file.txt", size=2), io.BytesIO(b"ok"))

        buffer.seek(0)
        with tarfile.open(fileobj=buffer) as tar:
            tar.extractall(tmp_path, filter="tar")

        locked = tmp_path / "locked"
        try:
            assert (locked / "file.txt").read_bytes() == b"ok"
            assert locked.stat().st_mode & 0o777 == 0o555
            assert locked.stat().st_mtime == 1_000_000
        finally:
            locked.chmod(0o755)


class TestErrorHandling:
    """`errorlevel`, `extraction_filter` and the version's default filter."""

    @staticmethod
    def archive(*names: str) -> io.BytesIO:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            for name in names:
                tar.addfile(member(name, size=2), io.BytesIO(b"ok"))
        buffer.seek(0)
        return buffer

    @staticmethod
    def raising(error: Exception) -> Callable[[tarfile.TarInfo, str], tarfile.TarInfo]:
        def reject(info: tarfile.TarInfo, path: str) -> tarfile.TarInfo:
            raise error

        return reject

    def test_extract_error_is_skipped_at_one_and_raised_at_two(
        self, tmp_path: pathlib.Path
    ) -> None:
        reject = self.raising(tarfile.ExtractError("no"))
        with tarfile.open(fileobj=self.archive("a.txt")) as tar:
            tar.extractall(tmp_path, filter=reject)
        assert os.listdir(tmp_path) == []

        with tarfile.open(fileobj=self.archive("a.txt"), errorlevel=2) as tar:
            with pytest.raises(tarfile.ExtractError):
                tar.extractall(tmp_path, filter=reject)

    def test_filter_error_is_skipped_at_zero_and_raised_at_one(
        self, tmp_path: pathlib.Path
    ) -> None:
        with tarfile.open(fileobj=self.archive("../escape.txt", "safe.txt"), errorlevel=0) as tar:
            tar.extractall(tmp_path / "dest", filter="data")
        assert os.listdir(tmp_path / "dest") == ["safe.txt"]

        with tarfile.open(fileobj=self.archive("../escape.txt")) as tar:
            with pytest.raises(tarfile.OutsideDestinationError):
                tar.extractall(tmp_path / "dest", filter="data")
        assert not (tmp_path / "escape.txt").exists()

    def test_extraction_filter_is_used_when_no_filter_is_given(
        self, tmp_path: pathlib.Path
    ) -> None:
        seen: list[str] = []

        def recording(info: tarfile.TarInfo, path: str) -> tarfile.TarInfo:
            seen.append(info.name)
            return info

        with tarfile.open(fileobj=self.archive("a.txt", "b.txt")) as tar:
            tar.extraction_filter = recording
            tar.extractall(tmp_path)

        assert seen == ["a.txt", "b.txt"]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="'data' is the default from 3.14")
    def test_the_default_rejects_an_escape(self, tmp_path: pathlib.Path) -> None:
        with tarfile.open(fileobj=self.archive("../escape.txt")) as tar:
            with pytest.raises(tarfile.OutsideDestinationError):
                tar.extractall(tmp_path / "dest")

    @pytest.mark.skipif(
        not (3, 12) <= sys.version_info < (3, 14), reason="the warning is 3.12 and 3.13"
    )
    def test_the_default_warns_and_trusts(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "dest").mkdir()
        with tarfile.open(fileobj=self.archive("../escape.txt")) as tar:
            with pytest.warns(DeprecationWarning):
                tar.extractall(tmp_path / "dest")
        assert (tmp_path / "escape.txt").read_bytes() == b"ok"

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="3.10 and 3.11 behaviour")
    def test_the_default_trusts_silently(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "dest").mkdir()
        with tarfile.open(fileobj=self.archive("../escape.txt")) as tar:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                tar.extractall(tmp_path / "dest")
        assert (tmp_path / "escape.txt").read_bytes() == b"ok"


class TestFilters:
    """What each filter rejects and rewrites."""

    DEST = "/tmp/destination"

    @pytest.mark.parametrize(
        ("info", "error"),
        [
            (member("../outside"), tarfile.OutsideDestinationError),
            (member("link", tarfile.SYMTYPE, linkname="/etc/passwd"), tarfile.AbsoluteLinkError),
            (
                member("link", tarfile.SYMTYPE, linkname="../../outside"),
                tarfile.LinkOutsideDestinationError,
            ),
            (member("device", tarfile.CHRTYPE), tarfile.SpecialFileError),
        ],
    )
    def test_data_filter_rejects(self, info: tarfile.TarInfo, error: type[Exception]) -> None:
        with pytest.raises(error) as raised:
            tarfile.data_filter(info, self.DEST)

        assert isinstance(raised.value, tarfile.FilterError)
        assert raised.value.tarinfo is info

    def test_a_leading_slash_is_stripped_not_rejected(self) -> None:
        for strip in (tarfile.data_filter, tarfile.tar_filter):
            assert strip(member("/etc/passwd"), self.DEST).name == "etc/passwd"

    @pytest.mark.skipif(sys.platform != "win32", reason="a drive letter is absolute on Windows")
    def test_a_name_still_absolute_after_stripping_is_rejected(self) -> None:
        with pytest.raises(tarfile.AbsolutePathError):
            tarfile.data_filter(member("C:/Windows/file"), "C:/destination")

    def test_data_filter_drops_ownership_and_unsafe_bits(self) -> None:
        info = member("file", mode=0o4777, uid=1_000, gid=1_000, uname="u", gname="g")

        filtered = tarfile.data_filter(info, self.DEST)

        assert filtered is not info
        assert filtered.mode == 0o755
        assert (filtered.uid, filtered.gid, filtered.uname, filtered.gname) == (None,) * 4
        assert info.mode == 0o4777

    def test_tar_filter_strips_bits_but_keeps_owner_and_devices(self) -> None:
        info = member("file", mode=0o4777, uid=1_000)
        device = member("device", tarfile.CHRTYPE)

        filtered = tarfile.tar_filter(info, self.DEST)

        assert filtered.mode == 0o755
        assert filtered.uid == 1_000
        assert tarfile.tar_filter(device, self.DEST) is device
        with pytest.raises(tarfile.OutsideDestinationError):
            tarfile.tar_filter(member("../out"), self.DEST)

    def test_fully_trusted_filter_returns_the_member(self) -> None:
        info = member("/etc/passwd")

        assert tarfile.fully_trusted_filter(info, self.DEST) is info


class TestWritingCopiesInChunks:
    """`add()` and `addfile()` | O(s) | O(1) per file, and the member cache."""

    def test_addfile_reads_in_chunks(self) -> None:
        size = 8 * 1_024 * 1_024
        source = CountingBytesIO(bytes(size))

        def write() -> None:
            with open_tar(fileobj=DiscardingSink(), mode="w") as tar:
                tar.addfile(member("big", size=size), source)

        peak = peak_bytes(write)

        assert source.read_bytes == size
        assert source.largest <= 64 * 1_024, f"one read took {source.largest} bytes"
        assert peak < 1_024 * 1_024, f"addfile() peaked at {peak} bytes"

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="ValueError from 3.13")
    def test_a_missing_file_object_raises(self) -> None:
        with tarfile.open(fileobj=io.BytesIO(), mode="w") as tar:
            with pytest.raises(ValueError, match="fileobj"):
                tar.addfile(member("data", size=10))

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="behaviour before 3.13")
    def test_a_missing_file_object_is_accepted_before_313(self) -> None:
        with tarfile.open(fileobj=io.BytesIO(), mode="w") as tar:
            tar.addfile(member("data", size=10))

            assert tar.getnames() == ["data"]

    def test_add_sorts_each_directory(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "src"
        (source / "inner").mkdir(parents=True)
        for name in ["c.txt", "b.txt", "a.txt", "inner/z.txt", "inner/y.txt"]:
            (source / name).write_text(name)

        with tarfile.open(fileobj=io.BytesIO(), mode="w") as tar:
            tar.add(source, arcname="src")
            names = tar.getnames()

        assert names == [
            "src",
            "src/a.txt",
            "src/b.txt",
            "src/c.txt",
            "src/inner",
            "src/inner/y.txt",
            "src/inner/z.txt",
        ]

    def test_add_without_recursion_stores_the_directory_alone(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "file.txt").write_text("x")

        with tarfile.open(fileobj=io.BytesIO(), mode="w") as tar:
            tar.add(tmp_path, arcname="dir", recursive=False)

            assert tar.getnames() == ["dir"]

    def test_add_filter_can_exclude_a_member(self, tmp_path: pathlib.Path) -> None:
        for name in ["keep.txt", "skip.log"]:
            (tmp_path / name).write_text(name)

        def no_logs(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
            return None if info.name.endswith(".log") else info

        with tarfile.open(fileobj=io.BytesIO(), mode="w") as tar:
            tar.add(tmp_path, arcname="d", filter=no_logs)

            assert tar.getnames() == ["d", "d/keep.txt"]

    def test_gettarinfo_reads_a_path_and_a_file_object(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(bytes(1_234))

        with tarfile.open(fileobj=io.BytesIO(), mode="w") as tar:
            by_path = tar.gettarinfo(str(path), arcname="data.bin")
            with path.open("rb") as handle:
                by_handle = tar.gettarinfo(fileobj=handle, arcname="other.bin")
            directory = tar.gettarinfo(str(tmp_path), arcname="dir")

        assert (by_path.name, by_path.size, by_path.isfile()) == ("data.bin", 1_234, True)
        assert (by_handle.name, by_handle.size) == ("other.bin", 1_234)
        assert directory.isdir() and directory.size == 0

    def test_global_pax_headers_are_written_first_and_read_back(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(
            fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT, pax_headers={"comment": "hi"}
        ) as tar:
            tar.addfile(member("file", size=0))

        assert buffer.getvalue()[156:157] == tarfile.XGLTYPE
        buffer.seek(0)
        with tarfile.open(fileobj=buffer) as tar:
            assert tar.pax_headers == {"comment": "hi"}
            assert tar.getnames() == ["file"]

    @pytest.mark.parametrize("compression", COMPRESSIONS)
    def test_compressed_modes_round_trip(self, compression: str) -> None:
        archive = build(3, 100, f"w:{compression}")

        with open_tar(fileobj=io.BytesIO(archive), mode=f"r:{compression}") as tar:
            assert tar.getnames() == ["m00000", "m00001", "m00002"]
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            assert len(tar.getmembers()) == 3


class TestTarInfo:
    """Headers are one block, plus extended blocks for a long name."""

    def test_a_short_name_is_one_block_and_round_trips(self) -> None:
        info = member("notes.txt", size=100, mtime=12_345)

        block = info.tobuf(tarfile.USTAR_FORMAT)
        parsed = tarfile.TarInfo.frombuf(block, tarfile.ENCODING, "surrogateescape")

        assert len(block) == 512
        assert (parsed.name, parsed.size, parsed.mtime) == ("notes.txt", 100, 12_345)

    def test_a_long_name_adds_blocks(self) -> None:
        block = tarfile.TarInfo("d/" * 100 + "file").tobuf(tarfile.PAX_FORMAT)

        assert len(block) > 512
        assert len(block) % 512 == 0

    def test_frombuf_rejects_a_bad_block(self) -> None:
        block = bytearray(tarfile.TarInfo("x").tobuf())
        block[0] ^= 0xFF

        with pytest.raises(tarfile.HeaderError):
            tarfile.TarInfo.frombuf(bytes(block), tarfile.ENCODING, "surrogateescape")
        with pytest.raises(tarfile.HeaderError):
            tarfile.TarInfo.frombuf(b"", tarfile.ENCODING, "surrogateescape")

    def test_fromtarfile_reads_the_next_header(self) -> None:
        long_name = "d/" * 100 + "file"
        archive = build(2, 0, names=["first", long_name].__getitem__)

        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            following = tarfile.TarInfo.fromtarfile(tar)

        assert following.name == long_name

    def test_replace_shares_or_copies_pax_headers(self) -> None:
        info = tarfile.TarInfo("a")
        info.pax_headers = {"comment": "x"}

        shallow = info.replace(name="b", deep=False)
        deep = info.replace(name="c")

        assert shallow.pax_headers is info.pax_headers
        assert deep.pax_headers is not info.pax_headers
        assert deep.pax_headers == info.pax_headers
        assert (info.name, shallow.name, deep.name) == ("a", "b", "c")

    def test_defaults(self) -> None:
        info = tarfile.TarInfo()

        assert (info.name, info.size, info.type) == ("", 0, tarfile.REGTYPE)
        assert info.isfile() and info.isreg()

    @pytest.mark.parametrize(
        ("kind", "predicate"),
        [
            (tarfile.REGTYPE, "isfile"),
            (tarfile.DIRTYPE, "isdir"),
            (tarfile.SYMTYPE, "issym"),
            (tarfile.LNKTYPE, "islnk"),
            (tarfile.CHRTYPE, "ischr"),
            (tarfile.BLKTYPE, "isblk"),
            (tarfile.FIFOTYPE, "isfifo"),
        ],
    )
    def test_each_predicate_matches_its_type(self, kind: bytes, predicate: str) -> None:
        info = member("x", kind)
        predicates = ["isfile", "isdir", "issym", "islnk", "ischr", "isblk", "isfifo"]

        assert [name for name in predicates if getattr(info, name)()] == [predicate]
        assert info.isreg() is (predicate == "isfile")
        assert info.isdev() is (predicate in {"ischr", "isblk", "isfifo"})

    def test_parsed_attributes(self) -> None:
        with tarfile.open(fileobj=io.BytesIO(build(2, 700))) as tar:
            first, second = tar.getmembers()

        assert first.offset == 0 and first.offset_data == 512
        assert second.offset == 512 + 1_024
        assert first.chksum > 0 and first.sparse is None
        assert (first.devmajor, first.devminor, first.linkname) == (0, 0, "")


class TestList:
    """`list()` | O(n): one line per member."""

    def test_names_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        with tarfile.open(fileobj=io.BytesIO(build(3, 1))) as tar:
            tar.list(verbose=False)

        assert capsys.readouterr().out.split() == ["m00000", "m00001", "m00002"]

    def test_a_subset(self, capsys: pytest.CaptureFixture[str]) -> None:
        with tarfile.open(fileobj=io.BytesIO(build(3, 1))) as tar:
            tar.list(verbose=False, members=tar.getmembers()[1:2])

        assert capsys.readouterr().out.split() == ["m00001"]

    def test_verbose(self, capsys: pytest.CaptureFixture[str]) -> None:
        with tarfile.open(fileobj=io.BytesIO(build(3, 1))) as tar:
            tar.list()

        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == 3
        assert all(line[1:10] == "rw-r--r--" for line in lines)


class TestExceptions:
    def test_hierarchy(self) -> None:
        for error in (
            tarfile.ReadError,
            tarfile.CompressionError,
            tarfile.StreamError,
            tarfile.ExtractError,
            tarfile.HeaderError,
            tarfile.FilterError,
        ):
            assert issubclass(error, tarfile.TarError)
        for error in (
            tarfile.AbsolutePathError,
            tarfile.OutsideDestinationError,
            tarfile.SpecialFileError,
            tarfile.AbsoluteLinkError,
            tarfile.LinkOutsideDestinationError,
            tarfile.LinkFallbackError,
        ):
            assert issubclass(error, tarfile.FilterError)

    def test_read_error_for_bytes_that_are_not_an_archive(self) -> None:
        with pytest.raises(tarfile.ReadError):
            tarfile.open(fileobj=io.BytesIO(b"not an archive" * 100))

    def test_compression_error_for_an_unknown_compression(self) -> None:
        with pytest.raises(tarfile.CompressionError):
            open_tar(fileobj=io.BytesIO(), mode="r:nope")


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
        [sys.executable, "-W", "error", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, with
    warnings raised as errors so a block relying on the default filter fails."""

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
        line, source = next(
            (n, s) for n, s in _blocks() if "assert tar.getmembers() is members" in s
        )
        mutated = source.replace(
            "assert tar.getmembers() is members", "assert tar.getmembers() is not members", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
