"""Tests for docs/stdlib/imghdr.md.

The page prices `imghdr.what()` as at most one 32-byte read followed by the
checks in `imghdr.tests`, tried in order until one names a format: O(t) for t
checks, with each built-in check O(1) in the header's length. The read is
settled by a recording file that counts the bytes read and the `tell()` and
`seek()` calls made through it, the order by counting wrappers around every
check, and the fixed-prefix checks by a traced peak and a timing ratio over a
header far longer than 32 bytes. The module exists on Python 3.10, 3.11 and
3.12 only, so every test that touches it takes the `imghdr` fixture, which
skips from 3.13; run them with one of those interpreters. Lib/imghdr.py
differs between v3.10.19, v3.11.14 and v3.12.12 in the import-time
DeprecationWarning and the raw-JPEG branch of `test_jpeg` added in 3.11, and
otherwise only in docstrings: no bound moves.

Measurement scope:

* From an open file, `what()` makes one `read(32)`, one `tell()` and one
  `seek()` back to the starting offset, whether that offset is 0 or 5, over a
  1,000,000-byte file. From a path, it opens the file once in `'rb'` mode
  through the module's `open`, reads 32 bytes, and has closed it on return,
  on a match, on a miss and when a check raises. Given `h`, it touches
  nothing of a `file` argument whose every attribute access fails. A pipe's
  read end makes it raise `OSError`.
* Counting wrappers around every check: a PNG header calls exactly the first
  two checks, an unrecognised header all 13 in list order, and an appended
  check runs only on a header no built-in check names. The `f` a check
  receives is a file still open during the check given a path, and `None`
  given an open file or `h`.
* A 10,000,000-byte unrecognised `h` peaks under 4 KB of traced allocation
  through all 13 checks, and in a timing test costs under 3x a 32-byte one.
* All 13 built-in formats are asserted by name from a minimal header, the
  two-byte TIFF and BMP signatures on text, a JFIF, Exif and an ICC-marker
  JPEG, and the raw `FF D8 FF DB` JPEG as `None` on 3.10 and `'jpeg'` from
  3.11.
* The import warns on 3.11 and 3.12, not on 3.10, and raises
  `ModuleNotFoundError` from 3.13.
* Every fenced Python block runs in its own subprocess on 3.10 to 3.12, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* The deprecation in 3.11 and the removal in 3.13 come from the 3.12
  documentation and PEP 594.
* What a caller-supplied check, or a particular file object's `read()`,
  `tell()` and `seek()`, costs is the caller's and is not measured. The
  module's `python -m imghdr` directory walker is not covered.
"""

from __future__ import annotations

import gc
import importlib
import importlib.util
import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "imghdr.md"
EXPECTED_BLOCKS = 3

PNG = b"\x89PNG\r\n\x1a\n"

HEADERS = {
    "jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00",
    "png": PNG,
    "gif": b"GIF87a",
    "tiff": b"II*\x00",
    "rgb": b"\x01\xda\x01\x01",
    "pbm": b"P1\n",
    "pgm": b"P5 ",
    "ppm": b"P6\t",
    "rast": b"\x59\xa6\x6a\x95",
    "xbm": b"#define ",
    "bmp": b"BM",
    "webp": b"RIFF\x00\x00\x00\x00WEBP",
    "exr": b"\x76\x2f\x31\x01",
}


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1000) -> float:
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
    """Peak traced allocation while func runs, with the collector held off."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        if was_enabled:
            gc.enable()


class Recorder:
    """A file over `data` that records every read, seek and tell made on it."""

    def __init__(self, data: bytes, start: int = 0) -> None:
        self._f = io.BytesIO(data)
        self._f.seek(start)
        self.requests: list[int] = []
        self.seeks: list[int] = []
        self.tells = 0
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        self.requests.append(size)
        return self._f.read(size)

    def seek(self, pos: int, whence: int = 0) -> int:
        self.seeks.append(pos)
        return self._f.seek(pos, whence)

    def tell(self) -> int:
        self.tells += 1
        return self._f.tell()

    def close(self) -> None:
        self.closed = True


class Untouchable:
    """An object every attribute access on which fails."""

    def __getattribute__(self, name: str) -> Any:
        raise AssertionError(f"what() touched file.{name}")


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("imghdr") is not None) == (sys.version_info < (3, 13))


@pytest.fixture
def imghdr() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: imghdr was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("imghdr")


class TestAvailability:
    """`import imghdr` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("imghdr")

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="imghdr was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import imghdr"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11)), result.stderr
        if sys.version_info >= (3, 11):
            assert "DeprecationWarning" in result.stderr
            assert "imghdr" in result.stderr


class TestWhatReadsOneHeader:
    """`imghdr.what(file, h=None)` | O(t) | O(1): a path is opened, read for
    32 bytes and closed; an open file is read for 32 bytes and sought back;
    with `h`, nothing is read. A whole-file read or a lost position would
    show in the recorded calls."""

    @pytest.mark.parametrize("start", [0, 5])
    def test_an_open_file_is_read_once_and_sought_back(self, imghdr: Any, start: int) -> None:
        f = Recorder(b"\0" * start + PNG + bytes(1_000_000), start)

        assert imghdr.what(f) == "png"
        assert f.requests == [32]
        assert f.tells == 1
        assert f.seeks == [start]
        assert f._f.tell() == start

    @pytest.mark.parametrize(
        ("data", "expected"), [(PNG + bytes(1_000_000), "png"), (bytes(1_000_000), None)]
    )
    def test_a_path_is_opened_read_once_and_closed(
        self, imghdr: Any, monkeypatch: pytest.MonkeyPatch, data: bytes, expected: str | None
    ) -> None:
        opened: list[tuple[Any, str, Recorder]] = []

        def recording_open(path: Any, mode: str = "r") -> Recorder:
            f = Recorder(data)
            opened.append((path, mode, f))
            return f

        monkeypatch.setattr(imghdr, "open", recording_open, raising=False)
        assert imghdr.what("image.bin") == expected

        assert [(path, mode) for path, mode, _ in opened] == [("image.bin", "rb")]
        f = opened[0][2]
        assert f.requests == [32]
        assert f.closed

    def test_a_path_is_closed_when_a_check_raises(
        self, imghdr: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opened: list[Recorder] = []

        def recording_open(path: Any, mode: str = "r") -> Recorder:
            opened.append(Recorder(b"no match"))
            return opened[-1]

        def failing(h: bytes, f: Any) -> None:
            raise ValueError("check failed")

        monkeypatch.setattr(imghdr, "open", recording_open, raising=False)
        monkeypatch.setattr(imghdr, "tests", [failing])
        with pytest.raises(ValueError, match="check failed"):
            imghdr.what("image.bin")
        assert opened[0].closed

    def test_a_real_path_and_path_object_work(self, imghdr: Any, tmp_path: pathlib.Path) -> None:
        image = tmp_path / "photo.jpg"
        image.write_bytes(PNG + bytes(1000))

        assert imghdr.what(str(image)) == "png"
        assert imghdr.what(image) == "png"

    def test_given_h_the_file_is_not_touched(self, imghdr: Any) -> None:
        assert imghdr.what(Untouchable(), h=PNG) == "png"
        assert imghdr.what(None, h=b"nothing") is None

    def test_an_unseekable_stream_raises(self, imghdr: Any) -> None:
        read_fd, write_fd = os.pipe()
        os.write(write_fd, PNG)
        os.close(write_fd)
        with open(read_fd, "rb") as pipe, pytest.raises(OSError):
            imghdr.what(pipe)


class TestChecksRunInOrder:
    """`imghdr.tests`: the checks run in list order, the first match wins,
    and an appended one runs only on a miss. Counting wrappers tell an early
    stop from a full pass, which a result alone cannot."""

    @staticmethod
    def _counted(imghdr: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        calls: list[str] = []

        def wrap(check: Callable[[bytes, Any], Any]) -> Callable[[bytes, Any], Any]:
            def counted(h: bytes, f: Any) -> Any:
                calls.append(check.__name__)
                return check(h, f)

            return counted

        monkeypatch.setattr(imghdr, "tests", [wrap(check) for check in imghdr.tests])
        return calls

    def test_there_are_thirteen_built_in_checks(self, imghdr: Any) -> None:
        assert len(imghdr.tests) == 13

    def test_a_match_stops_the_walk(self, imghdr: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self._counted(imghdr, monkeypatch)
        assert imghdr.what(None, h=PNG) == "png"
        assert calls == ["test_jpeg", "test_png"]

    def test_a_miss_runs_every_check(self, imghdr: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        names = [check.__name__ for check in imghdr.tests]
        calls = self._counted(imghdr, monkeypatch)
        assert imghdr.what(None, h=b"not an image") is None
        assert calls == names
        assert len(calls) == 13

    def test_an_appended_check_runs_only_on_a_miss(
        self, imghdr: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[bytes] = []

        def test_last(h: bytes, f: Any) -> str:
            seen.append(h)
            return "last"

        monkeypatch.setattr(imghdr, "tests", [*imghdr.tests, test_last])
        assert imghdr.what(None, h=PNG) == "png"
        assert seen == []
        assert imghdr.what(None, h=b"\x00\x00\x01\x00") == "last"
        assert seen == [b"\x00\x00\x01\x00"]

    def test_a_check_sees_the_file_only_for_a_path(
        self, imghdr: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        received: list[Any] = []

        def test_record(h: bytes, f: Any) -> None:
            received.append(None if f is None else f.closed)

        monkeypatch.setattr(imghdr, "tests", [test_record])
        image = tmp_path / "image.bin"
        image.write_bytes(PNG)

        imghdr.what(str(image))
        imghdr.what(io.BytesIO(PNG))
        imghdr.what(None, h=PNG)

        assert received == [False, None, None]


class TestChecksAreFixedPrefix:
    """Each built-in check compares a fixed-length prefix, so a long `h`
    costs what a short one does. A copy of the header would show in the
    traced peak, and a scan of it in the elapsed time."""

    def test_a_long_header_allocates_nothing_in_proportion(self, imghdr: Any) -> None:
        h = bytes(10_000_000)
        imghdr.what(None, h=h)

        peak = peak_bytes(lambda: imghdr.what(None, h=h))
        assert peak < 4_000, f"{peak} bytes traced for a 10 MB header"

    @pytest.mark.timing
    def test_a_long_header_costs_what_a_short_one_does(self, imghdr: Any) -> None:
        short = bytes(32)
        long = bytes(10_000_000)

        short_ns = best_ns(lambda: imghdr.what(None, h=short))
        long_ns = best_ns(lambda: imghdr.what(None, h=long))
        assert long_ns < 3 * short_ns, (
            f"a 10 MB header took {long_ns:.0f}ns against {short_ns:.0f}ns for 32 bytes"
        )


class TestFormats:
    """The formats the checks name, and the signatures weak enough to
    misfire."""

    @pytest.mark.parametrize(("name", "header"), HEADERS.items())
    def test_each_built_in_format(self, imghdr: Any, name: str, header: bytes) -> None:
        assert imghdr.what(None, h=header) == name

    def test_two_byte_signatures_match_text(self, imghdr: Any) -> None:
        assert imghdr.what(None, h=b"MMORPG notes") == "tiff"
        assert imghdr.what(None, h=b"II") == "tiff"
        assert imghdr.what(None, h=b"BMW service log") == "bmp"

    def test_jpeg_needs_a_jfif_or_exif_marker(self, imghdr: Any) -> None:
        assert imghdr.what(None, h=b"\xff\xd8\xff\xe1\x00\x10Exif\x00") == "jpeg"
        assert imghdr.what(None, h=b"\xff\xd8\xff\xe2\x0c\x58ICC_PROFILE") is None

    def test_a_raw_jpeg_is_recognised_from_3_11(self, imghdr: Any) -> None:
        expected = "jpeg" if sys.version_info >= (3, 11) else None
        assert imghdr.what(None, h=b"\xff\xd8\xff\xdb\x00\x43\x00") == expected


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
        [sys.executable, "-W", "error::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result, on
    the versions that still have the module, with a DeprecationWarning made
    an error so a block that imports without silencing it fails."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import imghdr" in source for _, source in blocks)

    def test_every_block_runs(self, imghdr: Any, tmp_path: pathlib.Path) -> None:
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

    def test_the_runner_notices_a_broken_assertion(
        self, imghdr: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "stream.tell() == 0" in s)
        mutated = source.replace("stream.tell() == 0", "stream.tell() == 32", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
