"""Tests for docs/builtins/abs.md.

abs() is PyNumber_Absolute: one call to the operand type's `nb_absolute` slot,
so every bound on the page is the operand type's. For `int` that slot is
long_abs in Objects/longobject.c, which returns a non-negative exact int as
itself and otherwise copies the digits (long_neg for a negative operand,
_PyLong_Copy for a subclass). The same three-line function is in the v3.10.0,
v3.11.0, v3.12.0 and v3.13.0 tags and on the 3.14 branch, so no version is
treated apart.

Identity and traced allocation settle the two integer rows without a
stopwatch:

* `abs(x) is x` for a non-negative exact int of any width, and tracemalloc
  attributes no bytes to the call;
* `abs(x)` for a negative int allocates the operand's own size - 26,692 bytes
  at 200,000 bits and 2,666,692 at 20,000,000 - so the space row is the
  operand's width, not a constant;
* an int subclass, negative or not, comes back as a plain `int`, allocated at
  the operand's width (the cached small ints -5..256 are the one exception,
  and are not what the test uses).

The complex row's two behavioural claims are checked directly: hypot() keeps
`abs(1e200 + 1e200j)` finite where squaring the parts would overflow, and a
magnitude past float range raises OverflowError. Delegation is checked with a
counting `__abs__`, which abs() calls exactly once and whose result it returns
untouched.

Two claims need elapsed time, each framed at the widest gap measured on the
pinned interpreter (aarch64, CPython 3.14):

* a negative operand's cost is linear in its width: x103 for x100 in bits
  (200,000 to 20,000,000), where a constant-time claim predicts x1 and a
  quadratic copy x10,000;
* a non-negative operand's cost is not: x1.03 for the same step, and the
  negative operand costs x1,570 the non-negative one at 20,000,000 bits.

One dimension is not varied: a `float` has one width, so its O(1) row has no
size variable to scale. The test asserts the value and sign behaviour the
page states, not a ratio. What `Fraction.__abs__` or `Decimal.__abs__` costs
belongs to those types' pages; the delegation row is checked for the result
and the call count only.
"""

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
from fractions import Fraction
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "abs.md"

SMALL_BITS = 200_000
LARGE_BITS = 20_000_000
"""A hundredfold step in width; the small end already costs ~450ns, far above
call overhead, so a linear copy shows up as close to x100."""


def wide(bits: int, negative: bool) -> int:
    """An int of exactly `bits` bits, with a low digit set so it is not a power of two."""
    value = (1 << (bits - 1)) | 7
    return -value if negative else value


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 1_000) -> float:
    """The fastest of several runs of `loops` calls, which is the least noisy estimate.

    A thousand calls put even the 26ns non-negative case at tens of
    microseconds per sample, well clear of timer resolution."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc attributes to one call, after a warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class TestNonNegativeInt:
    """Row: O(1) time and space, returns x itself."""

    @pytest.mark.parametrize("bits", [8, 1_000, SMALL_BITS, LARGE_BITS])
    def test_returns_the_same_object(self, bits: int) -> None:
        x = wide(bits, negative=False)
        assert abs(x) is x

    def test_zero_is_returned_as_itself(self) -> None:
        assert abs(0) is 0  # noqa: F632 - identity of the small-int singleton is the claim

    def test_allocates_nothing_at_any_width(self) -> None:
        for bits in (SMALL_BITS, LARGE_BITS):
            x = wide(bits, negative=False)
            assert traced_peak(lambda x=x: abs(x)) == 0, bits

    @pytest.mark.parametrize("negative", [False, True], ids=["non-negative", "negative"])
    def test_a_subclass_is_copied_into_a_plain_int(self, negative: bool) -> None:
        class Tagged(int):
            pass

        tagged = Tagged(wide(SMALL_BITS, negative=negative))
        result = abs(tagged)

        assert result is not tagged
        assert type(result) is int
        assert result == abs(int(tagged))
        assert traced_peak(lambda: abs(tagged)) >= sys.getsizeof(int(tagged))

    def test_bool_comes_back_as_an_int(self) -> None:
        assert abs(True) == 1
        assert type(abs(True)) is int


class TestNegativeInt:
    """Row: O(n) time and space, a digit-by-digit copy with the sign flipped."""

    def test_returns_a_new_object_with_the_sign_flipped(self) -> None:
        x = wide(SMALL_BITS, negative=True)
        result = abs(x)

        assert result is not x
        assert result == -x
        assert result > 0

    def test_allocation_is_the_operands_own_size(self) -> None:
        peaks = {}
        for bits in (SMALL_BITS, LARGE_BITS):
            x = wide(bits, negative=True)
            peaks[bits] = traced_peak(lambda x=x: abs(x))
            assert peaks[bits] >= sys.getsizeof(x), (bits, peaks[bits], sys.getsizeof(x))
        growth = peaks[LARGE_BITS] / peaks[SMALL_BITS]
        assert 50 < growth < 200, f"x100 in bits allocated x{growth:.1f}"

    def test_a_machine_word_value_still_allocates_a_fresh_int(self) -> None:
        # Small ints (-5..256) are cached singletons, so use a value past them.
        x = -1_000_000
        first, second = abs(x), abs(x)
        assert first == second == 1_000_000
        assert first is not second, "two calls shared one result object"

    @pytest.mark.timing
    def test_time_is_linear_in_the_width(self) -> None:
        small = wide(SMALL_BITS, negative=True)
        large = wide(LARGE_BITS, negative=True)

        growth = best_time(lambda: abs(large)) / best_time(lambda: abs(small))

        assert 20 < growth < 1_000, (
            f"x100 in bits cost x{growth:.1f}; constant predicts x1, linear x100, quadratic x10,000"
        )

    @pytest.mark.timing
    def test_a_non_negative_operand_does_not_scale(self) -> None:
        small = wide(SMALL_BITS, negative=False)
        large = wide(LARGE_BITS, negative=False)
        negative = wide(LARGE_BITS, negative=True)

        flat = best_time(lambda: abs(large)) / best_time(lambda: abs(small))
        sign_gap = best_time(lambda: abs(negative)) / best_time(lambda: abs(large))

        assert flat < 3, f"x100 in bits cost x{flat:.2f} for a non-negative operand"
        assert sign_gap > 50, f"the negative operand cost x{sign_gap:.0f} the non-negative one"


class TestFloat:
    """Row: O(1), clears the sign bit into a new float."""

    def test_stated_values(self) -> None:
        assert abs(-3.14) == 3.14
        assert abs(3.14) == 3.14
        assert abs(-5.0) == 5.0
        assert abs(-1.7e308) == 1.7e308

    def test_negative_zero_loses_its_sign(self) -> None:
        assert abs(0.0) == 0.0
        assert math.copysign(1.0, abs(-0.0)) == 1.0
        assert math.copysign(1.0, -0.0) == -1.0

    def test_the_result_is_a_new_float(self) -> None:
        x = 2.5
        assert abs(x) == x
        assert abs(x) is not x

    def test_the_result_type_is_float(self) -> None:
        assert type(abs(-5.0)) is float


class TestComplex:
    """Row: O(1), the magnitude as a float, OverflowError past float range."""

    def test_stated_values(self) -> None:
        assert abs(3 + 4j) == 5.0
        assert abs(-3 + 4j) == 5.0
        assert abs(0j) == 0.0
        assert abs(-5j) == 5.0
        assert type(abs(-5j)) is float

    def test_hypot_keeps_a_finite_magnitude_where_squaring_would_not(self) -> None:
        with pytest.raises(OverflowError):
            pow(1e200, 2)
        assert abs(1e200 + 1e200j) == pytest.approx(1.414213562373095e200)

    def test_a_magnitude_past_float_range_overflows(self) -> None:
        with pytest.raises(OverflowError, match="absolute value too large"):
            abs(1.5e308 + 1.5e308j)

    def test_an_infinite_part_wins_over_a_nan(self) -> None:
        assert abs(complex(float("inf"), float("nan"))) == math.inf
        assert math.isnan(abs(complex(float("nan"), 1.0)))


class TestDelegation:
    """Row: any other type goes to type(x).__abs__, called once, result returned as is."""

    def test_dunder_abs_is_called_exactly_once(self) -> None:
        calls = 0

        class Counted:
            def __abs__(self) -> int:
                nonlocal calls
                calls += 1
                return 42

        assert abs(Counted()) == 42
        assert calls == 1

    def test_the_result_is_returned_untouched(self) -> None:
        sentinel = object()

        class Odd:
            def __abs__(self) -> object:
                return sentinel

        assert abs(Odd()) is sentinel

    def test_a_subclass_override_is_honoured(self) -> None:
        class Custom(int):
            def __abs__(self) -> str:  # pyright: ignore[reportIncompatibleMethodOverride]
                return "custom"

        assert abs(Custom(-3)) == "custom"

    def test_fraction_and_decimal(self) -> None:
        assert abs(Fraction(-3, 4)) == Fraction(3, 4)
        assert abs(Decimal("-1.5")) == Decimal("1.5")
        assert type(abs(Fraction(-3, 4))) is Fraction
        assert type(abs(Decimal("-1.5"))) is Decimal

    def test_a_type_without_dunder_abs_is_rejected(self) -> None:
        class Plain:
            pass

        with pytest.raises(TypeError, match=r"bad operand type for abs\(\): 'Plain'"):
            abs(Plain())  # pyright: ignore[reportArgumentType]
        with pytest.raises(TypeError, match=r"bad operand type for abs\(\): 'str'"):
            abs("-5")  # pyright: ignore[reportArgumentType]

    def test_the_documented_class(self) -> None:
        class Distance:
            def __init__(self, value: int) -> None:
                self.value = value

            def __abs__(self) -> int:
                return abs(self.value)

        assert abs(Distance(-10)) == 10


class TestManualCheck:
    """Prose: `x if x >= 0 else -x` does the same work, because -x copies a negative int."""

    @pytest.mark.parametrize("bits", [8, SMALL_BITS])
    def test_both_spellings_agree(self, bits: int) -> None:
        for x in (wide(bits, negative=True), wide(bits, negative=False), 0):
            assert abs(x) == (x if x >= 0 else -x)

    def test_negation_allocates_what_abs_allocates(self) -> None:
        x = wide(SMALL_BITS, negative=True)
        assert traced_peak(lambda: -x) == traced_peak(lambda: abs(x))

    def test_the_manual_spelling_copies_nothing_for_a_non_negative_int(self) -> None:
        x = wide(SMALL_BITS, negative=False)
        assert traced_peak(lambda: x if x >= 0 else -x) == 0


class TestStatedExampleValues:
    """The values the page's comments give, checked rather than trusted."""

    def test_manhattan_distance(self) -> None:
        def manhattan_distance(x1: int, y1: int, x2: int, y2: int) -> int:
            return abs(x1 - x2) + abs(y1 - y2)

        assert manhattan_distance(0, 0, 3, 4) == 7

    def test_deviations(self) -> None:
        target = 100
        values = [95, 102, 98, 105, 99]
        assert [abs(v - target) for v in values] == [5, 2, 2, 5, 1]
        assert max(abs(v - target) for v in values) == 5

    def test_removing_sign_and_bulk(self) -> None:
        assert [abs(x) for x in [-1, -2, -3, 4, 5]] == [1, 2, 3, 4, 5]
        assert [abs(x) for x in [-5, 3, -2, 8, -1]] == [5, 3, 2, 8, 1]
        assert [abs(x) for x in [-1.5, 2.5, -3.5]] == [1.5, 2.5, 3.5]
        assert [abs(p[0]) + abs(p[1]) for p in [(1, 2), (3, 4), (5, 6)]] == [3, 7, 11]

    def test_extremes(self) -> None:
        assert abs(-(10**100)) == 10**100
        assert abs(-sys.maxsize - 1) == sys.maxsize + 1

    def test_zero(self) -> None:
        assert abs(0) == 0
        assert abs(-0) == 0


EXPECTED_BLOCKS = 13


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
        extremes = next(source for _, source in _blocks() if "sys.maxsize" in source)
        broken = extremes.replace("import sys\n", "", 1)
        assert broken != extremes, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
