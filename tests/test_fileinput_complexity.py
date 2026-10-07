"""Tests for docs/stdlib/fileinput.md.

The page prices the module a line at a time: a `FileInput` holds the line it
just read and a few counters, opens one file at a time, and pays a copy of the
remaining file list at each move to the next file. Laziness and the per-file
behaviour are settled by observation - a recording open hook and counting file
objects - so they need no tolerance; per-line space is a traced allocation
peak; the f² term is the one timing test.

Measurement scope:

* `input()` and `FileInput()` are asserted to call the open hook zero times,
  and to keep their own copy of the file list: appending to the caller's list
  afterwards adds no file. `input()` raises `RuntimeError` while the previous
  instance still has a file open, and accepts a new call once it is closed.
* The six module-level query functions are asserted to return what the global
  instance's methods return, and to raise `RuntimeError` before `input()` and
  after `close()`; `nextfile()` does too, and `close()` without an instance
  does nothing.
* One line held: iterating a 400,000-line file (11 characters per decoded
  line, with native line endings on disk) peaks under 1 MB of traced
  allocation, and so does an in-place edit of the same file, while `list()`
  of it peaks over 10 MB. The edit preserves the file's original byte size.
* `nextfile()` on the first line of a 10,000-line file makes the counting
  file object serve one `readline()` call, and `lineno()` does not count the
  skipped lines. What a buffered file reads ahead is outside that count.
* The f² term: with an open hook returning a shared empty file, 16,000 files
  cost more than 20x what 2,000 do, where a linear walk gives 8x (64x is the
  quadratic prediction). A generator that opens each name in turn, given the
  same opener, costs under 16x for the same 8x.
* `readline()` returns `''` at the end, `b''` in binary mode, instead of
  raising; `fileno()` is -1
  before the first line and after `close()`; `isstdin()` is true for `'-'`
  with `sys.stdin` replaced by a `StringIO`; `files=None` reads `sys.argv[1:]`
  and falls back to standard input when that is empty.
* In-place editing is asserted by file contents and directory listings: the
  backup is kept under the given extension and removed without one, an
  exception part way through leaves the written prefix and no backup, and an
  open hook with `inplace=True` raises `ValueError`.
* `hook_encoded()` is asserted to open nothing when called; `hook_compressed()`
  reads `.gz` and `.bz2` files and plain ones, and `mode='rb'` yields bytes.
* `mode='rU'` raises `ValueError` and `FileInput` has no `__getitem__` from
  3.11; on 3.10 `'rU'` is accepted with a `DeprecationWarning`. Text mode with
  neither `encoding` nor an open hook is observed to call `open()` with
  `encoding='locale'`.
* Every fenced Python block runs in its own subprocess and temporary working
  directory, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* O(B) per byte read is the cost of the underlying `readline()` of `io`,
  `gzip` and `bz2` file objects; it is not re-measured here, and decoding and
  decompression are not varied.
* Opening, closing and renaming a file are priced at O(1): a cost-model
  choice, since their real cost belongs to the filesystem.
* The O(f) space of the copied file list is read from Lib/fileinput.py's
  `tuple(files)`; only the copy's independence is observed.
* Standard input as a real terminal or pipe is not exercised, nor is
  `inplace=True` over standard input, which the module reads without editing.
* L is not varied here; tests/test_complexity_caveats.py shows a
  200,000-character line returned whole.
* Closing with files still to come releases the remaining list: the reverse
  of the O(f) copy already paid at construction, and not priced.
"""

from __future__ import annotations

import bz2
import fileinput
import gzip
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "fileinput.md"
EXPECTED_BLOCKS = 9


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


class CountingFile:
    """A text file stand-in that counts the readline() calls it serves."""

    def __init__(self, lines: list[str]) -> None:
        self._lines = iter(lines)
        self.reads = 0
        self.closed = False

    def readline(self) -> str:
        self.reads += 1
        return next(self._lines, "")

    def close(self) -> None:
        self.closed = True

    def fileno(self) -> int:
        return -1


class EmptyFile:
    """A file with no lines, shared by every name so opening costs nothing."""

    def readline(self) -> str:
        return ""

    def close(self) -> None:
        pass

    def fileno(self) -> int:
        return -1


@pytest.fixture(autouse=True)
def no_global_instance() -> Iterator[None]:
    fileinput.close()
    yield
    fileinput.close()


def _write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestConstructionOpensNothing:
    """`input()` and `FileInput()` are O(f): they copy the list and open nothing."""

    def test_no_file_is_opened_until_the_first_line(self) -> None:
        opened: list[str] = []

        def hook(name: Any, mode: str) -> CountingFile:
            opened.append(name)
            return CountingFile(["x\n"])

        lines = fileinput.FileInput(["a", "b"], openhook=hook)
        assert opened == []
        assert next(lines) == "x\n"
        assert opened == ["a"]

        fileinput.input(["c"], openhook=hook)
        assert opened == ["a"]

    def test_the_file_list_is_copied(self) -> None:
        names = ["a"]
        lines = fileinput.FileInput(names, openhook=lambda name, mode: CountingFile(["x\n"]))
        names.append("b")

        assert list(lines) == ["x\n"]

    def test_input_refuses_a_second_active_instance(self, tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path / "a.txt", "1\n2\n")
        first = fileinput.input(path, encoding="utf-8")
        next(first)

        with pytest.raises(RuntimeError, match="already active"):
            fileinput.input(path, encoding="utf-8")

        fileinput.close()
        assert next(fileinput.input(path, encoding="utf-8")) == "1\n"

    def test_files_none_reads_argv_and_falls_back_to_stdin(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write(tmp_path / "a.txt", "from file\n")
        monkeypatch.setattr(sys, "argv", ["prog", str(path)])
        assert list(fileinput.FileInput(encoding="utf-8")) == ["from file\n"]

        monkeypatch.setattr(sys, "argv", ["prog"])
        monkeypatch.setattr(sys, "stdin", io.StringIO("from stdin\n"))
        lines = fileinput.FileInput(encoding="utf-8")
        assert next(lines) == "from stdin\n"
        assert lines.isstdin() is True
        assert lines.filename() == "<stdin>"


class TestModuleFunctionsUseTheGlobalInstance:
    """The module-level functions ask the global instance, and raise without one."""

    NAMES = ("filename", "lineno", "filelineno", "fileno", "isfirstline", "isstdin")

    def test_they_answer_what_the_instance_answers(self, tmp_path: pathlib.Path) -> None:
        path = _write(tmp_path / "a.txt", "1\n2\n")
        state = fileinput.input(path, encoding="utf-8")
        next(state)
        next(state)

        for name in self.NAMES:
            assert getattr(fileinput, name)() == getattr(state, name)(), name
        assert fileinput.lineno() == 2

    def test_they_raise_without_an_instance(self, tmp_path: pathlib.Path) -> None:
        for name in (*self.NAMES, "nextfile"):
            with pytest.raises(RuntimeError, match="no active input"):
                getattr(fileinput, name)()

        fileinput.input(_write(tmp_path / "a.txt", "1\n"), encoding="utf-8")
        fileinput.close()

        for name in (*self.NAMES, "nextfile"):
            with pytest.raises(RuntimeError, match="no active input"):
                getattr(fileinput, name)()
        fileinput.close()  # without an instance, close() does nothing


class TestIterationHoldsOneLine:
    """Iterating, in place or not, holds one line, not the file."""

    LINES = 400_000

    def _big(self, tmp_path: pathlib.Path) -> pathlib.Path:
        return _write(tmp_path / "big.txt", "0123456789\n" * self.LINES)

    def test_iterating_peaks_far_below_the_file(self, tmp_path: pathlib.Path) -> None:
        path = self._big(tmp_path)

        def drain() -> None:
            with fileinput.FileInput(path, encoding="utf-8") as lines:
                for _ in lines:
                    pass

        def collect() -> None:
            with fileinput.FileInput(path, encoding="utf-8") as lines:
                assert len(list(lines)) == self.LINES

        streamed = peak_bytes(drain)
        collected = peak_bytes(collect)
        assert streamed < 1_000_000, f"iterating peaked at {streamed} bytes"
        assert collected > 10_000_000, f"list() peaked at only {collected} bytes"

    def test_an_in_place_edit_peaks_far_below_the_file(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = self._big(tmp_path)
        original_size = path.stat().st_size  # includes the native line endings
        monkeypatch.setattr(sys, "stdout", sys.stdout)  # restored even if the loop fails

        def edit() -> None:
            with fileinput.FileInput(path, inplace=True, encoding="utf-8") as lines:
                for line in lines:
                    sys.stdout.write(line.upper())

        streamed = peak_bytes(edit)
        assert streamed < 1_000_000, f"the in-place edit peaked at {streamed} bytes"
        assert path.stat().st_size == original_size

    def test_readline_returns_an_empty_string_at_the_end(self, tmp_path: pathlib.Path) -> None:
        lines = fileinput.FileInput(_write(tmp_path / "a.txt", "1\n"), encoding="utf-8")

        assert lines.readline() == "1\n"
        assert lines.readline() == ""
        with pytest.raises(StopIteration):
            next(lines)

        binary = tmp_path / "a.bin"
        binary.write_bytes(b"1\n")
        lines = fileinput.FileInput(binary, mode="rb")
        assert lines.readline() == b"1\n"
        assert lines.readline() == b""

    def test_binary_mode_yields_bytes(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.bin"
        path.write_bytes(b"\xff\n\x00\n")

        assert list(fileinput.FileInput(path, mode="rb")) == [b"\xff\n", b"\x00\n"]


class TestCountersAndNextfile:
    """The query methods read stored state; nextfile() skips without reading."""

    def test_counters_track_lines_within_and_across_files(self, tmp_path: pathlib.Path) -> None:
        first = _write(tmp_path / "a.txt", "1\n2\n")
        second = _write(tmp_path / "b.txt", "3\n")
        lines = fileinput.FileInput([first, second], encoding="utf-8")
        assert lines.fileno() == -1
        assert lines.filename() is None

        seen = [(line, lines.lineno(), lines.filelineno(), lines.isfirstline()) for line in lines]

        assert seen == [("1\n", 1, 1, True), ("2\n", 2, 2, False), ("3\n", 3, 1, True)]
        lines.close()
        assert lines.fileno() == -1

    def test_fileno_is_the_open_file(self, tmp_path: pathlib.Path) -> None:
        with fileinput.FileInput(_write(tmp_path / "a.txt", "1\n"), encoding="utf-8") as lines:
            next(lines)
            assert lines.fileno() >= 0
            assert lines.isstdin() is False

    def test_nextfile_does_not_read_the_rest(self) -> None:
        long = CountingFile(["header\n"] + ["body\n"] * 10_000)
        short = CountingFile(["header\n"])
        files = {"long": long, "short": short}

        lines = fileinput.FileInput(["long", "short"], openhook=lambda name, mode: files[str(name)])
        assert next(lines) == "header\n"
        lines.nextfile()

        assert long.reads == 1
        assert long.closed is True
        assert next(lines) == "header\n"
        assert lines.lineno() == 2


class TestLongFileListsAreQuadratic:
    """Each move to the next file copies the remaining list: O(f²) over f files."""

    @staticmethod
    def _fileinput(count: int) -> Callable[[], None]:
        empty = EmptyFile()
        names = ["n"] * count

        def run() -> None:
            for _ in fileinput.FileInput(names, openhook=lambda name, mode: empty):
                pass

        return run

    @staticmethod
    def _generator(count: int) -> Callable[[], None]:
        empty = EmptyFile()
        names = ["n"] * count

        def opener(name: str) -> EmptyFile:
            return empty

        def lines_of(paths: list[str]) -> Iterator[str]:
            for path in paths:
                handle = opener(path)
                yield from iter(handle.readline, "")
                handle.close()

        def run() -> None:
            for _ in lines_of(names):
                pass

        return run

    @pytest.mark.timing
    def test_eight_times_the_files_costs_far_more_than_eight_times(self) -> None:
        small = best_ns(self._fileinput(2_000))
        large = best_ns(self._fileinput(16_000))

        ratio = large / small
        assert ratio > 20, (
            f"8x the files cost x{ratio:.1f} ({small:.0f}ns to {large:.0f}ns); "
            "a linear walk gives x8, a quadratic one x64"
        )

    @pytest.mark.timing
    def test_a_generator_over_the_same_files_stays_linear(self) -> None:
        small = best_ns(self._generator(2_000))
        large = best_ns(self._generator(16_000))

        ratio = large / small
        assert ratio < 16, f"8x the files cost the generator x{ratio:.1f}"


class TestInPlaceEditing:
    """In-place editing renames to a backup, rewrites, and keeps the backup only on request."""

    def test_the_backup_is_kept_under_the_given_extension(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdout", sys.stdout)
        path = _write(tmp_path / "a.txt", "x\n")

        with fileinput.FileInput(path, inplace=True, backup=".orig", encoding="utf-8") as lines:
            for line in lines:
                print(line.upper(), end="")

        assert path.read_text(encoding="utf-8") == "X\n"
        assert (tmp_path / "a.txt.orig").read_text(encoding="utf-8") == "x\n"

    def test_without_a_backup_an_exception_loses_the_rest(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "stdout", sys.stdout)
        path = _write(tmp_path / "a.txt", "1\n2\n3\n")
        during: list[list[str]] = []

        with pytest.raises(ValueError, match="bad line"):
            with fileinput.FileInput(path, inplace=True, encoding="utf-8") as lines:
                for line in lines:
                    during.append(sorted(p.name for p in tmp_path.iterdir()))
                    if line == "2\n":
                        raise ValueError("bad line")
                    print(line, end="")

        assert during[0] == ["a.txt", "a.txt.bak"], "the edit reads from a .bak copy"
        assert path.read_text(encoding="utf-8") == "1\n"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.txt"]

    def test_an_open_hook_cannot_be_combined_with_inplace(self) -> None:
        with pytest.raises(ValueError, match="inplace"):
            fileinput.FileInput("a", inplace=True, openhook=fileinput.hook_encoded("utf-8"))


class TestOpenHooks:
    """The hooks decide how each file opens; building one opens nothing."""

    def test_hook_encoded_opens_nothing_until_called(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[Any] = []
        real_open = open

        def recording_open(*args: Any, **kwargs: Any) -> Any:
            opened.append(args[0])
            return real_open(*args, **kwargs)

        monkeypatch.setattr(fileinput, "open", recording_open, raising=False)
        hook = fileinput.hook_encoded("latin-1")
        assert opened == []

        path = tmp_path / "a.txt"
        path.write_bytes("é\n".encode("latin-1"))
        assert list(fileinput.FileInput(path, openhook=hook)) == ["é\n"]
        assert opened == [str(path)]

    def test_hook_compressed_reads_gzip_bzip2_and_plain_files(self, tmp_path: pathlib.Path) -> None:
        packed = tmp_path / "a.gz"
        packed.write_bytes(gzip.compress(b"g\n"))
        squeezed = tmp_path / "b.bz2"
        squeezed.write_bytes(bz2.compress(b"b\n"))
        plain = _write(tmp_path / "c.txt", "p\n")

        lines = fileinput.FileInput(
            [packed, squeezed, plain], openhook=fileinput.hook_compressed, encoding="utf-8"
        )
        assert list(lines) == ["g\n", "b\n", "p\n"]


class TestVersionNotes:
    """The 3.11 removals, and the locale default in text mode."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="version: 'U' modes removed in 3.11")
    def test_u_modes_and_indexing_are_gone(self) -> None:
        with pytest.raises(ValueError, match="'r' or 'rb'"):
            fileinput.FileInput("a", mode="rU")
        assert not hasattr(fileinput.FileInput, "__getitem__")

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="version: 'U' modes exist before 3.11")
    def test_u_modes_are_deprecated_on_3_10(self) -> None:
        with pytest.warns(DeprecationWarning, match="'U' mode"):
            fileinput.FileInput("a", mode="rU")

    def test_text_mode_without_an_encoding_opens_with_the_locale(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write(tmp_path / "a.txt", "1\n")
        encodings: list[Any] = []
        real_open = open

        def recording_open(*args: Any, **kwargs: Any) -> Any:
            encodings.append(kwargs.get("encoding"))
            return real_open(*args, **kwargs)

        monkeypatch.setattr(fileinput, "open", recording_open, raising=False)
        assert list(fileinput.FileInput(path)) == ["1\n"]
        assert list(fileinput.FileInput(path, encoding="utf-8")) == ["1\n"]

        assert encodings == ["locale", "utf-8"]


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
    """Each block runs in its own subprocess, so the module's global instance and
    the redirected standard output of an in-place edit cannot leak between them."""

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
        line, source = next((n, s) for n, s in _blocks() if "lines.lineno() == 2" in s)
        mutated = source.replace("lines.lineno() == 2", "lines.lineno() == 10_002", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
