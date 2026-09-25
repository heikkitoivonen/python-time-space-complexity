"""Tests for docs/stdlib/readline.md.

The page prices an in-memory history list, history files and a completion
hook, and gives two bounds wherever GNU readline and libedit differ. Every
interpreter these tests were written against - the uv-managed builds of each
supported version - uses libedit, so the libedit bounds are measured and the
GNU readline ones are read from source. Behaviour at the prompt - completion,
hooks, automatic history - is observed by running `input()` in a child process
on a pseudo-terminal and typing into it.

Measurement scope:

* libedit's indexed calls: `get_history_item()`, `replace_history_item()` and
  `remove_history_item()` at the newest entry cost more than 5x as much at
  32,000 entries as at 2,000, and less than 3x at the oldest entry, so the cost
  follows the position counted from the oldest end. `remove_history_item()` is
  timed together with an `add_history()` that restores the length.
* Reading the whole history by index on libedit: 4x the entries costs more
  than 8x, between the 4x a linear scan predicts and the 16x of a quadratic one,
  at 1,000 and 4,000 entries.
* `add_history()` per call, and `get_current_history_length()`, cost less than
  3x as much at 100,000 entries as at 1,000. `clear_history()` costs more than
  20x as much for 100x the entries.
* `input()` on a pseudo-terminal: the fastest of 40 lines costs more than 5x as
  much with 100,000 entries held as with 100, and less than 3x with automatic
  history turned off, which is the control showing the cost is the comparison
  with the newest entry. Typing "same", "same", "other", "same" stores
  "same", "other", "same"; with automatic history off nothing is stored.
* History files: `read_history_file()` appends to the history already held
  and raises `FileNotFoundError` for a missing file. `set_history_length(3)`
  leaves six in-memory entries alone and leaves three in the file after either
  writer; under libedit the truncated file has lost its header line and
  `read_history_file()` raises `OSError` on it, while removing the oldest
  entries before writing keeps it readable. `append_history_file(1)` writes
  the newest entry. Timed: `append_history_file(1)` costs less than 3x as much
  with 100,000 entries held as with 100, and appending 100,000 of them more
  than 20x as much as appending 1,000. Into a copy of a 100,000-line file it
  costs more than 10x as much as into a 1,000-line one with a history length
  set, and less than 3x without. `read_history_file()` and `write_history_file()` cost more than 5x
  as much for 10x the entries.
* Completion on a pseudo-terminal, with the user's init files replaced by
  empty ones: one Tab after "ap" with two matches calls the completer with
  states 0, 1 and 2 and no more, and one after "eat ban" reports
  text "ban", begin index 4, end index 7, the line buffer and completion type
  9 (Tab). With the delimiters set to a space, "eat=ban" reaches the completer
  whole. `get_completer()` returns the object set. Under libedit, GNU
  readline's "tab: complete" binding leaves Tab inserting a tab character and
  the completer uncalled.
* Hooks on a pseudo-terminal: under libedit the startup, pre-input and
  display-matches hooks are observed not to be called. Under GNU readline
  the test asserts one startup and one pre-input call per line; that branch
  has not run on any interpreter available here.
* Every fenced Python block runs in its own subprocess and asserts its own
  result, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The GNU readline bounds: `history_get()` indexes an array (O(1)),
  `remove_history()` moves the newer entries down one (O(h - i)),
  `replace_history_entry()` stores into its slot (O(1)), `clear_history()`
  frees each entry and `rl_insert_text()` shifts the text after the cursor,
  read from GNU readline's history.c and text.c. The GNU-only tests below are
  guarded on the backend and skip under libedit.
* The space bounds of the file writers: GNU readline's history_do_write()
  builds everything it writes in one buffer, and history_truncate_file()
  reads the whole file into one, per histfile.c; libedit's are not
  measured. Completion's O(m) space is the match array the library builds.
* That `input()` costs O(1) plus the line on GNU readline follows from
  Modules/readline.c, which calls `history_get(length)` once per line read,
  and the array lookup above.
* `redisplay()`, `insert_text()` and `get_line_buffer()` are only meaningful
  inside a hook while a line is edited; the O(b) bounds follow from
  Modules/readline.c converting the whole buffer and from the libraries'
  line-buffer handling, and are not varied in b.
* `parse_and_bind()` and `read_init_file()` are O(L) and O(F) by reading one
  line and every line of a file, and O(F) space for the bindings and macros
  a file can define; neither is varied in size.
* History and completion bounds treat each line and match as O(1), a
  cost-model choice the page states; line length is not varied.
* That GNU readline's `append_history_file()` needs an existing file: its
  history_do_write() in histfile.c opens for appending without `O_CREAT`.
  libedit is observed to create it.
* That history files from one library may not be readable by the other is
  the official documentation's statement; only libedit is available here.
* `append_history_file()`, `clear_history()` and `set_pre_input_hook()` are
  present only if the library provides them. The interpreters CI pins have
  all three; some 3.12 patch builds from the same distributor lack them.
* `readline` does not exist on Windows; the module is skipped there.
"""

from __future__ import annotations

import os
import pathlib
import re
import select
import shutil
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

readline = pytest.importorskip("readline")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "readline.md"
EXPECTED_BLOCKS = 5
LIBEDIT = "libedit" in (readline.__doc__ or "")
TAB_BINDING = "bind ^I rl_complete" if LIBEDIT else "tab: complete"

libedit_only = pytest.mark.skipif(not LIBEDIT, reason="libedit's history list")
gnu_only = pytest.mark.skipif(LIBEDIT, reason="GNU readline's history array")
needs_clear = pytest.mark.skipif(
    not hasattr(readline, "clear_history"), reason="the library lacks clear_history"
)
needs_append = pytest.mark.skipif(
    not hasattr(readline, "append_history_file"), reason="the library lacks append_history"
)


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


def empty_history() -> None:
    if hasattr(readline, "clear_history"):
        readline.clear_history()
    else:
        while readline.get_current_history_length():
            readline.remove_history_item(0)


def fill(entries: int) -> None:
    """Replace the history with `entries` distinct lines."""
    empty_history()
    for index in range(entries):
        readline.add_history(f"line {index}")


def history() -> list[str]:
    return [
        readline.get_history_item(index)
        for index in range(1, readline.get_current_history_length() + 1)
    ]


@pytest.fixture(autouse=True)
def _clean_readline() -> Iterator[None]:
    delims = readline.get_completer_delims()
    empty_history()
    yield
    empty_history()
    readline.set_history_length(-1)
    readline.set_completer(None)
    readline.set_completer_delims(delims)
    readline.set_auto_history(True)


def interactive(setup: str, keys: list[bytes], report: str, reads: int | None = None) -> str:
    """Run `input()` `reads` times on a pseudo-terminal, typing `keys`.

    `setup` runs first. Each entry of `keys` is typed, with a pause after it,
    once the child prints READY; `reads` defaults to the carriage returns typed.
    `report` is an expression whose repr the child prints after its last
    line, and may use `line`, the last line read. Returns that repr.
    """
    lines = b"".join(keys).count(b"\r") if reads is None else reads
    child = "\n".join(
        [
            "import readline, sys, time",
            setup,
            "print('READY', flush=True)",
            f"for _ in range({lines}):",
            "    line = input('> ')",
            f"print('RESULT', repr({report}), flush=True)",
        ]
    )
    master, slave = os.openpty()
    process = subprocess.Popen(
        [sys.executable, "-c", child],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
        env={**os.environ, "TERM": "xterm", "INPUTRC": os.devnull, "EDITRC": os.devnull},
    )
    os.close(slave)
    output = b""

    def read_until(pattern: bytes, seconds: float = 60) -> None:
        nonlocal output
        deadline = time.monotonic() + seconds
        while not re.search(pattern, output) and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    return

    try:
        read_until(rb"READY")
        for key in keys:
            os.write(master, key)
            time.sleep(0.2)
        read_until(rb"RESULT [^\n]*\n")
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
    text = output.decode(errors="replace")
    match = re.search(r"RESULT (.*)", text)
    assert match, f"the child printed no result:\n{text}"
    return match.group(1).strip()


class TestTheHistoryList:
    """`add_history` | O(1) amortized, `get_current_history_length` | O(1), and
    the indexing conventions: `get_history_item` is one-based and returns
    `None` outside the history; `replace_history_item` and
    `remove_history_item` are zero-based and raise `ValueError`."""

    def test_add_history_appends_at_the_newest_end(self) -> None:
        for line in ["first", "second", "third"]:
            readline.add_history(line)

        assert readline.get_current_history_length() == 3
        assert history() == ["first", "second", "third"]

    def test_get_history_item_is_one_based(self) -> None:
        fill(3)

        assert readline.get_history_item(1) == "line 0"
        assert readline.get_history_item(3) == "line 2"
        assert readline.get_history_item(0) is None
        assert readline.get_history_item(4) is None

    def test_replace_and_remove_are_zero_based(self) -> None:
        fill(3)

        readline.replace_history_item(0, "replaced")
        readline.remove_history_item(2)

        assert history() == ["replaced", "line 1"]

    @pytest.mark.parametrize("position", [3, -1])
    def test_a_position_outside_the_history_raises(self, position: int) -> None:
        fill(3)

        with pytest.raises(ValueError):
            readline.remove_history_item(position)
        with pytest.raises(ValueError):
            readline.replace_history_item(position, "x")
        assert readline.get_current_history_length() == 3

    @needs_clear
    def test_clear_history_empties_it(self) -> None:
        fill(10)

        readline.clear_history()

        assert readline.get_current_history_length() == 0

    @pytest.mark.timing
    def test_adding_costs_the_same_at_any_length(self) -> None:
        costs = []
        for entries in (1_000, 100_000):
            fill(entries)
            costs.append(best_ns(lambda: readline.add_history("x"), inner=1_000))

        ratio = costs[1] / costs[0]
        assert ratio < 3, f"add_history at 1,000 and 100,000 entries: {costs} ns, x{ratio:.2f}"

    @pytest.mark.timing
    def test_the_length_costs_the_same_at_any_length(self) -> None:
        costs = []
        for entries in (1_000, 100_000):
            fill(entries)
            costs.append(best_ns(readline.get_current_history_length, inner=1_000))

        ratio = costs[1] / costs[0]
        assert ratio < 3, f"length at 1,000 and 100,000 entries: {costs} ns, x{ratio:.2f}"

    @needs_clear
    @pytest.mark.timing
    def test_clearing_frees_every_entry(self) -> None:
        costs = []
        for entries in (1_000, 100_000):
            durations = []
            for _ in range(3):
                fill(entries)
                start = time.perf_counter_ns()
                readline.clear_history()
                durations.append(time.perf_counter_ns() - start)
            costs.append(min(durations))

        ratio = costs[1] / costs[0]
        assert ratio > 20, f"clear_history at 1,000 and 100,000 entries: {costs} ns, x{ratio:.2f}"


def _indexed_call(name: str, entries: int, position: int) -> Callable[[], Any]:
    """One indexed call at zero-based `position`, leaving the length unchanged."""
    if name == "get":
        return lambda: readline.get_history_item(position + 1)
    if name == "replace":
        return lambda: readline.replace_history_item(position, "x")

    def remove_and_restore() -> None:
        readline.remove_history_item(position)
        readline.add_history("x")

    assert position in (0, entries - 1), "removing elsewhere would reorder the history"
    return remove_and_restore


class TestIndexedCallsByBackend:
    """`get_history_item`, `replace_history_item`, `remove_history_item`:
    O(i) on libedit, which walks from the oldest entry; O(1), O(1) and
    O(h - i) on GNU readline, which keeps an array.

    Each is timed at the oldest and at the newest entry of a 2,000- and a
    32,000-entry history. A cost independent of position would move neither;
    a walk from the oldest end moves only the newest.
    """

    SIZES = (2_000, 32_000)

    def ratio(self, name: str, oldest: bool) -> tuple[float, list[float]]:
        costs = []
        for entries in self.SIZES:
            fill(entries)
            position = 0 if oldest else entries - 1
            costs.append(best_ns(_indexed_call(name, entries, position), inner=50))
        return costs[1] / costs[0], costs

    @libedit_only
    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["get", "replace", "remove"])
    def test_libedit_walks_to_the_newest_entry(self, name: str) -> None:
        ratio, costs = self.ratio(name, oldest=False)

        assert ratio > 5, f"{name} at the newest of 2,000 and 32,000: {costs} ns, x{ratio:.2f}"

    @libedit_only
    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["get", "replace", "remove"])
    def test_libedit_reaches_the_oldest_entry_at_once(self, name: str) -> None:
        ratio, costs = self.ratio(name, oldest=True)

        assert ratio < 3, f"{name} at the oldest of 2,000 and 32,000: {costs} ns, x{ratio:.2f}"

    @gnu_only
    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["get", "replace"])
    def test_gnu_readline_indexes_an_array(self, name: str) -> None:
        ratio, costs = self.ratio(name, oldest=False)

        assert ratio < 3, f"{name} at the newest of 2,000 and 32,000: {costs} ns, x{ratio:.2f}"

    @gnu_only
    @pytest.mark.timing
    def test_gnu_readline_shifts_the_newer_entries_on_remove(self) -> None:
        ratio, costs = self.ratio("remove", oldest=True)

        assert ratio > 5, f"remove at the oldest of 2,000 and 32,000: {costs} ns, x{ratio:.2f}"


class TestReadingTheWholeHistory:
    """Looping `get_history_item()` over a long history on libedit is O(h²).

    4x the entries: a linear scan predicts 4x, a quadratic one 16x."""

    @libedit_only
    @pytest.mark.timing
    def test_one_lookup_per_entry_is_quadratic_on_libedit(self) -> None:
        costs = []
        for entries in (1_000, 4_000):
            fill(entries)
            costs.append(best_ns(history, repeats=5))

        ratio = costs[1] / costs[0]
        assert ratio > 8, f"reading 1,000 and 4,000 entries: {costs} ns, x{ratio:.2f}"

    def test_it_returns_every_entry_in_order(self) -> None:
        fill(100)

        assert history() == [f"line {index}" for index in range(100)]


def assert_truncated_to(path: str, expected: list[str]) -> None:
    """Read back a file the length limit truncated.

    GNU readline keeps it readable. libedit drops the header line when it
    truncates, and the file no longer reads.
    """
    empty_history()
    if LIBEDIT:
        with pytest.raises(OSError):
            readline.read_history_file(path)
        lines = pathlib.Path(path).read_text().splitlines()
        assert [line.replace("\\040", " ") for line in lines] == expected
    else:
        readline.read_history_file(path)
        assert history() == expected


class TestHistoryFiles:
    """`read_history_file` appends, `write_history_file` rewrites,
    `append_history_file(k)` writes the newest k, and `set_history_length`
    caps the file, not the list - at the price of a whole-file rewrite."""

    def test_reading_appends_to_what_is_held(self, tmp_path: pathlib.Path) -> None:
        path = str(tmp_path / "history")
        fill(3)
        readline.write_history_file(path)
        empty_history()
        readline.add_history("kept")

        readline.read_history_file(path)

        assert history() == ["kept", "line 0", "line 1", "line 2"]

    def test_a_missing_file_raises(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(FileNotFoundError):
            readline.read_history_file(str(tmp_path / "missing"))

    def test_the_length_caps_the_file_not_the_list(self, tmp_path: pathlib.Path) -> None:
        path = str(tmp_path / "history")
        fill(6)

        readline.set_history_length(3)
        readline.write_history_file(path)

        assert readline.get_history_length() == 3
        assert readline.get_current_history_length() == 6
        assert_truncated_to(path, ["line 3", "line 4", "line 5"])

    @libedit_only
    def test_capping_the_list_first_keeps_the_file_readable(self, tmp_path: pathlib.Path) -> None:
        """The warning's advice: remove the oldest entries, O(1) each on libedit."""
        path = str(tmp_path / "history")
        fill(6)

        while readline.get_current_history_length() > 3:
            readline.remove_history_item(0)
        readline.write_history_file(path)

        empty_history()
        readline.read_history_file(path)
        assert history() == ["line 3", "line 4", "line 5"]

    def test_the_length_is_minus_one_by_default(self) -> None:
        fresh = subprocess.run(
            [sys.executable, "-c", "import readline; print(readline.get_history_length())"],
            capture_output=True,
            text=True,
            check=True,
        )

        assert fresh.stdout.strip() == "-1"

    @needs_append
    def test_append_writes_the_newest_entries(self, tmp_path: pathlib.Path) -> None:
        path = str(tmp_path / "history")
        fill(2)
        readline.write_history_file(path)
        readline.add_history("newest")

        readline.append_history_file(1, path)

        empty_history()
        readline.read_history_file(path)
        assert history() == ["line 0", "line 1", "newest"]

    @needs_append
    def test_append_truncates_the_file_when_a_length_is_set(self, tmp_path: pathlib.Path) -> None:
        path = str(tmp_path / "history")
        fill(5)
        readline.write_history_file(path)
        readline.add_history("newest")

        readline.set_history_length(2)
        readline.append_history_file(1, path)

        assert_truncated_to(path, ["line 4", "newest"])

    @needs_append
    @libedit_only
    def test_libedit_appends_to_a_missing_file(self, tmp_path: pathlib.Path) -> None:
        path = str(tmp_path / "missing")
        readline.add_history("only")

        readline.append_history_file(1, path)

        empty_history()
        readline.read_history_file(path)
        assert history() == ["only"]

    @needs_append
    @pytest.mark.skipif(
        sys.version_info < (3, 12, 9) or (3, 13) <= sys.version_info < (3, 13, 2),
        reason="the check arrived in 3.12.9 and 3.13.2",
    )
    def test_a_negative_count_raises(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "history"
        path.touch()

        with pytest.raises(ValueError):
            readline.append_history_file(-1, str(path))

    @needs_append
    @pytest.mark.timing
    def test_appending_costs_the_entries_it_writes(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "history"
        fill(100_000)
        costs = []
        for count in (1_000, 100_000):

            def append(count: int = count) -> None:
                path.write_text("")
                readline.append_history_file(count, str(path))

            costs.append(best_ns(append, repeats=3))

        ratio = costs[1] / costs[0]
        assert ratio > 20, f"append 1,000 and 100,000 of 100,000 entries: {costs} ns, x{ratio:.2f}"

    @needs_append
    @pytest.mark.timing
    def test_appending_costs_the_entries_written_not_the_history(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = tmp_path / "history"
        costs = []
        for entries in (100, 100_000):
            fill(entries)

            def append_one() -> None:
                path.write_text("")
                readline.append_history_file(1, str(path))

            costs.append(best_ns(append_one, inner=20))

        ratio = costs[1] / costs[0]
        assert ratio < 3, f"append 1 of 100 and of 100,000 entries: {costs} ns, x{ratio:.2f}"

    @needs_append
    @pytest.mark.timing
    @pytest.mark.parametrize("length", [-1, 10_000_000])
    def test_a_length_makes_appending_rewrite_the_file(
        self, tmp_path: pathlib.Path, length: int
    ) -> None:
        target = tmp_path / "target"
        costs = []
        for lines in (1_000, 100_000):
            source = tmp_path / f"source{lines}"
            fill(lines)
            readline.write_history_file(str(source))
            fill(10)
            readline.set_history_length(length)
            durations = []
            for _ in range(7):
                shutil.copyfile(source, target)
                start = time.perf_counter_ns()
                readline.append_history_file(1, str(target))
                durations.append(time.perf_counter_ns() - start)
            readline.set_history_length(-1)
            costs.append(min(durations))

        ratio = costs[1] / costs[0]
        if length < 0:
            assert ratio < 3, f"no length, 1,000- and 100,000-line files: {costs} ns, x{ratio:.2f}"
        else:
            assert ratio > 10, (
                f"length set, 1,000- and 100,000-line files: {costs} ns, x{ratio:.2f}"
            )

    @pytest.mark.timing
    def test_reading_and_writing_follow_the_file(self, tmp_path: pathlib.Path) -> None:
        reads, writes = [], []
        for entries in (10_000, 100_000):
            path = str(tmp_path / f"history{entries}")
            fill(entries)
            writes.append(best_ns(lambda p=path: readline.write_history_file(p), repeats=3))

            durations = []
            for _ in range(3):
                empty_history()
                start = time.perf_counter_ns()
                readline.read_history_file(path)
                durations.append(time.perf_counter_ns() - start)
            reads.append(min(durations))

        assert reads[1] / reads[0] > 5, f"read 10,000 and 100,000 entries: {reads} ns"
        assert writes[1] / writes[0] > 5, f"write 10,000 and 100,000 entries: {writes} ns"


class TestInputAddsEachLineOnce:
    """Reading a line with `input()` | O(h) libedit: before adding the line,
    readline fetches the newest entry to compare against it."""

    def test_only_a_line_equal_to_the_newest_entry_is_skipped(self) -> None:
        keys = [b"same\r", b"same\r", b"other\r", b"same\r"]
        result = interactive("", keys, "[readline.get_history_item(n) for n in (1, 2, 3, 4)]")

        assert eval(result) == ["same", "other", "same", None]  # noqa: S307

    def test_automatic_history_can_be_turned_off(self) -> None:
        result = interactive(
            "readline.set_auto_history(False)",
            [b"one\r", b"two\r"],
            "readline.get_current_history_length()",
        )

        assert result == "0"

    @staticmethod
    def fastest_line(entries: int, auto: bool) -> int:
        setup = "\n".join(
            [
                f"readline.set_auto_history({auto})",
                f"for n in range({entries}): readline.add_history(f'old {{n}}')",
                "best = 10 ** 18",
                "_input = input",
                "def input(prompt):",
                "    global best",
                "    start = time.perf_counter_ns()",
                "    _input(prompt)",
                "    best = min(best, time.perf_counter_ns() - start)",
            ]
        )
        typed = b"".join(f"x{index}\r".encode() for index in range(40))
        return int(interactive(setup, [typed], "best", reads=40))

    @libedit_only
    @pytest.mark.timing
    def test_each_line_costs_the_history_length_on_libedit(self) -> None:
        costs = [self.fastest_line(entries, auto=True) for entries in (100, 100_000)]

        ratio = costs[1] / costs[0]
        assert ratio > 5, f"input() with 100 and 100,000 entries: {costs} ns, x{ratio:.2f}"

    @pytest.mark.timing
    def test_without_automatic_history_it_does_not(self) -> None:
        costs = [self.fastest_line(entries, auto=False) for entries in (100, 100_000)]

        ratio = costs[1] / costs[0]
        assert ratio < 3, f"auto history off, 100 and 100,000 entries: {costs} ns, x{ratio:.2f}"


COMPLETER = """
calls = []
def completer(text, state):
    calls.append((text, state, readline.get_begidx(), readline.get_endidx(),
                  readline.get_line_buffer(), readline.get_completion_type()))
    options = [w for w in WORDS if w.startswith(text)]
    return options[state] if state < len(options) else None
readline.set_completer(completer)
"""
COMPLETER += f"readline.parse_and_bind({TAB_BINDING!r})\n"


class TestCompletion:
    """Completing one word is m + 1 completer calls; `get_begidx`,
    `get_endidx`, `get_line_buffer` and `get_completion_type` describe the word
    being completed; `set_completer_delims` decides where it starts."""

    def test_the_completer_is_asked_until_it_returns_none(self) -> None:
        setup = "WORDS = ['apple', 'apricot', 'banana']" + COMPLETER
        result = interactive(setup, [b"ap\t", b"\x15\r"], "[c[:2] for c in calls]")

        states = eval(result)  # noqa: S307 - the repr of a list the child built
        assert states == [("ap", 0), ("ap", 1), ("ap", 2)]

    def test_the_completer_sees_the_word_and_where_it_is(self) -> None:
        setup = "WORDS = ['banana']" + COMPLETER
        result = interactive(setup, [b"eat ban\t", b"\r"], "calls[0]")

        text, state, begin, end, buffer, kind = eval(result)  # noqa: S307
        assert (text, state, begin, end, buffer) == ("ban", 0, 4, 7, "eat ban")
        assert kind == ord("\t")

    def test_the_delimiters_decide_where_the_word_starts(self) -> None:
        setup = "WORDS = ['eat=banana']" + COMPLETER + "readline.set_completer_delims(' ')\n"
        result = interactive(setup, [b"eat=ban\t", b"\r"], "calls[0][0]")

        assert result == "'eat=ban'"

    def test_get_completer_returns_what_was_set(self) -> None:
        def completer(text: str, state: int) -> str | None:
            return None

        readline.set_completer(completer)
        assert readline.get_completer() is completer

        readline.set_completer(None)
        assert readline.get_completer() is None

    def test_the_delimiters_round_trip(self) -> None:
        readline.set_completer_delims(" \t\n=")

        assert readline.get_completer_delims() == " \t\n="

    @libedit_only
    def test_gnu_readline_s_binding_does_not_complete_on_libedit(self) -> None:
        setup = "WORDS = ['apple']" + COMPLETER.replace(TAB_BINDING, "tab: complete")
        result = interactive(setup, [b"ap\t\r"], "(calls, line)")

        calls, line = eval(result)  # noqa: S307
        assert calls == []
        assert line == "ap\t"


HOOKS = (
    """
seen = []
readline.set_startup_hook(lambda: seen.append('startup'))
if hasattr(readline, 'set_pre_input_hook'):
    readline.set_pre_input_hook(lambda: seen.append('pre-input'))
readline.set_completion_display_matches_hook(lambda *args: seen.append('display'))
WORDS = ['apple', 'apricot']
"""
    + COMPLETER
)


class TestHooks:
    """GNU readline calls the startup and pre-input hooks once per line and
    the display hook to list matches; libedit calls none of them."""

    def test_which_hooks_run(self) -> None:
        result = interactive(HOOKS, [b"one\r", b"ap\t\t", b"\x15\r"], "seen")

        seen = eval(result)  # noqa: S307
        if LIBEDIT:
            assert seen == []
        else:
            assert seen.count("startup") == 2
            if hasattr(readline, "set_pre_input_hook"):
                assert seen.count("pre-input") == 2
            assert "display" in seen


class TestConfiguration:
    """`read_init_file` raises for a missing file; `backend` names the
    library on 3.13+, agreeing with the `__doc__` check used before it."""

    def test_a_missing_init_file_raises(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(OSError):
            readline.read_init_file(str(tmp_path / "missing"))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_backend_agrees_with_the_docstring(self) -> None:
        assert readline.backend == ("editline" if LIBEDIT else "readline")


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
    """Each block runs in its own subprocess, so the history each one builds
    cannot leak into the next, and asserts its own result."""

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
        needle = "get_current_history_length() == 6"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, "get_current_history_length() == 3", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
