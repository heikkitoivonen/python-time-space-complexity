# random Module Complexity

The `random` module provides pseudo-random number generation for various probability distributions.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `random.random()` | O(1) | O(1) | Uniform [0.0, 1.0) |
| `random.randint(a, b)` | O(1) | O(1) | Uniform integer |
| `random.choice(seq)` | O(1) | O(1) | Random element |
| `random.choices(seq, k)` | O(k) to O(n + k log n) | O(k) to O(n + k) | O(k) if no weights; builds cumulative weights if provided |
| `random.sample(seq, k)` | O(k) to O(n) | O(k) to O(n) | Copies population when k is large or input is set/dict |
| `random.shuffle(list)` | O(n) | O(1) | In-place Fisher-Yates shuffle |
| `random.uniform(a, b)` | O(1) | O(1) | Uniform float |
| `random.gauss(mu, sigma)` | O(1) | O(1) | Gaussian distribution |
| `random.seed(a)` | O(len(a)) | O(1) | Seed processing depends on input type |

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

# Beta distribution - O(1)
x = random.betavariate(2, 5)  # O(1)

# Multiple samples - O(n)
samples = [random.betavariate(2, 5) for _ in range(1000)]  # O(1000)
```

### Other Distributions

```python
import random

# Exponential distribution - O(1)
x = random.expovariate(1/1000)  # Mean 1000

# Gamma distribution - O(1)
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

# Shuffle-sort (bogosort) - expected O(n!) time
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

### Vectorized Operations (using numpy)

```python
import numpy as np
import random

# Single random value - O(1)
single = random.random()  # Slow for large-scale

# But for bulk operations, numpy is faster
# Generate million random numbers - O(n)
arr = np.random.random(1000000)  # Faster than loop

# Shuffling large arrays - O(n)
big_arr = np.arange(1000000)
np.random.shuffle(big_arr)  # O(1000000)
```

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
import numpy as np
import secrets

# Cryptographically secure random (secure but slow) - O(1)
token = secrets.token_hex(16)  # For passwords/tokens

# For simulation/general use (fast)
value = random.random()  # O(1) - standard

# For scientific computing (vectorized)
array = np.random.random(1000)  # Fast bulk generation
```

## Thread Safety

```python
import random
import threading

# The module-level RNG is safe to call from multiple threads, but it shares state.
# Use a per-thread Random instance to avoid contention and interleaved sequences.

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
- **Different versions**: Some algorithms (e.g., `randrange`) have changed for quality, so sequences may differ

## Related Modules

- **[secrets](secrets.md)** - Cryptographically secure random numbers
- **numpy.random** - Fast vectorized random number generation
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
