"""Tests for docs/builtins/str.md.

These cover the rows the page shares with the official CPython
time-complexity page - substring search, reverse search and the splits built
on it, copying, iteration and concatenation - and the rows and paragraphs
beyond it: results returned unchanged, output-size terms, padding, stripping,
comparisons, hashing, character width and building with `+=`. Identity and traced allocation settle copying
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
  `start:end` region costs the same in both and scales with the region;
  `find()` and `count()` trace under 1,000 bytes for half of the larger
  string. A 100,000- or
  10,000,000-character pattern against a 100-character string costs the
  same for `find()`, `count()` and `in`: there is no m term.
* Widening: in a 1,000,000-character string holding one CJK character, a
  10,000-character ASCII pattern makes `in`, `find()`, `index()`,
  `count()`, `rfind()`, `rindex()`, `replace()`, `split()`, `rsplit()`,
  `partition()` and `rpartition()` each trace at least 10,000 bytes, where
  the same pattern in an all-ASCII string traces under 5,000 (the
  `ValueError` of `index()` and `rindex()` takes about 1,400).
* `rfind()` over a 1,000-character `start:end` region costs the same in a
  100,000- and a 10,000,000-character string.
* The reverse search: against a 100,000-character string, a pattern that
  mismatches at its second character costs `rfind()`, `rsplit()` and
  `rpartition()` between x3 and x50 as it grows from 100 to 1,000
  characters, where `find()`, `split()` and `partition()` stay under x3.
  `rsplit()` with no separator and with a one-character one scales with
  the string, from 10,000 to 1,000,000 characters.
* A pattern matching all but its last character, and one matching all but
  its second-to-last, the shapes that make a naive forward scan cost m per
  position, cost `find()`, `count()`, `in` and `replace()` under x3 as they grow from
  100 to 1,000 characters against a fixed 100,000-character string (about
  x1.0 measured). This also covers the
  substring row of docs/implementations/cpython.md.
* Iterating 10,000,000 characters costs between x10 and x1,000 iterating
  100,000.
* Returned unchanged, by identity on a 1,000-character exact `str`:
  `s + ""`, `"" + s`, `s * 1`, `center`/`ljust`/`rjust`/`zfill` to a width
  within the string, `strip()`, `lstrip()`/`rstrip()` and `replace()`,
  `removeprefix()`/`removesuffix()` with nothing to remove, `expandtabs()`
  with no tab, and `join()` of one piece with and without a separator.
* Padding a 3-character string to 100,000 and 10,000,000 costs between x10
  and x1,000 for all four padding methods; `center(5)` of a 10,000,000- and
  a 100,000-character string costs under x3 apart.
* `lstrip(chars)` stripping 1,000 characters that sit only at the end of
  `chars` is timed with 1,000, 10,000 and 100,000 characters of `chars`:
  each tenfold step costs between 3x and 30x, excluding constant and
  quadratic growth in `chars`. Separately,
  with 10,000 characters of `chars` stripping 10,000 characters costs over
  x10 stripping 100, so the two multiply; stripping nothing costs over x100 with 1,000,000 characters of `chars`
  against 100, the O(c) of reading `chars`.
* At a fixed 10,000 characters, `replace()` and `translate()` producing
  1,000 characters per character, and `expandtabs()` of 10 tabs at tabsize
  1,000,000 against 1,000, cost over x10. `translate()` of 1,000,000
  characters to an empty result traces at least 1,000,000 bytes. `join()` of 1,000,000 empty
  pieces costs between x10 and x1,000 of 10,000; `join()` of an iterator
  of 100,000 pieces traces over 500,000 bytes, of a list under 64 KiB.
* On 10,000,000 characters, `==` of equal strings costs over 100x `==` of
  strings of different lengths, of different widths, or of one object with
  itself; `<` differing at the last character costs over 100x `<` differing
  at the first.
* The first `hash()` of a fresh 10,000,000-character string costs over 100x
  a repeat on the same object, and so does the first `hash()` of an equal
  string built separately.
* `isascii()`, and `startswith()`/`endswith()` with a 1,000-character
  argument, cost under x3 on 100x the string.
* `s[1:]` and `s[::2]` scale with the characters selected between x10 and
  x1,000, and `s[1:]` of 10,000,001 characters traces at least 10,000,000
  bytes; `s[:100_000:2]` against `s[::2]` is the same hundredfold step in
  characters selected; `str.maketrans()` scales with 1,000 against 100,000
  dict entries and with two strings of 1,000 against 100,000 characters;
  `format()` and `%` with one field scale with the template.
* `sys.getsizeof()` grows by 1, 1, 2, 2 and 4 bytes per character for "a",
  "é", "Ā", "世" and an emoji; "世" plus 1,000 ASCII characters is 2,000
  bytes larger than "世".
* `+=` of 10-character pieces with another reference to the partial string
  held at each step costs over x5 per 3x step over 2,000 / 6,000 / 18,000
  pieces (linear predicts x3, quadratic x9).

Not settled here:

* The linear worst case of the forward search follows from the two-way
  algorithm in Objects/stringlib/fastsearch.h, present on every supported
  branch; only the one adversarial shape above is timed.
* Only ASCII patterns in a two-byte-wide string are measured for widening;
  a one-byte pattern in a four-byte-wide string takes the same path in
  Objects/unicodeobject.c (any_find_slice, PyUnicode_Contains).
* The `encode()` row is scoped to codecs doing constant work per character;
  no codec is timed here.
* Whether `+=` with no other reference grows the string in place, and so
  runs in linear time, depends on the platform's `realloc`; the page says
  only that CPython can, and no test asserts it.
* Searches are asserted in the forward/reverse pattern shapes above, not in
  random text; `count()` with an empty substring and maxsplit arguments are
  not timed.
* Timings hold the characters fixed, all "a" apart from the probes named.
"""

from __future__ import annotations

import copy
import pathlib
import sys
import time
import tracemalloc
from collections.abc import Callable
from itertools import pairwise
from typing import Any

import pytest

from tests.page_examples import DOCS, failing_blocks, python_blocks, run_block

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
        reverse_across_strings = growth(
            lambda: small.rfind("b", 0, 1_000), lambda: large.rfind("b", 0, 1_000), inner=100
        )
        across_regions = growth(
            lambda: large.find("b", 0, SMALL), lambda: large.find("b", 0, LARGE)
        )
        region_peak = peak_bytes(lambda: large.find("bc", 0, LARGE // 2))
        count_region_peak = peak_bytes(lambda: large.count("bc", 0, LARGE // 2))
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
        assert reverse_across_strings < CONSTANT, (
            f"rfind() over a 1,000-character region cost x{reverse_across_strings:.2f}"
        )
        assert_linear("find() over a region", across_regions)
        assert region_peak < 1_000, f"searching a region traced {region_peak} bytes"
        assert count_region_peak < 1_000, f"counting in a region traced {count_region_peak} bytes"
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
            "replace": growth(
                lambda: haystack.replace(short_pattern, "x"),
                lambda: haystack.replace(long_pattern, "x"),
            ),
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
            "replace": lambda text: text.replace(pattern, "x"),
            "split": lambda text: text.split(pattern),
            "rsplit": lambda text: text.rsplit(pattern),
            "partition": lambda text: text.partition(pattern),
            "rpartition": lambda text: text.rpartition(pattern),
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


class TestUnchangedResultsAreTheString:
    """Operations with nothing to change return `s` itself for an exact `str`:
    `s + ""`, `s * 1`, padding to w <= n, stripping nothing, `replace()`,
    `removeprefix()` and `removesuffix()` with no match, `expandtabs()` with
    no tab, and `join()` of one piece."""

    def test_each_returns_the_same_object(self) -> None:
        s = "x" * 1_000
        unchanged = {
            "s + ''": s + "",
            "'' + s": "" + s,
            "s * 1": s * 1,
            "center": s.center(10),
            "ljust": s.ljust(1_000),
            "rjust": s.rjust(5),
            "zfill": s.zfill(5),
            "strip": s.strip(),
            "lstrip": s.lstrip("y"),
            "rstrip": s.rstrip("y"),
            "replace": s.replace("y", "z"),
            "removeprefix": s.removeprefix("y"),
            "removesuffix": s.removesuffix("y"),
            "expandtabs": s.expandtabs(),
            "join": "".join([s]),
            "join with a separator": "-".join([s]),
        }

        for name, result in unchanged.items():
            assert result is s, name

    def test_repetition_of_zero_or_less_is_empty(self) -> None:
        assert "abc" * 0 == "" and "abc" * -3 == ""

    def test_a_padded_or_stripped_result_is_new(self) -> None:
        s = " abc "
        assert s.center(10) is not s and len(s.center(10)) == 10
        assert s.strip() == "abc"


class TestPaddingCostsTheWidth:
    """`center()`, `ljust()`, `rjust()`, `zfill()` | O(w): a 3-character
    string padded to 100,000 and to 10,000,000 must grow between x10 and
    x1,000, and padding a 10,000,000-character string to w = 5 must cost
    under x3 of padding a 100,000-character one."""

    @pytest.mark.timing
    def test_the_cost_follows_the_width(self) -> None:
        text = "abc"
        for name in ("center", "ljust", "rjust", "zfill"):
            method = getattr(text, name)
            assert_linear(name, growth(lambda m=method: m(SMALL), lambda m=method: m(LARGE)))

    @pytest.mark.timing
    def test_a_width_within_the_string_costs_nothing(self) -> None:
        small, large = "a" * SMALL, "a" * LARGE
        ratio = growth(lambda: small.center(5), lambda: large.center(5), inner=100)
        assert ratio < CONSTANT, f"center(5) on a 100x longer string cost x{ratio:.2f}"


class TestStripLooksUpEachStrippedCharacter:
    """`strip(chars)` | O(n + (d+1)·c): each stripped character is looked up
    in `chars`, and `chars` is read once even when nothing is stripped."""

    @pytest.mark.timing
    def test_the_cost_grows_with_chars_times_stripped(self) -> None:
        """Hold 1,000 stripped characters fixed while `chars` grows 100x.

        Each tenfold step predicts 10x for a linear scan, 1x for a constant
        lookup and 100x for quadratic work. The shortest scan has 1,000
        characters so call overhead and short-scan costs do not dominate.
        """
        text = "a" * 1_000 + "x"
        durations = []
        for size in (1_000, 10_000, 100_000):
            chars = "b" * (size - 1) + "a"
            assert text.lstrip(chars) == "x"
            durations.append(best_ns(lambda chars=chars: text.lstrip(chars), inner=10))
        ratios = [after / before for before, after in pairwise(durations)]

        assert all(3 < ratio < 30 for ratio in ratios), f"lstrip: {durations} ns, x{ratios}"

    @pytest.mark.timing
    def test_the_cost_grows_with_stripped_times_chars(self) -> None:
        """With 10,000 characters of `chars`, stripping 10,000 characters must
        cost over x10 stripping 100: O(c + d) would stay near x1."""
        chars = "b" * 9_999 + "a"
        few, many = "a" * 100 + "x", "a" * 10_000 + "x"

        ratio = growth(lambda: few.lstrip(chars), lambda: many.lstrip(chars), inner=3)

        assert ratio > LINEAR, f"100x more stripped characters cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_chars_is_read_even_when_nothing_is_stripped(self) -> None:
        text = "x" + "a" * 10
        short_chars, long_chars = "b" * 99 + "a", "b" * 999_999 + "a"

        ratio = growth(lambda: text.lstrip(short_chars), lambda: text.lstrip(long_chars), inner=3)

        assert ratio > LINEAR * 10, f"10,000x longer chars cost x{ratio:.1f}"


class TestOutputSizeTerms:
    """`replace()`, `translate()` and `expandtabs()` are O(n + r): at a fixed
    n, a 1,000x longer result must cost over x10. `sep.join()` is O(r + p):
    1,000,000 empty pieces cost between x10 and x1,000 of 10,000, and an
    iterator of 100,000 pieces is collected into a list first (traced peak
    over 500,000 bytes, where a list of them traces under 64 KiB)."""

    @pytest.mark.timing
    def test_a_longer_result_costs_more_at_the_same_n(self) -> None:
        text, tabs = "a" * 10_000, "\t" * 10
        ratios = {
            "replace": growth(
                lambda: text.replace("a", "x"), lambda: text.replace("a", "x" * 1_000)
            ),
            "translate": growth(
                lambda: text.translate({97: "x"}), lambda: text.translate({97: "x" * 1_000})
            ),
            "expandtabs": growth(
                lambda: tabs.expandtabs(1_000), lambda: tabs.expandtabs(1_000_000)
            ),
        }

        for name, ratio in ratios.items():
            assert ratio > LINEAR, f"{name}: a 1,000x longer result cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_join_pays_for_every_piece(self) -> None:
        few, many = [""] * 10_000, [""] * 1_000_000

        assert_linear("join of empty pieces", growth(lambda: "".join(few), lambda: "".join(many)))

    def test_translate_reserves_the_input_length(self) -> None:
        text = "a" * 1_000_000

        assert peak_bytes(lambda: text.translate({97: None})) >= 1_000_000

    def test_an_iterator_is_collected_first(self) -> None:
        pieces = [""] * 100_000

        from_list = peak_bytes(lambda: "".join(pieces))
        from_iterator = peak_bytes(lambda: "".join(iter(pieces)))

        assert from_list < 64 * 1024, f"a list of pieces traced {from_list} bytes"
        assert from_iterator > 500_000, f"an iterator of pieces traced {from_iterator} bytes"


class TestComparisons:
    """`s == t` is O(n), O(1) when the lengths or widths differ or both are
    the same object; `s < t` stops at the first unequal character. All on
    10,000,000 characters: the O(n) case must cost over 100x the O(1) one."""

    @pytest.mark.timing
    def test_equality_reads_the_characters_only_when_it_must(self) -> None:
        text, twin = "a" * LARGE, "a" * LARGE
        shorter = "a" * (LARGE - 1)
        wider = "世" + "a" * (LARGE - 1)

        full = best_ns(lambda: text == twin)
        shortcuts = {
            "different lengths": best_ns(lambda: text == shorter, inner=100),
            "different widths": best_ns(lambda: text == wider, inner=100),
            "the same object": best_ns(lambda: text == text, inner=100),
        }

        for name, ns in shortcuts.items():
            assert full > ns * 100, f"{name}: {ns:.0f}ns against {full:.0f}ns for a full compare"

    @pytest.mark.timing
    def test_ordering_stops_at_the_first_difference(self) -> None:
        text = "a" * LARGE
        first, last = "b" + "a" * (LARGE - 1), "a" * (LARGE - 1) + "b"

        late = best_ns(lambda: text < last)
        early = best_ns(lambda: text < first, inner=100)

        assert late > early * 100, f"{early:.0f}ns at the first character, {late:.0f}ns at the last"


class TestHashIsKeptInTheString:
    """`hash(s)` | O(n) first call; O(1) after: a fresh 10,000,000-character
    string's first hash must cost over 100x a repeat on the same object,
    and an equal string built separately pays its own first hash."""

    @pytest.mark.timing
    def test_a_second_hash_reads_the_kept_value(self) -> None:
        fresh = iter(["a" * LARGE for _ in range(7)])
        first = best_ns(lambda: hash(next(fresh)))
        text = "a" * LARGE
        hash(text)
        kept = best_ns(lambda: hash(text), inner=100)

        assert first > kept * 100, f"first {first:.0f}ns, kept {kept:.0f}ns"

    @pytest.mark.timing
    def test_an_equal_string_pays_its_own_first_hash(self) -> None:
        text = "a" * LARGE
        hash(text)
        twins = iter(["a" * LARGE for _ in range(7)])
        twin_first = best_ns(lambda: hash(next(twins)))
        kept = best_ns(lambda: hash(text), inner=100)

        assert twin_first > kept * 100, f"twin {twin_first:.0f}ns, kept {kept:.0f}ns"


class TestConstantRows:
    """`isascii()` and `startswith()` at a fixed prefix do not read the rest of
    the string: 100x the string costs under x3."""

    @pytest.mark.timing
    def test_they_ignore_the_strings_length(self) -> None:
        small, large, prefix = "a" * SMALL, "a" * LARGE, "a" * 1_000

        ratios = {
            "isascii": growth(small.isascii, large.isascii, inner=1_000),
            "startswith": growth(
                lambda: small.startswith(prefix), lambda: large.startswith(prefix), inner=100
            ),
            "endswith": growth(
                lambda: small.endswith(prefix), lambda: large.endswith(prefix), inner=100
            ),
        }

        for name, ratio in ratios.items():
            assert ratio < CONSTANT, f"{name}: a 100x longer string cost x{ratio:.2f}"


class TestLinearRows:
    """Rows the page prices by a length, timed over a hundredfold step:
    `s[i:j]` and a stepped slice in the characters selected (traced at about
    one byte per character), `str.maketrans()` in its mappings, and
    `format()` and `%` in the template length with one field."""

    @pytest.mark.timing
    def test_slices_scale_with_what_they_select(self) -> None:
        text = "a" * (LARGE + 1)

        assert_linear("s[i:j]", growth(lambda: text[1 : SMALL + 1], lambda: text[1:]))
        assert_linear("s[i:j:2]", growth(lambda: text[:SMALL:2], lambda: text[::2]))
        assert peak_bytes(lambda: text[1:]) >= LARGE

    @pytest.mark.timing
    def test_maketrans_scales_with_its_mappings(self) -> None:
        few = dict.fromkeys(range(1_000))
        many = dict.fromkeys(range(100_000))

        assert_linear("maketrans", growth(lambda: str.maketrans(few), lambda: str.maketrans(many)))
        short_x, short_y = "a" * 1_000, "b" * 1_000
        long_x, long_y = "a" * 100_000, "b" * 100_000
        assert_linear(
            "maketrans(x, y)",
            growth(lambda: str.maketrans(short_x, short_y), lambda: str.maketrans(long_x, long_y)),
        )

    @pytest.mark.timing
    def test_formatting_scales_with_the_template(self) -> None:
        short_template, long_template = "a" * SMALL + "{}", "a" * LARGE + "{}"
        short_percent, long_percent = "a" * SMALL + "%s", "a" * LARGE + "%s"

        assert_linear(
            "format", growth(lambda: short_template.format(1), lambda: long_template.format(1))
        )
        assert_linear("%", growth(lambda: short_percent % 1, lambda: long_percent % 1))


class TestCharacterWidth:
    """Each string is stored at 1, 2 or 4 bytes per character, chosen by its
    widest character: `sys.getsizeof()` grows by exactly that much per added
    character, and one CJK character makes 1,000 ASCII characters take 2,000
    bytes."""

    def test_the_widest_character_sets_the_width(self) -> None:
        def bytes_per_char(ch: str) -> int:
            return (sys.getsizeof(ch * 2_000) - sys.getsizeof(ch * 1_000)) // 1_000

        assert [bytes_per_char(ch) for ch in ("a", "é", "\u0100", "世", "😀")] == [1, 1, 2, 2, 4]
        assert sys.getsizeof("世" + "a" * 1_000) - sys.getsizeof("世") == 2_000


class TestBuildingWithPlusEquals:
    """`+=` in a loop is O(r²) at worst: with another reference to the partial
    string held at every step, 2,000 / 6,000 / 18,000 ten-character pieces
    must cost over x5 per 3x step, where a linear build costs x3 and a
    quadratic one x9."""

    @pytest.mark.timing
    def test_another_reference_makes_every_step_copy(self) -> None:
        def build(pieces: int) -> str:
            result = ""
            for _ in range(pieces):
                alias = result  # noqa: F841 - the reference is the subject
                result += "0123456789"
            return result

        times = [best_ns(lambda n=n: build(n), repeats=3) for n in (2_000, 6_000, 18_000)]

        for before, after in pairwise(times):
            assert after > before * 5, f"a 3x longer build cost x{after / before:.1f}"


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


class TestDocumentedExamples:
    """Each block runs in its own interpreter and defines every name it uses."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(DOCS / "builtins/str.md")) == 4

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(DOCS / "builtins/str.md", tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_failing_assertion(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(DOCS / "builtins/str.md") if 's.find("b")' in s)
        mutated = source.replace('assert s.find("b") == 1_000_000', 'assert s.find("b") == 0', 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0
