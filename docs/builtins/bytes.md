# Bytes and Bytearray Operations Complexity

The `bytes` type is an immutable sequence of bytes, while `bytearray` is the mutable equivalent.

## Complexity Reference

### Bytes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Direct lookup |
| `access[i]` | O(1) | O(1) | Direct indexing |
| `in` (membership) | O(n) | O(1) | Linear search |
| **Search** ||||
| `find(sub)` | O(n + m) avg | O(1) | n = bytes length, m = pattern length |
| `rfind(sub)` | O(n*m) worst | O(1) | Search from right |
| `index(sub)` | O(n) | O(1) | Like find() but raises ValueError |
| `rindex(sub)` | O(n*m) worst | O(1) | Like rfind() but raises ValueError |
| `count(sub)` | O(n) | O(1) | Count non-overlapping occurrences |
| `startswith(prefix)` | O(m) | O(1) | m = prefix length |
| `endswith(suffix)` | O(m) | O(1) | m = suffix length |
| **Replace/Translate** ||||
| `replace(old, new)` | O(n) | O(n) | Creates new bytes object |
| `translate(table)` | O(n) | O(n) | Single pass with table lookup |
| `maketrans(from, to)` | O(k) | O(k) | k = mapping size; static method |
| `expandtabs(tabsize)` | O(n) | O(n) | Replace tabs with spaces |
| `removeprefix(prefix)` | O(n) | O(n) | Returns slice if prefix matches (Python 3.9+) |
| `removesuffix(suffix)` | O(n) | O(n) | Returns slice if suffix matches (Python 3.9+) |
| **Split/Join** ||||
| `split(sep)` | O(n) | O(n) | Single pass |
| `rsplit(sep)` | O(n) | O(n) | Split from right |
| `splitlines()` | O(n) | O(n) | Split on line boundaries |
| `partition(sep)` | O(n) | O(n) | Split into 3-tuple at first sep |
| `rpartition(sep)` | O(n) | O(n) | Split into 3-tuple at last sep |
| `join(iterable)` | O(n) | O(n) | n = total output length |
| **Case Conversion** ||||
| `upper()` | O(n) | O(n) | ASCII uppercase |
| `lower()` | O(n) | O(n) | ASCII lowercase |
| `capitalize()` | O(n) | O(n) | Uppercase first, lowercase rest |
| `title()` | O(n) | O(n) | Titlecase words |
| `swapcase()` | O(n) | O(n) | Swap upper/lower |
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
| `isdigit()` | O(n) | O(1) | Check digit chars |
| `islower()` | O(n) | O(1) | Check lowercase |
| `isspace()` | O(n) | O(1) | Check whitespace |
| `istitle()` | O(n) | O(1) | Check titlecase |
| `isupper()` | O(n) | O(1) | Check uppercase |
| **Encoding** ||||
| `decode(encoding)` | O(n) | O(n) | Convert to string |
| `hex()` | O(n) | O(n) | Convert to hex string |
| `fromhex(string)` | O(n) | O(n) | Create bytes from hex; class method |

*Note: bytes is immutable, so operations that appear to modify return new objects (O(n) space).*

### Bytearray

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Direct lookup |
| `access[i]` | O(1) | O(1) | Direct indexing |
| `in` (membership) | O(n) | O(1) | Linear search |
| **Mutation** ||||
| `append(x)` | O(1)* | O(1) | Amortized, may resize |
| `extend(iterable)` | O(k) | O(k) | k = length |
| `insert(i, x)` | O(n) | O(1) | Shift elements |
| `pop()` | O(1) | O(1) | Remove last |
| `pop(i)` | O(n) | O(1) | Remove at index; shifts remaining |
| `remove(x)` | O(n) | O(1) | Search and remove |
| `clear()` | O(n) | O(1) | Deallocate |
| `copy()` | O(n) | O(n) | Shallow copy |
| `reverse()` | O(n) | O(1) | Reverse in-place |
| `resize(n)` | O(n) | O(1) | Resize to n bytes; may truncate or zero-fill |
| **Search** ||||
| `find(sub)` | O(n + m) avg | O(1) | n = length, m = pattern length |
| `rfind(sub)` | O(n*m) worst | O(1) | Search from right |
| `index(sub)` | O(n) | O(1) | Like find() but raises ValueError |
| `rindex(sub)` | O(n*m) worst | O(1) | Like rfind() but raises ValueError |
| `count(sub)` | O(n) | O(1) | Count non-overlapping occurrences |
| `startswith(prefix)` | O(m) | O(1) | m = prefix length |
| `endswith(suffix)` | O(m) | O(1) | m = suffix length |
| **Replace/Translate** ||||
| `replace(old, new)` | O(n) | O(n) | Creates new bytearray |
| `translate(table)` | O(n) | O(n) | Single pass with table lookup |
| `maketrans(from, to)` | O(k) | O(k) | k = mapping size; static method |
| `expandtabs(tabsize)` | O(n) | O(n) | Replace tabs with spaces |
| `removeprefix(prefix)` | O(n) | O(n) | Returns slice if prefix matches |
| `removesuffix(suffix)` | O(n) | O(n) | Returns slice if suffix matches |
| **Split/Join** ||||
| `split(sep)` | O(n) | O(n) | Single pass |
| `rsplit(sep)` | O(n) | O(n) | Split from right |
| `splitlines()` | O(n) | O(n) | Split on line boundaries |
| `partition(sep)` | O(n) | O(n) | Split into 3-tuple at first sep |
| `rpartition(sep)` | O(n) | O(n) | Split into 3-tuple at last sep |
| `join(iterable)` | O(n) | O(n) | n = total output length |
| **Case Conversion** ||||
| `upper()` | O(n) | O(n) | ASCII uppercase |
| `lower()` | O(n) | O(n) | ASCII lowercase |
| `capitalize()` | O(n) | O(n) | Uppercase first, lowercase rest |
| `title()` | O(n) | O(n) | Titlecase words |
| `swapcase()` | O(n) | O(n) | Swap upper/lower |
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
| `isdigit()` | O(n) | O(1) | Check digit chars |
| `islower()` | O(n) | O(1) | Check lowercase |
| `isspace()` | O(n) | O(1) | Check whitespace |
| `istitle()` | O(n) | O(1) | Check titlecase |
| `isupper()` | O(n) | O(1) | Check uppercase |
| **Encoding** ||||
| `decode(encoding)` | O(n) | O(n) | Convert to string |
| `hex()` | O(n) | O(n) | Convert to hex string |
| `fromhex(string)` | O(n) | O(n) | Create bytearray from hex; class method |

## Implementation Details

### Bytes vs Bytearray

```python
# Bytes: immutable
b = b"hello"
b[0]           # 104 (ASCII value)
b[0] = 106     # TypeError: bytes are immutable

# Bytearray: mutable
ba = bytearray(b"hello")
ba[0] = 106    # OK, becomes b"jello"
ba.append(33)  # OK
```

### Performance Comparison

```python
# Bytes: immutable, hashable
data = b"x" * 1000000
h = hash(data)      # Can be hashed

# Bytearray: mutable, not hashable
data_mut = bytearray(data)
h = hash(data_mut)  # TypeError: not hashable
```

## Use Cases

### Bytes
- Fixed binary data
- As dictionary keys (immutable)
- Network protocols
- File I/O

### Bytearray
- Modifying binary data
- Building up binary streams
- Incremental encoding/decoding
- Memoryview compatibility

## Common Operations

### Encoding/Decoding

```python
# String to bytes
s = "Hello, 世界"
b = s.encode('utf-8')      # O(n)
b = s.encode('ascii')      # O(n), may raise

# Bytes to string
b = b"Hello"
s = b.decode('utf-8')      # O(n)
s = b.decode('ascii')      # O(n)
```

### Searching and Replacing

```python
# Find substring: O(n + m) worst for long strings, O(n*m) worst for pathological cases
data = b"hello world"
idx = data.find(b"world")  # O(n)

# Replace: O(n)
new = data.replace(b"world", b"python")

# Split: O(n)
parts = data.split(b" ")
```

## Version Notes

- **All Python 3.x**: Core complexity unchanged
- **Python 3.2+**: Bytearray optimizations
- **Python 3.5+**: Better unicode handling

## Related Types

- **[Strings](str.md)** - Unicode text
- **[Lists](list.md)** - Mutable sequences
- **Memoryview** - Zero-copy buffer interface

## Further Reading

- [CPython Internals: bytes](https://zpoint.github.io/CPython-Internals/BasicObject/bytes/bytes.html) -
  Deep dive into CPython's bytes implementation
