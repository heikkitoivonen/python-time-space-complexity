"""Tests for docs/builtins/hex.md.

hex() is builtin_hex in Python/bltinmodule.c: PyNumber_ToBase(x, 16), which
calls `__index__` once through _PyNumber_Index and hands the resulting int to
_PyLong_Format. For base 16 that is long_format_binary in Objects/longobject.c,
which sizes the string from the digit count and writes one character per four
bits. The call chain is the same in the v3.11.14, v3.12.12, v3.13.11, v3.14.2
and v3.15.0rc3 tags, so no version is treated apart.

Measurement scope:

* output size: `len(hex(x))` is `(x.bit_length() + 3) // 4 + 2` for a positive
  x, one more for a negative one, and 3 for zero, at widths from 1 to
  1,000,000 bits;
* space: tracemalloc's peak for hex() of a 1,000,000-bit int lies between one
  and two bytes per hex digit, the size of the returned ASCII string;
* time: a hundredfold step in width, 100,000 to 10,000,000 bits. The test
  accepts x20 to x1,000: a constant-time claim predicts x1 and a quadratic one
  x10,000;
* the digit limit: with `sys.set_int_max_str_digits(640)`, hex() of a
  1,001-digit int succeeds while str() of it raises ValueError;
* `__index__`: a counting `__index__` is called once per hex() call, and a
  float, a str and an object without `__index__` raise TypeError;
* the lowercase claim: hex() of an int with every hex digit present contains
  no uppercase letter, and format(x, 'X') is its uppercase twin;
* the page's parsing advice: `int(s)` rejects hex()'s output, `int(s, 16)` and
  `int(s, 0)` accept it;
* bytes.hex() against hex(): two digits per byte, leading zero bytes kept by
  bytes.hex() and dropped by hex(int.from_bytes(...));
* every stated example value, and every fenced block runs in a subprocess;
  the blocks whose printed output is deterministic have it compared with the
  page's comments.

Not settled here:

* O(log n) and O(h) in the table are the same bound: for a positive n, h is
  ceil(n.bit_length() / 4), and h is 1 for zero. That is a definition, not a
  measurement.
* The cost of a user `__index__` is the caller's; the page names it once and
  the tests hold it at O(1).
* The Memory Address Representation block prints id() values, which differ
  per run; it is run but its output is not compared.
* "Using hex() for very frequent operations (cache result)" is advice with no
  measurable claim attached.
* Not varied: the bit pattern (every timed int is all ones), the width of
  the traced-peak probe (one 1,000,000-bit int; the output-length checks
  cover the growth), and int subclasses, which _PyNumber_Index passes
  through without `__index__`.
"""

from __future__ import annotations

import hashlib
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "hex.md"
EXPECTED_BLOCKS = 13

SMALL = 100_000
LARGE = 10_000_000


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 3) -> float:
    """The fastest of several runs of `loops` calls, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times) / loops


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc sees while `func` runs, after one warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class CountingIndex:
    """An object usable as an integer, counting its `__index__` calls."""

    def __init__(self, value: int) -> None:
        self.value = value
        self.calls = 0

    def __index__(self) -> int:
        self.calls += 1
        return self.value


class TestOneCharacterPerHexDigit:
    """Rows: Convert integer and Negative integer - O(h), one character per
    hex digit after a '0x' or '-0x' prefix."""

    @pytest.mark.parametrize("bits", [1, 2, 4, 5, 63, 64, 65, 1_000, 1_000_000])
    def test_output_length_is_the_digit_count_plus_the_prefix(self, bits: int) -> None:
        value = (1 << bits) - 1
        digits = (value.bit_length() + 3) // 4

        assert len(hex(value)) == digits + 2
        assert len(hex(-value)) == digits + 3
        assert hex(-value) == "-" + hex(value)

    def test_zero_has_one_digit(self) -> None:
        assert hex(0) == "0x0"

    @pytest.mark.serial
    def test_peak_space_is_one_to_two_bytes_per_digit(self) -> None:
        value = (1 << 1_000_000) - 1
        digits = 1_000_000 // 4

        peak = traced_peak(lambda: hex(value))

        assert digits <= peak < 2 * digits, peak

    @pytest.mark.timing
    def test_time_is_linear_in_the_digit_count(self) -> None:
        small = (1 << SMALL) - 1
        large = (1 << LARGE) - 1
        hex(large)  # warm up

        ratio = best_time(lambda: hex(large)) / best_time(lambda: hex(small), loops=100)

        assert 20 < ratio < 1_000, f"x{ratio:.1f} for x{LARGE // SMALL} in bits"


class TestLargeIntegers:
    """Row: Large integer - not limited by sys.set_int_max_str_digits(), which
    exempts power-of-two bases."""

    def test_the_digit_limit_does_not_apply(self) -> None:
        previous = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(640)
        try:
            value = 10**1000
            assert hex(value) == "0x" + format(value, "x")
            with pytest.raises(ValueError, match="limit"):
                str(value)
        finally:
            sys.set_int_max_str_digits(previous)


class TestIndexProtocol:
    """Row: Object with `__index__` - `__index__` + O(h); any other non-int
    raises TypeError."""

    def test_index_is_called_once(self) -> None:
        obj = CountingIndex(255)

        assert hex(obj) == "0xff"
        assert obj.calls == 1

    def test_bool_is_an_int(self) -> None:
        assert hex(True) == "0x1"
        assert hex(False) == "0x0"

    @pytest.mark.parametrize("value", [3.0, "5", object()])
    def test_other_types_raise(self, value: object) -> None:
        with pytest.raises(TypeError):
            hex(value)  # type: ignore[arg-type]


class TestCaseAndPrefix:
    """Version Notes and the Do/Avoid lists: hex() writes lowercase digits
    after '0x'; format(x, 'x') and f'{x:x}' give the same digits without it,
    and 'X' gives them in uppercase."""

    def test_digits_are_lowercase(self) -> None:
        value = 0x123456789ABCDEF

        assert hex(value) == "0x123456789abcdef"
        assert format(value, "X") == "123456789ABCDEF"

    def test_format_drops_only_the_prefix(self) -> None:
        for value in [*range(100), -5, 2**70]:
            assert format(value, "x") == f"{value:x}"
            assert hex(value) == ("-0x" if value < 0 else "0x") + f"{abs(value):x}"


class TestParsing:
    """Bidirectional Conversion and the Avoid list: int(s, 16) and int(s, 0)
    read hex()'s output, plain int(s) rejects it."""

    def test_base_16_and_base_0_accept_the_prefix(self) -> None:
        assert int("0xff", 16) == 255
        assert int("0xff", 0) == 255
        assert int("ff", 16) == 255
        assert int(hex(-12345), 0) == -12345

    def test_plain_int_rejects_the_prefix(self) -> None:
        with pytest.raises(ValueError, match="0xff"):
            int("0xff")


class TestBytesHex:
    """Checksums/Hashes: bytes.hex() writes two digits per byte and keeps
    leading zero bytes; hex() of the same value as an int drops them."""

    @pytest.mark.parametrize("data", [b"", b"\x00", b"\x00\x0f", b"hello" * 100])
    def test_two_digits_per_byte(self, data: bytes) -> None:
        assert len(data.hex()) == 2 * len(data)

    def test_hex_drops_leading_zero_bytes(self) -> None:
        digest = b"\x00" * 3 + hashlib.sha256(b"hello").digest()[3:]

        assert digest.hex().startswith("000000")
        assert hex(int.from_bytes(digest, "big"))[2:] == digest.hex().lstrip("0")


class TestStatedExampleValues:
    """The values the page's comments give, checked rather than trusted."""

    def test_basic_usage(self) -> None:
        expected = {0: "0x0", 15: "0xf", 255: "0xff", 256: "0x100", 4095: "0xfff"}
        for value, text in expected.items():
            assert hex(value) == text
        assert hex(-1) == "-0x1"
        assert hex(-255) == "-0xff"
        assert hex(-1000) == "-0x3e8"

    def test_large_integers(self) -> None:
        assert hex(2**32) == "0x100000000"
        assert hex(2**100) == "0x1" + "0" * 25
        assert len(hex(10**100)) - 2 == 84
        assert len(hex(255)) - 2 == 2
        assert hex(2**64 - 1) == "0x" + "f" * 16
        assert max(len(hex(n)) - 2 for n in range(100)) == 2

    def test_common_use_cases(self) -> None:
        assert hex(42) == "0x2a"
        assert bin(42) == "0b101010"
        assert hex(0x1A2B) == "0x1a2b"
        assert hex(12345) == "0x3039"


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, under the interpreter running the tests."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    @pytest.mark.parametrize(
        ("marker", "expected"),
        [
            (
                "values = [1, 2, 4, 8",
                ["0x2a"] + [f"{v:3d} = {hex(v)}" for v in [1, 2, 4, 8, 16, 32, 64, 128]],
            ),
            ('print(f"Dec:', ["Dec: 42, Hex: 0x2a, Bin: 0b101010"]),
        ],
    )
    def test_printed_output_matches_the_comments(
        self, tmp_path: pathlib.Path, marker: str, expected: list[str]
    ) -> None:
        block = next(source for _, source in _blocks() if marker in source)

        result = _run(block, tmp_path)

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == expected

    def test_the_address_block_prints_two_distinct_addresses(self, tmp_path: pathlib.Path) -> None:
        block = next(source for _, source in _blocks() if "addr = id(obj)" in source)

        result = _run(block, tmp_path)

        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert len(lines) == 3
        assert all(line.startswith("0x") for line in lines)
        assert lines[1] != lines[2]

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "def rgb_to_hex" in source)
        broken = block.replace("assert color == '#ff8040'", "assert color == '#ff8041'", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
