"""Tests to verify documented behaviour of the re module.

The page's headline bounds - linear typical, exponential worst - were right.
What was wrong sat around them, in the annotations on the examples and in a
demonstration that demonstrated nothing:

* `match.group(i)` was annotated O(1) three times. It slices the subject, so
  it copies: a group of 100,000 characters costs 1.99e-06s against 5.1e-08s
  for one of 10, and a million costs 2.01e-05s - dead linear. `span()` stays
  at 4.7e-08s at every size, which is the O(1) alternative the page never
  mentioned. `groups()` is the same slicing, once per group.
* `finditer` was annotated "O(1) per match". Each step scans forward to the
  next match: 2.0e-07s when the match is at the cursor, 3.9e-05s when the
  next one is 200,000 characters away. The memory claim is the true part.
* The catastrophic-backtracking example searched `(a+)+$` against a string of
  nothing but `a`, printed the elapsed time and commented "Can be very slow!".
  That input *matches*, on the first attempt, in 1.6e-07s. The blow-up needs
  a subject that fails: `(a+)+b` against 24 `a`s takes 0.91s.
* The anchors example claimed `^start.*?end$` was "more efficient" than
  `start.*end` on the string "start middle end" - where the match is at
  position 0 and the anchor cannot help. Measured, the anchored pattern is
  the slower of the two there. The saving is real but on different input:
  against 100,000 characters that never match, anchored is 8.3e-08s against
  1.99e-05s, because `^` stops `search` retrying at every offset. The stated
  reason was wrong too - that is re-anchoring, not backtracking.
* "Bad: materializes all matches - O(m) memory" contradicted the table's
  O(k) two screens above. k is the right term.
* The Version Notes said nothing about atomic groups `(?>...)` or possessive
  quantifiers, added in 3.11 - which is exactly the "rewrite pattern to be
  atomic" the page recommends without saying the language now has it.
  `(?>a+)+b` and `(a++)+b` both settle the 0.91s case in 3.0e-05s.

Two code blocks did not run: one used an undefined `large_file`, the other an
undefined `process`.

Untested axes, and why:

* Pattern shape. Compilation is measured on a repeated group; a pattern whose
  parse tree is deep rather than long would change the constant, not the term.
* Unicode and flags. Everything here is ASCII with no flags. `re.IGNORECASE`
  and `re.UNICODE` change how a character class is built, not how the scan
  scales with the subject.

Read against the 3.14 sources afterwards, which sharpened three things:

* `match_getslice_by_index` reads two integers out of `self->mark` and hands
  them to `getslice`, which calls `PyUnicode_Substring`. That function opens
  with `if (start == 0 && end == length) return unicode_result_unchanged(self)`
  - so a group spanning the whole subject is returned unchanged, and only a
  proper substring is copied. It is why an early measurement of `group(0)`
  looked flat, and it is now pinned rather than tripped over.
* `findall` was documented O(k) space. The list holds k *copies*, so the
  matched text counts too: 20,000 matches cost 1.25 MB at 5 characters each
  and 5.15 MB at 200. The row and the tip beside it also disagreed, one
  saying O(k) and the other O(k + g).
* The cache prose written for this round called the compiled-pattern cache
  an LRU, and dated the second-level cache to 3.13. Both were read off the
  3.14 source alone. It is an LRU from 3.12, where `_compile` pops and
  re-inserts a found pattern as most recently used; on 3.10 and 3.11 the hit
  was a plain dict lookup and the 513th pattern dropped the oldest-inserted
  entry however often it had been used. `_MAXCACHE2` is 3.12 as well - the
  first probe checked 3.10, 3.11, 3.13 and 3.14 and skipped the one version
  where both changes landed. Both behaviours are pinned by identity,
  version-branched like the anchor tests.
* The Match rows used `k` for the number of groups while the preamble defined
  it as the number of matches, and `re.purge()` used `c` for the cache size.
  Both now have their own name.

`match.expand()` and `sub()` with a string replacement do cache the compiled
template - the C `compile_template` delegates to `re._compile_template`, which
is `lru_cache(512)`. It is not on the page because it cannot be shown: purging
between calls costs nothing measurable even with a 3,000-character template
(6.30e-04s either way), the expansion itself dominating.

Not settled by execution:

* "O(exp)" as an upper bound. The tests show the blow-up doubling with each
  added character over a range small enough to finish; no test can exhibit
  the exponent itself.
* "Third-party: the regex package provides additional features" and the
  Python 2.x note.
* "Alternation with overlap (`foo|fo`)" in the Avoid list. It is a
  correctness trap rather than a cost one - `foo|fo` never reaches its second
  branch - and the page files it under performance.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import timeit
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "stdlib" / "re.md"
EXPECTED_BLOCKS = 13

# 3.11 brought two changes this page depends on: atomic groups and possessive
# quantifiers, and an early exit for a search whose pattern starts with `^`.
ATOMIC_SUPPORTED = sys.version_info >= (3, 11)
ANCHOR_SHORT_CIRCUITS = sys.version_info >= (3, 11)

# The compiled-pattern cache is private, so it is not in the type stubs.
_re_internals: Any = re
MAXCACHE: int = _re_internals._MAXCACHE
MAXCACHE2: int | None = getattr(re, "_MAXCACHE2", None)


def pattern_cache() -> dict[Any, Any]:
    """The module's LRU of compiled patterns."""
    return _re_internals._cache


def per_call(operation: Callable[[], Any], number: int = 20_000, repeat: int = 5) -> float:
    """Seconds per call, taking the best of several runs."""
    return min(timeit.repeat(operation, number=number, repeat=repeat)) / number


def peak_bytes(operation: Callable[[], Any]) -> int:
    """Peak Python allocation during one call, with the tracer left off."""
    tracemalloc.start()
    try:
        operation()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


@pytest.fixture
def clean_pattern_cache() -> Iterator[None]:
    """Empty the compiled-pattern cache, and empty it again afterwards."""
    re.purge()
    yield
    re.purge()


class TestMatchObjectsHoldPositions:
    """The Match table: positions are free, text is a copy."""

    @staticmethod
    def _match_with_group(size: int) -> re.Match[str]:
        found = re.compile(r"a(x+)b").search("a" + "x" * size + "b")
        assert found is not None
        return found

    def test_span_returns_indices_into_the_subject(self) -> None:
        found = self._match_with_group(50)

        assert found.span(1) == (1, 51)
        assert found.start(1) == 1 and found.end(1) == 51
        assert found.string[slice(*found.span(1))] == found.group(1)

    def test_group_returns_a_copy_not_a_view(self) -> None:
        """Why the row is O(g): there is no view type to return."""
        found = self._match_with_group(1_000)

        text = found.group(1)

        assert text is not found.string
        assert len(text) == 1_000
        assert sys.getsizeof(text) > sys.getsizeof(found.span(1))

    @pytest.mark.timing
    def test_group_cost_follows_the_captured_length(self) -> None:
        small = self._match_with_group(1_000)
        large = self._match_with_group(1_000_000)

        small_time = per_call(lambda: small.group(1), 50_000)
        large_time = per_call(lambda: large.group(1), 20_000)

        assert large_time > small_time * 20, (
            f"a thousand times the captured text is copied out: "
            f"1,000 chars {small_time:.2e}s, 1,000,000 chars {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_span_does_not_follow_the_captured_length(self) -> None:
        """The alternative the page now points at."""
        small = self._match_with_group(1_000)
        large = self._match_with_group(1_000_000)

        small_time = per_call(lambda: small.span(1), 50_000)
        large_time = per_call(lambda: large.span(1), 50_000)

        assert large_time < small_time * 2, (
            f"two integers, whatever they point at: 1,000 chars {small_time:.2e}s, "
            f"1,000,000 chars {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_groups_pays_once_per_group(self) -> None:
        one = re.compile(r"(x{100})").search("x" * 100)
        many = re.compile("".join(r"(x{100})" for _ in range(50))).search("x" * 5_000)
        assert one is not None and many is not None

        one_time = per_call(one.groups, 50_000)
        many_time = per_call(many.groups, 20_000)

        assert many_time > one_time * 5, (
            f"fifty groups are fifty slices, not one: 1 group {one_time:.2e}s, "
            f"50 groups {many_time:.2e}s"
        )

    def test_a_group_spanning_the_whole_subject_is_not_copied(self) -> None:
        """The one case where `group()` is free, from `PyUnicode_Substring`.

        It returns the subject unchanged when the slice covers all of it, so
        `fullmatch(...).group()` hands back the string it was given.
        """
        whole = re.compile(r"x+").search("x" * 1_000)
        partial = re.compile(r"a(x+)b").search("a" + "x" * 1_000 + "b")
        assert whole is not None and partial is not None

        assert whole.group(0) is whole.string, "start == 0 and end == len is the fast path"
        assert partial.group(1) is not partial.string, "a proper substring is copied"
        assert partial.group(1) == "x" * 1_000

    def test_groupdict_carries_the_same_slices(self) -> None:
        found = re.compile(r"(?P<head>a+)(?P<tail>b+)").search("aaabbb")
        assert found is not None

        assert found.groupdict() == {"head": "aaa", "tail": "bbb"}
        assert found.groups() == ("aaa", "bbb")

    def test_expand_substitutes_the_named_groups(self) -> None:
        found = re.compile(r"(?P<word>\w+)").search("hello world")
        assert found is not None

        assert found.expand(r"<\g<word>!>") == "<hello!>"

    @pytest.mark.timing
    def test_expand_follows_the_template_length(self) -> None:
        """The t in the expand row's O(t + g).

        The g side is the same group slicing the tests above pin; what varies
        here is the literal template text the expansion copies out. Both
        sizes are far above the fixed call overhead, because 3.12 rewrote
        template expansion and left the shorter end of an earlier framing
        indistinguishable from noise: at 100,000 characters 3.11 takes
        1.31e-02s and 3.14 takes 2.12e-06s. The bound is unchanged - both
        rise tenfold for a tenfold template - and only the constant moved.
        """
        found = re.compile(r"(a+)").fullmatch("a" * 1_000)
        assert found is not None

        brief = r"\1" + "x" * 10_000
        lengthy = r"\1" + "x" * 1_000_000

        short = per_call(lambda: found.expand(brief), 200, repeat=3)
        long = per_call(lambda: found.expand(lengthy), 1, repeat=3)

        assert long > short * 20, (
            f"the template is copied into the result: {len(brief):,} chars "
            f"{short:.2e}s, {len(lengthy):,} chars {long:.2e}s"
        )


class TestFinditerIsLazyNotFree:
    """`finditer` | O(m) over the scan | O(1) space |."""

    def test_finditer_holds_one_match_at_a_time(self) -> None:
        pattern = re.compile(r"\w+")
        text = " ".join(f"word{index}" for index in range(20_000))

        materialised = peak_bytes(lambda: pattern.findall(text))
        streamed = peak_bytes(lambda: [None for _ in pattern.finditer(text)] and None)

        assert materialised > streamed * 3, (
            f"findall keeps every match, finditer keeps one: findall {materialised:,} "
            f"bytes, finditer {streamed:,} bytes"
        )

    @pytest.mark.timing
    def test_each_step_scans_to_the_next_match(self) -> None:
        """The corrected annotation: the steps are not O(1)."""
        pattern = re.compile(r"z")
        adjacent = "zz"
        distant = "z" + "a" * 200_000 + "z"

        def second_match(subject: str) -> re.Match[str]:
            found = pattern.finditer(subject)
            next(found)
            return next(found)

        near = per_call(lambda: second_match(adjacent), 20_000)
        far = per_call(lambda: second_match(distant), 200)

        assert far > near * 20, (
            f"the step costs the distance it covers: adjacent {near:.2e}s, 200,000 apart {far:.2e}s"
        )

    def test_the_whole_iteration_finds_every_match(self) -> None:
        pattern = re.compile(r"\w+")
        text = "Hello world from Python"

        assert [found.group() for found in pattern.finditer(text)] == pattern.findall(text)


class TestBacktracking:
    """The claim the page's own example contradicted."""

    def test_all_a_input_matches_the_nested_quantifier_at_once(self) -> None:
        """`(a+)+$` on nothing but `a` is the fast case, not the slow one."""
        pattern = re.compile(r"(a+)+$")

        assert pattern.search("a" * 20) is not None

    @pytest.mark.timing
    def test_the_blow_up_needs_a_subject_that_fails(self) -> None:
        matching = re.compile(r"(a+)+$")
        failing = re.compile(r"(a+)+b")

        succeeds = per_call(lambda: matching.search("a" * 18), 2_000)
        fails = per_call(lambda: failing.search("a" * 18), 3, repeat=3)

        assert fails > succeeds * 1_000, (
            f"the page timed the wrong input: match {succeeds:.2e}s, non-match {fails:.2e}s"
        )

    @pytest.mark.timing
    def test_each_extra_character_roughly_doubles_the_work(self) -> None:
        """As close to "O(exp)" as a test can get and still finish."""
        pattern = re.compile(r"(a+)+b")

        short = per_call(lambda: pattern.search("a" * 14), 10, repeat=3)
        longer = per_call(lambda: pattern.search("a" * 18), 3, repeat=3)

        assert longer > short * 8, (
            f"four more characters should cost about sixteen times as much: "
            f"14 chars {short:.2e}s, 18 chars {longer:.2e}s"
        )

    @pytest.mark.timing
    def test_removing_the_nesting_settles_it(self) -> None:
        nested = re.compile(r"(a+)+b")
        flat = re.compile(r"a+b")

        nested_time = per_call(lambda: nested.search("a" * 18), 3, repeat=3)
        flat_time = per_call(lambda: flat.search("a" * 18), 5_000)

        assert nested_time > flat_time * 1_000, f"nested {nested_time:.2e}s, flat {flat_time:.2e}s"

    @pytest.mark.timing
    @pytest.mark.skipif(
        not ATOMIC_SUPPORTED, reason="atomic groups and possessive quantifiers are 3.11+"
    )
    def test_atomic_and_possessive_forms_settle_it_too(self) -> None:
        """The remedy the page recommended without naming, added in 3.11.

        Both keep the nested shape and forbid the redistribution that makes
        it explode, so the pattern still means what it meant.
        """
        nested = re.compile(r"(a+)+b")
        atomic = re.compile(r"(?>a+)+b")
        possessive = re.compile(r"(a++)+b")

        nested_time = per_call(lambda: nested.search("a" * 18), 3, repeat=3)
        atomic_time = per_call(lambda: atomic.search("a" * 18), 5_000)
        possessive_time = per_call(lambda: possessive.search("a" * 18), 5_000)

        assert nested_time > atomic_time * 1_000, (
            f"nested {nested_time:.2e}s, atomic {atomic_time:.2e}s"
        )
        assert nested_time > possessive_time * 1_000, (
            f"nested {nested_time:.2e}s, possessive {possessive_time:.2e}s"
        )

    @pytest.mark.skipif(ATOMIC_SUPPORTED, reason="3.11 and later accept them")
    def test_before_3_11_the_syntax_is_rejected(self) -> None:
        with pytest.raises(re.error):
            re.compile(r"(?>a+)+b")
        with pytest.raises(re.error):
            re.compile(r"(a++)+b")


class TestAnchors:
    """The corrected claim: `^` stops the retry, it does not stop backtracking."""

    @pytest.mark.timing
    def test_an_anchor_saves_nothing_when_the_match_is_at_the_start(self) -> None:
        """What the page's own example measured, had it measured anything."""
        unanchored = re.compile(r"start.*end")
        anchored = re.compile(r"^start.*end")
        text = "start middle end"

        loose = per_call(lambda: unanchored.search(text))
        tight = per_call(lambda: anchored.search(text))

        assert tight > loose * 0.5, (
            f"the anchor cannot help at position 0: unanchored {loose:.2e}s, anchored {tight:.2e}s"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(not ANCHOR_SHORT_CIRCUITS, reason="the anchored early exit is Python 3.11+")
    def test_an_anchor_saves_the_retry_when_nothing_matches(self) -> None:
        """`sre_lib.h` gives up after the first attempt when the pattern
        opens with `SRE_AT_BEGINNING`, rather than walking to the end.
        """
        unanchored = re.compile(r"start.*end")
        anchored = re.compile(r"^start.*end")
        haystack = "x" * 100_000

        loose = per_call(lambda: unanchored.search(haystack), 200)
        tight = per_call(lambda: anchored.search(haystack), 20_000)

        assert loose > tight * 20, (
            f"one attempt per position against one attempt in total: "
            f"unanchored {loose:.2e}s, anchored {tight:.2e}s"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(ANCHOR_SHORT_CIRCUITS, reason="3.11 and later exit early")
    def test_before_3_11_the_anchor_cost_rather_than_saved(self) -> None:
        """Which is why the page dates the advice.

        Without the early exit the retry loop runs anyway and the assertion
        fails at every position, while the unanchored form still gets its
        literal-prefix fast scan - so anchoring made it slower.
        """
        unanchored = re.compile(r"start.*end")
        anchored = re.compile(r"^start.*end")
        haystack = "x" * 100_000

        loose = per_call(lambda: unanchored.search(haystack), 200)
        tight = per_call(lambda: anchored.search(haystack), 200)

        assert tight > loose, (
            f"before 3.11 the anchored form should be the slower one: "
            f"unanchored {loose:.2e}s, anchored {tight:.2e}s"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(not ANCHOR_SHORT_CIRCUITS, reason="the anchored early exit is Python 3.11+")
    def test_the_anchored_search_stops_growing_with_the_subject(self) -> None:
        anchored = re.compile(r"^start.*end")
        small = "x" * 100_000
        large = "x" * 400_000

        short = per_call(lambda: anchored.search(small), 20_000)
        long = per_call(lambda: anchored.search(large), 20_000)

        assert long < short * 2, (
            f"four times the haystack, one attempt either way: "
            f"100,000 chars {short:.2e}s, 400,000 chars {long:.2e}s"
        )

    def test_both_forms_agree_on_the_answer(self) -> None:
        for text in ("start middle end", "x start middle end", "nothing here"):
            loose = re.search(r"start.*end", text)
            tight = re.search(r"^start.*end", text)

            assert (loose is not None) == (text.find("start") >= 0 and text.endswith("end"))
            assert (tight is not None) == text.startswith("start")


class TestPatternCache:
    """`re.compile` caches 512 patterns; the eviction policy changed in 3.12."""

    def test_the_documented_size_is_the_implementation_size(self) -> None:
        assert MAXCACHE == 512

    def test_compiling_the_same_pattern_returns_the_same_object(
        self, clean_pattern_cache: None
    ) -> None:
        first = re.compile(r"\d+")
        second = re.compile(r"\d+")

        assert first is second, "a cache hit hands back the compiled pattern"

    def test_the_cache_drops_one_entry_rather_than_emptying(
        self, clean_pattern_cache: None
    ) -> None:
        """The contrast worth drawing: one entry goes, not the whole cache.

        `_strptime` empties its format cache once it overflows; `re` evicts a
        single entry and keeps the rest. The sizes here come out the same
        under either eviction policy, so which one runs is pinned by the two
        recency tests below - it changed in 3.12.
        """
        sizes = []
        for index in range(MAXCACHE + 4):
            re.compile(f"unique-pattern-{index}")
            if index in (0, MAXCACHE - 2, MAXCACHE - 1, MAXCACHE + 3):
                sizes.append(len(pattern_cache()))

        assert sizes == [1, MAXCACHE - 1, MAXCACHE, MAXCACHE], (
            f"expected the cache to fill and then hold: {sizes}"
        )

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="hits refresh recency from 3.12 on")
    def test_before_3_12_a_hit_does_not_save_the_oldest_entry(
        self, clean_pattern_cache: None
    ) -> None:
        """3.10 and 3.11 are insertion-ordered, not an LRU.

        A cache hit in `_compile` is a plain dict lookup with no move to the
        end, so however often the oldest-inserted entry is used it is still
        the one a 513th pattern drops.
        """
        oldest = re.compile("pattern-oldest")
        for index in range(MAXCACHE - 1):
            re.compile(f"pattern-{index}")
        assert len(pattern_cache()) == MAXCACHE
        assert re.compile("pattern-oldest") is oldest, "the entry is present"

        re.compile("pattern-new")  # the 513th insert

        assert re.compile("pattern-oldest") is not oldest, (
            "the oldest-inserted entry was dropped despite the recent hit"
        )

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="before 3.12 a hit changes nothing")
    def test_from_3_12_a_hit_saves_the_entry(self, clean_pattern_cache: None) -> None:
        """From 3.12 a hit pops and re-inserts, so the used entry survives.

        `_compile` re-records a found pattern as most recently used, and the
        513th pattern drops the least recently used one instead. On 3.13+
        the fast-path FIFO may serve the hit first; it has long since
        evicted a pattern this old, so the LRU refresh still happens.
        """
        oldest = re.compile("pattern-oldest")
        for index in range(MAXCACHE - 1):
            re.compile(f"pattern-{index}")
        assert len(pattern_cache()) == MAXCACHE
        assert re.compile("pattern-oldest") is oldest, "the hit re-records it"

        re.compile("pattern-new")  # the 513th insert

        assert re.compile("pattern-oldest") is oldest, (
            "a recently used entry should not be the one dropped"
        )

    def test_purge_empties_it(self, clean_pattern_cache: None) -> None:
        re.compile(r"\d+")
        assert len(pattern_cache()) > 0

        re.purge()

        assert len(pattern_cache()) == 0

    @pytest.mark.skipif(MAXCACHE2 is None, reason="the second-level cache is Python 3.12+")
    def test_the_fast_path_cache_is_smaller(self) -> None:
        assert MAXCACHE2 == 256
        assert MAXCACHE2 is not None and MAXCACHE2 < MAXCACHE


class TestCompilationAndEscaping:
    """`re.compile(pattern)` | O(n) | and `re.escape(string)` | O(n) |."""

    @pytest.mark.timing
    def test_compilation_follows_the_pattern_length(self) -> None:
        short = "(?:abc)" * 10
        long = "(?:abc)" * 100

        short_time = per_call(lambda: (re.purge(), re.compile(short)), 200)
        long_time = per_call(lambda: (re.purge(), re.compile(long)), 200)
        re.purge()

        assert long_time > short_time * 3, (
            f"ten times the pattern is ten times the parse: {len(short)} chars "
            f"{short_time:.2e}s, {len(long)} chars {long_time:.2e}s"
        )

    def test_escape_leaves_ordinary_characters_alone(self) -> None:
        assert re.escape("abc123") == "abc123"
        assert re.escape("a.b*c") == "a\\.b\\*c"
        assert re.match(re.escape("a.b*c") + "$", "a.b*c") is not None

    def test_an_invalid_pattern_raises_re_error(self) -> None:
        with pytest.raises(re.error):
            re.compile(r"(unclosed")


class TestDocumentedValues:
    """The results the examples state in their comments."""

    def test_findall_returns_the_listed_words(self) -> None:
        assert re.compile(r"\w+").findall("Hello world from Python") == [
            "Hello",
            "world",
            "from",
            "Python",
        ]

    def test_sub_produces_the_listed_strings(self) -> None:
        pattern = re.compile(r"\d+")
        text = "Numbers: 10, 20, 30"

        assert pattern.sub("X", text) == "Numbers: X, X, X"
        assert pattern.sub(lambda m: str(int(m.group()) * 2), text) == "Numbers: 20, 40, 60"

    def test_split_produces_the_listed_parts(self) -> None:
        assert re.compile(r",\s*").split("apple, banana, cherry") == [
            "apple",
            "banana",
            "cherry",
        ]

    def test_the_grouping_example_extracts_what_it_says(self) -> None:
        found = re.compile(r"(\d+)-(\w+)").search("123-abc")
        assert found is not None

        assert found.group(0) == "123-abc"
        assert found.group(1) == "123"
        assert found.group(2) == "abc"
        assert found.groups() == ("123", "abc")
        assert found.span(1) == (0, 3)


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, on every supported version.

    The block showing atomic groups guards them behind a version check rather
    than being held back: on 3.10 the syntax is a compile error, and a block
    that cannot run there would go untested on the version that needs the
    warning most.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )
        guarded = [line for line, source in blocks if "sys.version_info" in source]
        assert len(guarded) == 1, f"one block should be version-gated, found {guarded}"

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_nested_pattern_is_only_run_on_a_short_subject(self) -> None:
        """The long call has to stay commented out.

        `bad_pattern` is the nested quantifier, and its cost quadruples every
        two characters: 9.1e-04s at 14, 1.4e-02s at 18, 5.7e-02s at 20. The
        block shows the shape at 8 and leaves the expensive one as a comment,
        which the block runner cannot check for itself - running the page is
        exactly what would hang.
        """
        blocks = [(line, source) for line, source in _blocks() if "bad_pattern" in source]
        assert len(blocks) == 1, f"expected one backtracking block, found {blocks}"
        line, source = blocks[0]

        live = [
            statement.strip()
            for statement in source.splitlines()
            if statement.strip().startswith("bad_pattern.search")
        ]
        assert live, "the nested pattern should still be exercised somewhere"

        for statement in live:
            repetition = re.search(r"'a' \* (\d+)", statement)
            assert repetition is not None, f"{PAGE.name}:{line}: {statement}"
            assert int(repetition.group(1)) <= 8, (
                f"{PAGE.name}:{line} runs the blow-up on a long subject: {statement}"
            )

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import re\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
