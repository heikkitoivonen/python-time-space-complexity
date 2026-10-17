"""Tests for docs/builtins/input.md.

`input()` is `builtin_input_impl()` in Python/bltinmodule.c. When
`sys.stdin.fileno()` and `sys.stdout.fileno()` are the C stdin and stdout and
both are terminals, it reads through `PyOS_Readline()`; otherwise it writes the
prompt to `sys.stdout`, flushes it, and returns `sys.stdin.readline()` without
its trailing newline (`PyFile_GetLine()` in Objects/fileobject.c), raising
`EOFError` on an empty read. The off-terminal path is settled here in process
with `io.StringIO` streams and recording stand-ins; the terminal path runs a
child interpreter on a pseudo-terminal.

Measurement scope:

* A line keeps its leading and trailing spaces and loses only its newline; a
  last line without one is returned whole; an empty line is `""`; an empty
  read raises `EOFError("EOF when reading a line")`.
* With recording streams, one call does, in order: flush `sys.stderr`, call
  `sys.stdin.fileno()`, write the prompt once with no newline, flush
  `sys.stdout`, call `sys.stdin.readline()` once. A stdin object with nothing
  but `readline()` works. A non-`str` prompt has `__str__` called once and
  its result written. Iterating a `StringIO` subclass as `sys.stdin` calls
  neither `fileno()` nor `flush()`.
* Time for one `input()` from an `io.StringIO` over lines of 10,000, 100,000
  and 1,000,000 characters, fastest of five, rises by more than 20x over the
  whole range and by under 40x per 10x step. The same holds for a prompt of
  100,000, 1,000,000 and 10,000,000 characters written to an `io.StringIO`
  stdout with a one-character line. The output buffer is preallocated and
  overwritten, so the write copies characters rather than letting an empty
  StringIO retain a reference to the prompt.
* The traced peak of one `input()` over a 1,000,000-character ASCII line from
  a `readline()` that returns a prebuilt string lies between 0.5 and 3 bytes
  per character.
* On a pseudo-terminal (stdin and stdout on it, stderr a pipe): without
  `readline` imported, the prompt arrives on stderr and not on the terminal,
  the typed line comes back with its spaces, and a `sys.stdin` wrapper whose
  `readline()` raises is not called. With `readline` imported the prompt
  arrives on the terminal and not on stderr, the first line grows the history
  by one entry equal to it, and a second identical line leaves it at one.
  The driver drains both the terminal and stderr until EOF before waiting
  for exit. A child that writes 1 MiB to each after its last input, including
  a terminal drain, verifies that unread output cannot block completion.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(k + h) libedit and O(k) GNU history check: `tests/test_readline_complexity.py`
  measures it. Only the backend this interpreter links is run here.
* Windows: it has no pseudo-terminal to drive and no `readline` module, so the
  terminal tests skip there. That its console reader also writes the prompt
  to standard error is read from `PyOS_StdioReadline()` in Parser/myreadline.c.
* Line length and prompt length were each varied with the other held at one
  character or empty; only ASCII text was used. Space was traced at one line
  length, and not for the prompt.
* A terminal line ended by end-of-file characters instead of a newline, which
  the reader without `readline` can return with its last character cut; the
  page scopes its whole-last-line claim to input off a terminal.
* The `int()` and `float()` conversion costs, which the int() and float()
  pages measure.
"""

from __future__ import annotations

import errno
import io
import os
import pathlib
import re
import select
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "input.md"
EXPECTED_BLOCKS = 5

SIZES = (10_000, 100_000, 1_000_000)
PROMPT_SIZES = (100_000, 1_000_000, 10_000_000)


def fastest_ns(func: Callable[[], object], setup: Callable[[], object], repeats: int = 5) -> int:
    """Fastest of `repeats` runs of `func`, each after a fresh untimed `setup`."""
    best = None
    for _ in range(repeats):
        setup()
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


@pytest.fixture
def streams(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Return a function that installs stdin, stdout and stderr for one test."""

    def install(stdin: Any, stdout: Any = None, stderr: Any = None) -> None:
        monkeypatch.setattr(sys, "stdin", stdin)
        monkeypatch.setattr(sys, "stdout", stdout if stdout is not None else io.StringIO())
        monkeypatch.setattr(sys, "stderr", stderr if stderr is not None else io.StringIO())

    yield install


class Recorder:
    """A stream that records every call made on it into a shared event list."""

    def __init__(self, name: str, events: list[tuple[str, str, Any]], lines: str = "") -> None:
        self.name = name
        self.events = events
        self.source = io.StringIO(lines)

    def fileno(self) -> int:
        self.events.append((self.name, "fileno", None))
        raise io.UnsupportedOperation("fileno")

    def write(self, text: str) -> int:
        self.events.append((self.name, "write", text))
        return len(text)

    def flush(self) -> None:
        self.events.append((self.name, "flush", None))

    def readline(self) -> str:
        self.events.append((self.name, "readline", None))
        return self.source.readline()


class TestReadingALine:
    """Rows: `input()` is O(k) and returns the line without its trailing
    newline, keeping other whitespace; at end of input it raises
    `EOFError`."""

    def test_only_the_newline_is_removed(self, streams: Callable[..., None]) -> None:
        streams(io.StringIO("  Alice  \n\t\nBob"))

        assert input() == "  Alice  "
        assert input() == "\t"
        assert input() == "Bob"

    def test_an_empty_line_is_an_empty_string(self, streams: Callable[..., None]) -> None:
        streams(io.StringIO("\n"))

        assert input() == ""

    def test_end_of_input_raises(self, streams: Callable[..., None]) -> None:
        streams(io.StringIO("last\n"))
        input()

        with pytest.raises(EOFError, match="^EOF when reading a line$"):
            input()

    def test_any_object_with_readline_will_do(self, streams: Callable[..., None]) -> None:
        class OnlyReadline:
            def readline(self) -> str:
                return "fed\n"

        streams(OnlyReadline())

        assert input() == "fed"


class TestOneCall:
    """Rows: `input(prompt)` writes `str(prompt)` with no newline before
    reading. Prose: off a terminal the prompt goes to `sys.stdout`, which is
    flushed before the line is read; each call also flushes `sys.stderr` and
    calls `sys.stdin.fileno()`, and iterating `sys.stdin` does neither."""

    def test_the_order_of_a_call(self, streams: Callable[..., None]) -> None:
        events: list[tuple[str, str, Any]] = []
        streams(
            Recorder("stdin", events, "42\n"),
            Recorder("stdout", events),
            Recorder("stderr", events),
        )

        assert input("Answer: ") == "42"
        assert events == [
            ("stderr", "flush", None),
            ("stdin", "fileno", None),
            ("stdout", "write", "Answer: "),
            ("stdout", "flush", None),
            ("stdin", "readline", None),
        ]

    def test_every_call_repeats_the_checks(self, streams: Callable[..., None]) -> None:
        events: list[tuple[str, str, Any]] = []
        streams(
            Recorder("stdin", events, "1\n2\n3\n"),
            Recorder("stdout", events),
            Recorder("stderr", events),
        )

        for _ in range(3):
            input()

        assert [e for e in events if e[1] in ("fileno", "flush")] == [
            ("stderr", "flush", None),
            ("stdin", "fileno", None),
            ("stdout", "flush", None),
        ] * 3

    def test_iterating_stdin_makes_no_checks(self, streams: Callable[..., None]) -> None:
        events: list[tuple[str, str, Any]] = []

        class Counting(io.StringIO):
            def fileno(self) -> int:
                events.append(("stdin", "fileno", None))
                return super().fileno()

            def flush(self) -> None:
                events.append(("stdin", "flush", None))

        streams(Counting("1\n2\n3\n"), Recorder("stdout", events), Recorder("stderr", events))

        assert list(sys.stdin) == ["1\n", "2\n", "3\n"]
        assert events == []

    def test_a_prompt_is_converted_with_str_once(self, streams: Callable[..., None]) -> None:
        conversions: list[int] = []

        class Prompt:
            def __str__(self) -> str:
                conversions.append(1)
                return "> "

        shown = io.StringIO()
        streams(io.StringIO("x\n"), shown)

        assert input(Prompt()) == "x"
        assert conversions == [1]
        assert shown.getvalue() == "> "


class TestTheCostIsLinear:
    """Rows: `input()` is O(k) time and space; `input(prompt)` adds O(m). The
    excluded shapes are O(1) (a total ratio near 1) and O(k²) (100x per 10x
    step)."""

    @staticmethod
    def check(times: list[int]) -> None:
        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        total = times[-1] / times[0]
        assert total > 20, f"times {times}: x{total:.1f} over 100x the size"
        assert all(step < 40 for step in steps), f"times {times}: steps {steps}"

    @pytest.mark.timing
    def test_time_follows_the_line(self, streams: Callable[..., None]) -> None:
        streams(io.StringIO())
        times = []
        for size in SIZES:
            text = "x" * size + "\n"
            times.append(
                fastest_ns(input, lambda text=text: setattr(sys, "stdin", io.StringIO(text)))
            )

        self.check(times)

    @pytest.mark.timing
    def test_time_follows_the_prompt(self, streams: Callable[..., None]) -> None:
        streams(io.StringIO())
        times = []
        for size in PROMPT_SIZES:
            prompt = "p" * size

            def setup(prompt: str = prompt) -> None:
                sys.stdin = io.StringIO("x\n")
                sys.stdout = io.StringIO("\0" * len(prompt))

            times.append(fastest_ns(lambda prompt=prompt: input(prompt), setup))
            assert isinstance(sys.stdout, io.StringIO)
            assert sys.stdout.getvalue() == prompt

        self.check(times)

    def test_space_follows_the_line(self, streams: Callable[..., None]) -> None:
        size = 1_000_000
        line = "x" * size + "\n"

        class Prebuilt:
            def readline(self) -> str:
                return line

        streams(Prebuilt())
        input()  # warm
        tracemalloc.start()
        try:
            result = input()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert len(result) == size
        assert 0.5 * size < peak < 3 * size, f"peak {peak} bytes for {size} characters"


TERMINAL_CHILD = r"""
import sys

class NoReadline:
    def __init__(self, stream):
        self._stream = stream

    def readline(self, *args):
        raise AssertionError("sys.stdin.readline() was called")

    def __getattr__(self, name):
        return getattr(self._stream, name)

sys.stdin = NoReadline(sys.stdin)
lengths = []
if sys.argv[1] == "readline":
    import readline
    lengths.append(readline.get_current_history_length())
lines = []
for index in range(2):
    lines.append(input(f"P{index}> "))
    if sys.argv[1] == "readline":
        lengths.append(readline.get_current_history_length())
report = repr(lines)
if sys.argv[1] == "readline":
    growth = [later - lengths[0] for later in lengths[1:]]
    report += f" {growth} {readline.get_history_item(lengths[-1])!r}"
sys.stderr.write(f"RESULT {report}\n")
"""


def wait_for_prompt(controller: int, prompt: bytes, shown: bytes) -> bytes:
    """Read terminal output until this input call's prompt arrives."""
    deadline = time.monotonic() + 30
    while prompt not in shown and time.monotonic() < deadline:
        if select.select([controller], [], [], 0.2)[0]:
            try:
                chunk = os.read(controller, 4096)
            except OSError:
                break
            if not chunk:
                break
            shown += chunk
    assert prompt in shown, f"missing {prompt!r}; terminal output: {shown!r}"
    return shown


def finish_terminal_child(
    process: subprocess.Popen[bytes], controller: int, shown: bytes
) -> tuple[str, str]:
    """Drain both output channels before waiting for exit. On macOS a
    terminal drain can wait for the master to read even a short final echo."""
    assert process.stderr is not None
    error_fd = process.stderr.fileno()
    output = {controller: bytearray(shown), error_fd: bytearray()}
    pending = list(output)
    deadline = time.monotonic() + 60
    while pending:
        remaining = deadline - time.monotonic()
        assert remaining > 0, (
            f"child did not close its output; terminal: {output[controller][-4096:]!r}; "
            f"stderr: {output[error_fd][-4096:]!r}"
        )
        ready, _, _ = select.select(pending, [], [], min(remaining, 0.2))
        for fd in ready:
            try:
                chunk = os.read(fd, 65536)
            except OSError as error:
                if fd != controller or error.errno != errno.EIO:
                    raise
                # Linux reports the closed slave as EIO; macOS returns EOF.
                chunk = b""
            if chunk:
                output[fd].extend(chunk)
            else:
                pending.remove(fd)
    process.wait(timeout=max(0.1, deadline - time.monotonic()))
    shown_text = output[controller].decode(errors="replace")
    errors = output[error_fd].decode(errors="replace")
    assert process.returncode == 0, f"child exited {process.returncode}: {errors}"
    return shown_text, errors


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="platform: Windows has no pseudo-terminal (os.openpty) and no readline module",
)
class TestOnATerminal:
    """Prose: on a terminal `input()` reads through the line reader, not
    `sys.stdin.readline()`; the prompt goes to standard output with `readline`
    imported and to standard error without it. Row: with `readline` imported
    the line is appended to the history unless it repeats the newest entry."""

    @staticmethod
    def run(tmp_path: pathlib.Path, mode: str, source: str = TERMINAL_CHILD) -> tuple[str, str]:
        """Type the same line twice at the child's two prompts; return what
        the terminal showed and what arrived on stderr."""
        import termios

        script = tmp_path / "child.py"
        script.write_text(source, encoding="utf-8")
        controller, terminal = os.openpty()
        termios.tcsetwinsize(terminal, (24, 80))
        process = subprocess.Popen(
            [sys.executable, str(script), mode],
            stdin=terminal,
            stdout=terminal,
            stderr=subprocess.PIPE,
            close_fds=True,
            env={
                **os.environ,
                "TERM": "xterm",
                "INPUTRC": os.devnull,
                "EDITRC": os.devnull,
            },
        )
        os.close(terminal)
        shown = b""

        try:
            if mode == "plain":
                # The prompts go to stderr; the terminal queues both lines until read.
                os.write(controller, b"hi \rhi \r")
            else:
                for index in range(2):
                    # A line editor can redraw a prompt. Only the next input()
                    # call's distinct prompt means it is ready for another line.
                    shown = wait_for_prompt(controller, f"P{index}> ".encode(), shown)
                    os.write(controller, b"hi \r")
            return finish_terminal_child(process, controller, shown)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(controller)
            if process.stderr is not None:
                process.stderr.close()

    def test_without_readline(self, tmp_path: pathlib.Path) -> None:
        shown, errors = self.run(tmp_path, "plain")

        assert "RESULT ['hi ', 'hi ']" in errors, errors
        for prompt in ("P0> ", "P1> "):
            assert errors.count(prompt) == 1, errors
            assert prompt not in shown, shown

    def test_with_readline(self, tmp_path: pathlib.Path) -> None:
        shown, errors = self.run(tmp_path, "readline")

        assert "RESULT ['hi ', 'hi '] [1, 1] 'hi '" in errors, errors
        for prompt in ("P0> ", "P1> "):
            assert prompt not in errors.split("RESULT")[0], errors
            assert prompt in shown, shown

    def test_a_redrawn_prompt_does_not_advance_the_driver(self, tmp_path: pathlib.Path) -> None:
        source = TERMINAL_CHILD.replace(
            '    lines.append(input(f"P{index}> "))',
            '    lines.append(input(f"P{index}> "))\n    print(f"P{index}> ", end="", flush=True)',
        )
        assert source != TERMINAL_CHILD

        shown, errors = self.run(tmp_path, "readline", source)

        assert "RESULT ['hi ', 'hi '] [1, 1] 'hi '" in errors, errors
        assert shown.count("P0> ") >= 2, shown
        assert shown.count("P1> ") >= 2, shown

    def test_output_after_the_last_input_is_drained_before_exit(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Output larger than either channel's buffer makes the child depend
        on its parent reading, on Linux as well as macOS. No sleep or timing
        ratio is needed to establish that both channels are drained."""
        source = TERMINAL_CHILD.replace(
            "report = repr(lines)",
            "import termios\n"
            "sys.stdout.write('~' * 1_048_576)\n"
            "sys.stdout.flush()\n"
            "termios.tcdrain(sys.stdout.fileno())\n"
            "sys.stderr.write('!' * 1_048_576)\n"
            "sys.stderr.flush()\n"
            "report = repr(lines)",
        )
        assert source != TERMINAL_CHILD

        shown, errors = self.run(tmp_path, "readline", source)

        assert shown.count("~") == 1_048_576
        assert errors.count("!") == 1_048_576
        assert "RESULT ['hi ', 'hi '] [1, 1] 'hi '" in errors, errors[-4096:]


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
    """Each block replaces `sys.stdin` with an `io.StringIO`, runs in its own
    subprocess with the real stdin on the null device, and asserts its own
    result."""

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
        line, source = next((n, s) for n, s in _blocks() if 'shown.getvalue() == "Answer: "' in s)
        mutated = source.replace('"Answer: "', '"Answer: \\n"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
