# abs() Function Complexity

The `abs()` function returns the absolute value of a number. It calls the
operand's `__abs__()`, so the cost is the operand type's: constant for a
`float` or `complex`, and linear in the width of a negative `int`.

## Complexity Analysis

For an integer operand, let `d` be its width in digits, proportional to
`x.bit_length()`. Space excludes the operand itself.

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Non-negative `int` | O(1) | O(1) | Returns `x` itself; an `int` subclass that inherits `__abs__` is copied into a plain `int`, O(d) |
| Negative `int` | O(d) | O(d) | Copies every digit with the sign flipped |
| `float` | O(1) | O(1) | Clears the sign bit into a new `float`, whatever the magnitude |
| `complex` | O(1) | O(1) | Returns the magnitude as a `float`; `OverflowError` when finite parts give a magnitude past float range |
| Any other type | `type(x).__abs__` | — | `Fraction`, `Decimal` and the rest delegate; a type without `__abs__` raises `TypeError` |

## Basic Usage

### Absolute Values

```python
# O(1) - a machine-word int or a float
abs(-5)        # 5
abs(5)         # 5
abs(0)         # 0
abs(-3.14)     # 3.14
abs(3.14)      # 3.14
```

### Complex Numbers

```python
# O(1) - the magnitude, computed as hypot(real, imag)
abs(3 + 4j)    # 5.0
abs(-3 + 4j)   # 5.0
abs(0j)        # 0.0

# hypot() does not square the parts first, so this stays finite
abs(1e200 + 1e200j)   # 1.414213562373095e+200

# Only the magnitude itself can overflow
try:
    abs(1.5e308 + 1.5e308j)
except OverflowError:
    pass       # absolute value too large
```

### Wide Integers

```python
# O(1) - a non-negative int comes back as the same object
big = 10**100
abs(big) is big        # True

# O(d) - a negative int is copied, digit by digit
abs(-big)              # 10**100, a new object
```

## Custom __abs__ Method

```python
# The cost is whatever __abs__ costs; abs() adds one call
class Distance:
    def __init__(self, value):
        self.value = value

    def __abs__(self):
        # O(1) for a machine-word value
        return abs(self.value)

d = Distance(-10)
result = abs(d)  # 10
```

## Performance Patterns

### Bulk Absolute Values

```python
# O(n) - n items, each O(1) for a machine-word int
numbers = [-5, 3, -2, 8, -1]
absolute = [abs(x) for x in numbers]

# Same with any numeric type
floats = [-1.5, 2.5, -3.5]
absolute = [abs(x) for x in floats]  # O(n)
```

### Distance Calculations

```python
# O(1) for machine-word coordinates - two subtractions and two absolute values
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
# abs() - clear, idiomatic
x = -5
result = abs(x)  # 5

# Manual - the same work: -x copies a negative int exactly as abs() does
result = x if x >= 0 else -x  # 5
```

Neither spelling has a better bound than the other: for a negative `int`,
`-x` makes the same copy `abs()` does. `abs()` is preferred for clarity, and
because it works for any type with an `__abs__()`.

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
# O(1) - a negative zero float loses its sign
abs(0)      # 0
abs(-0)     # 0
abs(0.0)    # 0.0
abs(-0.0)   # 0.0
```

### Extremes

```python
import sys

# O(d) - the negative value is copied; ints do not overflow
abs(-10**100)          # 10**100
abs(-sys.maxsize - 1)  # sys.maxsize + 1

# O(1) - a float's magnitude does not change the cost
abs(-1.7e308)          # 1.7e308
```

### Type Coercion

```python
# int and float keep their type; complex gives a float
abs(-5)          # int
abs(-5.0)        # float
abs(-5j)         # 5.0, a float

# A str has no __abs__
try:
    abs("-5")
except TypeError:
    pass         # bad operand type for abs(): 'str'
```

## Best Practices

✅ **Do**:

- Use `abs()` for absolute values
- Use in list comprehensions for bulk operations
- Use for distance/magnitude calculations
- Use for deviation analysis

❌ **Avoid**:

- Manual if/else checks (less readable, with the same bound)
- Assuming type compatibility

## Related Functions

- **[int](int.md)** - Arbitrary-precision integer arithmetic, including `-x`
- **[max()](max.md)** - Find maximum value
- **[min()](min.md)** - Find minimum value
- **[pow()](pow.md)** - Power function
- **[math.fabs()](../stdlib/math.md)** - Float absolute value
