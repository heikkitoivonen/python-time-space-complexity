"""Tests for docs/stdlib/audioop.md.

The page prices every function by the bytes in its fragment: C loops that
read the buffer in place and return numbers or new `bytes` objects, linear
in the fragment except for `getsample()` (O(1)), `findfit()`
(O((n - m + 1)·m)) and `ratecv()` (O(n + o)). The module exists on
Python 3.10, 3.11 and 3.12 only, so every runtime test takes the `audioop`
fixture, which skips from 3.13; run them with one of those interpreters. CI's
timing jobs run on every supported version, so the timing tests below run there
on 3.10 to 3.12; its full-suite jobs use the newest Python, where only the
availability tests run. Modules/audioop.c differs between v3.10.19, v3.11.14
and v3.12.12 only in the import-time DeprecationWarning (3.11), shift
expressions rewritten as multiplications and added assertions (3.12): no bound
moves. Sizes and space are settled by observation - output lengths and a
`tracemalloc` peak - and growth classes by timing ratios.

Measurement scope:

* The seven analysis functions, over a 10 MB fragment held as `bytes`,
  `bytearray`, `memoryview` and `array.array`, each peak under 4 KB of traced
  allocation; a copy would be 10 MB. `mul()` and `reverse()` over the same
  fragment peak under 1.5 times its length. Every other O(n) row, over a
  4 MB `bytearray`, peaks under its output's length (twice it for `ratecv()`,
  which copies its rounded-up buffer) plus 1 MB, so the input is not copied.
  `max`, `minmax`, `avg`, `rms`, `cross`, `avgpp`, `maxpp` and `getsample`
  match a hand computation on a small fragment. A strided `memoryview` raises
  `BufferError`.
* Every O(n) function is timed at 48,000, 480,000 and 4,800,000 bytes; each
  10x step costs between 3x and 30x (linear predicts 10x, quadratic 100x).
  `getsample()` on 4,800,000 bytes costs under 3 times what it does on 48.
* `findmax()` on 200,000 samples costs under 3 times as much with a window of
  100,000 samples as with one of 10; a per-window rescan predicts 10,000x.
  `findfit()` on 20,000 samples costs over 20 times more with a 2,000-sample
  reference than a 20-sample one ((n - m + 1)·m predicts 90x, linear 1x), and
  over 20 times more with a 10,000-sample reference than a 19,990-sample one
  (predicts 450x), so both factors are real.
* Output lengths are asserted exactly for every width from 1 to 4: n for
  `add`, `mul`, `bias`, `reverse` and `byteswap`; n/2 for `tomono`; 2n for
  `tostereo`; n·newwidth/width for `lin2lin`; n/width for `lin2ulaw` and
  `lin2alaw`; n·width for `ulaw2lin` and `alaw2lin`; n/(2·width), rounded
  down at three samples, for `lin2adpcm`; 2·n·width for `adpcm2lin`.
* `ratecv()` returns n·outrate/inrate bytes, give or take outrate/inrate + 2
  frames (upsampling stops at the last input frame), for six rate pairs, and at
  a fixed 4,000-byte input each 10x step of outrate (10, 100 and 1,000 times
  inrate) costs between 3x and 30x. Fed in chunks with its state threaded
  through, `ratecv()` (44,100 to 8,000 Hz in 1,000-frame chunks; the page's
  example uses 441-frame chunks), `lin2adpcm()` and `adpcm2lin()` produce the
  bytes one call does; other rates, chunk sizes and channel counts are not
  varied. Two 1-sample `lin2adpcm()` chunks give no bytes where one
  2-sample call gives one: an odd chunk's half byte is not in the state. One
  2-byte frame at 1,000,003 to 1,000,000 Hz peaks over 1.9 MB of traced
  allocation, and under 2.1 MB, for 2 bytes of output, while 1,024 frames at 44,100 to 48,000
  peak under 3 times the output plus 1 KB.
* `add()` and `mul()` clip at the width's limits and `bias()` wraps, at every
  width; `byteswap()` and `reverse()` are checked on a 3-byte-sample
  fragment. `audioop.error` is raised for a width of 5, an odd-length
  fragment passed to `findfit()`, `findfactor()` or `findmax()`, a partial sample,
  `add()` and `findfactor()` on unequal lengths, `findfit()` with the longer
  reference, `findmax()` with a window longer than the fragment, and
  `getsample()` past the end; it subclasses `Exception`.
* The import warns on 3.11 and 3.12, not on 3.10, and raises
  `ModuleNotFoundError` from 3.13.
* Every fenced Python block runs in its own subprocess on 3.10 to 3.12.

Not settled here:

* The deprecation in 3.11 and the removal in 3.13 come from the 3.12
  documentation and PEP 594.
* The O(n + o) time and O(o) space of `ratecv()` are read from
  Modules/audioop.c: it writes each output frame once, allocates
  ceil(frames/inrate')·outrate' frames (rates divided by their gcd), and
  copies the o bytes written into the result. The transient that rounding
  causes is measured above for one pair of coprime rates; other pairs and
  channel counts are not varied. The time tests use one channel.
* Only random 16-bit content is timed; the analysis loops have no
  data-dependent branch that changes their pass count, which is read from
  source, and other widths are not timed.
"""

from __future__ import annotations

import array
import gc
import importlib
import importlib.util
import math
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "audioop.md"
EXPECTED_BLOCKS = 6
WIDTHS = (1, 2, 3, 4)


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = float(time.perf_counter_ns() - start)
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, with the collector held off."""
    func()
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        if was_enabled:
            gc.enable()


# Every O(n) row, called on a 16-bit fragment f.
LINEAR_CALLS: dict[str, Callable[[Any, Any], Any]] = {
    "max": lambda a, f: a.max(f, 2),
    "minmax": lambda a, f: a.minmax(f, 2),
    "avg": lambda a, f: a.avg(f, 2),
    "rms": lambda a, f: a.rms(f, 2),
    "cross": lambda a, f: a.cross(f, 2),
    "avgpp": lambda a, f: a.avgpp(f, 2),
    "maxpp": lambda a, f: a.maxpp(f, 2),
    "add": lambda a, f: a.add(f, f, 2),
    "mul": lambda a, f: a.mul(f, 2, 0.5),
    "bias": lambda a, f: a.bias(f, 2, 3),
    "reverse": lambda a, f: a.reverse(f, 2),
    "byteswap": lambda a, f: a.byteswap(f, 2),
    "tomono": lambda a, f: a.tomono(f, 2, 0.5, 0.5),
    "tostereo": lambda a, f: a.tostereo(f, 2, 1, 1),
    "lin2lin": lambda a, f: a.lin2lin(f, 2, 4),
    "ratecv": lambda a, f: a.ratecv(f, 2, 1, 44100, 22050, None),
    "lin2ulaw": lambda a, f: a.lin2ulaw(f, 2),
    "ulaw2lin": lambda a, f: a.ulaw2lin(f, 2),
    "lin2alaw": lambda a, f: a.lin2alaw(f, 2),
    "alaw2lin": lambda a, f: a.alaw2lin(f, 2),
    "lin2adpcm": lambda a, f: a.lin2adpcm(f, 2, None),
    "adpcm2lin": lambda a, f: a.adpcm2lin(f, 2, None),
    "findfactor": lambda a, f: a.findfactor(f, f),
    "findmax": lambda a, f: a.findmax(f, 100),
}


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("audioop") is not None) == (sys.version_info < (3, 13))


@pytest.fixture
def audioop() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: audioop was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("audioop")


def _samples(values: list[int]) -> bytes:
    return array.array("h", values).tobytes()


class TestAvailability:
    """`import audioop` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("audioop")

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="audioop was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import audioop"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11)), result.stderr
        if sys.version_info >= (3, 11):
            assert "DeprecationWarning" in result.stderr
            assert "audioop" in result.stderr


class TestAnalysisReadsInPlace:
    """Analysis rows: O(n) time, O(1) space. The fragment is read through the
    buffer protocol, so no kind of buffer is copied; a copy would show as a
    10 MB peak."""

    NAMES = ("max", "minmax", "avg", "rms", "cross", "avgpp", "maxpp")

    @pytest.mark.parametrize("kind", ["bytes", "bytearray", "memoryview", "array"])
    @pytest.mark.parametrize("name", NAMES)
    def test_a_10_mb_fragment_is_not_copied(self, audioop: Any, name: str, kind: str) -> None:
        raw = os.urandom(10_000_000)
        fragment: Any = {
            "bytes": raw,
            "bytearray": bytearray(raw),
            "memoryview": memoryview(raw),
            "array": array.array("h", raw),
        }[kind]
        func = getattr(audioop, name)
        peak = peak_bytes(lambda: func(fragment, 2))
        assert peak < 4_000, f"{name} on {kind}: peak {peak} bytes"

    def test_the_results_match_a_python_computation(self, audioop: Any) -> None:
        values = [0, 1000, -3000, 2000, -500, 0, 7, -7]
        fragment = _samples(values)
        assert audioop.max(fragment, 2) == max(abs(v) for v in values)
        assert audioop.minmax(fragment, 2) == (min(values), max(values))
        assert audioop.avg(fragment, 2) == math.floor(sum(values) / len(values))
        rms = int(math.sqrt(sum(v * v for v in values) / len(values)))
        assert audioop.rms(fragment, 2) == rms
        signs = [v < 0 for v in values]
        assert audioop.cross(fragment, 2) == sum(a != b for a, b in pairwise(signs))
        assert audioop.getsample(fragment, 2, 2) == -3000

    def test_peak_to_peak_measures_successive_extremes(self, audioop: Any) -> None:
        fragment = _samples([0, 10, 0, 30, 0])  # extremes 10, 0, 30
        assert audioop.avgpp(fragment, 2) == 20
        assert audioop.maxpp(fragment, 2) == 30

    def test_a_strided_view_is_rejected(self, audioop: Any) -> None:
        with pytest.raises(BufferError):
            audioop.max(memoryview(bytes(8))[::2], 1)

    def test_getsample_past_the_end_raises(self, audioop: Any) -> None:
        with pytest.raises(audioop.error, match="out of range"):
            audioop.getsample(_samples([1, 2]), 2, 2)


class TestNoFunctionCopiesItsInput:
    """Every O(n) row reads its input in place: the peak is the output alone
    (two of it for `ratecv()`), where a copy would add the input's 4 MB."""

    N = 4_000_000

    @pytest.mark.parametrize("name", sorted(LINEAR_CALLS))
    def test_the_peak_is_the_output(self, audioop: Any, name: str) -> None:
        fragment = bytearray(os.urandom(self.N))
        call = LINEAR_CALLS[name]
        result = call(audioop, fragment)
        data = result[0] if isinstance(result, tuple) else result
        out = len(data) if isinstance(data, bytes) else 0
        copies = 2 if name == "ratecv" else 1
        peak = peak_bytes(lambda: call(audioop, fragment))
        assert peak < copies * out + 1_000_000, f"{name}: peak {peak}, output {out}"


class TestTransformationsAllocateOnlyTheirOutput:
    """Transformation rows: O(n) space is the returned fragment alone."""

    @pytest.mark.parametrize("name", ["mul", "reverse"])
    def test_the_peak_is_one_output(self, audioop: Any, name: str) -> None:
        fragment = bytearray(os.urandom(10_000_000))
        call: dict[str, Callable[[], Any]] = {
            "mul": lambda: audioop.mul(fragment, 2, 0.5),
            "reverse": lambda: audioop.reverse(fragment, 2),
        }
        peak = peak_bytes(call[name])
        assert len(fragment) <= peak < 1.5 * len(fragment), f"{name}: peak {peak}"


class TestOutputSizes:
    """The Notes column's output lengths, at every width."""

    N = 48

    @pytest.mark.parametrize("width", WIDTHS)
    def test_same_length_outputs(self, audioop: Any, width: int) -> None:
        f = os.urandom(self.N)
        assert len(audioop.add(f, f, width)) == self.N
        assert len(audioop.mul(f, width, 0.5)) == self.N
        assert len(audioop.bias(f, width, 3)) == self.N
        assert len(audioop.reverse(f, width)) == self.N
        assert len(audioop.byteswap(f, width)) == self.N

    @pytest.mark.parametrize("width", WIDTHS)
    def test_channel_changes(self, audioop: Any, width: int) -> None:
        f = os.urandom(self.N)
        assert len(audioop.tomono(f, width, 0.5, 0.5)) == self.N // 2
        assert len(audioop.tostereo(f, width, 1, 1)) == 2 * self.N

    @pytest.mark.parametrize("newwidth", WIDTHS)
    @pytest.mark.parametrize("width", WIDTHS)
    def test_lin2lin(self, audioop: Any, width: int, newwidth: int) -> None:
        f = os.urandom(self.N)
        assert len(audioop.lin2lin(f, width, newwidth)) == self.N * newwidth // width

    @pytest.mark.parametrize("width", WIDTHS)
    def test_codecs(self, audioop: Any, width: int) -> None:
        f = os.urandom(self.N)
        assert len(audioop.lin2ulaw(f, width)) == self.N // width
        assert len(audioop.lin2alaw(f, width)) == self.N // width
        assert len(audioop.ulaw2lin(f, width)) == self.N * width
        assert len(audioop.alaw2lin(f, width)) == self.N * width
        encoded, state = audioop.lin2adpcm(f, width, None)
        assert len(encoded) == self.N // (2 * width)
        assert isinstance(state, tuple)
        odd, _ = audioop.lin2adpcm(os.urandom(3 * width), width, None)
        assert len(odd) == 1  # three samples: n/(2·width) rounded down
        decoded, _ = audioop.adpcm2lin(f, width, None)
        assert len(decoded) == 2 * self.N * width


class TestOverflow:
    """`add()` and `mul()` clip; `bias()` wraps around."""

    @pytest.mark.parametrize("width", WIDTHS)
    def test_add_and_mul_clip_bias_wraps(self, audioop: Any, width: int) -> None:
        top = 2 ** (8 * width - 1) - 1
        bottom = -(2 ** (8 * width - 1))
        high = top.to_bytes(width, sys.byteorder, signed=True)
        low = bottom.to_bytes(width, sys.byteorder, signed=True)

        assert audioop.getsample(audioop.add(high, high, width), width, 0) == top
        assert audioop.getsample(audioop.add(low, low, width), width, 0) == bottom
        assert audioop.getsample(audioop.mul(high, width, 3.0), width, 0) == top
        assert audioop.getsample(audioop.bias(high, width, 1), width, 0) == bottom

    def test_byteswap_and_reverse(self, audioop: Any) -> None:
        fragment = bytes([1, 2, 3, 4, 5, 6])
        assert audioop.byteswap(fragment, 3) == bytes([3, 2, 1, 6, 5, 4])
        assert audioop.reverse(fragment, 3) == bytes([4, 5, 6, 1, 2, 3])


class TestErrors:
    """`audioop.error` covers bad widths, partial samples and mismatched
    lengths."""

    def test_it_is_an_exception(self, audioop: Any) -> None:
        assert issubclass(audioop.error, Exception)

    def test_the_documented_causes(self, audioop: Any) -> None:
        two = _samples([1, 2])
        with pytest.raises(audioop.error):
            audioop.max(b"\0" * 10, 5)
        with pytest.raises(audioop.error, match="whole number"):
            audioop.max(b"\0" * 3, 2)
        with pytest.raises(audioop.error, match="same"):
            audioop.add(two, two + two, 2)
        with pytest.raises(audioop.error, match="same size"):
            audioop.findfactor(two, two + two)
        with pytest.raises(audioop.error, match="longer"):
            audioop.findfit(two, two + two)
        with pytest.raises(audioop.error, match="longer"):
            audioop.findmax(two, 3)

    def test_the_search_functions_take_16_bit_samples_only(self, audioop: Any) -> None:
        odd = b"\0" * 5
        with pytest.raises(audioop.error, match="even-sized"):
            audioop.findfit(odd + odd, odd)
        with pytest.raises(audioop.error, match="even-sized"):
            audioop.findfactor(odd, odd)
        with pytest.raises(audioop.error, match="even-sized"):
            audioop.findmax(odd, 1)


@pytest.mark.timing
class TestLinearRowsAreLinear:
    """Every O(n) row: three sizes in 10x steps, each step between 3x and 30x.
    `getsample()` is O(1): its cost does not follow the fragment."""

    SIZES = (48_000, 480_000, 4_800_000)

    @pytest.mark.parametrize("name", sorted(LINEAR_CALLS))
    def test_each_10x_step_costs_about_10x(self, audioop: Any, name: str) -> None:
        call = LINEAR_CALLS[name]
        raw = os.urandom(self.SIZES[-1])
        times = [best_ns(lambda f=raw[:size]: call(audioop, f)) for size in self.SIZES]
        ratios = [later / earlier for earlier, later in pairwise(times)]
        assert all(3 < ratio < 30 for ratio in ratios), f"{name}: {ratios}"

    def test_getsample_does_not_follow_the_fragment(self, audioop: Any) -> None:
        small = os.urandom(48)
        large = os.urandom(4_800_000)

        def many(fragment: bytes) -> Callable[[], None]:
            def run() -> None:
                for index in range(1_000):
                    audioop.getsample(fragment, 2, index % 24)

            return run

        ratio = best_ns(many(large)) / best_ns(many(small))
        assert ratio < 3, ratio


@pytest.mark.timing
class TestSearchCosts:
    """`findmax()` is O(n) whatever the window; `findfit()` is
    O((n - m + 1)·m), separated from O(n) by growing m, and from O(n·m) by
    letting m approach n."""

    def test_findmax_ignores_the_window_length(self, audioop: Any) -> None:
        fragment = os.urandom(400_000)
        short = best_ns(lambda: audioop.findmax(fragment, 10))
        long = best_ns(lambda: audioop.findmax(fragment, 100_000))
        assert long / short < 3, (short, long)

    def test_findfit_grows_with_the_reference(self, audioop: Any) -> None:
        fragment = os.urandom(40_000)
        small = best_ns(lambda: audioop.findfit(fragment, fragment[:40]), repeats=3)
        large = best_ns(lambda: audioop.findfit(fragment, fragment[:4_000]), repeats=3)
        assert large / small > 20, (small, large)

    def test_findfit_is_cheap_when_few_offsets_remain(self, audioop: Any) -> None:
        fragment = os.urandom(40_000)
        half = best_ns(lambda: audioop.findfit(fragment, fragment[:20_000]), repeats=3)
        nearly_all = best_ns(lambda: audioop.findfit(fragment, fragment[:39_980]), repeats=3)
        assert half / nearly_all > 20, (half, nearly_all)


class TestSearchResults:
    def test_findfit_returns_offset_and_factor(self, audioop: Any) -> None:
        quiet = [i * 7 % 21 - 10 for i in range(100)]
        loud = [3000, 1000, -2000, -500, 2500, -3000, 100, 0, -1500, 1200]
        fragment = _samples(quiet + loud + quiet)
        offset, factor = audioop.findfit(fragment, _samples(loud))
        assert offset == 100
        assert factor == pytest.approx(1.0)
        assert audioop.findmax(fragment, 10) == 100


class TestRatecv:
    """`ratecv()`: o is about n·outrate/inrate, time O(n + o), and the state
    makes chunked output equal one call."""

    @pytest.mark.parametrize(
        ("inrate", "outrate"),
        [(44100, 8000), (8000, 44100), (44100, 48000), (48000, 44100), (8000, 80000), (3, 1)],
    )
    def test_the_output_follows_the_rate_ratio(
        self, audioop: Any, inrate: int, outrate: int
    ) -> None:
        fragment = os.urandom(2 * 30_000)
        data, _ = audioop.ratecv(fragment, 2, 1, inrate, outrate, None)
        expected = len(fragment) * outrate / inrate
        # Upsampling stops at the last input frame, short of one interval
        slack = 2 * (outrate // inrate + 2)
        assert abs(len(data) - expected) <= slack, (len(data), expected)

    def test_chunks_with_state_equal_one_call(self, audioop: Any) -> None:
        signal = os.urandom(2 * 9_000)
        whole, _ = audioop.ratecv(signal, 2, 1, 44100, 8000, None)
        state = None
        pieces = []
        for start in range(0, len(signal), 2_000):
            piece, state = audioop.ratecv(signal[start : start + 2_000], 2, 1, 44100, 8000, state)
            pieces.append(piece)
        assert b"".join(pieces) == whole

    def test_adpcm_chunks_with_state_equal_one_call(self, audioop: Any) -> None:
        signal = os.urandom(2 * 9_000)
        whole, _ = audioop.lin2adpcm(signal, 2, None)
        state = None
        pieces = []
        for start in range(0, len(signal), 2_000):
            piece, state = audioop.lin2adpcm(signal[start : start + 2_000], 2, state)
            pieces.append(piece)
        assert b"".join(pieces) == whole

    def test_adpcm2lin_chunks_with_state_equal_one_call(self, audioop: Any) -> None:
        encoded = os.urandom(4_500)
        whole, _ = audioop.adpcm2lin(encoded, 2, None)
        state = None
        pieces = []
        for start in range(0, len(encoded), 500):
            piece, state = audioop.adpcm2lin(encoded[start : start + 500], 2, state)
            pieces.append(piece)
        assert b"".join(pieces) == whole

    def test_an_odd_adpcm_chunk_drops_its_last_half_byte(self, audioop: Any) -> None:
        whole, _ = audioop.lin2adpcm(b"\0\0\0\0", 2, None)
        first, state = audioop.lin2adpcm(b"\0\0", 2, None)
        second, _ = audioop.lin2adpcm(b"\0\0", 2, state)
        assert len(whole) == 1
        assert first + second == b""

    def test_coprime_rates_round_the_buffer_up(self, audioop: Any) -> None:
        peak = peak_bytes(lambda: audioop.ratecv(b"\0\0", 2, 1, 1_000_003, 1_000_000, None))
        assert 1_900_000 < peak < 2_100_000, peak

    def test_standard_rates_allocate_about_the_output(self, audioop: Any) -> None:
        chunk = os.urandom(2 * 1_024)
        out, _ = audioop.ratecv(chunk, 2, 1, 44100, 48000, None)
        peak = peak_bytes(lambda: audioop.ratecv(chunk, 2, 1, 44100, 48000, None))
        assert peak < 3 * len(out) + 1_000, (peak, len(out))

    @pytest.mark.timing
    def test_time_follows_the_output(self, audioop: Any) -> None:
        fragment = os.urandom(4_000)
        times = [
            best_ns(lambda r=ratio: audioop.ratecv(fragment, 2, 1, 1_000, 1_000 * r, None))
            for ratio in (10, 100, 1_000)
        ]
        ratios = [later / earlier for earlier, later in pairwise(times)]
        assert all(3 < ratio < 30 for ratio in ratios), ratios


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
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result, on
    the versions that still have the module."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import audioop" in source for _, source in blocks)

    def test_every_block_runs(self, audioop: Any, tmp_path: pathlib.Path) -> None:
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

    def test_the_runner_notices_a_broken_assertion(
        self, audioop: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "== 1541" in s)
        mutated = source.replace("== 1541", "== 1540", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
