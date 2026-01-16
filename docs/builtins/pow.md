# pow() Function Complexity

The `pow()` function returns the power of a number with optional modulo operation.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| `pow(x, y)` small exponent | O(log y) | O(1) | Fast exponentiation |
| `pow(x, y)` large exponent | O(log y) | O(1) | Still logarithmic |
| `pow(x, y, z)` modular | O(log y * log z) | O(1) | Optimized for cryptography |
| Float exponentiation | O(1) | O(1) | Native operation |

## Basic Usage

### Integer Powers

```python
# O(log y) - exponentiation by squaring
pow(2, 3)      # 8
pow(2, 10)     # 1024
pow(2, 100)    # 1267650600228229401496703205376

# Negative exponents - returns float
pow(2, -1)     # 0.5
pow(2, -2)     # 0.25
```

### Float Powers

```python
# O(1) - native operation
pow(2.0, 3)    # 8.0
pow(2.5, 2)    # 6.25
pow(2.0, 0.5)  # 1.414... (square root)
pow(2.0, -1)   # 0.5
```

### Modular Exponentiation

```python
# O(log y * log z) - optimized algorithm
pow(2, 10, 1000)    # 24 (2^10 % 1000)
pow(3, 100, 7)      # 4 (3^100 % 7)
pow(2, 1000, 13)    # 3 (2^1000 % 13)

# Much faster than (base ** exp) % mod
# Avoids computing huge intermediate values
```

## Performance Analysis

### Exponentiation by Squaring

```
The algorithm works by:
1. If y is even: pow(x, y) = pow(x*x, y/2)
2. If y is odd: pow(x, y) = x * pow(x, y-1)

This reduces exponent from y to log(y) multiplications
```

### vs ** Operator

```python
# Both use same algorithm
2 ** 10        # 1024
pow(2, 10)     # 1024 - same complexity O(log y)

# Both are equivalent
x ** y == pow(x, y)  # True

# pow() with modulo is more efficient
(x ** y) % z   # O(log y) exponentiation + expensive modulo
pow(x, y, z)   # O(log y * log z) - keeps numbers small
```

## Common Patterns

### Powers of 10

```python
# O(log 10) - fast
pow(10, 2)     # 100
pow(10, 6)     # 1000000
pow(10, 100)   # 10^100

# Useful for scientific notation
factor = pow(10, 3)  # 1000
result = 5 * factor
```

### Powers of 2

```python
# O(log 2) - very fast
pow(2, 8)      # 256 (2^8)
pow(2, 16)     # 65536 (2^16)
pow(2, 32)     # 4294967296 (2^32)

# Can use bit shift for exact powers of 2
1 << 8  # 256 - even faster for powers of 2
```

### Cryptographic Operations

```python
# O(log y * log z) - RSA-like operations
# Compute c = m^e mod n efficiently
message = 42
exponent = 65537
modulus = 10**9 + 7

ciphertext = pow(message, exponent, modulus)
# O(log 65537 * log 10^9) - very efficient

# Without modulo: would create huge intermediate value
encrypted = (message ** exponent) % modulus  # Slower
```

### Modular Arithmetic

```python
# O(log y * log z)
a = pow(3, 100, 1000)  # 3^100 mod 1000
b = pow(7, 200, 1000)  # 7^200 mod 1000

# Useful for:
# - Cryptography
# - Number theory
# - Hash functions
# - Modular equations
```

## Performance Considerations

### Large Exponents

```python
# O(log y) - still fast for huge exponents
result = pow(2, 1000000)  # Computed efficiently

# Not O(y) - exponentiation by squaring makes it logarithmic
# This would be O(1000000) if done naively:
result = 2 * 2 * 2 * ... * 2  # 1000000 times

# pow() uses about 20 multiplications for 2^1000000
```

### Memory Usage

```python
# O(1) space - no intermediate lists
result = pow(2, 100)  # O(1) space

# Integer result may be large though
result = pow(2, 1000)  # Result has ~300 digits
```

## Edge Cases

### Zero Exponent

```python
# O(1) - always returns 1
pow(x, 0)      # 1
pow(0, 0)      # 1 (by convention in Python)
pow(-5, 0)     # 1
pow(2.5, 0)    # 1.0
```

### One Exponent

```python
# O(1) - returns base
pow(x, 1)      # x
pow(5, 1)      # 5
pow(2.5, 1)    # 2.5
```

### Zero Base

```python
# O(1)
pow(0, 5)      # 0
pow(0, 0)      # 1 (convention)
try:
    pow(0, -1)  # ZeroDivisionError
except ZeroDivisionError:
    pass
```

## Best Practices

✅ **Do**:
- Use `pow(x, y, z)` for modular exponentiation
- Use `pow(x, y)` or `x ** y` (equivalent for small values)
- Use for cryptographic operations (efficient algorithm)
- Remember O(log y) complexity - efficient even for large exponents

❌ **Avoid**:
- Computing `(x ** y) % z` - use `pow(x, y, z)` instead
- Naive exponentiation (multiply x by itself y times)
- Assuming O(y) complexity (it's O(log y))

## Related Functions

- **[abs()](abs.md)** - Absolute value
- **[math.pow()](../stdlib/math.md)** - Float-only power
- **[**  operator** - Exponentiation (equivalent)
- **[math.isqrt()](../stdlib/math.md)** - Integer square root

## Comparison with Alternatives

```python
# pow() is more efficient for modular exponentiation
x, y, z = 2, 100, 1000

# O(log y * log z) - fast
result1 = pow(x, y, z)

# O(log y) exponentiation + O(log z) modulo - slower
result2 = (x ** y) % z

# O(y) - very slow
result3 = (x * x * x * ... * x) % z  # 100 multiplications
```

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior and complexity
- **Python 3.8+**: Consistent performance across versions
