"""Tests for docs/builtins/str.md.

These cover the rows the page shares with the official CPython
time-complexity page: substring search, reverse search and the splits built
on it, copying, and iteration. Identity and traced allocation settle copying
and widening with no tolerance; the growth classes are settled by timing a
hundredfold step in one dimension, where a row claiming O(1) has to come in
under x3 and a linear one between x10 and x1,000. The rest of the table's
growth classes are timed in tests/test_builtin_complexity.py
(TestStrComplexity).

Measurement scope:

* `s[:]`, `str(s)`, `copy.copy(s)` and `copy.deepcopy(s)` return `s` itself
  for an exact `str`, and a new object for an instance of a `str` subclass.
* `find()`, `count()` and `in` for an absent pattern scale with the string
  from 100,000 to 10,000,000 characters. `find()` over a 1,000-character
  `start:end` region costs the same in both, scales with the region, and
  traces under 1,000 bytes for half of the larger string. A 100,000- or
  10,000,000-character pattern against a 100-character string costs the
  same for `find()`, `count()` and `in`: there is no m term.
* Widening: in a 1,000,000-character string holding one CJK character, a
  10,000-character ASCII pattern makes `in`, `find()`, `index()`,
  `count()`, `rfind()` and `rindex()` each trace at least 10,000 bytes,
  where the same pattern in an all-ASCII string traces under 5,000 (the
  `ValueError` of `index()` and `rindex()` takes about 1,400).
* The reverse search: against a 100,000-character string, a pattern that
  mismatches at its second character costs `rfind()`, `rsplit()` and
  `rpartition()` between x3 and x50 as it grows from 100 to 1,000
  characters, where `find()`, `split()` and `partition()` stay under x3.
  `rsplit()` with no separator and with a one-character one scales with
  the string, from 10,000 to 1,000,000 characters.
* A pattern matching all but its last character, and one matching all but
  its second-to-last, the shapes that make a naive forward scan cost m per
  position, cost `find()`, `count()` and `in` under x3 as they grow from
  100 to 1,000 characters against a fixed 100,000-character string (about
  x1.0 measured). This also covers the
  substring row of docs/implementations/cpython.md.
* Iterating 10,000,000 characters costs between x10 and x1,000 iterating
  100,000.

Not settled here:

* The linear worst case of the forward search follows from the two-way
  algorithm in Objects/stringlib/fastsearch.h, present on every supported
  branch; only the one adversarial shape above is timed.
* Only ASCII patterns in a two-byte-wide string are measured for widening;
  a one-byte pattern in a four-byte-wide string takes the same path in
  Objects/unicodeobject.c (any_find_slice, PyUnicode_Contains).
* The `encode()` row is scoped to codecs doing constant work per character;
  no codec is timed here.
* Timings hold the characters fixed, all "a" apart from the probes named.
"""

from __future__ import annotations

import copy
import pathlib
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "str.md"

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


def test_the_page_exists() -> None:
    assert PAGE.is_file()


class TestCopyingReturnsTheString:
    """`s[:]`, `str(s)`, `copy.copy(s)` | O(1) | O(1): `s` itself for an exact `str`."""

    def test_an_exact_str_is_returned_itself(self) -> None:
        text = "x" * LARGE

        assert text[:] is text
        assert str(text) is text
        assert copy.copy(text) is text
        assert copy.deepcopy(text) is text

    def test_a_subclass_instance_is_copied(self) -> None:
        class Text(str):
            pass

        text = Text("abc")

        assert text[:] is not text and text[:] == text
        assert str(text) is not text and type(str(text)) is str
        assert copy.copy(text) is not text and copy.copy(text) == text
        assert copy.deepcopy(text) is not text and copy.deepcopy(text) == text


class TestForwardSearchIsLinearInTheRegion:
    """`in`, `find(sub, start, end)`, `index()`, `count()` | O(n): n is the
    characters searched, and a substring longer than them returns at once."""

    @pytest.mark.timing
    def test_a_scan_scales_with_the_string(self) -> None:
        small, large = "a" * SMALL, "a" * LARGE

        ratios = {
            "find": growth(lambda: small.find("bc"), lambda: large.find("bc")),
            "count": growth(lambda: small.count("bc"), lambda: large.count("bc")),
            "in": growth(lambda: "bc" in small, lambda: "bc" in large),
        }

        for name, ratio in ratios.items():
            assert_linear(name, ratio)

    @pytest.mark.timing
    def test_n_is_the_region_searched_and_a_longer_pattern_reads_nothing(self) -> None:
        small, large, tiny = "a" * SMALL, "a" * LARGE, "a" * 100
        short_pattern, long_pattern = "a" * SMALL, "a" * LARGE

        across_strings = growth(
            lambda: small.find("b", 0, 1_000), lambda: large.find("b", 0, 1_000), inner=100
        )
        across_regions = growth(
            lambda: large.find("b", 0, SMALL), lambda: large.find("b", 0, LARGE)
        )
        region_peak = peak_bytes(lambda: large.find("bc", 0, LARGE // 2))
        across_patterns = {
            "find": growth(
                lambda: tiny.find(short_pattern), lambda: tiny.find(long_pattern), inner=100
            ),
            "count": growth(
                lambda: tiny.count(short_pattern), lambda: tiny.count(long_pattern), inner=100
            ),
            "in": growth(lambda: short_pattern in tiny, lambda: long_pattern in tiny, inner=100),
        }

        assert across_strings < CONSTANT, f"a 1,000-character region cost x{across_strings:.2f}"
        assert_linear("find() over a region", across_regions)
        assert region_peak < 1_000, f"searching a region traced {region_peak} bytes"
        for name, ratio in across_patterns.items():
            assert ratio < CONSTANT, f"{name}: a 100x longer pattern cost x{ratio:.2f}"

    @pytest.mark.timing
    @pytest.mark.parametrize("tail", ["b", "ba"])
    def test_a_pattern_mismatching_at_its_end_stays_linear(self, tail: str) -> None:
        """The shapes that turn a naive forward scan into n·m: every position
        matches all but the pattern's last character, or all but its
        second-to-last, which a scan checking the last character first does
        not reject at once. Against a fixed 100,000-character string, growing
        the pattern from 100 to 1,000 characters leaves `find()`, `count()`
        and `in` under x3, where m comparisons per position would cost x10."""
        haystack = "a" * SMALL
        short_pattern = "a" * (100 - len(tail)) + tail
        long_pattern = "a" * (1_000 - len(tail)) + tail

        ratios = {
            "find": growth(
                lambda: haystack.find(short_pattern), lambda: haystack.find(long_pattern)
            ),
            "count": growth(
                lambda: haystack.count(short_pattern), lambda: haystack.count(long_pattern)
            ),
            "in": growth(lambda: short_pattern in haystack, lambda: long_pattern in haystack),
        }

        for name, ratio in ratios.items():
            assert ratio < CONSTANT, f"{name}: a 10x longer pattern cost x{ratio:.2f}"


class TestANarrowerPatternIsWidened:
    """The O(m) in the search rows' space column: a substring stored narrower
    than the string is copied at the string's width before the search."""

    def test_an_ascii_pattern_in_cjk_text_is_copied(self) -> None:
        wide = "世" + "a" * 1_000_000
        narrow = "a" * 1_000_001
        pattern = "a" * 9_999 + "b"
        searches: dict[str, Callable[[str], object]] = {
            "in": lambda text: pattern in text,
            "find": lambda text: text.find(pattern),
            "index": lambda text: pytest.raises(ValueError, text.index, pattern),
            "count": lambda text: text.count(pattern),
            "rfind": lambda text: text.rfind(pattern),
            "rindex": lambda text: pytest.raises(ValueError, text.rindex, pattern),
        }

        for name, search in searches.items():
            search(wide)  # warm the call path outside the trace
            widened = peak_bytes(lambda search=search: search(wide))
            same_width = peak_bytes(lambda search=search: search(narrow))

            assert widened >= 10_000, f"{name} in CJK text traced {widened}"
            assert same_width < 5_000, f"{name} in ASCII text traced {same_width}"


class TestReverseSearchPaysForThePattern:
    """`rfind()`, `rindex()`, `rsplit(sep)`, `rpartition(sep)` | O(n·m) worst."""

    @pytest.mark.timing
    def test_only_the_reverse_search_grows_with_the_pattern(self) -> None:
        """A pattern mismatching at its second character is compared almost
        in full at every position by the reverse search, and rejected at once
        by the forward one."""
        haystack = "a" * SMALL
        short_pattern, long_pattern = "ab" + "a" * 98, "ab" + "a" * 998

        def ratio(operation: Callable[[str], object]) -> float:
            return growth(
                lambda: operation(short_pattern), lambda: operation(long_pattern), inner=1
            )

        reverse = {
            "rfind": ratio(haystack.rfind),
            "rsplit": ratio(haystack.rsplit),
            "rpartition": ratio(haystack.rpartition),
        }
        forward = {
            "find": ratio(haystack.find),
            "split": ratio(haystack.split),
            "partition": ratio(haystack.partition),
        }

        for name, value in reverse.items():
            assert CONSTANT < value < 50, f"{name}: a 10x longer pattern cost x{value:.1f}"
        for name, value in forward.items():
            assert value < CONSTANT, f"{name}: a 10x longer pattern cost x{value:.2f}"

    @pytest.mark.timing
    def test_rsplit_without_a_long_separator_scans(self) -> None:
        # 10,000 and 1,000,000 characters keep the larger result to 500,000 parts.
        small, large = "a " * 5_000, "a " * 500_000

        assert_linear("rsplit()", growth(small.rsplit, large.rsplit, inner=1))
        assert_linear("rsplit(' ')", growth(lambda: small.rsplit(" "), lambda: large.rsplit(" ")))


class TestIteration:
    """`for c in s` | O(n) | O(1)."""

    def test_each_step_is_one_character(self) -> None:
        assert list("a世b") == ["a", "世", "b"]

    @pytest.mark.timing
    def test_iteration_scales_with_the_string(self) -> None:
        small, large = "a" * SMALL, "a" * LARGE

        def drain(text: str) -> None:
            for _ in text:
                pass

        assert_linear("for c in s", growth(lambda: drain(small), lambda: drain(large)))
