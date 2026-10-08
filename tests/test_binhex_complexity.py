"""Tests for docs/stdlib/binhex.md.

The page prices both functions as one streamed pass over the file: O(n) time
in the bytes read plus the bytes written, and O(1) auxiliary space. Counting
the bytes that reach `binascii.crc_hqx`, which every byte of file data passes
through on each side, shows the file is processed once; that the rest of the
work is linear too is read from Lib/binhex.py, whose loops move fixed-size
chunks. Space is settled by `tracemalloc` peaks that stay under 2x while the
file grows sixteenfold. The argument and error rows
are settled by observation. The module exists on Python 3.10 only, so every
test that touches it takes the `binhex` fixture, which skips from 3.11; run
them with a 3.10 interpreter.

Measurement scope:

* Encoding and decoding 8 MiB and 128 MiB files of one repeated byte and of
  the 256 byte values in turn: the CRC sees the file's size, plus less than
  1 KiB of header and checksum, on each side, and the decoded file equals the
  original. Each function's traced peak at 128 MiB is under 2x its peak at
  8 MiB, against 16x for a peak that followed the file and 4x for one that
  followed its square root. On 3.10.22 the
  peaks are about 0.5 MB and 0.8 MB, except `hexbin()` on the repeated byte,
  which levels off at about 22 MB from 64 MiB to 512 MiB: Lib/binhex.py
  decodes up to a 128,000-byte read of run-length codes at once, and each
  code expands to up to 255 bytes.
* An 8 MiB file of one repeated byte encodes to under 1/50 of its size, so
  `hexbin()` can write far more than it reads.
* `binhex()` given a `BytesIO` as output, and `hexbin()` given one as input,
  each leave it closed. `hexbin(input, None)` writes the file under the name
  stored in it, in the working directory.
* `binhex.Error` is raised by `hexbin()` for text with no `:` marker
  ("No binhex data found") and for one encoded character replaced by another
  valid one ("CRC error"); by `binhex()` for an input whose base name has 64
  characters ("Filename too long"), and not for 63. A character outside the
  BinHex alphabet raises `binascii.Error` ("Illegal char"), which is not a
  subclass of `binhex.Error`.
* A 14,007-byte encoded file cut every 37 bytes from byte 60: each cut
  either raises `binhex.Error` ("Premature EOF") or keeps calling `read()`
  at the end of the input past 1,000 calls, when an in-memory file stops it,
  and both outcomes occur. Lib/binhex.py's `_Hqxdecoderengine.read()` loops
  while it has decoded part of a request and the input returns nothing.
* Importing the module on 3.10 emits a `DeprecationWarning`; from 3.11 it
  raises `ModuleNotFoundError`, and `binascii` has `crc_hqx` and none of
  `a2b_hqx`, `b2a_hqx`, `rlecode_hqx` and `rledecode_hqx`.
* Every fenced Python block runs in its own subprocess on 3.10, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The deprecation in 3.9 comes from the 3.10 documentation; 3.9 is not a
  supported interpreter.
* The format description in the introduction is read from Lib/binhex.py.
* Pricing file-name handling at O(1) is a cost-model choice; path length is
  not varied. That a `BytesIO` passed in or out holds the whole file is what
  the object is, and is not measured.
* Corruption is tried at the middle of one file only, and how far the
  decoder gets before failing is not measured. That a looping decode never
  ends is read from the source; the test stops it after 1,000 reads.
* No file carries a resource fork: `binhex()` always writes an empty one.
* `binhex.Error` is a plain `Exception` subclass with no state of its own,
  read from Lib/binhex.py; its construction is not measured.
* `FInfo`, `getfileinfo`, `openrsrc`, `BinHex` and `HexBin` are outside the
  module's `__all__` and its 3.10 documentation; the page does not cover them,
  and the audit lists them under needs-classification on 3.10.
"""

from __future__ import annotations

import binascii
import gc
import importlib
import importlib.util
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "binhex.md"
EXPECTED_BLOCKS = 2
MIB = 1024 * 1024


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


@pytest.fixture
def binhex() -> Iterator[Any]:
    if sys.version_info >= (3, 11):
        pytest.skip("version: binhex was removed in Python 3.11")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("binhex")


class LoopingAtEOF(Exception):
    """Raised by `EndlessReadGuard` once a reader has asked past the end 1,000 times."""


class EndlessReadGuard(io.BytesIO):
    """An in-memory file that stops a reader still asking for data after 1,000
    reads at the end."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.reads_at_eof = 0

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        if not data:
            self.reads_at_eof += 1
            if self.reads_at_eof > 1000:
                raise LoopingAtEOF
        return data


def _encode(binhex: Any, directory: pathlib.Path, payload: bytes) -> pathlib.Path:
    source = directory / "input.bin"
    encoded = directory / "encoded.hqx"
    source.write_bytes(payload)
    binhex.binhex(str(source), str(encoded))
    return encoded


class TestAvailability:
    """`import binhex` works on 3.10 with a warning and fails from 3.11, when
    `binascii` keeps only `crc_hqx` of the helpers it was built on."""

    def test_the_module_exists_only_before_3_11(self) -> None:
        exists = importlib.util.find_spec("binhex") is not None
        assert exists == (sys.version_info < (3, 11))

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="removed in Python 3.11")
    def test_importing_it_warns(self) -> None:
        sys.modules.pop("binhex", None)
        with pytest.warns(DeprecationWarning, match="binhex"):
            importlib.import_module("binhex")

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="present before Python 3.11")
    def test_importing_it_raises_and_binascii_keeps_only_crc_hqx(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("binhex")
        assert hasattr(binascii, "crc_hqx")
        removed = ("a2b_hqx", "b2a_hqx", "rlecode_hqx", "rledecode_hqx")
        assert not [name for name in removed if hasattr(binascii, name)]


class TestConversionIsOneStreamedPass:
    """`binhex()` and `hexbin()` are O(n) time and O(1) space. Every data byte
    passes through `crc_hqx` once on each side, so counting its input shows
    one pass; a peak that followed the file would grow 16x across the sizes
    and is held under 2x."""

    @pytest.mark.parametrize("pattern", [b"a", bytes(range(256))], ids=["repeated", "cycling"])
    def test_each_side_passes_the_file_once_in_bounded_memory(
        self, binhex: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, pattern: bytes
    ) -> None:
        original_crc = binhex.binascii.crc_hqx
        processed = 0

        def counting_crc(data: bytes, value: int) -> int:
            nonlocal processed
            processed += len(data)
            return original_crc(data, value)

        monkeypatch.setattr(binhex.binascii, "crc_hqx", counting_crc)
        peaks: dict[str, list[int]] = {"binhex": [], "hexbin": []}
        source, encoded, restored = (tmp_path / name for name in ("in", "hqx", "out"))
        for size in (8 * MIB, 128 * MIB):
            payload = pattern * (size // len(pattern))
            source.write_bytes(payload)
            for name, inp, out in (("binhex", source, encoded), ("hexbin", encoded, restored)):
                processed = 0
                convert = partial(getattr(binhex, name), str(inp), str(out))
                peaks[name].append(peak_bytes(convert))
                assert size <= processed < size + 1024, (name, size, processed)
            assert restored.read_bytes() == payload
            del payload
        for name, (small, large) in peaks.items():
            assert large < small * 2, (name, small, large)

    def test_repeated_bytes_encode_far_smaller(self, binhex: Any, tmp_path: pathlib.Path) -> None:
        encoded = _encode(binhex, tmp_path, b"a" * (8 * MIB))
        assert encoded.stat().st_size * 50 < 8 * MIB


class TestArguments:
    """A file object passed as `binhex()`'s output or `hexbin()`'s input is
    closed when done, and `hexbin(input, None)` takes its output name from the
    file."""

    def test_binhex_closes_an_output_stream(self, binhex: Any, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "input.bin"
        source.write_bytes(b"data" * 100)
        stream = io.BytesIO()
        binhex.binhex(str(source), stream)
        assert stream.closed

    def test_hexbin_closes_an_input_stream(self, binhex: Any, tmp_path: pathlib.Path) -> None:
        encoded = _encode(binhex, tmp_path, b"data" * 100)
        stream = io.BytesIO(encoded.read_bytes())
        binhex.hexbin(stream, str(tmp_path / "out.bin"))
        assert stream.closed
        assert (tmp_path / "out.bin").read_bytes() == b"data" * 100

    def test_hexbin_without_output_uses_the_stored_name(
        self, binhex: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        encoded = _encode(binhex, source_dir, b"stored")
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        monkeypatch.chdir(target_dir)
        binhex.hexbin(str(encoded), None)
        assert (target_dir / "input.bin").read_bytes() == b"stored"


class TestErrors:
    """`binhex.Error` covers missing, truncated and corrupted data and a long
    input name; a character outside the alphabet raises `binascii.Error`."""

    @pytest.fixture
    def encoded(self, binhex: Any, tmp_path: pathlib.Path) -> bytes:
        return _encode(binhex, tmp_path, bytes(range(256)) * 40).read_bytes()

    def _decode(self, binhex: Any, directory: pathlib.Path, data: bytes) -> None:
        damaged = directory / "damaged.hqx"
        damaged.write_bytes(data)
        binhex.hexbin(str(damaged), str(directory / "out.bin"))

    def test_no_marker(self, binhex: Any, tmp_path: pathlib.Path) -> None:
        with pytest.raises(binhex.Error, match="No binhex data found"):
            self._decode(binhex, tmp_path, b"no encoded data")

    def test_truncated_input_raises_or_never_ends(
        self, binhex: Any, tmp_path: pathlib.Path, encoded: bytes
    ) -> None:
        outcomes: dict[str, list[int]] = {}
        for cut in range(60, len(encoded), 37):
            stream = EndlessReadGuard(encoded[:cut])
            try:
                binhex.hexbin(stream, str(tmp_path / "out.bin"))
            except binhex.Error as error:
                outcome = str(error)
            except LoopingAtEOF:
                outcome = "loops"
            else:
                outcome = "decoded"
            outcomes.setdefault(outcome, []).append(cut)
        assert set(outcomes) == {"Premature EOF on binhex file", "loops"}, outcomes

    def test_corrupted(self, binhex: Any, tmp_path: pathlib.Path, encoded: bytes) -> None:
        middle = len(encoded) // 2
        replacement = b"!" if encoded[middle : middle + 1] != b"!" else b"a"
        damaged = encoded[:middle] + replacement + encoded[middle + 1 :]
        with pytest.raises(binhex.Error, match="CRC error"):
            self._decode(binhex, tmp_path, damaged)

    def test_illegal_character_is_a_binascii_error(
        self, binhex: Any, tmp_path: pathlib.Path, encoded: bytes
    ) -> None:
        assert not issubclass(binascii.Error, binhex.Error)
        middle = len(encoded) // 2
        with pytest.raises(binascii.Error, match="Illegal char"):
            self._decode(binhex, tmp_path, encoded[:middle] + b"~" + encoded[middle + 1 :])

    def test_input_name_over_63_characters(self, binhex: Any, tmp_path: pathlib.Path) -> None:
        for length in (63, 64):
            source = tmp_path / ("x" * length)
            source.write_bytes(b"data")
            output = str(tmp_path / f"{length}.hqx")
            if length == 63:
                binhex.binhex(str(source), output)
            else:
                with pytest.raises(binhex.Error, match="Filename too long"):
                    binhex.binhex(str(source), output)


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
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result, on
    the version that still has the module."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import binhex" in source for _, source in blocks)

    def test_every_block_runs(self, binhex: Any, tmp_path: pathlib.Path) -> None:
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
        self, binhex: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "== source.read_bytes()" in s)
        mutated = source.replace("== source.read_bytes()", "!= source.read_bytes()", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
