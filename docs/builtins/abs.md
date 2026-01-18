# abs() Function Complexity

The `abs()` function returns the absolute value of a number.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Integer | O(1) | O(1) | Simple sign check |
| Float | O(1) | O(1) | IEEE 754 sign bit operation |
| Complex | O(1) | O(1) | Returns magnitude: sqrt(real² + imag²) |
| Custom class | O(k) | O(m) | Depends on `__abs__()` implementation |

## Basic Usage

### Absolute Values

```python
# O(1) - simple arithmetic
abs(-5)        # 5
abs(5)         # 5
abs(0)         # 0
abs(-3.14)     # 3.14
abs(3.14)      # 3.14
```

### Complex Numbers

```python
# O(1) - magnitude calculation
abs(3 + 4j)    # 5.0 (sqrt(3^2 + 4^2))
abs(-3 + 4j)   # 5.0
abs(0j)        # 0.0
```

## Custom __abs__ Method

```python
# O(k) where k = __abs__ time
class Distance:
    def __init__(self, value):
        self.value = value
    
    def __abs__(self):
        # O(1) - simple operation
        return abs(self.value)

d = Distance(-10)
result = abs(d)  # 10
```

## Performance Patterns

### Conditional Absolute Values

```python
# O(1) - all constant time
numbers = [-5, 3, -2, 8, -1]
absolute = [abs(x) for x in numbers]  # O(n) - n simple O(1) operations

# Same with any numeric type
floats = [-1.5, 2.5, -3.5]
absolute = [abs(x) for x in floats]  # O(n)
```

### Distance Calculations

```python
# O(1) - simple absolute value
def manhattan_distance(x1, y1, x2, y2):
    return abs(x1 - x2) + abs(y1 - y2)

# Usage
dist = manhattan_distance(0, 0, 3, 4)  # 7

# O(n) - for n points
points = [(1, 2), (3, 4), (5, 6)]
distances = [abs(p[0]) + abs(p[1]) for p in points]  # O(n)
```

## Comparison with Alternatives

### abs() vs Manual Check

```python
# abs() - O(1), clear, idiomatic
x = -5
result = abs(x)  # 5

# Manual - O(1), but unnecessary
result = x if x >= 0 else -x  # 5

# abs() is preferred for clarity
```

### abs() vs max()

```python
# Both O(1) for single value
abs(-5)      # 5
max(-5, 5)   # 5

# abs() is more direct for absolute value
# max() is for finding maximum of multiple items
```

## Use Cases

### Finding Deviations

```python
# O(n) - find deviation from target
target = 100
values = [95, 102, 98, 105, 99]
deviations = [abs(v - target) for v in values]
# [5, 2, 2, 5, 1]

# Find maximum deviation
max_deviation = max(abs(v - target) for v in values)  # 5
```

### Removing Sign

```python
# O(n) - strip negative signs
numbers = [-1, -2, -3, 4, 5]
unsigned = [abs(x) for x in numbers]
# [1, 2, 3, 4, 5]
```

### Comparing Magnitudes

```python
# O(1) - compare absolute values
a = -5
b = 3

if abs(a) > abs(b):
    print("a has larger magnitude")
```

## Edge Cases

### Zero

```python
# O(1)
abs(0)      # 0
abs(-0)     # 0
abs(0.0)    # 0.0
abs(-0.0)   # 0.0
```

### Extremes

```python
# O(1) - handles large numbers
abs(-10**100)  # Very large positive
abs(-sys.maxsize)  # Minimum integer
```

### Type Coercion

```python
# O(1) - works with numeric types
abs(-5)          # int
abs(-5.0)        # float
abs(-5j)         # complex (returns float)

# Not with strings
try:
    abs("-5")  # TypeError
except TypeError:
    pass
```

## Performance Notes

```python
# abs() is extremely fast - built-in C function
import timeit

# Timing shows abs() is optimized
t = timeit.timeit(lambda: abs(-5), number=10**7)
# Much faster than manual if/else due to C implementation
```

## Best Practices

✅ **Do**:

- Use `abs()` for absolute values
- Use in list comprehensions for bulk operations
- Use for distance/magnitude calculations
- Use for deviation analysis

❌ **Avoid**:

- Manual if/else checks (less readable)
- Using `max()` when `abs()` is clearer
- Assuming type compatibility

## Related Functions

- **[max()](max.md)** - Find maximum value
- **[min()](min.md)** - Find minimum value
- **[pow()](pow.md)** - Power function
- **math.fabs()** - Float absolute value

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior
- **Python 3.8+**: Consistent performance
