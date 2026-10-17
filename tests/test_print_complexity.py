"""Tests for docs/builtins/print.md.

print() is builtin_print in Python/bltinmodule.c. It resolves `file` (None
means sys.stdout, and a sys.stdout of None returns at once), checks that `sep`
and `end` are str or None, then for each argument writes the separator and
calls PyFile_WriteObject, which takes `str()` of the argument and passes the
result to `file.write`. It writes `end` and, with flush=True, calls the
file's flush(). Nothing joins the pieces. builtin_print does this in the
v3.11.14, v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags; between them only
argument passing and reference handling change, so no version is treated
apart.

Almost every row is settled by observation: a recording file sees each
`write()` and `flush()` call and the object passed, and a recording
`__str__` shows when each argument is converted. A stopwatch settles the
growth in k and a traced peak the O(m) space; the n term rests on
the cost model that prices file.write(s) at O(len(s)).

Measurement scope:

* writes: k = 1, 3 and 100 arguments make 2k write() calls in the order
  argument, separator, ..., end; no arguments make one call with "\\n". Each
  argument's `__str__` is called once, after the previous piece is written.
* an exact str argument reaches write() as the same object, a str subclass as
  a new exact str, and an int as its decimal text.
* growth in k: printing 1,000 and 100,000 short strings to a discarding file
  costs between x20 and x400, where linear predicts x100 and quadratic
  x10,000. String length is not varied.
* space: with a discarding file, printing two lists whose reprs are about
  1.5 MB each peaks under 1.5 times one repr's peak, and printing three
  1,000,000-character strings peaks under 10 KB. These run serially, since
  xdist's I/O thread allocates while tracemalloc is tracing.
* sep and end: sep=0 or end=0 raises TypeError naming the argument with no
  write() made; sep=None and end=None behave as " " and "\\n".
* file: file=None writes to sys.stdout, and an object with only a write()
  method is accepted.
* flush: flush=True makes one flush() call after end is written, and none
  without it; a regular file opened for writing has size 0 after a short
  print() and the full length after flush=True.
* sys.stdout set to None: print() returns without calling `__str__`.
* a self-referencing list prints "[[...]]", and an int of 5,001 digits raises
  ValueError under the default digit limit.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* Passing the k arguments can be O(k) in time and space: 3.11 packs them
  into a tuple. The page's bounds exclude it; the space tests hold k at two and three.
* The cost of each argument's `__str__` and of the file's write() and flush()
  is the caller's; the page names it once, and the tests use strings, small
  ints and lists with a file that records or discards.
* When text reaches the operating system depends on the file's buffering:
  only a block-buffered regular file is observed, not a terminal's line
  buffering or an unbuffered binary stream.
* That sys.stdout is None under pythonw on Windows is the sys module's
  documented behaviour; the tests set it to None directly.
* Not varied: argument types beyond str, int, list and a custom `__str__`,
  separator and end lengths, and non-UTF-8 encodings.
"""

from __future__ import annotations

import io
import os
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "print.md"
EXPECTED_BLOCKS = 7


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


class Recorder:
    """A file that records every write() and flush() call, in order."""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    def write(self, text: Any) -> int:
        self.events.append(("write", text))
        return len(text)

    def flush(self) -> None:
        self.events.append(("flush", None))

    @property
    def writes(self) -> list[Any]:
        return [text for kind, text in self.events if kind == "write"]


class Discard:
    """A file that keeps nothing."""

    def write(self, text: str) -> int:
        return len(text)


class TestOneWritePerPiece:
    """`print(*objects)`: one str() and one write() per argument, one write()
    per separator and one for end, so 2k calls for k >= 1 arguments."""

    @pytest.mark.parametrize("k", [1, 3, 100])
    def test_k_arguments_make_2k_writes(self, k: int) -> None:
        out = Recorder()
        print(*[f"a{i}" for i in range(k)], file=out)

        expected: list[str] = []
        for i in range(k):
            if i:
                expected.append(" ")
            expected.append(f"a{i}")
        expected.append("\n")
        assert out.writes == expected
        assert len(out.writes) == 2 * k

    def test_no_arguments_write_only_end(self) -> None:
        out = Recorder()
        print(file=out)
        assert out.writes == ["\n"]

    def test_each_argument_is_converted_once_just_before_its_write(self) -> None:
        out = Recorder()

        class Traced:
            def __init__(self, name: str) -> None:
                self.name = name

            def __str__(self) -> str:
                out.events.append(("str", self.name))
                return self.name

        print(Traced("a"), Traced("b"), file=out)

        assert out.events == [
            ("str", "a"),
            ("write", "a"),
            ("write", " "),
            ("str", "b"),
            ("write", "b"),
            ("write", "\n"),
        ]

    def test_an_exact_str_argument_is_written_without_a_copy(self) -> None:
        text = "x" * 100_000
        out = Recorder()
        print(text, 42, file=out)

        assert out.writes[0] is text
        assert out.writes[2] == "42"

    def test_a_str_subclass_is_converted_to_a_new_str(self) -> None:
        class Text(str):
            pass

        text = Text("x" * 100)
        out = Recorder()
        print(text, file=out)

        assert type(out.writes[0]) is str
        assert out.writes[0] is not text
        assert out.writes[0] == text

    @pytest.mark.timing
    def test_time_grows_linearly_with_the_arguments(self) -> None:
        sink = Discard()
        small = [f"item{i}" for i in range(1_000)]
        large = [f"item{i}" for i in range(100_000)]

        small_ns = best_ns(lambda: print(*small, file=sink), inner=10)
        large_ns = best_ns(lambda: print(*large, file=sink), repeats=5)

        ratio = large_ns / small_ns
        assert 20 < ratio < 400, (
            f"100x the arguments cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "linear predicts x100 and quadratic x10,000"
        )


@pytest.mark.serial
class TestSpaceIsTheLongestArgument:
    """Space is O(m): each converted argument is released before the next is
    converted, nothing joins the output, and a str is not copied."""

    def test_two_large_lists_peak_at_one_repr(self) -> None:
        first = list(range(200_000))
        second = list(range(200_000))
        sink = Discard()

        one = peak_bytes(lambda: str(first))
        both = peak_bytes(lambda: print(first, second, file=sink))

        assert one > 1_000_000, one
        assert both < 1.5 * one, (
            f"printing two lists peaked at {both:,} bytes against {one:,} for one repr; "
            "holding both reprs or the joined output would be about twice that"
        )

    def test_large_strings_are_not_copied(self) -> None:
        text = "x" * 1_000_000
        sink = Discard()

        peak = peak_bytes(lambda: print(text, text, text, file=sink))

        assert peak < 10_000, f"{peak:,} bytes for three 1,000,000-character strings"


class TestSepAndEnd:
    """`sep` and `end` must be str or None; anything else raises TypeError
    before anything is written."""

    def test_a_non_string_sep_raises_before_any_write(self) -> None:
        out = Recorder()
        bad: Any = 0
        with pytest.raises(TypeError, match="sep must be None or a string"):
            print("a", "b", sep=bad, file=out)
        assert out.events == []

    def test_a_non_string_end_raises_before_any_write(self) -> None:
        out = Recorder()
        bad: Any = 0
        with pytest.raises(TypeError, match="end must be None or a string"):
            print("a", "b", end=bad, file=out)
        assert out.events == []

    def test_none_means_the_defaults(self) -> None:
        out = Recorder()
        print("a", "b", sep=None, end=None, file=out)
        assert out.writes == ["a", " ", "b", "\n"]

    def test_custom_separator_and_end(self) -> None:
        buffer = io.StringIO()
        print("x", "y", "z", sep="-", end="!", file=buffer)
        assert buffer.getvalue() == "x-y-z!"


class TestFileArgument:
    """`file=f` needs only a write() method; `file=None` means sys.stdout."""

    def test_file_none_writes_to_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        out = Recorder()
        monkeypatch.setattr(sys, "stdout", out)
        print("hi", file=None)
        assert out.writes == ["hi", "\n"]

    def test_an_object_with_only_write_is_enough(self) -> None:
        sink = Discard()
        print("hi", file=sink)


class TestFlush:
    """`flush=True` adds one flush() call after end is written; a regular
    file holds short output in its buffer until then."""

    def test_flush_true_calls_flush_once_after_end(self) -> None:
        out = Recorder()
        print("a", file=out, flush=True)
        assert out.events == [("write", "a"), ("write", "\n"), ("flush", None)]

    def test_no_flush_by_default(self) -> None:
        out = Recorder()
        print("a", file=out)
        assert ("flush", None) not in out.events

    def test_a_regular_file_holds_output_until_flushed(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "out.txt"
        with open(path, "w", encoding="utf-8", newline="") as f:
            print("first", file=f)
            assert os.path.getsize(path) == 0
            print("second", file=f, flush=True)
            assert os.path.getsize(path) == len("first\nsecond\n")


class TestNoStdout:
    """`print(*objects)` while sys.stdout is None returns without converting
    or writing anything."""

    def test_nothing_is_converted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        converted: list[int] = []

        class Traced:
            def __str__(self) -> str:
                converted.append(1)
                return "x"

        monkeypatch.setattr(sys, "stdout", None)
        print(Traced(), Traced())
        assert converted == []


class TestEdgeCases:
    """A self-referencing list prints `[...]` for the cycle, and an int over
    the digit limit raises ValueError."""

    def test_a_cycle_prints_an_ellipsis(self) -> None:
        cycle: list[Any] = []
        cycle.append(cycle)
        buffer = io.StringIO()
        print(cycle, file=buffer)
        assert buffer.getvalue() == "[[...]]\n"

    def test_an_int_over_the_digit_limit_raises(self) -> None:
        assert sys.get_int_max_str_digits() == 4_300
        with pytest.raises(ValueError, match="integer string conversion"):
            print(10**5_000, file=Discard())


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
    """Each block runs in its own subprocess and asserts its own results."""

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
        line, source = next((n, s) for n, s in _blocks() if "len(joined.calls) == 2" in s)
        mutated = source.replace("len(joined.calls) == 2", "len(joined.calls) == 2_000", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
