"""Tests for docs/builtins/float_func.md.

float() is float_new_impl in Objects/floatobject.c. With no argument it
returns 0.0; an exact str goes to PyFloat_FromString, and everything else to
PyNumber_Float in Objects/abstract.c, which returns an exact float as the same
object, calls `__float__` if the type has one, else `__index__`, copies a float
subclass's value, and hands anything else to PyFloat_FromString. That function
parses a str after _PyUnicode_TransformDecimalAndSpaceToASCII, which returns the
same object for an ASCII string and builds an O(n) ASCII copy otherwise; bytes
and bytearray are read in place, and any other buffer is copied into a bytes
object. _Py_string_to_number_with_underscores copies the text only when it
contains an underscore. An int goes through PyLong_AsDouble, which converts
compact ints directly and others with _PyLong_Frexp, raising OverflowError past
DBL_MAX_EXP bits. Python/dtoa.c and Python/pystrtod.c differ between v3.11.14
and v3.14.2 in allocation, interpreter state and how infinity and NaN are
spelled, not in the parsing algorithm. float.from_number() is new in v3.14.

Measurement scope:

* time, strings: four shapes at 20,000, 200,000 and 2,000,000 characters -
  plain ASCII digits, a 2**53 + 1 halfway case followed by zeros and a final
  1 (its rounding depends on that last digit), whitespace padding, and
  Arabic-Indic digits (the copying path). Each tenfold step is asserted
  between x3 and x40: linear predicts x10, quadratic x100. Measured here on
  3.14: x9.8 to x11.8 per step across the four shapes;
* space, strings: tracemalloc's peak parsing 200,000-character ASCII digits,
  whitespace-padded text or the halfway case, and 200,000-byte bytes and
  bytearray, is under 1 KiB; underscores, Arabic-Indic digits, EM SPACE
  padding, a memoryview and an array.array peak above 200,000 bytes, so the
  small peaks are not an unmeasured operation. A non-contiguous memoryview
  raises TypeError;
* identity: float(x) is x for an exact float; a float subclass instance
  comes back as a new, exact float;
* ints: 2**1023 converts and 2**1024 and 2**1024 - 1 raise OverflowError,
  which bounds every convertible int at 1,024 bits. Rejecting 2**k costs
  between x20 and x1,000 from k = 100,000 to k = 10,000,000 (linear
  predicts x100, constant x1, quadratic x10,000; measured here about x90),
  and so does an object whose `__index__` returns 2**k; rejecting an int
  with a nonzero bit 100 places below its top bit costs under x5 over the
  same step (measured about x1), because _PyLong_Frexp's sticky-bit loop
  stops at the first nonzero digit;
* the protocol order: an object with `__float__` and `__index__` has only
  `__float__` called, once; one with only `__index__` has it called once;
* special values in any case, with a sign and surrounding whitespace; every
  rejected string named on the page raises ValueError and a list TypeError;
* range: 1e309 and an exponent of a hundred digits give infinity, 1e-324
  gives 0.0, 2**53 + 1 rounds to 2**53, and the result's getsizeof is that of
  1.0 for 300 digits while an int's grows with its digits; int() refuses
  more than 4,300 digits where float() accepts 10,000;
* a literal compiles to a constant and float("3.14") to a call;
* float.from_number() on 3.14+: it converts a number and raises TypeError
  for a string;
* every fenced Python block runs in its own subprocess with
  DeprecationWarning as an error, and a mutated assertion in one of them is
  asserted to fail.

Not settled here:

* That int() parsing is superlinear is the int() page's claim, measured in
  tests/test_complexity_caveats.py (TestIntFromStringIsSuperlinear); this
  file checks only the digit limit.
* The O(1) rows for no argument, a float and a bool are not timed. The
  int row's O(d) is timed only on the rejecting path: a convertible int has
  at most 1,024 bits, too few to separate from call overhead.
* The "method + O(1)" row prices the caller's `__float__` or `__index__` as
  the method's own cost; only call counts are observed.
* The space rows price a successful parse. A rejected string's ValueError
  message carries the argument's repr, so a failure holds O(n) space.
* The example blocks and the digit-limit tests assume the default int digit
  limit; an interpreter run with PYTHONINTMAXSTRDIGITS set fails them.
* An int or float subclass that overrides `__float__` is priced by the
  protocol row, as its method's cost; only inherited conversion is tested.
* Not varied: str subclasses as the argument, strings beyond dtoa.c's
  MAX_DIGITS (10**9 digits), exponent-digit counts beyond a hundred, and
  bytes containing underscores or non-ASCII bytes.
"""

from __future__ import annotations

import array
import dis
import math
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "float_func.md"
EXPECTED_BLOCKS = 9

SIZES = (20_000, 200_000, 2_000_000)
SPACE_SIZE = 200_000
SMALL_PEAK = 1024


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 3) -> float:
    """The fastest of several runs of `loops` calls, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times) / loops


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc sees while `func` runs, after one warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class TestConvertingNumbers:
    """Rows `float()`, a float, an int or bool: values, identity and the 1,024-bit
    limit. The int row's O(d) is timed in TestIntConversionScan."""

    def test_values(self) -> None:
        assert float() == 0.0  # noqa: UP018 - the call is the subject
        assert float(42) == 42.0
        assert float(True) == 1.0
        assert float(False) == 0.0
        assert float(2**1023) == 8.98846567431158e307

    def test_an_exact_float_comes_back_as_the_same_object(self) -> None:
        value = 3.14
        assert float(value) is value

    def test_a_float_subclass_becomes_a_new_exact_float(self) -> None:
        class Sub(float):
            pass

        value = Sub(2.5)
        result = float(value)

        assert result is not value
        assert type(result) is float
        assert result == 2.5

    def test_every_convertible_int_has_at_most_1024_bits(self) -> None:
        assert float((1 << 1024) - (1 << 970) - 1) == sys.float_info.max
        with pytest.raises(OverflowError, match="too large to convert to float"):
            float(1 << 1024)
        with pytest.raises(OverflowError, match="too large to convert to float"):
            float((1 << 1024) - 1)


class TestIntConversionScan:
    """Int row and Converting Numbers: the scan below an int's top bits reads
    a power of two in full, even when the int is then rejected, and stops at
    once for an int with a nonzero bit near its top."""

    @staticmethod
    def _reject(value: Any) -> None:
        try:
            float(value)
        except OverflowError:
            return
        raise AssertionError("an int beyond the float range was converted")

    @pytest.mark.timing
    def test_an_index_result_is_scanned_too(self) -> None:
        class Index:
            def __init__(self, value: int) -> None:
                self.value = value

            def __index__(self) -> int:
                return self.value

        small, large = Index(1 << 100_000), Index(1 << 10_000_000)
        small_time = best_time(lambda: self._reject(small))
        large_time = best_time(lambda: self._reject(large))
        ratio = large_time / small_time
        assert 20 < ratio < 1_000, f"100x the bits cost x{ratio:.1f}; linear predicts x100"

    @pytest.mark.timing
    def test_rejecting_a_power_of_two_is_linear(self) -> None:
        small, large = 1 << 100_000, 1 << 10_000_000
        small_time = best_time(lambda: self._reject(small))
        large_time = best_time(lambda: self._reject(large))
        ratio = large_time / small_time
        assert 20 < ratio < 1_000, f"100x the bits cost x{ratio:.1f}; linear predicts x100"

    @pytest.mark.timing
    def test_a_nonzero_bit_below_the_top_stops_the_scan(self) -> None:
        # The top bit, and a nonzero bit 100 places below it, within the
        # first few digits the conversion shifts out.
        small = 1 << 99_999 | 1 << 99_899
        large = 1 << 9_999_999 | 1 << 9_999_899
        small_time = best_time(lambda: self._reject(small), loops=100)
        large_time = best_time(lambda: self._reject(large), loops=100)
        ratio = large_time / small_time
        assert ratio < 5, f"100x the bits cost x{ratio:.1f}; an early stop predicts x1"


class TestProtocolOrder:
    """Row: `x` defines `__float__` or `__index__` - `__float__` is tried
    first, and the method is called once."""

    def test_float_is_called_and_index_is_not(self) -> None:
        calls: list[str] = []

        class Both:
            def __float__(self) -> float:
                calls.append("__float__")
                return 1.5

            def __index__(self) -> int:
                calls.append("__index__")
                return 7

        assert float(Both()) == 1.5
        assert calls == ["__float__"]

    def test_index_is_used_without_float(self) -> None:
        calls: list[str] = []

        class OnlyIndex:
            def __index__(self) -> int:
                calls.append("__index__")
                return 7

        assert float(OnlyIndex()) == 7.0
        assert calls == ["__index__"]


def _digits(n: int) -> str:
    return "1" * n


def _halfway(n: int) -> str:
    # Exactly between 2**53 and 2**53 + 2 until the final digit: the
    # correctly-rounded comparison has to read every digit.
    return "9007199254740993." + "0" * n + "1"


def _padded(n: int) -> str:
    return " " * n + "1.5"


def _arabic_indic(n: int) -> str:
    return "\u0663" * n


class TestStringParsingIsLinear:
    """Rows for strings - O(n) time, on every shape the page names."""

    @pytest.mark.timing
    @pytest.mark.parametrize("make", [_digits, _halfway, _padded, _arabic_indic])
    def test_each_tenfold_step_costs_about_tenfold(self, make: Callable[[int], str]) -> None:
        texts = [make(n) for n in SIZES]
        times = [best_time(lambda text=text: float(text)) for text in texts]
        ratios = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]

        for ratio in ratios:
            assert 3 < ratio < 40, (
                f"{make.__name__}: a tenfold step should cost about tenfold, "
                f"not x100 (quadratic) or x1 (constant): ratios {ratios}, times {times}"
            )

    def test_the_halfway_input_rounds_on_its_last_digit(self) -> None:
        assert float(_halfway(10_000)) == 2.0**53 + 2
        assert float("9007199254740993." + "0" * 10_000) == 2.0**53


class TestStringParsingSpace:
    """Rows for strings and buffers - O(1) space in place, O(n) for a copy."""

    @pytest.mark.serial
    @pytest.mark.parametrize(
        "value",
        [
            "1" * SPACE_SIZE + ".5",
            " " * SPACE_SIZE + "1.5",
            _halfway(SPACE_SIZE),
            b"1" * SPACE_SIZE,
            bytearray(b"1" * SPACE_SIZE),
        ],
        ids=["ascii", "ascii-whitespace", "halfway", "bytes", "bytearray"],
    )
    def test_parsing_in_place_allocates_nothing_that_grows(self, value: Any) -> None:
        peak = traced_peak(lambda: float(value))
        assert peak < SMALL_PEAK, f"parsed in place, yet peaked at {peak} bytes"

    @pytest.mark.parametrize(
        "value",
        [
            "1_" * (SPACE_SIZE // 2) + "1",
            "\u0663" * SPACE_SIZE,
            "\u2003" * SPACE_SIZE + "1",
            memoryview(b"1" * SPACE_SIZE),
            array.array("b", b"1" * SPACE_SIZE),
        ],
        ids=["underscores", "arabic-indic-digits", "em-space", "memoryview", "array"],
    )
    def test_a_copied_argument_allocates_its_length(self, value: Any) -> None:
        peak = traced_peak(lambda: float(value))
        assert peak > SPACE_SIZE, f"a copy was expected, but the peak was {peak} bytes"

    def test_a_non_contiguous_buffer_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="must be a string or a real number"):
            float(memoryview(b"1234")[::2])  # type: ignore[arg-type]


class TestStringValues:
    """Notation, special values, whitespace and invalid strings, as the page's
    examples state them."""

    def test_notation(self) -> None:
        assert float("1.23e-4") == 0.000123
        assert float("1E10") == 10000000000.0
        assert float(".5") == 0.5
        assert float("5.") == 5.0
        assert float(b"2.5") == 2.5

    @pytest.mark.parametrize(
        ("text", "expected"),
        [("inf", math.inf), ("-Infinity", -math.inf), (" +iNfInItY\n", math.inf)],
    )
    def test_infinity_in_any_case(self, text: str, expected: float) -> None:
        assert float(text) == expected

    @pytest.mark.parametrize("text", ["nan", "NaN", "-NAN", "\tnan "])
    def test_nan_in_any_case(self, text: str) -> None:
        assert math.isnan(float(text))

    def test_whitespace_underscores_and_non_ascii(self) -> None:
        assert float("\t2.5\n") == 2.5
        assert float("1_000.5") == 1000.5
        assert float("\u0663.\u0665") == 3.5
        assert float("\u20031.5\u3000") == 1.5

    @pytest.mark.parametrize(
        "text", ["", "   ", "3.14.15", "1.5x", "x1.5", "1__0", "_1", "1_", "0x10", "infinit"]
    )
    def test_invalid_strings_raise_value_error(self, text: str) -> None:
        with pytest.raises(ValueError, match="could not convert string to float"):
            float(text)

    def test_other_types_raise_type_error(self) -> None:
        with pytest.raises(TypeError, match="must be a string or a real number"):
            float([1.5])  # type: ignore[arg-type]


class TestRangeAndRounding:
    """Range and Rounding: out-of-range values become infinity or zero, and
    the result is one double however many digits it is given."""

    def test_overflow_and_underflow_do_not_raise(self) -> None:
        assert float("1e308") < sys.float_info.max
        assert float("1e309") == math.inf
        assert float("1e" + "9" * 100) == math.inf
        assert float("1e-324") == 0.0
        assert float("-1e-324") == 0.0

    def test_digits_beyond_53_bits_are_rounded_away(self) -> None:
        assert sys.float_info.mant_dig == 53
        assert float("9007199254740993") == 9007199254740992.0
        assert float("3." + "14" * 500) == 3.1414141414141414

    def test_the_result_is_fixed_width(self) -> None:
        assert sys.getsizeof(float("9" * 300)) == sys.getsizeof(1.0)

    def test_an_int_result_grows_with_its_digits(self) -> None:
        assert sys.getsizeof(int("9" * 300)) > sys.getsizeof(int("9" * 30))


class TestFloatVsInt:
    """float() vs int() on Strings: int() refuses a decimal string over 4,300
    digits by default; float() has no such limit."""

    def test_int_has_a_digit_limit(self) -> None:
        assert sys.int_info.default_max_str_digits == 4300
        with pytest.raises(ValueError, match=r"Exceeds the limit \(4300 digits\)"):
            int("9" * (sys.int_info.default_max_str_digits + 1))

    def test_float_has_none(self) -> None:
        assert float("9" * 10_000) == math.inf
        assert float("0." + "1" * 10_000) == float("0." + "1" * 20)

    def test_int_rejects_a_decimal_point(self) -> None:
        with pytest.raises(ValueError):
            int("3.14")


class TestLiteralVsCall:
    """Literal vs float(): a literal is a compiled constant, float("3.14") a
    call made every time the code runs."""

    def test_a_literal_is_a_constant_and_float_is_a_call(self) -> None:
        def literal() -> float:
            return 3.14

        def parsed() -> float:
            return float("3.14")

        assert literal() == parsed()
        assert 3.14 in literal.__code__.co_consts
        assert not any(i.opname.startswith("CALL") for i in dis.get_instructions(literal))
        assert any(i.opname.startswith("CALL") for i in dis.get_instructions(parsed))


@pytest.mark.skipif(sys.version_info < (3, 14), reason="version: float.from_number() is 3.14+")
class TestFromNumber:
    """Version Notes: float.from_number() converts a number and rejects a
    string."""

    def test_converts_a_number(self) -> None:
        from_number: Any = getattr(float, "from_number")  # noqa: B009 - 3.14+ only
        assert from_number(True) == 1.0
        assert from_number(7) == 7.0

    def test_rejects_a_string(self) -> None:
        from_number: Any = getattr(float, "from_number")  # noqa: B009 - 3.14+ only
        with pytest.raises(TypeError):
            from_number("1.5")


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
        [sys.executable, "-W", "error::DeprecationWarning", script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, under the interpreter running the tests, with
    DeprecationWarning as an error, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        target = 'assert float("1e309") == math.inf'
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, 'assert float("1e309") == 0.0', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run(mutated, tmp_path).returncode != 0
