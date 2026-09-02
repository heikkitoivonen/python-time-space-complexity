# Functools Module Complexity

The `functools` module provides higher-order functions and operations on callable objects.

## Functions

### Caching/Memoization

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `lru_cache(maxsize)` | O(h) avg hit, O(h + w) miss | O(min(n, maxsize)); O(n) for `maxsize=None`; O(1) for `maxsize=0` | h = building and hashing this call's key, after which the lookup itself is O(1) avg; w = one call of the wrapped function; n = distinct calls cached |
| `cache()` | O(h) avg hit, O(h + w) miss | O(n) unbounded | Same h, w and n; defined as `lru_cache(maxsize=None)`, so nothing is evicted |
| `cached_property` | O(1) after first call | O(1) per property |  |


### Function Composition

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `reduce(func, iterable)` | O(n·f) | O(1) auxiliary, plus the accumulator | n = items in the iterable, f = cost of one `func` call |
| `partial(func, *args, **keywords)` | O(p + q) | O(p + q) | p = stored positional args, q = stored keyword bindings |
| `partialmethod(func, *args, **keywords)` | O(p + q) | O(p + q) | Method-descriptor version; stores and flattens by the same rules |
| `wraps(wrapped, assigned, updated)` | O(a + u) when applied | O(a + u) | The decorator form of `update_wrapper`, taking the same a and u and paying the same cost |
| `update_wrapper(wrapper, wrapped, assigned, updated)` | O(a + u) | O(a + u) | a = names listed in `assigned`, u = total entries across the mappings named by `updated`. |

### Comparison Helpers

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `cmp_to_key(func)` | O(1) | O(1) | Convert cmp function to key function |
| `total_ordering` | O(1) | O(1) | Class decorator; fills in missing comparison methods |

### Single Dispatch

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `singledispatch` | O(1) avg hit, super-linear miss for related types | O(k) registered + O(t) cached types | k = registered implementations, t = distinct argument types dispatched on. Hit is O(1) avg (cached per argument type, weak-keyed) |
| `singledispatchmethod` | O(1) avg hit, super-linear miss for related types | O(k) registered + O(t) cached types | Same k and t; method descriptor version (Python 3.8+), sharing `singledispatch`'s dispatch cache |


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
# Space: O(n) - n nested calls are live at once; the cache itself is the
# smaller term, holding only min(n, 128) entries

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

## reduce

### Reduce Operation

```python
from functools import reduce
import operator

# Reduce applies the function n-1 times, so the total is n-1 times whatever
# one call costs -- and since each result is fed back in as the next call's
# first argument, "what one call costs" can grow as the fold proceeds
data = [1, 2, 3, 4, 5]

# Sum all: O(n) while the running total stays machine-word sized
total = reduce(operator.add, data)  # 15

# Product all: O(n) here, but NOT in general. Python ints are arbitrary
# precision, so the running product keeps widening -- over range(1, n + 1)
# this builds n!, whose O(n log n) bits make the fold badly super-linear
product = reduce(operator.mul, data)  # 120

# Max: O(n), and safely so -- the accumulator is always one of the inputs,
# so unlike the two above it cannot grow beyond the largest of them
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

## Additional Examples

### cmp_to_key

```python
from functools import cmp_to_key

# Old-style comparison function
def compare(a, b):
    return (a > b) - (a < b)

# Convert to key function for sorted() - cmp_to_key() itself is O(1)
sorted_data = sorted([3, 1, 4, 1, 5], key=cmp_to_key(compare))
# Still O(n log n), but the wrapper calls compare() on every comparison
# rather than computing a key once per element - a real constant-factor cost
```

### total_ordering

```python
from functools import total_ordering

@total_ordering
class Student:
    def __init__(self, name, grade):
        self.name = name
        self.grade = grade

    def __eq__(self, other):
        return self.grade == other.grade

    def __lt__(self, other):
        return self.grade < other.grade

    # total_ordering fills in __le__, __gt__, __ge__
```

### singledispatch

```python
from functools import singledispatch

@singledispatch
def process(arg):
    return f"Default: {arg}"

@process.register(int)
def _(arg):
    return f"Integer: {arg * 2}"

@process.register(list)
def _(arg):
    return f"List of {len(arg)} items"

process("hello")  # "Default: hello"
process(5)        # "Integer: 10"
process([1,2,3])  # "List of 3 items"
```


## Version Notes

- **Python 2.5+**: `reduce`, `partial`
- **Python 3.2+**: `lru_cache`, `cmp_to_key`, `total_ordering`
- **Python 3.4+**: `singledispatch`, `partialmethod`
- **Python 3.8+**: `cached_property`, `singledispatchmethod`
- **Python 3.9+**: `cache` (unbounded `lru_cache`)

## Related Documentation

- [Itertools Module](itertools.md) - Iterator functions
- [Operator Module](operator.md) - Operator functions
- [abc Module](abc.md) - `get_cache_token()`'s actual home
- [reprlib Module](reprlib.md) - `recursive_repr()`'s actual home
