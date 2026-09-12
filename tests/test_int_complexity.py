"""Tests for docs/builtins/int.md and docs/builtins/int_func.md.

CPython stores an int as 30-bit digits (`sys.int_info.bits_per_digit`). The
type page's bounds are in bit lengths and the constructor page's in string
length. Where a bound can be settled without a stopwatch it is: identity
checks separate "returns x itself" from a copy, `sys.getsizeof` separates a
result sized by the narrower operand from one sized by the wider, and
tracemalloc's peak separates a copy from a borrow.

The growth tests time an operation at two sizes and assert on the ratio. The
size step is 4x, so linear predicts 4x, Karatsuba 4^1.58 = 9x and schoolbook
16x; the constant-time tests step 64x instead, see below. Inputs are random
bits for the type page and repeated characters for the constructor page.
Measured on one aarch64 machine under CPython 3.14.7:

* addition and subtraction of a 100,000-bit value from 1M then 4M bits: x3.8;
* multiplication of two 100,000-bit operands against 400,000-bit ones: x9.2,
  the Karatsuba shape; a 1,000-bit multiplier against a 4M-then-16M-bit
  operand: x4.1, schoolbook, linear in the wide operand; a 100,000-bit
  multiplier, above the cutoff, against 1M then 4M bits: x4.1, still linear
  in the wide operand, which is the O(n * m^0.58) slicing;
* schoolbook division, sized under the 3.12 divide-and-conquer thresholds:
  x3.9 for 4x the divisor at a fixed 4,000-bit quotient and x3.9 for 4x the
  quotient at a fixed 8,000-bit divisor, so the cost is the product of the
  two widths, not of the dividend and the divisor; a one-digit divisor
  scales x3.8 with the dividend; equal widths from 1M to 4M bits: x4.05; a
  positive dividend below the divisor is returned as the remainder itself
  and costs x1.0 for 4x the divisor when it has fewer digits, x4.0 when it
  shares the divisor's top digit; a negative one allocates an m-bit
  remainder and costs x4.0;
* division of a 200,000-bit value by a 100,000-bit one against 4x both: x8.9
  on 3.14, the divide-and-conquer shape, against the schoolbook figure on
  3.10 recorded in TestHugeDivision;
* true division with both operands 1M then 4M bits: x4.9;
* negation of a 1M-bit value allocates 133 KB at peak and 533 KB for 4M
  bits: a copy, so `-x` and `abs(-x)` are linear in the width;
* `a & b` with a 1,000-bit `b` and a 1M-then-4M-bit `a`: x1.0, and the
  result is the size of `b`; `a | b` and `a ^ b` with 250,000 then 4M bits,
  batched 100 calls per sample: x20-x27 for 16x the wider operand;
* `~x`, `x << 100`, `x >> 100`: x3.7-x4.0; `1 << s` for 16x the shift: x15; `x >> (n - 100)`: x1.0
  for a non-negative x and x4.0 for a negative one;
* the constant-time claims - `bit_length`, `int(x)`, `bool(x)`, `abs` of a
  non-negative value, `a & b` with a narrow `b`, a comparison of different
  widths, a right shift that keeps 100 bits - are sub-microsecond calls, so
  each sample runs the call 200 times and the sizes are 1M against 64M bits
  rather than 4M: linear would be x64, and every one measured x1.0;
* `bin`, `hex`, `oct`: x4.1, x4.1, x3.9;
* comparing equal 4M-bit values against 16M-bit ones: x4.0; comparing values
  of different widths: x1.0;
* `hash`: x4.0; `bit_count`: x3.9; `from_bytes`: x4.1; `to_bytes` of a fixed
  1,000-bit value into 125,000 then 500,000 bytes: x4.0, so the length is the
  size variable, not the value's width;
* `str`, `repr` and `f"{x}"` of 1,000 then 4,000 decimal digits: x17-x18,
  quadratic on every version
  because 4,000 digits is under the 3.12 fast path's 1,000-digit (30-bit)
  threshold; 20,000 then 80,000 digits: x8.5 on 3.14.7 and x15.8 on 3.10.21;
* `int(str)` in base 16 for 100,000 then 400,000 characters: x4.2, and base
  2: x4.1; base 3 for 5,000 then 20,000: x15.7, base 36: x16.8, base 10 for
  1,000 then 4,000: x15.7; base 10 for 20,000 then 80,000: x9.0 on 3.14.7
  and x16.3 on 3.10.21.

The thresholds themselves - 70 digits for Karatsuba and 140 for squaring, 300 and 150 digits for
divide-and-conquer division, 1,000 digits for `str`, 6,000 characters for
`int(str)` - are read from Objects/longobject.c on the released 3.14 branch
and not measured; the tests size their inputs to land on the intended side.

Covered elsewhere: `x ** y` by tests/test_pow_complexity.py, which owns the
bounds the row repeats; float()'s scan by the float pages, with the absence of
a cap asserted in tests/test_complexity_caveats.py.

Not settled by running code: the PyPy sentences, which no interpreter here can
run.

Not varied: the digit pattern. The type page's tests use random bits, so a
value with long runs of zero digits, which some operations skip, is not
covered; and no test runs on a 15-bit-digit build, which no supported CI
platform uses.
"""

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable
from random import Random
from typing import Any

import pytest

PAGE_DIR = pathlib.Path(__file__).parent.parent / "docs" / "builtins"
TYPE_PAGE = PAGE_DIR / "int.md"
FUNCTION_PAGE = PAGE_DIR / "int_func.md"

LINEAR_AT_4X = 4.0
"""What a linear operation costs for four times the input."""


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def ratio(small: Callable[[], Any], large: Callable[[], Any], repeats: int = 5) -> float:
    return best_time(large, repeats) / best_time(small, repeats)


def random_bits(bits: int, seed: int = 7) -> int:
    """A random int of exactly `bits` bits."""
    return Random(seed).getrandbits(bits) | (1 << (bits - 1))


def batched(func: Callable[[], Any], loops: int = 200) -> Callable[[], None]:
    """Run a sub-microsecond call enough times for the timer to see it."""

    def run() -> None:
        for _ in range(loops):
            func()

    return run


def peak_bytes(func: Callable[[], Any]) -> int:
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


@pytest.fixture
def default_cap() -> Any:
    """Pin the decimal digit cap at its default for one test and put it back."""
    limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(sys.int_info.default_max_str_digits)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(limit)


@pytest.fixture
def uncapped_digits() -> Any:
    """Lift the decimal digit cap for one test and put it back."""
    limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(0)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(limit)


class TestDigits:
    def test_thirty_bit_digits(self) -> None:
        assert sys.int_info.bits_per_digit == 30


class TestAdditionAndSubtraction:
    @pytest.mark.timing
    @pytest.mark.parametrize(
        "operation",
        [
            pytest.param(lambda x, y: x + y, id="add"),
            pytest.param(lambda x, y: x - y, id="sub"),
        ],
    )
    def test_linear_in_the_wider_operand(self, operation: Callable[[int, int], int]) -> None:
        narrow = random_bits(100_000)
        small, large = random_bits(1_000_000), random_bits(4_000_000)

        growth = ratio(lambda: operation(small, narrow), lambda: operation(large, narrow))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the wide operand"


class TestMultiplication:
    @pytest.mark.timing
    def test_wide_operands_multiply_in_karatsuba_time(self) -> None:
        a, b = random_bits(100_000), random_bits(100_000, seed=8)
        c, d = random_bits(400_000), random_bits(400_000, seed=8)

        growth = ratio(lambda: a * b, lambda: c * d)

        assert 6 < growth < 13, f"x{growth:.1f} for 4x the bits (schoolbook 16, Karatsuba 9)"

    @pytest.mark.timing
    def test_a_narrow_multiplier_is_linear_in_the_wide_operand(self) -> None:
        narrow = random_bits(1_000)
        a, b = random_bits(4_000_000), random_bits(16_000_000)

        growth = ratio(lambda: a * narrow, lambda: b * narrow)

        assert growth < 7, f"x{growth:.1f} for 4x the wide operand"

    @pytest.mark.timing
    def test_a_multiplier_above_the_cutoff_is_still_linear_in_the_wider_operand(self) -> None:
        """Karatsuba on unequal widths slices the wide operand into pieces the
        size of the narrow one: O(n * m^0.58), linear in n at a fixed m."""
        multiplier = random_bits(100_000)
        a, b = random_bits(1_000_000), random_bits(4_000_000)

        growth = ratio(lambda: a * multiplier, lambda: b * multiplier, repeats=3)

        assert growth < 7, f"x{growth:.1f} for 4x the wide operand"


class TestSchoolbookDivision:
    """Sized under the 3.12 thresholds (a divisor of 300 digits and a quotient
    of 150) so every supported version runs the same algorithm."""

    @pytest.mark.timing
    def test_cost_is_linear_in_the_divisor_at_a_fixed_quotient(self) -> None:
        quotient_bits = 4_000
        small_divisor, large_divisor = random_bits(50_000), random_bits(200_000)
        small = random_bits(50_000 + quotient_bits, seed=8)
        large = random_bits(200_000 + quotient_bits, seed=8)

        growth = ratio(lambda: divmod(small, small_divisor), lambda: divmod(large, large_divisor))

        assert growth < 7, f"x{growth:.1f} for 4x the divisor; O(n * m) would give about 16"

    @pytest.mark.timing
    def test_cost_is_linear_in_the_quotient_at_a_fixed_divisor(self) -> None:
        divisor = random_bits(8_000)
        small, large = random_bits(58_000, seed=8), random_bits(208_000, seed=8)

        growth = ratio(lambda: divmod(small, divisor), lambda: divmod(large, divisor))

        assert growth < 7, f"x{growth:.1f} for 4x the quotient"

    @pytest.mark.timing
    def test_a_one_digit_divisor_is_one_pass(self) -> None:
        small, large = random_bits(1_000_000), random_bits(4_000_000)

        growth = ratio(lambda: divmod(small, 7), lambda: divmod(large, 7))

        assert growth < 7, f"x{growth:.1f} for 4x the dividend"

    @pytest.mark.timing
    def test_equal_widths_cost_the_divisor(self) -> None:
        """The divisor is one below the dividend so the quotient is one digit
        rather than zero, which would take the O(1) exit instead."""
        small, large = random_bits(1_000_000), random_bits(4_000_000)
        small_divisor, large_divisor = small - 1, large - 1

        growth = ratio(lambda: divmod(small, small_divisor), lambda: divmod(large, large_divisor))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x both widths"

    def test_a_positive_dividend_below_the_divisor_is_returned_as_the_remainder(self) -> None:
        dividend, divisor = random_bits(1_000), random_bits(4_000_000)

        assert dividend % divisor is dividend
        assert divmod(dividend, divisor) == (0, dividend)

    @pytest.mark.timing
    def test_a_positive_dividend_below_the_divisor_costs_nothing_more_for_a_wider_divisor(
        self,
    ) -> None:
        dividend = random_bits(1_000)
        small, large = random_bits(1_000_000), random_bits(64_000_000)

        growth = ratio(batched(lambda: dividend % small), batched(lambda: dividend % large), 10)

        assert growth < 5, f"x{growth:.1f} for 64x the divisor; linear would be 64"

    @pytest.mark.timing
    def test_a_smaller_dividend_with_the_same_top_digit_still_divides(self) -> None:
        """The O(1) exit needs fewer digits or a smaller top digit; two values
        that share their top digit go through schoolbook division, O(m)."""
        small_dividend, large_dividend = (1 << 1_000_000) + 1, (1 << 4_000_000) + 1
        small_divisor, large_divisor = small_dividend + 1, large_dividend + 1

        growth = ratio(
            lambda: divmod(small_dividend, small_divisor),
            lambda: divmod(large_dividend, large_divisor),
        )

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x both widths"

    def test_a_negative_dividend_below_the_divisor_allocates_the_remainder(self) -> None:
        small, large = -1 % (1 << 1_000_000), -1 % (1 << 4_000_000)

        assert 3 < sys.getsizeof(large) / sys.getsizeof(small) < 5

    @pytest.mark.timing
    def test_modulo_costs_the_same_as_division(self) -> None:
        quotient_bits = 4_000
        small_divisor, large_divisor = random_bits(50_000), random_bits(200_000)
        small = random_bits(50_000 + quotient_bits, seed=8)
        large = random_bits(200_000 + quotient_bits, seed=8)

        growth = ratio(lambda: small % small_divisor, lambda: large % large_divisor)

        assert growth < 7, f"x{growth:.1f} for 4x the divisor"


class TestHugeDivision:
    """Above both thresholds, 3.12 hands division to a divide-and-conquer
    algorithm in _pylong; before that it is schoolbook all the way up.
    Measured for this test's sizes: x8.9 on 3.14.7 and x16.0 on 3.10.21."""

    @pytest.mark.timing
    def test_growth_for_four_times_both_operands(self) -> None:
        small_divisor, large_divisor = random_bits(100_000), random_bits(400_000)
        small, large = random_bits(200_000, seed=8), random_bits(800_000, seed=8)

        growth = ratio(
            lambda: divmod(small, small_divisor), lambda: divmod(large, large_divisor), repeats=3
        )

        if sys.version_info >= (3, 12):
            assert 6 < growth < 13, f"x{growth:.1f}; divide-and-conquer predicts about 9"
        else:
            assert growth > 12, f"x{growth:.1f}; schoolbook predicts about 16"


class TestTrueDivision:
    @pytest.mark.timing
    def test_cost_is_linear_in_the_operand_widths(self) -> None:
        small_divisor, large_divisor = random_bits(1_000_000), random_bits(4_000_000)
        small, large = small_divisor * 3 + 7, large_divisor * 3 + 7

        growth = ratio(lambda: small / small_divisor, lambda: large / large_divisor)

        assert growth < 8, f"x{growth:.1f} for 4x both operands"

    def test_the_result_is_a_float(self) -> None:
        result = (10**400) / (10**399)

        assert isinstance(result, float)
        assert result == 10.0


class TestSignOperations:
    def test_negation_copies_the_digits(self) -> None:
        small, large = random_bits(1_000_000), random_bits(4_000_000)

        growth = peak_bytes(lambda: -large) / peak_bytes(lambda: -small)

        assert 3 < growth < 5, f"x{growth:.1f} bytes at peak for 4x the bits"
        negated = -small
        assert -negated is not small

    def test_abs_of_a_negative_copies_and_of_a_non_negative_returns_itself(self) -> None:
        positive = random_bits(1_000_000)
        negative = -positive

        assert abs(positive) is positive
        assert abs(negative) is not positive
        assert peak_bytes(lambda: abs(negative)) > sys.getsizeof(positive) // 2

    def test_unary_plus_returns_the_int_itself(self) -> None:
        value = random_bits(1_000)

        assert +value is value


class TestBitwise:
    @pytest.mark.timing
    def test_and_costs_the_narrower_operand_when_both_are_non_negative(self) -> None:
        narrow = random_bits(1_000)
        small, large = random_bits(1_000_000), random_bits(64_000_000)

        growth = ratio(batched(lambda: small & narrow), batched(lambda: large & narrow), 10)

        assert growth < 5, f"x{growth:.1f} for 64x the wide operand; linear would be 64"

    def test_the_result_of_and_is_sized_by_the_narrower_operand(self) -> None:
        narrow, wide = random_bits(1_000), random_bits(4_000_000)

        assert sys.getsizeof(wide & narrow) == sys.getsizeof(narrow)
        assert sys.getsizeof(wide | narrow) == sys.getsizeof(wide)

    def test_a_negative_operand_makes_and_as_wide_as_the_other(self) -> None:
        narrow, wide = random_bits(1_000), random_bits(4_000_000)

        assert sys.getsizeof(wide & -narrow) == sys.getsizeof(wide)
        assert sys.getsizeof(-wide & narrow) == sys.getsizeof(narrow)

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "operation",
        [
            pytest.param(lambda x, y: x | y, id="or"),
            pytest.param(lambda x, y: x ^ y, id="xor"),
        ],
    )
    def test_or_and_xor_cost_the_wider_operand(self, operation: Callable[[int, int], int]) -> None:
        """Batch 100 calls at 250,000 then 4,000,000 bits, holding the
        narrower operand at 1,000 bits. A 16x step separates constant (1x),
        linear (16x) and quadratic (256x) work despite allocation/cache
        effects: CPython 3.11.14 measures 17-25x. Signs and digit patterns
        are not varied.
        """
        narrow = random_bits(1_000)
        small, large = random_bits(250_000), random_bits(4_000_000)

        growth = ratio(
            batched(lambda: operation(small, narrow), 100),
            batched(lambda: operation(large, narrow), 100),
        )

        assert 6 < growth < 48, f"x{growth:.1f} for 16x the wide operand"

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "operation",
        [
            pytest.param(lambda x: ~x, id="invert"),
            pytest.param(lambda x: x << 100, id="lshift"),
            pytest.param(lambda x: x >> 100, id="rshift"),
            pytest.param(lambda x: x.bit_count(), id="bit_count"),
            pytest.param(lambda x: hash(x), id="hash"),
            pytest.param(bin, id="bin"),
            pytest.param(hex, id="hex"),
            pytest.param(oct, id="oct"),
        ],
    )
    def test_linear_in_the_bit_length(self, operation: Callable[[int], Any]) -> None:
        small, large = random_bits(1_000_000), random_bits(4_000_000)

        growth = ratio(lambda: operation(small), lambda: operation(large))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the bits"

    @pytest.mark.timing
    def test_a_left_shift_of_one_is_linear_in_the_shift(self) -> None:
        """A shift of 1 is an allocation and little else, so the step is 16x
        to keep the measurement above timer noise: linear predicts 16."""
        growth = ratio(batched(lambda: 1 << 1_000_000, 20), batched(lambda: 1 << 16_000_000, 20))

        assert 6 < growth < 40, f"x{growth:.1f} for 16x the shift"

    @pytest.mark.timing
    def test_a_right_shift_costs_the_surviving_bits(self) -> None:
        small, large = random_bits(1_000_000), random_bits(64_000_000)

        growth = ratio(
            batched(lambda: small >> (1_000_000 - 100)),
            batched(lambda: large >> (64_000_000 - 100)),
            10,
        )

        assert growth < 5, f"x{growth:.1f} for 64x the bits when 100 survive either way"

    @pytest.mark.timing
    def test_a_negative_right_shift_is_linear_in_the_width(self) -> None:
        small, large = -random_bits(1_000_000), -random_bits(4_000_000)

        growth = ratio(lambda: small >> (1_000_000 - 100), lambda: large >> (4_000_000 - 100))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the bits when 100 survive either way"

    def test_a_negative_right_shift_rounds_toward_minus_infinity(self) -> None:
        assert -7 >> 1 == -4

    def test_shift_results_are_sized_by_the_shift(self) -> None:
        assert (1 << 4_000).bit_length() == 4_001
        assert (random_bits(4_000) >> 3_000).bit_length() == 1_000
        assert random_bits(4_000) >> 4_000 == 0

    def test_hex_and_binary_formatting_are_uncapped(self) -> None:
        wide = random_bits(100_000)

        assert len(format(wide, "x")) == 25_000
        assert len(f"{wide:b}") == 100_000


class TestComparison:
    @pytest.mark.timing
    def test_equal_widths_compare_digit_by_digit(self) -> None:
        small, large = random_bits(4_000_000), random_bits(16_000_000)
        small_copy, large_copy = small + 0, large + 0

        growth = ratio(lambda: small == small_copy, lambda: large == large_copy, repeats=20)

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the bits"

    @pytest.mark.timing
    def test_different_widths_compare_in_constant_time(self) -> None:
        narrow = random_bits(1_000)
        small, large = random_bits(1_000_000), random_bits(64_000_000)

        growth = ratio(batched(lambda: small < narrow), batched(lambda: large < narrow), 10)

        assert growth < 5, f"x{growth:.1f} for 64x the wider operand; linear would be 64"


class TestConstantTime:
    @pytest.mark.timing
    @pytest.mark.parametrize(
        "operation",
        [
            pytest.param(lambda x: x.bit_length(), id="bit_length"),
            pytest.param(int, id="int"),
            pytest.param(bool, id="bool"),
            pytest.param(abs, id="abs-of-non-negative"),
        ],
    )
    def test_independent_of_the_bit_length(self, operation: Callable[[int], Any]) -> None:
        small, large = random_bits(1_000_000), random_bits(64_000_000)

        growth = ratio(batched(lambda: operation(small)), batched(lambda: operation(large)), 10)

        assert growth < 5, f"x{growth:.1f} for 64x the bits; linear would be 64"


class TestDecimalConversion:
    @pytest.mark.timing
    @pytest.mark.parametrize(
        "convert",
        [
            pytest.param(str, id="str"),
            pytest.param(repr, id="repr"),
            pytest.param(lambda value: f"{value}", id="format"),
        ],
    )
    def test_quadratic_under_the_fast_path_threshold(self, convert: Callable[[int], str]) -> None:
        small, large = int("9" * 1_000), int("9" * 4_000)

        growth = ratio(lambda: convert(small), lambda: convert(large))

        assert growth > 10, f"x{growth:.1f} for 4x the digits; linear would be 4"

    @pytest.mark.timing
    def test_str_growth_above_the_threshold(self, uncapped_digits: None) -> None:
        small, large = int("9" * 20_000), int("9" * 80_000)

        growth = ratio(lambda: str(small), lambda: str(large), repeats=3)

        if sys.version_info >= (3, 12):
            assert 6 < growth < 13, f"x{growth:.1f}; divide-and-conquer predicts about 9"
        else:
            assert growth > 12, f"x{growth:.1f}; quadratic predicts about 16"

    def test_the_cap_covers_str_repr_and_format(self, default_cap: None) -> None:
        wide = int("9" * 4_000) * 10**1_000

        with pytest.raises(ValueError):
            str(wide)
        with pytest.raises(ValueError):
            repr(wide)
        with pytest.raises(ValueError):
            f"{wide}"
        assert len(hex(wide)) > 4_000

    def test_the_default_cap(self, default_cap: None) -> None:
        assert sys.int_info.default_max_str_digits == 4300
        assert len(str(int("9" * 4300))) == 4300


class TestIdentities:
    """Accessors that return x itself are O(1) whatever its width."""

    @pytest.mark.parametrize("value", [5, 1 << 100, -(1 << 100)], ids=["small", "wide", "negative"])
    def test_accessors_return_the_int_itself(self, value: int) -> None:
        assert int(value) is value
        assert value.real is value
        assert value.numerator is value
        assert value.conjugate() is value
        assert value.as_integer_ratio()[0] is value
        assert +value is value

    def test_constants(self) -> None:
        value = 1 << 100

        assert value.imag == 0
        assert value.denominator == 1
        assert value.as_integer_ratio() == (value, 1)

    def test_a_subclass_instance_is_copied_to_an_exact_int(self) -> None:
        class Tagged(int):
            pass

        tagged = Tagged(1 << 100)
        converted = int(tagged)

        assert converted is not tagged
        assert type(converted) is int
        assert converted == tagged

    def test_is_integer_arrived_in_312(self) -> None:
        if sys.version_info >= (3, 12):
            assert (1 << 100).is_integer() is True
        else:
            assert not hasattr(int, "is_integer")

    def test_bit_length_and_bit_count(self) -> None:
        value = (1 << 100) | 1

        assert value.bit_length() == 101
        assert value.bit_count() == 2

    def test_to_bytes_round_trips_and_overflows(self) -> None:
        value = random_bits(1_000)
        raw = value.to_bytes(125, "big")

        assert int.from_bytes(raw, "big") == value
        with pytest.raises(OverflowError):
            value.to_bytes(124, "big")

    @pytest.mark.timing
    def test_to_bytes_is_linear_in_the_requested_length(self) -> None:
        """The value stays 1,000 bits wide; only the padding grows."""
        value = random_bits(1_000)

        growth = ratio(
            lambda: value.to_bytes(125_000, "big"), lambda: value.to_bytes(500_000, "big")
        )

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the length"

    @pytest.mark.timing
    def test_from_bytes_is_linear_in_the_byte_count(self) -> None:
        small = random_bits(1_000_000).to_bytes(125_000, "big")
        large = random_bits(4_000_000).to_bytes(500_000, "big")

        growth = ratio(lambda: int.from_bytes(small, "big"), lambda: int.from_bytes(large, "big"))

        assert 2.5 < growth < 7, f"x{growth:.1f} for 4x the bytes"


class TestSmallIntCache:
    def test_minus_five_to_256_are_shared(self) -> None:
        for text in ("-5", "0", "100", "256"):
            assert int(text) is int(text), text

    def test_the_neighbours_outside_the_range_are_not(self) -> None:
        for text in ("-6", "257", "300"):
            assert int(text) is not int(text), text


class TestPublicNamesAreDocumented:
    """The Instance Methods and Numeric Attributes tables against dir(int)."""

    VERSION_GATED = {"is_integer": (3, 12)}

    @staticmethod
    def documented_names() -> set[str]:
        text = TYPE_PAGE.read_text(encoding="utf-8")
        start = text.index("## Instance Methods")
        end = text.index("## Common Operations")
        return set(re.findall(r"^\| `(\w+)", text[start:end], re.MULTILINE))

    def test_the_extractor_sees_the_tables(self) -> None:
        assert {"bit_length", "real"} <= self.documented_names()

    def test_every_public_name_has_a_row(self) -> None:
        public = {name for name in dir(int) if not name.startswith("_")}

        missing = public - self.documented_names()

        assert not missing, f"public names without a row: {sorted(missing)}"

    def test_every_row_names_something_that_exists(self) -> None:
        public = {name for name in dir(int) if not name.startswith("_")}

        invented = self.documented_names() - public
        for name in invented:
            assert name in self.VERSION_GATED, f"no such attribute: {name}"
            assert sys.version_info < self.VERSION_GATED[name], f"{name} should exist here"
            assert re.search(rf"`{name}\(\)`.*3\.12\+", TYPE_PAGE.read_text(encoding="utf-8"))


class TestIntFunction:
    """docs/builtins/int_func.md."""

    def test_documented_values(self) -> None:
        assert int() == 0  # noqa: UP018 - the call is the subject under test
        assert int(42) == 42  # noqa: UP018 - the call is the subject under test
        assert int(3.14) == 3
        assert int(3.99) == 3
        assert int(-2.5) == -2
        assert int(True) == 1
        assert int(False) == 0
        assert int("42") == 42
        assert int("-123") == -123
        assert int("+42") == 42
        assert int("  42  ") == 42
        assert int("\t10\n") == 10
        assert int("101", 2) == 5
        assert int("ff", 16) == 255
        assert int("77", 8) == 63
        assert int("1A2B", 16) == 6699
        assert int("11010110", 2) == 214
        assert int("Z", 36) == 35

    @pytest.mark.parametrize("text", ["", "- 42", "forty-two"])
    def test_rejected_literals(self, text: str) -> None:
        with pytest.raises(ValueError):
            int(text)

    @pytest.mark.parametrize("base", [1, 37])
    def test_rejected_bases(self, base: int) -> None:
        with pytest.raises(ValueError):
            int("10", base)

    def test_a_float_conversion_is_bounded(self) -> None:
        assert int(1e300).bit_length() == 997
        assert int(sys.float_info.max).bit_length() == 1024
        with pytest.raises(OverflowError):
            int(float("inf"))

    @pytest.mark.timing
    @pytest.mark.parametrize("base", [2, 16])
    def test_power_of_two_bases_parse_linearly(self, base: int) -> None:
        digit = "1" if base == 2 else "f"
        small, large = digit * 100_000, digit * 400_000

        growth = ratio(lambda: int(small, base), lambda: int(large, base))

        assert growth < 7, f"base {base}: x{growth:.1f} for 4x the characters"

    @pytest.mark.timing
    @pytest.mark.parametrize("base", [3, 36])
    def test_other_bases_parse_quadratically(self, base: int, uncapped_digits: None) -> None:
        digit = "2" if base == 3 else "z"
        small, large = digit * 5_000, digit * 20_000

        growth = ratio(lambda: int(small, base), lambda: int(large, base))

        assert growth > 10, f"base {base}: x{growth:.1f} for 4x the characters; linear would be 4"

    @pytest.mark.timing
    def test_base_10_is_quadratic_under_the_fast_path_threshold(self) -> None:
        small, large = "9" * 1_000, "9" * 4_000

        growth = ratio(lambda: int(small), lambda: int(large))

        assert growth > 10, f"x{growth:.1f} for 4x the digits; linear would be 4"

    @pytest.mark.timing
    def test_base_10_growth_above_the_threshold(self, uncapped_digits: None) -> None:
        small, large = "9" * 20_000, "9" * 80_000

        growth = ratio(lambda: int(small), lambda: int(large), repeats=3)

        if sys.version_info >= (3, 12):
            assert 6 < growth < 13, f"x{growth:.1f}; divide-and-conquer predicts about 9"
        else:
            assert growth > 12, f"x{growth:.1f}; quadratic predicts about 16"

    def test_the_cap_applies_only_to_non_power_of_two_bases(self, default_cap: None) -> None:
        over = sys.int_info.default_max_str_digits + 1

        with pytest.raises(ValueError):
            int("9" * over)
        with pytest.raises(ValueError):
            int("2" * over, 3)
        assert int("f" * over, 16).bit_length() == 4 * over
        assert int("1" * over, 2).bit_length() == over

    def test_base_zero_takes_the_prefixed_bases_cost_and_cap(self, default_cap: None) -> None:
        over = sys.int_info.default_max_str_digits + 1

        assert int("0x" + "f" * over, 0).bit_length() == 4 * over
        assert int("0b" + "1" * over, 0).bit_length() == over
        assert int("0o" + "7" * over, 0).bit_length() == 3 * over
        with pytest.raises(ValueError):
            int("9" * over, 0)
        assert int("0x1f", 0) == 31
        assert int("17", 0) == 17

    def test_dunder_int_is_called_once(self) -> None:
        calls = 0

        class Celsius:
            def __int__(self) -> int:
                nonlocal calls
                calls += 1
                return 21

        assert int(Celsius()) == 21
        assert calls == 1

    def test_dunder_index_is_used(self) -> None:
        class Handle:
            def __index__(self) -> int:
                return 3

        assert int(Handle()) == 3

    def test_the_trunc_fallback_is_gone_in_314(self) -> None:
        class Rounded:
            def __trunc__(self) -> int:
                return 8

        if sys.version_info >= (3, 14):
            with pytest.raises(TypeError):
                int(Rounded())
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                assert int(Rounded()) == 8


def _blocks(page: pathlib.Path) -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = page.read_text(encoding="utf-8").splitlines()
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
    """Every python block on both pages runs, under the interpreter running
    the tests, in its own process with stdin closed."""

    EXPECTED = {TYPE_PAGE: 7, FUNCTION_PAGE: 22}

    @pytest.mark.parametrize("page", [TYPE_PAGE, FUNCTION_PAGE], ids=["int", "int_func"])
    def test_the_page_has_the_expected_blocks(self, page: pathlib.Path) -> None:
        blocks = _blocks(page)

        assert len(blocks) == self.EXPECTED[page], (
            f"expected {self.EXPECTED[page]} python blocks, found {len(blocks)}"
        )

    @pytest.mark.parametrize("page", [TYPE_PAGE, FUNCTION_PAGE], ids=["int", "int_func"])
    def test_every_block_runs(self, page: pathlib.Path, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks(page):
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{page.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks(TYPE_PAGE)[0][1]
        broken = original.replace("a + b", "a + undefined_b", 1)
        assert broken != original, "the mutation did not rewrite the expression"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
