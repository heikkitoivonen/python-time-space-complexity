"""Tests for docs/stdlib/lzma.md.

The page prices xz and LZMA in the bytes that go in and come out, and in the
dictionary size D a stream is written with: a compressor allocates for D when
it is built and may hold up to about D bytes of input it has not yet encoded,
a decompressor allocates the stream's D when it reads the header, one-shot
calls hold the whole result, and a file object decompresses as it is read.
liblzma allocates through `PyMem_RawMalloc` (`PyLzma_Malloc` in
Modules/_lzmamodule.c), which `tracemalloc` traces, so working memory is
settled by traced allocation; held input by what a call returns; laziness and
seeking by a `BytesIO` that counts the bytes taken from it; the multi-stream
cost by a decompressor proxy that counts the bytes handed to it; and the timed
rows by ratios far from the excluded growth classes.

Measurement scope:

* Dictionary size: decompressing a one-byte stream peaks between 256 KiB and
  512 KiB at preset 0, between 8 MiB and 10 MiB at preset 6, and between
  1 MiB and 1.5 MiB for a filter chain with `dict_size` 1 MiB. Preset 9's
  LZMA2 filter properties encode a 64 MiB `dict_size`, read without building
  its 673 MiB compressor. Building an `LZMADecompressor` peaks under 5 KB, a
  call given only the 12-byte header of a preset-2 stream under 100 KB, and
  the call given the rest over 2 MiB; building one for
  `FORMAT_RAW` with `dict_size` 8 MiB peaks between 8 MiB and 12 MiB. With
  `memlimit=1 MiB` a preset-2 stream raises `LZMAError` and a preset-0 stream
  decodes.
* Compressor working memory: building an `LZMACompressor` at preset 6 peaks
  more than 20x higher than at preset 0 (D is 32x larger), and so do
  opening an `LZMAFile` for writing and `compress(b'x')`; the default
  compressor peaks within 10% of preset 6. A one-byte stream written with
  `PRESET_EXTREME` at preset 0 or 6 decodes with a peak within 10% of the
  plain preset's, so the flag keeps D.
  `compress()` of 20,000,000 zero bytes at preset 0 peaks within 1.5x of
  compressing 1,000 bytes.
* Compression time: 16x the input (250,000 to 4,000,000 bytes) costs between
  8x and 64x the time for generated text and random bytes at preset 0, and
  random bytes at preset 6. The per-byte cost at preset 6 rises while the
  input is smaller than D, so its ratio sits above 16x; the bound excludes
  constant and quadratic growth, not a logarithmic factor.
* Held input: at preset 2 (D = 2 MiB), one `compress()` of 1,000,000 random
  bytes returns under 100,000 bytes, and the next call, of one byte, returns
  over 800,000; a separate `flush()` after the same call also returns over
  800,000. At preset 1 (D = 1 MiB), the output of one 3,000,000-byte call
  decodes to all but under 1 MiB of it. `LZMAFile.write()` of the same
  1,000,000 bytes at preset 2 leaves under 100,000 bytes in the target, and
  `close()` writes the rest. After `flush()`, `compress()` and `flush()`
  raise `ValueError`.
* `decompress()` of one 10,000,000-byte stream peaks above 5 MB. Over 1,000
  concatenated streams of one byte it hands the decompressors it creates more
  than s·n/4 bytes in total, where n is the input's length: every stream
  recopies the rest. An `LZMAFile` over 1,000 streams of 4,000 random bytes
  hands them at most n plus one read buffer (`io.DEFAULT_BUFFER_SIZE`, 8 KiB
  before 3.14 and 128 KiB from it) per stream, and fewer than s·n/8.
  Garbage, a truncated stream, and a raw stream without filters raise;
  trailing bytes that are not a stream are dropped, and `FORMAT_AUTO` reads
  a `FORMAT_ALONE` stream.
* `LZMADecompressor.decompress()` given all but the last 100 bytes of a
  1,000,000-byte random stream returns over 990,000 bytes. With
  `max_length=4096` on a 10,000,000-byte bomb it returns exactly 4096 bytes
  with `needs_input` false. With `max_length=1000` on the 5,000,000-byte
  preset-0 compression of random data it peaks above 4 MB: the unconsumed
  input is copied and held. A call after `eof` raises `EOFError`;
  `unused_data` is `b''` before `eof`, including after half the stream, the
  trailing bytes after it, and the same object on a second access. `check` is
  `CHECK_UNKNOWN` after 11 bytes and the written check once the 12-byte
  stream header is fed, before the rest; `CHECK_NONE` for `FORMAT_ALONE`.
* `LZMAFile` and `open()` take nothing from a counting source when built for
  reading. On 4,000,000 random bytes compressed at preset 0, `read(1000)` and
  `peek()` each take at most one read buffer; within 250,000 bytes, a forward
  seek to 2,000,000 takes 2,000,000, a further seek to 3,000,000 takes
  1,000,000 more, a backward seek to 1,000,000 takes 1,000,000 from offset
  zero, and `SEEK_END` takes the remaining 3,000,000; after rewinding,
  `seek(-3_000_000, SEEK_END)` takes 1,000,000, so the size is kept. A
  500-byte backward seek inside the read buffer takes nothing.
  `read(16 MiB)` and `read1(16 MiB)` on a one-byte file each peak above
  8 MiB. `peek()` does not move `tell()`. Concatenated streams read back
  in turn, including one appended in `'ab'` mode. A 13-byte `write()` and
  `flush()` leave nothing decodable in the target; `close()` leaves a wrapped
  `BytesIO` open and closes a file it opened. `closed`, `fileno()`,
  `readable()`, `writable()` and `seekable()` are asserted by value, and
  `mode` and `name` from 3.13; a text mode returns an `io.TextIOWrapper`.
* Constants: `PRESET_DEFAULT` is 6; `is_check_supported()` is true for the
  four checks and false for `CHECK_ID_MAX` and `CHECK_UNKNOWN`; a raw chain of
  `FILTER_DELTA` and `FILTER_LZMA2` with `MF_HC4` and `MODE_FAST` round-trips.
* `compression.lzma` is asserted to be this module's names from 3.14.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That time is linear at every preset rests on liblzma's match finders
  bounding the work per byte by the preset's depth and nice-length limits;
  only presets 0 and 6 are timed, on generated text and random bytes, and a
  16x step excludes only constant and quadratic growth. `PRESET_EXTREME`,
  the `CHECK_*` choices, and the BCJ filters are not timed.
* O(D) construction time is an upper bound and is not timed: across presets
  0 to 7 construction time is not monotonic in D. Presets 7 to 9 allocate 185 MiB to 673 MiB and are not
  built. That decompressor time does not include a D term is likewise not
  timed.
* "Up to about D bytes" of held input is observed at presets 1 and 2, and on
  one input shape each; the held amount's dependence on how much output one
  call has room for is not varied. That the next call, however small, encodes
  what is held is observed at preset 2 only.
* That the multi-stream proxies' counts are copies, rather than views, is
  read from `decompress()` taking `unused_data` (a new `bytes`) in
  Lib/lzma.py and from `LZMADecompressor` building it with
  `PyBytes_FromStringAndSize` in Modules/_lzmamodule.c; the tests count bytes
  handed over.
* Bounds are in the bytes that go in and come out. Input whose compressed
  bytes produce no output - many empty concatenated streams, or
  `writelines()` over many empty items - costs time in the streams or items
  passed over, is not measured, and is outside those bounds.
* Filter IDs for architectures this build of liblzma lacks, and the platform
  filters' output, are not exercised.
* `LZMAFile.raw` is reported by the audit's runtime inspection although the
  class does not have it, and the inherited `readinto1()`, `detach()`,
  `truncate()` and `isatty()` are the `io` base class's; the page documents
  none of them.
"""

from __future__ import annotations

import functools
import io
import lzma
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "lzma.md"
EXPECTED_BLOCKS = 7

KIB = 1 << 10
MIB = 1 << 20

# The filter-property codecs are private, so not in the type stubs.
_lzma_internals: Any = lzma


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
def compressed_random(size: int, preset: int) -> bytes:
    return lzma.compress(random_bytes(size), preset=preset)


class CountingBytesIO(io.BytesIO):
    """A `BytesIO` that records how many bytes have been read from it."""

    taken = 0

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        self.taken += len(data)
        return data


class FedCounter:
    """Wraps `LZMADecompressor` and counts the bytes handed to every instance."""

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


def decodable(stream: bytes) -> int:
    """How many bytes a partial stream decodes to."""
    return len(lzma.LZMADecompressor().decompress(stream))


class TestTheDictionarySetsTheMemory:
    """D is 256 KiB at preset 0 to 64 MiB at preset 9, or `dict_size` in a
    filter chain; a decompressor allocates it when the header arrives, and
    `memlimit` caps it."""

    @pytest.mark.parametrize(
        ("preset", "low", "high"),
        [(0, 256 * KIB, 512 * KIB), (6, 8 * MIB, 10 * MIB)],
    )
    def test_a_one_byte_stream_costs_its_readers_d(self, preset: int, low: int, high: int) -> None:
        stream = lzma.compress(b"x", preset=preset)

        peak = peak_bytes(lambda: lzma.decompress(stream))

        assert low <= peak <= high, f"preset {preset} decoded with a {peak}-byte peak"

    def test_preset_9_sets_d_to_64_mib(self) -> None:
        properties = _lzma_internals._encode_filter_properties(
            {"id": lzma.FILTER_LZMA2, "preset": 9}
        )
        decoded = _lzma_internals._decode_filter_properties(lzma.FILTER_LZMA2, properties)

        assert decoded["dict_size"] == 64 * MIB

    def test_a_filter_chain_sets_d_with_dict_size(self) -> None:
        filters = [{"id": lzma.FILTER_LZMA2, "dict_size": MIB}]
        stream = lzma.compress(b"x", filters=filters)

        peak = peak_bytes(lambda: lzma.decompress(stream))

        assert MIB <= peak <= MIB * 3 // 2, peak

    def test_the_decompressor_allocates_when_the_header_arrives(self) -> None:
        stream = lzma.compress(b"x", preset=2)
        built = peak_bytes(lzma.LZMADecompressor)
        decompressor = lzma.LZMADecompressor()

        header_only = peak_bytes(lambda: decompressor.decompress(stream[:12]))
        rest = peak_bytes(lambda: decompressor.decompress(stream[12:]))

        assert built < 5_000, built
        assert header_only < 100_000, header_only
        assert rest > 2 * MIB, rest
        assert decompressor.eof

    def test_a_raw_decompressor_allocates_d_when_built(self) -> None:
        filters = [{"id": lzma.FILTER_LZMA2, "dict_size": 8 * MIB}]

        peak = peak_bytes(lambda: lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters))

        assert 8 * MIB <= peak <= 12 * MIB, peak

    def test_memlimit_refuses_a_larger_dictionary(self) -> None:
        data = b"payload " * 1000

        assert lzma.decompress(lzma.compress(data, preset=0), memlimit=MIB) == data
        with pytest.raises(lzma.LZMAError, match="Memory usage limit"):
            lzma.decompress(lzma.compress(data, preset=2), memlimit=MIB)
        with pytest.raises(lzma.LZMAError, match="Memory usage limit"):
            lzma.LZMADecompressor(memlimit=MIB).decompress(lzma.compress(data, preset=2))


class TestCompressorWorkingMemory:
    """`LZMACompressor(...)` | O(D) | O(D), and `compress()` | O(m + D) |
    O(n + D): the compressor allocates for D up front, and memory follows the
    output, not the input."""

    @staticmethod
    def built(preset: int | None = None) -> int:
        return peak_bytes(lambda: lzma.LZMACompressor(preset=preset))

    def test_the_preset_sets_the_working_memory(self) -> None:
        preset_0, preset_6 = self.built(0), self.built(6)

        assert preset_6 > preset_0 * 20, f"preset 0 {preset_0} bytes, preset 6 {preset_6}"

    def test_the_default_is_preset_6(self) -> None:
        assert lzma.PRESET_DEFAULT == 6
        default, preset_6 = self.built(), self.built(6)

        assert abs(default - preset_6) < preset_6 / 10, (default, preset_6)

    @pytest.mark.parametrize("preset", [0, 6])
    def test_extreme_keeps_the_same_d(self, preset: int) -> None:
        plain = lzma.compress(b"x", preset=preset)
        extreme = lzma.compress(b"x", preset=preset | lzma.PRESET_EXTREME)

        plain_peak = peak_bytes(lambda: lzma.decompress(plain))
        extreme_peak = peak_bytes(lambda: lzma.decompress(extreme))

        assert abs(extreme_peak - plain_peak) < plain_peak / 10, (plain_peak, extreme_peak)

    def test_a_tiny_input_still_pays_for_d(self) -> None:
        preset_0 = peak_bytes(lambda: lzma.compress(b"x", preset=0))
        preset_6 = peak_bytes(lambda: lzma.compress(b"x", preset=6))

        assert preset_6 > preset_0 * 20, (preset_0, preset_6)

    def test_memory_follows_the_output_not_the_input(self) -> None:
        data = b"\0" * 20_000_000
        small = b"\0" * 1_000

        large_peak = peak_bytes(lambda: lzma.compress(data, preset=0))
        small_peak = peak_bytes(lambda: lzma.compress(small, preset=0))

        assert len(lzma.compress(data, preset=0)) < 10_000
        assert large_peak < small_peak * 1.5, f"{large_peak} for 20 MB, {small_peak} for 1 KB"


class TestCompressionIsLinear:
    """`compress()` is O(m + D) at every preset."""

    @pytest.mark.timing
    @pytest.mark.parametrize(("preset", "shape"), [(0, "text"), (0, "random"), (6, "random")])
    def test_time_scales_with_the_input(self, preset: int, shape: str) -> None:
        make = generated_text if shape == "text" else random_bytes
        small, large = make(250_000), make(4_000_000)

        small_ns = best_ns(lambda: lzma.compress(small, preset=preset))
        large_ns = best_ns(lambda: lzma.compress(large, preset=preset))

        ratio = large_ns / small_ns
        assert 8 < ratio < 64, f"16x the {shape} input at preset {preset} cost x{ratio:.2f}"


class TestTheCompressorHoldsInput:
    """`LZMACompressor.compress(data)` | O(c + D): a call returns once its
    input is taken in, up to about D bytes can be held unencoded, and the next
    call or `flush()` | O(D) encodes them."""

    DATA_SIZE = 1_000_000

    def test_a_large_call_returns_almost_nothing(self) -> None:
        compressor = lzma.LZMACompressor(preset=2)

        first = compressor.compress(random_bytes(self.DATA_SIZE))

        assert len(first) < 100_000, len(first)

    def test_the_next_call_encodes_what_is_held(self) -> None:
        compressor = lzma.LZMACompressor(preset=2)
        first = compressor.compress(random_bytes(self.DATA_SIZE))

        second = compressor.compress(b"x")

        assert len(second) > 800_000, len(second)
        assert lzma.decompress(first + second + compressor.flush()) == (
            random_bytes(self.DATA_SIZE) + b"x"
        )

    def test_flush_encodes_what_is_held(self) -> None:
        compressor = lzma.LZMACompressor(preset=2)
        first = compressor.compress(random_bytes(self.DATA_SIZE))

        rest = compressor.flush()

        assert len(rest) > 800_000, len(rest)
        assert lzma.decompress(first + rest) == random_bytes(self.DATA_SIZE)

    def test_no_more_than_about_d_is_held(self) -> None:
        data = random_bytes(3_000_000)
        compressor = lzma.LZMACompressor(preset=1)  # D = 1 MiB

        out = compressor.compress(data)

        held = len(data) - decodable(out)
        assert held < MIB, f"{held} bytes held at D = 1 MiB"

    def test_a_flushed_compressor_cannot_be_used_again(self) -> None:
        compressor = lzma.LZMACompressor(preset=0)
        compressor.compress(b"data")
        compressor.flush()

        with pytest.raises(ValueError, match="flushed"):
            compressor.compress(b"more")
        with pytest.raises(ValueError, match="Repeated call"):
            compressor.flush()


class TestDecompress:
    """`decompress(data)` | O(n + m) | O(m + D) for one stream, and
    O(s·n + m) over s concatenated streams; an `LZMAFile` recopies at most one
    read buffer per stream."""

    def test_one_stream_holds_the_output(self) -> None:
        payload = lzma.compress(b"x" * 10_000_000, preset=0)

        peak = peak_bytes(lambda: lzma.decompress(payload))

        assert len(payload) < 10_000
        assert peak > 5_000_000, f"a 10 MB result peaked at {peak} bytes"

    def test_every_stream_recopies_the_rest_of_the_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        streams = 1_000
        data = lzma.compress(b"x", preset=0) * streams
        counter = FedCounter(lzma.LZMADecompressor)
        monkeypatch.setattr(lzma, "LZMADecompressor", counter)

        assert lzma.decompress(data) == b"x" * streams

        n = len(data)
        assert counter.fed > streams * n // 4, (
            f"{streams} streams of {n} bytes fed {counter.fed} bytes; linear would be ~{n}"
        )

    def test_an_lzmafile_recopies_up_to_one_buffer_per_stream(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        streams = 1_000
        record = random_bytes(4_000)
        data = lzma.compress(record, preset=0) * streams
        counter = FedCounter(lzma.LZMADecompressor)
        monkeypatch.setattr(lzma, "LZMADecompressor", counter)

        with lzma.LZMAFile(io.BytesIO(data)) as f:
            assert f.read() == record * streams

        n, buffer = len(data), io.DEFAULT_BUFFER_SIZE
        assert counter.fed <= n + buffer * streams, f"fed {counter.fed} bytes for {n}"
        assert counter.fed < streams * n // 8, f"fed {counter.fed} bytes for {n}"

    def test_bad_input(self) -> None:
        with pytest.raises(lzma.LZMAError, match="format not supported"):
            lzma.decompress(b"garbage!")
        with pytest.raises(lzma.LZMAError, match="ended before"):
            lzma.decompress(lzma.compress(b"x" * 1_000, preset=0)[:-3])
        assert lzma.decompress(lzma.compress(b"ok", preset=0) + b"junk") == b"ok"

    def test_auto_reads_both_containers(self) -> None:
        alone = lzma.compress(b"legacy", format=lzma.FORMAT_ALONE, preset=0)

        assert lzma.decompress(alone) == b"legacy"
        assert lzma.decompress(lzma.compress(b"xz", preset=0)) == b"xz"

    def test_raw_needs_filters(self) -> None:
        with pytest.raises(ValueError, match="filter"):
            lzma.compress(b"x", format=lzma.FORMAT_RAW)
        with pytest.raises(ValueError, match="filter"):
            lzma.LZMADecompressor(format=lzma.FORMAT_RAW)


class TestStreamingDecompressor:
    """`LZMADecompressor.decompress(data, max_length=-1)` | O(h + c + r):
    output arrives as its input does, `max_length` bounds it, unconsumed input
    is copied and held, and the decompressor handles one stream."""

    def test_output_arrives_before_the_stream_is_complete(self) -> None:
        data = random_bytes(1_000_000)
        stream = lzma.compress(data, preset=0)
        decompressor = lzma.LZMADecompressor()

        partial = decompressor.decompress(stream[:-100])

        assert len(partial) > 990_000, len(partial)
        assert data.startswith(partial)
        assert not decompressor.eof

    def test_max_length_bounds_the_output(self) -> None:
        bomb = lzma.compress(b"\0" * 10_000_000, preset=0)
        decompressor = lzma.LZMADecompressor()

        chunk = decompressor.decompress(bomb, max_length=4096)

        assert chunk == b"\0" * 4096
        assert decompressor.needs_input is False
        assert decompressor.eof is False

    def test_unconsumed_input_is_copied_and_held(self) -> None:
        compressed = compressed_random(5_000_000, 0)
        decompressor = lzma.LZMADecompressor()

        peak = peak_bytes(lambda: decompressor.decompress(compressed, max_length=1000))

        assert peak > 4_000_000, f"holding {len(compressed)} bytes peaked at {peak}"
        rest = decompressor.decompress(b"")
        while not decompressor.eof:
            rest += decompressor.decompress(b"")
        assert len(rest) == 5_000_000 - 1000

    def test_one_stream_only(self) -> None:
        decompressor = lzma.LZMADecompressor()
        decompressor.decompress(lzma.compress(b"data", preset=0))

        assert decompressor.eof
        with pytest.raises(EOFError, match="end of stream"):
            decompressor.decompress(b"more")

    def test_unused_data_is_set_at_the_end_of_the_stream(self) -> None:
        stream = lzma.compress(b"data", preset=0)
        decompressor = lzma.LZMADecompressor()
        assert decompressor.unused_data == b""
        assert decompressor.needs_input is True

        decompressor.decompress(stream[: len(stream) // 2])
        assert not decompressor.eof
        assert decompressor.unused_data == b""

        decompressor.decompress(stream[len(stream) // 2 :] + b"tail")

        assert decompressor.unused_data == b"tail"
        assert decompressor.unused_data is decompressor.unused_data

    def test_check_is_known_once_the_header_is_read(self) -> None:
        stream = lzma.compress(b"data", check=lzma.CHECK_SHA256, preset=0)
        decompressor = lzma.LZMADecompressor()
        assert decompressor.check == lzma.CHECK_UNKNOWN

        decompressor.decompress(stream[:11])
        assert decompressor.check == lzma.CHECK_UNKNOWN
        decompressor.decompress(stream[11:12])
        assert decompressor.check == lzma.CHECK_SHA256

        decompressor.decompress(stream[12:])
        assert decompressor.eof
        assert decompressor.check == lzma.CHECK_SHA256
        alone = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        alone.decompress(lzma.compress(b"data", format=lzma.FORMAT_ALONE, preset=0))
        assert alone.check == lzma.CHECK_NONE


class TestLZMAFile:
    """`LZMAFile` and `open()` read nothing until asked, decompress what is
    read, emulate `seek()` by decompressing, build the compressor when opened
    for writing, and write only what has been encoded."""

    SIZE = 4_000_000

    @property
    def compressed(self) -> bytes:
        return compressed_random(self.SIZE, 0)

    @property
    def payload(self) -> bytes:
        return random_bytes(self.SIZE)

    def test_opening_reads_nothing(self) -> None:
        source = CountingBytesIO(self.compressed)

        lzma.LZMAFile(source)
        lzma.open(source)
        lzma.open(source, "rt", encoding="latin-1")

        assert source.taken == 0

    def test_opening_for_writing_builds_the_compressor(self) -> None:
        preset_0 = peak_bytes(lambda: lzma.open(io.BytesIO(), "wb", preset=0))
        preset_6 = peak_bytes(lambda: lzma.LZMAFile(io.BytesIO(), "wb", preset=6))

        assert preset_6 > preset_0 * 20, (preset_0, preset_6)

    def test_a_small_read_takes_one_buffer(self) -> None:
        source = CountingBytesIO(self.compressed)

        with lzma.LZMAFile(source) as f:
            assert f.read(1000) == self.payload[:1000]

        assert source.taken <= io.DEFAULT_BUFFER_SIZE, f"took {source.taken} bytes"

    def test_peek_takes_one_buffer_and_does_not_move(self) -> None:
        source = CountingBytesIO(self.compressed)

        with lzma.LZMAFile(source) as f:
            peeked = f.peek()
            assert source.taken <= io.DEFAULT_BUFFER_SIZE, f"took {source.taken} bytes"
            assert peeked and self.payload.startswith(peeked)
            assert f.tell() == 0
            f.read(10)
            assert f.peek().startswith(self.payload[10:11])
            assert f.tell() == 10

    def test_seek_decompresses_forward_and_rewinds_backward(self) -> None:
        source = CountingBytesIO(self.compressed)
        f = lzma.LZMAFile(source)
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
        with lzma.LZMAFile(source) as f:
            f.seek(2_000_000)
            f.read(1000)
            source.taken = 0

            f.seek(2_000_500)

            assert source.taken == 0
            assert f.tell() == 2_000_500
            assert f.read(10) == self.payload[2_000_500:2_000_510]

    def test_lines_and_iteration(self) -> None:
        text = b"".join(f"line {i}\n".encode() for i in range(100))

        with lzma.LZMAFile(io.BytesIO(lzma.compress(text, preset=0))) as f:
            assert f.readline() == b"line 0\n"
            assert f.readlines(10) == [b"line 1\n", b"line 2\n"]
            assert list(f)[-1] == b"line 99\n"

    @pytest.mark.parametrize("method", ["read", "read1"])
    def test_a_read_allocates_the_size_it_asks_for(self, method: str) -> None:
        f = lzma.LZMAFile(io.BytesIO(lzma.compress(b"x", preset=0)))
        read = getattr(f, method)

        peak = peak_bytes(lambda: read(16 * MIB))

        assert peak > 8 * MIB, f"{method}(16 MiB) of one byte peaked at {peak}"
        f.close()

    def test_readinto_and_read1(self) -> None:
        with lzma.LZMAFile(io.BytesIO(self.compressed)) as f:
            buffer = bytearray(100)
            assert f.readinto(buffer) == 100
            assert bytes(buffer) == self.payload[:100]
            assert 0 < len(f.read1(1000)) <= 1000

    def test_concatenated_streams_read_in_turn(self) -> None:
        target = io.BytesIO()
        with lzma.LZMAFile(target, "wb", preset=0) as f:
            f.write(b"one")
        with lzma.LZMAFile(target, "ab", preset=0) as f:
            f.write(b"two")

        assert lzma.decompress(target.getvalue()) == b"onetwo"
        target.seek(0)
        with lzma.LZMAFile(target) as f:
            assert f.read() == b"onetwo"

    def test_a_large_write_is_held_until_close(self) -> None:
        data = random_bytes(1_000_000)
        target = io.BytesIO()
        f = lzma.LZMAFile(target, "wb", preset=2)

        assert f.write(data) == len(data)
        assert len(target.getvalue()) < 100_000, len(target.getvalue())
        assert f.tell() == len(data)

        f.close()
        assert lzma.decompress(target.getvalue()) == data

    def test_flush_writes_nothing_held(self) -> None:
        target = io.BytesIO()
        f = lzma.LZMAFile(target, "wb", preset=0)

        f.write(b"small record\n")
        f.flush()
        assert decodable(target.getvalue()) == 0

        f.writelines([b"more\n", b"lines\n"])
        f.close()
        assert lzma.decompress(target.getvalue()) == b"small record\nmore\nlines\n"

    def test_close_closes_only_a_file_it_opened(self, tmp_path: pathlib.Path) -> None:
        wrapped = io.BytesIO()
        with lzma.LZMAFile(wrapped, "wb", preset=0) as f:
            f.write(b"data")
        assert not wrapped.closed
        assert f.closed

        path = tmp_path / "data.xz"
        with lzma.open(path, "wb", preset=0) as named:
            assert named.writable() and not named.readable()
            assert isinstance(named.fileno(), int)
            inner = named._fp  # pyright: ignore[reportAttributeAccessIssue]  # noqa: SLF001
            named.write(b"data")
        assert inner.closed

        with lzma.open(path) as f:
            assert f.readable() and f.seekable() and not f.writable()
            assert f.read() == b"data"
        assert f.closed

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_mode_and_name(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "data.xz"
        with lzma.LZMAFile(path, "wb", preset=0) as f:
            assert f.mode == "wb"
            assert f.name == str(path)
        with lzma.LZMAFile(path) as f:
            assert f.mode == "rb"

    def test_text_mode_wraps_in_a_text_wrapper(self) -> None:
        with lzma.open(io.BytesIO(lzma.compress(b"a\nb\n", preset=0)), "rt", encoding="ascii") as f:
            assert isinstance(f, io.TextIOWrapper)
            assert f.read() == "a\nb\n"


class TestConstantsAndExceptions:
    """Checks, filters, match finders and modes are O(1) constants; a custom
    chain built from them round-trips."""

    def test_is_check_supported(self) -> None:
        for check in (lzma.CHECK_NONE, lzma.CHECK_CRC32, lzma.CHECK_CRC64, lzma.CHECK_SHA256):
            assert lzma.is_check_supported(check) is True
        assert lzma.is_check_supported(lzma.CHECK_ID_MAX) is False
        assert lzma.is_check_supported(lzma.CHECK_UNKNOWN) is False

    def test_a_raw_filter_chain_round_trips(self) -> None:
        filters = [
            {"id": lzma.FILTER_DELTA, "dist": 4},
            {"id": lzma.FILTER_LZMA2, "preset": 1, "mf": lzma.MF_HC4, "mode": lzma.MODE_FAST},
        ]
        data = generated_text(10_000)

        stream = lzma.compress(data, format=lzma.FORMAT_RAW, filters=filters)

        assert lzma.decompress(stream, format=lzma.FORMAT_RAW, filters=filters) == data

    def test_the_other_filter_ids_are_distinct(self) -> None:
        ids = {
            lzma.FILTER_LZMA1,
            lzma.FILTER_LZMA2,
            lzma.FILTER_DELTA,
            lzma.FILTER_X86,
            lzma.FILTER_IA64,
            lzma.FILTER_ARM,
            lzma.FILTER_ARMTHUMB,
            lzma.FILTER_POWERPC,
            lzma.FILTER_SPARC,
        }
        assert len(ids) == 9
        assert len({lzma.MF_HC3, lzma.MF_HC4, lzma.MF_BT2, lzma.MF_BT3, lzma.MF_BT4}) == 5
        assert lzma.MODE_FAST != lzma.MODE_NORMAL

    def test_lzma_error_is_an_exception(self) -> None:
        assert issubclass(lzma.LZMAError, Exception)


class TestVersionNotes:
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_compression_lzma_is_this_module(self) -> None:
        from compression import lzma as reexported

        for name in lzma.__all__:
            assert getattr(reexported, name) is getattr(lzma, name)


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
        assert _run_block(mutated, tmp_path).returncode != 0
