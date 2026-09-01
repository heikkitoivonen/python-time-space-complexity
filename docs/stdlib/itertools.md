# Itertools Module Complexity

The `itertools` module provides efficient looping tools for creating iterators and combinations.

## Iterator Functions

### Creating Iterators

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `count(start, step)` | O(1) per item | O(1) | Infinite counter |
| `cycle(iterable)` | O(1) per item | O(n) | Stores copy of iterable |
| `repeat(obj, times)` | O(1) per item | O(1) | Repeat same item |
| `accumulate(iter, func)` | O(n) total | O(1) | Running totals/reductions |

### Filtering Iterators

| Function | Time | Space | Notes |
|----------|------|-------|-------|
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
| `starmap(func, iter)` | O(n) total | O(1) | Apply func(*args) for each args tuple |
| `tee(iterable, n)` | O(n) init | O(g + n) | n iterators sharing one buffer, so the copies do not multiply it. g = how far the leading iterator has run ahead of the trailing one, not how much has been consumed: iterators advanced in lockstep hold almost nothing |
| `batched(iterable, n)` | O(n) total | O(n) per batch | Group into n-sized tuples (Python 3.12+) |
| `pairwise(iterable)` | O(n) total | O(1) | Successive overlapping pairs (Python 3.10+) |

### Grouping & Windowing

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `groupby(iterable, key)` | O(n) total | O(1) | Group consecutive |
| `combinations(iterable, r)` | O(n + r + r×C(n,r)) total | O(n + r) init + O(r) per item | All r-combinations. Two costs land before any result does: the iterable is copied to a tuple, and an r-entry index array is allocated — `combinations((), 1_000_000)` yields nothing and still holds 8 MB. Nor does the result count bound the rest: C(n,1) and C(n,n-1) are both n results, and the second costs hundreds of times more. O(r) per result is an upper bound that is tight only when you keep the results, as `list()` does — that forces a fresh r-element copy each time. Drop each result before asking for the next and the tuple is refilled in place from the leftmost changed index onward, which is O(1) amortised |
| `combinations_with_replacement(iter, r)` | O(n + r + r×C(n+r-1,r)) total | O(n + r) init + O(r) per item | Combinations allowing repeats; same up-front input copy and r-entry index array |
| `permutations(iterable, r)` | O(n + r + r×P(n,r)) total | O(n + r) init + O(r) per item | All permutations; same up-front input copy, plus an n-entry indices array and an r-entry cycles array — which is where its O(n + r) setup comes from |
| `product(iter1, iter2, ...)` | O(k + Σnᵢ + k×n₁×n₂×...×nₖ) total | O(k + Σnᵢ) init + O(k) per item | Cartesian product; stores all inputs in memory first and keeps per-pool state, so a single empty pool makes the result set empty without making the setup free. Builds a k-tuple per result |

## Memory Characteristics

All itertools functions are lazy iterators, but some cache input data (e.g., `cycle`, `tee`, `product`).

```python
import itertools


def pred(value):
    return value % 2 == 0


numbers = range(10)
iter1, iter2 = iter("ab"), iter("cd")

# All of these are O(1) memory (lazy): none of them reads its input until you
# ask for an item, and none keeps more than the item it is handing back
c = itertools.count()                     # Infinite counter
f = itertools.filterfalse(pred, numbers)  # Filtered iterator
z = itertools.chain(iter1, iter2)         # Chained iterators
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

# Opposite of filter - O(n). filterfalse keeps what the predicate rejects,
# so an "is even" predicate leaves the odd numbers
odd = filterfalse(lambda x: x % 2 == 0, data)
list(odd)  # [1, 3, 5, 7, 9]
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
from itertools import product


def process(x, y):
    pass


# Bad: materializes all 1,000,000 pairs at once - O(n*m) memory
pairs = [(x, y) for x in range(1000) for y in range(1000)]

# Better: the 1,000,000 pairs are yielded one at a time and never all held.
# Not O(1) though - product() copies each input to a tuple before yielding
# anything, so this holds the 2,000 input values throughout: O(n + m)
pairs = product(range(1000), range(1000))
for x, y in pairs:
    process(x, y)
```

### Chain Multiple Iterators

```python
from itertools import chain


def process(item):
    pass


def source():
    return iter(range(1000))


# Bad: convert to lists then concatenate - O(n+m) memory
result = list(source()) + list(source()) + list(source())

# Good: chain lazily - O(1) memory, and it never builds the joined list
result = chain(source(), source(), source())
for item in result:
    process(item)
```

### Window Operations

```python
from itertools import islice

# Sliding window: n - w + 1 windows, O(w) memory, and O(n*w) time rather
# than O(n). Each window is a fresh w-tuple, so the windows alone are n*w
# items no matter how they are built: widening w from 2 to 256 at a fixed n
# costs about ten times as much, where O(n) would cost the same. Rebuilding
# with a deque instead of w[1:] + (item,) does not help, because the tuple()
# per window costs the same. Only yielding one reused deque, valid until the
# next iteration, is flat in w
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
- **Python 3.10+**: `pairwise()` added
- **Python 3.12+**: `batched()` added

## Related Documentation

- [Collections Module](collections.md) - For data structures
- [Heapq Module](heapq.md) - For priority queues
- [Functools Module](functools.md) - For higher-order functions
