"""Tests for docs/stdlib/pty.md.

The page prices three operations. `openpty()` and `fork()` are fixed-cost
handle operations; `spawn()` runs a copy loop for the whole life of the child,
so its time is the bytes it moves and its space is bounded by the loop's
buffers rather than by that traffic. Most rows are settled by observation - a
counting read callback, a `tracemalloc` peak over a large transfer, an audit
hook, a device-open counter - rather than by a clock.

`pty.fork()` returns in both processes at once, and a fork inside an xdist
worker thread can deadlock in the child, so the whole module runs serially and
guards on a usable pty.

Measurement scope:

* The `spawn()` time row is settled by a read callback that counts its calls:
  each call returns at most 1024 bytes, so the count is at least b / 1024 and
  rises with the child's output, which is the b in O(b). The count is a lower
  bound on the loop's work; that no other per-iteration work grows with the
  stream is read from the loop's source, not measured. Both transfer tests
  confirm the whole payload was read from the master; delivery of those bytes
  to standard output is not asserted, and the page claims only the reading.
  The space row is a
  `tracemalloc` peak taken while a child writes one and then sixteen megabytes
  through the loop, with the whole payload confirmed received: the peak stays
  in the low kilobytes at both sizes, because the loop copies a bounded chunk
  at a time and does not accumulate the stream.
  The default 1024-byte reader is used, which is the scope the row states; a
  callback that returns larger blocks is not varied. The bound holds on every
  supported version: 3.10 writes each chunk on as it arrives, and 3.11+
  buffers behind a fixed high-water mark.
* `spawn()` blocking for at least the child's lifetime is settled by returning
  a non-zero exit status from a child that sleeps before exiting: the status is
  the child's, so the call did not return before the child did. A descendant
  that keeps the slave open and so keeps the loop running longer is not
  exercised.
* The `pty.spawn` audit event and the raw-mode-while-copying behavior are each
  observed in a subprocess - the audit hook because it cannot be removed once
  added, and the raw-mode check because it needs the parent's own stdin to be a
  terminal, which is arranged with an `openpty()` pair. Raw mode is told apart
  from cbreak mode by the flags `setraw()` clears and `setcbreak()` keeps:
  ISIG and OPOST, as well as ICANON and ECHO.
* `fork()` making the child a session leader with a controlling terminal is
  read from the child itself: `os.getsid(0)` equals its pid, its standard
  descriptors are terminals, and opening `/dev/tty` succeeds, which it does
  only for a process that has a controlling terminal. The child's `master_fd`
  being invalid is not asserted; the page states it and the child never uses
  it.
* `openpty()` returning a fixed-cost pair is shown by writing one end and
  reading the other. Its generic fallback scanning a fixed device table is
  shown by making `os.openpty()` raise and counting the `os.open()` attempts
  against a device table where every name is absent: the count is the table's
  256 entries and never depends on an input size.

Not settled here:

* `fork()` copying the parent's page tables (the m in the note) is a kernel
  cost with no portable observable from Python, so the O(1)-with-a-note row is
  reviewed against `os.forkpty()` and CPython source, not measured. The same
  page-table cost is the subject of the `os.fork()` row on the os page.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Iterator
from unittest import mock

import pytest

if sys.platform == "win32":  # pragma: no cover - the module is Unix only
    pytest.skip("pty is a Unix-only module", allow_module_level=True)

import pty  # noqa: E402  (after the platform guard)

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pty.md"
EXPECTED_BLOCKS = 3

# A fork inside an xdist worker thread can deadlock in the child.
pytestmark = pytest.mark.serial


def _pty_is_usable() -> bool:
    try:
        master_fd, slave_fd = os.openpty()
    except OSError:  # pragma: no cover - only on a build without ptys
        return False
    os.close(master_fd)
    os.close(slave_fd)
    return True


@pytest.fixture(autouse=True)
def _needs_a_pty() -> None:
    if not _pty_is_usable():  # pragma: no cover - only on a build without ptys
        pytest.skip("pty needs a working pseudo-terminal")


@pytest.fixture
def quiet_stdout() -> Iterator[None]:
    """Point fd 1 at /dev/null: spawn() writes the child's output there."""
    saved = os.dup(pty.STDOUT_FILENO)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, pty.STDOUT_FILENO)
        yield
    finally:
        os.dup2(saved, pty.STDOUT_FILENO)
        os.close(devnull)
        os.close(saved)


class TestOpenpty:
    """A pair whose cost is fixed, plus a bounded fallback scan."""

    def test_returns_a_readable_writable_pair(self) -> None:
        master_fd, slave_fd = pty.openpty()
        try:
            os.write(slave_fd, b"hello\n")
            # The line discipline turns the newline into carriage-return newline.
            assert os.read(master_fd, 1024) == b"hello\r\n"
        finally:
            os.close(master_fd)
            os.close(slave_fd)

    def test_the_fallback_scans_a_fixed_device_table(self) -> None:
        """With os.openpty() failing, the emulation opens names from a fixed table.

        Every table name is made absent, so the scan runs to the end and
        raises; the attempt count is then the table's 256 entries, whatever
        the host's own device nodes.
        """
        attempts: list[str] = []

        def counting_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
            attempts.append(str(path))
            raise FileNotFoundError(str(path))

        with (
            mock.patch.object(os, "openpty", side_effect=OSError),
            mock.patch.object(os, "open", counting_open),
            pytest.raises(OSError, match="out of pty devices"),
        ):
            pty.openpty()

        assert len(attempts) == 16 * 16, len(attempts)
        assert all(path.startswith("/dev/pty") for path in attempts)


class TestSpawn:
    """The copy loop: O(b) time, O(1) space, and it blocks until the child exits."""

    def test_the_read_callback_is_called_once_per_block(self, quiet_stdout: None) -> None:
        """Each call returns at most 1024 bytes, so the calls are at least b / 1024."""

        def calls_for(byte_count: int) -> int:
            count = 0
            received = 0

            def reader(fd: int) -> bytes:
                nonlocal count, received
                count += 1
                data = os.read(fd, 1024)
                received += len(data)
                return data

            program = f"import os; os.write(1, b'x' * {byte_count})"
            status = pty.spawn([sys.executable, "-c", program], reader, stdin_read=lambda fd: b"")
            assert os.waitstatus_to_exitcode(status) == 0
            assert received == byte_count, (received, byte_count)
            return count

        small = calls_for(2_000)
        large = calls_for(400_000)
        assert small >= 2_000 // 1024, small
        assert large >= 400_000 // 1024, large
        assert large > small * 10, (small, large)

    def test_space_stays_bounded_while_megabytes_cross(self, quiet_stdout: None) -> None:
        """O(1) space: sixteen times the traffic leaves the peak in the same low kilobytes."""

        received = 0

        def reader(fd: int) -> bytes:
            nonlocal received
            data = os.read(fd, 1024)
            received += len(data)
            return data

        def peak_for(payload: int) -> int:
            nonlocal received
            received = 0
            program = f"import os; os.write(1, b'x' * {payload})"
            assert not tracemalloc.is_tracing()
            tracemalloc.start()
            try:
                status = pty.spawn(
                    [sys.executable, "-c", program], reader, stdin_read=lambda fd: b""
                )
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            assert os.waitstatus_to_exitcode(status) == 0
            assert received == payload, (received, payload)
            return peak

        small = peak_for(1 << 20)
        large = peak_for(16 << 20)
        assert large < 64 * 1024, (small, large)
        assert large < 2 * small, (small, large)

    def test_it_blocks_until_the_child_exits(self) -> None:
        """The returned status is the child's, so the call outlived the child."""
        program = "import sys, time; time.sleep(0.3); sys.exit(3)"
        status = pty.spawn([sys.executable, "-c", program], stdin_read=lambda fd: b"")

        assert os.waitstatus_to_exitcode(status) == 3

    def test_it_emits_the_audit_event(self) -> None:
        """addaudithook cannot be removed, so observe the event in a subprocess."""
        driver = textwrap.dedent(
            """
            import json, sys, pty
            seen = []
            sys.addaudithook(lambda name, args: seen.append(args[0]) if name == "pty.spawn" else None)
            pty.spawn(["true"], stdin_read=lambda fd: b"")
            print(json.dumps(seen))
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", driver],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().endswith('[["true"]]')

    def test_it_sets_raw_mode_while_copying(self) -> None:
        """When the parent's stdin is a terminal, the copy runs it in raw mode.

        The parent needs a real terminal for stdin, so it runs behind an
        openpty() pair; a read callback samples the canonical-mode flag while
        the loop is active and the parent's settings are checked afterwards.
        """
        # spawn copies the child's output to fd 1, so the report goes to fd 2
        # and the inner command is silent to keep the two streams unmixed.
        driver = textwrap.dedent(
            """
            import json, os, pty, termios
            LFLAGS = termios.ICANON | termios.ECHO | termios.ISIG
            def is_raw(attrs):
                return not (attrs[3] & LFLAGS) and not (attrs[1] & termios.OPOST)
            before = termios.tcgetattr(0)
            during = []
            def reader(fd):
                during.append(is_raw(termios.tcgetattr(0)))
                return os.read(fd, 1024)
            pty.spawn(["true"], reader, stdin_read=lambda fd: b"")
            after = termios.tcgetattr(0)
            os.write(2, json.dumps({
                "raw_before": is_raw(before),
                "raw_during": during,
                "restored": before == after,
            }).encode())
            """
        )
        master_fd, slave_fd = pty.openpty()
        try:
            with subprocess.Popen(
                [sys.executable, "-c", driver],
                stdin=slave_fd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ) as child:
                os.close(slave_fd)
                slave_fd = -1
                try:
                    _, err = child.communicate(timeout=60)
                except subprocess.TimeoutExpired:
                    child.kill()
                    raise
        finally:
            os.close(master_fd)
            if slave_fd != -1:
                os.close(slave_fd)

        assert child.returncode == 0, err
        report = json.loads(err)
        assert report["raw_before"] is False
        assert report["raw_during"] == [True]  # raw, not merely cbreak, while the loop runs
        assert report["restored"] is True  # and put back on the way out


class TestFork:
    """The child becomes a session leader with a controlling terminal."""

    def test_child_is_a_session_leader_on_a_terminal(self) -> None:
        """Opening /dev/tty succeeds only for a process with a controlling terminal."""
        pid, master_fd = pty.fork()
        if pid == 0:  # pragma: no cover - runs only in the forked child
            code = 1
            try:
                leader = os.getsid(0) == os.getpid()
                on_tty = os.isatty(0) and os.isatty(1) and os.isatty(2)
                os.close(os.open("/dev/tty", os.O_RDWR))
                os.write(1, b"leader\n" if leader and on_tty else b"no\n")
                code = 0
            finally:
                os._exit(code)  # never let the child fall back into pytest

        chunks = []
        while True:
            try:
                data = os.read(master_fd, 1024)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
        os.close(master_fd)
        _, status = os.waitpid(pid, 0)

        assert b"leader" in b"".join(chunks)
        assert os.waitstatus_to_exitcode(status) == 0


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
    )


class TestDocumentedExamples:
    """Each fenced block runs on its own and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if 'b"hello\\r\\n"' in s)
        mutated = source.replace('b"hello\\r\\n"', 'b"WRONG"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
