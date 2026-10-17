"""Tests for docs/builtins/pow.md.

Integer powers with abs(x) >= 2 and y > 0 have result width r = Θ(b * y), so
result size and traced allocation settle their space rows without a stopwatch;
time needs one, framed for the widest gap measured. Modular powers are settled
the same way, one size variable at a time: base width, positive and negative
exponent width, and modulus width, each varied with the others held fixed.

The grade-school upper bounds follow long_pow, long_invmod and l_mod in
Objects/longobject.c. long_pow does the same work in the v3.11.14, v3.12.12,
v3.13.11, v3.14.2 and v3.15.0rc3 tags, so no version is treated apart. Initial
division of a b-bit base by an m-bit modulus costs O(b*m); the remaining
inversion costs O(m²), and O(e) modular steps cost O(e*m²). The measurements
below cover each size dimension; they do not prove those asymptotic bounds.

Measurement scope:

* integer powers: result width 64,000 and 256,000 bits for a 64-bit base at
  y = 1,000 and 4,000; widths for bases ±2 and ±3 lie between (b - 1) * y + 1
  and b * y for odd and even y; sys.getsizeof grows x4 for x4 in y, and is the
  same for x4 in the base's width at a quarter of the exponent.
* integer power time: x4 in y costs between x5 and x30 (log predicts x1, linear
  x4, grade-school squaring x16); x8 in the base's bits at fixed y costs over
  x8, where a bound in y alone predicts x1.
* bases 0, 1 and -1: the traced peak does not grow from a 101-bit exponent to a
  10,001-bit one, while time grows between x10 and x300, so the exponent is
  scanned.
* converting an int to a float, for y < 0 or a float operand: rejecting
  2**10_000_000 costs between x20 and x1,000 the time of 2**100_000, as the
  base of pow(x, -1), as the negative exponent of pow(2, y), and as either
  operand of a power with the float 2.0; linear predicts x100 and constant x1.
  A power of two is the worst case; most ints stop the scan after a few
  digits, which tests/test_float_func_complexity.py measures. The traced peak
  of pow(x, -1) does not grow from an 11-bit base to a 1,001-bit one.
* float powers: pow(1.0000001, 3.7) and pow(1.7e308, 0.99) cost within x5 of
  each other, and a negative base with a fractional exponent gives a
  complex.
* modular powers: a base of 10,001 then 1,000,001 bits against a 128-bit
  modulus raises the traced peak x30 to x200 and the time x10 to x300; with a
  reduced base and a 1,024-bit modulus the peak stays under 4m bytes and under
  x2 for x10 in y, while the two-step form's peak grows x5 to x20; x2 in the
  exponent's bits costs x1.3 to x3.5, and x4 in the modulus' bits over x6.
* modular inverse: negative exponents of 10,001 and 1,000,001 bits raise the
  peak x30 to x200 against modulus 1009, while positive exponents of the same
  widths leave it flat.
* reducing during or after: at 42**65537 mod 10**9+7 the intermediate is
  353,397 bits against a 30-bit modulus; the two-step form peaks over x100 the
  three-argument one and costs over x50 in time.
* powers of two: pow(2, 10**6) == 1 << 10**6; the shift costs under x30 for x10
  in n and pow() over x100 the shift; a dense 64-bit base costs over x3 a power
  of two at about the same result width, which is why the growth tests use one.
* pow(x, 1) returns a new object, whose traced peak grows over x50 from a
  1,001-bit base to a 100,001-bit one.
* `x ** y`: equal results for int and float operands; `2 ** 8` compiles with
  no BINARY_OP, `2 ** 1000` keeps one, and `pow(2, 8)` stays a call.
* delegation: Decimal, Fraction and complex results; a recording int subclass's
  `__pow__` receives the modulus. `__rpow__` dispatch is not exercised.
* every value and exception the page's blocks state, every block run in its own
  subprocess, and a flipped assertion in one shown to fail.

Not settled here:

* The release that introduced the modular inverse and the keyword arguments
  (3.8) and the integer-to-string limit (3.11 and 3.10.7): every supported
  interpreter has all three, so the tests assert the features, not the
  release.
* The O(r²) row is an upper bound: pow(2, n) measures about n^1.15 in the result
  width where a 64-bit base measures n^1.59, so a power-of-two base sits far
  below it, and Karatsuba multiplication keeps any wide base below it.
* Not varied: operand types other than int and float are checked for
  delegation only, and the base shape in the modular probes (2**k + 1) and the
  modulus width in the base-width probes (128 bits) stay fixed.
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
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

WORD = (1 << 64) - 59
"""A 64-bit base that is not a power of two, so its powers are dense."""


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[[], Any]) -> int:
    """Return the peak bytes tracemalloc attributes to one call.

    The first call is discarded so that a one-time allocation it may make
    cannot land in whichever measurement runs first in a process."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class TestIntegerPowerWidth:
    """The `pow(x, y)`, integers, `abs(x) >= 2`, `y > 0` row: O(r²) time and
    Θ(r) space for a result of r = Θ(b * y) bits, and the row for bases 0, 1
    and -1."""

    def test_result_width_is_linear_in_the_exponent(self) -> None:
        assert pow(WORD, 1_000).bit_length() == pytest.approx(64_000, rel=0.01)
        assert pow(WORD, 4_000).bit_length() == pytest.approx(256_000, rel=0.01)

    @pytest.mark.parametrize("base", [2, 3, -2, -3])
    def test_growing_results_at_the_unit_base_boundary(self, base: int) -> None:
        """For b-bit bases of magnitude at least two, the width lies between
        (b - 1) * y + 1 and b * y. Both exponent parities are covered.
        """
        bits = base.bit_length()
        for exponent in (1, 100, 101, 10_000):
            width = pow(base, exponent).bit_length()
            assert (bits - 1) * exponent + 1 <= width <= bits * exponent

    @pytest.mark.parametrize("base", [0, 1, -1])
    @pytest.mark.parametrize("odd", [False, True])
    def test_bounded_results_do_not_allocate_with_exponent_width(
        self, base: int, odd: bool
    ) -> None:
        """100x the exponent bits, with fixed base and parity, leaves O(1) space.

        Inputs are allocated before tracing. This checks result size and peak
        workspace separately; it does not infer running time from result size.
        """
        exponents = [(1 << bits) + odd for bits in (100, 10_000)]
        expected = 0 if base == 0 else (-1 if base == -1 and odd else 1)
        for exponent in exponents:
            result = pow(base, exponent)
            assert result == expected
            assert result.bit_length() <= 1
        peaks = [traced_peak(lambda y=y: pow(base, y)) for y in exponents]
        assert peaks[1] <= peaks[0] + 512, f"bounded-result peak grew: {peaks}"

    @pytest.mark.timing
    @pytest.mark.parametrize("base", [0, 1, -1])
    def test_bounded_results_still_scan_the_exponent(self, base: int) -> None:
        """100x the exponent bits costs about 70x on CPython 3.14.

        The odd, sparse exponent shape and base stay fixed. A constant-time
        parity shortcut would give a ratio near one.
        """
        small_exp, large_exp = (1 << 100) + 1, (1 << 10_000) + 1
        small = best_time(lambda: [pow(base, small_exp) for _ in range(100)])
        large = best_time(lambda: [pow(base, large_exp) for _ in range(100)])
        assert 10 < large / small < 300, f"exponent scan: {small:.2e}s vs {large:.2e}s"

    def test_result_space_is_linear_in_the_exponent(self) -> None:
        """Θ(r), not the O(1) a logarithmic reading would imply."""
        small = sys.getsizeof(pow(WORD, 1_000))
        large = sys.getsizeof(pow(WORD, 4_000))

        assert large / small == pytest.approx(4.0, rel=0.05), (
            f"x4 in the exponent gave {small} then {large} bytes"
        )

    def test_result_space_is_linear_in_the_base_width(self) -> None:
        """The same r, reached by widening the base instead of the exponent."""
        by_exponent = sys.getsizeof(pow(WORD, 4_000))
        by_base = sys.getsizeof(pow((1 << 256) - 59, 1_000))

        assert by_base / by_exponent == pytest.approx(1.0, rel=0.05), (
            f"equal r gave {by_exponent} then {by_base} bytes"
        )

    @pytest.mark.timing
    def test_time_is_superlinear_in_the_result_width(self) -> None:
        """x4 in y measured x9.1. A log bound predicts x1, a linear one x4."""
        small = best_time(lambda: pow(WORD, 2_500))
        large = best_time(lambda: pow(WORD, 10_000))
        ratio = large / small

        assert ratio > 5.0, (
            f"x4 in the exponent cost only x{ratio:.2f} "
            f"({small:.2e}s then {large:.2e}s) - that is not superlinear"
        )
        assert ratio < 30.0, (
            f"x4 in the exponent cost x{ratio:.2f}, worse than the grade-school "
            f"x16 ({small:.2e}s then {large:.2e}s)"
        )

    @pytest.mark.timing
    def test_the_base_width_is_a_size_variable_of_its_own(self) -> None:
        """Holding y fixed, x8 in the base's bits measured x22. A bound written
        in the exponent alone predicts x1."""
        narrow = best_time(lambda: pow(WORD, 2_000))
        wide = best_time(lambda: pow((1 << 512) - 59, 2_000))
        ratio = wide / narrow

        assert ratio > 8.0, (
            f"x8 in the base's width cost only x{ratio:.2f} at a fixed exponent "
            f"({narrow:.2e}s then {wide:.2e}s)"
        )


def reject_ratio(power: Callable[[int], Any], sign: int = 1) -> float:
    """Time to reject 2**10_000_000 over time to reject 2**100_000.

    Converting an int to a float scans its bits below the top 55 until one is
    nonzero, so a power of two is read in full: linear predicts x100."""

    def reject(value: int) -> Callable[[], None]:
        def run() -> None:
            for _ in range(3):
                try:
                    power(value)
                except OverflowError:
                    continue
                raise AssertionError("an int beyond the float range was converted")

        return run

    small, large = sign * (1 << 100_000), sign * (1 << 10_000_000)
    return best_time(reject(large)) / best_time(reject(small))


class TestNegativeIntegerExponent:
    """The `pow(x, y)`, integers, `y < 0` row: via float, O(b + e) at worst, and
    OverflowError once the base leaves float range."""

    @pytest.mark.timing
    def test_converting_a_power_of_two_base_is_linear(self) -> None:
        ratio = reject_ratio(lambda base: pow(base, -1))

        assert 20 < ratio < 1_000, f"100x the base bits cost x{ratio:.1f}; linear is x100"

    @pytest.mark.timing
    def test_converting_a_power_of_two_exponent_is_linear(self) -> None:
        ratio = reject_ratio(lambda exponent: pow(2, exponent), sign=-1)

        assert 20 < ratio < 1_000, f"100x the exponent bits cost x{ratio:.1f}; linear is x100"

    def test_returns_a_float(self) -> None:
        assert pow(2, -1) == 0.5
        assert isinstance(pow(2, -1), float)
        assert pow(2, -2) == 0.25

    def test_a_base_wider_than_a_float_overflows_with_the_stated_message(self) -> None:
        with pytest.raises(OverflowError, match="too large to convert to float"):
            pow(10**1000, -1)

    def test_the_float_path_allocates_nothing_that_grows_with_the_base(self) -> None:
        """O(1) space: a 1,001-bit base peaks no higher than an 11-bit one."""
        bases = [(1 << 10) + 1, (1 << 1_000) + 1]
        for base in bases:
            assert isinstance(pow(base, -1), float)
        peaks = [traced_peak(lambda x=x: pow(x, -1)) for x in bases]

        assert peaks[1] <= peaks[0] + 512, f"float-path peaks grew with the base: {peaks}"


class TestFloatPower:
    """The `pow(x, y)`, float base or exponent row: fixed-precision arithmetic,
    O(1) either way; an int
    on the other side is converted first, O(b) or O(e) at worst."""

    def test_stated_values(self) -> None:
        assert pow(2.0, 3) == 8.0
        assert pow(2.5, 2) == 6.25
        assert pow(2.0, 0.5) == 1.4142135623730951
        assert pow(1.7e308, 0.99) == pytest.approx(1.4065152073912217e305)

    def test_a_negative_base_with_a_fractional_exponent_is_complex(self) -> None:
        result = pow(-8, 1 / 3)

        assert isinstance(result, complex)
        assert result == pytest.approx(1 + 1.7320508075688772j)

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "power",
        [lambda exponent: pow(2.0, exponent), lambda base: pow(base, 2.0)],
        ids=["int exponent", "int base"],
    )
    def test_an_int_operand_is_converted_in_linear_time_at_worst(
        self, power: Callable[[int], Any]
    ) -> None:
        ratio = reject_ratio(power)

        assert 20 < ratio < 1_000, f"100x the int's bits cost x{ratio:.1f}; linear is x100"

    @pytest.mark.timing
    def test_cost_is_independent_of_magnitude(self) -> None:
        small = best_time(lambda: [pow(1.0000001, 3.7) for _ in range(10_000)])
        large = best_time(lambda: [pow(1.7e308, 0.99) for _ in range(10_000)])
        ratio = max(small, large) / min(small, large)

        assert ratio < 5.0, (
            f"float pow varied by x{ratio:.2f} across 300 orders of magnitude "
            f"({small:.2e}s vs {large:.2e}s)"
        )


class TestModularExponentiation:
    """Base preprocessing and modular arithmetic, with independent size probes."""

    EXPONENT = (1 << 256) + 1
    MODULUS = (1 << 1024) - 159

    @pytest.mark.parametrize("exponent", [2, -2])
    @pytest.mark.parametrize("sign", [1, -1])
    def test_wide_base_preprocessing_allocates_with_base_width(
        self, exponent: int, sign: int
    ) -> None:
        """Fixed exponent and 128-bit modulus isolate the base-width term.

        Bases of 10,001 and 1,000,001 bits yield peaks around 2,752 and
        266,752 bytes on CPython 3.14. Both base and exponent signs are covered;
        the base shape and modulus width do not vary.
        """
        modulus = (1 << 128) - 159
        bases = [sign * ((1 << bits) + 1) for bits in (10_000, 1_000_000)]
        for base in bases:
            assert pow(base, exponent, modulus) == pow(base % modulus, exponent, modulus)
        peaks = [traced_peak(lambda x=x: pow(x, exponent, modulus)) for x in bases]
        assert 30 < peaks[1] / peaks[0] < 200, f"base preprocessing peaks: {peaks}"

    @pytest.mark.timing
    @pytest.mark.parametrize("exponent", [2, -2])
    def test_wide_base_preprocessing_time_tracks_base_width(self, exponent: int) -> None:
        """100x the base width costs about 60–110x at fixed y and m on 3.14.

        Base construction is excluded. The modulus is fixed at 128 bits;
        this does not measure the joint growth of b and m.
        """
        modulus = (1 << 128) - 159
        small_base, large_base = (1 << 10_000) + 1, (1 << 1_000_000) + 1
        small = best_time(lambda: pow(small_base, exponent, modulus))
        large = best_time(lambda: pow(large_base, exponent, modulus))
        assert 10 < large / small < 300, f"base preprocessing: {small:.2e}s vs {large:.2e}s"

    def test_stated_values(self) -> None:
        assert pow(2, 10, 1000) == 24
        assert pow(3, 100, 7) == 4
        assert pow(2, 1000, 13) == 3

    def test_reduced_base_workspace_is_bounded_by_modulus_width(self) -> None:
        """With a reduced base, workspace stays O(m); the two-step form
        allocates the whole power. Tracing measures total peak bytes, not
        the bit width of each arithmetic intermediate."""
        modular = traced_peak(lambda: pow(3, 100_000, self.MODULUS))
        naive = traced_peak(lambda: (3**100_000) % self.MODULUS)

        assert modular < 4 * self.MODULUS.bit_length(), (
            f"pow(3, 100000, z) allocated {modular} traced bytes for a "
            f"{self.MODULUS.bit_length()}-bit modulus"
        )
        assert naive / modular > 20, f"the two-step form peaked at {naive} bytes against {modular}"

    def test_the_traced_peak_does_not_grow_with_the_exponent(self) -> None:
        """With fixed reduced base and modulus, x10 in positive y leaves
        modular workspace bounded and multiplies the two-step peak by ten."""
        modular = [traced_peak(lambda y=y: pow(3, y, self.MODULUS)) for y in (10**5, 10**6)]
        naive = [traced_peak(lambda y=y: (3**y) % self.MODULUS) for y in (10**5, 10**6)]

        assert modular[1] / modular[0] < 2.0, f"modular peak tracked y: {modular}"
        assert 5.0 < naive[1] / naive[0] < 20.0, (
            f"two-step peak did not track the exponent: {naive}"
        )

    def test_the_result_is_bounded_by_the_modulus(self) -> None:
        """The result width is at most m; this does not measure workspace."""
        assert pow(3, 10**6, self.MODULUS).bit_length() <= self.MODULUS.bit_length()

    def test_a_negative_modulus_gives_its_sign_or_zero(self) -> None:
        assert pow(2, 10, -1000) == -976
        assert pow(2, 3, -8) == 0

    def test_a_zero_modulus_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be 0"):
            pow(2, 10, 0)

    def test_a_float_operand_with_a_modulus_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="all arguments are integers"):
            # The type checker rejects these too; the page documents the
            # runtime behaviour, so the calls have to reach the interpreter.
            pow(2.0, 3, 5)  # pyright: ignore[reportCallIssue, reportArgumentType]
        with pytest.raises(TypeError, match="all arguments are integers"):
            pow(2, 3.0, 5)  # pyright: ignore[reportCallIssue, reportArgumentType]

    @pytest.mark.timing
    def test_time_is_linear_in_the_exponents_bits(self) -> None:
        """x2 in log y measured x2.03 - the one place a logarithm is a time
        bound, because the modulus caps the operand width."""
        small = best_time(lambda: pow(3, self.EXPONENT, self.MODULUS))
        large = best_time(lambda: pow(3, (1 << 512) + 1, self.MODULUS))
        ratio = large / small

        assert 1.3 < ratio < 3.5, (
            f"x2 in the exponent's bits cost x{ratio:.2f} ({small:.2e}s then {large:.2e}s)"
        )

    @pytest.mark.timing
    def test_time_is_superlinear_in_the_modulus_bits(self) -> None:
        """x4 in m measured x13.4: the m² term. Linear would give x4."""
        small = best_time(lambda: pow(3, self.EXPONENT, self.MODULUS))
        large = best_time(lambda: pow(3, self.EXPONENT, (1 << 4096) - 159))
        ratio = large / small

        assert ratio > 6.0, (
            f"x4 in the modulus' bits cost only x{ratio:.2f}, which is no worse "
            f"than linear ({small:.2e}s then {large:.2e}s)"
        )


class TestModularInverse:
    """The `pow(x, y, z), y < 0` row, and the Modular Inverse section."""

    def test_the_inverse_round_trips(self) -> None:
        assert pow(3, -1, 1000) == 667
        assert 3 * 667 % 1000 == 1

    def test_negative_exponent_copy_allocates_with_exponent_width(self) -> None:
        """Fixed base 2 and modulus 1009 isolate the negative-exponent copy.

        Exponents have 10,001 and 1,000,001 bits, allocated before tracing.
        Negative peaks are about 1,360 and 133,360 bytes on CPython 3.14;
        positive exponents of the same widths are the control.
        """
        positive = [1 << bits for bits in (10_000, 1_000_000)]
        negative = [-y for y in positive]
        positive_peaks = [traced_peak(lambda y=y: pow(2, y, 1009)) for y in positive]
        negative_peaks = [traced_peak(lambda y=y: pow(2, y, 1009)) for y in negative]
        assert positive_peaks[1] <= positive_peaks[0] + 512, positive_peaks
        assert 30 < negative_peaks[1] / negative_peaks[0] < 200, negative_peaks
        assert negative_peaks[1] > 20 * (positive_peaks[1] + 512)

    def test_a_negative_exponent_below_minus_one_inverts_then_exponentiates(self) -> None:
        assert pow(3, -5, 1000) == 107
        assert pow(3, -5, 1000) == pow(pow(3, -1, 1000), 5, 1000)

    def test_a_base_sharing_a_factor_with_the_modulus_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="not invertible"):
            pow(4, -1, 8)

    def test_the_inverse_is_bounded_by_the_modulus(self) -> None:
        """The inverse result fits in m bits; exponent-copy space is separate."""
        modulus = (1 << 1024) - 159

        assert pow(3, -1, modulus).bit_length() <= modulus.bit_length()


class TestThreeArgumentFormVersusReducingAfterwards:
    """The Reducing During or After section: the three-argument form wins once
    the full power is much wider than the modulus.

    The divergence is a width, so both halves are observable. Only the final
    timing uses a stopwatch, and there the gap is four orders of magnitude."""

    MESSAGE, EXPONENT, MODULUS = 42, 65537, 10**9 + 7

    def test_a_small_power_is_barely_wider_than_the_modulus(self) -> None:
        """The page's 11-bit power against a 10-bit modulus: widths only."""
        assert (2**10).bit_length() == 11
        assert (1000).bit_length() == 10
        assert pow(2, 10, 1000) == (2**10) % 1000 == 24

    def test_a_large_power_diverges_in_width(self) -> None:
        intermediate = pow(self.MESSAGE, self.EXPONENT).bit_length()

        assert intermediate == 353_397
        assert self.MODULUS.bit_length() == 30
        assert intermediate / self.MODULUS.bit_length() > 10_000

    def test_a_large_power_diverges_in_allocation(self) -> None:
        modular = traced_peak(lambda: pow(self.MESSAGE, self.EXPONENT, self.MODULUS))
        naive = traced_peak(lambda: (self.MESSAGE**self.EXPONENT) % self.MODULUS)

        assert modular < 1_000, (
            f"the three-argument form peaked at {modular} bytes for a 30-bit modulus"
        )
        assert naive / modular > 100, f"the two-step form peaked at {naive} bytes against {modular}"

    def test_both_forms_agree(self) -> None:
        assert pow(self.MESSAGE, self.EXPONENT, self.MODULUS) == 115_812_009
        assert (self.MESSAGE**self.EXPONENT) % self.MODULUS == 115_812_009

    @pytest.mark.timing
    def test_a_large_power_diverges_in_time(self) -> None:
        """Measured x19,000. The threshold excludes any constant-factor story."""
        modular = best_time(lambda: pow(self.MESSAGE, self.EXPONENT, self.MODULUS))
        naive = best_time(lambda: (self.MESSAGE**self.EXPONENT) % self.MODULUS)
        ratio = naive / modular

        assert ratio > 50.0, (
            f"the two-step form cost only x{ratio:.1f} ({modular:.2e}s vs {naive:.2e}s)"
        )


class TestExactPowersOfTwo:
    """The Exact Powers of Two section: a shift is Θ(n) and squares nothing."""

    N = 1_000_000

    def test_the_two_spellings_agree(self) -> None:
        assert pow(2, self.N) == 1 << self.N

    @pytest.mark.timing
    def test_a_power_of_two_base_costs_less_than_a_dense_one(self) -> None:
        """Both calls build a result of about 1,000,000 bits; the power of two measured
        x12 cheaper, which is why the timing tests above use a 64-bit base."""
        power_of_two = best_time(lambda: pow(2, 1_000_000))
        dense = best_time(lambda: pow(WORD, 1_000_000 // 64))

        assert dense / power_of_two > 3.0, (
            f"a dense base cost only x{dense / power_of_two:.2f} of a power of "
            f"two at the same width ({power_of_two:.2e}s vs {dense:.2e}s)"
        )

    @pytest.mark.timing
    def test_the_shift_is_far_from_quadratic(self) -> None:
        """x10 in n costs under x30, where quadratic predicts x100. Fixed
        overhead keeps one step from separating linear from slightly
        superlinear; the next test separates the shift from pow(2, n)."""
        small = best_time(lambda: 1 << 100_000)
        large = best_time(lambda: 1 << 1_000_000)
        ratio = large / small

        assert ratio < 30.0, (
            f"x10 in n cost x{ratio:.2f}, near quadratic ({small:.2e}s then {large:.2e}s)"
        )

    @pytest.mark.timing
    def test_the_shift_beats_the_squaring_loop(self) -> None:
        """Measured x2,463 at n = 1e6, with a power-of-two base for pow()."""
        shift = best_time(lambda: 1 << self.N)
        squaring = best_time(lambda: pow(2, self.N))
        ratio = squaring / shift

        assert ratio > 100.0, (
            f"pow(2, n) cost only x{ratio:.1f} of the shift ({shift:.2e}s vs {squaring:.2e}s)"
        )


class TestThePowerOperator:
    """The `x ** y` row: one operation with `pow(x, y)`, and a literal power is
    folded at compile time only when its result is small."""

    def test_the_two_spellings_agree(self) -> None:
        assert pow(2, 10) == 2**10
        assert pow(2.5, 2) == 2.5**2
        assert pow(WORD, 50) == WORD**50

    @staticmethod
    def _opnames(source: str) -> set[str]:
        return {op.opname for op in dis.get_instructions(compile(source, "<doc>", "eval"))}

    def test_a_small_literal_power_is_folded_at_compile_time(self) -> None:
        assert "BINARY_OP" not in self._opnames("2 ** 8")
        assert "BINARY_OP" in self._opnames("2 + x"), "the probe must see a run-time BINARY_OP"

    def test_a_wide_literal_power_is_computed_at_run_time(self) -> None:
        assert "BINARY_OP" in self._opnames("2 ** 1000")

    def test_pow_with_literals_is_still_a_call(self) -> None:
        assert any(name.startswith("CALL") for name in self._opnames("pow(2, 8)"))


class TestDelegationToOtherTypes:
    """The `pow(x, y)`, any other type row: the operand types' `__pow__` and
    `__rpow__` carry the cost; only `__pow__` is checked here."""

    def test_decimal_fraction_and_complex(self) -> None:
        assert pow(Decimal("2"), 3) == Decimal(8)
        assert pow(Fraction(1, 2), 3) == Fraction(1, 8)
        assert pow(1j, 2) == pytest.approx(-1 + 0j)

    def test_a_complex_modulus_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="complex modulo"):
            pow(1j, 2, 3)  # pyright: ignore[reportCallIssue, reportArgumentType]

    def test_the_modulus_is_forwarded_to_dunder_pow(self) -> None:
        """Three arguments reach the type, so a third argument is its problem
        and not an int-only feature of pow()."""
        seen: list[tuple[Any, Any]] = []

        class Recording(int):
            def __pow__(self, exp: Any, mod: Any = None) -> str:  # type: ignore[override]
                seen.append((exp, mod))
                return "delegated"

        assert pow(Recording(2), 3, 5) == "delegated"
        assert seen == [(3, 5)]


class TestKeywordArguments:
    """The 3.8 entry in Version Notes: base, exp and mod are keyword-capable."""

    def test_every_parameter_accepts_its_keyword(self) -> None:
        assert pow(base=2, exp=3) == 8
        assert pow(2, exp=3, mod=5) == 3
        assert pow(base=3, exp=-1, mod=1000) == 667


class TestEdgeCaseResults:
    """Every value and exception the Edge Cases section states."""

    def test_a_zero_exponent_is_one(self) -> None:
        assert pow(7, 0) == 1
        assert pow(0, 0) == 1
        assert pow(-5, 0) == 1
        assert pow(2.5, 0) == 1.0

    def test_an_exponent_of_one_returns_the_base(self) -> None:
        assert pow(7, 1) == 7
        assert pow(2.5, 1) == 2.5

    def test_an_exponent_of_one_builds_a_new_integer(self) -> None:
        """O(b) for a wide base: a new object, whose peak tracks the base."""
        bases = [(1 << 1_000) + 1, (1 << 100_000) + 1]
        for base in bases:
            result = pow(base, 1)
            assert result == base
            assert result is not base
        peaks = [traced_peak(lambda x=x: pow(x, 1)) for x in bases]

        assert peaks[1] / peaks[0] > 50, f"pow(x, 1) peaks did not track the base: {peaks}"

    def test_a_zero_base(self) -> None:
        assert pow(0, 5) == 0

        with pytest.raises(ZeroDivisionError):
            pow(0, -1)


class TestIntegerStringLimit:
    """The Performance Best Practices line about str() on a wide result, and the second
    Version Notes entry. Present on every supported interpreter, so what is
    asserted is the behaviour, not the release."""

    def test_a_wide_result_refuses_to_stringify(self) -> None:
        wide = pow(2, 1_000_000)
        original = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(4_300)
            with pytest.raises(ValueError, match="Exceeds the limit"):
                str(wide)
        finally:
            sys.set_int_max_str_digits(original)

    def test_raising_the_limit_lets_it_through(self) -> None:
        wide = pow(2, 1_000_000)
        original = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(400_000)
            assert len(str(wide)) == 301_030
        finally:
            sys.set_int_max_str_digits(original)


PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "pow.md"

EXPECTED_BLOCKS = 8


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
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "pow(3, -1, 1000) == 667" in s)
        mutated = source.replace("pow(3, -1, 1000) == 667", "pow(3, -1, 1000) == 668", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run(mutated, tmp_path).returncode != 0
