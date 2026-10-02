"""Tests for docs/stdlib/getpass.md.

The page prices a prompt as one line read: O(p + n) time for the prompt and
the typed characters, O(n) for the line it keeps. Terminal behaviour - echo
off, the settings restored, `/dev/tty` before standard input - is settled by
driving `getpass()` in a child process on a pseudo-terminal from
`os.openpty()`, and the line's growth by feeding the fallback and the
Windows reader inputs of increasing length in process. `getuser()` is
settled by observation: which variable it returns and how often it reaches
the user database.

Measurement scope:

* `getpass()` in a child with no controlling terminal and the
  pseudo-terminal as standard input returns the typed line without its
  newline, nothing typed appears on the terminal, the prompt goes to
  `sys.stderr`, and every terminal attribute after the child exits equals
  the one before it started (with `ECHO` set). End of input (^D on an empty
  line) raises `EOFError`, and the attributes are equal afterwards too.
  With the pseudo-terminal made the child's controlling terminal and
  standard input and error as pipes, the prompt appears on the terminal and
  nothing reaches `sys.stderr`, so `/dev/tty` is tried first.
* `fallback_getpass()` issues `GetPassWarning`, writes the warning line and
  the prompt to `stream`, and returns the line without its newline, leaving
  the next line unread; an empty `sys.stdin` raises `EOFError`. With the
  input built before tracing starts, its traced peak over a
  1,000,000-character line is between 5x and 20x the one over 100,000
  characters. Piped standard input in a child with no controlling terminal
  reaches it too.
* `echo_char` (3.14+) is fed 10,000, 100,000 and 1,000,000 characters
  through `fallback_getpass()`: each 10x step costs under 30x, where
  quadratic concatenation would cost 100x. Every character typed writes one
  `echo_char`, a backspace removes one character and writes `"\\b \\b"`, and
  a two-character, control, non-ASCII or non-string `echo_char` raises from
  `unix_getpass()` and `fallback_getpass()` before `sys.stdin` is read. On a
  pseudo-terminal, public `getpass(echo_char='*')` returns the edited line,
  writes the masks to `sys.stderr`, echoes nothing typed, and restores the
  terminal attributes, `ICANON` included. Through the piped-stdin fallback
  it writes no mask.
* `win_getpass()` runs on every platform against a fake `msvcrt` module
  supplying `getwch()` and `putwch()`: 10x the keys costs under 30x across
  the same three sizes, the prompt is written a character at a time, and a
  replaced `sys.stdin` sends it to `fallback_getpass()` instead.
* `getuser()` returns the first non-empty of `LOGNAME`, `USER`, `LNAME` and
  `USERNAME`, follows a change to the environment between calls, never
  calls `pwd.getpwuid()` when one is set, and calls it once when none is.
  A uid missing from the database raises `OSError` on 3.13+ and `KeyError`
  before.
* Every fenced Python block runs in its own subprocess with no controlling
  terminal, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The cost of the user-database lookup `getuser()` falls back to. It is one
  call into the system's NSS backend, which decides what it costs.
* The length of a user name or an environment variable. The page prices
  both at O(1); only which variable is read is observed.
* `win_getpass()` on a real Windows console. The fake `msvcrt` settles the
  Python loop and its fallback; `getwch()` itself is Windows-only.
* Backspace with `echo_char` or on Windows slices the string typed so far,
  so a backspace costs the length before it. Only typing without
  backspaces is measured, and the page prices that case.
* That `hmac.compare_digest()` in the login pattern takes time independent
  of where its inputs differ is the `hmac` module's documented contract;
  only the result of the comparison is asserted.
* The terminal driver's own line limit in canonical mode (4,095 characters
  on Linux) is a property of the operating system, not the module.
"""

from __future__ import annotations

import getpass
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
import types
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import pytest

# The stubs omit the platform helpers and, before 3.14, `echo_char`.
HELPERS: Any = getpass
PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "getpass.md"
EXPECTED_BLOCKS = 5
POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32", reason="termios and pseudo-terminals are POSIX-only"
)
ECHO_CHAR = pytest.mark.skipif(sys.version_info < (3, 14), reason="echo_char is 3.14+")


def fastest_read(size: int, read: Callable[[str], Any], repeats: int = 3) -> float:
    """Fastest of `repeats` calls of `read` on `size` characters, in seconds.

    `read` builds its input from the string it is given; building that string
    happens before the clock starts.
    """
    best: float | None = None
    for _ in range(repeats):
        keys = "a" * size
        start = time.perf_counter()
        read(keys)
        elapsed = time.perf_counter() - start
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


class CountingSink:
    """A stream that records what was written and how many writes it took."""

    def __init__(self) -> None:
        self.text = ""
        self.writes = 0

    def write(self, text: str) -> int:
        self.text += text
        self.writes += 1
        return len(text)

    def flush(self) -> None:
        pass


class NullSink:
    """A stream that discards everything, so it costs the same at any length."""

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        pass


def fallback(stdin: io.StringIO, monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> str:
    """`fallback_getpass()` reading from `stdin`, built by the caller."""
    monkeypatch.setattr(sys, "stdin", stdin)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", getpass.GetPassWarning)
        return HELPERS.fallback_getpass("", NullSink(), **kwargs)


@dataclass
class Session:
    stdout: bytes
    stderr: bytes
    screen: bytes
    before: list[Any]
    after: list[Any]


def _drain(fd: int, until: bytes | None = None, timeout: float = 10.0) -> bytes:
    """Read from fd until `until` appears, or until nothing arrives for a moment."""
    seen = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        wait = deadline - time.monotonic() if until is not None else 0.2
        ready, _, _ = select.select([fd], [], [], wait)
        if not ready:
            break
        try:
            chunk = os.read(fd, 1024)
        except OSError:
            break
        if not chunk:
            break
        seen += chunk
        if until is not None and until in seen:
            break
    if until is not None:
        assert until in seen, f"waited for {until!r}, saw {seen!r}"
    return seen


def on_terminal(code: str, keys: bytes, *, controlling: bool = False) -> Session:
    """Run `code` in a child on a fresh pseudo-terminal and type `keys` at the prompt.

    By default the terminal is the child's standard input and it has no
    controlling terminal, so `getpass()` falls through to standard input. With
    `controlling`, the terminal becomes the controlling terminal and standard
    input and error are pipes, so only `/dev/tty` reaches it.
    """
    import termios

    try:
        controller, terminal = os.openpty()
    except OSError:  # pragma: no cover - only on a build without ptys
        pytest.skip("missing pty: needs a working pseudo-terminal")
    before = termios.tcgetattr(terminal)
    child: subprocess.Popen[bytes] | None = None
    try:
        if controlling:
            code = f"import fcntl, termios; fcntl.ioctl({terminal}, termios.TIOCSCTTY, 0)\n{code}"
        child = subprocess.Popen(
            [sys.executable, "-c", code],
            stdin=subprocess.DEVNULL if controlling else terminal,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=(terminal,),
            start_new_session=True,
            bufsize=0,
        )
        assert child.stdout is not None and child.stderr is not None
        prompt_fd = controller if controlling else child.stderr.fileno()
        shown = _drain(prompt_fd, until=b"Password: ")
        os.write(controller, keys)
        stdout, stderr = child.communicate(timeout=30)
        screen = _drain(controller)
        if controlling:
            screen = shown + screen
        else:
            stderr = shown + stderr
        return Session(stdout, stderr, screen, before, termios.tcgetattr(terminal))
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait()
        os.close(terminal)
        os.close(controller)


@POSIX_ONLY
class TestEchoIsOffWhileReading:
    """`getpass.getpass()` | O(p + n) | O(n) | Echo is off while the line is
    read, and the terminal settings are restored even when reading raises.

    A real terminal driver is the only thing that can show echo is off, so
    the child reads from a pseudo-terminal and the parent reads back what the
    terminal displayed.
    """

    READ = "import getpass; print(repr(getpass.getpass()))"

    def test_the_typed_line_is_returned_without_its_newline(self) -> None:
        session = on_terminal(self.READ, b"s3cret\n")

        assert session.stdout.decode().strip() == "'s3cret'"

    def test_nothing_typed_is_echoed(self) -> None:
        session = on_terminal(self.READ, b"s3cret\n")

        assert b"s3cret" not in session.screen, session.screen

    def test_the_settings_are_restored_afterwards(self) -> None:
        import termios

        session = on_terminal(self.READ, b"s3cret\n")

        assert session.before[3] & termios.ECHO
        assert session.after == session.before

    def test_end_of_input_raises_and_still_restores_echo(self) -> None:
        import termios

        code = textwrap.dedent(
            """
            import getpass
            try:
                getpass.getpass()
            except EOFError:
                print('EOF')
            """
        )
        session = on_terminal(code, b"\x04")

        assert session.stdout.decode().strip() == "EOF"
        assert session.before[3] & termios.ECHO
        assert session.after == session.before

    def test_without_a_controlling_terminal_the_prompt_goes_to_stderr(self) -> None:
        session = on_terminal(self.READ, b"s3cret\n")

        assert b"Password: " in session.stderr
        assert b"Password: " not in session.screen

    def test_dev_tty_is_tried_before_standard_input(self) -> None:
        session = on_terminal(self.READ, b"s3cret\n", controlling=True)

        assert session.stdout.decode().strip() == "'s3cret'"
        assert b"Password: " in session.screen
        assert session.stderr == b"", session.stderr
        assert b"s3cret" not in session.screen


class TestFallbackReadsOneEchoedLine:
    """`getpass.fallback_getpass()` | O(p + n) | O(n) | issues
    `GetPassWarning` and reads one line from `sys.stdin`, echoed."""

    def test_it_warns_and_returns_the_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("s3cret\nnext\n"))
        sink = CountingSink()

        with pytest.warns(getpass.GetPassWarning):
            result = HELPERS.fallback_getpass("Secret: ", sink)

        assert result == "s3cret"
        assert sink.text == "Warning: Password input may be echoed.\nSecret: "
        assert sys.stdin.read() == "next\n", "more than one line was read"

    def test_empty_input_raises_eof(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(EOFError):
            fallback(io.StringIO(""), monkeypatch)

    def test_the_line_is_the_space(self, monkeypatch: pytest.MonkeyPatch) -> None:
        small = io.StringIO("a" * 100_000 + "\n")
        large = io.StringIO("a" * 1_000_000 + "\n")
        results: list[str] = []

        small_peak = peak_bytes(lambda: results.append(fallback(small, monkeypatch)))
        large_peak = peak_bytes(lambda: results.append(fallback(large, monkeypatch)))

        assert [len(result) for result in results] == [100_000, 1_000_000]
        ratio = large_peak / small_peak
        assert 5 < ratio < 20, (
            f"10x the line peaked at x{ratio:.1f} ({small_peak} to {large_peak} bytes); "
            "O(n) space predicts about x10"
        )

    @POSIX_ONLY
    def test_piped_stdin_without_a_terminal_reaches_it(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import getpass; print(getpass.getpass())"],
            input="s3cret\n",
            capture_output=True,
            text=True,
            start_new_session=True,
            timeout=60,
            check=False,
        )

        assert result.stdout == "s3cret\n"
        assert "GetPassWarning" in result.stderr
        assert "Password input may be echoed" in result.stderr


@ECHO_CHAR
class TestEchoCharMasksEachKey:
    """`getpass.getpass(..., echo_char='*')` | O(p + n) | O(n) | one masking
    character per key; the module handles backspace."""

    def test_each_key_writes_one_mask(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("s3cret\n"))
        sink = CountingSink()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", getpass.GetPassWarning)
            result = HELPERS.fallback_getpass("", sink, echo_char="*")

        assert result == "s3cret"
        assert sink.text.endswith("******")
        assert sink.text.count("*") == 6

    def test_backspace_is_handled_by_the_module(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("ab\x7fc\n"))
        sink = CountingSink()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", getpass.GetPassWarning)
            result = HELPERS.fallback_getpass("", sink, echo_char="*")

        assert result == "ac"
        assert sink.text.endswith("**\b \b*")

    @POSIX_ONLY
    def test_on_a_terminal_each_character_is_masked(self) -> None:
        import termios

        code = "import getpass; print(repr(getpass.getpass(echo_char='*')))"
        session = on_terminal(code, b"ab\x7fc\n")

        assert session.stdout.decode().strip() == "'ac'"
        assert b"**\b \b*" in session.stderr, session.stderr
        assert b"ab" not in session.screen
        assert session.before[3] & termios.ICANON
        assert session.after == session.before

    @POSIX_ONLY
    def test_the_fallback_ignores_it(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import getpass; print(getpass.getpass(echo_char='*'))"],
            input="s3cret\n",
            capture_output=True,
            text=True,
            start_new_session=True,
            timeout=60,
            check=False,
        )

        assert result.stdout == "s3cret\n"
        assert "GetPassWarning" in result.stderr
        assert "*" not in result.stderr

    @pytest.mark.parametrize("reader", ["unix_getpass", "fallback_getpass"])
    @pytest.mark.parametrize("bad", ["**", "\t", "é", b"*"])
    def test_a_bad_mask_is_rejected_before_reading(
        self, reader: str, bad: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stdin = io.StringIO("s3cret\n")
        monkeypatch.setattr(sys, "stdin", stdin)

        with pytest.raises((ValueError, TypeError)):
            getattr(HELPERS, reader)(echo_char=bad)

        assert stdin.tell() == 0

    @pytest.mark.timing
    def test_masked_reading_is_linear(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def read(keys: str) -> None:
            fallback(io.StringIO(keys + "\n"), monkeypatch, echo_char="*")

        times = [fastest_read(size, read) for size in (10_000, 100_000, 1_000_000)]

        for small, large in pairwise(times):
            assert large < small * 30, (
                f"10x the keys cost x{large / small:.1f} ({times}); "
                "quadratic concatenation would cost x100"
            )


class FakeMsvcrt(types.SimpleNamespace):
    """The two console calls `win_getpass()` makes, fed from a string."""

    def __init__(self, keys: str) -> None:
        super().__init__(written=[])
        self._keys = iter(keys)

    def getwch(self) -> str:
        return next(self._keys)

    def putwch(self, char: str) -> None:
        self.written.append(char)


class TestWindowsReadsKeyByKey:
    """`getpass.win_getpass()` | O(p + n) | O(n) | reads console keys with
    `msvcrt.getwch()`, and falls back when `sys.stdin` has been replaced.

    The loop is pure Python, so a fake `msvcrt` runs it on every platform.
    """

    def install(self, keys: str, monkeypatch: pytest.MonkeyPatch) -> FakeMsvcrt:
        fake = FakeMsvcrt(keys)
        monkeypatch.setattr(getpass, "msvcrt", fake, raising=False)
        monkeypatch.setattr(sys, "stdin", sys.__stdin__)
        return fake

    def test_it_returns_the_keys_up_to_enter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self.install("s3cret\rignored", monkeypatch)

        assert HELPERS.win_getpass("Pw: ") == "s3cret"
        assert "".join(fake.written) == "Pw: \r\n"

    def test_a_replaced_stdin_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self.install("never read", monkeypatch)
        monkeypatch.setattr(sys, "stdin", io.StringIO("s3cret\n"))

        with pytest.warns(getpass.GetPassWarning):
            assert HELPERS.win_getpass("", NullSink()) == "s3cret"
        assert fake.written == []

    @pytest.mark.timing
    def test_reading_is_linear(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def read(keys: str) -> None:
            self.install(keys + "\r", monkeypatch)
            HELPERS.win_getpass("")

        times = [fastest_read(size, read) for size in (10_000, 100_000, 1_000_000)]

        for small, large in pairwise(times):
            assert large < small * 30, (
                f"10x the keys cost x{large / small:.1f} ({times}); "
                "quadratic concatenation would cost x100"
            )


VARIABLES = ("LOGNAME", "USER", "LNAME", "USERNAME")


class TestGetuserTrustsTheEnvironment:
    """`getpass.getuser()` | O(1) | O(1) | The first non-empty of `LOGNAME`,
    `USER`, `LNAME` and `USERNAME`; otherwise one user-database lookup by
    uid on Unix. Nothing is cached."""

    @pytest.fixture(autouse=True)
    def _clear(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in VARIABLES:
            monkeypatch.delenv(name, raising=False)

    @pytest.mark.parametrize("index", range(len(VARIABLES)))
    def test_the_first_set_variable_wins(self, index: int, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in VARIABLES[index:]:
            monkeypatch.setenv(name, f"from-{name}")

        assert getpass.getuser() == f"from-{VARIABLES[index]}"

    def test_an_empty_variable_is_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOGNAME", "")
        monkeypatch.setenv("USER", "alice")

        assert getpass.getuser() == "alice"

    def test_nothing_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USER", "alice")
        assert getpass.getuser() == "alice"

        monkeypatch.setenv("USER", "bob")
        assert getpass.getuser() == "bob"

    @pytest.mark.skipif(sys.platform == "win32", reason="pwd is POSIX-only")
    def test_a_set_variable_never_reaches_the_database(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import pwd

        calls: list[int] = []
        monkeypatch.setattr(pwd, "getpwuid", lambda uid: calls.append(uid))
        monkeypatch.setenv("USERNAME", "alice")

        assert getpass.getuser() == "alice"
        assert calls == []

    @pytest.mark.skipif(sys.platform == "win32", reason="pwd is POSIX-only")
    def test_with_none_set_it_looks_up_the_uid_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pwd

        calls: list[int] = []

        def lookup(uid: int) -> tuple[str, ...]:
            calls.append(uid)
            return ("from-database",)

        monkeypatch.setattr(pwd, "getpwuid", lookup)

        assert getpass.getuser() == "from-database"
        assert calls == [os.getuid()]

    @pytest.mark.skipif(sys.platform == "win32", reason="pwd is POSIX-only")
    def test_a_missing_entry_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import pwd

        def lookup(uid: int) -> tuple[str, ...]:
            raise KeyError(uid)

        monkeypatch.setattr(pwd, "getpwuid", lookup)
        expected = OSError if sys.version_info >= (3, 13) else KeyError

        with pytest.raises(expected):
            getpass.getuser()

    def test_getpasswarning_is_a_user_warning(self) -> None:
        assert issubclass(getpass.GetPassWarning, UserWarning)


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
        start_new_session=sys.platform != "win32",  # no terminal for getpass() to open
        check=False,
    )


# Blocks that drive a pseudo-terminal or detach from the terminal, by a phrase
# they contain; they need os.openpty() or start_new_session, both POSIX-only.
POSIX_BLOCKS = ("os.openpty()", "start_new_session=True")


class TestDocumentedExamples:
    """Each block runs in its own subprocess with no controlling terminal, so
    a `getpass()` that is not fed by the block itself cannot block on a
    reader's terminal, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        accounted = 0
        for line, source in _blocks():
            accounted += 1
            if sys.platform == "win32" and any(p in source for p in POSIX_BLOCKS):
                continue
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert accounted == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "== 'alice'" in s)
        mutated = source.replace("== 'alice'", "== 'carol'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
