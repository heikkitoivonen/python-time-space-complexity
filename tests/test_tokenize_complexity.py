"""Tests for docs/stdlib/tokenize.md.

The page prices tokenizing as linear in the source with memory bounded by one
line, encoding detection as the first two lines, and `untokenize()` as the
tokens plus the text they write back. Nearly every row is settled by
observation: a counting `readline`, an identity check on the shared line
string, a `tracemalloc` peak that ignores the line count, the bytes handed to
`detect_encoding()`, the length of the text `untokenize()` produces.

Measurement scope:

* Laziness is a counting `readline`. Creating the generator calls it zero
  times; the first token of line 1 costs one call and the first token of line
  2 a second, with no read-ahead. `tokenize()` on bytes calls it once for the
  `ENCODING` token and not again before the second token. Stopping after the
  first token of a 10,000-line source leaves 9,999 lines unread.
* Space is a `tracemalloc` peak over the generator drained without keeping
  its tokens. 32x the lines, at a fixed line length, leaves the peak within
  1.5x; 32x the longest line, at a fixed line count, raises it by more than
  4x and less than 64x; a triple-quoted string spanning 32x the lines does
  the same. Sizes are 1,000 and 32,000 lines or characters; the upper bound
  excludes growth that is quadratic in the line. Token width within a line, non-ASCII
  content and indentation depth are not varied.
* Time is two timing tests on ASCII sources. 8x the tokens across 8x the
  lines costs between 4x and 16x; the same token count on one line and on
  many lines costs within 2x of each other. Non-ASCII columns, which the C
  tokenizer converts from byte offsets, are not varied.
* The shared `line` string is an identity check over every token on one
  line, and the ENDMARKER's empty line is asserted separately.
* `detect_encoding()` is the counting `readline` again, over ten shapes of
  header ahead of a 1.2 MB body: the calls made, the bytes handed out and the
  lines returned. A byte-order mark ahead of a blank line reads the second
  line like any other blank first line. A one-megabyte first line without a cookie is handed out
  whole, which is the O(h) rather than O(1). The three `SyntaxError` paths
  are asserted on their messages.
* `open()` is a patched `_builtin_open` returning a buffered reader that
  records each line read: one line of eighteen bytes from a file of half a
  million lines, and the stream positioned at byte 0 afterwards.
* `untokenize()` is settled by length. A token placed at column 100,000
  produces 100,000 characters of output from a four-token stream, two tokens
  placed at columns 100,000 and 100,001 produce no space between them, and
  the first stream as two-tuples produces five characters. Round-tripping is asserted equal to the
  source on a nested, commented input; the compat spacing is asserted
  literally. The claim stops at a line: a backslash continuation comes back
  with the space before it from 3.12 and without it up to 3.11, which is
  asserted on both sides. The `t` term is two timing tests: 4x the tokens at a fixed
  token width, which scales c with t, costs between 2.5x and 8x; 3x the
  tokens at a fixed 200,000-character output costs more than 2x.
* `TokenError` is asserted on both sides of the 3.12 boundary: an
  unterminated single-quoted string and a NUL byte yield `ERRORTOKEN` up to
  3.11 and raise from 3.12, while an EOF inside brackets or after a
  backslash continuation raises everywhere.
  The tokens of the line before the fault are asserted yielded on every
  version. Within the faulty line the C tokenizer differs by fault: the
  unterminated string is preceded by its line's earlier tokens, the NUL byte
  rejects its whole line, and the page claims only the earlier lines.
* The f-string boundary is a token count for one f-string: one token up to
  3.11 and seven from 3.12. The t-string is the same count on 3.14 only.
* An inconsistent dedent is asserted to raise `IndentationError` on every
  version, after the tokens before it.
* The command line runs `python -m tokenize` as a subprocess on a source
  whose second line opens a triple-quoted string it never closes: with a file
  argument stdout is empty and stderr carries the error; with the same bytes
  on stdin the six tokens ahead of the fault are printed. `-e` is asserted
  on the exact names it prints.

Not settled here:

* `tok_name` and `exact_type` are dict lookups by construction; the test
  asserts only what they return.
* The C tokenizer's per-token column conversion for non-ASCII lines is read
  from `Python/Python-tokenize.c`, which caches the byte-to-character offset
  of the current line, and is not timed.

Intentionally undocumented: `Untokenizer` and the pattern helpers `group`,
`any`, `maybe`, `cookie_re`, `blank_re` and `endpats` are module-level
implementation details outside `__all__` and the official documentation.
"""

from __future__ import annotations

import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tokenize
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tokenize.md"
EXPECTED_BLOCKS = 4
C_TOKENIZER = sys.version_info >= (3, 12)


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
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountingLines:
    """A readline that records how often it was called and how much it gave out."""

    def __init__(self, data: str | bytes) -> None:
        self.stream: io.StringIO | io.BytesIO
        self.stream = io.StringIO(data) if isinstance(data, str) else io.BytesIO(data)
        self.calls = 0
        self.handed_out = 0

    def readline(self) -> Any:
        self.calls += 1
        line = self.stream.readline()
        self.handed_out += len(line)
        return line


def drain(text: str) -> int:
    return drain_stream(io.StringIO(text))


def drain_stream(stream: io.StringIO) -> int:
    """Tokens in the stream, consumed without keeping them."""
    count = 0
    for _ in tokenize.generate_tokens(stream.readline):
        count += 1
    return count


def peak_over(text: str) -> int:
    """Peak while tokenizing text held in a stream built beforehand."""
    stream = io.StringIO(text)
    return peak_bytes(lambda: drain_stream(stream))


def names(text: str) -> list[tuple[str, str]]:
    return [
        (tokenize.tok_name[token.type], token.string)
        for token in tokenize.generate_tokens(io.StringIO(text).readline)
    ]


class TestLaziness:
    """The generator reads one line at a time and never ahead of the token it yields."""

    def test_nothing_is_read_until_the_generator_is_advanced(self) -> None:
        lines = CountingLines("first = 1\nsecond = 2\n" * 5000)

        tokens = tokenize.generate_tokens(lines.readline)

        assert lines.calls == 0
        assert next(tokens).string == "first"
        assert lines.calls == 1

    def test_the_second_line_is_read_for_its_first_token_and_not_before(self) -> None:
        lines = CountingLines("first = 1\nsecond = 2\n" * 5000)
        tokens = tokenize.generate_tokens(lines.readline)

        line_one = [next(tokens) for _ in range(4)]
        assert [token.string for token in line_one] == ["first", "=", "1", "\n"]
        assert lines.calls == 1

        assert next(tokens).string == "second"
        assert lines.calls == 2

    def test_stopping_early_leaves_the_rest_unread(self) -> None:
        lines = CountingLines("x = 1\n" * 10_000)

        for token in tokenize.generate_tokens(lines.readline):
            if token.type == tokenize.NUMBER:
                break

        assert lines.calls == 1
        assert lines.handed_out == len("x = 1\n")

    def test_tokenize_on_bytes_reads_one_line_for_the_encoding_token(self) -> None:
        lines = CountingLines(b"x = 1\n" * 1000)
        tokens = tokenize.tokenize(lines.readline)

        first = next(tokens)
        assert (first.type, first.string) == (tokenize.ENCODING, "utf-8")
        assert lines.calls == 1
        assert next(tokens).string == "x"
        assert lines.calls == 1

    def test_tokens_on_a_line_share_its_line_string(self) -> None:
        tokens = list(tokenize.generate_tokens(io.StringIO("total = a + b\n").readline))

        assert tokens[-1].type == tokenize.ENDMARKER
        assert tokens[-1].line == ""
        assert len(tokens) == 7
        assert all(token.line is tokens[0].line for token in tokens[:-1])


class TestSpace:
    """The peak is a line, not the source: it ignores line count and tracks line length."""

    def test_the_peak_ignores_the_line_count(self) -> None:
        few = peak_over("x = 1\n" * 1_000)
        many = peak_over("x = 1\n" * 32_000)

        assert many < few * 1.5, f"32x the lines moved the peak from {few} to {many} bytes"

    def test_the_peak_tracks_the_longest_line(self) -> None:
        def source(width: int) -> str:
            return "x = " + " + ".join(["a"] * width) + "\n" + "y = 2\n" * 100

        short = peak_over(source(1_000))
        long = peak_over(source(32_000))

        assert short * 4 < long < short * 64, (
            f"32x the longest line moved the peak from {short} to {long}"
        )

    def test_the_peak_tracks_a_token_that_spans_lines(self) -> None:
        def source(lines: int) -> str:
            return "s = '''\n" + "abc\n" * lines + "'''\n"

        assert drain(source(1_000)) == drain(source(32_000)) == 5
        short = peak_over(source(1_000))
        long = peak_over(source(32_000))

        assert short * 4 < long < short * 64, (
            f"32x the string's lines moved the peak from {short} to {long}"
        )


class TestTime:
    """Linear in the source, whether it is one line or many."""

    @pytest.mark.timing
    def test_eight_times_the_source_costs_about_eight_times(self) -> None:
        small = "value = alpha + beta\n" * 2_000
        large = small * 8
        assert drain(large) == (drain(small) - 1) * 8 + 1

        small_ns = best_ns(lambda: drain(small), inner=3)
        large_ns = best_ns(lambda: drain(large), inner=3)

        ratio = large_ns / small_ns
        assert 4 < ratio < 16, (
            f"8x the source cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns)"
        )

    @pytest.mark.timing
    def test_one_long_line_costs_what_many_short_ones_do(self) -> None:
        many = "a + a\n" * 16_000
        one = "a + " * 31_999 + "a\n"
        assert drain(one) == drain(many) == 64_001

        many_ns = best_ns(lambda: drain(many), inner=3)
        one_ns = best_ns(lambda: drain(one), inner=3)

        ratio = one_ns / many_ns
        assert 0.5 < ratio < 2, (
            f"one line of 64,000 tokens cost x{ratio:.2f} of 16,000 lines of four "
            f"({many_ns:.0f}ns against {one_ns:.0f}ns)"
        )


class TestDetectEncoding:
    """At most two lines are read, and every byte of them is decoded."""

    BODY = b"x = 1\n" * 200_000

    @pytest.mark.parametrize(
        ("header", "encoding", "calls", "handed_out"),
        [
            (b"", "utf-8", 1, 0),
            (b"# -*- coding: latin-1 -*-\n", "iso-8859-1", 1, 26),
            (b"import os\n", "utf-8", 1, 10),
            (b"\n# coding: latin-1\n", "iso-8859-1", 2, 19),
            (b"\n", "utf-8", 2, 7),
            (b"#!/usr/bin/python\n# hello\n", "utf-8", 2, 26),
            (b"\xef\xbb\xbf", "utf-8-sig", 1, 9),
            (b"\xef\xbb\xbf# coding: utf-8\n", "utf-8-sig", 1, 19),
            (b"\xef\xbb\xbf\n# coding: utf-8\n", "utf-8-sig", 2, 20),
            (b"x = " + b"1" * 1_000_000 + b"\n", "utf-8", 1, 1_000_005),
        ],
        ids=[
            "empty",
            "cookie",
            "code",
            "blank-then-cookie",
            "blank-then-code",
            "two-comments",
            "bom",
            "bom-and-cookie",
            "bom-then-blank",
            "megabyte-first-line",
        ],
    )
    def test_reads_at_most_two_lines(
        self, header: bytes, encoding: str, calls: int, handed_out: int
    ) -> None:
        lines = CountingLines(header + (self.BODY if header else b""))

        found, consumed = tokenize.detect_encoding(lines.readline)

        assert found == encoding
        assert lines.calls == calls
        assert lines.handed_out == handed_out
        assert sum(len(line) for line in consumed) == handed_out - (
            3 if found == "utf-8-sig" else 0
        )

    @pytest.mark.parametrize(
        ("header", "message"),
        [
            (b"\xef\xbb\xbf# coding: latin-1\n", "encoding problem: utf-8"),
            (b"# coding: no-such-codec\n", "unknown encoding: no-such-codec"),
            (b"x = '\xff'\n", "invalid or missing encoding declaration"),
        ],
        ids=["bom-disagrees-with-cookie", "unknown-codec", "undecodable-line"],
    )
    def test_the_three_syntax_errors(self, header: bytes, message: str) -> None:
        with pytest.raises(SyntaxError, match=re.escape(message)):
            tokenize.detect_encoding(io.BytesIO(header).readline)

    def test_the_first_line_that_settles_it_ends_the_read(self) -> None:
        third_line_cookie = b"#!/usr/bin/python\nimport os\n# coding: latin-1\n"
        lines = CountingLines(third_line_cookie)

        assert tokenize.detect_encoding(lines.readline)[0] == "utf-8"
        assert lines.calls == 2


class TestOpen:
    """Detection, a seek back to zero, and no further reading."""

    def test_reads_one_line_of_a_large_file_then_rewinds(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "latin.py"
        path.write_bytes(b"# coding: latin-1\n" + b"y = 2\n" * 500_000)
        reads: list[int] = []

        class RecordingReader(io.BufferedReader):
            def readline(self, size: int | None = -1) -> bytes:
                line = super().readline(size)
                reads.append(len(line))
                return line

        monkeypatch.setattr(
            tokenize, "_builtin_open", lambda name, mode: RecordingReader(io.FileIO(name, "r"))
        )

        with tokenize.open(path) as text:
            assert reads == [18]
            assert text.buffer.tell() == 0
            assert text.encoding == "iso-8859-1"
            assert text.readline() == "# coding: latin-1\n"

    def test_the_stream_decodes_with_the_detected_encoding(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "latin.py"
        path.write_bytes(b"# coding: latin-1\nname = '\xe9'\n")

        with tokenize.open(path) as text:
            assert text.read() == "# coding: latin-1\nname = '\u00e9'\n"


class TestUntokenize:
    """Output length is the text written back, which the positions decide."""

    @staticmethod
    def far_apart() -> list[tokenize.TokenInfo]:
        info = tokenize.TokenInfo
        return [
            info(tokenize.NAME, "a", (1, 0), (1, 1), ""),
            info(tokenize.NAME, "b", (1, 100_000), (1, 100_001), ""),
            info(tokenize.NEWLINE, "\n", (1, 100_001), (1, 100_002), ""),
            info(tokenize.ENDMARKER, "", (2, 0), (2, 0), ""),
        ]

    def test_five_tuples_pay_for_the_columns(self) -> None:
        text = tokenize.untokenize(self.far_apart())

        assert isinstance(text, str)
        assert len(text) == 100_002
        assert text == "a" + " " * 99_999 + "b\n"

    def test_the_gap_is_what_costs_not_the_column(self) -> None:
        info = tokenize.TokenInfo
        adjacent = [
            info(tokenize.NAME, "a", (1, 100_000), (1, 100_001), ""),
            info(tokenize.OP, "+", (1, 100_001), (1, 100_002), ""),
            info(tokenize.NEWLINE, "\n", (1, 100_002), (1, 100_003), ""),
            info(tokenize.ENDMARKER, "", (2, 0), (2, 0), ""),
        ]

        assert tokenize.untokenize(adjacent) == " " * 100_000 + "a+\n"

    def test_two_tuples_ignore_the_columns(self) -> None:
        text = tokenize.untokenize(token[:2] for token in self.far_apart())

        assert text == "a b \n"

    def test_a_token_behind_the_previous_one_is_refused(self) -> None:
        first, second, *_ = self.far_apart()

        with pytest.raises(ValueError, match="precedes previous end"):
            tokenize.untokenize([second, first])

    def test_round_trip_and_the_compat_spacing(self) -> None:
        source = "if x:\n    y = 1  # note\n"
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))

        assert tokenize.untokenize(tokens) == source
        kept = [token for token in tokens if token.type != tokenize.COMMENT]
        assert tokenize.untokenize(kept) == "if x:\n    y = 1        \n"
        loose = tokenize.untokenize((token.type, token.string) for token in tokens)
        assert loose == "if x :\n    y =1 # note\n"

    def test_a_tab_between_tokens_comes_back_as_one_space(self) -> None:
        tokens = list(tokenize.generate_tokens(io.StringIO("x\t=\t1\n").readline))

        assert tokenize.untokenize(tokens) == "x = 1\n"

    def test_a_continuation_keeps_its_space_from_3_12(self) -> None:
        tokens = list(tokenize.generate_tokens(io.StringIO("x = \\\n    1\n").readline))

        joined = "x = \\\n    1\n" if C_TOKENIZER else "x =\\\n    1\n"
        assert tokenize.untokenize(tokens) == joined

    def test_a_stream_that_began_with_encoding_comes_back_as_bytes(self) -> None:
        raw = list(tokenize.tokenize(io.BytesIO(b"x = 1\n").readline))

        assert raw[0].type == tokenize.ENCODING
        assert tokenize.untokenize(raw) == b"x = 1\n"
        assert tokenize.untokenize(raw[1:]) == "x = 1\n"

    @pytest.mark.timing
    def test_four_times_the_tokens_costs_about_four_times(self) -> None:
        small = list(tokenize.generate_tokens(io.StringIO("a = b + c\n" * 10_000).readline))
        large = list(tokenize.generate_tokens(io.StringIO("a = b + c\n" * 40_000).readline))
        assert len(large) == (len(small) - 1) * 4 + 1

        small_ns = best_ns(lambda: tokenize.untokenize(small), inner=3)
        large_ns = best_ns(lambda: tokenize.untokenize(large), inner=3)

        ratio = large_ns / small_ns
        assert 2.5 < ratio < 8, (
            f"4x the tokens cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns)"
        )

    @pytest.mark.timing
    def test_more_tokens_cost_more_at_a_fixed_output_length(self) -> None:
        dense = list(tokenize.generate_tokens(io.StringIO("a = b + c\n" * 20_000).readline))
        sparse = list(tokenize.generate_tokens(io.StringIO("abcdefghi\n" * 20_000).readline))
        assert (len(dense), len(sparse)) == (120_001, 40_001)
        assert len(tokenize.untokenize(dense)) == len(tokenize.untokenize(sparse)) == 200_000

        dense_ns = best_ns(lambda: tokenize.untokenize(dense), inner=3)
        sparse_ns = best_ns(lambda: tokenize.untokenize(sparse), inner=3)

        ratio = dense_ns / sparse_ns
        assert ratio > 2, (
            f"3x the tokens for the same output cost x{ratio:.2f} "
            f"({sparse_ns:.0f}ns to {dense_ns:.0f}ns); a cost in c alone would give x1"
        )


class TestTokenTypes:
    """`tok_name` and `exact_type` name a token; f-strings split from 3.12."""

    def test_exact_type_names_the_operator(self) -> None:
        tokens = list(tokenize.generate_tokens(io.StringIO("x += 1\n").readline))
        name, op = tokens[0], tokens[1]

        assert tokenize.tok_name[name.type] == "NAME"
        assert name.exact_type == name.type
        assert tokenize.tok_name[op.type] == "OP"
        assert tokenize.tok_name[op.exact_type] == "PLUSEQUAL"

    def test_an_fstring_is_one_token_or_seven(self) -> None:
        found = names('f"a{x}b"\n')

        if C_TOKENIZER:
            assert [name for name, _ in found] == [
                "FSTRING_START",
                "FSTRING_MIDDLE",
                "OP",
                "NAME",
                "OP",
                "FSTRING_MIDDLE",
                "FSTRING_END",
                "NEWLINE",
                "ENDMARKER",
            ]
        else:
            assert found == [("STRING", 'f"a{x}b"'), ("NEWLINE", "\n"), ("ENDMARKER", "")]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="t-strings are 3.14")
    def test_a_tstring_splits_the_same_way(self) -> None:
        found = [name for name, _ in names('t"a{x}b"\n')]

        assert found[:7] == [
            "TSTRING_START",
            "TSTRING_MIDDLE",
            "OP",
            "NAME",
            "OP",
            "TSTRING_MIDDLE",
            "TSTRING_END",
        ]


class TestTokenError:
    """Raised from inside the stream, and for more shapes from 3.12."""

    def test_the_tokens_before_the_fault_are_yielded_first(self) -> None:
        seen: list[str] = []

        with pytest.raises(tokenize.TokenError, match="EOF in multi-line statement"):
            for token in tokenize.generate_tokens(io.StringIO("total = (1,\n").readline):
                seen.append(token.string)

        assert seen == ["total", "=", "(", "1", ",", "\n"]

    def test_a_continuation_at_eof_raises_everywhere(self) -> None:
        with pytest.raises(tokenize.TokenError, match="EOF in multi-line statement"):
            names("x = 1 \\\n")

    def test_an_inconsistent_dedent_is_an_indentation_error(self) -> None:
        seen: list[str] = []

        with pytest.raises(IndentationError):
            for token in tokenize.generate_tokens(io.StringIO("if x:\n    y\n  z\n").readline):
                seen.append(token.string)

        assert seen == ["if", "x", ":", "\n", "    ", "y", "\n"]

    @pytest.mark.parametrize(
        ("faulty_line", "message", "errortoken"),
        [("y = 'abc\n", "unterminated string literal", "'"), ("y = 1\0\n", "null bytes", "\0")],
        ids=["unterminated-string", "nul-byte"],
    )
    def test_a_malformed_token_raises_from_3_12(
        self, faulty_line: str, message: str, errortoken: str
    ) -> None:
        source = "x = 1\n" + faulty_line
        seen: list[tuple[str, str]] = []

        if C_TOKENIZER:
            with pytest.raises(tokenize.TokenError, match=message):
                for token in tokenize.generate_tokens(io.StringIO(source).readline):
                    seen.append((tokenize.tok_name[token.type], token.string))
            assert seen[:4] == [("NAME", "x"), ("OP", "="), ("NUMBER", "1"), ("NEWLINE", "\n")]
        else:
            seen = names(source)
            assert ("ERRORTOKEN", errortoken) in seen
            assert seen[-1] == ("ENDMARKER", "")


def shell_commands() -> list[tuple[list[str], bool]]:
    """The page's bash block: argv per command with `python` as this interpreter, and
    whether the command reads the file from standard input."""
    text = PAGE.read_text(encoding="utf-8")
    shell = re.search(r"```bash\n(.*?)```", text, re.DOTALL)
    assert shell is not None
    commands = []
    for line in shell.group(1).splitlines():
        if not line.startswith("python"):
            continue
        argv = line.split()
        from_stdin = "<" in argv
        argv = [part for part in argv if part != "<"]
        commands.append(([sys.executable, *argv[1:]], from_stdin))
    assert len(commands) == 3
    return commands


class TestCommandLine:
    """`python -m tokenize` lists a file before printing and streams standard input."""

    SOURCE = b"x = 1\ns = '''open\n"

    def run(self, cwd: pathlib.Path, argv: list[str], from_stdin: bool) -> Any:
        if from_stdin:
            argv = [part for part in argv if part != "script.py"]
        return subprocess.run(
            argv,
            cwd=cwd,
            input=self.SOURCE if from_stdin else None,
            capture_output=True,
            timeout=60,
        )

    def test_a_file_prints_nothing_before_the_error(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "script.py").write_bytes(self.SOURCE)
        (argv, from_stdin), _, _ = shell_commands()
        assert not from_stdin

        result = self.run(tmp_path, argv, from_stdin)

        assert result.returncode == 1
        assert result.stdout == b""
        assert b"script.py:2:" in result.stderr
        assert b"EOF in multi-line string" in result.stderr

    def test_standard_input_prints_the_tokens_before_the_error(
        self, tmp_path: pathlib.Path
    ) -> None:
        _, _, (argv, from_stdin) = shell_commands()
        assert from_stdin

        result = self.run(tmp_path, argv, from_stdin)

        assert result.returncode == 1
        assert b"EOF in multi-line string" in result.stderr
        printed = [line.split()[1] for line in result.stdout.decode().splitlines()]
        assert printed == ["NAME", "OP", "NUMBER", "NEWLINE", "NAME", "OP"]

    def test_exact_names_the_operators(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "script.py").write_bytes(b"x = (1)\n")
        _, (argv, from_stdin), _ = shell_commands()
        assert "-e" in argv and not from_stdin

        result = self.run(tmp_path, argv, from_stdin)

        assert result.returncode == 0, result.stderr
        printed = [line.split()[1] for line in result.stdout.decode().splitlines()]
        assert printed == [
            "ENCODING",
            "NAME",
            "EQUAL",
            "LPAR",
            "NUMBER",
            "RPAR",
            "NEWLINE",
            "ENDMARKER",
        ]


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
        [sys.executable, str(script)], cwd=cwd, capture_output=True, text=True, timeout=120
    )


class TestDocumentedExamples:
    """Each block asserts its own result and runs in a temporary directory."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert calls == 2" in s)
        mutated = source.replace("assert calls == 2", "assert calls == 3", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
