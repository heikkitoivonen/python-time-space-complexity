# round() Function Complexity

The `round()` function rounds a number to the nearest integer or a specified number of decimal places.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Round to nearest integer | O(1) | O(1) | Single arithmetic operation |
| Round to n decimals | O(1) | O(1) | Fixed precision operation |
| Banker's rounding (.5) | O(1) | O(1) | Round to nearest even |

## Basic Usage

### Rounding Integers

```python
# O(1) - simple arithmetic
round(5.5)     # 6
round(5.4)     # 5
round(4.5)     # 4 (banker's rounding - rounds to even)
round(-5.5)    # -6
round(-4.5)    # -4
```

### Rounding to Decimals

```python
# O(1) - fixed precision
round(3.14159, 2)      # 3.14
round(2.675, 2)        # 2.67 (banker's rounding)
round(1.234567, 3)     # 1.235
round(10.12345, 1)     # 10.1
```

### Banker's Rounding

```python
# O(1) - rounds to nearest even when exactly at .5
round(0.5)     # 0 (nearest even)
round(1.5)     # 2 (nearest even)
round(2.5)     # 2 (nearest even)
round(3.5)     # 4 (nearest even)

# This is IEEE 754 standard rounding
```

## Performance Patterns

### Rounding Collections

```python
# O(n) - rounding multiple values
numbers = [1.234, 5.678, 2.345, 8.901]
rounded = [round(x, 2) for x in numbers]  # O(n)

# Same with map
rounded = list(map(lambda x: round(x, 2), numbers))  # O(n)
```

### Precision Loss

```python
# O(1) but be aware of floating point precision
result = round(2.675, 2)  # 2.67 not 2.68!
# This is due to float representation, not round()

# For financial calculations use Decimal
from decimal import Decimal
result = round(Decimal("2.675"), 2)  # Decimal("2.68")
```

## Common Patterns

### Display Formatting

```python
# O(1) - round for display
price = 19.99
tax = price * 0.08  # 1.5992...
total = round(price + tax, 2)  # 21.59

# Note: round() for display, not calculation
```

### Rounding to Powers of 10

```python
# O(1) - round to nearest 10, 100, etc.
value = 1234.5

round(value, -1)   # 1230.0 (nearest 10)
round(value, -2)   # 1200.0 (nearest 100)
round(value, -3)   # 1000.0 (nearest 1000)

# Negative digits round left of decimal
```

### Statistical Rounding

```python
# O(n) - round measurements
measurements = [1.234, 1.256, 1.267, 1.278]
rounded = [round(m, 2) for m in measurements]
# [1.23, 1.26, 1.27, 1.28]
```

## Comparison with Alternatives

### round() vs int()

```python
# round() - rounds to nearest
round(5.6)     # 6
int(5.6)       # 5 - truncates

# round() - handles negative
round(-5.6)    # -6
int(-5.6)      # -5

# Different behaviors
round(5.5)     # 6 (banker's rounding)
int(5.5)       # 5 (truncation)
```

### round() vs Decimal

```python
# round() - float precision issues
round(2.675, 2)  # 2.67 (not 2.68!)

# Decimal - precise
from decimal import Decimal
Decimal("2.675").quantize(Decimal("0.01"))  # Decimal("2.68")

# Use Decimal for financial calculations
```

### round() vs Format String

```python
# round() - returns number
x = 3.14159
rounded = round(x, 2)  # 3.14 (float)

# Format string - returns string
formatted = f"{x:.2f}"  # "3.14" (string)

# round() for calculation, format for display
```

## Edge Cases

### Zero

```python
# O(1)
round(0)       # 0
round(0.0)     # 0
round(0.5)     # 0 (banker's rounding to even)
```

### Very Small Numbers

```python
# O(1)
round(0.0001, 4)   # 0.0001
round(0.0001, 3)   # 0.0
round(1e-10, 10)   # 1e-10
```

### Very Large Numbers

```python
# O(1) - but may lose precision
round(1e20, 2)     # 1e+20
round(123456789.123, 2)  # 123456789.12
```

## Floating Point Pitfalls

```python
# Be aware of float representation issues
round(2.675, 2)    # 2.67 (not 2.68!)
# Float representation: 2.675 is actually 2.6749999...

# For exact rounding use Decimal
from decimal import Decimal, ROUND_HALF_UP

result = float(Decimal("2.675").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
# 2.68 - exact
```

## Performance Notes

```python
# round() is very fast - O(1) operation
import timeit

# Timing comparison
t_round = timeit.timeit(lambda: round(3.14159, 2), number=10**7)
t_format = timeit.timeit(lambda: f"{3.14159:.2f}", number=10**7)

# round() is typically faster for computation
# format is better for display
```

## Best Practices

✅ **Do**:

- Use `round()` for numeric rounding
- Use `Decimal` for financial calculations
- Use `f"{x:.2f}"` for display formatting
- Remember banker's rounding behavior
- Use negative digits for rounding to powers of 10

❌ **Avoid**:

- Using `round()` for financial calculations (precision issues)
- Assuming traditional rounding (0.5 rounds up) - Python uses banker's
- Relying on exact float precision
- Using `round()` for display (use format strings)

## Related Functions

- **[int()](int.md)** - Convert to integer (truncates)
- **[abs()](abs.md)** - Absolute value
- **[decimal.Decimal](../stdlib/decimal.md)** - Precise decimal arithmetic
- **[format()](format.md)** - Format numbers for display

## Version Notes

- **Python 2.x**: Traditional rounding (0.5 rounds away from zero)
- **Python 3.x**: Banker's rounding (0.5 rounds to nearest even)
- **Python 3.8+**: Consistent banker's rounding behavior
