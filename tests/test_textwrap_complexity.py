"""Tests for docs/stdlib/textwrap.md.

The page prices every function at one pass over the whole text, with one
exception: a word longer than a line is broken one line at a time, and each
break copies the rest of the word. Space bounds and the claims that
`shorten()` and `max_lines` still split the whole text are settled by traced
allocation at a fixed width while the text grows; the long-word term and the
linear functions are settled by timing ratios across a 16x or 10x size step;
the option and output claims are settled by observation.

Measurement scope:

* The long-word term: at width 8, one word grown from 25,000 to 400,000
  characters costs more than 40x (linear predicts 16x, quadratic 256x), while
  7-letter words over the same lengths cost under 32x, and so does the long
  word with `break_long_words=False`. A run of whitespace between two letters
  over the same lengths costs more than 40x with `drop_whitespace=False` and
  under 32x without it; a run at the start of the text, grown from 6,250 to
  100,000 characters, costs more than 40x. The mechanism, `chunk[end:]` in
  `_handle_long_word`, is read from Lib/textwrap.py and is the same on every
  supported release.
* `wrap()` space: the traced peak over 7-letter words grows more than 5x and
  less than 20x from 10,000 to 100,000 characters.
* `shorten()` at width 20 and `wrap(max_lines=1)` at width 70 have traced
  peaks that grow more than 5x and less than 20x from 10,000 to 100,000
  characters while their output stays within one line.
* `dedent()` and `indent()` over 12-character lines: each 10x step from
  10,000 to 1,000,000 characters costs under 30x (quadratic predicts 100x),
  and their peaks grow more than 5x and less than 20x per step. The m·p
  term of `indent()` is a peak that grows more than 5x as the prefix goes
  from 1 to 1,000 characters over 10,000 lines of three characters.
* `indent()` calls its predicate exactly once per line, with the line ending
  attached; by default it skips lines that are only whitespace.
* `TextWrapper()` construction peaks under 5 KB, and `wordsep_re` and
  `wordsep_simple_re` are the same objects on every instance and on the
  class. The module functions are observed to build one `TextWrapper` per
  call. Changing `width` on an instance changes its next `wrap()`.
* `fill()` is asserted equal to `'\\n'.join(wrap())`; `shorten()` is asserted
  to return at most `width` characters, to ignore `expand_tabs` and
  `replace_whitespace`, and to use its placeholder; `break_long_words=False`
  (including a break after a hyphen while `break_on_hyphens` is on),
  `fix_sentence_endings` and `max_lines` are asserted by output.
* `dedent()` is asserted to blank lines of only spaces and tabs without
  letting them narrow the margin, and to find no common margin between a tab
  and spaces. A line holding another whitespace character, such as `\r`, is
  blanked and ignored from 3.14 and keeps the margin at zero before it; both
  sides are asserted, guarded on `sys.version_info`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Counting n after tab expansion, and treating `initial_indent`,
  `subsequent_indent` and `placeholder` as constant length and shorter than
  `width`, are definitional choices. The output repeats the indent on every line, so a long indent
  adds its length times the lines produced.
* The O(n + n·k/w) bound with several long words sums one O(k²/w) term per
  word and is read from Lib/textwrap.py; only a single long word is timed.
* Whether `wordsep_re` stays linear on adversarial input. The timed inputs
  are 7-letter words, one run of a single letter and runs of spaces; hyphens,
  punctuation and mixed whitespace are not varied.
* A caller's `indent()` predicate cost is outside the bound by definition.
* The audit lists `TextWrapper.wordsep_re`, `wordsep_simple_re`,
  `sentence_end_re` and `unicode_whitespace_trans` as needing
  classification: they are undocumented class attributes, compiled or built
  once at import, and are not documented on the page.
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "textwrap.md"
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


def words(length: int) -> str:
    """`length` characters of 7-letter words, each followed by a space."""
    return "abcdefg " * (length // 8)


def indented_lines(length: int) -> str:
    """`length` characters of 12-character lines with a four-space margin."""
    return "    abc def\n" * (length // 12)


class TestLongWordsAreCopiedPerLine:
    """`wrap` | O(n + n·k/w): a word longer than a line copies its remainder
    once per line, so one word of n characters costs O(n²/w).

    A 16x step separates linear (16x) from quadratic (256x); ordinary words
    over the same lengths are the control that the step itself is linear.
    """

    SIZES = (25_000, 400_000)

    @staticmethod
    def growth(
        text_of: Callable[[int], str], sizes: tuple[int, int] = SIZES, **kwargs: Any
    ) -> float:
        small, large = (text_of(size) for size in sizes)
        small_ns = best_ns(lambda: textwrap.wrap(small, 8, **kwargs), repeats=3)
        large_ns = best_ns(lambda: textwrap.wrap(large, 8, **kwargs), repeats=3)
        return large_ns / small_ns

    @pytest.mark.timing
    def test_one_long_word_grows_faster_than_linear(self) -> None:
        ratio = self.growth(lambda size: "x" * size)

        assert ratio > 40, f"16x the word cost x{ratio:.1f}; linear is 16, quadratic 256"

    @pytest.mark.timing
    def test_ordinary_words_grow_linearly(self) -> None:
        ratio = self.growth(words)

        assert ratio < 32, f"16x the words cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_leading_whitespace_is_a_long_word(self) -> None:
        ratio = self.growth(lambda size: " " * size + "a", sizes=(6_250, 100_000))

        assert ratio > 40, f"16x the leading whitespace cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_inner_whitespace_is_a_long_word_only_when_kept(self) -> None:
        kept = self.growth(lambda size: "a" + " " * size + "b", drop_whitespace=False)
        dropped = self.growth(lambda size: "a" + " " * size + "b")

        assert kept > 40, f"16x the kept whitespace cost x{kept:.1f}"
        assert dropped < 32, f"16x the dropped whitespace cost x{dropped:.1f}"

    @pytest.mark.timing
    def test_keeping_the_word_whole_is_linear(self) -> None:
        ratio = self.growth(lambda size: "x" * size, break_long_words=False)

        assert ratio < 32, f"16x the unbroken word cost x{ratio:.1f}"

    def test_the_word_is_broken_into_full_lines(self) -> None:
        blob = "x" * 10_000

        lines = textwrap.wrap(blob, width=76)

        assert lines == [blob[i : i + 76] for i in range(0, len(blob), 76)]

    def test_break_long_words_false_gives_the_word_its_own_line(self) -> None:
        long = "x" * 30

        assert textwrap.wrap("ab " + long + " cd", 10, break_long_words=False) == [
            "ab",
            long,
            "cd",
        ]

    def test_break_on_hyphens_still_breaks_an_unbroken_word(self) -> None:
        assert textwrap.wrap("alpha-beta", 6, break_long_words=False) == ["alpha-", "beta"]
        assert textwrap.wrap("alpha-beta", 6, break_long_words=False, break_on_hyphens=False) == [
            "alpha-beta"
        ]


class TestWrapAndFill:
    """`wrap` and `fill` | O(n) space; `fill` is `wrap` joined with newlines,
    and the text is one paragraph."""

    def test_the_peak_follows_the_text(self) -> None:
        small, large = words(10_000), words(100_000)

        peaks = [peak_bytes(lambda t=text: textwrap.wrap(t, 70)) for text in (small, large)]  # type: ignore[misc]

        assert peaks[0] * 5 < peaks[1] < peaks[0] * 20, f"10x the text peaked at {peaks}"

    def test_fill_is_wrap_joined(self) -> None:
        text = words(1_000)

        assert textwrap.fill(text, 30) == "\n".join(textwrap.wrap(text, 30))

    def test_a_newline_is_whitespace(self) -> None:
        assert textwrap.wrap("one\ntwo\n\nthree", 40) == ["one two  three"]
        assert textwrap.wrap("one\ntwo", 20) == ["one two"]

    def test_fix_sentence_endings_puts_two_spaces(self) -> None:
        text = "Hi there. Bye now."

        assert textwrap.wrap(text, 40, fix_sentence_endings=True) == ["Hi there.  Bye now."]
        assert textwrap.wrap(text, 40) == ["Hi there. Bye now."]


class TestTruncationSplitsTheWholeText:
    """`shorten` | O(n) | O(n) although the result is at most `width`; and
    `max_lines` stops building lines only after the whole text is split."""

    def test_shorten_peak_follows_the_text_not_the_width(self) -> None:
        small, large = words(10_000), words(100_000)

        peaks = [peak_bytes(lambda t=text: textwrap.shorten(t, 20)) for text in (small, large)]  # type: ignore[misc]

        assert textwrap.shorten(large, 20) == textwrap.shorten(small, 20)
        assert peaks[0] * 5 < peaks[1] < peaks[0] * 20, f"10x the text at width 20: {peaks}"

    def test_max_lines_peak_follows_the_text(self) -> None:
        small, large = words(10_000), words(100_000)

        peaks = [
            peak_bytes(lambda t=text: textwrap.wrap(t, 70, max_lines=1))  # type: ignore[misc]
            for text in (small, large)
        ]

        assert len(textwrap.wrap(large, 70, max_lines=1)) == 1
        assert peaks[0] * 5 < peaks[1] < peaks[0] * 20, f"10x the text at max_lines=1: {peaks}"

    @pytest.mark.parametrize("width", [12, 20, 40, 100])
    def test_shorten_fits_the_width(self, width: int) -> None:
        text = "The quick brown fox jumps over the lazy dog"

        assert len(textwrap.shorten(text, width)) <= width

    def test_shorten_ignores_the_whitespace_options(self) -> None:
        text = "a\tb\n\nc"

        assert textwrap.shorten(text, 20, expand_tabs=False, replace_whitespace=False) == "a b c"
        assert textwrap.shorten(text, 20) == "a b c"

    def test_placeholder_and_max_lines_by_output(self) -> None:
        text = "The quick brown fox jumps over the lazy dog"

        assert textwrap.shorten(text, 20) == "The quick [...]"
        assert textwrap.shorten(text, 20, placeholder="...") == "The quick brown..."
        assert textwrap.wrap(text, 15, max_lines=2) == ["The quick brown", "fox jumps [...]"]


class TestDedentAndIndent:
    """`dedent` | O(n) | O(n) and `indent` | O(n + m·p) | O(n + m·p); the
    predicate is called once per line."""

    SIZES = (10_000, 100_000, 1_000_000)

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["dedent", "indent"])
    def test_each_10x_step_costs_under_30x(self, name: str) -> None:
        operation: Callable[[str], str] = (
            textwrap.dedent if name == "dedent" else lambda t: textwrap.indent(t, "> ")
        )
        texts = [indented_lines(size) for size in self.SIZES]
        durations = [best_ns(lambda t=text: operation(t)) for text in texts]  # type: ignore[misc]
        ratios = [durations[1] / durations[0], durations[2] / durations[1]]

        assert all(ratio < 30 for ratio in ratios), f"{name}: {durations} ns, ratios {ratios}"

    @pytest.mark.parametrize("name", ["dedent", "indent"])
    def test_the_peak_follows_the_text(self, name: str) -> None:
        operation: Callable[[str], str] = (
            textwrap.dedent if name == "dedent" else lambda t: textwrap.indent(t, "> ")
        )
        texts = [indented_lines(size) for size in self.SIZES]

        peaks = [peak_bytes(lambda t=text: operation(t)) for text in texts]  # type: ignore[misc]

        steps = [peaks[1] / peaks[0], peaks[2] / peaks[1]]
        assert all(5 < step < 20 for step in steps), f"{name}: {peaks}"

    def test_indent_output_grows_with_the_prefix(self) -> None:
        text = "ab\n" * 10_000

        peaks = [
            peak_bytes(lambda p=prefix: textwrap.indent(text, p))  # type: ignore[misc]
            for prefix in ("#", "#" * 1_000)
        ]

        assert len(textwrap.indent(text, "#" * 1_000)) == 10_000 * 1_003
        assert peaks[1] > peaks[0] * 5, f"a 1,000x longer prefix peaked at {peaks}"

    def test_the_predicate_sees_each_line_once(self) -> None:
        seen: list[str] = []

        def every_line(line: str) -> bool:
            seen.append(line)
            return True

        result = textwrap.indent("first\n\nsecond\n", "> ", every_line)

        assert seen == ["first\n", "\n", "second\n"]
        assert result == "> first\n> \n> second\n"

    def test_by_default_whitespace_only_lines_are_skipped(self) -> None:
        assert textwrap.indent("a\n  \n\nb", "> ") == "> a\n  \n\n> b"

    def test_dedent_blanks_whitespace_only_lines_without_narrowing(self) -> None:
        assert textwrap.dedent("  a\n    \n  b") == "a\n\nb"
        assert textwrap.dedent("    a\n  \n    b\n") == "a\n\nb\n"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="3.14 blanks any whitespace line")
    def test_any_whitespace_only_line_is_ignored_from_314(self) -> None:
        assert textwrap.dedent("  a\n\r\n  b") == "a\n\nb"

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="before 3.14 only spaces and tabs")
    def test_another_whitespace_character_holds_the_margin_before_314(self) -> None:
        assert textwrap.dedent("  a\n\r\n  b") == "  a\n\r\n  b"

    def test_a_tab_and_spaces_share_no_margin(self) -> None:
        assert textwrap.dedent("  a\n\tb") == "  a\n\tb"
        assert textwrap.dedent("\ta\n\tb") == "a\nb"


class TestTextWrapperHoldsOnlyItsOptions:
    """`TextWrapper()` | O(1) | O(1); its expressions are compiled at import,
    the module functions build one per call, and options are read per call."""

    def test_construction_allocates_almost_nothing(self) -> None:
        textwrap.TextWrapper(width=40)  # warm

        peak = peak_bytes(lambda: textwrap.TextWrapper(width=40, initial_indent="* "))

        assert peak < 5_000, f"TextWrapper() allocated {peak} bytes"

    def test_the_expressions_are_shared_by_every_instance(self) -> None:
        first, second = textwrap.TextWrapper(), textwrap.TextWrapper(width=10)

        assert first.wordsep_re is second.wordsep_re is textwrap.TextWrapper.wordsep_re
        assert first.wordsep_simple_re is textwrap.TextWrapper.wordsep_simple_re
        assert "wordsep_re" not in vars(first)

    def test_the_module_functions_build_one_wrapper_per_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        built: list[int] = []

        class Counting(textwrap.TextWrapper):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                built.append(1)
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(textwrap, "TextWrapper", Counting)

        for call in (textwrap.wrap, textwrap.fill, textwrap.shorten):
            before = len(built)
            call("a b", 10)
            assert len(built) == before + 1, call.__name__

    def test_options_are_read_on_every_call(self) -> None:
        wrapper = textwrap.TextWrapper(width=20, initial_indent="* ", subsequent_indent="  ")
        text = "one two three four five six seven"

        assert wrapper.wrap(text) == ["* one two three four", "  five six seven"]

        wrapper.width = 12

        assert wrapper.fill(text) == "* one two\n  three four\n  five six\n  seven"

    def test_the_version_noted_options_exist(self) -> None:
        wrapper = textwrap.TextWrapper()

        assert (wrapper.tabsize, wrapper.max_lines, wrapper.placeholder) == (8, None, " [...]")
        assert callable(textwrap.indent) and callable(textwrap.shorten)


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
        line, source = next((n, s) for n, s in _blocks() if "len(lines) == 132" in s)
        mutated = source.replace("len(lines) == 132", "len(lines) == 131", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
