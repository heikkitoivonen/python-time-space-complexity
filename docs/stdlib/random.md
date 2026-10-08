# random Module Complexity

The `random` module draws pseudo-random numbers from a Mersenne Twister written in C, and builds
integers, sequence operations and distributions in Python on top of it. The module-level functions
are bound methods of one hidden `random.Random` instance, so each also exists as a `Random` method
at the same cost, and the generator's whole state is a fixed 624 words whatever it has produced.

`n` is the length of the population passed in, `k` the number of values drawn or returned, `w`
the bit width of the widest integer an operation handles - its operands as well as its result -
`b` a byte count, `s` the size of a seed - its length for a str, bytes or bytearray, its bit width
for an int - and `a` the characters in the command-line arguments.
Costs are counted in generator draws and element accesses, and indexing a sequence is priced at
O(1). A sequence index fits a word, because `len()` has to return one; an integer passed as a
bound has no such limit, so the rows that take one carry `w`. "Expected" marks a rejection loop:
the number of draws is not bounded, but its mean is a small constant.

## Complexity Reference

### Integers and bytes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.random()`, `Random.random()` | O(1) | O(1) | Uniform float in [0.0, 1.0) |
| `random.getrandbits(w)`, `Random.getrandbits(w)` | O(w) | O(w) | Returns a non-negative int of at most w bits |
| `random.randbytes(b)`, `Random.randbytes(b)` | O(b) | O(b) | One `getrandbits(8 * b)` |
| `random.randrange(stop)`, `random.randrange(start, stop)` | O(w) expected | O(w) | `stop` is excluded |
| `random.randrange(start, stop, step)` | O(w) expected, plus one [`//`](../builtins/int.md) and one `*` on w-bit operands | O(w) | Can be superlinear in w when the step is itself a big integer |
| `random.randint(a, b)` | O(w) expected | O(w) | Both ends included |

### Sequences

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.choice(seq)` | O(1) expected | O(1) | One index lookup |
| `random.choices(population, k=k)` | O(k) | O(k) | With replacement; the population is indexed, never copied |
| `random.choices(population, weights, k=k)` | O(n + k log n) | O(n + k) | Accumulates the weights on every call, then bisects once per draw |
| `random.choices(population, cum_weights=c, k=k)` | O(k log n) | O(k) | Skips the accumulation, so prepared cumulative weights can be reused across calls |
| `random.sample(population, k)` | O(k) expected | O(k) | Independent of n. `population` must be a sequence; 3.10 still accepts a set, copying it in O(n) |
| `random.sample(population, k, counts=c)` | O(n + k log n) expected | O(n + k) | Accumulates the counts, samples k positions, then bisects each one |
| `random.shuffle(x)` | O(n) expected | O(1) | In place |

### Distributions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.uniform(a, b)` | O(1) | O(1) | One draw |
| `random.triangular(low, high, mode)` | O(1) | O(1) | One draw |
| `random.expovariate(lambd)` | O(1) | O(1) | One draw |
| `random.paretovariate(alpha)` | O(1) | O(1) | One draw |
| `random.weibullvariate(alpha, beta)` | O(1) | O(1) | One draw |
| `random.gauss(mu, sigma)` | O(1) | O(1) | Makes two values from two draws and keeps the second in the generator for the next call |
| `random.normalvariate(mu, sigma)` | O(1) expected | O(1) | Rejection loop; keeps nothing between calls |
| `random.lognormvariate(mu, sigma)` | O(1) expected | O(1) | `exp()` of a `normalvariate()` |
| `random.gammavariate(alpha, beta)` | O(1) expected | O(1) | Rejection loop |
| `random.betavariate(alpha, beta)` | O(1) expected | O(1) | Up to two `gammavariate()` calls |
| `random.vonmisesvariate(mu, kappa)` | O(1) expected | O(1) | Rejection loop |
| `random.binomialvariate(n=1, p=0.5)` | O(1) expected | O(1) | Python 3.12+; however many trials are asked for |

### Seeding and state

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.seed(a=None, version=2)`, `Random.seed(a=None, version=2)` | O(s) | O(s) | With the default `version=2`, a str, bytes or bytearray seed costs its length in both time and space |
| `random.getstate()`, `Random.getstate()` | O(1) | O(1) | A tuple holding the 624-word Twister state plus a position, and the `gauss()` spare |
| `random.setstate(state)`, `Random.setstate(state)` | O(1) | O(1) | Restores exactly what `getstate()` captured |

### Random

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.Random(x=None)` | O(s) | O(s) | An independent generator, seeded as `seed()` is. Every function above is also a method of it, at the same cost |

### SystemRandom

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.SystemRandom()` | O(1) | O(1) | Draws from `os.urandom()`, so there is no generator state to seed or save. Every `Random` method is available, at the same number of draws |
| `SystemRandom.random()` | O(1) | O(1) | One `os.urandom()` call per value |
| `SystemRandom.getrandbits(w)` | O(w) | O(w) | One `os.urandom()` call for the bytes holding w bits |
| `SystemRandom.randbytes(b)` | O(b) | O(b) | One `os.urandom(b)` call |
| `SystemRandom.seed(a=None)` | O(1) | O(1) | Does nothing |
| `SystemRandom.getstate()`, `SystemRandom.setstate(state)` | O(1) | O(1) | Raise `NotImplementedError`: there is no state to save |

### Command line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.main(arg_list=None)` | O(a) | O(a) | Python 3.13+, `python -m random`: parses the arguments, then makes one `choice()`, `randint()` or `uniform()`, or returns the help text when given none |

## Integers and Bit Width

`randrange()` and `randint()` draw as many bits as the span of the range needs, and retry when
the draw falls outside it, which happens at most half the time. The width that matters is the
widest integer you pass: nothing bounds it, so `randrange(2**2048)` draws and returns integers of
about 2,048 bits, and a two-element range based at `2**4096` still adds its offset to a 4,097-bit
`start`. The sequence functions never reach such widths, because a sequence index fits a word.

```python
import random

key = random.randrange(2**2048)  # O(w) expected
assert 0 <= key < 2**2048

bits = random.getrandbits(64)  # O(w)
assert bits.bit_length() <= 64

blob = random.randbytes(16)  # O(b)
assert len(blob) == 16

# A two-element range is still O(w) when start is wide
start = 2**4096
assert random.randrange(start, start + 2) in (start, start + 1)  # O(w) expected

assert random.randint(1, 6) in range(1, 7)  # both ends included
assert random.randrange(0, 100, 5) % 5 == 0  # one // and one * on top
```

## Choosing from Sequences

### Single and Repeated Choices

`choice()` and the unweighted `choices()` index the population once per value. A `range` is a
sequence too, so choosing from a huge one costs no more than choosing from a short list.

```python
import random

colors = ['red', 'green', 'blue']
assert random.choice(colors) in colors  # O(1) expected
assert random.choice(range(10**12)) < 10**12  # the range is never built

draws = random.choices(colors, k=5)  # O(k), with replacement
assert len(draws) == 5 and set(draws) <= set(colors)
```

### Weighted Choices

`weights=` is accumulated into a fresh list on every call, which is the O(n) term; each draw is
then a bisection. When the same weights serve many calls, accumulate them once and pass
`cum_weights=` instead.

```python
import random
from itertools import accumulate

items = ['a', 'b', 'c', 'd']
weights = [5, 1, 1, 1]

picks = random.choices(items, weights=weights, k=100)  # O(n + k log n)
assert len(picks) == 100

cumulative = list(accumulate(weights))  # O(n), once
assert cumulative == [5, 6, 7, 8]
for _ in range(10):
    batch = random.choices(items, cum_weights=cumulative, k=10)  # O(k log n) each
    assert set(batch) <= set(items)
```

### Sampling Without Replacement

`sample()` is O(k) however long the population is. It remembers the indices it has drawn in a
set, or, when the population is no bigger than that set would be, copies it into a list and
draws from that; either way the work and memory follow k. Pass a `range` to sample from a span
of integers far larger than k without building it. A dict is not a sequence and is rejected, and so, from
Python 3.11, is a set: convert one first with `list()` or `sorted()`.

```python
import random

winners = random.sample(range(10**9), 5)  # O(k) expected; the range is not built
assert len(set(winners)) == 5

deck = list(range(52))
hand = random.sample(deck, 5)  # O(k) expected
assert len(set(hand)) == 5 and deck == list(range(52))

try:
    random.sample({'a': 1, 'b': 2}, 1)
except TypeError as error:
    assert 'sequence' in str(error)
else:
    raise AssertionError('sample() accepted a dict')

assert len(random.sample(list({1, 2, 3}), 2)) == 2  # O(n) to convert

# counts= repeats each element without building the repeated list
balls = random.sample(['red', 'blue'], counts=[4, 2], k=5)  # O(n + k log n) expected
assert balls.count('blue') <= 2
```

### Shuffling

`shuffle()` swaps in place, drawing about once per element, in O(1) extra space. For a shuffled
copy that leaves the original alone, `sample(x, len(x))` costs the same time plus an O(n) list.

```python
import random

cards = list(range(10))
random.shuffle(cards)  # O(n) expected, O(1) space
assert sorted(cards) == list(range(10))

original = [1, 2, 3, 4, 5]
copy = random.sample(original, k=len(original))  # O(n) expected, O(n) space
assert sorted(copy) == original and original == [1, 2, 3, 4, 5]
```

## Distributions

Every distribution is O(1) per value. The closed-form ones take exactly one draw. The others run
a rejection loop whose mean number of draws stays a small constant over the whole parameter
range. `gauss()` makes values in pairs and keeps the spare in the generator, which is why it is
not safe to share between threads without a lock; `normalvariate()` keeps nothing.

```python
import random

rng = random.Random(7)

assert 0.0 <= rng.random() < 1.0  # O(1)
assert 2.0 <= rng.uniform(2.0, 5.0) <= 5.0  # O(1), one draw
assert rng.expovariate(1 / 1000) >= 0.0  # O(1), mean 1000

samples = [rng.normalvariate(100, 15) for _ in range(1000)]  # O(1) expected each
assert 80 < sum(samples) / len(samples) < 120

assert 0.0 <= rng.betavariate(2, 5) <= 1.0  # O(1) expected
assert rng.gammavariate(2, 2) > 0.0  # O(1) expected

if hasattr(rng, 'binomialvariate'):  # Python 3.12+
    assert 0 <= rng.binomialvariate(10**9, 0.5) <= 10**9  # O(1) expected

rng.gauss(0.0, 1.0)  # O(1): two values made, one kept
assert rng.getstate()[2] is not None  # the spare
```

## Seeding and State

### Reproducible Sequences

Seeding costs the size of the seed: a str or bytes seed costs its length, and an int its bit
width. The state `getstate()` returns is the same size whatever the seed was.

```python
import random

random.seed(42)  # O(s)
first = [random.random(), random.randint(1, 100)]
random.seed(42)
assert [random.random(), random.randint(1, 100)] == first

random.seed('a long string seed')  # O(s), s = length of the string
state = random.getstate()  # O(1)
assert len(state[1]) == 625  # the Twister's 624 words plus its position

x = random.random()
random.setstate(state)  # O(1)
assert random.random() == x
```

### Independent Streams

Each `Random` instance has its own state, so a seeded instance per thread or per task gives each
one a reproducible sequence of its own. The module functions share a single hidden instance:
`random()` is one step in C and safe to call from several threads, but no thread then sees a
sequence of its own. `SystemRandom` reads `os.urandom()` on every draw and has no generator
state to seed or save; use it, or [`secrets`](secrets.md), where values must be unpredictable.

```python
import random
import threading

results = {}

def worker(seed):
    rng = random.Random(seed)  # O(s), one per thread
    results[seed] = [rng.random() for _ in range(3)]

threads = [threading.Thread(target=worker, args=(seed,)) for seed in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()

expected = random.Random(2)
assert results[2] == [expected.random() for _ in range(3)]  # reproducible per thread
assert results[0] != results[1]

secure = random.SystemRandom()  # O(1)
assert 0.0 <= secure.random() < 1.0  # one os.urandom() call
try:
    secure.getstate()
except NotImplementedError:
    pass
else:
    raise AssertionError('SystemRandom has no state to return')
```

## Common Patterns

### Reservoir Sampling

`sample()` needs a sequence. To pick k items from a stream of unknown length without holding it,
keep a k-item reservoir and draw once per later item.

```python
import random

def reservoir_sample(iterable, k, rng=random):
    reservoir = []
    for index, item in enumerate(iterable):
        if index < k:
            reservoir.append(item)
        else:
            slot = rng.randrange(index + 1)  # O(1) expected
            if slot < k:
                reservoir[slot] = item
    return reservoir

picked = reservoir_sample(iter(range(100_000)), 10)  # O(n) expected time, O(k) space
assert len(picked) == 10 and len(set(picked)) == 10
```

### Monte Carlo Estimation

```python
import math
import random

def estimate_pi(samples, rng):
    inside = 0
    for _ in range(samples):  # O(samples)
        x, y = rng.random(), rng.random()  # O(1) each
        if x * x + y * y <= 1.0:
            inside += 1
    return 4 * inside / samples

assert abs(estimate_pi(100_000, random.Random(1)) - math.pi) < 0.05
```

## Performance Best Practices

✅ **Do**:

- Pass `cum_weights=` when the same weights serve many `choices()` calls, so the O(n)
  accumulation happens once
- Pass a `range` rather than a list of integers to `choice()` or `sample()`: they cost the same
  on either, and the list costs O(n) to build
- Give each thread or task its own seeded `random.Random()` for a reproducible stream
- Use `secrets` or `SystemRandom` where values must be unpredictable

❌ **Avoid**:

- `random.choices(population, weights)[0]` in a loop over the same weights - each call
  re-accumulates all n of them
- Converting a large set to a list just to draw a few items repeatedly - convert once and keep it
- Sharing `gauss()` between threads without a lock - two callers can be handed the same spare
- Seeding from a large string or bytes object in a hot path - the cost follows its length
- The module functions for security tokens - the Mersenne Twister is predictable from its output

## Version Notes

- **Python 3.6+**: `random.choices()` added
- **Python 3.9+**: `random.randbytes()` added, and `random.sample()` gained `counts`
- **Python 3.11+**: `random.sample()` rejects a set; convert it to a sequence first
- **Python 3.12+**: `random.binomialvariate()` added
- **Python 3.13+**: `python -m random` command line, through `random.main()`

## Related Modules

- **[secrets](secrets.md)** - `SystemRandom` behind token helpers, for values that must be
  unpredictable
- **[statistics](statistics.md)** - summarising the values drawn here
- **[bisect](bisect.md)** - the O(log n) search `choices()` runs per weighted draw
- **[itertools](itertools.md)** - `accumulate()` to prepare `cum_weights=` once
