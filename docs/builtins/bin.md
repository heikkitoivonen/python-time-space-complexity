# bin() Function Complexity

The `bin()` function returns the binary representation of an integer.
It writes one character per binary digit, so its time and the size of the
string it returns are both linear in the integer's number of binary digits.

`n` is the integer's absolute value and `b` is the number of binary digits in
the result: `n.bit_length()`, about log₂ n, or 1 for zero.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert integer | O(log n) | O(log n) | O(b): one character per binary digit |
| Negative integer | O(log n) | O(log n) | Adds '-0b' prefix |
| Large integer | O(b) | O(b) | Not limited by `sys.set_int_max_str_digits()`, which exempts power-of-two bases |
| Object with `__index__` | `__index__` + O(b) | `__index__` + O(b) | Any other non-int, such as a float, raises `TypeError` |

## Basic Usage

### Decimal to Binary

```python
# O(log n)
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
bin(big)  # O(b) - b = 101 binary digits
```

## Complexity Details

### Logarithmic Time

Conversion time grows with the number of bits:

```python
# Small number - few bits
bin(3)      # '0b11' - b = 2

# Large number - many bits
bin(2**64 - 1)  # b = 64

# Relationship: binary digits = bit_length()
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
x = 0b1100
y = 0b1010

print(f"x = {bin(x)}")           # x = 0b1100
print(f"y = {bin(y)}")           # y = 0b1010
print(f"x & y = {bin(x & y)}")   # x & y = 0b1000
print(f"x | y = {bin(x | y)}")   # x | y = 0b1110
print(f"x ^ y = {bin(x ^ y)}")   # x ^ y = 0b110
print(f"~x = {bin(~x)}")         # ~x = -0b1101
```

### Binary String to Integer

```python
# Linear in the string's length - parse binary string
binary_str = "0b1010"
value = int(binary_str, 2)  # O(len(binary_str))
assert value == 10

# Without prefix
value = int("1010", 2)  # Also linear in the length
assert value == 10
```

## Bit Manipulation Operations

```python
# bin() shows the result of each bitwise operator
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
# O(k * b) - k numbers of up to b bits each
numbers = list(range(100))
binary_values = [bin(n) for n in numbers]
# k = 100, b = 7

# vs direct method
binary_values = [f"{n:b}" for n in numbers]
# Same digits, without the '0b' prefix
```

### Counting Set Bits

```python
# O(b) - builds a string of b + 2 or more characters, then scans it
def count_bits_bin(value):
    return bin(value).count('1')

# Better - also O(b), but builds no string
def count_bits_optimal(value):
    return value.bit_count()

# Both give the same result
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
- Parsing `bin()` output with plain `int(s)`, which rejects the '0b' prefix; use `int(s, 2)` or `int(s, 0)`

## Version Notes

- **Python 3.10+**: Added `int.bit_count()` for bit counting
- **All Python 3**: `bin(x)` returns a string with a '0b' prefix, '-0b' for a negative number, and accepts any object with `__index__`

## Related Functions

- **[hex()](hex.md)** - Hexadecimal representation
- **[oct()](oct.md)** - Octal representation
- **[int().bit_length()](int.md)** - Number of bits needed
- **[int().bit_count()](int.md)** - Count set bits (Python 3.10+)
- **[format()](format.md)** - Format with specifications
