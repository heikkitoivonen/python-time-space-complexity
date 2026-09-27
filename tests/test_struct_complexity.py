"""Tests for docs/stdlib/struct.md.

The page prices one record at a time: compiling is linear in the format
string, packing writes every byte of the record, unpacking builds one value
per field and copies the bytes of `s` fields, and the module-level functions
put a cache of compiled formats in front of all of it. Space claims are
settled by traced allocation and `Struct.__sizeof__()`, which separate the
states by orders of magnitude and need no tolerance; the cache and the buffer
export are settled by observation; growth in time uses ratios over a 100x
span of sizes.

Measurement scope:

* `Struct()` stores a repeat count rather than expanding it:
  `Struct('i')`, `Struct('1000000i')` and `Struct('1000000s')` report the
  same `__sizeof__()`, while `'i' * 1000` reports 999 more codes than `'i'`.
  Compiling `'i' * 20,000` and `'i' * 200,000` peaks at more than 5x and
  less than 20x apart, and in a timing test 100x the format costs between
  20x and 1,000x.
* `pack()` of `'1000000x'` and of `'1000000s'` with an empty argument each
  peak at over a million bytes; `pack_into()` of the million pad bytes into a
  buffer filled with `0xff` peaks under 1 KB, leaves the same buffer object
  and zeroes every byte. A ten-million-byte argument to a `'2s'` field peaks
  under 1 KB and returns two bytes. Timing tests take `pack()` from 1,000 to
  100,000 `i` fields, under the `@`, `<` and `>` prefixes, and from 100,000 to
  ten million pad bytes; the field step costs more than 20x, the byte step
  more than 10x, and each less than 1,000x.
* `unpack()` of a million pad bytes returns `()` with a traced peak of zero,
  and in a timing test ten million pad bytes cost under 3x what ten thousand
  do. A million-byte `s` field peaks over a million bytes. Unpacking 20,000
  and 200,000 `q` fields holding values above a million peaks more than 8x
  apart, and in a timing test 1,000 to 100,000 fields costs between 20x and
  1,000x. A `'1000p'` field holding 999 bytes unpacks 255.
* `unpack_from()` at an offset five million bytes into a ten-million-byte
  object peaks under 1 KB. `iter_unpack()` over the same object peaks under
  1 KB to create and under 1 KB per `next()`; a `bytearray` raises
  `BufferError` on `extend()` while the iterator is open and accepts it once
  the iterator is exhausted. A buffer that is not a multiple of the record
  size raises `struct.error`.
* The format cache is observed through `calcsize()`, whose result is a small
  int: after `_clearcache()` a first call has a nonzero traced peak and a
  second call, with an equal string built separately, a peak of zero. After
  100 distinct formats the first is still a zero-peak hit; one more distinct
  format makes the most recently added of the 100 a miss, which an LRU
  eviction would not, and a second pass over those 101 formats in
  turn misses on all 101 calls. The measured function is warmed on a format
  already in the cache, or has already run when no warm-up is possible.
* `Struct.format` of `'<4sIH'` returns an equal but distinct string on each
  access (one-character strings are shared by CPython, so not every format), and
  `Struct.size` equals `calcsize()`.
* The count and buffer-size checks are observed to run before conversion:
  values whose `__index__` counts its calls are never converted when `pack()`
  gets too few of them or `pack_into()` gets a buffer too small.
* `F` and `D` round-trip complex values on Python 3.14+ and raise
  `struct.error` before it.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Pricing one value's conversion at O(1) is a cost-model assumption. It
  holds for ints, floats and bytes; an `__index__`, `__float__` or
  `__bool__` supplied by the caller runs at its own cost, and very wide ints
  are not varied.
* Hashing a format string built fresh for each call is O(m) and hashing a
  literal is paid once: that is `str` hashing, not `struct`, and is not
  measured here.
* The cache's capacity of 100 is read from `MAXCACHE` in Modules/_struct.c
  (the same on every supported version); the test pins it on the running
  interpreter only.
* Native (`@`) sizes and alignment are the platform's; only Linux is
  measured, and the example asserts only that `'@ci'` is larger than
  `'=ci'`.
* The O(k + B) and O(k + t) bounds are read from `s_pack_internal()` and
  `s_unpack_internal()` in Modules/_struct.c. The tests show each variable
  moves the cost of the operation it is varied on, not that the terms add.
  Byte order is varied only for `pack()` of `i` fields.
* `iter_unpack()` also rejects a zero-size format; that precondition is not
  exercised.
"""

from __future__ import annotations

import pathlib
import re
import struct
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "struct.md"
EXPECTED_BLOCKS = 7


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
    """Peak traced allocation while func runs, after one untraced warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def assert_grows_linearly(label: str, small: float, large: float) -> None:
    """A 100x step in size: linear predicts 100x, constant 1x, quadratic 10,000x."""
    ratio = large / small
    assert 20 < ratio < 1_000, f"{label}: 100x the size cost x{ratio:.1f}"


class CountingIndex:
    """An integer-like value that records how often it is converted."""

    calls = 0

    def __index__(self) -> int:
        CountingIndex.calls += 1
        return 1


class TestCompilingIsLinearInTheFormat:
    """`struct.Struct(format)` | O(m) | O(m).

    m counts format characters, so a repeat count costs its digits and not
    the fields it describes.
    """

    def test_a_repeat_count_is_stored_not_expanded(self) -> None:
        one = struct.Struct("i").__sizeof__()
        assert struct.Struct("1000000i").__sizeof__() == one
        assert struct.Struct("1000000s").__sizeof__() == one

    def test_each_format_character_is_one_code(self) -> None:
        one = struct.Struct("i").__sizeof__()
        per_code = struct.Struct("ii").__sizeof__() - one

        assert per_code > 0
        assert struct.Struct("i" * 1000).__sizeof__() == one + 999 * per_code

    def test_compile_space_grows_with_the_format(self) -> None:
        small_format, large_format = "i" * 20_000, "i" * 200_000

        small = peak_bytes(lambda: struct.Struct(small_format))
        large = peak_bytes(lambda: struct.Struct(large_format))

        assert 5 < large / small < 20, f"10x the format peaked x{large / small:.1f}"

    @pytest.mark.timing
    def test_compile_time_is_linear_in_the_format(self) -> None:
        small_format, large_format = "i" * 1_000, "i" * 100_000

        small = best_ns(lambda: struct.Struct(small_format), inner=20)
        large = best_ns(lambda: struct.Struct(large_format))

        assert_grows_linearly("Struct()", small, large)


class TestPackWritesTheWholeRecord:
    """`pack()` | O(k + B) | O(B) and `pack_into()` | O(k + B) | O(1).

    Pad bytes and short `s` arguments still cost the output their bytes,
    because the record is zero-filled before any field is written.
    """

    def test_pack_allocates_the_whole_record(self) -> None:
        pad = struct.Struct("1000000x")
        text = struct.Struct("1000000s")

        pad_peak = peak_bytes(pad.pack)
        text_peak = peak_bytes(lambda: text.pack(b""))

        assert pad_peak > 1_000_000, f"packing a million pad bytes peaked at {pad_peak}"
        assert text_peak > 1_000_000, f"packing an empty 1,000,000s field peaked at {text_peak}"
        assert text.pack(b"") == bytes(1_000_000)

    def test_pack_into_writes_every_byte_and_allocates_no_output(self) -> None:
        pad = struct.Struct("1000000x")
        buffer = bytearray(b"\xff" * 1_000_000)
        before = id(buffer)

        peak = peak_bytes(lambda: pad.pack_into(buffer, 0))

        assert peak < 1_000, f"pack_into() of a million bytes allocated {peak}"
        assert id(buffer) == before
        assert buffer.count(0) == 1_000_000, "every pad byte was zeroed in place"

    def test_pack_into_writes_at_the_offset(self) -> None:
        buffer = bytearray(12)
        struct.pack_into("<i", buffer, 8, 7)
        assert buffer == bytearray(8) + struct.pack("<i", 7)

    def test_a_long_argument_costs_the_field_width(self) -> None:
        field = struct.Struct("2s")
        argument = b"x" * 10_000_000

        peak = peak_bytes(lambda: field.pack(argument))

        assert field.pack(argument) == b"xx"
        assert peak < 1_000, f"a 2-byte field took {peak} bytes from a 10 MB argument"

    @pytest.mark.timing
    def test_pack_time_grows_with_fields(self) -> None:
        small, large = struct.Struct("1000i"), struct.Struct("100000i")
        small_values, large_values = tuple(range(1_000)), tuple(range(100_000))

        small_ns = best_ns(lambda: small.pack(*small_values), inner=20)
        large_ns = best_ns(lambda: large.pack(*large_values))

        assert_grows_linearly("pack() in fields", small_ns, large_ns)

    @pytest.mark.timing
    def test_pack_time_grows_with_bytes(self) -> None:
        small, large = struct.Struct("100000x"), struct.Struct("10000000x")

        small_ns = best_ns(small.pack, inner=20)
        large_ns = best_ns(large.pack)

        ratio = large_ns / small_ns
        assert 10 < ratio < 1_000, f"pack() of 100x the pad bytes cost x{ratio:.1f}"


class TestUnpackBuildsOneValuePerField:
    """`unpack()` | O(k + t) | O(k + t).

    Pad bytes produce no value and are not read; `s` fields copy their bytes
    into the result; a `p` field returns at most 255 bytes.
    """

    def test_pad_bytes_are_not_read(self) -> None:
        pad = struct.Struct("1000000x")
        data = pad.pack()

        peak = peak_bytes(lambda: pad.unpack(data))

        assert pad.unpack(data) == ()
        assert peak == 0, f"unpacking a million pad bytes allocated {peak}"

    @pytest.mark.timing
    def test_pad_bytes_cost_no_time(self) -> None:
        small, large = struct.Struct("10000x"), struct.Struct("10000000x")
        small_data, large_data = small.pack(), large.pack()

        small_ns = best_ns(lambda: small.unpack(small_data), inner=1_000)
        large_ns = best_ns(lambda: large.unpack(large_data), inner=1_000)

        assert large_ns < small_ns * 3, (
            f"1,000x the pad bytes should not cost more: {small_ns:.0f}ns vs {large_ns:.0f}ns"
        )

    def test_string_fields_carry_their_bytes(self) -> None:
        text = struct.Struct("1000000s")
        data = text.pack(b"y" * 1_000_000)

        peak = peak_bytes(lambda: text.unpack(data))

        assert text.unpack(data) == (data,)
        assert peak > 1_000_000, f"unpacking a million-byte field peaked at {peak}"

    def test_result_space_grows_with_fields(self) -> None:
        small, large = struct.Struct("20000q"), struct.Struct("200000q")
        small_data = small.pack(*range(1_000_000, 1_020_000))
        large_data = large.pack(*range(1_000_000, 1_200_000))

        small_peak = peak_bytes(lambda: small.unpack(small_data))
        large_peak = peak_bytes(lambda: large.unpack(large_data))

        assert large_peak > small_peak * 8, (
            f"10x the fields peaked at {small_peak} then {large_peak}"
        )

    def test_a_pascal_string_returns_at_most_255_bytes(self) -> None:
        (value,) = struct.unpack("1000p", struct.pack("1000p", b"x" * 999))
        assert value == b"x" * 255

    @pytest.mark.timing
    def test_unpack_time_grows_with_fields(self) -> None:
        small, large = struct.Struct("1000q"), struct.Struct("100000q")
        small_data = small.pack(*range(1_000_000, 1_001_000))
        large_data = large.pack(*range(1_000_000, 1_100_000))

        small_ns = best_ns(lambda: small.unpack(small_data), inner=20)
        large_ns = best_ns(lambda: large.unpack(large_data))

        assert_grows_linearly("unpack() in fields", small_ns, large_ns)


class TestBuffersAreNotCopied:
    """`unpack_from()` unpacks the B-byte record at an offset; `iter_unpack()` is O(1) to
    create and O(k + t) per record, and holds an export of the buffer."""

    DATA = bytes(10_000_000)

    def test_unpack_from_does_not_copy_the_buffer(self) -> None:
        data = self.DATA

        peak = peak_bytes(lambda: struct.unpack_from("<i", data, 5_000_000))

        assert struct.unpack_from("<i", data, offset=5_000_000) == (0,)
        assert peak < 1_000, f"unpack_from() on 10 MB allocated {peak}"

    def test_creating_an_iterator_does_not_copy_the_buffer(self) -> None:
        data = self.DATA
        record = struct.Struct("<ii")

        peak = peak_bytes(lambda: record.iter_unpack(data))

        assert peak < 1_000, f"iter_unpack() over 10 MB allocated {peak}"

    def test_each_step_unpacks_one_record(self) -> None:
        records = struct.iter_unpack("<ii", self.DATA)

        peak = peak_bytes(lambda: next(records))

        assert next(records) == (0, 0)
        assert peak < 1_000, f"one step over a 10 MB buffer allocated {peak}"

    def test_the_buffer_stays_exported_until_exhaustion(self) -> None:
        buffer = bytearray(struct.pack("<3h", 1, 2, 3))
        records = struct.iter_unpack("<h", buffer)

        with pytest.raises(BufferError):
            buffer.extend(b"\x00\x00")

        assert list(records) == [(1,), (2,), (3,)]
        buffer.extend(b"\x00\x00")
        assert len(buffer) == 8

    def test_the_buffer_must_hold_whole_records(self) -> None:
        with pytest.raises(struct.error, match="multiple of 4"):
            struct.iter_unpack("<i", b"123456")


def _calcsize(fmt: str) -> int:
    return struct.calcsize(fmt)


def _lookup_peak(fmt: str, warm: str | None) -> int:
    """Traced peak of one calcsize(fmt), warming the function on a cached format.

    Pass warm=None only once _calcsize has already run, since a warm-up call
    would itself change the cache.
    """
    if warm is not None:
        _calcsize(warm)
    tracemalloc.start()
    try:
        _calcsize(fmt)
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class TestTheFormatCache:
    """The module-level functions cache compiled formats: a hit compiles
    nothing, and the cache holds 100 formats and is emptied when it fills."""

    FORMATS = [f"{count}x" for count in range(100)]

    def test_a_hit_compiles_nothing(self) -> None:
        first, again = "".join(["<", "7", "x"]), "".join(["<", "7", "x"])
        assert first == again and first is not again
        struct._clearcache()  # type: ignore[attr-defined]
        _calcsize("<1x")  # the warm-up format, now cached

        miss = _lookup_peak(first, warm="<1x")
        hit = _lookup_peak(again, warm="<1x")

        assert miss > 0, "a miss compiles the format"
        assert hit == 0, f"an equal format string found in the cache allocated {hit}"

    def test_the_cache_is_emptied_when_it_fills(self) -> None:
        struct._clearcache()  # type: ignore[attr-defined]
        for fmt in self.FORMATS:
            _calcsize(fmt)

        assert _lookup_peak(self.FORMATS[0], warm=self.FORMATS[50]) == 0, (
            "100 formats fit in the cache"
        )

        _calcsize("100x")

        assert _lookup_peak(self.FORMATS[99], warm="100x") > 0, "the 101st format emptied the cache"
        struct._clearcache()  # type: ignore[attr-defined]

    def test_more_than_100_formats_in_turn_miss_on_every_call(self) -> None:
        formats = [*self.FORMATS, "100x"]
        struct._clearcache()  # type: ignore[attr-defined]
        for fmt in formats:
            _calcsize(fmt)

        misses = sum(_lookup_peak(fmt, warm=None) > 0 for fmt in formats)

        assert misses == len(formats), f"{misses} of {len(formats)} calls in turn missed"
        struct._clearcache()  # type: ignore[attr-defined]


class TestStructAttributes:
    """`Struct.format` | O(m) | O(m) and `Struct.size` | O(1) | O(1)."""

    def test_format_is_a_new_string_on_each_access(self) -> None:
        header = struct.Struct("<4sIH")
        assert header.format == "<4sIH"
        assert header.format is not header.format

    def test_size_is_calcsize(self) -> None:
        for fmt in ("i", "3i", "10s", "<ihb", "!IH", "@ci"):
            assert struct.Struct(fmt).size == struct.calcsize(fmt)


class TestErrorsComeBeforeConversion:
    """`struct.error` - count and size checks run against the compiled format
    before any value is converted."""

    def test_a_wrong_count_converts_nothing(self) -> None:
        CountingIndex.calls = 0

        with pytest.raises(struct.error, match="expected 2 items"):
            struct.pack("<hh", CountingIndex())

        assert CountingIndex.calls == 0

    def test_a_short_buffer_converts_nothing(self) -> None:
        CountingIndex.calls = 0

        with pytest.raises(struct.error, match="requires a buffer of at least"):
            struct.pack_into("<hh", bytearray(2), 0, CountingIndex(), CountingIndex())

        assert CountingIndex.calls == 0
        assert struct.pack("<h", CountingIndex()) == b"\x01\x00"
        assert CountingIndex.calls == 1, "the counter does count a conversion"

    def test_a_short_buffer_is_rejected_by_unpack(self) -> None:
        with pytest.raises(struct.error, match="4 bytes"):
            struct.unpack("<i", b"AB")

    def test_an_out_of_range_value_and_a_bad_format(self) -> None:
        with pytest.raises(struct.error, match="format requires"):
            struct.pack("<h", 70_000)
        with pytest.raises(struct.error, match="bad char"):
            struct.calcsize("z")


class TestByteOrderChangesTheLayoutNotTheBound:
    """The prefix picks byte order and alignment."""

    def test_native_alignment_pads(self) -> None:
        assert struct.calcsize("=ci") == 5
        assert struct.calcsize("@ci") > struct.calcsize("=ci")

    def test_standard_sizes_are_fixed_across_byte_orders(self) -> None:
        for prefix in ("<", ">", "!", "="):
            assert struct.calcsize(f"{prefix}i") == 4
            assert struct.calcsize(f"{prefix}q") == 8

    @pytest.mark.timing
    @pytest.mark.parametrize("prefix", ["<", ">"])
    def test_every_byte_order_grows_linearly(self, prefix: str) -> None:
        small, large = struct.Struct(f"{prefix}1000i"), struct.Struct(f"{prefix}100000i")
        small_values, large_values = tuple(range(1_000)), tuple(range(100_000))

        small_ns = best_ns(lambda: small.pack(*small_values), inner=20)
        large_ns = best_ns(lambda: large.pack(*large_values))

        assert_grows_linearly(f"pack() with {prefix!r}", small_ns, large_ns)


class TestComplexFormats:
    """Version Notes: `F` and `D` were added in Python 3.14."""

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="F and D arrived in 3.14")
    def test_complex_values_round_trip(self) -> None:
        assert struct.calcsize("<F") == 8
        assert struct.calcsize("<D") == 16
        assert struct.unpack("<F", struct.pack("<F", 1 + 2j)) == (1 + 2j,)
        assert struct.unpack("<D", struct.pack("<D", 1 + 2j)) == (1 + 2j,)

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="F and D exist from 3.14")
    def test_complex_formats_are_rejected_before_3_14(self) -> None:
        for code in ("F", "D"):
            with pytest.raises(struct.error, match="bad char"):
                struct.calcsize(f"<{code}")


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
    """Each block runs in its own subprocess, so the format cache cannot leak
    between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert record.unpack(data) ==" in s)
        mutated = source.replace("(b'ok',)", "(b'no',)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
