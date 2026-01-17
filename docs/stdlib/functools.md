# Functools Module Complexity

The `functools` module provides higher-order functions and operations on callable objects.

## Functions

### Caching/Memoization

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `lru_cache(maxsize)` | O(1) hit, O(f(n)) miss | O(min(n, maxsize)) | Hit is O(1), miss runs wrapped function f(n) |
| `cache()` | O(1) hit, O(f(n)) miss | O(n) unbounded | Hit is O(1), miss runs wrapped function f(n) |
| `cached_property` | O(1) after first call | O(1) per property | Descriptor cache |

### Function Composition

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `reduce(func, iterable)` | O(n) | O(1) | Fold/aggregate |
| `partial(func, args)` | O(1) | O(k) for k args | Create partial function |
| `wraps(wrapped)` | O(1) | O(1) | Copy function metadata |

## Caching Complexity

### LRU Cache

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# Complexity with cache:
# Time: O(n) - each value computed once
# Space: O(min(n, 128)) - limited cache size

# Without cache would be O(2^n)
```

### Cache Performance

```python
import time
from functools import lru_cache

@lru_cache(maxsize=256)
def expensive_computation(x):
    # O(n) computation
    return sum(range(x))

# First call: O(n) - computes
start = time.time()
result = expensive_computation(1000000)
first_time = time.time() - start

# Second call: O(1) - cache hit
start = time.time()
result = expensive_computation(1000000)
second_time = time.time() - start

# second_time << first_time (cache hit)
```

## Reduce Operation

```python
from functools import reduce
import operator

# Reduce: O(n) - applies function n-1 times
data = [1, 2, 3, 4, 5]

# Sum all: O(n)
total = reduce(operator.add, data)  # 15

# Product all: O(n)
product = reduce(operator.mul, data)  # 120

# Max: O(n)
maximum = reduce(lambda a, b: a if a > b else b, data)  # 5
```

## Partial Functions

```python
from functools import partial

# Create partial function: O(1)
def multiply(x, y):
    return x * y

times_3 = partial(multiply, 3)  # O(1) - just stores args

# Use partial: same complexity as original
result = times_3(5)  # O(1) - calls multiply(3, 5)
```

## Common Patterns

### Memoization for Recursion

```python
from functools import lru_cache

@lru_cache(maxsize=None)  # Unlimited cache
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n-1)  # O(1) with cache

# Complexity: O(n) time, O(n) space (with cache)
# Without cache: O(n) time, O(n) space (call stack)
```

### Reduce for Aggregation

```python
from functools import reduce

# Sum with reduce: O(n)
numbers = [1, 2, 3, 4, 5]
total = reduce(lambda a, b: a + b, numbers)

# Instead of:
total = 0
for n in numbers:
    total += n

# Both O(n), but reduce is more functional style
```

### Creating Callable Variants

```python
from functools import partial

# Base function
def format_data(value, width, align='<'):
    return f"{value:{align}{width}}"

# Create variants: O(1) each
left_align = partial(format_data, width=10, align='<')
right_align = partial(format_data, width=10, align='>')

# Use them
print(left_align(42))    # '42        '
print(right_align(42))   # '        42'
```

## Cache Management

### Checking Cache Stats

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def compute(n):
    return n * n

compute(5)    # O(n)
compute(5)    # O(1) - cache hit
compute(6)    # O(n)
compute(5)    # O(1) - cache hit

# View cache stats
info = compute.cache_info()
print(info)
# CacheInfo(hits=2, misses=2, maxsize=128, currsize=2)

# Clear cache
compute.cache_clear()
```

### Cache Decorators Comparison

```python
from functools import lru_cache, cache, cached_property

# lru_cache: Limited size, configurable
@lru_cache(maxsize=128)
def func1(x):
    return x * x

# cache (Python 3.9+): Unlimited
@cache
def func2(x):
    return x * x

# cached_property: Descriptor for class properties
class MyClass:
    @cached_property
    def expensive_property(self):
        # Computed once per instance
        return sum(range(1000000))
```

## Performance Characteristics

### When to Use Cache

```python
from functools import lru_cache

# GOOD: Pure function, called repeatedly
@lru_cache(maxsize=128)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# BAD: Non-deterministic
@lru_cache(maxsize=128)
def get_current_time():
    return time.time()  # Returns different values!

# BAD: Depends on external state
cached_value = None
@lru_cache(maxsize=128)
def read_file(path):
    return open(path).read()  # File might change!
```

### Memory vs Speed Tradeoff

```python
from functools import lru_cache

# Small cache: Less memory, more recomputation
@lru_cache(maxsize=16)
def expensive(x):
    return sum(range(x))

# Large cache: More memory, fewer recomputations
@lru_cache(maxsize=1024)
def expensive(x):
    return sum(range(x))

# Unbounded cache: Most memory, no recomputation
@lru_cache(maxsize=None)
def expensive(x):
    return sum(range(x))
```

## Version Notes

- **Python 2.5+**: `reduce`, `partial`
- **Python 3.2+**: `lru_cache`
- **Python 3.8+**: `cached_property`
- **Python 3.9+**: `cache` (unbounded `lru_cache`)

## Related Documentation

- [Itertools Module](itertools.md) - Iterator functions
- [Operator Module](operator.md) - Operator functions
