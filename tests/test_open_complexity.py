"""Tests for docs/builtins/open.md.

open() is io.open, `_io_open_impl` in Modules/_io/_iomodule.c: it builds a
FileIO, then a BufferedReader, BufferedWriter or BufferedRandom unless
`buffering=0`, then a TextIOWrapper in text mode. The buffer is allocated when
the buffered object is built. Most rows are settled by observation: the type
open() returns, what a pipe still holds after open() or readline(), the file's
size on disk before and after a flush, and behaviour of the modes. That
opening and seeking do not grow with the file need a stopwatch; space is
settled by traced allocation.

Measurement scope:

* opening reads nothing: open() of the read end of an empty pipe, whose write
  end is still open, returns in binary and in text mode instead of blocking.
  Opening a 64 MiB file costs under x3 opening a 1,000-byte one, in both
  modes. Seeking 60 MiB into the large file and reading 100 bytes costs under
  x3 seeking to 0 and reading 100 bytes.
* the buffer: tracemalloc's peak for open() of a small file with
  `buffering=4096` is under 64 KiB, and with `buffering=8 MiB` between 8 MiB
  and 8 MiB + 64 KiB, so the O(b) is the buffer `buffering` sets; the default
  is not varied. read(8 MiB) on a 1,000-byte file peaks at 8 MiB or more, in
  binary and in text mode, which is the O(size) of `read(size)`.
* iterating a 2.2 MB text file of 100,000 lines, opened outside the
  measurement, peaks under 100 KB, while readlines() on it peaks over 2 MB.
  These run serially, since xdist's I/O thread allocates while tracemalloc is
  tracing.
* a raw readline(): on a pipe holding two lines, readline() on a
  `buffering=0` file leaves the second line in the pipe, where a buffered one
  takes it into its buffer. That it reads one byte per system call is read
  from `_io__IOBase_readline_impl` in Modules/_io/iobase.c, which reads one
  byte at a time from an object without peek(); a timing test shows
  readline() of a 100,000-byte line costs more than x20 unbuffered what it
  costs buffered.
* buffering: 100 one-byte writes to a buffered binary file leave it empty on
  disk until flush(); an unbuffered binary write is on disk at once; a
  line-buffered text file is empty after a write without a newline and holds
  everything after one with a newline; truncate(), seek() and close() write
  out pending bytes; `buffering=0` in text mode raises ValueError.
* modes: 'w' truncates, 'a' writes at the end after seek(0), 'x' raises
  FileExistsError on an existing file, and the returned types are FileIO,
  BufferedReader, BufferedWriter, BufferedRandom and TextIOWrapper.
* encoding: with `-X utf8=0` the default text encoding equals
  locale.getencoding() on every version; on 3.15+, with PYTHONUTF8 unset and
  a C.UTF-8 locale, UTF-8 mode is on and the default is 'utf-8'.
* text positioning: a tell() cookie returns to the same line, a nonzero
  relative seek raises, and tell() inside a for loop raises OSError.
* every fenced block runs in its own subprocess and working directory, and a
  mutated assertion in one is asserted to fail.

Not settled here:

* The filesystem's own costs - path resolution, truncation of a large file by
  'w', what a system call costs on a given device - belong to the operating
  system; the page names them as unpriced.
* The O(c) of text tell() is the io page's row and is measured in
  tests/test_io_complexity.py; here only its behaviour is checked. The O(b)
  flush that text tell() and seek() and the amortized reads and writes can
  pay is read from Modules/_io/textio.c and Modules/_io/bufferedio.c; only
  seek() and truncate() flushing is observed, in binary mode.
* Not varied: encodings other than UTF-8, newline translation (files whose
  byte counts are asserted are written with `newline="\\n"`), and files on
  network or pseudo filesystems, where open() and seek() can cost more.
"""

from __future__ import annotations

import io
import locale
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "open.md"
EXPECTED_BLOCKS = 11
MIB = 1 << 20


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


@pytest.fixture(scope="module")
def small_and_large(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:
    directory = tmp_path_factory.mktemp("sizes")
    small = directory / "small.bin"
    small.write_bytes(b"x" * 1_000)
    large = directory / "large.bin"
    with open(large, "wb") as f:
        for _ in range(64):
            f.write(b"y" * MIB)
    return str(small), str(large)


class TestOpeningReadsNothing:
    """`open(...)` is O(1): it does not read the file, so its cost does not
    grow with the file's size, and seeking is O(1) however far it moves."""

    @pytest.mark.timing
    @pytest.mark.parametrize("mode", ["rb", "r"])
    def test_opening_does_not_grow_with_the_file(
        self, small_and_large: tuple[str, str], mode: str
    ) -> None:
        small, large = small_and_large
        encoding = None if "b" in mode else "utf-8"

        def opener(path: str) -> Callable[[], None]:
            return lambda: open(path, mode, encoding=encoding).close()

        small_ns = best_ns(opener(small), inner=100)
        large_ns = best_ns(opener(large), inner=100)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"open({mode!r}) of 64 MiB cost x{ratio:.2f} open() of 1,000 bytes "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns)"
        )

    @pytest.mark.timing
    def test_seeking_far_costs_the_same_as_seeking_near(
        self, small_and_large: tuple[str, str]
    ) -> None:
        _, large = small_and_large

        def seek_and_read(position: int) -> Callable[[], None]:
            def run() -> None:
                with open(large, "rb") as f:
                    f.seek(position)
                    assert len(f.read(100)) == 100

            return run

        near_ns = best_ns(seek_and_read(0), inner=100)
        far_ns = best_ns(seek_and_read(60 * MIB), inner=100)

        ratio = far_ns / near_ns
        assert ratio < 3, f"seek 60 MiB cost x{ratio:.2f} seek 0 ({near_ns:.0f}ns)"


@pytest.mark.serial
class TestSpace:
    """`open()` allocates O(b), the buffer `buffering` sets; iterating holds
    one line, `readlines()` the whole file."""

    def test_the_buffer_is_what_buffering_asks_for(self, small_and_large: tuple[str, str]) -> None:
        small, _ = small_and_large

        tiny = peak_bytes(lambda: open(small, "rb", buffering=4096).close())
        huge = peak_bytes(lambda: open(small, "rb", buffering=8 * MIB).close())

        assert tiny < 64 * 1024, tiny
        assert 8 * MIB <= huge < 8 * MIB + 64 * 1024, huge

    @pytest.mark.parametrize("mode", ["rb", "r"])
    def test_read_size_allocates_for_the_size_asked(
        self, small_and_large: tuple[str, str], mode: str
    ) -> None:
        small, _ = small_and_large
        with open(small, mode, encoding=None if "b" in mode else "utf-8") as f:
            peak = peak_bytes(lambda: f.read(8 * MIB))
        assert peak >= 8 * MIB, peak

    def test_iterating_holds_one_line_and_readlines_holds_all(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "lines.txt"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for i in range(100_000):
                f.write(f"line {i:08d} of text\n")
        assert path.stat().st_size == 2_200_000

        with open(path, encoding="utf-8") as f:

            def iterate() -> None:
                f.seek(0)
                for _ in f:
                    pass

            iterate()
            lazy = peak_bytes(iterate)

            def everything() -> None:
                f.seek(0)
                assert len(f.readlines()) == 100_000

            eager = peak_bytes(everything)

        assert lazy < 100_000, lazy
        assert eager > 2_000_000, eager


class TestPipes:
    """Opening reads nothing, and a raw `readline()` reads the line and no
    further, observed on a pipe."""

    def test_opening_an_empty_pipe_does_not_block(self) -> None:
        code = (
            "import os\n"
            "r, w = os.pipe()\n"
            "open(r, 'rb', closefd=False).close()\n"
            "open(r, 'r', encoding='utf-8', closefd=False).close()\n"
            "print('opened')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=30, check=True
        )
        assert result.stdout.strip() == "opened"

    @pytest.mark.parametrize(("buffering", "rest"), [(0, b"def\n"), (-1, b"")])
    def test_a_raw_readline_leaves_the_rest_in_the_pipe(self, buffering: int, rest: bytes) -> None:
        r, w = os.pipe()
        os.write(w, b"abc\ndef\n")
        os.close(w)
        with open(r, "rb", buffering=buffering) as f:
            assert f.readline() == b"abc\n"
            assert os.read(f.fileno(), 100) == rest


class TestUnbufferedReadline:
    """`f.readline()` on a `buffering=0` file makes one system call per
    byte."""

    @pytest.mark.timing
    def test_a_raw_readline_is_far_slower_than_a_buffered_one(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "long.bin"
        path.write_bytes(b"z" * 100_000 + b"\n")

        def readline(buffering: int) -> Callable[[], None]:
            def run() -> None:
                with open(path, "rb", buffering=buffering) as f:
                    assert len(f.readline()) == 100_001

            return run

        buffered_ns = best_ns(readline(-1), repeats=5)
        raw_ns = best_ns(readline(0), repeats=3)

        ratio = raw_ns / buffered_ns
        assert ratio > 20, (
            f"an unbuffered readline() of 100,000 bytes cost x{ratio:.1f} a buffered one "
            f"({buffered_ns:.0f}ns to {raw_ns:.0f}ns)"
        )


class TestBuffering:
    """`f.write(data)` reaches the file when a write no longer fits in the
    buffer, or on `flush()` or `close()`; `buffering=0` is binary only; `buffering=1` flushes text at
    each newline."""

    def test_small_writes_wait_for_flush(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "out.bin"
        with open(path, "wb") as f:
            for _ in range(100):
                f.write(b"x")
            assert path.stat().st_size == 0
            f.flush()
            assert path.stat().st_size == 100

    def test_close_writes_out_the_buffer(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "out.txt"
        f = open(path, "w", encoding="utf-8")
        f.write("pending")
        assert path.stat().st_size == 0
        f.close()
        assert path.read_text(encoding="utf-8") == "pending"

    @pytest.mark.parametrize("operation", ["seek", "truncate"])
    def test_seek_and_truncate_flush_first(self, tmp_path: pathlib.Path, operation: str) -> None:
        path = tmp_path / "out.bin"
        with open(path, "wb") as f:
            f.write(b"abc")
            assert path.stat().st_size == 0
            if operation == "seek":
                f.seek(0)
            else:
                f.truncate()
            assert path.stat().st_size == 3

    def test_an_unbuffered_write_is_on_disk_at_once(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "out.bin"
        with open(path, "wb", buffering=0) as f:
            assert isinstance(f, io.FileIO)
            f.write(b"x")
            assert path.stat().st_size == 1

    def test_line_buffering_flushes_at_a_newline(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "app.log"
        with open(path, "w", buffering=1, encoding="utf-8", newline="\n") as f:
            f.write("starting")
            assert path.stat().st_size == 0
            f.write(" done\n")
            assert path.stat().st_size == len("starting done\n")

    def test_unbuffered_text_is_refused(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(ValueError, match="unbuffered text"):
            open(tmp_path / "x.txt", "w", buffering=0)


class TestModes:
    """What each mode returns, and how 'w', 'a' and 'x' treat an existing
    file."""

    @pytest.mark.parametrize(
        ("mode", "kind"),
        [
            ("r", io.TextIOWrapper),
            ("rb", io.BufferedReader),
            ("wb", io.BufferedWriter),
            ("ab", io.BufferedWriter),
            ("r+b", io.BufferedRandom),
        ],
    )
    def test_the_returned_type(self, tmp_path: pathlib.Path, mode: str, kind: type) -> None:
        path = tmp_path / "f"
        path.write_bytes(b"data")
        with open(path, mode, encoding=None if "b" in mode else "utf-8") as f:
            assert type(f) is kind

    def test_w_truncates_a_and_x(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "f.txt"
        path.write_text("old contents", encoding="utf-8")

        with open(path, "w", encoding="utf-8") as f:
            assert path.stat().st_size == 0
            f.write("abc")
        with open(path, "a", encoding="utf-8") as f:
            f.seek(0)
            f.write("Z")
        assert path.read_text(encoding="utf-8") == "abcZ"

        with pytest.raises(FileExistsError):
            open(path, "x")


class TestEncoding:
    """Text mode's default encoding is UTF-8 on 3.15+, and the locale's
    encoding earlier unless UTF-8 mode is on."""

    @staticmethod
    def _run(*args: str, env: dict[str, str]) -> str:
        code = (
            "import locale, sys\n"
            "f = open(sys.argv[1])\n"
            "print(sys.flags.utf8_mode, f.encoding, locale.getencoding())\n"
            "f.close()\n"
        )
        result = subprocess.run(
            [sys.executable, *args, "-c", code, __file__],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=True,
        )
        return result.stdout.strip()

    @staticmethod
    def _env() -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
        env["LC_ALL"] = "C.UTF-8"
        return env

    def test_without_utf8_mode_the_default_is_the_locale_encoding(self) -> None:
        mode, encoding, locale_encoding = self._run("-X", "utf8=0", env=self._env()).split()
        assert mode == "0"
        assert encoding == locale_encoding

    @pytest.mark.skipif(sys.version_info < (3, 15), reason="version: UTF-8 default from 3.15")
    def test_utf8_is_the_default_from_3_15(self) -> None:
        mode, encoding, _ = self._run(env=self._env()).split()
        assert mode == "1"
        assert encoding == "utf-8"

    def test_the_in_process_default_follows_utf8_mode(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "f.txt"
        path.write_bytes(b"")
        with open(path) as f:
            expected = "utf-8" if sys.flags.utf8_mode else locale.getencoding()
            assert f.encoding == expected


class TestTextPositions:
    """`f.tell()` in text mode is a cookie `seek()` takes back; nonzero
    relative seeks and tell() inside a for loop are refused."""

    def test_a_cookie_returns_to_the_line(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "t.txt"
        path.write_text("naïve\ncafé\nüber\n", encoding="utf-8")
        with open(path, encoding="utf-8") as f:
            f.readline()
            cookie = f.tell()
            assert f.readline() == "café\n"
            f.seek(cookie)
            assert f.readline() == "café\n"
            with pytest.raises(OSError, match="nonzero"):
                f.seek(3, os.SEEK_CUR)

    def test_tell_inside_a_for_loop_raises(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "t.txt"
        path.write_text("a\nb\n", encoding="utf-8")
        with open(path, encoding="utf-8") as f, pytest.raises(OSError):
            for _ in f:
                f.tell()


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
    """Each block runs in its own subprocess and asserts its own results."""

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
        line, source = next((n, s) for n, s in _blocks() if "== 0  # Nothing written" in s)
        mutated = source.replace("== 0  # Nothing written", "== 100  # Nothing written", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
