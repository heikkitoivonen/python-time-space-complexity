"""Tests for docs/stdlib/re.md.

The page prices compilation in the pattern's length and matching in the
subject's, with the scan cost `s` standing for the difference between one
attempt and an attempt at every start position. Where a claim is about what a
call copies or keeps - positions against text, the subject a match holds, the
list `findall` builds against the one match `finditer` holds - it is settled
by identity or traced allocation, which need no tolerance. Where it is about
growth - one attempt against many, competing repetitions, the anchor's early
exit - it is settled by timing at sizes in equal multiplicative steps, with
thresholds between what linear and quadratic growth predict. The pattern cache
is settled by identity and by counting calls into the compiler.

Measurement scope:

* `re.compile` over `(?:abc)` repeated 10, 100 and 1,000 times: each 10x
  step in the pattern costs between 4x and 40x, which admits linear growth
  and excludes quadratic. Two alternatives sharing a prefix of 1,000, 4,000
  and 16,000 characters are the O(n²) case, settled by counting: the parser
  moves the prefix out one item at a time with `del item[0]`, and those
  deletions shift exactly n(n+1) items for two alternatives sharing n
  characters, while alternatives with no common prefix shift none. Each
  shifted item is one pointer moved, so linear parsing overhead obscures the
  quadratic term in wall-clock timings: on 3.10 and 3.14 the shared prefix
  costs 1.3x to 1.8x the unshared one at 1,000 characters and 5.8x to 16.7x
  at 32,000. The
  same pattern and flags compiled twice is the same object; after `purge()`
  it is not, nor with `re.DEBUG`, which prints the parse tree. Long literals, alternations of 8,000
  words, 8,000 capturing or named groups and 16,000 backreferences all
  compiled in time linear in the pattern on 3.14; only the repeated group is
  asserted.
* One attempt against many: `\\w+@` against 500, 2,000 and 8,000 `a`s. With
  `match()` and `fullmatch()` each 4x step costs under 8x; with `search()`
  over 8x, since every start position scans to the end. `\\b\\w+@` and
  `\\w+@` over 20-character words separated by spaces stay under 8x per
  step with `search()`, so a bounded failed attempt keeps the scan linear.
* Competing repetitions: `a*a*b` matched against 250, 1,000 and 4,000 `a`s
  costs over 8x per 4x step within one attempt. `(a+)+b` costs over 8x
  from 14 to 18 characters against a failing subject, and over 1,000x more
  than `(a+)+$` on a subject it matches, than `a+b`, and on 3.11+ than
  `(?>a+)+b` and `(a++)+b`. Before 3.11 the latter two are asserted to be
  `re.error`. `a*a*b` is also asserted under 40x per 4x step, which excludes
  cubic growth. `(?:a|aa)+b`, one repetition over overlapping alternatives,
  costs over 5x from 16 to 22 characters.
* Backtracking stack: a `fullmatch` of `(?:ab)*` peaks over 5x higher at
  200,000 characters than at 20,000, while `[ab]*` peaks under 10 KB at
  2,000,000.
* The anchor, on 3.11+: `^start.*end` and `\\Astart.*end` search 100,000
  non-matching characters in under 1/20 the time of `start.*end`, and 10x
  the subject costs the anchored search under 3x; with `re.MULTILINE` the
  `^` search costs over 4x at 10x the subject. Before 3.11 the anchored
  search costs over 4x at 10x the subject. `match()` costs under 3x at 10x
  the subject. With the match at position 0 the anchored search is not
  asserted faster.
* A `Match` is the same size for a 10- and a 1,000,000-character subject and
  larger with 50 groups than with none; `Match.string` is the subject.
  `group()` of a proper substring is a new string whose cost grows over 20x
  from 1,000 to 1,000,000 characters, `span()` under 10x; `group(0)` over the
  whole of an exact `str` or `bytes` subject is the subject, while a
  `bytearray` subject gives back `bytes`. `group(1, 2, 2, 1)` is a tuple of
  four, repeats included. `groups()` over 50 groups costs over 5x one
  group. `expand()` over a template of 10,000,000 against 10,000 characters
  costs over 20x, with the captured group held at 1,000 characters.
* `findall` over 20,000 words peaks over 3x what iterating `finditer`
  does, and over 2x as high at 200-character matches as at 5-character ones
  for the same count. `finditer` over `(a+)+b` and 40 `a`s returns within a
  30-second subprocess timeout, so it does not scan; building it peaks over
  8 KB higher with 1,000 groups than with none, the O(c) of its marks. The second step of `finditer` costs over 20x more when the next
  match is 200,000 characters away than when it is adjacent.
* `sub` peaks over 20x higher when 1,000 matches become 1,000-character
  replacements than when they become one character, over the same subject;
  deleting 100,000 matches peaks over 20x higher than deleting 1,000, with
  an empty result either way, which is the k term. A template of 1,000,000
  characters with a backreference peaks over 20x higher than one of 10,000
  against a subject it never matches, which is the t term. A template with
  a backreference, used 50 times, is parsed once, observed
  through the cache on `re._compile_template` (3.12+) or `re._compile_repl`.
  A function replacement is called once per match. Over 2,001 empty
  matches, a template of 1,000 backreferences to an empty group costs over
  20x one of a single backreference, with the same result: the k·t term.
* `Pattern.groupindex` is a `mappingproxy` that refuses assignment when the
  pattern has named groups, and a new empty dict when it has none; it costs
  under 3x as much with 2,000 named groups as with one. The module-level
  functions call the compiler once for a pattern used twice, and again after
  `purge()`. `re.escape` peaks over 5x higher for 10x the input.
* The cache holds 512 patterns and drops one entry when a new pattern arrives
  at a full cache. Which entry is not on the page: from 3.12 a hit that
  reaches the 512-entry cache re-records it as most recently used, so the
  513th pattern drops a different one, while a hit served by the 256-entry
  fast-path cache in front of it refreshes nothing; on 3.10 and 3.11 the
  oldest-inserted entry is dropped despite a recent hit.
* `re.PatternError` is `re.error` from 3.13, and absent before; `pos`,
  `lineno` and `colno` locate the error in a multi-line pattern.
* Every fenced Python block runs in its own subprocess, on every supported
  version, and a mutated assertion in one of them is asserted to fail. The
  catastrophic-backtracking block is asserted to run its nested pattern only
  on subjects of at most 8 `a`s.

Not settled here:

* That the backtracking worst case is exponential rather than a high-degree
  polynomial. The tests show the cost multiplying with each added character
  over a range small enough to finish; no test can exhibit the exponent.
* The pattern held fixed. Matching bounds are in m; how the per-character
  cost grows with the pattern - an alternation of many branches, a large
  character class - is not measured. Everything here is ASCII: `IGNORECASE`,
  `LOCALE` and non-ASCII character classes are not varied, nor are `bytes`
  patterns, whose code path is the same C engine.
* `re.purge()` as O(1) is read from Lib/re/__init__.py: it clears caches whose
  entry counts `_MAXCACHE` and `_MAXCACHE2` bound. Freeing the patterns they
  held is charged to their compilation, by the page's cost model, and is not
  measured.
* The flag constants, `RegexFlag`, `re.Pattern`, `re.Match`, `Pattern.pattern`,
  `Pattern.flags`, `Pattern.groups`, `Match.pos`, `Match.endpos` and
  `PatternError.msg` and `.pattern` are stored attributes, read from
  Modules/_sre/sre.c and Lib/re/_constants.py; only their values are asserted.
* `re.Scanner`, `Pattern.scanner` and `Match.regs` are undocumented and not on
  the page.
* Nesting depth: a pattern nested 500 groups deep raises
  `RecursionError` in the parser rather than compiling; that limit is not a
  cost the page prices.
"""

from __future__ import annotations

import operator
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "stdlib" / "re.md"
EXPECTED_BLOCKS = 8

# Atomic groups, possessive quantifiers and the anchored early exit are 3.11+.
ATOMIC_SUPPORTED = sys.version_info >= (3, 11)
ANCHOR_SHORT_CIRCUITS = sys.version_info >= (3, 11)

# The cache and the compiler entry point are private, so not in the type stubs.
_re_internals: Any = re
MAXCACHE: int = _re_internals._MAXCACHE
MAXCACHE2: int | None = getattr(re, "_MAXCACHE2", None)


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


def pattern_cache() -> dict[Any, Any]:
    """The module's cache of compiled patterns."""
    return _re_internals._cache


def compiler_module() -> Any:
    """The module whose `compile` the pattern cache calls on a miss."""
    return getattr(re, "_compiler", None) or _re_internals.sre_compile


def parser_module() -> Any:
    """The module that parses a pattern into `SubPattern` item lists."""
    return getattr(re, "_parser", None) or _re_internals.sre_parse


def template_cache() -> Any:
    """The lru_cache that parses a replacement template."""
    return getattr(re, "_compile_template", None) or _re_internals._compile_repl


@pytest.fixture
def clean_pattern_cache() -> Iterator[None]:
    """Empty the pattern caches, and empty them again afterwards."""
    re.purge()
    yield
    re.purge()


class TestCompilation:
    """`re.compile(pattern, flags=0)` | O(n) | O(n), O(n²) for alternatives
    sharing a long common prefix; cached except with `re.DEBUG`."""

    @pytest.mark.timing
    def test_each_step_in_pattern_length_costs_a_linear_step(self) -> None:
        times = []
        for repeat in (10, 100, 1_000):
            pattern = "(?:abc)" * repeat
            times.append(best_ns(lambda p=pattern: (re.purge(), re.compile(p)), inner=10))
        re.purge()

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(4 < step < 40 for step in steps), (
            f"10x the pattern should cost about 10x, not 100x: {times} ns, steps {steps}"
        )

    def test_a_shared_prefix_across_alternatives_shifts_quadratically_many_items(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        subpattern = parser_module().SubPattern
        delete = subpattern.__delitem__
        shifted = [0]

        def counting_delete(self: Any, index: Any) -> None:
            shifted[0] += len(self.data) - 1 if index == 0 else 0
            delete(self, index)

        monkeypatch.setattr(subpattern, "__delitem__", counting_delete)

        def items_shifted(pattern: str) -> int:
            shifted[0] = 0
            re.purge()
            re.compile(pattern)
            return shifted[0]

        for length in (1_000, 4_000, 16_000):
            shared = "x" * length + "a|" + "x" * length + "b"
            assert items_shifted(shared) == length * (length + 1), f"prefix of {length}"
        assert items_shifted("x" * 16_000 + "a|" + "y" * 16_000 + "b") == 0
        re.purge()

    def test_debug_bypasses_the_cache(
        self, clean_pattern_cache: None, capsys: pytest.CaptureFixture[str]
    ) -> None:
        first = re.compile("ab", re.DEBUG)

        assert re.compile("ab", re.DEBUG) is not first
        assert "LITERAL" in capsys.readouterr().out

    def test_the_same_pattern_and_flags_return_the_same_object(
        self, clean_pattern_cache: None
    ) -> None:
        first = re.compile(r"\d+")

        assert re.compile(r"\d+") is first
        assert re.compile(r"\d+", re.IGNORECASE) is not first, "flags are part of the key"

    def test_after_purge_the_pattern_compiles_again(self, clean_pattern_cache: None) -> None:
        first = re.compile(r"\d+")

        re.purge()

        assert re.compile(r"\d+") is not first
        assert len(pattern_cache()) == 1

    def test_an_invalid_pattern_raises_re_error(self) -> None:
        with pytest.raises(re.error):
            re.compile(r"(unclosed")


class TestModuleFunctionsCompileOnAMiss:
    """The module-level rows: `re.compile`'s cost on a miss, a lookup on a hit."""

    def test_a_pattern_used_twice_is_compiled_once(
        self, clean_pattern_cache: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        compiler = compiler_module()
        real = compiler.compile
        calls: list[object] = []

        def counting(pattern: object, flags: int) -> object:
            calls.append(pattern)
            return real(pattern, flags)

        monkeypatch.setattr(compiler, "compile", counting)

        assert re.search(r"\d+x", "12x") is not None
        assert re.findall(r"\d+x", "1x 2x") == ["1x", "2x"]
        assert re.sub(r"\d+x", "-", "1x 2x") == "- -"
        assert calls == [r"\d+x"], f"one compile for three calls: {calls}"

        re.purge()
        assert re.split(r"\d+x", "a1xb") == ["a", "b"]
        assert calls == [r"\d+x", r"\d+x"], "purge() empties the cache"


class TestOneAttemptOrMany:
    """`match`/`fullmatch` | O(m), `search` | O(s): s is O(m²) when failed
    attempts run to the end, and O(m) when each stops within a bounded
    distance."""

    SIZES = (500, 2_000, 8_000)

    @classmethod
    def _steps(cls, operation: Callable[[str], Any], make: Callable[[int], str]) -> list[float]:
        times = []
        for size in cls.SIZES:
            subject = make(size)
            assert operation(subject) is None
            times.append(best_ns(lambda s=subject: operation(s), repeats=3))
        return [later / earlier for earlier, later in zip(times, times[1:], strict=False)]

    @pytest.mark.timing
    def test_match_makes_one_attempt(self) -> None:
        pattern = re.compile(r"\w+@")

        for operation in (pattern.match, pattern.fullmatch):
            steps = self._steps(operation, lambda size: "a" * size)
            assert all(step < 8 for step in steps), f"4x the subject: steps {steps}"

    @pytest.mark.timing
    def test_search_retries_at_every_position(self) -> None:
        pattern = re.compile(r"\w+@")

        steps = self._steps(pattern.search, lambda size: "a" * size)

        assert all(step > 8 for step in steps), f"4x the subject should cost ~16x: {steps}"

    @pytest.mark.timing
    def test_a_word_boundary_keeps_the_search_linear(self) -> None:
        pattern = re.compile(r"\b\w+@")

        steps = self._steps(pattern.search, lambda size: "a" * size)

        assert all(step < 8 for step in steps), f"4x the subject should cost ~4x: {steps}"

    @pytest.mark.timing
    def test_bounded_failed_attempts_keep_the_search_linear(self) -> None:
        pattern = re.compile(r"\w+@")

        steps = self._steps(pattern.search, lambda size: ("a" * 20 + " ") * (size // 21))

        assert all(step < 8 for step in steps), f"words of 20 characters: steps {steps}"

    def test_both_patterns_find_the_same_match(self) -> None:
        text = "mail alice@example.com"
        loose = re.search(r"\w+@", text)
        bounded = re.search(r"\b\w+@", text)

        assert loose is not None and bounded is not None
        assert loose.group() == bounded.group() == "alice@"


class TestBacktracking:
    """Patterns that can match the same characters in several ways: polynomial
    or exponential in m within one failing attempt."""

    @pytest.mark.timing
    def test_two_repetitions_competing_are_quadratic_in_one_attempt(self) -> None:
        pattern = re.compile(r"a*a*b")
        subjects = ["a" * size for size in (250, 1_000, 4_000)]
        times = [best_ns(lambda s=subject: pattern.match(s), repeats=3) for subject in subjects]

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(8 < step < 40 for step in steps), f"4x the subject should cost ~16x: {steps}"

    @pytest.mark.timing
    def test_overlapping_alternatives_in_a_repetition_multiply_too(self) -> None:
        pattern = re.compile(r"(?:a|aa)+b")
        short = "a" * 16
        longer = "a" * 22

        short_time = best_ns(lambda: pattern.match(short), repeats=3, inner=5)
        longer_time = best_ns(lambda: pattern.match(longer), repeats=3)

        assert longer_time > short_time * 5, f"16 {short_time:.0f} ns, 22 {longer_time:.0f} ns"

    def test_a_nested_quantifier_matches_a_matching_subject_at_once(self) -> None:
        assert re.search(r"(a+)+$", "a" * 20) is not None
        assert re.search(r"(a+)+b", "a" * 20 + "b") is not None

    @pytest.mark.timing
    def test_the_blow_up_needs_a_failing_attempt(self) -> None:
        matching = re.compile(r"(a+)+$")
        failing = re.compile(r"(a+)+b")

        succeeds = best_ns(lambda: matching.search("a" * 18), inner=200)
        fails = best_ns(lambda: failing.search("a" * 18), repeats=3)

        assert fails > succeeds * 1_000, f"match {succeeds:.0f} ns, non-match {fails:.0f} ns"

    @pytest.mark.timing
    def test_each_extra_character_multiplies_the_work(self) -> None:
        pattern = re.compile(r"(a+)+b")

        short = best_ns(lambda: pattern.search("a" * 14), repeats=3, inner=5)
        longer = best_ns(lambda: pattern.search("a" * 18), repeats=3)

        assert longer > short * 8, f"14 chars {short:.0f} ns, 18 chars {longer:.0f} ns"

    @pytest.mark.timing
    def test_removing_the_nesting_settles_it(self) -> None:
        nested = re.compile(r"(a+)+b")
        flat = re.compile(r"a+b")

        nested_time = best_ns(lambda: nested.search("a" * 18), repeats=3)
        flat_time = best_ns(lambda: flat.search("a" * 18), inner=1_000)

        assert nested_time > flat_time * 1_000, f"nested {nested_time:.0f}, flat {flat_time:.0f}"

    @pytest.mark.timing
    @pytest.mark.skipif(not ATOMIC_SUPPORTED, reason="atomic groups are Python 3.11+")
    def test_atomic_and_possessive_forms_settle_it_too(self) -> None:
        nested = re.compile(r"(a+)+b")
        atomic = re.compile(r"(?>a+)+b")
        possessive = re.compile(r"(a++)+b")

        nested_time = best_ns(lambda: nested.search("a" * 18), repeats=3)
        atomic_time = best_ns(lambda: atomic.search("a" * 18), inner=1_000)
        possessive_time = best_ns(lambda: possessive.search("a" * 18), inner=1_000)

        assert nested_time > atomic_time * 1_000, f"{nested_time:.0f} vs {atomic_time:.0f}"
        assert nested_time > possessive_time * 1_000, f"{nested_time:.0f} vs {possessive_time:.0f}"

    @pytest.mark.skipif(ATOMIC_SUPPORTED, reason="3.11 and later accept them")
    def test_before_3_11_the_syntax_is_rejected(self) -> None:
        with pytest.raises(re.error):
            re.compile(r"(?>a+)+b")
        with pytest.raises(re.error):
            re.compile(r"(a++)+b")


class TestBacktrackingStack:
    """The size paragraph: O(1) stack for a single-character repeat, O(m) for
    a repeated group."""

    def test_a_repeated_group_records_each_iteration(self) -> None:
        pattern = re.compile(r"(?:ab)*")
        small = "ab" * 10_000
        large = "ab" * 100_000

        small_peak = peak_bytes(lambda: pattern.fullmatch(small))
        large_peak = peak_bytes(lambda: pattern.fullmatch(large))

        assert large_peak > small_peak * 5, f"20,000 chars {small_peak}, 200,000 {large_peak}"

    def test_a_single_character_repeat_needs_no_stack(self) -> None:
        pattern = re.compile(r"[ab]*")
        subject = "ab" * 1_000_000
        pattern.fullmatch("ab")  # warm

        peak = peak_bytes(lambda: pattern.fullmatch(subject))

        assert peak < 10_000, f"2,000,000 characters peaked at {peak} bytes"


class TestAnchors:
    """From 3.11 a `^` or `\\A` search stops after the first attempt."""

    UNANCHORED = r"start.*end"
    ANCHORED = (r"^start.*end", r"\Astart.*end")

    @pytest.mark.timing
    def test_an_anchor_saves_nothing_when_the_match_is_at_the_start(self) -> None:
        unanchored = re.compile(self.UNANCHORED)
        anchored = re.compile(self.ANCHORED[0])
        text = "start middle end"

        loose = best_ns(lambda: unanchored.search(text), inner=2_000)
        tight = best_ns(lambda: anchored.search(text), inner=2_000)

        assert tight > loose * 0.5, f"unanchored {loose:.0f} ns, anchored {tight:.0f} ns"

    @pytest.mark.timing
    @pytest.mark.skipif(not ANCHOR_SHORT_CIRCUITS, reason="the early exit is Python 3.11+")
    def test_an_anchor_saves_the_retry_when_nothing_matches(self) -> None:
        unanchored = re.compile(self.UNANCHORED)
        haystack = "x" * 100_000
        loose = best_ns(lambda: unanchored.search(haystack), inner=20)

        for spelling in self.ANCHORED:
            anchored = re.compile(spelling)
            tight = best_ns(lambda a=anchored: a.search(haystack), inner=2_000)
            assert loose > tight * 20, f"{spelling}: unanchored {loose:.0f}, anchored {tight:.0f}"

    @pytest.mark.timing
    @pytest.mark.skipif(not ANCHOR_SHORT_CIRCUITS, reason="the early exit is Python 3.11+")
    def test_the_anchored_search_stops_growing_with_the_subject(self) -> None:
        small = "x" * 100_000
        large = "x" * 1_000_000
        for spelling in self.ANCHORED:
            anchored = re.compile(spelling)
            short = best_ns(lambda a=anchored: a.search(small), inner=2_000)
            long = best_ns(lambda a=anchored: a.search(large), inner=2_000)
            assert long < short * 3, f"{spelling}: 100,000 {short:.0f} ns, 1,000,000 {long:.0f} ns"

    @pytest.mark.timing
    def test_a_multiline_caret_still_retries(self) -> None:
        anchored = re.compile(self.ANCHORED[0], re.MULTILINE)
        small = "x" * 100_000
        large = "x" * 1_000_000

        short = best_ns(lambda: anchored.search(small), inner=20)
        long = best_ns(lambda: anchored.search(large), inner=20)

        assert long > short * 4, f"100,000 chars {short:.0f} ns, 1,000,000 chars {long:.0f} ns"

    @pytest.mark.timing
    @pytest.mark.skipif(ANCHOR_SHORT_CIRCUITS, reason="3.11 and later exit early")
    def test_before_3_11_the_anchored_search_grows_with_the_subject(self) -> None:
        anchored = re.compile(self.ANCHORED[0])
        small = "x" * 100_000
        large = "x" * 1_000_000

        short = best_ns(lambda: anchored.search(small), inner=20)
        long = best_ns(lambda: anchored.search(large), inner=20)

        assert long > short * 4, f"100,000 chars {short:.0f} ns, 1,000,000 chars {long:.0f} ns"

    @pytest.mark.timing
    def test_match_is_anchored_on_every_version(self) -> None:
        pattern = re.compile(self.UNANCHORED)
        small = "x" * 100_000
        large = "x" * 1_000_000

        short = best_ns(lambda: pattern.match(small), inner=2_000)
        long = best_ns(lambda: pattern.match(large), inner=2_000)

        assert long < short * 3, f"100,000 chars {short:.0f} ns, 1,000,000 chars {long:.0f} ns"

    def test_both_forms_agree_on_the_answer(self) -> None:
        for text in ("start middle end", "x start middle end", "nothing here"):
            loose = re.search(self.UNANCHORED, text)
            tight = re.search(self.ANCHORED[0], text)

            assert (loose is not None) == ("start" in text and text.endswith("end"))
            assert (tight is not None) == text.startswith("start")


class TestMatchObjectsHoldPositions:
    """The Match table: positions are O(1), text is a copy, and the match
    holds the subject itself."""

    @staticmethod
    def _match_with_group(size: int) -> re.Match[str]:
        found = re.compile(r"a(x+)b").search("a" + "x" * size + "b")
        assert found is not None
        return found

    def test_a_match_does_not_grow_with_the_subject(self) -> None:
        short = re.compile(r"x").search("x" * 10)
        long = re.compile(r"x").search("x" * 1_000_000)
        many = re.compile(r"(x)" * 50).search("x" * 50)
        assert short is not None and long is not None and many is not None

        assert sys.getsizeof(long) == sys.getsizeof(short)
        assert sys.getsizeof(many) > sys.getsizeof(short), "two positions per group"

    def test_string_is_the_subject_itself(self) -> None:
        subject = "a" + "x" * 1_000 + "b"
        found = re.compile(r"a(x+)b").search(subject)
        assert found is not None

        assert found.string is subject

    def test_span_returns_indices_into_the_subject(self) -> None:
        found = self._match_with_group(50)

        assert found.span(1) == (1, 51)
        assert found.start(1) == 1 and found.end(1) == 51
        assert found.string[slice(*found.span(1))] == found.group(1)

    def test_a_proper_substring_is_copied_and_the_whole_subject_is_not(self) -> None:
        whole = re.compile(r"x+").search("x" * 1_000)
        partial = self._match_with_group(1_000)
        assert whole is not None

        assert whole.group(0) is whole.string
        assert partial.group(1) is not partial.string
        assert partial.group(1) == partial[1] == "x" * 1_000

    def test_the_whole_subject_rule_covers_bytes_but_not_bytearray(self) -> None:
        subject = b"x" * 1_000
        mutable = bytearray(subject)
        from_bytes = re.compile(rb"x+").fullmatch(subject)
        from_bytearray = re.compile(rb"x+").fullmatch(mutable)
        assert from_bytes is not None and from_bytearray is not None

        assert from_bytes.group(0) is subject
        assert type(from_bytearray.group(0)) is bytes

    def test_several_arguments_return_a_tuple_of_them(self) -> None:
        found = re.compile(r"(a)(b)?").match("a")
        assert found is not None

        assert found.group(1, 2, 2, 1) == ("a", None, None, "a")

    @pytest.mark.timing
    def test_group_cost_follows_the_captured_length(self) -> None:
        small = self._match_with_group(1_000)
        large = self._match_with_group(1_000_000)

        small_time = best_ns(lambda: small.group(1), inner=2_000)
        large_time = best_ns(lambda: large.group(1), inner=200)

        assert large_time > small_time * 20, f"1,000 {small_time:.0f} ns, 1e6 {large_time:.0f} ns"

    @pytest.mark.timing
    def test_span_does_not_follow_the_captured_length(self) -> None:
        small = self._match_with_group(1_000)
        large = self._match_with_group(1_000_000)

        small_time = best_ns(lambda: small.span(1), inner=5_000)
        large_time = best_ns(lambda: large.span(1), inner=5_000)

        assert large_time < small_time * 10, f"1,000 {small_time:.0f} ns, 1e6 {large_time:.0f} ns"

    @pytest.mark.timing
    def test_groups_pays_once_per_group(self) -> None:
        one = re.compile(r"(x{100})").search("x" * 100)
        many = re.compile(r"(x{100})" * 50).search("x" * 5_000)
        assert one is not None and many is not None

        one_time = best_ns(one.groups, inner=2_000)
        many_time = best_ns(many.groups, inner=2_000)

        assert many_time > one_time * 5, f"1 group {one_time:.0f} ns, 50 {many_time:.0f} ns"

    def test_groupdict_holds_the_named_groups_only(self) -> None:
        found = re.compile(r"(\d+)-(?P<word>\w+)").search("id: 123-abc")
        assert found is not None

        assert found.groupdict() == {"word": "abc"}
        assert found.groups() == ("123", "abc")
        assert found.lastindex == 2 and found.lastgroup == "word"
        assert found.pos == 0 and found.endpos == len("id: 123-abc")

    @pytest.mark.timing
    def test_expand_follows_the_template_length(self, clean_pattern_cache: None) -> None:
        """Captured group held at 1,000 characters and one backreference;
        the template's literal text varies 1,000x."""
        found = re.compile(r"(a+)").fullmatch("a" * 1_000)
        assert found is not None
        brief = r"\1" + "x" * 10_000
        lengthy = r"\1" + "x" * 10_000_000

        for template in (brief, lengthy):
            result = found.expand(template)
            assert len(result) == 1_000 + len(template) - 2
        del result

        short = best_ns(lambda: found.expand(brief), repeats=3, inner=50)
        long = best_ns(lambda: found.expand(lengthy), repeats=3)

        assert long > short * 20, f"10,000 chars {short:.0f} ns, 10,000,000 chars {long:.0f} ns"


class TestFindallAndFinditer:
    """`findall` | O(k + g) space; `finditer` | O(c) to build, O(c) per match."""

    def test_finditer_holds_one_match_at_a_time(self) -> None:
        pattern = re.compile(r"\w+")
        text = " ".join(f"word{index}" for index in range(20_000))

        def walk() -> None:
            for _ in pattern.finditer(text):
                pass

        materialised = peak_bytes(lambda: pattern.findall(text))
        streamed = peak_bytes(walk)

        assert materialised > streamed * 3, f"findall {materialised}, finditer {streamed}"

    def test_findall_holds_the_matched_text_too(self) -> None:
        pattern = re.compile(r"x+")
        short = " ".join(["x" * 5] * 20_000)
        long = " ".join(["x" * 200] * 20_000)

        short_peak = peak_bytes(lambda: pattern.findall(short))
        long_peak = peak_bytes(lambda: pattern.findall(long))

        assert long_peak > short_peak * 2, f"5-char {short_peak}, 200-char {long_peak}"

    def test_two_or_more_groups_give_tuples(self) -> None:
        assert re.findall(r"(\w)(\d)", "a1 b2") == [("a", "1"), ("b", "2")]
        assert re.findall(r"(\w)\d", "a1 b2") == ["a", "b"]

    def test_building_the_iterator_scans_nothing(self, tmp_path: pathlib.Path) -> None:
        """`(a+)+b` over 40 `a`s would take hours to scan, so building its
        iterator in a subprocess with a timeout fails promptly if it scans."""
        source = "import re\nit = re.compile(r'(a+)+b').finditer('a' * 40)\nassert iter(it) is it\n"

        result = _run_block(source, tmp_path, timeout=30)

        assert result.returncode == 0, result.stderr

    def test_building_the_iterator_allocates_per_group(self) -> None:
        """The O(c) in the construction row: two marks per group."""
        none = re.compile("b")
        many = re.compile("(a)" * 1_000 + "b")
        none.finditer("zz")
        many.finditer("zz")  # warm

        none_peak = peak_bytes(lambda: none.finditer("zz"))
        many_peak = peak_bytes(lambda: many.finditer("zz"))

        assert many_peak > none_peak + 8_000, f"0 groups {none_peak}, 1,000 groups {many_peak}"

    @pytest.mark.timing
    def test_each_step_scans_to_the_next_match(self) -> None:
        pattern = re.compile(r"z")

        def second_match(subject: str) -> re.Match[str]:
            found = pattern.finditer(subject)
            next(found)
            return next(found)

        adjacent = "zz"
        distant = "z" + "a" * 200_000 + "z"

        near = best_ns(lambda: second_match(adjacent), inner=2_000)
        far = best_ns(lambda: second_match(distant), inner=20)

        assert far > near * 20, f"adjacent {near:.0f} ns, 200,000 apart {far:.0f} ns"


class TestSubstitution:
    """`sub` | O(s + t + k·t + r) | O(k + t + r): the result and its pieces, a cached
    template expanded at every match, and one function call per match."""

    def test_the_peak_follows_the_result_not_the_subject(self) -> None:
        pattern = re.compile(r"\d")
        subject = "a1" * 1_000
        pattern.sub("x", subject)  # warm

        brief = "x"
        lengthy = "x" * 1_000

        short = peak_bytes(lambda: pattern.sub(brief, subject))
        long = peak_bytes(lambda: pattern.sub(lengthy, subject))

        assert long > short * 20, f"one-char repl {short}, 1,000-char repl {long}"

    def test_the_pieces_cost_space_even_when_the_result_is_empty(self) -> None:
        """The k in O(k + r): deleting every match leaves r at 0."""
        pattern = re.compile("a")
        few = "a" * 1_000
        many = "a" * 100_000
        pattern.sub("", few)  # warm

        few_peak = peak_bytes(lambda: pattern.sub("", few))
        many_peak = peak_bytes(lambda: pattern.sub("", many))

        assert pattern.sub("", many) == ""
        assert many_peak > few_peak * 20, f"1,000 matches {few_peak}, 100,000 {many_peak}"

    def test_a_new_template_costs_its_length_even_without_a_match(
        self, clean_pattern_cache: None
    ) -> None:
        """The t in O(s + t + r): the subject has no match and r is 3."""
        pattern = re.compile(r"(\d)")
        brief = r"\1" + "x" * 10_000
        lengthy = r"\1" + "x" * 1_000_000

        short_peak = peak_bytes(lambda: pattern.sub(brief, "abc"))
        long_peak = peak_bytes(lambda: pattern.sub(lengthy, "abc"))

        assert long_peak > short_peak * 20, f"10,000 chars {short_peak}, 1e6 {long_peak}"

    def test_a_template_is_parsed_once(self, clean_pattern_cache: None) -> None:
        cache = template_cache()
        pattern = re.compile(r"(\d)")

        for _ in range(50):
            assert pattern.sub(r"<\1>", "a1b2") == "a<1>b<2>"

        info = cache.cache_info()
        assert info.misses == 1 and info.hits == 49, info

    @pytest.mark.timing
    def test_a_template_is_expanded_at_every_match(self) -> None:
        """The k·t term: 2,001 empty matches, each expanding backreferences to
        an empty group, so r stays 2,000 while the template grows 1,000x."""
        pattern = re.compile("()")
        subject = "x" * 2_000
        brief, lengthy = r"\1", r"\1" * 1_000
        pattern.sub(brief, "x")  # parse both templates
        pattern.sub(lengthy, "x")

        assert pattern.sub(brief, subject) == pattern.sub(lengthy, subject) == subject
        short = best_ns(lambda: pattern.sub(brief, subject), repeats=3)
        long = best_ns(lambda: pattern.sub(lengthy, subject), repeats=3)

        assert long > short * 20, f"1 backreference {short:.0f} ns, 1,000 {long:.0f} ns"

    def test_a_function_is_called_once_per_match(self) -> None:
        calls: list[str] = []

        def double(match: re.Match[str]) -> str:
            calls.append(match.group())
            return str(int(match.group()) * 2)

        assert re.sub(r"\d+", double, "Numbers: 10, 20, 30") == "Numbers: 20, 40, 60"
        assert calls == ["10", "20", "30"]

    def test_subn_and_split_return_what_the_page_says(self) -> None:
        pattern = re.compile(r"\d+")

        assert pattern.subn("X", "10, 20, 30") == ("X, X, X", 3)
        assert re.split(r"(,)\s*", "a, b") == ["a", ",", "b"]
        assert re.split(r",\s*", "a, b, c", maxsplit=1) == ["a", "b, c"]


class TestPatternAttributes:
    """`Pattern.groupindex` | O(1): returned without copying the mapping."""

    def test_without_named_groups_it_is_a_new_empty_dict(self) -> None:
        pattern = re.compile(r"(a)")

        assert pattern.groupindex == {}
        assert pattern.groupindex is not pattern.groupindex

    def test_with_named_groups_it_is_a_read_only_view(self) -> None:
        pattern = re.compile(r"(?P<head>a)(b)(?P<tail>c)")

        view = pattern.groupindex
        assert isinstance(view, types.MappingProxyType)
        assert dict(view) == {"head": 1, "tail": 3}
        with pytest.raises(TypeError):
            operator.setitem(cast(Any, view), "head", 2)
        assert pattern.groups == 3 and pattern.pattern == r"(?P<head>a)(b)(?P<tail>c)"

    @pytest.mark.timing
    def test_groupindex_does_not_follow_the_group_count(self) -> None:
        one = re.compile(r"(?P<g0>a)")
        many = re.compile("".join(f"(?P<g{index}>a)" for index in range(2_000)))

        one_time = best_ns(lambda: one.groupindex, inner=5_000)
        many_time = best_ns(lambda: many.groupindex, inner=5_000)

        assert many_time < one_time * 3, f"1 group {one_time:.0f} ns, 2,000 {many_time:.0f} ns"


class TestEscape:
    """`re.escape(pattern)` | O(n) | O(n)."""

    def test_the_peak_follows_the_input(self) -> None:
        short = "a.b*" * 25_000
        long = "a.b*" * 250_000

        short_peak = peak_bytes(lambda: re.escape(short))
        long_peak = peak_bytes(lambda: re.escape(long))

        assert long_peak > short_peak * 5, f"100,000 chars {short_peak}, 1,000,000 {long_peak}"

    def test_escaped_text_matches_itself(self) -> None:
        assert re.escape("abc123") == "abc123"
        assert re.escape("a.b*c") == "a\\.b\\*c"
        assert re.fullmatch(re.escape("a.b*c"), "a.b*c") is not None


class TestPatternCache:
    """512 patterns, and one entry dropped on overflow.

    Which entry is dropped is not on the page. From 3.12 a hit that reaches
    the 512-entry cache re-records the entry as most recently used, but a hit
    served by the 256-entry fast-path cache in front of it returns without
    touching it; on 3.10 and 3.11 no hit refreshes an entry. The two
    version-gated tests pin that, through a hit that reaches the main cache.
    """

    def test_the_documented_size_is_the_implementation_size(self) -> None:
        assert MAXCACHE == 512

    def test_the_cache_drops_one_entry_rather_than_emptying(
        self, clean_pattern_cache: None
    ) -> None:
        sizes = []
        for index in range(MAXCACHE + 4):
            re.compile(f"unique-pattern-{index}")
            if index in (0, MAXCACHE - 1, MAXCACHE + 3):
                sizes.append(len(pattern_cache()))

        assert sizes == [1, MAXCACHE, MAXCACHE], f"expected the cache to fill and hold: {sizes}"

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="hits refresh recency from 3.12")
    def test_before_3_12_a_hit_does_not_save_the_oldest_entry(
        self, clean_pattern_cache: None
    ) -> None:
        oldest = re.compile("pattern-oldest")
        for index in range(MAXCACHE - 1):
            re.compile(f"pattern-{index}")
        assert re.compile("pattern-oldest") is oldest, "the entry is present"

        re.compile("pattern-new")  # the 513th pattern

        assert re.compile("pattern-oldest") is not oldest, "the oldest inserted is dropped"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="before 3.12 a hit changes nothing")
    def test_from_3_12_a_hit_saves_the_entry(self, clean_pattern_cache: None) -> None:
        """The 256-entry fast-path cache has long since dropped a pattern
        this old, so the hit reaches the LRU and re-records it."""
        oldest = re.compile("pattern-oldest")
        for index in range(MAXCACHE - 1):
            re.compile(f"pattern-{index}")
        assert re.compile("pattern-oldest") is oldest, "the hit re-records it"

        re.compile("pattern-new")  # the 513th pattern

        assert (str, "pattern-oldest", 0) in pattern_cache(), "the least recently used is dropped"
        assert re.compile("pattern-oldest") is oldest

    @pytest.mark.skipif(MAXCACHE2 is None, reason="the fast-path cache is Python 3.12+")
    def test_the_fast_path_cache_is_smaller(self) -> None:
        assert MAXCACHE2 == 256


class TestFlagsAndExceptions:
    """The Flags and exceptions rows: values and the 3.11 and 3.13 names."""

    def test_the_flags_are_int_flags_with_aliases(self) -> None:
        assert issubclass(re.RegexFlag, int)
        assert re.I is re.IGNORECASE and re.M is re.MULTILINE and re.S is re.DOTALL
        assert re.A is re.ASCII and re.X is re.VERBOSE and re.U is re.UNICODE
        assert re.L is re.LOCALE
        assert isinstance(re.I | re.M, re.RegexFlag)
        assert isinstance(re.DEBUG, re.RegexFlag)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="NOFLAG is Python 3.11+")
    def test_noflag_is_zero(self) -> None:
        assert getattr(re, "NOFLAG") == 0  # noqa: B009 - 3.11+, not in the 3.10 stubs

    def test_the_types_are_what_compile_and_match_return(self) -> None:
        pattern = re.compile("a")
        found = pattern.match("a")

        assert isinstance(pattern, re.Pattern) and isinstance(found, re.Match)

    def test_pattern_error_is_re_error_from_3_13(self) -> None:
        if sys.version_info >= (3, 13):
            assert getattr(re, "PatternError") is re.error  # noqa: B009 - 3.13+
        else:
            assert not hasattr(re, "PatternError")

    def test_the_error_locates_itself(self) -> None:
        with pytest.raises(re.error) as caught:
            re.compile("ab\ncd(")

        error = caught.value
        assert error.pattern == "ab\ncd("
        assert (error.pos, error.lineno, error.colno) == (5, 2, 3)
        assert error.msg == "missing ), unterminated subpattern"


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


def _run_block(
    source: str, cwd: pathlib.Path, timeout: float = 120
) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result.

    The block showing atomic groups guards them behind a version check, so it
    runs on 3.10 too.
    """

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

    def test_the_nested_pattern_runs_only_on_short_subjects(self) -> None:
        """The long call has to stay a comment: running the page is exactly
        what would hang, so the runner cannot check it for itself."""
        blocks = [(line, source) for line, source in _blocks() if "bad_pattern" in source]
        assert len(blocks) == 1, f"expected one backtracking block, found {blocks}"
        line, source = blocks[0]

        live = [
            statement
            for statement in source.splitlines()
            if "bad_pattern.search" in statement and not statement.lstrip().startswith("#")
        ]
        assert live, "the nested pattern should still be exercised"
        for statement in live:
            repetition = re.search(r"'a' \* (\d+)", statement)
            assert repetition is not None, f"{PAGE.name}:{line}: {statement}"
            assert int(repetition.group(1)) <= 8, (
                f"{PAGE.name}:{line} runs the blow-up: {statement}"
            )

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "match.span(1) == (4, 7)" in s)
        mutated = source.replace("match.span(1) == (4, 7)", "match.span(1) == (4, 8)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
