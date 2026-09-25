# statistics Module Complexity

The `statistics` module computes averages, spread, relations between two inputs, kernel density
estimates and normal-distribution quantities. It is pure Python, and what separates its functions
is what they hold: `mean()`, `fmean()`, `geometric_mean()` and the spread functions stream through
their input keeping only running sums, while the medians, quantiles and modes keep a copy or a
count as large as the data.

`n` is the data points (the length of `data`, or of each of `x` and `y`), `u` is the distinct
values among them, `q` is the number of intervals asked of a `quantiles()` method (its `n`
argument), `s` is the samples asked of `NormalDist.samples()` (its `n` argument), and `w` is the
data points within one bandwidth of the point a bounded-kernel estimate is evaluated at. Bounds
treat arithmetic, comparison and hashing of one data value as O(1), as they are for floats and
machine-size ints, and the bounds are for int and float data. The exact-arithmetic functions keep
one partial sum per distinct denominator, which stays bounded for ints and floats; `Fraction` data
can have n of them, and `Fraction` and `Decimal` arithmetic also grows with the digits. Space counts
what a call allocates, its result included, but not its input.

## Complexity Reference

### Averages and measures of central location

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `statistics.mean(data)` | O(n) | O(1) | One pass with exact arithmetic; accepts an iterator |
| `statistics.fmean(data, weights=None)` | O(n) | O(1), O(n) for iterator weights | One pass in floats, so it is faster than `mean()`; iterator weights are copied to a list |
| `statistics.geometric_mean(data)` | O(n) | O(1) | Accepts an iterator |
| `statistics.harmonic_mean(data, weights=None)` | O(n) | O(1), O(n) for iterator data or weights | An iterator `data` or `weights` is copied to a list first |
| `statistics.median(data)` | O(n log n) | O(n) | Sorts a copy; O(n) time when `data` is already sorted |
| `statistics.median_low(data)`, `statistics.median_high(data)` | O(n log n) | O(n) | As `median()`, returning a data point rather than an average |
| `statistics.median_grouped(data, interval=1.0)` | O(n log n) | O(n) | Sorts a copy, then two binary searches |
| `statistics.mode(data)` | O(n) | O(u) | Counts every value, then returns the first most common one |
| `statistics.multimode(data)` | O(n) | O(u) | Every value with the highest count, in first-seen order |
| `statistics.quantiles(data, *, n=4, method='exclusive')` | O(n log n + q) | O(n + q) | Sorts a copy, then interpolates q - 1 cut points |

### Measures of spread

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `statistics.variance(data, xbar=None)`, `statistics.pvariance(data, mu=None)` | O(n) | O(1) | One pass with exact arithmetic; accepts an iterator |
| `statistics.stdev(data, xbar=None)`, `statistics.pstdev(data, mu=None)` | O(n) | O(1) | The variance's pass, then one square root |

### Relations between two inputs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `statistics.covariance(x, y, /)` | O(n) | O(1) | `x` and `y` must be sequences of equal length |
| `statistics.correlation(x, y, /, *, method='linear')` | O(n) | O(n) | Holds centred copies of both inputs |
| `statistics.correlation(x, y, method='ranked')` | O(n log n) | O(n) | Sorts both inputs to rank them |
| `statistics.linear_regression(x, y, /, *, proportional=False)` | O(n) | O(n) | Holds a centred copy of `x`; O(1) space with `proportional=True` |
| `statistics.LinearRegression`, `LinearRegression.slope`, `LinearRegression.intercept` | O(1) | O(1) | The named tuple `linear_regression()` returns |

### Kernel density estimation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `statistics.kde(data, h, kernel='normal', *, cumulative=False)` | O(1) | O(1) | For `normal`, `logistic` and `sigmoid`, which weight every point; `data` is held by reference |
| `statistics.kde(data, h, kernel)` with a bounded kernel | O(n log n) | O(n) | Every other kernel: sorts a copy of `data` once |
| Calling an estimate built with `normal`, `logistic` or `sigmoid` | O(n) | O(1) | Sums a kernel term for every data point |
| Calling an estimate built with a bounded kernel | O(log n + w) | O(w) | Binary searches the sorted copy, then sums the w points in reach; a call after `len(data)` changes first re-sorts, O(n log n) time and O(n) space |
| `statistics.kde_random(data, h, kernel='normal', *, seed=None)` | O(1) | O(1) | `data` is held by reference |
| Calling a `kde_random()` result | O(1) | O(1) | One random data point plus one kernel offset |

### NormalDist

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `statistics.NormalDist(mu=0.0, sigma=1.0)` | O(1) | O(1) | Holds two floats |
| `NormalDist.from_samples(data)` | O(n) | O(1) | The mean and sample standard deviation in one pass |
| `NormalDist.samples(n, *, seed=None)` | O(s) | O(s) | Returns a list of s floats |
| `NormalDist.pdf(x)`, `NormalDist.cdf(x)`, `NormalDist.inv_cdf(p)`, `NormalDist.zscore(x)` | O(1) | O(1) | Closed forms and a fixed rational approximation |
| `NormalDist.quantiles(n=4)` | O(q) | O(q) | q - 1 calls to `inv_cdf()` |
| `NormalDist.overlap(other)` | O(1) | O(1) | |
| `NormalDist.mean`, `NormalDist.median`, `NormalDist.mode`, `NormalDist.stdev`, `NormalDist.variance` | O(1) | O(1) | Read-only properties |
| `+` and `-` with a constant or another `NormalDist`, `*` and `/` by a constant, unary `+` and `-` | O(1) | O(1) | Each returns a new `NormalDist` |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `statistics.StatisticsError` | O(1) | O(1) | A `ValueError` subclass, raised for empty data and other invalid inputs |

## Streaming and Sorting

### One Pass or a Sorted Copy

`mean()`, `fmean()`, `geometric_mean()` and the variance family keep running sums and never hold
the data, so a generator over a large source costs O(1) memory on Python 3.11+. The median family
and `quantiles()` sort a copy first, so they hold all n values whatever you pass.

```python
import statistics

def readings():
    for i in range(1, 10_001):
        yield i % 7

assert statistics.mean(readings()) == 2.9998              # O(n) time, O(1) memory
assert statistics.fmean(readings()) == 2.9998             # O(n) time, O(1) memory
assert round(statistics.pvariance(readings()), 3) == 3.999  # O(n) time, O(1) memory

assert statistics.median(readings()) == 3                   # O(n log n) time, O(n) memory
assert statistics.quantiles(readings(), n=4) == [1.0, 3.0, 5.0]  # O(n log n + q)
```

### Sorted Input

The sort is Timsort, which finishes in a single linear scan on data that is already in order. So
when several order statistics are needed from the same data, sort it once: every later call still
copies it, but each copy sorts in O(n).

```python
import statistics

data = [7, 1, 9, 3, 5, 3, 8]

ordered = sorted(data)                     # O(n log n), once
assert statistics.median(ordered) == 5     # O(n) - already sorted
assert statistics.median_low([1, 2, 3, 4]) == 2
assert statistics.median_high([1, 2, 3, 4]) == 3
assert statistics.median([1, 2, 3, 4]) == 2.5  # an even count averages the middle two
assert statistics.quantiles(ordered, n=4) == [3.0, 5.0, 8.0]  # O(n + q)
```

## Exact and Float Averages

`mean()`, `variance()` and `pvariance()` compute in exact integer ratios, and return a `Fraction`
for `Fraction` data and a `Decimal` for `Decimal` data. `fmean()` stays in floats and always
returns one. Both kinds are one pass, but the exact
arithmetic makes `mean()` the slower of the two.

```python
import statistics
from fractions import Fraction

assert statistics.mean([1, 2, 3, 4]) == 2.5                        # O(n)
assert statistics.mean([Fraction(1, 3), Fraction(2, 3)]) == Fraction(1, 2)
assert statistics.fmean([1, 2, 3, 4]) == 2.5                       # O(n), always a float

assert statistics.geometric_mean([4, 9]) == 6.0                    # O(n)
assert statistics.harmonic_mean([40, 60]) == 48.0                  # O(n)

assert statistics.variance([1, 2, 3, 4, 5]) == 2.5                 # O(n)
assert statistics.pstdev([2, 4, 4, 4, 5, 5, 7, 9]) == 2.0          # O(n)
assert round(statistics.stdev([1, 2, 3, 4, 5]), 4) == 1.5811       # O(n)
```

## Counting Modes

`mode()` and `multimode()` count every value in a dictionary, so memory follows the distinct
values rather than the data. A tie is not an error: `mode()` returns the value seen first, and
`multimode()` returns all of them.

```python
import statistics

assert statistics.mode(['red', 'blue', 'red']) == 'red'   # O(n) time, O(u) memory
assert statistics.mode([1, 1, 2, 2]) == 1                 # a tie returns the first seen
assert statistics.multimode([1, 1, 2, 2, 3]) == [1, 2]    # O(n) time, O(u) memory
assert statistics.multimode([]) == []

try:
    statistics.mode([])
except statistics.StatisticsError as error:
    assert 'no mode' in str(error)
else:
    raise AssertionError('mode() of empty data returned')
```

## Relations Between Two Inputs

`covariance()`, `correlation()` and `linear_regression()` take `len()` of both inputs, so they
need sequences, not iterators. The ranked correlation replaces each input by its ranks, which is a
sort.

```python
import statistics

x = [1, 2, 3, 4, 5]
y = [2, 4, 5, 4, 5]

assert statistics.covariance(x, y) == 1.5                          # O(n)
assert round(statistics.correlation(x, y), 4) == 0.7746            # O(n)
assert statistics.correlation(x, [v ** 3 for v in x], method='ranked') == 1.0  # O(n log n)

fit = statistics.linear_regression(x, y)                           # O(n)
assert (fit.slope, fit.intercept) == (0.6, 2.2)
assert statistics.linear_regression(x, [2 * v for v in x], proportional=True).slope == 2.0

try:
    statistics.covariance(iter(x), iter(y))
except TypeError as error:
    assert 'len()' in str(error)
else:
    raise AssertionError('covariance() accepted iterators')
```

## Kernel Density Estimates

`kde()` returns a function, and the choice of kernel decides where the cost lands. The `normal`,
`logistic` and `sigmoid` kernels give every point some weight, so building the estimate is free and
every evaluation sums over all n points. The bounded kernels sort a copy once, and each
evaluation then looks only at the points within the bandwidth.

```python
import statistics

data = [-2.1, -1.3, -0.4, 1.9, 5.1, 6.2]

f = statistics.kde(data, h=1.5)                                  # O(1) - normal kernel
assert round(f(0.0), 4) == 0.1099                                # O(n) per call

g = statistics.kde(data, h=1.5, kernel='triangular')             # O(n log n) - sorts once
assert round(g(0.0), 4) == 0.0963                                # O(log n + w) per call
assert g(100.0) == 0.0                                           # nothing within reach

cdf = statistics.kde(data, h=1.5, kernel='triangular', cumulative=True)
assert cdf(100.0) == 1.0

draw = statistics.kde_random(data, h=1.5, seed=8675309)          # O(1)
assert isinstance(draw(), float)                                 # O(1) per call
```

## Normal Distributions

`NormalDist` holds a mean and a standard deviation and nothing else. Fitting one to data is a
single pass; after that every probability, `inv_cdf()` value and combination is O(1), however
large the data it came from.

```python
import statistics
from statistics import NormalDist

heights = NormalDist.from_samples([168, 172, 175, 181, 169, 177])  # O(n)
assert round(heights.mean, 1) == 173.7                             # O(1)

iq = NormalDist(100, 15)                                           # O(1)
assert round(iq.cdf(130), 4) == 0.9772                             # O(1)
assert round(iq.inv_cdf(0.5), 6) == 100.0                          # O(1)
assert round(iq.pdf(100), 5) == 0.0266                             # O(1)
assert iq.zscore(130) == 2.0                                       # O(1)
assert [round(v, 2) for v in iq.quantiles(4)] == [89.88, 100.0, 110.12]  # O(q)
assert round(iq.overlap(NormalDist(110, 15)), 4) == 0.7389         # O(1)

combined = NormalDist(10, 3) + NormalDist(20, 4)                   # O(1)
assert (combined.mean, combined.stdev) == (30.0, 5.0)
assert (2 * NormalDist(1, 1)).variance == 4.0

draws = NormalDist(0, 1).samples(1_000, seed=42)                   # O(s)
assert len(draws) == 1_000

try:
    NormalDist(0, 0).pdf(0)
except statistics.StatisticsError as error:
    assert 'sigma is zero' in str(error)
else:
    raise AssertionError('pdf() of a zero-width distribution returned')
```

## Common Patterns

### Summarising a Sample

```python
import statistics

def summarise(data):
    ordered = sorted(data)                        # O(n log n), once
    return {
        'mean': statistics.fmean(ordered),        # O(n)
        'stdev': statistics.stdev(ordered),       # O(n)
        'median': statistics.median(ordered),     # O(n) - already sorted
        'quartiles': statistics.quantiles(ordered),  # O(n + q)
        'min': ordered[0],                        # O(1)
        'max': ordered[-1],                       # O(1)
    }

summary = summarise([10, 20, 30, 40, 50])
assert summary['median'] == 30
assert summary['quartiles'] == [15.0, 30.0, 45.0]
assert (summary['min'], summary['max']) == (10, 50)
```

### Flagging Outliers

```python
from statistics import NormalDist

baseline = [9.8, 10.1, 10.0, 9.9, 10.2, 10.0]
model = NormalDist.from_samples(baseline)          # O(n), once

readings = [10.1, 12.5, 9.9]
outliers = [r for r in readings if abs(model.zscore(r)) > 3]  # O(1) per reading
assert outliers == [12.5]
```

## Performance Best Practices

✅ **Do**:

- Pass a generator to `mean()`, `fmean()` or `variance()` when the data does not fit in memory;
  on Python 3.11+ they hold running sums, not values
- Use `fmean()` when a float result is enough; it skips the exact arithmetic `mean()` does
- Sort once and pass the sorted list when you need several of `median()`, `median_low()`,
  `median_high()` and `quantiles()`
- Fit a `NormalDist` once and reuse it: after `from_samples()`, each `pdf()`, `cdf()`, `inv_cdf()`
  and `zscore()` is O(1)
- Choose a bounded kernel for `kde()` when the estimate is evaluated many times over large data

❌ **Avoid**:

- Computing a median of a stream you only need the mean of: it holds all n values
- Appending to the data behind a bounded-kernel `kde()` estimate between calls; each call after a
  length change re-sorts it

## Version Notes

- **Python 3.11+**: `mean()`, `variance()`, `pvariance()`, `stdev()`, `pstdev()` and
  `NormalDist.from_samples()` read an iterator in one pass; on 3.10 they copy it to a list first,
  O(n) space
- **Python 3.11+**: `multimode()` no longer sorts the counts: O(n) rather than O(n + u log u)
- **Python 3.11+**: `fmean()` accepts `weights`, and `linear_regression()` accepts `proportional`
- **Python 3.12+**: `correlation()` accepts `method='ranked'`; it and `linear_regression()` hold
  centred copies of their inputs, O(n) space where 3.10 and 3.11 used O(1)
- **Python 3.13+**: Added `kde()` and `kde_random()`
- **Python 3.13+**: `quantiles()` of a single data point returns q - 1 copies of it instead of
  raising `StatisticsError`

## Related Modules

- **[math](math.md)** - `fsum()`, an accurate float sum without the rest of the module
- **[fractions](fractions.md)** - the exact values `mean()` and `variance()` compute with
- **[random](random.md)** - drawing random samples
- **[bisect](bisect.md)** - order statistics on data you keep sorted yourself
