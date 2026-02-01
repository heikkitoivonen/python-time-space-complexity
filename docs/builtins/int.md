# Integer Type Complexity

The `int` type represents arbitrary precision integers. Python 3 has a single integer type that can represent numbers of any size.

## Arithmetic Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x + y` | O(n)* | O(n) | n = max bit length; O(1) for small ints |
| `x - y` | O(n)* | O(n) | n = max bit length; O(1) for small ints |
| `x * y` | O(n*m) to O(n^1.58)* | O(n+m) | Karatsuba for large numbers |
| `x // y` | O(n*m)* | O(n) | Long division algorithm |
| `x % y` | O(n*m)* | O(n) | Same as division |
| `x ** y` | O(log y * n²)* | O(result digits) | Binary exponentiation |
| `divmod(x, y)` | O(n*m)* | O(n) | Combined division |
| `abs(x)` | O(1) | O(1) | Sign flip only |
| `neg(x)` | O(1) | O(1) | Negate |
| `-x` | O(1) | O(1) | Unary minus |
| `+x` | O(1) | O(1) | Unary plus |

*Note: For small integers (fit in machine word), operations are O(1). Complexity shown is for arbitrary precision.

## Bit Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x & y` (bitwise AND) | O(min(n,m)) | O(min(n,m)) | Word-aligned |
| `x \| y` (bitwise OR) | O(max(n,m)) | O(max(n,m)) | Word-aligned |
| `x ^ y` (bitwise XOR) | O(max(n,m)) | O(max(n,m)) | Word-aligned |
| `~x` (bitwise NOT) | O(n) | O(n) | Invert bits |
| `x << n` | O(n) | O(n) | Shift left |
| `x >> n` | O(n) | O(n) | Shift right |
| `bin(x)` | O(n) | O(n) | Convert to binary |
| `hex(x)` | O(n) | O(n) | Convert to hex |
| `oct(x)` | O(n) | O(n) | Convert to octal |

## Comparison Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x == y` | O(n) | O(1) | Element-wise |
| `x < y` | O(n) | O(1) | Comparison |
| `x > y` | O(n) | O(1) | Comparison |
| `x <= y` | O(n) | O(1) | Comparison |
| `x >= y` | O(n) | O(1) | Comparison |
| `x != y` | O(n) | O(1) | Comparison |

## Special Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hash(x)` | O(1) | O(1) | Hash value |
| `str(x)` | O(n) | O(n) | Convert to string |
| `repr(x)` | O(n) | O(n) | String representation |
| `int(x)` | O(1) | O(1) | No-op if already int |

## Instance Methods

| Method | Time | Space | Notes |
|--------|------|-------|-------|
| `bit_length()` | O(1) | O(1) | Number of bits needed to represent value |
| `bit_count()` | O(n) | O(1) | Count of 1 bits (popcount); Python 3.10+ |
| `to_bytes(length, byteorder)` | O(n) | O(n) | Convert to bytes; n = length |
| `from_bytes(bytes, byteorder)` | O(n) | O(n) | Class method; create int from bytes |
| `as_integer_ratio()` | O(1) | O(1) | Returns (self, 1) tuple |
| `is_integer()` | O(1) | O(1) | Always returns True for int |
| `conjugate()` | O(1) | O(1) | Returns self; complex number compatibility |

## Numeric Attributes

| Attribute | Time | Notes |
|-----------|------|-------|
| `real` | O(1) | Returns self; real part |
| `imag` | O(1) | Always 0; imaginary part |
| `numerator` | O(1) | Returns self; for Rational interface |
| `denominator` | O(1) | Always 1; for Rational interface |

## Common Operations

### Basic Arithmetic

```python
# Addition - O(n) for large integers
a = 10**1000
b = 10**1000
result = a + b  # O(1000) operations

# Multiplication - O(n*m) or O(n²) with Karatsuba
x = 10**500
y = 10**500
result = x * y  # Efficient for large numbers

# Exponentiation - O(y*n²) with binary exponentiation
base = 2
exp = 1000
result = base ** exp  # O(log exp) multiplications
```

### Division and Modulo

```python
# Long division - O(n*m) complexity
dividend = 10**1000
divisor = 10**500
quotient, remainder = divmod(dividend, divisor)

# Modulo - same as division
remainder = 10**1000 % (10**500)  # O(1000 * 500)
```

### Bit Operations

```python
# Bit shifts - O(n) for n bits
x = 1 << 1000  # Shift left by 1000 - O(1000)
y = x >> 500   # Shift right by 500 - O(500)

# Bitwise operations - efficient
a = (1 << 100) - 1
b = (1 << 50) - 1
result = a & b  # O(50) - min of bit lengths
result = a | b  # O(100) - max of bit lengths
```

### Base Conversions

```python
# String conversion - O(n) for n digits
x = 10**1000
s = str(x)  # O(1000) - must process all digits

# Hexadecimal - O(n)
hex_str = hex(x)  # O(1000/4) ≈ O(250) (4 bits per hex digit)

# Binary - O(n)
bin_str = bin(x)  # O(1000) (1 bit per binary digit)
```

## Performance Characteristics

### Small Integers (CPython optimization)

```python
# Python caches small integers (-5 to 256)
a = 100
b = 100
print(a is b)  # True - same object!

# Large integers use arbitrary precision
x = 10**1000
y = 10**1000
print(x is y)  # False - different objects
```

### Arithmetic Complexity by Implementation

```python
# For small integers (fit in machine word) - O(1)
small = 1000 + 2000  # O(1)

# For large integers - O(n) to O(n²)
large = (10**10000) + (10**10000)  # O(10000)

# Multiplication is expensive for large numbers
product = (10**5000) * (10**5000)  # O(5000²) to O(5000*log(5000))
```

## Version Notes

- **Python 3.x**: All integers are arbitrary precision
- **Python 2.x**: Had `int` and `long` types (unified in 3.x)
- **CPython 3.11+**: Optimizations for arithmetic operations

## Implementation Details

### CPython

Uses variable-length representation for arbitrary precision:

- Small integers cached for performance
- Uses Karatsuba algorithm for large multiplication
- Bit operations are efficient (word-aligned)
- Division uses long division algorithm

### PyPy

Similar performance characteristics with JIT compilation helping with:

- Repeated operations
- Type stability

## Related Types

- **[Float](float.md)** - Fixed precision floating point
- **[Bool](bool.md)** - Boolean (subclass of int)
- **Complex** - Complex numbers
- **[Decimal](../stdlib/decimal.md)** - Arbitrary precision decimal

## Further Reading

- [CPython Internals: int](https://zpoint.github.io/CPython-Internals/BasicObject/long/long.html) -
  Deep dive into CPython's int implementation
