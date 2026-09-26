"""Tests for docs/stdlib/difflib.md.

The page prices everything through `SequenceMatcher`: `b` is indexed once, and
the match then searches ranges of `a`, walking the index entries of each element
it meets. The cost of a match is settled by counting that work directly rather
than timing it: a `SequenceMatcher` subclass wraps each index list so that every
entry the search walks is counted, and adds the length of the range of `a` each
`find_longest_match()` call scans. The counts are exact and repeatable, so the
shape tests assert growth ratios with no tolerance for noise. Caching, laziness
and space are settled by identity, call counters and traced allocation.

Measurement scope:

* Construction indexes `b` and only stores `a`: a `tracemalloc` peak for a
  100,000-element distinct `b` exceeds 1 MB and is over 100x the peak for the
  same list as `a`. `isjunk` is recorded to run once per distinct element of a
  300-element `b` of four distinct characters, never on `a`, and its junk is
  absent from `b2j`. `set_seq1()` keeps the same `b2j` object and drops the
  cached blocks; `set_seq2()` with the object already set keeps `b2j`, and a new
  one replaces it.
* `get_matching_blocks()` and `get_opcodes()` return the same list object on a
  second call, and `ratio()` after the blocks are cached makes no
  `find_longest_match()` call. `get_grouped_opcodes()` is observed to trim a
  leading and a trailing `equal` entry of the cached `get_opcodes()` list in
  place.
* Match work, counted as above: identical distinct sequences of 2,000 and
  20,000 elements cost exactly 2A in one call, and sequences sharing nothing
  exactly A. With distinct elements and an edit every 1,000, 100 and 10
  positions of a 5,000-element sequence, each 10x in blocks costs more than 5x
  in work, and every count is within 2(B + A·k), k counting the sentinel. With
  an edit every fifty positions, 4x the length (2,000 to 8,000) costs more than
  10x; the same
  number of edits at random positions (seeded) costs under a quarter of the
  evenly spaced count at 8,000.
* The cubic shape uses the default `autojunk=True`: `a` is A zeros and `b`
  places a zero every 100 elements among 99 distinct fillers, so zero is never
  popular. Each doubling from 1,000 to 4,000 costs more than 6x in work, where a
  quadratic predicts 4x and a cubic 8x (measured x7.3 and x7.6). The same holds
  with `autojunk=False` on `"a" * A` against `"ba" * (A / 2)`, 50 to 200 (x7.8,
  x7.9). A timing test on the first shape asserts 4x the length costs more than
  30x the time, between the quadratic 16x and the cubic 64x.
* `find_longest_match()` walks one index entry per occurrence: a single-element
  `a` against 100 and 100,000 copies of it (`autojunk=False`) peaks more than
  100x higher at the larger size, and a match over distinct elements costs
  exactly A in the work count.
* The popularity threshold is asserted at its boundary for B = 200 (3 copies
  kept, 4 popular) and B = 1,000 (11 kept, 12 popular), and never below 200.
  `"x" + text` against `"y" + text` over 1,000 random lowercase letters scores
  0.0 with the default and more than 0.99 with `autojunk=False`.
* `quick_ratio()` and `real_quick_ratio()` are asserted to be upper bounds on
  `ratio()` and on each other, and `real_quick_ratio()` to equal
  2·min(A, B)/(A + B).
* `unified_diff()`, `context_diff()` and `ndiff()` are observed to make every
  line-level `find_longest_match()` call before their first line is returned,
  and none after. Streaming `unified_diff()` of a 100,000-line `a` against an
  empty `b` peaks above 400 KB (the deleted range is sliced); `ndiff()` on the
  same input peaks under 50 KB, and both exceed 4 MB with the sizes swapped.
* `ndiff()` line-pair comparisons are counted as `set_seq1()` calls, which
  also include one per matcher built. On 3.14+ a replaced block of r mutually similar
  lines takes at most 22r pairs, and 4x r costs under 6x. On 3.10–3.13 the same
  shape costs more than 6x per doubling of r from 25 to 100 (cubic), and a
  block of 50 dissimilar lines takes at least r² pairs. Streaming the delta of
  a block of similar lines, 4x r (10 to 40) raises the traced peak by under
  1.5x on 3.14+ (2,000-character lines, where c dominates the O(B) line index)
  and by more than 2x on 3.10–3.13 (200-character lines).
* `HtmlDiff.make_table()` and `make_file()` are observed to call `ndiff()`
  once. `diff_bytes()` is observed to exhaust both input iterators before its
  first line and to round-trip an undecodable byte. `restore()` is observed to
  take one delta line to yield its first line.
* `get_close_matches()` is observed to index the word once, to run no full
  match over 1,000 possibilities the quick ratios reject, one per survivor when
  they pass, and to reject `n <= 0` and a cutoff outside [0, 1].
* Python 3.14+ raises `TypeError` for a string `a` or `b` in `unified_diff()`
  and `context_diff()`; 3.10–3.13 accept it. Both sides are guarded on
  `sys.version_info`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* Hashing and comparing one element are priced O(1). For lines that holds only
  in the unit the page counts: line length is varied only in the `ndiff()`
  space test.
* The O(A·B·min(A, B)) worst case is read from Lib/difflib.py:
  `get_matching_blocks()` makes at most 2·min(A, B) + 1 searches, each walking
  at most A positions and B index entries per position. The tests show two shapes grow
  cubically, not that none grows faster.
* That blocks of varied length "cost far less" than evenly spaced ones rests on
  one seeded random placement per size, at one edit density.
* The per-pair cost of `ndiff()` (a character-level match) is not varied in the
  line length c; neither are `IS_LINE_JUNK()`'s O(c) and the O(s) of
  `HtmlDiff` output, `wrapcolumn` and `context`, which are read from the source.
* `get_close_matches()`'s worst case is composed from the `SequenceMatcher`
  rows, not measured; its final `heapq.nlargest()` over the survivors is not
  varied.
"""

from __future__ import annotations

import difflib
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Hashable, Iterator, Sequence
from difflib import (
    IS_CHARACTER_JUNK,
    IS_LINE_JUNK,
    Differ,
    HtmlDiff,
    Match,
    SequenceMatcher,
    context_diff,
    diff_bytes,
    get_close_matches,
    ndiff,
    restore,
    unified_diff,
)
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "difflib.md"
EXPECTED_BLOCKS = 11


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = float(time.perf_counter_ns() - start)
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def internal(matcher: SequenceMatcher[Any]) -> Any:
    """The matcher, for its documented attributes the type stubs omit."""
    return matcher


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountedEntries(list[int]):
    """An index list that counts every entry a search walks."""

    walked = 0

    def __iter__(self) -> Iterator[int]:
        for position in list.__iter__(self):
            CountedEntries.walked += 1
            yield position


class CountingMatcher(SequenceMatcher[Any]):
    """A SequenceMatcher whose match work can be read off exactly.

    Work is the positions of `a` each `find_longest_match()` call scans plus the
    index entries it walks: the two loops that make up the match.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.calls = 0
        super().__init__(*args, **kwargs)

    def set_seq2(self, b: Sequence[Any]) -> None:
        super().set_seq2(b)
        self.b2j = {element: CountedEntries(positions) for element, positions in self.b2j.items()}

    def find_longest_match(
        self, alo: int = 0, ahi: int | None = None, blo: int = 0, bhi: int | None = None
    ) -> Match:
        self.calls += 1
        CountedEntries.walked += (len(internal(self).a) if ahi is None else ahi) - alo
        return super().find_longest_match(alo, ahi, blo, bhi)


def match_work(a: Sequence[Hashable], b: Sequence[Hashable], autojunk: bool = True) -> int:
    """Positions scanned plus index entries walked by one full match."""
    matcher = CountingMatcher(None, a, b, autojunk=autojunk)
    CountedEntries.walked = 0
    matcher.get_matching_blocks()
    return CountedEntries.walked


def blocks_of(a: Sequence[Hashable], b: Sequence[Hashable]) -> int:
    """k: matching blocks, the closing sentinel included."""
    return len(SequenceMatcher(None, a, b).get_matching_blocks())


def evenly_edited(size: int, every: int) -> tuple[list[int], list[int]]:
    """Distinct elements with one replaced every `every` positions."""
    a = list(range(size))
    b = list(a)
    for index in range(every // 2, size, every):
        b[index] = -index - 1
    return a, b


def randomly_edited(size: int, edits: int, seed: int) -> tuple[list[int], list[int]]:
    """Distinct elements with `edits` replaced at seeded random positions."""
    a = list(range(size))
    b = list(a)
    for index in random.Random(seed).sample(range(size), edits):
        b[index] = -index - 1
    return a, b


def sparse_zeros(size: int) -> tuple[list[int], list[int]]:
    """A zeros against a zero every 100 elements: zero is never popular."""
    return [0] * size, ([0, *range(1, 100)]) * (size // 100)


class TestConstructionIndexesB:
    """`SequenceMatcher(isjunk, a, b)` | O(B) | O(B): `b` is indexed, `a` stored,
    and `isjunk` runs once per distinct element of `b`."""

    def test_the_peak_follows_b_not_a(self) -> None:
        large = list(range(100_000))
        small = list(range(10))

        indexing_b = peak_bytes(lambda: SequenceMatcher(None, small, large))
        storing_a = peak_bytes(lambda: SequenceMatcher(None, large, small))

        assert indexing_b > 1_000_000, f"indexing 100,000 elements peaked at {indexing_b}"
        assert indexing_b > storing_a * 100, (indexing_b, storing_a)

    def test_isjunk_runs_once_per_distinct_element_of_b(self) -> None:
        calls: list[str] = []

        def isjunk(element: str) -> bool:
            calls.append(element)
            return element == " "

        matcher = SequenceMatcher(isjunk, "unrelated", "abc " * 75)

        assert sorted(calls) == [" ", "a", "b", "c"], f"{len(calls)} calls for 300 positions"
        assert internal(matcher).bjunk == {" "}
        assert " " not in internal(matcher).b2j

    def test_isjunk_never_sees_a(self) -> None:
        calls: list[str] = []

        def isjunk(element: str) -> bool:
            calls.append(element)
            return False

        SequenceMatcher(isjunk, "xyz", "ab").ratio()

        assert set(calls) == {"a", "b"}


class TestSettingSequences:
    """`set_seq1(a)` | O(1) keeps the index; `set_seq2(b)` | O(B) rebuilds it
    unless `b` is the object already set; `set_seqs` does both."""

    def test_set_seq1_keeps_the_index_and_drops_the_cache(self) -> None:
        matcher = SequenceMatcher(None, "abcd", "bcde")
        index = internal(matcher).b2j
        before = matcher.get_matching_blocks()

        matcher.set_seq1("bcde")

        assert internal(matcher).b2j is index
        assert matcher.get_matching_blocks() is not before
        assert matcher.ratio() == 1.0

    def test_set_seq2_with_the_same_object_is_a_no_op(self) -> None:
        b = list(range(1_000))
        matcher = SequenceMatcher(None, [], b)
        index = internal(matcher).b2j

        matcher.set_seq2(b)

        assert internal(matcher).b2j is index

    def test_set_seq2_with_a_new_object_rebuilds(self) -> None:
        matcher = SequenceMatcher(None, "abcd", "abcd")
        index = internal(matcher).b2j

        matcher.set_seq2("wxyz")

        assert internal(matcher).b2j is not index
        assert set(internal(matcher).b2j) == set("wxyz")

    def test_set_seqs_sets_both(self) -> None:
        matcher = SequenceMatcher()

        matcher.set_seqs("abcd", "bcde")

        assert (internal(matcher).a, internal(matcher).b) == ("abcd", "bcde")
        assert matcher.ratio() == 0.75


class TestResultsAreCached:
    """`get_matching_blocks()` and `get_opcodes()` are cached; `ratio()` is O(k)
    once the blocks are."""

    def test_blocks_and_opcodes_are_the_same_objects_next_time(self) -> None:
        matcher = SequenceMatcher(None, "abxcd", "abcd")

        assert matcher.get_matching_blocks() is matcher.get_matching_blocks()
        assert matcher.get_opcodes() is matcher.get_opcodes()

    def test_ratio_reuses_the_blocks(self) -> None:
        matcher = CountingMatcher(None, "qabxcd", "abycdf")
        matcher.get_matching_blocks()
        searches = matcher.calls

        ratio = matcher.ratio()

        assert matcher.calls == searches, "ratio() searched again"
        assert ratio == 2 * 4 / 12

    def test_opcodes_describe_the_edit(self) -> None:
        matcher = SequenceMatcher(None, "qabxcd", "abycdf")

        assert matcher.get_opcodes() == [
            ("delete", 0, 1, 0, 0),
            ("equal", 1, 3, 0, 2),
            ("replace", 3, 4, 2, 3),
            ("equal", 4, 6, 3, 5),
            ("insert", 6, 6, 5, 6),
        ]

    def test_grouped_opcodes_trim_the_cached_list_in_place(self) -> None:
        a = list("abcdefghijklmnopqrstuvwxyz")
        b = list(a)
        b[13] = "X"
        matcher = SequenceMatcher(None, a, b)
        opcodes = matcher.get_opcodes()
        assert opcodes[0] == ("equal", 0, 13, 0, 13)

        groups = matcher.get_grouped_opcodes(1)
        assert isinstance(groups, Iterator)
        assert list(groups) == [
            [("equal", 12, 13, 12, 13), ("replace", 13, 14, 13, 14), ("equal", 14, 15, 14, 15)]
        ]

        assert matcher.get_opcodes() is opcodes
        assert opcodes[0] == ("equal", 12, 13, 12, 13)
        assert opcodes[-1] == ("equal", 14, 15, 14, 15)


class TestInputShapeSetsTheMatchCost:
    """`get_matching_blocks()` | O(A + B) best, O(A·B·min(A, B)) worst, and
    O(B + A·k) at worst when no element of `b` repeats.

    Each shape is measured as exact match work, so the ratios separate linear,
    quadratic and cubic growth without timing noise.
    """

    @pytest.mark.parametrize("size", [2_000, 20_000])
    def test_identical_sequences_are_linear(self, size: int) -> None:
        a = list(range(size))

        assert match_work(a, list(a)) == 2 * size

    @pytest.mark.parametrize("size", [2_000, 20_000])
    def test_sequences_sharing_nothing_are_linear(self, size: int) -> None:
        assert match_work(list(range(size)), list(range(size, 2 * size))) == size

    def test_distinct_elements_cost_grows_with_blocks(self) -> None:
        size = 5_000
        works: list[int] = []
        for every in (1_000, 100, 10):
            a, b = evenly_edited(size, every)
            k = blocks_of(a, b)
            work = match_work(a, b)
            assert work <= 2 * (len(b) + size * k), (every, k, work)
            works.append(work)

        assert works[1] > works[0] * 5, works
        assert works[2] > works[1] * 5, works

    def test_regular_edits_are_quadratic_in_length(self) -> None:
        small = match_work(*evenly_edited(2_000, 50))
        large = match_work(*evenly_edited(8_000, 50))

        assert large > small * 10, f"4x the length: {small} -> {large}, x{large / small:.1f}"

    def test_random_edits_cost_far_less_than_regular_ones(self) -> None:
        even_a, even_b = evenly_edited(8_000, 50)
        edits = sum(1 for x, y in zip(even_a, even_b, strict=True) if x != y)
        random_a, random_b = randomly_edited(8_000, edits, seed=8_000)

        even = match_work(even_a, even_b)
        scattered = match_work(random_a, random_b)

        assert scattered * 4 < even, f"{edits} edits: random {scattered}, even {even}"

    def test_repeats_in_both_are_cubic_with_the_default_autojunk(self) -> None:
        works = [match_work(*sparse_zeros(size)) for size in (1_000, 2_000, 4_000)]

        for smaller, larger in zip(works, works[1:], strict=False):
            assert larger > smaller * 6, f"doubling cost x{larger / smaller:.2f}: {works}"

    def test_repeats_in_both_are_cubic_without_autojunk(self) -> None:
        works = [
            match_work("a" * size, "ba" * (size // 2), autojunk=False) for size in (50, 100, 200)
        ]

        for smaller, larger in zip(works, works[1:], strict=False):
            assert larger > smaller * 6, f"doubling cost x{larger / smaller:.2f}: {works}"

    @pytest.mark.timing
    def test_the_cubic_shape_is_cubic_in_time(self) -> None:
        def match(size: int) -> Callable[[], Any]:
            a, b = sparse_zeros(size)
            return lambda: SequenceMatcher(None, a, b).get_matching_blocks()

        small = best_ns(match(1_000), repeats=3)
        large = best_ns(match(4_000), repeats=3)

        ratio = large / small
        assert ratio > 30, f"4x the length cost x{ratio:.1f}; quadratic is 16, cubic 64"


class TestFindLongestMatch:
    """`find_longest_match()` | O(A·B) worst | O(B): one index entry walked, and
    held, per occurrence; O(A) when no element of `b` repeats."""

    def test_the_peak_follows_the_occurrences_in_b(self) -> None:
        peaks = []
        for size in (100, 100_000):
            matcher = SequenceMatcher(None, [0], [0] * size, autojunk=False)
            peaks.append(peak_bytes(matcher.find_longest_match))

        assert peaks[1] > peaks[0] * 100, peaks

    def test_distinct_elements_cost_a_single_pass(self) -> None:
        a = list(range(10_000))
        matcher = CountingMatcher(None, a, list(reversed(a)))
        CountedEntries.walked = 0

        match = matcher.find_longest_match()

        assert CountedEntries.walked == 2 * len(a)
        assert (match.a, match.b, match.size) == (0, len(a) - 1, 1)

    def test_default_bounds_cover_both_sequences(self) -> None:
        matcher = SequenceMatcher(None, " abcd", "abcd abcd")

        assert matcher.find_longest_match() == Match(0, 4, 5)
        assert matcher.find_longest_match(0, 5, 0, 4) == Match(1, 0, 4)


class TestAutojunk:
    """With `autojunk=True` and B >= 200, an element occurring more than
    B/100 + 1 times is popular and left out of the index, which changes the
    result."""

    @pytest.mark.parametrize(
        ("size", "copies", "popular"),
        [(200, 3, False), (200, 4, True), (1_000, 11, False), (1_000, 12, True), (199, 150, False)],
    )
    def test_the_threshold(self, size: int, copies: int, popular: bool) -> None:
        b: list[object] = [*(["x"] * copies), *range(size - copies)]
        matcher = SequenceMatcher(None, [], b)

        assert ("x" in internal(matcher).bpopular) is popular
        assert ("x" in internal(matcher).b2j) is not popular

    def test_autojunk_false_keeps_everything(self) -> None:
        matcher = SequenceMatcher(None, [], ["x"] * 1_000, autojunk=False)

        assert internal(matcher).bpopular == set()
        assert len(internal(matcher).b2j["x"]) == 1_000

    def test_small_alphabet_text_scores_zero(self) -> None:
        rng = random.Random(0)
        text = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(1_000))

        default = SequenceMatcher(None, "x" + text, "y" + text)
        exact = SequenceMatcher(None, "x" + text, "y" + text, autojunk=False)

        assert len(internal(default).bpopular) == 26
        assert default.ratio() == 0.0
        assert exact.ratio() > 0.99


class TestQuickRatios:
    """`quick_ratio()` O(A + B) and `real_quick_ratio()` O(1) are upper bounds."""

    @pytest.mark.parametrize(
        ("a", "b"), [("abcd", "bcde"), ("kitten", "sitting"), ("abc", "xyz"), ("", "abc")]
    )
    def test_each_bounds_the_next(self, a: str, b: str) -> None:
        matcher = SequenceMatcher(None, a, b)

        assert matcher.real_quick_ratio() >= matcher.quick_ratio() >= matcher.ratio()

    def test_real_quick_ratio_uses_only_the_lengths(self) -> None:
        matcher = SequenceMatcher(None, "abc", "xyzxyzx")

        assert matcher.real_quick_ratio() == 2 * 3 / 10

    def test_quick_ratio_keeps_the_count_of_b(self) -> None:
        matcher = SequenceMatcher(None, "aab", "abb")
        assert matcher.quick_ratio() == 2 * 2 / 6
        counts = matcher.fullbcount  # type: ignore[attr-defined]

        matcher.set_seq1("bbb")

        assert matcher.quick_ratio() == 2 * 2 / 6
        assert matcher.fullbcount is counts  # type: ignore[attr-defined]


class _RecordingMatcher(SequenceMatcher[Any]):
    """Records which matcher each search belongs to, in order."""

    log: list[int] = []

    def find_longest_match(
        self, alo: int = 0, ahi: int | None = None, blo: int = 0, bhi: int | None = None
    ) -> Match:
        _RecordingMatcher.log.append(id(self))
        return super().find_longest_match(alo, ahi, blo, bhi)


class TestDiffGeneratorsMatchUpFront:
    """`unified_diff()`, `context_diff()` and `ndiff()` are generators that run
    the whole line match before their first line."""

    OLD = [f"line {index}\n" for index in range(200)]
    NEW = [line if index % 20 else f"changed {index}\n" for index, line in enumerate(OLD)]

    @pytest.mark.parametrize("function", [unified_diff, context_diff, ndiff])
    def test_every_line_search_happens_before_the_first_line(
        self, function: Callable[..., Iterator[str]], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _RecordingMatcher.log = []
        monkeypatch.setattr(difflib, "SequenceMatcher", _RecordingMatcher)

        diff = function(self.OLD, self.NEW)
        assert _RecordingMatcher.log == [], "a search ran before the first next()"
        next(diff)
        line_matcher = _RecordingMatcher.log[0]
        before = _RecordingMatcher.log.count(line_matcher)
        list(diff)

        assert before > 1
        assert _RecordingMatcher.log.count(line_matcher) == before

    @staticmethod
    def _stream(function: Callable[..., Iterator[str]], a: list[str], b: list[str]) -> None:
        for _ in function(a, b):
            pass

    LARGE = [f"line {index}\n" for index in range(100_000)]

    def test_unified_diff_holds_the_deleted_range(self) -> None:
        peak = peak_bytes(lambda: self._stream(unified_diff, self.LARGE, []))

        assert peak > 400_000, f"a 100,000-line deletion peaked at {peak}"

    def test_ndiff_does_not_hold_a(self) -> None:
        peak = peak_bytes(lambda: self._stream(ndiff, self.LARGE, []))

        assert peak < 50_000, f"a 100,000-line deletion peaked at {peak}"

    @pytest.mark.parametrize("function", [unified_diff, ndiff])
    def test_both_hold_the_index_of_b(self, function: Callable[..., Iterator[str]]) -> None:
        peak = peak_bytes(lambda: self._stream(function, [], self.LARGE))

        assert peak > 4_000_000, f"indexing 100,000 lines peaked at {peak}"


class _PairCountingMatcher(SequenceMatcher[Any]):
    """Counts set_seq1() calls: one per line pair `ndiff()` compares."""

    pairs = 0

    def set_seq1(self, a: Sequence[Any]) -> None:
        _PairCountingMatcher.pairs += 1
        super().set_seq1(a)


def ndiff_pairs(r: int, similar: bool, monkeypatch: pytest.MonkeyPatch) -> int:
    """Line pairs compared inside one replaced block of r lines."""
    if similar:
        old = [f"line {index:04d} text aaaa\n" for index in range(r)]
        new = [f"line {index:04d} text aaab\n" for index in range(r)]
    else:
        old = [f"{index:04d} qwertyuiop\n" for index in range(r)]
        new = [f"{index:04d} zxcvbnmasd\n" for index in range(r)]
    with monkeypatch.context() as patch:
        patch.setattr(difflib, "SequenceMatcher", _PairCountingMatcher)
        _PairCountingMatcher.pairs = 0
        delta = list(ndiff(old, new))
        pairs = _PairCountingMatcher.pairs
    assert list(restore(delta, 1)) == old
    assert list(restore(delta, 2)) == new
    # Includes one set_seq1() per matcher built, a small overcount.
    return pairs


class TestNdiffReplacedBlocks:
    """`Differ.compare()` / `ndiff()`: O(r) line pairs and O(c) space per
    replaced block on 3.14+; O(r²) to O(r³) pairs and O(r·c) on 3.10–3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="windowed search from 3.14")
    def test_pairs_are_linear_in_the_block(self, monkeypatch: pytest.MonkeyPatch) -> None:
        small = ndiff_pairs(100, similar=True, monkeypatch=monkeypatch)
        large = ndiff_pairs(400, similar=True, monkeypatch=monkeypatch)

        assert large <= 22 * 400, large
        assert large < small * 6, f"4x the lines: {small} -> {large} pairs"

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="exhaustive search before 3.14")
    def test_similar_lines_are_cubic_before_314(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pairs = [ndiff_pairs(r, similar=True, monkeypatch=monkeypatch) for r in (25, 50, 100)]

        for smaller, larger in zip(pairs, pairs[1:], strict=False):
            assert larger > smaller * 6, f"doubling r cost x{larger / smaller:.2f}: {pairs}"

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="exhaustive search before 3.14")
    def test_every_pair_is_compared_before_314(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert ndiff_pairs(50, similar=False, monkeypatch=monkeypatch) >= 50 * 50

    @staticmethod
    def _peak_for(r: int, c: int) -> int:
        old = [f"{index:04d}" + "a" * c + "\n" for index in range(r)]
        new = [f"{index:04d}" + "a" * (c - 1) + "b\n" for index in range(r)]

        def stream() -> None:
            for _ in ndiff(old, new):
                pass

        return peak_bytes(stream)

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="no recursion from 3.14")
    def test_space_does_not_grow_with_the_block(self) -> None:
        small, large = self._peak_for(10, 2_000), self._peak_for(40, 2_000)

        assert large < small * 1.5, f"4x the lines peaked {small} -> {large}"

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="recursive search before 3.14")
    def test_space_grows_with_the_block_before_314(self) -> None:
        small, large = self._peak_for(10, 200), self._peak_for(40, 200)

        assert large > small * 2, f"4x the lines peaked {small} -> {large}"

    def test_ndiff_is_differ_compare_with_character_junk(self) -> None:
        old = ["apple\n", "banana\n", "cherry\n"]
        new = ["apple\n", "bananas\n", "cherry\n"]

        delta = list(ndiff(old, new))

        assert delta == list(Differ(None, IS_CHARACTER_JUNK).compare(old, new))
        assert delta == ["  apple\n", "- banana\n", "+ bananas\n", "?       +\n", "  cherry\n"]


class TestHtmlDiffRunsNdiff:
    """`HtmlDiff.make_table()` and `make_file()` cost an `ndiff()` plus the
    rendered characters."""

    def test_each_call_runs_one_ndiff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[int] = []
        original = difflib.ndiff

        def counting(*args: Any, **kwargs: Any) -> Iterator[str]:
            calls.append(1)
            return original(*args, **kwargs)

        monkeypatch.setattr(difflib, "ndiff", counting)
        html = HtmlDiff()

        table = html.make_table(["a\n", "b\n"], ["a\n", "c\n"])
        assert len(calls) == 1
        page = html.make_file(["a\n", "b\n"], ["a\n", "c\n"])
        assert len(calls) == 2

        assert table.lstrip().startswith("<table")
        assert page.lstrip().startswith("<!DOCTYPE html") and page.rstrip().endswith("</html>")


class TestDiffBytes:
    """`diff_bytes()` decodes both inputs before `dfunc` starts, O(s)."""

    def test_both_inputs_are_read_before_the_first_line(self) -> None:
        taken = {"a": 0, "b": 0}

        def lines(name: str, count: int) -> Iterator[bytes]:
            for index in range(count):
                taken[name] += 1
                yield b"line %d\n" % index

        diff = diff_bytes(unified_diff, lines("a", 50), lines("b", 60))
        assert taken == {"a": 0, "b": 0}

        assert next(diff) == b"--- \n"
        assert taken == {"a": 50, "b": 60}

    def test_undecodable_bytes_survive(self) -> None:
        diff = list(diff_bytes(unified_diff, [b"a\n", b"\xff\n"], [b"a\n", b"b\n"], b"x", b"y"))

        assert b"-\xff\n" in diff


class TestStringInputs:
    """3.14+ rejects a string where `unified_diff()` and `context_diff()` expect
    a list of lines."""

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="rejected from 3.14")
    @pytest.mark.parametrize("function", [unified_diff, context_diff])
    def test_a_string_raises(self, function: Callable[..., Iterator[str]]) -> None:
        with pytest.raises(TypeError, match="sequence of strings"):
            list(function("one\ntwo\n", ["one\n"]))
        with pytest.raises(TypeError, match="sequence of strings"):
            list(function(["one\n"], "one\ntwo\n"))

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="accepted before 3.14")
    @pytest.mark.parametrize("function", [unified_diff, context_diff])
    def test_a_string_is_diffed_by_character(self, function: Callable[..., Iterator[str]]) -> None:
        assert list(function("ab", "ac"))


class TestRestore:
    """`restore(delta, which)` | O(1) per delta line."""

    def test_it_takes_one_delta_line_per_line_yielded(self) -> None:
        taken = [0]

        def delta() -> Iterator[str]:
            for index in range(1_000):
                taken[0] += 1
                yield f"  line {index}\n"

        lines = restore(delta(), 1)
        assert next(lines) == "line 0\n"
        assert taken == [1]

    def test_it_rebuilds_either_side(self) -> None:
        old = ["one\n", "two\n", "three\n"]
        new = ["one\n", "tree\n", "emu\n"]
        delta = list(ndiff(old, new))

        assert list(restore(delta, 1)) == old
        assert list(restore(delta, 2)) == new


class _FullMatchCountingMatcher(SequenceMatcher[Any]):
    """Counts set_seq2() calls and full matches that are actually computed."""

    indexed: list[Sequence[Any]] = []
    full_matches = 0

    def set_seq2(self, b: Sequence[Any]) -> None:
        _FullMatchCountingMatcher.indexed.append(b)
        super().set_seq2(b)

    def get_matching_blocks(self) -> list[Match]:
        if self.matching_blocks is None:  # type: ignore[attr-defined]
            _FullMatchCountingMatcher.full_matches += 1
        return super().get_matching_blocks()


class TestGetCloseMatches:
    """`get_close_matches()`: the word is indexed once, and only possibilities
    that pass the quick ratios pay a full match."""

    @pytest.fixture(autouse=True)
    def _count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _FullMatchCountingMatcher.indexed = []
        _FullMatchCountingMatcher.full_matches = 0
        monkeypatch.setattr(difflib, "SequenceMatcher", _FullMatchCountingMatcher)

    def test_rejected_possibilities_pay_no_full_match(self) -> None:
        possibilities = [f"zz{index:04d}" for index in range(1_000)]

        assert get_close_matches("abcdef", possibilities) == []
        assert [b for b in _FullMatchCountingMatcher.indexed if b] == ["abcdef"]
        assert _FullMatchCountingMatcher.full_matches == 0

    def test_each_survivor_pays_one(self) -> None:
        possibilities = [f"abcdef{index % 10}" for index in range(100)]

        matches = get_close_matches("abcdef", possibilities, n=2)

        assert len(matches) == 2
        assert [b for b in _FullMatchCountingMatcher.indexed if b] == ["abcdef"]
        assert _FullMatchCountingMatcher.full_matches == 100

    def test_best_first(self) -> None:
        assert get_close_matches("appel", ["ape", "apple", "peach", "puppy"]) == ["apple", "ape"]

    @pytest.mark.parametrize(("n", "cutoff"), [(0, 0.6), (-1, 0.6), (3, -0.1), (3, 1.1)])
    def test_bad_arguments_raise(self, n: int, cutoff: float) -> None:
        with pytest.raises(ValueError):
            get_close_matches("appel", ["apple"], n=n, cutoff=cutoff)


class TestHelpers:
    """`IS_LINE_JUNK`, `IS_CHARACTER_JUNK` and `Match`."""

    @pytest.mark.parametrize(
        ("line", "junk"), [("\n", True), ("  # \n", True), ("#", True), ("x = 1\n", False)]
    )
    def test_is_line_junk(self, line: str, junk: bool) -> None:
        assert IS_LINE_JUNK(line) is junk

    @pytest.mark.parametrize(
        ("ch", "junk"), [(" ", True), ("\t", True), ("\n", False), ("a", False)]
    )
    def test_is_character_junk(self, ch: str, junk: bool) -> None:
        assert IS_CHARACTER_JUNK(ch) is junk

    def test_match_is_a_named_tuple(self) -> None:
        match = Match(1, 2, 3)

        assert (match.a, match.b, match.size) == (1, 2, 3)
        assert tuple(match) == (1, 2, 3)


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
        line, source = next((n, s) for n, s in _blocks() if "default.ratio() == 0.0" in s)
        mutated = source.replace("default.ratio() == 0.0", "default.ratio() > 0.5", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
