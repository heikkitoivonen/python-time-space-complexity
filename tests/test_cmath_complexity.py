"""Tests for docs/stdlib/cmath.md.

The page prices every `cmath` call at O(1): each function works on a pair of
C doubles, so no argument can grow. What can be observed is that the input is
bounded and the output fixed-width: arguments are converted once, before the
function runs, through a fixed protocol; the result is one `complex`, `float`,
`bool` or two-float tuple; and the conversion that admits an `int`
rejects one too large for a double instead of carrying it. The behavioural
notes are settled by direct observation, with no timing.

Measurement scope:

* Every function documented in the table returns the type the page names -
  `complex` for the power, logarithmic, trigonometric and hyperbolic functions
  and `rect()`, `float` for `phase()`, a tuple of two floats for `polar()`, and
  `bool` for the classification functions - on a complex input, a float
  input and an int input; `rect()` is given a float and an int, the two real
  arguments it takes.
* 1,000 rounds of every complex-valued function and `polar()`, on warmed
  functions after a `gc.collect()`, peak under 2 KB of traced allocation, so
  nothing a call allocates outlives it; `polar()` returns a new tuple on every
  call.
* Conversion is counted: an object with `__float__` has it called once per
  argument; one with both `__complex__` and `__float__` has only
  `__complex__` called; one with only `__index__` has it called once;
  `log(z, base)` and `isclose(a, b, rel_tol=..., abs_tol=...)` convert each
  argument once; `rect(r, phi)` calls `__float__` once per argument and
  rejects a `complex`.
* An `int` converts only while a double can hold it: `2**1024 - 2**971`, the
  largest finite double, converts exactly and `2**1024` raises
  `OverflowError`, so an `int` that converts is at most 1,024 bits.
* `log(0)`, `log10(0)`, `atan(1j)` and `atanh(1)` raise `ValueError`, and
  `exp(1000)` raises `OverflowError`; no NaN is returned.
* `sqrt()` returns the principal root: `sqrt(-4) == 2j`, and over 1,000 random
  complex inputs the real part is non-negative and the square is close to the
  input. `phase()` lies in [-pi, pi] over the same inputs, and the sign of a
  zero imaginary part picks pi or -pi on the negative real axis.
* `polar(z)` equals `(abs(z), phase(z))`, and `rect()` inverts it within
  `isclose()` over the random inputs.
* `isfinite()` is false when either part is infinite or NaN, `isinf()` and
  `isnan()` true when either part is; `isclose()` honours `rel_tol` and
  `abs_tol` and is false against a value outside both.
* The constants: `pi`, `e`, `tau` and `inf` equal the `math` constants, `nan`
  is a float NaN, and `infj` and `nanj` are `complex` with a zero real part.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* "O(1) per call" is a definitional bound for fixed-width doubles: there is no
  size variable to vary, and no timing test is made. Rejecting an oversized
  `int` is not priced; it can scan the int's digits before raising.
* The cost of a caller's `__complex__`, `__float__` or `__index__` is the
  caller's; only how many times each is called is asserted.
* Accuracy of the results beyond `isclose()` at default tolerance, and the
  special-value tables for infinite and NaN inputs other than those named
  above, are not varied.
"""

from __future__ import annotations

import cmath
import gc
import math
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "cmath.md"
EXPECTED_BLOCKS = 6

COMPLEX_RESULTS: list[Callable[..., complex]] = [
    cmath.exp,
    cmath.log,
    cmath.log10,
    cmath.sqrt,
    cmath.sin,
    cmath.cos,
    cmath.tan,
    cmath.asin,
    cmath.acos,
    cmath.atan,
    cmath.sinh,
    cmath.cosh,
    cmath.tanh,
    cmath.asinh,
    cmath.acosh,
    cmath.atanh,
]
CLASSIFIERS: list[Callable[[Any], bool]] = [cmath.isfinite, cmath.isinf, cmath.isnan]


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    gc.collect()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def random_complexes(count: int) -> list[complex]:
    rng = random.Random(20260930)
    return [complex(rng.uniform(-50, 50), rng.uniform(-50, 50)) for _ in range(count)]


class Counted:
    """A number that records which conversion methods were called on it."""

    def __init__(self, value: float) -> None:
        self.value = value
        self.calls: list[str] = []


class FloatLike(Counted):
    def __float__(self) -> float:
        self.calls.append("__float__")
        return float(self.value)


class ComplexAndFloatLike(FloatLike):
    def __complex__(self) -> complex:
        self.calls.append("__complex__")
        return complex(self.value)


class IndexLike(Counted):
    def __index__(self) -> int:
        self.calls.append("__index__")
        return int(self.value)


class TestEveryCallReturnsOneFixedWidthValue:
    """Every row is O(1) time and space: the result is one `complex`, `float`,
    `bool` or two-float tuple, whatever the input type."""

    @pytest.mark.parametrize("func", COMPLEX_RESULTS, ids=lambda f: f.__name__)
    @pytest.mark.parametrize("value", [0.5 + 0.25j, 0.5, 2])
    def test_functions_return_a_complex(self, func: Callable[..., complex], value: Any) -> None:
        assert type(func(value)) is complex

    @pytest.mark.parametrize("value", [3 + 4j, 3.0, 3])
    def test_conversions_return_their_documented_types(self, value: Any) -> None:
        assert type(cmath.phase(value)) is float
        result = cmath.polar(value)
        assert type(result) is tuple and [type(part) for part in result] == [float, float]

    def test_rect_returns_a_complex(self) -> None:
        assert type(cmath.rect(5, 0.5)) is complex

    @pytest.mark.parametrize("func", CLASSIFIERS, ids=lambda f: f.__name__)
    @pytest.mark.parametrize("value", [1 + 2j, 1.5, 1])
    def test_classification_returns_a_bool(self, func: Callable[[Any], bool], value: Any) -> None:
        assert type(func(value)) is bool
        assert type(cmath.isclose(value, value)) is bool

    def test_a_call_allocates_nothing_that_grows(self) -> None:
        z = 0.5 + 0.25j

        def many_calls() -> None:
            for _ in range(1_000):
                for func in COMPLEX_RESULTS:
                    func(z)
                cmath.polar(z)

        many_calls()
        peak = peak_bytes(many_calls)
        assert peak < 2_000, f"1,000 rounds of calls peaked at {peak} bytes"

    def test_polar_builds_a_new_tuple(self) -> None:
        z = 3 + 4j
        assert cmath.polar(z) is not cmath.polar(z)


class TestArgumentsAreConvertedOnce:
    """Arguments other than `complex` or `float` go through `__complex__`,
    `__float__` or `__index__`, once per argument, before the function runs."""

    def test_float_is_called_once(self) -> None:
        value = FloatLike(9)
        assert cmath.sqrt(value) == 3 + 0j
        assert value.calls == ["__float__"]

    def test_complex_is_preferred_to_float(self) -> None:
        value = ComplexAndFloatLike(9)
        assert cmath.sqrt(value) == 3 + 0j
        assert value.calls == ["__complex__"]

    def test_index_is_the_last_resort(self) -> None:
        value = IndexLike(9)
        assert cmath.sqrt(value) == 3 + 0j
        assert value.calls == ["__index__"]

    def test_log_converts_both_arguments_once(self) -> None:
        z, base = FloatLike(8), FloatLike(2)
        assert cmath.isclose(cmath.log(z, base), 3)
        assert z.calls == ["__float__"] and base.calls == ["__float__"]

    def test_isclose_converts_all_four_arguments_once(self) -> None:
        a, b, rel, absolute = FloatLike(1), FloatLike(1.5), FloatLike(0.5), FloatLike(0)
        assert cmath.isclose(a, b, rel_tol=rel, abs_tol=absolute)
        assert [x.calls for x in (a, b, rel, absolute)] == [["__float__"]] * 4

    def test_rect_takes_two_real_arguments(self) -> None:
        r, phi = FloatLike(2), FloatLike(0)
        assert cmath.rect(r, phi) == 2 + 0j
        assert r.calls == ["__float__"] and phi.calls == ["__float__"]
        with pytest.raises(TypeError):
            cmath.rect(1j, 0)  # type: ignore[arg-type]


class TestAnIntConvertsOnlyWhileADoubleHoldsIt:
    """An `int` that converts is at most 1,024 bits; a larger one raises
    `OverflowError` instead of being processed."""

    def test_the_largest_double_converts(self) -> None:
        largest = 2**1024 - 2**971
        assert float(largest) == sys.float_info.max
        assert cmath.sqrt(largest) == complex(math.sqrt(sys.float_info.max))
        assert largest.bit_length() == 1024

    def test_one_more_bit_raises(self) -> None:
        with pytest.raises(OverflowError, match="too large to convert to float"):
            cmath.sqrt(2**1024)


class TestErrorsRaiseRatherThanReturnSpecialValues:
    """Domain errors raise `ValueError`, range errors `OverflowError`."""

    @pytest.mark.parametrize(
        ("func", "value"),
        [(cmath.log, 0), (cmath.log10, 0), (cmath.atan, 1j), (cmath.atanh, 1)],
        ids=["log", "log10", "atan", "atanh"],
    )
    def test_domain_errors(self, func: Callable[[Any], complex], value: Any) -> None:
        with pytest.raises(ValueError, match="math domain error"):
            func(value)

    def test_range_error(self) -> None:
        with pytest.raises(OverflowError, match="math range error"):
            cmath.exp(1000)


class TestPolarAndPrincipalValues:
    """`sqrt()` is the principal root, `phase()` lies in [-pi, pi] with the sign
    of a zero imaginary part choosing the end, and `rect()` inverts `polar()`."""

    def test_sqrt_is_the_principal_root(self) -> None:
        assert cmath.sqrt(-4) == 2j
        for z in random_complexes(1_000):
            root = cmath.sqrt(z)
            assert root.real >= 0
            assert cmath.isclose(root * root, z)

    def test_phase_range_and_signed_zero(self) -> None:
        for z in random_complexes(1_000):
            assert -math.pi <= cmath.phase(z) <= math.pi
        assert cmath.phase(complex(-1.0, 0.0)) == math.pi
        assert cmath.phase(complex(-1.0, -0.0)) == -math.pi

    def test_polar_is_abs_and_phase_and_rect_inverts_it(self) -> None:
        for z in random_complexes(1_000):
            r, phi = cmath.polar(z)
            assert (r, phi) == (abs(z), cmath.phase(z))
            assert cmath.isclose(cmath.rect(r, phi), z)


class TestClassification:
    """`isfinite()` needs both parts finite; `isinf()` and `isnan()` need either
    part; `isclose()` compares against `rel_tol` and `abs_tol`."""

    inf = float("inf")
    nan = float("nan")

    def test_either_part_decides(self) -> None:
        for z in (complex(self.inf, 0), complex(0, self.inf)):
            assert cmath.isinf(z) and not cmath.isfinite(z) and not cmath.isnan(z)
        for z in (complex(self.nan, 0), complex(0, self.nan)):
            assert cmath.isnan(z) and not cmath.isfinite(z) and not cmath.isinf(z)
        assert cmath.isfinite(1 + 2j)

    def test_isclose_tolerances(self) -> None:
        assert not cmath.isclose(1, 1 + 1e-6)
        assert cmath.isclose(1, 1 + 1e-6, rel_tol=1e-5)
        assert cmath.isclose(0, 1e-12j, abs_tol=1e-11)
        assert not cmath.isclose(0, 1e-12j)


class TestConstants:
    """The float constants match `math`; `infj` and `nanj` are complex with a
    zero real part."""

    def test_float_constants(self) -> None:
        assert (cmath.pi, cmath.e, cmath.tau, cmath.inf) == (math.pi, math.e, math.tau, math.inf)
        assert type(cmath.nan) is float and math.isnan(cmath.nan)

    def test_imaginary_constants(self) -> None:
        assert type(cmath.infj) is complex and type(cmath.nanj) is complex
        assert cmath.infj.real == 0 and math.isinf(cmath.infj.imag)
        assert cmath.nanj.real == 0 and math.isnan(cmath.nanj.imag)


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
        line, source = next((n, s) for n, s in _blocks() if "assert Meters.calls == 1" in s)
        mutated = source.replace("assert Meters.calls == 1", "assert Meters.calls == 2", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
