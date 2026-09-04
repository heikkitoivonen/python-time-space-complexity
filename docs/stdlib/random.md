# random Module Complexity

The `random` module provides pseudo-random number generation for various probability distributions.

## Complexity Reference

Throughout, `n` is the size of the population passed in, `k` the number of
values drawn, `w` the bit width of the widest integer an operation handles -
its operands as well as its result - and `s` the size of a seed. Costs are
counted in generator draws and element accesses, with an index taken as one
word: a sequence bounds its index with `len()`. An integer passed as a *bound*
has no such limit, so the rows that take one carry `w`. "Expected" marks a
rejection loop: the number of draws is not bounded, but its mean is a small
constant.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.random()` | O(1) | O(1) | Uniform [0.0, 1.0) |
| `random.getrandbits(w)` | O(w) | O(w) | Returns a w-bit integer |
| `random.randbytes(count)` | O(count) | O(count) | One `getrandbits(8 * count)` |
| `random.randrange([start,] stop)` | O(w) expected | O(w) | One word for ordinary bounds. `stop` is excluded |
| `random.randrange(start, stop, step)` | O(w) expected, plus one [`//`](../builtins/int.md) and one [`*`](../builtins/int.md) on w-bit operands | O(w) | Superlinear in w once those operands are big integers |
| `random.randint(a, b)` | O(w) expected | O(w) | Uniform integer, both ends included |
| `random.choice(seq)` | O(1) expected | O(1) | One index lookup, so O(1) only where indexing is |
| `random.choices(seq, k=k)` | O(k) | O(k) | With replacement; the population is not copied |
| `random.choices(seq, weights, k=k)` | O(n + k log n) | O(n + k) | Accumulates the weights once, then bisects per draw |
| `random.choices(seq, cum_weights=c, k=k)` | O(k log n) | O(k) | Skips the accumulation; pass this to reuse one set of weights across calls |
| `random.sample(seq, k)` | O(k) to O(n) | O(k) to O(n) | Tracks the k drawn indices, or copies the population when that copy is smaller than the index set; `seq` must be a sequence, not a set or dict |
| `random.sample(seq, k, counts=c)` | O(n + k log n) | O(n + k) | Accumulates the counts, then bisects each selection |
| `random.shuffle(list)` | O(n) | O(1) | In-place Fisher-Yates shuffle |
| `random.uniform(a, b)` | O(1) | O(1) | Uniform float |
| `random.triangular(low, high, mode)` | O(1) | O(1) | One draw |
| `random.gauss(mu, sigma)` | O(1) | O(1) | Generates values in pairs and caches the spare |
| `random.normalvariate(mu, sigma)` | O(1) expected | O(1) | Rejection loop, and no cached spare |
| `random.lognormvariate(mu, sigma)` | O(1) expected | O(1) | `exp()` of a `normalvariate()` |
| `random.expovariate(lambd)` | O(1) | O(1) | One draw |
| `random.paretovariate(alpha)` | O(1) | O(1) | One draw |
| `random.weibullvariate(alpha, beta)` | O(1) | O(1) | One draw |
| `random.gammavariate(alpha, beta)` | O(1) expected | O(1) | Rejection loop |
| `random.betavariate(alpha, beta)` | O(1) expected | O(1) | Two `gammavariate()` calls |
| `random.vonmisesvariate(mu, kappa)` | O(1) expected | O(1) | Rejection loop |
| `random.binomialvariate(n, p)` | O(1) expected | O(1) | Python 3.12+ |
| `random.seed(a)` | O(s) | O(s) | A str or bytes seed is hashed with the whole input kept, so both terms follow its length |
| `random.getstate()` / `random.setstate(state)` | O(1) | O(1) | The Mersenne Twister state is a fixed 625 words |
| `random.Random(a)` | O(s) | O(s) | An independent stream; seeded as above |
| `random.SystemRandom()` | O(1) | O(1) | Draws from `os.urandom()`; cannot be seeded and keeps no state |

## Basic Random Number Generation

### Uniform Distribution

```python
import random

# Random float [0.0, 1.0) - O(1)
x = random.random()  # ~0.37

# Random integer [a, b] inclusive - O(1)
n = random.randint(1, 10)  # Between 1 and 10

# Random float in range - O(1)
y = random.uniform(0, 100)  # Between 0 and 100
```

### Seeding for Reproducibility

```python
import random

# Set seed for reproducible results - O(1)
random.seed(42)

# Same seed produces same sequence
x1 = random.random()  # Always same value with seed(42)
y1 = random.randint(1, 100)

random.seed(42)
x2 = random.random()  # Same as x1
y2 = random.randint(1, 100)  # Same as y1

# Useful for testing: reproducible randomness
```

## Sequence Operations

### Random Selection

```python
import random

# Choose one random element - O(1)
lst = [10, 20, 30, 40, 50]
item = random.choice(lst)  # One of the elements

# Works with strings
char = random.choice("hello")  # 'h', 'e', 'l', 'l', or 'o'

# Get one random element from range - O(1)
num = random.choice(range(1000000))  # O(1) even for huge range!
```

### Multiple Random Selections

```python
import random

# Multiple selections WITH replacement - O(k)
lst = [1, 2, 3, 4, 5]
selections = random.choices(lst, k=3)  # [5, 2, 5] - O(3)

# Weighted selection - O(n + k log n)
colors = ['red', 'blue', 'green']
weights = [0.5, 0.3, 0.2]
draws = random.choices(colors, weights=weights, k=100)  # O(n + k log n)

# Without replacement (sample) - O(k) to O(n)
unique = random.sample(lst, k=3)  # [3, 1, 4] - no duplicates
```

### Shuffling

```python
import random

# In-place shuffle - O(n)
lst = [1, 2, 3, 4, 5]
random.shuffle(lst)  # Modifies list in place - O(5)
# lst might be [3, 1, 5, 2, 4]

# Shuffle large list - O(n)
big_list = list(range(1000000))
random.shuffle(big_list)  # O(1000000)

# Get shuffled copy - O(n) space
original = [1, 2, 3, 4, 5]
shuffled = random.sample(original, k=len(original))  # [4, 1, 3, 5, 2]
# Original unchanged - O(5) space
```

## Common Probability Distributions

### Gaussian (Normal) Distribution

```python
import random

# Normal distribution - O(1)
mu = 0      # Mean
sigma = 1   # Standard deviation

# Single value - O(1)
x = random.gauss(mu, sigma)  # Typically near 0

# Generate samples - O(n)
samples = [random.gauss(100, 15) for _ in range(1000)]  # O(1000)
```

### Beta Distribution

```python
import random

# Beta distribution - O(1) expected, via two gammavariate() calls
x = random.betavariate(2, 5)

# Multiple samples - O(n)
samples = [random.betavariate(2, 5) for _ in range(1000)]  # O(1000)
```

### Other Distributions

```python
import random

# Exponential distribution - O(1)
x = random.expovariate(1/1000)  # Mean 1000

# Gamma distribution - O(1) expected, from a rejection loop
y = random.gammavariate(2, 2)

# Generate many samples - O(n)
samples = [random.gammavariate(2, 2) for _ in range(10000)]  # O(10000)
```

## Common Patterns

### Random Sampling from Large Datasets

```python
import random

# Algorithm: Reservoir sampling - O(n) time, O(k) space
def reservoir_sample(iterable, k):
    """Sample k items from iterable without loading all in memory"""
    reservoir = []
    for i, item in enumerate(iterable):
        if i < k:
            reservoir.append(item)
        else:
            j = random.randint(0, i)  # O(1) per item
            if j < k:
                reservoir[j] = item
    return reservoir

# Usage - O(n) for iteration, O(1) per random operation
large_iter = range(1000000)
sample = reservoir_sample(large_iter, 100)  # O(1000000)
```

### Randomized Algorithms

```python
import random

# Randomized quicksort pivot selection - O(1)
def random_partition(arr, low, high):
    pivot_idx = random.randint(low, high)  # O(1)
    # ... partition logic

# Shuffle-sort (bogosort) - expected O(n * n!) time: n! shuffles of O(n) each
def shuffle_sort(arr):
    while not is_sorted(arr):
        random.shuffle(arr)  # O(n) per iteration
    return arr
```

### Monte Carlo Simulations

```python
import random

# Estimate Pi using random points - O(n) iterations
def estimate_pi(num_samples):
    inside_circle = 0
    for _ in range(num_samples):
        x = random.random()  # O(1)
        y = random.random()  # O(1)
        if x*x + y*y <= 1:
            inside_circle += 1
    return 4 * inside_circle / num_samples

# Estimate Pi
pi_estimate = estimate_pi(100000)  # O(100000)
```

## Random Walks

### 1D Random Walk

```python
import random

def random_walk(steps):
    """Perform a random walk"""
    position = 0
    for _ in range(steps):
        step = random.choice([-1, 1])  # O(1)
        position += step
    return position

# Simulate random walk - O(n)
final_position = random_walk(1000)  # O(1000)
```

### 2D Random Walk

```python
import random

def random_walk_2d(steps):
    """2D random walk"""
    x, y = 0, 0
    for _ in range(steps):
        direction = random.choice([(0,1), (0,-1), (1,0), (-1,0)])
        x += direction[0]
        y += direction[1]
    return x, y

# Simulate 2D random walk - O(n)
final_pos = random_walk_2d(10000)  # O(10000)
```

## Performance Optimization

### Weighted Random Selection

```python
import random
from bisect import bisect

# Simple weighted choice with normalization - O(n)
def weighted_choice(choices, weights):
    total = sum(weights)
    r = random.uniform(0, total)
    upto = 0
    for choice, weight in zip(choices, weights):
        if upto + weight >= r:
            return choice
        upto += weight
    return choices[-1]

# O(n) where n = number of choices
# Better: use random.choices() when you want multiple draws
items = ['a', 'b', 'c']
weights = [0.5, 0.3, 0.2]
result = random.choices(items, weights=weights, k=1)[0]  # O(n)
```

## State Management

### Multiple Random Streams

```python
import random

# Create independent random states - O(1)
rng1 = random.Random(42)
rng2 = random.Random(43)

# Each has its own state - O(1)
x1 = rng1.random()  # Independent
x2 = rng2.random()  # Independent

# Useful for parallel processing
# Each thread gets its own RNG with different seed
```

### Getstate and Setstate

```python
import random

# Capture random state - O(1)
state = random.getstate()

# Generate some random numbers
x1 = random.random()
y1 = random.randint(1, 100)

# Restore state - O(1)
random.setstate(state)

# Get same random numbers
x2 = random.random()  # Same as x1
y2 = random.randint(1, 100)  # Same as y1
```

## Comparison with Alternatives

```python
import random
import secrets

# Cryptographically secure random (secure but slow) - O(1)
token = secrets.token_hex(16)  # For passwords/tokens

# For simulation/general use (fast)
value = random.random()  # O(1) - standard
```

## Thread Safety

```python
import random
import threading

# random() is a single C step, so the module-level RNG is safe to call from
# multiple threads -- but it shares state, so no thread gets its own sequence.
# gauss() is the exception: it caches a spare value between calls, and two
# threads can be handed the same one. Give each thread its own Random instance.

def worker(seed):
    rng = random.Random(seed)  # O(1) - thread-safe
    value = rng.random()  # O(1)
    print(value)

# Create threads with separate RNGs
threads = [
    threading.Thread(target=worker, args=(i,))
    for i in range(10)
]
```

## Version Notes

- **Python 2.x and 3.x**: Core functions available in all versions
- **Python 3.6+**: `random.choices()` added
- **Python 3.9+**: `random.randbytes()` added, and `random.sample()` gained `counts`
- **Python 3.11+**: `random.sample()` rejects a set; convert it to a sequence first
- **Python 3.12+**: `random.binomialvariate()` added
- **Different versions**: Some algorithms (e.g., `randrange`) have changed for quality, so sequences may differ

## Related Modules

- **[secrets](secrets.md)** - Cryptographically secure random numbers
- **[statistics](statistics.md)** - Statistical functions

## Best Practices

✅ **Do**:

- Use `random.seed()` for reproducible randomness in tests
- Use `random.choices()` for weighted selection
- Use each thread's own `random.Random()` instance
- Use `secrets` for cryptographic randomness
- Cache seed for reproducibility

❌ **Avoid**:

- Assuming `random()` is cryptographically secure (use `secrets` instead)
- Sharing RNG between threads (create separate instances)
- Re-seeding frequently (defeats reproducibility)
- Shuffling huge lists if you can iterate instead
- Forgetting that `shuffle()` is O(n) (can be slow for large lists)
