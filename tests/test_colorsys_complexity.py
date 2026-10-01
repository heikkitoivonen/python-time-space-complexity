"""Tests for docs/stdlib/colorsys.md.

Every function on the page takes three floats and returns three, so no input
has a size and every row is O(1). That bound is read from Lib/colorsys.py; the
tests settle the behaviour the Notes column and the examples rely on - grey
handling, hue wrapping, YIQ clamping, round trips - by direct observation, and
the one cost claim with a size in it, the extra list a normalised copy costs,
by traced allocation across sizes.

Measurement scope:

* Each of the six functions is called on a non-grey colour under
  `tracemalloc`, after a warm-up call, and peaks under 4 KB; each returns a
  3-tuple, and two calls on the same input return equal tuples that are not
  the same object, so no result is cached.
* `colorsys.__all__` is exactly the six conversion functions: there is no
  batch form.
* `yiq_to_rgb()` is asserted to clamp an out-of-gamut colour into [0, 1], so
  that YIQ -> RGB -> YIQ does not return the original YIQ, and `rgb_to_yiq()` to
  return a negative I for blue without clamping.
* `rgb_to_hls()` and `rgb_to_hsv()` return hue and saturation 0.0 for six
  greys from black to white.
* `hls_to_rgb()` returns the same colour for hues h, h + 1 and h - 1 at
  h = 0.1, 0.4 and 0.9. `hsv_to_rgb()` does the same for h and h + 1, returns
  a negative channel for hue -0.1 and one above 1 for hue -0.25, and returns
  the hue-0.9 colour once -0.1 is reduced with `% 1.0`.
* Round trips through HLS and HSV are `math.isclose()` to the input on a grid
  of 216 colours, and for (0, 15/255, 45/255) both are close but not equal.
  Through HSV, a red of 1e-20 comes back as 0.0: `math.isclose()` rejects it
  with the default tolerances and accepts it with `abs_tol=1e-12`.
* Passing 0-255 components (255, 100, 50) to `rgb_to_hsv()` and
  `rgb_to_hls()` raises nothing and returns a value outside [0, 1], and
  `rgb_to_hls(2, 1, 0)` raises `ZeroDivisionError`.
* Building a normalised copy of n colours before converting them peaks above
  the inline comprehension by an amount that grows more than 20x when n goes
  from 2,000 to 200,000 (O(n) predicts 100x, a constant 1x). The inputs are
  built before the measurement and only random 0-255 triples are used.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* O(1) time for every function is read from Lib/colorsys.py on 3.10 to 3.14:
  each is straight-line float arithmetic with no loop or recursion, and the
  module is unchanged across that range apart from how `rgb_to_hls()` and
  `rgb_to_hsv()` spell the range term. Timing a function with no size
  variable would assert nothing a constant could falsify.
* Treating float arithmetic as O(1) is a cost-model assumption. `int`,
  `Fraction` or `Decimal` components are accepted by some functions and cost
  more per operation; they are not measured.
* The palette and batch examples' n conversions are read from their own
  loops; calls are not counted.
* The [0, 1] component convention, and I and Q ranging a little wider, are
  the module's documented contract; only the YIQ sign is observed.
"""

from __future__ import annotations

import colorsys
import itertools
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "colorsys.md"
EXPECTED_BLOCKS = 5

FUNCTIONS: list[Callable[[float, float, float], tuple[float, float, float]]] = [
    colorsys.rgb_to_yiq,
    colorsys.yiq_to_rgb,
    colorsys.rgb_to_hls,
    colorsys.hls_to_rgb,
    colorsys.rgb_to_hsv,
    colorsys.hsv_to_rgb,
]


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def close(got: tuple[float, ...], expected: tuple[float, ...]) -> bool:
    return all(math.isclose(x, y, abs_tol=1e-12) for x, y in zip(got, expected, strict=True))


GRID = [i / 5 for i in range(6)]
COLOURS = list(itertools.product(GRID, repeat=3))


class TestEveryConversionIsConstant:
    """Every row is O(1) time and space: one fixed computation per colour,
    returning a fresh 3-tuple."""

    @pytest.mark.parametrize("func", FUNCTIONS, ids=lambda f: f.__name__)
    def test_a_call_peaks_under_4_kb(
        self, func: Callable[[float, float, float], tuple[float, float, float]]
    ) -> None:
        func(0.2, 0.4, 0.6)
        peak = peak_bytes(lambda: func(0.2, 0.4, 0.6))
        assert peak < 4096, f"{func.__name__} peaked at {peak} bytes"

    @pytest.mark.parametrize("func", FUNCTIONS, ids=lambda f: f.__name__)
    def test_nothing_is_cached(
        self, func: Callable[[float, float, float], tuple[float, float, float]]
    ) -> None:
        first = func(0.2, 0.4, 0.6)
        second = func(0.2, 0.4, 0.6)
        assert isinstance(first, tuple) and len(first) == 3
        assert first == second
        assert first is not second

    def test_there_is_no_batch_form(self) -> None:
        assert set(colorsys.__all__) == {f.__name__ for f in FUNCTIONS}


class TestYiqClamping:
    """`yiq_to_rgb()` clamps each channel to [0, 1], so an out-of-gamut YIQ
    colour does not round-trip; `rgb_to_yiq()` does not clamp."""

    def test_an_out_of_gamut_colour_is_clamped(self) -> None:
        rgb = colorsys.yiq_to_rgb(0.5, 0.6, 0.0)
        assert all(0.0 <= x <= 1.0 for x in rgb)
        assert rgb[0] == 1.0 and rgb[2] == 0.0

    def test_a_clamped_colour_does_not_round_trip(self) -> None:
        yiq = (0.5, 0.6, 0.0)
        back = colorsys.rgb_to_yiq(*colorsys.yiq_to_rgb(*yiq))
        assert not close(back, yiq)

    def test_rgb_to_yiq_does_not_clamp(self) -> None:
        assert colorsys.rgb_to_yiq(0.0, 0.0, 1.0)[1] < 0


class TestGreysHaveNoHue:
    """`rgb_to_hls()` and `rgb_to_hsv()` return hue and saturation 0.0 for a
    grey."""

    @pytest.mark.parametrize("level", GRID)
    def test_hls(self, level: float) -> None:
        hue, light, saturation = colorsys.rgb_to_hls(level, level, level)
        assert (hue, saturation) == (0.0, 0.0)
        assert math.isclose(light, level)

    @pytest.mark.parametrize("level", GRID)
    def test_hsv(self, level: float) -> None:
        assert colorsys.rgb_to_hsv(level, level, level) == (0.0, 0.0, level)


class TestHueWrapping:
    """`hls_to_rgb()` wraps hue modulo 1, negative values included;
    `hsv_to_rgb()` wraps above 1 but can return a channel outside [0, 1] for a
    negative hue, which `% 1.0` corrects."""

    @pytest.mark.parametrize("hue", [0.1, 0.4, 0.9])
    def test_hls_wraps_both_ways(self, hue: float) -> None:
        expected = colorsys.hls_to_rgb(hue, 0.5, 1.0)
        for shifted in (hue + 1.0, hue - 1.0):
            got = colorsys.hls_to_rgb(shifted, 0.5, 1.0)
            assert close(got, expected)

    @pytest.mark.parametrize("hue", [0.1, 0.4, 0.9])
    def test_hsv_wraps_above_one(self, hue: float) -> None:
        expected = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        got = colorsys.hsv_to_rgb(hue + 1.0, 1.0, 1.0)
        assert close(got, expected)

    def test_hsv_does_not_wrap_a_negative_hue(self) -> None:
        assert min(colorsys.hsv_to_rgb(-0.1, 1.0, 1.0)) < 0
        assert max(colorsys.hsv_to_rgb(-0.25, 1.0, 1.0)) > 1
        assert colorsys.hsv_to_rgb(-0.1 % 1.0, 1.0, 1.0) == colorsys.hsv_to_rgb(0.9, 1.0, 1.0)


class TestRoundTrips:
    """A round trip returns the same colour up to float rounding."""

    @pytest.mark.parametrize(
        ("there", "back"),
        [
            (colorsys.rgb_to_hls, colorsys.hls_to_rgb),
            (colorsys.rgb_to_hsv, colorsys.hsv_to_rgb),
        ],
        ids=["hls", "hsv"],
    )
    def test_round_trip_is_close(
        self,
        there: Callable[[float, float, float], tuple[float, float, float]],
        back: Callable[[float, float, float], tuple[float, float, float]],
    ) -> None:
        for rgb in COLOURS:
            got = back(*there(*rgb))
            assert close(got, rgb), rgb

    def test_equality_is_too_strict_for_a_round_trip(self) -> None:
        rgb = (0.0, 15 / 255, 45 / 255)
        for there, back in [
            (colorsys.rgb_to_hls, colorsys.hls_to_rgb),
            (colorsys.rgb_to_hsv, colorsys.hsv_to_rgb),
        ]:
            got = back(*there(*rgb))
            assert got != rgb
            assert close(got, rgb)

    def test_a_component_near_zero_needs_an_absolute_tolerance(self) -> None:
        rgb = (1e-20, 0.5, 1.0)
        got = colorsys.hsv_to_rgb(*colorsys.rgb_to_hsv(*rgb))
        assert not math.isclose(got[0], rgb[0])
        assert math.isclose(got[0], rgb[0], abs_tol=1e-12)


class TestNothingIsValidated:
    """0-255 components passed to an `rgb_to_*` function give a wrong result or
    raise."""

    def test_rgb_to_hsv_accepts_0_to_255(self) -> None:
        assert colorsys.rgb_to_hsv(255, 100, 50)[2] == 255

    def test_rgb_to_hls_accepts_0_to_255(self) -> None:
        assert colorsys.rgb_to_hls(255, 100, 50)[1] > 1

    def test_rgb_to_hls_can_divide_by_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            colorsys.rgb_to_hls(2, 1, 0)


class TestNormalisedCopyCostsLinearMemory:
    """Building a normalised copy of n colours before converting them costs
    O(n) memory beyond scaling each colour inline."""

    @staticmethod
    def _extra(n: int) -> int:
        rng = random.Random(n)
        colors = [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(n)]

        def inline() -> None:
            [colorsys.rgb_to_hsv(r / 255, g / 255, b / 255) for r, g, b in colors]

        def copied() -> None:
            normalized = [(r / 255, g / 255, b / 255) for r, g, b in colors]
            [colorsys.rgb_to_hsv(r, g, b) for r, g, b in normalized]

        return peak_bytes(copied) - peak_bytes(inline)

    def test_the_extra_peak_grows_with_n(self) -> None:
        small = self._extra(2_000)
        large = self._extra(200_000)
        assert small > 0
        assert large / small > 20, f"extra peak {small} at 2,000, {large} at 200,000"


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
        line, source = next((n, s) for n, s in _blocks() if "colors[1] == (50, 205, 255)" in s)
        mutated = source.replace("colors[1] == (50, 205, 255)", "colors[1] == (49, 204, 255)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
