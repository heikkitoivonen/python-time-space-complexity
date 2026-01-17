# int() Function Complexity

The `int()` function converts objects to integers or creates integers from strings with specified bases.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert int | O(1) | O(1) | Already integer |
| Convert float | O(1) | O(1) | Truncate decimal |
| Convert string (base 10) | O(n) | O(1) | n = string length |
| Convert string (other base) | O(n) | O(1) | Parse digits in base |
| Convert bool | O(1) | O(1) | True→1, False→0 |

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
# O(n) - where n = string length
int("42")       # 42
int("-123")     # -123
int("0")        # 0
int("")         # ValueError
```

### From Different Bases

```python
# O(n) - parse digits in specified base
int("101", 2)     # 5 (binary)
int("ff", 16)     # 255 (hex)
int("77", 8)      # 63 (octal)
int("1A2B", 16)   # 6699 (hex)
```

## Complexity Details

### String Parsing

```python
# O(n) - linear in string length
short = int("42")      # O(2)
long = int("1" * 1000) # O(1000)

# Each character must be parsed
x = 0
for char in "12345":
    # Process each digit - O(n) total
    x = x * 10 + int(char)
```

### Base Conversion

```python
# O(n) - different bases same complexity
binary = int("1010101", 2)     # O(7)
octal = int("1234567", 8)      # O(7)
hex_val = int("ABCDEF", 16)    # O(6)

# Base doesn't affect complexity, just interpretation
```

### From Float

```python
# O(1) - just truncate
int(3.14)   # 3 - instant
int(3.99)   # 3 - instant (not rounded!)
int(-2.5)   # -2 (truncates toward zero)
```

## Common Patterns

### String to Integer Conversion

```python
# O(n) - user input parsing
user_input = input("Enter a number: ")  # "42"
try:
    number = int(user_input)  # O(n) - parse string
    process(number)
except ValueError:
    print("Invalid integer")
```

### Base Conversion

```python
# O(n) - convert from different bases
hex_string = "FF"
value = int(hex_string, 16)  # O(2) - binary: 255

# Useful for configuration
config_bits = "11010110"
flags = int(config_bits, 2)  # O(8) - binary flags
```

### List Comprehension

```python
# O(n * m) - n items, m = avg string length
strings = ["10", "20", "30", "40"]
numbers = [int(s) for s in strings]  # O(n)
# [10, 20, 30, 40]

# With base
hex_strings = ["FF", "10", "20"]
numbers = [int(s, 16) for s in hex_strings]  # O(n)
# [255, 16, 32]
```

## Performance Patterns

### String vs Direct

```python
# O(1) - direct
x = 42

# O(n) - string parsing
y = int("42")  # O(2)

# For performance, avoid string parsing if possible
config = 42  # Direct
value = int(config)  # O(1)

# vs
config = "42"  # String
value = int(config)  # O(n)
```

### Batch Conversion

```python
# O(n) - convert list of strings
data = ["1", "2", "3", "100", "200"]
numbers = [int(x) for x in data]  # O(n) total

# Using map - same complexity
numbers = list(map(int, data))  # O(n) total
```

### Base Conversion Efficiency

```python
# All O(n), no performance difference by base
# Time is proportional to string length, not base

# Short string, any base
int("10", 2)      # O(2)
int("10", 10)     # O(2)
int("10", 16)     # O(2)

# Long string
long_val = "1" * 1000
int(long_val, 2)  # O(1000)
int(long_val, 10) # O(1000)
int(long_val, 16) # O(1000)
```

## Practical Examples

### Parsing User Input

```python
# O(n) - parse and validate
def get_positive_int(prompt):
    while True:
        try:
            value = int(input(prompt))  # O(n)
            if value > 0:
                return value
            print("Must be positive")
        except ValueError:
            print("Must be an integer")

# Usage
count = get_positive_int("Enter count: ")
```

### Configuration from Strings

```python
# O(n) - parse config values
config_str = "timeout:30,retries:3,port:8080"

def parse_config(config_str):
    config = {}
    for item in config_str.split(","):
        key, value = item.split(":")
        config[key] = int(value)  # O(m) per value
    return config

config = parse_config(config_str)
# {'timeout': 30, 'retries': 3, 'port': 8080}
```

### Bit Manipulation

```python
# O(n) - parse binary for bit flags
def parse_flags(binary_str):
    value = int(binary_str, 2)  # O(n)
    flags = {}
    for i, bit in enumerate(reversed(binary_str)):
        flags[f"flag_{i}"] = bool(int(bit))
    return flags

flags_str = "11010110"
flags = parse_flags(flags_str)
# {'flag_0': 0, 'flag_1': 1, 'flag_2': 1, ...}
```

### Custom Number Base

```python
# O(n) - support custom bases
def int_from_base(string, base):
    if base < 2 or base > 36:
        raise ValueError("Base must be 2-36")
    return int(string, base)  # O(n)

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
# O(n) - handle negative numbers
int("-42")      # -42
int("+42")      # 42 (plus sign OK)
int("- 42")     # ValueError (space not allowed)
```

### Large Numbers

```python
# O(n) - Python handles arbitrary precision
big = int("999999999999999999999999999999")
huge = int("1" * 10000)  # O(10000)

# No overflow, just slower with more digits
```

### Invalid Bases

```python
# O(1) - check base
try:
    int("10", 1)   # ValueError: base must be >= 2
    int("10", 37)  # ValueError: base must be <= 36
except ValueError:
    pass
```

## Comparison with float()

```python
# int() - O(n) from string, O(1) from float
int("42")    # O(2)
int(3.14)    # O(1) - truncate

# float() - similar but handles decimals
float("3.14")  # O(4)

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
- Forgetting that int() parses, doesn't evaluate

## Related Functions

- **[float()](float_func.md)** - Convert to floating-point
- **[str()](str_func.md)** - Convert to string
- **[bin()](bin.md)** - Binary representation
- **[hex()](hex.md)** - Hexadecimal representation

## Version Notes

- **Python 2.x**: Long integers separate (long type)
- **Python 3.x**: Single int type with arbitrary precision
- **All versions**: Truncates toward zero when converting float
