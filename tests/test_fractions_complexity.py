"""Tests for docs/stdlib/fractions.md.

The page prices every operation in `b`, the bit length of the parts involved,
because a `Fraction` is two Python integers and costs what their arithmetic
costs. Which operations reduce is settled by counting `gcd` calls through a
proxy for the module's `math` global, and which ones multiply by counting
multiplications on an `int` subclass; neither needs a tolerance. Growth in `b`
is settled by timing ratios over a 16x step in bit length, where linear
predicts x16, `M(b)` about x81 and quadratic x256.

Measurement scope:

* `Fraction(n, d)` calls `gcd` once; `Fraction(int)`, `Fraction(Fraction)` and
  `Fraction(float)` call it zero times, as do `Fraction.from_number()` (3.14+),
  `a // b`, `a ** k`, `-a`, `+a`, `abs(a)` and every comparison between
  two fractions; `+a` reuses both stored integers. `+`, `-`, `*`
  and `/` each call it at least once on operands that share no factor, and
  their results are asserted reduced over 200 random pairs of 64-bit parts.
* A float's parts are asserted bounded: the largest finite float has a
  1,024-bit numerator and the smallest subnormal a 1,075-bit denominator.
* Growth with `b`, from 10,000-bit to 160,000-bit random odd parts: pair
  construction and `a + b`, `a * b` and `a % b` grow more than x40, and
  `Fraction.from_decimal()` over 2,000 to 32,000 digits more than x40, which
  excludes linear. `float(a)`, `hash(a)` on values it has not cached, and
  `int(a)` on a value between 1 and 2 grow less than x64, which excludes
  quadratic. At 160,000 bits, `<` on two equal-valued fractions with distinct
  parts costs more than 20x `==`, the gap between a multiplication and a
  comparison of the parts.
* `a < b` against a `Rational` stand-in multiplies exactly twice; `a == b`
  multiplies zero times.
* `limit_denominator()` on a ratio of consecutive Fibonacci numbers, whose
  partial quotients are all 1 so the walk is as long as `L` allows: 100x the
  digits of `L` costs between x20 and x1,000, so it follows `log L`, not `L`;
  at a fixed `L` of 10**300, 16x the bits of the value costs less than x64.
  The result is asserted to be the closest fraction with a denominator at most
  `L` against a brute-force search over 300 random values and every `L` up to
  40.
* Adding reciprocals of the first eight primes leaves their product as the
  denominator, and adding eight eighths leaves 1; squaring and adding 1/7 at
  least doubles the denominator's bits, and `limit_denominator()` caps it.
* `str()`, `repr()` and `format(a, '.3e')` raise `ValueError` for a
  5,001-digit numerator under the default 4,300-digit limit, and succeed once
  it is raised, while `'.3f'` on a 5,001-digit denominator succeeds under
  it; a 5,000-digit string raises, while `'1e5000'` builds a 16,610-bit
  numerator. The limit is set explicitly and restored.
* `hash()` equals that of an equal `int`, float and `Decimal`, and `float()`
  is correct where both parts overflow a float on their own.
* The version-noted behaviours are asserted on the versions that have them:
  underscores in strings from 3.11, spaces around `/`, `is_integer()` and the
  float presentation types from 3.12, fill and alignment without a type from
  3.13, and `from_number()` and `as_integer_ratio()` objects from 3.14.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The exponents: that `gcd` and long division are O(b²) and multiplication
  O(b^1.58) is read from Objects/longobject.c (Lehmer `gcd`, Karatsuba
  multiplication). The timing tests separate superlinear from linear and
  linear from quadratic; they do not separate O(b^1.58) from O(b²).
* `str()` and `format()` as O(b²): CPython switches to a subquadratic decimal
  conversion for large integers from 3.12, and the default digit limit stops
  conversion well before the difference shows, so only the limit is tested.
* The O(b²) worst case of `int()` and `//` when the integer part itself has
  about `b` bits, and `round(a, p)` and `format()` as O((b + p)²), follow from
  Lib/fractions.py's single floor division and `divmod` and are not timed.
* `limit_denominator()`'s first division when the integer part itself has
  about `b` bits, a format width, and `round(a, p)` with negative `p` are
  read from Lib/fractions.py and not timed.
* `a ** k` as O(M(k·b)) is two integer powers in Lib/fractions.py; the test
  asserts the parts are exactly `n**k` and `d**k` and that no `gcd` runs.
* Space bounds are asserted through the size of results, not traced
  allocation. Operand shape beyond random odd parts - highly composite
  denominators, very unequal operand sizes - is not varied.
"""

from __future__ import annotations

import copy
import fractions
import math
import numbers
import operator
import pathlib
import random
import re
import statistics
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "fractions.md"
EXPECTED_BLOCKS = 10

SMALL_BITS = 10_000
LARGE_BITS = 160_000  # 16x: linear x16, M(b) about x81, quadratic x256


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
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


def odd_bits(rng: random.Random, bits: int) -> int:
    """A random odd integer of exactly `bits` bits."""
    return rng.getrandbits(bits) | (1 << (bits - 1)) | 1


class CountingMath:
    """Stands in for the `math` module inside `fractions`, recording `gcd`."""

    def __init__(self) -> None:
        self.gcd_calls: list[tuple[int, ...]] = []

    def gcd(self, *args: int) -> int:
        self.gcd_calls.append(args)
        return math.gcd(*args)

    def __getattr__(self, name: str) -> Any:
        return getattr(math, name)


@pytest.fixture
def counting_math(monkeypatch: pytest.MonkeyPatch) -> CountingMath:
    proxy = CountingMath()
    monkeypatch.setattr(fractions, "math", proxy)
    return proxy


@pytest.fixture
def default_digit_limit() -> Iterator[int]:
    original = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(4300)
    yield 4300
    sys.set_int_max_str_digits(original)


class CountingInt(int):
    """An int whose multiplications are recorded, as operand on either side."""

    multiplications: list[int] = []

    def __mul__(self, other: Any) -> Any:
        CountingInt.multiplications.append(1)
        return int(self) * other

    def __rmul__(self, other: Any) -> Any:
        CountingInt.multiplications.append(1)
        return other * int(self)


class PlainRational:
    """A minimal `Rational` whose parts count their multiplications."""

    def __init__(self, numerator: int, denominator: int) -> None:
        self.numerator = CountingInt(numerator)
        self.denominator = CountingInt(denominator)


numbers.Rational.register(PlainRational)


class TestOnlyPairsAreReduced:
    """`Fraction(numerator, denominator)` | O(b²) - one `gcd`; `Fraction(n)`,
    `Fraction(other_fraction)` and a float | O(1) - no `gcd`."""

    def test_a_pair_is_reduced_with_one_gcd(self, counting_math: CountingMath) -> None:
        reduced = Fraction(6, 8)

        assert (reduced.numerator, reduced.denominator) == (3, 4)
        assert counting_math.gcd_calls == [(6, 8)]

    def test_the_sign_moves_to_the_numerator(self) -> None:
        value = Fraction(3, -4)

        assert (value.numerator, value.denominator) == (-3, 4)

    def test_an_int_a_fraction_and_a_float_run_no_gcd(self, counting_math: CountingMath) -> None:
        source = Fraction(3, 4)
        counting_math.gcd_calls.clear()

        results = [Fraction(7), Fraction(source), Fraction(0.5)]

        assert counting_math.gcd_calls == []
        assert [r.as_integer_ratio() for r in results] == [(7, 1), (3, 4), (1, 2)]

    def test_a_zero_denominator_raises(self) -> None:
        with pytest.raises(ZeroDivisionError, match=r"Fraction\(1, 0\)"):
            Fraction(1, 0)

    def test_a_float_s_parts_are_bounded(self) -> None:
        largest = Fraction(sys.float_info.max)
        smallest = Fraction(5e-324)

        assert largest.numerator.bit_length() == 1024
        assert smallest.denominator.bit_length() == 1075
        assert Fraction.from_float(0.1) == Fraction(0.1)
        assert Fraction(0.1) == Fraction(3602879701896397, 36028797018963968)

    def test_a_decimal_converts_exactly_and_reduced(self) -> None:
        assert Fraction(Decimal("0.25")) == Fraction(1, 4)
        assert Fraction.from_decimal(Decimal("0.25")) == Fraction(1, 4)
        assert Fraction(Decimal("1E+3")) == 1000

    def test_the_string_forms(self) -> None:
        assert Fraction("3/4") == Fraction(3, 4)
        assert Fraction("-1.25") == Fraction(-5, 4)
        assert Fraction("1e-3") == Fraction(1, 1000)
        assert Fraction(" 6/8 ") == Fraction(3, 4)

    def test_a_long_digit_run_raises_but_an_exponent_does_not(
        self, default_digit_limit: int
    ) -> None:
        with pytest.raises(ValueError, match="limit"):
            Fraction("1" * (default_digit_limit + 700))

        assert Fraction("1e5000").numerator.bit_length() == 16_610

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_from_number_runs_no_gcd(self, counting_math: CountingMath) -> None:
        from_number = Fraction.from_number  # type: ignore[attr-defined]
        source = Fraction(3, 4)
        counting_math.gcd_calls.clear()

        results = [from_number(7), from_number(source), from_number(0.5)]

        assert counting_math.gcd_calls == []
        assert [r.as_integer_ratio() for r in results] == [(7, 1), (3, 4), (1, 2)]
        assert from_number(Decimal("0.25")) == Fraction(1, 4)
        with pytest.raises(TypeError):
            from_number("1/2")

    @pytest.mark.timing
    def test_pair_construction_is_superlinear_in_bits(self) -> None:
        rng = random.Random(1)
        durations = []
        for bits in (SMALL_BITS, LARGE_BITS):
            numerator, denominator = odd_bits(rng, bits), odd_bits(rng, bits)
            durations.append(best_ns(lambda n=numerator, d=denominator: Fraction(n, d), 3))
        ratio = durations[1] / durations[0]

        assert ratio > 40, f"16x the bits cost x{ratio:.1f} ({durations} ns); linear is x16"

    @pytest.mark.timing
    def test_from_decimal_is_superlinear_in_digits(self) -> None:
        durations = []
        with localcontext() as context:
            context.prec = 100_000
            for digits in (2_000, 32_000):
                value = Decimal("1." + "3" * digits)
                durations.append(best_ns(lambda v=value: Fraction.from_decimal(v), 3))
        ratio = durations[1] / durations[0]

        assert ratio > 40, f"16x the digits cost x{ratio:.1f} ({durations} ns); linear is x16"


class TestArithmeticStaysReduced:
    """`+ - * /` | O(b²) | O(b) with a `gcd`; `//` without one; `**` without
    one and with `k·b`-bit parts; unary operations without one."""

    @pytest.mark.parametrize("operation", ["add", "sub", "mul", "truediv"])
    def test_each_operation_calls_gcd(self, counting_math: CountingMath, operation: str) -> None:
        a, b = Fraction(3, 10), Fraction(7, 15)
        counting_math.gcd_calls.clear()

        getattr(operator, operation)(a, b)

        assert counting_math.gcd_calls, f"{operation} ran no gcd"

    def test_results_are_in_lowest_terms(self) -> None:
        rng = random.Random(2)
        for _ in range(200):
            a = Fraction(rng.getrandbits(64) + 1, rng.getrandbits(64) + 1)
            b = Fraction(rng.getrandbits(64) + 1, rng.getrandbits(64) + 1)
            for result in (a + b, a - b, a * b, a / b, a % b):
                assert math.gcd(result.numerator, result.denominator) == 1
                assert result.denominator > 0

    def test_result_parts_have_at_most_twice_the_bits(self) -> None:
        rng = random.Random(3)
        bits = 2_000
        a = Fraction(odd_bits(rng, bits), odd_bits(rng, bits))
        b = Fraction(odd_bits(rng, bits), odd_bits(rng, bits))
        for result in (a + b, a - b, a * b, a / b):
            assert result.denominator.bit_length() <= 2 * bits
            assert abs(result.numerator).bit_length() <= 2 * bits + 1

    def test_coprime_denominators_multiply_out(self) -> None:
        primes = [2, 3, 5, 7, 11, 13, 17, 19]
        total = Fraction(0)
        for prime in primes:
            total += Fraction(1, prime)

        assert total.denominator == math.prod(primes)

    def test_shared_factors_do_not_grow(self) -> None:
        total = Fraction(0)
        for _ in range(8):
            total += Fraction(1, 8)

        assert total == 1
        assert total.denominator == 1

    def test_floor_division_returns_an_int_without_gcd(self, counting_math: CountingMath) -> None:
        a, b = Fraction(7, 2), Fraction(2)
        counting_math.gcd_calls.clear()

        quotient = a // b

        assert quotient == 1 and type(quotient) is int
        assert counting_math.gcd_calls == []

        remainder = a % b

        assert counting_math.gcd_calls, "% reduces its result"
        assert remainder.as_integer_ratio() == (3, 2)
        assert divmod(a, b) == (1, Fraction(3, 2))
        assert Fraction(-7, 2) // 2 == -2 and Fraction(-7, 2) % 2 == Fraction(1, 2)

    def test_a_power_raises_both_parts_without_gcd(self, counting_math: CountingMath) -> None:
        base = Fraction(2, 3)
        counting_math.gcd_calls.clear()

        cube = base**3
        inverse = base**-2

        assert (cube.numerator, cube.denominator) == (8, 27)
        assert (inverse.numerator, inverse.denominator) == (9, 4)
        assert counting_math.gcd_calls == []
        assert isinstance(Fraction(1, 4) ** Fraction(1, 2), float)
        assert isinstance(Fraction(-1) ** Fraction(1, 2), complex)

    def test_a_power_s_parts_have_k_times_the_bits(self) -> None:
        rng = random.Random(4)
        numerator, denominator = odd_bits(rng, 1_000), odd_bits(rng, 1_000) * 2
        base = Fraction(numerator, denominator)

        power = base**7

        assert power.numerator == base.numerator**7
        assert power.denominator == base.denominator**7

    def test_unary_operations_run_no_gcd(self, counting_math: CountingMath) -> None:
        value = Fraction(-3, 4)
        counting_math.gcd_calls.clear()

        results = [-value, +value, abs(value)]

        assert counting_math.gcd_calls == []
        assert [r.as_integer_ratio() for r in results] == [(3, 4), (-3, 4), (3, 4)]
        large = Fraction(-(3**200), 4**200)
        positive = +large
        assert positive.numerator is large.numerator
        assert positive.denominator is large.denominator

    def test_a_float_operand_makes_a_float(self) -> None:
        third = Fraction(1, 3)

        assert third + 1 == Fraction(4, 3)
        mixed = third + 0.5
        assert type(mixed) is float
        assert mixed == 1 / 3 + 0.5

    def test_squaring_doubles_the_bits_and_limit_denominator_caps_them(self) -> None:
        x = Fraction(1, 3)
        for _ in range(6):
            before = x.denominator.bit_length()
            x = x * x + Fraction(1, 7)
            assert x.denominator.bit_length() >= 2 * before - 1
        x = x.limit_denominator(10**12)
        assert x.denominator <= 10**12

    def test_arithmetic_is_pure_python(self) -> None:
        assert hasattr(Fraction.__add__, "__code__")
        assert hasattr(Fraction.__mul__, "__code__")

    @pytest.mark.timing
    @pytest.mark.parametrize("operation", ["+", "*", "%"])
    def test_arithmetic_is_superlinear_in_bits(self, operation: str) -> None:
        rng = random.Random(5)
        durations = []
        for bits in (SMALL_BITS, LARGE_BITS):
            a = Fraction(odd_bits(rng, bits), odd_bits(rng, bits))
            b = Fraction(odd_bits(rng, bits), odd_bits(rng, bits))
            function = {
                "+": lambda a=a, b=b: a + b,
                "*": lambda a=a, b=b: a * b,
                "%": lambda a=a, b=b: a % b,
            }[operation]
            durations.append(best_ns(function, 3))
        ratio = durations[1] / durations[0]

        assert ratio > 40, f"a {operation} b: 16x the bits cost x{ratio:.1f}; linear is x16"


class TestComparisonAndHashing:
    """`==` | O(b) - compares parts; `<` | O(M(b)) - cross-multiplies; neither
    reduces; `hash()` | O(b) and agrees with other numeric types."""

    @pytest.fixture(autouse=True)
    def _reset(self) -> None:
        CountingInt.multiplications.clear()

    def test_equality_multiplies_nothing(self) -> None:
        other = PlainRational(1, 2)

        assert Fraction(1, 2) == other
        assert Fraction(1, 3) != other
        assert CountingInt.multiplications == []

    def test_ordering_multiplies_twice(self) -> None:
        other = PlainRational(1, 2)

        assert Fraction(1, 3) < other  # type: ignore[operator]

        assert len(CountingInt.multiplications) == 2

    def test_comparisons_run_no_gcd(self, counting_math: CountingMath) -> None:
        a, b = Fraction(2, 3), Fraction(3, 4)
        counting_math.gcd_calls.clear()

        assert a < b and a <= b and b > a and b >= a and a != b
        assert counting_math.gcd_calls == []

    def test_comparisons_with_floats(self) -> None:
        assert Fraction(1, 2) == 0.5
        assert Fraction(1, 10) != 0.1, "the float is converted exactly"
        assert Fraction(1, 3) < 0.34
        assert Fraction(1, 2) > Fraction(1, 3)

    def test_hash_agrees_with_other_numeric_types(self) -> None:
        assert hash(Fraction(1, 2)) == hash(0.5) == hash(Decimal("0.5"))
        assert hash(Fraction(4, 2)) == hash(2)
        prices = {0.5: "half", 2: "two"}
        assert prices[Fraction(1, 2)] == "half"
        assert prices[Fraction(4, 2)] == "two"

    def test_bool_tests_the_numerator(self) -> None:
        assert not Fraction(0, 5)
        assert Fraction(1, 10**100)

    @pytest.mark.timing
    def test_ordering_costs_a_multiplication_equality_does_not(self) -> None:
        rng = random.Random(6)
        numerator, denominator = odd_bits(rng, LARGE_BITS), odd_bits(rng, LARGE_BITS)
        a = Fraction(numerator, denominator)
        b = Fraction(numerator + 0, denominator + 0)
        assert a.numerator is not b.numerator

        equal_ns = best_ns(lambda: a == b, inner=20)
        less_ns = best_ns(lambda: a < b, inner=3)

        assert less_ns > equal_ns * 20, f"< took {less_ns:.0f} ns, == {equal_ns:.0f} ns"

    @pytest.mark.timing
    def test_hash_is_linear_in_bits(self) -> None:
        rng = random.Random(7)
        durations = []
        for bits in (SMALL_BITS, LARGE_BITS):
            numerator, denominator = odd_bits(rng, bits), odd_bits(rng, bits)
            # Fresh values for every repeat, so the hash cache never answers
            batches = iter(
                [
                    [Fraction(numerator + 2 * i * denominator + r, denominator) for i in range(3)]
                    for r in range(0, 14, 2)
                ]
            )

            def hash_batch(batches: Iterator[list[Fraction]] = batches) -> None:
                for value in next(batches):
                    hash(value)

            durations.append(best_ns(hash_batch, repeats=7))
        ratio = durations[1] / durations[0]

        assert ratio < 64, f"16x the bits cost x{ratio:.1f}; quadratic is x256"


class TestLimitDenominator:
    """`limit_denominator(L)` | O(b·log L) | O(b): the closest fraction with
    denominator at most `L`, by a walk of at most O(log L) steps."""

    @staticmethod
    def fibonacci_ratio(index: int) -> Fraction:
        previous, current = 1, 1
        for _ in range(index):
            previous, current = current, previous + current
        return Fraction(current, previous)

    def test_it_finds_the_closest_fraction(self) -> None:
        rng = random.Random(8)
        for _ in range(300):
            value = Fraction(rng.randrange(1, 10**6), rng.randrange(1, 10**6))
            for limit in range(1, 41):
                found = value.limit_denominator(limit)
                best_distance = min(
                    abs(value - Fraction(round(value * q), q)) for q in range(1, limit + 1)
                )
                assert found.denominator <= limit
                assert abs(value - found) == best_distance

    def test_the_page_s_approximations(self) -> None:
        pi = Fraction("3.141592653589793")

        assert pi.limit_denominator(10) == Fraction(22, 7)
        assert pi.limit_denominator(100) == Fraction(311, 99)
        assert pi.limit_denominator(1000) == Fraction(355, 113)
        assert Fraction(1.4142135623).limit_denominator(1000) == Fraction(1393, 985)
        assert Fraction(0.1).limit_denominator(1000) == Fraction(1, 10)

    def test_a_denominator_within_the_limit_is_returned_unchanged(
        self, counting_math: CountingMath
    ) -> None:
        value = Fraction(22, 7)
        counting_math.gcd_calls.clear()

        result = value.limit_denominator(10)

        assert counting_math.gcd_calls == []
        assert result.as_integer_ratio() == (22, 7)
        with pytest.raises(ValueError, match="at least 1"):
            value.limit_denominator(0)

    @pytest.mark.timing
    def test_cost_follows_the_digits_of_the_limit_not_the_limit(self) -> None:
        value = self.fibonacci_ratio(20_000)
        durations = [
            best_ns(lambda m=limit: value.limit_denominator(m), inner=3)
            for limit in (10**10, 10**1000)
        ]
        ratio = durations[1] / durations[0]

        assert 20 < ratio < 1_000, (
            f"100x the digits of L cost x{ratio:.1f}; O(log L) predicts about x100 "
            "and O(L) would never finish"
        )

    @pytest.mark.timing
    def test_cost_is_linear_in_the_value_s_bits(self) -> None:
        values = [self.fibonacci_ratio(index) for index in (2_500, 40_000)]
        durations = [
            best_ns(lambda v=value: v.limit_denominator(10**300), inner=3) for value in values
        ]
        ratio = durations[1] / durations[0]

        assert ratio < 64, f"16x the bits cost x{ratio:.1f}; quadratic is x256"


class TestConversions:
    """Accessors are O(1); `float()` is O(b); `int()` is one floor division;
    `str()`, `repr()` and `format()` convert both parts to decimal and hit
    the integer digit limit."""

    def test_accessors_return_the_stored_parts(self) -> None:
        value = Fraction(14, 24)
        ratio = value.as_integer_ratio()

        assert (value.numerator, value.denominator) == (7, 12)
        assert ratio == (7, 12)
        assert ratio[0] is value.numerator and ratio[1] is value.denominator

    def test_float_is_correct_where_the_parts_overflow(self) -> None:
        value = Fraction(10**400 + 1, 10**399)

        with pytest.raises(OverflowError):
            float(value.numerator)
        assert float(value) == 10.0

    def test_integer_conversions(self) -> None:
        value = Fraction(22, 7)

        assert int(value) == 3 and int(-value) == -3
        assert math.trunc(-value) == -3
        assert math.floor(-value) == -4 and math.ceil(value) == 4
        assert round(Fraction(5, 2)) == 2 and round(Fraction(7, 2)) == 4
        assert round(value, 3) == Fraction(3143, 1000)
        assert type(round(value, 3)) is Fraction

    def test_str_and_repr(self) -> None:
        assert str(Fraction(22, 7)) == "22/7"
        assert repr(Fraction(22, 7)) == "Fraction(22, 7)"
        assert str(Fraction(4, 2)) == "2"

    def test_the_digit_limit_stops_printing(self, default_digit_limit: int) -> None:
        huge = Fraction(10**5000 + 1, 3)

        with pytest.raises(ValueError, match="limit"):
            str(huge)
        with pytest.raises(ValueError, match="limit"):
            repr(huge)
        if sys.version_info >= (3, 12):
            with pytest.raises(ValueError, match="limit"):
                format(huge, ".3e")
            assert format(Fraction(1, 10**5000), ".3f") == "0.000"
        assert huge.limit_denominator(1).numerator.bit_length() > 16_000

        sys.set_int_max_str_digits(10_000)
        assert str(huge).endswith("/3")
        assert repr(huge).endswith(", 3)")
        if sys.version_info >= (3, 12):
            assert format(huge, ".3e") == "3.333e+4999"

    def test_copies_are_the_object_itself(self) -> None:
        value = Fraction(1, 3)

        assert copy.copy(value) is value
        assert copy.deepcopy(value) is value

    @pytest.mark.timing
    @pytest.mark.parametrize("conversion", [float, int])
    def test_conversion_of_a_small_value_is_linear_in_bits(
        self, conversion: Callable[[Fraction], Any]
    ) -> None:
        rng = random.Random(9)
        durations = []
        for bits in (SMALL_BITS, LARGE_BITS):
            denominator = odd_bits(rng, bits)
            value = Fraction(denominator + odd_bits(rng, bits // 2), denominator)
            assert 1 < value < 2
            durations.append(best_ns(lambda v=value: conversion(v), inner=20))
        ratio = durations[1] / durations[0]

        assert ratio < 64, f"{conversion.__name__}: 16x the bits cost x{ratio:.1f}"


class TestVersionNotes:
    """Each Version Notes entry, on the versions that have it."""

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_underscores_in_strings(self) -> None:
        assert Fraction("1_000") == 1000
        assert Fraction("1_0/2_0") == Fraction(1, 2)

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="added in 3.12")
    def test_is_integer_float_formats_and_spaced_slash(self) -> None:
        assert Fraction(4, 2).is_integer()  # type: ignore[attr-defined]
        assert not Fraction(1, 2).is_integer()  # type: ignore[attr-defined]
        assert format(Fraction(22, 7), ".3f") == "3.143"
        assert format(Fraction(1, 8), ".1%") == "12.5%"
        assert format(Fraction(1, 3), ".2e") == "3.33e-01"
        assert Fraction("1 / 2") == Fraction(1, 2)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_formatting_without_a_type(self) -> None:
        assert format(Fraction(1, 3), ">6") == "   1/3"
        assert format(Fraction(1000, 3), ",") == "1,000/3"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_objects_with_as_integer_ratio(self) -> None:
        class Ratio:
            def as_integer_ratio(self) -> tuple[int, int]:
                return (3, 4)

        assert Fraction(Ratio()) == Fraction(3, 4)  # type: ignore[arg-type]
        assert Fraction.from_number(Ratio()) == Fraction(3, 4)  # type: ignore[attr-defined]


class TestRelatedModules:
    """The reasons the page gives for going elsewhere."""

    def test_decimal_keeps_its_precision(self) -> None:
        with localcontext() as context:
            context.prec = 28
            total = Decimal(0)
            for prime in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29):
                total += Decimal(1) / prime

        assert len(total.as_tuple().digits) <= 28

    def test_statistics_keeps_fractions_exact(self) -> None:
        data = [Fraction(1, 3), Fraction(1, 6)]
        mean = statistics.mean(data)
        median = statistics.median(data)

        assert mean == median == Fraction(1, 4)
        assert type(mean) is Fraction and type(median) is Fraction


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
        target = "pi.limit_denominator(100) == Fraction(311, 99)"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "pi.limit_denominator(100) == Fraction(355, 113)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
