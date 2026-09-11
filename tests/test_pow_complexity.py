"""Tests for docs/builtins/pow.md.

The page's own framing is what these tests defend: `O(log y)` is a count of
multiplications, not a time bound, and the cost of an integer power is set by
the width of its result, `r = b * y` bits for a `b`-bit base.

Where the page states a cost, the preferred evidence here is a width or an
allocation rather than a stopwatch. `sys.getsizeof` settles the space rows with
no tolerance, and `tracemalloc` settles "no intermediate exceeds `m` bits": the
three-argument form's traced peak stays inside the modulus and does not move
when the exponent grows tenfold, while the two-step form's tracks the exponent.

The rest need elapsed time, each framed to leave the widest gap measured:

* an integer power is superlinear in `y` (x9.1 for x4, where a log bound
  predicts x1 and a linear one x4, and grade-school squaring x16);
* the base's width is a size variable of its own (x22 for x8 in the base's bits
  at a fixed `y`, against x1 if `y` governed the cost alone);
* modular exponentiation is linear in the exponent's bits (x2.0 for x2);
* and superlinear in the modulus' bits (x13.4 for x4, against x4 if linear);
* reducing afterwards costs x19,000 at RSA scale, and nothing at 2**10;
* `1 << n` beats `pow(2, n)` by x2,500 at n = 1e6;
* and a dense base costs x12 more than a power of two at the same result
  width, which is why the growth tests above use a 64-bit base rather than 2.

That last one is also the caveat on the table's `O(r²)`: it is an upper bound,
as the page's Performance Notes say, and a power-of-two base sits far below it -
`pow(2, n)` measures about n^1.15 in the result width where a 64-bit base
measures n^1.59.

Measured on one aarch64 machine under CPython 3.14; the thresholds sit far from
both the asserted and the excluded shape so a slower or differently-tuned CI
runner still separates them.

One dimension is deliberately not varied: operand types other than `int` and
`float` are checked for delegation only. What `Decimal.__pow__` or a NumPy
scalar costs belongs to those types' pages.

One claim cannot be settled by running code here: the page dates the modular
inverse and the keyword arguments to Python 3.8, and the integer-to-string limit
to 3.11 and 3.10.7. This project supports 3.10 and newer and pins 3.10.21, so
every supported interpreter already has all three. The tests below assert that
the features are present, not the release that introduced them.
"""

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

    The discarded first call matters: whichever measurement runs first in a
    process otherwise absorbs tracemalloc's own warm-up, which read 1360 bytes
    against a steady 936 on 3.10 and made the result depend on test order."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class TestIntegerPowerWidth:
    """The `Integer base, y >= 0` row: O(r²) time and Θ(r) space for a result
    of r = b * y bits. The space half needs no timing at all."""

    def test_result_width_is_linear_in_the_exponent(self) -> None:
        assert pow(WORD, 1_000).bit_length() == pytest.approx(64_000, rel=0.01)
        assert pow(WORD, 4_000).bit_length() == pytest.approx(256_000, rel=0.01)

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


class TestNegativeIntegerExponent:
    """The `Integer base, y < 0` row: O(1) via float, and OverflowError once
    the base leaves float range."""

    def test_returns_a_float(self) -> None:
        assert pow(2, -1) == 0.25 * 2
        assert isinstance(pow(2, -1), float)
        assert pow(2, -2) == 0.25

    def test_a_base_wider_than_a_float_overflows(self) -> None:
        with pytest.raises(OverflowError):
            pow(10**1000, -1)

    def test_the_float_path_allocates_nothing_wide(self) -> None:
        """O(1) space: the result is one float however large the exponent."""
        assert sys.getsizeof(pow(2, -1)) == sys.getsizeof(pow(2, -1_000_000))


class TestFloatPower:
    """The `Float base or exponent` row: one libm call, O(1) either way."""

    def test_stated_values(self) -> None:
        assert pow(2.0, 3) == 8.0
        assert pow(2.5, 2) == 6.25
        assert pow(2.0, 0.5) == 1.4142135623730951
        assert pow(1.7e308, 0.99) == 1.4065152073912217e305

    def test_a_negative_base_with_a_fractional_exponent_is_complex(self) -> None:
        result = pow(-8, 1 / 3)

        assert isinstance(result, complex)
        assert result == pytest.approx(1 + 1.7320508075688772j)

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
    """The `pow(x, y, z), y >= 0` row: O(log y * m²) time, Θ(m) space."""

    EXPONENT = (1 << 256) + 1
    MODULUS = (1 << 1024) - 159

    def test_stated_values(self) -> None:
        assert pow(2, 10, 1000) == 24
        assert pow(3, 100, 7) == 4
        assert pow(2, 1000, 13) == 3

    def test_intermediates_never_exceed_the_modulus(self) -> None:
        """Reduced mod z every step, without a stopwatch: the three-argument
        form's traced peak stays within the modulus, while the two-step form
        allocates the whole power."""
        modular = traced_peak(lambda: pow(3, 100_000, self.MODULUS))
        naive = traced_peak(lambda: (3**100_000) % self.MODULUS)

        assert modular < 4 * self.MODULUS.bit_length(), (
            f"pow(3, 100000, z) allocated {modular} traced bytes for a "
            f"{self.MODULUS.bit_length()}-bit modulus"
        )
        assert naive / modular > 20, f"the two-step form peaked at {naive} bytes against {modular}"

    def test_the_traced_peak_does_not_grow_with_the_exponent(self) -> None:
        """Theta(m), not Theta(r): x10 in y leaves the modular peak where it
        was and multiplies the two-step form's by ten."""
        modular = [traced_peak(lambda y=y: pow(3, y, self.MODULUS)) for y in (10**5, 10**6)]
        naive = [traced_peak(lambda y=y: (3**y) % self.MODULUS) for y in (10**5, 10**6)]

        assert modular[1] / modular[0] < 2.0, f"modular peak tracked y: {modular}"
        assert 5.0 < naive[1] / naive[0] < 20.0, (
            f"two-step peak did not track the exponent: {naive}"
        )

    def test_the_result_is_bounded_by_the_modulus(self) -> None:
        """Θ(m) space, whatever the exponent."""
        assert pow(3, 10**6, self.MODULUS).bit_length() <= self.MODULUS.bit_length()

    def test_a_negative_modulus_gives_a_negative_result(self) -> None:
        assert pow(2, 10, -1000) == -976

    def test_a_zero_modulus_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be 0"):
            pow(2, 10, 0)

    def test_all_three_arguments_must_be_integers(self) -> None:
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

    def test_a_negative_exponent_below_minus_one_inverts_then_exponentiates(self) -> None:
        assert pow(3, -5, 1000) == 107
        assert pow(3, -5, 1000) == pow(pow(3, -1, 1000), 5, 1000)

    def test_a_base_sharing_a_factor_with_the_modulus_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="not invertible"):
            pow(4, -1, 8)

    def test_the_inverse_is_bounded_by_the_modulus(self) -> None:
        """Θ(m) space, as for the non-negative case."""
        modulus = (1 << 1024) - 159

        assert pow(3, -1, modulus).bit_length() <= modulus.bit_length()


class TestThreeArgumentFormVersusReducingAfterwards:
    """The page's central recommendation: the two forms cost the same while
    `b * y` is small and diverge as soon as it is not.

    The divergence is a width, so both halves are observable. Only the final
    timing uses a stopwatch, and there the gap is four orders of magnitude."""

    MESSAGE, EXPONENT, MODULUS = 42, 65537, 10**9 + 7

    def test_a_small_power_leaves_nothing_to_save(self) -> None:
        """The page's 11-bit intermediate against a 10-bit modulus."""
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
    def test_two_is_the_cheapest_base_at_a_fixed_result_width(self) -> None:
        """Both calls build a 1,000,000-bit result; the power of two measured
        x12 cheaper, which is why the timing tests above use a 64-bit base."""
        power_of_two = best_time(lambda: pow(2, 1_000_000))
        dense = best_time(lambda: pow(WORD, 1_000_000 // 64))

        assert dense / power_of_two > 3.0, (
            f"a dense base cost only x{dense / power_of_two:.2f} of a power of "
            f"two at the same width ({power_of_two:.2e}s vs {dense:.2e}s)"
        )

    @pytest.mark.timing
    def test_the_shift_is_linear_in_the_result_width(self) -> None:
        """x10 in n measured x5.1, so not the squaring loop's growth."""
        small = best_time(lambda: 1 << 100_000)
        large = best_time(lambda: 1 << 1_000_000)
        ratio = large / small

        assert ratio < 30.0, (
            f"x10 in n cost x{ratio:.2f}, which is not linear ({small:.2e}s then {large:.2e}s)"
        )

    @pytest.mark.timing
    def test_the_shift_beats_the_squaring_loop(self) -> None:
        """Measured x2,463 at n = 1e6, and base 2 is pow()'s best case."""
        shift = best_time(lambda: 1 << self.N)
        squaring = best_time(lambda: pow(2, self.N))
        ratio = squaring / shift

        assert ratio > 100.0, (
            f"pow(2, n) cost only x{ratio:.1f} of the shift ({shift:.2e}s vs {squaring:.2e}s)"
        )


class TestThePowerOperator:
    """The Performance Notes: `pow(x, y)` and `x ** y` are one operation, and
    `**` on literals is folded before it ever runs."""

    def test_the_two_spellings_agree(self) -> None:
        assert pow(2, 10) == 2**10
        assert pow(2.5, 2) == 2.5**2
        assert pow(WORD, 50) == WORD**50

    def test_a_literal_power_is_folded_at_compile_time(self) -> None:
        folded = compile("2 ** 8", "<doc>", "eval")
        called = compile("pow(2, 8)", "<doc>", "eval")

        assert 256 in folded.co_consts, "the peephole optimizer stopped folding"
        assert 256 not in called.co_consts, "pow() should still be a call"


class TestDelegationToOtherTypes:
    """The `Any other type` row: pow() is `type(x).__pow__`, so the cost
    belongs to the operand."""

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

    def test_a_zero_base(self) -> None:
        assert pow(0, 5) == 0

        with pytest.raises(ZeroDivisionError):
            pow(0, -1)


class TestIntegerStringLimit:
    """The Best Practices line about str() on a wide result, and the second
    Version Notes entry. Present on every supported interpreter, so what is
    asserted is the behaviour, not the release."""

    def test_a_wide_result_refuses_to_stringify(self) -> None:
        wide = pow(2, 1_000_000)

        with pytest.raises(ValueError, match="Exceeds the limit"):
            str(wide)

    def test_raising_the_limit_lets_it_through(self) -> None:
        wide = pow(2, 1_000_000)
        original = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(400_000)
            assert len(str(wide)) == 301_030
        finally:
            sys.set_int_max_str_digits(original)


PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "pow.md"

EXPECTED_BLOCKS = 7


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

    def test_every_block_binds_the_names_it_uses(self, tmp_path: pathlib.Path) -> None:
        """A block that leans on a name from its prose rather than binding it
        compiles and then dies at run time, so NameError gets its own check."""
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if "NameError" in result.stderr:
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("pow(2, 3)", "pow(undefined_base, 3)", 1)
        assert broken != original, "the mutation did not rewrite the call"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
