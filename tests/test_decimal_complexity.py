"""Tests for docs/stdlib/decimal.md.

The page prices the module in digits: a `Decimal` is a coefficient plus a
bounded exponent, the context precision decides how many digits a result
keeps, and the constructor is the one operation that does not round. Identity,
digit counts and signal flags settle most of it without a stopwatch. Growth
classes that only a stopwatch can separate - linear parsing against quadratic
base conversion, quadratic multiplication against a linear operand, a
quadratic `sqrt()` against a superquadratic `exp()` - are measured at two
sizes with the threshold placed between the claimed shape and the excluded
one.

Measurement scope:

* Construction. `Decimal(str)` at 20,000 and 80,000 digits grows under 6x for
  4x the digits, which excludes quadratic; it is priced by characters read,
  which a literal of 1,000 leading zeros and one digit shows directly and a
  timing over 2,000 against 200,000 leading zeros shows by growing more than
  10x at a fixed one-digit coefficient. `Decimal(int)` over the 4x digit step
  grows more than 8x, which excludes linear. `Decimal(Decimal)` is asserted to
  return the same object.
* Conversion out. `int(d)` grows more than 8x for 4x the coefficient digits,
  and `int()`, `round(d)` and `as_integer_ratio()` each grow more than 8x for
  4x the exponent at one coefficient digit - positive for the numerator,
  negative for `as_integer_ratio()`'s denominator - which is the (n + e)² of
  those rows. `float(d)` grows under 6x for the same 4x digit step. A float's
  exact expansion is asserted at 767 digits for the widest denormal and 309
  for `sys.float_info.max`, and its cost is flat across those two, so it is
  bounded by the format.
* Rendering. `str()` over 20,000 and 200,000 digits grows more than 5x, and
  `format(d, '.2f')` over the same pair stays under 2x on a coefficient of
  nines. The discarded-digit scan is measured separately: a coefficient of
  zeros makes `format()`, `round(d, 2)` and `to_integral_value()` each grow
  more than 10x from 2,000 to 200,000 digits, which is why the page prices
  them O(r + n) and not O(r). A field width is asserted to produce a
  1,000,000-character result from a one-digit coefficient, which is the L
  term.
* Addition. The coefficients are held at one digit while the exponent gap
  grows from 1e2 to 1e8 at the default precision: time stays within 2x, so a
  gap the precision will not keep is not materialised. Raise the precision
  above the gap and it is: `Decimal(1) + Decimal('1E-2000')` at prec 3,000 is
  asserted to have 2,001 digits. Held at a gap of zero, time grows more than
  8x from 2,000 to 64,000 coefficient digits.
* Multiplication. Equal operands of 200 and 800 digits grow more than 10x,
  which excludes both linear and Karatsuba; one operand held at 50 digits
  while the other goes from 2,000 to 128,000 grows between 16x and 128x for
  64x, which is the linear term with a floor that excludes a constant. The
  exact product of two 50-digit coefficients is asserted to be 99 digits at a
  precision wide enough to keep it. `fma()` is separated from a rounded
  multiply followed by an add: at prec 3, 251 * 4 - 1000 is 4 fused and 0 in
  two steps.
* Division. The quotient's digit count is asserted equal to `prec` at 10 and
  60. Time grows under 8x for 4x the dividend digits at a fixed precision
  (the n term), under 8x for 4x the precision at fixed 30-digit operands (the
  p·m term with m fixed), and more than 8x when precision and both operands
  grow together by 4x (p·m with both moving).
* Powers and transcendentals. An integer exponent from 4 to 65,536 - 16,384x
  - costs under 20x, which is the binary exponentiation. Over an 8x precision
  step (250 to 2,000 digits) `sqrt()` grows under 100x, which brackets the
  64x a quadratic predicts with room for noise, while `exp()`, `ln()`,
  `log10()` and a non-integer `**` all grow more than 150x. Measured here:
  sqrt x48, exp x305, ln x440, `2 ** Decimal("0.5")` x319.
* Rounding. `quantize()` to three digits from a 200,000-digit coefficient of
  nines costs under 2x what it costs from a 2,000-digit one, and its traced
  peak is under 4 KB where rendering the same operand peaks over 100 KB -
  which is the O(r) space. Growing r instead, at a fixed operand, costs more.
  `to_integral_value()` is asserted to succeed at prec 2 where `quantize()`
  to the same exponent signals, and `round(d)` with no second argument to
  return an `int` rounded to even under a `ROUND_UP` context.
* Digit manipulation. `normalize()`, `shift()`, `rotate()`, `logical_and()`,
  `logical_invert()` and `next_plus()` each grow more than 4x from 2,000 to
  20,000 digits at a precision that matches - n and p move together there,
  and neither is separated from the other. `logical_and()` against a
  200,000-digit second operand costs more than 4x what it costs against a
  2,000-digit one at a fixed first operand, which is the m term, and a digit
  outside the retained width is asserted to still signal.
* Constant-time accessors. `canonical()`, `conjugate()` and `.real` are
  asserted to return the same object; `radix()`, `number_class()`, `logb()`,
  `adjusted()` and the ten `is_*` predicates are measured flat within 2x
  across a 100x operand. `copy_abs()`, `copy_negate()` and `copy_sign()` are
  asserted to keep every digit and raise no signal at a precision far below
  the operand's width. `same_quantum()` is asserted by behaviour only.
* Comparison. Two coefficients differing only in the last digit cost more
  than 10x as much at 200,000 digits as at 2,000; two differing in the first
  digit stay within 2x. An operand whose extra digits are the only thing
  deciding equality costs more than 10x over the same step, which is why the
  row is O(n + m) and not O(min(n, m)). `compare()` is asserted to return a
  `Decimal`, `compare_signal()` to raise on a NaN operand,
  `compare_total()` to order one.
* Context. `flags` and `traps` are the same object on every access;
  `setcontext()` is asserted to copy `BasicContext` and to install an
  ordinary `Context` as it stands; `localcontext()` is asserted to take its
  copy when the manager is built rather than when it is entered;
  `Context.copy()` returns a new object; the pre-made contexts keep their
  documented `prec` and traps; out-of-range `prec` raises `ValueError`;
  `copy_decimal()` raises `TypeError` on a string. Every `Context` arithmetic
  method named in the page's "as the operator" rows is asserted to agree with
  the operator or `Decimal` method it stands for.
* Signals. `10/0` raises `DivisionByZero` and `0/0` raises
  `InvalidOperation`; an untrapped `Inexact` sets a flag rather than raising,
  and the trap turns it into an exception; `Overflow`, `Subnormal`,
  `Underflow` and `FloatOperation` are raised or flagged from their own
  conditions, and `FloatOperation` is asserted to reach `Decimal(float)` and
  `create_decimal()` but not the two explicit float spellings. The four
  condition classes are asserted to be `InvalidOperation` subclasses.
* Special values. An infinity's coefficient is one digit and adding to it
  costs under a third of adding two 20,000-digit coefficients. A NaN is the
  same until it carries a payload: propagating a 200,000-digit payload costs
  more than 3x propagating a 10-digit one, which is why the page prices the
  payload as digits.
* Every fenced Python block runs in its own subprocess, so a context change
  cannot leak between them; the block chosen for the mutation test is
  asserted to pass unmutated and to fail once one of its assertions is
  flipped.

Not settled here:

* Where libmpdec switches from schoolbook to Karatsuba and then to a
  number-theoretic transform. The dispatch is read from
  Modules/_decimal/libmpdec/mpdecimal.c on the 3.14 branch; the tests measure
  only that short coefficients are quadratic and that a fixed small operand
  leaves the other one linear.
* The exact exponent of `exp()`, `ln()`, `log10()` and non-integer `**`. The
  page says superquadratic and the tests hold them to that over one precision
  interval, against a `sqrt()` measured on the same step. No degree is
  claimed, and no interval beyond 250 to 2,000 digits is measured.
* The `min(g, p)` term of addition is measured at its two ends - a gap the
  precision discards and a gap it keeps - not across the crossover.
* `Decimal.from_number()`, `decimal.IEEEContext()` and
  `decimal.IEEE_CONTEXT_MAX_BITS` exist from 3.14 only, so their tests are
  guarded on `sys.version_info` and do not run on the rest of the matrix.
  The same holds for `localcontext()`'s keyword attributes, which are 3.11+.
* Space is settled by traced peaks in three places: `quantize()` shrinking a
  200,000-digit coefficient to three digits peaks under 4 KB where rendering
  the same operand peaks over 100 KB, and `Decimal(str)` and `float()` each
  grow their peak more than 10x over a 100x input while the thing they return
  stays the same size - a one-digit coefficient and a double. `+a` and
  `create_decimal()` are measured the same way, for a five-digit result out of
  100x the coefficient and out of 100x the leading zeros, which is the O(n + p)
  and the constructor's O(L) those rows carry. Every other space cell is read
  from the result's digit count, `fma()`'s k term included.
* Dimensions the measurements hold fixed: sign, rounding mode, `Emin` and
  `Emax`, `clamp`, subnormal operands, and threading. Every timing test runs
  under the default context's `Emin`/`Emax` with a precision it sets itself.
* The audit reports 30 names as unclassified for this page - the pre-made
  contexts' inherited attributes, `Decimal.real`, `Decimal.imag`,
  `Context.to_integral`, `Context.to_integral_value`, `DecimalTuple` and its
  fields, and the four `InvalidOperation` conditions. All of them are priced
  in the page's tables; they are absent from the official inventory, not from
  the page.
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
from decimal import (
    ROUND_05UP,
    ROUND_CEILING,
    ROUND_DOWN,
    ROUND_FLOOR,
    ROUND_HALF_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    ROUND_UP,
    BasicContext,
    Clamped,
    Context,
    ConversionSyntax,
    Decimal,
    DecimalException,
    DecimalTuple,
    DefaultContext,
    DivisionByZero,
    DivisionImpossible,
    DivisionUndefined,
    ExtendedContext,
    FloatOperation,
    Inexact,
    InvalidContext,
    InvalidOperation,
    Overflow,
    Rounded,
    Subnormal,
    Underflow,
    getcontext,
    localcontext,
    setcontext,
)
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "decimal.md"
EXPECTED_BLOCKS = 13


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
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def digits(value: Decimal) -> int:
    """Digits in the coefficient - the page's n, m and r."""
    return len(value.as_tuple().digits)


def wide(count: int) -> Decimal:
    """A coefficient of `count` digits, just over 1, with nothing but nines
    after the point - so a rounding never carries into an extra digit."""
    return Decimal("1." + "9" * (count - 1))


def whole(count: int) -> Decimal:
    """An integer-valued coefficient of `count` digits, so `int()` has all of
    them to convert rather than truncating to the part before the point."""
    return Decimal("9" * count)


def other(count: int) -> Decimal:
    """A different coefficient of `count` digits, built from a literal so the
    active precision never reaches it."""
    return Decimal("2." + "7" * (count - 1))


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
        timeout=300,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestTheConstructorDoesNotRound:
    """`Decimal(value)` | "the precision is not consulted".

    The plausible wrong version is that construction rounds like every other
    operation. Digit counts and the `Inexact` flag separate the two with no
    tolerance. What the constructor does still take from the context is the
    traps, which is the distinction the page draws.
    """

    def test_every_digit_survives_a_narrow_precision(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            assert digits(Decimal("1" * 50)) == 50

    def test_construction_raises_no_signal(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            ctx.clear_flags()
            Decimal("1" * 50)
            assert ctx.flags[Inexact] is False
            assert ctx.flags[Rounded] is False

    def test_unary_plus_is_what_rounds(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            ctx.clear_flags()
            assert digits(+Decimal("1" * 50)) == 5
            assert ctx.flags[Inexact] is True

    def test_create_decimal_rounds_where_the_constructor_does_not(self) -> None:
        ctx = Context(prec=5)
        assert digits(ctx.create_decimal("1" * 50)) == 5
        assert digits(Decimal("1" * 50)) == 50

    @pytest.mark.timing
    def test_create_decimal_cost_grows_with_the_input_digits(self) -> None:
        """The n term of its row - the n-dependent rounding and conversion
        path, not the discarded-digit scan in isolation. The result is five
        digits either way."""
        ctx = Context(prec=5)
        small = Decimal("1." + "0" * 1_999)
        large = Decimal("1." + "0" * 199_999)
        assert digits(ctx.create_decimal(large)) == digits(ctx.create_decimal(small)) == 5
        ratio = best_ns(lambda: ctx.create_decimal(large), inner=20) / best_ns(
            lambda: ctx.create_decimal(small), inner=20
        )
        assert ratio > 4.0, f"100x the discarded digits cost {ratio:.1f}x"

    @pytest.mark.serial
    def test_rounding_a_wide_value_holds_it_while_it_rounds(self) -> None:
        """The O(n + p) space of `+a` and of `create_decimal()`, plus the
        O(L) the latter inherits from the constructor. The coefficient pairs
        round to five digits and the leading-zero pair to one, so in every
        case only a temporary the size of the input explains the peak."""
        small_text, large_text = "1." + "9" * 1_999, "1." + "9" * 199_999
        padded_small, padded_large = "0" * 2_000 + "1", "0" * 200_000 + "1"
        ctx = Context(prec=5)

        with localcontext() as inner:
            inner.prec = 5
            small, large = Decimal(small_text), Decimal(large_text)
            assert digits(+large) == digits(+small) == 5
            small_unary_peak = peak_bytes(lambda: +small)
            unary_growth = peak_bytes(lambda: +large) / max(small_unary_peak, 1)

        assert unary_growth > 10.0, (
            f"100x the coefficient for the same 5-digit result grew the peak {unary_growth:.1f}x"
        )

        assert digits(ctx.create_decimal(large_text)) == digits(ctx.create_decimal(small_text)) == 5
        small_created_peak = peak_bytes(lambda: ctx.create_decimal(small_text))
        created_growth = peak_bytes(lambda: ctx.create_decimal(large_text)) / max(
            small_created_peak, 1
        )
        assert created_growth > 10.0, (
            f"create_decimal() on 100x the digits grew the peak {created_growth:.1f}x"
        )

        assert (
            digits(ctx.create_decimal(padded_large))
            == digits(ctx.create_decimal(padded_small))
            == 1
        )
        small_padded_peak = peak_bytes(lambda: ctx.create_decimal(padded_small))
        padded_growth = peak_bytes(lambda: ctx.create_decimal(padded_large)) / max(
            small_padded_peak, 1
        )
        assert padded_growth > 10.0, (
            f"create_decimal() carries the constructor's O(L): 100x the leading "
            f"zeros grew the peak {padded_growth:.1f}x"
        )

    def test_copy_decimal_hands_back_the_same_object(self) -> None:
        ctx = Context(prec=5)
        unrounded = Decimal("1" * 50)
        assert ctx.copy_decimal(unrounded) is unrounded
        assert ctx.copy_decimal(5) == Decimal(5)
        for rejected in ("1.5", 0.5):
            with pytest.raises(TypeError):
                ctx.copy_decimal(cast("Any", rejected))

    def test_the_constructor_hands_back_a_decimal_unchanged(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            unrounded = Decimal("1" * 50)
            assert Decimal(unrounded) is unrounded

    def test_the_traps_still_reach_it(self) -> None:
        """Not rounding is not the same as ignoring the context."""
        with localcontext() as ctx:
            ctx.prec = 5
            with pytest.raises(InvalidOperation):
                Decimal("not a number")

            ctx.traps[FloatOperation] = True
            with pytest.raises(FloatOperation):
                Decimal(0.1)
            assert Decimal.from_float(0.1) == Decimal(Decimal.from_float(0.1))

    def test_copy_abs_and_friends_do_not_round(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            ctx.clear_flags()
            negative = Decimal("-" + "1" * 50)
            assert digits(negative.copy_abs()) == 50
            assert digits(negative.copy_negate()) == 50
            assert digits(negative.copy_sign(Decimal(1))) == 50
            assert not any(ctx.flags.values()), "copy_* signalled"


class TestConstructionBounds:
    """`Decimal(str)` is O(n) where `Decimal(int)` is O(n²).

    Both are conversions of the same value; only the base differs. Four times
    the digits separates them by a factor of four: linear predicts 4x,
    quadratic 16x, and the thresholds sit at 6x and 8x.
    """

    SMALL = 20_000
    LARGE = 80_000

    @pytest.mark.timing
    def test_parsing_a_decimal_string_is_linear(self) -> None:
        small = "9" * self.SMALL
        large = "9" * self.LARGE
        ratio = best_ns(lambda: Decimal(large)) / best_ns(lambda: Decimal(small))
        assert ratio < 6.0, f"4x the digits should cost about 4x, not {ratio:.1f}x"

    @pytest.mark.timing
    def test_converting_an_integer_is_not(self) -> None:
        small = 10**self.SMALL - 1
        large = 10**self.LARGE - 1
        with localcontext() as ctx:
            ctx.prec = self.LARGE + 10
            ratio = best_ns(lambda: Decimal(large)) / best_ns(lambda: Decimal(small))
        assert ratio > 8.0, f"base conversion should be superlinear, not {ratio:.1f}x for 4x"

    def test_parsing_is_priced_by_the_characters_not_the_digits(self) -> None:
        padded = Decimal("0" * 1_000 + "1")
        assert digits(padded) == 1

    @pytest.mark.timing
    def test_leading_zeros_cost_what_digits_cost(self) -> None:
        small = "0" * 2_000 + "1"
        large = "0" * 200_000 + "1"
        ratio = best_ns(lambda: Decimal(large)) / best_ns(lambda: Decimal(small))
        assert ratio > 10.0, (
            f"a one-digit coefficient behind 100x the characters cost {ratio:.1f}x, "
            f"so the bound is in the string and not the coefficient"
        )

    @pytest.mark.timing
    def test_int_is_the_conversion_back_and_float_is_not(self) -> None:
        with localcontext() as ctx:
            ctx.prec = self.LARGE + 10
            small, large = whole(self.SMALL), whole(self.LARGE)
            to_int = best_ns(lambda: int(large), repeats=3) / best_ns(lambda: int(small), repeats=3)
            to_float = best_ns(lambda: float(large), inner=20) / best_ns(
                lambda: float(small), inner=20
            )
        assert to_int > 8.0, f"int() should be superlinear, not {to_int:.1f}x for 4x"
        assert to_float < 6.0, f"float() should be linear, not {to_float:.1f}x for 4x"

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("name", "sign", "call"),
        [
            ("int", "+", lambda value: int(value)),
            ("round", "+", lambda value: round(value)),
            ("as_integer_ratio numerator", "+", lambda value: value.as_integer_ratio()),
            ("as_integer_ratio denominator", "-", lambda value: value.as_integer_ratio()),
        ],
    )
    def test_the_exponent_is_a_size_when_it_has_to_be_written_out(
        self, name: str, sign: str, call: Callable[[Decimal], Any]
    ) -> None:
        """One coefficient digit either way: only the exponent grows."""
        small, large = Decimal(f"1E{sign}5000"), Decimal(f"1E{sign}20000")
        assert digits(small) == digits(large) == 1
        with localcontext() as ctx:
            ctx.prec = 100_000
            ratio = best_ns(lambda: call(large), repeats=3) / best_ns(
                lambda: call(small), repeats=3
            )
        assert ratio > 8.0, (
            f"{name}() on 4x the exponent cost {ratio:.1f}x at one coefficient digit"
        )

    def test_a_float_expansion_is_bounded_by_the_format(self) -> None:
        widest_denormal = sys.float_info.min - 5e-324
        assert digits(Decimal(widest_denormal)) == 767
        assert digits(Decimal(sys.float_info.max)) == 309
        assert digits(Decimal(0.1)) == 55

    def test_from_float_matches_the_constructor(self) -> None:
        assert Decimal.from_float(0.1) == Decimal(0.1)
        assert Decimal.from_float(0.1) != Decimal("0.1")

    @pytest.mark.timing
    def test_a_float_costs_the_same_however_wide_its_expansion(self) -> None:
        widest = sys.float_info.min - 5e-324
        narrowest = sys.float_info.max
        ratio = best_ns(lambda: Decimal(widest), inner=50) / best_ns(
            lambda: Decimal(narrowest), inner=50
        )
        assert ratio < 4.0, f"767 digits against 309 should not cost {ratio:.1f}x"

    @pytest.mark.serial
    def test_parsing_holds_the_string_and_float_holds_the_coefficient(self) -> None:
        """The O(L) and O(n) space cells, each against the bounded result it
        returns: a one-digit coefficient and a double."""
        short, long_literal = "0" * 2_000 + "1", "0" * 200_000 + "1"
        assert digits(Decimal(long_literal)) == digits(Decimal(short)) == 1
        small_peak = peak_bytes(lambda: Decimal(short))
        parse_growth = peak_bytes(lambda: Decimal(long_literal)) / max(small_peak, 1)
        assert parse_growth > 10.0, (
            f"100x the characters behind the same one-digit coefficient grew the "
            f"peak {parse_growth:.1f}x, so the space is in the string"
        )

        with localcontext() as ctx:
            ctx.prec = 300_000
            small, large = wide(2_000), wide(200_000)
            float(small)
            float(large)
            small_float_peak = peak_bytes(lambda: float(small))
            float_growth = peak_bytes(lambda: float(large)) / max(small_float_peak, 1)
        assert float_growth > 10.0, (
            f"float() returns a double either way, but 100x the coefficient grew "
            f"the peak {float_growth:.1f}x"
        )

    def test_as_tuple_builds_a_fresh_tuple_each_time(self) -> None:
        value = Decimal("1.5")
        assert value.as_tuple() is not value.as_tuple()
        assert value.as_tuple() == DecimalTuple(sign=0, digits=(1, 5), exponent=-1)
        assert Decimal(cast("Any", value.as_tuple())) == value

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="from_number is 3.14+")
    def test_from_number_dispatches_to_the_three_cases(self) -> None:
        from_number = cast("Any", Decimal).from_number
        assert from_number(314) == Decimal(314)
        assert from_number(0.1) == Decimal(0.1)
        assert from_number(Decimal("3.14")) == Decimal("3.14")


class TestRenderingRendersWhatItKeeps:
    """`str(d)` | O(n) against `format(d, spec)` | O(r + n).

    `str()` has to produce every digit; a format spec naming a precision
    rounds first and produces r of them. A coefficient of nines makes the
    inexactness visible at the first discarded digit, which is where the
    O(r) side of the format bound shows; the zeros case below is the n side.
    """

    SMALL = 20_000
    LARGE = 200_000

    @pytest.mark.timing
    def test_str_renders_every_digit(self) -> None:
        with localcontext() as ctx:
            ctx.prec = self.LARGE + 10
            small, large = wide(self.SMALL), wide(self.LARGE)
            ratio = best_ns(lambda: str(large)) / best_ns(lambda: str(small))
        assert ratio > 5.0, f"10x the digits should cost about 10x, not {ratio:.1f}x"

    @pytest.mark.timing
    def test_a_precision_in_the_spec_renders_only_what_it_keeps(self) -> None:
        with localcontext() as ctx:
            ctx.prec = self.LARGE + 10
            small, large = wide(self.SMALL), wide(self.LARGE)
            ratio = best_ns(lambda: format(large, ".2f"), inner=20) / best_ns(
                lambda: format(small, ".2f"), inner=20
            )
        assert ratio < 2.0, f"a 3-digit result should not cost 10x more, got {ratio:.1f}x"

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("name", "call"),
        [
            ("format", lambda value: format(value, ".2f")),
            ("round", lambda value: round(value, 2)),
            ("to_integral_value", lambda value: value.to_integral_value()),
        ],
    )
    def test_a_zero_tail_is_scanned_which_is_the_n_term(
        self, name: str, call: Callable[[Decimal], Any]
    ) -> None:
        with localcontext() as ctx:
            ctx.prec = self.LARGE + 10
            small = Decimal("1." + "0" * 1_999)
            large = Decimal("1." + "0" * (self.LARGE - 1))
            ratio = best_ns(lambda: call(large), inner=20) / best_ns(lambda: call(small), inner=20)
        assert ratio > 10.0, (
            f"{name}() has nothing non-zero to stop the scan at, so it is linear: "
            f"{ratio:.1f}x for 100x the digits"
        )

    def test_a_field_width_writes_what_it_asks_for(self) -> None:
        one = Decimal(1)
        assert digits(one) == 1
        assert len(format(one, "1000000.0f")) == 1_000_000

    def test_the_renderers_agree_on_a_small_value(self) -> None:
        value = Decimal("1.23456E+7")
        assert str(value) == "1.23456E+7"
        assert repr(value) == "Decimal('1.23456E+7')"
        assert value.to_eng_string() == "12.3456E+6"
        assert format(value, ".2f") == "12345600.00"
        assert Context(prec=9).to_sci_string(value) == "1.23456E+7"
        assert Context(prec=9).to_eng_string(value) == "12.3456E+6"

    def test_a_large_exponent_renders_short(self) -> None:
        assert str(Decimal("1E+999999")) == "1E+999999"
        assert Decimal("1E+999999").as_tuple() == (0, (1,), 999999)


class TestAdditionReadsCoefficientsNotExponents:
    """`a + b` | O(n + m) | "a gap between the exponents is not materialised".

    The wrong version - aligning the operands by padding out the gap - would
    make a 1e8 gap eight orders of magnitude dearer than a 1e2 one. It is
    not, and the same addition does grow with the coefficients.
    """

    @pytest.mark.timing
    def test_the_exponent_gap_does_not_cost_anything(self) -> None:
        one = Decimal(1)
        near, far = Decimal("1E-2"), Decimal("1E-100000000")
        ratio = best_ns(lambda: one + far, inner=200) / best_ns(lambda: one + near, inner=200)
        assert ratio < 2.0, f"a 1e8 gap should cost what a 1e2 gap does, not {ratio:.1f}x"

    @pytest.mark.timing
    def test_the_coefficients_do(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 28
            small_a, small_b = wide(2_000), other(2_000)
            large_a, large_b = wide(64_000), other(64_000)
            ratio = best_ns(lambda: large_a + large_b, inner=20) / best_ns(
                lambda: small_a + small_b, inner=20
            )
        assert ratio > 8.0, f"32x the digits should cost far more than {ratio:.1f}x"

    def test_a_gap_wider_than_the_precision_leaves_the_value_alone(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 28
            huge, tiny = Decimal("1E+999999"), Decimal("1E-999999")
            assert huge + tiny == huge
            # A materialised gap would be two million digits wide
            assert digits(huge + tiny) <= ctx.prec

    def test_a_gap_the_precision_keeps_is_materialised(self) -> None:
        """The min(g, p) term: widen p past the gap and the digits appear."""
        near, far = Decimal(1), Decimal("1E-2000")
        assert digits(near) == digits(far) == 1
        with localcontext() as ctx:
            ctx.prec = 3_000
            assert digits(near + far) == 2_001
        with localcontext() as ctx:
            ctx.prec = 28
            assert digits(near + far) == 28


class TestMultiplicationIsTheProductOfTheOperands:
    """`a * b` | O(n·m).

    Two claims in one row, and they need different inputs. Growing both
    operands together shows the product term; holding one at 50 digits while
    the other grows shows that the bound is n·m and not max(n, m)². The
    sizes for the first are small enough to stay in libmpdec's schoolbook
    range, where the row's n·m is what runs.
    """

    @pytest.mark.timing
    def test_equal_operands_grow_quadratically(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            small_a, small_b = wide(200), other(200)
            large_a, large_b = wide(800), other(800)
            ratio = best_ns(lambda: large_a * large_b, inner=20) / best_ns(
                lambda: small_a * small_b, inner=20
            )
        assert ratio > 10.0, (
            f"4x both operands should cost about 16x, not {ratio:.1f}x - linear would be 4x"
        )

    @pytest.mark.timing
    def test_a_fixed_small_operand_leaves_the_other_linear(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            fixed = wide(50)
            small, large = wide(2_000), wide(128_000)
            ratio = best_ns(lambda: large * fixed, inner=5) / best_ns(
                lambda: small * fixed, inner=5
            )
        assert 16.0 < ratio < 128.0, (
            f"64x one operand at a fixed other should stay near 64x, not {ratio:.1f}x"
        )

    def test_the_exact_product_is_as_wide_as_both_operands(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 200
            a, b = Decimal("1." + "9" * 49), Decimal("2." + "7" * 49)
            assert digits(a) == 50 and digits(b) == 50
            assert digits(a * b) == 99

    def test_fma_rounds_once_at_the_end(self) -> None:
        # 251 * 4 is 1004, which a 3-digit precision rounds to 1.00E+3. Adding
        # -1000 to the rounded product loses the 4; fma never rounds it away.
        with localcontext() as ctx:
            ctx.prec = 3
            a, b, c = Decimal(251), Decimal(4), Decimal(-1000)
            assert a.fma(b, c) == Decimal(4)
            assert a * b + c == Decimal(0)
            assert Context(prec=3).fma(a, b, c) == Decimal(4)


class TestDivisionStopsAtThePrecision:
    """`a / b` | O(n + p·m).

    Three terms, three inputs: the dividend at a fixed precision (n), the
    precision at fixed short operands (p, with m held small), and both
    together (p·m). The first two are linear and the third is not, which is
    what distinguishes the bound from a flat O(p²) or O(n·m).
    """

    def test_the_quotient_is_exactly_prec_digits(self) -> None:
        a, b = Decimal("1." + "9" * 49), Decimal("2." + "7" * 49)
        for precision in (10, 60):
            with localcontext() as ctx:
                ctx.prec = precision
                assert digits(a / b) == precision

    @pytest.mark.timing
    def test_the_dividend_is_linear_at_a_fixed_precision(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 28
            divisor = Decimal("2.7")
            small, large = wide(16_000), wide(64_000)
            ratio = best_ns(lambda: large / divisor, inner=5) / best_ns(
                lambda: small / divisor, inner=5
            )
        assert ratio < 8.0, f"4x the dividend should cost about 4x, not {ratio:.1f}x"

    @pytest.mark.timing
    def test_the_precision_is_linear_at_a_fixed_divisor_width(self) -> None:
        a, b = Decimal("1." + "9" * 29), Decimal("2." + "7" * 29)

        def at(precision: int) -> float:
            with localcontext() as ctx:
                ctx.prec = precision
                return best_ns(lambda: a / b, inner=20)

        ratio = at(6_400) / at(1_600)
        assert ratio < 8.0, f"4x the precision at m=30 should cost about 4x, not {ratio:.1f}x"

    @pytest.mark.timing
    def test_precision_and_operands_together_are_not(self) -> None:
        def at(precision: int) -> float:
            with localcontext() as ctx:
                ctx.prec = precision
                a, b = wide(precision), other(precision)
                return best_ns(lambda: a / b, inner=5)

        ratio = at(4_000) / at(1_000)
        assert ratio > 8.0, f"p and m both 4x should cost about 16x, not {ratio:.1f}x"

    def test_integer_division_and_remainder_follow_the_same_path(self) -> None:
        a, b = Decimal("100"), Decimal("7")
        assert a // b == Decimal("14")
        assert a % b == Decimal("2")
        assert divmod(a, b) == (Decimal("14"), Decimal("2"))
        # remainder_near takes the nearest multiple, so it can go negative
        assert a.remainder_near(b) == Decimal("2")
        assert Decimal("11") % Decimal("7") == Decimal("4")
        assert Decimal("11").remainder_near(Decimal("7")) == Decimal("-3")

    def test_a_quotient_wider_than_the_precision_signals(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            with pytest.raises(InvalidOperation):
                _ = Decimal("1" * 10) // Decimal(1)


class TestPowers:
    """`a ** k` | O(log k) multiplications against a non-integer exponent
    routed through `exp(b * ln(a))`.

    A 16,384x exponent costing under 20x is binary exponentiation; repeated
    multiplication would be 16,384x.
    """

    @pytest.mark.timing
    def test_an_integer_exponent_costs_its_logarithm(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 200
            base = wide(200)
            ratio = best_ns(lambda: base**65_536, repeats=3) / best_ns(lambda: base**4, repeats=3)
        assert ratio < 20.0, (
            f"16,384x the exponent should cost about 14 more steps, not {ratio:.1f}x"
        )

    def test_a_half_power_is_the_square_root(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 28
            assert Decimal(2) ** Decimal("0.5") == Decimal(2).sqrt()
            assert Decimal(2) ** 10 == Decimal(1024)

    def test_a_modulus_makes_it_exact_integer_arithmetic(self) -> None:
        assert pow(Decimal(2), Decimal(1000), Decimal(7)) == Decimal(2)
        with pytest.raises(InvalidOperation):
            pow(Decimal("1.5"), Decimal(2), Decimal(7))

    def test_context_power_agrees_with_the_operator(self) -> None:
        ctx = Context(prec=9)
        assert ctx.power(Decimal(2), Decimal(10)) == Decimal(2) ** 10
        assert ctx.power(Decimal(2), Decimal(1000), Decimal(7)) == Decimal(2)


class TestTranscendentalsAreSuperquadratic:
    """`exp()`, `ln()`, `log10()` | superquadratic in p, against
    `sqrt()` | O(p²).

    The page's claim is comparative, so the test is too: the same 8x
    precision step is applied to both. A quadratic operation predicts 64x.
    The thresholds bracket that - under 100x leaves room for noise above 64x
    while still excluding the series functions, which come in past 150x.
    """

    SMALL_PREC = 250
    LARGE_PREC = 2_000
    QUADRATIC_AT_8X = 100.0
    SUPERQUADRATIC_AT_8X = 150.0

    @staticmethod
    def _ratio(call: Callable[[Decimal], Decimal], repeats: int) -> float:
        def at(precision: int) -> float:
            with localcontext() as ctx:
                ctx.prec = precision
                two = Decimal(2)
                call(two)  # warm the code object before measuring
                return best_ns(lambda: call(two), repeats=repeats)

        return at(TestTranscendentalsAreSuperquadratic.LARGE_PREC) / at(
            TestTranscendentalsAreSuperquadratic.SMALL_PREC
        )

    @pytest.mark.timing
    def test_sqrt_stays_quadratic(self) -> None:
        ratio = self._ratio(Decimal.sqrt, repeats=5)
        assert ratio < self.QUADRATIC_AT_8X, (
            f"8x the precision should cost about 64x for a quadratic sqrt, not {ratio:.1f}x"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["exp", "ln", "log10"])
    def test_the_series_functions_do_not(self, name: str) -> None:
        ratio = self._ratio(getattr(Decimal, name), repeats=3)
        assert ratio > self.SUPERQUADRATIC_AT_8X, (
            f"{name}() should outgrow a quadratic's 64x for 8x the precision, got {ratio:.1f}x"
        )

    @pytest.mark.timing
    def test_a_non_integer_power_costs_both_of_them(self) -> None:
        half = Decimal("0.5")
        ratio = self._ratio(lambda base: base**half, repeats=3)
        assert ratio > self.SUPERQUADRATIC_AT_8X, (
            f"a non-integer ** goes through exp(b * ln(a)), so it should outgrow "
            f"a quadratic's 64x for 8x the precision, got {ratio:.1f}x"
        )

    def test_they_are_correctly_rounded_at_the_working_precision(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 9
            assert Decimal(1).exp() == Decimal("2.71828183")
            assert Decimal("2.71828183").ln() == Decimal("1.00000000")
            assert Decimal(1000).log10() == Decimal(3)
            assert Decimal(2).sqrt() == Decimal("1.41421356")


class TestRoundingIsPricedByTheResult:
    """`quantize()` | O(r + n) | O(r).

    The result is r digits whatever the operand holds - that is the O(r)
    space, settled here by a traced peak against rendering the same operand.
    The n term is the scan for `Inexact`, which stops at the first non-zero
    digit; it is measured in TestRenderingRendersWhatItKeeps on a zero tail,
    where there is nothing to stop at.
    """

    def test_the_result_is_as_wide_as_the_exponent_asks(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 200_000
            value = wide(100_000)
            cents = value.quantize(Decimal("0.01"))
            assert digits(cents) == 3
            assert cents == Decimal("2.00")

    @pytest.mark.timing
    def test_the_operand_width_does_not_reach_the_result(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            cents = Decimal("0.01")
            small, large = wide(2_000), wide(200_000)
            ratio = best_ns(lambda: large.quantize(cents), inner=20) / best_ns(
                lambda: small.quantize(cents), inner=20
            )
        assert ratio < 2.0, f"100x the operand for a 3-digit result cost {ratio:.1f}x"

    @pytest.mark.timing
    def test_the_result_width_does(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            value = wide(200_000)
            narrow, broad = Decimal("1E-2"), Decimal("1E-199999")
            ratio = best_ns(lambda: value.quantize(broad), repeats=5) / best_ns(
                lambda: value.quantize(narrow), repeats=5
            )
        assert ratio > 2.0, f"keeping 200,000 digits instead of 3 cost {ratio:.1f}x"

    @pytest.mark.serial
    def test_shrinking_to_three_digits_allocates_three_digits(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            value = wide(200_000)
            cents = Decimal("0.01")
            value.quantize(cents)  # warm the code object before tracing
            str(value)
            rounded_peak = peak_bytes(lambda: value.quantize(cents))
            rendered_peak = peak_bytes(lambda: str(value))

        assert rounded_peak < 4_096, f"a 3-digit result peaked at {rounded_peak} bytes"
        assert rendered_peak > 100_000, (
            f"rendering the same operand should be the O(n) control, "
            f"but it peaked at only {rendered_peak} bytes"
        )

    def test_round_with_a_second_argument_is_the_same_operation(self) -> None:
        value = Decimal("1.9999")
        assert round(value, 2) == value.quantize(Decimal("0.01"))

    def test_round_without_one_is_not(self) -> None:
        with localcontext() as ctx:
            ctx.rounding = ROUND_UP
            assert round(Decimal("2.5")) == 2
            assert isinstance(round(Decimal("2.5")), int)
            assert Decimal("2.5").quantize(Decimal(1)) == Decimal(3)

    def test_to_integral_value_has_no_precision_check(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 2
            assert Decimal("123").to_integral_value() == Decimal("123")
            assert Decimal("123").to_integral() == Decimal("123")
            with pytest.raises(InvalidOperation):
                Decimal("123").quantize(Decimal(1))

    def test_to_integral_exact_signals_where_to_integral_value_does_not(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 9
            ctx.clear_flags()
            assert Decimal("1.5").to_integral_value() == Decimal(2)
            assert not any(ctx.flags.values())

            assert Decimal("1.5").to_integral_exact() == Decimal(2)
            assert ctx.flags[Inexact] is True
            assert ctx.flags[Rounded] is True

            assert Decimal("1.5").to_integral() == Decimal(2)

    def test_the_rounding_mode_picks_the_digit(self) -> None:
        value = Decimal("2.675")
        cents = Decimal("0.01")
        assert value.quantize(cents, rounding=ROUND_HALF_UP) == Decimal("2.68")
        assert value.quantize(cents, rounding=ROUND_HALF_DOWN) == Decimal("2.67")
        assert value.quantize(cents, rounding=ROUND_HALF_EVEN) == Decimal("2.68")
        assert value.quantize(cents, rounding=ROUND_DOWN) == Decimal("2.67")
        assert value.quantize(cents, rounding=ROUND_UP) == Decimal("2.68")
        assert value.quantize(cents, rounding=ROUND_CEILING) == Decimal("2.68")
        assert value.quantize(cents, rounding=ROUND_FLOOR) == Decimal("2.67")
        # ROUND_05UP rounds away from zero only when the kept digit is 0 or 5
        assert value.quantize(cents, rounding=ROUND_05UP) == Decimal("2.67")
        assert Decimal("2.605").quantize(cents, rounding=ROUND_05UP) == Decimal("2.61")


class TestDigitManipulation:
    """`shift()`, `rotate()` and the `logical_*` family | O(n + p) | O(p).

    All five take the coefficient to p digits before doing anything, so the
    result is p digits wide however narrow the operand was.
    """

    def test_shift_and_rotate_work_on_a_p_digit_coefficient(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 9
            value = Decimal("1" * 20)
            assert value.shift(3) == Decimal("111111000")
            assert value.rotate(3) == Decimal("111111111")
            # At most p digits: leading zeros are not kept
            assert digits(Decimal(1).rotate(2)) == 3
            assert digits(value.shift(3)) <= ctx.prec

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("name", "build", "call"),
        [
            # normalize() stops at the first non-zero from the right, so its
            # input needs a tail of zeros for it to walk.
            (
                "normalize",
                lambda count: Decimal("1" * (count // 2) + "0" * (count // 2)),
                lambda value: value.normalize(),
            ),
            ("shift", lambda count: Decimal("1" * count), lambda value: value.shift(3)),
            ("rotate", lambda count: Decimal("1" * count), lambda value: value.rotate(3)),
            (
                "logical_and",
                lambda count: Decimal("1" * count),
                lambda value: value.logical_and(value),
            ),
            (
                "logical_invert",
                lambda count: Decimal("1" * count),
                lambda value: value.logical_invert(),
            ),
            ("next_plus", lambda count: Decimal("1" * count), lambda value: value.next_plus()),
        ],
    )
    def test_they_grow_with_the_digits_they_touch(
        self,
        name: str,
        build: Callable[[int], Decimal],
        call: Callable[[Decimal], Decimal],
    ) -> None:
        def at(count: int) -> float:
            with localcontext() as ctx:
                ctx.prec = count
                value = build(count)
                call(value)
                return best_ns(lambda: call(value), inner=20)

        ratio = at(20_000) / at(2_000)
        assert ratio > 4.0, f"{name}() grew only {ratio:.1f}x over 10x the digits"

    @pytest.mark.timing
    def test_the_logical_family_reads_its_second_operand_too(self) -> None:
        """The m term: the first operand is fixed at 2,000 digits."""
        with localcontext() as ctx:
            ctx.prec = 200_000
            first = Decimal("1" * 2_000)
            small, large = Decimal("1" * 2_000), Decimal("1" * 200_000)
            ratio = best_ns(lambda: first.logical_and(large), inner=5) / best_ns(
                lambda: first.logical_and(small), inner=5
            )
        assert ratio > 4.0, f"100x the second operand cost {ratio:.1f}x"

    def test_the_logical_family_needs_binary_operands(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 9
            assert Decimal(1100).logical_and(Decimal(1010)) == Decimal(1000)
            assert Decimal(1100).logical_or(Decimal(1010)) == Decimal(1110)
            assert Decimal(1100).logical_xor(Decimal(1010)) == Decimal(110)
            assert Decimal(1).logical_invert() == Decimal("111111110")
            with pytest.raises(InvalidOperation):
                Decimal(12).logical_and(Decimal(11))
            # A digit outside the retained width is validated all the same
            with pytest.raises(InvalidOperation):
                Decimal("2" + "1" * 10).logical_and(Decimal("11111"))

    def test_normalize_strips_trailing_zeros(self) -> None:
        assert Decimal("1.2300").normalize() == Decimal("1.23")
        assert digits(Decimal("1.2300").normalize()) == 3
        assert Decimal("1E+2").normalize() == Decimal("1E+2")

    def test_scaleb_moves_the_exponent(self) -> None:
        assert Decimal("1.5").scaleb(3) == Decimal("1.5E+3")
        assert digits(Decimal("1.5").scaleb(3)) == 2

    def test_the_neighbours_are_at_the_working_precision(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 9
            assert Decimal(1).next_plus() == Decimal("1.00000001")
            assert Decimal(1).next_minus() == Decimal("0.999999999")
            # next_toward has to compare the two first, which is its n + m term
            assert Decimal(1).next_toward(Decimal(2)) == Decimal("1.00000001")
            assert Decimal(1).next_toward(Decimal(0)) == Decimal("0.999999999")
            assert Decimal(1).next_toward(Decimal(1)) == Decimal(1)


class TestConstantTimeAccessors:
    """The O(1) rows: `canonical()`, `conjugate()`, `.real`, `.imag`,
    `radix()`, `number_class()`, `same_quantum()`, `logb()`, `adjusted()`
    and the ten `is_*` predicates.

    Identity settles the first three with no tolerance - an O(n) reading
    would have to build something. The rest are measured flat across a 100x
    operand, which is what separates O(1) from a coefficient scan.
    """

    def test_the_three_that_return_the_same_object(self) -> None:
        value = Decimal("1" * 1000)
        assert value.canonical() is value
        assert value.conjugate() is value
        assert value.real is value
        assert value.imag == Decimal(0)

    def test_the_copies_are_copies(self) -> None:
        value = Decimal("1" * 1000)
        negated = Decimal("-" + "1" * 1000)
        assert value.copy_abs() is not value
        assert value.copy_abs() == value
        assert value.copy_negate() == negated
        assert value.copy_sign(Decimal(-1)) == negated

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "call",
        [
            Decimal.radix,
            Decimal.number_class,
            Decimal.logb,
            Decimal.adjusted,
            Decimal.is_canonical,
            Decimal.is_finite,
            Decimal.is_infinite,
            Decimal.is_nan,
            Decimal.is_normal,
            Decimal.is_qnan,
            Decimal.is_signed,
            Decimal.is_snan,
            Decimal.is_subnormal,
            Decimal.is_zero,
        ],
        ids=lambda call: call.__name__,
    )
    def test_they_do_not_look_at_the_coefficient(self, call: Callable[[Decimal], Any]) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            small, large = wide(2_000), wide(200_000)
            call(small)
            call(large)
            ratio = best_ns(lambda: call(large), inner=100) / best_ns(
                lambda: call(small), inner=100
            )
        assert ratio < 2.0, f"{call.__name__} grew {ratio:.1f}x over 100x the digits"

    def test_same_quantum_compares_exponents(self) -> None:
        assert Decimal("1.00").same_quantum(Decimal("9.99")) is True
        assert Decimal("1.00").same_quantum(Decimal("9.9")) is False
        assert Decimal("Infinity").same_quantum(Decimal("-Infinity")) is True

    def test_the_predicates_answer_for_each_class(self) -> None:
        assert Decimal(1).is_finite() and Decimal(1).is_canonical()
        assert Decimal("Infinity").is_infinite()
        assert Decimal("NaN").is_nan() and Decimal("NaN").is_qnan()
        assert Decimal("sNaN").is_snan()
        assert Decimal("-1").is_signed() and Decimal(0).is_zero()
        assert Decimal(1).is_normal()
        with localcontext() as ctx:
            ctx.Emin = -3
            ctx.prec = 3
            assert Decimal("1E-5").is_subnormal()
        assert Decimal(1).radix() == Decimal(10)
        assert Decimal("1.5").number_class() == "+Normal"
        assert Decimal("1E+5").logb() == Decimal(5)
        assert Decimal("1E+5").adjusted() == 5


class TestComparisonsStopAtTheFirstDifference:
    """`a < b`, `compare()`, `compare_signal()`, `compare_total()` |
    O(min(n, m)).

    Three shapes: coefficients differing in the first digit, coefficients of
    equal length differing only in the last, and a one-digit operand against
    a long tail. The first is what the "a difference there ends it" clause
    predicts; the other two are the n + m the row is priced at.
    """

    @pytest.mark.timing
    def test_an_early_difference_costs_nothing(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            small_a, small_b = wide(2_000), other(2_000)
            large_a, large_b = wide(200_000), other(200_000)
            ratio = best_ns(lambda: large_a < large_b, inner=100) / best_ns(
                lambda: small_a < small_b, inner=100
            )
        assert ratio < 2.0, f"a first-digit difference grew {ratio:.1f}x over 100x the digits"

    @pytest.mark.timing
    def test_a_late_one_costs_the_whole_coefficient(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            small_a = Decimal("1" * 2_000)
            small_b = Decimal("1" * 1_999 + "2")
            large_a = Decimal("1" * 200_000)
            large_b = Decimal("1" * 199_999 + "2")
            ratio = best_ns(lambda: large_a < large_b, inner=100) / best_ns(
                lambda: small_a < small_b, inner=100
            )
        assert ratio > 10.0, f"a last-digit difference should scan it all, got {ratio:.1f}x"

    @pytest.mark.timing
    def test_a_longer_operands_tail_is_what_decides_equality(self) -> None:
        """Why the row is O(n + m) and not O(min(n, m)): the short operand
        runs out, and the long one's remaining digits settle it."""
        with localcontext() as ctx:
            ctx.prec = 300_000
            one = Decimal(1)
            small = Decimal("1." + "0" * 2_000 + "1")
            large = Decimal("1." + "0" * 200_000 + "1")
            assert digits(one) == 1
            ratio = best_ns(lambda: one < large, inner=100) / best_ns(
                lambda: one < small, inner=100
            )
        assert ratio > 10.0, (
            f"a one-digit operand against 100x the tail cost {ratio:.1f}x, so the tail is read"
        )

    def test_compare_returns_a_decimal(self) -> None:
        result = Decimal(1).compare(Decimal(2))
        assert isinstance(result, Decimal)
        assert result == Decimal(-1)
        assert Decimal(2).compare(Decimal(2)) == Decimal(0)
        assert Decimal(1).compare(Decimal("NaN")).is_nan()

    def test_compare_signal_signals_where_compare_does_not(self) -> None:
        with pytest.raises(InvalidOperation):
            Decimal("NaN").compare_signal(Decimal(1))

    def test_compare_total_orders_a_nan_instead(self) -> None:
        assert Decimal("NaN").compare_total(Decimal(1)) == Decimal(1)
        assert Decimal("1.0").compare_total(Decimal("1.00")) == Decimal(1)
        assert Decimal("-1").compare_total_mag(Decimal("2")) == Decimal(-1)

    def test_max_and_min_round_the_winner(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            wide = Decimal("1" * 20)
            assert digits(wide.max(Decimal(1))) == 5
            assert wide.min(Decimal(1)) == Decimal(1)
            assert Decimal(-3).max_mag(Decimal(2)) == Decimal(-3)
            assert Decimal(-3).min_mag(Decimal(2)) == Decimal(2)

    def test_a_decimal_compares_with_a_float_but_does_not_compute_with_one(self) -> None:
        assert Decimal("10.00") == 10.0
        assert Decimal(1) < 1.5
        with pytest.raises(TypeError):
            _ = cast("Any", Decimal("19.99")) * 3.0
        assert Decimal("19.99") * 3 == Decimal("59.97")


class TestContext:
    """The `Context` rows | O(1) throughout, plus the "as the operator"
    grouping.

    `flags` and `traps` returning the same object is what makes reading them
    free; `setcontext()` copying is what keeps `BasicContext` from being
    mutated by whoever installed it. The grouped arithmetic rows are checked
    by running each method against the operator it stands for.
    """

    def test_flags_and_traps_are_not_rebuilt(self) -> None:
        ctx = Context(prec=9)
        assert ctx.flags is ctx.flags
        assert ctx.traps is ctx.traps

    def test_setcontext_copies_the_pre_made_three(self) -> None:
        previous = getcontext()
        try:
            for premade in (DefaultContext, BasicContext, ExtendedContext):
                setcontext(premade)
                assert getcontext() is not premade
                assert getcontext().prec == premade.prec
        finally:
            setcontext(previous)

    def test_setcontext_installs_anything_else_as_it_stands(self) -> None:
        previous = getcontext()
        mine = Context(prec=11)
        try:
            setcontext(mine)
            assert getcontext() is mine
            mine.prec = 13
            assert getcontext().prec == 13, "the installed context is live"
        finally:
            setcontext(previous)

    def test_localcontext_copies_when_the_manager_is_built(self) -> None:
        previous = getcontext()
        try:
            setcontext(Context(prec=9))
            manager = localcontext()
            getcontext().prec = 17
            with manager as ctx:
                assert ctx.prec == 9, "the copy was taken at construction"
        finally:
            setcontext(previous)

    def test_localcontext_restores_the_previous_context(self) -> None:
        before = getcontext().prec
        with localcontext() as ctx:
            ctx.prec = before + 7
            assert getcontext().prec == before + 7
        assert getcontext().prec == before

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="kwargs are 3.11+")
    def test_localcontext_takes_attributes_as_keywords(self) -> None:
        with cast("Any", localcontext)(prec=7) as ctx:
            assert ctx.prec == 7
            assert getcontext().prec == 7

    def test_an_omitted_field_comes_from_defaultcontext(self) -> None:
        fresh = Context(prec=12)
        assert fresh.prec == 12
        assert fresh.rounding == DefaultContext.rounding
        assert fresh.Emin == DefaultContext.Emin
        assert fresh.copy() is not fresh
        assert fresh.copy().prec == 12

    def test_the_pre_made_contexts_keep_their_settings(self) -> None:
        assert DefaultContext.prec == 28
        assert BasicContext.prec == 9 and ExtendedContext.prec == 9
        assert BasicContext.traps[InvalidOperation] is True
        assert BasicContext.traps[Clamped] is True
        assert BasicContext.traps[Underflow] is True
        assert ExtendedContext.traps[InvalidOperation] is False

    def test_etiny_and_etop_follow_emin_emax_and_prec(self) -> None:
        ctx = Context(prec=5, Emin=-999, Emax=999)
        assert ctx.Etiny() == ctx.Emin - (ctx.prec - 1)
        assert ctx.Etop() == ctx.Emax - (ctx.prec - 1)

    def test_an_attribute_outside_the_limits_is_rejected(self) -> None:
        ctx = Context(prec=9)
        with pytest.raises(ValueError):
            ctx.prec = 0
        with pytest.raises(ValueError):
            ctx.Emax = -1
        assert ctx.prec == 9

    def test_clear_flags_and_clear_traps(self) -> None:
        ctx = Context(prec=5)
        ctx.create_decimal("1" * 20)
        assert ctx.flags[Inexact] is True
        ctx.clear_flags()
        assert not any(ctx.flags.values())
        ctx.clear_traps()
        assert not any(ctx.traps.values())

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("add", lambda a, b: a + b),
            ("subtract", lambda a, b: a - b),
            ("multiply", lambda a, b: a * b),
            ("divide", lambda a, b: a / b),
            ("divide_int", lambda a, b: a // b),
            ("remainder", lambda a, b: a % b),
            ("divmod", divmod),
            ("remainder_near", Decimal.remainder_near),
            ("compare", Decimal.compare),
            ("compare_signal", Decimal.compare_signal),
            ("compare_total", Decimal.compare_total),
            ("compare_total_mag", Decimal.compare_total_mag),
            ("max", Decimal.max),
            ("max_mag", Decimal.max_mag),
            ("min", Decimal.min),
            ("min_mag", Decimal.min_mag),
            ("next_toward", Decimal.next_toward),
            ("copy_sign", Decimal.copy_sign),
            ("same_quantum", Decimal.same_quantum),
            ("quantize", Decimal.quantize),
            ("shift", Decimal.shift),
            ("rotate", Decimal.rotate),
            ("scaleb", Decimal.scaleb),
        ],
    )
    def test_the_binary_context_methods_match_their_operators(
        self, name: str, expected: Callable[[Decimal, Decimal], Any]
    ) -> None:
        ctx = Context(prec=9)
        a, b = Decimal("123.5"), Decimal("7")
        with localcontext(ctx):
            assert getattr(ctx, name)(a, b) == expected(a, b)

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("abs", abs),
            ("minus", lambda a: -a),
            ("plus", lambda a: +a),
            ("exp", Decimal.exp),
            ("ln", Decimal.ln),
            ("log10", Decimal.log10),
            ("logb", Decimal.logb),
            ("sqrt", Decimal.sqrt),
            ("normalize", Decimal.normalize),
            ("logical_invert", lambda a: Decimal(1).logical_invert()),
            ("next_minus", Decimal.next_minus),
            ("next_plus", Decimal.next_plus),
            ("to_integral", Decimal.to_integral),
            ("to_integral_exact", Decimal.to_integral_exact),
            ("to_integral_value", Decimal.to_integral_value),
            ("copy_abs", Decimal.copy_abs),
            ("copy_negate", Decimal.copy_negate),
            ("canonical", Decimal.canonical),
            ("number_class", Decimal.number_class),
            ("to_eng_string", Decimal.to_eng_string),
            ("to_sci_string", str),
            ("is_canonical", Decimal.is_canonical),
            ("is_finite", Decimal.is_finite),
            ("is_infinite", Decimal.is_infinite),
            ("is_nan", Decimal.is_nan),
            ("is_normal", Decimal.is_normal),
            ("is_qnan", Decimal.is_qnan),
            ("is_signed", Decimal.is_signed),
            ("is_snan", Decimal.is_snan),
            ("is_subnormal", Decimal.is_subnormal),
            ("is_zero", Decimal.is_zero),
        ],
    )
    def test_the_unary_context_methods_match_their_methods(
        self, name: str, expected: Callable[[Decimal], Any]
    ) -> None:
        ctx = Context(prec=9)
        value = Decimal("123.5") if name != "logical_invert" else Decimal(1)
        with localcontext(ctx):
            assert getattr(ctx, name)(value) == expected(value)

    def test_the_remaining_context_methods(self) -> None:
        ctx = Context(prec=9)
        assert ctx.radix() == Decimal(10)
        assert ctx.fma(Decimal(2), Decimal(3), Decimal(4)) == Decimal(10)
        assert ctx.logical_and(Decimal(1100), Decimal(1010)) == Decimal(1000)
        assert ctx.logical_or(Decimal(1100), Decimal(1010)) == Decimal(1110)
        assert ctx.logical_xor(Decimal(1100), Decimal(1010)) == Decimal(110)
        assert ctx.create_decimal_from_float(0.5) == Decimal("0.5")

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="IEEEContext is 3.14+")
    def test_ieeecontext(self) -> None:
        import decimal

        ieee_context = cast("Any", decimal).IEEEContext
        assert ieee_context(32).prec == 7
        assert ieee_context(128).prec == 34
        assert cast("Any", decimal).IEEE_CONTEXT_MAX_BITS >= 128


class TestSignals:
    """The signal rows: a flag records, a trap raises.

    The two zero-division conditions are the page's example of why the
    distinction matters - `10/0` and `0/0` are not the same signal, and only
    one of them is about dividing by zero.
    """

    def test_the_two_zero_divisions_are_different_conditions(self) -> None:
        with pytest.raises(DivisionByZero):
            _ = Decimal(10) / Decimal(0)
        with pytest.raises(InvalidOperation):
            _ = Decimal(0) / Decimal(0)

    def test_an_untrapped_signal_sets_a_flag_instead(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            ctx.clear_flags()
            assert ctx.traps[Inexact] is False
            _quotient = Decimal(1) / Decimal(3)
            assert ctx.flags[Inexact] is True
            assert ctx.flags[Rounded] is True
            assert _quotient == Decimal("0.33333")

    def test_the_trap_turns_it_into_an_exception(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 5
            ctx.traps[Inexact] = True
            with pytest.raises(Inexact):
                Decimal(1).__truediv__(Decimal(3))

    def test_overflow_and_underflow_come_from_the_exponent_range(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 9
            with pytest.raises(Overflow):
                _ = Decimal("1E999999999999999999") * Decimal("1E999999999999999999")
            ctx.clear_flags()
            ctx.Emin = -3
            assert Decimal("1E-3") * Decimal("1E-3") == Decimal("1E-6")
            assert ctx.flags[Subnormal] is True
            assert ctx.flags[Underflow] is False, "an exact subnormal is not an underflow"

            ctx.clear_flags()
            _ = Decimal("1.11111111E-3") * Decimal("1E-9")
            assert ctx.flags[Subnormal] is True
            assert ctx.flags[Underflow] is True

    def test_floatoperation_catches_the_implicit_conversions(self) -> None:
        ctx = Context(prec=9)
        assert ctx.create_decimal_from_float(0.1) == Decimal("0.100000000")
        assert ctx.create_decimal(0.1) == Decimal("0.100000000")

        ctx.traps[FloatOperation] = True
        with pytest.raises(FloatOperation):
            ctx.create_decimal(0.1)
        with localcontext(ctx):
            with pytest.raises(FloatOperation):
                Decimal(0.1)
            # The two explicit spellings say they mean it, so they stay quiet
            assert Decimal.from_float(0.1) == Decimal(Decimal.from_float(0.1))
            assert ctx.create_decimal_from_float(0.1) == Decimal("0.100000000")

    def test_the_four_conditions_sit_under_invalidoperation(self) -> None:
        for condition in (
            ConversionSyntax,
            DivisionImpossible,
            DivisionUndefined,
            InvalidContext,
        ):
            assert issubclass(condition, InvalidOperation)
        for signal in (
            Clamped,
            DivisionByZero,
            Inexact,
            InvalidOperation,
            Overflow,
            Rounded,
            Subnormal,
            Underflow,
            FloatOperation,
        ):
            assert issubclass(signal, DecimalException)

    def test_a_bad_literal_is_an_invalid_operation(self) -> None:
        with pytest.raises(InvalidOperation):
            Decimal("not a number")


class TestSpecialValuesShortCircuit:
    """ "Infinities and NaNs carry no digits, so they skip the digit
    arithmetic entirely."

    An infinity has a one-digit coefficient, so the claim is really that the
    operation does not widen it to p. Timing separates it from an addition
    that does have digits to add. A NaN is the same only while it carries no
    payload, and the last test here is what keeps the page honest about that.
    """

    @pytest.mark.timing
    def test_infinity_arithmetic_skips_the_digits(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 50_000
            big = wide(20_000)
            infinity = Decimal("Infinity")
            digits_time = best_ns(lambda: big + big, inner=20)
            special_time = best_ns(lambda: infinity + 5, inner=20)

        assert special_time * 3 < digits_time, (
            f"a special value has no digits to add: "
            f"digits={digits_time:.0f}ns special={special_time:.0f}ns"
        )

    def test_turning_an_infinity_back_into_a_number_builds_p_digits(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 9
            largest = Decimal("Infinity").next_minus()
            assert digits(largest) == ctx.prec
            assert largest.is_finite()

    def test_special_values_still_propagate(self) -> None:
        assert Decimal("Infinity") + 5 == Decimal("Infinity")
        assert (Decimal("NaN") + 5).is_nan()
        assert Decimal("NaN") != Decimal("NaN")
        assert Decimal("Infinity").as_tuple().digits == (0,)
        assert Decimal("Infinity").number_class() == "+Infinity"

    def test_a_signalling_nan_raises(self) -> None:
        with pytest.raises(InvalidOperation):
            _ = Decimal("sNaN") + 5

    def test_a_nan_payload_is_digits(self) -> None:
        payload = Decimal("NaN123")
        assert payload.as_tuple().digits == (1, 2, 3)
        assert (payload + 5).as_tuple().digits == (1, 2, 3)

    @pytest.mark.timing
    def test_and_they_are_carried_like_digits(self) -> None:
        with localcontext() as ctx:
            ctx.prec = 300_000
            short = Decimal("NaN" + "1" * 10)
            long_payload = Decimal("NaN" + "1" * 200_000)
            ratio = best_ns(lambda: long_payload + 5, inner=20) / best_ns(
                lambda: short + 5, inner=20
            )
        assert ratio > 3.0, (
            f"a 200,000-digit payload propagated for {ratio:.1f}x what a 10-digit "
            f"one did, so the page cannot call every NaN O(1)"
        )


class TestDecimalTuple:
    """`DecimalTuple` | O(1) | O(1) to build and read - a three-field named
    tuple, whose `count()` and `index()` are O(n) because one of those three
    fields is the whole digit tuple."""

    def test_the_fields(self) -> None:
        parts = Decimal("-1.25").as_tuple()
        assert isinstance(parts, DecimalTuple)
        assert parts.sign == 1
        assert parts.digits == (1, 2, 5)
        assert parts.exponent == -2
        # At most three comparisons, one of them against the whole digit tuple
        assert parts.count(1) == 1
        assert parts.index(-2) == 2
        assert parts.count((1, 2, 5)) == 1

    def test_it_round_trips_through_the_constructor(self) -> None:
        value = Decimal("-1.25")
        assert Decimal(cast("Any", value.as_tuple())) == value
        assert Decimal(cast("Any", DecimalTuple(0, (1, 5), -1))) == Decimal("1.5")


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so a context change cannot leak
    between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "digits) == 767" in s)
        mutated = source.replace("digits) == 767", "digits) == 768", 1)
        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"

        clean = tmp_path / "clean"
        clean.mkdir()
        assert _run_block(source, clean).returncode == 0, "the unmutated block already fails"

        broken = tmp_path / "broken"
        broken.mkdir()
        result = _run_block(mutated, broken)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
