"""Tests for docs/stdlib/zlib.md.

The page prices every call in the bytes it is given (n) and the bytes it
returns (m), and treats the state a compression or decompression object keeps
as a fixed amount set by `wbits` and `memLevel`. Space is settled by traced
allocation, which `tracemalloc` sees for zlib's own buffers too, so a fixed
state and a copy of the data differ by orders of magnitude. Growth classes are
settled by timing ratios over equal multiplicative steps, and the behaviour the
prose relies on - output caps, leftover input, flush modes, wrappers - by
observing what the calls return.

Measurement scope:

* `compress()` at levels 0, 1, 6 and 9 over 62,500, 500,000 and 4,000,000
  bytes of space-separated pseudo-random words: each 8x step costs between 3x
  and 32x, which excludes O(1) and O(n^2) (64x). Level 0 returns more than n
  bytes, levels 1-9 fewer, and level -1 returns what level 6 does.
* `decompress()` of 20,000,000 zero bytes, compressed to under 40,000 bytes:
  the input expands more than 500x and the traced peak exceeds the output. In a
  timing test, 16x the output (2,000,000 to 32,000,000 zero bytes) costs
  between 4x and 64x.
* `compressobj()` peaks under 1,000,000 traced bytes at the defaults, and
  `wbits=9, memLevel=1` under a quarter of that. Streaming 200 chunks of
  65,536 random bytes, each sliced afresh from the source, through one
  object and discarding the output, peaks under 2,000,000 bytes against
  13,107,200 compressed. `Compress.copy()`, and
  `Decompress.copy()` after 1,000,000 bytes of output, each peak under
  1,000,000 bytes, and a decompressor copied halfway through a stream and the
  original each finish it.
* `Compress.flush()` returns under 300,000 bytes after 1,000,000 and after
  16,000,000 bytes of input, both for random bytes and for word text.
* `Decompress.decompress(bomb, 65_536)` on the 20,000,000-byte bomb returns
  65,536 bytes, peaks under 1,000,000 traced bytes, and leaves the rest of the
  input in `unconsumed_tail`, a different object from the input with the
  leftover's length. `Decompress.flush()` then returns all the remaining
  output, and `max_length=0` returns all of it in one call.
* Looping a whole buffer of 524,288 and 4,194,304 stored random bytes through
  `unconsumed_tail` with a 4,096-byte cap: the 8x step costs more than 24x
  (O(n^2) predicts 64x). Feeding the same buffers in 4,096-byte chunks costs
  under 20x (O(n) predicts 8x).
* `compressobj()` with each of the five strategies over the same three sizes
  of word text, flushed at the end: each 8x step costs between 3x and 32x.
  `decompress(bomb, bufsize=16)` returns all 20,000,000 bytes.
* After `eof`, a second call replaces `unused_data` with a new object holding
  the old bytes plus the new. In a timing test, 512 calls of 65,536 bytes
  after the end cost more than 24x what 64 calls do (O(n^2) predicts 64x).
  Capping a call on a stream followed by a 1,000,000-byte trailer at one
  byte leaves the trailer in `unconsumed_tail`, and `flush()` moves it into
  `unused_data`.
* In timing tests, `compressobj(zdict=...)` costs between 4x and 64x more for
  a 16,000,000-byte dictionary than a 1,000,000-byte one, and the
  `decompress()` call on a zlib stream that needs a 16,000,000-byte
  dictionary costs more than 50x what a 16,000-byte one does; only the zlib
  format is timed. Neither constructor, raw or zlib, peaks over 1,000,000
  bytes with the larger dictionary.
* Flushing after every 1,024-byte chunk of word text: `Z_SYNC_FLUSH` output
  is larger than no intermediate flush, and `Z_FULL_FLUSH` larger again, on
  that input only; a `Z_SYNC_FLUSH` makes everything compressed so far
  decodable. `Compress.flush(Z_TREES)` raises `zlib.error`.
* With `compressobj()`, the zlib stream minus its 2-byte header and 4-byte
  trailer equals the raw (`wbits=-15`) stream; `wbits=31` output is read by
  `gzip.decompress()` and by `wbits=47`. `compress(data, wbits=...)` is
  asserted on 3.11+, and to raise `TypeError` before.
* `unused_data` holds bytes after the end of the stream, `eof` turns true
  there, and a truncated stream raises `zlib.error`.
* Each checksum over 16,000,000 bytes peaks under 1,000 traced bytes, where
  `bytes(view)` of the same input peaks above 15,000,000. In a timing test,
  16x the input (250,000 to 4,000,000 bytes) costs between 4x and 64x.
  Folding 1,000,192 bytes through each function in 4,096-byte, 65,536-byte
  and uneven (1, 7, 4,099 ...) chunks gives the one-shot result, starting from
  0 for `crc32()` and 1 for `adler32()`. A 65,536-byte `memoryview` slice
  shares its input and peaks under 1,000 traced bytes.
* Every fenced block runs in its own subprocess and working directory, and a
  mutated assertion in the checksum block is asserted to make it fail.

Not settled here:

* `ZLIBNG_VERSION` exists only on a 3.14+ build linked against zlib-ng; the
  local build links zlib, so its presence is not observed.
* The state's size is read from zlib's documented memory formula and observed
  only at two parameter settings; other `wbits`/`memLevel` pairs are not
  varied. The raw-stream `decompressobj(wbits=-15, zdict=...)` is observed
  not to copy the dictionary; its time is not measured.
* `Compress.flush()` is bounded by the size of what it returns; its time is
  not measured.
* Relative speed and ratio between levels 1-9 depend on the data and are not
  claimed; only word text, zero bytes and random bytes are measured.
"""

from __future__ import annotations

import gzip
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
from functools import cache
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "zlib.md"
EXPECTED_BLOCKS = 11

CHECKSUMS = pytest.mark.parametrize(
    ("checksum", "start"), [(zlib.crc32, 0), (zlib.adler32, 1)], ids=["crc32", "adler32"]
)


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


@cache
def word_text(size: int, seed: int = 1) -> bytes:
    """`size` bytes of space-separated pseudo-random words."""
    rng = random.Random(seed)
    words = [
        bytes(rng.choice(b"abcdefghij") for _ in range(rng.randint(2, 9))) for _ in range(2_000)
    ]
    return b" ".join(rng.choice(words) for _ in range(size // 4))[:size]


BOMB_SIZE = 20_000_000


@pytest.fixture(scope="module")
def bomb() -> bytes:
    return zlib.compress(b"\0" * BOMB_SIZE, 9)


class TestCompressIsLinearAtEveryLevel:
    """`zlib.compress(data, level)`: O(n) at every level."""

    @pytest.mark.timing
    @pytest.mark.parametrize("level", [0, 1, 6, 9])
    def test_eight_times_the_input_costs_eight_times_the_time(self, level: int) -> None:
        text = word_text(4_000_000)
        sizes = [62_500, 500_000, 4_000_000]
        times = [best_ns(lambda s=s: zlib.compress(text[:s], level), repeats=3) for s in sizes]
        ratios = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]

        assert all(3 < ratio < 32 for ratio in ratios), f"8x steps cost {ratios}"


class TestEveryStrategyIsLinear:
    """`Z_FILTERED`, `Z_HUFFMAN_ONLY`, `Z_RLE`, `Z_FIXED`: they change the output, not the bound."""

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "strategy",
        [zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED, zlib.Z_HUFFMAN_ONLY, zlib.Z_RLE, zlib.Z_FIXED],
        ids=["default", "filtered", "huffman_only", "rle", "fixed"],
    )
    def test_eight_times_the_input_costs_eight_times_the_time(self, strategy: int) -> None:
        text = word_text(4_000_000)

        def deflate(size: int) -> None:
            compressor = zlib.compressobj(strategy=strategy)
            compressor.compress(text[:size])
            compressor.flush()

        sizes = [62_500, 500_000, 4_000_000]
        times = [best_ns(lambda s=s: deflate(s), repeats=3) for s in sizes]
        ratios = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]

        assert all(3 < ratio < 32 for ratio in ratios), f"8x steps cost {ratios}"


class TestCompressionLevels:
    """Level 0 stores; levels 1-9 compress; -1 is level 6."""

    def test_level_zero_returns_more_than_its_input(self) -> None:
        data = word_text(200_000)
        assert len(zlib.compress(data, zlib.Z_NO_COMPRESSION)) > len(data)

    def test_levels_one_to_nine_return_less(self) -> None:
        data = word_text(200_000)
        for level in range(zlib.Z_BEST_SPEED, zlib.Z_BEST_COMPRESSION + 1):
            compressed = zlib.compress(data, level)
            assert len(compressed) < len(data)
            assert zlib.decompress(compressed) == data

    def test_the_default_level_is_six(self) -> None:
        data = word_text(200_000)
        assert zlib.Z_DEFAULT_COMPRESSION == -1
        assert zlib.compress(data) == zlib.compress(data, 6)


class TestDecompressHoldsTheWholeOutput:
    """`zlib.decompress(data)`: O(n + m) time, O(m) space, no cap on m."""

    @pytest.mark.serial
    def test_a_small_input_expands_to_a_large_output(self, bomb: bytes) -> None:
        assert len(bomb) < 40_000
        assert BOMB_SIZE / len(bomb) > 500

        peak = peak_bytes(lambda: zlib.decompress(bomb))

        assert peak > BOMB_SIZE, f"decompressing {BOMB_SIZE} B peaked at {peak} B"

    def test_bufsize_is_only_the_initial_buffer(self, bomb: bytes) -> None:
        assert len(zlib.decompress(bomb, bufsize=16)) == BOMB_SIZE

    @pytest.mark.timing
    def test_sixteen_times_the_output_costs_sixteen_times_the_time(self) -> None:
        small = zlib.compress(b"\0" * 2_000_000, 9)
        large = zlib.compress(b"\0" * 32_000_000, 9)
        zlib.decompress(small)

        ratio = best_ns(lambda: zlib.decompress(large), 5) / best_ns(
            lambda: zlib.decompress(small), 5
        )

        assert 4 < ratio < 64, f"16x the output cost x{ratio:.1f}"


class TestObjectsHoldAFixedState:
    """`compressobj()`, `decompressobj()` and `copy()`: O(1) space."""

    @pytest.mark.serial
    def test_compressobj_allocates_a_fixed_state_set_by_its_parameters(self) -> None:
        default = peak_bytes(zlib.compressobj)
        small = peak_bytes(lambda: zlib.compressobj(wbits=9, memLevel=1))

        assert default < 1_000_000, f"compressobj() peaked at {default} B"
        assert small < default / 4, f"wbits=9, memLevel=1 peaked at {small} B of {default} B"

    @pytest.mark.serial
    def test_streaming_compression_does_not_hold_the_stream(self) -> None:
        source = random.Random(3).randbytes(200 * 65_536)
        compressor = zlib.compressobj()
        compressor.compress(source[:65_536])

        def stream() -> None:
            for start in range(0, len(source), 65_536):
                compressor.compress(source[start : start + 65_536])  # a fresh chunk each time

        peak = peak_bytes(stream)

        assert peak < 2_000_000, f"compressing 200 x 64 KiB peaked at {peak} B"

    @pytest.mark.serial
    def test_copies_duplicate_only_the_state(self) -> None:
        compressor = zlib.compressobj()
        compressor.compress(word_text(1_000_000))
        decompressor = zlib.decompressobj()
        assert len(decompressor.decompress(zlib.compress(word_text(1_000_000)))) == 1_000_000

        assert peak_bytes(compressor.copy) < 1_000_000
        assert peak_bytes(decompressor.copy) < 1_000_000

    def test_a_midstream_copy_continues_independently(self) -> None:
        payload = word_text(1_000_000)
        compressed = zlib.compress(payload)
        half = len(compressed) // 2
        decompressor = zlib.decompressobj()
        head = decompressor.decompress(compressed[:half])
        branch = decompressor.copy()

        assert head + decompressor.decompress(compressed[half:]) == payload
        assert head + branch.decompress(compressed[half:]) == payload
        assert decompressor.eof and branch.eof


class TestCompressFlushEmitsOnlyTheState:
    """`Compress.flush()`: O(1) - however much was compressed before."""

    @pytest.mark.parametrize("kind", ["random", "text"])
    @pytest.mark.parametrize("size", [1_000_000, 16_000_000])
    def test_flush_output_does_not_follow_the_input(self, kind: str, size: int) -> None:
        data = random.Random(4).randbytes(size) if kind == "random" else word_text(size)
        compressor = zlib.compressobj()
        for start in range(0, size, 65_536):
            compressor.compress(data[start : start + 65_536])

        assert len(compressor.flush()) < 300_000


class TestMaxLengthCapsDecompression:
    """`Decompress.decompress(data, max_length)`: m <= a positive max_length; the rest is copied."""

    @pytest.mark.serial
    def test_a_capped_call_does_not_hold_the_whole_output(self, bomb: bytes) -> None:
        decompressor = zlib.decompressobj()
        decompressor.decompress(b"")

        peak = peak_bytes(lambda: decompressor.decompress(bomb, 65_536))

        assert peak < 1_000_000, f"a capped call on the bomb peaked at {peak} B"

    def test_leftover_input_is_copied_into_unconsumed_tail(self, bomb: bytes) -> None:
        decompressor = zlib.decompressobj()
        piece = decompressor.decompress(bomb, 65_536)
        tail = decompressor.unconsumed_tail

        assert len(piece) == 65_536
        assert 0 < len(tail) < len(bomb)
        assert tail is not bomb and bomb.endswith(tail)
        assert not decompressor.eof

    def test_flush_decompresses_the_tail_without_a_cap(self, bomb: bytes) -> None:
        decompressor = zlib.decompressobj()
        piece = decompressor.decompress(bomb, 65_536)

        assert len(piece) + len(decompressor.flush()) == BOMB_SIZE

    def test_a_max_length_of_zero_is_no_limit(self, bomb: bytes) -> None:
        assert len(zlib.decompressobj().decompress(bomb, 0)) == BOMB_SIZE

    def test_flush_copies_a_trailer_left_in_the_tail(self) -> None:
        trailer = b"t" * 1_000_000
        decompressor = zlib.decompressobj()
        piece = decompressor.decompress(zlib.compress(b"ab") + trailer, 1)
        assert len(decompressor.unconsumed_tail) > len(trailer)

        assert piece + decompressor.flush() == b"ab"
        assert decompressor.unused_data == trailer


def _whole_buffer(compressed: bytes, cap: int) -> int:
    decompressor = zlib.decompressobj()
    data, total = compressed, 0
    while data:
        total += len(decompressor.decompress(data, cap))
        data = decompressor.unconsumed_tail
    return total


def _chunked(compressed: bytes, cap: int) -> int:
    decompressor = zlib.decompressobj()
    total = 0
    for start in range(0, len(compressed), cap):
        data = compressed[start : start + cap]
        while data:
            total += len(decompressor.decompress(data, cap))
            data = decompressor.unconsumed_tail
    return total


class TestUnconsumedTailCopiesTheRestOfTheBuffer:
    """Looping one large buffer through `unconsumed_tail` is quadratic; chunks are not."""

    @pytest.mark.timing
    def test_a_whole_buffer_loop_grows_quadratically_and_chunks_linearly(self) -> None:
        rng = random.Random(5)
        small = zlib.compress(rng.randbytes(524_288), 0)
        large = zlib.compress(rng.randbytes(4_194_304), 0)
        assert _whole_buffer(small, 4_096) == _chunked(small, 4_096) == 524_288
        assert _whole_buffer(large, 4_096) == _chunked(large, 4_096) == 4_194_304

        whole = best_ns(lambda: _whole_buffer(large, 4_096), 3) / best_ns(
            lambda: _whole_buffer(small, 4_096), 3
        )
        chunked = best_ns(lambda: _chunked(large, 4_096), 3) / best_ns(
            lambda: _chunked(small, 4_096), 3
        )

        assert whole > 24, f"8x the buffer cost the whole-buffer loop only x{whole:.1f}"
        assert chunked < 20, f"8x the buffer cost the chunked loop x{chunked:.1f}"


class TestInputAfterTheEndIsAppendedToACopy:
    """After `eof`, each call copies `unused_data` to append to it: O(n + m + u)."""

    def test_each_call_replaces_unused_data_with_a_longer_copy(self) -> None:
        decompressor = zlib.decompressobj()
        decompressor.decompress(zlib.compress(b"body"))
        assert decompressor.eof
        decompressor.decompress(b"x" * 1_000)
        before = decompressor.unused_data

        decompressor.decompress(b"y" * 1_000)

        assert decompressor.unused_data is not before
        assert decompressor.unused_data == before + b"y" * 1_000

    @pytest.mark.timing
    def test_feeding_after_eof_is_quadratic_in_the_trailing_bytes(self) -> None:
        stream = zlib.compress(b"body")
        chunk = b"x" * 65_536

        def feed(calls: int) -> None:
            decompressor = zlib.decompressobj()
            decompressor.decompress(stream)
            for _ in range(calls):
                decompressor.decompress(chunk)

        ratio = best_ns(lambda: feed(512), 3) / best_ns(lambda: feed(64), 3)

        assert ratio > 24, f"8x the calls after eof cost only x{ratio:.1f}"


class TestPresetDictionaries:
    """`compressobj(zdict=...)` is O(z) time, O(1) space; `decompressobj` keeps a reference."""

    @pytest.mark.timing
    def test_compressobj_checksums_the_whole_dictionary(self) -> None:
        rng = random.Random(6)
        small, large = rng.randbytes(1_000_000), rng.randbytes(16_000_000)
        zlib.compressobj(zdict=small)

        ratio = best_ns(lambda: zlib.compressobj(zdict=large), 5) / best_ns(
            lambda: zlib.compressobj(zdict=small), 5
        )

        assert 4 < ratio < 64, f"16x the dictionary cost x{ratio:.1f}"

    @pytest.mark.serial
    def test_neither_constructor_copies_the_dictionary(self) -> None:
        zdict = random.Random(7).randbytes(16_000_000)
        zlib.compressobj(zdict=zdict)
        zlib.decompressobj(zdict=zdict)

        assert peak_bytes(lambda: zlib.compressobj(zdict=zdict)) < 1_000_000
        assert peak_bytes(lambda: zlib.compressobj(wbits=-15, zdict=zdict)) < 1_000_000
        assert peak_bytes(lambda: zlib.decompressobj(zdict=zdict)) < 1_000_000
        assert peak_bytes(lambda: zlib.decompressobj(wbits=-15, zdict=zdict)) < 1_000_000

    @pytest.mark.timing
    def test_the_decompress_call_that_needs_the_dictionary_checksums_it(self) -> None:
        rng = random.Random(8)
        payload = b"shared words " * 100

        def stream_and_dict(size: int) -> tuple[bytes, bytes]:
            zdict = rng.randbytes(size)
            compressor = zlib.compressobj(zdict=zdict)
            return compressor.compress(payload) + compressor.flush(), zdict

        small, large = stream_and_dict(16_000), stream_and_dict(16_000_000)

        def decompress(pair: tuple[bytes, bytes]) -> None:
            assert zlib.decompressobj(zdict=pair[1]).decompress(pair[0]) == payload

        ratio = best_ns(lambda: decompress(large), 5) / best_ns(lambda: decompress(small), 5)

        assert ratio > 50, f"1,000x the dictionary cost only x{ratio:.1f}"


class TestFlushModes:
    """`Z_SYNC_FLUSH` makes data so far decodable; each flush costs ratio, `Z_FULL_FLUSH` more."""

    def test_a_sync_flush_makes_the_prefix_readable(self) -> None:
        compressor = zlib.compressobj()
        decompressor = zlib.decompressobj()
        head = compressor.compress(b"first " * 100) + compressor.flush(zlib.Z_SYNC_FLUSH)

        assert decompressor.decompress(head) == b"first " * 100
        assert not decompressor.eof

    def test_frequent_flushes_cost_ratio(self) -> None:
        data = word_text(1_000_000, seed=2)

        def size(mode: int | None) -> int:
            compressor = zlib.compressobj()
            out = []
            for start in range(0, len(data), 1_024):
                out.append(compressor.compress(data[start : start + 1_024]))
                if mode is not None:
                    out.append(compressor.flush(mode))
            out.append(compressor.flush())
            joined = b"".join(out)
            assert zlib.decompress(joined) == data
            return len(joined)

        assert size(None) < size(zlib.Z_SYNC_FLUSH) < size(zlib.Z_FULL_FLUSH)

    def test_compress_flush_rejects_z_trees(self) -> None:
        compressor = zlib.compressobj()
        compressor.compress(b"data")
        with pytest.raises(zlib.error):
            compressor.flush(zlib.Z_TREES)


class TestWbitsChoosesTheWrapper:
    """zlib, raw and gzip wrap the same DEFLATE stream."""

    def _deflate(self, data: bytes, wbits: int) -> bytes:
        compressor = zlib.compressobj(wbits=wbits)
        return compressor.compress(data) + compressor.flush()

    def test_the_zlib_stream_is_the_raw_stream_with_a_header_and_trailer(self) -> None:
        data = word_text(100_000)
        zlib_format, raw = self._deflate(data, 15), self._deflate(data, -15)

        assert zlib_format[2:-4] == raw
        assert zlib_format[-4:] == zlib.adler32(data).to_bytes(4, "big")

    def test_gzip_output_is_read_by_gzip_and_by_auto_detection(self) -> None:
        data = word_text(100_000)
        gzip_format = self._deflate(data, 31)

        assert gzip.decompress(gzip_format) == data
        assert zlib.decompress(gzip_format, wbits=32 + 15) == data

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="version: wbits added in 3.11")
    def test_compress_accepts_wbits(self) -> None:
        data = word_text(100_000)
        compress: Callable[..., bytes] = zlib.compress  # typed for 3.10, which lacks wbits
        assert compress(data, wbits=-15) == self._deflate(data, -15)

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="version: wbits exists from 3.11")
    def test_compress_rejects_wbits_before_3_11(self) -> None:
        compress: Callable[..., bytes] = zlib.compress
        with pytest.raises(TypeError):
            compress(b"data", wbits=-15)


class TestDataAfterTheStream:
    """`unused_data` and `eof`; a truncated stream raises `zlib.error`."""

    def test_trailing_bytes_land_in_unused_data(self) -> None:
        decompressor = zlib.decompressobj()
        assert decompressor.decompress(zlib.compress(b"body") + b"trailer") == b"body"
        assert decompressor.eof
        assert decompressor.unused_data == b"trailer"

    def test_a_truncated_stream_raises(self) -> None:
        with pytest.raises(zlib.error, match="incomplete or truncated"):
            zlib.decompress(zlib.compress(b"body")[:-3])


class TestChecksumsHoldNothingButTheValue:
    """`adler32(data)` / `crc32(data)`: O(1) space."""

    @pytest.mark.serial
    @CHECKSUMS
    def test_the_peak_does_not_follow_the_input(
        self, checksum: Callable[[Any], int], start: int
    ) -> None:
        view = memoryview(b"x" * 16_000_000)
        checksum(view)

        checksummed = peak_bytes(lambda: checksum(view))
        copied = peak_bytes(lambda: bytes(view))

        assert checksummed < 1_000, f"a checksum of 16 MB peaked at {checksummed} B"
        assert copied > 15_000_000, f"the copying control peaked at only {copied} B"


class TestChecksumsReadTheInputOnce:
    """`adler32(data)` / `crc32(data)`: O(n) time, n = len(data)."""

    @pytest.mark.timing
    @CHECKSUMS
    def test_sixteen_times_the_input_costs_sixteen_times_the_time(
        self, checksum: Callable[[Any], int], start: int
    ) -> None:
        small, large = b"x" * 250_000, b"x" * 4_000_000
        checksum(small)

        ratio = best_ns(lambda: checksum(large)) / best_ns(lambda: checksum(small))

        assert 4 < ratio < 64, f"16x the input cost x{ratio:.1f}"


class TestTheValueArgumentContinuesAChecksum:
    """Passing the previous result as `value` continues a running checksum."""

    @CHECKSUMS
    def test_the_defaults_are_the_empty_input_s_checksum(
        self, checksum: Callable[..., int], start: int
    ) -> None:
        assert checksum(b"") == start
        assert checksum(b"abc", start) == checksum(b"abc")

    @CHECKSUMS
    @pytest.mark.parametrize("sizes", [[4_096], [65_536], [1, 7, 4_099, 65_537, 3]])
    def test_any_chunking_gives_the_one_shot_result(
        self, checksum: Callable[..., int], start: int, sizes: list[int]
    ) -> None:
        data = bytes(range(256)) * 3_907
        view = memoryview(data)
        running, offset, turn = start, 0, 0
        while offset < len(data):
            size = sizes[turn % len(sizes)]
            running = checksum(view[offset : offset + size], running)
            offset += size
            turn += 1

        assert turn > 1
        assert running == checksum(data)

    @pytest.mark.serial
    def test_the_example_s_memoryview_slices_do_not_copy(self) -> None:
        data = b"payload " * 100_000
        chunk = memoryview(data)[65_536 : 2 * 65_536]

        assert chunk.obj is data
        assert peak_bytes(lambda: memoryview(data)[65_536 : 2 * 65_536]) < 1_000


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
    """Each block runs in its own subprocess and working directory."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert running_crc == crc" in s)
        mutated = source.replace("assert running_crc == crc", "assert running_crc != crc", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
