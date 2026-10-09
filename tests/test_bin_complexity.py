"""Tests for docs/builtins/bin.md.

bin() is builtin_bin in Python/bltinmodule.c: PyNumber_ToBase(x, 2), which
calls `__index__` once through _PyNumber_Index and hands the resulting int to
_PyLong_Format. For base 2 that is long_format_binary in Objects/longobject.c,
which sizes the string from the digit count and writes one character per bit.
The call chain is the same in the v3.10.19, v3.11.14, v3.12.12, v3.13.11 and
v3.14.2 tags, so no version is treated apart.

Measurement scope:

* output size: `len(bin(x))` is `x.bit_length() + 2` for a positive x, one more
  for a negative one, and 3 for zero, at widths from 1 to 1,000,000 bits;
* space: tracemalloc's peak for bin() of a 1,000,000-bit int lies between one
  and two bytes per bit, the size of the returned ASCII string;
* time: a hundredfold step in width, 100,000 to 10,000,000 bits, measured x104
  for bin(), x88 for int.bit_count() and x106 for int(s, 2) on the pinned
  interpreter (aarch64, CPython 3.14). The tests accept x20 to x1,000: a
  constant-time claim predicts x1 and a quadratic one x10,000;
* the digit limit: with `sys.set_int_max_str_digits(640)`, bin(), oct() and
  hex() of a 1,001-digit int succeed while str() of it raises ValueError;
* `__index__`: a counting `__index__` is called once per bin() call, and a
  float, a str and an object without `__index__` raise TypeError;
* bit_count() against bin().count('1'): equal results on positive, negative
  and zero values, and a traced peak under 1 KiB for bit_count() on a
  1,000,000-bit int against at least 1,000,000 bytes for the string route;
* the page's parsing advice: `int(s)` rejects bin()'s output, `int(s, 2)` and
  `int(s, 0)` accept it;
* every stated example value, and every fenced block runs in a subprocess;
  the blocks that print have their output compared with the page's comments.

Not settled here:

* O(log n) and O(b) in the table are the same bound: for a positive n, b is
  n.bit_length(), which is floor(log2 n) + 1, and b is 1 for zero. That is a
  definition, not a measurement.
* The cost of a user `__index__` is the caller's; the page names it once and
  the tests hold it at O(1).
* The Bit Manipulation Operations block makes no cost claim; the cost of the
  bitwise operators themselves belongs to the int page.
* "Using bin() for very frequent operations", "assuming binary operations are
  faster" and "building binary from decimal without understanding conversion"
  are advice with no measurable claim attached.
* Not varied: the bit pattern (every timed int is all ones) and
  int subclasses, which _PyNumber_Index passes through without `__index__`.
"""

from __future__ import annotations

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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "bin.md"
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


class TestOneCharacterPerBit:
    """Rows: Convert integer and Negative integer - O(b), one character per
    binary digit after a '0b' or '-0b' prefix."""

    @pytest.mark.parametrize("bits", [1, 2, 63, 64, 65, 1_000, 1_000_000])
    def test_output_length_is_the_bit_length_plus_the_prefix(self, bits: int) -> None:
        value = (1 << bits) - 1

        assert len(bin(value)) == value.bit_length() + 2
        assert len(bin(-value)) == value.bit_length() + 3
        assert bin(-value) == "-" + bin(value)

    def test_zero_has_one_digit(self) -> None:
        assert bin(0) == "0b0"

    @pytest.mark.serial
    def test_peak_space_is_linear_in_the_bit_count(self) -> None:
        value = (1 << 1_000_000) - 1

        peak = traced_peak(lambda: bin(value))

        assert 1_000_000 <= peak < 2 * 1_000_000, peak

    @pytest.mark.timing
    def test_time_is_linear_in_the_bit_count(self) -> None:
        small = (1 << SMALL) - 1
        large = (1 << LARGE) - 1
        bin(large)  # warm up

        ratio = best_time(lambda: bin(large)) / best_time(lambda: bin(small), loops=100)

        assert 20 < ratio < 1_000, f"x{ratio:.1f} for x{LARGE // SMALL} in bits"


class TestLargeIntegers:
    """Row: Large integer - not limited by sys.set_int_max_str_digits(), which
    exempts power-of-two bases."""

    def test_the_digit_limit_does_not_apply(self) -> None:
        previous = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(640)
        try:
            value = 10**1000
            assert bin(value) == "0b" + format(value, "b")
            assert oct(value) == "0o" + format(value, "o")
            assert hex(value) == "0x" + format(value, "x")
            with pytest.raises(ValueError, match="limit"):
                str(value)
        finally:
            sys.set_int_max_str_digits(previous)


class TestIndexProtocol:
    """Row: Object with `__index__` - `__index__` + O(b); any other non-int
    raises TypeError."""

    def test_index_is_called_once(self) -> None:
        obj = CountingIndex(5)

        assert bin(obj) == "0b101"
        assert obj.calls == 1

    def test_bool_is_an_int(self) -> None:
        assert bin(True) == "0b1"
        assert bin(False) == "0b0"

    @pytest.mark.parametrize("value", [3.0, "5", object()])
    def test_other_types_raise(self, value: object) -> None:
        with pytest.raises(TypeError):
            bin(value)  # type: ignore[arg-type]


class TestBitCount:
    """Counting Set Bits: bit_count() is O(b) like bin().count('1'), but builds
    no string."""

    @pytest.mark.parametrize("value", [0, 1, 0b101010, -0b101010, (1 << 1_000) - 7])
    def test_both_routes_agree(self, value: int) -> None:
        assert bin(value).count("1") == value.bit_count()

    @pytest.mark.serial
    def test_bit_count_builds_no_string(self) -> None:
        value = (1 << 1_000_000) - 1

        string_route = traced_peak(lambda: bin(value).count("1"))
        bit_count = traced_peak(lambda: value.bit_count())

        assert string_route >= 1_000_000, string_route
        assert bit_count < 1024, bit_count

    @pytest.mark.timing
    def test_bit_count_is_linear_in_the_bit_count(self) -> None:
        small = (1 << SMALL) - 1
        large = (1 << LARGE) - 1
        large.bit_count()  # warm up

        ratio = best_time(lambda: large.bit_count()) / best_time(
            lambda: small.bit_count(), loops=100
        )

        assert 20 < ratio < 1_000, f"x{ratio:.1f} for x{LARGE // SMALL} in bits"


class TestParsing:
    """Binary String to Integer and the Avoid list: int(s, 2) and int(s, 0)
    read bin()'s output, plain int(s) rejects it; parsing is linear in the
    string's length."""

    def test_base_2_and_base_0_accept_the_prefix(self) -> None:
        assert int("0b1010", 2) == 10
        assert int("0b1010", 0) == 10
        assert int("1010", 2) == 10
        assert int(bin(-255), 0) == -255

    def test_plain_int_rejects_the_prefix(self) -> None:
        with pytest.raises(ValueError, match="0b1010"):
            int("0b1010")

    def test_leading_zeros_lengthen_the_input_not_the_value(self) -> None:
        assert int("0b" + "0" * 10_000 + "1010", 2) == 10

    @pytest.mark.timing
    def test_parsing_is_linear_in_the_length(self) -> None:
        small = "1" * SMALL
        large = "1" * LARGE
        int(large, 2)  # warm up

        ratio = best_time(lambda: int(large, 2)) / best_time(lambda: int(small, 2), loops=100)

        assert 20 < ratio < 1_000, f"x{ratio:.1f} for x{LARGE // SMALL} in length"


class TestStatedExampleValues:
    """The values the page's comments give, checked rather than trusted."""

    def test_basic_usage(self) -> None:
        expected = {0: "0b0", 1: "0b1", 2: "0b10", 3: "0b11", 8: "0b1000", 255: "0b11111111"}
        for value, text in expected.items():
            assert bin(value) == text
        assert bin(-1) == "-0b1"
        assert bin(-8) == "-0b1000"
        assert bin(-255) == "-0b11111111"

    def test_large_integers(self) -> None:
        assert bin(2**10) == "0b10000000000"
        assert bin(2**32) == "0b1" + "0" * 32
        assert len(bin(2**100)) - 2 == 101
        assert len(bin(3)) - 2 == 2
        assert len(bin(2**64 - 1)) - 2 == 64
        assert max(len(bin(n)) - 2 for n in range(100)) == 7

    def test_bitwise_results(self) -> None:
        a, b = 0b1100, 0b1010
        assert bin(a & b) == "0b1000"
        assert bin(a | b) == "0b1110"
        assert bin(a ^ b) == "0b110"
        assert bin(~a) == "-0b1101"
        assert ~a == -13
        assert bin(a << 2) == "0b110000"
        assert bin(a >> 1) == "0b110"

    def test_format_drops_only_the_prefix(self) -> None:
        for value in [*range(100), -5, 2**70]:
            assert format(value, "b") == f"{value:b}"
            assert bin(value) == ("-0b" if value < 0 else "0b") + f"{abs(value):b}"

    def test_practical_examples(self) -> None:
        assert bin(42) == "0b101010"
        assert bin(0b100 | 0b010) == "0b110"
        assert bin(192) == "0b11000000"
        my_set = (1 << 3) | (1 << 5)
        assert bin(my_set) == "0b101000"
        assert bin(my_set & ~(1 << 3)) == "0b100000"


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
            ("def has_bit_set", ["0b101010", "False", "True"]),
            (
                'print(f"x = {bin(x)}")',
                ["x = 0b1100", "y = 0b1010", "x & y = 0b1000", "x | y = 0b1110"]
                + ["x ^ y = 0b110", "~x = -0b1101"],
            ),
            ("# Bitwise AND", ["0b1000", "0b1110", "0b110", "-0b1101", "0b110000", "0b110"]),
            ("READ = 0b100", ["0b110"]),
            ("ip = ", ["0b11000000", "0b" + "1" * 24 + "0" * 8]),
            ("SET_SIZE", ["0b101000", "True", "False", "0b100000"]),
        ],
    )
    def test_printed_output_matches_the_comments(
        self, tmp_path: pathlib.Path, marker: str, expected: list[str]
    ) -> None:
        block = next(source for _, source in _blocks() if marker in source)

        result = _run(block, tmp_path)

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == expected

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "def count_bits_bin" in source)
        broken = block.replace("value.bit_count()", "value.bit_count() + 1", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
