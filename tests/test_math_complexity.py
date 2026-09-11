"""Tests to verify documented behaviour of the math module.

The float half of the page is definitional: a float is a fixed-width operand,
so there is no size to vary and "O(1)" restates the type rather than a measured
bound. The integer half is where the measurements are, and where these tests
concentrate.

The integer rows:

* `math.gcd()` is O(n²) in the digits of the smaller operand. Doubling the bit
  length of two random operands costs x3.4 to x3.9 on every supported version,
  close enough to x4 to exclude anything linear, and the classical bound for
  Euclid with schoolbook multiplication. Space is O(n): the peak rises x3.92
  for 4x the bits, on 3.10, 3.12 and 3.14 alike.
* `math.lcm()` is bounded by that gcd, and its result carries the operands'
  digits combined. That part needs no stopwatch: for operands of 8,193 and
  8,192 bits sharing a gcd of 1 bit, the result is exactly 16,384 bits.
* `math.factorial(n)`, `math.comb(n, k)` and `math.perm(n, k)` are O(d²) in the
  digits of the result. d is the size variable that moves: factorial's result
  grows x10.8 for 8x n (Theta(n log n) bits) and the time follows at x3.2 to
  x3.8 per doubling.
* n is barely a variable for comb. `comb(n, 50)`'s result gains a flat 50 bits
  per doubling of n - 334, 384, 434 and 484 bits at n = 2,000 through 16,000 -
  and the time is flat with it, x1.06 to x1.46 for 8x n where a linear term
  would give x8.
* k is the variable, and comb and perm do not answer to it alike.
  `comb(n, k) == comb(n, n - k)`, and comb(1000, 995) lands within 3% of
  comb(1000, 5) on every version. perm has no such identity: perm(1000, 995)
  costs x592 to x2029 what perm(1000, 5) does.
* `math.isqrt()` is O(n²) in the digits of its argument, x3.0 to x4.2 per
  doubling, and is exact where `sqrt()` raises OverflowError.

The five sequence functions divide on space, not time - all of them walk their
input in O(n):

* `hypot()` and `dist()` hold the coordinates. hypot's peak is 8x for 8x the
  arguments, and about twice what passing the same arguments to another C
  variadic costs (x1.92 to x2.00 against `max`). That control carries the
  argument: passing n arguments is O(n) whoever receives them, so growth alone
  proves nothing about hypot.
* `fsum()`, `prod()` over floats and `sumprod()` hold a constant. fsum's
  partial sums are non-overlapping and a double's exponent range caps how many
  can exist at once, so no input grows them: the peak is identical (512 B on
  3.14, 960 B on 3.10) for 1,000 and for 100,000 values of randomly spread
  magnitude, and exponents 55, 60, 100 and 200 apart never allocate at all.
* `prod()` over ints is the exception. The running product grows with every
  factor, so it follows the digits of the result like the integer rows above.

An int argument reaching a float function splits three ways. `floor()`,
`ceil()` and `trunc()` hand it back unchanged at O(1); `log()`, `log2()`,
`log10()` and `isqrt()` have a large-int path, costing x44 to x66 more on a
200,000-bit int than on a small one; everything else converts and raises
OverflowError beyond the float range, the predicates included.

sum() and fsum() differ by version. gh-100425 gave the builtin a compensation
term for floats in 3.12, so `sum([1e100, 1.0, -1e100])` is 0.0 before 3.12 and
1.0 from 3.12, where fsum is 1.0 throughout. One compensation term is not
exactness: [1e16, 1.0, 1e-16, -1e16, -1.0] sums to -1.0 before 3.12 and 0.0
from 3.12, against fsum's correctly rounded 1e-16.

math has 62 public names across the supported versions.
TestEveryPublicNameIsDocumented compares the page's table against dir(math) in
both directions, so a later release cannot outgrow the page unnoticed.

Not settled by execution:

* The exponent in the quadratic rows. CPython's Karatsuba multiplication beats
  the grade-school bound for large operands, so the measured exponents sit
  between 1.6 and 2. The rows state the upper bound the way the divmod and
  decimal pages here do, and these tests assert superlinear growth rather than
  a particular power.
* libm's accuracy and speed on extreme arguments, which are the platform's
  rather than CPython's.
* Whether "O(1)" is the right unit for a float operation at all - the FPU still
  does work proportional to the format's width. The page counts a hardware
  float operation as constant and these tests follow it.

Axes not varied: negative and mixed-sign integer operands, the `base` argument
of log beyond the two-argument form, and non-CPython implementations.
"""

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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def random_odd(bits: int, seed: int) -> int:
    """A reproducible odd integer of the given bit length."""
    generator = random.Random(seed)
    return generator.getrandbits(bits) | (1 << (bits - 1)) | 1


# Documented on the page but absent from the older interpreters. Each must
# carry a version marker in its own row; the coverage test checks that.
ADDED_AFTER_310 = {"cbrt": "3.11", "exp2": "3.11", "sumprod": "3.12", "fma": "3.13"}


def _documented_names() -> set[str]:
    """Every `math.<name>` the Complexity Reference table mentions.

    Rows group families as `math.sin/cos/tan(x)`, so a slash-separated run
    after `math.` names one function each.
    """
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("| Operation | Time | Space | Notes |")
    end = text.index("!!! warning")
    names: set[str] = set()
    for group in re.findall(
        r"math\.([A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*)", text[start:end]
    ):
        names.update(group.split("/"))
    return names


class TestEveryPublicNameIsDocumented:
    """The table has to name every public attribute of `math`.

    A page is lint-clean and green whether it covers its module or a fifth of
    it, and no reader of the page can tell the difference. This is the check
    that can: the interpreter running the suite decides what `math` contains.
    """

    def test_no_public_name_is_missing_from_the_table(self) -> None:
        public = {name for name in dir(math) if not name.startswith("_")}
        documented = _documented_names()

        missing = sorted(public - documented)

        assert not missing, f"{len(missing)} public names absent from the table: {missing}"

    def test_the_table_names_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        public = {name for name in dir(math) if not name.startswith("_")}
        documented = _documented_names()

        unknown = sorted(documented - public - set(ADDED_AFTER_310))

        assert not unknown, f"the table names attributes math does not have: {unknown}"

    def test_the_later_additions_carry_a_version_marker(self) -> None:
        """A row for something 3.10 lacks has to say so."""
        text = PAGE.read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.startswith("| `math.")]

        for name, version in ADDED_AFTER_310.items():
            owning = [row for row in rows if f"math.{name}" in row]
            assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
            assert version in owning[0], f"the {name} row should say {version}+: {owning[0]}"

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        """Counted, so a new release adding a function fails here first."""
        public = {name for name in dir(math) if not name.startswith("_")}

        assert 58 <= len(public) <= 62, (
            f"math has {len(public)} public names; re-run the coverage audit"
        )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()
        public = {name for name in dir(math) if not name.startswith("_")}

        assert len(documented) >= 58, f"the extractor found only {len(documented)} names"
        assert {"sin", "isqrt", "tau", "comb", "sumprod"} <= documented, (
            "the extractor missed rows that are certainly on the page"
        )
        assert public - (documented - {"isqrt"}) == {"isqrt"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestIntArgumentsToTheFloatFunctions:
    """The section that replaced two per-row notes, covering every row at once.

    Three behaviours, and the page says which functions have which. The
    partition below is the claim: anything that moves between groups in a
    later release fails here.
    """

    RETURN_THE_INT = ("floor", "ceil", "trunc")
    HAVE_A_LARGE_INT_PATH = ("log", "log2", "log10", "isqrt")

    def test_floor_ceil_and_trunc_return_the_int_unchanged(self) -> None:
        big = (1 << 200_000) + 1

        for name in self.RETURN_THE_INT:
            result = getattr(math, name)(big)
            assert result is big, f"math.{name} should hand the int straight back"

    def test_the_logarithms_take_an_int_no_float_could_hold(self) -> None:
        big = (1 << 2000) + 1

        assert math.log(big) == pytest.approx(2000 * math.log(2))
        assert math.log2(big) == pytest.approx(2000.0)
        assert math.log10(big) == pytest.approx(2000 * math.log10(2))
        assert math.isqrt(big) > 0

    def test_log1p_is_not_one_of_them(self) -> None:
        """The row says "all but log1p", so the exception needs pinning too."""
        with pytest.raises(OverflowError):
            math.log1p((1 << 2000) + 1)

    def test_every_other_single_argument_function_converts_and_overflows(self) -> None:
        """The partition, taken over the whole module rather than a sample."""
        big = (1 << 2000) + 1
        exempt = set(self.RETURN_THE_INT) | set(self.HAVE_A_LARGE_INT_PATH)
        # factorial and perm reject a huge argument for their own reasons, and
        # gcd/lcm take ints by definition.
        integer_functions = {"factorial", "perm", "comb", "gcd", "lcm"}
        overflowed, unexpected = [], []

        for name in sorted(dir(math)):
            if name.startswith("_") or name in exempt or name in integer_functions:
                continue
            function = getattr(math, name)
            if not callable(function):
                continue
            try:
                function(big)
            except OverflowError:
                overflowed.append(name)
            except TypeError:
                continue  # needs more arguments than one
            else:
                unexpected.append(name)

        assert not unexpected, f"these took a huge int without converting: {unexpected}"
        assert "isfinite" in overflowed, "the predicates convert too, which is the point"
        assert len(overflowed) > 20, f"only {len(overflowed)} functions reached: {overflowed}"

    def test_math_pow_overflows_where_the_builtin_returns_an_int(self) -> None:
        """The `math.pow` row's note."""
        with pytest.raises(OverflowError):
            math.pow(2, 2000)

        assert pow(2, 2000).bit_length() == 2001


class TestSequenceFunctionsDivideOnSpace:
    """`hypot`/`dist` hold their input; `fsum`/`sumprod`/`prod` do not.

    The time bound is O(n) for all five, so space is the whole content of
    these rows and the only thing worth measuring.
    """

    def test_dist_holds_its_coordinates(self) -> None:
        small_p, small_q = [1.0] * 200, [2.0] * 200
        large_p, large_q = [1.0] * 1600, [2.0] * 1600
        math.dist(small_p, small_q)
        math.dist(large_p, large_q)

        small_peak = peak_bytes(lambda: math.dist(small_p, small_q))
        large_peak = peak_bytes(lambda: math.dist(large_p, large_q))

        assert large_peak > 4 * small_peak, (
            f"8x the dimensions should cost about 8x: {small_peak} B against {large_peak} B"
        )

    def test_fsum_over_the_same_length_does_not(self) -> None:
        """The control for the row above, and the fsum row's own claim.

        Compared against `dist` at the same length rather than against itself
        at two lengths: fsum's own peak is a flat 48 B up to 3.13 and 0 B on
        3.14, small enough that ordinary interpreter noise can double it, but
        never in the neighbourhood of the ~38 KB dist holds for 1,600 pairs.
        """
        values, other = [1.0] * 1600, [2.0] * 1600
        math.fsum(values)
        math.dist(values, other)

        fsum_peak = peak_bytes(lambda: math.fsum(values))
        dist_peak = peak_bytes(lambda: math.dist(values, other))

        assert 20 * fsum_peak < dist_peak, (
            f"fsum should hold a constant where dist holds the input: "
            f"{fsum_peak} B against {dist_peak} B"
        )

    def test_prod_over_floats_holds_nothing_either(self) -> None:
        values, other = [1.5] * 1600, [2.0] * 1600
        math.prod(values)
        math.dist(values, other)

        prod_peak = peak_bytes(lambda: math.prod(values))
        dist_peak = peak_bytes(lambda: math.dist(values, other))

        assert 20 * prod_peak < dist_peak, (
            f"prod over floats should hold nothing per element: {prod_peak} B against {dist_peak} B"
        )

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="math.sumprod() is 3.12+")
    def test_sumprod_is_the_o1_member_of_the_family(self) -> None:
        left, right = [1.0] * 1600, [2.0] * 1600
        math.sumprod(left, right)  # type: ignore[attr-defined]
        math.dist(left, right)

        sumprod_peak = peak_bytes(lambda: math.sumprod(left, right))  # type: ignore[attr-defined]
        dist_peak = peak_bytes(lambda: math.dist(left, right))

        assert 20 * sumprod_peak < dist_peak, (
            f"sumprod should hold nothing per element, unlike dist: "
            f"{sumprod_peak} B against {dist_peak} B"
        )
        assert math.sumprod([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]) == 32.0  # type: ignore[attr-defined]

    def test_the_documented_values(self) -> None:
        assert math.dist((0.0, 0.0), (3.0, 4.0)) == 5.0
        assert math.fsum([0.1] * 10) == 1.0
        assert math.prod([2.0, 3.0, 7.0]) == 42.0


class TestIsqrtAndIntegerProd:
    """`math.isqrt(n)` | O(n²) | O(n), and `math.prod()` over ints."""

    def test_isqrt_is_exact_where_sqrt_cannot_be(self) -> None:
        assert math.isqrt(10**40) == 10**20
        assert math.isqrt((1 << 200) - 1) == (1 << 100) - 1
        with pytest.raises(OverflowError):
            math.sqrt(10**400)

    def test_the_isqrt_peak_tracks_the_argument_digits(self) -> None:
        small = (1 << (1 << 13)) + 1
        large = (1 << (1 << 15)) + 1
        math.isqrt(small)
        math.isqrt(large)

        small_peak = peak_bytes(lambda: math.isqrt(small))
        large_peak = peak_bytes(lambda: math.isqrt(large))

        assert large_peak > 2.5 * small_peak, (
            f"4x the digits should cost about 4x: {small_peak} B against {large_peak} B"
        )

    def test_an_int_product_grows_with_every_factor(self) -> None:
        """Why the prod row carries a second bound for ints."""
        digits = [math.prod([3] * n).bit_length() for n in (500, 1000, 2000)]

        assert digits == [793, 1585, 3170], f"unexpected result sizes: {digits}"

    @pytest.mark.timing
    def test_isqrt_grows_faster_than_the_digit_count(self) -> None:
        small = (1 << (1 << 12)) + 1
        large = (1 << (1 << 15)) + 1
        small_time = best_ns(lambda: math.isqrt(small), repeats=5)
        large_time = best_ns(lambda: math.isqrt(large), repeats=5)

        assert large_time > 12 * small_time, (
            f"8x the digits should cost more than linear growth: "
            f"{small_time:.0f} ns against {large_time:.0f} ns"
        )

    @pytest.mark.timing
    def test_prod_over_ints_grows_faster_than_the_term_count(self) -> None:
        small = [3] * 500
        large = [3] * 4000
        small_time = best_ns(lambda: math.prod(small), repeats=3)
        large_time = best_ns(lambda: math.prod(large), repeats=3)

        assert large_time > 12 * small_time, (
            f"8x the terms should cost more than linear growth: "
            f"{small_time:.0f} ns against {large_time:.0f} ns"
        )


class TestFloatRowsTakeFloats:
    """`math.sqrt(x)` and `math.log(x)` | O(1) - for the floats they are for.

    The O(1) itself is definitional; what the rows now add is what an int
    argument costs, and that is observable in one case and timed in the other.
    """

    def test_sqrt_refuses_an_int_beyond_the_float_range(self) -> None:
        big = (1 << 2000) + 1

        assert math.sqrt(1 << 100) == pytest.approx(2.0**50)
        with pytest.raises(OverflowError):
            math.sqrt(big)

    def test_log_accepts_the_int_sqrt_refuses(self) -> None:
        big = (1 << 2000) + 1

        assert math.log(big) == pytest.approx(2000 * math.log(2))

    @pytest.mark.timing
    def test_log_of_a_large_int_costs_more_than_a_small_one(self) -> None:
        """The row's note, which only a stopwatch settles.

        The large-int path allocates nothing that tracks the operand - the
        peak is a flat 162 B at 20,000 and at 200,000 bits - so allocation
        cannot separate the two and elapsed time has to.
        """
        big = (1 << 200_000) + 1

        small_ns = best_ns(lambda: math.log(3), inner=200)
        big_ns = best_ns(lambda: math.log(big), inner=20)

        assert big_ns > 5 * small_ns, (
            f"a 200,000-bit int should cost more than a small one: "
            f"{small_ns:.0f} ns against {big_ns:.0f} ns"
        )


class TestHypotHoldsItsCoordinates:
    """`math.hypot(*coords)` | O(n) | O(n).

    Growth alone does not settle the space bound: passing n arguments is O(n)
    whoever receives them. `max` is the control - another C variadic, taking
    the same arguments, with no buffer of its own - and hypot peaks at about
    twice it.
    """

    def test_the_peak_grows_with_the_coordinate_count(self) -> None:
        small = [1.0] * 200
        large = [1.0] * 1600
        math.hypot(*small)
        math.hypot(*large)

        small_peak = peak_bytes(lambda: math.hypot(*small))
        large_peak = peak_bytes(lambda: math.hypot(*large))

        assert large_peak > 4 * small_peak, (
            f"8x the coordinates should cost about 8x, so O(1) cannot be the "
            f"bound: {small_peak} B against {large_peak} B"
        )

    def test_hypot_holds_more_than_the_arguments_alone(self) -> None:
        """The control: `max` receives the same arguments and keeps nothing."""
        coords = [1.0] * 1600
        max(*coords)
        math.hypot(*coords)

        control_peak = peak_bytes(lambda: max(*coords))
        hypot_peak = peak_bytes(lambda: math.hypot(*coords))

        assert control_peak > 0, "the control must allocate, or it compares nothing"
        assert hypot_peak > 1.5 * control_peak, (
            f"hypot should hold a copy of its own on top of the arguments: "
            f"{control_peak} B against {hypot_peak} B"
        )

    def test_the_documented_values(self) -> None:
        assert math.hypot(3.0, 4.0) == 5.0
        assert math.hypot(1.0, 2.0, 2.0) == 3.0


class TestFsumSpaceIsBounded:
    """`math.fsum(iterable)` | O(n) | O(1) - checked, and left alone.

    The partials are non-overlapping and a double's exponent range caps how
    many can exist, so the working set is bounded by the format rather than by
    the input.
    """

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

        assert small_peak == large_peak, (
            f"100x the values should not move a bounded working set: "
            f"{small_peak} B against {large_peak} B"
        )

    def test_widely_separated_exponents_do_not_grow_it_either(self) -> None:
        """The adversarial shape: values too far apart to merge into one partial.

        Compared against a same-length input whose terms all share an exponent
        and so collapse into a single partial. Any growth in the partials array
        would show up as a difference; the peaks are identical instead (48 B up
        to 3.13, 0 B on 3.14 - the returned float, not the array).
        """
        for separation in (55, 60, 100, 200):
            values = [2.0**exponent for exponent in range(0, -1000, -separation)]
            assert len(values) > 4
            baseline = [1.0] * len(values)
            math.fsum(values)
            math.fsum(baseline)

            spread_peak = peak_bytes(lambda v=values: math.fsum(v))
            flat_peak = peak_bytes(lambda v=baseline: math.fsum(v))

            assert spread_peak == flat_peak, (
                f"separation {separation} over {len(values)} values grew the "
                f"working set: {flat_peak} B against {spread_peak} B"
            )

    def test_the_textbook_example_stopped_separating_them_in_312(self) -> None:
        """The textbook fsum example is version-dependent.

        gh-100425 gave the builtin sum() a compensation term for floats in
        3.12, so the example every fsum tutorial uses returns 0.0 before that
        and 1.0 from it. The page states the split rather than one side of it.
        """
        values = [1e100, 1.0, -1e100]

        assert math.fsum(values) == 1.0
        if sys.version_info >= (3, 12):
            assert sum(values) == 1.0, "3.12 compensates, so the classic example agrees"
        else:
            assert sum(values) == 0.0, "before 3.12 the 1.0 is lost"

    def test_three_magnitudes_still_separate_them_everywhere(self) -> None:
        """One compensation term is not exactness.

        sum() gives -1.0 before 3.12 and 0.0 from 3.12; both are wrong, and
        fsum returns the correctly rounded 1e-16 on every supported version.
        This is the pair the page now uses to make the point.
        """
        values = [1e16, 1.0, 1e-16, -1e16, -1.0]

        assert math.fsum(values) == 1e-16
        assert sum(values) != math.fsum(values)
        assert sum(values) == (0.0 if sys.version_info >= (3, 12) else -1.0)


class TestGcdAndLcmScaleWithDigits:
    """`math.gcd()` | O(n²) | O(n) and `math.lcm()` with it - both said "Varies"."""

    def test_the_peak_tracks_the_operand_digits(self) -> None:
        """The space correction, which needs no stopwatch."""
        small_a, small_b = random_odd(1 << 13, 1), random_odd(1 << 13, 2)
        large_a, large_b = random_odd(1 << 15, 3), random_odd(1 << 15, 4)
        math.gcd(small_a, small_b)
        math.gcd(large_a, large_b)

        small_peak = peak_bytes(lambda: math.gcd(small_a, small_b))
        large_peak = peak_bytes(lambda: math.gcd(large_a, large_b))

        assert large_peak > 2.5 * small_peak, (
            f"4x the digits should cost about 4x, so O(1) cannot be the bound: "
            f"{small_peak} B against {large_peak} B"
        )

    def test_the_lcm_result_carries_both_operands(self) -> None:
        """`n = digits; the result carries the operands' digits combined`.

        Exact rather than approximate: lcm(a, b) * gcd(a, b) == a * b, so with
        a one-bit gcd the result is the operands' bits less that one.
        """
        a = (1 << 8192) | 1
        b = (1 << 8191) | 3

        assert math.gcd(a, b) == 1
        assert math.lcm(a, b).bit_length() == a.bit_length() + b.bit_length() - 1

    def test_both_take_any_number_of_arguments(self) -> None:
        """3.9 made them variadic; the page's signature said `(a, b)`."""
        assert math.gcd(12, 18, 30) == 6
        assert math.lcm(4, 6, 10) == 60
        assert math.gcd() == 0
        assert math.lcm() == 1

    def test_the_documented_values(self) -> None:
        assert math.gcd(84, 30) == 6
        assert math.lcm(6, 10) == 30

    @pytest.mark.timing
    def test_gcd_grows_faster_than_the_digit_count(self) -> None:
        """x3.4 to x3.8 per doubling, against x2 for anything linear."""
        pairs = [
            (random_odd(bits, seed), random_odd(bits, seed + 100))
            for seed, bits in enumerate((1 << 13, 1 << 14, 1 << 15))
        ]
        timings = [best_ns(lambda p=pair: math.gcd(*p), repeats=5) for pair in pairs]

        for before, after in zip(timings, timings[1:], strict=False):
            assert after > 2.5 * before, (
                f"doubling the digits should cost more than doubling the time: {timings}"
            )


class TestFactorialGrowsWithItsResult:
    """`math.factorial(n)` | O(d²) | O(d) | d = digits of the result."""

    def test_the_result_grows_faster_than_n(self) -> None:
        """Theta(n log n) bits: 8x n gives x10.8, not x8."""
        digits = [math.factorial(n).bit_length() for n in (1000, 8000)]

        assert digits[1] > 8 * digits[0], f"the result should outgrow n itself: {digits} bits"

    def test_the_peak_tracks_the_result(self) -> None:
        math.factorial(2000)
        math.factorial(16000)

        small_peak = peak_bytes(lambda: math.factorial(2000))
        large_peak = peak_bytes(lambda: math.factorial(16000))

        assert large_peak > 4 * small_peak, (
            f"8x n should cost more than 8x, since the result does: "
            f"{small_peak} B against {large_peak} B"
        )

    def test_the_documented_value(self) -> None:
        assert math.factorial(10) == 3628800

    def test_floats_are_rejected(self) -> None:
        """Removed in 3.10, which is this project's oldest supported version."""
        with pytest.raises(TypeError):
            math.factorial(10.0)  # type: ignore[arg-type]

    @pytest.mark.timing
    def test_time_grows_faster_than_n(self) -> None:
        timings = [best_ns(lambda n=n: math.factorial(n), repeats=3) for n in (4000, 8000, 16000)]

        for before, after in zip(timings, timings[1:], strict=False):
            assert after > 2.5 * before, f"doubling n should cost more than x2: {timings}"


class TestCombAndPermAreDrivenByK:
    """`math.comb(n, k)` and `math.perm(n, k)` | O(d²) | O(d).

    n barely counts, and the two functions answer to k differently. The digit
    counts settle the first without a stopwatch, because d - the size of the
    result - is the table's size variable.
    """

    def test_n_only_adds_logarithmically_to_comb(self) -> None:
        """A flat 50 bits per doubling of n - one per factor, as log n grows."""
        digits = [math.comb(n, 50).bit_length() for n in (2000, 4000, 8000, 16000)]
        steps = [after - before for before, after in zip(digits, digits[1:], strict=False)]

        assert digits == [334, 384, 434, 484], f"unexpected digit counts: {digits}"
        assert all(step == 50 for step in steps), (
            f"each doubling of n should add one bit per factor: {steps}"
        )

    def test_k_drives_comb_linearly_in_the_result(self) -> None:
        """Against the flat growth above: at k = n/2 the result tracks n."""
        digits = [math.comb(n, n // 2).bit_length() for n in (2000, 16000)]

        assert digits[1] > 7 * digits[0], f"k = n/2 should track n: {digits} bits"

    def test_comb_mirrors_but_perm_does_not(self) -> None:
        """The identity behind the two rows differing."""
        assert math.comb(1000, 5) == math.comb(1000, 995)
        assert math.perm(1000, 5) != math.perm(1000, 995)

        comb_digits = [math.comb(1000, k).bit_length() for k in (5, 995)]
        perm_digits = [math.perm(1000, k).bit_length() for k in (5, 995)]

        assert comb_digits[0] == comb_digits[1], f"comb mirrors: {comb_digits}"
        assert perm_digits[1] > 100 * perm_digits[0], f"perm does not: {perm_digits}"

    def test_the_documented_values(self) -> None:
        assert math.comb(10, 3) == 120
        assert math.perm(10, 3) == 720
        assert math.comb(1000, 5) == 8250291250200
        assert math.perm(1000, 5) == 990034950024000

    @pytest.mark.timing
    def test_comb_is_nearly_flat_in_n(self) -> None:
        """x1.06 to x1.46 for 8x n, where a linear term would give x8."""
        small_ns = best_ns(lambda: math.comb(2000, 50), repeats=5, inner=20)
        large_ns = best_ns(lambda: math.comb(16000, 50), repeats=5, inner=20)

        assert large_ns < 3 * small_ns, (
            f"8x n should not cost 8x at a fixed k: {small_ns:.0f} ns against {large_ns:.0f} ns"
        )

    @pytest.mark.timing
    def test_the_mirror_is_free_for_comb_and_not_for_perm(self) -> None:
        """comb lands within 3% of its mirror; perm pays x592 to x2029."""
        comb_small = best_ns(lambda: math.comb(1000, 5), inner=50)
        comb_large = best_ns(lambda: math.comb(1000, 995), inner=50)
        perm_small = best_ns(lambda: math.perm(1000, 5), inner=50)
        perm_large = best_ns(lambda: math.perm(1000, 995), repeats=3)

        assert comb_large < 3 * comb_small, (
            f"comb(n, n-k) should cost what comb(n, k) does: "
            f"{comb_small:.0f} ns against {comb_large:.0f} ns"
        )
        assert perm_large > 50 * perm_small, (
            f"perm has no mirror to take: {perm_small:.0f} ns against {perm_large:.0f} ns"
        )


class TestIscloseRow:
    """`math.isclose(a, b)` | O(1) | O(1)."""

    def test_the_documented_example(self) -> None:
        assert math.isclose(0.1 + 0.2, 0.3)
        assert (0.1 + 0.2) != 0.3


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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
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
    """Every block runs, with nothing held back and nothing pre-classified."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: Any) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: Any) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import math\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
