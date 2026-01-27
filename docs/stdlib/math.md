# math Module Complexity

The `math` module provides fast floating-point math functions and a few integer-specific helpers.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.sqrt(x)` | O(1) | O(1) | Floating-point operation |
| `math.log(x[, base])` | O(1) | O(1) | Floating-point operation |
| `math.sin/cos/tan(x)` | O(1) | O(1) | Floating-point operation |
| `math.hypot(*coords)` | O(n) | O(1) | n = number of coordinates |
| `math.fsum(iterable)` | O(n) | O(1) | Accurate summation of n values |
| `math.isclose(a, b)` | O(1) | O(1) | Floating-point comparison |
| `math.gcd(a, b)` | Varies | O(1) | Depends on integer size |
| `math.lcm(a, b)` | Varies | O(1) | Depends on integer size |
| `math.factorial(n)` | Varies | Varies | Big-int cost grows with n |
| `math.comb(n, k)` | Varies | Varies | Big-int cost grows with n and k |
| `math.perm(n, k)` | Varies | Varies | Big-int cost grows with n and k |

!!! warning "Floating-point precision"
    Most `math` functions operate on binary floating-point numbers. Results are fast but may be imprecise
    for some decimal fractions. Use `decimal` for exact decimal arithmetic.

## Common Operations

### Basic Transcendentals

```python
import math

x = 2.0

# O(1)
root = math.sqrt(x)
log2 = math.log(x, 2)
angle = math.sin(math.pi / 6)
```

### Hypotenuse and Distance

```python
import math

# O(n) in number of coordinates
r2 = math.hypot(3.0, 4.0)          # 5.0
r3 = math.hypot(1.0, 2.0, 2.0)     # 3.0
```

### Accurate Summation

```python
import math

values = [1e100, 1.0, -1e100]

# Regular sum may lose precision
regular = sum(values)       # 0.0

# fsum keeps extra precision
accurate = math.fsum(values)  # 1.0
```

### Integers: gcd, lcm, factorial, comb, perm

```python
import math

# gcd/lcm
g = math.gcd(84, 30)   # 6
l = math.lcm(6, 10)    # 30

# factorial, combinations, permutations
f = math.factorial(10)     # 3628800
c = math.comb(10, 3)       # 120
p = math.perm(10, 3)       # 720
```

### Robust Comparisons

```python
import math

# Avoid direct equality for floats
math.isclose(0.1 + 0.2, 0.3)  # True
```

## Performance Notes

- Floating-point operations are typically constant time and CPU-bound.
- Integer-heavy functions (`factorial`, `comb`, `perm`, `gcd`, `lcm`) scale with operand size.
- `fsum` provides better accuracy with a small constant-factor cost over `sum`.

## Related Modules

- [cmath Module](cmath.md) - Complex-number math
- [decimal Module](decimal.md) - Decimal arithmetic
- [fractions Module](fractions.md) - Rational arithmetic
- [statistics Module](statistics.md) - Descriptive statistics
- [random Module](random.md) - Random numbers
