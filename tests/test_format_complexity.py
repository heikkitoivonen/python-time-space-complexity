"""Tests for docs/builtins/format.md.

`format(value, spec)` is one call to `type(value).__format__`, so the page's
bounds are the bounds of the built-in types' `__format__` methods plus the
dispatch around them. Dispatch is settled by observation: a counting
`__format__` and `__str__`, identity of the returned object, and the
`TypeError`s the page names. Identity rows are settled by `is`, so they need
no tolerance. The growth rows are settled by timing ratios over a 16x to 100x
step, chosen so the linear and quadratic predictions are at least 10x apart.

Measurement scope:

* dispatch: `format(obj, spec)` calls `type(obj).__format__` exactly once with
  the spec, ignores an instance attribute named `__format__`, and raises
  `TypeError` for a non-`str` result. `object.__format__` calls `__str__`
  exactly once for an empty spec and raises `TypeError` for `'>10'`.
* str: an exact one-million-character `str` is returned as the same object by
  `format(s)`, `format(s, '')`, `format(s, 's')`, `format(s, '<10')`,
  `format(s, '.2000000')`, `f'{s}'` and `f'{s:s}'`. A spec one character wider
  returns a new string of that length, and `'.3'` a three-character one. A
  `str` subclass comes back as a new exact `str`.
* padding: `format('', '<w')` for w = 100,000 and 10,000,000 grows less than
  1,000x (linear predicts 100, quadratic 10,000).
* int: `format(x)` and `format(x, 'd')` on 250-digit and 4,000-digit values
  grow more than 64x (linear predicts 16, quadratic 256). At 4,000 and 80,000
  digits, with the digit limit lifted, `format(x)` costs between half and
  twice `str(x)`, which ties it to the conversion the int page prices,
  including the 3.12+ divide-and-conquer path that
  tests/test_int_complexity.py measures above 30,000 bits. A 5,000-digit
  value raises `ValueError` under the default limit for `format(x)` and
  `format(x, ',')` and not for `'x'`. `format(x, 'x')` on 100,000-bit and
  10,000,000-bit values grows less than 1,000x (linear 100, quadratic 10,000).
  `format(10**400, 'f')` raises `OverflowError`, and `format(x, 'f')` equals
  `format(float(x), 'f')` for a value that fits.
* float: `format(0.1, '.Nf')` returns N + 2 characters for N = 10,000 and
  1,000,000, and its time grows less than 1,000x between them.
  `format(1.1, '.Ng')` returns the same 53-character string for both, while
  its traced peak is under 100 KB at N = 10,000 and over 500 KB at
  N = 1,000,000, so room for the precision is reserved even where `'g'` drops
  the zeros; its time grows less than 20x between them (linear in the
  precision predicts 100).
* f-strings: `f'{obj}'` and `f'{obj:spec}'` return the very object
  `__format__` returned. `str.format()` calls `__format__` once per field with
  that field's spec; `%s` calls `__str__` and never `__format__`. `%r`, `%d`
  and `%f` are not varied.
* 3.14+ fractional grouping: `'.4_f'` and `'.4,f'` format 1234.5678 as
  `'1234.567_8'` and `'1234.567,8'` from 3.14 and raise `ValueError` before
  it.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Pricing a format specification at O(1) is a cost-model assumption: the
  built-in specs are a few characters, and a long width only matters through
  the n characters it produces, which the padding test measures.
* The O(d) term of the int float presentation types is the int-to-float
  conversion that docs/builtins/float.md prices and tests; here only the
  overflow and the equal output are asserted.
* `'f'` on a float with a large exponent writes up to 309 integer digits; the
  cost of producing them is bounded by the float's range and is not varied.
* `Decimal`, `Fraction` and `datetime` specs are priced on their own pages;
  the datetime example here asserts output only.
* Non-ASCII fill characters and results are not varied.
"""

from __future__ import annotations

import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "format.md"
EXPECTED_BLOCKS = 10


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


def random_int(bits: int) -> int:
    """A random positive int of exactly `bits` bits."""
    return random.getrandbits(bits) | 1 << (bits - 1)


def decimal_int(digits: int) -> int:
    """A positive int of exactly `digits` decimal digits."""
    return 10**digits - 1


@pytest.fixture
def uncapped_digits() -> Iterator[None]:
    limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(0)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(limit)


@pytest.fixture
def default_cap() -> Iterator[None]:
    limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(4_300)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(limit)


class TestDispatchIsOneFormatCall:
    """`format(value, format_spec='')` is O(1) plus a call to
    `type(value).__format__`, observed here on a class that defines one; a
    non-`str` result raises `TypeError`."""

    def test_calls_the_types_format_once_with_the_spec(self) -> None:
        calls: list[str] = []

        class Recorder:
            def __format__(self, spec: str) -> str:
                calls.append(spec)
                return "done"

        obj = Recorder()
        obj.__format__ = lambda spec: "instance"  # type: ignore[method-assign]

        assert format(obj, ">5") == "done"
        assert calls == [">5"]

    def test_a_non_str_result_raises(self) -> None:
        class Broken:
            def __format__(self, spec: str) -> Any:
                return 42

        with pytest.raises(TypeError, match="must return a str"):
            format(Broken())


class TestObjectFormatIsStr:
    """`format(obj)` on a class that inherits `object.__format__` costs
    `str(obj)`; any non-empty spec raises `TypeError`."""

    def test_an_empty_spec_calls_str_once(self) -> None:
        calls = 0

        class Plain:
            def __str__(self) -> str:
                nonlocal calls
                calls += 1
                return "plain"

        assert format(Plain()) == "plain"
        assert calls == 1

    def test_any_other_spec_raises(self) -> None:
        with pytest.raises(TypeError, match="unsupported format string"):
            format(object(), ">10")


class TestStrIsReturnedUnchanged:
    """`format(s)`, `format(s, spec)`: O(1), the same object, when the spec
    neither pads nor truncates. A spec that does builds an O(n) result, and a
    subclass is copied into an exact `str`."""

    S = "x" * 1_000_000

    @pytest.mark.parametrize("spec", ["", "s", "<10", ".2000000"])
    def test_a_spec_that_changes_nothing_returns_s(self, spec: str) -> None:
        assert format(self.S, spec) is self.S

    def test_format_without_a_spec_returns_s(self) -> None:
        assert format(self.S) is self.S

    def test_an_fstring_of_one_field_returns_s(self) -> None:
        s = self.S
        assert f"{s}" is s
        assert f"{s:s}" is s

    def test_padding_builds_a_new_string_of_the_width(self) -> None:
        padded = format(self.S, f"<{len(self.S) + 1}")
        assert padded is not self.S
        assert len(padded) == len(self.S) + 1

    def test_truncating_builds_the_shorter_string(self) -> None:
        assert format(self.S, ".3") == "xxx"

    def test_a_subclass_comes_back_as_a_new_exact_str(self) -> None:
        class Sub(str):
            pass

        value = Sub("abc")
        result = format(value)
        assert type(result) is str
        assert result is not value
        assert result == "abc"


class TestPaddingIsLinearInWidth:
    """`format(s, spec)` that pads: O(n) in the result length."""

    @pytest.mark.timing
    def test_hundredfold_width_costs_far_less_than_quadratic(self) -> None:
        small = best_ns(lambda: format("", "<100000"))
        large = best_ns(lambda: format("", "<10000000"), repeats=5)

        growth = large / small
        assert growth < 1_000, f"x{growth:.0f} for 100x the width; linear 100, quadratic 10,000"


class TestIntDecimalIsTheStrConversion:
    """`format(x)`, `format(x, 'd')`, `format(x, ',')`: the conversion `str(x)`
    performs, O(d² + n) below 30,000 bits on every version, capped by
    `sys.get_int_max_str_digits()`."""

    @pytest.mark.timing
    @pytest.mark.parametrize("spec", ["", "d"])
    def test_quadratic_below_the_fast_path_threshold(self, spec: str) -> None:
        small, large = decimal_int(250), decimal_int(4_000)

        growth = best_ns(lambda: format(large, spec)) / best_ns(lambda: format(small, spec))

        assert growth > 64, f"x{growth:.1f} for 16x the digits; linear 16, quadratic 256"

    @pytest.mark.timing
    @pytest.mark.parametrize("digits", [4_000, 80_000])
    def test_costs_what_str_costs(self, uncapped_digits: None, digits: int) -> None:
        x = decimal_int(digits)
        repeats = 3 if digits > 10_000 else 7

        relative = best_ns(lambda: format(x), repeats) / best_ns(lambda: str(x), repeats)

        assert 0.5 < relative < 2, f"format(x) costs x{relative:.2f} str(x) at {digits} digits"

    def test_returns_what_str_returns(self) -> None:
        x = random_int(10_000)
        assert format(x) == format(x, "d") == str(x)

    @pytest.mark.parametrize("spec", ["", "d", ","])
    def test_the_digit_limit_applies(self, default_cap: None, spec: str) -> None:
        with pytest.raises(ValueError, match="limit"):
            format(decimal_int(5_000), spec)


class TestPowerOfTwoBasesAreLinear:
    """`format(x, 'b' / 'o' / 'x' / 'X')`: O(n), with no digit limit."""

    @pytest.mark.parametrize("spec", ["b", "o", "x", "X"])
    def test_the_digit_limit_does_not_apply(self, default_cap: None, spec: str) -> None:
        x = decimal_int(5_000)
        assert int(format(x, spec), {"b": 2, "o": 8, "x": 16, "X": 16}[spec]) == x

    @pytest.mark.timing
    def test_hundredfold_bits_cost_far_less_than_quadratic(self) -> None:
        small, large = random_int(100_000), random_int(10_000_000)

        growth = best_ns(lambda: format(large, "x"), repeats=5) / best_ns(
            lambda: format(small, "x")
        )

        assert growth < 1_000, f"x{growth:.0f} for 100x the bits; linear 100, quadratic 10,000"


class TestIntFloatTypesConvertFirst:
    """`format(x, 'e' / 'f' / 'g' / '%')` converts `x` to a float first, so an
    int too large for one raises `OverflowError`."""

    def test_an_int_beyond_the_float_range_overflows(self) -> None:
        with pytest.raises(OverflowError):
            format(10**400, "f")

    @pytest.mark.parametrize("spec", ["e", "f", "g", "%"])
    def test_the_result_is_the_floats(self, spec: str) -> None:
        x = 2**60 + 1
        assert format(x, spec) == format(float(x), spec)


class TestFloatPrecisionIsLinear:
    """`format(f, spec)`: O(n) time and O(n + p) space; `'f'` writes every
    digit of the precision, and `'g'` reserves room for all of them even when
    it drops trailing zeros."""

    @pytest.mark.parametrize("precision", [10_000, 1_000_000])
    def test_every_requested_digit_is_written(self, precision: int) -> None:
        assert len(format(0.1, f".{precision}f")) == precision + 2

    def test_g_pays_for_the_precision_it_drops(self) -> None:
        def peak(precision: int) -> tuple[str, int]:
            assert not tracemalloc.is_tracing()
            tracemalloc.start()
            try:
                result = format(1.1, f".{precision}g")
                return result, tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()

        (short, small), (long, large) = peak(10_000), peak(1_000_000)
        assert short == long and len(short) == 53
        assert small < 100_000, f"{small} bytes at precision 10,000"
        assert large > 500_000, f"{large} bytes at precision 1,000,000"

    @pytest.mark.timing
    def test_g_time_follows_the_result_not_the_precision(self) -> None:
        small = best_ns(lambda: format(1.1, ".10000g"), inner=20)
        large = best_ns(lambda: format(1.1, ".1000000g"), inner=20)

        growth = large / small
        assert growth < 20, f"x{growth:.1f} for 100x the precision; linear in it would be 100"

    @pytest.mark.timing
    def test_hundredfold_precision_costs_far_less_than_quadratic(self) -> None:
        small = best_ns(lambda: format(0.1, ".10000f"))
        large = best_ns(lambda: format(0.1, ".1000000f"), repeats=5)

        growth = large / small
        assert growth < 1_000, f"x{growth:.0f} for 100x the digits; linear 100, quadratic 10,000"


class TestFormattingSyntax:
    """f-strings and `str.format()` call `__format__` per field; `%s` calls
    `str()` instead; an f-string that is one field is that field's result."""

    def test_a_lone_fstring_field_is_the_format_result(self) -> None:
        produced: list[str] = []

        class Fresh:
            def __format__(self, spec: str) -> str:
                result = "".join(["fresh", spec])
                produced.append(result)
                return result

        obj = Fresh()
        assert f"{obj}" is produced[-1]
        assert f"{obj:>5}" is produced[-1]

    def test_str_format_calls_format_once_per_field(self) -> None:
        calls: list[str] = []

        class Recorder:
            def __format__(self, spec: str) -> str:
                calls.append(spec)
                return "r"

        # The subject is str.format() itself, which ruff would rewrite as an f-string
        template = "{:a} {} {:b}"
        assert template.format(Recorder(), Recorder(), Recorder()) == "r r r"
        assert calls == ["a", "", "b"]

    def test_percent_s_calls_str_not_format(self) -> None:
        calls: list[str] = []

        class Both:
            def __str__(self) -> str:
                calls.append("str")
                return "s"

            def __format__(self, spec: str) -> str:
                calls.append("format")
                return "f"

        assert "%s" % Both() == "s"  # noqa: UP031 - %-formatting is the subject
        assert calls == ["str"]


class TestFractionalGrouping:
    """Version Notes: from 3.14, `'_'` and `','` can group a float's
    fractional digits."""

    def test_grouping_after_the_point(self) -> None:
        for separator in "_,":
            spec = f".4{separator}f"
            if sys.version_info >= (3, 14):
                assert format(1234.5678, spec) == f"1234.567{separator}8"
            else:
                with pytest.raises(ValueError):
                    format(1234.5678, spec)


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
    """Each block runs in its own subprocess, so the digit limit one of them
    lifts cannot leak into another, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "format(s) is s" in s)
        mutated = source.replace("format(s) is s", "format(s) is not s", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
