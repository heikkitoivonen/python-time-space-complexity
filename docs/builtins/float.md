# Float Type Complexity

The `float` type represents floating-point numbers with fixed precision (64-bit IEEE 754 double).

## Arithmetic Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x + y` | O(1) | O(1) | IEEE 754 addition |
| `x - y` | O(1) | O(1) | Subtraction |
| `x * y` | O(1) | O(1) | Multiplication |
| `x / y` | O(1) | O(1) | Division |
| `x // y` | O(1) | O(1) | Floor division |
| `x % y` | O(1) | O(1) | Modulo |
| `x ** y` | O(1) | O(1) | Exponentiation |
| `divmod(x, y)` | O(1) | O(1) | Combined division |
| `abs(x)` | O(1) | O(1) | Absolute value |
| `-x` | O(1) | O(1) | Negation |

## Comparison Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x == y` | O(1) | O(1) | Equality check |
| `x < y` | O(1) | O(1) | Less than |
| `x > y` | O(1) | O(1) | Greater than |
| `x <= y` | O(1) | O(1) | Less or equal |
| `x >= y` | O(1) | O(1) | Greater or equal |
| `x != y` | O(1) | O(1) | Not equal |
| `x is y` | O(1) | O(1) | Object identity |

## Special Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hash(x)` | O(1) | O(1) | Hash value |
| `str(x)` | O(1) | O(1) | String conversion |
| `repr(x)` | O(1) | O(1) | Representation |
| `int(x)` | O(1) | O(1) | Convert to int |
| `float(x)` | O(1) | O(1) | Convert from other |
| `round(x, n)` | O(1) | O(1) | Round to n places |
| `math.floor(x)` | O(1) | O(1) | Floor |
| `math.ceil(x)` | O(1) | O(1) | Ceiling |
| `math.trunc(x)` | O(1) | O(1) | Truncate |

## Common Operations

### Basic Arithmetic

```python
# All operations are constant time (fixed 64-bit precision)
x = 3.14
y = 2.71

sum_result = x + y      # O(1)
product = x * y         # O(1)
quotient = x / y        # O(1)
exponent = x ** y       # O(1) - built-in, not iterative
```

### Rounding and Truncation

```python
import math

x = 3.14159

# All O(1)
rounded = round(x, 2)   # 3.14
floored = math.floor(x) # 3
ceiled = math.ceil(x)   # 4
truncated = math.trunc(x) # 3
```

### Comparison and Equality

```python
# All comparisons are O(1)
x = 1.0
y = 1.0

if x == y:              # O(1)
    pass
if x < y + 0.001:       # O(1)
    pass
```

## Precision and Limitations

### Fixed 64-bit Precision

```python
# IEEE 754 double precision (64 bits)
# - 1 sign bit
# - 11 exponent bits (range ~10^-308 to 10^308)
# - 52 mantissa bits (~15-17 decimal digits precision)

x = 0.1 + 0.2
print(x == 0.3)  # False! Precision loss

# Representation
print(f"{x:.20f}")  # 0.30000000000000004443
```

### Avoiding Precision Issues

```python
from decimal import Decimal

# Use Decimal for financial calculations
price = Decimal('0.10')
tax = Decimal('0.20')
total = price + tax  # Exact: 0.30

# Use math.isclose for float comparisons
import math
x = 0.1 + 0.2
if math.isclose(x, 0.3):  # Accounts for precision
    print("Equal within tolerance")
```

## Special Float Values

| Value | Representation | Notes |
|-------|-----------------|-------|
| Positive infinity | `float('inf')` | Larger than any number |
| Negative infinity | `float('-inf')` | Smaller than any number |
| Not a Number | `float('nan')` | Unordered, `nan != nan` |
| Zero | `0.0` or `-0.0` | Two representations |

```python
import math

x = float('inf')
y = float('nan')

# Infinity operations
print(x + 100)          # inf
print(x - x)            # nan (indeterminate)
print(x / x)            # nan

# NaN behavior - unordered
print(math.isnan(y))    # True
print(y == y)           # False (NaN != NaN always)
print(y < 5)            # False (unordered)
print(y > 5)            # False (unordered)
```

## Performance Characteristics

### Fixed-size Operations

```python
# All float operations are hardware-assisted - O(1)
import timeit

# Addition
timeit.timeit('1.5 + 2.5', number=1000000)

# Division
timeit.timeit('10.0 / 3.0', number=1000000)

# Complex computation
timeit.timeit('(1.5 + 2.5) * (10.0 / 3.0)', number=1000000)
```

### Type Conversion Overhead

```python
x = 5
y = 5.0

# int to float - O(1)
z = float(x)

# float to int - O(1)
w = int(y)

# Repeated conversions are still O(1) but can add up
for i in range(1000000):
    _ = float(i)  # O(1) each, O(n) total for loop
```

## Version Notes

- **Python 2.x**: Separate `int` and `float` division operators
- **Python 3.x**: Unified `/` operator always returns float
- **All versions**: Uses IEEE 754 double precision

## Related Types

- **[Int](int.md)** - Arbitrary precision integers
- **Complex** - Complex floating-point numbers
- **[Decimal](../stdlib/decimal.md)** - Arbitrary precision decimal
- **[Fraction](../stdlib/fractions.md)** - Rational numbers

## Best Practices

✅ **Do**:

- Use `float` for general numerical computation
- Use `math.isclose()` for float comparisons
- Use `round()` for display, not comparison

❌ **Avoid**:

- Comparing floats with `==` directly
- Assuming decimal representation is exact
- Using floats for financial calculations (use `Decimal`)
