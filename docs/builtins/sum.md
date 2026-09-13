# sum() Function Complexity

The `sum()` function adds the items of an iterable to a start value, which
defaults to `0`. It makes one pass and one `+` per item, so the cost is the
number of items times the cost of one addition. That addition is constant for
machine-word integers and floats, linear in the width for wider integers, and
a copy of the whole running total for lists and tuples.

## Complexity Analysis

Let `n` be the number of items. Space excludes the iterable itself and
`start`.

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Exact `int` and `bool` items, running total within a machine word | O(n) | O(1) | Accumulated in a C integer |
| Wider `int` items | O(n·(w + log n)) | O(w + log n) | `w` = bits of the widest item or `start`; each `+` copies the running total, which is at most `log n` bits wider |
| `float` and `complex` items | O(n) | O(1) | `float` is accumulated in a C double, compensated from Python 3.12 |
| `list` or `tuple` items with a matching `start` | O(n·N) | O(N) | `N` = total elements, `start` included; each `+` copies the whole running total. Use `itertools.chain` |
| `str`, `bytes`, `bytearray` | — | — | Such a `start` raises `TypeError`; without one, `0 + "a"` raises. Use `''.join()` |
| Any other type | O(n·a) | O(1) auxiliary | `a` = cost of one `+`, done once per item; `sum()` holds only the running total |

## Basic Usage

### Summing Numbers

```python
# O(n) - single pass through items
numbers = [1, 2, 3, 4, 5]
total = sum(numbers)  # 15

# Works with any numeric iterable
total = sum([1.5, 2.5, 3.0])  # 7.0
total = sum(range(100))       # 4950
total = sum((10, 20, 30))     # 60

# With start value
total = sum([1, 2, 3], start=100)  # 106
```

### Generator Expressions

```python
# O(n) - evaluates generator once
total = sum(x for x in range(10))  # 45
total = sum(x**2 for x in range(5))  # 30

# More efficient than creating list first
total = sum(x for x in range(1000000))  # O(n) time, O(1) space

# vs creating list first
total = sum([x for x in range(1000000)])  # O(n) time, O(n) space
```

## Common Patterns

### Counting Items

```python
# O(n) time, O(n) space - list comprehension
count = sum([1 for x in range(100) if x % 2 == 0])  # 50 even numbers

# Better: sum with boolean (True=1, False=0) - O(n) time, O(1) space
count = sum(x % 2 == 0 for x in range(100))  # 50 even numbers
```

### Computing Statistics

```python
# O(n) - one pass for the sum, len() is O(1)
numbers = [1, 2, 3, 4, 5]
average = sum(numbers) / len(numbers)  # 3.0

# Two passes - counting by iterating again
average = sum(numbers) / sum(1 for _ in numbers)  # 3.0
```

### Flattening Lists

```python
# O(n*N) - n = number of lists, N = total items
# Each + copies every item accumulated so far
nested = [[1, 2], [3, 4], [5, 6]]
flat = sum(nested, [])  # [1, 2, 3, 4, 5, 6] - avoid this!

# Better approaches:
# O(N) - each item copied once
from itertools import chain
flat = list(chain.from_iterable(nested))

# O(N) - single pass, no repeated copying
flat = [item for sublist in nested for item in sublist]
```

## Performance Considerations

### Wide Integers

```python
# O(n) - machine-word ints are accumulated in C
total = sum(range(1000))  # 499500

# O(n*(w + log n)) - each + copies the running total, w = bits per item
wide = [10**300] * 1000
total = sum(wide)  # 1000 * 10**300
```

### Why Not for Strings

```python
# ❌ sum() refuses a str start outright
try:
    text = sum(["a", "b", "c"], "")
except TypeError:
    pass  # sum() can't sum strings [use ''.join(seq) instead]

# ❌ And without a start, the first + is 0 + "a"
try:
    text = sum(["a", "b", "c"])
except TypeError:
    pass  # unsupported operand type(s) for +: 'int' and 'str'

# ✅ O(total length) with join
text = "".join(["a", "b", "c", "d", "e"])  # "abcde"
```

The same applies to `bytes` and `bytearray`: use `b"".join()`.

## Working with Custom Objects

### Custom __add__ Method

```python
# O(n*m) where m = time for __add__
class Vector:
    def __init__(self, *components):
        self.components = components

    def __add__(self, other):
        # O(m) where m = number of components
        return Vector(*(a + b for a, b in zip(self.components, other.components)))

    def __repr__(self):
        return f"Vector{self.components}"

vectors = [Vector(1, 2), Vector(3, 4), Vector(5, 6)]
result = sum(vectors, Vector(0, 0))  # Vector(9, 12)
# Complexity: O(n*m) where n=3 vectors, m=2 components
```

### Default Start Value

```python
# The first + is start + item, and start defaults to 0
result = sum([1, 2, 3])            # 6
result = sum([1, 2, 3], start=10)  # 16

# Without a start, the first item is added to 0, so the type needs __radd__
class Vector:
    def __init__(self, *components):
        self.components = components

    def __add__(self, other):
        return Vector(*(a + b for a, b in zip(self.components, other.components)))

    def __radd__(self, other):
        return self if other == 0 else NotImplemented

result = sum([Vector(1, 2), Vector(3, 4)])  # Vector(4, 6), no start needed
```

## Comparison with Alternatives

### vs Loop

```python
# sum() - O(n)
numbers = list(range(10000))
total = sum(numbers)

# Manual loop - O(n), same bound
total = 0
for num in numbers:
    total += num

# Both have same complexity, sum() is preferred
```

### vs Accumulate

```python
from itertools import accumulate

# sum() - O(n), returns single value
numbers = [1, 2, 3, 4, 5]
total = sum(numbers)  # 15

# accumulate - O(n) but returns all intermediate sums
totals = list(accumulate(numbers))  # [1, 3, 6, 10, 15]
```

### vs math.fsum

```python
from math import fsum

# Both O(n). fsum() keeps every partial sum exactly; sum() carries
# one compensation term from Python 3.12, and none before it.
values = [0.1] * 10
fsum(values)  # 1.0 on every version
sum(values)   # 1.0 from 3.12; 0.9999999999999999 before
```

## Best Practices

✅ **Do**:

- Use `sum()` for numeric aggregation
- Use generator expressions with `sum()` for memory efficiency
- Use `math.fsum()` when float rounding matters

❌ **Avoid**:

- `sum(nested_lists, [])` - copies the whole running total at every step
- `sum(strings, "")` - raises `TypeError`; use `"".join()`

## Related Functions

- **[any()](any.md)** - Check if any item is true
- **[all()](all.md)** - Check if all items are true
- **[max()](max.md)** - Find maximum value
- **[min()](min.md)** - Find minimum value
- **[math.fsum()](../stdlib/math.md)** - Precise float summation

## Version Notes

- **Python 3.8+**: `start` can be passed as a keyword argument
- **Python 3.12+**: `float` items are summed with Neumaier compensation, so
  `sum([0.1] * 10) == 1.0`
