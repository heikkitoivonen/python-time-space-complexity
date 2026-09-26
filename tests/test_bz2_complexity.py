"""Tests for docs/stdlib/bz2.md.

The page prices bzip2 in the bytes that go in and come out, and in the block
size B that libbzip2 works in: a compressor returns nothing until a block
fills, a decompressor returns nothing until a whole compressed block is in,
one-shot calls hold the whole result, and a file object decompresses as it is
read. Block behaviour is settled by observing what a call returns, space by
traced allocation, laziness and seeking by a `BytesIO` that counts the bytes
taken from it, the multi-stream cost by a decompressor proxy that counts the
bytes handed to it, and the one timed row by ratios far from the excluded
growth classes.

Measurement scope:

* `compress()` of 20,000,000 identical bytes at level 1 peaks under 2 MB,
  about the same as compressing 1,000 bytes, so neither the input nor a
  buffer sized for it is held. Building a `BZ2Compressor` at level 9 peaks more
  than 4x higher than at level 1; libbzip2's compressor allocates through
  `PyMem_RawMalloc`, which `tracemalloc` traces. At levels 1 and 9, 16x the
  generated text (250,000 to 4,000,000 bytes) costs between 8x and 32x the
  time.
* `decompress()` of one 10,000,000-byte stream peaks above 5 MB. Over 1,000
  concatenated 37-byte streams it hands the decompressors it creates more
  than s·n/4 bytes in total, where n is the input's length: every stream
  recopies the rest. A `BZ2File` over 1,000 streams of 4,000 random bytes
  hands them at most n plus one read buffer (`io.DEFAULT_BUFFER_SIZE`, 8 KiB
  before 3.14 and 128 KiB from it) per stream, and fewer than s·n/8.
  Garbage raises `OSError`, a truncated stream `ValueError`, and trailing
  bytes that are not a stream are dropped.
* Blocks: at level 1, `compress()` of 50,000 bytes returns `b''` and of
  150,000 random bytes returns a block's worth; after 1,050,000 random bytes,
  `flush()` returns under 120,000 bytes. A one-block stream fed all but its
  last 100 bytes returns `b''`, and the rest returns the whole block.
  `read(1)` from a 90,000-byte one-block level-1 file takes every compressed
  byte of it. After `flush()`, `compress()` and `flush()` raise `ValueError`.
* `BZ2Decompressor.decompress(max_length=4096)` on a 10,000,000-byte bomb
  returns exactly 4096 bytes with `needs_input` false. With
  `max_length=1000` on the 5,000,000-byte level-1 compression of random data,
  the call peaks above 4 MB: the unconsumed input is copied and held. A call
  after `eof` raises `EOFError`; `unused_data` is `b''` before `eof`, the
  trailing bytes after it, and the same object on a second access.
* `BZ2File` and `open()` take nothing from a counting source when built for
  reading. On 4,000,000 random bytes compressed at level 1 (B = 100 kB),
  `read(1000)` takes at most one block plus one read buffer; within 250,000
  bytes, a forward seek to 2,000,000 takes 2,000,000, a further seek to
  3,000,000 takes 1,000,000 more, a backward seek to 1,000,000 takes
  1,000,000 from offset zero, and `SEEK_END` takes the remaining 3,000,000;
  after rewinding, `seek(-3_000_000, SEEK_END)` takes 1,000,000, so the size
  is kept. A 500-byte backward seek inside the read buffer takes nothing.
  `read(100_000_000)` and `read1(100_000_000)` on a one-byte file each peak
  above 50 MB, so a read's space follows the size it asks for.
  `peek()` does not move `tell()`. Concatenated streams read back in turn,
  including one appended in `'ab'` mode. `write()` of 13 bytes and `flush()`
  leave the target empty, `writelines()` of 150,000 random bytes at level 1
  passes over 90,000 bytes on, and `close()` writes the rest; `close()` leaves a wrapped
  `BytesIO` open and closes a file it opened. `closed`, `fileno()`,
  `readable()`, `writable()` and `seekable()` are asserted by value, and
  `mode` and `name` from 3.13; a text mode returns an `io.TextIOWrapper`.
* `compression.bz2` is asserted to be this module's names from 3.14.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* O(m) rather than O(m log m) for compression rests on libbzip2 sorting each
  block of at most B bytes on its own; a 16x timing step cannot separate the
  two, and only excludes constant and quadratic growth. Only generated text
  is timed; input content beyond that text, random bytes and runs of one
  byte is not varied, nor are levels 2 to 8.
* The decompressor's working memory is allocated by libbzip2 with `malloc`,
  which `tracemalloc` does not see, so that it is set by the stream's block
  size and does not grow with the input is read from the bzip2
  documentation, not measured.
* The O(B) term in decompression and read rows is observed as input taken,
  not timed: nothing comes out until the block's compressed bytes are in.
* That the multi-stream proxies' counts are copies, rather than views, is
  read from `decompress()` taking `unused_data` (a new `bytes`) in Lib/bz2.py
  and from `BZ2Decompressor` building it with `PyBytes_FromStringAndSize` in
  Modules/_bz2module.c; the tests count bytes handed over.
* Bounds are in the bytes that go in and come out. Input whose compressed
  bytes produce no output - many empty concatenated streams, or
  `writelines()` over many empty items - costs time in the streams or items
  passed over, is not measured, and is outside those bounds.
* `BZ2File.raw` is reported by the audit's runtime inspection although the
  class does not have it, and the inherited `readinto1()`, `detach()`,
  `truncate()` and `isatty()` are the `io` base class's; the page documents
  none of them.
"""

from __future__ import annotations

import bz2
import functools
import io
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "bz2.md"
EXPECTED_BLOCKS = 6


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
def compressed_random(size: int, level: int) -> bytes:
    return bz2.compress(random_bytes(size), level)


class CountingBytesIO(io.BytesIO):
    """A `BytesIO` that records how many bytes have been read from it."""

    taken = 0

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        self.taken += len(data)
        return data


class FedCounter:
    """Wraps `BZ2Decompressor` and counts the bytes handed to every instance."""

    fed = 0

    def __init__(self, real: Any) -> None:
        self.real = real

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        counter = self
        inner = self.real(*args, **kwargs)

        class Proxy:
            def decompress(self, data: bytes, max_length: int = -1) -> bytes:
                counter.fed += len(data)
                return inner.decompress(data, max_length)

            def __getattr__(self, name: str) -> Any:
                return getattr(inner, name)

        return Proxy()


class TestOneShotCompress:
    """`compress(data, compresslevel=9)` | O(m) | O(n): memory follows the
    output, and the working memory is set by the level, not the input."""

    def test_memory_follows_the_output_not_the_input(self) -> None:
        data = b"x" * 20_000_000
        small = b"x" * 1_000

        large_peak = peak_bytes(lambda: bz2.compress(data, 1))
        small_peak = peak_bytes(lambda: bz2.compress(small, 1))

        assert len(bz2.compress(data, 1)) < 1_000
        assert large_peak < 2_000_000, f"20 MB of input peaked at {large_peak} bytes"
        assert large_peak < small_peak * 1.5, f"{large_peak} for 20 MB, {small_peak} for 1 KB"

    def test_the_level_sets_the_working_memory(self) -> None:
        level_1 = peak_bytes(lambda: bz2.BZ2Compressor(1))
        level_9 = peak_bytes(lambda: bz2.BZ2Compressor(9))

        assert level_9 > level_1 * 4, f"level 1 {level_1} bytes, level 9 {level_9}"

    @pytest.mark.timing
    @pytest.mark.parametrize("level", [1, 9])
    def test_time_scales_with_the_input(self, level: int) -> None:
        small = generated_text(250_000)
        large = generated_text(4_000_000)

        small_ns = best_ns(lambda: bz2.compress(small, level))
        large_ns = best_ns(lambda: bz2.compress(large, level))

        ratio = large_ns / small_ns
        assert 8 < ratio < 32, f"16x the text at level {level} cost x{ratio:.2f}"

    def test_the_level_range_and_its_error(self) -> None:
        for level in (0, 10):
            with pytest.raises(ValueError, match="between 1 and 9"):
                bz2.compress(b"data", level)
            with pytest.raises(ValueError, match="between 1 and 9"):
                bz2.BZ2Compressor(level)


class TestDecompress:
    """`decompress(data)` | O(n + m) | O(m) for one stream, and O(s·n + m)
    over s concatenated streams; a `BZ2File` recopies at most one read buffer
    per stream."""

    def test_one_stream_holds_the_output(self) -> None:
        payload = bz2.compress(b"x" * 10_000_000)

        peak = peak_bytes(lambda: bz2.decompress(payload))

        assert len(payload) < 1_000
        assert peak > 5_000_000, f"a 10 MB result peaked at {peak} bytes"

    def test_every_stream_recopies_the_rest_of_the_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        streams = 1_000
        data = bz2.compress(b"x") * streams
        counter = FedCounter(bz2.BZ2Decompressor)
        monkeypatch.setattr(bz2, "BZ2Decompressor", counter)

        assert bz2.decompress(data) == b"x" * streams

        n = len(data)
        assert counter.fed > streams * n // 4, (
            f"{streams} streams of {n} bytes fed {counter.fed} bytes; linear would be ~{n}"
        )

    def test_a_bz2file_recopies_up_to_one_buffer_per_stream(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        streams = 1_000
        record = random_bytes(4_000)
        data = bz2.compress(record) * streams
        counter = FedCounter(bz2.BZ2Decompressor)
        monkeypatch.setattr(bz2, "BZ2Decompressor", counter)

        with bz2.BZ2File(io.BytesIO(data)) as f:
            assert f.read() == record * streams

        n, buffer = len(data), io.DEFAULT_BUFFER_SIZE
        assert counter.fed <= n + buffer * streams, f"fed {counter.fed} bytes for {n}"
        assert counter.fed < streams * n // 8, f"fed {counter.fed} bytes for {n}"

    def test_bad_input(self) -> None:
        with pytest.raises(OSError, match="Invalid data stream"):
            bz2.decompress(b"garbage!")
        with pytest.raises(ValueError, match="ended before"):
            bz2.decompress(bz2.compress(b"x" * 1_000)[:-3])
        assert bz2.decompress(bz2.compress(b"ok") + b"junk") == b"ok"


class TestBlocksAreTheUnitOfWork:
    """The compressor returns `b''` until a block fills and `flush()` holds at
    most one block; the decompressor returns nothing until a whole compressed
    block is in."""

    def test_nothing_comes_out_until_a_block_fills(self) -> None:
        compressor = bz2.BZ2Compressor(1)

        assert compressor.compress(generated_text(50_000)) == b""
        assert len(bz2.BZ2Compressor(1).compress(random_bytes(150_000))) > 90_000

    def test_flush_emits_at_most_one_block(self) -> None:
        compressor = bz2.BZ2Compressor(1)
        compressor.compress(random_bytes(1_050_000))

        assert len(compressor.flush()) < 120_000

    def test_a_flushed_compressor_cannot_be_used_again(self) -> None:
        compressor = bz2.BZ2Compressor()
        compressor.compress(b"data")
        compressor.flush()

        with pytest.raises(ValueError, match="flushed"):
            compressor.compress(b"more")
        with pytest.raises(ValueError, match="Repeated call"):
            compressor.flush()

    def test_the_decompressor_waits_for_the_whole_block(self) -> None:
        data = generated_text(90_000)
        stream = bz2.compress(data, 1)
        decompressor = bz2.BZ2Decompressor()

        assert decompressor.decompress(stream[:-100]) == b""
        assert decompressor.decompress(stream[-100:]) == data
        assert decompressor.eof

    def test_reading_one_byte_takes_the_whole_block(self) -> None:
        data = generated_text(90_000)
        stream = bz2.compress(data, 1)
        source = CountingBytesIO(stream)

        with bz2.BZ2File(source) as f:
            assert f.read(1) == data[:1]

        assert source.taken == len(stream)


class TestStreamingDecompressor:
    """`BZ2Decompressor.decompress(data, max_length=-1)` | O(h + c + r + B):
    `max_length` bounds the output, unconsumed input is copied and held, and
    the decompressor handles one stream."""

    def test_max_length_bounds_the_output(self) -> None:
        bomb = bz2.compress(b"\0" * 10_000_000)
        decompressor = bz2.BZ2Decompressor()

        chunk = decompressor.decompress(bomb, max_length=4096)

        assert chunk == b"\0" * 4096
        assert decompressor.needs_input is False
        assert decompressor.eof is False

    def test_unconsumed_input_is_copied_and_held(self) -> None:
        compressed = compressed_random(5_000_000, 1)
        decompressor = bz2.BZ2Decompressor()

        peak = peak_bytes(lambda: decompressor.decompress(compressed, max_length=1000))

        assert peak > 4_000_000, f"holding {len(compressed)} bytes peaked at {peak}"
        rest = decompressor.decompress(b"")
        while not decompressor.eof:
            rest += decompressor.decompress(b"")
        assert len(rest) == 5_000_000 - 1000

    def test_one_stream_only(self) -> None:
        decompressor = bz2.BZ2Decompressor()
        decompressor.decompress(bz2.compress(b"data"))

        assert decompressor.eof
        with pytest.raises(EOFError, match="already reached"):
            decompressor.decompress(b"more")

    def test_unused_data_holds_the_tail_once_the_stream_ends(self) -> None:
        decompressor = bz2.BZ2Decompressor()
        assert decompressor.unused_data == b""
        assert decompressor.needs_input is True

        decompressor.decompress(bz2.compress(b"data") + b"tail")

        assert decompressor.unused_data == b"tail"
        assert decompressor.unused_data is decompressor.unused_data


class TestBZ2File:
    """`BZ2File` and `open()` read nothing until asked, decompress what is
    read a block at a time, emulate `seek()` by decompressing, and write only
    as blocks fill."""

    SIZE = 4_000_000

    @property
    def compressed(self) -> bytes:
        return compressed_random(self.SIZE, 1)

    @property
    def payload(self) -> bytes:
        return random_bytes(self.SIZE)

    def test_opening_reads_nothing(self) -> None:
        source = CountingBytesIO(self.compressed)

        bz2.BZ2File(source)
        bz2.open(source)
        bz2.open(source, "rt", encoding="latin-1")

        assert source.taken == 0

    def test_a_small_read_takes_one_block(self) -> None:
        source = CountingBytesIO(self.compressed)

        with bz2.BZ2File(source) as f:
            assert f.read(1000) == self.payload[:1000]

        assert source.taken <= 110_000 + io.DEFAULT_BUFFER_SIZE, f"took {source.taken} bytes"

    def test_seek_decompresses_forward_and_rewinds_backward(self) -> None:
        source = CountingBytesIO(self.compressed)
        f = bz2.BZ2File(source)
        slack = 250_000

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
        with bz2.BZ2File(source) as f:
            f.seek(2_000_000)
            f.read(1000)
            source.taken = 0

            f.seek(2_000_500)

            assert source.taken == 0
            assert f.tell() == 2_000_500
            assert f.read(10) == self.payload[2_000_500:2_000_510]

    def test_peek_does_not_move_the_position(self) -> None:
        with bz2.BZ2File(io.BytesIO(self.compressed)) as f:
            f.read(10)
            peeked = f.peek(1)

            assert peeked.startswith(self.payload[10:11])
            assert f.tell() == 10

    def test_lines_and_iteration(self) -> None:
        text = b"".join(f"line {i}\n".encode() for i in range(100))

        with bz2.BZ2File(io.BytesIO(bz2.compress(text))) as f:
            assert f.readline() == b"line 0\n"
            assert f.readlines(10) == [b"line 1\n", b"line 2\n"]
            assert list(f)[-1] == b"line 99\n"

    @pytest.mark.parametrize("method", ["read", "read1"])
    def test_a_read_allocates_the_size_it_asks_for(self, method: str) -> None:
        f = bz2.BZ2File(io.BytesIO(bz2.compress(b"x")))
        read = getattr(f, method)

        peak = peak_bytes(lambda: read(100_000_000))

        assert peak > 50_000_000, f"{method}(100_000_000) of one byte peaked at {peak}"
        f.close()

    def test_readinto_and_read1(self) -> None:
        with bz2.BZ2File(io.BytesIO(self.compressed)) as f:
            buffer = bytearray(100)
            assert f.readinto(buffer) == 100
            assert bytes(buffer) == self.payload[:100]
            assert 0 < len(f.read1(1000)) <= 1000

    def test_concatenated_streams_read_in_turn(self) -> None:
        target = io.BytesIO()
        with bz2.BZ2File(target, "wb") as f:
            f.write(b"one")
        with bz2.BZ2File(target, "ab") as f:
            f.write(b"two")

        assert bz2.decompress(target.getvalue()) == b"onetwo"
        target.seek(0)
        with bz2.BZ2File(target) as f:
            assert f.read() == b"onetwo"

    def test_output_waits_for_a_block_or_close(self) -> None:
        target = io.BytesIO()
        f = bz2.BZ2File(target, "wb", compresslevel=1)

        assert f.write(b"small record\n") == 13
        f.flush()
        assert target.getvalue() == b""
        assert f.tell() == 13

        f.writelines([random_bytes(150_000)])
        assert len(target.getvalue()) > 90_000, "a full block was held back"

        f.close()
        assert bz2.decompress(target.getvalue()) == b"small record\n" + random_bytes(150_000)

    def test_close_closes_only_a_file_it_opened(self, tmp_path: pathlib.Path) -> None:
        wrapped = io.BytesIO()
        with bz2.BZ2File(wrapped, "wb") as f:
            f.write(b"data")
        assert not wrapped.closed
        assert f.closed

        path = tmp_path / "data.bz2"
        with bz2.open(path, "wb") as named:
            assert named.writable() and not named.readable()
            assert isinstance(named.fileno(), int)
            inner = named._fp  # pyright: ignore[reportAttributeAccessIssue]  # noqa: SLF001
            named.write(b"data")
        assert inner.closed

        with bz2.open(path) as f:
            assert f.readable() and f.seekable() and not f.writable()
            assert f.read() == b"data"
        assert f.closed

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_mode_and_name(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "data.bz2"
        with bz2.BZ2File(path, "wb") as f:
            assert f.mode == "wb"
            assert f.name == str(path)
        with bz2.BZ2File(path) as f:
            assert f.mode == "rb"

    def test_text_mode_wraps_in_a_text_wrapper(self) -> None:
        with bz2.open(io.BytesIO(bz2.compress(b"a\nb\n")), "rt", encoding="ascii") as f:
            assert isinstance(f, io.TextIOWrapper)
            assert f.read() == "a\nb\n"


class TestVersionNotes:
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_compression_bz2_is_this_module(self) -> None:
        from compression import bz2 as reexported

        for name in bz2.__all__:
            assert getattr(reexported, name) is getattr(bz2, name)


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
