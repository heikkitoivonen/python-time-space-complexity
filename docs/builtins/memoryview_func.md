# memoryview() Function Complexity

The `memoryview()` function creates memory views of bytes-like objects without copying.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Create memoryview | O(1) | O(1) | Just view, no copy of underlying data |
| Index access | O(1) | O(1) | Direct memory access |
| Slicing | O(1) | O(1) | Creates new view object, no data copy |
| `bytes(mv)` conversion | O(n) | O(n) | n = view size; copies data |
| Modification | O(1) | O(1) | Only if underlying buffer is mutable (e.g., bytearray) |

## Basic Usage

### From Bytes

```python
# O(1) - create view, no copy
b = b"hello"
mv = memoryview(b)
# <memory at 0x...>

# Access elements
mv[0]      # 104 (ord('h'))
mv[1:3]    # <memory at 0x...> - slice is also O(1) view
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

# Access as view
mv[0]  # 1
```

## Complexity Details

### No Copying

```python
# O(1) - memoryview doesn't copy data
b = b"a" * 10000
mv = memoryview(b)  # O(1) - instant, no copy

# vs creating a list copy
lst = list(b)  # O(n) - creates list

# View uses original memory
```

### Slicing

```python
# O(1) - slice is just another view
b = b"hello world"
mv = memoryview(b)

# Original view
mv[0]      # 104

# Slice - also O(1), doesn't copy
slice_view = mv[6:11]  # <memory at 0x...> - "world"

# Can modify through slice (if writable)
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

process(view)  # Efficient - no copy
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

### Memory Mapping

```python
# O(1) - create view of mutable buffer
buffer = bytearray(1024)
view = memoryview(buffer)

# Modify through view
view[0:4] = b"HEAD"  # O(4) - copy 4 bytes

# Read back
header = bytes(view[0:4])  # O(4) to convert to bytes
```

### Efficient Data Transfer

```python
# O(1) - pass view instead of copying
def send_data(view):
    # view is O(1) to create, no memory allocation
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
copy = data[100:200]  # O(100) - creates new bytes

# Efficient - memoryview
view = memoryview(data)  # O(1)
slice_view = view[100:200]  # O(1) - just a view
```

### vs List Conversion

```python
# List conversion - O(n)
b = b"hello"
lst = list(b)  # O(5) - [104, 101, 108, 108, 111]

# Memoryview - O(1)
mv = memoryview(b)  # O(1)
mv[0]  # 104
```

### Batch Processing

```python
# O(n) - process without copying
def process_chunks(data):
    mv = memoryview(data)  # O(1)
    
    # Process in chunks - O(n) total
    for i in range(0, len(mv), 1024):
        chunk = mv[i:i+1024]  # O(1) per chunk - just view
        process_chunk(chunk)  # Process view

data = b"x" * 1000000
process_chunks(data)  # Efficient - no copies
```

## Practical Examples

### Binary File Processing

```python
# O(1) - create view of file data
with open("large.bin", "rb") as f:
    data = f.read()

mv = memoryview(data)  # O(1)

# Access header without copying
magic = bytes(mv[0:4])  # O(4) - only copy what needed
version = mv[4]  # O(1)

# Process payload - O(1) view creation
payload = mv[16:]  # O(1)
```

### Image Data Manipulation

```python
# O(1) - view image pixels
from PIL import Image

img = Image.open("photo.png")
img_bytes = img.tobytes()  # Get raw pixel data

mv = memoryview(img_bytes)  # O(1) view

# Access pixel - O(1)
pixel_r = mv[0]  # Red component
pixel_g = mv[1]  # Green component
pixel_b = mv[2]  # Blue component
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
header = parse_header(packet)
```

### Efficient Buffer Sharing

```python
# O(1) - share buffer without copying
def fill_buffer(view, value):
    for i in range(len(view)):
        view[i] = value

buffer = bytearray(1000)
view = memoryview(buffer)  # O(1)

fill_buffer(view, 0)  # Fill with zeros - O(1000)
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
# mv[0] = 72  # TypeError - read-only buffer

# But can create view
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

## Conversion Operations

```python
# O(n) - convert memoryview to bytes
data = b"hello"
mv = memoryview(data)

# Convert to bytes
b = bytes(mv)  # O(5) - creates copy
# b'hello'

# Convert to list
lst = list(mv)  # O(5)
# [104, 101, 108, 108, 111]
```

## Limitations

```python
# O(1) - fast, but limited flexibility
mv = memoryview(b"hello")

# Can't concatenate directly
# mv + mv  # TypeError

# Must convert to bytes first
result = bytes(mv) + bytes(mv)  # O(2n)

# Can't append
# mv.append(33)  # AttributeError
```

## Best Practices

✅ **Do**:

- Use memoryview for zero-copy access
- Create memoryview to pass to functions efficiently
- Use slicing for efficient sub-ranges
- Convert to bytes only when necessary

❌ **Avoid**:

- Using memoryview for single access (overhead not worth it)
- Assuming memoryview works like list (different API)
- Trying to modify immutable buffers (bytes)
- Creating memoryview of very small data

## Related Functions

- **[bytes()](bytes_func.md)** - Immutable bytes
- **[bytearray()](bytearray_func.md)** - Mutable bytes
- **[array](https://docs.python.org/3/library/array.html)** - Typed array module

## Version Notes

- **Python 2.x**: memoryview() available (added in 2.7)
- **Python 3.x**: Improved memoryview with slicing
- **All versions**: Zero-copy view of bytes-like objects
