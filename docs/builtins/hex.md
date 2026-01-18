# hex() Function Complexity

The `hex()` function returns the hexadecimal representation of an integer.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert integer | O(log n) | O(log n) | n = integer value |
| Negative integer | O(log n) | O(log n) | Adds '-0x' prefix |
| Large integer | O(log n) | O(log n) | Works with arbitrary precision |

## Basic Usage

### Decimal to Hexadecimal

```python
# O(log n) - where n = integer value
hex(0)      # '0x0'
hex(15)     # '0xf'
hex(255)    # '0xff'
hex(256)    # '0x100'
hex(4095)   # '0xfff'
```

### Negative Numbers

```python
# O(log n) - prefix with minus sign
hex(-1)     # '-0x1'
hex(-255)   # '-0xff'
hex(-1000)  # '-0x3e8'
```

### Large Integers

```python
# O(log n) - even very large numbers
hex(2**32)     # '0x100000000'
hex(2**100)    # '0x10000000000000000000000000'

# Arbitrary precision
big = 10**100
hex(big)       # O(log(10**100)) = O(100)
```

## Complexity Details

### Logarithmic Time

The conversion takes time proportional to the number of digits:

```python
# Small number - few digits
hex(255)    # '0xff' - 3 digits, O(log 255) = O(8)

# Large number - more digits
hex(2**64 - 1)  # '0xffffffffffffffff' - 16 hex digits
                # O(log(2**64)) = O(64)

# Relationship: hex digits = log₁₆(n) = log₂(n) / 4
```

## Common Patterns

### Bit Manipulation

```python
# O(log n) - convert for display/debugging
x = 42
print(hex(x))  # '0x2a'

# Useful for understanding bit patterns
values = [1, 2, 4, 8, 16, 32, 64, 128]
for v in values:
    print(f"{v:3d} = {hex(v)}")
    # Shows powers of 2 in hex
```

### Color Representation

```python
# O(log n) - RGB values to hex color
def rgb_to_hex(r, g, b):
    # O(log(256)) = O(8) per channel
    return f"#{hex(r)[2:]:>02}{hex(g)[2:]:>02}{hex(b)[2:]:>02}"

color = rgb_to_hex(255, 128, 64)
# '#ff8040'

# Converting from integers
red = 255
green = 128
blue = 64
color_hex = f"#{red:02x}{green:02x}{blue:02x}"
# Cleaner with format strings
```

### Memory Address Representation

```python
# O(log n) - memory addresses in hex
obj = [1, 2, 3]
addr = id(obj)
print(hex(addr))  # '0x7f...'  (memory address)

# Compare addresses
obj1 = []
obj2 = []
print(hex(id(obj1)))
print(hex(id(obj2)))
# Different addresses shown in hex
```

## Comparison with Alternatives

### hex() vs format()

```python
# hex() - returns string with '0x' prefix
hex(255)           # '0xff'

# format() - more flexible
format(255, 'x')   # 'ff' (no prefix)
format(255, 'X')   # 'FF' (uppercase, no prefix)
format(255, '#x')  # '0xff' (with prefix)

# Performance - both O(log n), format slightly faster
```

### hex() vs bin() vs oct()

```python
# All O(log n) but different bases
hex(255)    # '0xff'     (base 16)
bin(255)    # '0b11111111' (base 2)
oct(255)    # '0o377'    (base 8)

# Which base?
# hex - most compact, good for colors/addresses
# bin - for bit manipulation
# oct - rare, legacy use
```

## Builtin Integer Methods

```python
# to_bytes() - O(log n) alternative
x = 255
hex_bytes = x.to_bytes(2, 'big')
# b'\x00\xff'

# bit_length() - O(1) related operation
x = 255
bits = x.bit_length()  # 8
hex(x)  # '0xff' - 2 digits = 8 bits

# Relationship: hex digits ≈ bit_length() / 4
```

## Bidirectional Conversion

```python
# hex() and int() are inverses
# O(log n) each way

x = 255
hex_str = hex(x)       # O(log 255)
restored = int(hex_str, 16)  # O(log 255)
assert restored == x

# Useful for serialization
value = 12345
hex_form = hex(value)  # '0x3039'
original = int(hex_form, 16)  # 12345
```

## Performance Patterns

### Batch Conversion

```python
# O(n * log m) - n numbers, each ~m value
numbers = list(range(100))
hex_values = [hex(n) for n in numbers]
# O(100 * log 100)

# vs direct method
hex_values = [f"{n:x}" for n in numbers]
# Similar complexity, might be slightly faster
```

### Building Hex Strings

```python
# O(n) - building multi-value hex
values = [10, 20, 30, 40]
hex_str = ''.join(hex(v)[2:] for v in values)
# 'a141e28' - concatenated hex values
```

## Special Cases

### Zero

```python
# O(1)
hex(0)  # '0x0'
```

### Powers of Two

```python
# O(log n) - still efficient even for powers
hex(2**10)    # '0x400'
hex(2**20)    # '0x100000'
hex(2**100)   # Very large hex number, still O(log 2**100)
```

## Common Use Cases

### Debug Output

```python
# O(log n) - show value in different bases
value = 42
print(f"Dec: {value}, Hex: {hex(value)}, Bin: {bin(value)}")
# Dec: 42, Hex: 0x2a, Bin: 0b101010
```

### Configuration Values

```python
# O(log n) - save/restore hex values
config_value = 0x1A2B
config_str = hex(config_value)  # '0x1a2b'
# ... save to file ...
restored = int(config_str, 16)  # 0x1a2b
```

### Checksums/Hashes

```python
# O(log n) - display hash in hex
import hashlib
data = b"hello"
h = hashlib.sha256(data).digest()
# Convert bytes to hex for display
hex_hash = h.hex()  # Bytes.hex() is even faster
```

## Best Practices

✅ **Do**:

- Use `hex()` for readable hex representation
- Use `format(value, 'x')` when you don't need '0x' prefix
- Use f-strings for complex formatting: `f"{value:x}"`
- Use `int(hex_string, 16)` to convert back

❌ **Avoid**:

- Assuming hex() output is always lowercase (it is, but format uppercase with 'X')
- Building hex from decimal without understanding the conversion
- Using `hex()` for very frequent operations (cache result)
- Forgetting the '0x' prefix when parsing with `int()`

## Related Functions

- **[bin()](bin.md)** - Binary representation
- **[oct()](oct.md)** - Octal representation
- **[int()](int.md)** - Convert to integer (can parse hex)
- **[format()](format.md)** - Format with specifications

## Version Notes

- **Python 2.x**: Works with int and long
- **Python 3.x**: Works with arbitrary precision integers
- **All versions**: Returns string representation with '0x' prefix
