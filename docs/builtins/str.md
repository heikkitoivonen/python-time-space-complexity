# String Operations Complexity

The `str` type is an immutable sequence of Unicode characters. Python strings have been optimized significantly, especially in Python 3.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Direct lookup |
| `access[i]` | O(1) | O(1) | Direct indexing |
| `in` (substring) | O(n + m) avg | O(1) | Uses Two-Way / fastsearch algorithm in CPython |
| `s + s` (concatenation) | O(n+m) | O(n+m) | Creates new string |
| `s * n` (repetition) | O(n\*len(s)) | O(n\*len(s)) | Creates new string |
| `slice [::2]` | O(k) | O(k) | k = slice length |
| **Search** ||||
| `find(sub)` | O(n + m) avg | O(1) | Uses Two-Way / fastsearch algorithm in CPython |
| `rfind(sub)` | O(n*m) worst | O(1) | Uses backward Boyer-Moore-Horspool |
| `index(sub)` | O(n + m) | O(1) | Like find() but raises ValueError if not found |
| `rindex(sub)` | O(n*m) worst | O(1) | Like rfind() but raises ValueError if not found |
| `count(sub)` | O(n + m) avg | O(1) | n = string, m = substring |
| `startswith(prefix)` | O(m) | O(1) | m = prefix length |
| `endswith(suffix)` | O(m) | O(1) | m = suffix length |
| **Replace/Translate** ||||
| `replace(old, new)` | O(n) | O(n) | Single pass |
| `translate(table)` | O(n) | O(n) | Single pass with table lookup |
| `maketrans()` | O(k) | O(k) | k = number of mappings; static method |
| `expandtabs(tabsize)` | O(n) | O(n) | Replace tabs with spaces |
| `removeprefix(prefix)` | O(n) | O(n) | Returns slice if prefix matches (Python 3.9+) |
| `removesuffix(suffix)` | O(n) | O(n) | Returns slice if suffix matches (Python 3.9+) |
| **Split/Join** ||||
| `split(sep)` | O(n) | O(n) | Single pass |
| `rsplit(sep)` | O(n) | O(n) | Split from right |
| `splitlines()` | O(n) | O(n) | Split on line boundaries |
| `partition(sep)` | O(n) | O(n) | Split into 3-tuple at first sep |
| `rpartition(sep)` | O(n) | O(n) | Split into 3-tuple at last sep |
| `join(iterable)` | O(n) | O(n) | n = total output chars |
| **Case Conversion** ||||
| `upper()` | O(n) | O(n) | Must process each char |
| `lower()` | O(n) | O(n) | Must process each char |
| `capitalize()` | O(n) | O(n) | Uppercase first, lowercase rest |
| `title()` | O(n) | O(n) | Titlecase words |
| `swapcase()` | O(n) | O(n) | Swap upper/lower |
| `casefold()` | O(n) | O(n) | Aggressive lowercase for caseless matching |
| **Stripping** ||||
| `strip(chars)` | O(n) | O(n) | Remove from both ends |
| `lstrip(chars)` | O(n) | O(n) | Remove from left |
| `rstrip(chars)` | O(n) | O(n) | Remove from right |
| **Padding/Alignment** ||||
| `center(width)` | O(n) | O(n) | Pad both sides |
| `ljust(width)` | O(n) | O(n) | Pad right side |
| `rjust(width)` | O(n) | O(n) | Pad left side |
| `zfill(width)` | O(n) | O(n) | Pad with zeros |
| **Predicates** ||||
| `isalnum()` | O(n) | O(1) | Check alphanumeric |
| `isalpha()` | O(n) | O(1) | Check alphabetic |
| `isascii()` | O(n) | O(1) | Check ASCII (Python 3.7+) |
| `isdecimal()` | O(n) | O(1) | Check decimal chars |
| `isdigit()` | O(n) | O(1) | Check digit chars |
| `isidentifier()` | O(n) | O(1) | Check valid identifier |
| `islower()` | O(n) | O(1) | Check lowercase |
| `isnumeric()` | O(n) | O(1) | Check numeric chars |
| `isprintable()` | O(n) | O(1) | Check printable |
| `isspace()` | O(n) | O(1) | Check whitespace |
| `istitle()` | O(n) | O(1) | Check titlecase |
| `isupper()` | O(n) | O(1) | Check uppercase |
| **Formatting** ||||
| `format(*args)` | O(n) | O(n) | n = template length |
| `format_map(mapping)` | O(n) | O(n) | Like format() with mapping |
| **Encoding** ||||
| `encode(encoding)` | O(n) | O(n) | Convert to bytes |

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

## Further Reading

- [CPython Internals: str](https://zpoint.github.io/CPython-Internals/BasicObject/str/str.html) -
  Deep dive into CPython's str implementation
