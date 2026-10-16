# hex() Function Complexity

The `hex()` function returns the hexadecimal representation of an integer.
It writes one character per hexadecimal digit, so its time and the size of the
string it returns are both linear in the integer's number of hex digits.

`n` is the integer's absolute value and `h` is the number of hex digits in the
result: `n.bit_length()` divided by 4 and rounded up, about log₁₆ n, or 1 for
zero.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert integer | O(log n) | O(log n) | O(h): one character per hex digit |
| Negative integer | O(log n) | O(log n) | Adds '-0x' prefix |
| Large integer | O(h) | O(h) | Not limited by `sys.set_int_max_str_digits()`, which exempts power-of-two bases |
| Object with `__index__` | `__index__` + O(h) | `__index__` + O(h) | Any other non-int, such as a float, raises `TypeError` |

## Basic Usage

### Decimal to Hexadecimal

```python
# O(log n)
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
hex(big)       # O(h) - h = 84 hex digits
```

## Complexity Details

### Logarithmic Time

The conversion takes time proportional to the number of digits:

```python
# Small number - few digits
hex(255)    # '0xff' - h = 2

# Large number - more digits
hex(2**64 - 1)  # '0xffffffffffffffff' - h = 16

# Relationship: hex digits = bit_length() / 4, rounded up
value = 4095
digits = len(hex(value)) - 2  # Subtract '0x'
assert digits == (value.bit_length() + 3) // 4
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
# O(1) - RGB values to hex color, at most 2 hex digits per channel
def rgb_to_hex(r, g, b):
    # Pad each channel to two digits: hex(8) is '0x8'
    return f"#{hex(r)[2:]:>02}{hex(g)[2:]:>02}{hex(b)[2:]:>02}"

color = rgb_to_hex(255, 128, 64)
assert color == '#ff8040'
assert rgb_to_hex(255, 8, 64) == '#ff0840'

# Converting from integers
red = 255
green = 128
blue = 64
color_hex = f"#{red:02x}{green:02x}{blue:02x}"
# Cleaner with format strings
assert color_hex == color
```

### Memory Address Representation

```python
# O(log n) - memory addresses in hex
obj = [1, 2, 3]
addr = id(obj)
print(hex(addr))  # '0x...' (memory address)

# Compare addresses
obj1 = []
obj2 = []
print(hex(id(obj1)))
print(hex(id(obj2)))
# Different addresses shown in hex
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
# O(k * h) - k numbers of up to h hex digits each
numbers = list(range(100))
hex_values = [hex(n) for n in numbers]
# k = 100, h = 2

# vs direct method
hex_values = [f"{n:x}" for n in numbers]
# Same digits, without the '0x' prefix
```

### Building Hex Strings

```python
# O(total hex digits) - building multi-value hex
values = [10, 20, 30, 40]
hex_str = ''.join(hex(v)[2:] for v in values)
assert hex_str == 'a141e28'  # Unpadded: the digits run together

# Pad to a fixed width to keep the values apart
hex_str = ''.join(f"{v:02x}" for v in values)
assert hex_str == '0a141e28'
```

## Common Use Cases

### Debug Output

```python
# hex() and bin() are O(log n) each - show value in different bases
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
# Bytes to hex: use bytes.hex(), not hex()
import hashlib
data = b"hello"
digest = hashlib.sha256(data).digest()
hex_hash = digest.hex()  # O(len(digest)), two digits per byte
assert len(hex_hash) == 2 * len(digest)

# hex() of the same value drops leading zero bytes
assert hex(int.from_bytes(b"\x00\x0f", "big")) == '0xf'
assert b"\x00\x0f".hex() == '000f'
```

## Best Practices

✅ **Do**:

- Use `hex()` for readable hex representation
- Use `format(value, 'x')` when you don't need '0x' prefix
- Use f-strings for complex formatting: `f"{value:x}"`
- Use `int(hex_string, 16)` to convert back

❌ **Avoid**:

- Expecting uppercase digits from `hex()`; it always writes lowercase, so use `format(value, 'X')` for uppercase
- Using `hex()` for very frequent operations (cache result)
- Parsing `hex()` output with plain `int(s)`, which rejects the '0x' prefix; use `int(s, 16)` or `int(s, 0)`

## Related Functions

- **[bin()](bin.md)** - Binary representation
- **[oct()](oct.md)** - Octal representation
- **[int()](int.md)** - Convert to integer (can parse hex)
- **[format()](format.md)** - Format with specifications

## Version Notes

- **All Python 3**: `hex(x)` returns a lowercase string with a '0x' prefix, '-0x' for a negative number, and accepts any object with `__index__`
