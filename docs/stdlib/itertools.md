# Itertools Module Complexity

The `itertools` module provides efficient looping tools for creating iterators and combinations.

## Iterator Functions

### Creating Iterators

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `count(start, step)` | O(1) per item | O(1) | Infinite counter |
| `cycle(iterable)` | O(1) per item | O(n) | Repeated n items |
| `repeat(obj, times)` | O(1) per item | O(1) | Repeat same item |

### Filtering Iterators

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `filter(pred, iter)` | O(n) total | O(1) | Filter items |
| `filterfalse(pred, iter)` | O(n) total | O(1) | Opposite filter |
| `compress(iter, sel)` | O(n) total | O(1) | Mask-based filter |
| `dropwhile(pred, iter)` | O(n) total | O(1) | Drop while true |
| `takewhile(pred, iter)` | O(n) total | O(1) | Take while true |
| `islice(iter, start, stop, step)` | O(n) total | O(1) | Slice iterator |

### Combining Iterators

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `chain(iter1, iter2, ...)` | O(n+m) total | O(1) | Combine iterators |
| `chain.from_iterable(iterable)` | O(n) total | O(1) | Chain nested iterables |
| `zip_longest(iter1, iter2, ...)` | O(n) total | O(1) | Zip with fill value |

### Grouping & Windowing

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `groupby(iterable, key)` | O(n) total | O(1) | Group consecutive |
| `combinations(iterable, r)` | O(n!/(r!(n-r)!)) | O(r) per item | All r-combinations |
| `permutations(iterable, r)` | O(n!/(n-r)!) | O(r) per item | All permutations |
| `product(iter1, iter2, ...)` | O(n*m) total | O(r) per item | Cartesian product |

## Memory Characteristics

All itertools functions are lazy - they generate items on demand without storing the entire result.

```python
import itertools

# All of these are O(1) memory (lazy)
c = itertools.count()              # Infinite counter
f = itertools.filterfalse(pred, x)  # Filtered iterator
z = itertools.chain(iter1, iter2)  # Chained iterators
```

## Common Use Cases

### Infinite Sequences

```python
from itertools import count, cycle, repeat

# Infinite counter: O(1) memory
counter = count(0, 1)
next(counter)  # 0
next(counter)  # 1

# Repeat cycle: O(n) memory for n items
colors = cycle(['red', 'green', 'blue'])
next(colors)  # 'red'
next(colors)  # 'green'

# Repeat same item: O(1) memory
ones = repeat(1)
next(ones)  # 1
next(ones)  # 1
```

### Filtering & Selecting

```python
from itertools import filterfalse, takewhile, dropwhile

data = [1, 2, 3, 4, 5, 6, 7, 8, 9]

# Keep items while condition true - O(n)
result = takewhile(lambda x: x < 5, data)
list(result)  # [1, 2, 3, 4]

# Drop items while condition true - O(n)
result = dropwhile(lambda x: x < 5, data)
list(result)  # [5, 6, 7, 8, 9]

# Opposite of filter - O(n)
even = filterfalse(lambda x: x % 2 == 0, data)
list(even)  # [1, 3, 5, 7, 9]
```

### Combinations & Permutations

```python
from itertools import combinations, permutations, product

# Combinations: O(C(n,r)) = O(n!/(r!(n-r)!))
combs = combinations('ABC', 2)
list(combs)  # [('A', 'B'), ('A', 'C'), ('B', 'C')]

# Permutations: O(P(n,r)) = O(n!/(n-r)!)
perms = permutations('ABC', 2)
list(perms)  # [('A', 'B'), ('A', 'C'), ('B', 'A'), ...]

# Product (cartesian): O(n*m*...)
prod = product('AB', '12')
list(prod)  # [('A','1'), ('A','2'), ('B','1'), ('B','2')]
```

### Grouping

```python
from itertools import groupby

# Group consecutive equal items - O(n)
data = [1, 1, 2, 2, 2, 3, 1, 1]
for key, group in groupby(data):
    print(key, list(group))
# 1 [1, 1]
# 2 [2, 2, 2]
# 3 [3]
# 1 [1, 1]

# With key function
data = ['apple', 'apricot', 'banana', 'blueberry']
for key, group in groupby(data, key=lambda x: x[0]):
    print(key, list(group))
# a ['apple', 'apricot']
# b ['banana', 'blueberry']
```

## Performance Tips

### Use itertools for Large Data

```python
# Bad: materializes all combinations O(n*m) memory
pairs = [(x, y) for x in range(1000) for y in range(1000)]

# Good: lazy generation O(1) memory
from itertools import product
pairs = product(range(1000), range(1000))
for x, y in pairs:
    process(x, y)
```

### Chain Multiple Iterators

```python
# Bad: convert to lists then concatenate O(n+m) memory
result = list(iter1) + list(iter2) + list(iter3)

# Good: chain lazily O(1) memory
from itertools import chain
result = chain(iter1, iter2, iter3)
for item in result:
    process(item)
```

### Window Operations

```python
from itertools import islice

# Create sliding window: O(n) items, O(w) memory
def window(iterable, size):
    it = iter(iterable)
    w = tuple(islice(it, size))
    yield w
    for item in it:
        w = w[1:] + (item,)
        yield w

for w in window(range(10), 3):
    print(w)  # (0,1,2), (1,2,3), (2,3,4), ...
```

## Version Notes

- **Python 2.6+**: Most functions available
- **Python 3.x**: All modern functions available
- **Python 3.10+**: Some optimization improvements

## Related Documentation

- [Collections Module](collections.md) - For data structures
- [Heapq Module](heapq.md) - For priority queues
- [Functools Module](functools.md) - For higher-order functions
