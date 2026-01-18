# String Operations Complexity

The `str` type is an immutable sequence of Unicode characters. Python strings have been optimized significantly, especially in Python 3.

## Time Complexity

| Operation | Time | Notes |
|-----------|------|-------|
| `len()` | O(1) | Direct lookup |
| `access[i]` | O(1) | Direct indexing |
| `in` (substring) | O(n + m) worst for long strings, O(n*m) worst for pathological cases | Uses Two-Way / fastsearch algorithm in CPython (linear worst-case) |
| `count(sub)` | O(n + m) worst for long strings, O(n*m) worst for pathological cases | n = string, m = substring; uses Two-Way/fastsearch (linear worst-case) |
| `find(sub)` | O(n + m) worst for long strings, O(n*m) worst for pathological cases | Uses Two-Way / fastsearch algorithm in CPython (linear worst-case) |
| `replace(old, new)` | O(n) | Single pass |
| `split(sep)` | O(n) | Single pass |
| `join()` | O(n) | n = total chars |
| `upper()/lower()` | O(n) | Must process each char |
| `strip()` | O(n) | May check both ends |
| `startswith()`/`endswith()` | O(m) | m = prefix/suffix length |
| `format()` | O(n) | n = template length |
| `s + s` (concatenation) | O(n+m) | Creates new string |
| `s * n` (repetition) | O(n\*len(s)) | Creates new string |
| `slice [::2]` | O(k) | k = slice length |
| `encode()` | O(n) | Convert to bytes |

## Space Complexity

| Operation | Space |
|-----------|-------|
| Slicing | O(k) for k characters |
| Concatenation | O(n+m) new string |
| Repetition | O(n*len(s)) |
| Split | O(n) for result list |
| Join | O(n) total output |

## Implementation Details

### String Interning

```python
# Small strings and identifiers are interned (reused)
s1 = "hello"
s2 = "hello"
print(s1 is s2)  # Likely True - same object

# Large strings are not interned
s3 = "x" * 1000
s4 = "x" * 1000
print(s3 is s4)  # False - different objects
```

### Python 3 Unicode Optimization

```python
# Python 3 uses adaptive string representation
# ASCII strings use less memory than full Unicode

# Compact representation for ASCII
s = "hello"  # Uses 1 byte per character

# Full Unicode representation
s = "hello 世界"  # Uses more bytes for non-ASCII
```

### String Concatenation Performance

```python
# Inefficient: O(n²) - creates new strings repeatedly
result = ""
for i in range(10000):
    result += str(i)  # Copies entire string each time

# Efficient: O(n) - single allocation
result = "".join(str(i) for i in range(10000))
```

## Advanced Features

### String Methods Complexity

| Method | Complexity | Notes |
|--------|-----------|-------|
| `str.find()` | O(n + m) worst for long strings, O(n*m) worst for pathological cases | CPython uses Two-Way / fastsearch algorithm (linear worst-case) |
| `str.count()` | O(n + m) worst for long strings, O(n*m) worst for pathological cases | Non-overlapping searches (Two-Way/fastsearch) |
| `str.replace()` | O(n) | Single pass with copy |
| `str.split()` | O(n) | Single pass |
| `str.startswith()` | O(m) | m = prefix length |
| `str.translate()` | O(n) | Single pass |

### Substring Search

```python
# Linear time on average for substring search
s = "a" * 1000000 + "b"
result = s.find("b")  # Usually O(n) avg, not O(n²)

# CPython uses optimized algorithms (similar to Boyer-Moore)
```

## Version Notes

| Version | Change |
|---------|--------|
| Python 3.0+ | Unicode by default |
| Python 3.3+ | Flexible string representation (PEP 393) |
| Python 3.8+ | f-string performance improvements |
| Python 3.11+ | Faster string operations, better inlining |

## Implementation Comparison

### CPython
Highly optimized with string interning and flexible representations.

### PyPy
JIT compilation provides additional optimization for repeated operations.

### Jython
Backed by Java strings, similar performance characteristics.

## Best Practices

✅ **Do**:

- Use `str.join()` for combining multiple strings
- Use f-strings for formatting (Python 3.6+)
- Use `in` for substring checking (O(n) average)
- Use `.find()` and `.replace()` for efficient manipulation

❌ **Avoid**:

- String concatenation in loops with `+`
- Repeated `.replace()` calls - do once or use regex
- Checking membership with `in` inside nested loops without caching
- Creating many intermediate string objects

## Common Patterns

### Efficient String Building

```python
# Bad: O(n²)
result = ""
for word in words:
    result += word

# Good: O(n)
result = "".join(words)

# Also good: list comprehension with join
result = "".join(w.upper() for w in words)
```

### String Formatting

```python
# Python 3.6+ f-strings (preferred)
name = "World"
message = f"Hello, {name}!"  # Efficient and readable

# Older style (still works)
message = "Hello, {}!".format(name)

# Avoid %
message = "Hello, %s!" % name
```

### Pattern Matching

```python
# Use str methods for simple patterns
if s.startswith("test_"):  # O(m) where m = prefix length
    pass

# Use regex for complex patterns
import re
pattern = re.compile(r"test_\d+")  # Compile once
if pattern.match(s):  # Reuse compiled pattern
    pass
```

## Related Types

- **[Bytes](bytes_func.md)** - Immutable byte sequence
- **[Bytearray](bytearray_func.md)** - Mutable byte sequence
- **[Regex (re)](../stdlib/re.md)** - Pattern matching
