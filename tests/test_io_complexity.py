"""Tests for docs/stdlib/io.md.

The page prices the three layers of a file stack and the two in-memory
streams. Which layer makes how many calls is settled by counting: raw
streams and sinks that record every `readinto()`, `read()` and `write()` made
on them. Sharing and copying are settled by identity and traced allocation,
which separate an O(1) handoff from an O(n) copy by orders of magnitude.
Timing is used where neither can see the cost: `TextIOWrapper.tell()` and
`seek()`, `StringIO` conversion and truncation, `BytesIO` truncation, and
`str +=`.

Measurement scope:

* `IOBase.readline()` on a raw stream with no `peek()` makes 10,000 reads for
  a 10,000-byte line; a `BufferedReader` with a 4,096-byte buffer makes at
  most four, and so does a loop of 10,000 `read(1)` calls through it, the
  first of which asks the raw stream for 4,096 bytes. `read1()` asking for a
  megabyte makes exactly one raw read. `peek(1)` makes one raw read, returns
  the whole 4,096-byte buffer, and a following `read()` still returns every
  byte. `RawIOBase.readall()` over three default buffers makes more than
  three reads. Iteration is observed to call `readline()`, `readlines(4)` to
  stop after two 3-byte lines, and `writelines()` to make one `write()` per
  item with no separators added. The base `BufferedIOBase.readinto()` and
  `readinto1()` are observed to call `read()` with the target's length.
* A `BufferedWriter` with a 4,096-byte buffer turns 10,000 one-byte writes
  into at most three raw writes, holds fewer than 4,096 bytes until
  `flush()`, and `close()` writes them out. A `BufferedRandom` is observed
  to hand pending bytes to its raw stream on `seek()`, `truncate()`,
  `detach()` and `close()`, and a `TextIOWrapper` to its buffer on `tell()`,
  `seek()` and `reconfigure()`. Building a reader with a 10 MB buffer peaks
  over 10 MB, and with a 4 KB buffer under 64 KB.
* `open()` is asserted to build `FileIO`, `BufferedReader`, `BufferedWriter`,
  `BufferedRandom` and `TextIOWrapper` for the modes the page names, and
  `io.open is open`. The buffer it picks is observed with `peek()` over a
  512 KB file: on 3.14+ it is `max(min(st_blksize, 8 MiB), 128 KiB)`, and
  before that `st_blksize`, with `DEFAULT_BUFFER_SIZE` asserted as 131,072
  and 8,192 either side of 3.14.
* `FileIO.read(100)` on a pipe holding 5 bytes returns 5; a non-blocking
  pipe accepts fewer than the 10 MB a single `write()` offers.
  `readinto()` into a 1 MB `bytearray` peaks under 64 KB from a `FileIO` and
  from a `BufferedReader`.
* `TextIOWrapper()` over 10 MB reads nothing and peaks under 64 KB.
  `readline()` over the same stream moves its buffer 8,192 bytes, one chunk.
  Writes stay in the wrapper until `flush()`, reach the buffer at once with
  `write_through`, and on a newline with `line_buffering`. `reconfigure()`
  is asserted to change the encoding and `line_buffering` before a read.
* `tell()` is timed on two-byte UTF-8 text: after `read(1,000,000)` it costs
  more than 20x what it costs after `read(2,500)`, and after `readline()` on
  a 1 MB line under 3x what it costs on a 10,000-character line, so it
  follows the chunk and not the stream. After `read()` to the end it is more
  than 100x cheaper than after `read(1,000,000)`. `seek(cookie)` on fresh
  streams, to a cookie taken after `read(1,000,000)`, costs under 10x one
  taken after `read(2,500)` in UTF-8, UTF-16 and Latin-1, where a re-decode
  to the cookie would cost hundreds of times more. Each stream is first
  returned to 0, so freeing the decoded chunk is not timed, and a read after
  the seek returns a marker character placed at that position; `seek(0)` costs under 3x across
  the same two streams. `tell()` inside a `for` loop raises `OSError`, and a
  nonzero relative seek raises on a `TextIOWrapper` and a `StringIO`.
* `StringIO(s)` on a million ASCII characters peaks over a megabyte, and a
  hundred times the characters costs more than 20x in time. 2,000, 20,000
  and 200,000 appended rows each cost under 30x the previous tenth, so
  writing is not quadratic. After a million characters of appends and a
  `seek(0)`, the first `readline()`, and the first `write()`, each cost more
  than 50x the second, and the first `readline()` and `truncate(1)` each
  peak over a megabyte. `getvalue()` after a thousand appends peaks over a
  megabyte. A hundred times the characters makes `truncate(1)` after writes
  more than 20x dearer, and `seek()` plus `tell()` less than 3x. A write one
  character a million past the end peaks over a megabyte.
* `BytesIO(b)` over 10 MB peaks under 64 KB and `getvalue()` returns `b`
  itself; over a `bytearray` of the same size it peaks over 10 MB. After
  writes, `getvalue()` returns the same object twice and peaks under 64 KB.
  With that object held, the next write peaks over 10 MB and the one after
  under 64 KB. `getbuffer()` peaks under 64 KB on a stream it does not share
  and over 10 MB on one built from `bytes`; while a view is open `write()`,
  `truncate()` and `close()` raise `BufferError` and `getvalue()` returns a
  copy. `truncate(size // 4)` on a stream sharing its bytes costs more than
  20x for 100x the bytes; `seek()` and `tell()` cost under 20x. A write one
  byte 10 MB past the end peaks over 10 MB and leaves zero bytes behind it.
* `str +=` on CPython with a second reference to the string: 250, 2,000 and
  16,000 appends of 20 characters cost more than 500x from the first size to
  the last and more than 32x for the last 8x step, against 64x and 8x for a
  linear loop.
* `io.Reader` and `io.Writer` accept any object with the method and reject
  one without it; they are skipped before 3.14. `UnsupportedOperation` is
  both an `OSError` and a `ValueError`, and `io.BlockingIOError` is the
  builtin.
* Every fenced Python block runs in its own subprocess and temporary working
  directory, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* What a system call costs. The page prices one at the bytes it moves; the
  kernel, the filesystem and the device decide the rest. `FileIO`
  construction, `truncate()` on a file and `open_code()`'s hook are read from
  the documentation, not measured.
* Raw streams that transfer less than asked. The counting fixtures always
  fill a read and accept a whole write, so one raw call per buffer is shown
  only for streams that do; a pipe or socket returning short reads makes
  more.
* Encoding and decoding at O(1) per character is a cost-model assumption,
  scoped on the page to codecs whose state clears between characters.
  `tell()` is timed only on UTF-8. ISO-2022-JP, whose decoder keeps its
  mode across a run, is outside that scope and not measured. UTF-7 inside a
  long base64 run is
  outside that scope: its decoder never clears, `tell()` falls back to one
  decode call per byte, and 200 to 2,000 characters was observed to cost
  about 90x.
* The flush that `seek()`, `truncate()`, `detach()`, `tell()` and
  `reconfigure()` do is observed, not timed; its O(b) bound is the buffer
  it writes out.
* An unaliased `str +=` loop is not priced by the page: CPython extends the
  string in place, but whether that stays linear depends on the allocator.
* `BytesIO.truncate()` on a stream that does not share its bytes shrinks its
  buffer with `realloc`, whose cost is the allocator's; the O(n) bound is
  shown through the shared case, which copies.
* `io.Reader` and `io.Writer` checks are asserted by result, not timed.
* The audit's unclassified runtime members of the concrete classes -
  `BufferedRWPair.close`, `BufferedRandom.peek` and the like - are the base
  class rows inherited; `UnsupportedOperation.winerror` exists only on
  Windows.
"""

from __future__ import annotations

import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from functools import partial
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "io.md"
EXPECTED_BLOCKS = 9

SMALL_PEAK = 64_000
TEN_MB = 10_000_000


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


def best_fresh_ns(make: Callable[[], Callable[[], Any]], repeats: int = 5) -> float:
    """Fastest of `repeats` single calls, each on state `make` builds untimed."""
    best: float | None = None
    for _ in range(repeats):
        func = make()
        start = time.perf_counter_ns()
        func()
        elapsed = float(time.perf_counter_ns() - start)
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


class CountingRaw(io.RawIOBase):
    """An in-memory raw stream that counts the reads made on it."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0
        self.reads = 0
        self.requested: list[int] = []

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        self.reads += 1
        self.requested.append(len(buffer))
        chunk = self.data[self.pos : self.pos + len(buffer)]
        buffer[: len(chunk)] = chunk
        self.pos += len(chunk)
        return len(chunk)


class CountingSink(io.RawIOBase):
    """A raw stream that records every write made on it."""

    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def writable(self) -> bool:
        return True

    def write(self, b: Any) -> int:
        self.writes.append(bytes(b))
        return len(b)

    @property
    def data(self) -> bytes:
        return b"".join(self.writes)


def two_byte_text(characters: int) -> bytes:
    return ("é" * characters).encode("utf-8")


class TestBufferingBatchesRawCalls:
    """`IOBase.readline()` makes one read per byte without `peek()`; the
    buffered rows cost one raw read or write per `b` bytes."""

    LINE = b"x" * 9_999 + b"\n"

    def test_readline_without_peek_reads_a_byte_at_a_time(self) -> None:
        raw = CountingRaw(self.LINE)

        assert raw.readline() == self.LINE
        assert raw.reads == len(self.LINE)

    def test_a_buffered_readline_reads_a_buffer_at_a_time(self) -> None:
        raw = CountingRaw(self.LINE)

        assert io.BufferedReader(raw, buffer_size=4096).readline() == self.LINE
        assert raw.reads <= 4

    def test_small_reads_come_from_the_buffer(self) -> None:
        raw = CountingRaw(self.LINE)
        buffered = io.BufferedReader(raw, buffer_size=4096)

        taken = b"".join(iter(lambda: buffered.read(1), b""))

        assert taken == self.LINE
        assert raw.reads <= 4

    def test_one_small_read_on_an_empty_buffer_fills_it(self) -> None:
        raw = CountingRaw(self.LINE)
        buffered = io.BufferedReader(raw, buffer_size=4096)

        assert buffered.read(1) == b"x"
        assert raw.requested == [4096], "O(1) amortized, O(b) for the read that refills"

    def test_readall_reads_until_the_end(self) -> None:
        data = b"x" * (io.DEFAULT_BUFFER_SIZE * 3)
        raw = CountingRaw(data)

        assert raw.readall() == data
        assert raw.reads > 3, "one read per chunk, then the empty read at the end"

    def test_readlines_stops_after_hint(self) -> None:
        stream = io.BytesIO(b"aa\nbb\ncc\ndd\n")

        assert stream.readlines(4) == [b"aa\n", b"bb\n"]
        assert stream.readlines() == [b"cc\n", b"dd\n"]

    def test_the_base_readinto_goes_through_read(self) -> None:
        sizes: list[int] = []

        class ReadOnly(io.BufferedIOBase):
            def read(self, size: int | None = -1) -> bytes:
                sizes.append(-1 if size is None else size)
                return b"x" * (size or 0)

            def read1(self, size: int = -1) -> bytes:
                return self.read(size)

        target = bytearray(1_000)

        assert ReadOnly().readinto(target) == 1_000
        assert ReadOnly().readinto1(target) == 1_000
        assert sizes == [1_000, 1_000]

    def test_read1_makes_at_most_one_raw_read(self) -> None:
        raw = CountingRaw(b"x" * 2_000_000)
        buffered = io.BufferedReader(raw, buffer_size=4096)

        assert 0 < len(buffered.read1(1_000_000)) <= 1_000_000
        assert raw.reads == 1

    def test_peek_consumes_nothing_and_returns_the_buffer(self) -> None:
        raw = CountingRaw(self.LINE)
        buffered = io.BufferedReader(raw, buffer_size=4096)

        peeked = buffered.peek(1)

        assert raw.reads == 1
        assert len(peeked) == 4096, "peek(1) returns what is buffered, not one byte"
        assert buffered.read() == self.LINE

    def test_iteration_calls_readline(self) -> None:
        calls: list[int] = []

        class Lines(io.IOBase):
            def __init__(self, lines: list[bytes]) -> None:
                self.lines = iter(lines)

            def readline(self, size: int | None = -1) -> bytes:
                calls.append(1)
                return next(self.lines, b"")

        assert list(Lines([b"a\n", b"b\n"])) == [b"a\n", b"b\n"]
        assert len(calls) == 3, "two lines, then the empty read that ends iteration"

    def test_writelines_writes_each_item_without_separators(self) -> None:
        sink = CountingSink()

        sink.writelines([b"a", b"b", b"c"])

        assert sink.writes == [b"a", b"b", b"c"]

    def test_small_writes_reach_the_raw_stream_a_buffer_at_a_time(self) -> None:
        sink = CountingSink()
        writer = io.BufferedWriter(sink, buffer_size=4096)

        for _ in range(10_000):
            writer.write(b"x")

        assert len(sink.writes) <= 3
        pending = 10_000 - len(sink.data)
        assert 0 < pending < 4096

        writer.flush()

        assert sink.data == b"x" * 10_000

    @pytest.mark.parametrize("operation", ["seek", "truncate", "detach", "close"])
    def test_operations_that_flush_write_out_the_buffer(self, operation: str) -> None:
        seen: list[bytes] = []

        class Raw(io.BytesIO):
            def close(self) -> None:
                seen.append(self.getvalue())
                super().close()

        raw = Raw()
        stream = io.BufferedRandom(raw)  # type: ignore[arg-type]
        stream.write(b"abc")
        assert raw.getvalue() == b""

        if operation == "seek":
            stream.seek(0)
        elif operation == "truncate":
            stream.truncate()
        elif operation == "detach":
            stream.detach()
        else:
            stream.close()

        assert (seen[0] if operation == "close" else raw.getvalue()) == b"abc"

    @pytest.mark.parametrize("operation", ["tell", "seek", "reconfigure"])
    def test_text_operations_that_flush_write_out_the_wrapper(self, operation: str) -> None:
        buffer = io.BytesIO()
        text = io.TextIOWrapper(buffer, encoding="ascii")
        text.write("abc")
        assert buffer.getvalue() == b""

        if operation == "tell":
            text.tell()
        elif operation == "seek":
            text.seek(0)
        else:
            text.reconfigure(line_buffering=True)

        assert buffer.getvalue() == b"abc"

    def test_close_flushes(self) -> None:
        sink = CountingSink()
        writer = io.BufferedWriter(sink, buffer_size=4096)
        writer.write(b"abc")

        writer.close()

        assert sink.data == b"abc"

    def test_the_buffer_is_allocated_with_the_object(self) -> None:
        big = peak_bytes(lambda: io.BufferedReader(CountingRaw(b""), buffer_size=TEN_MB))
        small = peak_bytes(lambda: io.BufferedReader(CountingRaw(b""), buffer_size=4096))

        assert big > TEN_MB, f"a 10 MB buffer peaked at {big} bytes"
        assert small < SMALL_PEAK, f"a 4 KB buffer peaked at {small} bytes"

    def test_detach_returns_the_raw_stream(self) -> None:
        raw = CountingRaw(b"abc")
        buffered = io.BufferedReader(raw)

        assert buffered.raw is raw
        assert buffered.detach() is raw
        with pytest.raises(ValueError, match="detached"):
            buffered.read()

    def test_buffered_random_reads_what_it_wrote(self) -> None:
        stream = io.BufferedRandom(io.BytesIO())  # type: ignore[arg-type]

        stream.write(b"hello")
        stream.seek(0)

        assert stream.read() == b"hello"

    def test_a_rw_pair_reads_one_way_and_writes_the_other(self) -> None:
        reader, sink = CountingRaw(b"in"), CountingSink()
        pair = io.BufferedRWPair(reader, sink)

        assert pair.read() == b"in"
        pair.write(b"out")
        pair.flush()

        assert sink.data == b"out"
        assert pair.seekable() is False


class TestWhatOpenBuilds:
    """`io.open` is the builtin, and each mode stops at the layer the page
    names; the buffer it picks follows the 3.14 rule."""

    @pytest.fixture
    def path(self, tmp_path: pathlib.Path) -> pathlib.Path:
        target = tmp_path / "data.bin"
        target.write_bytes(b"x" * 512 * 1024)
        return target

    def test_io_open_is_the_builtin(self) -> None:
        assert io.open is open

    @pytest.mark.parametrize(
        ("mode", "buffering", "expected"),
        [
            ("rb", 0, io.FileIO),
            ("rb", -1, io.BufferedReader),
            ("wb", -1, io.BufferedWriter),
            ("r+b", -1, io.BufferedRandom),
            ("r", -1, io.TextIOWrapper),
        ],
    )
    def test_each_mode_builds_its_layer(
        self, path: pathlib.Path, mode: str, buffering: int, expected: type
    ) -> None:
        encoding = "latin-1" if "b" not in mode else None
        with open(path, mode, buffering=buffering, encoding=encoding) as f:
            assert type(f) is expected

    def test_open_code_opens_for_binary_reading(self, path: pathlib.Path) -> None:
        with io.open_code(str(path)) as f:
            assert isinstance(f, io.BufferedReader)
            assert f.read(3) == b"xxx"

    def test_text_encoding_passes_a_name_through(self) -> None:
        # typeshed exports it from 3.11; the function itself is there from 3.10.
        text_encoding = io.text_encoding  # pyright: ignore[reportAttributeAccessIssue]
        assert text_encoding("latin-1") == "latin-1"
        assert text_encoding(None) in {"locale", "utf-8"}

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="128 KiB from 3.14")
    def test_the_default_buffer_is_128_kib(self, path: pathlib.Path) -> None:
        assert io.DEFAULT_BUFFER_SIZE == 128 * 1024
        blksize = os.stat(path).st_blksize
        with open(path, "rb") as f:
            assert len(f.peek(1)) == max(min(blksize, 8 * 1024 * 1024), io.DEFAULT_BUFFER_SIZE)

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="8 KiB before 3.14")
    def test_the_default_buffer_was_8_kib(self, path: pathlib.Path) -> None:
        assert io.DEFAULT_BUFFER_SIZE == 8 * 1024
        blksize = os.stat(path).st_blksize
        with open(path, "rb") as f:
            assert len(f.peek(1)) == (blksize if blksize > 1 else io.DEFAULT_BUFFER_SIZE)

    def test_every_stream_is_an_iobase(self, path: pathlib.Path) -> None:
        with open(path, "rb", buffering=0) as raw:
            assert isinstance(raw, io.RawIOBase)
            assert raw.mode == "rb"
            assert raw.name == str(path)
        assert isinstance(io.BytesIO(), io.BufferedIOBase)
        assert isinstance(io.StringIO(), io.TextIOBase)
        for stream in (io.BytesIO(), io.StringIO()):
            assert isinstance(stream, io.IOBase)
            with pytest.raises(io.UnsupportedOperation):
                stream.fileno()

    def test_truncate_shortens_a_file(self, path: pathlib.Path) -> None:
        with open(path, "r+b") as f:
            assert f.truncate(10) == 10
        assert path.stat().st_size == 10


@pytest.mark.skipif(not hasattr(os, "pipe"), reason="needs os.pipe")
class TestRawCallsAreSingleSystemCalls:
    """`RawIOBase.read()` may return fewer bytes, `write()` may write fewer,
    and `readinto()` allocates nothing."""

    def test_read_returns_what_one_call_got(self) -> None:
        read_fd, write_fd = os.pipe()
        with open(read_fd, "rb", buffering=0) as reader, open(write_fd, "wb", 0) as writer:
            writer.write(b"hello")

            assert reader.read(100) == b"hello"

    def test_a_non_blocking_write_can_be_partial(self) -> None:
        read_fd, write_fd = os.pipe()
        os.set_blocking(write_fd, False)
        with open(read_fd, "rb", buffering=0), open(write_fd, "wb", buffering=0) as writer:
            written = writer.write(b"x" * TEN_MB)

        assert written is not None and 0 < written < TEN_MB

    @pytest.mark.parametrize("buffering", [0, -1])
    def test_readinto_fills_the_callers_buffer(
        self, tmp_path: pathlib.Path, buffering: int
    ) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(b"x" * 1_000_000)
        target = bytearray(1_000_000)

        with open(path, "rb", buffering=buffering) as f:
            assert isinstance(f, (io.FileIO, io.BufferedReader))
            peak = peak_bytes(partial(f.readinto, target))

        assert target == b"x" * 1_000_000
        assert peak < SMALL_PEAK, f"readinto of 1 MB peaked at {peak} bytes"


class TestTextWrapperIsLazy:
    """`TextIOWrapper()` reads nothing, `readline()` decodes one chunk, and
    writes wait for a flush unless `write_through` or `line_buffering`."""

    def test_construction_reads_nothing(self) -> None:
        buffer = io.BytesIO(b"x\n" * (TEN_MB // 2))
        built = [io.TextIOWrapper(io.BytesIO(), encoding="ascii")]  # warm the codec lookup

        peak = peak_bytes(lambda: built.append(io.TextIOWrapper(buffer, encoding="ascii")))

        assert buffer.tell() == 0
        assert peak < SMALL_PEAK, f"TextIOWrapper() peaked at {peak} bytes over 10 MB"

    def test_readline_decodes_one_chunk(self) -> None:
        buffer = io.BytesIO(b"x\n" * (TEN_MB // 2))
        text = io.TextIOWrapper(buffer, encoding="ascii")

        assert text.readline() == "x\n"
        assert buffer.tell() == text._CHUNK_SIZE == 8192  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        ("options", "text", "reaches_buffer"),
        [
            ({}, "a\n", False),
            ({"write_through": True}, "a", True),
            ({"line_buffering": True}, "a", False),
            ({"line_buffering": True}, "a\n", True),
        ],
    )
    def test_when_a_write_reaches_the_buffer(
        self, options: dict[str, bool], text: str, reaches_buffer: bool
    ) -> None:
        buffer = io.BytesIO()
        wrapper = io.TextIOWrapper(
            buffer,
            encoding="ascii",
            line_buffering=options.get("line_buffering", False),
            write_through=options.get("write_through", False),
        )

        wrapper.write(text)

        assert (buffer.getvalue() == text.encode()) is reaches_buffer
        wrapper.flush()
        assert buffer.getvalue() == text.encode()

    def test_attributes(self) -> None:
        buffer = io.BytesIO(b"a\r\nb\n")
        text = io.TextIOWrapper(buffer, encoding="ascii", errors="replace")

        assert text.read() == "a\nb\n"
        assert text.buffer is buffer
        assert (text.encoding, text.errors) == ("ascii", "replace")
        assert set(text.newlines) == {"\r\n", "\n"}  # type: ignore[arg-type]
        assert (text.line_buffering, text.write_through) == (False, False)

    def test_reconfigure_changes_the_encoding_and_buffering(self) -> None:
        fresh = io.TextIOWrapper(io.BytesIO("é".encode("latin-1")), encoding="utf-8")
        fresh.reconfigure(encoding="latin-1", line_buffering=True)

        assert fresh.read() == "é"
        assert fresh.line_buffering is True

    def test_detach_flushes_and_returns_the_buffer(self) -> None:
        buffer = io.BytesIO()
        text = io.TextIOWrapper(buffer, encoding="ascii")
        text.write("abc")

        assert text.detach() is buffer
        assert buffer.getvalue() == b"abc"
        with pytest.raises(ValueError, match="detached"):
            text.write("x")

    def test_the_newline_decoder_translates_across_calls(self) -> None:
        decoder = io.IncrementalNewlineDecoder(None, translate=True)

        assert decoder.decode("a\r") == "a"
        assert decoder.decode("\nb", final=True) == "\nb"


class TestTextTellFollowsTheChunk:
    """`TextIOWrapper.tell()` | O(c): it re-decodes the last chunk, so it grows
    with what the last read decoded and not with the stream, and is O(1) where
    nothing decoded is waiting. `seek(cookie)` | O(1) whatever the chunk."""

    SMALL, LARGE = 2_500, 1_000_000

    @classmethod
    def after_read(cls, size: int) -> io.TextIOWrapper:
        text = io.TextIOWrapper(io.BytesIO(two_byte_text(cls.LARGE * 4)), encoding="utf-8")
        text.read(size)
        return text

    @classmethod
    def after_readline(cls, line: int) -> io.TextIOWrapper:
        data = ("é" * line + "\n").encode("utf-8") * 2
        text = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")
        text.readline()
        text.read(10)
        return text

    @pytest.mark.timing
    def test_tell_grows_with_the_chunk(self) -> None:
        small, large = self.after_read(self.SMALL), self.after_read(self.LARGE)

        durations = [best_ns(small.tell), best_ns(large.tell)]

        assert durations[1] > durations[0] * 20, f"read(2,500) then read(1,000,000): {durations} ns"

    @pytest.mark.timing
    def test_tell_does_not_grow_with_the_stream(self) -> None:
        short, long = self.after_readline(10_000), self.after_readline(1_000_000)

        durations = [best_ns(short.tell, inner=3), best_ns(long.tell, inner=3)]

        assert durations[1] < durations[0] * 3, f"100x the stream, one chunk: {durations} ns"

    @pytest.mark.timing
    def test_tell_is_constant_after_reading_to_the_end(self) -> None:
        text = io.TextIOWrapper(io.BytesIO(two_byte_text(self.LARGE * 4)), encoding="utf-8")
        text.read()
        pending = self.after_read(self.LARGE)

        durations = [best_ns(text.tell, inner=10), best_ns(pending.tell)]

        assert durations[1] > durations[0] * 100, f"at the end, then mid-chunk: {durations} ns"

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("encoding", "character"), [("utf-8", "é"), ("utf-16", "é"), ("latin-1", "é")]
    )
    def test_seek_to_a_cookie_does_not_grow_with_the_chunk(
        self, encoding: str, character: str
    ) -> None:
        def moved(size: int) -> tuple[io.TextIOWrapper, int]:
            text = character * size + "Z" + character * (self.LARGE * 4 - size)
            stream = io.TextIOWrapper(io.BytesIO(text.encode(encoding)), encoding=encoding)
            stream.read(size)
            cookie = stream.tell()
            stream.seek(0)  # drop the decoded chunk, whose freeing is not the seek's cost
            return stream, cookie

        def after_read(size: int) -> Callable[[], Callable[[], object]]:
            def make() -> Callable[[], object]:
                stream, cookie = moved(size)
                return partial(stream.seek, cookie)

            return make

        for size in (self.SMALL, self.LARGE):
            stream, cookie = moved(size)
            stream.seek(cookie)
            assert stream.read(1) == "Z"

        durations = [best_fresh_ns(after_read(size)) for size in (self.SMALL, self.LARGE)]

        assert durations[1] < durations[0] * 10, (
            f"{encoding}, cookies after read(2,500) and read(1,000,000): {durations} ns; "
            "re-decoding to the cookie would cost hundreds of times more"
        )

    @pytest.mark.timing
    def test_seek_to_zero_does_not_grow_either(self) -> None:
        streams = [self.after_read(self.SMALL), self.after_read(self.LARGE)]

        durations = [best_ns(partial(stream.seek, 0)) for stream in streams]

        assert durations[1] < durations[0] * 3, (
            f"seek(0) after read(2,500) then read(1,000,000): {durations} ns"
        )

    def test_a_cookie_brings_back_the_position(self) -> None:
        text = io.TextIOWrapper(io.BytesIO("naïve\ncafé\n".encode()), encoding="utf-8")
        text.readline()
        cookie = text.tell()

        text.readline()
        text.seek(cookie)

        assert text.readline() == "café\n"

    def test_tell_is_refused_inside_a_for_loop(self) -> None:
        text = io.TextIOWrapper(io.BytesIO(b"a\nb\n"), encoding="ascii")

        with pytest.raises(OSError, match="next\\(\\) call"):
            for _ in text:
                text.tell()

    @pytest.mark.parametrize("stream", ["wrapper", "stringio"])
    def test_relative_seeks_are_only_by_zero(self, stream: str) -> None:
        text: io.TextIOBase = (
            io.TextIOWrapper(io.BytesIO(b"abc"), encoding="ascii")
            if stream == "wrapper"
            else io.StringIO("abc")
        )

        assert text.seek(0, os.SEEK_END) == 3
        with pytest.raises(OSError, match="nonzero"):
            text.seek(-1, os.SEEK_CUR)


class TestStringIOCopies:
    """`StringIO` copies its initial value and every `getvalue()`, appends in
    amortized O(k), and converts its buffer once on the first read."""

    def test_the_initial_value_is_copied(self) -> None:
        value = "x" * 1_000_000

        peak = peak_bytes(lambda: io.StringIO(value))

        assert peak > 1_000_000, f"StringIO of a million characters peaked at {peak}"

    @pytest.mark.timing
    def test_construction_grows_with_the_value(self) -> None:
        values = ["x" * 100_000, "x" * 10_000_000]

        durations = [best_ns(partial(io.StringIO, value), repeats=5) for value in values]

        assert durations[1] > durations[0] * 20, f"100x the characters: {durations} ns"

    @pytest.mark.timing
    def test_appending_is_linear(self) -> None:
        def build(rows: int) -> str:
            buffer = io.StringIO()
            for index in range(rows):
                buffer.write(f"row {index}\n")
            return buffer.getvalue()

        durations = [best_ns(partial(build, rows), repeats=5) for rows in (2_000, 20_000, 200_000)]

        for smaller, larger in pairwise(durations):
            assert larger < smaller * 30, f"10x the rows each step: {durations} ns"

    @pytest.mark.timing
    @pytest.mark.parametrize("operation", ["readline", "write"])
    def test_the_first_read_or_inner_write_after_appending_pays_once(self, operation: str) -> None:
        def appended() -> io.StringIO:
            buffer = io.StringIO()
            for _ in range(1_000):
                buffer.write("x" * 999 + "\n")
            buffer.seek(0)
            return buffer

        def call(buffer: io.StringIO) -> Callable[[], object]:
            return buffer.readline if operation == "readline" else partial(buffer.write, "y")

        first = best_fresh_ns(lambda: call(appended()))

        def second_call() -> Callable[[], object]:
            buffer = appended()
            call(buffer)()
            return call(buffer)

        second = best_fresh_ns(second_call)

        assert first > second * 50, f"first {operation} {first} ns, second {second} ns"

    def test_getvalue_after_writes_allocates_the_whole_string(self) -> None:
        buffer = io.StringIO()
        for _ in range(1_000):
            buffer.write("x" * 1_000)

        peak = peak_bytes(buffer.getvalue)

        assert peak > 1_000_000, f"getvalue() of a million characters peaked at {peak}"

    @pytest.mark.parametrize("operation", ["readline", "truncate"])
    def test_converting_after_appends_takes_space_too(self, operation: str) -> None:
        buffer = io.StringIO()
        for _ in range(1_000):
            buffer.write("x" * 999 + "\n")
        buffer.seek(0)

        peak = peak_bytes(
            buffer.readline if operation == "readline" else partial(buffer.truncate, 1)
        )

        assert peak > 1_000_000, f"the first {operation} after appends peaked at {peak}"

    def test_a_write_past_the_end_fills_the_gap(self) -> None:
        text, binary = io.StringIO(), io.BytesIO()
        text.seek(1_000_000)
        binary.seek(TEN_MB)

        text_peak = peak_bytes(partial(text.write, "x"))
        binary_peak = peak_bytes(partial(binary.write, b"x"))

        assert text_peak > 1_000_000, f"one character a million past the end: {text_peak}"
        assert binary_peak > TEN_MB, f"one byte 10 MB past the end: {binary_peak}"
        assert binary.getvalue()[:3] == b"\0\0\0"

    @pytest.mark.timing
    def test_truncating_after_writes_grows_with_the_stream(self) -> None:
        def written(size: int) -> Callable[[], Callable[[], int]]:
            def make() -> Callable[[], int]:
                buffer = io.StringIO()
                buffer.write("x" * size)
                return lambda: buffer.truncate(1)

            return make

        durations = [best_fresh_ns(written(size)) for size in (100_000, 10_000_000)]

        assert durations[1] > durations[0] * 20, f"100x the characters: {durations} ns"

    @pytest.mark.timing
    def test_seek_and_tell_do_not_grow_with_the_stream(self) -> None:
        def seek_and_tell(stream: io.StringIO) -> int:
            stream.seek(500)
            return stream.tell()

        streams = [io.StringIO("x" * size) for size in (1_000, 10_000_000)]

        durations = [best_ns(partial(seek_and_tell, stream), inner=100) for stream in streams]

        assert durations[1] < durations[0] * 3, f"10,000x the characters: {durations} ns"


class TestBytesIOShares:
    """`BytesIO` shares a `bytes` initial value and its `getvalue()` result,
    copying only when a write would change bytes someone else holds, and
    refuses writes while a `getbuffer()` view is open."""

    def test_a_bytes_initial_value_is_shared(self) -> None:
        data = b"x" * TEN_MB

        peak = peak_bytes(lambda: io.BytesIO(data))

        assert peak < SMALL_PEAK, f"BytesIO(bytes) peaked at {peak}"
        assert io.BytesIO(data).getvalue() is data

    def test_any_other_buffer_is_copied(self) -> None:
        data = bytearray(TEN_MB)

        peak = peak_bytes(lambda: io.BytesIO(data))

        assert peak > TEN_MB, f"BytesIO(bytearray) peaked at {peak}"

    def test_getvalue_hands_back_its_own_object(self) -> None:
        stream = io.BytesIO()
        stream.write(b"x" * TEN_MB)
        stream.getvalue()

        peak = peak_bytes(stream.getvalue)

        assert stream.getvalue() is stream.getvalue()
        assert peak < SMALL_PEAK, f"getvalue() after writes peaked at {peak}"

    def test_writing_while_the_value_is_held_copies_once(self) -> None:
        stream = io.BytesIO()
        stream.write(b"x" * TEN_MB)
        held = stream.getvalue()

        first = peak_bytes(lambda: stream.write(b"y"))
        second = peak_bytes(lambda: stream.write(b"y"))

        assert held == b"x" * TEN_MB
        assert first > TEN_MB, f"the first write while shared peaked at {first}"
        assert second < SMALL_PEAK, f"the next write peaked at {second}"

    def test_getbuffer_copies_only_a_shared_stream(self) -> None:
        unshared = io.BytesIO()
        unshared.write(b"x" * TEN_MB)
        data = b"x" * TEN_MB
        shared = io.BytesIO(data)

        unshared_peak = peak_bytes(lambda: unshared.getbuffer().release())
        shared_peak = peak_bytes(lambda: shared.getbuffer().release())

        assert unshared_peak < SMALL_PEAK, f"getbuffer() peaked at {unshared_peak}"
        assert shared_peak > TEN_MB, f"getbuffer() on a shared stream peaked at {shared_peak}"

    def test_an_open_view_refuses_writes_and_copies_getvalue(self) -> None:
        stream = io.BytesIO()
        stream.write(b"abc")
        view = stream.getbuffer()

        view[0] = ord("z")
        for refused in (lambda: stream.write(b"q"), lambda: stream.truncate(0), stream.close):
            with pytest.raises(BufferError):
                refused()
        assert stream.getvalue() == b"zbc"
        assert stream.getvalue() is not stream.getvalue()

        view.release()
        stream.write(b"q")

    @pytest.mark.timing
    def test_truncating_a_shared_stream_copies_what_it_keeps(self) -> None:
        def make(size: int) -> Callable[[], Callable[[], object]]:
            data = b"x" * size

            def build() -> Callable[[], object]:
                stream = io.BytesIO(data)
                return partial(stream.truncate, size // 4)

            return build

        durations = [best_fresh_ns(make(size), repeats=7) for size in (100_000, TEN_MB)]

        assert durations[1] > durations[0] * 20, f"100x the bytes: {durations} ns"

    def test_reads_return_what_was_asked(self) -> None:
        stream = io.BytesIO(b"ab\ncd")
        target = bytearray(2)

        assert stream.read1(1) == b"a"
        assert stream.readline() == b"b\n"
        assert stream.readinto(target) == 2
        assert target == b"cd"

    @pytest.mark.timing
    def test_seek_and_tell_do_not_grow_with_the_stream(self) -> None:
        def make(size: int) -> Callable[[], Callable[[], object]]:
            def build() -> Callable[[], object]:
                stream = io.BytesIO()
                stream.write(b"x" * size)
                return lambda: (stream.seek(size // 2), stream.tell())

            return build

        durations = [best_fresh_ns(make(size), repeats=7) for size in (100_000, TEN_MB)]

        assert durations[1] < durations[0] * 20, f"100x the bytes: {durations} ns"


@pytest.mark.skipif(sys.implementation.name != "cpython", reason="CPython's in-place +=")
class TestStrConcatenation:
    """`+=` on a `str` that something else still refers to copies what came
    before, so the loop is O(n²)."""

    @staticmethod
    def build(rows: int) -> str:
        text = ""
        previous = text
        for _ in range(rows):
            previous = text  # a second reference, so += cannot extend in place
            text += "x" * 19 + "\n"
        assert len(previous) == len(text) - 20
        return text

    @pytest.mark.timing
    def test_an_aliased_loop_is_quadratic(self) -> None:
        durations = [best_ns(partial(self.build, rows), repeats=3) for rows in (250, 2_000, 16_000)]
        ratios = [larger / smaller for smaller, larger in pairwise(durations)]

        assert durations[2] > durations[0] * 500, f"64x rows: {durations} ns, linear is 64x"
        assert ratios[1] > 32, f"8x rows per step: {ratios}; linear is 8x, quadratic 64x"


class TestProtocolsAndConstants:
    """`io.Reader` and `io.Writer` check for one method; the constants and
    exceptions are what the page says they are."""

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_reader_and_writer_check_for_the_method(self) -> None:
        class OnlyRead:
            def read(self, size: int = -1) -> bytes:
                return b""

        assert isinstance(io.BytesIO(), io.Reader)  # type: ignore[attr-defined]
        assert isinstance(OnlyRead(), io.Reader)  # type: ignore[attr-defined]
        assert not isinstance(OnlyRead(), io.Writer)  # type: ignore[attr-defined]
        assert isinstance(io.StringIO(), io.Writer)  # type: ignore[attr-defined]
        assert not isinstance(object(), io.Reader)  # type: ignore[attr-defined]

    def test_constants_and_exceptions(self) -> None:
        assert (io.SEEK_SET, io.SEEK_CUR, io.SEEK_END) == (0, 1, 2)
        assert issubclass(io.UnsupportedOperation, OSError)
        assert issubclass(io.UnsupportedOperation, ValueError)
        assert io.BlockingIOError is BlockingIOError


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
    """Each block runs in its own subprocess and working directory, so the
    temporary file one of them creates cannot leak, and asserts its own
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
        line, source = next((n, s) for n, s in _blocks() if "raw.reads == 10_000" in s)
        mutated = source.replace("raw.reads == 10_000", "raw.reads == 9_999", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
