"""Tests for docs/builtins/complex_func.md.

complex() is complex.__new__ in Objects/complexobject.c. A single exact
complex argument is returned as the same object; a str goes to
complex_subtype_from_string, which calls _PyUnicode_TransformDecimalAndSpaceToASCII
(the same object back for an ASCII string, an O(n) copy otherwise) and
_Py_string_to_number_with_underscores (a copy only when the string contains
an underscore). A number is converted with PyNumber_Float / PyFloat_AsDouble;
an int goes through PyLong_AsDouble, which raises OverflowError past
DBL_MAX_EXP bits. Its sticky-bit loop scans the low digits until the first
nonzero one, so rejecting a power of two is O(d) in the int's digits while a
typical large int stops after a few. From v3.14.2: complex.from_number(), a
DeprecationWarning for a complex `real` or `imag` argument, and TypeError for
a string passed as `real=` (v3.10.19 to v3.13.11 accept it).

Measurement scope:

* identity: complex(c) is c for an exact complex;
* time, string: a thousandfold step in length, 2,002 to 2,000,002 characters,
  measured x1,006 (3.10) and x1,119 (3.14). The test accepts x100 to x30,000:
  a constant-time claim predicts x1 and a quadratic one x1,000,000;
* space, string: tracemalloc's peak parsing a 200,002-character ASCII string
  is under 1 KiB; a 200,001-character string of Arabic-Indic digits peaks above
  its length, as does an ASCII one with underscores;
* int: 2**1000 converts; 10**400 and a 10,000,000-bit int raise OverflowError.
  Peak space for rejecting the 10,000,000-bit int is under 1 KiB;
* the protocol order: an object with `__complex__` and `__float__` has only
  `__complex__` called, once; one with only `__index__` has it called once;
* the version-gated 3.14 behaviour, and that a literal compiles to a constant
  while complex(3, 4) compiles to a call;
* every stated example value, and every fenced block runs in a subprocess.

Not settled here:

* The O(1) rows for two numbers, a float, conjugate(), real/imag and the
  arithmetic and cmath examples are not timed: their inputs are two doubles,
  with no size to vary.
* Not varied: int subclasses and float subclasses as arguments, complex
  subclasses as the class or the argument (the identity shortcut is exact-type
  only).
* Rejection time is not priced on the page: rejecting 1 << 10_000_000 against
  1 << 1100 measured x846 (3.10) and x1,300 (3.14), from the sticky-bit scan
  over zero low digits, a power-of-two shape that ordinary ints do not have.
"""

from __future__ import annotations

import cmath
import dis
import math
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "complex_func.md"
EXPECTED_BLOCKS = 12


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


def reject(value: int) -> None:
    """Call complex() on an int too large for a float, which must raise."""
    try:
        complex(value)
    except OverflowError:
        return
    raise AssertionError("complex() accepted an int too large for a float")


class TestFromNumbers:
    """Rows: complex(), from two numbers, from int/float - O(1)."""

    def test_values(self) -> None:
        assert complex() == 0j  # noqa: UP018 - the call is the subject
        assert complex(3, 4) == 3 + 4j
        assert complex(real=3, imag=4) == 3 + 4j
        assert complex(3) == 3 + 0j
        assert complex(3.14) == 3.14 + 0j

    def test_an_int_must_fit_in_a_float(self) -> None:
        assert complex(1 << 1000).real == float(1 << 1000)
        with pytest.raises(OverflowError, match="too large to convert to float"):
            complex(10**400)


class TestFromComplex:
    """Row: from complex - an exact complex is returned as the same object."""

    def test_identity(self) -> None:
        original = complex(3, 4)

        assert complex(original) is original


class TestHugeInt:
    """Row: from int/float - an int too large for a float raises OverflowError."""

    @pytest.mark.serial
    def test_rejection_takes_constant_space(self) -> None:
        large = 1 << 10_000_000

        assert traced_peak(lambda: reject(large)) < 1024


class TestFromString:
    """Row: from string - O(n) time, O(n) space; no copy for an ASCII string
    without underscores."""

    @staticmethod
    def _text(digits: int, digit: str = "1") -> str:
        return digit * digits + "+" + "2" * digits + "j"

    def test_accepted_forms(self) -> None:
        assert complex("3+4j") == 3 + 4j
        assert complex("-1-2j") == -1 - 2j
        assert complex("5j") == 5j
        assert complex("10") == 10 + 0j
        assert complex(" (3+4j) ") == 3 + 4j
        assert complex("1_000+2j") == 1000 + 2j
        assert complex("٣+4j") == 3 + 4j

    @pytest.mark.parametrize("text", ["3 + 4j", "3+4j+5j"])
    def test_malformed(self, text: str) -> None:
        with pytest.raises(ValueError, match="malformed string"):
            complex(text)

    def test_a_string_cannot_take_an_imaginary_part(self) -> None:
        with pytest.raises(TypeError):
            complex("1", 2)  # type: ignore[call-overload]

    @pytest.mark.timing
    def test_parsing_is_linear(self) -> None:
        small = self._text(1_000)
        large = self._text(1_000_000)

        ratio = best_time(lambda: complex(large), loops=5) / best_time(
            lambda: complex(small), loops=2000
        )

        assert 100 < ratio < 30_000, f"x{ratio:.1f} for x1,000 in length"

    @pytest.mark.serial
    def test_ascii_is_parsed_in_place(self) -> None:
        text = self._text(100_000)

        assert traced_peak(lambda: complex(text)) < 1024

    @pytest.mark.serial
    @pytest.mark.parametrize(
        "text",
        ["١" * 200_000 + "j", "1_" * 100_000 + "1j"],
        ids=["non-ascii", "underscores"],
    )
    def test_copied_strings_take_linear_space(self, text: str) -> None:
        assert traced_peak(lambda: complex(text)) > len(text)


class TestProtocols:
    """Row: object with __complex__, __float__ or __index__ - method + O(1),
    __complex__ tried first."""

    def test_complex_is_tried_first(self) -> None:
        calls: list[str] = []

        class Both:
            def __complex__(self) -> complex:
                calls.append("complex")
                return 1 + 2j

            def __float__(self) -> float:
                calls.append("float")
                return 3.0

        assert complex(Both()) == 1 + 2j
        assert calls == ["complex"]

    def test_float_is_tried_before_index(self) -> None:
        calls: list[str] = []

        class Both:
            def __float__(self) -> float:
                calls.append("float")
                return 3.0

            def __index__(self) -> int:
                calls.append("index")
                return 7

        assert complex(Both()) == 3 + 0j
        assert calls == ["float"]

    def test_index_is_called_once(self) -> None:
        calls: list[int] = []

        class Index:
            def __index__(self) -> int:
                calls.append(1)
                return 7

        assert complex(Index()) == 7 + 0j  # type: ignore[call-overload]
        assert calls == [1]


class TestVersion314:
    """Version Notes: Python 3.14+."""

    def test_from_number(self) -> None:
        if sys.version_info < (3, 14):
            assert not hasattr(complex, "from_number")
            return
        original = 1 + 2j
        assert complex.from_number(original) is original  # type: ignore[attr-defined]
        assert complex.from_number(3.14) == 3.14 + 0j  # type: ignore[attr-defined]
        with pytest.raises(TypeError):
            complex.from_number("3+4j")  # type: ignore[attr-defined]

    @pytest.mark.parametrize("args", [(1, 2j), (1j, 2)])
    def test_complex_parts_are_deprecated(self, args: tuple[complex, complex]) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            complex(*args)

        deprecated = any(issubclass(w.category, DeprecationWarning) for w in caught)
        assert deprecated == (sys.version_info >= (3, 14))

    def test_string_as_real_keyword(self) -> None:
        if sys.version_info >= (3, 14):
            with pytest.raises(TypeError):
                complex(real="1")  # type: ignore[call-overload]
        else:
            assert complex(real="1") == 1 + 0j  # type: ignore[call-overload]


class TestLiteral:
    """Literal vs complex(): a literal is a constant, complex(3, 4) is a call."""

    def test_a_literal_compiles_to_a_constant(self) -> None:
        literal = list(dis.get_instructions(compile("3 + 4j", "<s>", "eval")))
        call = [i.opname for i in dis.get_instructions(compile("complex(3, 4)", "<s>", "eval"))]

        assert any("CONST" in i.opname and i.argval == 3 + 4j for i in literal), literal
        assert not any(i.opname.startswith(("CALL", "BINARY")) for i in literal), literal
        assert any(name.startswith("CALL") for name in call), call


class TestStatedExampleValues:
    """The values the page's comments and asserts give, checked rather than trusted."""

    def test_arithmetic(self) -> None:
        c1, c2 = complex(3, 4), complex(1, 2)
        assert c1 + c2 == 4 + 6j
        assert c1 * c2 == -5 + 10j
        assert c1 / c2 == 2.2 - 0.4j
        assert c1**2 == -7 + 24j
        assert abs(c1) == 5.0
        assert c1.conjugate() == 3 - 4j
        assert (c1 * c1.conjugate()).real == 25.0

    def test_math_rejects_complex(self) -> None:
        with pytest.raises(TypeError):
            math.sqrt(1j)  # type: ignore[arg-type]
        assert cmath.sqrt(-1) == 1j


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
    DeprecationWarning as an error."""

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
        block = next(source for _, source in _blocks() if "complex(10**400)" in source)
        broken = block.replace("except OverflowError", "except TypeError", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "OverflowError" in result.stderr
