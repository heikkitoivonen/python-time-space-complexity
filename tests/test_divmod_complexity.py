"""Tests for docs/builtins/divmod.md.

divmod() is builtin_divmod in Python/bltinmodule.c and calls PyNumber_Divmod,
which tries `type(a).__divmod__` and then `type(b).__rdivmod__`. For ints that
is long_divmod -> l_divmod in Objects/longobject.c: one-digit operands take a
fast path, larger ones schoolbook long_divrem, O(m * (n - m + 1)) for an n-bit
dividend and an m-bit divisor (O(n + m) when m > n). From v3.12.0 (v3.12.12, v3.13.11, v3.14.2),
l_divmod hands a divisor over 300 digits with a quotient over 150 digits to
Lib/_pylong.py int_divmod, documented there as O(n**1.58), Karatsuba's log2(3); v3.10.19 and
v3.11.14 have no _pylong. For floats it is float_divmod in
Objects/floatobject.c, one fmod and a floor.

Measurement scope:

* machine-size ints and floats: every stated example value, the floor rule for
  negative operands, and divmod(a, b) == (a // b, a % b);
* a small divisor: a dividend of 100,000 bits against 800,000 bits, divisor 7,
  measured x8.2 on the pinned interpreter (aarch64, CPython 3.14). The test
  accepts x3 to x24: linear predicts x8, quadratic x64;
* a divisor 64 bits shorter than the dividend, same sizes: measured x8.1,
  same bounds - the quotient is small, so the m * (n - m + 1) bound is linear;
* a divisor half the dividend's size, same sizes: measured x30 on 3.14
  (n**1.58 predicts x27). From 3.12 the test accepts x12 to x50, which rules
  out quadratic x64 at its upper end; before 3.12 it requires above x40;
* result space: the quotient of a half-size division has about n/2 bits
  (result size only; peak auxiliary space is not traced);
* one division vs two: for the half-size 800,000-bit case `(a // b, a % b)`
  measured x8.8 the time of divmod(a, b); the test requires above x1.5;
* for unrelated types whose left `__divmod__` returns NotImplemented,
  `__divmod__` and then `__rdivmod__` are called once each;
* the to_base loop calls divmod once per output digit;
* every fenced block runs in a subprocess.

Not settled here:

* Machine-size int and float rows are not timed against a size: they have none.
* "neither spelling is consistently faster" on machine-size ints is a
  statement of no claim; nothing asserts which of the two wins.
* Not varied: negative large ints (the sign fix-up is O(n + m)), a divisor longer than the
  dividend, int subclasses,
  and the exact _pylong thresholds, which are source-only above.
"""

from __future__ import annotations

import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "divmod.md"
EXPECTED_BLOCKS = 9

SMALL_BITS = 100_000
LARGE_BITS = 800_000


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 3) -> float:
    """The fastest of several runs of `loops` calls, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times) / loops


def exact_bits(bits: int, rng: random.Random) -> int:
    """A random int of exactly `bits` bits."""
    return rng.getrandbits(bits) | (1 << (bits - 1))


def size_ratio(divisor_bits: Callable[[int], int], loops: int = 3) -> float:
    """Time at LARGE_BITS over time at SMALL_BITS for the given divisor size."""
    rng = random.Random(1)
    times: list[float] = []
    for bits in (SMALL_BITS, LARGE_BITS):
        a = exact_bits(bits, rng)
        b = exact_bits(divisor_bits(bits), rng)
        times.append(best_time(lambda a=a, b=b: divmod(a, b), loops=loops))
    return times[1] / times[0]


class TestMachineSizeAndFloat:
    """Rows: machine-size ints and floats - O(1), floor quotient, remainder
    with the divisor's sign."""

    def test_matches_floor_division_and_modulo(self) -> None:
        for a in range(-20, 21):
            for b in [-7, -5, -1, 1, 3, 5, 7]:
                q, r = divmod(a, b)
                assert (q, r) == (a // b, a % b)
                assert a == b * q + r
                assert abs(r) < abs(b)
                assert r == 0 or (r > 0) == (b > 0)

    def test_floats_and_mixed_give_floats(self) -> None:
        assert divmod(17.5, 5) == (3.0, 2.5)
        assert divmod(17, 5.0) == (3.0, 2.0)
        assert all(isinstance(x, float) for x in divmod(17, 5.0))

    def test_zero_divisor_raises(self) -> None:
        with pytest.raises(ZeroDivisionError):
            divmod(5, 0)
        with pytest.raises(ZeroDivisionError):
            divmod(5.0, 0.0)


@pytest.mark.timing
class TestLargeInts:
    """Rows: large ints - O(m * (n - m + 1)), and O((n + m)^1.58) on 3.12+
    when both the divisor and the quotient are large."""

    def test_small_divisor_is_linear(self) -> None:
        ratio = size_ratio(lambda bits: 3, loops=50)

        assert 3 < ratio < 24, f"x{ratio:.1f} for x8 in bits"

    def test_divisor_near_the_dividend_is_linear(self) -> None:
        ratio = size_ratio(lambda bits: bits - 64, loops=50)

        assert 3 < ratio < 24, f"x{ratio:.1f} for x8 in bits"

    def test_half_size_divisor(self) -> None:
        ratio = size_ratio(lambda bits: bits // 2, loops=1)

        if sys.version_info >= (3, 12):
            assert 12 < ratio < 50, f"x{ratio:.1f} for x8 in bits"
        else:
            assert ratio > 40, f"x{ratio:.1f} for x8 in bits"

    def test_one_division_beats_two(self) -> None:
        rng = random.Random(2)
        a = exact_bits(LARGE_BITS, rng)
        b = exact_bits(LARGE_BITS // 2, rng)

        ratio = best_time(lambda: (a // b, a % b), loops=1) / best_time(
            lambda: divmod(a, b), loops=1
        )

        assert ratio > 1.5, f"separate // and % cost x{ratio:.2f} of divmod()"


class TestLargeIntSpace:
    """Row: large ints - O(n) space, the size of the quotient and remainder."""

    def test_results_are_bounded_by_the_dividend(self) -> None:
        rng = random.Random(3)
        a = exact_bits(LARGE_BITS, rng)
        b = exact_bits(LARGE_BITS // 2, rng)

        q, r = divmod(a, b)

        assert LARGE_BITS // 2 <= q.bit_length() <= LARGE_BITS // 2 + 1
        assert r.bit_length() <= LARGE_BITS // 2
        assert a == b * q + r


class TestOtherTypes:
    """Row: other types - calls `type(a).__divmod__`, then
    `type(b).__rdivmod__`."""

    def test_divmod_then_rdivmod(self) -> None:
        calls: list[str] = []

        class Left:
            def __divmod__(self, other: object) -> Any:
                calls.append("__divmod__")
                return NotImplemented

        class Right:
            def __rdivmod__(self, other: object) -> tuple[int, int]:
                calls.append("__rdivmod__")
                return (1, 2)

        assert divmod(Left(), Right()) == (1, 2)  # type: ignore[operator]
        assert calls == ["__divmod__", "__rdivmod__"]


class TestBaseConversion:
    """Converting to Another Base: one divmod() call per output digit."""

    def test_one_call_per_digit(self) -> None:
        calls = 0

        def counting_divmod(a: int, b: int) -> tuple[int, int]:
            nonlocal calls
            calls += 1
            return divmod(a, b)

        num = 255**7
        digits: list[int] = []
        while num:
            num, rem = counting_divmod(num, 16)
            digits.append(rem)

        assert calls == len(digits) == len(format(255**7, "x"))


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
    """Every block runs, and its asserts pin the stated values."""

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
        block = next(source for _, source in _blocks() if "divmod(-10, 3)" in source)
        broken = block.replace("== (-4, 2)", "== (-3, -1)", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
