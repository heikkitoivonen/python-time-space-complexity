# sum() Function Complexity

The `sum()` function returns the sum of all items in an iterable, optionally adding a start value.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Summing integers | O(n) | O(1) | Single pass, accumulation |
| Summing floats | O(n) | O(1) | Same as integers |
| Summing strings (concatenation) | O(n²) | O(n) | Avoid! Each concatenation copies; use ''.join() |
| With custom objects | O(n*k) | O(1) | k = __add__ time |

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
# O(n) - count 1s
count = sum([1 for x in range(100) if x % 2 == 0])  # 50 even numbers

# Better: use len() or sum with boolean
count = sum(1 for x in range(100) if x % 2 == 0)  # Still O(n)
```

### Computing Statistics

```python
# O(n) - single pass
numbers = [1, 2, 3, 4, 5]
total = sum(numbers)
average = total / len(numbers)

# Don't do this - O(2n)
average = sum(numbers) / len(numbers)  # Iterate twice
```

### Flattening Lists

```python
# O(n²) - inefficient!
# Each sum call is O(n), and we have n lists
nested = [[1, 2], [3, 4], [5, 6]]
flat = sum(nested, [])  # O(n²) - avoid this!

# Better approaches:
# O(n) - single iteration
from itertools import chain
flat = list(chain(*nested))

# O(n) - unpacking
flat = [item for sublist in nested for item in sublist]
```

## Performance Considerations

### Integer vs Float Arithmetic

```python
# Both O(n) but integers are slightly faster
sum([1, 2, 3, 4, 5])           # O(n) - integers
sum([1.0, 2.0, 3.0, 4.0, 5.0])  # O(n) - floats (slightly slower)
```

### Why Not for Strings

```python
# ❌ O(n²) - avoid!
# Each + creates new string and copies all data
text = ""
for word in ["a", "b", "c", "d", "e"]:
    text = text + word  # Creates new string each time

# ❌ Still O(n²) - sum with strings is also quadratic!
# text = sum(["a", "b", "c", "d", "e"], "")  # Don't use

# ✅ Best: O(n) with join
text = "".join(["a", "b", "c", "d", "e"])
```

## Working with Custom Objects

### Custom __add__ Method

```python
# O(n*k) where k = time for __add__
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
# Important: start value type must support __add__
result = sum([1, 2, 3], start=0)      # 6
result = sum([1, 2, 3], start=10)     # 16

# Start value is crucial for types
result = sum(["a", "b", "c"], start="")  # "abc" - O(n²)
result = sum(["a", "b", "c"])  # TypeError - can't add str + int
```

## Comparison with Alternatives

### vs Loop

```python
# sum() - O(n), clean, optimized
numbers = list(range(10000))
total = sum(numbers)

# Manual loop - O(n), same but more verbose
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

## Pitfalls

### Floating Point Precision

```python
# Summing floats can lose precision
numbers = [0.1] * 10
print(sum(numbers))  # 1.0000000000000007, not exactly 1.0

# Better: use decimal for financial calculations
from decimal import Decimal
numbers = [Decimal('0.1')] * 10
print(sum(numbers, Decimal('0')))  # Exact: 1.0
```

### Empty Sequence

```python
# sum() of empty is 0
result = sum([])  # 0

# Or start value
result = sum([], start=100)  # 100

# But TypeError with strings if no start
try:
    sum(["a", "b"])  # TypeError
except TypeError:
    pass

# Works with start=""
result = sum(["a", "b"], start="")  # "ab"
```

## Performance Notes

```python
# Timing comparison: sum vs alternatives

# O(n) - optimal for summing numbers
sum(range(1000000))

# O(n) but requires list creation first
__builtins__.sum(list(range(1000000)))

# O(n*log(n)) - much slower
sorted([1,2,3])[0] + sorted([1,2,3])[1]  # Don't do this

# O(n) - alternative using math.fsum for precision
from math import fsum
fsum([0.1] * 10)  # More precise for floats
```

## Best Practices

✅ **Do**:

- Use `sum()` for numeric aggregation
- Use generator expressions with `sum()` for memory efficiency
- Use `sum([], start=[])` with explicit start value
- Use `math.fsum()` when precision matters

❌ **Avoid**:

- `sum(nested_lists, [])` - O(n²) concatenation
- `sum(strings, "")` - inefficient string concatenation
- Forgetting start value (causes TypeError with non-numeric sequences)
- Summing booleans when `any()` or `all()` is clearer

## Related Functions

- **[any()](any.md)** - Check if any item is true
- **[all()](all.md)** - Check if all items are true
- **[max()](max.md)** - Find maximum value
- **[min()](min.md)** - Find minimum value
- **math.fsum()** - Precise float summation

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior, more consistent
- **Python 3.8+**: No changes to complexity
