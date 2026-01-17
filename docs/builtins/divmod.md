# divmod() Function Complexity

The `divmod()` function returns the quotient and remainder of division as a tuple: (quotient, remainder).

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Integer division | O(1) | O(1) | Fixed-size integers |
| Float division | O(1) | O(1) | IEEE 754 floats |
| Large integers | O(n²) | O(n) | n = number of digits; arbitrary precision |

*Note: For typical fixed-size integers that fit in machine words, divmod is O(1). The O(n²) complexity applies only to Python's arbitrary-precision integers with many digits.*

## Basic Usage

### Integer Division

```python
# O(1) - division and modulo in one operation
divmod(17, 5)      # (3, 2)  -> 17 = 5 * 3 + 2
divmod(20, 3)      # (6, 2)  -> 20 = 3 * 6 + 2
divmod(10, 2)      # (5, 0)  -> 10 = 2 * 5 + 0

# Equivalent to but more efficient than:
# (17 // 5, 17 % 5)  -> (3, 2)
```

### Float Division

```python
# O(1) - floating point division
divmod(17.5, 5)    # (3.0, 2.5)
divmod(10.0, 3.0)  # (3.0, 1.0)

# Also works with mixed types
divmod(17, 5.0)    # (3.0, 2.0)
divmod(17.5, 5)    # (3.0, 2.5)
```

### Negative Numbers

```python
# O(1) - follows Python's floor division rules
divmod(-17, 5)     # (-4, 3)   -> -17 = 5 * (-4) + 3
divmod(17, -5)     # (-4, -3)  -> 17 = (-5) * (-4) + (-3)
divmod(-17, -5)    # (3, -2)   -> -17 = (-5) * 3 + (-2)

# Python ensures: a = b * q + r, where 0 <= |r| < |b|
```

## Performance Patterns

### Efficiency vs Separate Operations

```python
# O(1) - single operation
q, r = divmod(a, b)

# O(2) - two separate operations
q = a // b
r = a % b

# divmod() is more efficient - does both in one pass
# Also more readable intent
```

### Large Integer Operations

```python
# O(n²) where n = number of digits
a = 10**1000
b = 10**500
q, r = divmod(a, b)

# For large integers, efficiency matters
# divmod() avoids redundant computation
# vs doing // and % separately
```

## Common Patterns

### Conversion Between Number Bases

```python
# O(log n) where n = number to convert
def to_base(num, base):
    digits = []
    while num:
        num, remainder = divmod(num, base)
        digits.append(remainder)
    return digits[::-1]

# Convert to binary
binary = to_base(42, 2)
# [1, 0, 1, 0, 1, 0]

# Convert to hexadecimal
hexadecimal = to_base(255, 16)
# [15, 15] -> FF
```

### Time/Date Calculations

```python
# O(1) - split seconds into minutes and seconds
total_seconds = 125
minutes, seconds = divmod(total_seconds, 60)
# minutes = 2, seconds = 5

# Split into hours and minutes
hours, minutes = divmod(total_seconds // 60, 60)
# hours = 0, minutes = 2

# Full breakdown
def format_seconds(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

format_seconds(3665)  # "01:01:05"
```

### Pagination and Chunking

```python
# O(1) - calculate pages needed
items = 125
page_size = 10
pages, extra = divmod(items, page_size)
# pages = 12 (with 5 items in last page), extra = 5

# Or just use pages
total_pages = (items + page_size - 1) // page_size
# Same as divmod approach
```

### Iterating with Offset

```python
# O(n/k) - process items in groups
items = list(range(20))
group_size = 3

for i in range(0, len(items), group_size):
    group = items[i:i+group_size]
    process(group)

# Alternative with divmod
num_groups, remainder = divmod(len(items), group_size)
for g in range(num_groups):
    group = items[g*group_size:(g+1)*group_size]
    process(group)
```

## Comparison with Alternatives

### divmod() vs // and %

```python
# divmod() - O(1), cleaner intent
q, r = divmod(17, 5)  # (3, 2)

# Separate operations - O(2) but typically optimized
q = 17 // 5  # 3
r = 17 % 5   # 2

# divmod() is preferred when you need both
# Slightly more efficient
# More readable: "divide and get remainder"
```

### divmod() vs Loops

```python
# divmod() - O(1)
q, r = divmod(17, 5)

# Loop simulation - O(q)
q = 0
while 17 >= 5:
    17 -= 5
    q += 1
r = 17
# Much slower for large quotients

# divmod() is always better
```

## Edge Cases

### Zero Dividend

```python
# O(1)
divmod(0, 5)    # (0, 0)
divmod(0, -5)   # (0, 0)
```

### Zero Divisor

```python
# O(1) - raises ZeroDivisionError
try:
    divmod(5, 0)  # ZeroDivisionError
except ZeroDivisionError:
    pass
```

### One

```python
# O(1)
divmod(5, 1)    # (5, 0)
divmod(5, -1)   # (-5, 0)
```

### Negative Results

```python
# O(1) - follows Python's floor division
divmod(-10, 3)   # (-4, 2)
# Because: -10 = 3 * (-4) + 2

# Not (-3, -1) as some might expect
# Python uses floor division (rounds down)
```

## Performance Considerations

### Integer Arithmetic

```python
import timeit

# Small integers
t1 = timeit.timeit(lambda: divmod(17, 5), number=10**7)

# Combined vs separate
t2 = timeit.timeit(lambda: (17 // 5, 17 % 5), number=10**7)

# divmod() often faster (single operation)
```

### When to Use divmod()

```python
# Use divmod() when:
# 1. You need both quotient and remainder
# 2. You care about efficiency
# 3. You want readable code

# 1. Need both values
q, r = divmod(a, b)

# 2. Performance critical
for i in range(large_count):
    q, r = divmod(items[i], base)  # Efficient

# 3. Clear intent
# divmod communicates "divide and remainder"
# better than separate // and % operations
```

## Best Practices

✅ **Do**:
- Use `divmod()` when you need both quotient and remainder
- Use for base conversion algorithms
- Use for time calculations and pagination
- Remember floor division semantics for negatives

❌ **Avoid**:
- Computing `q` and `r` separately when you need both
- Forgetting about negative number behavior
- Assuming truncation toward zero (Python uses floor)
- Dividing by zero without checking

## Related Functions

- **[// operator](int.md)** - Floor division (quotient only)
- **[% operator](int.md)** - Modulo (remainder only)
- **[pow(x, y, z)](pow.md)** - Modular exponentiation
- **[math.fmod()](../stdlib/math.md)** - Floating point remainder

## Mathematical Note

```
divmod(a, b) returns (q, r) where:
  a = b * q + r
  0 <= |r| < |b|

This is floor division, not truncation toward zero.
Important for negative numbers!
```

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior, consistent
- **Python 3.8+**: No changes to complexity or behavior
