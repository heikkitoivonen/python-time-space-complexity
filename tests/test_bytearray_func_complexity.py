"""Tests for docs/builtins/bytearray_func.md.

The page prices each way of calling `bytearray()` by the size of what it is
given, and says every form that takes data copies it into a buffer of its own.
Copies and their independence are settled by traced allocation and by mutating
the result, which need no tolerance; error behaviour by what is raised; the
growth classes by timing a hundredfold step in the source, where a linear
constructor has to cost between x10 and x1,000 - far from the x1 of a constant
and the x10,000 of a square.

Measurement scope:

* `bytearray(count)`, `bytearray(bytes)`, `bytearray(str, 'utf-8')`,
  `bytearray.fromhex()`, `bytearray(list)` and an ASCII encode with
  `errors='ignore'` - which emits nothing and still walks the string - all
  scale with their source, from 100,000 to 10,000,000 bytes, items or
  characters (the list at a tenth of that, the hex string at twice it). Building 10,000,000 bytes from a
  count or from a `bytes` traces a peak of at least 10,000,000.
* The empty bytearray has an allocation of 0. A copy of a `bytearray`
  source is mutated and the source asserted unchanged; `memoryview` and
  `array.array` sources are accepted. The `TypeError` and `ValueError` cases
  are asserted by their messages.
* `fromhex()` skips whitespace between pairs, and takes a `bytes` argument
  on 3.14 and raises `TypeError` before.
* A bytes-like source copied in one step costs less than a tenth of a list
  of the same 100,000 items, which is the page's advice to pass one when
  you have it. `bytearray([200])` holds one byte and traces under 1,000
  bytes, where `bytearray(1_000_000)` traces at least the count.
* `readinto()` from an `io.BytesIO` into a preallocated 1,000,000-byte
  bytearray traces under 1,000 bytes and leaves the same object holding the
  data: the Common Patterns example's reuse of one buffer. A 500,000-byte
  slice of a `memoryview` of it traces under 1,000.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The `str` constructor is timed with UTF-8 and with ASCII plus
  `errors='ignore'`; other codecs and error handlers are not varied. The
  encoding row is scoped to codecs and error handlers whose cost and output
  are proportional to their input. A registered handler may return a
  replacement of any length, and a codec that rebuilds its result as it goes
  costs more than its output; both are caller-chosen and neither is measured.
* Timings hold the element values fixed, all zeros or one repeated
  character. The iterable is timed as a list, whose size is known up front
  from 3.11; a generator, which grows the buffer as it goes, is exercised
  for its result only.
"""

from __future__ import annotations

import array
import io
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "bytearray_func.md"
EXPECTED_BLOCKS = 4

SMALL = 100_000
LARGE = 10_000_000
STEP = LARGE / SMALL  # every scaling measurement below uses this hundredfold step
LINEAR = 10  # a hundredfold input must cost at least this much more
QUADRATIC = 1_000  # ... and below this, where a quadratic one would be near x10,000

# The Windows heap hands a block above about 1 MB to VirtualAlloc and returns it
# on free, so each call that allocates one pays for freshly committed,
# zero-filled pages, while a 100 KB result stays cache-resident. A constructor
# whose work is one bulk copy into a new buffer then costs x2,000 to x3,900 for
# the 100x step from SMALL to LARGE.
FRESH_PAGES_ON_WINDOWS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="on Windows a new buffer above about 1 MB is freshly committed, zero-filled pages, "
    "so the step crosses from cache-resident to page-faulting memory",
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


def growth(small: Callable[[], Any], large: Callable[[], Any], inner: int = 1) -> float:
    """How many times more the large call costs than the small one."""
    return best_ns(large, inner=inner) / best_ns(small, inner=inner)


def assert_linear(name: str, ratio: float) -> None:
    """A hundredfold input costs far more than a constant and far less than a square."""
    assert LINEAR < ratio < QUADRATIC, f"{name}: {STEP:.0f}x the input cost x{ratio:.1f}"


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class TestEmptyAndCount:
    """`bytearray()` | O(1) with no buffer; `bytearray(count)` | O(n) | O(n)
    zero bytes, and a negative count raises."""

    def test_the_empty_bytearray_allocates_no_buffer(self) -> None:
        assert bytearray().__alloc__() == 0
        assert bytearray(0) == bytearray()

    def test_a_count_gives_that_many_zero_bytes(self) -> None:
        assert bytearray(5) == b"\x00\x00\x00\x00\x00"
        with pytest.raises(ValueError, match="negative count"):
            bytearray(-1)

    def test_a_count_allocates_the_buffer_up_front(self) -> None:
        peak = peak_bytes(lambda: bytearray(LARGE))

        assert peak >= LARGE, f"bytearray({LARGE}) peaked at {peak} bytes"

    def test_a_count_is_a_size_and_a_one_item_list_is_a_value(self) -> None:
        """`bytearray(count)` allocates the count; `bytearray([count])` one byte."""
        count = 1_000_000

        as_size = peak_bytes(lambda: bytearray(count))
        as_value = peak_bytes(lambda: bytearray([200]))

        assert bytearray([200]) == b"\xc8"
        assert as_size >= count, f"bytearray({count}) peaked at {as_size}"
        assert as_value < 1_000, f"bytearray([200]) peaked at {as_value}"


class TestEveryDataSourceIsCopied:
    """`bytearray(bytes_like)` | O(k) as an independent copy;
    `bytearray(iterable)` | O(k), one byte per item."""

    def test_a_bytes_like_source_is_copied_not_shared(self) -> None:
        source = bytearray(b"hello")

        copy = bytearray(source)
        copy[0] = ord("j")

        assert copy is not source
        assert source == bytearray(b"hello")
        assert bytearray(memoryview(b"xy")) == b"xy"
        assert bytearray(array.array("B", [1, 2])) == b"\x01\x02"

    def test_copying_a_bytes_allocates_its_length(self) -> None:
        source = bytes(LARGE)

        peak = peak_bytes(lambda: bytearray(source))

        assert peak >= LARGE, f"bytearray(bytes of {LARGE}) peaked at {peak} bytes"

    def test_an_iterable_supplies_one_byte_per_item(self) -> None:
        assert bytearray([65, 66, 67]) == b"ABC"
        assert bytearray(value for value in range(3)) == b"\x00\x01\x02"
        with pytest.raises(ValueError, match="range\\(0, 256\\)"):
            bytearray([0, 256])
        with pytest.raises(ValueError, match="range\\(0, 256\\)"):
            bytearray([-1])

    @pytest.mark.timing
    def test_a_bytes_like_source_beats_an_iterable_of_the_same_items(self) -> None:
        """One bulk copy against a conversion per item, at a fixed k."""
        # Under the 1 MB at which a Windows result is freshly committed pages.
        as_bytes, as_list = bytes(SMALL), [0] * SMALL

        bulk = best_ns(lambda: bytearray(as_bytes), repeats=5)
        per_item = best_ns(lambda: bytearray(as_list), repeats=5)

        assert per_item > bulk * 10, f"list {per_item:.0f}ns against bytes {bulk:.0f}ns"


class TestTextAndHexSources:
    """`bytearray(string, encoding, errors)` | O(k) and needs the encoding;
    `bytearray.fromhex()` | O(k), skipping whitespace."""

    def test_a_string_needs_an_encoding(self) -> None:
        assert bytearray("café", "utf-8") == b"caf\xc3\xa9"
        assert bytearray("é" * 1_000, "ascii", "ignore") == b"", "the discarded input is still read"
        with pytest.raises(TypeError, match="without an encoding"):
            bytearray("café")  # type: ignore[call-overload]

    def test_fromhex_reads_two_characters_per_byte(self) -> None:
        assert bytearray.fromhex("48 65") == b"He"
        assert bytearray.fromhex("4865") == b"He"
        assert bytearray.fromhex(" 48\t65\n") == b"He"
        assert isinstance(bytearray.fromhex("48"), bytearray)

    def test_fromhex_takes_bytes_from_3_14(self) -> None:
        if sys.version_info >= (3, 14):
            assert bytearray.fromhex(b"ab") == b"\xab"  # type: ignore[arg-type]
        else:
            with pytest.raises(TypeError):
                bytearray.fromhex(b"ab")  # type: ignore[arg-type]


class TestEachConstructorScales:
    """Every row but the empty one is linear in its source."""

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_each_constructor_scales_with_its_source(self) -> None:
        def scaling(source: Callable[[int], Any], build: Callable[[Any], Any]) -> float:
            # One pair of sources alive at a time.
            small, large = source(SMALL), source(LARGE)
            return growth(lambda: build(small), lambda: build(large))

        ratios = {
            "count": scaling(lambda size: size, bytearray),
            "bytes": scaling(bytes, bytearray),
            "str": scaling(lambda size: "é" * size, lambda text: bytearray(text, "utf-8")),
            "fromhex": scaling(lambda size: "ab" * size, bytearray.fromhex),
            "list": scaling(lambda size: [0] * (size // 10), bytearray),
            # A lossy handler emits nothing, and still walks every character.
            "str, ascii, ignore": scaling(
                lambda size: "é" * size, lambda text: bytearray(text, "ascii", "ignore")
            ),
        }

        for name, ratio in ratios.items():
            assert_linear(f"bytearray from {name}", ratio)


class TestPreallocatedReadBuffer:
    """Common Patterns: `bytearray(count)` once, then `readinto()` fills the
    same buffer, and a `memoryview` slice reads it in place."""

    def test_readinto_fills_the_existing_buffer_without_allocating_it(self) -> None:
        size = 1_000_000
        stream = io.BytesIO(b"a" * size)
        buffer = bytearray(size)
        before = id(buffer)

        peak = peak_bytes(lambda: stream.readinto(buffer))

        assert id(buffer) == before and buffer == b"a" * size
        assert peak < 1_000, f"readinto() of {size} bytes peaked at {peak}"

    def test_a_view_slice_copies_nothing(self) -> None:
        size = 1_000_000
        view = memoryview(bytearray(size))

        slice_peak = peak_bytes(lambda: view[: size // 2])

        assert slice_peak < 1_000, f"a view slice peaked at {slice_peak}"
        view.release()


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "one_byte = bytearray([4])" in s)
        mutated = source.replace('bytearray(b"\\x04")', 'bytearray(b"\\x05")', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
