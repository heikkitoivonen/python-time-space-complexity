# fractions Module Complexity

The `fractions` module provides support for rational number arithmetic, maintaining exact fractional values without floating-point rounding errors.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Fraction()` creation | O(log n) | O(log n) | GCD calculation, n = max numerator/denominator |
| `Fraction` arithmetic | O(log n) | O(log n) | GCD for result simplification |
| `Fraction` comparison | O(log n) | O(1) | Requires common denominator |
| `Fraction` conversion | O(1) or O(log n) | O(log n) | From int/float/string |
| `limit_denominator()` | O(k) | O(1) | k = max denominator |

## Basic Usage

### Creating Fractions

```python
from fractions import Fraction

# From integers - O(log n) for GCD
f1 = Fraction(3, 4)          # 3/4
f2 = Fraction(6, 8)          # Automatically reduces to 3/4
f3 = Fraction(2, 1)          # 2

# From string - O(log n) parsing and reduction
f4 = Fraction("1/3")         # 1/3
f5 = Fraction("0.25")        # 1/4

# From float - O(log n), may be imprecise
f6 = Fraction(0.5)           # 1/2
f7 = Fraction(0.1)           # 3602879701896397/36028797018963968 (approximation)

# From Decimal - O(log n)
from decimal import Decimal
f8 = Fraction(Decimal("0.25"))  # 1/4

# Copy - O(1)
f9 = Fraction(f1)            # 3/4
```

### Properties

```python
from fractions import Fraction

f = Fraction(7, 12)

# Numerator and denominator - O(1)
print(f.numerator)           # 7
print(f.denominator)         # 12

# Always in lowest terms
f2 = Fraction(14, 24)
print(f2.numerator)          # 7 (auto-reduced)
print(f2.denominator)        # 12

# Inverse - O(1)
f_inv = f.limit_denominator(1000)
```

## Arithmetic Operations

### Addition and Subtraction

```python
from fractions import Fraction

f1 = Fraction(1, 2)  # 1/2
f2 = Fraction(1, 3)  # 1/3

# Addition - O(log n) for GCD and reduction
f3 = f1 + f2         # 5/6 (common denominator: 6)

# Subtraction - O(log n)
f4 = f1 - f2         # 1/6

# With integers - O(log n)
f5 = f1 + 2          # 5/2
f6 = 3 - f2          # 8/3
```

### Multiplication and Division

```python
from fractions import Fraction

f1 = Fraction(2, 3)  # 2/3
f2 = Fraction(3, 4)  # 3/4

# Multiplication - O(log n) for reduction
f3 = f1 * f2         # 6/12 = 1/2 (auto-reduced)

# Division - O(log n)
f4 = f1 / f2         # (2/3) / (3/4) = 8/9

# Power - O(log n) per multiplication
f5 = f1 ** 2         # 4/9
f6 = f2 ** -1        # 4/3 (reciprocal)
```

### Modulo and Floor Division

```python
from fractions import Fraction

f1 = Fraction(7, 2)  # 3.5
f2 = Fraction(2, 1)  # 2

# Floor division - O(log n)
result = f1 // f2    # 1 (7/2 // 2 = 1)

# Modulo - O(log n)
remainder = f1 % f2  # Fraction(3, 2) (1.5)

# Divmod - O(log n)
div, mod = divmod(f1, f2)
print(div)           # 1
print(mod)           # 3/2
```

## Comparison Operations

### Equality and Ordering

```python
from fractions import Fraction

f1 = Fraction(1, 2)
f2 = Fraction(2, 4)  # Also 1/2
f3 = Fraction(1, 3)

# Equality - O(log n) or O(1) if already reduced
print(f1 == f2)      # True (both 1/2)
print(f1 == f3)      # False

# Ordering - O(log n) for cross-multiplication
print(f1 > f3)       # True (1/2 > 1/3)
print(f1 < f3)       # False
print(f1 <= f3)      # False

# With other types - O(log n)
print(f1 == 0.5)     # True
print(f1 > 0.3)      # True
```

## Conversion and Approximation

### Convert to Other Types

```python
from fractions import Fraction

f = Fraction(22, 7)  # π approximation

# To float - O(log n)
float_val = float(f)          # 3.142857...

# To int (floor division) - O(log n)
int_val = int(f)              # 3

# To string - O(log n)
str_val = str(f)              # '22/7'

# To tuple (numerator, denominator) - O(1)
num, denom = f.numerator, f.denominator
```

### Limit Denominator

```python
from fractions import Fraction

# Approximate with smaller denominator - O(k) where k = max_denominator
f = Fraction(22, 7)           # 22/7 ≈ 3.142857

# Limit to denominator 10
approx = f.limit_denominator(10)  # 22/7 (stays same)

# Limit to denominator 1 (nearest integer)
approx = Fraction(0.3).limit_denominator(1)  # 0/1

# Find simple fraction approximation
pi_approx = Fraction(3.14159).limit_denominator(100)
print(pi_approx)      # 355/113 (excellent π approximation)

# Approximate float
sqrt2 = Fraction(1.4142135623).limit_denominator(1000)
print(sqrt2)          # 1393/985
```

## Common Patterns

### Exact Decimal Computation

```python
from fractions import Fraction

# Problem: floating-point arithmetic has rounding errors
prices = [0.1, 0.2, 0.3]
total_float = sum(prices)
print(total_float)    # 0.6000000000000001 (wrong!)

# Solution: use Fractions for exact arithmetic
prices_frac = [Fraction(1, 10), Fraction(2, 10), Fraction(3, 10)]
total_frac = sum(prices_frac)
print(total_frac)     # 3/5 (exact)
print(float(total_frac))  # 0.6
```

### Continuous Fractions

```python
from fractions import Fraction

def continued_fraction(value, depth=10):
    """Generate continued fraction representation"""
    
    coefficients = []
    x = Fraction(value)
    
    for _ in range(depth):
        a = int(x)
        coefficients.append(a)
        
        x = x - a
        if x == 0:
            break
        
        x = 1 / x
    
    return coefficients

# √2 continued fraction
sqrt2_cf = continued_fraction(1.41421356, depth=5)
print(sqrt2_cf)  # [1, 2, 2, 2, 2]
```

### Rational Interpolation

```python
from fractions import Fraction

class RationalFunction:
    """Simple rational function evaluation"""
    
    def __init__(self, numerator, denominator):
        self.num = numerator  # List of Fraction coefficients
        self.den = denominator
    
    def evaluate(self, x):
        """Evaluate at x - O(n) for polynomial evaluation"""
        
        # Evaluate numerator polynomial
        num_val = sum(
            coef * (x ** i)
            for i, coef in enumerate(self.num)
        )
        
        # Evaluate denominator polynomial
        den_val = sum(
            coef * (x ** i)
            for i, coef in enumerate(self.den)
        )
        
        # O(log n) for GCD reduction
        return Fraction(num_val, den_val)

# f(x) = (2x + 1) / (x - 1)
func = RationalFunction(
    [Fraction(1), Fraction(2)],      # numerator: 1 + 2x
    [Fraction(-1), Fraction(1)]      # denominator: -1 + x
)

result = func.evaluate(Fraction(3, 1))  # (1 + 6) / (3 - 1) = 7/2
print(result)  # 7/2
```

## Performance Comparison

### Fractions vs Float

```python
from fractions import Fraction
import timeit

# Accumulation test
def test_float():
    result = 0.0
    for _ in range(1000):
        result += 0.1
    return result

def test_fraction():
    result = Fraction(0)
    for _ in range(1000):
        result += Fraction(1, 10)
    return result

# Float: faster, but inaccurate
float_result = test_float()
print(f"Float: {float_result}")  # 100.00000000000007

# Fraction: slower, but exact
frac_result = test_fraction()
print(f"Fraction: {frac_result}")  # 100

# Benchmark
float_time = timeit.timeit(test_float, number=1000)
frac_time = timeit.timeit(test_fraction, number=1000)

print(f"Float time: {float_time:.4f}s")      # Much faster
print(f"Fraction time: {frac_time:.4f}s")    # Slower
```

### Denominator Representation Size

```python
from fractions import Fraction

# Small denominators - fast
f1 = Fraction(1, 2)      # Small numbers
f2 = Fraction(1, 3)

result1 = f1 + f2        # O(log(small)) - fast
print(result1)           # 5/6

# Large denominators - slower
f3 = Fraction(1, 1000000)
f4 = Fraction(1, 999999)

result2 = f3 + f4        # O(log(large)) - slower
print(result2)           # 1999999/999999000000
```

## Memory Efficiency

### Denominator Growth

```python
from fractions import Fraction

# Denominator can grow large with operations
f = Fraction(1, 2)

# After many operations
for _ in range(10):
    f = f + Fraction(1, 7)

print(f.denominator)  # Can become very large

# Denominator growth can be managed with limit_denominator
f_limited = f.limit_denominator(1000)
print(f_limited)      # Simplified approximation
```

## When to Use Fractions

### Good For
- Financial calculations requiring exact arithmetic
- Rational number mathematics
- Avoiding floating-point errors in accumulation
- Scientific computations with exact ratios

```python
from fractions import Fraction

# Financial: exact currency operations
price1 = Fraction(10, 3)    # $3.33...
price2 = Fraction(20, 3)    # $6.66...
total = price1 + price2     # Exact $10
```

### Avoid When
- Performance-critical numerical code (use float)
- Large-scale scientific computing (use NumPy)
- Simple integer arithmetic
- When floating-point precision is acceptable

## Related Documentation

- [Decimal Module](decimal.md)
- [Math Module](math.md)
- [Numbers Module](numbers.md)
