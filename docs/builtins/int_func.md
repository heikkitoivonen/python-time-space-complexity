# int() Function Complexity

The `int()` function converts objects to integers or creates integers from strings with specified bases.

## Complexity Analysis

n is the length of a string argument.

| Case | Time | Space | Notes |
|------|------|-------|-------|
| No argument | O(1) | O(1) | Returns `0` |
| Convert int | O(1) | O(1) | Returns the argument itself; an instance of a subclass that inherits the conversion is copied, linear in its bits |
| Convert float | O(1) | O(1) | Truncates toward zero; the result is at most 1,024 bits |
| Convert bool | O(1) | O(1) | True→1, False→0 |
| Convert string, base 10 | O(n²) | O(n) | Each nine-digit group is folded into a growing value. Capped at `sys.get_int_max_str_digits()`, 4,300 digits by default, `ValueError` beyond. 3.12+: O(n^1.58) above 6,000 digits once the cap is raised |
| Convert string, base 2, 4, 8, 16 or 32 | O(n) | O(n) | Each character is a fixed number of bits; no cap |
| Convert string, any other base from 3 to 36 | O(n²) | O(n) | Same accumulation and cap as base 10, with no 3.12 fast path |
| Convert string, base 0 | as the detected base | as the detected base | A `0x`, `0o` or `0b` prefix selects 16, 8 or 2, otherwise base 10, with that base's cost and cap |
| Convert object with `__int__` or `__index__` | O(f) | O(f) | f = that method's cost, called once; the `__trunc__` fallback is removed in 3.14 |

## Basic Usage

### From Numeric Types

```python
# O(1) - type conversions
int(42)         # 42 (already int)
int(3.14)       # 3 (truncate)
int(3.99)       # 3 (truncate, not round)
int(True)       # 1
int(False)      # 0
```

### From Strings

```python
# O(n²) in the digit count
int("42")       # 42
int("-123")     # -123
int("0")        # 0

try:
    int("")     # ValueError
except ValueError:
    pass
```

### From Different Bases

```python
# O(n) - bases 2, 8 and 16 map each character straight to bits
int("101", 2)     # 5 (binary)
int("ff", 16)     # 255 (hex)
int("77", 8)      # 63 (octal)
int("1A2B", 16)   # 6699 (hex)
```

## Complexity Details

### String Parsing

!!! note "Why base 10 is quadratic"
    Each group of nine digits is folded in by multiplying the value accumulated so far by 10⁹, so the work is the sum of the growing widths: O(n²). Bases 2, 4, 8, 16 and 32 copy bits straight into the result, O(n). Since 3.12, base 10 switches to an O(n^1.58) divide-and-conquer above 6,000 digits, but the default 4,300-digit cap has to be raised before that path is reachable.

```python
# O(n²) - the accumulated value is multiplied at every step
short = int("42")
long = int("1" * 1000)

# The same accumulation, spelled out
x = 0
for char in "12345":
    x = x * 10 + int(char)
```

### Base Conversion

```python
# Power-of-two bases are linear: one character is a fixed number of bits
binary = int("1010101", 2)
octal = int("1234567", 8)
hex_val = int("ABCDEF", 16)

# Any other base accumulates like base 10 and is quadratic
base3 = int("2101", 3)
base36 = int("zz", 36)
```

### From Float

```python
# O(1) - just truncate
int(3.14)   # 3 - O(1)
int(3.99)   # 3 - O(1), not rounded
int(-2.5)   # -2 (truncates toward zero)
```

## Common Patterns

### String to Integer Conversion

```python
# One parse per attempt, quadratic in the digits
for user_input in ["42", "forty-two"]:
    try:
        number = int(user_input)
        print(number)
    except ValueError:
        print("Invalid integer")
```

### Base Conversion

```python
# O(n) - power-of-two bases
hex_string = "FF"
value = int(hex_string, 16)  # 255

# Useful for configuration
config_bits = "11010110"
flags = int(config_bits, 2)  # 214
```

### List Comprehension

```python
# n strings of m digits: O(n * m²), or O(n * m) for a power-of-two base
strings = ["10", "20", "30", "40"]
numbers = [int(s) for s in strings]
# [10, 20, 30, 40]

# With base
hex_strings = ["FF", "10", "20"]
numbers = [int(s, 16) for s in hex_strings]
# [255, 16, 32]
```

## Performance Patterns

### String vs Direct

```python
# O(1) - direct
x = 42

# Quadratic in the digits - string parsing
y = int("42")

# Keep values numeric where you can
config = 42
value = int(config)  # O(1): returns the same object

config = "42"
value = int(config)  # parses again every time
```

### Batch Conversion

```python
# One parse per item
data = ["1", "2", "3", "100", "200"]
numbers = [int(x) for x in data]

# Using map - same work
numbers = list(map(int, data))
```

### Base Conversion Efficiency

```python
# The base decides the algorithm, not just the interpretation
digits = "1" * 4000
int(digits, 2)   # O(n): bits copied straight in
int(digits, 16)  # O(n): four bits per character
int(digits, 10)  # O(n²): every step multiplies the running value
int(digits, 3)   # O(n²): the same accumulation as base 10
```

## Practical Examples

### Parsing User Input

```python
# One parse per candidate
def get_positive_int(candidates):
    for text in candidates:
        try:
            value = int(text)
        except ValueError:
            print("Must be an integer")
            continue
        if value > 0:
            return value
        print("Must be positive")
    return None

count = get_positive_int(["abc", "-3", "7"])  # 7
```

### Configuration from Strings

```python
# One parse per value
config_str = "timeout:30,retries:3,port:8080"

def parse_config(config_str):
    config = {}
    for item in config_str.split(","):
        key, value = item.split(":")
        config[key] = int(value)
    return config

config = parse_config(config_str)
# {'timeout': 30, 'retries': 3, 'port': 8080}
```

### Bit Manipulation

```python
# The parse is O(n); the loop then builds one key per bit
def parse_flags(binary_str):
    value = int(binary_str, 2)  # O(n)
    flags = {}
    for i, bit in enumerate(reversed(binary_str)):
        flags[f"flag_{i}"] = bool(int(bit))
    return flags

flags_str = "11010110"
flags = parse_flags(flags_str)
# {'flag_0': False, 'flag_1': True, 'flag_2': True, ...}
```

### Custom Number Base

```python
# Linear for a power-of-two base, quadratic otherwise
def int_from_base(string, base):
    if base < 2 or base > 36:
        raise ValueError("Base must be 2-36")
    return int(string, base)

# Useful for specialized parsing
value = int_from_base("Z", 36)  # 35 in base 36
value = int_from_base("1010", 2)  # 10 in binary
```

## Edge Cases

### Empty String

```python
# O(1) - error
try:
    int("")  # ValueError: invalid literal
except ValueError:
    pass
```

### Whitespace

```python
# O(n) - strips whitespace automatically
int("  42  ")     # 42 - whitespace stripped
int("\t10\n")     # 10 - tab and newline stripped
```

### Sign Handling

```python
# A leading sign is part of the literal
int("-42")      # -42
int("+42")      # 42 (plus sign OK)

try:
    int("- 42")  # ValueError (space not allowed)
except ValueError:
    pass
```

### Large Numbers

```python
# O(n²) - and capped at 4,300 decimal digits by default
big = int("999999999999999999999999999999")
huge = int("1" * 4000)

try:
    int("1" * 5000)
except ValueError:
    pass  # raise the cap with sys.set_int_max_str_digits() for trusted input

# Power-of-two bases have no cap
wide = int("f" * 5000, 16)
```

### Invalid Bases

```python
# O(1) - check base
try:
    int("10", 1)   # ValueError: base must be >= 2 and <= 36, or 0
    int("10", 37)  # ValueError: same check
except ValueError:
    pass
```

## Comparison with float()

```python
# int() - quadratic in the digits from a string, O(1) from a float
int("42")    # 42
int(3.14)    # 3 - truncate

# float() - a linear scan into a fixed-width result, with no digit cap
float("3.14")  # 3.14

# int() truncates, float() keeps precision
int(3.99)   # 3
float(3.99) # 3.99
```

## Best Practices

✅ **Do**:

- Validate input before converting: `int(input())`
- Use `try-except` for user input
- Specify base explicitly when parsing non-decimal: `int(s, 16)`
- Cache conversion results if used multiple times

❌ **Avoid**:

- Assuming int() won't fail on user input
- Using int() repeatedly on same string (cache it)
- Expecting int() to round (it truncates)
- Parsing thousands of decimal digits in a hot path (quadratic, and capped)

## Related Functions

- **[float()](float_func.md)** - Convert to floating-point
- **[str()](str_func.md)** - Convert to string
- **[bin()](bin.md)** - Binary representation
- **[hex()](hex.md)** - Hexadecimal representation

## Version Notes

- **Python 2.x**: Long integers separate (long type)
- **Python 3.x**: Single int type with arbitrary precision
- **All versions**: Truncates toward zero when converting float
- **Python 3.11** (backported to 3.10.7): decimal digit cap, adjustable with `sys.set_int_max_str_digits()`
- **Python 3.12**: O(n^1.58) base-10 parsing above 6,000 digits
- **Python 3.14**: the `__trunc__` fallback is removed; objects need `__int__` or `__index__`
