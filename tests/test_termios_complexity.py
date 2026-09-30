"""Tests for docs/stdlib/termios.md.

The page prices every operation O(1): each function is one or two system
calls on a fixed-size kernel structure, and the only list it builds, the
control-character list, has `termios.NCCS` entries. Nothing here has an input
size to vary, so the rows are settled by observation on a pseudo-terminal pair
from `os.openpty()` - list shapes and identities, what a flush leaves readable,
what the other end of the pair receives - rather than by a clock. No test
touches the process's own terminal.

Measurement scope:

* `tcgetattr()` returns seven entries whose `cc` list has `NCCS` entries, a
  new outer and `cc` list on every call, on the slave and the master alike,
  and accepts an object with `fileno()` as well as a descriptor; that the
  other functions take `fd` through the same `fildes` converter is read from
  Modules/termios.c rather than exercised for each. `cc[VMIN]` and
  `cc[VTIME]` are one-byte `bytes` in canonical mode and integers once
  `ICANON` is cleared through `tcsetattr()`. A slice of the list, and
  `list()` of it, share its `cc` list; a second `tcgetattr()` and
  `copy.deepcopy()` do not, and a change through either leaves the first list
  unchanged.
* `tcsetattr()` is asserted to apply a cleared `ICANON` (one byte then reads
  without a newline), to reject a list that is not seven entries long with
  `TypeError`, and, with `TCSAFLUSH`, to discard a line already readable on
  the slave while `TCSANOW` keeps one. The `TCSAFLUSH` test turns `ECHO` off
  first: on macOS the flush waits until the master has read any echoed
  output, and nothing reads it there. `tcflush(TCIFLUSH)` discards a
  readable line in the same way. Readability is waited for with `select()`
  before the flush, and its absence is checked with a 0.2 s `select()`
  afterwards.
* On Linux, `tcflow(TCOOFF)` makes a non-blocking write to the slave raise
  `BlockingIOError` and keeps a blocking one in a thread unfinished for
  0.3 s after the thread signals it is about to write; `TCOON` lets the
  next write, or the waiting one, through to the master. CPython's own
  Lib/test/test_termios.py runs its suspend-and-resume test on Linux only.
  `TCIOFF` and `TCION` deliver the slave's `cc[VSTOP]` and `cc[VSTART]`
  bytes to the master.
* On Linux, `tcdrain()` returns within a second with 100 bytes the master
  has not read, and `tcsendbreak(fd, 0)` within 0.2 s, under the 0.25 s a
  serial break lasts; both are timing tests. On macOS `tcdrain()` is
  asserted to be still waiting 0.5 s after 100 bytes were written, and to
  return within 5 s once the master reads them; `tcsendbreak(fd, 0)` to take
  at least 0.3 s. Those two run only on macOS, in the macOS CI job.
* `tcgetwinsize()` and `tcsetwinsize()` (3.11+, guarded on
  `sys.version_info`) round-trip `(rows, columns)`, and the master reports
  what was set on the slave; on 3.10 the two names are asserted absent.
* `termios.error` is an `Exception` subclass raised by `tcgetattr()` on a
  pipe with the arguments `(ENOTTY, os.strerror(ENOTTY))`.
* An attribute change made by a child process, which then exits, is still in
  force on the pseudo-terminal afterwards.
* Every fenced Python block runs in its own subprocess with its own
  pseudo-terminal pair, and a mutated assertion in one of them is asserted to
  fail. The window-size block needs 3.11 and is skipped, with that reason, on
  3.10.

Not settled here:

* That each call is O(1) is read from Modules/termios.c: every function makes
  one or two system calls on a `struct termios` or `struct winsize`, and
  `tcgetattr()` and `tcsetattr()` loop once over the `NCCS` control
  characters. What the kernel does inside those calls is not priced.
* How long `TCSADRAIN`, `tcdrain()` and `tcsendbreak()` wait on a real
  device depends on the line's speed and what is queued; a pseudo-terminal
  has no line, so only its behaviour is observed. The 0.25 to 0.5 s
  break is the official documentation's, for a zero `duration`. The macOS
  behaviour follows from the BSD terminal driver's `ttywait()`, which
  `tcdrain()` and `TCSADRAIN`/`TCSAFLUSH` wait in until the output queue is
  empty - on a pseudo-terminal, until the master has read it - and from the
  BSD libc `tcsendbreak()`, which sleeps about 0.4 s in `select()` between
  `TIOCSBRK` and `TIOCCBRK` whatever the device.
* `tcflush(TCOFLUSH)` is not observed: on a Linux pseudo-terminal a write to
  the slave has already reached the master, so there is no untransmitted
  output to discard.
* Which constants exist and their values are the platform's. The tests
  other than the Linux-only and macOS-only ones above hold on both, which
  the Linux and macOS CI jobs verify. The BSDs are not considered.
* The module does not exist on Windows, so the whole file skips there.
"""

from __future__ import annotations

import copy
import errno
import os
import pathlib
import re
import select
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Iterator

import pytest

if sys.platform == "win32":  # pragma: no cover - the module is Unix only
    pytest.skip("platform: termios is a Unix-only module", allow_module_level=True)

import termios  # noqa: E402  (after the platform guard)

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "termios.md"
EXPECTED_BLOCKS = 7
WINDOW_SIZE_BLOCK = "termios.tcsetwinsize(slave, (24, 80))"


def readable(fd: int, timeout: float) -> bool:
    """Whether `fd` becomes readable within `timeout` seconds."""
    return bool(select.select([fd], [], [], timeout)[0])


def read_exactly(fd: int, size: int) -> bytes:
    """Read `size` bytes, however the pseudo-terminal splits them."""
    data = b""
    while len(data) < size:
        assert readable(fd, 5), f"only {data!r} arrived"
        data += os.read(fd, size - len(data))
    return data


@pytest.fixture
def pair() -> Iterator[tuple[int, int]]:
    """A fresh pseudo-terminal pair, closed afterwards."""
    try:
        master, slave = os.openpty()
    except OSError:  # pragma: no cover - only on a build without ptys
        pytest.skip("missing pty: termios tests need a working pseudo-terminal")
    try:
        yield master, slave
    finally:
        os.close(master)
        os.close(slave)


class TestTcgetattrBuildsAFixedSizeList:
    """`tcgetattr(fd)` | O(1) | O(1) | a new seven-entry list whose `cc` has
    `NCCS` entries."""

    def test_seven_entries_and_nccs_control_characters(self, pair: tuple[int, int]) -> None:
        master, slave = pair

        for fd in (slave, master):
            attributes = termios.tcgetattr(fd)

            assert len(attributes) == 7
            assert all(isinstance(value, int) for value in attributes[:6])
            assert len(attributes[6]) == termios.NCCS

    def test_every_call_builds_new_lists(self, pair: tuple[int, int]) -> None:
        _, slave = pair

        first = termios.tcgetattr(slave)
        second = termios.tcgetattr(slave)

        assert first == second
        assert first is not second
        assert first[6] is not second[6]

    def test_a_file_object_is_accepted(self, pair: tuple[int, int]) -> None:
        _, slave = pair

        with os.fdopen(os.dup(slave), "rb", buffering=0) as stream:
            assert termios.tcgetattr(stream) == termios.tcgetattr(slave)

    def test_vmin_and_vtime_are_integers_only_outside_canonical_mode(
        self, pair: tuple[int, int]
    ) -> None:
        _, slave = pair
        attributes = termios.tcgetattr(slave)
        assert attributes[3] & termios.ICANON
        assert all(isinstance(value, bytes) and len(value) == 1 for value in attributes[6])

        attributes[3] &= ~termios.ICANON
        termios.tcsetattr(slave, termios.TCSANOW, attributes)
        raw = termios.tcgetattr(slave)

        assert isinstance(raw[6][termios.VMIN], int)
        assert isinstance(raw[6][termios.VTIME], int)
        integer_slots = {termios.VMIN, termios.VTIME}
        others = [value for index, value in enumerate(raw[6]) if index not in integer_slots]
        assert all(isinstance(value, bytes) for value in others)


class TestCopyingAnAttributeList:
    """A slice copies the outer list only; a second `tcgetattr()` or a
    `deepcopy()` gives a `cc` list of its own."""

    def test_a_slice_or_list_call_shares_cc(self, pair: tuple[int, int]) -> None:
        _, slave = pair
        saved = termios.tcgetattr(slave)

        sliced = saved[:]
        listed = list(saved)
        sliced[6][termios.VEOF] = b"\x01"

        assert sliced is not saved and listed is not saved
        assert sliced[6] is saved[6] and listed[6] is saved[6]
        assert saved[6][termios.VEOF] == b"\x01"

    def test_a_second_call_and_deepcopy_do_not(self, pair: tuple[int, int]) -> None:
        _, slave = pair
        saved = termios.tcgetattr(slave)
        original = saved[6][termios.VEOF]

        separate = termios.tcgetattr(slave)
        deep = copy.deepcopy(saved)
        separate[6][termios.VEOF] = b"\x01"
        deep[6][termios.VEOF] = b"\x02"

        assert saved[6][termios.VEOF] == original == b"\x04"


class TestTcsetattr:
    """`tcsetattr(fd, when, attributes)` | O(1) | O(1); `TCSAFLUSH` discards
    unread input, `TCSANOW` does not."""

    def test_clearing_icanon_delivers_single_bytes(self, pair: tuple[int, int]) -> None:
        master, slave = pair
        attributes = termios.tcgetattr(slave)
        attributes[3] &= ~termios.ICANON
        attributes[6][termios.VMIN] = 1
        attributes[6][termios.VTIME] = 0

        termios.tcsetattr(slave, termios.TCSANOW, attributes)
        os.write(master, b"x")

        assert readable(slave, 5)
        assert os.read(slave, 1) == b"x"

    def test_a_short_list_is_rejected(self, pair: tuple[int, int]) -> None:
        _, slave = pair

        with pytest.raises(TypeError, match="7 element list"):
            termios.tcsetattr(slave, termios.TCSANOW, termios.tcgetattr(slave)[:6])

    def test_tcsaflush_discards_a_waiting_line(self, pair: tuple[int, int]) -> None:
        master, slave = pair
        quiet = termios.tcgetattr(slave)
        quiet[3] &= ~termios.ECHO  # no echoed output for TCSAFLUSH to wait on
        termios.tcsetattr(slave, termios.TCSANOW, quiet)
        os.write(master, b"typed ahead\n")
        assert readable(slave, 5)

        termios.tcsetattr(slave, termios.TCSAFLUSH, quiet)

        assert not readable(slave, 0.2)

    def test_tcsanow_keeps_it(self, pair: tuple[int, int]) -> None:
        master, slave = pair
        os.write(master, b"typed ahead\n")
        assert readable(slave, 5)

        termios.tcsetattr(slave, termios.TCSANOW, termios.tcgetattr(slave))

        assert readable(slave, 0.2)
        assert os.read(slave, 100) == b"typed ahead\n"


class TestAModeOutlivesTheProcess:
    """A terminal left in a changed mode stays that way after the process that
    changed it exits, which is why the page restores in `finally`."""

    def test_a_child_s_change_survives_its_exit(self, pair: tuple[int, int]) -> None:
        _, slave = pair
        assert termios.tcgetattr(slave)[3] & termios.ICANON
        child = (
            "import sys, termios\n"
            "fd = int(sys.argv[1])\n"
            "attributes = termios.tcgetattr(fd)\n"
            "attributes[3] &= ~termios.ICANON\n"
            "termios.tcsetattr(fd, termios.TCSANOW, attributes)\n"
        )

        subprocess.run(
            [sys.executable, "-c", child, str(slave)],
            pass_fds=(slave,),
            check=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )

        assert not termios.tcgetattr(slave)[3] & termios.ICANON


class TestEchoIsAnLflagBit:
    """Clearing `ECHO` on a separate list stops the echo, and restoring the
    saved list brings it back: the "Reading Without Echo" pattern."""

    def test_echo_on_then_off_then_restored(self, pair: tuple[int, int]) -> None:
        master, slave = pair
        saved = termios.tcgetattr(slave)
        quiet = termios.tcgetattr(slave)
        quiet[3] &= ~termios.ECHO

        os.write(master, b"shown\n")
        assert os.read(slave, 100) == b"shown\n"
        assert read_exactly(master, 7) == b"shown\r\n"

        try:
            termios.tcsetattr(slave, termios.TCSADRAIN, quiet)
            os.write(master, b"secret\n")
            assert os.read(slave, 100) == b"secret\n"
        finally:
            termios.tcsetattr(slave, termios.TCSADRAIN, saved)

        assert not readable(master, 0.2)
        assert termios.tcgetattr(slave) == saved


class TestQueueControl:
    """`tcflush`, `tcflow`, `tcdrain` and `tcsendbreak` | O(1) | O(1)."""

    def test_tcflush_discards_unread_input(self, pair: tuple[int, int]) -> None:
        master, slave = pair
        os.write(master, b"stale\n")
        assert readable(slave, 5)

        termios.tcflush(slave, termios.TCIFLUSH)

        assert not readable(slave, 0.2)

    @pytest.mark.skipif(
        sys.platform != "linux",
        reason="a write held by TCOOFF is Linux pty behaviour; BSD queues it "
        "(CPython's Lib/test/test_termios.py runs this on Linux only)",
    )
    def test_tcooff_holds_writes_until_tcoon(self, pair: tuple[int, int]) -> None:
        master, slave = pair

        termios.tcflow(slave, termios.TCOOFF)
        os.set_blocking(slave, False)
        with pytest.raises(BlockingIOError):
            os.write(slave, b"held")
        assert not readable(master, 0.2)

        termios.tcflow(slave, termios.TCOON)
        os.set_blocking(slave, True)
        os.write(slave, b"sent")

        assert read_exactly(master, 4) == b"sent"

    @pytest.mark.skipif(
        sys.platform != "linux",
        reason="a write held by TCOOFF is Linux pty behaviour; BSD queues it "
        "(CPython's Lib/test/test_termios.py runs this on Linux only)",
    )
    def test_a_blocking_write_waits_for_tcoon(self, pair: tuple[int, int]) -> None:
        master, slave = pair
        termios.tcflow(slave, termios.TCOOFF)
        about_to_write = threading.Event()

        def write() -> None:
            about_to_write.set()
            os.write(slave, b"held")

        writer = threading.Thread(target=write, daemon=True)

        writer.start()
        assert about_to_write.wait(5)
        writer.join(0.3)
        waited = writer.is_alive()
        termios.tcflow(slave, termios.TCOON)
        writer.join(5)

        assert waited, "a blocking write finished while output was suspended"
        assert not writer.is_alive()
        assert read_exactly(master, 4) == b"held"

    def test_tcioff_and_tcion_send_stop_and_start(self, pair: tuple[int, int]) -> None:
        master, slave = pair
        control = termios.tcgetattr(slave)[6]

        termios.tcflow(slave, termios.TCIOFF)
        assert read_exactly(master, 1) == control[termios.VSTOP]

        termios.tcflow(slave, termios.TCION)
        assert read_exactly(master, 1) == control[termios.VSTART]

    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason="BSD ttywait() blocks tcdrain until the master reads the queued output",
    )
    @pytest.mark.timing
    def test_tcdrain_returns_at_once_on_a_pseudo_terminal(self, pair: tuple[int, int]) -> None:
        _, slave = pair
        os.write(slave, b"q" * 100)  # the master never reads it

        start = time.perf_counter()
        termios.tcdrain(slave)
        elapsed = time.perf_counter() - start

        assert elapsed < 1, f"tcdrain took {elapsed:.3f}s on a pseudo-terminal"

    @pytest.mark.skipif(
        sys.platform == "darwin",
        reason="macOS libc tcsendbreak sleeps ~0.4 s in select() between TIOCSBRK and TIOCCBRK",
    )
    @pytest.mark.timing
    def test_tcsendbreak_returns_at_once_on_a_pseudo_terminal(self, pair: tuple[int, int]) -> None:
        _, slave = pair

        start = time.perf_counter()
        termios.tcsendbreak(slave, 0)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.2, f"a zero-duration break took {elapsed:.3f}s on a pseudo-terminal"

    @pytest.mark.skipif(sys.platform != "darwin", reason="the BSD terminal driver's ttywait()")
    def test_tcdrain_waits_for_the_master_to_read_on_macos(self, pair: tuple[int, int]) -> None:
        master, slave = pair
        os.write(slave, b"q" * 100)
        started = threading.Event()
        drained = threading.Event()

        def drain() -> None:
            started.set()
            termios.tcdrain(slave)
            drained.set()

        threading.Thread(target=drain, daemon=True).start()
        assert started.wait(5), "the draining thread never started"
        waited = not drained.wait(0.5)
        received = read_exactly(master, 100)

        assert waited, "tcdrain returned while the master had read nothing"
        assert drained.wait(5), "tcdrain still waiting after the master read everything"
        assert received == b"q" * 100

    @pytest.mark.skipif(sys.platform != "darwin", reason="the BSD libc tcsendbreak()")
    @pytest.mark.timing
    def test_tcsendbreak_sleeps_on_macos(self, pair: tuple[int, int]) -> None:
        _, slave = pair

        start = time.perf_counter()
        termios.tcsendbreak(slave, 0)
        elapsed = time.perf_counter() - start

        assert elapsed >= 0.3, f"a zero-duration break took {elapsed:.3f}s on macOS"


class TestWindowSize:
    """`tcgetwinsize` and `tcsetwinsize` | O(1) | O(1) | Python 3.11+."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_a_size_round_trips_and_both_ends_see_it(self, pair: tuple[int, int]) -> None:
        master, slave = pair

        termios.tcsetwinsize(slave, (24, 80))  # type: ignore[attr-defined]

        assert termios.tcgetwinsize(slave) == (24, 80)  # type: ignore[attr-defined]
        assert termios.tcgetwinsize(master) == (24, 80)  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="present from 3.11")
    def test_absent_before_311(self) -> None:
        assert not hasattr(termios, "tcgetwinsize")
        assert not hasattr(termios, "tcsetwinsize")


class TestErrors:
    """`termios.error` | raised with `(errno, message)` when a call fails."""

    def test_a_pipe_is_not_a_terminal(self) -> None:
        read_end, write_end = os.pipe()
        try:
            with pytest.raises(termios.error) as raised:
                termios.tcgetattr(read_end)
        finally:
            os.close(read_end)
            os.close(write_end)

        number, message = raised.value.args
        assert number == errno.ENOTTY
        assert message == os.strerror(errno.ENOTTY)
        assert issubclass(termios.error, Exception)


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
    """Each block runs in its own subprocess on its own pseudo-terminal pair,
    and asserts its own result. The window-size block needs Python 3.11."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS
        assert sum(WINDOW_SIZE_BLOCK in source for _, source in _blocks()) == 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if WINDOW_SIZE_BLOCK in source and sys.version_info < (3, 11):
                continue  # tcsetwinsize() and tcgetwinsize() were added in 3.11
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS - (sys.version_info < (3, 11))
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        target = "assert not select.select([master], [], [], 0.2)[0]  # nothing was echoed"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, target.replace("assert not", "assert"), 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
