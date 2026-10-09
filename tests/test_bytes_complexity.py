"""Tests for docs/builtins/bytes.md.

The page prices a `bytes` as one immutable buffer. Its searches and
predicates only read it; everything that produces bytes builds a new object,
except that an exact `bytes` returns itself wherever the result would be an
equal copy. Identity and allocation settle those rows with no tolerance: `is`
separates the receiver from a copy, and a traced peak separates an n-byte
copy from none. Values and errors are settled by what is returned or raised,
and the growth classes a counter cannot reach by timing a hundredfold step in
one dimension. A row claiming O(1) has to come in under x3 for that step, and
a row claiming linearity between x10 and x1,000 - far from the x1 of a
constant and the x10,000 of a square.

Measurement scope:

* `len()`, `b[i]`, `iter(b)`, `memoryview(b)` and a 10-byte slice cost the
  same at 100,000 and 10,000,000 bytes; a slice of k bytes scales with k.
  `b[:]` and `b[::1]` are the receiver and trace no allocation where `b[1:]`
  of 10,000,000 bytes traces at least that, and a `memoryview` and a slice of
  one trace under 1,000 bytes. Item assignment raises `TypeError` and writing
  through the view raises `TypeError` for read-only memory.
* `b + other` scales in each operand separately and leaves both untouched;
  `b * count` scales in the receiver and in the count, measured on 10,000
  and 1,000,000-byte receivers so the result stays under 100 MB. `b * 1` is
  the receiver and `b * 0` and `b * -1` are empty. Building the same
  1,000,000 bytes by `+=` from 1,000 chunks costs more than five times
  building them from 100, where `b"".join()` of the same chunks costs under
  three times.
* `==` between equal 10,000,000-byte objects scales, and between objects of
  different length it does not. `<` between equal-length objects scales when
  they differ only in the last byte and does not when they differ in the
  first. Iterating with `sum()` scales.
* `hash()` of a freshly built object scales with its length, timed with the
  object built outside the measurement; a second `hash()` of the same object
  costs the same at both sizes.
* `%` scales with a format string of literal bytes followed by one `%s`,
  which the result copies, so n and w grow together there; and with the
  result alone at a fixed two-byte format string, using a `bytes` value.
  A format string of 10,000,000 `-` flags and one `%s`, formatting `b""`,
  returns `b""` and traces a peak of at least 10,000,000 bytes: the n in
  the space column.
* Searching: `find()`, `rfind()` and `in` for an absent byte, `count()` for a
  present one and `in` with a `bytes` pattern scale with the receiver.
  `startswith()` costs the same on both receiver sizes and scales with the
  prefix instead; a tuple of 10,000 empty candidates with `start` past the
  end costs more than ten times a tuple of 100, the q term. The O(n·m)
  reverse search is separated from the forward one by holding a
  100,000-byte receiver fixed and growing the pattern from 100 to 1,000
  bytes, in two shapes. Against a pattern mismatching at its second byte,
  `rfind()`, `rsplit()` and `rpartition()` each cost between x4 and x50,
  where `find()`, `count()`, `split()`, `partition()` and `replace()` stay
  flat; against one mismatching only at its next-to-last byte all eight
  come in under x3.
* Receiver identity: every row whose Notes say `b itself` is asserted with
  `is` on an input it leaves unchanged - `replace()` with no match and with
  a count of 0, `translate()` with `None`, an identity table and an absent
  `delete`, the three strips with and without `chars`, `removeprefix()` and
  `removesuffix()` with an absent and an empty affix, the four padding
  methods at a width at or below the length, `split()` and `rsplit()` with an
  absent separator and with whitespace splitting on input without
  whitespace, `splitlines()` with no line break, `partition()` and
  `rpartition()` on a miss, and `join()` of one `bytes` part. The case
  methods and `expandtabs()` are asserted to return a new object on inputs
  they leave unchanged, and a `bytes` subclass to get a new exact `bytes`
  from `strip()`.
* What identity saves: with nothing to strip, `strip()`, `strip(chars)`,
  `center(10)` and `removeprefix()` of an absent prefix cost the same at
  100,000 and 10,000,000 bytes, where stripping every byte scales; on a
  fixed 1,000-byte receiver with nothing to strip, 100x the `chars` costs
  more than x10, which is the O(c) left. `removeprefix()` of a prefix
  mismatching only at its last byte scales with the prefix at a fixed
  receiver, the O(m) of the absent case. `replace()` with no match and
  `partition()` and `split()` on a miss trace under 1,000 bytes over
  10,000,000, while `partition()` on a hit traces the bytes it copies and
  `translate()` returning its receiver still traces a full-size peak.
* Transforms: `upper()`, `translate()`, `replace()` with every byte
  replaced by two, `strip()` of every byte, `removeprefix()` of a present
  prefix, `expandtabs()` and `center(n + 10)` scale with the receiver, and
  `expandtabs(0)` scales while returning nothing. The w term of
  `replace()`, `center()` and `expandtabs()` is a tenfold result at a fixed
  ten-byte receiver costing between x3 and x40. `strip(chars)` at a fixed
  100,000 bytes stripped costs between x10 and x1,000 as `chars` grows from
  100 to 10,000 bytes with the stripped byte last in it. `translate()` at a
  fixed 1,000 bytes scales with `delete`. `maketrans()` returns 256 bytes for
  1-byte and 200-byte arguments, traces under 2,000 bytes, and scales with
  arguments of repeated bytes.
* Splitting and joining: `split()` scales; `join()` scales with ten parts'
  bytes, with the number of parts and with the number of empty parts, and
  200,000 empty parts peak above 2,000,000 bytes, the p term.
* Predicates and conversions: `isalpha()` scales and costs more than ten
  times as much as the same bytes with a digit in front; `decode()`, `hex()`,
  `isascii()` and `bytes.fromhex()` scale. `fromhex()` takes a `bytes`
  argument from 3.14 and raises `TypeError` before.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(n + m) bound on `find()`, `count()`, `split()`, `partition()`,
  `replace()` and `in` follows from the two-way algorithm in
  Objects/stringlib/fastsearch.h, present on every supported branch; only the
  n term and the flat response to the pattern are timed. The reverse search
  is measured at one receiver size, by pattern length alone.
* The receiver-identity paths are read from Objects/bytesobject.c and
  Objects/stringlib/{transmogrify,split,partition,join}.h, the same from
  v3.10.19 through v3.14.2; only the pinned interpreter is run locally. They
  are asserted for an exact `bytes`; a subclass is checked only for `strip()`.
* The `%` row is measured with `%s` and a `bytes` value. Formatting an `int`
  with `%d` costs what `int` to decimal costs, which the page leaves to the
  value; other conversions are not varied.
* The `decode()` row is scoped to codecs and error handlers whose cost and
  output are proportional to their input; only UTF-8 is measured.
* `strip()`'s (s + 1)·c term is measured on `strip()` only; the three share
  one implementation. `bytes.fromhex()` is measured on `str` input.
* Timings hold the element values fixed. Scaling measurements run at 100,000
  and 10,000,000 bytes except where named above; `split()` runs at 50,000
  and 5,000,000 bytes, and `join()`'s part counts at 2,000 and 200,000.
"""

from __future__ import annotations

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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "bytes.md"
EXPECTED_BLOCKS = 7

SMALL = 100_000
LARGE = 10_000_000
STEP = LARGE / SMALL  # the hundredfold step of the scaling measurements, unless one says otherwise
LINEAR = 10  # a hundredfold input must cost at least this much more
CONSTANT = 3  # ... and at most this much more when the row says O(1)
QUADRATIC = 1_000  # ... and below this, where a quadratic one would be near x10,000

# The Windows heap hands a block above about 1 MB to VirtualAlloc and returns it
# on free, so each call that allocates one pays for freshly committed,
# zero-filled pages, while a 100 KB result stays cache-resident. An operation
# whose work is one bulk copy into a new buffer then costs far more than x100
# for the 100x step from SMALL to LARGE.
FRESH_PAGES_ON_WINDOWS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="on Windows a new buffer above about 1 MB is freshly committed, zero-filled pages, "
    "so the step crosses from cache-resident to page-faulting memory",
)


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
    """Peak traced allocation while func runs.

    func is called once first: from 3.12 the interpreter can attach monitoring
    data to a code object on its first run after any tracer has been
    installed, and that would land in the peak of a call that allocates
    nothing itself.
    """
    func()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def letters(size: int) -> bytes:
    return b"a" * size


class TestIndexingIsConstant:
    """`len(b)`, `b[i]` | O(1); `b[i] = v` raises `TypeError`."""

    def test_items_are_ints_and_cannot_be_assigned(self) -> None:
        data = b"abc"
        target: Any = data

        assert data[0] == 97 and data[-1] == 99
        with pytest.raises(TypeError, match="does not support item assignment"):
            target[0] = 106
        assert data == b"abc"

    @pytest.mark.timing
    def test_size_does_not_change_the_cost(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        ratios = {
            "len": growth(lambda: len(small), lambda: len(large), inner=100),
            "b[i]": growth(lambda: small[SMALL // 2], lambda: large[LARGE // 2], inner=100),
        }

        for name, ratio in ratios.items():
            assert ratio < CONSTANT, f"{name}: 100x the bytes cost x{ratio:.2f}"


class TestSlicesCopyViewsShare:
    """`b[i:j]` | O(k) | O(k), the receiver itself for a full step-1 slice;
    `memoryview(b)` | O(1), read-only, with O(1) slices."""

    def test_a_slice_is_a_new_bytes_unless_it_covers_everything(self) -> None:
        data = b"abcdefgh"

        assert data[2:5] == b"cde" and type(data[2:5]) is bytes
        assert data[::2] == b"aceg" and data[::-1] == b"hgfedcba"
        assert data[:] is data
        assert data[::1] is data
        assert data[0 : len(data)] is data
        assert data[1:] is not data

    def test_a_partial_slice_allocates_and_a_full_one_does_not(self) -> None:
        data = bytes(LARGE)

        partial = peak_bytes(lambda: data[1:])
        full = peak_bytes(lambda: data[:])

        assert partial >= LARGE - 1, f"b[1:] of {LARGE} bytes peaked at {partial}"
        assert full < 1_000, f"b[:] peaked at {full} bytes"

    def test_a_view_shares_the_buffer_and_is_read_only(self) -> None:
        data = bytes(LARGE)

        view_peak = peak_bytes(lambda: memoryview(data))
        slice_peak = peak_bytes(lambda: memoryview(data)[5 : LARGE - 5])
        view: Any = memoryview(data)

        assert view_peak < 1_000, f"memoryview() peaked at {view_peak} bytes"
        assert slice_peak < 1_000, f"a slice of the view peaked at {slice_peak} bytes"
        with pytest.raises(TypeError, match="read-only"):
            view[0] = 1
        assert view[1:3].tobytes() == b"\x00\x00"
        view.release()

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_a_slice_costs_its_own_length_not_the_receiver_s(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        across_receivers = growth(lambda: small[5:15], lambda: large[5:15], inner=100)
        across_slices = growth(lambda: large[1 : SMALL + 1], lambda: large[1:], inner=3)
        views = growth(lambda: memoryview(small), lambda: memoryview(large), inner=100)

        assert across_receivers < CONSTANT, f"a 10-byte slice cost x{across_receivers:.2f}"
        assert_linear("b[i:j]", across_slices)
        assert views < CONSTANT, f"memoryview() cost x{views:.2f} on 100x the bytes"


class TestConcatenationAndRepetition:
    """`b + other`, `b += other` | O(n + k); `b * count` | O(n·count), O(1)
    for a count of 1 or of 0 or less."""

    def test_concatenation_builds_a_new_object_and_leaves_both_alone(self) -> None:
        original = b"hello"
        mutable, view = bytearray(b"!"), memoryview(b"?")

        changed = b"j" + original[1:]
        joined = original + mutable + view

        assert changed == b"jello" and changed is not original
        assert joined == b"hello!?" and type(joined) is bytes
        assert original == b"hello" and mutable == b"!" and view == b"?"

    def test_repetition_by_one_is_the_receiver_and_by_zero_is_empty(self) -> None:
        data = b"ab"

        assert data * 3 == b"ababab"
        assert data * 1 is data
        assert data * 0 == b"" and data * -1 == b""

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_concatenation_copies_both_operands(self) -> None:
        small, large = bytes(SMALL), bytes(LARGE)
        tiny = b"x"

        by_receiver = growth(lambda: small + tiny, lambda: large + tiny, inner=3)
        by_operand = growth(lambda: tiny + small, lambda: tiny + large, inner=3)

        assert_linear("b + other over 100x the receiver", by_receiver)
        assert_linear("b + other over 100x the operand", by_operand)

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_repetition_scales_in_both_dimensions(self) -> None:
        # Two orders smaller than SMALL and LARGE: a 100 MB result would
        # price the page faults of writing it rather than the product.
        narrow, wide = letters(10_000), letters(1_000_000)

        by_length = growth(lambda: narrow * 10, lambda: wide * 10, inner=3)
        by_count = growth(lambda: narrow * 10, lambda: narrow * 1_000, inner=3)

        assert_linear("b * count over 100x the bytes", by_length)
        assert_linear("b * count over 100x the count", by_count)

    @pytest.mark.timing
    def test_accumulating_with_iadd_is_quadratic_and_join_is_not(self) -> None:
        """The same 1,000,000 bytes in 100 chunks and in 1,000.

        Holding the total fixed leaves the chunk count as the only thing that
        moves: if every += copies what came before, ten times the chunks
        costs about ten times as much, where `join()` - one pass over the
        parts and one copy of the total - barely moves.
        """
        total = 1_000_000

        def parts(count: int) -> list[bytes]:
            return [b"x" * (total // count)] * count

        def accumulate(chunks: list[bytes]) -> bytes:
            result = b""
            for chunk in chunks:
                result += chunk
            return result

        few, many = parts(100), parts(1_000)

        assert accumulate(many) == b"".join(few) == b"x" * total
        accumulating = best_ns(lambda: accumulate(many), repeats=3) / best_ns(
            lambda: accumulate(few), repeats=3
        )
        joining = growth(lambda: b"".join(few), lambda: b"".join(many), inner=3)

        assert accumulating > 5, f"10x the chunks by += cost x{accumulating:.1f}"
        assert joining < CONSTANT, f"10x the chunks by join() cost x{joining:.1f}"


class TestComparisonsAndIteration:
    """`==` | O(n), O(1) when the lengths differ; orderings walk to the first
    difference; iteration | O(n), `iter(b)` O(1)."""

    def test_the_documented_results(self) -> None:
        data = b"ab"

        assert data == b"ab" and data != b"abc" and data < b"b" and data > b"aa"
        assert list(data) == [97, 98]
        assert data != bytearray(b"x") and data == bytearray(b"ab")

    @pytest.mark.timing
    def test_equality_walks_equal_lengths_and_shortcuts_different_ones(self) -> None:
        small, small_twin = bytes(SMALL), bytes(SMALL)
        large, large_twin = bytes(LARGE), bytes(LARGE)
        small_longer, large_longer = bytes(SMALL + 1), bytes(LARGE + 1)

        same_length = growth(lambda: small == small_twin, lambda: large == large_twin)
        different = growth(lambda: small == small_longer, lambda: large == large_longer, inner=100)

        assert_linear("== over equal lengths", same_length)
        assert different < CONSTANT, f"== on different lengths cost x{different:.2f} on 100x"

    @pytest.mark.timing
    def test_ordering_stops_at_the_first_difference(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        small_last, large_last = letters(SMALL - 1) + b"b", letters(LARGE - 1) + b"b"
        small_first, large_first = b"b" + letters(SMALL - 1), b"b" + letters(LARGE - 1)

        at_the_end = growth(lambda: small < small_last, lambda: large < large_last)
        at_the_start = growth(lambda: small < small_first, lambda: large < large_first, 100)

        assert small < small_last and large < large_first
        assert_linear("< differing in the last byte", at_the_end)
        assert at_the_start < CONSTANT, f"< differing at once cost x{at_the_start:.2f}"

    @pytest.mark.timing
    def test_iteration_scales_and_making_an_iterator_does_not(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        iteration = growth(lambda: sum(small), lambda: sum(large))
        making_an_iterator = growth(lambda: iter(small), lambda: iter(large), inner=100)

        assert_linear("iterating", iteration)
        assert making_an_iterator < CONSTANT, f"iter() cost x{making_an_iterator:.2f} on 100x"


class TestHashIsCached:
    """`hash(b)` | O(n) the first time, then O(1); an equal object built
    separately hashes again."""

    def test_equal_bytes_hash_equal_and_a_bytearray_is_unhashable(self) -> None:
        key = b"GET /health HTTP/1.1".partition(b" HTTP/")[0]

        assert hash(key) == hash(b"GET /health")
        assert {b"GET /health": 1}[key] == 1
        with pytest.raises(TypeError, match="unhashable"):
            hash(bytearray(key))

    @pytest.mark.timing
    def test_the_first_hash_reads_every_byte_and_later_ones_do_not(self) -> None:
        def first_hash(size: int) -> float:
            best: float | None = None
            for _ in range(5):
                fresh = b"q" * size  # a new object, built outside the measurement
                start = time.perf_counter_ns()
                hash(fresh)
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        small, large = letters(SMALL), letters(LARGE)
        hash(small)
        hash(large)

        first = first_hash(LARGE) / first_hash(SMALL)
        cached = growth(lambda: hash(small), lambda: hash(large), inner=100)

        assert_linear("the first hash()", first)
        assert cached < CONSTANT, f"a cached hash() cost x{cached:.2f} on 100x the bytes"


class TestFormatting:
    """`b % values` | O(n + w) | O(n + w)."""

    def test_the_documented_results(self) -> None:
        assert b"%s-%d" % (b"x", 5) == b"x-5"
        assert b"%(a)s" % {b"a": b"q"} == b"q"
        assert b"%b" % bytearray(b"z") == b"z"

    def test_the_format_string_sizes_the_first_buffer(self) -> None:
        """The n in the space column: an empty result from a long format."""
        template = b"%" + b"-" * LARGE + b"s"  # LARGE flags, one conversion

        peak = peak_bytes(lambda: template % b"")

        assert template % b"" == b""
        assert peak >= LARGE, f"a {LARGE}-byte format string peaked at {peak} bytes"

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_formatting_scales_with_the_template_and_with_the_result(self) -> None:
        small_template, large_template = letters(SMALL) + b"%s", letters(LARGE) + b"%s"
        small_value, large_value = letters(SMALL), letters(LARGE)

        by_template = growth(lambda: small_template % b"x", lambda: large_template % b"x")
        by_result = growth(lambda: b"%s" % small_value, lambda: b"%s" % large_value)

        assert_linear("% over 100x the template", by_template)
        assert_linear("% over 100x the result", by_result)


class TestSearching:
    """`find()`, `index()`, `count()`, `in` | O(n + m); `startswith()`,
    `endswith()` | O(m + q); `rfind()`, `rindex()` | O(n·m) worst case."""

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
    def test_a_scan_scales_with_the_receiver(self) -> None:
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
    def test_startswith_costs_the_prefix_not_the_receiver(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        short_prefix, long_prefix = letters(SMALL), letters(LARGE)

        across_receivers = growth(
            lambda: small.startswith(b"a" * 10), lambda: large.startswith(b"a" * 10), inner=100
        )
        across_prefixes = growth(
            lambda: large.startswith(short_prefix), lambda: large.startswith(long_prefix), inner=3
        )

        assert across_receivers < CONSTANT, f"a 10-byte prefix cost x{across_receivers:.2f}"
        assert_linear("startswith(prefix)", across_prefixes)

    @pytest.mark.timing
    def test_a_tuple_costs_its_candidates_even_when_they_are_empty(self) -> None:
        """The q term: every candidate is tried, whatever its length."""
        data = b"a"
        few, many = (b"",) * 100, (b"",) * 10_000

        # `start` past the end, so no candidate can match and none is skipped.
        ratio = growth(lambda: data.startswith(few, 2), lambda: data.startswith(many, 2), inner=3)

        assert not data.startswith(many, 2)
        assert LINEAR < ratio < QUADRATIC, f"100x the candidates cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_only_the_reverse_search_pays_for_the_pattern_at_every_position(self) -> None:
        """Hold the receiver fixed and grow the pattern tenfold, in two shapes.

        A pattern that mismatches at its second byte is compared almost in
        full at every position by a reverse search, which then grows with the
        pattern; the forward search stays flat on it. A pattern that
        mismatches only near its end is the case a naive forward scan turns
        quadratic; staying flat on it is what separates the documented
        O(n + m) from a scan with no linear-time fallback.
        """
        haystack = letters(SMALL)
        shapes = {
            "mismatching at the second byte": (b"ab" + b"a" * 98, b"ab" + b"a" * 998),
            "mismatching at the next-to-last byte": (b"a" * 98 + b"ba", b"a" * 998 + b"ba"),
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


# Each call leaves its receiver unchanged and is documented to return it.
RETURNS_THE_RECEIVER: dict[str, Callable[[bytes], object]] = {
    "replace, no match": lambda b: b.replace(b"z", b"y"),
    "replace, count 0": lambda b: b.replace(b"H", b"y", 0),
    "translate(None)": lambda b: b.translate(None),
    "translate, identity table": lambda b: b.translate(bytes(range(256))),
    "translate, absent delete": lambda b: b.translate(None, b"z"),
    "strip()": lambda b: b.strip(),
    "lstrip()": lambda b: b.lstrip(),
    "rstrip()": lambda b: b.rstrip(),
    "strip(chars)": lambda b: b.strip(b"z"),
    "lstrip(chars)": lambda b: b.lstrip(b"z"),
    "rstrip(chars)": lambda b: b.rstrip(b"z"),
    "removeprefix, absent": lambda b: b.removeprefix(b"z"),
    "removeprefix, empty": lambda b: b.removeprefix(b""),
    "removesuffix, absent": lambda b: b.removesuffix(b"z"),
    "removesuffix, empty": lambda b: b.removesuffix(b""),
    "center": lambda b: b.center(5),
    "ljust": lambda b: b.ljust(3),
    "rjust": lambda b: b.rjust(5),
    "zfill": lambda b: b.zfill(0),
    "split(sep)": lambda b: b.split(b",")[0],
    "split()": lambda b: b.split()[0],
    "rsplit(sep)": lambda b: b.rsplit(b",")[0],
    "rsplit()": lambda b: b.rsplit()[0],
    "splitlines()": lambda b: b.splitlines()[0],
    "partition, miss": lambda b: b.partition(b",")[0],
    "rpartition, miss": lambda b: b.rpartition(b",")[2],
    "join of one part": lambda b: b",".join([b]),
}

# Each leaves this receiver unchanged too, and is documented to copy it.
ALWAYS_COPIES: dict[str, tuple[bytes, Callable[[bytes], bytes]]] = {
    "upper": (b"HELLO 1", lambda b: b.upper()),
    "lower": (b"hello 1", lambda b: b.lower()),
    "capitalize": (b"Hello world", lambda b: b.capitalize()),
    "title": (b"Hello World", lambda b: b.title()),
    "swapcase": (b"123 456", lambda b: b.swapcase()),
    "expandtabs": (b"no tabs", lambda b: b.expandtabs()),
}


class TestUnchangedResultsAreTheReceiver:
    """The rows whose Notes say `b` itself, and the ones that always copy."""

    @pytest.mark.parametrize("name", sorted(RETURNS_THE_RECEIVER))
    def test_a_call_that_changes_nothing_returns_the_receiver(self, name: str) -> None:
        data = b"Hello"

        assert RETURNS_THE_RECEIVER[name](data) is data

    @pytest.mark.parametrize("name", sorted(ALWAYS_COPIES))
    def test_these_copy_even_when_nothing_changes(self, name: str) -> None:
        data, call = ALWAYS_COPIES[name]

        result = call(data)

        assert result == data, f"{name} changed an input chosen to stay the same"
        assert result is not data, f"{name} returned the receiver"

    def test_a_subclass_gets_a_copy_from_strip(self) -> None:
        class Packet(bytes):
            pass

        packet = Packet(b"Hello")
        stripped = packet.strip()

        assert stripped == packet and stripped is not packet
        assert type(stripped) is bytes

    def test_a_miss_allocates_nothing_and_a_hit_copies(self) -> None:
        data = letters(LARGE)

        replace_miss = peak_bytes(lambda: data.replace(b"b", b"c"))
        partition_miss = peak_bytes(lambda: data.partition(b"b"))
        split_miss = peak_bytes(lambda: data.split(b"b"))
        partition_hit = peak_bytes(lambda: data.partition(b"a"))

        assert replace_miss < 1_000, f"replace() with no match peaked at {replace_miss}"
        assert partition_miss < 1_000, f"partition() on a miss peaked at {partition_miss}"
        assert split_miss < 1_000, f"split() on a miss peaked at {split_miss}"
        assert partition_hit >= LARGE - 1, f"partition() on a hit peaked at {partition_hit}"

    def test_translate_builds_the_result_before_returning_the_receiver(self) -> None:
        data = letters(LARGE)

        peak = peak_bytes(lambda: data.translate(None))

        assert data.translate(None) is data
        assert peak >= LARGE, f"translate(None) peaked at {peak} bytes"

    @pytest.mark.timing
    def test_returning_the_receiver_skips_the_copy(self) -> None:
        small, large = letters(SMALL), letters(LARGE)

        unchanged = {
            "strip()": growth(small.strip, large.strip, inner=100),
            "strip(chars)": growth(lambda: small.strip(b"x"), lambda: large.strip(b"x"), 100),
            "center(10)": growth(lambda: small.center(10), lambda: large.center(10), 100),
            "removeprefix, absent": growth(
                lambda: small.removeprefix(b"b"), lambda: large.removeprefix(b"b"), inner=100
            ),
        }
        stripping_everything = growth(lambda: small.strip(b"a"), lambda: large.strip(b"a"))

        for name, ratio in unchanged.items():
            assert ratio < CONSTANT, f"{name} with nothing to do cost x{ratio:.2f} on 100x"
        assert_linear("strip() of every byte", stripping_everything)

    @pytest.mark.timing
    def test_an_absent_affix_still_costs_its_length(self) -> None:
        """The O(m) of `removeprefix()` with the prefix absent, and the O(c)
        of a strip with nothing to strip, each at a fixed receiver."""
        data = letters(LARGE + 1)
        short_prefix, long_prefix = letters(SMALL - 1) + b"b", letters(LARGE - 1) + b"b"
        tiny = letters(1_000)
        few, many = b"x" * 10_000, b"x" * 1_000_000

        assert data.removeprefix(long_prefix) is data
        assert tiny.strip(many) is tiny
        by_prefix = growth(
            lambda: data.removeprefix(short_prefix), lambda: data.removeprefix(long_prefix), 3
        )
        by_chars = growth(lambda: tiny.strip(few), lambda: tiny.strip(many), inner=100)

        assert_linear("removeprefix() of an absent prefix", by_prefix)
        assert LINEAR < by_chars < QUADRATIC, (
            f"100x the chars cost x{by_chars:.1f} with nothing to strip"
        )


class TestTransforms:
    """The transforming rows: O(n) in the receiver, plus the w, c, d and k
    terms where the row names them."""

    def test_the_documented_results(self) -> None:
        data = b"  Hello  "
        table = bytes.maketrans(b"lo", b"01")

        assert data.strip() == b"Hello"
        assert data.upper() == b"  HELLO  "
        assert data.translate(table, delete=b" ") == b"He001"
        assert data.translate(None, b" ") == b"Hello"
        assert b"a\tb".expandtabs(4) == b"a   b"
        assert b"-7".zfill(3) == b"-07"
        assert b"ab".center(6, b"*") == b"**ab**"
        assert b"ab".removeprefix(b"a") == b"b" and b"ab".removesuffix(b"b") == b"a"
        assert b"aXbX".replace(b"X", b"-", 1) == b"a-bX"

    def test_maketrans_is_always_256_bytes(self) -> None:
        short = bytes.maketrans(b"a", b"b")
        long_from, long_to = bytes(range(200)), bytes(range(200))

        peak = peak_bytes(lambda: bytes.maketrans(long_from, long_to))
        long = bytes.maketrans(long_from, long_to)

        assert isinstance(short, bytes) and len(short) == len(long) == 256
        assert peak < 2_000, f"maketrans() of 200 bytes peaked at {peak}"
        with pytest.raises(ValueError, match="same length"):
            bytes.maketrans(b"a", b"bc")
        with pytest.raises(ValueError, match="256"):
            b"a".translate(b"x")

    @pytest.mark.timing
    def test_maketrans_reads_its_arguments_whatever_it_returns(self) -> None:
        short, long = letters(SMALL), letters(LARGE)

        ratio = growth(lambda: bytes.maketrans(short, short), lambda: bytes.maketrans(long, long))

        assert len(bytes.maketrans(long, long)) == 256
        assert_linear("maketrans()", ratio)

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_each_transform_scales_with_the_receiver(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        table = bytes.maketrans(b"a", b"b")

        ratios = {
            "upper": growth(small.upper, large.upper),
            "translate": growth(lambda: small.translate(table), lambda: large.translate(table)),
            "replace, no match": growth(
                lambda: small.replace(b"b", b"c"), lambda: large.replace(b"b", b"c")
            ),
            "replace, every byte": growth(
                lambda: small.replace(b"a", b"bb"), lambda: large.replace(b"a", b"bb")
            ),
            "removeprefix, present": growth(
                lambda: small.removeprefix(b"a"), lambda: large.removeprefix(b"a")
            ),
            "expandtabs": growth(small.expandtabs, large.expandtabs),
            "center(n + 10)": growth(
                lambda: small.center(SMALL + 10), lambda: large.center(LARGE + 10)
            ),
        }

        for name, ratio in ratios.items():
            assert_linear(name, ratio)

    @pytest.mark.timing
    def test_stripping_searches_chars_once_per_byte_it_strips(self) -> None:
        """The s·c term, with the stripped byte last in `chars` so each
        lookup scans all of it; every `chars` is built outside the timing."""
        data = letters(SMALL)
        short, long = b"x" * 99 + b"a", b"x" * 9_999 + b"a"

        assert data.strip(short) == data.strip(long) == b""
        ratio = growth(lambda: data.strip(short), lambda: data.strip(long), inner=3)

        assert LINEAR < ratio < QUADRATIC, f"100x the chars cost x{ratio:.2f}"

    @pytest.mark.timing
    def test_translate_reads_every_byte_of_delete(self) -> None:
        """The d term, at a receiver small enough for n not to hide it."""
        data = letters(1_000)
        few, many = b"x" * 10_000, b"x" * 1_000_000

        ratio = growth(
            lambda: data.translate(None, few), lambda: data.translate(None, many), inner=3
        )

        assert_linear("translate(None, delete)", ratio)

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_the_result_length_drives_what_a_transform_costs(self) -> None:
        """The w term: ten bytes in, and a result of 1,000,000 then
        10,000,000. Linear gives about x10, a result rebuilt by repeated
        concatenation about x100."""
        source = b"a" * 10
        tabs = b"\t" * 10
        filler, longer_filler = b"b" * 100_000, b"b" * 1_000_000

        ratios = {
            "center": growth(lambda: source.center(1_000_000), lambda: source.center(10_000_000)),
            "expandtabs": growth(
                lambda: tabs.expandtabs(100_000), lambda: tabs.expandtabs(1_000_000)
            ),
            "replace": growth(
                lambda: source.replace(b"a", filler), lambda: source.replace(b"a", longer_filler)
            ),
        }

        for name, ratio in ratios.items():
            assert 3 < ratio < 40, f"{name}: 10x the result cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_expandtabs_reads_the_input_it_does_not_write(self) -> None:
        small, large = b"\t" * SMALL, b"\t" * LARGE

        assert large.expandtabs(0) == b""
        assert_linear(
            "expandtabs(0)", growth(lambda: small.expandtabs(0), lambda: large.expandtabs(0))
        )


class TestSplittingAndJoining:
    """`split()` | O(n + m); `splitlines()` | O(n); `partition()` | O(n + m);
    `rsplit()`, `rpartition()` | O(n·m) worst case; `join()` | O(p + w)."""

    def test_the_documented_results(self) -> None:
        data = b"a,b,c"

        parts = data.split(b",")
        assert parts == [b"a", b"b", b"c"] and all(type(part) is bytes for part in parts)
        assert data.rsplit(b",", 1) == [b"a,b", b"c"]
        assert b"a\nb".splitlines() == [b"a", b"b"]
        assert data.partition(b",") == (b"a", b",", b"b,c")
        assert data.partition(b"z") == (data, b"", b"")
        assert data.rpartition(b"z") == (b"", b"", data)
        assert b",".join([b"a", bytearray(b"b"), memoryview(b"c")]) == data
        with pytest.raises(TypeError):
            b",".join(["a"])  # type: ignore[list-item]
        with pytest.raises(ValueError, match="empty separator"):
            data.split(b"")

    @pytest.mark.timing
    def test_split_scales_with_the_receiver(self) -> None:
        # Half the usual sizes: a million pieces alone would pass 64 MB.
        small = b"aaaaaaaaa," * (SMALL // 20)
        large = b"aaaaaaaaa," * (LARGE // 20)

        assert_linear("split()", growth(lambda: small.split(b","), lambda: large.split(b",")))

    def test_join_costs_something_per_part_whatever_it_holds(self) -> None:
        parts = [b""] * 200_000

        peak = peak_bytes(lambda: b"".join(parts))

        assert b"".join(parts) == b""
        assert peak > 2_000_000, f"200,000 empty parts peaked at {peak} bytes"

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_join_scales_with_the_parts_and_with_the_result(self) -> None:
        few_parts, many_parts = [b"ab"] * 2_000, [b"ab"] * 200_000
        few_empty, many_empty = [b""] * 2_000, [b""] * 200_000
        small_parts, big_parts = [bytes(10_000)] * 10, [bytes(1_000_000)] * 10

        by_count = growth(lambda: b",".join(few_parts), lambda: b",".join(many_parts))
        by_empty_count = growth(lambda: b"".join(few_empty), lambda: b"".join(many_empty))
        by_size = growth(lambda: b",".join(small_parts), lambda: b",".join(big_parts), inner=3)

        assert_linear("join() over 100x the parts", by_count)
        assert_linear("join() over 100x the empty parts", by_empty_count)
        assert_linear("join() over 100x the bytes in ten parts", by_size)


class TestPredicatesAndConversions:
    """The `is*()` predicates | O(n) | O(1), stopping at the first deciding
    byte; `decode()`, `hex()`, `bytes.fromhex()` | linear."""

    def test_the_documented_results(self) -> None:
        data = b"Hello"

        assert data.isalpha() and data.isalnum() and data.isascii() and data.istitle()
        assert not (data.isdigit() or data.islower() or data.isupper() or data.isspace())
        assert data.decode() == "Hello" and data.decode("ascii") == "Hello"
        assert data.hex() == "48656c6c6f"
        assert data.hex(":") == "48:65:6c:6c:6f"
        assert data.hex("_", 2) == "48_656c_6c6f"
        assert bytes.fromhex("48 65") == bytes.fromhex("4865") == b"He"
        assert bytes.fromhex("ff00") == b"\xff\x00"

    def test_fromhex_takes_bytes_from_3_14(self) -> None:
        argument: Any = b"ab"
        if sys.version_info >= (3, 14):
            assert bytes.fromhex(argument) == b"\xab"
            assert bytes.fromhex(memoryview(b"ab cd")) == b"\xab\xcd"  # type: ignore[arg-type]
        else:
            with pytest.raises(TypeError):
                bytes.fromhex(argument)

    @pytest.mark.timing
    def test_a_predicate_stops_at_the_first_deciding_byte(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        decided_early = b"1" + large

        full_scan = growth(small.isalpha, large.isalpha)
        early_exit = growth(decided_early.isalpha, large.isalpha)

        assert_linear("isalpha()", full_scan)
        assert early_exit > LINEAR, f"a leading digit left isalpha() at x1/{early_exit:.0f}"

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_conversions_scale(self) -> None:
        small, large = letters(SMALL), letters(LARGE)
        small_hex, large_hex = "ab" * (SMALL // 2), "ab" * (LARGE // 2)

        ratios = {
            "decode": growth(small.decode, large.decode),
            "hex": growth(small.hex, large.hex),
            "isascii": growth(small.isascii, large.isascii),
            "fromhex": growth(lambda: bytes.fromhex(small_hex), lambda: bytes.fromhex(large_hex)),
        }

        for name, ratio in ratios.items():
            assert_linear(name, ratio)


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
        target = 'assert len(fast) == 3 * len(b"header:payload\\n")'
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, target.replace("3 *", "4 *"), 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
