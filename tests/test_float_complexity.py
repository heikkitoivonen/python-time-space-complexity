"""Tests for docs/builtins/float.md.

A float is one C double inside a fixed-size object, so most of the page's O(1)
rows hold because nothing in the operands can grow. What the tests settle is
where something can: the int on the other side of a comparison or an
arithmetic operator, the exponent of `**`, the string `float()` and
`float.fromhex()` parse, the precision or width a format specification asks
for, and the size of every int or string a conversion returns. Bounded
outputs are settled by observing their length or bit width over the whole
float range, identity rows by `is`, and the few growth claims by timing ratios
over a 10x to 100x step, plus a traced allocation peak for the space bounds.

Measurement scope:

* fixed width: `sys.float_info.mant_dig` is 53 and `sys.float_info.max` is
  1.7976931348623157e308, and `sys.getsizeof()` is the same for 0.0, 5e-324,
  1.0, 1e300, inf and nan.
* arithmetic: `0.5 ** 1e15` costs under 4x `0.5 ** 2.0`, with the operands in
  variables so the compiler cannot fold them (repeated multiplication would be
  1e15 steps); `(-8.0) ** (1 / 3)` is a complex;
  `10.0 ** 400` raises OverflowError while `1e308 * 10`, `1e308 + 1e308` and
  `1e308 / 1e-10` are inf; `1.5 + 10**400` (and `-`, `*`, `/`, `//`, `%`, `**`)
  raises OverflowError naming the conversion to float, and rejecting `2**k`
  under `+`, `//` and `**` costs between x20 and x1,000 from k = 100,000 to
  k = 10,000,000 (linear in the int predicts x100, constant x1, quadratic
  x10,000; measured here about x90); `divmod()` equals
  `(//, %)`; `+x`, `x.real`, `x.conjugate()` and `float(x)` return `x` itself,
  and the same operations on a float subclass return a new plain float;
  `bool()` is False only for 0.0 and -0.0, and True for nan.
* comparison: all six operators against `2**1_000_000` cost under 4x the
  same comparison against `2**100`, where converting that power of two would
  scan all million bits; the results are exact, so
  `2**53 + 1 != float(2**53 + 1)`, `2**1024 > sys.float_info.max` without an
  OverflowError, and `inf > 10**400`.
* `hash(x) == hash(int(x))` for integral floats from 0.0 to 2.0**1000, both
  signs, and `{1: 'a'}[1.0]` finds the int key.
* `repr()` and `str()` read back as the same float, sign of zero included, for
  2,000 values spread over the whole exponent range, subnormals included, and
  none is longer than 24 characters; `f"{x}"` equals `str(x)`. That the digits
  are the fewest that round-trip is the documented repr algorithm (David Gay's
  shortest mode in Python/dtoa.c); the tests pin it only for 0.1 and 1e300.
* `format()` writes `p + 2` characters for `.{p}f` on 0.1 and `p` for a
  `>{p}` width; for `.{p}f` and `.{p}e` the traced peak lies between `p` and
  `4p` bytes at both p = 10,000 and p = 1,000,000; time from p = 1,000 to
  p = 100,000 grows under 300x (quadratic would be 10,000x). `'g'` drops
  trailing zeros, so `format(1.0, '.1000g')` is `'1'`.
  `'.0f'` writes 301 characters for 1e300 and 309 for the largest float.
* `int()`, `math.trunc()`, `math.floor()`, `math.ceil()` and `round()` return
  at most 1,024 bits for the largest float, raise OverflowError for both
  infinities and ValueError for nan; `round(x, ndigits)` is a float, and
  `ndigits` of plus and minus 10**18 returns at once, x and 0.0.
* `float(s)` and `float.fromhex(s)` from 10,000 to 1,000,000 characters grow
  more than 10x and less than 1,000x in time (linear predicts 100x, quadratic
  10,000x) and have a traced peak under 1,000 bytes at 1,000,000 ASCII
  characters. `float(s)` peaks above 100,000 bytes for 100,000 underscore
  groups, 100,000 Arabic-Indic digits, or 100,000 em spaces before `1.5`.
* `as_integer_ratio()` equals `Fraction(x)` (lowest terms) with a power-of-two
  denominator for 2,000 values, and is `2**1074` for 5e-324; `fromhex(hex(x))`
  is `x` for the same values, and no `hex()` is longer than 24 characters; `fromhex()` on a subclass returns the subclass.
* `float.from_number()` (3.14+): returns an exact float itself, calls a
  counting `__float__` once, falls back to `__index__`, and raises TypeError
  for a string where `float()` parses it. Its absence before 3.14 is asserted.
* Rounding: `round(2.675, 2)` is 2.67 and `Decimal(2.675)` is below
  `Decimal('2.675')`.
* Every fenced Python block runs in its own subprocess with warnings as
  errors, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That `float` is IEEE 754 binary64 on every platform CPython supports is a
  build requirement (3.11 and later refuse to build without IEEE 754 doubles);
  the tests check only the running platform's `sys.float_info`.
* The O(1) rows for the arithmetic operators, `hash()`, `hex()`,
  `is_integer()`, `as_integer_ratio()`, `round()` and the int conversions
  follow from the fixed width read in Objects/floatobject.c; the tests bound
  their outputs, not their time. Their constant still varies with the value:
  `'f'` formatting of 1e300 or `int(1e300)` costs more than the same call on
  1.5, inside the bound.
* The O(d) conversion of an int operand is timed only on the rejecting path
  and only for a power of two; a convertible int has at most 1,024 bits, too
  few to separate from call overhead. That most ints stop the scan early is
  measured for `float()` in tests/test_float_func_complexity.py.
  `float.fromhex()` on a non-ASCII string builds its UTF-8 form before
  raising ValueError; only ASCII input is measured.
* The cost of an operand's `__float__()` or `__index__()` under
  `float.from_number()` or `float()` is that method's own.
* Not varied: subnormal operands in the timing tests, NaN payloads, and
  locale. Format time is measured for `'f'` only, allocation for `'f'` and
  `'e'`, output length for `'f'`, `'e'`, `'g'` and width padding; other format
  types are not measured.
"""

from __future__ import annotations

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
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "float.md"
EXPECTED_BLOCKS = 4
# Python 3.14+; None before, where TestFromNumber is skipped.
FROM_NUMBER: Any = getattr(float, "from_number", None)


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


def sample_floats(count: int = 2000) -> list[float]:
    """Finite floats of both signs spread over every binary exponent."""
    rng = random.Random(1234)
    values = [0.0, -0.0, 5e-324, 2.2250738585072014e-308, sys.float_info.max, 0.1, 1.5]
    while len(values) < count:
        values.append(math.ldexp(rng.random(), rng.randint(-1074, 1024)) * rng.choice((1, -1)))
    return values


class Sub(float):
    """A float subclass, for the rows that return `x` itself only when exact."""


class TestFixedWidth:
    """Introduction: a float is one fixed-size double with 53 significant bits
    and a finite range up to about 1.8e308."""

    def test_float_info_describes_binary64(self) -> None:
        assert sys.float_info.mant_dig == 53
        assert sys.float_info.max == 1.7976931348623157e308

    def test_every_value_has_the_same_size(self) -> None:
        sizes = {sys.getsizeof(v) for v in (0.0, 5e-324, 1.0, 1e300, math.inf, math.nan)}
        assert len(sizes) == 1


class TestArithmetic:
    """Arithmetic rows: O(1) for float operands, an int operand is converted
    first in O(d) at worst, `**` is O(1) for any float exponent, and the
    overflow behaviour of the operators differs."""

    @pytest.mark.timing
    def test_power_costs_the_same_for_a_huge_exponent(self) -> None:
        base, small_exponent, huge_exponent = 0.5, 2.0, 1e15
        small = best_ns(lambda: base**small_exponent, inner=10_000)
        huge = best_ns(lambda: base**huge_exponent, inner=10_000)

        assert huge < small * 4, f"0.5 ** 2.0: {small:.1f} ns, 0.5 ** 1e15: {huge:.1f} ns"

    def test_negative_base_with_fractional_exponent_is_complex(self) -> None:
        root: Any = (-8.0) ** (1 / 3)
        assert isinstance(root, complex)
        assert math.isclose(root.real, 1.0)
        assert isinstance(pow(-8.0, 0.5), complex)

    def test_power_raises_on_overflow(self) -> None:
        with pytest.raises(OverflowError):
            _ = 10.0**400

    def test_other_operators_overflow_to_inf(self) -> None:
        assert 1e308 * 10 == math.inf
        assert 1e308 + 1e308 == math.inf
        assert 1e308 / 1e-10 == math.inf

    @pytest.mark.parametrize(
        "operation",
        [
            lambda x, n: x + n,
            lambda x, n: n - x,
            lambda x, n: x * n,
            lambda x, n: x / n,
            lambda x, n: x // n,
            lambda x, n: x % n,
            lambda x, n: x**n,
        ],
    )
    def test_an_int_beyond_the_float_range_raises(
        self, operation: Callable[[float, int], Any]
    ) -> None:
        with pytest.raises(OverflowError, match="too large to convert to float"):
            operation(1.5, 10**400)

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "operation",
        [lambda x, n: x + n, lambda x, n: x // n, lambda x, n: x**n],
        ids=["+", "//", "**"],
    )
    def test_converting_a_power_of_two_operand_is_linear(
        self, operation: Callable[[float, int], Any]
    ) -> None:
        def reject(n: int) -> None:
            try:
                operation(1.5, n)
            except OverflowError:
                return
            raise AssertionError("an int beyond the float range was converted")

        small, large = 1 << 100_000, 1 << 10_000_000
        small_ns = best_ns(lambda: reject(small))
        large_ns = best_ns(lambda: reject(large))
        ratio = large_ns / small_ns
        assert 20 < ratio < 1_000, f"100x the bits cost x{ratio:.1f}; linear predicts x100"

    def test_divmod_matches_floor_division_and_modulo(self) -> None:
        for x, y in ((7.5, 2.0), (-7.5, 2.0), (7.5, -2.0), (1e300, 3.0)):
            assert divmod(x, y) == (x // y, x % y)

    def test_identity_rows_return_an_exact_float_itself(self) -> None:
        x = 1.5
        assert +x is x
        assert x.real is x
        assert x.conjugate() is x
        assert float(x) is x

    def test_identity_rows_copy_a_subclass_instance(self) -> None:
        x = Sub(1.5)
        for result in (+x, x.real, x.conjugate(), float(x)):
            assert type(result) is float
            assert result is not x
            assert result == 1.5

    def test_negation_and_abs(self) -> None:
        assert -1.5 == -(1.5)
        assert abs(-1.5) == 1.5
        assert math.copysign(1.0, -0.0) == -1.0
        assert math.copysign(1.0, abs(-0.0)) == 1.0

    def test_bool_is_false_only_for_zeros(self) -> None:
        assert bool(0.0) is False
        assert bool(-0.0) is False
        assert bool(math.nan) is True
        assert bool(5e-324) is True


class TestComparisonWithInt:
    """Comparison rows and Mixing Floats and Ints: a comparison with an int of
    any size is exact and does not convert the int."""

    @pytest.mark.timing
    @pytest.mark.parametrize("op", ["<", "<=", ">", ">=", "==", "!="])
    def test_cost_does_not_grow_with_the_int(self, op: str) -> None:
        compare: Callable[[float, int], bool] = eval(f"lambda x, n: x {op} n")
        small_int = 2**100
        huge_int = 2**1_000_000

        small = best_ns(lambda: compare(1.5, small_int), inner=10_000)
        huge = best_ns(lambda: compare(1.5, huge_int), inner=10_000)

        assert huge < small * 4, f"x {op} 2**100: {small:.1f} ns, x {op} 2**1000000: {huge:.1f} ns"

    def test_comparison_is_exact(self) -> None:
        assert 2**53 + 1 != float(2**53 + 1)
        assert float(2**53 + 1) == 2**53
        assert 2**53 + 1 > float(2**53)

    def test_comparison_never_overflows(self) -> None:
        assert 2**1024 > sys.float_info.max
        assert math.inf > 10**400
        assert 1.5 < 10**100_000


class TestHash:
    """Row `hash(x)`: equals `hash(int(x))` for an integral x."""

    def test_integral_floats_hash_like_ints(self) -> None:
        for exponent in range(0, 1001, 7):
            for sign in (1, -1):
                x = sign * 2.0**exponent
                assert hash(x) == hash(int(x))
        assert hash(0.0) == hash(0) == hash(-0.0)

    def test_one_and_one_point_zero_are_one_key(self) -> None:
        table: dict[float, str] = {1: "a"}
        assert table[1.0] == "a"
        one_point_zero = 1.0
        assert len({1, one_point_zero}) == 1


class TestStrAndRepr:
    """Row `str(x)`, `repr(x)`, `f"{x}"`: the shortest string that reads back
    as `x`, so its length is bounded."""

    def test_repr_reads_back_and_is_bounded(self) -> None:
        for x in sample_floats():
            text = repr(x)
            assert float(text) == x
            assert math.copysign(1.0, float(text)) == math.copysign(1.0, x)
            assert len(text) <= 24
            assert str(x) == text
            assert f"{x}" == text

    def test_repr_is_the_shortest(self) -> None:
        assert repr(0.1) == "0.1"
        assert repr(1e300) == "1e+300"


class TestFormat:
    """Row `format(x, spec)`: O(p) in the precision or width asked for, and
    `'f'` writes every integer digit."""

    def test_output_length_follows_precision_and_width(self) -> None:
        for p in (10, 1_000, 100_000):
            assert len(format(0.1, f".{p}f")) == p + 2
            assert len(format(0.1, f">{p}")) == p

    @pytest.mark.parametrize("p", [10_000, 1_000_000])
    @pytest.mark.parametrize("kind", ["f", "e"])
    def test_space_is_proportional_to_precision(self, kind: str, p: int) -> None:
        spec = f".{p}{kind}"
        format(0.1, spec)

        peak = peak_bytes(lambda: format(0.1, spec))

        assert p < peak < 4 * p, f"format(0.1, {spec!r}) peaked at {peak:,} bytes"

    def test_g_drops_trailing_zeros(self) -> None:
        assert format(1.0, ".1000g") == "1"
        assert len(format(0.1, ".1000e")) == 1006

    @pytest.mark.timing
    def test_time_is_not_quadratic_in_precision(self) -> None:
        low_spec, high_spec = ".1000f", ".100000f"
        low = best_ns(lambda: format(0.1, low_spec), inner=20)
        high = best_ns(lambda: format(0.1, high_spec), inner=20)

        assert high < low * 300, f"p=1,000: {low:.0f} ns, p=100,000: {high:.0f} ns"

    def test_f_writes_every_integer_digit(self) -> None:
        assert len(format(1e300, ".0f")) == 301
        assert len(format(sys.float_info.max, ".0f")) == 309


class TestIntConversions:
    """Row `int(x)`, `math.trunc/floor/ceil`, `round(x)`: bounded results,
    errors for infinities and NaN; `round(x, ndigits)` returns a float."""

    CONVERSIONS: tuple[Callable[[float], int], ...] = (
        int,
        math.trunc,
        math.floor,
        math.ceil,
        round,
    )

    @pytest.mark.parametrize("convert", CONVERSIONS)
    def test_result_is_at_most_1024_bits(self, convert: Callable[[float], int]) -> None:
        assert convert(sys.float_info.max).bit_length() == 1024
        assert convert(-sys.float_info.max).bit_length() == 1024

    @pytest.mark.parametrize("convert", CONVERSIONS)
    def test_infinity_and_nan_raise(self, convert: Callable[[float], int]) -> None:
        for bad in (math.inf, -math.inf):
            with pytest.raises(OverflowError):
                convert(bad)
        with pytest.raises(ValueError):
            convert(math.nan)

    def test_round_with_ndigits_returns_a_float(self) -> None:
        assert type(round(3.14159, 2)) is float
        assert round(3.14159, 2) == 3.14
        assert type(round(3.5)) is int

    def test_round_with_any_ndigits_is_bounded(self) -> None:
        assert round(1.5, 10**18) == 1.5
        assert round(1.5, -(10**18)) == 0.0


class TestParsing:
    """Rows `float(x)` and `float.fromhex(s)`: O(n) time in the string, O(1)
    space for plain ASCII, and O(n) space for `float()` when the string has
    underscores or non-ASCII characters."""

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("name", "parse", "prefix"),
        [("float", float, "1."), ("fromhex", float.fromhex, "0x1.")],
    )
    def test_time_is_linear_in_the_string(
        self, name: str, parse: Callable[[str], float], prefix: str
    ) -> None:
        short = prefix + "1" * 10_000
        long = prefix + "1" * 1_000_000

        short_ns = best_ns(lambda: parse(short), repeats=5)
        long_ns = best_ns(lambda: parse(long), repeats=5)

        ratio = long_ns / short_ns
        assert 10 < ratio < 1_000, (
            f"{name}: 10,000 chars {short_ns:.0f} ns, 1,000,000 {long_ns:.0f}"
        )

    @pytest.mark.parametrize(
        ("parse", "prefix"),
        [(float, "1."), (float.fromhex, "0x1.")],
    )
    def test_space_is_constant_for_plain_ascii(
        self, parse: Callable[[str], float], prefix: str
    ) -> None:
        text = prefix + "1" * 1_000_000
        parse(text)

        assert peak_bytes(lambda: parse(text)) < 1_000

    @pytest.mark.parametrize(
        "text",
        ["0." + "0_" * 100_000 + "1", "0." + "\u0661" * 100_000, "\u2003" * 100_000 + "1.5"],
        ids=["underscores", "arabic-indic digits", "unicode spaces"],
    )
    def test_float_copies_underscored_or_non_ascii_text(self, text: str) -> None:
        float(text)

        assert peak_bytes(lambda: float(text)) > 100_000


class TestExactRepresentations:
    """Rows `as_integer_ratio()`, `hex()`, `float.fromhex()`, `is_integer()`
    and `imag`."""

    def test_as_integer_ratio_is_exact_and_in_lowest_terms(self) -> None:
        for x in sample_floats():
            numerator, denominator = x.as_integer_ratio()
            assert Fraction(numerator, denominator) == Fraction(x)
            assert math.gcd(numerator, denominator) == 1
            assert denominator & (denominator - 1) == 0

    def test_largest_denominator(self) -> None:
        assert (5e-324).as_integer_ratio() == (1, 2**1074)

    def test_hex_round_trips(self) -> None:
        for x in sample_floats():
            back = float.fromhex(x.hex())
            assert back == x
            assert math.copysign(1.0, back) == math.copysign(1.0, x)
            assert len(x.hex()) <= 24

    def test_fromhex_is_a_class_method(self) -> None:
        assert type(Sub.fromhex("0x1.8p0")) is Sub
        assert Sub.fromhex("0x1.8p0") == 1.5

    def test_is_integer_and_imag(self) -> None:
        assert (2.0).is_integer() is True
        assert (2.5).is_integer() is False
        assert (1.5).imag == 0.0


@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="version: float.from_number() was added in Python 3.14",
)
class TestFromNumber:
    """Row `float.from_number(x)`: returns an exact float itself, otherwise
    calls the operand's `__float__` or `__index__`, and rejects strings."""

    def test_returns_an_exact_float_itself(self) -> None:
        x = 1.5
        assert FROM_NUMBER(x) is x

    def test_calls_float_once(self) -> None:
        calls: list[int] = []

        class Real:
            def __float__(self) -> float:
                calls.append(1)
                return 2.5

        assert FROM_NUMBER(Real()) == 2.5
        assert calls == [1]

    def test_falls_back_to_index(self) -> None:
        class Index:
            def __index__(self) -> int:
                return 3

        assert FROM_NUMBER(Index()) == 3.0

    def test_rejects_a_string_that_float_parses(self) -> None:
        assert float("1.5") == 1.5
        with pytest.raises(TypeError):
            FROM_NUMBER("1.5")


class TestVersionNotes:
    """Version Notes: `float.from_number()` exists from Python 3.14."""

    def test_from_number_matches_the_version(self) -> None:
        assert hasattr(float, "from_number") == (sys.version_info >= (3, 14))


class TestRounding:
    """Rounding and Truncation: `round()` works on the binary value."""

    def test_a_decimal_halfway_case_stored_below_half_rounds_down(self) -> None:
        assert Decimal(2.675) < Decimal("2.675")
        assert round(2.675, 2) == 2.67


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
        [sys.executable, "-W", "error", script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs with warnings as errors, under the interpreter running
    the tests."""

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
        block = next(source for _, source in _blocks() if "'.1000f'" in source)
        broken = block.replace("== 1002", "== 1001", 1)
        assert broken != block, "the mutation did not change the precision assertion"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
