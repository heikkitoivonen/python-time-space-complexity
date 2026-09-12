# memoryview() Function Complexity

The `memoryview()` function wraps a buffer exporter - `bytes`, `bytearray`,
`array.array` and anything else with the buffer protocol - in a view that
reads and writes the exporter's memory in place. Creating, slicing and casting
a view never copies the data; converting one back to `bytes` or a `list`
always does.

## Complexity Analysis

Let `n` be the number of elements in the view across all its dimensions, `k`
the number of elements a slice covers, and `e` the cost of the exporter's own
`hash()`. Space excludes the exporter's buffer, which every view shares. The
bounds are for the built-in exporters, with element comparisons priced at
O(1) as they are for numbers; a Python `__buffer__()` or a value with its own
`__eq__()` costs whatever it does.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `memoryview(obj)` | O(1) | O(1) | A view object whose size depends on `ndim`, not on the buffer's length; a view of a view shares the same buffer |
| `mv[i]` | O(1) | O(1) | Unpacks one element into a Python object; a multi-dimensional view takes a full index tuple, `mv[i, j]` |
| `mv[i] = v` | O(1) | O(1) | Writable 1-D views, or a full index tuple; a read-only view raises `TypeError` |
| `mv[a:b]` | O(1) | O(1) | Another view over the same memory, whatever `k` is; a step keeps it a view too |
| `mv[a:b] = data` | O(k) | O(1) contiguous, O(k) strided | 1-D views only. Copies `k` elements in; `ValueError` unless `data` holds exactly `k` elements of the same format |
| `len(mv)` | O(1) | O(1) | The first dimension |
| `bytes(mv)`, `mv.tobytes()` | O(n) | O(n) | Copies every byte; a non-contiguous view is gathered element by element |
| `mv == other` | O(n) | O(1) | Element by element, by value: `1` as `'i'` equals `1` as `'h'`, and NaN equals nothing. O(1) `False` when the shapes differ; ordering comparisons raise `TypeError` |
| `hash(mv)` | O(n + e) | O(1) C-contiguous, O(n) otherwise | Read-only views with format `B`, `b` or `c`; the exporter is hashed too, so a short slice of an unhashed `bytes` still pays for the whole `bytes`. Cached, so later calls are O(1) |
| `for x in mv`, `x in mv` | O(n) | O(1) | 1-D views only; `in` is a linear scan |

## Methods

| Method | Time | Space | Notes |
|--------|------|-------|-------|
| `tobytes(order='C')` | O(n) | O(n) | `order` picks the element order of the copy, not its size |
| `tolist()` | O(n) | O(n) | One list entry per element, nested by dimension; a 0-D view returns its single element itself |
| `hex(sep, bytes_per_sep)` | O(n) | O(n) | Two characters per byte; a non-contiguous view copies itself first |
| `cast(format, shape)` | O(1) | O(1) | Reinterprets the same memory. C-contiguous views only, one side a byte format, the total byte size unchanged, and either the source or the new `shape` 1-D |
| `toreadonly()` | O(1) | O(1) | A new read-only view of the same buffer |
| `release()` | O(1) | O(1) | Reading or writing through the view afterwards raises `ValueError`; until then a `bytearray` exporter cannot be resized |
| `count(value)` | O(n) | O(1) | 3.14+. Compares every element; 1-D views only |
| `index(value, start, stop)` | O(n) | O(1) | 3.14+. Stops at the first match; `ValueError` when absent. 1-D views only |

## Attributes

| Attribute | Time | Space | Notes |
|-----------|------|-------|-------|
| `obj` | O(1) | O(1) | The exporter itself |
| `nbytes` | O(1) | O(1) | `n * itemsize` |
| `readonly` | O(1) | O(1) | |
| `format` | O(1) | O(1) | The `struct` format string, `'B'` for `bytes` |
| `itemsize` | O(1) | O(1) | Bytes per element |
| `ndim` | O(1) | O(1) | |
| `shape`, `strides`, `suboffsets` | O(ndim) | O(ndim) | `shape` and `strides` build a new tuple on every access when `ndim > 0`; `suboffsets` is `()` for ordinary buffers |
| `contiguous`, `c_contiguous`, `f_contiguous` | O(1) | O(1) | Flags computed when the view is created |

## Basic Usage

### From Bytes

```python
# O(1) - create view, no copy
b = b"hello"
mv = memoryview(b)
mv.obj is b   # True

# Access elements
mv[0]      # 104 (ord('h'))
mv[1:3]    # <memory at 0x...> - slice is also an O(1) view
```

### From Bytearray

```python
# O(1) - create view
ba = bytearray(b"hello")
mv = memoryview(ba)

# Can modify through view
mv[0] = 72  # O(1) - changes 'h' to 'H'
print(ba)   # bytearray(b'Hello')
```

### From Array

```python
# O(1) - works with array module
import array

arr = array.array('i', [1, 2, 3, 4, 5])
mv = memoryview(arr)

# Elements are the exporter's, not bytes
mv[0]        # 1
mv.format    # 'i'
mv.itemsize  # 4
mv.nbytes    # 20
```

## Complexity Details

### No Copying

```python
# O(1) - memoryview doesn't copy data
b = b"a" * 10000
mv = memoryview(b)  # O(1) - the view is the same size for any buffer

# vs creating a list copy
lst = list(b)  # O(n) - one list entry per byte
```

### Slicing

```python
# O(1) - slice is just another view
ba = bytearray(b"hello world")
mv = memoryview(ba)

# Slice - also O(1), doesn't copy
world = mv[6:11]
world.obj is ba   # True

# Writes through the slice land in the original
world[0] = 87     # 'W'
print(ba)         # bytearray(b'hello World')
```

### Indexing

```python
# O(1) - direct memory access
mv = memoryview(b"test")

# Read element
byte_val = mv[0]  # 116

# Write element (if mutable)
ba = bytearray(b"test")
mv = memoryview(ba)
mv[0] = 84  # O(1) - changes to 'T'
```

### Hashing and Equality

```python
# O(n) - both walk every element
b = b"hello"
mv = memoryview(b)
mv == b                 # True
mv == mv[1:]            # False - O(1), the shapes differ

hash(mv) == hash(b)     # True; cached, so the second call is O(1)

# A writable view cannot be hashed
try:
    hash(memoryview(bytearray(b"hello")))
except ValueError:
    pass                # cannot hash writable memoryview object
```

### Casting

```python
# O(1) - the same bytes, read as a different element type
raw = bytes(8)
as_ints = memoryview(raw).cast('i')
len(as_ints)      # 2
as_ints.nbytes    # 8, unchanged

# A shape turns a flat buffer into a matrix, still without copying
grid = memoryview(bytes(range(6))).cast('B', (2, 3))
grid.tolist()     # [[0, 1, 2], [3, 4, 5]] - O(n)
```

## Common Patterns

### Zero-Copy Data Access

```python
# O(1) - no memory copy
data = bytearray(b"binary data here")
view = memoryview(data)  # O(1)

# Process without copying
def process(view):
    for i in range(len(view)):
        print(view[i])

process(view)  # O(n) - one O(1) read per element
```

### Efficient Binary Protocol

```python
# O(1) - parse binary data without copying
binary_data = b"\x01\x02\x03\x04"
view = memoryview(binary_data)

# Parse header - O(1)
header_type = view[0]   # 1
header_version = view[1] # 2

# Parse payload - O(1) slice
payload = view[2:4]  # <memory>
```

### Slice Assignment

```python
# O(1) - create view of mutable buffer
buffer = bytearray(1024)
view = memoryview(buffer)

# Modify through view
view[0:4] = b"HEAD"  # O(k) - copies 4 bytes in

# Read back
header = bytes(view[0:4])  # O(k) to convert to bytes

# The lengths must match
try:
    view[0:4] = b"HEADER"
except ValueError:
    pass  # lvalue and rvalue have different structures
```

### Efficient Data Transfer

```python
# O(1) - pass view instead of copying
def send_data(view):
    # view is O(1) to create, no copy of the data
    # Copy only when actually sending
    bytes_to_send = bytes(view)  # O(n)
    # network.send(bytes_to_send)

data = b"large data" * 1000
view = memoryview(data)  # O(1) - instant
# send_data(view)  # Efficient
```

## Performance Patterns

### vs Copying

```python
# Inefficient - copying
data = b"x" * 10**6
copy = data[100:200]  # O(k) - creates new bytes

# Efficient - memoryview
view = memoryview(data)  # O(1)
slice_view = view[100:200]  # O(1) - just a view
```

### vs List Conversion

```python
# List conversion - O(n)
b = b"hello"
lst = list(b)  # [104, 101, 108, 108, 111]

# Memoryview - O(1)
mv = memoryview(b)  # O(1)
mv[0]  # 104
```

### Batch Processing

```python
def process_chunk(chunk):
    return sum(chunk)  # O(k) over the chunk's elements

# O(n) - process without copying
def process_chunks(data):
    mv = memoryview(data)  # O(1)

    # Process in chunks - O(n) total
    total = 0
    for i in range(0, len(mv), 1024):
        chunk = mv[i:i+1024]  # O(1) per chunk - just view
        total += process_chunk(chunk)
    return total

data = b"x" * 1000000
process_chunks(data)  # Efficient - no copies
```

## Practical Examples

### Binary File Processing

```python
import tempfile

with tempfile.TemporaryFile() as f:
    f.write(b"MAGC\x02" + bytes(11) + b"payload")
    f.seek(0)
    data = f.read()  # O(n) - the file is read once

mv = memoryview(data)  # O(1)

# Access header without copying
magic = bytes(mv[0:4])  # O(k) - only copy what is needed
version = mv[4]  # O(1)

# Process payload - O(1) view creation
payload = mv[16:]  # O(1)
```

### Network Protocol Parser

```python
# O(1) - parse protocol messages
def parse_header(data):
    view = memoryview(data)  # O(1)

    # Extract fields - all O(1)
    msg_type = view[0]
    length = int.from_bytes(view[1:3], 'big')
    flags = view[3]

    return {
        'type': msg_type,
        'length': length,
        'flags': flags
    }

packet = b"\x01\x00\x10\xFF" + b"payload..."
header = parse_header(packet)  # {'type': 1, 'length': 16, 'flags': 255}
```

### Efficient Buffer Sharing

```python
# O(1) - share buffer without copying
def fill_buffer(view, value):
    for i in range(len(view)):
        view[i] = value

buffer = bytearray(1000)
view = memoryview(buffer)  # O(1)

fill_buffer(view, 0)  # Fill with zeros - O(n)
# buffer is now filled
```

## Edge Cases

### Empty Memoryview

```python
# O(1)
mv = memoryview(b"")   # <memory at 0x...>
len(mv)  # 0
```

### Single Byte

```python
# O(1)
mv = memoryview(b"a")
mv[0]  # 97
```

### Immutable View

```python
# O(1) - view of bytes (immutable)
mv = memoryview(b"hello")

# Cannot modify
try:
    mv[0] = 72
except TypeError:
    pass  # cannot modify read-only memory
```

### Mutable View

```python
# O(1) - view of bytearray (mutable)
ba = bytearray(b"hello")
mv = memoryview(ba)

# Can modify
mv[0] = 72  # O(1) - 'H'
print(ba)   # bytearray(b'Hello')
```

### Memory Sharing

```python
# O(1) - modifications visible in original
ba = bytearray(b"test")
mv = memoryview(ba)

# Modify through view
mv[0] = 84  # 'T'

# Changes visible in original
print(ba)   # bytearray(b'Test')

# Changes also visible in view
print(mv[0])  # 84
```

### Releasing a View

```python
# O(1) - a live view pins a bytearray's size
ba = bytearray(b"test")
mv = memoryview(ba)

try:
    ba.append(33)
except BufferError:
    pass  # Existing exports of data: object cannot be re-sized

mv.release()   # O(1)
ba.append(33)  # fine now

try:
    mv[0]
except ValueError:
    pass  # operation forbidden on released memoryview object
```

## Conversion Operations

```python
# O(n) - convert memoryview to bytes
data = b"hello"
mv = memoryview(data)

# Convert to bytes
b = bytes(mv)  # O(n) - creates copy
# b'hello'

# Convert to list
lst = list(mv)  # O(n)
# [104, 101, 108, 108, 111]

# Hex string - two characters per byte
mv.hex()  # '68656c6c6f'
```

## Limitations

```python
# O(1) - fast, but limited flexibility
mv = memoryview(b"hello")

# Can't concatenate directly
try:
    mv + mv
except TypeError:
    pass

# Must convert to bytes first
result = bytes(mv) + bytes(mv)  # O(n)

# Can't append - a view has a fixed size
hasattr(mv, "append")  # False
```

## Best Practices

✅ **Do**:

- Use memoryview for zero-copy access
- Create memoryview to pass to functions efficiently
- Use slicing for efficient sub-ranges
- Convert to bytes only when necessary
- Release a view of a `bytearray` before resizing it

❌ **Avoid**:

- Creating a view for one short, one-off slice - the view object is bigger
  than a short `bytes` copy
- Assuming memoryview works like list (different API)
- Trying to modify immutable buffers (bytes)
- Hashing a writable view, or one over `bytearray` - both raise

## Related Functions

- **[bytes()](bytes_func.md)** - Immutable bytes
- **[bytearray()](bytearray_func.md)** - Mutable bytes
- **[array](../stdlib/array.md)** - Typed array module

## Version Notes

- **Python 3.12+**: exporters can be written in Python with `__buffer__()` and
  `__release_buffer__()`; `len()` of a 0-dimensional view raises `TypeError`
- **Python 3.14+**: `count()` and `index()`; `memoryview[int]` is a generic
  alias
