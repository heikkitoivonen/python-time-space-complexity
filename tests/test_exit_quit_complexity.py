"""Tests for docs/builtins/exit_quit.md.

`exit` and `quit` are `_sitebuiltins.Quitter` instances that `site.setquit()`
installs into builtins. Calling one closes `sys.stdin`, ignoring any error the
close raises, and raises `SystemExit(code)`; the bare name's `repr()` is the
hint `Use <name>() or <eof> to exit`, where `<eof>` is `Ctrl-Z plus Return`
when `os.sep` is a backslash and `Ctrl-D (i.e. EOF)` otherwise. The call's
claims are settled by observation in this process, with a recording object
standing in for `sys.stdin`; the exit status, the message and the cleanup
order by running a child interpreter; the REPL by driving one on a
pseudo-terminal. Nothing here needs a stopwatch.

Measurement scope:

* `exit(5)` and `quit(5)` raise `SystemExit` with code 5 after closing a
  recording `sys.stdin` exactly once, and still raise it when the close
  raises. `exit` and `quit` are one class, not functions, and their reprs
  are the hint for this platform's EOF key.
* Child interpreters exit with status 0 for `exit()` and `exit(None)`, 7
  for `exit(7)`, and 1 for `exit('a message')` and `exit([1])`, writing the
  object's `str()` and a newline to stderr in those two cases and nothing
  otherwise. Under `-S`, `exit(7)` raises `NameError`. After `sys.exit()` is
  caught `sys.stdin` is still open; after `exit()` it is closed.
* A `SystemExit` raised 10 and 200 recursive calls deep carries traceback
  chains that differ by exactly 190 entries, one per frame unwound. Uncaught,
  it runs a `finally` block, then an `__exit__` method, then an `atexit`
  handler, and the child exits with the code passed.
* On a pseudo-terminal, the default REPL from 3.13 exits with status 0 on a
  line holding only `exit` or `quit`, and evaluates the name instead after
  `exit = 40 + 2`; the REPL selected by `PYTHON_BASIC_REPL=1`, and the only REPL
  before 3.13, prints the hint and keeps running.
* Every fenced Python block runs in its own subprocess. The message block is
  asserted to exit with status 1 and its message on stderr, and the cleanup
  block to print the `atexit` line after its assertions pass; a mutated
  assertion in one block is asserted to fail.

Not settled here:

* The O(1) of the call follows from `Quitter.__call__` in
  Lib/_sitebuiltins.py: one `close()` and one `raise`, no loop. No allocation
  was measured.
* That unwinding costs O(d) time is inferred from the one traceback entry
  each frame adds; it was counted, not timed. The cost of the `finally`
  blocks, `__exit__` methods and `atexit` handlers is caller code, priced on
  the page as "plus the handlers".
* The O(m) message write follows from `_Py_HandleSystemExitAndKeyboardInterrupt`
  in Python/pythonrun.c, which writes the object with `PyFile_WriteObject`;
  messages were not varied in length. The page prices only a string: any
  other object is written as its `str()`, whose cost is the object's own.
* The REPL claims need a pseudo-terminal, so they are not run on Windows,
  where the `pty` module does not exist. The Windows EOF key in the hint is
  asserted only on Windows, from `os.sep`.
* The shared API audit reports `builtins.exit` and `builtins.quit` as
  documented but unresolved: they come from `site`, not from the builtins
  module itself, so its inventory does not observe them.
"""

from __future__ import annotations

import builtins
import os
import pathlib
import re
import select
import subprocess
import sys
import textwrap
import time
import types
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "exit_quit.md"
EXPECTED_BLOCKS = 6

EOF_KEY = "Ctrl-Z plus Return" if os.sep == "\\" else "Ctrl-D (i.e. EOF)"


def run_python(
    source: str, cwd: pathlib.Path, *flags: str, **env: str
) -> subprocess.CompletedProcess[str]:
    """Run `source` in a fresh interpreter in `cwd`, with stdin open on the null device."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return subprocess.run(
        [sys.executable, *flags, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env={**os.environ, **env},
        check=False,
    )


class RecordingStdin:
    """A `sys.stdin` stand-in that records each `close()` call."""

    def __init__(self, *, fail: bool = False) -> None:
        self.closes = 0
        self.fail = fail

    def close(self) -> None:
        self.closes += 1
        if self.fail:
            raise OSError("close failed")


QUITTERS: list[Any] = [builtins.exit, builtins.quit]


class TestTheCallClosesStdinThenRaises:
    """Rows: `exit(code=None)` / `quit(code=None)` close `sys.stdin`, then
    raise `SystemExit(code)`. A recording stdin separates closing it from
    leaving it alone, and the exception's code from a fixed one."""

    @pytest.mark.parametrize("quitter", QUITTERS, ids=["exit", "quit"])
    def test_one_close_then_systemexit_with_the_code(
        self, quitter: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stdin = RecordingStdin()
        monkeypatch.setattr(sys, "stdin", stdin)

        with pytest.raises(SystemExit) as raised:
            quitter(5)

        assert raised.value.code == 5
        assert stdin.closes == 1

    @pytest.mark.parametrize("quitter", QUITTERS, ids=["exit", "quit"])
    def test_a_failing_close_still_raises(
        self, quitter: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stdin = RecordingStdin(fail=True)
        monkeypatch.setattr(sys, "stdin", stdin)

        with pytest.raises(SystemExit) as raised:
            quitter("bye")

        assert raised.value.code == "bye"
        assert stdin.closes == 1


class TestTheBareName:
    """Row: the bare name's `repr()` is a hint naming the call and the EOF
    key. Prose: the two objects are callable instances of one class, not
    functions, and differ only in the name their hint prints."""

    def test_one_class_and_not_a_function(self) -> None:
        assert type(builtins.exit) is type(builtins.quit)
        assert type(builtins.exit).__name__ == "Quitter"
        assert not isinstance(builtins.exit, types.FunctionType)
        assert callable(builtins.exit)

    @pytest.mark.parametrize("name", ["exit", "quit"])
    def test_the_hint_names_the_call_and_the_eof_key(self, name: str) -> None:
        assert repr(getattr(builtins, name)) == f"Use {name}() or {EOF_KEY} to exit"


class TestExitStatus:
    """Rows: `None` or an int is the exit status, `None` meaning 0; any other
    object is written to stderr and the status is 1. Each runs in a child
    interpreter so the status is the one the process reports."""

    @pytest.mark.parametrize(
        ("argument", "status", "stderr"),
        [
            ("", 0, ""),
            ("None", 0, ""),
            ("7", 7, ""),
            ("'a message'", 1, "a message\n"),
            ("[1]", 1, "[1]\n"),
        ],
    )
    def test_status_and_stderr(
        self, argument: str, status: int, stderr: str, tmp_path: pathlib.Path
    ) -> None:
        result = run_python(f"exit({argument})", tmp_path)

        assert result.returncode == status
        assert result.stderr == stderr

    def test_absent_without_site(self, tmp_path: pathlib.Path) -> None:
        """Prose: `site` installs them, so they do not exist under `-S`."""
        result = run_python("exit(7)", tmp_path, "-S")

        assert result.returncode == 1
        assert "NameError: name 'exit' is not defined" in result.stderr

    def test_sys_exit_leaves_stdin_open(self, tmp_path: pathlib.Path) -> None:
        """Prose: `sys.exit()` does not close `sys.stdin`; `exit()` does."""
        result = run_python(
            """
            import sys

            for quitter in (sys.exit, exit):
                try:
                    quitter()
                except SystemExit:
                    print(sys.stdin.closed)
            """,
            tmp_path,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["False", "True"]


class TestWhatTheCallStarts:
    """Rows: unwinding is O(d) time and space, one traceback entry per frame,
    with `finally` and `__exit__` run on the way; `atexit` handlers run when
    the interpreter exits."""

    @staticmethod
    def traceback_entries(depth: int) -> int:
        def nested(remaining: int) -> None:
            if remaining == 0:
                builtins.exit(1)
            nested(remaining - 1)

        stdin = sys.stdin
        sys.stdin = RecordingStdin()  # type: ignore[assignment]
        try:
            nested(depth)
        except SystemExit as e:
            tb, entries = e.__traceback__, 0
            while tb is not None:
                tb, entries = tb.tb_next, entries + 1
            return entries
        finally:
            sys.stdin = stdin
        raise AssertionError("exit() returned")

    def test_one_traceback_entry_per_frame_unwound(self) -> None:
        assert self.traceback_entries(200) - self.traceback_entries(10) == 190

    def test_cleanup_runs_in_order_before_the_process_ends(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import atexit

            atexit.register(print, 'atexit')

            class Resource:
                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    print('__exit__')
                    return False

            with Resource():
                try:
                    exit(3)
                finally:
                    print('finally')
            print('not reached')
            """,
            tmp_path,
        )

        assert result.returncode == 3, result.stderr
        assert result.stdout.split() == ["finally", "__exit__", "atexit"]


def read_to_prompt(controller: int, output: bytearray, since: int) -> None:
    """Read from a REPL's terminal until a prompt appears after offset `since`
    and the REPL then stays quiet for half a second, or until it exits."""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        ready, _, _ = select.select([controller], [], [], 0.5)
        if not ready:
            if b">>> " in output[since:]:
                return
            continue
        try:
            chunk = os.read(controller, 65536)
        except OSError:
            return
        if not chunk:
            return
        output += chunk


@pytest.mark.skipif(
    sys.platform == "win32", reason="platform: Windows has no pty module to drive a REPL with"
)
class TestInteractiveUse:
    """Prose: from 3.13 the default REPL exits on a line holding only `exit`
    or `quit`, unless a variable of that name exists; the basic REPL, the only
    one before 3.13, prints the hint. Each REPL runs on a pseudo-terminal, and
    the test waits for the prompt before typing each line."""

    @staticmethod
    def repl(lines: list[str], **env: str) -> tuple[int | None, str]:
        """Type `lines` into `python -q -i`; return its status (None if still
        running two seconds later) and everything it printed."""
        controller, terminal = os.openpty()
        environment = {**os.environ, "TERM": "xterm", **env}
        for name in ("PYTHONSTARTUP", "PYTHON_BASIC_REPL"):
            if name not in env:
                environment.pop(name, None)
        process = subprocess.Popen(
            [sys.executable, "-q", "-i"],
            stdin=terminal,
            stdout=terminal,
            stderr=terminal,
            close_fds=True,
            env=environment,
        )
        os.close(terminal)
        output = bytearray()

        try:
            read_to_prompt(controller, output, 0)
            for line in lines:
                since = len(output)
                os.write(controller, line.encode() + b"\r")
                read_to_prompt(controller, output, since)
            try:
                status = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                status = None
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(controller)
        text = bytes(output).decode(errors="replace")
        if "can't use pyrepl" in text:
            pytest.skip(f"missing terminfo: the default REPL fell back to the basic one: {text}")
        return status, text

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: no command REPL before 3.13")
    @pytest.mark.parametrize("name", ["exit", "quit"])
    def test_default_repl_exits_on_the_bare_word(self, name: str) -> None:
        status, output = self.repl([name])

        assert status == 0, output
        assert f"Use {name}()" not in output

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: no command REPL before 3.13")
    def test_a_variable_of_that_name_wins(self) -> None:
        status, output = self.repl(["exit = 40 + 2", "exit"])

        assert status is None, output
        assert "42" in output, output

    @pytest.mark.parametrize("name", ["exit", "quit"])
    def test_basic_repl_prints_the_hint(self, name: str) -> None:
        env = {"PYTHON_BASIC_REPL": "1"} if sys.version_info >= (3, 13) else {}
        status, output = self.repl([name], **env)

        assert status is None, output
        assert f"Use {name}() or {EOF_KEY} to exit" in output


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


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory with stdin
    on the null device. Two blocks are expected to end differently from the
    rest: the message block exits with status 1 and its message on stderr,
    and the cleanup block prints its `atexit` line at exit."""

    MESSAGE = "error: config.json not found"

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in _blocks():
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = run_python(source, workdir)
            if self.MESSAGE in source:
                ok = result.returncode == 1 and result.stderr == self.MESSAGE + "\n"
            elif "atexit.register" in source:
                ok = result.returncode == 0 and result.stdout == "atexit handler\n"
            else:
                ok = result.returncode == 0 and result.stdout == ""
            if not ok:
                failures.append(
                    f"{PAGE.name}:{line} exited {result.returncode}\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr.strip()}"
                )

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "entries > 100 " in s)
        mutated = source.replace("entries > 100 ", "entries > 1000 ", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = run_python(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
