"""Tests for docs/stdlib/math.md.

The page prices the float functions at O(1), because a C double is a fixed-width
operand, and the integer functions in digits. The float half is therefore
settled by what an int argument does on its way in, and by which of the
sequence functions hold their input; the integer half is settled by result
sizes, which need no stopwatch, by traced allocation, and by timing ratios at
sizes far enough apart that a linear term and a quadratic one cannot be
confused.

Measurement scope:

* Int arguments to the float functions: `floor()`, `ceil()` and `trunc()`
  return a 200,000-bit int as the same object; `log()`, `log2()` and `log10()`
  answer for a 2,001-bit int; every other one-argument callable in the module
  raises `OverflowError` on it, `isfinite()` included. The conversion is timed
  on 20,000-, 200,000- and 2,000,000-bit ints through `log()` and `sqrt()`: a
  random int costs the same at all three (x1.1 over 100x the bits on aarch64
  3.14), while `2**w + 1`, whose digits below the leading ones are zero, grows
  with w (x80 over the same span).
* `math.pow(2, 2000)` raises `OverflowError` while `pow(2, 2000)` has 2,001
  bits. `nextafter(0.0, 1.0, steps=10**7)` equals 10**7 times the smallest
  subnormal and agrees with 1,000 single steps at steps=1000; 10**15 steps
  cost under 10x one step, where a walk would cost 10**15 times as much.
* `hypot()` and `dist()` hold their coordinates: the traced peak grows more
  than 4x for 8x the coordinates (200 to 1,600), and `hypot()` peaks above
  1.5x what `max()` does when handed the same 1,600 arguments, so the growth
  is not just the argument tuple. `fsum()`, `prod()` over floats and
  `sumprod()` over 1,600 pairs peak under 1/20 of `dist()` on the same input.
  `fsum()` peaks identically over 1,000 and 100,000 values of randomly spread
  magnitude, over values whose exponents are 55, 60, 100 and 200 apart
  against a same-length input that collapses to one partial, and over 38
  values 54 exponents apart - more partials than its 32-entry stack buffer
  holds - against the same 38 repeated 1,000 times.
* The unary partition skips a `TypeError` only for functions that need more
  than one argument or an iterable, so a scalar function rejecting an int
  fails it.
* `prod([3] * m)` has 793, 1,585 and 3,170 bits at m = 500, 1,000 and 2,000;
  16x the factors (2,000 to 32,000) costs more than 48x the time and its
  traced peak grows more than 4x for 8x the factors (2,000 to 16,000).
  `prod([1] * m)`, whose result stays one digit, costs more than 20x for 100x
  the factors (10,000 to 1,000,000), and a wide first factor followed by
  10,000 ones costs more than 20x for 100x its width (1,000 to 100,000 bits;
  x111 on aarch64 3.10 and 3.14), since each step multiplies the whole
  running product: the m·d term.
* `gcd()` is O(w·s). At a fixed 2,000-bit narrow operand, the wide one at
  100,000, 1,000,000 and 10,000,000 bits costs about 10x per step (x9.98 and
  x10.5 on aarch64 3.14), each step asserted above 5x where O(s²) predicts
  x1; the traced peak grows more than 5x from 100,000 to 1,000,000 bits. Two
  random operands of equal size cost x3.4 to x3.9 per doubling of the bits;
  8,192 to 32,768 bits is asserted above 8x, between linear's x4 and
  quadratic's x16, and their peak grows more than 2.5x for the same 4x.
  `lcm()` of a 8,193-bit and a 8,192-bit operand with gcd 1 has exactly
  16,384 bits.
* `isqrt()` costs more than 12x for 8x the bits (4,096 to 32,768) and its peak
  grows more than 2.5x for 4x the bits; it is exact on 10**40, 2**200 - 1 and
  10**400 where `sqrt()` raises.
* `factorial(n)` has more than 8x the bits for 8x n (1,000 to 8,000), its peak
  grows more than 4x for 8x n (2,000 to 16,000), and its time grows more than
  20x per 10x step of n from 2,000 to 200,000.
* `comb(n, 50)` has 334, 384, 434 and 484 bits at n = 2,000 to 16,000 - one bit
  per factor per doubling - and 8x n costs under 3x the time. At k = n / 2
  the result grows more than 7x for 8x n. `comb(1000, 995)` is
  `comb(1000, 5)` and costs under 3x it; `perm(1000, 995)` has more than 100x
  the bits of `perm(1000, 5)` and costs more than 50x it. `perm(n)` equals
  `factorial(n)`.
* `lgamma(1001) - 2 * lgamma(501)` matches `log(comb(1000, 500))` to 1e-9
  relative.
* `sum()` and `fsum()` are asserted on `[1e100, 1.0, -1e100]`, where `sum()`
  gives 0.0 before 3.12 and 1.0 from it, and on
  `[1e16, 1.0, 1e-16, -1e16, -1.0]`, where `sum()` differs from `fsum()`'s
  1e-16 on every version.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The exponent in the quadratic rows. CPython multiplies large ints with
  Karatsuba, so measured exponents sit between about 1.6 and 2; the rows give
  the schoolbook bound, and the tests assert superlinear growth rather than a
  particular power. The O(w·s) of `lcm()` beyond its gcd is read from
  `long_lcm` in Modules/mathmodule.c: one floor division and one
  multiplication.
* That `gcd()` and `lcm()` take further arguments one at a time against the
  running result is read from the argument loops of `math_gcd_impl` and
  `math_lcm_impl`; gcd and lcm are associative, so no result distinguishes
  the order. The tests assert only that the results match the pairwise ones.
* The O(w) that a wide n adds is read from `math_comb_impl`, which computes
  n - k before any product on every supported version; `perm()` with 1 <= k <= n
  has a result at least as wide as n, and `factorial()` refuses an n beyond a
  C long. No test varies n's width at a fixed result.
* `fsum()`'s accuracy depends on IEEE-754 double arithmetic without double
  rounding; the page claims only that it avoids `sum()`'s loss of precision,
  shown on the two inputs above.
* The log-space pattern is checked at `comb(1000, 500)` and `factorial(5000)`;
  the cancellation that subtracting nearby `lgamma()` values suffers for a
  tiny k against a huge n is not varied.
* The O(1) of the float rows is definitional: a float is fixed-width, and
  libm's speed and accuracy on extreme arguments belong to the platform.
* The O(w) worst case of converting an int is measured on `2**w + 1` only,
  the shape whose digits below the leading ones are all zero; that a random
  int stops after the leading digits is read from `_PyLong_Frexp` in
  Objects/longobject.c, which every float function and the log family reach.
* Negative and mixed-sign integer operands, `sumprod()` and `prod()` over
  types other than float and int, and `log()`'s `base` argument beyond one
  call are not varied.
"""

from __future__ import annotations

import gc
import math
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "math.md"
EXPECTED_BLOCKS = 9


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, with no garbage collection inside it.

    A collection triggered by func's own small allocations would run earlier
    tests' finalizers inside the measurement.
    """
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        if was_enabled:
            gc.enable()


def random_int(bits: int, seed: int) -> int:
    """A reproducible odd int of exactly `bits` bits."""
    return random.Random(seed).getrandbits(bits) | (1 << (bits - 1)) | 1


class TestFloatFunctionsTakeIntArguments:
    """Three behaviours for an int argument: `floor`/`ceil`/`trunc` return it,
    the log family takes any size, and everything else converts and overflows.

    The partition is taken over the whole module, so a function that moves
    between groups in a later release fails here.
    """

    RETURN_THE_INT = ("floor", "ceil", "trunc")
    TAKE_ANY_SIZE = ("log", "log2", "log10")
    INTEGER_FUNCTIONS = ("factorial", "perm", "comb", "gcd", "lcm", "isqrt")
    # These need a second argument or an iterable, so one int is a TypeError.
    NOT_UNARY = frozenset(
        {"atan2", "copysign", "dist", "fma", "fmod", "fsum", "isclose", "ldexp", "nextafter"}
        | {"pow", "prod", "remainder", "sumprod"}
    )

    def test_floor_ceil_and_trunc_return_the_int_unchanged(self) -> None:
        big = (1 << 200_000) + 1

        for name in self.RETURN_THE_INT:
            assert getattr(math, name)(big) is big, f"math.{name} should return the int itself"

    def test_the_logarithms_take_an_int_no_float_could_hold(self) -> None:
        big = (1 << 2000) + 1

        assert math.log(big) == pytest.approx(2000 * math.log(2))
        assert math.log2(big) == pytest.approx(2000.0)
        assert math.log10(big) == pytest.approx(2000 * math.log10(2))
        assert math.log(big, 2) == pytest.approx(2000.0)

    def test_every_other_one_argument_function_converts_and_overflows(self) -> None:
        big = (1 << 2000) + 1
        exempt = set(self.RETURN_THE_INT) | set(self.TAKE_ANY_SIZE) | set(self.INTEGER_FUNCTIONS)
        overflowed: list[str] = []
        rejected: list[str] = []
        unexpected: list[str] = []

        for name in sorted(dir(math)):
            function = getattr(math, name)
            if name.startswith("_") or name in exempt or not callable(function):
                continue
            try:
                function(big)
            except OverflowError:
                overflowed.append(name)
            except TypeError:
                rejected.append(name)
            else:
                unexpected.append(name)

        assert not unexpected, f"these took a huge int without converting: {unexpected}"
        assert set(rejected) <= self.NOT_UNARY, f"these refused an int: {rejected}"
        assert {"isfinite", "isinf", "isnan", "log1p", "sqrt", "exp"} <= set(overflowed)
        assert len(overflowed) > 20, f"only {len(overflowed)} functions reached: {overflowed}"

    def test_math_pow_overflows_where_the_builtin_stays_exact(self) -> None:
        with pytest.raises(OverflowError):
            math.pow(2, 2000)

        assert math.pow(2, 10) == 1024.0
        assert pow(2, 2000).bit_length() == 2001


class TestIntConversionReadsTheLeadingDigits:
    """Converting an int is O(1) for most ints and O(w) at worst.

    A random int costs the same at 20,000 and 2,000,000 bits; `2**w + 1`,
    whose digits below the leading ones are all zero, grows with w. The same
    100x span separates x1 from x100.
    """

    SIZES = (20_000, 200_000, 2_000_000)

    @staticmethod
    def sqrt_overflow(value: int) -> None:
        try:
            math.sqrt(value)
        except OverflowError:
            return
        raise AssertionError("sqrt took an int beyond the float range")

    @pytest.mark.timing
    def test_a_random_int_costs_the_same_at_any_width(self) -> None:
        values = [random_int(bits, seed) for seed, bits in enumerate(self.SIZES)]

        logs = [best_ns(lambda v=v: math.log(v), inner=50) for v in values]
        sqrts = [best_ns(lambda v=v: self.sqrt_overflow(v), inner=50) for v in values]

        assert logs[2] < 4 * logs[0], f"log over {self.SIZES} bits: {logs} ns"
        assert sqrts[2] < 4 * sqrts[0], f"sqrt over {self.SIZES} bits: {sqrts} ns"

    @pytest.mark.timing
    def test_zero_digits_below_the_leading_ones_cost_their_width(self) -> None:
        values = [(1 << bits) + 1 for bits in self.SIZES]

        logs = [best_ns(lambda v=v: math.log(v), inner=5) for v in values]

        for before, after in zip(logs, logs[1:], strict=False):
            assert after > 4 * before, f"log of 2**w + 1 over {self.SIZES} bits: {logs} ns"


@pytest.mark.skipif(sys.version_info < (3, 12), reason="version: steps is Python 3.12+")
class TestNextafterStepsIsOneJump:
    """`steps` is one jump rather than a walk of single steps."""

    def test_steps_lands_where_single_steps_would(self) -> None:
        walked = 0.0
        for _ in range(1000):
            walked = math.nextafter(walked, 1.0)

        assert math.nextafter(0.0, 1.0, steps=1000) == walked  # type: ignore[call-arg]
        assert math.nextafter(0.0, 1.0, steps=10**7) == 10**7 * 5e-324  # type: ignore[call-arg]

    @pytest.mark.timing
    def test_a_huge_step_count_costs_what_one_step_does(self) -> None:
        one = best_ns(lambda: math.nextafter(1.0, 2.0, steps=1), inner=500)  # type: ignore[call-arg]
        many = best_ns(lambda: math.nextafter(1.0, 2.0, steps=10**15), inner=500)  # type: ignore[call-arg]

        assert many < 10 * one, f"10**15 steps cost {many:.0f} ns against {one:.0f} ns for one"


class TestSequenceFunctionsDivideOnSpace:
    """`hypot`/`dist` | O(m) | O(m); `fsum`/`sumprod`/`prod` over floats | O(m) | O(1).

    Time is O(m) for all five, so space is what these rows decide. Each O(1)
    member is compared against `dist` at the same length, where the gap is
    tens of kilobytes against tens of bytes.
    """

    PAIRS = 1_600

    def test_dist_grows_with_its_coordinates(self) -> None:
        small_p, small_q = [1.0] * 200, [2.0] * 200
        large_p, large_q = [1.0] * 1_600, [2.0] * 1_600
        math.dist(small_p, small_q)
        math.dist(large_p, large_q)

        small_peak = peak_bytes(lambda: math.dist(small_p, small_q))
        large_peak = peak_bytes(lambda: math.dist(large_p, large_q))

        assert large_peak > 4 * small_peak, f"8x the dimensions: {small_peak} B, {large_peak} B"

    def test_hypot_grows_with_its_coordinates(self) -> None:
        small, large = [1.0] * 200, [1.0] * 1_600
        math.hypot(*small)
        math.hypot(*large)

        small_peak = peak_bytes(lambda: math.hypot(*small))
        large_peak = peak_bytes(lambda: math.hypot(*large))

        assert large_peak > 4 * small_peak, f"8x the coordinates: {small_peak} B, {large_peak} B"

    def test_hypot_holds_more_than_its_arguments(self) -> None:
        """Passing m arguments is O(m) whoever receives them; `max` is the control."""
        coords = [1.0] * 1_600
        max(*coords)
        math.hypot(*coords)

        control_peak = peak_bytes(lambda: max(*coords))
        hypot_peak = peak_bytes(lambda: math.hypot(*coords))

        assert control_peak > 0, "the control must allocate, or it compares nothing"
        assert hypot_peak > 1.5 * control_peak, f"max {control_peak} B, hypot {hypot_peak} B"

    @pytest.mark.parametrize("name", ["fsum", "prod", "sumprod"])
    def test_the_constant_space_members_hold_nothing_per_value(self, name: str) -> None:
        if name == "sumprod" and sys.version_info < (3, 12):
            pytest.skip("version: math.sumprod() is Python 3.12+")
        left, right = [1.5] * self.PAIRS, [2.0] * self.PAIRS
        operations: dict[str, Callable[[], Any]] = {
            "fsum": lambda: math.fsum(left),
            "prod": lambda: math.prod(left),
            "sumprod": lambda: math.sumprod(left, right),  # type: ignore[attr-defined]
        }
        operation = operations[name]
        operation()
        math.dist(left, right)

        peak = peak_bytes(operation)
        dist_peak = peak_bytes(lambda: math.dist(left, right))

        assert 20 * peak < dist_peak, f"{name} {peak} B against dist {dist_peak} B"


class TestFsumSpaceIsBounded:
    """`math.fsum(iterable)` | O(m) | O(1): the partials are capped by the
    exponent range, not by m."""

    def test_the_peak_does_not_move_with_the_input_length(self) -> None:
        generator = random.Random(3)

        def spread(count: int) -> list[float]:
            return [
                generator.uniform(-1, 1) * 2.0 ** generator.randint(-500, 500) for _ in range(count)
            ]

        small, large = spread(1_000), spread(100_000)
        math.fsum(small)
        math.fsum(large)

        small_peak = peak_bytes(lambda: math.fsum(small))
        large_peak = peak_bytes(lambda: math.fsum(large))

        assert small_peak == large_peak, f"100x the values: {small_peak} B, {large_peak} B"

    def test_widely_separated_exponents_do_not_grow_it_either(self) -> None:
        """Values too far apart to merge, against a same-length input that
        collapses into one partial."""
        for separation in (55, 60, 100, 200):
            values = [2.0**exponent for exponent in range(0, -1000, -separation)]
            assert len(values) > 4
            baseline = [1.0] * len(values)
            math.fsum(values)
            math.fsum(baseline)

            spread_peak = peak_bytes(lambda v=values: math.fsum(v))
            flat_peak = peak_bytes(lambda v=baseline: math.fsum(v))

            assert spread_peak == flat_peak, (
                f"separation {separation}: {flat_peak} B flat against {spread_peak} B spread"
            )

    def test_more_partials_than_the_stack_buffer_still_do_not_grow_with_m(self) -> None:
        """38 values 54 exponents apart cannot merge, so fsum needs more partials
        than its 32-entry stack buffer; 1,000 copies of them need no more."""
        values = [2.0**exponent for exponent in range(960, -1075, -54)]
        repeated = values * 1_000
        assert len(values) == 38
        math.fsum(values)
        math.fsum(repeated)

        once_peak = peak_bytes(lambda: math.fsum(values))
        repeated_peak = peak_bytes(lambda: math.fsum(repeated))

        assert once_peak == repeated_peak, f"1,000x the values: {once_peak} B, {repeated_peak} B"

    def test_the_textbook_example_separates_them_only_before_312(self) -> None:
        values = [1e100, 1.0, -1e100]

        assert math.fsum(values) == 1.0
        assert sum(values) == (1.0 if sys.version_info >= (3, 12) else 0.0)

    def test_three_magnitudes_separate_them_on_every_version(self) -> None:
        values = [1e16, 1.0, 1e-16, -1e16, -1.0]

        assert math.fsum(values) == 1e-16
        assert sum(values) != math.fsum(values)
        assert sum(values) == (0.0 if sys.version_info >= (3, 12) else -1.0)


class TestIntegerProdFollowsItsResult:
    """`math.prod()` over ints: O(d²) time and O(d) space in the result's digits."""

    def test_the_result_grows_with_every_factor(self) -> None:
        bits = [math.prod([3] * count).bit_length() for count in (500, 1_000, 2_000)]

        assert bits == [793, 1_585, 3_170], f"unexpected result sizes: {bits}"

    @pytest.mark.timing
    def test_time_grows_faster_than_the_factor_count(self) -> None:
        """16x the factors predicts 16x if linear and 256x if quadratic."""
        small, large = [3] * 2_000, [3] * 32_000
        assert math.prod(small) == 3**2_000
        assert math.prod(large) == 3**32_000

        small_ns = best_ns(lambda: math.prod(small), repeats=5)
        large_ns = best_ns(lambda: math.prod(large), repeats=5)

        assert large_ns > 48 * small_ns, f"16x the factors: {small_ns:.0f} ns, {large_ns:.0f} ns"

    def test_the_peak_tracks_the_result(self) -> None:
        small, large = [3] * 2_000, [3] * 16_000
        math.prod(small)
        math.prod(large)

        small_peak = peak_bytes(lambda: math.prod(small))
        large_peak = peak_bytes(lambda: math.prod(large))

        assert large_peak > 4 * small_peak, f"8x the factors: {small_peak} B, {large_peak} B"

    @pytest.mark.timing
    def test_a_result_that_does_not_grow_still_pays_for_each_factor(self) -> None:
        """The m term: `[1] * m` keeps a one-digit product."""
        small, large = [1] * 10_000, [1] * 1_000_000
        assert math.prod(large) == 1

        small_ns = best_ns(lambda: math.prod(small), repeats=5)
        large_ns = best_ns(lambda: math.prod(large), repeats=5)

        assert large_ns > 20 * small_ns, f"100x the factors: {small_ns:.0f} ns, {large_ns:.0f} ns"

    @pytest.mark.timing
    def test_every_factor_pays_for_the_width_of_the_running_product(self) -> None:
        """The m·d term: ones after a wide first factor still cost its width each."""
        ones = [1] * 10_000
        narrow, wide = [(1 << 1_000) - 1, *ones], [(1 << 100_000) - 1, *ones]

        narrow_ns = best_ns(lambda: math.prod(narrow), repeats=5)
        wide_ns = best_ns(lambda: math.prod(wide), repeats=5)

        assert wide_ns > 20 * narrow_ns, f"100x the width: {narrow_ns:.0f} ns, {wide_ns:.0f} ns"


class TestGcdFollowsBothOperands:
    """`math.gcd()` | O(w·s) | O(w), and `math.lcm()` with it.

    Holding the narrow operand fixed while the wide one grows separates
    O(w·s) from a bound in the narrow operand alone, which predicts no growth.
    """

    NARROW = random_int(2_000, 7)
    WIDE_BITS = (100_000, 1_000_000, 10_000_000)

    def test_the_peak_follows_the_wide_operand(self) -> None:
        wides = [random_int(bits, seed) for seed, bits in enumerate(self.WIDE_BITS[:2])]
        for wide in wides:
            math.gcd(wide, self.NARROW)

        peaks = [peak_bytes(lambda w=wide: math.gcd(w, self.NARROW)) for wide in wides]

        assert peaks[1] > 5 * peaks[0], f"10x the wide operand at a fixed narrow one: {peaks} B"

    def test_the_peak_tracks_equal_operands(self) -> None:
        small_a, small_b = random_int(1 << 13, 1), random_int(1 << 13, 2)
        large_a, large_b = random_int(1 << 15, 3), random_int(1 << 15, 4)
        math.gcd(small_a, small_b)
        math.gcd(large_a, large_b)

        small_peak = peak_bytes(lambda: math.gcd(small_a, small_b))
        large_peak = peak_bytes(lambda: math.gcd(large_a, large_b))

        assert large_peak > 2.5 * small_peak, f"4x the bits: {small_peak} B, {large_peak} B"

    @pytest.mark.timing
    def test_time_follows_the_wide_operand(self) -> None:
        wides = [random_int(bits, seed) for seed, bits in enumerate(self.WIDE_BITS)]

        timings = [best_ns(lambda w=wide: math.gcd(w, self.NARROW), repeats=3) for wide in wides]

        for before, after in zip(timings, timings[1:], strict=False):
            assert after > 5 * before, f"10x the wide operand at a fixed narrow one: {timings} ns"

    @pytest.mark.timing
    def test_equal_operands_grow_faster_than_their_digits(self) -> None:
        """4x the bits predicts x4 if linear and x16 if quadratic."""
        pairs = [
            (random_int(bits, seed), random_int(bits, seed + 100))
            for seed, bits in enumerate((1 << 13, 1 << 15))
        ]
        small_ns, large_ns = [best_ns(lambda p=pair: math.gcd(*p), repeats=5) for pair in pairs]

        assert large_ns > 8 * small_ns, f"4x equal operands: {small_ns:.0f} ns, {large_ns:.0f} ns"

    def test_the_lcm_result_carries_both_operands(self) -> None:
        """lcm(a, b) * gcd(a, b) == a * b, so with gcd 1 the bits add."""
        a = (1 << 8192) | 1
        b = (1 << 8191) | 3

        assert math.gcd(a, b) == 1
        assert math.lcm(a, b).bit_length() == a.bit_length() + b.bit_length() - 1

    def test_more_arguments_give_the_pairwise_result(self) -> None:
        assert math.gcd(12, 18, 30) == math.gcd(math.gcd(12, 18), 30) == 6
        assert math.lcm(4, 6, 10) == math.lcm(math.lcm(4, 6), 10) == 60
        assert math.gcd() == 0
        assert math.lcm() == 1


class TestIsqrtScalesWithTheArgument:
    """`math.isqrt(n)` | O(w²) | O(w), exact at any size."""

    def test_it_is_exact_where_sqrt_overflows(self) -> None:
        assert math.isqrt(10**40) == 10**20
        assert math.isqrt((1 << 200) - 1) == (1 << 100) - 1
        assert math.isqrt(10**400) == 10**200
        with pytest.raises(OverflowError):
            math.sqrt(10**400)

    def test_the_peak_tracks_the_argument(self) -> None:
        small, large = (1 << (1 << 13)) + 1, (1 << (1 << 15)) + 1
        math.isqrt(small)
        math.isqrt(large)

        small_peak = peak_bytes(lambda: math.isqrt(small))
        large_peak = peak_bytes(lambda: math.isqrt(large))

        assert large_peak > 2.5 * small_peak, f"4x the bits: {small_peak} B, {large_peak} B"

    @pytest.mark.timing
    def test_time_grows_faster_than_the_argument(self) -> None:
        small, large = (1 << (1 << 12)) + 1, (1 << (1 << 15)) + 1

        small_ns = best_ns(lambda: math.isqrt(small), repeats=5)
        large_ns = best_ns(lambda: math.isqrt(large), repeats=5)

        assert large_ns > 12 * small_ns, f"8x the bits: {small_ns:.0f} ns, {large_ns:.0f} ns"


class TestFactorialFollowsItsResult:
    """`math.factorial(n)` | O(d²) | O(d), d growing as n log n."""

    def test_the_result_outgrows_n(self) -> None:
        bits = [math.factorial(n).bit_length() for n in (1_000, 8_000)]

        assert bits[1] > 8 * bits[0], f"8x n: {bits} bits"

    def test_the_peak_tracks_the_result(self) -> None:
        math.factorial(2_000)
        math.factorial(16_000)

        small_peak = peak_bytes(lambda: math.factorial(2_000))
        large_peak = peak_bytes(lambda: math.factorial(16_000))

        assert large_peak > 4 * small_peak, f"8x n: {small_peak} B, {large_peak} B"

    @pytest.mark.timing
    def test_time_grows_faster_than_n(self) -> None:
        sizes = (2_000, 20_000, 200_000)
        timings = [best_ns(lambda n=n: math.factorial(n), repeats=5) for n in sizes]

        for before, after in zip(timings, timings[1:], strict=False):
            assert after > 20 * before, f"factorial at n = {sizes}: {timings} ns"


class TestCombAndPermFollowTheirResult:
    """`math.comb(n, k)` and `math.perm(n, k=None)` | O(d²) | O(d).

    The result sizes settle which argument drives d without a stopwatch; the
    timings confirm the cost follows d.
    """

    def test_n_adds_one_bit_per_factor_per_doubling(self) -> None:
        bits = [math.comb(n, 50).bit_length() for n in (2_000, 4_000, 8_000, 16_000)]

        assert bits == [334, 384, 434, 484], f"unexpected result sizes: {bits}"

    def test_k_near_half_of_n_tracks_n(self) -> None:
        bits = [math.comb(n, n // 2).bit_length() for n in (2_000, 16_000)]

        assert bits[1] > 7 * bits[0], f"k = n/2 for 8x n: {bits} bits"

    def test_comb_mirrors_and_perm_does_not(self) -> None:
        assert math.comb(1000, 5) == math.comb(1000, 995) == 8250291250200
        assert math.perm(1000, 5) == 990034950024000
        assert math.perm(1000, 995).bit_length() > 100 * math.perm(1000, 5).bit_length()

    def test_perm_without_k_is_factorial(self) -> None:
        assert math.perm(30) == math.factorial(30)

    @pytest.mark.timing
    def test_comb_is_nearly_flat_in_n(self) -> None:
        """x1.06 to x1.46 for 8x n, where a linear term would give x8."""
        small_ns = best_ns(lambda: math.comb(2_000, 50), repeats=5, inner=20)
        large_ns = best_ns(lambda: math.comb(16_000, 50), repeats=5, inner=20)

        assert large_ns < 3 * small_ns, f"8x n at k = 50: {small_ns:.0f} ns, {large_ns:.0f} ns"

    @pytest.mark.timing
    def test_the_mirror_is_free_for_comb_and_not_for_perm(self) -> None:
        """comb lands within 3% of its mirror; perm pays x592 to x2029."""
        comb_small = best_ns(lambda: math.comb(1000, 5), inner=50)
        comb_large = best_ns(lambda: math.comb(1000, 995), inner=50)
        perm_small = best_ns(lambda: math.perm(1000, 5), inner=50)
        perm_large = best_ns(lambda: math.perm(1000, 995), repeats=3)

        assert comb_large < 3 * comb_small, f"comb: {comb_small:.0f} ns, {comb_large:.0f} ns"
        assert perm_large > 50 * perm_small, f"perm: {perm_small:.0f} ns, {perm_large:.0f} ns"


class TestLogSpaceCombinatorics:
    """`lgamma(n + 1)` is the natural log of n! without building n!."""

    def test_lgamma_matches_the_log_of_the_exact_result(self) -> None:
        assert math.isclose(
            math.lgamma(1001) - 2 * math.lgamma(501), math.log(math.comb(1000, 500))
        )
        assert math.isclose(math.lgamma(5001), math.log(math.factorial(5000)))
        assert math.comb(1000, 500).bit_length() == 995


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
        line, source = next((n, s) for n, s in _blocks() if "math.gcd(84, 30) == 6" in s)
        mutated = source.replace("math.gcd(84, 30) == 6", "math.gcd(84, 30) == 7", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
