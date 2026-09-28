"""Tests for docs/stdlib/zlib.md.

This file settles the page's checksum rows, `zlib.adler32()` and
`zlib.crc32()`: O(n) time in the length of `data`, O(1) space, and a running
checksum through the `value` argument. Space is settled by traced allocation,
which separates a constant from a copy of the input by orders of magnitude;
time by a ratio over a sixteen-fold step in the input; the running checksum by
comparing chunked and one-shot results.

Measurement scope:

* Each checksum over 16,000,000 bytes peaks under 1,000 traced bytes, where
  `bytes(view)` of the same input - the control, a function that does copy -
  peaks above 15,000,000.
* In a timing test, 16x the input (250,000 to 4,000,000 bytes) costs between
  4x and 64x for each function, which excludes both O(1) and O(n^2).
* Folding 1,000,192 bytes through each function in 4,096-byte, 65,536-byte
  and uneven (1, 7, 4,099 ...) chunks gives the one-shot result every time,
  starting from the documented defaults: 0 for `crc32()`, 1 for `adler32()`.
  A 65,536-byte slice of a `memoryview`, as the page's example takes, is
  asserted to share the input (`chunk.obj is data`) and to peak under 1,000
  traced bytes.
* Every fenced block runs in its own subprocess and working directory, and a
  mutated assertion in the checksum block is asserted to make it fail. The
  blocks under "decompress()", both "Space Complexity" headings,
  "Compressobj", "Decompressobj", "Basic Compression/Decompression",
  "Incremental Flushing", "Best Practices" and "Checksums" check what they produced against their input, byte for
  byte or by CRC-32. The rest - including the two "Streaming Large File"
  and the "Preventing Decompression Bombs" blocks, which only define
  functions the runner does not call - are shown only to execute.

Not settled here:

* The page's compression rows - `compress()`, `decompress()`, the
  `compressobj()`/`decompressobj()` objects and their methods, compression
  levels and flushing - are outside this file's measurements.
* Only a byte string of one repeated value is measured. Both checksums walk
  their input without branching on its content, so other contents are not
  varied.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import zlib
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "zlib.md"
EXPECTED_BLOCKS = 19

CHECKSUMS = pytest.mark.parametrize(
    ("checksum", "start"), [(zlib.crc32, 0), (zlib.adler32, 1)], ids=["crc32", "adler32"]
)


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
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


class TestChecksumsHoldNothingButTheValue:
    """`adler32(data)` / `crc32(data)`: O(1) space."""

    @pytest.mark.serial
    @CHECKSUMS
    def test_the_peak_does_not_follow_the_input(
        self, checksum: Callable[[Any], int], start: int
    ) -> None:
        view = memoryview(b"x" * 16_000_000)
        checksum(view)

        checksummed = peak_bytes(lambda: checksum(view))
        copied = peak_bytes(lambda: bytes(view))

        assert checksummed < 1_000, f"a checksum of 16 MB peaked at {checksummed} B"
        assert copied > 15_000_000, f"the copying control peaked at only {copied} B"


class TestChecksumsReadTheInputOnce:
    """`adler32(data)` / `crc32(data)`: O(n) time, n = len(data)."""

    @pytest.mark.timing
    @CHECKSUMS
    def test_sixteen_times_the_input_costs_sixteen_times_the_time(
        self, checksum: Callable[[Any], int], start: int
    ) -> None:
        small, large = b"x" * 250_000, b"x" * 4_000_000
        checksum(small)

        ratio = best_ns(lambda: checksum(large)) / best_ns(lambda: checksum(small))

        assert 4 < ratio < 64, f"16x the input cost x{ratio:.1f}"


class TestTheValueArgumentContinuesAChecksum:
    """Passing the previous result as `value` continues a running checksum."""

    @CHECKSUMS
    def test_the_defaults_are_the_empty_input_s_checksum(
        self, checksum: Callable[..., int], start: int
    ) -> None:
        assert checksum(b"") == start
        assert checksum(b"abc", start) == checksum(b"abc")

    @CHECKSUMS
    @pytest.mark.parametrize("sizes", [[4_096], [65_536], [1, 7, 4_099, 65_537, 3]])
    def test_any_chunking_gives_the_one_shot_result(
        self, checksum: Callable[..., int], start: int, sizes: list[int]
    ) -> None:
        data = bytes(range(256)) * 3_907
        view = memoryview(data)
        running, offset, turn = start, 0, 0
        while offset < len(data):
            size = sizes[turn % len(sizes)]
            running = checksum(view[offset : offset + size], running)
            offset += size
            turn += 1

        assert turn > 1
        assert running == checksum(data)

    @pytest.mark.serial
    def test_the_example_s_memoryview_slices_do_not_copy(self) -> None:
        data = b"payload " * 100_000
        chunk = memoryview(data)[65_536 : 2 * 65_536]

        assert chunk.obj is data
        assert peak_bytes(lambda: memoryview(data)[65_536 : 2 * 65_536]) < 1_000


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
    """Each block runs in its own subprocess and working directory."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert running_crc == crc" in s)
        mutated = source.replace("assert running_crc == crc", "assert running_crc != crc", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
