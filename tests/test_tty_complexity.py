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
  `ISIG` and `OPOST`. From 3.12 each returns a list equal to what
  `tcgetattr()` read before the call, and restoring that list with
  `tcsetattr()` gives back the original attributes.
* `cfmakeraw()` and `cfmakecbreak()` (3.12+) are asserted to return `None`,
  to leave the list they were given as the same object, and to make no
  `tcgetattr()` or `tcsetattr()` call: both names are replaced, in `tty` and in
  `termios`, by functions that raise. The list each produces carries the same
  four flag words that `setraw()` or `setcbreak()` leaves on the terminal.
  From 3.12.2 both cbreak functions are asserted to leave `ICRNL` set.
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
* The module is Unix-only; on Windows this file skips at import.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import textwrap
from collections.abc import Callable, Iterator
from typing import Any

import pytest

termios = pytest.importorskip("termios", reason="tty is a Unix-only module")
import tty  # noqa: E402  (after the platform guard)

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tty.md"
EXPECTED_BLOCKS = 2
HAS_CFMAKE = sys.version_info >= (3, 12)
CFMAKE_ONLY = pytest.mark.skipif(not HAS_CFMAKE, reason="cfmakeraw/cfmakecbreak are 3.12+")


@pytest.fixture
def terminal() -> Iterator[int]:
    """The terminal end of a fresh pseudo-terminal pair."""
    try:
        controller, slave = os.openpty()
    except OSError:  # pragma: no cover - only on a build without ptys
        pytest.skip("needs a working pseudo-terminal")
    try:
        yield slave
    finally:
        os.close(slave)
        os.close(controller)


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

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-only")
    @CFMAKE_ONLY
    @pytest.mark.parametrize("change", [tty.setraw, tty.setcbreak])
    def test_the_replaced_attributes_are_returned_and_restore_the_terminal(
        self, terminal: int, change: Callable[[int], Any]
    ) -> None:
        before = termios.tcgetattr(terminal)

        saved = change(terminal)
        assert termios.tcgetattr(terminal) != before
        termios.tcsetattr(terminal, termios.TCSANOW, saved)

        assert saved == before
        assert termios.tcgetattr(terminal) == before


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
    def test_cbreak_leaves_carriage_return_translation_on(self, terminal: int) -> None:
        mode = termios.tcgetattr(terminal)
        assert mode[tty.IFLAG] & termios.ICRNL
        getattr(tty, "cfmakecbreak")(mode)  # noqa: B009 - typeshed 3.12+

        tty.setcbreak(terminal)

        assert mode[tty.IFLAG] & termios.ICRNL
        assert termios.tcgetattr(terminal)[tty.IFLAG] & termios.ICRNL


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

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-only")
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
