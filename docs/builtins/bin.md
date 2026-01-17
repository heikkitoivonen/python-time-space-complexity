# bin() Function Complexity

The `bin()` function returns the binary representation of an integer.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert integer | O(log n) | O(log n) | n = integer value; log n = number of bits |
| Negative integer | O(log n) | O(log n) | Adds '-0b' prefix |
| Large integer | O(b) | O(b) | b = number of bits = log₂(n) |

*Note: The complexity is O(log n) where n is the numeric value, which equals the number of bits needed to represent the number.*

## Basic Usage

### Decimal to Binary

```python
# O(log n) - where n = integer value
bin(0)      # '0b0'
bin(1)      # '0b1'
bin(2)      # '0b10'
bin(3)      # '0b11'
bin(8)      # '0b1000'
bin(255)    # '0b11111111'
```

### Negative Numbers

```python
# O(log n) - shows magnitude with minus
bin(-1)     # '-0b1'
bin(-8)     # '-0b1000'
bin(-255)   # '-0b11111111'
```

### Large Integers

```python
# O(log n) - number of binary digits
bin(2**10)    # '0b10000000000'
bin(2**32)    # '0b100000000000000000000000000000000'

# Arbitrary precision
big = 2**100
bin(big)  # O(100) - 100+ binary digits
```

## Complexity Details

### Logarithmic Time

Conversion time grows with the number of bits:

```python
# Small number - few bits
bin(3)      # '0b11' - 2 bits, O(log 3) = O(2)

# Large number - many bits
bin(2**64 - 1)  # 64 bits
                # O(log(2**64)) = O(64)

# Relationship: binary digits = log₂(n)
import math
value = 255
digits = len(bin(value)) - 2  # Subtract '0b'
assert digits == value.bit_length()
```

## Common Patterns

### Bit Manipulation

```python
# O(log n) - understand bit patterns
x = 42
print(bin(x))  # '0b101010'

# Check individual bits
def has_bit_set(value, bit_pos):
    return bool(value & (1 << bit_pos))

value = 0b1010  # 10 in decimal
print(has_bit_set(value, 0))  # False (bit 0)
print(has_bit_set(value, 1))  # True (bit 1)
```

### Debugging Bitwise Operations

```python
# O(log n) - show results clearly
a = 0b1100
b = 0b1010

print(f"a = {bin(a)}")           # a = 0b1100
print(f"b = {bin(b)}")           # b = 0b1010
print(f"a & b = {bin(a & b)}")   # a & b = 0b1000
print(f"a | b = {bin(a | b)}")   # a | b = 0b1110
print(f"a ^ b = {bin(a ^ b)}")   # a ^ b = 0b0110
print(f"~a = {bin(~a)}")         # ~a = -0b1101
```

### Binary String to Integer

```python
# O(log n) - parse binary string
binary_str = "0b1010"
value = int(binary_str, 2)  # O(log n)
assert value == 10

# Without prefix
value = int("1010", 2)  # Also O(log n)
assert value == 10
```

## Comparison with Alternatives

### bin() vs format()

```python
# bin() - returns string with '0b' prefix
bin(255)           # '0b11111111'

# format() - more flexible
format(255, 'b')   # '11111111' (no prefix)
format(255, '#b')  # '0b11111111' (with prefix)

# Performance - both O(log n), similar speed
```

### bin() vs bit_length()

```python
# bin() - string representation, O(log n)
s = bin(255)        # '0b11111111'

# bit_length() - O(1) operation
bits = (255).bit_length()  # 8

# Use bit_length() for count, bin() for display
```

## Bit Manipulation Operations

```python
# All O(1) in Python (fixed size, usually)
x = 0b1100  # 12
y = 0b1010  # 10

# Bitwise AND
result = x & y  # 0b1000 (8)
print(bin(result))  # '0b1000'

# Bitwise OR
result = x | y  # 0b1110 (14)
print(bin(result))  # '0b1110'

# Bitwise XOR
result = x ^ y  # 0b0110 (6)
print(bin(result))  # '0b110'

# Bitwise NOT (inverts all bits)
result = ~x     # -(13) due to two's complement
print(bin(result))  # '-0b1101'

# Left shift
result = x << 2  # 0b110000 (48)
print(bin(result))  # '0b110000'

# Right shift
result = x >> 1  # 0b110 (6)
print(bin(result))  # '0b110'
```

## Performance Patterns

### Batch Conversion

```python
# O(n * log m) - n numbers, each ~m value
numbers = list(range(100))
binary_values = [bin(n) for n in numbers]
# O(100 * log 100)

# vs direct method
binary_values = [f"{n:b}" for n in numbers]
# Similar, might be slightly faster with format
```

### Counting Set Bits

```python
# O(log n) - using bin()
def count_bits_bin(value):
    return bin(value).count('1')

# Better - O(1) with bit_count()
def count_bits_optimal(value):
    return value.bit_count()  # Python 3.10+

# Both give same result, bit_count() is faster
assert count_bits_bin(0b101010) == count_bits_optimal(0b101010)
```

## Practical Examples

### Permission Flags

```python
# O(log n) - display permission bits
READ = 0b100
WRITE = 0b010
EXECUTE = 0b001

permissions = READ | WRITE  # 0b110 (read + write)
print(bin(permissions))      # '0b110'

# Check if permission set
has_read = bool(permissions & READ)
has_write = bool(permissions & WRITE)
has_execute = bool(permissions & EXECUTE)
```

### IP Address Manipulation

```python
# O(log n) - work with IP octets
ip = "192.168.1.1"
octets = [int(x) for x in ip.split('.')]

# Show first octet in binary
print(bin(octets[0]))  # '0b11000000' (192)

# Network mask
mask = 0b11111111_11111111_11111111_00000000  # /24
print(bin(mask))
```

### Set Operations with Bits

```python
# O(log n) - use integers as efficient sets
SET_SIZE = 8  # Can represent 0-7

# Add elements (set bits)
my_set = 0  # Empty set
my_set |= (1 << 3)  # Add 3
my_set |= (1 << 5)  # Add 5

print(bin(my_set))  # '0b101000'

# Check membership
print(bool(my_set & (1 << 3)))  # True (has 3)
print(bool(my_set & (1 << 2)))  # False (no 2)

# Remove element (clear bit)
my_set &= ~(1 << 3)
print(bin(my_set))  # '0b100000'
```

## Special Cases

### Zero

```python
# O(1)
bin(0)  # '0b0'
```

### Powers of Two

```python
# O(log n) - shows single bit set
bin(1)      # '0b1'
bin(2)      # '0b10'
bin(4)      # '0b100'
bin(8)      # '0b1000'
bin(2**10)  # Single '1' followed by zeros
```

### All Ones

```python
# O(log n) - all bits set
bin(0xFF)      # '0b11111111' (255)
bin(0xFFFF)    # 16 ones
bin((1 << 32) - 1)  # 32 ones
```

## Best Practices

✅ **Do**:
- Use `bin()` for debugging bitwise operations
- Use `format(value, 'b')` if you don't need '0b' prefix
- Use `bit_length()` or `bit_count()` for counting
- Use `int(binary_str, 2)` to parse binary

❌ **Avoid**:
- Using `bin()` for very frequent operations (cache result)
- Assuming binary operations are faster than regular ops
- Building binary from decimal without understanding conversion
- Forgetting the '0b' prefix when parsing with `int()`

## Related Functions

- **[hex()](hex.md)** - Hexadecimal representation
- **[oct()](oct.md)** - Octal representation
- **[int().bit_length()](int.md)** - Number of bits needed
- **[int().bit_count()](int.md)** - Count set bits (Python 3.10+)
- **[format()](format.md)** - Format with specifications

## Version Notes

- **Python 2.x**: Works with int and long
- **Python 3.x**: Works with arbitrary precision integers
- **Python 3.10+**: Added `int.bit_count()` for bit counting
- **All versions**: Returns string with '0b' prefix
