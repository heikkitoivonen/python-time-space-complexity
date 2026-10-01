"""Tests for docs/stdlib/tty.md.

The page prices every operation at O(1): each one does a fixed set of bit
operations on the seven-item list `termios.tcgetattr()` returns, whose
control-character list has `termios.NCCS` entries on every call. There is no
size variable to vary, so the rows are settled by observation on a real
pseudo-terminal from `os.openpty()`: how many `tcgetattr()`/`tcsetattr()`
calls each function makes, which flags it changes, and whether it touches the
terminal at all.

Measurement scope:

* `setraw()` and `setcbreak()` are counted through wrappers installed on the
  module's own `tcgetattr` and `tcsetattr` names: exactly one of each per call.
  The mode each leaves is read back from the terminal: raw clears `ECHO`,
  `ICANON`, `ISIG` and `OPOST`; cbreak clears `ECHO` and `ICANON` and keeps
  `ISIG` and `OPOST`. From 3.12.1 each returns a list equal to what
  `tcgetattr()` read before the call, and restoring that list with
  `tcsetattr()` gives back the original attributes, apart from `PENDIN`,
  which the macOS terminal driver sets when `ICANON` comes back on; that
  bit is masked before comparing, here and in the page's first block. The
  terminal's `VMIN` and `VTIME` are first set to 5 and 2, away from the 1 and
  0 both modes write. On 3.12.0 the returned list carries 1 and 0; 3.12.1 and
  3.12.2 return 5 and 2 (each observed on that release).
* With echo off and a line written to the controller, `setraw()` with the
  default `when` or `TCSAFLUSH` leaves nothing to read on the terminal
  (`select()` with a 0.2 s timeout), and with `TCSADRAIN` or `TCSANOW` the
  whole line is still there to read; observed on Linux on 3.10 to 3.14, and run by the macOS
  CI job.
* A child process that calls `setraw()` on an inherited terminal descriptor
  and exits leaves the terminal in raw mode for the parent to read back.
* `setcbreak()` leaves `ICRNL` as it was, set or clear, on every version
  except 3.12.0 and 3.12.1, which clear it (observed on 3.10, 3.11,
  3.12.0-3.12.2, 3.13 and 3.14).
* With echo on and canonical mode, one byte written to the controller without
  a line end is not readable on the terminal within 0.2 s; after `setraw()` or
  `setcbreak()` with `TCSANOW` it is, and reads back as that one byte.
* `cfmakeraw()` and `cfmakecbreak()` (3.12+) are asserted to return `None`,
  to change the flag words of the list they were given, and to make no
  `tcgetattr()` or `tcsetattr()` call: both names are replaced, in `tty` and in
  `termios`, by functions that raise. The list each produces carries the same
  four flag words that `setraw()` or `setcbreak()` leaves on the terminal.
  From 3.12.2 `cfmakecbreak()` is asserted to leave `ICRNL` as it was.
* `IFLAG` to `CC` are asserted to be 0 to 6, and `mode[tty.CC]` to be the
  `NCCS`-entry control-character list.
* Both fenced blocks run in their own subprocess on a fresh pseudo-terminal,
  and a mutated assertion is asserted to make its block fail. The second block
  calls `cfmakeraw()`, so on 3.10 and 3.11 it is skipped by name.

Not settled here:

* That the bit operations are a fixed set, and so O(1), is read from Lib/tty.py
  on each supported version rather than measured: there is no input whose size
  the functions could depend on.
* The wait the page places outside the O(1): with `TCSADRAIN` or
  `TCSAFLUSH`, `tcsetattr()` waits for queued output to be sent (and
  `TCSAFLUSH` also discards unread input). Nothing is written to the terminal
  before a mode change here, so that wait is not exercised.
* That macOS sets `PENDIN` is read from the BSD terminal driver's `ttioctl()`,
  and observed only by the macOS CI job; Linux leaves the bit clear.
* The module is Unix-only; on Windows this file skips at import.
"""

from __future__ import annotations

import os
import pathlib
import re
import select
import subprocess
import sys
import textwrap
from collections.abc import Callable, Iterator
from typing import Any

import pytest

if sys.platform == "win32":
    pytest.skip("platform: tty is a Unix-only module", allow_module_level=True)
import termios  # noqa: E402  (after the platform guard)
import tty  # noqa: E402  (after the platform guard)

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tty.md"
EXPECTED_BLOCKS = 2
HAS_CFMAKE = sys.version_info >= (3, 12)
CBREAK_CLEARS_ICRNL = (3, 12, 0) <= sys.version_info < (3, 12, 2)
CFMAKE_ONLY = pytest.mark.skipif(not HAS_CFMAKE, reason="cfmakeraw/cfmakecbreak are 3.12+")


@pytest.fixture
def pair() -> Iterator[tuple[int, int]]:
    """Both ends of a fresh pseudo-terminal pair, controller first."""
    try:
        controller, slave = os.openpty()
    except OSError:  # pragma: no cover - only on a build without ptys
        pytest.skip("missing pty: needs a working pseudo-terminal")
    try:
        yield controller, slave
    finally:
        os.close(slave)
        os.close(controller)


@pytest.fixture
def terminal(pair: tuple[int, int]) -> int:
    """The terminal end of a fresh pseudo-terminal pair."""
    return pair[1]


class CallCounter:
    """Counts calls through the `tcgetattr`/`tcsetattr` names in `tty`."""

    def __init__(self) -> None:
        self.get = 0
        self.set = 0


@pytest.fixture
def counted(monkeypatch: pytest.MonkeyPatch) -> CallCounter:
    counter = CallCounter()
    # tty re-exports these from termios with a star import, which typeshed omits.
    real_get, real_set = getattr(tty, "tcgetattr"), getattr(tty, "tcsetattr")  # noqa: B009

    def get(fd: int) -> Any:
        counter.get += 1
        return real_get(fd)

    def put(fd: int, when: int, attributes: Any) -> None:
        counter.set += 1
        real_set(fd, when, attributes)

    monkeypatch.setattr(tty, "tcgetattr", get)
    monkeypatch.setattr(tty, "tcsetattr", put)
    return counter


def without_pendin(mode: list[Any]) -> list[Any]:
    """`mode` with `PENDIN` cleared: the BSD terminal driver on macOS sets it in
    `lflag` when a `tcsetattr()` turns `ICANON` back on, and Linux never does."""
    mode = list(mode)
    mode[tty.LFLAG] &= ~termios.PENDIN
    return mode


def flag_words(mode: list[Any]) -> tuple[int, int, int, int]:
    return mode[tty.IFLAG], mode[tty.OFLAG], mode[tty.CFLAG], mode[tty.LFLAG]


class TestModeChangesAreOneReadAndOneWrite:
    """`setraw()` / `setcbreak()`: O(1), one `tcgetattr()` and one `tcsetattr()`."""

    @pytest.mark.parametrize("change", [tty.setraw, tty.setcbreak])
    def test_one_read_and_one_write_per_call(
        self, terminal: int, counted: CallCounter, change: Callable[[int], Any]
    ) -> None:
        change(terminal)

        assert (counted.get, counted.set) == (1, 1)

    def test_raw_turns_off_signals_and_output_processing(self, terminal: int) -> None:
        tty.setraw(terminal)
        mode = termios.tcgetattr(terminal)

        assert not mode[tty.LFLAG] & (termios.ECHO | termios.ICANON | termios.ISIG)
        assert not mode[tty.OFLAG] & termios.OPOST

    def test_cbreak_keeps_signals_and_output_processing(self, terminal: int) -> None:
        before = termios.tcgetattr(terminal)
        assert before[tty.LFLAG] & termios.ISIG and before[tty.OFLAG] & termios.OPOST

        tty.setcbreak(terminal)
        mode = termios.tcgetattr(terminal)

        assert not mode[tty.LFLAG] & (termios.ECHO | termios.ICANON)
        assert mode[tty.LFLAG] & termios.ISIG
        assert mode[tty.OFLAG] & termios.OPOST

    @pytest.mark.skipif(
        sys.version_info < (3, 12, 1), reason="the original attributes are returned from 3.12.1"
    )
    @pytest.mark.parametrize("change", [tty.setraw, tty.setcbreak])
    def test_the_replaced_attributes_are_returned_and_restore_the_terminal(
        self, terminal: int, change: Callable[[int], Any]
    ) -> None:
        mode = termios.tcgetattr(terminal)
        mode[tty.CC][termios.VMIN] = b"\x05"
        mode[tty.CC][termios.VTIME] = b"\x02"
        termios.tcsetattr(terminal, termios.TCSANOW, mode)
        before = termios.tcgetattr(terminal)

        saved = change(terminal)
        assert termios.tcgetattr(terminal) != before
        termios.tcsetattr(terminal, termios.TCSANOW, saved)

        assert saved == before
        assert without_pendin(termios.tcgetattr(terminal)) == before

    @pytest.mark.skipif(CBREAK_CLEARS_ICRNL, reason="3.12.0 and 3.12.1 clear ICRNL")
    @pytest.mark.parametrize("icrnl", [True, False])
    def test_cbreak_leaves_carriage_return_translation_as_it_was(
        self, terminal: int, icrnl: bool
    ) -> None:
        mode = termios.tcgetattr(terminal)
        mode[tty.IFLAG] = (
            mode[tty.IFLAG] | termios.ICRNL if icrnl else mode[tty.IFLAG] & ~termios.ICRNL
        )
        termios.tcsetattr(terminal, termios.TCSANOW, mode)

        tty.setcbreak(terminal)

        assert bool(termios.tcgetattr(terminal)[tty.IFLAG] & termios.ICRNL) is icrnl

    @pytest.mark.parametrize("change", [tty.setraw, tty.setcbreak])
    def test_one_byte_is_readable_without_a_line_end(
        self, pair: tuple[int, int], change: Callable[[int, int], Any]
    ) -> None:
        controller, terminal = pair
        os.write(controller, b"a")
        assert not select.select([terminal], [], [], 0.2)[0], "canonical mode waits for a line"

        change(terminal, termios.TCSANOW)

        assert select.select([terminal], [], [], 5)[0]
        assert os.read(terminal, 10) == b"a"

    def test_a_mode_change_outlives_the_process_that_made_it(self, terminal: int) -> None:
        child = "import sys, tty; tty.setraw(int(sys.argv[1]))"
        subprocess.run(
            [sys.executable, "-c", child, str(terminal)],
            pass_fds=[terminal],
            check=True,
            timeout=60,
        )

        mode = termios.tcgetattr(terminal)
        assert not mode[tty.LFLAG] & (termios.ECHO | termios.ICANON | termios.ISIG)


class TestTheDefaultWhenDiscardsTypedAheadInput:
    """Best practices: the default `TCSAFLUSH` discards unread input, and
    `TCSADRAIN` or `TCSANOW` keeps it. Echo is turned off first, so no echoed
    output is queued for a drain to wait on."""

    @staticmethod
    def type_ahead(controller: int, terminal: int) -> None:
        mode = termios.tcgetattr(terminal)
        mode[tty.LFLAG] &= ~termios.ECHO
        termios.tcsetattr(terminal, termios.TCSANOW, mode)
        os.write(controller, b"typed ahead\n")
        assert select.select([terminal], [], [], 5)[0], "the line never arrived"

    @pytest.mark.parametrize(
        ("when", "kept"),
        [
            (None, False),
            (termios.TCSAFLUSH, False),
            (termios.TCSADRAIN, True),
            (termios.TCSANOW, True),
        ],
    )
    def test_unread_input_survives_only_without_a_flush(
        self, pair: tuple[int, int], when: int | None, kept: bool
    ) -> None:
        controller, terminal = pair
        self.type_ahead(controller, terminal)

        if when is None:
            tty.setraw(terminal)
        else:
            tty.setraw(terminal, when)

        assert bool(select.select([terminal], [], [], 0.2)[0]) is kept
        if kept:
            assert os.read(terminal, 100) == b"typed ahead\n"


@CFMAKE_ONLY
class TestCfmakeEditsTheListOnly:
    """`cfmakeraw()` / `cfmakecbreak()`: O(1), edit the list in place, no syscall."""

    @pytest.fixture
    def no_terminal_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: Any) -> Any:
            raise AssertionError("cfmake* must not touch the terminal")

        for module in (tty, termios):
            monkeypatch.setattr(module, "tcgetattr", refuse)
            monkeypatch.setattr(module, "tcsetattr", refuse)

    @pytest.mark.parametrize("name", ["cfmakeraw", "cfmakecbreak"])
    def test_the_list_is_edited_in_place_without_a_system_call(
        self, terminal: int, name: str, request: pytest.FixtureRequest
    ) -> None:
        mode = termios.tcgetattr(terminal)
        before = flag_words(mode)
        request.getfixturevalue("no_terminal_calls")

        result = getattr(tty, name)(mode)

        assert result is None
        assert flag_words(mode) != before
        assert not mode[tty.LFLAG] & (termios.ECHO | termios.ICANON)
        assert mode[tty.CC][termios.VMIN] == 1 and mode[tty.CC][termios.VTIME] == 0

    @pytest.mark.parametrize(
        ("name", "change"), [("cfmakeraw", tty.setraw), ("cfmakecbreak", tty.setcbreak)]
    )
    def test_the_list_matches_what_the_set_function_applies(
        self, terminal: int, name: str, change: Callable[[int], Any]
    ) -> None:
        mode = termios.tcgetattr(terminal)
        getattr(tty, name)(mode)

        change(terminal)

        assert flag_words(mode) == flag_words(termios.tcgetattr(terminal))

    @pytest.mark.skipif(sys.version_info < (3, 12, 2), reason="ICRNL is kept from 3.12.2")
    @pytest.mark.parametrize("icrnl", [True, False])
    def test_cbreak_leaves_carriage_return_translation_as_it_was(
        self, terminal: int, icrnl: bool
    ) -> None:
        mode = termios.tcgetattr(terminal)
        mode[tty.IFLAG] = (
            mode[tty.IFLAG] | termios.ICRNL if icrnl else mode[tty.IFLAG] & ~termios.ICRNL
        )

        getattr(tty, "cfmakecbreak")(mode)  # noqa: B009 - typeshed 3.12+

        assert bool(mode[tty.IFLAG] & termios.ICRNL) is icrnl


class TestConstantsIndexTheAttributeList:
    """`tty.IFLAG` to `tty.CC`: O(1) indices 0 to 6 into the attribute list."""

    def test_the_indices_follow_the_list_layout(self, terminal: int) -> None:
        names = ["IFLAG", "OFLAG", "CFLAG", "LFLAG", "ISPEED", "OSPEED", "CC"]
        mode = termios.tcgetattr(terminal)

        assert [getattr(tty, name) for name in names] == list(range(7)) == list(range(len(mode)))
        assert len(mode[tty.CC]) == termios.NCCS


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
    """Each block opens its own pseudo-terminal, so none needs the test's own
    terminal, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if "cfmake" in source and not HAS_CFMAKE:
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == (EXPECTED_BLOCKS if HAS_CFMAKE else EXPECTED_BLOCKS - 1)
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "& termios.ISIG #" in s)
        mutated = source.replace(
            "assert mode[tty.LFLAG] & termios.ISIG #",
            "assert not mode[tty.LFLAG] & termios.ISIG #",
            1,
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
