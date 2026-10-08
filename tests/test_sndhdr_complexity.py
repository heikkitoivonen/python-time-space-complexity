"""Tests for docs/stdlib/sndhdr.md.

The page prices `sndhdr.what()` as one 512-byte read followed by the functions
in `sndhdr.tests`, tried in order until one recognises the format, plus a walk
over the chunk headers of a WAV or AIFF file: O(t + c) time and O(1) space.
The reads are settled by a counting `io.FileIO` put in place of the module's
`open`, which counts every byte read through it; the order by counting
wrappers around every function; the space by traced peaks over files whose
chunk count grows a thousandfold. The module exists on Python 3.10, 3.11 and
3.12 only, so every test that touches it takes the `sndhdr` fixture, which
skips from 3.13; run them with one of those interpreters. Lib/sndhdr.py
differs between v3.10.19, v3.11.14 and v3.12.12 in the import-time
DeprecationWarning, a warning filter around its `import aifc`, and docstrings;
Lib/wave.py reads the `WAVE_FORMAT_EXTENSIBLE` layout from v3.12.0 and not in
v3.10.19 or v3.11.14.

Measurement scope:

* AU, HCOM, VOC, SNDT, SNDR and 8SVX files padded to 1,000,000 bytes, and an
  unrecognised one, are each read for exactly 512 bytes in one read, and the
  file is closed on return. A `pathlib.Path` and a bytes path work; an open
  file raises `TypeError` and a missing path `FileNotFoundError`.
* A WAV and an AIFF file of 4,000,000 16-bit frames are read for under 2,000
  bytes. With 10,000 padding chunks of four-byte bodies, a WAV file is read
  for over 80,000 bytes when they precede the `data` chunk and under 2,000
  when they follow it; an AIFF file is read for over 80,000 bytes with them
  on either side of `SSND`. The traced peak at 100,000 padding chunks is under twice
  the peak at 100, for both formats.
* Counting wrappers around the eight built-in functions: an AU file calls
  exactly the first two, an unrecognised file all eight in list order, and an
  appended function runs only on a file no built-in function recognises. The
  function receives the first 512 bytes, or the whole of a 104-byte file,
  and the open file, not yet closed. A truthy tuple it returns becomes a
  `SndHeaders`.
* Every built-in format is asserted by its `filetype` from a minimal file,
  and `what()` and `whathdr()` return equal results. `SndHeaders._fields`
  is asserted in order, and a 16-bit mono 8 kHz AU file in full. A
  floating-point WAV and an AIFC file compressed as `fl32` both return
  `None`, and so does a WAV file whose first chunk is a 28-byte `JUNK`
  chunk, while the same file without it is `'wav'`. A file holding only
  `.snd` raises `IndexError`. A `WAVE_FORMAT_EXTENSIBLE` WAV is `'wav'` from
  3.12 and `None` before; only the PCM subformat is built. Two zero bytes
  and a little-endian rate of 8,000 in front of text are `'sndr'`.
* The import warns on 3.11 and 3.12, not on 3.10, and raises
  `ModuleNotFoundError` from 3.13.
* Every fenced Python block that imports the module runs in its own
  subprocess on 3.10 to 3.12, the one that does not runs on every version,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The deprecation in 3.11 and the removal in 3.13, with `aifc` and `sunau`,
  come from the 3.12 documentation and PEP 594.
* That time follows the reads is read from Lib/wave.py, Lib/aifc.py and
  Lib/chunk.py, which read an eight-byte header per chunk and seek past the
  body of each chunk they skip; elapsed time is not measured. Only padding chunks with four-byte
  bodies are varied, and every file is a regular file on disk.
* The marker list `aifc` keeps from an AIFF `MARK` chunk is left out of the
  bounds; no file here has one. A caller-supplied function's cost is the
  caller's and is not measured.
* `SndHeaders` and the module's helpers (`get_long_be`, `get_long_le`,
  `get_short_be`, `get_short_le`, the eight `test_*` functions by name, and
  the `test` and `testall` command-line routines) are outside the official
  API inventory, so the audit lists them under needs-classification on 3.10
  to 3.12. The page documents `SndHeaders` and reaches the `test_*` functions
  through `sndhdr.tests`; the rest are not covered.
"""

from __future__ import annotations

import gc
import importlib
import importlib.util
import io
import os
import pathlib
import re
import struct
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sndhdr.md"
EXPECTED_BLOCKS = 4

# An 80-bit IEEE extended 8,000, the sample rate field of an AIFF COMM chunk.
RATE_8000 = b"\x40\x0b\xfa\x00\x00\x00\x00\x00\x00\x00"
PADDING_CHUNK = b"junk" + struct.pack("<I", 4) + b"\0\0\0\0"
AIFF_PADDING_CHUNK = b"APPL" + struct.pack(">L", 4) + b"abcd"

BUILT_IN = [
    "test_aifc",
    "test_au",
    "test_hcom",
    "test_voc",
    "test_wav",
    "test_8svx",
    "test_sndt",
    "test_sndr",
]


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


def wav_bytes(
    frames: int = 10,
    before: int = 0,
    after: int = 0,
    format_tag: int = 1,
    extra: bytes = b"",
) -> bytes:
    """A mono 16-bit 8 kHz WAV file with padding chunks around `data`."""
    fmt = struct.pack("<HHIIHH", format_tag, 1, 8000, 16000, 2, 16) + extra
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + PADDING_CHUNK * before
    body += b"data" + struct.pack("<I", frames * 2) + bytes(frames * 2) + PADDING_CHUNK * after
    return b"RIFF" + struct.pack("<I", len(body)) + body


def aiff_bytes(
    frames: int = 10, before: int = 0, after: int = 0, compression: bytes | None = None
) -> bytes:
    """A mono 16-bit 8 kHz AIFF file, or AIFC with `compression`, with
    padding chunks around `SSND`."""
    comm = struct.pack(">hLh", 1, frames, 16) + RATE_8000
    form = b"AIFF"
    if compression is not None:
        form = b"AIFC"
        comm += compression + b"\x00\x00"
    body = form + b"COMM" + struct.pack(">L", len(comm)) + comm + AIFF_PADDING_CHUNK * before
    ssnd = bytes(8 + frames * 2)
    body += b"SSND" + struct.pack(">L", len(ssnd)) + ssnd + AIFF_PADDING_CHUNK * after
    return b"FORM" + struct.pack(">L", len(body)) + body


def au_bytes(data: int = 16000) -> bytes:
    """A mono 16-bit linear 8 kHz AU file."""
    return struct.pack(">4s5I", b".snd", 24, data, 3, 8000, 1) + bytes(data)


HEADER_ONLY = {
    "au": au_bytes(),
    "hcom": bytes(65) + b"FSSD" + bytes(59) + b"HCOM" + bytes(12) + struct.pack(">I", 2),
    # Block type 1 at offset 26, rate code 256 - 0x9c four bytes later.
    "voc": b"Creative Voice File\x1a" + struct.pack("<H", 26) + bytes(4) + b"\x01\0\0\0\x9c",
    "sndt": b"SOUND" + bytes(3) + struct.pack("<I", 100) + bytes(8) + struct.pack("<H", 8000),
    "sndr": b"\0\0" + struct.pack("<H", 8000),
    "8svx": b"FORM" + struct.pack(">L", 4) + b"8SVX",
}

FORMATS = {
    **HEADER_ONLY,
    "aiff": aiff_bytes(),
    "aifc": aiff_bytes(compression=b"NONE"),
    "wav": wav_bytes(),
}


class CountingFileIO(io.FileIO):
    """An unbuffered file that counts the bytes and calls read through it."""

    def __init__(self, name: Any) -> None:
        super().__init__(name, "r")
        self.bytes_read = 0
        self.reads = 0

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        assert data is not None
        self.bytes_read += len(data)
        self.reads += 1
        return data

    def readinto(self, buffer: Any) -> int:
        count = super().readinto(buffer)
        assert count is not None
        self.bytes_read += count
        self.reads += 1
        return count


@pytest.fixture
def sndhdr() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: sndhdr was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("sndhdr")


@pytest.fixture
def opened(sndhdr: Any, monkeypatch: pytest.MonkeyPatch) -> list[CountingFileIO]:
    """Every file `sndhdr` opens from now on, counting what is read from it."""
    files: list[CountingFileIO] = []

    def counting_open(name: Any, mode: str = "r") -> CountingFileIO:
        assert mode == "rb"
        files.append(CountingFileIO(name))
        return files[-1]

    monkeypatch.setattr(sndhdr, "open", counting_open, raising=False)
    return files


def write(directory: pathlib.Path, name: str, data: bytes) -> pathlib.Path:
    path = directory / name
    path.write_bytes(data)
    return path


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("sndhdr") is not None) == (sys.version_info < (3, 13))


class TestAvailability:
    """`import sndhdr` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("sndhdr")

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="sndhdr was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import sndhdr"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11)), result.stderr
        if sys.version_info >= (3, 11):
            assert "DeprecationWarning" in result.stderr
            assert "sndhdr" in result.stderr


class TestWhatReadsTheHeader:
    """`sndhdr.what(filename)` | O(t + c) | O(1): a format decided by its
    header costs one 512-byte read however long the file is. A read of the
    whole file, or of a second block, would show in the byte count."""

    @pytest.mark.parametrize("name", HEADER_ONLY)
    def test_a_header_format_is_read_for_512_bytes(
        self, sndhdr: Any, opened: list[CountingFileIO], tmp_path: pathlib.Path, name: str
    ) -> None:
        data = HEADER_ONLY[name]
        path = write(tmp_path, "sound", data + bytes(1_000_000 - len(data)))

        assert sndhdr.what(str(path)).filetype == name
        assert len(opened) == 1
        assert (opened[0].bytes_read, opened[0].reads) == (512, 1)
        assert opened[0].closed

    def test_an_unrecognised_file_is_read_for_512_bytes(
        self, sndhdr: Any, opened: list[CountingFileIO], tmp_path: pathlib.Path
    ) -> None:
        path = write(tmp_path, "notes.txt", b"x" * 1_000_000)

        assert sndhdr.what(str(path)) is None
        assert (opened[0].bytes_read, opened[0].reads) == (512, 1)
        assert opened[0].closed

    def test_it_takes_a_path(self, sndhdr: Any, tmp_path: pathlib.Path) -> None:
        path = write(tmp_path, "speech.au", au_bytes())

        assert sndhdr.what(path).filetype == "au"
        assert sndhdr.what(os.fsencode(path)).filetype == "au"
        with open(path, "rb") as f, pytest.raises(TypeError):
            sndhdr.what(f)
        with pytest.raises(FileNotFoundError):
            sndhdr.what(str(tmp_path / "missing.au"))


class TestWavAndAiffWalkTheirChunks:
    """`c` is the chunk headers read: those up to `data` in a WAV file, every
    chunk in an AIFF file. `wave` stops at `data` and `aifc` seeks past the
    samples, so the audio's length does not enter the cost, and nothing is
    kept per chunk."""

    @pytest.mark.parametrize("build", [wav_bytes, aiff_bytes])
    def test_the_audio_is_not_read(
        self,
        sndhdr: Any,
        opened: list[CountingFileIO],
        tmp_path: pathlib.Path,
        build: Callable[..., bytes],
    ) -> None:
        path = write(tmp_path, "long", build(frames=4_000_000))

        assert sndhdr.what(str(path)).nframes == 4_000_000
        assert opened[0].bytes_read < 2_000, f"{opened[0].bytes_read} bytes read of 8 MB"

    def test_a_wav_file_is_walked_up_to_data(
        self, sndhdr: Any, opened: list[CountingFileIO], tmp_path: pathlib.Path
    ) -> None:
        ahead = write(tmp_path, "ahead.wav", wav_bytes(before=10_000))
        behind = write(tmp_path, "behind.wav", wav_bytes(after=10_000))

        assert sndhdr.what(str(ahead)).filetype == "wav"
        assert sndhdr.what(str(behind)).filetype == "wav"
        assert opened[0].bytes_read > 80_000, "chunks ahead of data were not read"
        assert opened[1].bytes_read < 2_000, "chunks after data were read"

    @pytest.mark.parametrize("side", ["before", "after"])
    def test_an_aiff_file_is_walked_to_the_end(
        self, sndhdr: Any, opened: list[CountingFileIO], tmp_path: pathlib.Path, side: str
    ) -> None:
        data = aiff_bytes(before=10_000) if side == "before" else aiff_bytes(after=10_000)
        path = write(tmp_path, "padded.aiff", data)

        assert sndhdr.what(str(path)).filetype == "aiff"
        assert opened[0].bytes_read > 80_000, f"10,000 chunks {side} SSND were not read"

    @pytest.mark.parametrize("build", [wav_bytes, aiff_bytes])
    def test_space_does_not_follow_the_chunks(
        self, sndhdr: Any, tmp_path: pathlib.Path, build: Callable[..., bytes]
    ) -> None:
        few = str(write(tmp_path, "few", build(before=100)))
        many = str(write(tmp_path, "many", build(before=100_000)))
        sndhdr.what(few)
        sndhdr.what(many)

        few_peak = peak_bytes(lambda: sndhdr.what(few))
        many_peak = peak_bytes(lambda: sndhdr.what(many))
        assert many_peak < 2 * few_peak, (
            f"100,000 chunks peaked at {many_peak} bytes against {few_peak} for 100"
        )


class TestTestsRunInOrder:
    """`sndhdr.tests` | O(1) | O(1): the functions are tried in order and the
    first match wins, so an appended function costs only files no earlier one
    recognises."""

    @staticmethod
    def _counted(sndhdr: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        calls: list[str] = []

        def wrap(test: Callable[[bytes, Any], Any]) -> Callable[[bytes, Any], Any]:
            def counted(h: bytes, f: Any) -> Any:
                calls.append(test.__name__)
                return test(h, f)

            return counted

        monkeypatch.setattr(sndhdr, "tests", [wrap(test) for test in sndhdr.tests])
        return calls

    def test_there_are_eight_built_in_functions(self, sndhdr: Any) -> None:
        assert [test.__name__ for test in sndhdr.tests] == BUILT_IN

    def test_a_match_stops_the_walk(
        self, sndhdr: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        calls = self._counted(sndhdr, monkeypatch)
        assert sndhdr.what(str(write(tmp_path, "a.au", au_bytes()))).filetype == "au"
        assert calls == ["test_aifc", "test_au"]

    def test_a_miss_runs_every_function(
        self, sndhdr: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        calls = self._counted(sndhdr, monkeypatch)
        assert sndhdr.what(str(write(tmp_path, "t.txt", b"plain text"))) is None
        assert calls == BUILT_IN

    def test_an_appended_function_runs_only_on_a_miss(
        self, sndhdr: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
    ) -> None:
        seen: list[tuple[bytes, str, bool]] = []

        def test_last(h: bytes, f: Any) -> tuple[str, int, int, int, int]:
            seen.append((h, f.name, f.closed))
            return ("flac", 0, 0, -1, 0)

        monkeypatch.setattr(sndhdr, "tests", [*sndhdr.tests, test_last])
        flac = str(write(tmp_path, "song.flac", b"fLaC" + bytes(1000)))
        au = str(write(tmp_path, "speech.au", au_bytes()))

        result = sndhdr.what(flac)
        assert type(result) is sndhdr.SndHeaders
        assert result == ("flac", 0, 0, -1, 0)
        assert sndhdr.what(au).filetype == "au"
        assert seen == [(b"fLaC" + bytes(508), flac, False)]

        short = str(write(tmp_path, "short.flac", b"fLaC" + bytes(100)))
        assert sndhdr.what(short).filetype == "flac"
        assert seen[-1] == (b"fLaC" + bytes(100), short, False)


class TestFormats:
    """The formats the built-in functions name, the `SndHeaders` they return,
    and the files the readers behind WAV and AIFF reject."""

    @pytest.mark.parametrize("name", FORMATS)
    def test_each_built_in_format(self, sndhdr: Any, tmp_path: pathlib.Path, name: str) -> None:
        path = str(write(tmp_path, "sound", FORMATS[name]))

        result = sndhdr.what(path)
        assert type(result) is sndhdr.SndHeaders
        assert result.filetype == name
        assert sndhdr.whathdr(path) == result

    def test_the_fields_and_their_order(self, sndhdr: Any, tmp_path: pathlib.Path) -> None:
        assert sndhdr.SndHeaders._fields == (
            "filetype",
            "framerate",
            "nchannels",
            "nframes",
            "sampwidth",
        )
        info = sndhdr.what(str(write(tmp_path, "speech.au", au_bytes())))
        assert info == ("au", 8000, 1, 8000, 16)

    def test_a_file_the_reader_rejects_is_none(self, sndhdr: Any, tmp_path: pathlib.Path) -> None:
        float_wav = write(tmp_path, "float.wav", wav_bytes(format_tag=3))
        fl32 = write(tmp_path, "float.aifc", aiff_bytes(compression=b"fl32"))

        assert sndhdr.what(str(float_wav)) is None
        assert sndhdr.what(str(fl32)) is None

    def test_a_wav_led_by_another_chunk_is_none(self, sndhdr: Any, tmp_path: pathlib.Path) -> None:
        fmt_first = wav_bytes()
        junk = b"JUNK" + struct.pack("<I", 28) + bytes(28)
        body = b"WAVE" + junk + fmt_first[12:]
        junk_first = b"RIFF" + struct.pack("<I", len(body)) + body

        assert sndhdr.what(str(write(tmp_path, "fmt.wav", fmt_first))).filetype == "wav"
        assert sndhdr.what(str(write(tmp_path, "junk.wav", junk_first))) is None

    def test_a_truncated_header_can_raise(self, sndhdr: Any, tmp_path: pathlib.Path) -> None:
        with pytest.raises(IndexError):
            sndhdr.what(str(write(tmp_path, "short.au", b".snd")))

    def test_an_extensible_wav_is_recognised_from_3_12(
        self, sndhdr: Any, tmp_path: pathlib.Path
    ) -> None:
        pcm_guid = b"\x01\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
        extra = struct.pack("<HHI", 22, 16, 4) + pcm_guid
        path = write(tmp_path, "extensible.wav", wav_bytes(format_tag=0xFFFE, extra=extra))

        result = sndhdr.what(str(path))
        if sys.version_info >= (3, 12):
            assert result == ("wav", 8000, 1, 10, 16)
        else:
            assert result is None

    def test_sndr_is_two_zero_bytes_and_a_rate(self, sndhdr: Any, tmp_path: pathlib.Path) -> None:
        path = write(tmp_path, "notes.txt", b"\0\0" + struct.pack("<H", 8000) + b"meeting notes")
        assert sndhdr.what(str(path)).filetype == "sndr"


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


def _run_all(blocks: list[tuple[int, str]], tmp_path: pathlib.Path) -> None:
    failures: list[str] = []
    for line, source in blocks:
        workdir = tmp_path / f"block{line}"
        workdir.mkdir()
        result = _run_block(source, workdir)
        if result.returncode != 0:
            failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")
    assert not failures, "\n\n".join(failures)


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result, with
    a DeprecationWarning made an error so a block that imports the module
    without silencing it fails. Blocks that import `sndhdr` run on the
    versions that still have it; the one that does not runs everywhere."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert sum("import sndhdr" in source for _, source in blocks) == EXPECTED_BLOCKS - 1

    def test_every_sndhdr_block_runs(self, sndhdr: Any, tmp_path: pathlib.Path) -> None:
        blocks = [(n, s) for n, s in _blocks() if "import sndhdr" in s]
        assert len(blocks) == EXPECTED_BLOCKS - 1
        _run_all(blocks, tmp_path)

    def test_the_block_without_sndhdr_runs_everywhere(self, tmp_path: pathlib.Path) -> None:
        blocks = [(n, s) for n, s in _blocks() if "import sndhdr" not in s]
        assert len(blocks) == 1
        _run_all(blocks, tmp_path)

    def test_the_runner_notices_a_broken_assertion(
        self, sndhdr: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "info.nframes == 8000" in s)
        mutated = source.replace("info.nframes == 8000", "info.nframes == 8001", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
        (tmp_path / "all").mkdir()
        with pytest.raises(AssertionError, match=f"{PAGE.name}:{line}"):
            _run_all([(line, mutated)], tmp_path / "all")
