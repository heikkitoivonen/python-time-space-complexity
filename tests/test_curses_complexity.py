"""Tests for docs/stdlib/curses.md.

The page splits the module's cost three ways: allocating a window is its whole
cell array, editing cells is local work against that array, and only the update
step talks to the terminal. Everything here runs inside a pseudo-terminal,
because `initscr()` needs one, and most rows are settled by counting bytes or
by identity rather than by a clock.

The harness holds the child at two barriers. The first is released once the
parent has sized the pseudo-terminal, so `initscr()` cannot read a size the
test did not set. The second is raised by the child once its input modes are
set, and is where the parent hands over any queued keystrokes. `pty.fork()`
returns in both processes at once, so without them both the size a test
asserts and the mode its input arrives under would depend on which process ran
first.

Measurement scope:

* The update path is settled by the bytes curses actually writes. The harness
  reads the pty master, so programs differing only in one call can be compared
  by output volume with no tolerance at all. Each one fills the screen,
  refreshes, makes the call under test, then fills the screen with the same
  characters and refreshes again - so a diffing update has nothing to say and
  the total stays where the first fill left it. `touchwin()` and `erase()` hold
  it there exactly; `clear()`, `clearok(True)` and `redrawwin()` roughly double
  it. `clear()` and a bare `clearok(True)` come out equal, which pins the
  repaint on the arming rather than on the blanking.
* `noutrefresh()` and `doupdate()` are separated by a stopwatch. Two hundred
  windows refreshed one at a time run the screen diff two hundred times and
  show every intermediate state; the same windows pushed through
  `noutrefresh()` and one `doupdate()` run it once, from the final screen. The
  measurement is of the two ways of getting a frame out, not of the diff in
  isolation - the intermediate frames are part of what the separate path costs.
  Every sample touches all two hundred windows first, so none of them is timing
  a window that had nothing to say.
* `newwin()` against `derwin()` is the sharpest framing available for the
  sharing claim, and it needs no clock in one direction: a write through a
  derived window is readable through its parent. The clock covers the other
  direction, where sixteen times the columns at a fixed row count leaves
  `derwin()` unchanged and would multiply any per-cell allocation by sixteen.
* The `instr()` and `getstr()` ceiling is exact, not asymptotic. Asking for
  3000 bytes of a 3000-byte row returns 2047 on 3.14 and 1023 before it, so the
  test reads the boundary off `sys.version_info` and asserts the number. The
  `getstr()` half feeds the characters through the pty rather than simulating
  them, which is why the harness takes an input string at all.
* `curses.panel` carries two costs that both grow with p, and they are pinned
  apart. The list walk is timed without touching the deck at all: the newest
  and the oldest panel of four thousand sit at opposite ends of the global
  list, so `below()` on one and `above()` on the other separate by two orders
  of magnitude even though the deck positions involved are identical.
  `replace()` sits beside them because `_curses_panel.c` has it take the same
  walk before swapping the window; the timing corroborates that reading rather
  than establishing it on its own. `window()`, which searches nothing, does not
  move. The deck cost is timed
  the other way, across two deck sizes, for `top()`, `bottom()`, `hide()` and
  `move()`, and across two panel heights for `update_panels()`, whose panels
  stay at one set of coordinates so that the pairs which overlap do not change
  with them; `show()` and `hidden()` are held against `hide()`
  on one deck, because comparing two measurements of a few tens of nanoseconds
  across processes is a division the clock can make zero.
  Each deck operation gets a process to itself, so that the panel it measures
  is in the visibility and deck position that operation needs. A panel another
  measurement had hidden would make `move()` time as a constant, which is the
  reading these tests exist to rule out.
* `new_panel()` is timed in batches of 32 with prebuilt windows and retained
  results, at deck sizes 64 and 6,400. The 100x interval costs under 15x
  for creation and over 20x for removal, whose clock covers only dropping the
  last reference; window setup and cleanup of creation batches are untimed.
* `syncup()` is varied in two directions on windows built the same way: the
  depth at a fixed row count, and the row count at a fixed depth. Both move it,
  which is what makes the bound the product rather than the depth alone.
  `syncdown()` is measured over the same row change and `cursyncup()`, which
  carries only the cursor, is measured there too and does not move.
* `mvwin()` and `mvderwin()` are both varied by height, and both grow. The
  first does so only slightly, so it is measured on a screen four hundred rows
  tall; a pair separated by fifteen rows leaves its line marking under the call
  overhead and reads as a constant.
* `putwin()` is settled by the size of the file it writes and by reading the
  window back: the serialized form grows with the area, and the restored window
  carries the characters and the rendition, not just the shape. Its O(1) space
  row is about auxiliary memory, which is a different quantity and is taken
  from the source rather than measured.
* What `initscr()` and `start_color()` publish onto the `curses` package is
  checked by attribute existence in a fresh process each time, since the first
  call in a process is the only one that can show the absence.
* The three ways an ordinary write stops being local are settled separately and
  by observation: `immedok(True)` and `echochar()` by the bytes they put on the
  terminal against the same program without them, and `syncok(True)` by the
  parent window's touch flag, which is off in the same test with the setting
  off. `getch()` refreshing a window that is holding changes is another byte
  comparison, against the same read on a window with nothing pending.
* `init_pair()` is measured two ways, because neither reaches the other's half
  of the row. Its O(R·C) is a stopwatch over two screen sizes, since the scan
  it does puts nothing on the terminal. What that scan arms takes three runs,
  because the two that would separate it are not enough: redefining the pair the screen is painted
  in writes nothing by itself, and the run without a following update pins
  that. It is the update after it that repaints, and the run with one shows it;
  the third redefines a pair nothing is painted in and that update stays
  silent.

Not settled here:

* Which calls return `ERR` on which terminal is the terminfo entry's business,
  not Python's. Four out-of-range writes and moves are asserted to raise
  `curses.error`; the rest is not a claim about the module.
* `napms()` is asserted to delay its caller and nothing more; whether other
  threads run through it is not measured here. `delay_output()` has no test at
  all: whether it pads the output stream or sleeps depends on the terminal's
  capabilities, and how long the pause lasts depends on the line speed, which
  no test here sets.
* `baudrate()`, `longname()`, `termname()`, `termattrs()`, `has_ic()`,
  `has_il()` and the `tigetflag`/`tigetnum`/`tigetstr` trio report the terminfo
  entry. Their O(1) rows say the lookup does not scan the database; the values
  belong to whichever entry `TERM` names and are not asserted.
* Mouse reporting needs a terminal that sends the events. `mousemask()` is
  exercised, `getmouse()` is not.
* This module is absent on Windows, and the page documents no Windows-only
  API, so nothing here is platform-gated beyond needing a pty.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import functools
import os
import pathlib
import pickle
import pty
import re
import select
import signal
import struct
import subprocess
import sys
import termios
import textwrap
import time
import traceback
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "stdlib" / "curses.md"
EXPECTED_BLOCKS = 5

# The ceiling `instr()` and `getstr()` read into. gh-134209 moved it to a
# heap-allocated 2048-byte buffer in 3.14; before that it was a 1024-byte stack
# buffer. Both spend the last byte on the terminator.
READ_CEILING = 2047 if sys.version_info >= (3, 14) else 1023

ROWS, COLS = 40, 120

# Told apart from b"", which means the child is done with that descriptor.
_NOTHING_YET = b"\x00nothing-yet"

# How long a pty child may take before the parent kills it and fails the test.
TIMEOUT = 120


def _write_all(fd: int, data: bytes) -> None:
    """os.write() may take only part of a payload; a truncated pickle is worse."""
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def _report(
    prepare: Callable[[], Any] | None,
    func: Callable[[Any], Any],
    gate_fd: int,
    ready_fd: int,
    write_fd: int,
) -> None:  # pragma: no cover - the child
    """Run prepare() then func() in the pty child, reporting back at each step.

    The child waits twice. The first wait lets the parent size the terminal
    before `initscr()` reads that size. The second tells the parent that the
    input modes are set, so anything fed to the terminal is read in the mode the
    test meant rather than by the line discipline that was there beforehand.
    """
    os.read(gate_fd, 1)
    os.close(gate_fd)
    os.environ["TERM"] = "xterm"
    # curses honours these over the size the terminal reports, and this process
    # inherited whatever the surrounding shell had.
    os.environ.pop("LINES", None)
    os.environ.pop("COLUMNS", None)

    payload: tuple[str, Any]
    try:
        prepared = prepare() if prepare is not None else None
    except BaseException:
        payload = ("err", traceback.format_exc())
    else:
        os.write(ready_fd, b"\x01")
        try:
            payload = ("ok", func(prepared))
        except BaseException:
            payload = ("err", traceback.format_exc())
    os.close(ready_fd)
    try:
        _write_all(write_fd, pickle.dumps(payload))
        os.close(write_fd)
    except OSError:
        pass


def _close(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


def _read(fd: int, is_master: bool) -> bytes:
    """Read what is there, treating only the pty's own hangup as end of input.

    A pty master reports the child's exit as EIO. Any other error would
    otherwise pass for EOF and silently truncate the byte counts this module
    compares.
    """
    try:
        return os.read(fd, 65536)
    except BlockingIOError:
        # The master is non-blocking, so select() can call it readable and the
        # data be gone by the time it is read. Not end of input.
        return _NOTHING_YET
    except OSError as error:
        if is_master and error.errno == errno.EIO:
            return b""
        raise


def _send_some(master: int, pending: bytes) -> bytes:
    """Hand over what the terminal will take, and keep the rest for next time.

    Writable readiness promises room, not room for all of it, and the master is
    non-blocking so a full buffer comes back rather than parking the caller.
    """
    try:
        return pending[os.write(master, pending) :]
    except BlockingIOError:
        return pending


def _pump(
    read_fd: int, ready_fd: int, master: int, feed: bytes, deadline: float
) -> tuple[list[bytes], int, bool]:
    """Read the report pipe, the readiness pipe and the terminal as one.

    Waiting on any of them alone would hang as soon as the child filled
    another's buffer. The readiness byte is where queued input starts being
    handed over, because by then the child has set the terminal modes it meant
    to read in; the input then goes out through the same loop, so a full input
    buffer cannot stop output being drained.
    """
    chunks: list[bytes] = []
    written = 0
    live = {read_fd, master, ready_fd}
    pending = b""
    while live:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return chunks, written, True
        writable_side = [master] if pending else []
        readable, writable, _ = select.select(list(live), writable_side, [], remaining)
        if not readable and not writable:
            return chunks, written, True
        if writable:
            # Sent a piece at a time, so a terminal whose input buffer is full
            # cannot stop the parent draining output or checking its deadline.
            pending = _send_some(master, pending)
        for fd in readable:
            data = _read(fd, fd == master)
            if data is _NOTHING_YET:
                continue
            if not data and fd != ready_fd:
                live.discard(fd)
                continue
            if fd == ready_fd:
                pending = feed if data else pending
                live.discard(ready_fd)
            elif fd == read_fd:
                chunks.append(data)
            else:
                written += len(data)
    return chunks, written, False


def _three_pipes() -> list[int]:
    """The gate, readiness and report pipes, owned from the moment they exist."""
    opened: list[int] = []
    try:
        for _ in range(3):
            opened.extend(os.pipe())
    except OSError:  # pragma: no cover - only when the process runs out of fds
        for fd in opened:
            _close(fd)
        raise
    return opened


def _unpack(chunks: list[bytes], timed_out: bool, status: int) -> Any:
    """The child's value, or an assertion naming how it failed to send one."""
    if timed_out:
        raise AssertionError(f"the pty child did not finish within {TIMEOUT} seconds")
    if status != 0:
        raise AssertionError(f"the pty child exited abnormally; wait status {status}")
    reported = b"".join(chunks)
    if not reported:
        raise AssertionError("the pty child exited cleanly but sent no report")
    kind, value = pickle.loads(reported)
    if kind == "err":
        raise AssertionError(f"the pty child raised:\n{value}")
    return value


def _reap(pid: int, deadline: float, timed_out: bool) -> tuple[bool, int, bool]:
    """Wait for the child, but only until the deadline the reading had.

    Every descriptor reaching end of input is not proof the child exited: it can
    close them and stay alive. So this polls rather than blocking, and hands
    back a timeout for the caller to kill on.
    """
    while not timed_out:
        done, code = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return True, code, False
        if time.monotonic() >= deadline:
            timed_out = True
        else:
            time.sleep(0.005)
    return False, 0, timed_out


def _in_terminal(
    func: Callable[[Any], Any],
    feed: bytes = b"",
    rows: int = ROWS,
    prepare: Callable[[], Any] | None = None,
) -> Any:
    """Run func() in a pty child and return its value and the bytes it wrote.

    The child inherits this module, so func is an ordinary closure rather than
    source text. Only its return value crosses back, through a pipe kept apart
    from the terminal stream so that curses output cannot corrupt it.

    One loop reads the report pipe, the readiness pipe and the terminal
    together, under a single deadline. Waiting on any of them alone would hang
    as soon as the child filled another's buffer.
    """
    opened = _three_pipes()
    gate_read, gate_write, ready_read, ready_write, read_fd, write_fd = opened
    try:
        pid, master = pty.fork()
    except OSError:  # pragma: no cover - only when the process runs out of fds
        for fd in opened:
            _close(fd)
        raise
    if pid == 0:  # pragma: no cover - the child never reports coverage
        try:
            for fd in (gate_write, ready_read, read_fd):
                os.close(fd)
            _report(prepare, func, gate_read, ready_write, write_fd)
        finally:
            # Anything escaping _report would otherwise unwind into the copy of
            # pytest this process was forked from, and run its teardown twice.
            os._exit(0)

    for fd in (gate_read, ready_write, write_fd):
        os.close(fd)
    deadline = time.monotonic() + TIMEOUT
    timed_out = True
    reaped = False
    status = 0
    try:
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, COLS, 0, 0))
        # Neither side of the terminal may park this loop: it is the only thing
        # draining output and the only thing watching the deadline.
        os.set_blocking(master, False)
        os.write(gate_write, b"\x01")
        chunks, written, timed_out = _pump(read_fd, ready_read, master, feed, deadline)
        reaped, status, timed_out = _reap(pid, deadline, timed_out)
    except BaseException:
        # Sizing the terminal, releasing the gate or selecting can all raise,
        # and the child may still be waiting on a gate this frame owns.
        timed_out = True
        raise
    finally:
        if timed_out:
            # waitpid() would otherwise block for as long as the child stays stuck.
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        try:
            if not reaped:
                status = os.waitpid(pid, 0)[1]
        finally:
            for fd in (gate_write, ready_read, read_fd, master):
                _close(fd)

    return _unpack(chunks, timed_out, status), written


def _screen(func: Callable[[Any], Any], feed: bytes = b"", rows: int = ROWS) -> Any:
    """Run func(stdscr) between initscr() and endwin(), inside a pty."""

    def prepare() -> Any:
        import curses

        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        return stdscr

    def body(stdscr: Any) -> Any:
        import curses

        try:
            return func(stdscr)
        finally:
            curses.endwin()

    return _in_terminal(body, feed=feed, rows=rows, prepare=prepare)


def _best(make: Callable[[], Callable[[], Any]], repeat: int = 7) -> float:
    """The fastest of repeat runs, each against a subject make() builds fresh.

    A window that has already been resized, or a background that is already the
    one being set, makes the second call a no-op, so the subject cannot be
    shared across repetitions.
    """
    timings: list[float] = []
    for _ in range(repeat):
        run = make()
        start = time.perf_counter()
        run()
        timings.append(time.perf_counter() - start)
    return min(timings)


def _probe(_: Any) -> str:
    """Report whether curses can start here, without raising out of the child.

    The child swallows its own failure so that `_terminal_is_usable` does not
    have to catch every exception: a broken harness still raises, rather than
    skipping the whole module as though the machine had no terminal.
    """
    try:
        import curses

        curses.initscr()
        curses.endwin()
    except Exception as error:  # pragma: no cover - only on a build without terminfo
        return f"unavailable: {error}"
    return "ok"


@functools.lru_cache(maxsize=1)
def _terminal_is_usable() -> bool:
    value, _ = _in_terminal(_probe)
    return value == "ok"


# `pty.fork()` in a process that has xdist's communication threads running can
# deadlock in the child, so the whole module runs without workers. The probe is
# a fixture rather than a `skipif` for the same reason: a module-level call
# would fork during collection, which happens in those workers even when every
# test in the file is about to be deselected.
pytestmark = pytest.mark.serial


@pytest.fixture(autouse=True)
def _needs_a_terminal() -> None:
    if not _terminal_is_usable():  # pragma: no cover - only on a build without terminfo
        pytest.skip("curses needs a pseudo-terminal and a terminfo entry for TERM")


class TestTheHarness:
    """A harness that cannot fail proves nothing about what it ran."""

    def test_a_failure_inside_the_child_reaches_the_test(self) -> None:
        def explode(_: Any) -> None:
            raise ValueError("deliberate")

        with pytest.raises(AssertionError, match="deliberate"):
            _in_terminal(explode)

    def test_an_assertion_inside_the_child_reaches_the_test(self) -> None:
        with pytest.raises(AssertionError, match="AssertionError"):
            _screen(lambda stdscr: (_ for _ in ()).throw(AssertionError("inner")))

    def test_the_child_sees_the_size_the_parent_set(self) -> None:
        """This is what the first gate buys.

        `pty.fork()` returns in both processes at once, and the size is set
        from the parent afterwards. A child that ran straight on would read
        whichever size the pty was created with.
        """

        def sizes(stdscr: Any) -> tuple[tuple[int, int], tuple[int, int]]:
            import curses

            return (stdscr.getmaxyx(), (curses.LINES, curses.COLS))

        (got, _) = _screen(sizes)

        assert got == ((ROWS, COLS), (ROWS, COLS))


class TestInitialisation:
    """What initscr() and start_color() publish, and what wrapper() restores."""

    def test_initscr_publishes_names_that_do_not_exist_before_it(self) -> None:
        def names(_: Any) -> dict[str, dict[str, bool]]:
            import curses

            before = {
                "LINES": hasattr(curses, "LINES"),
                "COLS": hasattr(curses, "COLS"),
                "ACS_HLINE": hasattr(curses, "ACS_HLINE"),
            }
            curses.initscr()
            try:
                after = {name: hasattr(curses, name) for name in before}
            finally:
                curses.endwin()
            return {"before": before, "after": after}

        (got, _) = _in_terminal(names)

        assert got["before"] == {"LINES": False, "COLS": False, "ACS_HLINE": False}
        assert got["after"] == {"LINES": True, "COLS": True, "ACS_HLINE": True}

    def test_start_color_publishes_the_colour_counts(self) -> None:
        def counts(_: Any) -> dict[str, Any]:
            import curses

            curses.initscr()
            try:
                before = hasattr(curses, "COLORS")
                curses.start_color()
                return {"before": before, "after": curses.COLORS > 0}
            finally:
                curses.endwin()

        (got, _) = _in_terminal(counts)

        assert got == {"before": False, "after": True}

    def test_filter_cuts_the_screen_down_to_one_line(self) -> None:
        def filtered(_: Any) -> tuple[tuple[int, int], int]:
            import curses

            curses.filter()
            stdscr = curses.initscr()
            try:
                return (stdscr.getmaxyx(), curses.LINES)
            finally:
                curses.endwin()

        (got, _) = _in_terminal(filtered)

        # The pty is ROWS tall; filter() must be called before initscr().
        assert got == ((1, COLS), 1)

    def test_use_env_decides_where_the_size_comes_from(self) -> None:
        def sized(flag: bool) -> Callable[[Any], tuple[int, int]]:
            def run(_: Any) -> tuple[int, int]:
                import curses

                os.environ["LINES"] = "11"
                os.environ["COLUMNS"] = "33"
                curses.use_env(flag)
                stdscr = curses.initscr()
                try:
                    return stdscr.getmaxyx()
                finally:
                    curses.endwin()

            return run

        (honoured, _) = _in_terminal(sized(True))
        (ignored, _) = _in_terminal(sized(False))

        assert honoured == (11, 33)
        # Not the pty's size either: with use_env off the terminfo entry decides.
        assert ignored != (11, 33)
        assert ignored != (ROWS, COLS)

    def test_a_window_cannot_be_constructed(self) -> None:
        def build(_: Any) -> str:
            import curses

            curses.initscr()
            try:
                curses.window(3, 3)  # type: ignore[call-arg]
            except TypeError as error:
                return str(error)
            finally:
                curses.endwin()
            return "no error"

        (message, _) = _in_terminal(build)

        assert "cannot create" in message

    def test_endwin_keeps_the_windows_and_refresh_resumes_curses(self) -> None:
        def cycle(stdscr: Any) -> dict[str, Any]:
            import curses

            stdscr.addstr(0, 0, "kept")
            stdscr.refresh()
            curses.endwin()
            ended = curses.isendwin()
            stdscr.refresh()
            return {"ended": ended, "resumed": not curses.isendwin(), "cell": stdscr.instr(0, 0, 4)}

        (got, _) = _screen(cycle)

        assert got == {"ended": True, "resumed": True, "cell": b"kept"}

    def test_wrapper_restores_the_terminal_when_the_callable_raises(self) -> None:
        def run(_: Any) -> dict[str, Any]:
            import curses
            import termios

            calls: list[str] = []
            for name in ("noecho", "echo", "cbreak", "nocbreak", "start_color", "endwin"):
                original = getattr(curses, name)

                def spy(*args: Any, _name: str = name, _original: Any = original) -> Any:
                    calls.append(_name)
                    return _original(*args)

                setattr(curses, name, spy)

            def boom(stdscr: Any) -> None:
                stdscr.addstr(0, 0, "about to fail")
                raise RuntimeError("from inside wrapper")

            raised = ""
            try:
                curses.wrapper(boom)
            except RuntimeError as error:
                raised = str(error)
            # The terminal is back in the mode a shell expects: ECHO on and
            # canonical input, both of which wrapper() turned off.
            attributes = termios.tcgetattr(0)[3]
            return {
                "raised": raised,
                "ended": curses.isendwin(),
                "calls": calls,
                "echo_on": bool(attributes & termios.ECHO),
                "canonical": bool(attributes & termios.ICANON),
            }

        (got, _) = _in_terminal(run)

        assert got["raised"] == "from inside wrapper"
        assert got["ended"] is True
        # Set up on the way in, undone on the way out, in that order. keypad()
        # is a window method rather than a module one, so it is not spied here;
        # start_color() has no inverse and wrapper() does not attempt one.
        assert got["calls"] == ["noecho", "cbreak", "start_color", "echo", "nocbreak", "endwin"]
        assert got["echo_on"] is True
        assert got["canonical"] is True

    def test_wrapper_hands_the_screen_and_its_own_arguments_to_the_callable(self) -> None:
        def run(_: Any) -> Any:
            import curses

            def body(stdscr: Any, first: int, second: str = "") -> tuple[Any, int, str]:
                return (stdscr.getmaxyx(), first, second)

            return curses.wrapper(body, 7, second="ok")

        (got, _) = _in_terminal(run)

        assert got == ((ROWS, COLS), 7, "ok")


class TestWindowAllocation:
    """newwin() allocates cells; the derived constructors borrow them."""

    @pytest.mark.timing
    def test_allocating_a_window_tracks_the_cell_count(self) -> None:
        def measure(stdscr: Any) -> dict[str, float]:
            import curses

            # Kept, so the clock covers the allocation and not the release.
            kept: list[Any] = []

            def build(factory: Any, rows: int, cols: int) -> Callable[[], Callable[[], Any]]:
                return lambda: lambda: kept.append(factory(rows, cols))

            result = {
                "pad_small": _best(build(curses.newpad, 64, 64)),
                "pad_large": _best(build(curses.newpad, 1024, 1024)),
                # newwin cannot exceed the screen, so its pair is smaller.
                "win_small": _best(build(curses.newwin, 2, 8)),
                "win_large": _best(build(curses.newwin, ROWS - 1, COLS - 1)),
            }
            assert kept
            return result

        (got, _) = _screen(measure)

        pad = got["pad_large"] / got["pad_small"]
        window = got["win_large"] / got["win_small"]
        assert pad > 32, f"256x the cells made newpad only x{pad:.1f}"
        # 39x120 cells against 2x8. The screen caps how far this pair can be
        # spread, and a 16-cell window is mostly fixed cost, so the ratio here
        # only has to exclude a constant; the pad pair above carries the bound.
        assert window > 3, f"292x the cells made newwin only x{window:.1f}"

    @pytest.mark.timing
    def test_a_derived_window_does_not_pay_for_its_columns(self) -> None:
        def measure(stdscr: Any) -> float:
            import curses

            parent = curses.newpad(1024, 1024)
            narrow = _best(lambda: lambda: parent.derwin(1024, 64, 0, 0))
            wide = _best(lambda: lambda: parent.derwin(1024, 1024, 0, 0))
            return wide / narrow

        (ratio, _) = _screen(measure)

        assert ratio < 4, f"16x the columns made derwin x{ratio:.1f}; it should not move"

    def test_a_derived_window_shares_its_parents_cells(self) -> None:
        def share(stdscr: Any) -> dict[str, bytes]:
            import curses

            parent = curses.newwin(10, 40, 0, 0)
            view = parent.derwin(3, 10, 2, 5)
            view.addstr(0, 0, "ZZZ")
            seen_by_parent = parent.instr(2, 5, 3)
            parent.addstr(2, 5, "QQQ")
            return {"parent": seen_by_parent, "view": view.instr(0, 0, 3)}

        (got, _) = _screen(share)

        assert got == {"parent": b"ZZZ", "view": b"QQQ"}

    def test_subwin_takes_screen_coordinates_and_derwin_parent_relative_ones(self) -> None:
        def place(stdscr: Any) -> dict[str, Any]:
            import curses

            base = curses.newwin(10, 20, 5, 10)
            return {
                "subwin": base.subwin(3, 5, 6, 12).getbegyx(),
                "derwin": base.derwin(3, 5, 1, 2).getbegyx(),
                "paryx": base.derwin(3, 5, 1, 2).getparyx(),
                "orphan": base.getparyx(),
            }

        (got, _) = _screen(place)

        assert got["subwin"] == (6, 12)
        assert got["derwin"] == (6, 12)
        assert got["paryx"] == (1, 2)
        assert got["orphan"] == (-1, -1)

    @pytest.mark.timing
    def test_resize_cost_tracks_the_cell_count(self) -> None:
        def measure(stdscr: Any) -> float:
            import curses

            def grow(rows: int, cols: int) -> Callable[[], Callable[[], Any]]:
                def make() -> Callable[[], Any]:
                    window = curses.newpad(4, 4)
                    return lambda: window.resize(rows, cols)

                return make

            return _best(grow(1024, 1024), 5) / _best(grow(64, 64), 5)

        (ratio, _) = _screen(measure)

        assert ratio > 32, f"256x the cells made resize only x{ratio:.1f}"

    def test_putwin_writes_a_file_that_grows_with_the_area(self, tmp_path: pathlib.Path) -> None:
        target = str(tmp_path)

        def dump(stdscr: Any) -> dict[str, Any]:
            import curses

            sizes: dict[str, Any] = {}
            for rows, cols in ((10, 10), (100, 100)):
                path = os.path.join(target, f"win{rows}x{cols}")
                window = curses.newpad(rows, cols)
                window.addstr(0, 0, "ROUNDTRIP", curses.A_BOLD)
                with open(path, "wb") as handle:
                    window.putwin(handle)
                with open(path, "rb") as handle:
                    restored = curses.getwin(handle)
                sizes[f"{rows}x{cols}"] = (
                    os.path.getsize(path),
                    restored.getmaxyx(),
                    restored.instr(0, 0, 9),
                    bool(restored.inch(0, 0) & curses.A_BOLD),
                )
            return sizes

        (got, _) = _screen(dump)

        small_bytes, small_shape, small_text, small_bold = got["10x10"]
        large_bytes, large_shape, large_text, large_bold = got["100x100"]
        assert small_shape == (10, 10)
        assert large_shape == (100, 100)
        # A reader that kept only the header would still pass on shape alone.
        assert small_text == large_text == b"ROUNDTRIP"
        assert small_bold is large_bold is True
        # 100x the cells. A fixed header keeps the ratio under 100, and anything
        # that stored only the window's header would not move at all.
        assert large_bytes > small_bytes * 20

    @pytest.mark.timing
    def test_resize_term_pays_for_every_window_curses_holds(self) -> None:
        def measure(stdscr: Any) -> float:
            import curses
            import itertools

            shapes = itertools.cycle([(ROWS - 1, COLS - 1), (ROWS, COLS)])

            def flip() -> Callable[[], Any]:
                rows, cols = next(shapes)
                # Asking for the size curses already has is a no-op, and _best
                # takes the minimum, so one of those would decide the result.
                assert curses.is_term_resized(rows, cols), "this resize would do nothing"
                return lambda: curses.resize_term(rows, cols)

            alone = _best(flip, 5)
            held = [curses.newwin(20, 60, 0, 0) for _ in range(1500)]
            crowded = _best(flip, 5)
            assert len(held) == 1500
            return crowded / alone

        (ratio, _) = _screen(measure)

        assert ratio > 4, f"1500 extra windows made resize_term only x{ratio:.1f}"


class TestWritingCells:
    """Edits to a window's own array, none of which reach the terminal."""

    @pytest.mark.timing
    def test_addstr_is_linear_in_the_string(self) -> None:
        def measure(stdscr: Any) -> float:
            import curses

            pad = curses.newpad(4, 20000)
            short = "a" * 500
            long = "a" * 16000
            return _best(lambda: lambda: pad.addstr(0, 0, long)) / _best(
                lambda: lambda: pad.addstr(0, 0, short)
            )

        (ratio, _) = _screen(measure)

        assert ratio > 8, f"32x the characters made addstr only x{ratio:.1f}"
        # Quadratic over the same step would be near 1024.
        assert ratio < 200, f"32x the characters made addstr x{ratio:.1f}"

    @pytest.mark.timing
    def test_addnstr_converts_the_whole_argument_whatever_it_writes(self) -> None:
        """The `len(str)` term: the cap is on the writing, not the conversion."""

        def measure(stdscr: Any) -> dict[str, float]:
            import curses

            pad = curses.newpad(4, 4000)
            short, long = "a" * 500, "a" * 64000
            return {
                "short": _best(lambda: lambda: pad.addnstr(0, 0, short, 8)),
                "long": _best(lambda: lambda: pad.addnstr(0, 0, long, 8)),
            }

        (got, _) = _screen(measure)

        ratio = got["long"] / got["short"]
        # Eight cells written either way; only the argument grew, 128-fold.
        assert ratio > 4, f"128x the argument at a fixed n cost only x{ratio:.1f}"

    def test_inserting_at_the_last_cell_does_not_scroll(self) -> None:
        def write(stdscr: Any) -> dict[str, Any]:
            import curses

            window = curses.newwin(3, 8, 0, 0)
            window.scrollok(True)
            for row in range(3):
                window.addstr(row, 0, f"row{row}")
            window.move(2, 7)
            window.insstr("Z")
            return {"top": window.instr(0, 0, 4), "bottom": window.instr(2, 0, 8)}

        (got, _) = _screen(write)

        # Scrolling would have thrown the first row away.
        assert got["top"] == b"row0"
        assert got["bottom"].endswith(b"Z")

    def test_the_window_codec_folds_a_character_but_not_a_string(self) -> None:
        """`encoding` reaches the narrow calls; addch() and addstr() go out wide."""

        def write(stdscr: Any) -> dict[str, Any]:
            import curses

            window = curses.newwin(4, 20, 0, 0)
            window.encoding = "ascii"
            calls = {
                "addstr": lambda: window.addstr(0, 0, "\u00e9"),
                "addch": lambda: window.addch(1, 0, "\u00e9"),
                "insch": lambda: window.insch(1, 2, "\u00e9"),
                "echochar": lambda: window.echochar("\u00e9"),
                "hline": lambda: window.hline(2, 0, "\u00e9", 3),
                "bkgdset": lambda: window.bkgdset("\u00e9"),
            }
            result: dict[str, Any] = {}
            for name, call in calls.items():
                try:
                    call()
                    result[name] = "wrote it"
                except UnicodeEncodeError:
                    result[name] = "used the codec"
            return result

        (got, _) = _screen(write)

        # On a wide build a str and a single character both go out wide, so the
        # window's codec never sees them. The narrower calls still fold through
        # it, and an ascii codec cannot carry this character.
        assert got["addstr"] == "wrote it"
        assert got["addch"] == "wrote it"
        for name in ("insch", "echochar", "hline", "bkgdset"):
            assert got[name] == "used the codec", f"{name} did not use window.encoding"

    @pytest.mark.timing
    def test_bkgd_rewrites_every_cell_and_bkgdset_does_not(self) -> None:
        def measure(stdscr: Any) -> dict[str, float]:
            import curses
            import itertools

            result: dict[str, float] = {}
            for label, cols in (("narrow", 64), ("wide", 1024)):
                pad = curses.newpad(512, cols)
                fills = itertools.cycle(".,;:-_=+*#")
                attrs = itertools.cycle([curses.A_BOLD, curses.A_NORMAL, curses.A_UNDERLINE])
                result[f"bkgd.{label}"] = _best(
                    lambda pad=pad, fills=fills: lambda: pad.bkgd(ord(next(fills)))
                )
                result[f"bkgdset.{label}"] = _best(
                    lambda pad=pad, attrs=attrs: lambda: pad.bkgdset(ord(" "), next(attrs))
                )
            return result

        (got, _) = _screen(measure)

        bkgd = got["bkgd.wide"] / got["bkgd.narrow"]
        bkgdset = got["bkgdset.wide"] / got["bkgdset.narrow"]
        assert bkgd > 4, f"16x the columns made bkgd only x{bkgd:.1f}"
        assert bkgdset < 2, f"16x the columns made bkgdset x{bkgdset:.1f}; it should not move"

    @pytest.mark.timing
    def test_deleteln_moves_every_cell_below_the_cursor(self) -> None:
        def measure(stdscr: Any) -> dict[str, float]:
            import curses

            def pad(rows: int, cols: int) -> Callable[[], Callable[[], Any]]:
                window = curses.newpad(rows, cols)
                for row in range(min(rows, 200)):
                    window.addstr(row, 0, "a" * (cols - 1))

                def make() -> Callable[[], Any]:
                    window.move(0, 0)
                    return window.deleteln

                return make

            return {
                "base": _best(pad(512, 64)),
                "wider": _best(pad(512, 1024)),
                "taller": _best(pad(4096, 64)),
            }

        (got, _) = _screen(measure)

        wider = got["wider"] / got["base"]
        taller = got["taller"] / got["base"]
        assert wider > 4, f"16x the columns made deleteln only x{wider:.1f}"
        assert taller > 2, f"8x the rows made deleteln only x{taller:.1f}"

    @pytest.mark.timing
    def test_a_newline_and_a_bottom_edge_write_scroll_the_window(self) -> None:
        """The cases the addch() and addstr() rows charge above a cell write."""

        def write(stdscr: Any) -> dict[str, Any]:
            import curses

            result: dict[str, Any] = {}

            window = curses.newwin(3, 10, 0, 0)
            window.scrollok(True)
            for row in range(3):
                window.addstr(row, 0, f"row{row}")
            window.move(2, 0)
            window.addch(ord("\n"))
            result["after_newline"] = window.instr(0, 0, 4)

            # A newline also clears what was left on its own line.
            clearing = curses.newwin(3, 10, 0, 0)
            clearing.addstr(0, 0, "abcdefghi")
            clearing.move(0, 3)
            clearing.addch(ord("\n"))
            result["cleared"] = clearing.instr(0, 0, 9)

            edge = curses.newwin(3, 10, 0, 0)
            edge.scrollok(True)
            for row in range(3):
                edge.addstr(row, 0, f"row{row}")
            edge.addstr(2, 9, "Z")
            result["after_edge"] = edge.instr(0, 0, 4)

            fixed = curses.newwin(3, 10, 0, 0)
            for row in range(3):
                fixed.addstr(row, 0, f"row{row}")
            try:
                fixed.addstr(2, 9, "Z")
                result["without_scrollok"] = "wrote it"
            except curses.error:
                result["without_scrollok"] = "curses.error"
            result["fixed_top"] = fixed.instr(0, 0, 4)
            return result

        (got, _) = _screen(write)

        # Each of these threw the first row away.
        assert got["after_newline"] == b"row1"
        assert got["after_edge"] == b"row1"
        assert got["cleared"] == b"abc      "
        # Without scrollok the same write raises and the window stands still.
        assert got["without_scrollok"] == "curses.error"
        assert got["fixed_top"] == b"row0"

    @pytest.mark.timing
    def test_scrolling_moves_every_cell(self) -> None:
        def measure(stdscr: Any) -> dict[str, float]:
            import curses

            def pad(rows: int, cols: int) -> Callable[[], Callable[[], Any]]:
                window = curses.newpad(rows, cols)
                window.scrollok(True)
                for row in range(min(rows, 200)):
                    window.addstr(row, 0, "a" * (cols - 1))
                return lambda: lambda: window.scroll(1)

            return {
                "base": _best(pad(512, 64)),
                "wider": _best(pad(512, 1024)),
                "taller": _best(pad(4096, 64)),
            }

        (got, _) = _screen(measure)

        wider = got["wider"] / got["base"]
        taller = got["taller"] / got["base"]
        assert wider > 4, f"16x the columns made scroll only x{wider:.1f}"
        assert taller > 2, f"8x the rows made scroll only x{taller:.1f}"

    @pytest.mark.timing
    def test_border_costs_the_perimeter_not_the_area(self) -> None:
        def measure(stdscr: Any) -> float:
            import curses

            narrow = curses.newpad(512, 64)
            wide = curses.newpad(512, 1024)
            return _best(lambda: wide.border) / _best(lambda: narrow.border)

        (ratio, _) = _screen(measure)

        # Rows stay at 512 while columns go from 64 to 1024, so a perimeter bound
        # predicts about (512 + 1024) / (512 + 64), and an area bound sixteen.
        assert ratio < 8, f"16x the columns made border x{ratio:.1f}; the area bound is 16"

    def test_overlay_is_transparent_on_blanks_and_overwrite_is_not(self) -> None:
        def copy(stdscr: Any) -> dict[str, bytes]:
            import curses

            source = curses.newwin(3, 6, 0, 0)
            source.addstr(0, 0, "AB")
            result: dict[str, bytes] = {}
            for name in ("overlay", "overwrite"):
                target = curses.newwin(3, 6, 0, 0)
                target.addstr(0, 0, "zzzzz")
                getattr(source, name)(target)
                result[name] = target.instr(0, 0, 5)
            return result

        (got, _) = _screen(copy)

        assert got == {"overlay": b"ABzzz", "overwrite": b"AB   "}


class TestReadingCells:
    """inch() reads one cell; instr() and getstr() read into a fixed buffer."""

    def test_instr_stops_at_the_module_ceiling(self) -> None:
        def read(stdscr: Any) -> dict[str, int]:
            import curses

            pad = curses.newpad(2, 4000)
            pad.addstr(0, 0, "z" * 3000)
            return {
                "asked_3000": len(pad.instr(0, 0, 3000)),
                "asked_nothing": len(pad.instr(0, 0)),
                "asked_10": len(pad.instr(0, 0, 10)),
            }

        (got, _) = _screen(read)

        assert got["asked_3000"] == READ_CEILING
        assert got["asked_nothing"] == READ_CEILING
        assert got["asked_10"] == 10

    def test_getstr_shares_the_ceiling(self) -> None:
        def read(stdscr: Any) -> int:
            import curses

            pad = curses.newpad(2, 4000)
            return len(pad.getstr(0, 0, 3000))

        (got, _) = _screen(read, feed=b"z" * 3000 + b"\n")

        assert got == READ_CEILING

    def test_inch_reads_one_cell_with_its_rendition(self) -> None:
        def read(stdscr: Any) -> dict[str, int]:
            import curses

            window = curses.newwin(3, 10, 0, 0)
            window.addstr(0, 0, "Q", curses.A_BOLD)
            cell = window.inch(0, 0)
            return {
                "text": cell & curses.A_CHARTEXT,
                "bold": bool(cell & curses.A_BOLD),
                "expected": ord("Q"),
            }

        (got, _) = _screen(read)

        assert got["text"] == got["expected"]
        assert got["bold"] is True

    def test_the_three_input_calls_differ_when_there_is_nothing_to_read(self) -> None:
        def read(stdscr: Any) -> dict[str, Any]:
            import curses

            window = curses.newwin(1, 10, 0, 0)
            window.nodelay(True)
            raised = {}
            for name in ("get_wch", "getkey"):
                try:
                    raised[name] = repr(getattr(window, name)())
                except curses.error as error:
                    raised[name] = type(error).__name__
            return raised

        (got, _) = _screen(read)

        # getch() has a sentinel; these two do not.
        assert got == {"get_wch": "error", "getkey": "error"}

    def test_getch_reports_an_empty_queue_with_a_sentinel(self) -> None:
        def read(stdscr: Any) -> dict[str, Any]:
            import curses

            window = curses.newwin(1, 10, 0, 0)
            window.nodelay(True)
            empty = window.getch()
            curses.ungetch(ord("q"))
            pushed = window.getch()
            curses.ungetch(ord("q"))
            curses.flushinp()
            flushed = window.getch()
            return {"empty": empty, "pushed": pushed, "flushed": flushed}

        (got, _) = _screen(read)

        assert got == {"empty": -1, "pushed": ord("q"), "flushed": -1}

    def test_a_write_past_the_edge_raises(self) -> None:
        def write(stdscr: Any) -> dict[str, str]:
            import curses

            attempts = {
                "below the last row": lambda: stdscr.addstr(curses.LINES + 50, 0, "x"),
                "past the last column": lambda: stdscr.addstr(0, curses.COLS + 50, "x"),
                # The character lands, but the cursor cannot advance off the window.
                "the bottom right cell": lambda: stdscr.addstr(
                    curses.LINES - 1, curses.COLS - 1, "x"
                ),
                "a move below the last row": lambda: stdscr.move(curses.LINES + 5, 0),
            }
            result = {}
            for what, attempt in attempts.items():
                try:
                    attempt()
                    result[what] = "no error"
                except curses.error:
                    result[what] = "curses.error"
            return result

        (got, _) = _screen(write)

        assert set(got.values()) == {"curses.error"}, got

    def test_getch_pushes_out_a_window_that_is_holding_changes(self) -> None:
        """Reading input is not free on a window that has not been refreshed."""

        def read(stdscr: Any, write_first: bool) -> None:
            import curses

            window = curses.newwin(5, 40, 0, 0)
            window.nodelay(True)
            window.refresh()
            if write_first:
                for row in range(4):
                    window.addstr(row, 0, f"line {row}")
            window.getch()

        (_, quiet) = _screen(lambda stdscr: read(stdscr, False))
        (_, holding) = _screen(lambda stdscr: read(stdscr, True))

        assert holding > quiet, "getch() on a window holding changes wrote nothing"

    def test_enclose_answers_for_one_position(self) -> None:
        def ask(stdscr: Any) -> dict[str, bool]:
            import curses

            window = curses.newwin(4, 10, 2, 3)
            return {"inside": window.enclose(3, 5), "outside": window.enclose(0, 0)}

        (got, _) = _screen(ask)

        assert got == {"inside": True, "outside": False}


class TestTheUpdatePath:
    """What reaches the terminal, counted in bytes, and what the diff costs."""

    def _repainted(self, between: str) -> int:
        """Bytes written by: fill, refresh, `between`, fill identically, refresh.

        The second fill restores exactly what the terminal already shows, so a
        diffing update has nothing to say and the total stays at the first
        fill's cost. Only a call that discards curses' picture of the screen
        makes the second refresh write anything.
        """

        def draw(stdscr: Any) -> None:
            import curses

            def fill() -> None:
                for row in range(curses.LINES - 1):
                    stdscr.addstr(row, 0, "x" * (curses.COLS - 1))

            fill()
            stdscr.refresh()
            if between == "clearok_true":
                stdscr.clearok(True)
            elif between:
                getattr(stdscr, between)()
            fill()
            stdscr.refresh()

        (_, written) = _screen(draw)
        return written

    def test_touching_and_erasing_write_nothing_extra(self) -> None:
        plain = self._repainted("")

        # touchwin() marks lines in the window; the update still compares
        # against the physical screen and finds them unchanged.
        assert self._repainted("touchwin") == plain
        # erase() blanks the cells, but the refill puts the same characters
        # back before anything is pushed out.
        assert self._repainted("erase") == plain

    def test_clearing_and_redrawing_repaint_the_screen(self) -> None:
        plain = self._repainted("")
        cleared = self._repainted("clear")
        redrawn = self._repainted("redrawwin")

        # clear() is erase() plus clearok(True), and clearok is the half that
        # costs: the next update repaints instead of diffing.
        assert cleared > plain * 1.5, f"clear() wrote {cleared} against {plain}"
        assert redrawn > plain * 1.5, f"redrawwin() wrote {redrawn} against {plain}"

    def test_clear_is_erase_plus_clearok(self) -> None:
        erased = self._repainted("erase")
        cleared = self._repainted("clear")
        armed = self._repainted("clearok_true")

        assert cleared > erased, "clear() wrote no more than erase()"
        # Arming the repaint without blanking anything costs the same as clear(),
        # which pins the difference on clearok() rather than on the blanking.
        assert armed == cleared

    def test_moving_the_cursor_writes_even_with_no_cell_changed(self) -> None:
        """Output is not the differing cells alone, which is why the page says so.

        `_repainted` cannot be reused here: its second fill moves the cursor
        itself, so a `move()` before it would be overwritten. This one fills
        once, refreshes, moves the cursor and refreshes again.
        """

        def draw(stdscr: Any, move_it: bool) -> None:
            import curses

            for row in range(curses.LINES - 1):
                stdscr.addstr(row, 0, "x" * (curses.COLS - 1))
            stdscr.refresh()
            if move_it:
                stdscr.move(curses.LINES // 2, curses.COLS // 2)
            stdscr.refresh()

        (_, still) = _screen(lambda stdscr: draw(stdscr, False))
        (_, moved) = _screen(lambda stdscr: draw(stdscr, True))

        # No cell differs in either run; the cursor still has to be put somewhere.
        assert moved > still, "moving the cursor produced no output at all"

    def test_immedok_turns_every_write_into_an_update(self) -> None:
        """The one setting that makes writing to a window reach the terminal."""

        def draw(stdscr: Any, immediate: bool) -> None:
            import curses

            window = curses.newwin(5, 40, 0, 0)
            window.refresh()
            window.immedok(immediate)
            for row in range(4):
                window.addstr(row, 0, f"line {row}")

        (_, deferred) = _screen(lambda stdscr: draw(stdscr, False))
        (_, immediate) = _screen(lambda stdscr: draw(stdscr, True))

        # Without it the four writes never leave the window's own array.
        assert immediate > deferred, "immedok(True) wrote no more than immedok(False)"

    def test_noutrefresh_reaches_the_screen_only_through_doupdate(self) -> None:
        def draw(stdscr: Any, update: bool) -> None:
            import curses

            window = curses.newwin(5, 40, 0, 0)
            for row in range(4):
                window.addstr(row, 0, f"line {row}")
            window.noutrefresh()
            if update:
                curses.doupdate()

        (_, staged) = _screen(lambda stdscr: draw(stdscr, False))
        (_, updated) = _screen(lambda stdscr: draw(stdscr, True))
        (_, nothing) = _screen(lambda stdscr: None)

        # Staging alone adds nothing over a session that drew nothing at all.
        assert staged == nothing, f"noutrefresh() wrote {staged - nothing} bytes"
        assert updated > staged, "doupdate() wrote nothing after the staging"

    def test_echochar_reaches_the_terminal_without_a_refresh(self) -> None:
        def draw(stdscr: Any, echo: bool) -> None:
            window = curses.newwin(5, 40, 0, 0) if False else stdscr
            if echo:
                window.echochar(ord("Q"))
            else:
                window.addch(0, 0, ord("Q"))

        import curses  # noqa: F401  (the closure above imports through the child)

        (_, plain) = _screen(lambda stdscr: draw(stdscr, False))
        (_, echoed) = _screen(lambda stdscr: draw(stdscr, True))

        assert echoed > plain, "echochar() wrote no more than addch()"

    def test_an_unchanged_screen_costs_no_output(self) -> None:
        def draw(stdscr: Any, extra: int) -> None:
            import curses

            for row in range(curses.LINES - 1):
                stdscr.addstr(row, 0, "x" * (curses.COLS - 1))
            stdscr.refresh()
            for _ in range(extra):
                curses.doupdate()

        (_, once) = _screen(lambda stdscr: draw(stdscr, 0))
        (_, many) = _screen(lambda stdscr: draw(stdscr, 20))

        assert many == once, f"20 further doupdate() calls wrote {many - once} bytes"

    @pytest.mark.timing
    def test_one_doupdate_beats_a_refresh_for_each_window(self) -> None:
        def measure(stdscr: Any) -> float:
            import curses

            def build() -> list[Any]:
                windows = [curses.newwin(1, 20, i % (curses.LINES - 1), 0) for i in range(200)]
                for index, window in enumerate(windows):
                    window.addstr(0, 0, f"row {index:03d}")
                return windows

            def dirty(windows: list[Any]) -> None:
                # Untimed, so that every sample has the same real work to do.
                for window in windows:
                    window.touchwin()

            def one_at_a_time(windows: list[Any]) -> Callable[[], Any]:
                dirty(windows)
                return lambda: [window.refresh() for window in windows]

            def all_at_once(windows: list[Any]) -> Callable[[], Any]:
                dirty(windows)
                return lambda: (
                    [window.noutrefresh() for window in windows],
                    curses.doupdate(),
                )

            separate, batched = build(), build()
            return _best(lambda: one_at_a_time(separate), 5) / _best(
                lambda: all_at_once(batched), 5
            )

        (ratio, _) = _screen(measure)

        assert ratio > 4, f"200 separate refreshes cost only x{ratio:.1f} of one doupdate"

    @pytest.mark.timing
    def test_noutrefresh_is_far_cheaper_for_an_untouched_window(self) -> None:
        def measure(stdscr: Any) -> float:
            import curses

            window = curses.newwin(0, 0, 0, 0)
            for row in range(curses.LINES - 1):
                window.addstr(row, 0, "b" * (curses.COLS - 1))
            window.noutrefresh()
            curses.doupdate()

            clean = _best(lambda: window.noutrefresh, 20)

            def dirty() -> Callable[[], Any]:
                window.touchwin()
                return window.noutrefresh

            return _best(dirty, 20) / clean

        (ratio, _) = _screen(measure)

        assert ratio > 4, f"a touched window cost only x{ratio:.1f} of an untouched one"

    @pytest.mark.timing
    def test_the_sync_calls_pay_for_the_rows_as_well_as_the_depth(self) -> None:
        def measure(stdscr: Any) -> dict[str, float]:
            import curses

            # Keep every ancestor alive until all sync calls have finished.
            # A derived window shares its parents' native storage.
            ancestors: list[Any] = []

            def chain(depth: int, rows: int) -> Any:
                window = curses.newpad(rows + depth, 512)
                for _ in range(depth):
                    ancestors.append(window)
                    window = window.derwin(rows, 8, 0, 0)
                return window

            shallow, deep = chain(2, 64), chain(64, 64)
            short, tall = chain(8, 16), chain(8, 512)
            return {
                "shallow": _best(lambda: shallow.syncup, 25),
                "deep": _best(lambda: deep.syncup, 25),
                "short": _best(lambda: short.syncup, 25),
                "tall": _best(lambda: tall.syncup, 25),
                "down_short": _best(lambda: short.syncdown, 25),
                "down_tall": _best(lambda: tall.syncdown, 25),
                "cursor_short": _best(lambda: short.cursyncup, 25),
                "cursor_tall": _best(lambda: tall.cursyncup, 25),
            }

        (got, _) = _screen(measure)

        by_depth = got["deep"] / got["shallow"]
        by_rows = got["tall"] / got["short"]
        assert by_depth > 4, f"32x the ancestors made syncup only x{by_depth:.1f}"
        # The rows matter too, which is what separates syncup from cursyncup.
        assert by_rows > 4, f"32x the rows made syncup only x{by_rows:.1f}"
        # syncdown carries the same line information the other way.
        downward = got["down_tall"] / got["down_short"]
        assert downward > 4, f"32x the rows made syncdown only x{downward:.1f}"
        cursor = got["cursor_tall"] / got["cursor_short"]
        assert cursor < 2, f"32x the rows made cursyncup x{cursor:.1f}; it carries only the cursor"

    @pytest.mark.timing
    def test_both_move_calls_pay_for_the_rows(self) -> None:
        """Neither is constant in the height, for two different reasons.

        `mvderwin()` rebinds a row pointer per row; `mvwin()` marks the lines it
        moved so they go out again. The second constant is much the smaller, so
        it is measured over a screen four hundred rows tall, and every timed
        call is preceded - outside the clock - by a move somewhere else, since
        asking a window for the position it already has costs nothing.
        """

        def measure(stdscr: Any) -> dict[str, float]:
            import curses
            import itertools

            parent = curses.newpad(1024, 256)
            short, tall = parent.derwin(8, 8, 0, 0), parent.derwin(900, 8, 0, 0)
            small, large = curses.newwin(2, 8, 0, 0), curses.newwin(380, 8, 0, 0)

            def stepping(window: Any, method: str) -> Callable[[], Callable[[], Any]]:
                spots = itertools.cycle([(0, 0), (4, 4)])
                move = getattr(window, method)

                def make() -> Callable[[], Any]:
                    move(*next(spots))
                    row, col = next(spots)
                    return lambda: move(row, col)

                return make

            return {
                "derwin_short": _best(stepping(short, "mvderwin"), 25),
                "derwin_tall": _best(stepping(tall, "mvderwin"), 25),
                "win_short": _best(stepping(small, "mvwin"), 25),
                "win_tall": _best(stepping(large, "mvwin"), 25),
            }

        (got, _) = _screen(measure, rows=400)

        derived = got["derwin_tall"] / got["derwin_short"]
        plain = got["win_tall"] / got["win_short"]
        assert derived > 2, f"112x the rows made mvderwin only x{derived:.1f}"
        assert plain > 1.5, f"190x the rows made mvwin only x{plain:.1f}"

    @pytest.mark.timing
    def test_touching_is_priced_in_lines_and_redrawing_in_cells(self) -> None:
        def measure(stdscr: Any) -> dict[str, float]:
            import curses

            narrow, wide = curses.newpad(512, 16), curses.newpad(512, 512)
            tall = curses.newpad(4096, 16)
            return {
                "touch_narrow": _best(lambda: narrow.touchwin, 25),
                "touch_wide": _best(lambda: wide.touchwin, 25),
                "touch_tall": _best(lambda: tall.touchwin, 25),
                "redraw_narrow": _best(lambda: narrow.redrawwin, 25),
                "redraw_wide": _best(lambda: wide.redrawwin, 25),
            }

        (got, _) = _screen(measure)

        by_width = got["touch_wide"] / got["touch_narrow"]
        by_height = got["touch_tall"] / got["touch_narrow"]
        assert by_width < 2, f"32x the columns made touchwin x{by_width:.1f}; lines are lines"
        assert by_height > 2, f"8x the rows made touchwin only x{by_height:.1f}"
        redraw = got["redraw_wide"] / got["redraw_narrow"]
        assert redraw > 1.5, f"32x the columns made redrawwin only x{redraw:.1f}"

    def test_syncok_makes_every_write_propagate_upward(self) -> None:
        """The third way an ordinary cell edit stops being local to its window."""

        def write(stdscr: Any, sync: bool) -> dict[str, bool]:
            import curses

            parent = curses.newwin(10, 40, 0, 0)
            child = parent.derwin(4, 10, 2, 5)
            parent.noutrefresh()
            child.noutrefresh()
            curses.doupdate()
            before = parent.is_wintouched()
            child.syncok(sync)
            child.addstr(0, 0, "ZZZ")
            return {"before": before, "after": parent.is_wintouched()}

        (plain, _) = _screen(lambda stdscr: write(stdscr, False))
        (synced, _) = _screen(lambda stdscr: write(stdscr, True))

        assert plain == {"before": False, "after": False}
        assert synced == {"before": False, "after": True}

    def test_touch_flags_are_readable(self) -> None:
        def flags(stdscr: Any) -> dict[str, bool]:
            import curses

            window = curses.newwin(5, 10, 0, 0)
            window.noutrefresh()
            curses.doupdate()
            before = window.is_wintouched()
            window.touchwin()
            after = window.is_wintouched()
            window.untouchwin()
            return {"before": before, "after": after, "untouched": window.is_wintouched()}

        (got, _) = _screen(flags)

        assert got == {"before": False, "after": True, "untouched": False}


class TestPanels:
    """The deck is one list; the panel objects are another, in creation order."""

    @pytest.mark.timing
    def test_a_lookup_walks_the_object_list_in_creation_order(self) -> None:
        def measure(stdscr: Any) -> dict[str, float]:
            import curses
            import curses.panel

            windows = [curses.newwin(4, 12, i % 18, (i * 3) % 60) for i in range(4000)]
            panels = [curses.panel.new_panel(w) for w in windows]
            newest, oldest = panels[-1], panels[0]
            spare = curses.newwin(4, 12, 0, 0)
            return {
                # Neither call changes the deck, so the only thing separating
                # them is where the wanted panel sits in the global list.
                "newest": _best(lambda: newest.below, 25),
                "oldest": _best(lambda: oldest.above, 25),
                "replace": _best(lambda: lambda: oldest.replace(spare), 25),
                "window": _best(lambda: oldest.window, 25),
            }

        (got, _) = _screen(measure)

        # The list is head-inserted, so the oldest panel is found last.
        search = got["oldest"] / got["newest"]
        assert search > 8, f"the oldest of 4000 panels was found in only x{search:.1f}"
        # replace() takes the same walk before it swaps the window.
        assert got["replace"] > got["newest"] * 4
        # window() searches nothing and touches no deck.
        assert got["window"] < got["oldest"] / 4

    @pytest.mark.timing
    def test_changing_the_deck_costs_the_deck(self) -> None:
        """top(), bottom(), hide() and move() each reconcile the whole deck.

        Every timed call is made to do real work: the panel is pushed off the
        top, made visible, or left somewhere else first, all of it outside the
        measurement. A call that found the deck already in the state it was
        asked for would return at once and time as a constant - and so would
        move() on a panel an earlier measurement had left hidden, which is why
        each operation gets a process of its own.
        """

        def measure(stdscr: Any, deck: int, operation: str) -> float:
            import curses
            import curses.panel

            held = [curses.panel.new_panel(curses.newwin(6, 20, i % 4, i % 4)) for i in range(deck)]
            first, last = held[0], held[-1]

            def raising() -> Callable[[], Any]:
                last.top()
                return first.top

            def hiding() -> Callable[[], Any]:
                first.show()
                return first.hide

            def lowering() -> Callable[[], Any]:
                first.top()
                return first.bottom

            def moving() -> Callable[[], Any]:
                first.show()
                first.move(0, 0)
                return lambda: first.move(1, 1)

            choices = {"top": raising, "bottom": lowering, "hide": hiding, "move": moving}
            return _best(choices[operation], 15)

        for operation in ("top", "bottom", "hide", "move"):
            (small, _) = _screen(lambda stdscr, op=operation: measure(stdscr, 256, op))
            (large, _) = _screen(lambda stdscr, op=operation: measure(stdscr, 1024, op))

            ratio = large / small
            assert ratio > 2, f"4x the deck made panel.{operation}() only x{ratio:.1f}"

    @pytest.mark.timing
    def test_show_and_hidden_do_not_reconcile_the_deck(self) -> None:
        """Both are held against work that does reconcile it, not against a clock.

        A single `show()` is a few tens of nanoseconds, which two measurements
        cannot compare across processes without dividing by something the clock
        may report as zero. So `show()` is measured inside a `hide()` that is
        already O(p): if showing reconciled the deck too, the pair would cost
        about twice what the `hide()` alone costs. `hidden()` is batched, which
        makes it long enough to time across two deck sizes directly.
        """

        def measure(stdscr: Any, deck: int) -> dict[str, float]:
            import curses
            import curses.panel

            held = [curses.panel.new_panel(curses.newwin(6, 20, i % 4, i % 4)) for i in range(deck)]
            first = held[0]

            def hiding() -> Callable[[], Any]:
                first.show()
                return first.hide

            def pairing() -> Callable[[], Any]:
                first.show()

                def run() -> None:
                    first.hide()
                    first.show()

                return run

            batch = held[:50]

            def showing() -> Callable[[], Any]:
                for panel in batch:  # untimed: fifty real transitions to make
                    panel.hide()
                assert all(panel.hidden() for panel in batch)

                def run() -> None:
                    for panel in batch:
                        panel.show()

                return run

            first.show()
            return {
                "hide": _best(hiding, 20),
                "pair": _best(pairing, 20),
                "show_fifty": _best(showing, 20),
                "hidden": _best(lambda: lambda: [first.hidden() for _ in range(100)], 20),
            }

        (small, _) = _screen(lambda stdscr: measure(stdscr, 256))
        (large, _) = _screen(lambda stdscr: measure(stdscr, 1024))

        for deck, got in (("256", small), ("1024", large)):
            added = got["pair"] / got["hide"]
            assert added < 1.6, f"on a deck of {deck}, adding show() cost x{added:.2f} of hide()"
        # Fifty real transitions per sample, which is long enough to compare the
        # two deck sizes directly rather than only against hide().
        showing = large["show_fifty"] / small["show_fifty"]
        assert showing < 2, f"4x the deck made fifty show() calls x{showing:.1f}"
        hidden = large["hidden"] / small["hidden"]
        assert hidden < 2, f"4x the deck made hidden() x{hidden:.1f}; it should not move"

    @pytest.mark.timing
    def test_making_a_panel_is_cheap_and_dropping_one_is_not(self) -> None:
        """Time 32 creations per sample with windows built outside the clock.

        Decks of 64 and 6,400 separate constant creation from linear
        removal over a 100x interval. Results stay alive until after timing;
        clearing them and building windows belong to sample setup.
        """

        def measure(stdscr: Any, deck: int) -> dict[str, float]:
            import curses
            import curses.panel

            held: list[Any] = [
                curses.panel.new_panel(curses.newwin(6, 20, i % 4, i % 4)) for i in range(deck)
            ]
            assert len(held) == deck
            created: list[Any] = []

            def making() -> Callable[[], Any]:
                created.clear()
                windows = [curses.newwin(6, 20, 0, 0) for _ in range(32)]

                def run() -> None:
                    for window in windows:
                        created.append(curses.panel.new_panel(window))

                return run

            make_time = _best(making, 15)
            created.clear()
            doomed: list[Any] = []

            def dropping() -> Callable[[], Any]:
                doomed.append(curses.panel.new_panel(curses.newwin(6, 20, 0, 0)))
                return doomed.clear

            return {"make": make_time, "drop": _best(dropping, 15)}

        small, _ = _screen(lambda stdscr: measure(stdscr, 64))
        large, _ = _screen(lambda stdscr: measure(stdscr, 6400))
        making = large["make"] / small["make"]
        dropping = large["drop"] / small["drop"]
        assert making < 15, (
            f"100x the deck made 32 new_panel() calls x{making:.1f}: {small}, {large}"
        )
        assert dropping > 20, f"100x the deck made panel removal x{dropping:.1f}: {small}, {large}"

    @pytest.mark.timing
    def test_update_panels_grows_with_the_square_of_the_deck(self) -> None:
        def measure(stdscr: Any) -> dict[str, float]:
            import curses
            import curses.panel

            held: list[Any] = []

            def add(count: int) -> None:
                for index in range(count):
                    window = curses.newwin(6, 20, index % 4, index % 4)
                    held.append(curses.panel.new_panel(window))

            add(32)
            small = _best(lambda: curses.panel.update_panels, 25)
            add(96)
            medium = _best(lambda: curses.panel.update_panels, 25)
            add(384)
            large = _best(lambda: curses.panel.update_panels, 25)
            return {"small": small, "medium": medium, "large": large}

        (got, _) = _screen(measure)

        first = got["medium"] / got["small"]
        second = got["large"] / got["medium"]
        # Each step is 4x the deck. Linear would be 4; the page says the square.
        assert first > 6, f"4x the panels made update_panels x{first:.1f}"
        assert second > 6, f"a further 4x made update_panels x{second:.1f}"
        # Cubic over a 4x step would be near 64.
        assert second < 40, f"a further 4x made update_panels x{second:.1f}"

    @pytest.mark.timing
    def test_update_panels_pays_for_the_rows_two_panels_share(self) -> None:
        """The h in the row: the same deck stacked the same way, but taller.

        Every panel sits at the same coordinates in both samples, so the pairs
        that overlap are the same pairs and only the rows they share change.
        This is the overlap term, not the staging term beside it - taller panels
        have more cells too, and nothing here tells the two apart.
        """

        def measure(stdscr: Any, rows: int) -> float:
            import curses
            import curses.panel

            # All at the same spot, so every pair overlaps in both samples and
            # only the rows they share changes.
            held = [curses.panel.new_panel(curses.newwin(rows, 20, 0, 0)) for _ in range(64)]
            assert len(held) == 64
            return _best(lambda: curses.panel.update_panels, 25)

        (short, _) = _screen(lambda stdscr: measure(stdscr, 2))
        (tall, _) = _screen(lambda stdscr: measure(stdscr, 16))

        ratio = tall / short
        assert ratio > 1.5, f"8x the rows per panel made update_panels only x{ratio:.1f}"

    def test_the_deck_is_newest_on_top(self) -> None:
        def stack(stdscr: Any) -> dict[str, Any]:
            import curses
            import curses.panel

            windows = [curses.newwin(3, 10, y, y) for y in range(4)]
            panels = [curses.panel.new_panel(w) for w in windows]
            result: dict[str, Any] = {
                "top_is_last": curses.panel.top_panel() is panels[-1],
                "bottom_is_first": curses.panel.bottom_panel() is panels[0],
                "below_the_bottom": curses.panel.bottom_panel().below() is None,
            }
            panels[0].top()
            result["after_top"] = curses.panel.top_panel() is panels[0]
            panels[0].hide()
            result["hidden"] = panels[0].hidden()
            result["top_after_hide"] = curses.panel.top_panel() is panels[-1]
            result["window_round_trip"] = panels[1].window() is windows[1]
            return result

        (got, _) = _screen(stack)

        assert got == {
            "top_is_last": True,
            "bottom_is_first": True,
            "below_the_bottom": True,
            "after_top": True,
            "hidden": True,
            "top_after_hide": True,
            "window_round_trip": True,
        }

    def test_userptr_raises_the_panel_modules_own_error(self) -> None:
        def ask(stdscr: Any) -> dict[str, Any]:
            import curses
            import curses.panel

            panel = curses.panel.new_panel(curses.newwin(3, 10, 0, 0))
            unset: str = ""
            try:
                panel.userptr()
            except curses.panel.error as error:
                unset = type(error).__name__
            panel.set_userptr({"a": 1})
            return {
                "unset": unset,
                "set": panel.userptr(),
                "distinct": curses.panel.error is not curses.error,
            }

        (got, _) = _screen(ask)

        assert got == {"unset": "error", "set": {"a": 1}, "distinct": True}


class TestAscii:
    """Every curses.ascii helper reads the one character it is handed."""

    def test_the_predicates_answer_from_the_code_alone(self) -> None:
        import curses.ascii as ascii_

        assert ascii_.isctrl(ascii_.BEL) is True
        assert ascii_.isctrl(ascii_.DEL) is False
        assert ascii_.iscntrl(ascii_.DEL) is True
        assert ascii_.isblank(" ") is True
        assert ascii_.ismeta(200) is True
        assert ascii_.isxdigit("f") is True
        assert ascii_.ispunct("!") is True
        assert ascii_.isalnum("7") is True

    def test_the_masks_keep_the_type_they_were_given(self) -> None:
        import curses.ascii as ascii_

        assert ascii_.ctrl("A") == "\x01"
        assert ascii_.ctrl(ord("A")) == 1
        assert ascii_.alt("A") == "\xc1"
        assert ascii_.alt(ord("A")) == 0xC1
        assert ascii_.ascii(0xC1) == ord("A")

    def test_the_two_unctrl_spellings_differ(self) -> None:
        def compare(stdscr: Any) -> dict[str, Any]:
            import curses
            import curses.ascii

            return {
                "module": curses.unctrl(1),
                "ascii": curses.ascii.unctrl(1),
                "module_meta": curses.unctrl(200),
                "ascii_meta": curses.ascii.unctrl(200),
                "keyname": curses.keyname(curses.KEY_LEFT),
            }

        (got, _) = _screen(compare)

        assert got["module"] == b"^A"
        assert got["ascii"] == "^A"
        assert got["module_meta"].startswith(b"M-")
        assert got["ascii_meta"].startswith("!")
        assert got["keyname"] == b"KEY_LEFT"

    def test_controlnames_is_indexed_by_code(self) -> None:
        import curses.ascii as ascii_

        assert len(ascii_.controlnames) == 33
        assert ascii_.controlnames[ascii_.NUL] == "NUL"
        assert ascii_.controlnames[ascii_.HT] == "HT"
        assert ascii_.controlnames[ascii_.LF] == "LF"
        assert ascii_.controlnames[ascii_.SP] == "SP"


class TestTextpad:
    """gather() reads the box back a cell at a time; rectangle() draws an edge."""

    @pytest.mark.timing
    def test_gather_costs_the_window_area(self) -> None:
        def measure(stdscr: Any) -> float:
            import curses
            import curses.textpad

            def box(rows: int, cols: int) -> Callable[[], Callable[[], Any]]:
                window = curses.newwin(rows, cols, 0, 0)
                for row in range(rows):
                    window.addstr(row, 0, "a" * (cols - 1))
                gather = curses.textpad.Textbox(window).gather
                return lambda: gather

            return _best(box(16, 80), 3) / _best(box(8, 40), 3)

        (ratio, _) = _screen(measure)

        assert ratio > 2.5, f"4x the cells made gather only x{ratio:.1f}"

    def test_gather_keeps_one_blank_past_the_text_and_drops_the_blank_rows(self) -> None:
        def collect(stdscr: Any) -> dict[str, Any]:
            import curses
            import curses.textpad

            window = curses.newwin(3, 20, 0, 0)
            box = curses.textpad.Textbox(window)
            for char in "hello":
                box.do_command(ord(char))
            stripped = box.gather()
            default_on = bool(box.stripspaces)
            box.stripspaces = False
            return {"stripped": stripped, "whole": box.gather(), "default_on": default_on}

        (got, _) = _screen(collect)

        assert got["default_on"] is True
        assert got["stripped"] == "hello \n"
        assert got["whole"] == "hello" + " " * 15 + "\n" + (" " * 20 + "\n") * 2

    def test_insert_mode_pushes_the_rest_of_the_line_right(self) -> None:
        def edit(stdscr: Any) -> dict[str, str]:
            import curses
            import curses.textpad

            result: dict[str, str] = {}
            for label, insert in (("insert", True), ("overwrite", False)):
                window = curses.newwin(1, 40, 0, 0)
                box = curses.textpad.Textbox(window, insert_mode=insert)
                for char in "hello":
                    box.do_command(ord(char))
                window.move(0, 0)
                for char in "XY":
                    box.do_command(ord(char))
                result[label] = box.gather()
            return result

        (got, _) = _screen(edit)

        assert got["insert"].startswith("XYhello")
        assert got["overwrite"].startswith("XYllo")

    def test_insert_mode_carries_past_the_end_of_a_line(self) -> None:
        """A single keystroke can rewrite every row below the cursor's."""

        def edit(stdscr: Any) -> str:
            import curses
            import curses.textpad

            window = curses.newwin(3, 6, 0, 0)
            box = curses.textpad.Textbox(window, insert_mode=True)
            for char in "abcdefghij":
                box.do_command(ord(char))
            window.move(0, 0)
            box.do_command(ord("X"))
            box.stripspaces = False
            return box.gather()

        (got, _) = _screen(edit)

        rows = got.splitlines()
        # "abcdef" filled the first row and "ghij" the second. Inserting one
        # character at the start pushed "f" over the row boundary, so a single
        # keystroke rewrote both rows.
        assert rows[0] == "Xabcde"
        assert rows[1] == "fghij "

    def test_ctrl_g_is_the_key_edit_stops_on(self) -> None:
        # typeshed types do_command as returning None, so the values below are
        # typed loosely; the assertions are what pin the two return codes.
        def ask(stdscr: Any) -> dict[str, Any]:
            import curses
            import curses.ascii
            import curses.textpad

            box = curses.textpad.Textbox(curses.newwin(3, 20, 0, 0))
            return {
                "bel": box.do_command(curses.ascii.BEL),
                "printable": box.do_command(ord("a")),
            }

        (got, _) = _screen(ask)

        # edit() loops while do_command is truthy, so 0 is the only way out.
        assert got["bel"] == 0
        assert got["printable"] == 1

    def test_rectangle_draws_only_the_perimeter(self) -> None:
        def draw(stdscr: Any) -> dict[str, bytes]:
            import curses
            import curses.textpad

            window = curses.newwin(6, 20, 0, 0)
            curses.textpad.rectangle(window, 0, 0, 4, 10)
            return {
                "top": window.instr(0, 0, 11),
                "middle": window.instr(2, 0, 11),
                "below": window.instr(5, 0, 11),
            }

        (got, _) = _screen(draw)

        # The corners and the runs between them differ; the interior and the row
        # under the rectangle are untouched.
        assert got["top"][0] != got["top"][1]
        assert len(set(got["top"][1:10])) == 1
        assert got["middle"][0] == got["middle"][10] != got["middle"][5]
        assert got["below"] == b" " * 11


class TestModuleLevelSurprises:
    """Two names that do not behave the way their spelling suggests."""

    def test_importing_curses_has_key_shadows_the_function(self) -> None:
        def shadow(_: Any) -> dict[str, str]:
            import curses

            before = type(curses.has_key).__name__
            import curses.has_key  # noqa: F401

            # Bound through Any because the name really is a module here, and
            # a type checker refuses the call for the same reason this asserts.
            shadowed: Any = curses.has_key
            try:
                shadowed(1)
            except TypeError as error:
                failure = str(error)
            else:
                failure = ""
            return {
                "before": before,
                "after": type(curses.has_key).__name__,
                "failure": failure,
            }

        (got, _) = _in_terminal(shadow)

        assert got["before"] != "module"
        assert got["after"] == "module"
        assert "not callable" in got["failure"]

    def test_the_terminfo_lookups_tell_absent_from_unknown(self) -> None:
        def ask(stdscr: Any) -> dict[str, Any]:
            import curses

            return {
                # "hc" and "lm" are real capabilities that a terminal emulator
                # does not have; "nosuchcapability" is not a capability at all.
                "absent_flag": curses.tigetflag("hc"),
                "unknown_flag": curses.tigetflag("nosuchcapability"),
                "absent_num": curses.tigetnum("lm"),
                "unknown_num": curses.tigetnum("nosuchcapability"),
                "present_flag": curses.tigetflag("am"),
                "unknown_str": curses.tigetstr("nosuchcapability"),
            }

        (got, _) = _screen(ask)

        # Absent and unknown are different answers, which is the whole row.
        assert got["absent_flag"] == 0
        assert got["unknown_flag"] == -1
        assert got["absent_num"] == -1
        assert got["unknown_num"] == -2
        assert got["present_flag"] == 1
        assert got["unknown_str"] is None

    def test_assume_default_colors_arrived_in_3_14(self) -> None:
        def ask(stdscr: Any) -> dict[str, bool]:
            import curses

            return {
                "assume": hasattr(curses, "assume_default_colors"),
                "use": hasattr(curses, "use_default_colors"),
            }

        (got, _) = _screen(ask)

        assert got["use"] is True
        assert got["assume"] is (sys.version_info >= (3, 14))

    def test_redefining_a_displayed_pair_arms_a_repaint(self) -> None:
        """The call writes nothing; what it arms for the next update does."""

        def draw(stdscr: Any, redefine: bool, then_update: bool) -> None:
            import curses

            curses.start_color()
            curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
            for row in range(curses.LINES - 1):
                stdscr.addstr(row, 0, "x" * (curses.COLS - 1), curses.color_pair(1))
            stdscr.refresh()
            pair = 1 if redefine else 2
            curses.init_pair(pair, curses.COLOR_GREEN, curses.COLOR_BLACK)
            if then_update:
                stdscr.refresh()

        (_, unused_then_update) = _screen(lambda stdscr: draw(stdscr, False, True))
        (_, live_then_update) = _screen(lambda stdscr: draw(stdscr, True, True))
        (_, live_no_update) = _screen(lambda stdscr: draw(stdscr, True, False))

        # The call itself puts nothing on the terminal; it marks the cells, and
        # the next update repaints them instead of diffing. Defining a pair
        # nothing is painted in leaves that update with nothing to say.
        assert live_no_update == unused_then_update
        assert live_then_update > unused_then_update

    @pytest.mark.timing
    def test_init_pair_scans_the_screen(self) -> None:
        """The row's time bound, which the byte counts beside it cannot reach."""

        def measure(stdscr: Any) -> dict[str, float]:
            import curses
            import itertools

            curses.start_color()
            curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
            for row in range(curses.LINES - 1):
                stdscr.addstr(row, 0, "x" * (curses.COLS - 1), curses.color_pair(1))
            stdscr.refresh()
            colours = itertools.cycle([curses.COLOR_GREEN, curses.COLOR_BLUE, curses.COLOR_CYAN])

            def redefining(pair: int) -> Callable[[], Callable[[], Any]]:
                # A fresh colour each time, so no call is a no-op.
                return lambda: (
                    lambda colour=next(colours): curses.init_pair(pair, colour, curses.COLOR_BLACK)
                )

            return {
                "displayed": _best(redefining(1), 15),
                "unused": _best(redefining(7), 15),
                "cells": float(curses.LINES * curses.COLS),
            }

        (small, _) = _screen(measure, rows=24)
        (large, _) = _screen(measure, rows=300)

        area = large["cells"] / small["cells"]
        ratio = large["displayed"] / small["displayed"]
        assert area > 10, f"the two screens differed by only x{area:.1f}"
        assert ratio > 4, f"{area:.0f}x the screen made init_pair only x{ratio:.1f}"

    def test_tparm_interprets_the_capability_string(self) -> None:
        def ask(stdscr: Any) -> dict[str, Any]:
            import curses

            cup = curses.tigetstr("cup")
            assert cup is not None, "the terminfo entry has no cup capability"
            return {"raw": cup, "filled": curses.tparm(cup, 3, 4)}

        (got, _) = _screen(ask)

        # The stored capability carries the parameter opcodes; tparm resolves
        # them, so the result holds neither of them and is shorter.
        assert b"%p1" in got["raw"]
        assert b"%p1" not in got["filled"]
        assert got["filled"].endswith(b"H")

    @pytest.mark.timing
    def test_napms_delays_the_caller(self) -> None:
        def sleep(stdscr: Any) -> float:
            import curses
            import time

            start = time.perf_counter()
            curses.napms(60)
            return time.perf_counter() - start

        (elapsed, _) = _screen(sleep)

        assert elapsed >= 0.05, f"napms(60) returned after {elapsed * 1000:.0f} ms"

    def test_is_term_resized_compares_against_the_current_size(self) -> None:
        def ask(stdscr: Any) -> dict[str, bool]:
            import curses

            return {
                "same": curses.is_term_resized(curses.LINES, curses.COLS),
                "different": curses.is_term_resized(curses.LINES + 5, curses.COLS),
            }

        (got, _) = _screen(ask)

        assert got == {"same": False, "different": True}

    def test_mousemask_returns_the_available_and_previous_masks(self) -> None:
        def ask(stdscr: Any) -> dict[str, Any]:
            import curses

            first_available, first_previous = curses.mousemask(curses.BUTTON1_PRESSED)
            second_available, second_previous = curses.mousemask(curses.BUTTON2_PRESSED)
            restored_available, restored_previous = curses.mousemask(first_available)
            return {
                "first_available": first_available,
                "first_previous": first_previous,
                "second_previous": second_previous,
                "restored_previous": restored_previous,
                "second_available": second_available,
                "restored_available": restored_available,
            }

        (got, _) = _screen(ask)

        # Nothing was set before the first call, and each later call reports the
        # mask the one before it settled on - not the mask that was requested.
        # All-zero masks would satisfy the equalities below on their own.
        assert got["first_available"] != 0
        assert got["second_available"] != 0
        assert got["first_available"] != got["second_available"]
        assert got["first_previous"] == 0
        assert got["second_previous"] == got["first_available"]
        assert got["restored_previous"] == got["second_available"]
        assert got["restored_available"] == got["first_available"]


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
    """Run one block under a pty, since curses.wrapper needs a terminal.

    The block's own output and curses' escape sequences share the pty, so what
    each block demonstrates is asserted by the block's own `assert` statements.
    The driver still forwards that stream to its stderr, because a failing
    block's traceback goes to the terminal and would otherwise be lost.
    """
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    driver = cwd / "driver.py"
    driver.write_text(
        textwrap.dedent(
            f"""
            import errno, os, pty, select, struct, fcntl, termios, signal, sys, time

            gate_read, gate_write = os.pipe()
            pid, master = pty.fork()
            if pid == 0:
                try:
                    os.close(gate_write)
                    # Wait for the parent to size the terminal before the block
                    # can reach initscr() and read a size it did not set.
                    os.read(gate_read, 1)
                    os.close(gate_read)
                    os.environ["TERM"] = "xterm"
                    os.environ.pop("LINES", None)
                    os.environ.pop("COLUMNS", None)
                    os.execv(sys.executable, [sys.executable, "block.py"])
                except BaseException:
                    os._exit(70)
            os.close(gate_read)
            seen = []
            timed_out = False
            reaped = False
            status = 0
            try:
                fcntl.ioctl(
                    master, termios.TIOCSWINSZ, struct.pack("HHHH", {ROWS}, {COLS}, 0, 0)
                )
                os.write(gate_write, b"\\x01")
                os.close(gate_write)
                deadline = time.monotonic() + {TIMEOUT}
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        break
                    ready, _, _ = select.select([master], [], [], remaining)
                    if not ready:
                        timed_out = True
                        break
                    try:
                        data = os.read(master, 65536)
                    except OSError as error:
                        # The child's exit reaches a pty master as EIO.
                        if error.errno != errno.EIO:
                            raise
                        data = b""
                    if not data:
                        break
                    seen.append(data)
                # Terminal EOF is not proof of exit: a block can close its
                # descriptors and keep running, so poll for it under the same
                # deadline rather than waiting without one.
                while not timed_out:
                    done, code = os.waitpid(pid, os.WNOHANG)
                    if done == pid:
                        reaped, status = True, code
                        break
                    if time.monotonic() >= deadline:
                        timed_out = True
                    else:
                        time.sleep(0.01)
            except BaseException:
                timed_out = True
                raise
            finally:
                if timed_out:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                try:
                    if not reaped:
                        status = os.waitpid(pid, 0)[1]
                finally:
                    for fd in (gate_write, master):
                        try:
                            os.close(fd)
                        except OSError:
                            pass
            # The block's traceback went to the terminal, so hand it back.
            sys.stderr.write(b"".join(seen).decode("utf-8", "replace"))
            if timed_out:
                sys.exit("the block did not finish within {TIMEOUT} seconds")
            sys.exit(os.waitstatus_to_exitcode(status))
            """
        ),
        encoding="utf-8",
    )
    return subprocess.run(
        [sys.executable, "driver.py"],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=TIMEOUT * 2,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block is a curses program, so every block runs under a pty.

    A block's exit status proves only that nothing raised - which is the point
    here, because each block carries its own assertions rather than printing a
    result that the terminal stream would interleave with escape sequences.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

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

    def test_the_runner_notices_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        line, source = _blocks()[0]
        mutated = source.replace("curses.newwin(1, 20, y, 0)", "curses.newwin(1, 20, y, 0) + 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        """An exit status that ignored a failed assert would pass every block."""
        line, source = next((n, s) for n, s in _blocks() if "is_wintouched() is False" in s)
        mutated = source.replace("is_wintouched() is False", "is_wintouched() is True", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
