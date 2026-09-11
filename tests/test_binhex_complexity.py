"""Evidence for docs/stdlib/binhex.md on Python 3.10.

The exported API is the documented scope; imported modules, constants, FInfo,
getfileinfo, openrsrc, BinHex and HexBin are implementation helpers outside it.
The released CPython 3.10 Lib/binhex.py processes files in 128000-byte chunks;
binascii's HQX, RLE and CRC loops do linear byte work. Counting CRC input guards
full data processing; traced peaks guard bounded auxiliary memory for repeated
and byte-cycling data at 8 MiB and 128 MiB. Path length, custom stream costs,
malformed-input costs and filesystem latency are not varied. Files on disk are
excluded from auxiliary space. The historical deprecation date is source-only
evidence from the official 3.10 documentation and 3.11 removal notice linked on
the page. Runtime tests execute only where the module exists; availability is
checked on every supported interpreter. The one code fence runs in a subprocess.
"""

import importlib
import importlib.util
import re
import subprocess
import sys
import tracemalloc
import warnings
from pathlib import Path

import pytest

PAGE = Path(__file__).resolve().parent.parent / "docs/stdlib/binhex.md"


def test_availability() -> None:
    assert (importlib.util.find_spec("binhex") is not None) == (sys.version_info < (3, 11))


@pytest.fixture
def module():
    if sys.version_info >= (3, 11):
        pytest.skip("binhex was removed in Python 3.11")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("binhex")


def test_exported_api_and_errors(module) -> None:
    rows = set(re.findall(r"^\| `([A-Za-z]+)\(", PAGE.read_text(), re.MULTILINE))
    assert rows == set(module.__all__)
    message = "message" * 1000
    error = module.Error(message)
    assert isinstance(error, Exception)
    assert error.args[0] is message


def test_invalid_data(module, tmp_path: Path) -> None:
    source = tmp_path / "invalid.hqx"
    source.write_bytes(b"no encoded data")
    with source.open("rb") as stream, pytest.raises(module.Error):
        module.hexbin(stream, str(tmp_path / "output.bin"))


@pytest.mark.parametrize("pattern", [b"a", bytes(range(256))])
def test_streamed_conversion(module, tmp_path: Path, monkeypatch, pattern: bytes) -> None:
    original_crc = module.binascii.crc_hqx
    processed = 0

    def crc(data, initial):
        nonlocal processed
        processed += len(data)
        return original_crc(data, initial)

    monkeypatch.setattr(module.binascii, "crc_hqx", crc)
    peaks = {"binhex": [], "hexbin": []}
    for size in (8 * 1024 * 1024, 128 * 1024 * 1024):
        payload = pattern * (size // len(pattern))
        source, encoded, restored = (tmp_path / name for name in ("in", "hqx", "out"))
        source.write_bytes(payload)
        for name, inp, out in (("binhex", source, encoded), ("hexbin", encoded, restored)):
            processed = 0
            tracemalloc.start()
            try:
                getattr(module, name)(str(inp), str(out))
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            assert size <= processed < size + 1024, (name, size, processed)
            peaks[name].append(peak)
        assert restored.read_bytes() == payload
    for name, (small, large) in peaks.items():
        assert large < small * 6, (name, small, large)


def test_example(module, tmp_path: Path) -> None:
    blocks = re.findall(r"```python\n(.*?)```", PAGE.read_text(), re.DOTALL)
    assert len(blocks) == 1
    result = subprocess.run(
        [sys.executable, "-c", blocks[0]],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"{PAGE}:27: {result.stderr}"
