"""Tests for docs/stdlib/shlex.md.

The page prices the lexer per character read plus the square of each token's
length, because a token grows by one string concatenation per character. The
quadratic term is read from Lib/shlex.py's `self.token += nextchar` and
checked by timing: at a fixed total length, one token against many short ones,
and that gap widening as the total grows; construction, laziness and the
per-token space are settled by traced allocation and stream positions, which
need no tolerance; the stack, pushback and attribute rows are settled by
observation.

Measurement scope:

* `split()` over tokens of one character grows each time the input grows 4x,
  from 40,000 to 160,000 to 640,000 characters, by under 8x per step: linear
  predicts 4x and quadratic 16x. At 200,000 characters, one token costs more
  than 4x what 100,000 one-character tokens of the same total cost, bare and
  double-quoted, and that gap is more than twice the one at 25,000 characters:
  the k² term predicts 8x, a shape-dependent constant 1x. Locally the gaps are
  about 2x and 12x. The peak allocation of `split()` grows more than 20x from 10,000
  to 1,000,000 characters.
* `get_token()` on a stream of 1,000,000 characters in short tokens peaks
  under 5 KB, and a 100,000-character token peaks above 100 KB, so its space is
  the token, not the input. A 100,000-character comment line before the token
  peaks above 100 KB, and 100,000 spaces before it under 5 KB. `split()` is
  observed to take one `read_token()` per token plus one for the end, which is
  why the `get_token()`, `read_token()` and iteration rows share its per-token
  bound.
* `shlex()` and `push_source()` over a 1,000,000-character stream peak under
  5 KB and leave the stream at offset 0; over the same text as a `str`, both
  peak above 1,000,000 bytes. The first `get_token()` on that stream leaves it
  a few characters in.
* `push_token()` is observed to be returned last-in first-out without moving
  the stream; `read_token()` to ignore a pushed token; `pop_source()` to close
  the stream it leaves and restore the file name, stream and line number;
  `get_token()` to pop an exhausted pushed source, and three stacked empty
  ones in a single call; `sourcehook()` to open a
  file named by the token after the `source` keyword, relative to `infile`;
  and `error_leader()` to format the file name and line.
* `quote()` returns a safe non-empty string itself, `''` for the empty
  string, and single-quotes anything else; `join()` round-trips through
  `split()`, and 1,000 empty arguments join to 1,000 `''` pairs. `quote()`
  over 30,000 to 3,000,000 characters and `join()` over 7,500 to 750,000
  three-character arguments each grow by under 30x per 10x step: linear
  predicts 10x and quadratic 100x. Only time is measured; their space bounds
  are read from Lib/shlex.py.
* `split(None)` raises `ValueError` from 3.12, and on 3.10 and 3.11 warns with
  `DeprecationWarning` and reads `sys.stdin`; the test is guarded on
  `sys.version_info`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Pricing membership in `wordchars`, `whitespace` and the other character
  classes at O(1) is a cost-model assumption; they are scanned per input
  character, so a class grown to thousands of characters is outside the
  bounds. Changing a class is asserted to change the tokens only.
* The cost of the `open()` in `sourcehook()` belongs to the filesystem, and
  `source` inclusion is outside the lexer bounds, as the page says.
* `get_token()` recurses once per exhausted source it pops, so a deep stack
  of empty sources costs recursion space as well as time; only a stack of
  three is exercised.
* `debug` is left at 0, and the timing and allocation tests read only an
  `io.StringIO` or a `str`; a custom `read()`, `readline()` or `close()` can
  dominate every bound.
* Streams other than `io.StringIO`, non-ASCII text, comment-heavy input and
  `punctuation_chars` runs are not varied in the timing tests; the quadratic
  token is measured in POSIX mode with `whitespace_split` on, as `split()`
  runs it.
"""

from __future__ import annotations

import io
import itertools
import pathlib
import re
import shlex
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "shlex.md"
EXPECTED_BLOCKS = 7


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


def short_tokens(length: int) -> str:
    """`length` characters of one-character tokens."""
    return "x " * (length // 2)


class TestSplitIsLinearForShortTokens:
    """`split(s)` | O(n + Σk²) | O(n): with k fixed at one, only n moves."""

    @pytest.mark.timing
    def test_four_times_the_input_is_far_from_sixteen_times(self) -> None:
        texts = [short_tokens(size) for size in (40_000, 160_000, 640_000)]
        durations = [best_ns(lambda t=text: shlex.split(t)) for text in texts]
        ratios = [later / earlier for earlier, later in itertools.pairwise(durations)]

        assert all(ratio < 8 for ratio in ratios), (
            f"4x steps of short tokens took {durations} ns, ratios {ratios}; "
            "linear predicts 4x and quadratic 16x"
        )

    def test_the_peak_follows_the_input(self) -> None:
        small = short_tokens(10_000)
        large = short_tokens(1_000_000)

        peaks = [peak_bytes(lambda: shlex.split(small)), peak_bytes(lambda: shlex.split(large))]

        assert peaks[1] > peaks[0] * 20, f"100x the input peaked at {peaks}"

    def test_split_takes_one_raw_read_per_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reads: list[object] = []
        original = shlex.shlex.read_token

        def counting(self: shlex.shlex) -> Any:
            token = original(self)
            reads.append(token)
            return token

        monkeypatch.setattr(shlex.shlex, "read_token", counting)

        assert shlex.split("a bb 'c c'") == ["a", "bb", "c c"]
        assert reads == ["a", "bb", "c c", None]


class TestALongTokenIsQuadratic:
    """`split` and `get_token` pay O(k²) for a k-character token. At a fixed
    total length, one token costs far more than many one-character ones, and
    that gap widens as the total grows: a k² term predicts 8x wider for 8x the
    total, and a shape-dependent constant predicts no change."""

    @staticmethod
    def gap(total: int, quoted: bool) -> float:
        one = "x" * total
        if quoted:
            one = '"' + one[2:] + '"'
        many = short_tokens(total)
        assert len(one) == len(many)
        assert len(shlex.split(one)) == 1
        assert len(shlex.split(many)) == total // 2

        one_ns = best_ns(lambda: shlex.split(one))
        many_ns = best_ns(lambda: shlex.split(many))
        return one_ns / many_ns

    @pytest.mark.timing
    @pytest.mark.parametrize("quoted", [False, True], ids=["bare", "quoted"])
    def test_one_token_s_extra_cost_grows_with_its_length(self, quoted: bool) -> None:
        small = self.gap(25_000, quoted)
        large = self.gap(200_000, quoted)

        assert large > 4, f"one 200,000-character token cost x{large:.2f} of short tokens"
        assert large > small * 2, (
            f"the one-token gap went from x{small:.2f} at 25,000 characters to "
            f"x{large:.2f} at 200,000; a k² term predicts 8x wider, a constant 1x"
        )


class TestTheLexerHoldsOneToken:
    """`shlex()` | O(1) for a stream, O(n) for a `str`; `get_token()` |
    O(k + m) space, stopping once it has a token."""

    TEXT = "run --fast target\n" * 55_556  # about 1,000,000 characters

    def test_a_stream_is_not_read_at_construction(self) -> None:
        stream = io.StringIO(self.TEXT)

        peak = peak_bytes(lambda: shlex.shlex(stream, posix=True))

        assert stream.tell() == 0
        assert peak < 5_000, f"shlex() over a stream allocated {peak} bytes"

    def test_a_str_is_copied_at_construction(self) -> None:
        text = self.TEXT

        peak = peak_bytes(lambda: shlex.shlex(text, posix=True))

        assert peak > len(text), f"shlex() over {len(text)} characters allocated {peak} bytes"

    def test_the_first_token_reads_only_that_token(self) -> None:
        stream = io.StringIO(self.TEXT)
        lexer = shlex.shlex(stream, posix=True)
        lexer.whitespace_split = True

        assert lexer.get_token() == "run"
        assert stream.tell() < 10

    def test_get_token_space_follows_the_token_not_the_input(self) -> None:
        lexer = shlex.shlex(io.StringIO(self.TEXT), posix=True)
        lexer.whitespace_split = True
        lexer.get_token()
        short_peak = peak_bytes(lexer.get_token)

        long_lexer = shlex.shlex(io.StringIO("y" * 100_000), posix=True)
        long_peak = peak_bytes(long_lexer.get_token)

        assert short_peak < 5_000, f"a short token over a 1 MB stream peaked at {short_peak}"
        assert long_peak > 100_000, f"a 100,000-character token peaked at {long_peak}"

    def test_a_skipped_comment_line_is_read_whole(self) -> None:
        commented = shlex.shlex(io.StringIO("#" + "c" * 100_000 + "\nabc"), posix=True)
        spaced = shlex.shlex(io.StringIO(" " * 100_000 + "abc"), posix=True)

        commented_peak = peak_bytes(commented.get_token)
        spaced_peak = peak_bytes(spaced.get_token)

        assert commented_peak > 100_000, f"a 100,000-character comment peaked at {commented_peak}"
        assert spaced_peak < 5_000, f"100,000 skipped spaces peaked at {spaced_peak}"

    def test_iteration_stops_at_eof(self) -> None:
        assert list(shlex.shlex("a b", posix=True)) == ["a", "b"]
        assert list(shlex.shlex("a b")) == ["a", "b"]
        assert shlex.shlex("a", posix=True).eof is None
        assert shlex.shlex("a").eof == ""


class TestPushbackAndSources:
    """The pushback and source-stack rows: what `push_token`, `read_token`,
    `push_source`, `pop_source`, `sourcehook` and `error_leader` do, and that
    `push_source` reads nothing from a stream but copies a `str`."""

    def test_pushed_tokens_come_back_last_in_first_out_without_reading(self) -> None:
        stream = io.StringIO("a b")
        lexer = shlex.shlex(stream)
        lexer.push_token("z")
        lexer.push_token("y")

        assert lexer.get_token() == "y"
        assert lexer.get_token() == "z"
        assert stream.tell() == 0
        assert lexer.get_token() == "a"

    def test_read_token_ignores_pushback(self) -> None:
        lexer = shlex.shlex("a b")
        lexer.push_token("pushed")

        assert lexer.read_token() == "a"
        assert lexer.get_token() == "pushed"

    def test_push_source_does_not_read_a_stream_and_copies_a_str(self) -> None:
        lexer = shlex.shlex("outer")
        stream = io.StringIO(TestTheLexerHoldsOneToken.TEXT)
        text = TestTheLexerHoldsOneToken.TEXT

        stream_peak = peak_bytes(lambda: lexer.push_source(stream))
        str_peak = peak_bytes(lambda: lexer.push_source(text))

        assert stream.tell() == 0
        assert stream_peak < 5_000, f"push_source() of a stream allocated {stream_peak} bytes"
        assert str_peak > len(text), f"push_source() of a str allocated {str_peak} bytes"

    def test_pop_source_closes_the_stream_and_restores_state(self) -> None:
        lexer = shlex.shlex("a\nb\nc", infile="outer.txt")
        lexer.get_token()
        lexer.get_token()
        outer = lexer.instream
        inner = io.StringIO("x")

        lexer.push_source(inner, "inner.txt")
        assert (lexer.infile, lexer.lineno) == ("inner.txt", 1)
        lexer.pop_source()

        assert inner.closed
        assert lexer.instream is outer
        assert (lexer.infile, lexer.lineno) == ("outer.txt", 3)

    def test_an_exhausted_source_is_popped_by_get_token(self) -> None:
        lexer = shlex.shlex("outer1 outer2", posix=True)
        assert lexer.get_token() == "outer1"

        lexer.push_source("inner", "included.txt")

        assert lexer.get_token() == "inner"
        assert lexer.error_leader() == '"included.txt", line 1: '
        assert lexer.get_token() == "outer2"
        assert lexer.infile is None
        assert lexer.get_token() is None

    def test_get_token_pops_every_exhausted_source_on_the_way(self) -> None:
        lexer = shlex.shlex("outer", posix=True)
        empties = [io.StringIO("") for _ in range(3)]
        for stream in empties:
            lexer.push_source(stream)

        assert lexer.get_token() == "outer"
        assert all(stream.closed for stream in empties)

    def test_a_source_keyword_opens_the_named_file(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "inc").write_text("included", encoding="utf-8")
        outer = tmp_path / "main.txt"
        with outer.open("w+", encoding="utf-8") as handle:
            handle.write("before source inc after")
            handle.seek(0)
            lexer = shlex.shlex(handle, infile=str(outer))
            lexer.source = "source"

            assert list(lexer) == ["before", "included", "after"]

    def test_error_leader_formats_the_file_and_line(self) -> None:
        lexer = shlex.shlex("a\nb", infile="conf.txt")
        lexer.get_token()
        lexer.get_token()

        assert lexer.error_leader() == '"conf.txt", line 2: '
        assert lexer.error_leader("other", 9) == '"other", line 9: '


class TestCharacterClasses:
    """The character-class attributes change which tokens come out, and
    `punctuation_chars` is fixed at construction."""

    def test_wordchars_decides_what_joins_a_word(self) -> None:
        default = shlex.shlex("user@example.com")
        widened = shlex.shlex("user@example.com")
        widened.wordchars += "@."

        assert list(default) == ["user", "@", "example", ".", "com"]
        assert list(widened) == ["user@example.com"]

    def test_commenters_and_quotes_are_configurable(self) -> None:
        lexer = shlex.shlex("a ; b", posix=True)
        lexer.commenters = ";"
        assert list(lexer) == ["a"]

        lexer = shlex.shlex("|a b|", posix=True)
        lexer.quotes = "|"
        assert list(lexer) == ["a b"]

    def test_punctuation_chars_is_read_only(self) -> None:
        lexer = shlex.shlex("a;b", punctuation_chars=True)

        assert lexer.punctuation_chars == "();<>|&"
        assert list(lexer) == ["a", ";", "b"]
        with pytest.raises(AttributeError):
            lexer.punctuation_chars = "x"  # type: ignore[misc]

    def test_lineno_counts_lines_read(self) -> None:
        lexer = shlex.shlex("a\nb\nc")
        assert lexer.lineno == 1
        list(lexer)
        assert lexer.lineno == 3


class TestQuoteAndJoin:
    """`quote(s)` | O(n) | O(n) and `join(args)` | O(n + a) | O(n + a)."""

    def test_a_safe_string_is_returned_itself(self) -> None:
        safe = "file_name-1.0/path:x=y@z%+,"

        assert shlex.quote(safe) is safe

    def test_anything_else_is_single_quoted(self) -> None:
        assert shlex.quote("") == "''"
        assert shlex.quote("a b") == "'a b'"
        assert shlex.quote("it's") == "'it'\"'\"'s'"
        assert shlex.quote("é") == "'é'"

    def test_join_pays_for_each_argument_even_an_empty_one(self) -> None:
        assert shlex.join([""] * 1_000) == " ".join(["''"] * 1_000)

    def test_join_round_trips_through_split(self) -> None:
        args = ["echo", "Hello World", "$HOME", "it's", ""]

        assert shlex.split(shlex.join(args)) == args

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["quote", "join"])
    def test_ten_times_the_input_is_far_from_a_hundred_times(self, name: str) -> None:
        operations: list[Callable[[], Any]] = []
        for size in (30_000, 300_000, 3_000_000):
            if name == "quote":
                text = "a'b " * (size // 4)
                operations.append(lambda t=text: shlex.quote(t))
            else:
                args = ["a b"] * (size // 4)
                operations.append(lambda a=args: shlex.join(a))
        durations = [best_ns(operation, repeats=3) for operation in operations]
        ratios = [later / earlier for earlier, later in itertools.pairwise(durations)]

        assert all(ratio < 30 for ratio in ratios), (
            f"{name}: 10x steps took {durations} ns, ratios {ratios}; "
            "linear predicts 10x and quadratic 100x"
        )


class TestSplitNone:
    """Version Notes: `split(None)` raises from 3.12; earlier it warns and
    reads `sys.stdin`."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="raises from 3.12")
    def test_it_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be None"):
            shlex.split(None)  # type: ignore[arg-type]

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="warns before 3.12")
    def test_it_warns_and_reads_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("from stdin"))

        with pytest.warns(DeprecationWarning):
            assert shlex.split(None) == ["from", "stdin"]  # type: ignore[arg-type]


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
        line, source = next((n, s) for n, s in _blocks() if "stream.tell() < 10" in s)
        mutated = source.replace("stream.tell() < 10", "stream.tell() < 2", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
