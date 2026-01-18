# oct() Function Complexity

The `oct()` function returns the octal (base 8) representation of an integer.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert integer | O(log n) | O(log n) | n = integer value |
| Negative integer | O(log n) | O(log n) | Adds '-0o' prefix |
| Large integer | O(log n) | O(log n) | Works with arbitrary precision |

## Basic Usage

### Decimal to Octal

```python
# O(log n) - where n = integer value
oct(0)      # '0o0'
oct(8)      # '0o10'
oct(64)     # '0o100'
oct(512)    # '0o1000'
oct(4095)   # '0o7777'
```

### Negative Numbers

```python
# O(log n) - shows magnitude with minus
oct(-1)     # '-0o1'
oct(-8)     # '-0o10'
oct(-64)    # '-0o100'
```

### Large Integers

```python
# O(log n) - octal digits
oct(2**9)    # '0o1000'
oct(2**12)   # '0o10000'
oct(2**100)  # Very large octal number
```

## Complexity Details

### Logarithmic Time

Conversion time grows with the number of octal digits:

```python
# Small number - few digits
oct(8)      # '0o10' - 2 digits, O(log 8) = O(3)

# Large number - more digits
oct(2**24 - 1)  # 8 octal digits
                # O(log(2**24)) = O(24)

# Relationship: octal digits = log₈(n) ≈ log₂(n) / 3
```

## Common Patterns

### File Permissions (Unix/Linux)

```python
# O(log n) - display file permissions in octal
import os

# File mode as integer
file_mode = 0o755  # Standard permissions

# Check permission components
user = (file_mode >> 6) & 0o7      # User permissions
group = (file_mode >> 3) & 0o7     # Group permissions
other = file_mode & 0o7             # Other permissions

print(f"User: {user}, Group: {group}, Other: {other}")
# User: 7, Group: 5, Other: 5

# Display in octal
print(oct(file_mode))  # '0o755'

# Convert back from octal
permissions = int('0o755', 8)  # 493 (decimal)
assert oct(permissions) == '0o755'
```

### Octal Escapes in Strings

```python
# Octal digits represent characters
# Not directly needed, but useful to understand

# '\101' is character with octal code 101
char = '\101'  # Same as chr(65) = 'A'
assert char == 'A'

# View the octal code
code = ord('A')
octal_code = oct(code)  # '0o101'
```

## Comparison with Alternatives

### oct() vs format()

```python
# oct() - returns string with '0o' prefix
oct(255)           # '0o377'

# format() - more flexible
format(255, 'o')   # '377' (no prefix)
format(255, '#o')  # '0o377' (with prefix)

# Performance - both O(log n), similar speed
```

### oct() vs hex() vs bin()

```python
# All O(log n) but different bases
value = 64

hex(value)    # '0x40'     (base 16) - most compact
oct(value)    # '0o100'    (base 8)  - medium
bin(value)    # '0b1000000' (base 2) - longest

# Use case:
# hex - colors, memory addresses
# oct - file permissions, historical/legacy
# bin - bit manipulation
```

## Bidirectional Conversion

```python
# oct() and int() are inverses
# O(log n) each way

x = 64
octal_str = oct(x)       # O(log 64)
restored = int(octal_str, 8)  # O(log 64)
assert restored == x

# Useful for configuration
mode = 0o755
octal_form = oct(mode)   # '0o755'
restored = int(octal_form, 8)  # 493 (decimal)
```

## Performance Patterns

### Batch Conversion

```python
# O(n * log m) - n numbers, each ~m value
numbers = [0o100, 0o200, 0o400]
octal_strings = [oct(n) for n in numbers]
# O(n * log m)

# vs direct format
octal_strings = [f"{n:o}" for n in numbers]
# Similar complexity
```

### Building Octal Values

```python
# O(log n) - combine octal digits
def build_permissions(user, group, other):
    # Each component is 0-7
    return (user << 6) | (group << 3) | other

perms = build_permissions(7, 5, 5)  # 0o755
print(oct(perms))  # '0o755'
```

## Practical Examples

### File Operations

```python
import os
import stat

# O(log n) - file mode operations
def get_permissions(path):
    mode = os.stat(path).st_mode
    perms = stat.S_IMODE(mode)
    return oct(perms)  # Returns octal string

# Create file with specific permissions
# os.chmod('/path/to/file', 0o644)  # Read/write owner, read others
```

### System Calls

```python
# O(log n) - convert to octal for system operations
# Historically common, less so now

permissions = 0o755
print(f"Setting permissions to {oct(permissions)}")
# '0o755' - rwxr-xr-x

permissions = 0o644
print(f"Setting permissions to {oct(permissions)}")
# '0o644' - rw-r--r--
```

### Legacy Code

```python
# Octal literals still used in modern Python
# O(log n) - conversion for display

# Python 2 required octal literals like 0755
# Python 3 uses 0o755

legacy_octal = 0o755
modern_octal = 0o755

assert legacy_octal == modern_octal

# Display
print(oct(legacy_octal))  # '0o755'
```

## Special Cases

### Zero

```python
# O(1)
oct(0)  # '0o0'
```

### Powers of Eight

```python
# O(log n) - shows pattern with single digit
oct(1)      # '0o1'
oct(8)      # '0o10'
oct(64)     # '0o100'
oct(512)    # '0o1000'
oct(8**4)   # '0o10000'
```

### Common Permission Values

```python
# O(1) - common patterns
oct(0o755)  # '0o755' - rwxr-xr-x (normal)
oct(0o644)  # '0o644' - rw-r--r-- (file)
oct(0o600)  # '0o600' - rw------- (private)
oct(0o700)  # '0o700' - rwx------ (directory)
```

## Octal vs Decimal Performance

```python
import timeit

# Performance is similar, O(log n) for both
value = 262144  # 2**18

# Decimal
t1 = timeit.timeit(lambda: str(value), number=100000)

# Octal
t2 = timeit.timeit(lambda: oct(value), number=100000)

# Similar time, decimal slightly faster due to base 10
```

## Best Practices

✅ **Do**:

- Use octal for file permissions and modes
- Use `format(value, 'o')` if you don't need '0o' prefix
- Use octal literals in permission codes: `0o755`
- Use `int(octal_str, 8)` to parse octal

❌ **Avoid**:

- Using octal without clear purpose (confusing)
- Forgetting the '0o' prefix (Python 3 requires it)
- Assuming octal arithmetic (it's still base 10)
- Using octal for new code (hex or binary clearer)

## Related Functions

- **[hex()](hex.md)** - Hexadecimal representation
- **[bin()](bin.md)** - Binary representation
- **[int()](int.md)** - Convert to integer (can parse octal)
- **[format()](format.md)** - Format with specifications

## Version Notes

- **Python 2.x**: Octal literals: `0755` (could omit 'o')
- **Python 3.x**: Octal literals: `0o755` (requires 'o')
- **All versions**: Works with arbitrary precision integers
- **Note**: Octal rarely used in modern code, prefer hex or binary
