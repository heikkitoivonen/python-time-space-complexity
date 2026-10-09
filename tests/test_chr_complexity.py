"""Tests for docs/builtins/chr.md.

chr() is builtin_chr in Python/bltinmodule.c and ends in PyUnicode_FromOrdinal,
which range-checks the value and returns a one-character string: a cached
singleton below 256, a new string otherwise. The argument is converted
differently across the supported range:

* v3.10.19, v3.11.14 and v3.12.12 use the Argument Clinic `int` converter, so
  an int outside the C `int` range raises OverflowError before the range check;
* v3.13.11 and v3.14.2 call PyLong_AsLongAndOverflow and clamp an overflowing
  value, so every out-of-range int raises ValueError (gh-76763, from 3.13.0).

Both paths call `__index__` once and stop converting an int after the few
digits that overflow a C long, so a huge argument is rejected in O(1).

Measurement scope:

* every code point from 0 to 0x10FFFF, surrogates included, gives a string of
  length one that ord() maps back;
* the out-of-range exception type and message, for -1, 0x110000, 2**31,
  -(2**31) - 1 and ±2**100, with the type chosen by the running version;
* time: rejecting a 10,000,000-bit int against a 100-bit one measured x1.0 on
  the pinned interpreter (aarch64, CPython 3.14). The test accepts under x10;
  conversion linear in the int's size would predict x100,000;
* space: tracemalloc's peak for chr(0x10FFFF) and for rejecting the
  10,000,000-bit int is under 1 KiB;
* `__index__`: a counting `__index__` is called once per chr() call, and a
  float, a str and an object without `__index__` raise TypeError;
* `''.join(map(chr, codes))`: a hundredfold step in the number of code points,
  10,000 to 1,000,000, measured x171. The test accepts x20 to x1,000: a
  constant-time claim predicts x1 and a quadratic one x10,000;
* a literal compiles to a constant while chr(65) compiles to a call;
* every stated example value, and every fenced block runs in a subprocess.

Not settled here:

* The O(1) rows for a valid code point are not timed against a size: chr()
  takes one integer, and the only size it has is the argument's magnitude,
  which the out-of-range timing covers.
* "Calling chr() on a constant code point; write the literal instead" is advice
  resting on the literal-is-a-constant test, not a measured speed difference.
* Not varied: int subclasses, which are converted without `__index__`, and the
  mix of code points in the join timing (all below 0x110000, most above 255).
"""

from __future__ import annotations

import dis
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import unicodedata
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "chr.md"
EXPECTED_BLOCKS = 16

OUT_OF_RANGE = "chr() arg not in range(0x110000)"


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


REJECTED = ValueError if sys.version_info >= (3, 13) else OverflowError


def reject(value: int) -> None:
    """Call chr() on an int beyond the C int range, which must raise."""
    try:
        chr(value)
    except REJECTED:
        return
    raise AssertionError(f"chr() accepted {value}")


class CountingIndex:
    """An object usable as an integer, counting its `__index__` calls."""

    def __init__(self, value: int) -> None:
        self.value = value
        self.calls = 0

    def __index__(self) -> int:
        self.calls += 1
        return self.value


class TestValidCodePoint:
    """Row: Valid code point - O(1), any code point from 0 to 0x10FFFF,
    surrogates included."""

    def test_every_code_point_gives_one_character(self) -> None:
        for code in range(0x110000):
            char = chr(code)
            assert len(char) == 1
            assert ord(char) == code

    def test_surrogates_are_returned_but_do_not_encode(self) -> None:
        surrogate = chr(0xD800)

        assert unicodedata.category(surrogate) == "Cs"
        with pytest.raises(UnicodeEncodeError):
            surrogate.encode("utf-8")

    @pytest.mark.serial
    def test_peak_space_is_constant(self) -> None:
        peak = traced_peak(lambda: chr(0x10FFFF))

        assert peak < 1024, peak


class TestOutOfRange:
    """Row: Out of range - O(1), ValueError; an int beyond the C int range
    raised OverflowError before Python 3.13."""

    @pytest.mark.parametrize("value", [-1, 0x110000])
    def test_near_the_range_raises_value_error(self, value: int) -> None:
        with pytest.raises(ValueError, match=re.escape(OUT_OF_RANGE)):
            chr(value)

    @pytest.mark.parametrize("value", [2**31, -(2**31) - 1, 2**100, -(2**100)])
    def test_beyond_the_c_int_range(self, value: int) -> None:
        message = OUT_OF_RANGE if REJECTED is ValueError else "too large to convert to C int"
        with pytest.raises(REJECTED, match=re.escape(message)):
            chr(value)

    @pytest.mark.timing
    def test_a_huge_int_is_rejected_in_constant_time(self) -> None:
        small = 1 << 100
        large = 1 << 10_000_000

        ratio = best_time(lambda: reject(large), loops=200) / best_time(
            lambda: reject(small), loops=200
        )

        assert ratio < 10, f"x{ratio:.1f} for x100,000 in bits"

    @pytest.mark.serial
    def test_a_huge_int_is_rejected_in_constant_space(self) -> None:
        large = 1 << 10_000_000

        peak = traced_peak(lambda: reject(large))

        assert peak < 1024, peak


class TestIndexProtocol:
    """Row: Object with `__index__` - `__index__` + O(1); any other non-int
    raises TypeError."""

    def test_index_is_called_once(self) -> None:
        obj = CountingIndex(66)

        assert chr(obj) == "B"
        assert obj.calls == 1

    def test_bool_is_an_int(self) -> None:
        assert chr(True) == "\x01"
        assert chr(False) == "\x00"

    @pytest.mark.parametrize("value", [65.0, "65", object()])
    def test_other_types_raise(self, value: object) -> None:
        with pytest.raises(TypeError):
            chr(value)  # type: ignore[arg-type]


class TestManyCodePoints:
    """Row: n code points to a string - O(n), and the generator and map()
    spellings build the same string."""

    def test_both_spellings_agree(self) -> None:
        codes = [72, 101, 108, 108, 111, 960, 0x1F600, 0x10FFFF]

        assert "".join(chr(c) for c in codes) == "".join(map(chr, codes))
        assert len("".join(map(chr, codes))) == len(codes)

    @pytest.mark.timing
    def test_join_map_is_linear_in_the_code_points(self) -> None:
        small = list(range(10_000))
        large = list(range(1_000_000))
        "".join(map(chr, large))  # warm up

        ratio = best_time(lambda: "".join(map(chr, large))) / best_time(
            lambda: "".join(map(chr, small)), loops=100
        )

        assert 20 < ratio < 1_000, f"x{ratio:.1f} for x100 in code points"


class TestLiteral:
    """vs String Literals: a literal is a constant, chr() is a call."""

    def test_a_literal_compiles_to_a_constant(self) -> None:
        literal = list(dis.get_instructions(compile("'A'", "<s>", "eval")))
        call = [i.opname for i in dis.get_instructions(compile("chr(65)", "<s>", "eval"))]

        assert any("CONST" in i.opname and i.argval == "A" for i in literal), literal
        assert not any(i.opname.startswith("CALL") for i in literal), literal
        assert any(name.startswith("CALL") for name in call), call


class TestStatedExampleValues:
    """The values the page's comments give, checked rather than trusted."""

    def test_basic_usage(self) -> None:
        expected = {
            65: "A",
            97: "a",
            48: "0",
            32: " ",
            960: "π",
            8364: "€",
            20013: "中",
            128512: "😀",
            10: "\n",
            9: "\t",
            0: "\0",
            92: "\\",
            233: "é",
            241: "ñ",
            223: "ß",
        }
        for code, char in expected.items():
            assert chr(code) == char

    def test_named_high_code_points(self) -> None:
        assert unicodedata.name(chr(119808)) == "MATHEMATICAL BOLD CAPITAL A"
        assert unicodedata.name(chr(127925)) == "MUSICAL NOTE"
        assert chr(127) == "\x7f"
        assert chr(0x10FFFF) == "\U0010ffff"

    def test_ord_round_trip(self) -> None:
        assert ord("A") == 65
        assert ord(chr(90)) == 90
        assert chr(ord("Z")) == "Z"

    def test_common_patterns(self) -> None:
        codes = [72, 101, 108, 108, 111]
        assert [chr(c) for c in codes] == ["H", "e", "l", "l", "o"]
        assert "".join(map(chr, codes)) == "Hello"
        assert "".join(chr(cp) for cp in range(65, 91)) == "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        assert "".join(chr(ord(c) + 3) for c in "ABC") == "DEF"
        assert "".join(chr(ord(c) - 3) for c in "DEF") == "ABC"
        assert "".join(chr(i) for i in range(ord("a"), ord("z") + 1)) == (
            "abcdefghijklmnopqrstuvwxyz"
        )
        ascii_chars = {i: chr(i) for i in range(32, 127)}
        assert (ascii_chars[32], ascii_chars[33], ascii_chars[34]) == (" ", "!", '"')
        assert ascii_chars[126] == "~"

    def test_character_ranges_hold_one_character_per_code_point(self) -> None:
        for start, end in [(0x0370, 0x03FF), (0x1F300, 0x1F600)]:
            assert len("".join(chr(i) for i in range(start, end + 1))) == end - start + 1


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

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "chr(0x110000)" in source)
        broken = block.replace("except ValueError:", "except TypeError:", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ValueError" in result.stderr
