# Integer Type Complexity

The `int` type represents arbitrary precision integers. Python 3 has a single integer type that can represent numbers of any size.

CPython stores an int as a sequence of 30-bit digits, so costs below are given in the operands' bit lengths: n is the bit length of `x` and m the bit length of `y`. A value whose magnitude is below 2^30 is a single digit, and every operation on two such values is O(1). Space bounds cover the result and temporaries, not the operands. An operation that "returns `x` itself" does so for an exact int; an instance of a subclass that inherits the operation gets a copy, O(n).

## Arithmetic Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x + y` | O(max(n, m)) | O(max(n, m)) | One pass with carry |
| `x - y` | O(max(n, m)) | O(max(n, m)) | Same as addition |
| `x * y` | O(n * m) | O(n + m) | Schoolbook. Karatsuba once both operands exceed 70 digits (2,100 bits), or 140 for `x * x`: O(n^1.58) for equal widths, and O(n * m^0.58) for n > m, where the wider operand is multiplied in m-bit slices |
| `x // y`, `x % y`, `divmod(x, y)` | O(q * m) | O(n + m) | Schoolbook, q = max(n - m, 0) + 1 quotient bits: O(n) for a one-digit divisor, O(m) for equal widths, O(1) when 0 <= x < y and x has fewer digits or a smaller top digit, O(m) when the top digits match (a negative x below y still allocates an m-bit remainder). 3.12+: O(n^1.58) divide-and-conquer once the divisor exceeds 300 digits and the quotient 150 |
| `x / y` | O(n + m) | O(n) | True division rounds to a float, so only the leading 55 bits of the quotient are computed; O(1) when both operands fit in a float exactly |
| `x ** y` | O(r²) | Θ(r) | For abs(x) >= 2 and y > 0, with r = result bits, about n * y. Bases 0, 1 and -1 cost O(m), a negative y returns a float in O(1); see [pow()](pow.md) for the three-argument form |
| `abs(x)` | O(n) | O(n) | Copies a negative operand with the sign flipped; returns `x` itself when it is non-negative |
| `-x` | O(n) | O(n) | Copies the digits with the sign flipped; O(1) for a one-digit value |
| `+x` | O(1) | O(1) | Returns `x` itself |

## Bit Operations

s is the shift count.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x & y` | O(min(n, m)) | O(min(n, m)) | For non-negative operands; a negative operand is complemented first, O(max(n, m)) |
| `x \| y` | O(max(n, m)) | O(max(n, m)) | |
| `x ^ y` | O(max(n, m)) | O(max(n, m)) | |
| `~x` | O(n) | O(n) | Computes `-(x + 1)` |
| `x << s` | O(n + s) | O(n + s) | The result is n + s bits wide |
| `x >> s` | O(n - s) | O(n - s) | For a non-negative x the result is n - s bits wide, O(1) once s >= n; a negative x costs O(n) |
| `bin(x)`, `hex(x)`, `oct(x)` | O(n) | O(n) | A power-of-two base maps bits straight to characters; `format(x, 'x')` and `f"{x:b}"` take the same path |

## Comparison Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x == y`, `x != y` | O(n) | O(1) | O(1) when the bit lengths differ; otherwise digit by digit from the top |
| `x < y`, `x <= y`, `x > y`, `x >= y` | O(n) | O(1) | The digit count decides first, then the digits |

## Special Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hash(x)` | O(n) | O(1) | O(1) for a one-digit value |
| `str(x)`, `repr(x)`, `f"{x}"` | O(n²) | O(n) | Each 30-bit digit is folded into a growing base-10⁹ array. 3.12+: O(n^1.58) divide-and-conquer above 1,000 digits (30,000 bits). Raises `ValueError` beyond `sys.get_int_max_str_digits()`, 4,300 decimal digits by default |
| `int(x)` | O(1) | O(1) | Returns `x` itself |
| `bool(x)` | O(1) | O(1) | |

## Instance Methods

| Method | Time | Space | Notes |
|--------|------|-------|-------|
| `bit_length()` | O(1) | O(1) | Digit count plus the width of the top digit |
| `bit_count()` | O(n) | O(1) | Population count over every digit; Python 3.10+ |
| `to_bytes(length, byteorder)` | O(length) | O(length) | `OverflowError` when x does not fit in `length` bytes |
| `from_bytes(bytes, byteorder)` | O(len(bytes)) | O(len(bytes)) | Class method |
| `as_integer_ratio()` | O(1) | O(1) | Returns `(x, 1)` with `x` itself as the numerator |
| `is_integer()` | O(1) | O(1) | Always `True`; Python 3.12+ |
| `conjugate()` | O(1) | O(1) | Returns `x` itself |

## Numeric Attributes

| Attribute | Time | Notes |
|-----------|------|-------|
| `real` | O(1) | Returns `x` itself |
| `imag` | O(1) | Always `0` |
| `numerator` | O(1) | Returns `x` itself; for the Rational interface |
| `denominator` | O(1) | Always `1`; for the Rational interface |

## Common Operations

### Basic Arithmetic

```python
# Addition - one pass over the wider operand, O(max(n, m))
a = 10**1000
b = 10**1000
result = a + b

# Multiplication - O(n * m) schoolbook below 2,100 bits per operand,
# O(n^1.58) Karatsuba above it
x = 10**500
y = 10**500
result = x * y  # 1,661 bits each: schoolbook

# Exponentiation - O(r²) in the result width, not O(log y)
base = 2
exp = 1000
result = base ** exp  # O(log exp) multiplications, each on a wider value
```

### Division and Modulo

```python
# Schoolbook division - O((n - m) * m): quotient bits times divisor bits
dividend = 10**1000
divisor = 10**500
quotient, remainder = divmod(dividend, divisor)

# Modulo - same algorithm, same cost
remainder = dividend % divisor

# A one-digit divisor is a single pass - O(n)
remainder = dividend % 7
```

### Bit Operations

```python
# Shifts - the result's width is the cost
x = 1 << 1000  # O(1000)
y = x >> 500   # O(500): the bits that survive

# Bitwise operations on non-negative operands
a = (1 << 100) - 1
b = (1 << 50) - 1
result = a & b  # O(50) - min of bit lengths
result = a | b  # O(100) - max of bit lengths
```

### Base Conversions

```python
# Decimal - O(n²): each 30-bit digit is folded into a growing base-10⁹ array
x = 10**1000
s = str(x)  # 1,001 characters, quadratic in the bit length

# Hexadecimal and binary - O(n): 4 bits or 1 bit per character, no carries
hex_str = hex(x)
bin_str = bin(x)
```

### Decimal Conversion Limit

```python
import sys

# str() and int() in base 10 are quadratic, so CPython caps them
x = 10**5000
try:
    str(x)  # 5,001 digits exceeds sys.get_int_max_str_digits()
except ValueError:
    pass

# Power-of-two bases are linear and uncapped
hex_str = hex(x)
parsed = int("f" * 10000, 16)

# Raise or remove the cap when the size is trusted, and put it back
limit = sys.get_int_max_str_digits()
sys.set_int_max_str_digits(0)
try:
    assert len(str(x)) == 5001
finally:
    sys.set_int_max_str_digits(limit)
```

## Performance Characteristics

### Small Integers (CPython optimization)

```python
# Python preallocates the integers -5 to 256 and returns the shared object
a = int("100")
b = int("100")
print(a is b)  # True - same object

# Every other parse allocates a new object
x = int("300")
y = int("300")
print(x is y)  # False - different objects

# Two equal literals in one function are one constant, folded by the
# compiler, so `300 is 300` would say True for a different reason
```

### Arithmetic Complexity by Implementation

```python
# One-digit integers, below 2**30 in magnitude - O(1)
small = 1000 + 2000

# Wide integers - linear in the bit length
large = (10**10000) + (10**10000)

# Multiplication grows faster than the operands
product = (10**5000) * (10**5000)  # 16,610 bits each: Karatsuba, O(n^1.58)
```

## Version Notes

- **Python 3.x**: All integers are arbitrary precision
- **Python 2.x**: Had `int` and `long` types (unified in 3.x)
- **Python 3.10**: `bit_count()` added
- **Python 3.11** (backported to 3.10.7): decimal string conversion is capped; `sys.set_int_max_str_digits()` adjusts the limit
- **Python 3.12**: `is_integer()` added; decimal conversion in both directions and huge divisions switch to O(n^1.58) divide-and-conquer algorithms above the thresholds in the tables

## Implementation Details

### CPython

Uses variable-length representation for arbitrary precision:

- 30-bit digits
- The integers -5 to 256 are preallocated and shared
- Karatsuba multiplication once both operands exceed 70 digits, or 140 when squaring
- Schoolbook division, with a divide-and-conquer fallback for huge operands from 3.12
- Decimal string conversion is quadratic and capped, power-of-two bases are linear and uncapped

### PyPy

Similar performance characteristics with JIT compilation helping with:

- Repeated operations
- Type stability

## Related Types

- **[Float](float.md)** - Fixed precision floating point
- **[Bool](bool.md)** - Boolean (subclass of int)
- **[Complex](complex_func.md)** - Complex numbers
- **[Decimal](../stdlib/decimal.md)** - Arbitrary precision decimal

## Further Reading

- [CPython Internals: int](https://zpoint.github.io/CPython-Internals/BasicObject/long/long.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's int implementation
