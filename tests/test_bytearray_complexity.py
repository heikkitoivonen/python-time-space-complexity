"""Tests for docs/builtins/bytearray_func.md.

The page prices a bytearray as one resizable buffer with a start offset. A
modest increase overallocates it by an eighth, which makes appending
amortized O(1); removing a prefix advances the offset rather than moving the
tail, for `del ba[:k]` and for a shorter slice assigned at the front, which
still copies what it assigns; a change of length anywhere else shifts the
tail; and the splitting and transforming methods shared
with `bytes` build a new object, copying all n bytes even when nothing
changed, where its searches and predicates only read the buffer. Copies, temporaries and identity are settled by traced allocation and
`__alloc__()`, which need no tolerance; error and value behaviour by what is
raised or returned; the growth classes a counter cannot reach by timing a
hundredfold step in one dimension. A row claiming O(1) has to come in under
x3 for that step, and a row claiming linearity between x10 and x1,000 - far
from the x1 of a constant and the x10,000 of a square.

Measurement scope:

* Construction: `bytearray(count)`, `bytearray(bytes)`, `bytearray(str,
  'utf-8')`, `bytearray.fromhex()`, `bytearray(list)` and an ASCII encode
  with `errors='ignore'` - which emits nothing and still walks the string -
  all scale with their source. Building 10,000,000 bytes from a count or
  from a `bytes` traces a peak of at least 10,000,000. The copy is asserted
  independent of its source by mutating it, the empty bytearray has an
  allocation of 0, and the `TypeError` and `ValueError` cases are asserted by
  their messages. `fromhex()` takes a `bytes` argument on 3.14 and raises
  `TypeError` before.
* `len()`, `ba[i]`, `ba[i] = v` and `iter(ba)` cost the same at 100,000 and
  10,000,000 bytes, as do `append()`, `ba += bytes` of 100 bytes, `extend()`
  of 100 bytes, `pop()`, `del ba[0]`, `del ba[:10]`, `del ba[-1]`, a
  same-length slice assignment and a 10-byte slice. `pop(0)`, `insert(0, x)`,
  `insert()` at the middle, `remove()` of the first byte, deleting a middle
  slice and a length-changing slice assignment at the front all scale.
* Deleting from the front traces no allocation while the remainder stays
  above half the allocation. Crossing that threshold copies the remainder
  into a new buffer while the old one is still held, on every path that
  shrinks: `del ba[0]`, `del ba[:1]`, `pop(0)`, `remove()` and a shortening
  slice assignment each peak at the 500,000 bytes they carry over from a
  1,000,000-byte buffer, and leave the allocation at the remainder. That is
  the O(n) side of those rows' space columns. Draining 1,000,000 bytes one `del ba[:1]` at a time costs
  under thirty times draining 100,000, where draining with `pop(0)` costs
  more than twenty times for a tenfold input. A `pop()` after `del ba[:499]`
  on a 1,000-byte buffer is observed to compact it within three calls, which
  is why that row reads amortized rather than O(1).
* A slice assigned from a 1,000,000-byte `bytes` peaks above 1,000,000 where
  the same bytes as a `bytearray` peak under 100,000, which is the temporary
  the row's space column names. Assigning a bytearray to its own slice takes
  the temporary as well, and growing a full 100,000-byte buffer by one byte
  peaks at the whole new buffer, which is the other O(n) in that column.
  Shortening a slice costs the same at both buffer sizes when the slice
  starts at the front, where the start offset moves as it does for `del` -
  with an empty replacement and with a one-byte one - and scales when it
  starts in the middle.
* A one-byte append to a 1,000-byte buffer leaves more allocated than the
  length, where extending an empty bytearray by 1,000,000 bytes leaves
  exactly the length plus the terminating byte: the two halves of the growth
  policy. Building start to finish in 100-byte chunks scales with the total
  for `+=` and for `extend()`, as it does for `append()` one byte at a time.
  The append that runs out of buffer traces a peak of the whole new one,
  with the start offset moved or not, where an append with room to spare
  traces under 1,000 bytes: that is the amortized in its space column.
  Appending 2,000 bytes one at a time passes through fewer than 100 distinct
  `sys.getsizeof()` values, against 2,000 for a reallocation per append, and
  building a buffer start to finish scales with its length - which is the
  amortized claim itself, and the one thing timing a single `append()`
  cannot see, since the fastest of several samples skips the reallocating
  calls. Extending an empty bytearray with a 1,000,000-item generator peaks above
  2,000,000 bytes (the temporary plus the result); from a prepared `bytes`
  it peaks under 1,500,000. `bytes + b"y"` scales with the value it copies,
  which is the concatenation the page steers away from.
* `ba[:]` of 10,000,000 traces a peak of at least 10,000,000 and
  `memoryview(ba)` under 1,000. Under a live view `append()`, `del`,
  `clear()` and `+=` raise `BufferError` while an item assignment succeeds.
* `clear()` on 100,000,000 bytes costs far more than on 1,000,000 and leaves
  an allocation of at most one byte. `reverse()` traces no allocation and
  scales; `copy()` traces a full-size peak. `resize()` (3.14+) costs the same
  at both sizes when shrinking by one byte and growing back, and scales when
  halving and regrowing; shrinking 100,000,000 bytes to one costs far more
  than shrinking 1,000,000 to one, which is its n term.
* Searching: `find()`, `rfind()` and `in` for an absent byte, `count()` for a
  present one and `in` with a `bytes` pattern all scale with the buffer.
  `startswith()` costs the same on both buffer sizes and scales with the
  prefix instead. A tuple of 10,000 empty candidates, with `start` past the
  end so none can match, costs more than ten times a tuple of 100, which is
  the q term of its row. The O(n·m) reverse search is separated from the two-way
  forward one by holding a 100,000-byte buffer fixed and growing the pattern
  from 100 to 1,000 bytes, in the two shapes that each defeat one direction.
  Against a pattern mismatching at its second byte - rejected at once by any
  forward search, and compared in full at every position by a reverse one -
  `rfind()`, `rsplit()` and `rpartition()` each cost between x4 and x50,
  where `find()`, `count()`, `split()`, `partition()` and `replace()` stay
  flat. Against one mismatching only at its last byte, which is what turns a
  naive forward scan quadratic, all eight come in under x3: that is the forward
  search's linear-time fallback, which the reverse search has no equivalent
  of.
* Transforms: seventeen methods are asserted to return a new bytearray that
  is not the receiver and to leave the receiver unchanged, each on an input
  it does not change - the five case methods on inputs chosen for them,
  since the shared one changes under those; `strip()` of a
  buffer with nothing to strip traces a full-size peak. `upper()`,
  `translate()`, `replace()` with no match and with every byte replaced by
  two, `strip()`, `removeprefix()`,
  `expandtabs()` and `center(10)` all scale with the receiver, and
  `expandtabs(0)` scales while returning nothing, which is the n term of its
  row. The w term of `replace()`, `center()` and `expandtabs()` is measured
  twice at a fixed input: as allocation, where a hundredfold result peaks
  more than ten times higher, and as time on a ten-byte receiver, where a
  tenfold result from 1,000,000 to 10,000,000 bytes costs between x3 and
  x40 - about x10 measured, against the x100 a result rebuilt by repeated
  concatenation would cost. `strip()` at a fixed 1,000,000 bytes costs
  x10 for ten times the `chars`, more than four times as much with the
  stripped byte last in `chars` as first, and a quarter as much with nothing
  to strip, and x10 again for a hundredfold `chars` with nothing to strip at
  all - the (s + 1)·c term. `translate()` at a fixed 1,000-byte receiver
  scales with the bytes in `delete`, which is its d term. `maketrans()`
  returns 256 bytes for 1-byte and 200-byte arguments and traces under 2,000
  bytes for the latter; over arguments of repeated bytes it scales with
  their length while still returning 256, which is its k term.
* `split()` scales with the buffer and `join()` with the bytes in ten parts,
  with the number of parts, and with the number of *empty* parts - which
  produce no output at all. Joining 1,000,000 empty parts peaks above
  10,000,000 bytes, which is the p term of its row. `partition()` on a miss
  returns the whole buffer as a copy plus two empties.
* Predicates: `isalpha()` scales with the letters it reads and costs more
  than ten times as much as the same buffer with a digit in front.
  `decode()`, `hex()`, `isascii()`, `==` between equal buffers and iteration
  all scale, as do `ba + other` in each of its two operands separately,
  `bytes(ba)` - which also traces a full-size peak - and `ba *= count` in
  the receiver's length and in the count, each measured on a buffer built
  outside the timing since the operation consumes it; `==` between buffers of different length costs the same at both
  sizes. `ba *= count` for a count of 0 or less leaves an empty bytearray
  with at most one byte allocated, which is `clear()`'s release rather than
  a count-sized result. `ba * count` scales in both of its dimensions, measured on 10,000
  and 1,000,000-byte buffers: a hundredfold buffer at a fixed count, and a
  hundredfold count at a fixed buffer.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `clear()`, and `resize()` shrinking, are O(n) because the allocator
  returns the pages; a small buffer shrinks in place at O(1), so both
  measurements span 1,000,000 to 100,000,000 bytes, where glibc unmaps, and
  carry no upper bound.
* The O(n + m) bound on `find()`, `count()` and `in` follows from the two-way
  algorithm in Objects/stringlib/fastsearch.h, present since 3.10; only the n
  term is timed. The reverse search's worst case is measured at one buffer
  size, by pattern length alone.
* The growth policy's threshold and the compaction threshold are read
  from bytearray_resize in Objects/bytearrayobject.c, the same on every
  supported branch; the tests observe that reallocations are rare and that
  compaction happens, not the ratios themselves.
* The `str` constructor is timed with UTF-8 and with ASCII plus
  `errors='ignore'`; other codecs and error handlers are not varied.
* `strip()`'s (s + 1)·c term is measured with `chars` holding one byte that
  matches; a `chars` where several match earlier lowers the constant without
  changing the term. The three stripping methods share one implementation,
  and only `strip()` is timed.
* The encoding rows are scoped to codecs and error handlers whose cost and
  output are proportional to their input. Only UTF-8 and ASCII are measured.
  A registered handler may return a replacement of any length, and a codec
  that rebuilds its result as it goes costs more than its output; both are
  caller-chosen and neither is measured.
* Timings hold the element values fixed, all `b"a"` or zeros. The scaling
  measurements run at 100,000 and 10,000,000 bytes except for `ba * count`,
  whose result would reach 100 MB there: its ratio then prices the page
  faults of writing that, not the product, so it is measured two orders
  smaller.
"""

from __future__ import annotations

import array
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "bytearray_func.md"
EXPECTED_BLOCKS = 8

SMALL = 100_000
LARGE = 10_000_000
STEP = LARGE / SMALL  # every scaling measurement below uses this hundredfold step
LINEAR = 10  # a hundredfold input must cost at least this much more
CONSTANT = 3  # ... and at most this much more when the row says O(1)
QUADRATIC = 1_000  # ... and below this, where a quadratic one would be near x10,000


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


def growth(small: Callable[[], Any], large: Callable[[], Any], inner: int = 1) -> float:
    """How many times more the large call costs than the small one."""
    return best_ns(large, inner=inner) / best_ns(small, inner=inner)


def assert_linear(name: str, ratio: float) -> None:
    """A hundredfold input costs far more than a constant and far less than a square."""
    assert LINEAR < ratio < QUADRATIC, f"{name}: {STEP:.0f}x the input cost x{ratio:.1f}"


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def letters(size: int) -> bytearray:
    return bytearray(b"a" * size)


class TestConstruction:
    """`bytearray(count)` | O(n), `bytearray(bytes_like)` | O(k) as a copy,
    `bytearray(iterable)` | O(k) item by item, `bytearray(str, encoding)` |
    O(k), `fromhex()` | O(k); the empty one allocates nothing."""

    def test_the_empty_bytearray_allocates_no_buffer(self) -> None:
        assert bytearray().__alloc__() == 0
        assert bytearray(0) == bytearray()

    def test_a_count_gives_that_many_zero_bytes(self) -> None:
        assert bytearray(5) == b"\x00\x00\x00\x00\x00"
        with pytest.raises(ValueError, match="negative count"):
            bytearray(-1)

    def test_a_count_allocates_the_buffer_up_front(self) -> None:
        peak = peak_bytes(lambda: bytearray(LARGE))

        assert peak >= LARGE, f"bytearray({LARGE}) peaked at {peak} bytes"

    def test_a_bytes_like_source_is_copied_not_shared(self) -> None:
        source = bytearray(b"hello")

        copy = bytearray(source)
        copy[0] = ord("j")

        assert copy is not source
        assert source == bytearray(b"hello")
        assert bytearray(memoryview(b"xy")) == b"xy"
        assert bytearray(array.array("B", [1, 2])) == b"\x01\x02"

    def test_copying_a_bytes_allocates_its_length(self) -> None:
        source = bytes(LARGE)

        peak = peak_bytes(lambda: bytearray(source))

        assert peak >= LARGE, f"bytearray(bytes of {LARGE}) peaked at {peak} bytes"

    def test_an_iterable_supplies_one_byte_per_item(self) -> None:
        assert bytearray([65, 66, 67]) == b"ABC"
        assert bytearray(value for value in range(3)) == b"\x00\x01\x02"
        with pytest.raises(ValueError, match="range\\(0, 256\\)"):
            bytearray([0, 256])
        with pytest.raises(ValueError, match="range\\(0, 256\\)"):
            bytearray([-1])

    def test_a_string_needs_an_encoding(self) -> None:
        assert bytearray("café", "utf-8") == b"caf\xc3\xa9"
        assert bytearray("é" * 1_000, "ascii", "ignore") == b"", "the discarded input is still read"
        with pytest.raises(TypeError, match="without an encoding"):
            bytearray("café")  # type: ignore[call-overload]

    def test_fromhex_reads_two_characters_per_byte(self) -> None:
        assert bytearray.fromhex("48 65") == b"He"
        assert bytearray.fromhex("4865") == b"He"

    def test_fromhex_takes_bytes_from_3_14(self) -> None:
        if sys.version_info >= (3, 14):
            assert bytearray.fromhex(b"ab") == b"\xab"  # type: ignore[arg-type]
        else:
            with pytest.raises(TypeError):
                bytearray.fromhex(b"ab")  # type: ignore[arg-type]

    @pytest.mark.timing
    def test_each_constructor_scales_with_its_source(self) -> None:
        small_bytes, large_bytes = bytes(SMALL), bytes(LARGE)
        small_text, large_text = "é" * SMALL, "é" * LARGE
        small_hex, large_hex = "ab" * SMALL, "ab" * LARGE
        small_list, large_list = [0] * (SMALL // 10), [0] * (LARGE // 10)

        ratios = {
            "count": growth(lambda: bytearray(SMALL), lambda: bytearray(LARGE)),
            "bytes": growth(lambda: bytearray(small_bytes), lambda: bytearray(large_bytes)),
            "str": growth(
                lambda: bytearray(small_text, "utf-8"), lambda: bytearray(large_text, "utf-8")
            ),
            "fromhex": growth(
                lambda: bytearray.fromhex(small_hex), lambda: bytearray.fromhex(large_hex)
            ),
            "list": growth(lambda: bytearray(small_list), lambda: bytearray(large_list)),
            # A lossy handler emits nothing, and still walks every character.
            "str, ascii, ignore": growth(
                lambda: bytearray(small_text, "ascii", "ignore"),
                lambda: bytearray(large_text, "ascii", "ignore"),
            ),
        }

        for name, ratio in ratios.items():
            assert_linear(f"bytearray from {name}", ratio)


class TestIndexingIsConstant:
    """`len(ba)`, `ba[i]`, `ba[i] = v` | O(1)."""

    def test_items_are_ints_in_range(self) -> None:
        data = bytearray(b"abc")
        data[0] = 65
        value: Any = b"b"

        assert data[0] == 65
        assert data == b"Abc"
        with pytest.raises(ValueError, match="range\\(0, 256\\)"):
            data[0] = 256
        with pytest.raises(TypeError):
            data[0] = value

    @pytest.mark.timing
    def test_size_does_not_change_the_cost(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        def write(target: bytearray) -> None:
            target[len(target) // 2] = 98

        ratios = {
            "len": growth(lambda: len(small), lambda: len(large), inner=100),
            "read": growth(lambda: small[SMALL // 2], lambda: large[LARGE // 2], inner=100),
            "write": growth(lambda: write(small), lambda: write(large), inner=100),
        }

        for name, ratio in ratios.items():
            assert ratio < CONSTANT, f"{name}: 100x the buffer cost x{ratio:.2f}"


class TestSlicesCopyViewsShare:
    """`ba[a:b]` | O(k) | O(k) as a new bytearray; `memoryview(ba)` | O(1) and
    pins the length."""

    def test_a_slice_is_an_independent_bytearray(self) -> None:
        data = bytearray(b"abcdefgh")

        piece = data[2:5]
        piece[0] = ord("X")

        assert isinstance(piece, bytearray)
        assert data[:] is not data
        assert data == b"abcdefgh"
        assert piece == b"Xde"
        assert data[::2] == b"aceg"

    def test_a_full_slice_allocates_the_whole_buffer_and_a_view_does_not(self) -> None:
        data = bytearray(LARGE)

        slice_peak = peak_bytes(lambda: data[:])
        view_peak = peak_bytes(lambda: memoryview(data))

        assert slice_peak >= LARGE, f"ba[:] of {LARGE} bytes peaked at {slice_peak}"
        assert view_peak < 1_000, f"memoryview() peaked at {view_peak} bytes"

    def test_a_live_view_pins_the_length(self) -> None:
        data = bytearray(b"abc")
        view = memoryview(data)

        def delete_first() -> None:
            del data[0]

        def concatenate() -> None:
            nonlocal data
            data += b"d"

        for change in (lambda: data.append(0), delete_first, data.clear, concatenate):
            with pytest.raises(BufferError, match="cannot be re-sized"):
                change()
        view[0] = ord("A")
        assert data == b"Abc"

        view.release()
        data.append(0)
        assert data == b"Abc\x00"

    @pytest.mark.timing
    def test_a_slice_costs_its_own_length_not_the_buffer_s(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        across_buffers = growth(lambda: small[5:15], lambda: large[5:15], inner=100)
        across_slices = growth(lambda: large[:SMALL], lambda: large[:LARGE], inner=3)

        assert across_buffers < CONSTANT, f"a 10-byte slice cost x{across_buffers:.2f} on 100x"
        assert_linear("ba[:k]", across_slices)


class TestSliceAssignment:
    """`ba[a:b] = data` | O(k) at the same length, O(n + k) when the length
    changes."""

    def test_same_length_replaces_and_other_lengths_shift(self) -> None:
        data = bytearray(b"0123456789")

        data[:2] = b""
        assert data == b"23456789"
        data = bytearray(b"0123456789")
        data[2:4] = b"AB"
        assert data == b"01AB456789"
        data[2:4] = b"abcd"
        assert data == b"01abcd456789"
        data[2:6] = b""
        assert data == b"01456789"
        data[0:2] = [1, 2]
        assert data == b"\x01\x02456789"
        with pytest.raises(ValueError, match="extended slice"):
            data[::2] = b"x"

    def test_a_non_bytearray_operand_is_copied_to_a_temporary(self) -> None:
        size = 1_000_000
        from_bytes, from_bytearray = bytes(size), bytearray(size)
        target = bytearray(size)

        bytes_peak = peak_bytes(lambda: target.__setitem__(slice(0, size), from_bytes))
        bytearray_peak = peak_bytes(lambda: target.__setitem__(slice(0, size), from_bytearray))
        self_peak = peak_bytes(lambda: target.__setitem__(slice(None), target))

        assert bytes_peak >= size, f"a bytes operand peaked at {bytes_peak}"
        assert bytearray_peak < size / 10, f"a bytearray operand peaked at {bytearray_peak}"
        assert self_peak >= size, f"assigning the receiver to itself peaked at {self_peak}"

    def test_growing_the_buffer_by_one_byte_allocates_all_of_it(self) -> None:
        """The other O(n) in that row's space column, with no compaction."""
        data = bytearray(SMALL)
        one_byte = bytearray(b"x")

        peak = peak_bytes(lambda: data.__setitem__(slice(1, 1), one_byte))

        assert peak >= SMALL, f"growing a full buffer by one byte peaked at {peak}"

    @pytest.mark.timing
    def test_only_a_change_of_length_costs_the_tail(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        def replace(target: bytearray) -> None:
            target[0:10] = b"bbbbbbbbbb"

        def grow_then_shrink(target: bytearray) -> None:
            target[0:0] = b"b"
            target[0:1] = b""

        one_byte = bytearray(b"x")

        def shorten_at_the_front(target: bytearray) -> None:
            target[:1] = b""
            target.append(0)  # restore the length, itself O(1) amortized

        def replace_a_longer_prefix(target: bytearray) -> None:
            target[:2] = one_byte  # shorter, but not empty: the byte is copied in
            target.append(0)

        def shorten_in_the_middle(target: bytearray) -> None:
            middle = len(target) // 2
            target[middle : middle + 1] = b""
            target.append(0)

        same_length = growth(lambda: replace(small), lambda: replace(large), inner=100)
        new_length = growth(
            lambda: grow_then_shrink(small), lambda: grow_then_shrink(large), inner=10
        )
        at_the_front = growth(
            lambda: shorten_at_the_front(small), lambda: shorten_at_the_front(large), inner=100
        )
        replacing_at_the_front = growth(
            lambda: replace_a_longer_prefix(small),
            lambda: replace_a_longer_prefix(large),
            inner=100,
        )
        in_the_middle = growth(
            lambda: shorten_in_the_middle(small), lambda: shorten_in_the_middle(large), inner=10
        )

        assert same_length < CONSTANT, f"a same-length assignment cost x{same_length:.2f}"
        assert_linear("a length-changing slice assignment", new_length)
        assert at_the_front < CONSTANT, f"shortening at the front cost x{at_the_front:.2f}"
        assert replacing_at_the_front < CONSTANT, (
            f"a shorter non-empty prefix cost x{replacing_at_the_front:.2f}"
        )
        assert_linear("shortening a slice in the middle", in_the_middle)


class TestAppendIsAmortized:
    """`append(x)` | O(1) amortized, `ba += other` | O(k) amortized, `extend()`
    | O(k): the buffer overallocates, so a reallocation is rare."""

    def test_the_buffer_grows_in_jumps_not_per_append(self) -> None:
        buffer = bytearray()
        sizes: set[int] = set()
        for _ in range(2_000):
            buffer.append(0)
            sizes.add(sys.getsizeof(buffer))

        assert 1 < len(sizes) < 100, f"2,000 appends passed through {len(sizes)} sizes"

    def test_the_append_that_grows_the_buffer_allocates_all_of_it(self) -> None:
        """Which is what amortized means in the space column too.

        An append with room to spare allocates nothing; the one that runs out
        takes a whole new buffer, and takes it whether or not the start
        offset has moved.
        """
        full, offset = bytearray(SMALL), bytearray(SMALL)
        del offset[0]  # advances the start offset, leaving the buffer in place

        growing = peak_bytes(lambda: full.append(0))
        growing_with_an_offset = peak_bytes(lambda: offset.append(0))
        with_room = peak_bytes(lambda: full.append(0))

        assert growing >= SMALL, f"the growing append peaked at {growing}"
        assert growing_with_an_offset >= SMALL, f"peaked at {growing_with_an_offset}"
        assert with_room < 1_000, f"an append with room to spare peaked at {with_room}"

    def test_a_modest_increase_overallocates_and_a_large_one_does_not(self) -> None:
        """Both halves of the growth policy the amortized claim rests on."""
        modest = bytearray(1_000)
        modest.append(0)
        large = bytearray()
        large.extend(bytes(1_000_000))

        assert modest.__alloc__() > len(modest) * 1.1, (
            f"a one-byte append took {modest.__alloc__()} for {len(modest)} bytes"
        )
        assert large.__alloc__() == len(large) + 1, (
            f"a 1,000,000-byte extend took {large.__alloc__()}"
        )

    def test_extend_copies_a_buffer_directly_and_gathers_an_iterable_first(self) -> None:
        size = 1_000_000
        source = bytes(size)

        from_bytes = peak_bytes(lambda: bytearray().extend(source))
        from_generator = peak_bytes(lambda: bytearray().extend(0 for _ in range(size)))

        assert from_bytes < size * 1.5, f"extend(bytes) peaked at {from_bytes} for {size}"
        assert from_generator >= size * 2, f"extend(generator) peaked at {from_generator}"

    def test_extend_and_iadd_accept_any_bytes_like_or_iterable(self) -> None:
        buffer = bytearray(b"a")
        buffer += b"b"
        buffer += memoryview(b"c")
        buffer.extend([100])
        buffer.extend(bytearray(b"e"))

        assert buffer == b"abcde"
        with pytest.raises(ValueError, match="range\\(0, 256\\)"):
            buffer.extend([256])

    @pytest.mark.timing
    def test_growing_costs_the_added_bytes_not_the_buffer(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        chunk = bytes(100)
        items = [0] * 100

        def concatenate(target: bytearray) -> None:
            target += chunk

        ratios = {
            "append": growth(lambda: small.append(0), lambda: large.append(0), inner=100),
            "+=": growth(lambda: concatenate(small), lambda: concatenate(large), inner=100),
            "extend": growth(lambda: small.extend(items), lambda: large.extend(items), inner=100),
        }

        for name, ratio in ratios.items():
            assert ratio < CONSTANT, f"{name} onto a 100x larger buffer cost x{ratio:.2f}"

    @pytest.mark.timing
    def test_a_whole_run_of_appends_stays_linear(self) -> None:
        """Amortized O(1) is a claim about the run, not about one call.

        Timing single appends cannot see it: the fastest of several samples
        skips the reallocating ones. Building the buffer start to finish at
        two sizes prices every reallocation on the way.
        """

        def build(size: int) -> bytearray:
            buffer = bytearray()
            for _ in range(size):
                buffer.append(0)
            return buffer

        short_run = best_ns(lambda: build(SMALL), repeats=3)
        long_run = best_ns(lambda: build(LARGE), repeats=2)

        assert_linear("appending one byte at a time", long_run / short_run)

    @pytest.mark.timing
    def test_a_whole_run_of_chunks_stays_linear_too(self) -> None:
        """`+=` and `extend()` over a build, for the same reason as append."""
        chunk = bytes(100)

        def build(size: int, concatenate: bool) -> bytearray:
            buffer = bytearray()
            for _ in range(size // len(chunk)):
                if concatenate:
                    buffer += chunk
                else:
                    buffer.extend(chunk)
            return buffer

        for name, concatenate in (("+=", True), ("extend()", False)):
            short = best_ns(lambda c=concatenate: build(SMALL, c), repeats=3)  # type: ignore[misc]
            long = best_ns(lambda c=concatenate: build(LARGE, c), repeats=2)  # type: ignore[misc]

            assert_linear(f"building with {name} in 100-byte chunks", long / short)

    @pytest.mark.timing
    def test_extend_scales_with_the_operand(self) -> None:
        small_bytes, large_bytes = bytes(SMALL), bytes(LARGE)
        small_list, large_list = [0] * (SMALL // 10), [0] * (LARGE // 10)

        from_bytes = growth(
            lambda: bytearray().extend(small_bytes), lambda: bytearray().extend(large_bytes)
        )
        from_list = growth(
            lambda: bytearray().extend(small_list), lambda: bytearray().extend(large_list)
        )

        assert_linear("extend(bytes)", from_bytes)
        assert_linear("extend(list)", from_list)

    @pytest.mark.timing
    def test_bytes_concatenation_copies_everything_accumulated(self) -> None:
        small, large = bytes(SMALL), bytes(LARGE)

        ratio = growth(lambda: small + b"y", lambda: large + b"y")

        assert_linear("bytes + b'y'", ratio)


class TestFrontDeletionAdvancesTheStart:
    """`del ba[i]`, `del ba[a:b]` | O(n), amortized O(1) at the front; `pop(i)`,
    `insert(i, x)`, `remove(x)` | O(n); `pop()` | O(1) amortized."""

    def test_deleting_and_popping_give_the_documented_values(self) -> None:
        buffer = bytearray(b"header:payload:trailer")

        del buffer[:7]
        assert buffer == b"payload:trailer"
        assert buffer.pop(0) == ord("p")
        buffer.insert(0, ord("P"))
        assert buffer == b"Payload:trailer"
        del buffer[-8:]
        assert buffer == b"Payload"
        assert buffer.pop() == ord("d")
        buffer.remove(ord("a"))
        assert buffer == b"Pyloa"
        with pytest.raises(ValueError, match="not found"):
            buffer.remove(ord("z"))
        with pytest.raises(IndexError, match="pop from empty"):
            bytearray().pop()

    def test_a_pop_compacts_the_buffer_once_it_is_half_empty(self) -> None:
        """Which is why that row reads amortized O(1) rather than O(1)."""
        data = bytearray(1_000)
        del data[:499]  # the start offset advances; the allocation does not move
        oversized = data.__alloc__()
        assert oversized > len(data) * 1.5, f"{oversized} allocated for {len(data)} bytes"

        steps = []
        for _ in range(3):
            data.pop()
            steps.append((len(data), data.__alloc__()))

        assert any(allocated <= size + 1 for size, allocated in steps), (
            f"the buffer stayed oversized across {steps}"
        )

    def test_deleting_from_the_front_allocates_nothing_until_it_compacts(self) -> None:
        data = bytearray(LARGE)

        def delete_prefix() -> None:
            del data[:10]

        assert peak_bytes(delete_prefix) < 100
        assert len(data) == LARGE - 10
        assert data.__alloc__() > LARGE, "the buffer was compacted for a 10-byte prefix"

    @pytest.mark.parametrize(
        ("name", "shrink"),
        [
            ("del ba[0]", lambda ba: ba.__delitem__(0)),
            ("del ba[:1]", lambda ba: ba.__delitem__(slice(0, 1))),
            ("pop(0)", lambda ba: ba.pop(0)),
            ("remove(x)", lambda ba: ba.remove(0)),
            ("ba[:1] = b''", lambda ba: ba.__setitem__(slice(0, 1), b"")),
        ],
    )
    def test_compaction_allocates_the_remainder_it_copies(
        self, name: str, shrink: Callable[[bytearray], object]
    ) -> None:
        """The O(n) side of the space column, on every path that shrinks.

        The buffer is taken to just above half its allocation first, so the
        next shrink of any kind crosses the threshold. The remainder is
        copied into a new buffer while the old one is still held.
        """
        size = 1_000_000
        data = bytearray(size)
        del data[: size // 2]  # advances the start offset; the allocation stays
        remainder = len(data)
        assert data.__alloc__() > remainder * 1.5

        peak = peak_bytes(lambda: shrink(data))

        assert peak >= remainder - 1, f"{name} compacted {remainder} bytes with a peak of {peak}"
        assert data.__alloc__() <= remainder, f"{name} left {data.__alloc__()} allocated"

    def test_the_buffer_is_compacted_once_the_remainder_falls_below_half(self) -> None:
        data = bytearray(LARGE)

        del data[: LARGE // 4]
        assert data.__alloc__() > LARGE, "a quarter is still above half the allocation"

        del data[: LARGE // 2]
        assert data.__alloc__() <= len(data) + 1, (
            f"{data.__alloc__()} bytes still allocated for {len(data)}"
        )

    @pytest.mark.timing
    def test_the_front_and_the_back_are_constant_and_the_middle_is_not(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        def delete_first(target: bytearray) -> None:
            del target[0]

        def delete_prefix(target: bytearray) -> None:
            del target[:10]

        def delete_last(target: bytearray) -> None:
            del target[-1]

        def delete_middle(target: bytearray) -> None:
            middle = len(target) // 2
            del target[middle : middle + 10]

        def insert_middle(target: bytearray) -> None:
            target.insert(len(target) // 2, 97)

        constant = {
            "del ba[0]": growth(lambda: delete_first(small), lambda: delete_first(large), 100),
            "del ba[:10]": growth(lambda: delete_prefix(small), lambda: delete_prefix(large), 10),
            "del ba[-1]": growth(lambda: delete_last(small), lambda: delete_last(large), 100),
            "pop()": growth(small.pop, large.pop, 100),
        }
        linear = {
            "pop(0)": growth(lambda: small.pop(0), lambda: large.pop(0), 10),
            "insert(0, x)": growth(lambda: small.insert(0, 97), lambda: large.insert(0, 97), 10),
            "insert middle": growth(lambda: insert_middle(small), lambda: insert_middle(large), 10),
            "remove(x)": growth(lambda: small.remove(97), lambda: large.remove(97), 10),
            "del middle": growth(lambda: delete_middle(small), lambda: delete_middle(large), 10),
        }

        for name, ratio in constant.items():
            assert ratio < CONSTANT, f"{name} on a 100x larger buffer cost x{ratio:.2f}"
        for name, ratio in linear.items():
            assert_linear(name, ratio)

    @pytest.mark.timing
    def test_draining_from_the_front_is_linear_in_total(self) -> None:
        def drain_by_deleting(size: int) -> None:
            buffer = bytearray(size)
            while buffer:
                del buffer[:1]

        def drain_by_popping(size: int) -> None:
            buffer = bytearray(size)
            while buffer:
                buffer.pop(0)

        deleting = best_ns(lambda: drain_by_deleting(1_000_000), repeats=3) / best_ns(
            lambda: drain_by_deleting(100_000), repeats=3
        )
        popping = best_ns(lambda: drain_by_popping(100_000), repeats=3) / best_ns(
            lambda: drain_by_popping(10_000), repeats=3
        )

        assert deleting < 30, f"draining 10x the bytes with del ba[:1] cost x{deleting:.1f}"
        assert popping > 20, f"draining 10x the bytes with pop(0) cost x{popping:.1f}"


class TestClearReverseCopyAndResize:
    """`clear()` | O(n) frees the buffer; `reverse()` | O(n) | O(1) in place;
    `copy()` | O(n) | O(n); `resize(size)` | O(n + size) | O(size), 3.14+."""

    def test_clear_releases_the_buffer(self) -> None:
        data = bytearray(LARGE)

        data.clear()

        assert len(data) == 0
        assert data.__alloc__() <= 1, f"clear() kept {data.__alloc__()} bytes allocated"

    def test_reverse_is_in_place_and_copy_is_not(self) -> None:
        data = letters(LARGE)
        data[0] = ord("b")

        reverse_peak = peak_bytes(data.reverse)
        copy_peak = peak_bytes(data.copy)
        copy = data.copy()

        assert reverse_peak < 100, f"reverse() allocated {reverse_peak} bytes"
        assert data[-1] == ord("b")
        assert copy_peak >= LARGE, f"copy() of {LARGE} bytes peaked at {copy_peak}"
        assert copy == data and copy is not data

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="resize() was added in 3.14")
    def test_resize_zero_fills_growth_and_truncates(self) -> None:
        data = bytearray(b"abc")

        data.resize(6)  # type: ignore[attr-defined]
        assert data == b"abc\x00\x00\x00"
        data.resize(2)  # type: ignore[attr-defined]
        assert data == b"ab"
        with pytest.raises(ValueError, match="positive sizes"):
            data.resize(-1)  # type: ignore[attr-defined]
        view = memoryview(data)
        with pytest.raises(BufferError, match="cannot be re-sized"):
            data.resize(10)  # type: ignore[attr-defined]
        view.release()

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="resize() exists from 3.14")
    def test_resize_is_absent_before_3_14(self) -> None:
        assert not hasattr(bytearray, "resize")

    @pytest.mark.timing
    def test_clear_costs_the_buffer_it_frees(self) -> None:
        def clear_cost(size: int) -> float:
            best: float | None = None
            for _ in range(5):
                data = bytearray(size)
                start = time.perf_counter_ns()
                data.clear()
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        ratio = clear_cost(100_000_000) / clear_cost(1_000_000)

        # No upper bound: the small buffer is released in place, so the ratio
        # reflects the allocator returning pages rather than a growth class.
        assert ratio > LINEAR, f"clear() of 100x the bytes cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_reverse_scales_with_the_buffer(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        ratio = growth(small.reverse, large.reverse)

        assert_linear("reverse()", ratio)

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="resize() was added in 3.14")
    @pytest.mark.timing
    def test_shrinking_costs_the_buffer_it_gives_back(self) -> None:
        """The n term: the same release `clear()` pays for, so no upper bound."""

        def shrink_cost(size: int) -> float:
            best: float | None = None
            for _ in range(5):
                data = bytearray(size)
                start = time.perf_counter_ns()
                data.resize(1)  # type: ignore[attr-defined]
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        ratio = shrink_cost(100_000_000) / shrink_cost(1_000_000)

        assert ratio > LINEAR, f"resizing 100x the buffer down to one byte cost x{ratio:.1f}"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="resize() was added in 3.14")
    @pytest.mark.timing
    def test_resize_costs_the_bytes_it_moves(self) -> None:
        small, large = bytearray(SMALL), bytearray(LARGE)

        def nudge(target: bytearray) -> None:
            size = len(target)
            target.resize(size - 1)  # type: ignore[attr-defined]
            target.resize(size)  # type: ignore[attr-defined]

        def halve_and_regrow(target: bytearray) -> None:
            size = len(target)
            target.resize(size // 2)  # type: ignore[attr-defined]
            target.resize(size)  # type: ignore[attr-defined]

        by_one = growth(lambda: nudge(small), lambda: nudge(large), inner=100)
        by_half = growth(lambda: halve_and_regrow(small), lambda: halve_and_regrow(large))

        assert by_one < CONSTANT, f"resizing by one byte on 100x the buffer cost x{by_one:.2f}"
        assert_linear("halving and regrowing", by_half)


class TestSearching:
    """`find()`, `index()`, `count()`, `in` | O(n + m); `startswith()`,
    `endswith()` | O(m); `rfind()`, `rindex()` | O(n·m) in the worst case."""

    def test_the_documented_results(self) -> None:
        haystack = letters(10_000)

        assert haystack.find(b"ab" + b"a" * 98) == -1
        assert haystack.rfind(b"ab" + b"a" * 98) == -1
        assert haystack.count(b"aa") == 5_000
        assert haystack.count(97) == 10_000
        assert haystack.startswith(b"aaa") and haystack.endswith((b"b", b"a"))
        assert 97 in haystack and b"aa" in haystack and 98 not in haystack
        assert haystack.find(97, 100) == 100
        with pytest.raises(ValueError, match="not found"):
            haystack.index(b"b")
        with pytest.raises(ValueError, match="not found"):
            haystack.rindex(98)

    @pytest.mark.timing
    def test_a_scan_scales_with_the_buffer(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        ratios = {
            "find": growth(lambda: small.find(b"b"), lambda: large.find(b"b")),
            "rfind": growth(lambda: small.rfind(b"b"), lambda: large.rfind(b"b")),
            "count": growth(lambda: small.count(97), lambda: large.count(97)),
            "in int": growth(lambda: 98 in small, lambda: 98 in large),
            "in bytes": growth(lambda: b"b" in small, lambda: b"b" in large),
        }

        for name, ratio in ratios.items():
            assert_linear(name, ratio)

    @pytest.mark.timing
    def test_startswith_costs_the_prefix_not_the_buffer(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        short_prefix, long_prefix = b"a" * SMALL, b"a" * LARGE

        across_buffers = growth(
            lambda: small.startswith(b"a" * 10),
            lambda: large.startswith(b"a" * 10),
            inner=100,
        )
        across_prefixes = growth(
            lambda: large.startswith(short_prefix), lambda: large.startswith(long_prefix), inner=3
        )

        assert across_buffers < CONSTANT, f"a 10-byte prefix cost x{across_buffers:.2f} on 100x"
        assert_linear("startswith(prefix)", across_prefixes)

    def test_a_tuple_of_candidates_is_accepted(self) -> None:
        data = bytearray(b"abc")

        assert data.startswith((b"z", b"ab")) and data.endswith((b"z", b"bc"))
        assert not data.startswith((b"z", b"y"))

    @pytest.mark.timing
    def test_a_tuple_costs_its_candidates_even_when_they_are_empty(self) -> None:
        """The q term: every candidate is tried, whatever its length."""
        data = bytearray(b"a")
        few, many = (b"",) * 100, (b"",) * 10_000

        # `start` past the end, so no candidate can match and none is skipped.
        ratio = growth(lambda: data.startswith(few, 2), lambda: data.startswith(many, 2), inner=3)

        assert ratio > LINEAR, f"100x the candidates cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_only_the_reverse_search_pays_for_the_pattern_at_every_position(self) -> None:
        """Hold the buffer fixed and grow the pattern tenfold, in two shapes.

        Each shape defeats one direction. A pattern that mismatches at its
        second byte is rejected at once by any forward search, naive or not,
        and is the one a reverse search has to compare in full at every
        position. A pattern that mismatches only at its last byte is the
        reverse of that: trivial backwards, and the case a naive forward scan
        turns quadratic. Staying flat on it is what separates the documented
        O(n + m) from a scan with no linear-time fallback.
        """
        haystack = letters(SMALL)
        shapes = {
            "mismatching at the second byte": (b"ab" + b"a" * 98, b"ab" + b"a" * 998),
            "mismatching at the last byte": (b"a" * 98 + b"ba", b"a" * 998 + b"ba"),
        }
        backward = ["rfind", "rsplit", "rpartition"]
        searches = ["find", "count", "split", "partition", "replace", *backward]

        def measure(name: str, pattern: bytes) -> Callable[[], Any]:
            if name == "replace":  # the one search here that takes two arguments
                return lambda: haystack.replace(pattern, b"x")
            return lambda: getattr(haystack, name)(pattern)

        for shape, (short, long) in shapes.items():
            for name in searches:
                ratio = growth(measure(name, short), measure(name, long), inner=3)
                if name in backward and shape == "mismatching at the second byte":
                    # Above x4 excludes a pattern-independent search, below
                    # x50 a cost quadratic in it; O(n·m) gives about x10.
                    assert 4 < ratio < 50, f"{name} paid x{ratio:.2f} for 10x a pattern {shape}"
                else:
                    assert ratio < CONSTANT, f"{name} paid x{ratio:.2f} for 10x a pattern {shape}"


TRANSFORMS: dict[str, Callable[[bytearray], bytearray]] = {
    "strip": lambda ba: ba.strip(b"z"),
    "lstrip": lambda ba: ba.lstrip(b"z"),
    "rstrip": lambda ba: ba.rstrip(b"z"),
    "removeprefix": lambda ba: ba.removeprefix(b"z"),
    "removesuffix": lambda ba: ba.removesuffix(b"z"),
    "replace": lambda ba: ba.replace(b"z", b"y"),
    "translate": lambda ba: ba.translate(None),
    "upper": lambda ba: ba.upper(),
    "lower": lambda ba: ba.lower(),
    "capitalize": lambda ba: ba.capitalize(),
    "title": lambda ba: ba.title(),
    "swapcase": lambda ba: ba.swapcase(),
    "center": lambda ba: ba.center(1),
    "ljust": lambda ba: ba.ljust(1),
    "rjust": lambda ba: ba.rjust(1),
    "zfill": lambda ba: ba.zfill(1),
    "expandtabs": lambda ba: ba.expandtabs(),
}


class TestTransformsReturnNewObjects:
    """Every transforming method | O(n) | O(n): a new bytearray, whether or
    not anything changed; `maketrans()` | O(k) | O(1) as a 256-byte table."""

    @pytest.mark.parametrize("name", sorted(TRANSFORMS))
    def test_the_receiver_is_untouched_and_the_result_is_new(self, name: str) -> None:
        data = bytearray(b"  Hello  ")

        result = TRANSFORMS[name](data)

        assert isinstance(result, bytearray)
        assert result is not data
        assert data == b"  Hello  "

    @pytest.mark.parametrize(
        ("name", "unchanged"),
        [
            ("upper", b"HELLO 123"),
            ("lower", b"hello 123"),
            ("capitalize", b"Hello world"),
            ("title", b"Hello World"),
            ("swapcase", b"123 456"),
        ],
    )
    def test_a_case_method_copies_even_when_the_case_is_already_right(
        self, name: str, unchanged: bytes
    ) -> None:
        """The other rows meet an input they leave alone through TRANSFORMS;
        these five need one chosen for them."""
        data = bytearray(unchanged)

        result = getattr(data, name)()

        assert result == unchanged, f"{name} changed an input it should not have"
        assert result is not data, f"{name} returned the receiver"

    def test_the_documented_results(self) -> None:
        data = bytearray(b"  Hello  ")
        table = bytearray.maketrans(b"lo", b"01")

        assert data.strip() == b"Hello"
        assert data.upper() == b"  HELLO  "
        assert data.translate(table, delete=b" ") == b"He001"
        assert data.translate(None, b" ") == b"Hello"
        assert bytearray(b"a\tb").expandtabs(4) == b"a   b"
        assert bytearray(b"7").zfill(3) == b"007"
        assert bytearray(b"ab").center(6, b"*") == b"**ab**"
        assert bytearray(b"ab").removeprefix(b"a") == b"b"

    def test_a_copy_is_made_even_when_nothing_changes(self) -> None:
        data = letters(LARGE)

        peak = peak_bytes(data.strip)

        assert peak >= LARGE, f"strip() with nothing to strip peaked at {peak} bytes"

    def test_maketrans_is_always_256_bytes(self) -> None:
        short = bytearray.maketrans(b"a", b"b")
        long_from, long_to = bytes(range(200)), bytes(range(200))

        peak = peak_bytes(lambda: bytearray.maketrans(long_from, long_to))
        long = bytearray.maketrans(long_from, long_to)

        assert isinstance(short, bytes) and len(short) == len(long) == 256
        assert peak < 2_000, f"maketrans() of 200 bytes peaked at {peak}"
        with pytest.raises(ValueError, match="same length"):
            bytearray.maketrans(b"a", b"bc")
        with pytest.raises(ValueError, match="256"):
            bytearray(b"a").translate(b"x")

    @pytest.mark.timing
    def test_maketrans_reads_its_arguments_whatever_it_returns(self) -> None:
        """The k term, at a fixed 256-byte result.

        Repeated bytes let the arguments grow past 256 while the table they
        build does not, so only their length can move the cost.
        """
        short, long = b"a" * SMALL, b"a" * LARGE

        ratio = growth(
            lambda: bytearray.maketrans(short, short), lambda: bytearray.maketrans(long, long)
        )

        assert len(bytearray.maketrans(long, long)) == 256
        assert_linear("maketrans()", ratio)

    @pytest.mark.timing
    def test_each_transform_scales_with_the_buffer(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        table = bytearray.maketrans(b"a", b"b")

        ratios = {
            "upper": growth(small.upper, large.upper),
            "translate": growth(lambda: small.translate(table), lambda: large.translate(table)),
            "replace, no match": growth(
                lambda: small.replace(b"b", b"c"), lambda: large.replace(b"b", b"c")
            ),
            # Every byte replaced, and the result twice the input: the hit
            # path, where an implementation rebuilding as it goes would show.
            "replace, every byte": growth(
                lambda: small.replace(b"a", b"bb"), lambda: large.replace(b"a", b"bb")
            ),
            "strip": growth(small.strip, large.strip),
            "removeprefix": growth(
                lambda: small.removeprefix(b"b"), lambda: large.removeprefix(b"b")
            ),
            "expandtabs": growth(small.expandtabs, large.expandtabs),
            "center(10)": growth(lambda: small.center(10), lambda: large.center(10)),
        }

        for name, ratio in ratios.items():
            assert_linear(name, ratio)

    @pytest.mark.timing
    def test_stripping_searches_chars_once_per_byte_it_strips(self) -> None:
        """The s·c term.

        `chars` is a membership test, scanned linearly, so the byte being
        stripped has to sit at its end for the scan to show: with it first,
        every lookup stops at the first byte and the cost is the copy alone.
        Stripping nothing still costs the one lookup that stops each end,
        which is the + 1 in the row's (s + 1)·c.
        """
        data = bytearray(b"a" * 1_000_000)
        # Every `chars` is built here: allocating one scales with c too, and
        # inside the timed call it would pass for the cost being measured.
        short, long = b"x" * 99 + b"a", b"x" * 999 + b"a"
        first, absent = b"a" + b"x" * 999, b"x" * 1_000

        by_chars = growth(lambda: data.strip(short), lambda: data.strip(long), inner=3)
        match_first = best_ns(lambda: data.strip(first), inner=3)
        nothing_to_strip = best_ns(lambda: data.strip(absent), inner=3)
        match_last = best_ns(lambda: data.strip(long), inner=3)

        assert 4 < by_chars < 50, f"10x the chars cost x{by_chars:.2f}"
        assert match_last > match_first * 4, (
            f"the byte's position in chars was free: {match_last:.0f}ns against {match_first:.0f}ns"
        )
        assert nothing_to_strip < match_last / 4, (
            f"stripping nothing cost {nothing_to_strip:.0f}ns against {match_last:.0f}ns"
        )

        # ... but not nothing: the boundary byte is still looked up.
        tiny = bytearray(b"a" * 1_000)
        few, many = b"x" * 1_000, b"x" * 100_000
        stopping = growth(lambda: tiny.strip(few), lambda: tiny.strip(many), inner=3)
        assert stopping > LINEAR, f"100x the chars cost x{stopping:.1f} with nothing to strip"

    @pytest.mark.timing
    def test_translate_reads_every_byte_of_delete(self) -> None:
        """The d term, at a receiver small enough for n not to hide it."""
        data = bytearray(b"a" * 1_000)
        few, many = b"x" * 10_000, b"x" * 1_000_000

        ratio = growth(
            lambda: data.translate(None, few), lambda: data.translate(None, many), inner=3
        )

        assert_linear("translate(None, delete)", ratio)

    def test_the_result_length_drives_what_a_transform_allocates(self) -> None:
        """The w term of `replace()`, the padding rows and `expandtabs()`.

        Held at a fixed input, each of these writes an output the caller
        sizes, and allocates it. The matching time term is timed separately,
        at a receiver small enough that the n term cannot hide it.
        """
        source = bytearray(b"a" * 10_000)
        tabs = bytearray(b"\t" * 10_000)

        peaks = {
            "replace": (
                peak_bytes(lambda: source.replace(b"a", b"b")),
                peak_bytes(lambda: source.replace(b"a", b"b" * 100)),
            ),
            "center": (
                peak_bytes(lambda: source.center(10_000)),
                peak_bytes(lambda: source.center(1_000_000)),
            ),
            "expandtabs": (
                peak_bytes(lambda: tabs.expandtabs(8)),
                peak_bytes(lambda: tabs.expandtabs(800)),
            ),
        }

        assert len(tabs.expandtabs(800)) == 8_000_000
        assert len(source.replace(b"a", b"b" * 100)) == 1_000_000
        for name, (narrow, wide) in peaks.items():
            assert wide > narrow * 10, f"{name} peaked at {narrow} and {wide} bytes"

    @pytest.mark.timing
    def test_the_result_length_drives_what_a_transform_costs(self) -> None:
        """The same w term in time, which allocation alone cannot settle.

        Ten bytes in, and a result of 1,000,000 then 10,000,000: a tenfold
        step, where linear gives about x10 and a result built by repeated
        concatenation would give about x100.
        """
        source = bytearray(b"a" * 10)
        tabs = bytearray(b"\t" * 10)
        filler, longer_filler = b"b" * 100_000, b"b" * 1_000_000

        ratios = {
            "center": growth(lambda: source.center(1_000_000), lambda: source.center(10_000_000)),
            "expandtabs": growth(
                lambda: tabs.expandtabs(100_000), lambda: tabs.expandtabs(1_000_000)
            ),
            "replace": growth(
                lambda: source.replace(b"a", filler),
                lambda: source.replace(b"a", longer_filler),
            ),
        }

        for name, ratio in ratios.items():
            assert 3 < ratio < 40, f"{name}: 10x the result cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_expandtabs_reads_the_input_it_does_not_write(self) -> None:
        """`tabsize=0` produces nothing, and still costs the whole input."""
        small, large = bytearray(b"\t" * SMALL), bytearray(b"\t" * LARGE)

        assert large.expandtabs(0) == b""
        assert_linear(
            "expandtabs(0)", growth(lambda: small.expandtabs(0), lambda: large.expandtabs(0))
        )


class TestSplittingAndJoining:
    """`split()`, `splitlines()` | O(n); `partition()` | O(n + m) copying
    everything; `rsplit()` and `rpartition()` | O(n·m) in the worst case;
    `join()` | O(p + w) in the parts and the result."""

    def test_the_pieces_are_new_bytearrays(self) -> None:
        data = bytearray(b"a,b,c")

        parts = data.split(b",")

        assert parts == [b"a", b"b", b"c"]
        assert all(isinstance(part, bytearray) for part in parts)
        assert data.rsplit(b",", 1) == [b"a,b", b"c"]
        assert bytearray(b"a\nb").splitlines() == [b"a", b"b"]
        assert data.partition(b",") == (b"a", b",", b"b,c")
        assert data.rpartition(b"z") == (b"", b"", b"a,b,c")
        assert data.rpartition(b"z")[2] is not data

    def test_join_accepts_bytes_like_parts_and_returns_a_bytearray(self) -> None:
        joined = bytearray(b",").join([b"a", bytearray(b"b"), memoryview(b"c")])

        assert joined == b"a,b,c"
        assert isinstance(joined, bytearray)
        with pytest.raises(TypeError):
            bytearray(b",").join(["a"])  # type: ignore[list-item]

    @pytest.mark.timing
    def test_split_scales_with_the_buffer(self) -> None:
        small = bytearray(b"aaaaaaaaa," * (SMALL // 10))
        large = bytearray(b"aaaaaaaaa," * (LARGE // 10))

        ratio = growth(lambda: small.split(b","), lambda: large.split(b","))

        assert_linear("split()", ratio)

    def test_join_costs_something_per_part_whatever_it_holds(self) -> None:
        """Empty parts produce no output, and each still costs a descriptor."""
        parts = [b""] * 1_000_000

        peak = peak_bytes(lambda: bytearray(b"").join(parts))

        assert bytearray(b"").join(parts) == b""
        assert peak > 10_000_000, f"1,000,000 empty parts peaked at {peak} bytes"

    @pytest.mark.timing
    def test_join_scales_with_the_parts_and_with_the_result(self) -> None:
        few_parts, many_parts = [b"ab"] * 10_000, [b"ab"] * 1_000_000
        few_empty, many_empty = [b""] * 10_000, [b""] * 1_000_000
        small_parts, big_parts = [bytes(10_000)] * 10, [bytes(1_000_000)] * 10
        separator = bytearray(b",")

        by_count = growth(lambda: separator.join(few_parts), lambda: separator.join(many_parts))
        # An empty separator, so p empty parts produce no output at all and
        # only the part count can move the cost.
        nothing = bytearray(b"")
        by_empty_count = growth(lambda: nothing.join(few_empty), lambda: nothing.join(many_empty))
        by_size = growth(
            lambda: separator.join(small_parts), lambda: separator.join(big_parts), inner=3
        )

        assert_linear("join() over 100x the parts", by_count)
        assert_linear("join() over 100x the empty parts", by_empty_count)
        assert_linear("join() over 100x the bytes in ten parts", by_size)


class TestPredicatesAndConversions:
    """The `is*()` predicates | O(n) | O(1), stopping at the first deciding
    byte; `decode()`, `hex()` | O(n) | O(n)."""

    def test_the_documented_results(self) -> None:
        data = bytearray(b"Hello")

        assert data.isalpha() and data.isalnum() and data.isascii() and data.istitle()
        assert not (data.isdigit() or data.islower() or data.isupper() or data.isspace())
        assert data.decode() == "Hello"
        assert data.decode("ascii") == "Hello"
        assert data.hex() == "48656c6c6f"
        assert data.hex(":") == "48:65:6c:6c:6f"
        assert data.hex("_", 2) == "48_656c_6c6f"

    @pytest.mark.timing
    def test_a_predicate_stops_at_the_first_deciding_byte(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        decided_early = bytearray(b"1") + large

        full_scan = growth(small.isalpha, large.isalpha)
        early_exit = growth(decided_early.isalpha, large.isalpha)

        assert_linear("isalpha()", full_scan)
        assert early_exit > LINEAR, f"a leading digit left isalpha() at x1/{early_exit:.0f}"

    @pytest.mark.timing
    def test_conversions_scale_with_the_buffer(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        ratios = {
            "decode": growth(small.decode, large.decode),
            "hex": growth(small.hex, large.hex),
            "isascii": growth(small.isascii, large.isascii),
        }

        for name, ratio in ratios.items():
            assert_linear(name, ratio)


class TestComparisonsIterationAndArithmetic:
    """`==` | O(n), O(1) when the lengths differ; `hash()` raises; iteration
    | O(n); `+` and `*` build a new bytearray of the result's length."""

    def test_the_documented_results(self) -> None:
        data = bytearray(b"ab")

        assert data == b"ab" and data != b"abc" and data < b"b"
        assert list(data) == [97, 98]
        assert data + b"c" == b"abc" and data * 3 == b"ababab"
        assert data + b"c" is not data
        data *= 2
        assert data == b"abab"
        assert data * 0 == b"" and data * -1 == b""
        with pytest.raises(TypeError, match="unhashable"):
            hash(data)

    def test_converting_to_bytes_copies_the_buffer(self) -> None:
        data = bytearray(LARGE)

        peak = peak_bytes(lambda: bytes(data))

        assert peak >= LARGE, f"bytes() of {LARGE} bytes peaked at {peak}"

    @pytest.mark.timing
    def test_converting_to_bytes_scales_with_the_buffer(self) -> None:
        small, large = bytearray(SMALL), bytearray(LARGE)

        assert_linear("bytes(ba)", growth(lambda: bytes(small), lambda: bytes(large), inner=3))

    @pytest.mark.timing
    def test_repeating_in_place_scales_in_both_dimensions(self) -> None:
        """`*=` grows the receiver, so each run needs a fresh one; the buffer
        is built outside the measurement."""

        def repeat_cost(size: int, count: int) -> float:
            best: float | None = None
            for _ in range(5):
                data = bytearray(size)
                start = time.perf_counter_ns()
                data *= count
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        by_length = repeat_cost(1_000_000, 10) / repeat_cost(10_000, 10)
        by_count = repeat_cost(10_000, 1_000) / repeat_cost(10_000, 10)

        assert_linear("ba *= count over 100x the bytes", by_length)
        assert_linear("ba *= count over 100x the count", by_count)

    @pytest.mark.parametrize("count", [0, -3])
    def test_repeating_by_zero_or_less_empties_the_buffer(self, count: int) -> None:
        """Which is the release `clear()` pays for, not a count-sized result."""
        data = bytearray(1_000_000)

        data *= count

        assert data == b""
        assert data.__alloc__() <= 1, f"{data.__alloc__()} bytes still allocated"

    @pytest.mark.timing
    def test_concatenation_copies_both_operands(self) -> None:
        """O(n + k): each side moves the cost on its own."""
        small, large = bytearray(SMALL), bytearray(LARGE)
        tiny = bytearray(b"x")

        by_receiver = growth(lambda: small + tiny, lambda: large + tiny, inner=3)
        by_operand = growth(lambda: tiny + small, lambda: tiny + large, inner=3)

        assert_linear("ba + other over 100x the receiver", by_receiver)
        assert_linear("ba + other over 100x the operand", by_operand)

    @pytest.mark.timing
    def test_equality_walks_equal_lengths_and_shortcuts_different_ones(self) -> None:
        small, small_twin = bytearray(SMALL), bytearray(SMALL)
        large, large_twin = bytearray(LARGE), bytearray(LARGE)
        small_longer, large_longer = bytearray(SMALL + 1), bytearray(LARGE + 1)

        same_length = growth(lambda: small == small_twin, lambda: large == large_twin)
        different = growth(lambda: small == small_longer, lambda: large == large_longer, inner=100)

        assert_linear("== over equal lengths", same_length)
        assert different < CONSTANT, f"== on different lengths cost x{different:.2f} on 100x"

    @pytest.mark.timing
    def test_iteration_and_repetition_scale_with_their_output(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        iteration = growth(lambda: sum(small), lambda: sum(large))
        making_an_iterator = growth(lambda: iter(small), lambda: iter(large), inner=100)
        # Repetition is measured on buffers two orders smaller: the row is
        # O(n·count) in the result, and a 100 MB one prices the page faults
        # of writing it rather than the product.
        narrow, wide = letters(10_000), letters(1_000_000)
        by_length = growth(lambda: narrow * 10, lambda: wide * 10, inner=3)
        by_count = growth(lambda: narrow * 10, lambda: narrow * 1_000, inner=3)

        assert_linear("iterating", iteration)
        assert_linear("ba * count over 100x the bytes", by_length)
        assert_linear("ba * count over 100x the count", by_count)
        assert making_an_iterator < CONSTANT, f"iter() cost x{making_an_iterator:.2f} on 100x"


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
        line, source = next((n, s) for n, s in _blocks() if "assert first == ord" in s)
        mutated = source.replace('assert first == ord("p")', 'assert first == ord("q")', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
