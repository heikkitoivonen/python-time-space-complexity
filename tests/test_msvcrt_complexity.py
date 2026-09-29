"""Tests for docs/stdlib/msvcrt.md.

Every function in the module is one call into the C runtime. Most rows are
O(1) and are settled by behaviour: what the call returns, what it leaves
behind, and whether it waits. The rest grow with something outside Python:
`kbhit()` copies every console input event that is waiting (n), a read
discards the events ahead of the key (e), and `heapmin()` walks the C
runtime heap (h). Those are timed, and `kbhit()`'s buffer, and the absence
of one in a read, are seen in the process's peak commit.

The console functions read and write the process's console. A test never
reads a key from the console pytest runs in: each console test runs in a
child created with CREATE_NO_WINDOW, which gets a console of its own with no
window, and puts its "key presses" there with WriteConsoleInputW. A read is
made only when a key or a pushed-back character is known to be waiting,
except in the one test that shows a read waiting, whose child queues its own
key when told to; every child has a timeout, so a read that waits by mistake
fails the test instead of hanging it. Echoed output is read back from the
child's screen buffer.

Measurement scope:

* `kbhit()` with 100, 1,000 and 10,000 key-release events waiting (which
  are not key presses, so it returns 0) grows at every step and costs over
  5x as much at 10,000 as at 100, fastest of seven runs of 20 calls; a
  constant cost predicts 1x.
* n against e: with a key press at the front of the queue and 100 or
  100,000 release events behind it, `kbhit()` costs over 10x as much at
  100,000, while `getch()` costs under 3x as much (fastest of seven single
  calls, each on a freshly filled queue); so `kbhit()` pays for the events
  behind the key and `getch()` does not. With 100 or 10,000 events ahead of
  the key instead, `getch()` costs over 10x as much at 10,000.
* Space: with the key press at the front and 400,000 events behind it, one
  `kbhit()` raises the child's peak commit by more than 4 MB (the events are
  20 bytes each) and consumes nothing. With 400,000 events ahead of a key,
  `getch()`, `getwch()`, `getche()` and `getwche()` each raise it by under
  1 MB. Each of these runs in a fresh child that makes no other console
  call before it, so no earlier peak can hide a buffer; as controls, the
  same child raises the peak by more than 4 MB for `kbhit()` and for an
  8 MB ctypes buffer made in place of the read.
* Each of the four reads, with 100,000 release events and then two key
  presses queued, returns the first key and leaves exactly the three events
  behind it: it discards the events ahead of the key and stops there.
* An injected key press makes `kbhit()` nonzero and `getch()` return it as
  bytes and `getwch()` as str, a non-ASCII character included. F1 comes back
  from `getch()` as `b'\\x00'` and then `b';'`, and the Up arrow as
  `b'\\xe0'` and then `b'H'`, with `kbhit()` still nonzero between the two
  calls. `getche()` and `getwche()` echo a key read from the
  console: the characters appear on the screen buffer, as do those written by
  `putch()` and `putwch()`, while the child's captured stdout stays empty.
* `ungetch()` makes `kbhit()` nonzero and the next `getch()` or `getche()`
  return the byte without waiting. Bytes come back in the order pushed, and a
  push raises OSError before the hundredth (the fourth, on the UCRT this was
  run on). `ungetwch()` holds one character: a second push raises OSError,
  `kbhit()` stays 0, and `getwch()` returns it. Neither buffer is read by the
  other family: with a byte and a character pushed back, `getwch()` returns
  the character and `getch()` the byte, and with a byte pushed back and a
  key queued, `getwch()` returns the key and leaves the byte for `getch()`.
  With only a byte pushed back, a child prints a line immediately before
  `getwch()` and is still running one second after the parent reads it;
  the key it then queues for itself on the parent's signal is what
  `getwch()` returns, and the byte is still waiting after. A `getwch()`
  that returned the byte would end the child before the check (a mutated
  child calling `getch()` there was seen to fail it).
* `locking()` on two descriptors of one file: a region locked through one
  makes an `LK_NBLCK` or `LK_NBRLCK` attempt through the other raise
  PermissionError at once, and a write into it fail; `LK_RLCK` excludes
  another reader the same way. The region starts at the current position,
  which the call does not move, and may lie past the end of the file.
  Adjacent regions are unlocked one at a time; an unlock spanning both
  raises. Closing the descriptor releases its locks. `LK_LOCK` and `LK_RLCK`
  on a held region raise OSError (errno 36, EDEADLOCK) after between 5 and
  30 seconds; the C runtime's documented ten attempts a second apart took
  9.1 seconds here.
* `heapmin()` returns None. It is timed with 1,000, 4,000 and 16,000 live
  20,000-byte bytes objects in the heap, each size in a fresh process,
  fastest of seven calls after a first call has released whatever was free. On an ARM64 build it grows at every
  step and costs over 4x as much at 16,000 as at 1,000, where a constant cost
  predicts 1x. On every build 16x the blocks costs under 64x, which excludes
  a quadratic walk. The x64 builds of 3.10 and 3.12, run under emulation on
  ARM64 Windows, stayed flat from 1,000 to 64,000 blocks: the cost is the
  Windows heap's, and not every heap walks its blocks.
* `setmode()` returns the previous mode, and `O_TEXT` turns a written `\\n`
  into `\\r\\n`. `get_osfhandle()` returns the handle `open_osfhandle()` was
  given, a descriptor from `open_osfhandle()` reads the file, closing it
  closes the handle, and an unknown descriptor raises OSError.
* `SetErrorMode()` returns the previous flags, and `GetErrorMode()` returns
  the ones just set both in the calling thread and in another, in a child
  process. The `LK_*` and `SEM_*` constants are the integers the C headers
  define and `CRT_ASSEMBLY_VERSION` a four-part version string; that it is
  the C runtime Python was built with is read from PC/msvcrtmodule.c, which
  formats it from the compiler's `_VC_CRT_*` macros. The debug-build names
  are asserted absent from a release build.
* Every fenced block on the page runs in its own subprocess with a console of
  its own, and a mutated assertion in one of them is asserted to fail.
* The file passes on 3.14 ARM64, on 3.13 ARM64, and on the x64 builds of
  3.10 and 3.12 under emulation, where the ARM64-only heapmin test skips.

Not settled here:

* That a console or file-system call is O(1). The page counts it that way,
  as the os page counts a syscall.
* `CrtSetReportFile()`, `CrtSetReportMode()`, `set_error_mode()` and the
  `CRT_*`, `CRTDBG_*`, `OUT_TO_*` and `REPORT_ERRMODE` constants exist only
  in a debug build of Python (`_DEBUG` in PC/msvcrtmodule.c, with `OUT_TO_*`
  and `REPORT_ERRMODE` added in 3.13); no debug build is run here. Each is one
  C runtime call or an integer.
* How many bytes `ungetch()` holds, and whether a push fits after a read, is
  the UCRT's, which ships with Windows rather than Python; only that the
  buffer is small and FIFO is asserted.
* `heapmin()` is timed on 20,000-byte blocks only; blocks small enough for
  Windows' low-fragmentation front end were not varied, and no native x64
  machine was run.
* `kbhit()` and `getch()` are varied in key-release events only; mouse,
  focus and resize events were not queued.
* Only `getch()` is timed against the events ahead of the key; that
  `getwch()`, `getche()` and `getwche()` cost the same O(e) rests on their
  discarding the same events and holding none of them, shown above.
* Every test except the block count is Windows-only and skips elsewhere, so
  a run on Linux or macOS verifies none of the page's claims.
"""

from __future__ import annotations

import importlib
import json
import os
import pathlib
import re
import subprocess
import sys
import sysconfig
import textwrap
import threading
import time
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "msvcrt.md"
EXPECTED_BLOCKS = 5

WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="msvcrt is Windows-only")
msvcrt: Any = importlib.import_module("msvcrt") if sys.platform == "win32" else None

# subprocess.CREATE_NO_WINDOW, which typeshed declares only on Windows: the
# child gets a console of its own with no window.
CREATE_NO_WINDOW = 0x08000000

# Helpers for a child with its own console: queue input events, count them,
# read the screen buffer and the process's peak commit.
CONSOLE = textwrap.dedent(
    """
    import ctypes
    import json
    import msvcrt
    import time
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    INVALID = wintypes.HANDLE(-1).value
    conin = kernel32.CreateFileW("CONIN$", 0xC0000000, 3, None, 3, 0, None)
    conout = kernel32.CreateFileW("CONOUT$", 0xC0000000, 3, None, 3, 0, None)
    assert conin not in (None, INVALID) and conout not in (None, INVALID), "no console"
    conin, conout = wintypes.HANDLE(conin), wintypes.HANDLE(conout)
    kernel32.FlushConsoleInputBuffer(conin)

    class KEY(ctypes.Structure):
        _fields_ = [
            ("down", wintypes.BOOL),
            ("repeat", wintypes.WORD),
            ("vk", wintypes.WORD),
            ("scan", wintypes.WORD),
            ("char", wintypes.WCHAR),
            ("state", wintypes.DWORD),
        ]

    class EVENT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("key", KEY), ("pad", ctypes.c_byte * 16)]
        _fields_ = [("type", wintypes.WORD), ("u", _U)]

    def queue(keys):
        records = (EVENT * len(keys))()
        for record, (down, char, vk, scan, state) in zip(records, keys):
            record.type = 1
            record.u.key.down = down
            record.u.key.repeat = 1
            record.u.key.vk = vk
            record.u.key.scan = scan
            record.u.key.char = char
            record.u.key.state = state
        written = wintypes.DWORD()
        kernel32.WriteConsoleInputW(conin, records, len(keys), ctypes.byref(written))
        assert written.value == len(keys)

    def press(char, vk=0x41, scan=0, state=0):
        queue([(True, char, vk, scan, state), (False, char, vk, scan, state)])

    def releases(count):
        for start in range(0, count, 1000):
            queue([(False, "a", 0x41, 0, 0)] * min(1000, count - start))

    def pending():
        count = wintypes.DWORD()
        kernel32.GetNumberOfConsoleInputEvents(conin, ctypes.byref(count))
        return count.value

    class COORD(ctypes.Structure):
        _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

    def screen(width=40):
        text = ctypes.create_unicode_buffer(width)
        read = wintypes.DWORD()
        kernel32.ReadConsoleOutputCharacterW(
            conout, text, width, COORD(0, 0), ctypes.byref(read)
        )
        return text.value[: read.value].rstrip()

    class MEMORY(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged",
                "nonpaged", "commit", "peak_commit",
            )
        ]

    def peak_commit():
        info = MEMORY()
        info.cb = ctypes.sizeof(info)
        process = wintypes.HANDLE(kernel32.GetCurrentProcess())
        assert kernel32.K32GetProcessMemoryInfo(process, ctypes.byref(info), info.cb)
        return info.peak_commit

    def best_ns(func, repeats=7, inner=20):
        best = None
        for _ in range(repeats):
            start = time.perf_counter_ns()
            for _ in range(inner):
                func()
            elapsed = (time.perf_counter_ns() - start) / inner
            best = elapsed if best is None else min(best, elapsed)
        return best

    def report(**values):
        print(json.dumps(values))
    """
)


def run_child(source: str, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    """Run source in a child with a console of its own and no window."""
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def in_console(body: str, timeout: float = 60) -> dict[str, Any]:
    """Run body after the CONSOLE helpers and return what it reported."""
    result = run_child(CONSOLE + textwrap.dedent(body), timeout)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


@WINDOWS
class TestKbhitCopiesTheWaitingEvents:
    """`kbhit()` | O(n) | O(n) - it never waits, and it copies every input
    event waiting in the console, those behind a key press included."""

    def test_it_answers_without_waiting(self) -> None:
        seen = in_console(
            """
            before = msvcrt.kbhit()
            press("k")
            report(before=before, after=msvcrt.kbhit(), key=msvcrt.getch().decode(),
                   drained=msvcrt.kbhit())
            """
        )
        assert seen == {"before": 0, "after": 1, "key": "k", "drained": 0}

    @pytest.mark.timing
    def test_time_follows_the_waiting_events(self) -> None:
        costs = in_console(
            """
            costs = {}
            for count in (100, 1_000, 10_000):
                kernel32.FlushConsoleInputBuffer(conin)
                releases(count)
                assert pending() == count and msvcrt.kbhit() == 0
                costs[count] = best_ns(msvcrt.kbhit)
            report(**{str(k): v for k, v in costs.items()})
            """,
            timeout=120,
        )
        small, middle, large = costs["100"], costs["1000"], costs["10000"]
        assert small < middle < large, costs
        assert large / small > 5, f"100x the events cost x{large / small:.1f}"

    @pytest.mark.timing
    def test_events_behind_a_key_cost_kbhit_but_not_getch(self) -> None:
        """A key press at the front with 100 or 100,000 events behind it:
        `kbhit()` pays for the events behind the key (n), `getch()` does not
        (e = 0). With 100 or 10,000 events ahead of the key instead,
        `getch()` pays (e)."""
        costs = in_console(
            """
            def fastest(func, ahead, behind):
                best = None
                for _ in range(7):
                    kernel32.FlushConsoleInputBuffer(conin)
                    releases(ahead)
                    press("k")
                    releases(behind)
                    start = time.perf_counter_ns()
                    func()
                    elapsed = time.perf_counter_ns() - start
                    best = elapsed if best is None else min(best, elapsed)
                return best

            costs = {}
            for count in (100, 100_000):
                costs[f"kbhit_behind{count}"] = fastest(msvcrt.kbhit, 0, count)
                costs[f"getch_behind{count}"] = fastest(msvcrt.getch, 0, count)
            for count in (100, 10_000):  # getch() reads each of these on its own
                costs[f"getch_ahead{count}"] = fastest(msvcrt.getch, count, 0)
            report(**costs)
            """,
            timeout=300,
        )
        kbhit = costs["kbhit_behind100000"] / costs["kbhit_behind100"]
        behind = costs["getch_behind100000"] / costs["getch_behind100"]
        ahead = costs["getch_ahead10000"] / costs["getch_ahead100"]
        assert kbhit > 10, f"1,000x the events behind the key cost kbhit() x{kbhit:.1f}: {costs}"
        assert behind < 3, f"1,000x the events behind the key cost getch() x{behind:.1f}: {costs}"
        assert ahead > 10, f"100x the events ahead of the key cost getch() x{ahead:.1f}: {costs}"

    def test_space_follows_every_waiting_event(self) -> None:
        """The key press is at the front, so only the events behind it (n,
        not e) can account for the buffer."""
        seen = in_console(
            """
            press("k")
            releases(400_000)
            before = peak_commit()
            assert msvcrt.kbhit() == 1
            report(grew=peak_commit() - before, left=pending())
            """,
            timeout=120,
        )
        assert seen["left"] == 400_002, "kbhit() consumed nothing"
        assert seen["grew"] > 4_000_000, f"400,000 events raised the peak by {seen['grew']} B"


@WINDOWS
class TestReadingKeys:
    """`getch()`, `getwch()`, `getche()`, `getwche()` | O(e) | O(1) - a read
    discards the events ahead of the key without holding them, and leaves
    those behind it."""

    @pytest.mark.parametrize("reader", ["getch", "getwch", "getche", "getwche"])
    def test_a_read_discards_the_events_ahead_of_the_key(self, reader: str) -> None:
        seen = in_console(
            f"""
            releases(100_000)
            press("b")
            press("c")
            key = msvcrt.{reader}()
            report(key=key if isinstance(key, str) else key.decode(), left=pending())
            """,
            timeout=120,
        )
        assert seen == {"key": "b", "left": 3}, "only the events behind the key are left"

    @pytest.mark.parametrize(
        ("call", "holds_the_queue"),
        [
            ("msvcrt.getch()", False),
            ("msvcrt.getwch()", False),
            ("msvcrt.getche()", False),
            ("msvcrt.getwche()", False),
            # Controls: the same child, measured the same way, sees a
            # queue-sized allocation.
            ("msvcrt.kbhit()", True),
            ("ctypes.create_string_buffer(20 * 400_000)", True),
        ],
    )
    def test_a_read_holds_one_event_at_a_time(self, call: str, holds_the_queue: bool) -> None:
        """Each call in a fresh child that has made no other console call, so
        no earlier peak can hide a queue-sized buffer."""
        seen = in_console(
            f"""
            releases(400_000)
            press("b")
            before = peak_commit()
            result = {call}
            report(grew=peak_commit() - before)
            """,
            timeout=120,
        )
        if holds_the_queue:
            assert seen["grew"] > 4_000_000, f"the control raised the peak by {seen['grew']} B"
        else:
            assert seen["grew"] < 1_000_000, f"{call} raised the peak by {seen['grew']} B"

    def test_bytes_and_str(self) -> None:
        seen = in_console(
            """
            press("x")
            as_bytes = msvcrt.getch()
            press("\\u00e9")
            report(as_bytes=repr(as_bytes), as_str=msvcrt.getwch())
            """
        )
        assert seen == {"as_bytes": "b'x'", "as_str": "é"}

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            ("vk=0x70, scan=0x3B", ("b'\\x00'", "b';'")),  # F1
            ("vk=0x26, scan=0x48, state=0x100", ("b'\\xe0'", "b'H'")),  # Up, an enhanced key
        ],
    )
    def test_a_function_or_arrow_key_is_two_reads(
        self, key: str, expected: tuple[str, str]
    ) -> None:
        seen = in_console(
            f"""
            press("\\x00", {key})
            assert msvcrt.kbhit()
            first = msvcrt.getch()
            between = msvcrt.kbhit()
            second = msvcrt.getch() if between else None
            report(first=repr(first), between=between, second=repr(second))
            """
        )
        assert seen == {"first": expected[0], "between": 1, "second": expected[1]}

    def test_echo_and_put_go_to_the_console(self) -> None:
        result = run_child(
            CONSOLE
            + textwrap.dedent(
                """
                import sys
                msvcrt.putch(b"P")
                msvcrt.putwch("\\u00e9")
                press("t")
                assert msvcrt.getche() == b"t"
                press("w")
                assert msvcrt.getwche() == "w"
                sys.stderr.write(screen())
                """
            )
        )
        assert result.returncode == 0, result.stderr
        assert result.stderr == "Pétw"
        assert result.stdout == "", "putch() and the echo bypass sys.stdout"


@WINDOWS
class TestPushingBack:
    """`ungetch()` and `ungetwch()` | O(1) - a small buffer for bytes and a
    one-character buffer for str, each read only by its own family."""

    def test_a_pushed_byte_is_read_without_waiting(self) -> None:
        seen = in_console(
            """
            msvcrt.ungetch(b"a")
            hit = msvcrt.kbhit()
            first = msvcrt.getch()
            msvcrt.ungetch(b"e")
            report(hit=hit, first=first.decode(), echoed=msvcrt.getche().decode(),
                   left=msvcrt.kbhit())
            """
        )
        assert seen == {"hit": 1, "first": "a", "echoed": "e", "left": 0}

    def test_the_byte_buffer_is_small_and_in_order(self) -> None:
        seen = in_console(
            """
            pushed = []
            for index in range(100):
                try:
                    msvcrt.ungetch(bytes([65 + index % 26]))
                except OSError:
                    break
                pushed.append(chr(65 + index % 26))
            read = []
            while msvcrt.kbhit():
                read.append(msvcrt.getch().decode())
            report(pushed=pushed, read=read)
            """
        )
        assert 1 <= len(seen["pushed"]) < 100
        assert seen["read"] == seen["pushed"]

    def test_the_str_buffer_holds_one_and_kbhit_does_not_see_it(self) -> None:
        seen = in_console(
            """
            msvcrt.ungetwch("\\u00e9")
            try:
                msvcrt.ungetwch("z")
                second = "accepted"
            except OSError:
                second = "raised"
            hit = msvcrt.kbhit()
            report(second=second, hit=hit, read=msvcrt.getwch())
            """
        )
        assert seen == {"second": "raised", "hit": 0, "read": "é"}

    def test_each_family_reads_only_its_own_buffer(self) -> None:
        seen = in_console(
            """
            msvcrt.ungetch(b"q")
            msvcrt.ungetwch("r")
            wide = msvcrt.getwch()
            narrow = msvcrt.getch()
            report(wide=wide, narrow=narrow.decode(), left=msvcrt.kbhit())
            """
        )
        assert seen == {"wide": "r", "narrow": "q", "left": 0}

    def test_getwch_skips_a_pushed_byte_for_a_key(self) -> None:
        seen = in_console(
            """
            msvcrt.ungetch(b"q")
            press("z")
            wide = msvcrt.getwch()
            report(wide=wide, narrow=msvcrt.getch().decode(), left=msvcrt.kbhit())
            """
        )
        assert seen == {"wide": "z", "narrow": "q", "left": 0}

    @pytest.mark.timing
    def test_getwch_waits_with_only_a_pushed_byte(self) -> None:
        """The child says "ready" just before `getwch()` and is still running
        a second later; a key it queues for itself only when told to then
        ends the wait, and the byte is still there for `getch()`."""
        source = CONSOLE + textwrap.dedent(
            """
            import sys
            import threading

            def on_signal():
                sys.stdin.readline()
                press("z")

            threading.Thread(target=on_signal, daemon=True).start()
            msvcrt.ungetch(b"q")
            print("ready", flush=True)
            wide = msvcrt.getwch()
            narrow = msvcrt.getch().decode() if msvcrt.kbhit() else None
            report(wide=wide, narrow=narrow)
            """
        )
        child = subprocess.Popen(
            [sys.executable, "-c", source],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            creationflags=CREATE_NO_WINDOW,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        watchdog = threading.Timer(60, child.kill)
        watchdog.start()
        try:
            assert child.stdout is not None
            assert child.stdout.readline().strip() == "ready", "the child did not reach getwch()"
            time.sleep(1)
            assert child.poll() is None, "getwch() returned with only a byte pushed back"
            out, err = child.communicate("go\n", timeout=30)
        finally:
            watchdog.cancel()
            if child.poll() is None:
                child.kill()
                child.wait()
        assert child.returncode == 0, err
        assert json.loads(out.strip().splitlines()[-1]) == {"wide": "z", "narrow": "q"}


@WINDOWS
class TestLocking:
    """`locking(fd, mode, nbytes)` | O(1) - a byte range from the current
    position, exclusive, waited on only by `LK_LOCK` and `LK_RLCK`."""

    @pytest.fixture
    def two_fds(self, tmp_path: pathlib.Path) -> Any:
        path = tmp_path / "data.bin"
        path.write_bytes(b"\0" * 10)
        first = os.open(path, os.O_RDWR | getattr(os, "O_BINARY"))  # noqa: B009
        second = os.open(path, os.O_RDWR | getattr(os, "O_BINARY"))  # noqa: B009
        try:
            yield first, second
        finally:
            for fd in (first, second):
                try:
                    os.close(fd)
                except OSError:
                    pass

    @staticmethod
    def lock(fd: int, mode: int, offset: int, nbytes: int) -> None:
        os.lseek(fd, offset, os.SEEK_SET)
        msvcrt.locking(fd, mode, nbytes)

    def test_a_held_region_refuses_at_once(self, two_fds: tuple[int, int]) -> None:
        first, second = two_fds
        self.lock(first, msvcrt.LK_NBLCK, 100, 10)  # past the end of the file
        assert os.lseek(first, 0, os.SEEK_CUR) == 100, "the position did not move"

        for mode in (msvcrt.LK_NBLCK, msvcrt.LK_NBRLCK):
            with pytest.raises(PermissionError):
                self.lock(second, mode, 105, 1)
        self.lock(second, msvcrt.LK_NBLCK, 0, 10)  # outside the region
        self.lock(second, msvcrt.LK_UNLCK, 0, 10)

    def test_a_read_lock_is_exclusive_too(self, two_fds: tuple[int, int]) -> None:
        first, second = two_fds
        self.lock(first, msvcrt.LK_RLCK, 0, 5)
        with pytest.raises(PermissionError):
            self.lock(second, msvcrt.LK_NBRLCK, 0, 5)
        os.lseek(second, 0, os.SEEK_SET)
        with pytest.raises(PermissionError):
            os.write(second, b"x")

    def test_regions_are_unlocked_as_they_were_locked(self, two_fds: tuple[int, int]) -> None:
        first, _ = two_fds
        self.lock(first, msvcrt.LK_NBLCK, 100, 10)
        self.lock(first, msvcrt.LK_NBLCK, 110, 10)
        with pytest.raises(PermissionError):
            self.lock(first, msvcrt.LK_UNLCK, 100, 20)
        self.lock(first, msvcrt.LK_UNLCK, 100, 10)
        self.lock(first, msvcrt.LK_UNLCK, 110, 10)
        with pytest.raises(PermissionError):
            self.lock(first, msvcrt.LK_UNLCK, 110, 10)

    def test_closing_releases_the_lock(self, two_fds: tuple[int, int]) -> None:
        first, second = two_fds
        self.lock(first, msvcrt.LK_NBLCK, 0, 5)
        os.close(first)
        self.lock(second, msvcrt.LK_NBLCK, 0, 5)

    @pytest.mark.timing
    @pytest.mark.parametrize("mode", ["LK_LOCK", "LK_RLCK"])
    def test_a_waiting_lock_retries_then_raises(self, two_fds: tuple[int, int], mode: str) -> None:
        first, second = two_fds
        self.lock(first, msvcrt.LK_NBLCK, 0, 5)
        start = time.perf_counter()
        with pytest.raises(OSError) as refused:
            self.lock(second, getattr(msvcrt, mode), 0, 5)
        waited = time.perf_counter() - start
        assert refused.value.errno == 36  # EDEADLOCK in the C runtime
        assert 5 < waited < 30, f"gave up after {waited:.1f} s"


@WINDOWS
class TestHeapminWalksTheHeap:
    """`heapmin()` | O(h) | O(1) - h = blocks in the C runtime heap, which
    the heap Windows gives the process may walk, and never more than once."""

    def test_it_returns_none(self) -> None:
        assert msvcrt.heapmin() is None

    @staticmethod
    def costs() -> dict[int, float]:
        """Each size in a fresh process: a heap that has already grown and
        shrunk once places the next blocks differently."""
        costs: dict[int, float] = {}
        for count in (1_000, 4_000, 16_000):
            found = in_console(
                f"""
                blocks = [bytes(20_000) for _ in range({count})]
                msvcrt.heapmin()
                report(ns=best_ns(msvcrt.heapmin, inner=1))
                """
            )
            costs[count] = found["ns"]
        return costs

    @pytest.mark.timing
    def test_time_is_at_most_linear_in_the_blocks(self) -> None:
        costs = self.costs()
        ratio = costs[16_000] / costs[1_000]
        assert ratio < 64, f"16x the blocks cost x{ratio:.1f}: {costs}"

    @pytest.mark.timing
    @pytest.mark.skipif(
        sysconfig.get_platform() != "win-arm64", reason="the walk is observed on ARM64 builds"
    )
    def test_time_follows_the_blocks_on_arm64(self) -> None:
        costs = self.costs()
        assert costs[1_000] < costs[4_000] < costs[16_000], costs
        ratio = costs[16_000] / costs[1_000]
        assert ratio > 4, f"16x the blocks cost x{ratio:.1f}"


@WINDOWS
class TestDescriptorsAndHandles:
    """`setmode()`, `get_osfhandle()`, `open_osfhandle()` | O(1)."""

    def test_setmode_returns_the_previous_mode(self, tmp_path: pathlib.Path) -> None:
        text, binary = getattr(os, "O_TEXT"), getattr(os, "O_BINARY")  # noqa: B009
        path = tmp_path / "t.txt"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | binary)
        try:
            assert msvcrt.setmode(fd, text) == binary
            os.write(fd, b"a\nb")
            assert msvcrt.setmode(fd, binary) == text
        finally:
            os.close(fd)
        assert path.read_bytes() == b"a\r\nb"

    def test_handles_round_trip(self, tmp_path: pathlib.Path) -> None:
        winapi: Any = importlib.import_module("_winapi")

        path = tmp_path / "h.bin"
        path.write_bytes(b"data")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY"))  # noqa: B009
        try:
            handle = msvcrt.get_osfhandle(fd)
            process = winapi.GetCurrentProcess()
            duplicate = winapi.DuplicateHandle(
                process, handle, process, 0, False, winapi.DUPLICATE_SAME_ACCESS
            )
        finally:
            os.close(fd)

        new_fd = msvcrt.open_osfhandle(duplicate, os.O_RDONLY)
        assert msvcrt.get_osfhandle(new_fd) == duplicate
        assert os.read(new_fd, 10) == b"data"
        os.close(new_fd)

        import ctypes

        kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined]
        flags = ctypes.c_ulong()
        is_open = kernel32.GetHandleInformation(ctypes.c_void_p(duplicate), ctypes.byref(flags))
        assert not is_open, "closing the descriptor closed the handle"

    def test_an_unknown_descriptor_raises(self) -> None:
        with pytest.raises(OSError):
            msvcrt.get_osfhandle(99_999)


@WINDOWS
class TestErrorModeAndConstants:
    """The error-mode functions and the constants: O(1) each."""

    def test_seterrormode_returns_the_previous_flags(self) -> None:
        result = run_child(
            "import msvcrt\n"
            "old = msvcrt.SetErrorMode(msvcrt.SEM_FAILCRITICALERRORS)\n"
            "now = msvcrt.GetErrorMode()\n"
            "import threading\n"
            "seen = []\n"
            "worker = threading.Thread(target=lambda: seen.append(msvcrt.GetErrorMode()))\n"
            "worker.start()\n"
            "worker.join()\n"
            "back = msvcrt.SetErrorMode(old)\n"
            "print(now == msvcrt.SEM_FAILCRITICALERRORS == back, msvcrt.GetErrorMode() == old)\n"
            "print(seen == [msvcrt.SEM_FAILCRITICALERRORS])\n"
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["True", "True", "True"], "another thread sees it too"

    def test_the_constants(self) -> None:
        assert (msvcrt.LK_UNLCK, msvcrt.LK_LOCK, msvcrt.LK_NBLCK) == (0, 1, 2)
        assert (msvcrt.LK_RLCK, msvcrt.LK_NBRLCK) == (3, 4)
        assert (msvcrt.SEM_FAILCRITICALERRORS, msvcrt.SEM_NOGPFAULTERRORBOX) == (1, 2)
        assert (msvcrt.SEM_NOALIGNMENTFAULTEXCEPT, msvcrt.SEM_NOOPENFILEERRORBOX) == (4, 0x8000)
        assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", msvcrt.CRT_ASSEMBLY_VERSION)

    @pytest.mark.skipif(hasattr(sys, "gettotalrefcount"), reason="a debug build has them")
    def test_the_debug_names_are_absent_from_a_release_build(self) -> None:
        for name in ("CrtSetReportFile", "CrtSetReportMode", "set_error_mode", "CRT_WARN"):
            assert not hasattr(msvcrt, name), name


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
        timeout=60,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess with a console of its own and no
    window, so a block that reads keys reads only what it pushed back, and a
    block that would wait for a key times out instead."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @WINDOWS
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

    @WINDOWS
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if 'keys == [b"q"]' in s)
        mutated = source.replace('keys == [b"q"]', 'keys == [b"x"]', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
