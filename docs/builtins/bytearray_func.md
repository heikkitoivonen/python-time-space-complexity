# bytearray() Function Complexity

The `bytearray()` function creates mutable byte arrays from strings, iterables, or allocates empty bytearrays.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Empty bytearray | O(1) | O(1) | bytearray() |
| From string with encoding | O(n) | O(n) | n = string length |
| From iterable | O(n) | O(n) | n = iterable length |
| From int (size) | O(n) | O(n) | n = requested size |
| Copy bytes | O(n) | O(n) | n = bytes length |

## Basic Usage

### Create Empty Bytearray

```python
# O(1)
ba = bytearray()       # bytearray(b'')
ba = bytearray(0)      # bytearray(b'') (size 0)
```

### From String with Encoding

```python
# O(n) - where n = string length
ba = bytearray("hello", "utf-8")        # bytearray(b'hello')
ba = bytearray("café", "utf-8")         # bytearray(b'caf\xc3\xa9')
ba = bytearray("中国", "utf-8")         # Multiple bytes per character
```

### Allocate Bytearray (Zero-filled)

```python
# O(n) - where n = size
ba = bytearray(10)      # bytearray(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
ba = bytearray(1000)    # 1000 zero bytes
```

### From Iterable of Integers

```python
# O(n) - where n = number of items
ba = bytearray([65, 66, 67])         # bytearray(b'ABC')
ba = bytearray(range(256))           # All byte values
ba = bytearray([0, 255, 128, 64])    # bytearray(b'\x00\xff\x80@')
```

### Copy Bytes

```python
# O(n) - where n = bytes length
original = b"hello"
ba = bytearray(original)  # Creates mutable copy: bytearray(b'hello')
```

## Complexity Details

### String Encoding

```python
# O(n) - linear in string length
short = bytearray("hi", "utf-8")        # O(2)
long = bytearray("a" * 1000, "utf-8")   # O(1000)

# Each character must be encoded
# ASCII characters = 1 byte each
# UTF-8 multibyte = multiple bytes
```

### Mutability Operations

```python
# All O(1) per operation on bytearray (unlike immutable bytes)
ba = bytearray(b"hello")

ba[0] = 72  # O(1) - change 'h' to 'H'
ba.append(33)  # O(1) amortized - may trigger resize
ba.extend([33, 33])  # O(k) amortized - add k items
```

### From Iterable

```python
# O(n) - iterate and convert
data = [65, 66, 67, 68, 69]
ba = bytearray(data)  # O(5)

# With range
ba = bytearray(range(256))  # O(256)
```

## Common Patterns

### Encoding Strings (Mutable)

```python
# O(n) - convert text to mutable bytes
text = "Hello, World!"
ba = bytearray(text, "utf-8")  # O(13)
# bytearray(b'Hello, World!')

# Modify in place
ba[0] = ord('h')  # O(1) - change first character
```

### Building Binary Data

```python
# O(n) - build byte sequence
ba = bytearray()

# Add bytes
ba.extend([0x48, 0x65, 0x6C, 0x6C, 0x6F])  # O(5)
# bytearray(b'Hello')

# Modify specific bytes
ba[0] = 0x48  # O(1)
```

### Byte Manipulation

```python
# O(1) per operation
ba = bytearray(b"test")

# Index access
ba[0]  # 116 (ord('t'))

# Modification
ba[0] = 84  # O(1) - change to 'T'

# Append
ba.append(33)  # O(1) amortized

# Extend
ba.extend(b"ing")  # O(3) - append "ing"
```

## Performance Patterns

### vs bytes (Immutable)

```python
# bytes - immutable, cannot modify
b = b"hello"
# b[0] = 72  # TypeError - immutable

# bytearray - mutable
ba = bytearray(b"hello")
ba[0] = 72  # O(1) - OK, mutable
```

### Building Byte Strings

```python
# Inefficient with bytes
b = b""
for i in range(100):
    b += bytes([i])  # O(n^2) - recreates each time!

# Better with bytearray
ba = bytearray()
for i in range(100):
    ba.append(i)  # O(1) amortized - efficient

# Convert to bytes when done
final_bytes = bytes(ba)  # O(n)
```

### Modifying Binary Data

```python
# O(n) - convert to bytearray for modifications
original = b"\x48\x65\x6C\x6C\x6F"  # "Hello"

# Make mutable copy
ba = bytearray(original)  # O(n)

# Modify
ba[0] = 0x68  # O(1)
ba[1] = 0x69  # O(1)

# Convert back
modified = bytes(ba)  # O(n)
```

## Practical Examples

### Network Protocol Building

```python
# O(n) - build binary protocol message
def build_packet(header, payload):
    packet = bytearray()
    
    packet.extend(header)      # O(|header|)
    packet.append(len(payload))  # O(1)
    packet.extend(payload)     # O(|payload|)
    
    return bytes(packet)  # O(n) - convert to immutable
```

### Image Data Manipulation

```python
# O(n) - modify pixel data
image_data = bytearray([255, 0, 0, 0, 255, 0, 0, 0, 255])
# Three RGB pixels

# Modify pixel values
image_data[0] = 200  # O(1) - change red value
image_data[4] = 200  # O(1) - change green value

# Process efficiently without copying
```

### Cryptographic Operations

```python
# O(n) - prepare data for encryption
import hashlib

message = "Secret message"
ba = bytearray(message, "utf-8")  # O(n)

# Modify if needed
ba[0] = ord('s')  # O(1)

# Hash
hashed = hashlib.sha256(ba).hexdigest()  # O(n)
```

### File Data Processing

```python
# O(n) - read and modify file
with open("data.bin", "rb") as f:
    data = bytearray(f.read())  # O(n) - read entire file

# Modify specific bytes
data[0] = 0x00  # O(1) - change magic number

# Write back
with open("output.bin", "wb") as f:
    f.write(data)  # O(n)
```

## Edge Cases

### Empty Bytearray

```python
# O(1)
ba = bytearray()       # bytearray(b'')
ba = bytearray(0)      # bytearray(b'') - size 0
ba = bytearray("")     # bytearray(b'') - empty string
```

### Zero-size Allocation

```python
# O(1)
ba = bytearray(0)  # bytearray(b'') - empty
```

### Invalid Encoding

```python
# O(n) - error during conversion
try:
    ba = bytearray("café", "ascii")  # UnicodeEncodeError
except UnicodeEncodeError:
    pass
```

### Invalid Iterable Values

```python
# O(n) - error checking
try:
    ba = bytearray([0, 256, 128])  # ValueError - 256 > 255
except ValueError:
    pass

try:
    ba = bytearray([-1, 50, 100])  # ValueError - negative
except ValueError:
    pass
```

### Large Allocations

```python
# O(n) - allocate and zero-fill
huge = bytearray(10**7)  # 10MB of zeros
```

## Modifying Bytearray

```python
# Various O(1) or O(k) operations
ba = bytearray(b"hello")

# Index assignment - O(1)
ba[0] = 72  # bytearray(b'Hello')

# Append - O(1) amortized
ba.append(33)  # bytearray(b'Hello!')

# Extend - O(k)
ba.extend(b"!!!")  # bytearray(b'Hello!!!!')

# Insert - O(n) - must shift
ba.insert(5, 32)  # O(n) - shifts remaining bytes

# Remove - O(n)
ba.remove(33)  # O(n) - removes first occurrence

# Pop - O(1) if last, O(n) if middle
ba.pop()  # O(1) - remove last byte
ba.pop(0)  # O(n) - remove first byte
```

## Comparison with bytes()

```python
# bytes - immutable
b = bytes("hello", "utf-8")
# b[0] = 72  # TypeError

# bytearray - mutable
ba = bytearray("hello", "utf-8")
ba[0] = 72  # O(1) - OK

# Both O(n) to create, but bytearray allows modification
```

## Best Practices

✅ **Do**:
- Use bytearray when you need mutable bytes
- Build byte sequences with bytearray then convert to bytes
- Modify in-place rather than concatenating
- Specify encoding explicitly: `bytearray(text, "utf-8")`

❌ **Avoid**:
- Using bytearray when immutable bytes sufficient
- Concatenating bytes in loops (use bytearray)
- Forgetting encoding parameter
- Assuming bytearray is always faster (similar performance)

## Related Functions

- **[bytes()](bytes_func.md)** - Immutable bytes
- **[str()](str_func.md)** - Convert to string
- **[memoryview()](memoryview_func.md)** - View bytes without copying
- **[encode()](str.md)** - String method to bytes

## Version Notes

- **Python 2.x**: bytearray() available
- **Python 3.x**: Same behavior
- **All versions**: Mutable, unhashable
