"""Tests for docs/builtins/oct.md.

oct() is builtin_oct in Python/bltinmodule.c: PyNumber_ToBase(x, 8), which
calls `__index__` once through _PyNumber_Index and hands the resulting int to
_PyLong_Format. For base 8 that is long_format_binary in Objects/longobject.c,
which sizes the string from the bit length and writes one character per three
bits; format(x, 'o') reaches the same function. int(s, 8) and int(s, 0) with a
'0o' prefix parse through long_from_binary_base, the linear path PyLong_FromString
takes for every power-of-two base, and only the non-binary path checks
sys.get_int_max_str_digits(). The call chain is the same in the v3.11.14,
v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags, so no version is treated apart.

Measurement scope:

* output size: `len(oct(x))` is `(x.bit_length() + 2) // 3 + 2` for a positive
  x, one more for a negative one, and 3 for zero, at widths from 1 to
  1,000,000 bits;
* space: tracemalloc's peak for oct() of a 1,000,000-bit int lies between one
  and two bytes per octal digit, the size of the returned ASCII string;
* time: a hundredfold step in width, 100,000 to 10,000,000 bits, for oct(),
  format(x, 'o') and int(s, 8). The test accepts x20 to x1,000: a
  constant-time claim predicts x1 and a quadratic one x10,000. Locally each
  measured about x100 on 3.15;
* octal against decimal: a tenfold step from 20,000 to 200,000 bits costs
  str() more than 1.8 times the growth it costs oct(), with the digit limit
  lifted. Locally oct() grew x10 on 3.11 and 3.15 while str() grew x109 on
  3.11 and x41 on 3.15;
* the digit limit: with `sys.set_int_max_str_digits(640)`, oct() of a
  1,001-digit int and int() of the result in base 8 succeed, as do hex() and
  bin() and their base 16 and base 2 parses, while str() of it raises
  ValueError;
* `__index__`: a counting `__index__` is called once per oct() call, bool is
  accepted, and a float, a str and an object without `__index__` raise
  TypeError;
* prefix and parsing: format(x, 'o') is oct() without '0o' (after the sign),
  '#o' keeps it, `int(s, 8)` and `int(s, 0)` read oct()'s output and plain
  `int(s)` rejects it; `oct(x)[2:]` of a negative number keeps the 'o';
* the octal-literal note: compiling `0755` raises SyntaxError and `0o755` is
  493;
* every stated example value is asserted inside its block, every fenced
  block runs in a subprocess, and a mutated assertion is asserted to fail.

Not settled here:

* O(d) and the index page's O(log n) are the same bound: for a positive n, d
  is ceil(n.bit_length() / 3), and d is 1 for zero. That is a definition, not
  a measurement.
* The cost of a user `__index__` is the caller's; the page names it once and
  the tests hold it at O(1).
* Not varied: the bit pattern (every timed int is all ones), the width of
  the traced-peak probe (one 1,000,000-bit int; the output-length checks
  cover the growth), and int subclasses, which _PyNumber_Index passes
  through without `__index__`.
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
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "oct.md"
EXPECTED_BLOCKS = 7

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


class TestOneCharacterPerOctalDigit:
    """Row: `oct(x)` - O(d), one character per octal digit after a '0o' or
    '-0o' prefix."""

    @pytest.mark.parametrize("bits", [1, 2, 3, 4, 63, 64, 65, 1_000, 1_000_000])
    def test_output_length_is_the_digit_count_plus_the_prefix(self, bits: int) -> None:
        value = (1 << bits) - 1
        digits = (value.bit_length() + 2) // 3

        assert len(oct(value)) == digits + 2
        assert len(oct(-value)) == digits + 3
        assert oct(-value) == "-" + oct(value)

    def test_zero_has_one_digit(self) -> None:
        assert oct(0) == "0o0"

    @pytest.mark.serial
    def test_peak_space_is_one_to_two_bytes_per_digit(self) -> None:
        value = (1 << 1_000_000) - 1
        digits = -(-1_000_000 // 3)

        peak = traced_peak(lambda: oct(value))

        assert digits <= peak < 2 * digits, peak


class TestLinearTime:
    """Rows: `oct(x)`, `format(x, 'o')` and `int(s, 8)` - all O(d), linear in
    the digit count."""

    @pytest.mark.timing
    @pytest.mark.parametrize("operation", ["oct", "format", "int"])
    def test_time_is_linear_in_the_digit_count(self, operation: str) -> None:
        small = (1 << SMALL) - 1
        large = (1 << LARGE) - 1
        convert: Callable[[Any], Any]
        small_arg: Any
        large_arg: Any
        if operation == "oct":
            convert, small_arg, large_arg = oct, small, large
        elif operation == "format":
            convert, small_arg, large_arg = lambda value: format(value, "o"), small, large
        else:
            convert, small_arg, large_arg = partial(int, base=8), oct(small), oct(large)
        convert(large_arg)  # warm up

        ratio = best_time(lambda: convert(large_arg)) / best_time(
            lambda: convert(small_arg), loops=100
        )

        assert 20 < ratio < 1_000, f"{operation}: x{ratio:.1f} for x{LARGE // SMALL} in bits"


class TestOctalVersusDecimal:
    """Octal vs Decimal for Large Integers: str() is slower than linear and
    limited by sys.set_int_max_str_digits(); oct() and int(s, 8) are linear
    and not limited."""

    @pytest.mark.timing
    def test_str_grows_faster_than_oct(self) -> None:
        previous = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)
        try:
            small = (1 << 20_000) - 1
            large = (1 << 200_000) - 1
            str(large)  # warm up

            oct_ratio = best_time(lambda: oct(large)) / best_time(lambda: oct(small), loops=20)
            str_ratio = best_time(lambda: str(large)) / best_time(lambda: str(small), loops=20)
        finally:
            sys.set_int_max_str_digits(previous)

        assert 3 < oct_ratio < 30, f"oct: x{oct_ratio:.1f} for x10 in bits"
        assert str_ratio > 1.8 * oct_ratio, (
            f"str: x{str_ratio:.1f} against oct: x{oct_ratio:.1f} for x10 in bits"
        )

    def test_the_digit_limit_applies_to_str_only(self) -> None:
        previous = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(640)
        try:
            value = 10**1000
            text = oct(value)
            assert text == "0o" + format(value, "o")
            assert int(text, 8) == value
            assert int(text, 0) == value
            assert int(hex(value), 16) == value
            assert int(bin(value), 2) == value
            with pytest.raises(ValueError, match="limit"):
                str(value)
        finally:
            sys.set_int_max_str_digits(previous)


class TestIndexProtocol:
    """Row: `oct(obj)` with `__index__` - `__index__` + O(d); any other
    non-int raises TypeError."""

    def test_index_is_called_once(self) -> None:
        obj = CountingIndex(0o644)

        assert oct(obj) == "0o644"
        assert obj.calls == 1

    def test_bool_is_an_int(self) -> None:
        assert oct(True) == "0o1"
        assert oct(False) == "0o0"

    @pytest.mark.parametrize("value", [8.0, "8", object()])
    def test_other_types_raise(self, value: object) -> None:
        with pytest.raises(TypeError):
            oct(value)  # type: ignore[arg-type]


class TestPrefixAndParsing:
    """Rows: `format(x, 'o')` and `int(s, 8)`, `int(s, 0)`; the Do and Avoid
    lists and the Version Notes."""

    def test_format_drops_only_the_prefix(self) -> None:
        for value in [*range(100), -8, -5, 2**70]:
            assert format(value, "o") == f"{value:o}"
            assert oct(value) == ("-0o" if value < 0 else "0o") + f"{abs(value):o}"
            assert format(value, "#o") == oct(value)

    def test_slicing_a_negative_keeps_the_o(self) -> None:
        assert oct(-8)[2:] == "o10"
        assert format(-8, "o") == "-10"

    def test_base_8_and_base_0_accept_the_prefix(self) -> None:
        assert int("0o755", 8) == 493
        assert int("755", 8) == 493
        assert int("0o755", 0) == 493
        assert int(oct(-12345), 0) == -12345

    def test_plain_int_rejects_the_prefix(self) -> None:
        with pytest.raises(ValueError, match="0o755"):
            int("0o755")

    def test_an_octal_literal_needs_the_prefix(self) -> None:
        with pytest.raises(SyntaxError):
            compile("0755", "<literal>", "eval")
        assert eval(compile("0o755", "<literal>", "eval")) == 493


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
    """Every block runs in its own subprocess and asserts its own results."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        line, block = next((n, s) for n, s in _blocks() if "assert oct(4095)" in s)
        broken = block.replace("oct(4095) == '0o7777'", "oct(4095) == '0o7776'", 1)
        assert broken != block, f"the mutation matched nothing in {PAGE.name}:{line}"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
