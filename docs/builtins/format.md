# format() Function Complexity

The `format()` function formats a value into a string according to a format specification.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `format(value)` | O(n) | O(n) | n = result string length |
| `format(value, spec)` | O(n) | O(n) | n = result string length |
| `f"{value}"` | O(n) | O(n) | F-string (Python 3.6+) |
| `"{0}".format(value)` | O(n) | O(n) | str.format() method |
| `"%s" % value` | O(n) | O(n) | Old % formatting |

All return new string of size n; time proportional to output size.

## Basic Usage

### Simple Formatting

```python
# Format integer - O(1) to O(n) depending on digits
format(42)              # "42" - O(2)
format(42, '05d')       # "00042" - O(5)

# Format float - O(n) for string size
format(3.14159)         # "3.14159" - O(7)
format(3.14159, '.2f')  # "3.14" - O(4)

# Format string - O(n)
format("hello")         # "hello" - O(5)
```

### Format Specifications

```python
# Integer formatting - O(k) where k = digit count
value = 42
format(value, 'd')      # "42" - standard decimal
format(value, '05d')    # "00042" - zero-padded to 5
format(value, 'x')      # "2a" - hexadecimal
format(value, 'b')      # "101010" - binary
format(value, 'o')      # "52" - octal

# Float formatting - O(precision)
value = 3.14159265
format(value, '.2f')    # "3.14" - 2 decimal places
format(value, '.4f')    # "3.1416" - 4 decimal places
format(value, 'e')      # "3.141593e+00" - exponential
format(value, 'g')      # "3.14159" - general format
```

## Format Specification Mini-language

### Format Spec Syntax

```python
# General format: [[fill]align][sign][#][0][width][,][.precision][type]

# Width and padding - O(w) where w = width
value = 42
format(value, '10')     # "        42" - right aligned, 10 width
format(value, '<10')    # "42        " - left aligned
format(value, '^10')    # "    42    " - center aligned
format(value, '010')    # "0000000042" - zero padding

# Sign and alternate form - O(n)
value = -42
format(value, '+d')     # "-42" - show sign
format(value, ' d')     # "-42" - space for positive

value = 255
format(value, '#x')     # "0xff" - alternate form (prefix)
format(value, '#b')     # "0b11111111" - binary prefix

# Thousands separator - O(n)
value = 1000000
format(value, ',')      # "1,000,000" - comma separator
format(value, '_')      # "1_000_000" - underscore separator (Python 3.6+)
```

## String Formatting Methods

### str.format() Method

```python
# Using format() method - O(n)
template = "Hello, {}!"
result = template.format("World")  # "Hello, World!" - O(13)

# Multiple placeholders - O(n)
template = "{0} + {1} = {2}"
result = template.format(1, 2, 3)  # "1 + 2 = 3" - O(9)

# Named arguments - O(n)
template = "{name} is {age} years old"
result = template.format(name="Alice", age=30)  # O(26)
```

### F-strings (Python 3.6+)

```python
# F-strings are compiled to format calls - O(n)
name = "Alice"
age = 30

# Simple variable - O(n)
message = f"Hello, {name}"  # "Hello, Alice" - O(11)

# With expressions - O(n)
value = 42
message = f"Answer: {value * 2}"  # "Answer: 84" - O(10)

# With format spec - O(n)
pi = 3.14159
message = f"Pi: {pi:.2f}"  # "Pi: 3.14" - O(8)

# Multiple substitutions - O(n)
result = f"{name} is {age} years old"  # O(26)
```

### Old % Formatting

```python
# % operator formatting - O(n)
template = "Hello, %s"
result = template % "World"  # "Hello, World" - O(12)

# Multiple values - O(n)
template = "%s + %s = %d"
result = template % (1, 2, 3)  # "1 + 2 = 3" - O(9)

# Numeric formatting - O(n)
template = "Value: %.2f"
result = template % 3.14159  # "Value: 3.14" - O(11)
```

## Common Patterns

### Number Formatting

```python
# Integer with thousands separator - O(digits + separators)
num = 1234567
formatted = format(num, ',d')  # "1,234,567" - O(10)

# Float with fixed decimals - O(precision)
value = 3.14159
formatted = format(value, '.2f')  # "3.14" - O(4)

# Scientific notation - O(precision)
large = 123456789.0
formatted = format(large, '.2e')  # "1.23e+08" - O(8)

# Percentage - O(precision)
value = 0.42
formatted = format(value, '.1%')  # "42.0%" - O(5)
```

### Date and Time Formatting

```python
from datetime import datetime

# DateTime formatting - O(n)
dt = datetime(2024, 1, 15, 14, 30, 0)
formatted = f"{dt:%Y-%m-%d}"     # "2024-01-15" - O(10)
formatted = f"{dt:%H:%M:%S}"     # "14:30:00" - O(8)

# Using format() - O(n)
formatted = format(dt, '%Y-%m-%d %H:%M:%S')  # O(19)
```

### Alignment and Padding

```python
# Left align - O(width)
value = "hello"
formatted = format(value, '<20')  # "hello               " - O(20)

# Right align - O(width)
formatted = format(value, '>20')  # "               hello" - O(20)

# Center align - O(width)
formatted = format(value, '^20')  # "       hello        " - O(20)

# Custom fill character - O(width)
formatted = format(value, '.>20')  # ".............hello" - O(20)
```

### Grouping and Separators

```python
# Comma grouping - O(n)
large = 1234567890
formatted = f"{large:,}"  # "1,234,567,890" - O(13)

# Underscore grouping (Python 3.6+) - O(n)
formatted = f"{large:_}"  # "1_234_567_890" - O(13)

# Binary with grouping - O(bits)
value = 255
formatted = f"{value:_b}"  # "11111111" - O(8)
```

## Custom Classes with __format__

### Implementing __format__

```python
# Custom formatting - O(implementation)
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __format__(self, spec):
        if spec == 'tuple':
            return f"({self.x}, {self.y})"  # O(n)
        elif spec == 'verbose':
            return f"Point({self.x}, {self.y})"  # O(n)
        else:
            return f"{self.x:.1f},{self.y:.1f}"  # O(n)

# Usage
p = Point(3.14, 2.71)
format(p, 'tuple')     # "(3.14, 2.71)" - O(14)
format(p, 'verbose')   # "Point(3.14, 2.71)" - O(18)
f"{p}"                 # "3.1,2.7" - O(7)
```

### Custom Class Example

```python
class Temperature:
    def __init__(self, celsius):
        self.celsius = celsius
    
    def __format__(self, spec):
        if spec == 'F':
            fahrenheit = self.celsius * 9/5 + 32
            return f"{fahrenheit:.1f}°F"  # O(n)
        else:
            return f"{self.celsius:.1f}°C"  # O(n)

# Usage
temp = Temperature(25)
format(temp, 'F')      # "77.0°F" - O(6)
format(temp, 'C')      # "25.0°C" - O(6)
f"{temp:F}"            # "77.0°F" - O(6)
```

## Performance Considerations

### F-strings vs format()

```python
# F-strings are typically faster (compiled)
name = "Alice"

# F-string - O(n), optimized
message = f"Hello, {name}"

# format() method - O(n)
message = "Hello, {}".format(name)

# % formatting - O(n)
message = "Hello, %s" % name

# All have same complexity but f-strings may be slightly faster
```

### Building Large Strings

```python
# Inefficient: repeated string concatenation - O(n²)
result = ""
for item in items:
    result += format(item, '05d') + ","  # O(n²) due to concatenation

# Efficient: join with list - O(n)
parts = [format(item, '05d') for item in items]  # O(n)
result = ",".join(parts)  # O(n)

# Efficient: use generator with join - O(n)
result = ",".join(format(item, '05d') for item in items)  # O(n)
```

### Formatting in Loops

```python
# Pre-compile format specs
items = list(range(1000000))

# Inefficient: repeated format calls - O(n)
results = [format(item, '010d') for item in items]

# Same complexity but more readable
results = [f"{item:010d}" for item in items]

# Both O(n); prefer f-strings or list comprehension
```

## Comparison: Different Formatting Methods

```python
value = 42.567

# Method 1: format() function - O(n)
s1 = format(value, '.2f')  # "42.57" - O(5)

# Method 2: str.format() - O(n)
s2 = "{:.2f}".format(value)  # "42.57" - O(5)

# Method 3: f-string - O(n)
s3 = f"{value:.2f}"  # "42.57" - O(5)

# Method 4: % operator - O(n)
s4 = "%.2f" % value  # "42.57" - O(5)

# All equivalent complexity; f-strings preferred (Python 3.6+)
```

## Special Format Types

### Boolean

```python
# Boolean formatting - O(1) to O(n)
value = True
format(value)           # "True" - O(4)
format(value, 'd')      # "1" - treated as int
format(value, '05d')    # "00001" - as integer

value = False
format(value)           # "False" - O(5)
format(value, 'd')      # "0" - as integer
```

### Complex Numbers

```python
# Complex number formatting - O(n)
value = 3 + 4j
format(value)           # "(3+4j)" - O(6)
format(value, '.2f')    # Error - no float spec for complex

# Use string representation
value = 3.14 + 2.71j
formatted = f"{value}"  # "(3.14+2.71j)" - O(12)
```

## Version Notes

- **Python 2.x**: `format()` available, % formatting standard
- **Python 3.x**: `format()` available, str.format() method standard
- **Python 3.6+**: F-strings available (preferred)
- **Python 3.10+**: Enhanced f-string debugging with `=` specifier

## Related Functions

- **[str.format()](str.md)** - String format() method
- **[f-strings](str.md)** - Formatted string literals
- **[repr()](builtins/repr.md)** - String representation
- **[str()](builtins/str.md)** - Convert to string

## Best Practices

✅ **Do**:
- Use f-strings for clarity and performance (Python 3.6+)
- Use str.format() for templating with variables
- Use format() function for custom formatting logic
- Pre-compile format specs if used repeatedly
- Use join() for building large formatted strings

❌ **Avoid**:
- % formatting for new code (harder to read)
- Repeated string concatenation with format() results (O(n²))
- Complex format specs without documentation
- Formatting in inner loops without profiling
- Mixing formatting methods in same code
