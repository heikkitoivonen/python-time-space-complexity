"""Tests for docs/stdlib/binhex.md.

The module exists on Python 3.10 only, and 3.10 is not a supported
interpreter, so no test here imports it. What runs on every supported
version:

* `import binhex` raises `ModuleNotFoundError`, and `binascii` has `crc_hqx`
  and none of `a2b_hqx`, `b2a_hqx`, `rlecode_hqx` and `rledecode_hqx`.
* The page has two fenced Python blocks; each imports `binhex` and compiles.

Not settled here:

* Every row, the introduction and the examples describe the 3.10 module and
  are read from Lib/binhex.py at v3.10.19. Both functions move the file in
  `read(128000)` chunks through `binascii.crc_hqx` and the run-length and
  6-bit coder engines, whose buffers hold one chunk at most, so time is
  linear in the bytes read and written and space is bounded; a run-length
  decode can expand each three-byte code to up to 255 bytes. `binhex()`
  raises `Error('Filename too long')` for a base name over 63 characters.
  `_Hqxdecoderengine.read()` raises `Error('Premature EOF on binhex file')`
  when the input ends mid-character or before any of a request is decoded,
  and loops forever once part of a request is decoded and the input returns
  nothing, which is the page's loop-forever case.
* The deprecation in 3.9 comes from the 3.10 documentation; neither 3.9 nor
  3.10 is a supported interpreter.
* `FInfo`, `getfileinfo`, `openrsrc`, `BinHex` and `HexBin` are outside the
  module's `__all__` and its 3.10 documentation; the page does not cover them.
"""

from __future__ import annotations

import binascii
import importlib
import pathlib
import re
import textwrap

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "binhex.md"
EXPECTED_BLOCKS = 2


class TestAvailability:
    """`import binhex` fails on every supported version, and `binascii` keeps
    only `crc_hqx` of the helpers it was built on."""

    def test_importing_it_raises_and_binascii_keeps_only_crc_hqx(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("binhex")
        assert hasattr(binascii, "crc_hqx")
        removed = ("a2b_hqx", "b2a_hqx", "rlecode_hqx", "rledecode_hqx")
        assert not [name for name in removed if hasattr(binascii, name)]


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


class TestDocumentedExamples:
    """The blocks need the module, so they are compiled rather than run."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import binhex" in source for _, source in blocks)

    def test_every_block_compiles(self) -> None:
        for line, source in _blocks():
            compile(source, f"{PAGE.name}:{line}", "exec")
