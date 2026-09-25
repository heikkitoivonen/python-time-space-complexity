"""Tests for docs/stdlib/statistics.md.

The page separates the functions that stream through their input holding
running sums from those that keep a copy or a count as large as the data.
Which kind a function is gets settled by traced allocation over a generator,
which separates the two by orders of magnitude and needs no tolerance,
together with the result over the generator matching the result over a
list, which a second pass over the spent generator could not give. Sorting
costs are settled by counting comparisons on a float subclass, which
separates an already-sorted input from a shuffled one exactly. Timing is used
only where neither can see the claim: linear growth of the exact averages,
`mean()` against `fmean()`, and per-call cost of a kernel density estimate.

Measurement scope:

* `mean()`, `fmean()`, `geometric_mean()`, `variance()`, `pvariance()`,
  `stdev()`, `pstdev()` and `NormalDist.from_samples()` over a generator of
  200,000 floats return what they return for the list, and peak under
  64 KB on 3.11+, against over 1.6 MB for
  `median()` of the same generator. On 3.10 the six that copy an iterator
  (`mean()`, the variance family and `from_samples()`) are asserted to peak
  over 1.6 MB instead. `harmonic_mean()` peaks under 64 KB over a list and
  over 1.6 MB over a generator, and likewise for a list and a generator of
  weights; `fmean()` with a generator of weights peaks over 1.6 MB and with
  a list of weights under 64 KB (3.11+). Sized weights that are neither a
  list nor a tuple, such as a `range`, are copied on 3.12+ and not on 3.11;
  the page claims only the iterator case, and the sized case is not
  asserted. `mean()`, `variance()` and `pvariance()` are asserted to return
  a `Fraction` for `Fraction` data and a `Decimal` for `Decimal` data.
* `mean()` and `variance()` are timed at 10,000, 40,000 and 160,000 floats;
  each 4x step is asserted under 8x, which a quadratic's 16x would exceed.
  `mean()` of 100,000 floats is asserted over 3x `fmean()`.
* `median()`, `median_low()`, `median_high()`, `median_grouped()` and
  `quantiles()` are given 10,001 values of a float subclass that counts
  `__lt__`: already sorted, each makes at most 10,001 + 64 comparisons (the
  sort's single scan plus `median_grouped()`'s two binary searches); shuffled,
  each makes over 100,000. Each also peaks over 80 KB when handed a sorted
  list, so the copy is made regardless. `quantiles(n=q)` returns q - 1 cut
  points; with one data point it returns q - 1 copies on 3.13+ and raises
  `StatisticsError` before.
* `mode()` and `multimode()` over 100,000 values peak more than 20x higher
  with 100,000 distinct values than with 10. Ties are asserted to resolve to
  the first value seen. `multimode()` is observed to call
  `Counter.most_common()` with no argument on 3.10, which sorts every
  count, and not at all on 3.11+.
* `covariance()` over two lists of 100,000 floats peaks under 64 KB;
  `correlation()` and `linear_regression()` peak over 1.6 MB on 3.12+ and
  under 64 KB on 3.10 and 3.11; `linear_regression(proportional=True)` peaks
  under 64 KB. Iterators are asserted to raise `TypeError`. The ranked
  correlation (3.12+) is asserted to make over 100,000 comparisons on 10,000
  shuffled values.
* `kde()` (3.13+) over 100,000 floats peaks under 16 KB with the normal
  kernel and over 800 KB with the triangular one. A call to the normal-kernel
  estimate costs over 30x more at 100,000 points than at 1,000; a call to the
  triangular estimate on evenly spaced points with a bandwidth covering two
  of them costs under 5x more. On 10,001 shuffled values of the counting
  float subclass, building a triangular estimate makes over 100,000
  comparisons, a call under 100, the first call after an append over
  100,000 again, and building a normal one none. A bounded-kernel estimate
  sees an appended point and does not see a same-length replacement; a
  normal-kernel estimate and a `kde_random()` result see an in-place change
  to `data`. `kde_random()` peaks under 16 KB to build over 100,000 points,
  each draw lies within `h` of a data point for the rectangular kernel, and
  a draw costs under 5x more at 100,000 points than at 1,000.
* `NormalDist` has two slots and no `__dict__`; `samples(s)` returns s
  floats and its peak grows more than 50x from s = 1,000 to s = 100,000;
  `quantiles(q)` returns q - 1 values. The O(1) methods, properties and
  operators are asserted by their results.
* Every fenced Python block runs in its own subprocess; the ranked
  correlation block needs 3.12 and the kde block 3.13. A mutated assertion in
  one block is asserted to fail.

Not settled here:

* Treating arithmetic, comparison and hashing of one value as O(1) is the
  page's cost model. It holds for floats and machine-size ints; exact
  `Fraction` and `Decimal` values and very large ints are not varied.
* The O(1) space of the exact-arithmetic functions is the partial sums keyed
  by denominator in Lib/statistics.py's `_sum()` and `_ss()`. Floats have a
  bounded set of power-of-two denominators, which is what the allocation
  measurements exercise; data with many distinct denominators is not varied.
* `kde_random()` draws for the quartic and triweight kernels solve for the
  inverse CDF by Newton-Raphson iteration; its iteration count is read as
  bounded from Lib/statistics.py and not measured.
* `NormalDist.inv_cdf()` is a fixed rational approximation (Wichura AS241),
  read from source; its O(1) is not timed.
* Input order is varied only for the sorting functions; the streaming
  functions are measured on random floats in one order.
* The `mean()` and `variance()` growth tests bound growth from above: they
  exclude a quadratic, not a sublinear cost no correct implementation could
  have. The n log n of a shuffled sort is one size's comparison count, not a
  growth series.
* `mean()` against `fmean()` is timed on floats only.
* Bounded-kernel `kde()` calls are timed with w held at about two; growth in
  w and cumulative-estimate calls are not timed.
"""

from __future__ import annotations

import pathlib
import random
import re
import statistics
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import Counter
from collections.abc import Callable, Iterable
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "statistics.md"
EXPECTED_BLOCKS = 9
MINIMUM_VERSION = {
    "method='ranked'": (3, 12),
    "statistics.kde(": (3, 13),
}

SMALL = 64_000
LARGE = 1_600_000

# Typed as Any for the APIs newer than typeshed's 3.10 signatures; each use is
# guarded on sys.version_info.
NEWER: Any = statistics


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


def floats(count: int, seed: int = 1) -> list[float]:
    rng = random.Random(seed)
    return [rng.random() for _ in range(count)]


class CountingFloat(float):
    """A float whose `<` comparisons are counted."""

    comparisons = 0

    def __lt__(self, other: float) -> bool:
        CountingFloat.comparisons += 1
        return float.__lt__(self, other)


def comparisons_for(func: Callable[[list[CountingFloat]], Any], values: list[int]) -> int:
    data = [CountingFloat(v) for v in values]
    CountingFloat.comparisons = 0
    func(data)
    return CountingFloat.comparisons


STREAMING: dict[str, Callable[[Iterable[float]], Any]] = {
    "mean": statistics.mean,
    "fmean": statistics.fmean,
    "geometric_mean": statistics.geometric_mean,
    "variance": statistics.variance,
    "pvariance": statistics.pvariance,
    "stdev": statistics.stdev,
    "pstdev": statistics.pstdev,
    "from_samples": statistics.NormalDist.from_samples,
}
COPIED_ON_310 = {"mean", "variance", "pvariance", "stdev", "pstdev", "from_samples"}


class TestStreamingFunctionsHoldNoData:
    """The averages and the variance family | O(n) | O(1): one pass, running
    sums only. A generator of 200,000 floats separates O(1) from a copy by
    more than 25x."""

    DATA = floats(200_000)

    @pytest.mark.parametrize("name", sorted(STREAMING))
    def test_a_generator_is_not_copied(self, name: str) -> None:
        func = STREAMING[name]

        assert func(x for x in self.DATA) == func(self.DATA)
        peak = peak_bytes(lambda: func(x for x in self.DATA))

        if sys.version_info < (3, 11) and name in COPIED_ON_310:
            assert peak > LARGE, f"{name}() of a generator peaked at only {peak} bytes on 3.10"
        else:
            assert peak < SMALL, f"{name}() of a generator peaked at {peak} bytes"

    def test_the_median_of_the_same_generator_holds_it_all(self) -> None:
        peak = peak_bytes(lambda: statistics.median(x for x in self.DATA))

        assert peak > LARGE, f"median() of a generator peaked at only {peak} bytes"

    def test_harmonic_mean_copies_an_iterator_but_not_a_list(self) -> None:
        listed = peak_bytes(lambda: statistics.harmonic_mean(self.DATA))
        streamed = peak_bytes(lambda: statistics.harmonic_mean(x for x in self.DATA))

        assert listed < SMALL, f"harmonic_mean() of a list peaked at {listed} bytes"
        assert streamed > LARGE, f"harmonic_mean() of a generator peaked at {streamed} bytes"

    def test_harmonic_mean_copies_iterator_weights(self) -> None:
        weights = [1.0] * len(self.DATA)

        listed = peak_bytes(lambda: statistics.harmonic_mean(self.DATA, weights))
        streamed = peak_bytes(lambda: statistics.harmonic_mean(self.DATA, (w for w in weights)))

        assert listed < SMALL, f"harmonic_mean() with list weights peaked at {listed} bytes"
        assert streamed > LARGE, f"harmonic_mean() with generator weights peaked at {streamed}"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="fmean() weights are 3.11+")
    def test_fmean_copies_weights_that_are_not_a_list_or_tuple(self) -> None:
        weights = [1.0] * len(self.DATA)

        listed = peak_bytes(lambda: NEWER.fmean(self.DATA, weights))
        streamed = peak_bytes(lambda: NEWER.fmean(self.DATA, (w for w in weights)))

        assert listed < SMALL, f"fmean() with list weights peaked at {listed} bytes"
        assert streamed > LARGE, f"fmean() with generator weights peaked at {streamed} bytes"
        assert NEWER.fmean([10, 20], weights=[3, 1]) == 12.5


class TestExactArithmeticGrowsLinearly:
    """`mean()` and `variance()` | O(n): the exact arithmetic is per value.
    Three sizes in 4x steps; linear predicts 4x a step, quadratic 16x."""

    SIZES = (10_000, 40_000, 160_000)

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["mean", "variance"])
    def test_each_4x_step_costs_under_8x(self, name: str) -> None:
        func = getattr(statistics, name)
        datasets = [floats(size) for size in self.SIZES]

        times = [best_ns(lambda d=d: func(d), repeats=5) for d in datasets]

        for small, large in zip(times, times[1:], strict=False):
            assert large / small < 8, f"{name}(): 4x the data cost x{large / small:.1f}"


class TestExactAndFloatAverages:
    """`mean()` works in exact ratios and keeps the input's type; `fmean()`
    stays in floats and is the faster of the two."""

    @pytest.mark.parametrize("func", [statistics.mean, statistics.variance, statistics.pvariance])
    def test_fraction_and_decimal_data_keep_their_type(self, func: Callable[..., Any]) -> None:
        assert type(func([Fraction(1, 3), Fraction(2, 3), Fraction(2)])) is Fraction
        assert type(func([Decimal("0.5"), Decimal("1.5"), Decimal("4")])) is Decimal
        assert statistics.mean([Fraction(1, 3), Fraction(2, 3)]) == Fraction(1, 2)

    def test_fmean_always_returns_a_float(self) -> None:
        assert type(statistics.fmean([Fraction(1, 3), Fraction(2, 3)])) is float
        assert type(statistics.fmean([1, 2])) is float

    @pytest.mark.timing
    def test_mean_is_slower_than_fmean(self) -> None:
        data = floats(100_000)

        exact = best_ns(lambda: statistics.mean(data), repeats=5)
        fast = best_ns(lambda: statistics.fmean(data), repeats=5)

        assert exact > 3 * fast, f"mean() {exact:.0f}ns against fmean() {fast:.0f}ns"


SORTING: dict[str, Callable[[list[Any]], Any]] = {
    "median": statistics.median,
    "median_low": statistics.median_low,
    "median_high": statistics.median_high,
    "median_grouped": statistics.median_grouped,
    "quantiles": statistics.quantiles,
}


class TestSortingFunctionsHoldACopy:
    """The median family and `quantiles()` | O(n log n) | O(n), and O(n) time
    when the data is already sorted. Counting `<` on 10,001 values: a sorted
    input takes one scan, a shuffled one n log n."""

    COUNT = 10_001

    @pytest.mark.parametrize("name", sorted(SORTING))
    def test_sorted_input_takes_one_scan(self, name: str) -> None:
        count = comparisons_for(SORTING[name], list(range(self.COUNT)))

        assert count <= self.COUNT + 64, f"{name}() made {count} comparisons on sorted input"

    @pytest.mark.parametrize("name", sorted(SORTING))
    def test_shuffled_input_takes_n_log_n(self, name: str) -> None:
        values = random.Random(2).sample(range(self.COUNT), self.COUNT)

        count = comparisons_for(SORTING[name], values)

        assert count > 100_000, f"{name}() made only {count} comparisons on shuffled input"

    @pytest.mark.parametrize("name", sorted(SORTING))
    def test_a_sorted_list_is_still_copied(self, name: str) -> None:
        ordered = sorted(floats(self.COUNT))
        func = SORTING[name]

        peak = peak_bytes(lambda: func(ordered))

        assert peak > 80_000, f"{name}() of a sorted list peaked at only {peak} bytes"

    def test_quantiles_returns_q_minus_one_cut_points(self) -> None:
        data = list(range(100))
        assert len(statistics.quantiles(data, n=4)) == 3
        assert len(statistics.quantiles(data, n=1_000)) == 999
        assert len(statistics.quantiles(data, n=10, method="inclusive")) == 9

    def test_a_single_data_point(self) -> None:
        if sys.version_info >= (3, 13):
            assert statistics.quantiles([5], n=4) == [5, 5, 5]
        else:
            with pytest.raises(statistics.StatisticsError):
                statistics.quantiles([5], n=4)

    def test_the_medians(self) -> None:
        assert statistics.median([1, 2, 3, 4]) == 2.5
        assert statistics.median_low([1, 2, 3, 4]) == 2
        assert statistics.median_high([1, 2, 3, 4]) == 3
        assert statistics.median_grouped([1, 2, 2, 3, 4, 4, 4, 4, 4, 5]) == 3.7


class TestModeCountsDistinctValues:
    """`mode()` and `multimode()` | O(n) | O(u): memory follows the distinct
    values. 100,000 values with 10 distinct against 100,000 distinct."""

    COUNT = 100_000

    @pytest.mark.parametrize("func", [statistics.mode, statistics.multimode])
    def test_memory_follows_distinct_values(self, func: Callable[[list[int]], Any]) -> None:
        few = [i % 10 for i in range(self.COUNT)]
        many = list(range(self.COUNT))

        few_peak = peak_bytes(lambda: func(few))
        many_peak = peak_bytes(lambda: func(many))

        assert many_peak > 20 * few_peak, f"u=10 peaked at {few_peak}, u=n at {many_peak}"

    def test_a_tie_returns_the_first_value_seen(self) -> None:
        assert statistics.mode([2, 1, 1, 2]) == 2
        assert statistics.multimode([2, 1, 1, 2, 3]) == [2, 1]

    def test_multimode_sorts_the_counts_only_on_310(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[object] = []

        class RecordingCounter(Counter):
            def most_common(self, n: int | None = None) -> list[tuple[Any, int]]:
                calls.append(n)
                return super().most_common(n)

        monkeypatch.setattr(statistics, "Counter", RecordingCounter)

        assert statistics.multimode([1, 1, 2]) == [1]
        assert calls == ([None] if sys.version_info < (3, 11) else []), calls


class TestTwoInputFunctions:
    """`covariance()` | O(n) | O(1); `correlation()` and `linear_regression()`
    | O(n) | O(n) on 3.12+, where they hold centred copies; the ranked
    correlation sorts."""

    X = floats(100_000, seed=3)
    Y = floats(100_000, seed=4)

    def test_covariance_holds_nothing(self) -> None:
        peak = peak_bytes(lambda: statistics.covariance(self.X, self.Y))

        assert peak < SMALL, f"covariance() peaked at {peak} bytes"

    @pytest.mark.parametrize("name", ["correlation", "linear_regression"])
    def test_centred_copies_from_312(self, name: str) -> None:
        func = getattr(statistics, name)

        peak = peak_bytes(lambda: func(self.X, self.Y))

        if sys.version_info >= (3, 12):
            assert peak > LARGE, f"{name}() peaked at only {peak} bytes"
        else:
            assert peak < SMALL, f"{name}() peaked at {peak} bytes"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="proportional is 3.11+")
    def test_proportional_regression_holds_nothing(self) -> None:
        peak = peak_bytes(lambda: NEWER.linear_regression(self.X, self.Y, proportional=True))

        assert peak < SMALL, f"linear_regression(proportional=True) peaked at {peak} bytes"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="method='ranked' is 3.12+")
    def test_ranked_correlation_sorts(self) -> None:
        count = 10_000
        x = random.Random(5).sample(range(count), count)
        y = random.Random(6).sample(range(count), count)

        comparisons = comparisons_for(
            lambda data: NEWER.correlation(data, [CountingFloat(v) for v in y], method="ranked"),
            x,
        )

        assert comparisons > 100_000, f"ranked correlation made {comparisons} comparisons"

    @pytest.mark.parametrize(
        "func", [statistics.covariance, statistics.correlation, statistics.linear_regression]
    )
    def test_iterators_are_rejected(self, func: Callable[..., Any]) -> None:
        with pytest.raises(TypeError, match="len"):
            func(iter([1, 2, 3]), iter([1, 2, 4]))

    def test_linear_regression_returns_the_named_tuple(self) -> None:
        fit = statistics.linear_regression([1, 2, 3], [2, 4, 6])

        assert isinstance(fit, statistics.LinearRegression)
        assert (fit.slope, fit.intercept) == (2.0, 0.0)


@pytest.mark.skipif(sys.version_info < (3, 13), reason="kde() and kde_random() are 3.13+")
class TestKernelDensityEstimates:
    """`kde()` | O(1) to build with the normal, logistic and sigmoid kernels,
    O(n log n) and O(n) with a bounded one; a call is O(n) or O(log n + w)."""

    def test_building_with_the_normal_kernel_holds_nothing(self) -> None:
        data = floats(100_000)

        normal = peak_bytes(lambda: NEWER.kde(data, h=0.1))
        bounded = peak_bytes(lambda: NEWER.kde(data, h=0.1, kernel="triangular"))

        assert normal < 16_000, f"kde(normal) peaked at {normal} bytes"
        assert bounded > 800_000, f"kde(triangular) peaked at only {bounded} bytes"

    @pytest.mark.timing
    def test_a_normal_kernel_call_sums_every_point(self) -> None:
        small = NEWER.kde([float(i) for i in range(1_000)], h=1.0)
        large = NEWER.kde([float(i) for i in range(100_000)], h=1.0)

        ratio = best_ns(lambda: large(500.0), repeats=5) / best_ns(lambda: small(500.0), repeats=5)

        assert ratio > 30, f"100x the points cost x{ratio:.1f} per call"

    @pytest.mark.timing
    def test_a_bounded_kernel_call_sums_the_points_in_reach(self) -> None:
        small = NEWER.kde([float(i) for i in range(1_000)], h=1.0, kernel="triangular")
        large = NEWER.kde([float(i) for i in range(100_000)], h=1.0, kernel="triangular")

        ratio = best_ns(lambda: large(500.5), inner=200) / best_ns(lambda: small(500.5), inner=200)

        assert ratio < 5, f"100x the points cost x{ratio:.1f} per call at fixed w"

    def test_a_bounded_kernel_re_sorts_only_when_the_length_changes(self) -> None:
        data = [0.0, 1.0, 2.0]
        estimate = NEWER.kde(data, h=0.5, kernel="triangular")
        assert estimate(10.0) == 0.0

        data[0] = 10.0
        assert estimate(10.0) == 0.0  # same length: the sorted copy is kept

        data.append(10.0)
        assert estimate(10.0) > 0.0  # new length: sorted again

    def test_a_bounded_kernel_sorts_when_built_and_after_a_length_change(self) -> None:
        count = 10_001
        values = random.Random(7).sample(range(count), count)
        data = [CountingFloat(v) for v in values]

        CountingFloat.comparisons = 0
        estimate = NEWER.kde(data, h=1.0, kernel="triangular")
        built = CountingFloat.comparisons

        CountingFloat.comparisons = 0
        estimate(500.5)
        called = CountingFloat.comparisons

        data.append(CountingFloat(-1))
        CountingFloat.comparisons = 0
        estimate(500.5)
        resorted = CountingFloat.comparisons

        CountingFloat.comparisons = 0
        NEWER.kde(data, h=1.0)

        assert built > 100_000, f"building made only {built} comparisons"
        assert called < 100, f"a call made {called} comparisons"
        assert resorted > 100_000, f"a call after append made only {resorted} comparisons"
        assert CountingFloat.comparisons == 0, "building a normal-kernel estimate compared values"

    def test_a_normal_kernel_estimate_reads_data_by_reference(self) -> None:
        data = [0.0, 1.0, 2.0]
        estimate = NEWER.kde(data, h=0.5)
        before = estimate(10.0)

        data[0] = 10.0

        assert estimate(10.0) > before + 0.1

    def test_kde_random_reads_data_by_reference(self) -> None:
        data = [0.0, 1.0, 2.0]
        draw = NEWER.kde_random(data, h=0.1, kernel="rectangular", seed=1)

        data[:] = [1_000.0, 1_000.0, 1_000.0]

        assert all(abs(draw() - 1_000.0) <= 0.1 for _ in range(50))

    def test_building_kde_random_copies_nothing(self) -> None:
        data = floats(100_000)

        peak = peak_bytes(lambda: NEWER.kde_random(data, h=0.1))

        assert peak < 16_000, f"kde_random() peaked at {peak} bytes"

    def test_a_draw_is_a_data_point_plus_a_kernel_offset(self) -> None:
        data = [0.0, 100.0, 200.0]
        draw = NEWER.kde_random(data, h=1.0, kernel="rectangular", seed=1)

        for _ in range(200):
            value = draw()
            assert min(abs(value - point) for point in data) <= 1.0, value

    @pytest.mark.timing
    def test_a_draw_does_not_grow_with_the_data(self) -> None:
        small = NEWER.kde_random(floats(1_000), h=0.1, seed=1)
        large = NEWER.kde_random(floats(100_000), h=0.1, seed=1)

        ratio = best_ns(large, inner=2_000) / best_ns(small, inner=2_000)

        assert ratio < 5, f"100x the points cost x{ratio:.1f} per draw"


class TestNormalDist:
    """`NormalDist` holds two floats; `from_samples()` is one pass,
    `samples(s)` is O(s), `quantiles(q)` is O(q), and the rest is O(1)."""

    def test_an_instance_holds_two_floats(self) -> None:
        dist = statistics.NormalDist(1, 2)

        assert set(statistics.NormalDist.__slots__) == {"_mu", "_sigma"}
        assert not hasattr(dist, "__dict__")
        assert (type(dist.mean), type(dist.stdev)) == (float, float)

    def test_samples_grow_with_s(self) -> None:
        dist = statistics.NormalDist()

        small = peak_bytes(lambda: dist.samples(1_000, seed=1))
        large = peak_bytes(lambda: dist.samples(100_000, seed=1))

        assert len(dist.samples(1_000, seed=1)) == 1_000
        assert large > 50 * small, f"s=1,000 peaked at {small}, s=100,000 at {large}"

    def test_quantiles_returns_q_minus_one_values(self) -> None:
        assert len(statistics.NormalDist().quantiles(100)) == 99
        assert statistics.NormalDist(5, 1).quantiles(2) == [5.0]

    def test_the_constant_time_members(self) -> None:
        dist = statistics.NormalDist(100, 15)

        assert (dist.mean, dist.median, dist.mode) == (100.0, 100.0, 100.0)
        assert (dist.stdev, dist.variance) == (15.0, 225.0)
        assert dist.zscore(130) == 2.0
        assert round(dist.cdf(130), 4) == 0.9772
        assert round(dist.inv_cdf(0.9772498680518208), 6) == 130.0
        assert round(dist.pdf(100), 5) == 0.0266
        assert dist.overlap(dist) == 1.0

    def test_the_operators_return_new_distributions(self) -> None:
        a = statistics.NormalDist(10, 3)
        b = statistics.NormalDist(20, 4)

        assert a + b == statistics.NormalDist(30, 5)
        assert b - a == statistics.NormalDist(10, 5)
        assert a * 2 == 2 * a == statistics.NormalDist(20, 6)
        assert a / 2 == statistics.NormalDist(5, 1.5)
        assert -a == statistics.NormalDist(-10, 3)
        assert +a == a and +a is not a
        assert a + 1 == statistics.NormalDist(11, 3)

    def test_from_samples_fits_the_data(self) -> None:
        fitted = statistics.NormalDist.from_samples([2, 4, 4, 4, 5, 5, 7, 9])

        assert fitted.mean == 5.0
        assert round(fitted.stdev, 6) == round(statistics.stdev([2, 4, 4, 4, 5, 5, 7, 9]), 6)


class TestStatisticsError:
    """`StatisticsError` is a `ValueError`, raised for empty and invalid data."""

    def test_it_is_a_value_error(self) -> None:
        assert issubclass(statistics.StatisticsError, ValueError)

    @pytest.mark.parametrize(
        "call",
        [
            lambda: statistics.mean([]),
            lambda: statistics.fmean([]),
            lambda: statistics.median([]),
            lambda: statistics.mode([]),
            lambda: statistics.variance([1]),
            lambda: statistics.quantiles([], n=4),
            lambda: statistics.NormalDist(0, 0).pdf(0),
        ],
    )
    def test_empty_and_invalid_data_raise_it(self, call: Callable[[], Any]) -> None:
        with pytest.raises(statistics.StatisticsError):
            call()


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


def _too_new(source: str) -> tuple[int, int] | None:
    for marker, version in MINIMUM_VERSION.items():
        if marker in source and sys.version_info < version:
            return version
    return None


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result; the
    two-input block needs 3.12 for the ranked correlation and the kde block
    needs 3.13."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        for marker in MINIMUM_VERSION:
            assert sum(marker in source for _, source in blocks) == 1, marker

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if _too_new(source):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        skipped = sum(1 for version in MINIMUM_VERSION.values() if sys.version_info < version)
        assert ran == EXPECTED_BLOCKS - skipped
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "outliers == [12.5]" in s)
        mutated = source.replace("outliers == [12.5]", "outliers == [10.1]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
