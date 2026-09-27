"""Tests for docs/stdlib/gzip.md.

The page prices gzip in the bytes that go in and come out: one-shot calls hold
the whole result, `decompress()` recopies the rest of its input per member from
3.11, and a `GzipFile` decompresses as it is read, emulates `seek()` by
decompressing, and passes compressed output on as zlib's buffers fill. Space is
settled by traced allocation, laziness and seeking by a `BytesIO` that counts
the bytes taken from it, the multi-member cost by a `zlib` proxy that counts
the bytes handed to every decompressor, and the one timed row by ratios far
from the excluded growth classes.

Measurement scope:

* `compress()` of 20,000,000 identical bytes at levels 1 and 9 peaks under
  2 MB, less than 1.5x compressing 1,000 bytes, so neither the input nor a
  buffer sized for it is held. At levels 1 and 9, 16x the generated text
  (250,000 to 4,000,000 bytes) costs between 8x and 32x the time. From 3.14
  the header's mtime is 0 unless one is passed, and two calls return equal
  bytes; before 3.14 it is the current time.
* `decompress()` of one 10,000,000-byte member peaks above 5 MB. Over 1,000
  concatenated members of 4,000 random bytes, it hands the decompressors it
  creates more than s·n/4 bytes from 3.11, and at most n plus one read buffer
  per member on 3.10, where n is the input's length. A `GzipFile` over the
  same input hands them at most n plus one read buffer (`READ_BUFFER_SIZE`,
  128 KiB, from 3.12; `io.DEFAULT_BUFFER_SIZE`, 8 KiB, before) per member.
  Garbage and trailing bytes that are not a member raise `BadGzipFile`, a
  corrupted CRC or length raises it, as does a member cut to its first byte;
  one cut after two or five bytes, or three short of its end, raises
  `EOFError`, and trailing zero bytes are skipped; a `GzipFile` treats
  trailing bytes the same way.
* A raw `zlib` decompressor with gzip framing returns more than a quarter of
  the output after half of a generated-text member's bytes, so decoding does
  not wait for the whole input. With `max_length=4096` it returns exactly 4096
  bytes of a 10,000,000-byte bomb and holds the rest of the input in
  `unconsumed_tail`.
* `GzipFile` and `open()` take nothing from a counting source when built for
  reading; built for writing, the target holds the 10-byte header at once. On
  4,000,000 random bytes, `read(1000)` takes at most one read buffer plus one
  `io.DEFAULT_BUFFER_SIZE`; within 300,000 bytes, a forward seek to 2,000,000
  takes 2,000,000, a further seek to 3,000,000 takes 1,000,000 more, a
  backward seek to 1,000,000 takes 1,000,000 from offset zero, and `SEEK_END`
  takes the remaining 3,000,000; after rewinding, `seek(-3_000_000, SEEK_END)`
  takes 1,000,000, so the size is kept. A 500-byte backward seek inside the
  read buffer takes nothing. `read(100_000_000)` on a one-byte file peaks
  above 50 MB, so a read's space follows the size it asks for. `read1()` with
  no size returns at most `io.DEFAULT_BUFFER_SIZE` bytes. `peek(1)` returns
  more than one byte and does not move `tell()`. `rewind()` returns the next
  read to the first byte and raises `OSError` in write mode. `mtime` is `None`
  before the first read, the header's value after it, and the second member's
  after reading two.
* Writing 2,000,000 random bytes without a flush puts more than 1,000,000
  compressed bytes in the target, and `writelines()` does the same. After
  `write()` and `flush()`, a raw `zlib` decompressor returns the record from
  the target before `close()`. A forward seek in write mode writes zero bytes,
  a backward one raises `OSError`, and `SEEK_END` raises `ValueError`.
  `close()` leaves a wrapped `BytesIO` open and closes a file it opened.
  `closed`, `fileno()`, `readable()`, `writable()`, `seekable()` and `name`
  are asserted by value; `mode` is `'rb'`/`'wb'` from 3.13 and
  `gzip.READ`/`gzip.WRITE` (1 and 2) before. A text mode returns an
  `io.TextIOWrapper`.
* `compression.gzip` is asserted to be this module's names from 3.14.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* O(m) for compression rests on DEFLATE's bounded match search: each input
  byte is compared against at most a fixed number of earlier positions in a
  32 KiB window, set by the level. A 16x timing step only excludes constant
  and quadratic growth. Only generated text is timed; random bytes, runs of
  one byte, and levels 0 and 2 to 8 are not.
* That the window, zlib's working memory and `GzipFile`'s buffers are fixed
  sizes is read from Lib/gzip.py (`READ_BUFFER_SIZE`, `_WRITE_BUFFER_SIZE`)
  and zlib's `deflateInit2` with `DEF_MEM_LEVEL`; the O(1) bounds for
  `flush()`, `close()` and `tell()` rest on those constants, and are not
  timed. `peek()` and the read and seek bounds also rest on the page's
  assumption that compressed bytes produce output.
* The O(n) term in one-member `decompress()` space from 3.11 is the copy
  `data[fp.tell():]` in Lib/gzip.py; it only matters for a member whose
  compressed bytes produce little output, which is not measured.
* That the multi-member proxies' counts are copies, rather than views, is
  read from `decompress()` slicing `data[fp.tell():]` and
  `do.unused_data[8:]` in Lib/gzip.py; the tests count bytes handed over.
* Bounds are in the bytes that go in and come out. Input whose compressed
  bytes produce no output - many empty members, or long runs of zero padding
  - costs time in the bytes passed over and is outside those bounds.
* `GzipFile.raw`, `myfileobj`, `BadGzipFile.winerror`, `gzip.main()` and
  `gzip.write32u()` are reported by the audit's runtime inspection; they are
  internals, a Windows-only `OSError` field or the command-line entry point,
  and the page documents none of them. The inherited `detach()`,
  `truncate()` and `isatty()` are the `io` base class's.
"""

from __future__ import annotations

import functools
import gzip
import io
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import zlib
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "gzip.md"
EXPECTED_BLOCKS = 5
READ_BUFFER = getattr(gzip, "READ_BUFFER_SIZE", io.DEFAULT_BUFFER_SIZE)


def best_ns(func: Callable[[], Any], repeats: int = 3, inner: int = 1) -> float:
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


@functools.cache
def generated_text(size: int, seed: int = 1) -> bytes:
    """Compressible, realistic text: lines of words from a 500-word vocabulary."""
    rng = random.Random(seed)
    words = [f"w{index}" for index in range(500)]
    lines: list[bytes] = []
    total = 0
    while total < size:
        line = (" ".join(rng.choice(words) for _ in range(8)) + "\n").encode()
        lines.append(line)
        total += len(line)
    return b"".join(lines)[:size]


@functools.cache
def random_bytes(size: int, seed: int = 3) -> bytes:
    return random.Random(seed).randbytes(size)


@functools.cache
def compressed_random(size: int) -> bytes:
    return gzip.compress(random_bytes(size), 1, mtime=0)


class CountingBytesIO(io.BytesIO):
    """A `BytesIO` that records how many bytes have been read from it."""

    taken = 0

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        self.taken += len(data)
        return data


class FedZlib:
    """Stands in for the `zlib` module inside `gzip`, counting the bytes handed
    to every decompressor it creates."""

    def __init__(self) -> None:
        self.fed = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(zlib, name)

    def _counting(self, inner: Any) -> Any:
        return _CountingDecompressor(self, inner)

    def decompressobj(self, *args: Any, **kwargs: Any) -> Any:
        return self._counting(zlib.decompressobj(*args, **kwargs))

    def _ZlibDecompressor(self, *args: Any, **kwargs: Any) -> Any:  # noqa: N802
        return self._counting(zlib._ZlibDecompressor(*args, **kwargs))  # pyright: ignore[reportAttributeAccessIssue]


class _CountingDecompressor:
    """A decompressor that adds the bytes it is handed to its `FedZlib`.

    Defined once rather than per decompressor: a class built in a closure sits
    in a reference cycle, so each discarded decompressor, and the rest of the
    input it holds as `unused_data`, would wait for the cyclic collector.
    """

    def __init__(self, counter: FedZlib, inner: Any) -> None:
        self._counter = counter
        self._inner = inner

    def decompress(self, data: bytes, *args: Any) -> bytes:
        self._counter.fed += len(data)
        return self._inner.decompress(data, *args)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class TestOneShotCompress:
    """`compress(data, compresslevel=9, *, mtime=0)` | O(m) | O(n): linear at
    every level, and memory follows the output, not the input."""

    @pytest.mark.parametrize("level", [1, 9])
    def test_memory_follows_the_output_not_the_input(self, level: int) -> None:
        data = b"x" * 20_000_000
        small = b"x" * 1_000

        large_peak = peak_bytes(lambda: gzip.compress(data, level))
        small_peak = peak_bytes(lambda: gzip.compress(small, level))

        assert len(gzip.compress(data, level)) < 100_000
        assert large_peak < 2_000_000, f"20 MB of input peaked at {large_peak} bytes"
        assert large_peak < small_peak * 1.5, f"{large_peak} for 20 MB, {small_peak} for 1 KB"

    @pytest.mark.timing
    @pytest.mark.parametrize("level", [1, 9])
    def test_time_scales_with_the_input(self, level: int) -> None:
        small = generated_text(250_000)
        large = generated_text(4_000_000)

        small_ns = best_ns(lambda: gzip.compress(small, level))
        large_ns = best_ns(lambda: gzip.compress(large, level))

        ratio = large_ns / small_ns
        assert 8 < ratio < 32, f"16x the text at level {level} cost x{ratio:.2f}"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="mtime=0 default from 3.14")
    def test_the_default_mtime_is_zero(self) -> None:
        first = gzip.compress(b"data")

        assert first[4:8] == b"\0\0\0\0"
        assert gzip.compress(b"data") == first

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="mtime=0 default from 3.14")
    def test_the_default_mtime_is_the_current_time(self) -> None:
        stamp = int.from_bytes(gzip.compress(b"data")[4:8], "little")

        assert abs(stamp - time.time()) < 60


class TestDecompress:
    """`decompress(data)` | O(n + m) | O(n + m) for one member, and O(s·n + m)
    over s concatenated members from 3.11; a `GzipFile` recopies at most one
    read buffer per member."""

    MEMBERS = 1_000

    @property
    def members(self) -> bytes:
        return gzip.compress(random_bytes(4_000), mtime=0) * self.MEMBERS

    def test_one_member_holds_the_output(self) -> None:
        payload = gzip.compress(b"x" * 10_000_000)

        peak = peak_bytes(lambda: gzip.decompress(payload))

        assert len(payload) < 20_000
        assert peak > 5_000_000, f"a 10 MB result peaked at {peak} bytes"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="per-member copies from 3.11")
    def test_every_member_recopies_the_rest_of_the_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        data = self.members
        counter = FedZlib()
        monkeypatch.setattr(gzip, "zlib", counter)

        assert gzip.decompress(data) == random_bytes(4_000) * self.MEMBERS

        n = len(data)
        assert counter.fed > self.MEMBERS * n // 4, (
            f"{self.MEMBERS} members of {n} bytes fed {counter.fed}; linear would be ~{n}"
        )

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 reads through GzipFile")
    def test_on_3_10_decompress_is_linear_in_the_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        data = self.members
        counter = FedZlib()
        monkeypatch.setattr(gzip, "zlib", counter)

        assert gzip.decompress(data) == random_bytes(4_000) * self.MEMBERS

        n = len(data)
        assert counter.fed <= n + READ_BUFFER * self.MEMBERS, f"fed {counter.fed} for {n}"

    def test_a_gzipfile_recopies_up_to_one_buffer_per_member(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        data = self.members
        counter = FedZlib()
        monkeypatch.setattr(gzip, "zlib", counter)

        with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
            assert f.read() == random_bytes(4_000) * self.MEMBERS

        n = len(data)
        assert counter.fed <= n + READ_BUFFER * self.MEMBERS, f"fed {counter.fed} for {n}"
        assert counter.fed < self.MEMBERS * n // 8, f"fed {counter.fed} for {n}"

    def test_bad_input(self) -> None:
        good = gzip.compress(b"x" * 1_000)
        corrupt = good[:-8] + bytes([good[-8] ^ 1]) + good[-7:]

        with pytest.raises(gzip.BadGzipFile, match="Not a gzipped file"):
            gzip.decompress(b"garbage!")
        with pytest.raises(gzip.BadGzipFile, match="Not a gzipped file"):
            gzip.decompress(good + b"junk")
        with pytest.raises(gzip.BadGzipFile, match="CRC"):
            gzip.decompress(corrupt)
        with pytest.raises(gzip.BadGzipFile, match="length"):
            gzip.decompress(good[:-4] + (1).to_bytes(4, "little"))
        with pytest.raises(gzip.BadGzipFile, match="Not a gzipped file"):
            gzip.decompress(good[:1])
        for cut in (2, 5, len(good) - 3):
            with pytest.raises(EOFError, match="ended before"):
                gzip.decompress(good[:cut])
        with gzip.GzipFile(fileobj=io.BytesIO(good + b"junk")) as f:
            with pytest.raises(gzip.BadGzipFile, match="Not a gzipped file"):
                f.read()
        with gzip.GzipFile(fileobj=io.BytesIO(good + b"\0" * 16)) as f:
            assert f.read() == b"x" * 1_000
        assert gzip.decompress(good + b"\0" * 16) == b"x" * 1_000
        assert issubclass(gzip.BadGzipFile, OSError)


class TestStreamingDecode:
    """DEFLATE decodes a stream as its bytes arrive, and a `zlib` decompressor
    with gzip framing and `max_length` bounds the output of one call."""

    def test_output_arrives_before_the_whole_input(self) -> None:
        data = generated_text(1_000_000)
        member = gzip.compress(data, mtime=0)
        decompressor = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)

        first = decompressor.decompress(member[: len(member) // 2])

        assert len(first) > len(data) // 4, f"half the input gave {len(first)} bytes"
        assert first + decompressor.decompress(member[len(member) // 2 :]) == data

    def test_max_length_bounds_the_output(self) -> None:
        bomb = gzip.compress(b"\0" * 10_000_000)
        decompressor = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)

        assert decompressor.decompress(bomb, 4096) == b"\0" * 4096
        assert not decompressor.eof
        assert decompressor.unconsumed_tail, "the input not yet consumed is held"


class TestGzipFileReading:
    """`GzipFile` and `open()` read nothing until asked, decompress as much as
    is read, and emulate `seek()` by decompressing."""

    SIZE = 4_000_000

    @property
    def compressed(self) -> bytes:
        return compressed_random(self.SIZE)

    @property
    def payload(self) -> bytes:
        return random_bytes(self.SIZE)

    def test_opening_reads_nothing(self) -> None:
        source = CountingBytesIO(self.compressed)

        gzip.GzipFile(fileobj=source)
        gzip.open(source)
        gzip.open(source, "rt", encoding="latin-1")

        assert source.taken == 0

    def test_a_small_read_takes_one_buffer(self) -> None:
        source = CountingBytesIO(self.compressed)

        with gzip.GzipFile(fileobj=source) as f:
            assert f.read(1000) == self.payload[:1000]

        limit = READ_BUFFER + io.DEFAULT_BUFFER_SIZE
        assert source.taken <= limit, f"took {source.taken} bytes"

    def test_seek_decompresses_forward_and_rewinds_backward(self) -> None:
        source = CountingBytesIO(self.compressed)
        f = gzip.GzipFile(fileobj=source)
        slack = 300_000

        f.seek(2_000_000)
        assert abs(source.taken - 2_000_000) < slack, source.taken

        source.taken = 0
        f.seek(3_000_000)
        assert abs(source.taken - 1_000_000) < slack, "a forward seek restarted"

        source.taken = 0
        f.seek(1_000_000)
        assert abs(source.taken - 1_000_000) < slack, "a backward seek did not rewind"
        assert f.read(10) == self.payload[1_000_000:1_000_010]

        source.taken = 0
        assert f.seek(0, io.SEEK_END) == self.SIZE
        assert abs(source.taken - 3_000_000) < slack, "SEEK_END did not read to the end"

        f.seek(0)
        source.taken = 0
        assert f.seek(-3_000_000, io.SEEK_END) == 1_000_000
        assert abs(source.taken - 1_000_000) < slack, "the size was not kept"
        f.close()

    def test_a_short_backward_seek_stays_in_the_read_buffer(self) -> None:
        source = CountingBytesIO(self.compressed)
        with gzip.GzipFile(fileobj=source) as f:
            f.seek(2_000_000)
            f.read(1000)
            source.taken = 0

            f.seek(2_000_500)

            assert source.taken == 0
            assert f.tell() == 2_000_500
            assert f.read(10) == self.payload[2_000_500:2_000_510]

    def test_rewind_starts_again_from_the_first_byte(self) -> None:
        with gzip.GzipFile(fileobj=io.BytesIO(self.compressed)) as f:
            f.seek(3_000_000)
            f.rewind()

            assert f.tell() == 0
            assert f.read(10) == self.payload[:10]

        with gzip.GzipFile(fileobj=io.BytesIO(), mode="wb") as f:
            with pytest.raises(OSError, match="rewind"):
                f.rewind()

    def test_peek_is_not_bounded_by_n_and_does_not_move(self) -> None:
        with gzip.GzipFile(fileobj=io.BytesIO(self.compressed)) as f:
            f.read(10)
            peeked = f.peek(1)

            assert len(peeked) > 1
            assert peeked.startswith(self.payload[10:11])
            assert f.tell() == 10

    def test_lines_and_iteration(self) -> None:
        text = b"".join(f"line {i}\n".encode() for i in range(100))

        with gzip.GzipFile(fileobj=io.BytesIO(gzip.compress(text))) as f:
            assert f.readline() == b"line 0\n"
            assert f.readlines(10) == [b"line 1\n", b"line 2\n"]
            assert list(f)[-1] == b"line 99\n"

    def test_a_read_allocates_the_size_it_asks_for(self) -> None:
        f = gzip.GzipFile(fileobj=io.BytesIO(gzip.compress(b"x")))

        peak = peak_bytes(lambda: f.read(100_000_000))

        assert peak > 50_000_000, f"read(100_000_000) of one byte peaked at {peak}"
        f.close()

    def test_read1_without_a_size_returns_at_most_one_buffer(self) -> None:
        with gzip.GzipFile(fileobj=io.BytesIO(self.compressed)) as f:
            chunk = f.read1()

        assert 0 < len(chunk) <= io.DEFAULT_BUFFER_SIZE
        assert chunk == self.payload[: len(chunk)]

    def test_readinto_and_readinto1(self) -> None:
        with gzip.GzipFile(fileobj=io.BytesIO(self.compressed)) as f:
            buffer = bytearray(100)
            assert f.readinto(buffer) == 100
            assert bytes(buffer) == self.payload[:100]
            got = f.readinto1(buffer)
            assert 0 < got <= 100
            assert bytes(buffer[:got]) == self.payload[100 : 100 + got]

    def test_mtime_arrives_with_the_first_header(self) -> None:
        with gzip.GzipFile(fileobj=io.BytesIO(gzip.compress(b"data", mtime=12345))) as f:
            assert f.mtime is None
            f.read(1)
            assert f.mtime == 12345

        members = gzip.compress(b"one", mtime=1) + gzip.compress(b"two", mtime=2)
        with gzip.GzipFile(fileobj=io.BytesIO(members)) as f:
            assert f.read() == b"onetwo"
            assert f.mtime == 2

    def test_concatenated_members_read_in_turn(self) -> None:
        target = io.BytesIO()
        with gzip.GzipFile(fileobj=target, mode="wb") as f:
            f.write(b"one")
        with gzip.GzipFile(fileobj=target, mode="ab") as f:
            f.write(b"two")

        assert gzip.decompress(target.getvalue()) == b"onetwo"
        target.seek(0)
        with gzip.GzipFile(fileobj=target) as f:
            assert f.read() == b"onetwo"

    def test_text_mode_wraps_in_a_text_wrapper(self) -> None:
        with gzip.open(io.BytesIO(gzip.compress(b"a\nb\n")), "rt", encoding="ascii") as f:
            assert isinstance(f, io.TextIOWrapper)
            assert f.read() == "a\nb\n"


class TestGzipFileWriting:
    """Write modes write the header at once, pass compressed output on as
    zlib's buffers fill, make everything written decodable on `flush()`, and
    seek forward only by writing zeros."""

    def test_the_header_is_written_at_once(self) -> None:
        target = io.BytesIO()
        f = gzip.GzipFile(fileobj=target, mode="wb", mtime=0)

        assert len(target.getvalue()) == 10
        assert target.getvalue()[:2] == b"\x1f\x8b"
        f.close()

    @pytest.mark.parametrize("method", ["write", "writelines"])
    def test_output_reaches_the_file_without_a_flush(self, method: str) -> None:
        target = io.BytesIO()
        f = gzip.GzipFile(fileobj=target, mode="wb", compresslevel=1)
        data = random_bytes(2_000_000)

        if method == "write":
            assert f.write(data) == len(data)
        else:
            f.writelines([data[:1_000_000], data[1_000_000:]])

        assert len(target.getvalue()) > 1_000_000, f"{len(target.getvalue())} bytes out"
        f.close()
        assert gzip.decompress(target.getvalue()) == data

    def test_flush_makes_what_was_written_decodable(self) -> None:
        target = io.BytesIO()
        f = gzip.GzipFile(fileobj=target, mode="wb", mtime=0)
        f.write(b"small record\n")
        reader = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)
        assert reader.decompress(target.getvalue()) == b""

        f.flush()

        reader = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)
        assert reader.decompress(target.getvalue()) == b"small record\n"
        assert f.tell() == 13
        f.close()
        assert gzip.decompress(target.getvalue()) == b"small record\n"

    def test_seek_in_write_mode_moves_forward_by_writing_zeros(self) -> None:
        target = io.BytesIO()
        with gzip.GzipFile(fileobj=target, mode="wb") as f:
            f.write(b"ab")
            f.seek(10)
            assert f.tell() == 10
            f.write(b"cd")
            with pytest.raises(OSError, match="Negative seek"):
                f.seek(5)
            with pytest.raises(ValueError, match="end"):
                f.seek(0, io.SEEK_END)

        assert gzip.decompress(target.getvalue()) == b"ab" + b"\0" * 8 + b"cd"

    def test_close_closes_only_a_file_it_opened(self, tmp_path: pathlib.Path) -> None:
        wrapped = io.BytesIO()
        with gzip.GzipFile(fileobj=wrapped, mode="wb") as f:
            f.write(b"data")
        assert not wrapped.closed
        assert f.closed

        path = tmp_path / "data.gz"
        with gzip.open(path, "wb") as named:
            assert named.writable() and not named.readable() and named.seekable()
            assert isinstance(named.fileno(), int)
            assert named.name == str(path)
            inner = named.myfileobj
            named.write(b"data")
        assert inner is not None and inner.closed

        with gzip.open(path) as f:
            assert f.readable() and f.seekable() and not f.writable()
            assert f.read() == b"data"
        assert f.closed

    def test_mode(self) -> None:
        with gzip.GzipFile(fileobj=io.BytesIO(), mode="wb") as writer:
            written = writer.mode
        with gzip.GzipFile(fileobj=io.BytesIO(gzip.compress(b""))) as reader:
            read = reader.mode

        if sys.version_info >= (3, 13):
            assert (read, written) == ("rb", "wb")
        else:
            assert (read, written) == (gzip.READ, gzip.WRITE) == (1, 2)


class TestVersionNotes:
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_compression_gzip_is_this_module(self) -> None:
        from compression import gzip as reexported

        for name in gzip.__all__:
            assert getattr(reexported, name) is getattr(gzip, name)


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert total == 10_000_000" in s)
        mutated = source.replace("assert total == 10_000_000", "assert total == 9_999_999", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
