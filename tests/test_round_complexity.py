"""Tests for docs/builtins/round.md.

round() is builtin_round in Python/bltinmodule.c: it looks up `__round__` on
the number's type and calls it with no argument when ndigits is omitted or
None, and with ndigits otherwise. float.__round__ (Objects/floatobject.c)
rounds to an int with C round() and a half-to-even fix, or, with ndigits,
returns x unchanged past NDIGITS_MAX (323), a signed zero below NDIGITS_MIN
(-308), and otherwise calls double_round: _Py_dg_dtoa in mode 3 produces the
digits down to the 10**-ndigits place, and _Py_dg_strtod reads them back.
int.__round__ (Objects/longobject.c) returns the int itself for ndigits >= 0
and otherwise computes 10**k with long_pow and rounds with
_PyLong_DivmodNear. These functions do the same work in the v3.11.14,
v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags, so no version is treated
apart.

Results, delegation and identity are settled by observation; the growth
terms need a stopwatch.

Measurement scope:

* halves: round() of 0.5, 1.5, 2.5 and -2.5, and round(0.125, 2) and
  round(0.375, 2), where the half is exact in binary, go to the even
  neighbour; round(2.675, 2) is 2.67 because the float is below the half.
* float to int: the result of round(sys.float_info.max) has 1,024 bits;
  infinities raise OverflowError and NaN raises ValueError.
* float digits: round(x, 2) is timed at x = 1.2345e3, 1.2345e30 and
  1.2345e300. The cost increase over the second interval exceeds 20x the
  first increase. Subtracting adjacent timings cancels fixed call overhead:
  linear digit processing predicts about 10x, quadratic about 100x.
  round(1.5, 300)
  costs under x3 what round(1.5, 2) does, since the expansion ends after
  one decimal.
* float ndigits limits: ndigits of 324 and 10**100 return x, and -309
  returns a zero with x's sign; an infinity or NaN with ndigits comes back
  unchanged.
* int: round(n), round(n, 0) and round(n, 10**100) return the same object;
  round(n, -2) costs x3 to x24 from a 50,000-bit int to a 400,000-bit one,
  linear predicting x8 and quadratic x64; what going from 100,000 to
  400,000 bits adds to round(n, -k) is more than x2 larger at k = 8,000
  than at k = 2,000, b·k predicting x4 and b + k x1; round(5, -k) costs more than x12 from k = 10,000
  to 80,000, linear predicting x8, and its traced peak for k = 80,000 is
  over 30,000 bytes, about the size of 10**80,000.
* delegation: a counting `__round__` receives no argument for round(x) and
  round(x, None) and the ndigits value otherwise; a type without
  `__round__` raises TypeError naming it; a float ndigits raises TypeError
  for a float and for an int, and is passed on unchanged to any other
  type's `__round__`.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The O(d) space of the float path is the digit buffer _Py_dg_dtoa
  allocates, read from Python/dtoa.c; a buffer of a few hundred bytes is
  not separated from the interpreter's own allocations by measurement.
* The float timing varies d through x's magnitude only. d set by ndigits
  is bounded by where x's exact expansion ends, and is not timed apart.
  The finite float exponent range limits the probe to hundreds of digits;
  superlinear growth here does not establish the worst-case quadratic bound,
  which follows from the digit-generation loops in Python/dtoa.c.
  A tiny abs(x) adds a scaling step inside _Py_dg_dtoa that is bounded by
  the float's exponent range and is not priced.
* The k² term of round(n, -k) is a grade-school bound; the measured growth
  of building 10**k is nearer k**1.585, from Karatsuba multiplication.
* Decimal and Fraction rounding costs are those of their own pages, and
  are tested there.
"""

from __future__ import annotations

import math
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "round.md"
EXPECTED_BLOCKS = 8


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


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class TestHalvesRoundToEven:
    """Exact halves go to the even neighbour, for whole numbers and decimal
    places; a decimal half that is not exact in binary is rounded on the
    value the float holds."""

    @pytest.mark.parametrize(
        ("value", "expected"), [(0.5, 0), (1.5, 2), (2.5, 2), (-2.5, -2), (3.5, 4)]
    )
    def test_whole_number_halves(self, value: float, expected: int) -> None:
        assert round(value) == expected

    def test_exact_decimal_halves(self) -> None:
        assert round(0.125, 2) == 0.12
        assert round(0.375, 2) == 0.38

    def test_an_inexact_half_rounds_the_stored_value(self) -> None:
        assert Decimal(2.675) < Decimal("2.675")
        assert round(2.675, 2) == 2.67


class TestFloatToInteger:
    """`round(x)` and `round(x, None)` on a float are O(1) and return an int
    of at most 1,024 bits; infinities and NaN raise."""

    def test_the_result_is_an_int(self) -> None:
        assert type(round(5.6)) is int
        assert type(round(5.6, None)) is int

    def test_the_largest_float_gives_1024_bits(self) -> None:
        assert round(sys.float_info.max).bit_length() == 1_024

    def test_infinity_overflows(self) -> None:
        with pytest.raises(OverflowError, match="infinity"):
            round(math.inf)

    def test_nan_is_a_value_error(self) -> None:
        with pytest.raises(ValueError, match="NaN"):
            round(math.nan)


class TestFloatDecimalPlaces:
    """`round(x, ndigits)` on a float is O(d²) in the digits it produces,
    O(1) for ordinary values; past the float's ndigits range, and for an
    infinity or NaN, it returns without converting."""

    @pytest.mark.timing
    def test_cost_grows_faster_than_the_digits_produced(self) -> None:
        durations = [
            best_ns(lambda x=value: round(x, 2), inner=2_000)
            for value in (1.2345e3, 1.2345e30, 1.2345e300)
        ]
        increases = [
            after - before for before, after in zip(durations, durations[1:], strict=False)
        ]

        assert increases[0] > 0, f"round: {durations} ns, increases {increases} ns"
        ratio = increases[1] / increases[0]
        assert ratio > 20, (
            f"round: {durations} ns, increases {increases} ns, increase ratio x{ratio:.1f}; "
            "linear predicts about x10 and quadratic about x100"
        )

    @pytest.mark.timing
    def test_digits_stop_where_the_expansion_ends(self) -> None:
        few_ns = best_ns(lambda: round(1.5, 2), inner=2_000)
        many_ns = best_ns(lambda: round(1.5, 300), inner=2_000)

        ratio = many_ns / few_ns
        assert ratio < 3, (
            f"ndigits=300 cost x{ratio:.2f} ndigits=2 ({few_ns:.0f}ns to {many_ns:.0f}ns) "
            "on a value whose expansion ends after one decimal"
        )
        assert round(1.5, 300) == 1.5

    @pytest.mark.parametrize("ndigits", [324, 10**100])
    def test_a_large_ndigits_returns_x(self, ndigits: int) -> None:
        assert round(1.2345e300, ndigits) == 1.2345e300
        assert round(0.1, ndigits) == 0.1

    def test_a_small_ndigits_returns_a_signed_zero(self) -> None:
        assert math.copysign(1.0, round(-3.0, -309)) == -1.0
        assert round(-3.0, -309) == 0.0
        assert round(3.0, -308) == 0.0

    def test_infinity_and_nan_come_back(self) -> None:
        assert round(math.inf, 2) == math.inf
        assert math.isnan(round(math.nan, 2))


class TestIntRounding:
    """An exact int with ndigits >= 0 is returned itself; a negative ndigits
    costs O(b·k + k²) and O(b + k) space, building 10**k even for a small
    int."""

    @pytest.mark.parametrize("ndigits", [None, 0, 3, 10**100])
    def test_non_negative_ndigits_returns_the_same_int(self, ndigits: int | None) -> None:
        n = 123_456_789_012_345_678_901_234_567_890
        assert round(n, ndigits) is n

    def test_negative_ndigits_round_half_to_even(self) -> None:
        assert round(1234, -2) == 1200
        assert round(1250, -2) == 1200
        assert round(1350, -2) == 1400
        assert round(-1250, -2) == -1200
        assert round(5, -3) == 0

    @pytest.mark.timing
    def test_a_small_k_is_linear_in_the_int(self) -> None:
        small = (1 << 50_000) - 12_345
        large = (1 << 400_000) - 12_345

        small_ns = best_ns(lambda: round(small, -2), inner=20)
        large_ns = best_ns(lambda: round(large, -2), inner=3)

        ratio = large_ns / small_ns
        assert 3 < ratio < 24, (
            f"x8 the bits cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "linear predicts x8 and quadratic x64"
        )

    @pytest.mark.timing
    def test_the_cost_per_bit_grows_with_k(self) -> None:
        narrow = (1 << 100_000) - 12_345
        wide = (1 << 400_000) - 12_345

        def extra_ns(k: int) -> float:
            """What 300,000 more bits add to round(n, -k)."""
            return best_ns(lambda: round(wide, -k), repeats=5) - best_ns(
                lambda: round(narrow, -k), repeats=5
            )

        small_k = extra_ns(2_000)
        large_k = extra_ns(8_000)

        ratio = large_k / small_k
        assert ratio > 2, (
            f"x4 the k made the extra bits cost x{ratio:.2f} ({small_k:.0f}ns to "
            f"{large_k:.0f}ns); b·k predicts x4, and b + k x1"
        )

    @pytest.mark.timing
    def test_a_small_int_still_pays_for_ten_to_the_k(self) -> None:
        small_ns = best_ns(lambda: round(5, -10_000), repeats=5)
        large_ns = best_ns(lambda: round(5, -80_000), repeats=5)

        ratio = large_ns / small_ns
        assert ratio > 12, (
            f"x8 the k on the int 5 cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "linear in k predicts x8, and a cost that ignored k x1"
        )

    @pytest.mark.serial
    def test_ten_to_the_k_is_allocated(self) -> None:
        assert round(5, -80_000) == 0
        peak = traced_peak(lambda: round(5, -80_000))
        assert peak > 30_000, f"round(5, -80_000) peaked at {peak} bytes"


class TestDelegation:
    """Any other type costs what its `__round__` does: round(x) and
    round(x, None) call it with no argument, round(x, ndigits) with ndigits.
    A type without one raises TypeError; a float and an int require an
    integer ndigits."""

    class Recorder:
        def __init__(self) -> None:
            self.calls: list[tuple[Any, ...]] = []

        def __round__(self, *args: Any) -> str:
            self.calls.append(args)
            return "rounded"

    def test_round_passes_ndigits_through(self) -> None:
        recorder = self.Recorder()

        assert round(recorder) == "rounded"  # type: ignore[call-overload]
        assert round(recorder, None) == "rounded"  # type: ignore[call-overload]
        assert round(recorder, 2) == "rounded"  # type: ignore[call-overload]
        ndigits = 1.0
        assert round(recorder, ndigits) == "rounded"  # type: ignore[call-overload]
        assert recorder.calls == [(), (), (2,), (1.0,)]
        assert recorder.calls[-1][0] is ndigits

    def test_a_type_without_round_raises(self) -> None:
        with pytest.raises(TypeError, match="__round__"):
            round("1.5")  # type: ignore[call-overload]

    @pytest.mark.parametrize("number", [1.5, 10], ids=["float", "int"])
    def test_a_float_ndigits_is_rejected(self, number: float) -> None:
        with pytest.raises(TypeError, match="cannot be interpreted as an integer"):
            round(number, 1.0)  # type: ignore[call-overload]


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
        encoding="utf-8",
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own results."""

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
        line, source = next((n, s) for n, s in _blocks() if "round(1250, -2) == 1200" in s)
        mutated = source.replace("round(1250, -2) == 1200", "round(1250, -2) == 1300", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
