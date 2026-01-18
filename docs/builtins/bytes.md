# Bytes and Bytearray Operations Complexity

The `bytes` type is an immutable sequence of bytes, while `bytearray` is the mutable equivalent.

## Time Complexity

### Bytes

| Operation | Time | Notes |
|-----------|------|-------|
| `len()` | O(1) | Direct lookup |
| `access[i]` | O(1) | Direct indexing |
| `in` (membership) | O(n) | Linear search |
| `index(x)` | O(n) | Linear search |
| `count(x)` | O(n) | Linear scan |
| `copy()` | O(n) | Creates new bytes object |
| `join()` | O(n) | Single pass, n = total output length |
| `split()` | O(n) | Single pass |
| `find(sub)` | O(n + m) worst for long strings, O(n*m) worst for pathological cases | n = bytes length, m = pattern length |
| `replace(old, new)` | O(n) | Creates new bytes object |
| `decode()` | O(n) | Convert to string |
| `hex()` | O(n) | Convert to hex |

*Note: bytes is immutable, so operations that appear to modify return new objects (O(n) space).*

### Bytearray

| Operation | Time | Notes |
|-----------|------|-------|
| `append(x)` | O(1)* | Amortized, may resize |
| `insert(i, x)` | O(n) | Shift elements |
| `extend(iterable)` | O(k) | k = length |
| `pop()` | O(1) | Remove last |
| `pop(0)` | O(n) | Shift remaining |
| `remove(x)` | O(n) | Search and remove |
| `clear()` | O(n) | Deallocate |

## Space Complexity

| Operation | Space |
|-----------|-------|
| `bytes()` copy | O(n) |
| `bytearray()` operations | O(1) amortized |
| `decode()` | O(n) for string |
| `join()` | O(n) result |

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
