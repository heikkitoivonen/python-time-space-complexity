"""Tests for docs/stdlib/compression.md.

The package exists from Python 3.14, and `compression.zstd` only where CPython
was built with libzstd, so this file skips on older interpreters and on builds
without it. The page prices Zstandard in the bytes that go in and come out:
one-shot calls hold the whole input's worth of output, streaming calls hold one
chunk, and a file object decompresses as it is read. Space is settled by traced
allocation of the Python-visible buffers, laziness and re-reading by a
`BytesIO` that counts the bytes taken from it, the multi-frame cost by a
decompressor proxy that counts the bytes handed to it, and the remaining rows by
observation or by timing ratios far from the excluded growth class.

Measurement scope:

* The four re-exporting submodules are asserted to carry each public name of
  the standalone module as the same object (`__all__` where the module has
  one, otherwise every non-underscore name).
* `compress()` of 10,000,000 identical bytes peaks above 5 MB for an output
  under 1 KB, and 100x the input raises the peak more than 50x. At the default
  level, 16x the text (250,000 to 4,000,000 bytes of generated JSON) costs
  between 4x and 64x the time; at level 19 the same 16x step, from 62,500
  bytes, does too. Level 19 is asserted more than 5x slower than level 1 on
  1,000,000 bytes of that text and to produce the smaller output.
* Dictionaries: `compress()` of a 5-byte record with a plain 1 MiB
  raw-content dictionary costs more than 16x the same call with an 8 KiB one.
  Passing `as_digested_dict` costs under 3x across those two sizes and is more
  than 16x cheaper than the plain 1 MiB call. `ZstdCompressor(zstd_dict=zd)`
  costs more than 8x as much at 1 MiB as at 8 KiB. Given a fresh 1 MiB
  dictionary's `as_digested_dict`, the first compressor at level 3 and the
  first at level 5 each cost more than 20x a later one at the same level. Repeated `decompress()`
  with the dictionary itself costs under 3x across the two sizes once it is
  digested; over five fresh 1 MiB `ZstdDict`s, all kept alive, the fastest
  first `ZstdDecompressor()` costs more than 20x the fastest of 40 later rounds, and passing
  the 1 MiB one's `as_undigested_dict` instead costs more than 8x as much.
* `decompress()` over 1,000 concatenated 67-byte frames hands the
  decompressors it creates more than f·n/4 bytes in total, where n is the
  input's length: every frame recopies the tail. Splitting the same input
  with `get_frame_size()` and decompressing frame by frame hands them exactly
  n. A `ZstdFile` over 1,000 frames of 4,000 random bytes hands its
  decompressors more than 4n, and at most n plus two 128 KiB read buffers
  (`io.DEFAULT_BUFFER_SIZE` on 3.14) per frame. One 10,000,000-byte frame
  decompresses with a peak above 5 MB.
* `ZstdCompressor.compress()` over 1,000 chunks of 64 KiB peaks under 3x one
  chunk; a 10-byte chunk returns `b''`. After 8,000,000 bytes of text fed with
  `CONTINUE`, `flush()` returns under 150,000 bytes. `last_mode` starts at
  `FLUSH_FRAME` and follows the last call. `set_pledged_input_size()` puts the
  size in the header and raises `ValueError` mid-frame. Output ending in
  `FLUSH_BLOCK` decompresses to everything fed so far without reaching
  `eof`.
* `ZstdDecompressor.decompress(max_length=4096)` on a 1,000,000-byte bomb
  returns exactly 4096 bytes with `needs_input` false. With `max_length=1000`
  on 5,000,000 bytes of compressed random data, the unconsumed input is copied
  and held: the call peaks above 4 MB. Holding half of that input, a call
  adding 1,000 bytes allocates above 0.8 of the held half, and the output
  through `eof` is intact; that the allocation is a copy of the held bytes
  into a larger buffer is read from `stream_decompress_lock_held` in
  Modules/_zstd/decompressor.c. A second frame's worth of input after
  `eof` raises `EOFError`; `unused_data` is `b''` before `eof`, the trailing
  bytes after it, and the same object on a second access.
* `ZstdFile` and `open()` take nothing from a counting source when built for
  reading. Reading 1,000 bytes of a 4,000,000-byte random-data file takes at
  most one 128 KiB read buffer of it. On that file, within 200,000 bytes, a
  forward seek to 2,000,000 takes 2,000,000 bytes, a further seek to
  3,000,000 takes 1,000,000 more, a backward seek to 1,000,000 takes 1,000,000
  from offset zero, a 500-byte backward seek inside the read buffer takes
  nothing, and `SEEK_END` takes the remaining 3,000,000; after
  rewinding, `seek(-3_000_000, SEEK_END)` takes 1,000,000, so the size is
  kept. `peek()` does not move `tell()`. Concatenated
  frames read back in turn. `write()` of incompressible data reaches the
  target before `flush()`; `flush()` makes all written data decompressible;
  `close()` leaves a wrapped `BytesIO` open and closes a file it opened.
  `mode`, `name`, `fileno()`, `closed`, `readable()`, `writable()` and
  `seekable()` are asserted by value; a text mode returns an
  `io.TextIOWrapper`.
* `train_dict()` over 1,000 and 16,000 generated JSON samples at a fixed
  `dict_size` of 8 KiB, and `finalize_dict()` over 2,000 and 32,000, cost
  between 4x and 64x apart; over 8,000 samples both peak above the joined
  samples' length. `ZstdDict()` copies its content, `dict_content` is a new object on
  each access with a traced peak above d, `len()` is d, `dict_id` is zero for
  raw content, and non-dictionary content raises `ValueError`.
* `get_frame_info()` on frames of 100 and 100,000 blocks costs under 3x
  apart, and `get_frame_size()` more than 50x apart; `get_frame_size()` stops
  at the end of the frame. `decompressed_size` is `None` for a streamed frame
  and for `compress()` with `content_size_flag` off, and `dictionary_id` is
  the dictionary's id.
* Parameter bounds, the level range and its `ValueError`, `ZstdError` for
  garbage and truncated input, `window_log_max` rejecting a frame with a
  larger window, the `Strategy` order, the default level and the version
  attributes are asserted directly.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The compressor's and decompressor's working memory is allocated by libzstd
  with `malloc`, which `tracemalloc` does not see; the page keeps it out of
  the Space column and the tests measure only Python-visible buffers.
* Linearity is timed at levels 3 and 19 on one generated JSON text.
  Other levels, including 20-22 and the negative levels, follow from libzstd
  bounding the search at each position by the level's parameters; they are
  not timed. Input content beyond that text, random bytes and runs of one
  byte is not varied.
* `train_dict()` and `finalize_dict()` are varied in the sample bytes only,
  at one `dict_size` and one sample shape; the trainer is libzstd's.
* `nb_workers` and the other multi-threading parameters, and long distance
  matching, are not exercised.
* Read, peek and seek bounds are in the uncompressed bytes they return or pass
  over. Input carrying compressed bytes with no output, such as long runs of
  empty or skippable frames, is not measured and is outside those bounds.
* The one-block bound on `flush()` holds for the single-threaded compressor
  the page assumes; with `nb_workers` above 0 a flush can drain whole jobs.
* That the multi-frame proxies' counts are copies, rather than views, is read
  from `decompress()` taking `unused_data` (a new `bytes`) in
  Lib/compression/zstd/__init__.py; the tests count bytes handed over.
* `ZstdDict.as_prefix` exists at runtime but is not in the official
  reference, and `ZstdFile.raw` is reported by the audit's runtime
  inspection although instances do not have it; the page documents neither.
"""

from __future__ import annotations

import importlib
import io
import json
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

if sys.version_info < (3, 14):
    pytest.skip("the compression package is new in Python 3.14", allow_module_level=True)

zstd: Any = pytest.importorskip("compression.zstd")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "compression.md"
EXPECTED_BLOCKS = 8


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
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def json_text(records: int, seed: int = 1) -> bytes:
    """Compressible, realistic text: newline-separated JSON records."""
    rng = random.Random(seed)
    words = [f"w{index}" for index in range(500)]
    return b"".join(
        json.dumps(
            {"id": rng.randrange(10**6), "name": " ".join(rng.choice(words) for _ in range(8))}
        ).encode()
        + b"\n"
        for _ in range(records)
    )


def json_samples(count: int, seed: int = 2) -> list[bytes]:
    return json_text(count, seed).splitlines()


def random_bytes(size: int, seed: int = 3) -> bytes:
    return random.Random(seed).randbytes(size)


class CountingBytesIO(io.BytesIO):
    """A `BytesIO` that records how many bytes have been read from it."""

    taken = 0

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        self.taken += len(data)
        return data


class FedCounter:
    """Wraps `ZstdDecompressor` and counts the bytes handed to every instance."""

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


class TestPackageModulesReexport:
    """`compression.zlib`, `.gzip`, `.bz2`, `.lzma` re-export the standalone
    modules' public names as the same objects."""

    @pytest.mark.parametrize("name", ["zlib", "gzip", "bz2", "lzma"])
    def test_every_public_name_is_the_same_object(self, name: str) -> None:
        standalone = importlib.import_module(name)
        packaged = importlib.import_module(f"compression.{name}")
        public = getattr(standalone, "__all__", None) or [
            attr for attr in dir(standalone) if not attr.startswith("_")
        ]

        assert packaged is not standalone
        assert public
        for attr in public:
            assert getattr(packaged, attr) is getattr(standalone, attr), f"{name}.{attr}"


class TestOneShotCompressHoldsTheInputsWorth:
    """`compress(data)` | O(m) | O(m): the output buffer is sized for
    incompressible input, so memory follows m whatever the ratio."""

    def test_memory_follows_the_input_not_the_output(self) -> None:
        data = b"x" * 10_000_000
        output = zstd.compress(data)

        peak = peak_bytes(lambda: zstd.compress(data))

        assert len(output) < 1_000
        assert peak > 5_000_000, f"compress() of 10 MB peaked at {peak} bytes"

    def test_memory_grows_with_the_input(self) -> None:
        small, large = b"x" * 100_000, b"x" * 10_000_000

        peaks = [peak_bytes(lambda d=d: zstd.compress(d)) for d in (small, large)]  # type: ignore[misc]

        assert peaks[1] > peaks[0] * 50, f"100x the input: {peaks}"

    @pytest.mark.timing
    def test_time_is_linear_at_the_default_level(self) -> None:
        text = json_text(70_000)
        small, large = text[:250_000], text[:4_000_000]
        assert len(large) == 4_000_000

        durations = [best_ns(lambda d=d: zstd.compress(d), repeats=5) for d in (small, large)]  # type: ignore[misc]
        ratio = durations[1] / durations[0]

        assert 4 < ratio < 64, f"16x the text: {durations} ns, x{ratio:.1f}; quadratic is x256"


class TestCompressionLevels:
    """Each level is linear in the input; higher levels search more per byte,
    taking longer, usually for a smaller result."""

    TEXT = json_text(20_000)

    @pytest.mark.timing
    def test_level_19_is_linear(self) -> None:
        small, large = self.TEXT[:62_500], self.TEXT[:1_000_000]
        assert len(large) == 1_000_000

        durations = [
            best_ns(lambda d=d: zstd.compress(d, level=19), repeats=3)  # type: ignore[misc]
            for d in (small, large)
        ]
        ratio = durations[1] / durations[0]

        assert 4 < ratio < 64, f"16x the text at level 19: x{ratio:.1f}; quadratic is x256"

    @pytest.mark.timing
    def test_level_19_is_slower_than_level_1_for_a_smaller_result(self) -> None:
        data = self.TEXT[:1_000_000]

        fast = best_ns(lambda: zstd.compress(data, level=1), repeats=3)
        slow = best_ns(lambda: zstd.compress(data, level=19), repeats=3)

        assert slow > fast * 5, f"level 19 took {slow:.0f} ns against level 1's {fast:.0f}"
        assert len(zstd.compress(data, level=19)) < len(zstd.compress(data, level=1))

    def test_the_level_range_and_its_error(self) -> None:
        lower, upper = zstd.CompressionParameter.compression_level.bounds()

        assert lower < 0 < zstd.COMPRESSION_LEVEL_DEFAULT < upper
        assert zstd.decompress(zstd.compress(b"abc", level=upper)) == b"abc"
        assert zstd.decompress(zstd.compress(b"abc", level=lower)) == b"abc"
        with pytest.raises(ValueError, match="valid range"):
            zstd.compress(b"abc", level=upper + 1)


class TestDecompress:
    """`decompress(data)` | O(n + m) | O(n + m) for one frame, and
    O(f·n + m) over f concatenated frames; splitting with `get_frame_size()`
    first is O(n + m), and a `ZstdFile` recopies up to one read buffer per
    frame boundary."""

    RECORD = random_bytes(50) * 2
    FRAMES = 1_000

    def test_one_frame_holds_the_output(self) -> None:
        payload = zstd.compress(b"x" * 10_000_000)

        peak = peak_bytes(lambda: zstd.decompress(payload))

        assert len(payload) < 1_000
        assert peak > 5_000_000, f"a 10 MB result peaked at {peak} bytes"

    def test_every_frame_recopies_the_rest_of_the_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        frames = zstd.compress(self.RECORD) * self.FRAMES
        counter = FedCounter(zstd.ZstdDecompressor)
        monkeypatch.setattr(zstd, "ZstdDecompressor", counter)

        assert zstd.decompress(frames) == self.RECORD * self.FRAMES

        n = len(frames)
        assert counter.fed > self.FRAMES * n // 4, (
            f"{self.FRAMES} frames of {n} bytes fed {counter.fed} bytes; linear would be ~{n}"
        )

    def test_splitting_with_get_frame_size_feeds_each_byte_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        frames = zstd.compress(self.RECORD) * self.FRAMES
        counter = FedCounter(zstd.ZstdDecompressor)
        monkeypatch.setattr(zstd, "ZstdDecompressor", counter)

        view = memoryview(frames)
        parts: list[bytes] = []
        start = 0
        while start < len(view):
            end = start + zstd.get_frame_size(view[start:])
            parts.append(zstd.decompress(view[start:end]))
            start = end

        assert b"".join(parts) == self.RECORD * self.FRAMES
        assert counter.fed == len(frames)

    def test_a_zstdfile_recopies_up_to_one_buffer_per_frame(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from compression.zstd import _zstdfile  # pyright: ignore[reportMissingImports]

        record = random_bytes(4_000)
        frames = zstd.compress(record) * self.FRAMES
        counter = FedCounter(_zstdfile.ZstdDecompressor)
        monkeypatch.setattr(_zstdfile, "ZstdDecompressor", counter)

        with zstd.ZstdFile(io.BytesIO(frames)) as f:
            assert f.read() == record * self.FRAMES

        n, buffer = len(frames), io.DEFAULT_BUFFER_SIZE
        assert buffer == 128 * 1024
        assert counter.fed > n * 4, f"fed {counter.fed} bytes for {n}: no recopying seen"
        assert counter.fed <= n + 2 * buffer * self.FRAMES, (
            f"fed {counter.fed} bytes for {n} in {self.FRAMES} frames"
        )

    def test_decompress_rejects_bad_input(self) -> None:
        with pytest.raises(zstd.ZstdError):
            zstd.decompress(b"garbage!")
        with pytest.raises(zstd.ZstdError, match="ended before"):
            zstd.decompress(zstd.compress(b"x" * 1_000)[:-3])


class TestStreamingCompressorHoldsOneChunk:
    """`ZstdCompressor.compress(data)` | O(c) | O(c); `flush()` | O(1) | O(1)."""

    def test_the_peak_follows_the_chunk_not_the_stream(self) -> None:
        chunk = random_bytes(65_536)

        def stream() -> None:
            compressor = zstd.ZstdCompressor()
            for _ in range(1_000):
                compressor.compress(chunk)
            compressor.flush()

        peak = peak_bytes(stream)

        assert peak < len(chunk) * 3, f"1,000 chunks of 64 KiB peaked at {peak} bytes"

    def test_a_small_chunk_may_return_nothing(self) -> None:
        compressor = zstd.ZstdCompressor()

        assert compressor.compress(b"0123456789") == b""
        assert zstd.decompress(compressor.flush()) == b"0123456789"

    def test_flush_emits_at_most_about_one_block(self) -> None:
        text = json_text(130_000)[:8_000_000]
        compressor = zstd.ZstdCompressor()
        for start in range(0, len(text), 65_536):
            compressor.compress(text[start : start + 65_536])

        tail = compressor.flush()

        assert len(tail) < 150_000, f"flush after 8 MB returned {len(tail)} bytes"

    def test_last_mode_tracks_the_last_call(self) -> None:
        compressor = zstd.ZstdCompressor()
        assert compressor.last_mode == zstd.ZstdCompressor.FLUSH_FRAME

        compressor.compress(b"a")
        assert compressor.last_mode == zstd.ZstdCompressor.CONTINUE
        compressor.compress(b"b", zstd.ZstdCompressor.FLUSH_BLOCK)
        assert compressor.last_mode == zstd.ZstdCompressor.FLUSH_BLOCK
        compressor.flush()
        assert compressor.last_mode == zstd.ZstdCompressor.FLUSH_FRAME

    def test_flush_block_makes_everything_so_far_decompressible(self) -> None:
        compressor = zstd.ZstdCompressor()
        so_far = compressor.compress(b"first ") + compressor.compress(
            b"second", zstd.ZstdCompressor.FLUSH_BLOCK
        )

        decompressor = zstd.ZstdDecompressor()
        assert decompressor.decompress(so_far) == b"first second"
        assert decompressor.eof is False

    def test_flush_frame_in_compress_completes_a_frame(self) -> None:
        compressor = zstd.ZstdCompressor()

        frame = compressor.compress(b"whole", zstd.ZstdCompressor.FLUSH_FRAME)

        assert zstd.get_frame_size(frame) == len(frame)
        assert zstd.decompress(frame) == b"whole"

    def test_pledged_size_reaches_the_header_and_only_at_a_frame_start(self) -> None:
        data = b"payload " * 1000
        compressor = zstd.ZstdCompressor()

        compressor.set_pledged_input_size(len(data))
        frame = compressor.compress(data[:100]) + compressor.compress(data[100:])
        frame += compressor.flush()

        assert zstd.get_frame_info(frame).decompressed_size == len(data)
        compressor.compress(b"more")
        with pytest.raises(ValueError, match="FLUSH_FRAME"):
            compressor.set_pledged_input_size(10)


class TestStreamingDecompressor:
    """`ZstdDecompressor.decompress(data, max_length)` | O(h + c + r) | O(h + c + r):
    r is capped by `max_length`, and input it could not consume is held."""

    def test_max_length_bounds_the_output(self) -> None:
        bomb = zstd.compress(b"\0" * 1_000_000)
        decompressor = zstd.ZstdDecompressor()

        chunk = decompressor.decompress(bomb, max_length=4096)

        assert len(bomb) < 100
        assert len(chunk) == 4096
        assert decompressor.needs_input is False
        assert decompressor.eof is False

    def test_unconsumed_input_is_copied_and_held(self) -> None:
        payload = zstd.compress(random_bytes(5_000_000))
        decompressor = zstd.ZstdDecompressor()

        peak = peak_bytes(lambda: decompressor.decompress(payload, max_length=1000))

        assert peak > 4_000_000, f"holding ~5 MB of input peaked at {peak} bytes"
        rest = decompressor.decompress(b"")
        while not decompressor.eof:
            rest += decompressor.decompress(b"")
        assert len(rest) == 5_000_000 - 1000

    def test_new_input_is_appended_to_what_is_held(self) -> None:
        payload = zstd.compress(random_bytes(5_000_000))
        half = len(payload) // 2
        decompressor = zstd.ZstdDecompressor()
        decompressor.decompress(payload[:half], max_length=1000)

        chunks: list[bytes] = []
        peak = peak_bytes(
            lambda: chunks.append(decompressor.decompress(payload[half : half + 1000], 1000))
        )

        assert peak > half * 0.8, f"appending to ~{half} held bytes peaked at {peak}"
        chunks.append(decompressor.decompress(payload[half + 1000 :]))
        while not decompressor.eof:
            chunks.append(decompressor.decompress(b""))
        assert b"".join(chunks) == random_bytes(5_000_000)[1000:]

    def test_one_frame_only(self) -> None:
        first, second = zstd.compress(b"one"), zstd.compress(b"two")
        decompressor = zstd.ZstdDecompressor()

        assert decompressor.unused_data == b""
        assert decompressor.decompress(first + second) == b"one"
        assert decompressor.eof is True
        assert decompressor.needs_input is False
        with pytest.raises(EOFError):
            decompressor.decompress(second)

    def test_unused_data_is_built_once(self) -> None:
        first, trailing = zstd.compress(b"one"), b"trailing bytes"
        decompressor = zstd.ZstdDecompressor()
        decompressor.decompress(first + trailing)

        unused = decompressor.unused_data

        assert unused == trailing
        assert decompressor.unused_data is unused


class TestDictionaryLoading:
    """A plain or undigested dictionary is loaded again on every `compress()`
    call, O(m + d); `as_digested_dict` is O(m) after the first call at a level;
    `ZstdCompressor(zstd_dict=zd)` is O(d); a decompressor keeps the digested
    dictionary on the `ZstdDict`.

    Raw-content dictionaries of random bytes, 8 KiB and 1 MiB, compress a
    5-byte record; the gap is the load, since the record is fixed.
    """

    SMALL = zstd.ZstdDict(random_bytes(8 * 1024), is_raw=True)
    LARGE_CONTENT = random_bytes(1024 * 1024)
    LARGE = zstd.ZstdDict(LARGE_CONTENT, is_raw=True)

    @pytest.mark.timing
    def test_an_undigested_dictionary_costs_its_size_per_call(self) -> None:
        costs = [
            best_ns(lambda zd=zd: zstd.compress(b"hello", zstd_dict=zd), repeats=7)  # type: ignore[misc]
            for zd in (self.SMALL, self.LARGE)
        ]

        assert costs[1] > costs[0] * 16, f"128x the dictionary: {costs} ns"

    @pytest.mark.timing
    def test_a_digested_dictionary_is_reused(self) -> None:
        undigested = best_ns(lambda: zstd.compress(b"hello", zstd_dict=self.LARGE), repeats=7)
        digested = [
            best_ns(
                lambda zd=zd: zstd.compress(b"hello", zstd_dict=zd.as_digested_dict),  # type: ignore[misc]
                repeats=7,
                inner=20,
            )
            for zd in (self.SMALL, self.LARGE)
        ]

        assert undigested > digested[1] * 16, f"{undigested} ns undigested, {digested} digested"
        assert digested[1] < digested[0] * 3, f"digested across 128x the dictionary: {digested}"

    @pytest.mark.timing
    def test_a_digested_dictionary_is_built_once_per_level(self) -> None:
        zd = zstd.ZstdDict(self.LARGE_CONTENT, is_raw=True)
        kept: list[Any] = []

        def build(level: int) -> int:
            return self.once_ns(
                lambda: kept.append(zstd.ZstdCompressor(level=level, zstd_dict=zd.as_digested_dict))
            )

        first_at_3 = build(3)
        again_at_3 = min(build(3) for _ in range(5))
        first_at_5 = build(5)
        again_at_5 = min(build(5) for _ in range(5))

        assert first_at_3 > again_at_3 * 20, f"{first_at_3} ns first, {again_at_3} ns again"
        assert first_at_5 > again_at_5 * 20, f"{first_at_5} ns first, {again_at_5} ns again"

    @pytest.mark.timing
    def test_building_a_compressor_loads_the_dictionary(self) -> None:
        costs = [
            best_ns(lambda zd=zd: zstd.ZstdCompressor(zstd_dict=zd), repeats=7, inner=5)  # type: ignore[misc]
            for zd in (self.SMALL, self.LARGE)
        ]

        assert costs[1] > costs[0] * 8, f"128x the dictionary: {costs} ns"

    @staticmethod
    def once_ns(func: Callable[[], Any]) -> int:
        start = time.perf_counter_ns()
        func()
        return time.perf_counter_ns() - start

    @pytest.mark.timing
    def test_a_decompressor_digests_a_dictionary_on_first_use(self) -> None:
        fresh = [zstd.ZstdDict(self.LARGE_CONTENT, is_raw=True) for _ in range(5)]
        kept: list[Any] = []

        first = min(
            self.once_ns(lambda zd=zd: kept.append(zstd.ZstdDecompressor(zstd_dict=zd)))  # type: ignore[misc]
            for zd in fresh
        )
        later = min(
            self.once_ns(lambda zd=zd: kept.append(zstd.ZstdDecompressor(zstd_dict=zd)))  # type: ignore[misc]
            for _ in range(40)
            for zd in fresh
        )

        assert first > later * 20, f"first use {first} ns, later {later} ns"

    @pytest.mark.timing
    def test_a_decompressor_keeps_the_digested_dictionary(self) -> None:
        kept: list[float] = []
        for zd in (self.SMALL, self.LARGE):
            frame = zstd.compress(b"hello world", zstd_dict=zd.as_digested_dict)
            kept.append(
                best_ns(lambda f=frame, d=zd: zstd.decompress(f, zstd_dict=d), repeats=7, inner=20)  # type: ignore[misc]
            )
        frame = zstd.compress(b"hello world", zstd_dict=self.LARGE.as_digested_dict)
        reloaded = best_ns(
            lambda: zstd.decompress(frame, zstd_dict=self.LARGE.as_undigested_dict),
            repeats=7,
            inner=20,
        )

        assert kept[1] < kept[0] * 3, f"a kept dictionary across 128x its size: {kept} ns"
        assert reloaded > kept[1] * 8, f"kept {kept[1]:.0f} ns, reloaded {reloaded:.0f} ns"


class TestZstdFile:
    """`ZstdFile` and `open()` read nothing until asked, decompress what is
    read, and emulate `seek()` by decompressing."""

    SIZE = 4_000_000
    PAYLOAD = random_bytes(SIZE)
    COMPRESSED = zstd.compress(PAYLOAD)

    def test_opening_reads_nothing(self) -> None:
        source = CountingBytesIO(self.COMPRESSED)

        zstd.ZstdFile(source)
        zstd.open(source)
        zstd.open(source, "rt", encoding="latin-1")

        assert source.taken == 0

    def test_a_small_read_takes_a_small_part_of_the_file(self) -> None:
        source = CountingBytesIO(self.COMPRESSED)

        with zstd.ZstdFile(source) as f:
            assert f.read(1000) == self.PAYLOAD[:1000]

        assert source.taken <= io.DEFAULT_BUFFER_SIZE, f"read(1000) took {source.taken} bytes"
        assert source.taken * 10 < len(self.COMPRESSED)

    def test_seek_decompresses_forward_and_rewinds_backward(self) -> None:
        source = CountingBytesIO(self.COMPRESSED)
        f = zstd.ZstdFile(source)
        slack = 200_000

        f.seek(2_000_000)
        assert abs(source.taken - 2_000_000) < slack, source.taken

        source.taken = 0
        f.seek(3_000_000)
        assert abs(source.taken - 1_000_000) < slack, "a forward seek restarted"

        source.taken = 0
        f.seek(1_000_000)
        assert abs(source.taken - 1_000_000) < slack, "a backward seek did not rewind"
        assert f.read(10) == self.PAYLOAD[1_000_000:1_000_010]

        source.taken = 0
        assert f.seek(0, io.SEEK_END) == self.SIZE
        assert abs(source.taken - 3_000_000) < slack, "SEEK_END did not read to the end"

        f.seek(0)
        source.taken = 0
        assert f.seek(-3_000_000, io.SEEK_END) == 1_000_000
        assert abs(source.taken - 1_000_000) < slack, "the size was not kept"
        f.close()

    def test_a_short_backward_seek_stays_in_the_read_buffer(self) -> None:
        source = CountingBytesIO(self.COMPRESSED)
        with zstd.ZstdFile(source) as f:
            f.seek(2_000_000)
            f.read(1000)
            source.taken = 0

            f.seek(2_000_500)

            assert source.taken == 0
            assert f.read(10) == self.PAYLOAD[2_000_500:2_000_510]

    def test_peek_does_not_move_the_position(self) -> None:
        with zstd.ZstdFile(io.BytesIO(self.COMPRESSED)) as f:
            f.read(10)
            peeked = f.peek(1)

            assert peeked
            assert peeked.startswith(self.PAYLOAD[10:11])
            assert f.tell() == 10

    def test_lines_and_iteration(self) -> None:
        text = b"".join(f"line {i}\n".encode() for i in range(100))

        with zstd.ZstdFile(io.BytesIO(zstd.compress(text))) as f:
            assert f.readline() == b"line 0\n"
            assert list(f)[-1] == b"line 99\n"

    def test_readinto_and_read1(self) -> None:
        with zstd.ZstdFile(io.BytesIO(self.COMPRESSED)) as f:
            buffer = bytearray(100)
            assert f.readinto(buffer) == 100
            assert f.readinto1(buffer) > 0
            assert 0 < len(f.read1(1000)) <= 1000

    def test_concatenated_frames_read_in_turn(self) -> None:
        frames = zstd.compress(b"one") + zstd.compress(b"two")

        with zstd.ZstdFile(io.BytesIO(frames)) as f:
            assert f.read() == b"onetwo"

    def test_write_passes_output_on_at_once_and_flush_ends_a_block(self) -> None:
        target = io.BytesIO()
        f = zstd.ZstdFile(target, "wb")
        assert target.getvalue() == b""

        assert f.write(self.PAYLOAD[:500_000]) == 500_000
        assert len(target.getvalue()) > 250_000, "incompressible output was held back"
        f.write(b"tail")
        f.flush()

        decompressor = zstd.ZstdDecompressor()
        assert decompressor.decompress(target.getvalue()) == self.PAYLOAD[:500_000] + b"tail"
        assert decompressor.eof is False
        assert f.tell() == 500_004
        f.close()
        assert zstd.decompress(target.getvalue()) == self.PAYLOAD[:500_000] + b"tail"

    def test_close_closes_only_a_file_it_opened(self, tmp_path: pathlib.Path) -> None:
        wrapped = io.BytesIO()
        with zstd.ZstdFile(wrapped, "wb") as f:
            f.write(b"data")
        assert not wrapped.closed
        assert f.closed

        path = tmp_path / "data.zst"
        with zstd.open(path, "wb") as named:
            assert named.mode == "wb"
            assert named.name == str(path)
            assert named.writable() and not named.readable()
            inner = named._fp  # pyright: ignore[reportAttributeAccessIssue]  # noqa: SLF001
            assert isinstance(named.fileno(), int)
            named.write(b"data")
        assert inner.closed

        with zstd.open(path) as f:
            assert f.mode == "rb"
            assert f.readable() and f.seekable() and not f.writable()
            assert f.read() == b"data"
        assert f.closed

    def test_text_mode_wraps_in_a_text_wrapper(self) -> None:
        with zstd.open(io.BytesIO(zstd.compress(b"a\nb\n")), "rt", encoding="ascii") as f:
            assert isinstance(f, io.TextIOWrapper)
            assert f.read() == "a\nb\n"

    def test_flush_modes_are_the_compressors(self) -> None:
        assert zstd.ZstdFile.FLUSH_BLOCK == zstd.ZstdCompressor.FLUSH_BLOCK
        assert zstd.ZstdFile.FLUSH_FRAME == zstd.ZstdCompressor.FLUSH_FRAME


class TestDictionaries:
    """`train_dict` and `finalize_dict` | O(s) | O(s); `ZstdDict` | O(d) |
    O(d) copies its content; `dict_content` copies it again on every access."""

    @pytest.mark.timing
    def test_training_is_linear_in_the_samples(self) -> None:
        samples = json_samples(16_000)
        small, large = samples[:1_000], samples

        durations = [
            best_ns(lambda s=s: zstd.train_dict(s, 8 * 1024), repeats=3)  # type: ignore[misc]
            for s in (small, large)
        ]
        ratio = durations[1] / durations[0]

        assert 4 < ratio < 64, f"16x the samples: x{ratio:.1f}; quadratic is x256"

    def test_training_and_finalizing_hold_the_joined_samples(self) -> None:
        samples = json_samples(8_000)
        total = sum(map(len, samples))
        raw = zstd.ZstdDict(b"".join(samples[:200])[:16_384], is_raw=True)

        peaks = [
            peak_bytes(lambda: zstd.train_dict(samples, 8 * 1024)),
            peak_bytes(lambda: zstd.finalize_dict(raw, samples, 32_768, 3)),
        ]

        assert min(peaks) > total, f"{total} sample bytes, peaks {peaks}"

    @pytest.mark.timing
    def test_finalizing_is_linear_in_the_samples(self) -> None:
        samples = json_samples(32_000)
        raw = zstd.ZstdDict(b"".join(samples[:200])[:16_384], is_raw=True)
        small, large = samples[:2_000], samples

        durations = [
            best_ns(lambda s=s: zstd.finalize_dict(raw, s, 32_768, 3), repeats=3)  # type: ignore[misc]
            for s in (small, large)
        ]
        ratio = durations[1] / durations[0]

        assert 4 < ratio < 64, f"16x the samples: x{ratio:.1f}; quadratic is x256"
        finalized = zstd.finalize_dict(raw, small, 32_768, 3)
        assert finalized.dict_id != 0

    def test_a_trained_dictionary_shrinks_a_small_record(self) -> None:
        samples = json_samples(2_000)
        dictionary = zstd.train_dict(samples, 4096)
        record = json_samples(1, seed=99)[0]

        with_dict = zstd.compress(record, zstd_dict=dictionary.as_digested_dict)

        assert len(dictionary.dict_content) <= 4096
        assert len(with_dict) < len(zstd.compress(record))
        assert zstd.get_frame_info(with_dict).dictionary_id == dictionary.dict_id
        assert zstd.decompress(with_dict, zstd_dict=dictionary) == record

    def test_the_content_is_copied_in_and_out(self) -> None:
        content = bytearray(random_bytes(64 * 1024))
        dictionary = zstd.ZstdDict(content, is_raw=True)
        content[:8] = b"\0" * 8

        first = dictionary.dict_content
        peak = peak_bytes(lambda: dictionary.dict_content)

        assert first[:8] != b"\0" * 8
        assert dictionary.dict_content is not first
        assert peak > len(content)
        assert len(dictionary) == len(content)
        assert dictionary.dict_id == 0

    def test_non_dictionary_content_needs_is_raw(self) -> None:
        with pytest.raises(ValueError, match="invalid Zstandard dictionary"):
            zstd.ZstdDict(b"not a dictionary")

    def test_the_load_modes_wrap_the_same_dictionary(self) -> None:
        dictionary = zstd.ZstdDict(random_bytes(1024), is_raw=True)

        assert dictionary.as_digested_dict[0] is dictionary
        assert dictionary.as_undigested_dict[0] is dictionary
        assert dictionary.as_digested_dict[1] != dictionary.as_undigested_dict[1]


class TestFrames:
    """`get_frame_info` | O(1) reads the header; `get_frame_size` | O(b) walks
    the block headers."""

    @staticmethod
    def frame_of(blocks: int) -> bytes:
        compressor = zstd.ZstdCompressor()
        piece = random_bytes(16) * 4
        parts = [compressor.compress(piece, zstd.ZstdCompressor.FLUSH_BLOCK) for _ in range(blocks)]
        parts.append(compressor.flush())
        return b"".join(parts)

    @pytest.mark.timing
    def test_info_reads_the_header_and_size_walks_the_blocks(self) -> None:
        small, large = self.frame_of(100), self.frame_of(100_000)
        assert zstd.get_frame_size(small) == len(small)
        assert zstd.get_frame_size(large) == len(large)

        info = [best_ns(lambda f=f: zstd.get_frame_info(f), inner=20) for f in (small, large)]  # type: ignore[misc]
        size = [best_ns(lambda f=f: zstd.get_frame_size(f)) for f in (small, large)]  # type: ignore[misc]

        assert info[1] < info[0] * 3, f"get_frame_info over 1000x the blocks: {info} ns"
        assert size[1] > size[0] * 50, f"get_frame_size over 1000x the blocks: {size} ns"

    def test_frame_size_stops_at_the_end_of_the_frame(self) -> None:
        frame = zstd.compress(b"payload")

        assert zstd.get_frame_size(frame + b"trailing") == len(frame)

    def test_decompressed_size_is_recorded_only_when_known(self) -> None:
        data = b"payload " * 1000
        streamed = zstd.ZstdCompressor()
        unsized = streamed.compress(data) + streamed.flush()

        assert zstd.get_frame_info(zstd.compress(data)).decompressed_size == len(data)
        assert zstd.get_frame_info(unsized).decompressed_size is None
        assert zstd.get_frame_info(unsized).dictionary_id == 0
        no_size = {zstd.CompressionParameter.content_size_flag: 0}
        assert zstd.get_frame_info(zstd.compress(data, options=no_size)).decompressed_size is None


class TestParametersAndConstants:
    """Parameter enums, bounds, strategies, the default level, the version
    attributes and the error classes."""

    def test_bounds_are_inclusive_pairs(self) -> None:
        for parameter in [*zstd.CompressionParameter, *zstd.DecompressionParameter]:
            lower, upper = parameter.bounds()
            assert lower <= upper, parameter

    def test_every_compression_parameter_is_accepted_at_its_lower_bound(self) -> None:
        for parameter in zstd.CompressionParameter:
            lower, _ = parameter.bounds()
            assert zstd.decompress(zstd.compress(b"abc", options={parameter: lower})) == b"abc"

    def test_an_out_of_range_parameter_raises_value_error(self) -> None:
        _, upper = zstd.CompressionParameter.window_log.bounds()

        with pytest.raises(ValueError, match="valid range"):
            zstd.compress(b"abc", options={zstd.CompressionParameter.window_log: upper + 1})

    def test_window_log_max_caps_the_window_a_frame_may_ask_for(self) -> None:
        options = {zstd.CompressionParameter.window_log: 20}
        frame = zstd.compress(random_bytes(2_000_000), options=options)

        with pytest.raises(zstd.ZstdError):
            zstd.decompress(frame, options={zstd.DecompressionParameter.window_log_max: 15})
        assert len(zstd.decompress(frame)) == 2_000_000

    def test_strategies_are_ordered_fastest_to_strongest(self) -> None:
        names = ["fast", "dfast", "greedy", "lazy", "lazy2", "btlazy2", "btopt", "btultra"]
        values = [zstd.Strategy[name] for name in [*names, "btultra2"]]

        assert values == sorted(values)
        assert len(set(values)) == len(values)

    def test_constants_and_versions(self) -> None:
        assert zstd.COMPRESSION_LEVEL_DEFAULT == 3
        assert zstd.zstd_version == ".".join(map(str, zstd.zstd_version_info))
        assert issubclass(zstd.ZstdError, Exception)


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
    """Each block runs in its own subprocess and working directory, and
    asserts its own result."""

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
        needle = "assert len(chunk) == 4096"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, "assert len(chunk) == 4097", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
