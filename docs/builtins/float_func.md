# float() Function Complexity

The `float()` function converts objects to floating-point numbers.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert int | O(1) | O(1) | Direct conversion for small ints; O(n) for arbitrary precision |
| Convert string | O(n) | O(1) | n = string length |
| Convert bool | O(1) | O(1) | True→1.0, False→0.0 |
| Special values | O(n) | O(1) | Parses "inf", "-inf", "nan" strings |

## Basic Usage

### From Numeric Types

```python
# O(1) - type conversions
float(42)       # 42.0
float(-10)      # -10.0
float(3)        # 3.0
float(True)     # 1.0
float(False)    # 0.0
```

### From Strings

```python
# O(n) - where n = string length
float("3.14")           # 3.14
float("-2.5")           # -2.5
float("1.23e-4")        # 0.000123 (scientific notation)
float("1E10")           # 10000000000.0
float(".5")             # 0.5
float("5.")             # 5.0
```

### Special Values

```python
# O(1) - special floating-point values
float("inf")        # infinity
float("-inf")       # negative infinity
float("nan")        # not a number
float("Infinity")   # Also infinity
float("NaN")        # Also not a number (case insensitive)
```

## Complexity Details

### String Parsing

```python
# O(n) - linear in string length
short = float("1.5")        # O(3)
long = float("3." + "14" * 500)  # O(1000+)

# Each character parsed - O(n)
```

### Notation Handling

```python
# O(n) - same complexity for all formats
decimal = float("3.14159")           # O(8)
scientific = float("3.14159e-10")    # O(12)
exponential = float("31415.9e-4")    # O(12)

# Length is what matters
```

### From Integer

```python
# O(1) - just convert type
float(42)       # 42.0 - instant
float(999999999999999999)  # O(1) - instant
```

## Common Patterns

### String to Float Conversion

```python
# O(n) - user input parsing
user_input = input("Enter a number: ")  # "3.14"
try:
    value = float(user_input)  # O(n)
    process(value)
except ValueError:
    print("Invalid number")
```

### Scientific Notation

```python
# O(n) - parse scientific notation
scientific_values = ["1e3", "2.5e-2", "1.23e10"]

values = [float(s) for s in scientific_values]  # O(n)
# [1000.0, 0.025, 12300000000.0]
```

### Unit Conversion

```python
# O(n) - parse and convert
def parse_temperature(temp_str):
    value = float(temp_str)  # O(n)
    # Could be Celsius, convert to Kelvin
    return value + 273.15

temp = parse_temperature("25.5")  # 298.65
```

## Performance Patterns

### String vs Direct

```python
# O(1) - direct
x = 3.14

# O(n) - string parsing
y = float("3.14")  # O(4)

# For performance, avoid string parsing if possible
value = 3.14  # Direct - O(1)
result = float(value)  # O(1)

# vs
value = "3.14"  # String
result = float(value)  # O(n)
```

### Batch Conversion

```python
# O(n * m) - n strings, m = avg length
strings = ["1.5", "2.7", "3.14", "10.0"]
values = [float(s) for s in strings]  # O(n * m)

# Using map - same complexity
values = list(map(float, strings))  # O(n * m)
```

### vs int() Conversion

```python
# float() similar to int() but handles decimals
int("42")       # O(2)
float("42")     # O(2)

int("3.14")     # ValueError!
float("3.14")   # O(4) - handles decimals

# float() is more flexible
```

## Practical Examples

### CSV Parsing

```python
# O(n * m) - parse CSV with float values
csv_line = "1.5,2.7,3.14,10.0"

def parse_csv_floats(line):
    return [float(x) for x in line.split(",")]  # O(n)

values = parse_csv_floats(csv_line)
# [1.5, 2.7, 3.14, 10.0]
```

### Decimal Arithmetic

```python
# O(n) - string parsing for precision
def money_to_float(money_str):
    # "$10.50" -> 10.5
    cleaned = money_str.replace("$", "").strip()
    return float(cleaned)  # O(n)

prices = ["$10.50", "$25.00", "$5.99"]
values = [money_to_float(p) for p in prices]
# [10.5, 25.0, 5.99]
```

### Statistics Calculation

```python
# O(n) - convert and compute
def calculate_average(data_str):
    values = [float(x) for x in data_str.split(",")]  # O(n)
    return sum(values) / len(values)  # O(n)

avg = calculate_average("10.5,20.3,15.7")  # 15.5
```

### Matrix/Vector Operations

```python
# O(n) - convert all elements
def parse_vector(vector_str):
    # "1.5 2.7 3.14" -> [1.5, 2.7, 3.14]
    return [float(x) for x in vector_str.split()]  # O(n)

vec = parse_vector("1.5 2.7 3.14")
magnitude = sum(x**2 for x in vec) ** 0.5
```

## Edge Cases

### Empty String

```python
# O(1) - error
try:
    float("")  # ValueError
except ValueError:
    pass
```

### Whitespace

```python
# O(n) - strips whitespace
float("  3.14  ")    # 3.14
float("\t2.5\n")     # 2.5
float("  ")          # ValueError
```

### Invalid Format

```python
# O(n) - parsing fails
try:
    float("3.14.15")   # ValueError
    float("1.5x")      # ValueError
    float("x1.5")      # ValueError
except ValueError:
    pass
```

### Special Values

```python
# O(1) - special values
inf = float("inf")
result = inf + 100  # Still infinity
result = inf * -1   # -infinity

nan = float("nan")
result = nan == nan  # False (NaN != NaN)
result = nan + 1     # Still NaN
```

### Very Large/Small Numbers

```python
# O(n) - parsing doesn't overflow
huge = float("1e308")     # Max finite float
tiny = float("1e-308")    # Very small

beyond = float("1e309")   # Becomes infinity!
near_zero = float("1e-324")  # Becomes 0.0
```

## Comparison with int()

```python
# int() - truncates, requires valid integer format
int("42")       # OK
int("3.14")     # ValueError!
int(3.14)       # 3 (truncate)

# float() - handles decimals, more flexible
float("42")     # 42.0
float("3.14")   # 3.14
float(42)       # 42.0 (convert from int)
```

## Mathematical Properties

```python
# O(1) - mathematical operations
x = float("3.14")

# Arithmetic
y = x + 1       # 4.14
z = x * 2       # 6.28

# Special cases
inf = float("inf")
result = 1 / inf     # 0.0
result = inf / inf   # nan

nan = float("nan")
result = nan + 1     # nan (propagates)
```

## Best Practices

✅ **Do**:

- Use `try-except` for user input
- Handle special values (inf, nan) if relevant
- Validate ranges for your use case
- Use decimal.Decimal for financial calculations

❌ **Avoid**:

- Floating-point arithmetic for money (use Decimal)
- Comparing floats with `==` (use tolerance)
- Assuming string parsing always succeeds
- Assuming float precision is unlimited

## Related Functions

- **[int()](int_func.md)** - Convert to integer
- **[str()](str_func.md)** - Convert to string
- **[round()](round.md)** - Round to nearest integer
- **[decimal.Decimal](https://docs.python.org/3/library/decimal.html)** - Precise decimal arithmetic

## Version Notes

- **Python 2.x**: Separate int/long types, float same
- **Python 3.x**: Unified int type, float same behavior
- **All versions**: Uses IEEE 754 double precision
