# bytes() Function Complexity

The `bytes()` function creates bytes objects from strings, iterables, or allocates empty bytes.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Empty bytes | O(1) | O(1) | bytes() |
| From string with encoding | O(n) | O(n) | n = string length |
| From iterable | O(n) | O(n) | n = iterable length |
| From int (size) | O(n) | O(n) | n = requested size |
| Copy bytes | O(n) | O(n) | n = bytes length |

## Basic Usage

### Create Empty Bytes

```python
# O(1)
b = bytes()       # b''
b = bytes(0)      # b'' (size 0)
```

### From String with Encoding

```python
# O(n) - where n = string length
b = bytes("hello", "utf-8")        # b'hello'
b = bytes("café", "utf-8")         # b'caf\xc3\xa9' (3 bytes for é)
b = bytes("中国", "utf-8")         # Multiple bytes per character
```

### Allocate Bytes (Zero-filled)

```python
# O(n) - where n = size
b = bytes(10)      # b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
b = bytes(1000)    # 1000 zero bytes
```

### From Iterable of Integers

```python
# O(n) - where n = number of items
b = bytes([65, 66, 67])         # b'ABC'
b = bytes(range(256))           # All byte values
b = bytes([0, 255, 128, 64])    # b'\x00\xff\x80@'
```

### Copy Bytes

```python
# O(n) - where n = bytes length
original = b"hello"
copy = bytes(original)  # Creates new bytes object
```

## Complexity Details

### String Encoding

```python
# O(n) - linear in string length
short = bytes("hi", "utf-8")       # O(2)
long = bytes("a" * 1000, "utf-8")  # O(1000)

# Each character must be encoded
# ASCII characters = 1 byte each
# UTF-8 multibyte = multiple bytes
```

### Multibyte Characters

```python
# O(n) - but n = encoded byte length, not character count
english = bytes("hello", "utf-8")  # O(5) - 5 ASCII characters
# Result: b'hello' (5 bytes)

accented = bytes("café", "utf-8")  # O(4) - 4 characters
# Result: b'caf\xc3\xa9' (5 bytes!) - é = 2 bytes in UTF-8

chinese = bytes("中国", "utf-8")   # O(2) - 2 characters
# Result: 6 bytes (3 bytes per character)
```

### From Iterable

```python
# O(n) - iterate and convert
data = [65, 66, 67, 68, 69]
b = bytes(data)  # O(5)
# b'ABCDE'

# With range
b = bytes(range(256))  # O(256)
```

### Allocating Size

```python
# O(n) - allocate and zero-fill
small = bytes(10)      # O(10)
medium = bytes(1000)   # O(1000)
large = bytes(1000000) # O(1000000)

# Must initialize all bytes to zero
```

## Common Patterns

### Encoding Strings

```python
# O(n) - convert text to bytes
text = "Hello, World!"
encoded = bytes(text, "utf-8")  # O(13)
# b'Hello, World!'
```

### Different Encodings

```python
# O(n) - same complexity, different results
text = "café"

utf8 = bytes(text, "utf-8")         # O(4) - 5 bytes result
utf16 = bytes(text, "utf-16")       # O(4) - 10 bytes result
latin1 = bytes(text, "latin-1")     # O(4) - 4 bytes result
ascii = bytes(text, "ascii")        # UnicodeEncodeError!
```

### Converting Between Bytes and Strings

```python
# O(n) - encode and decode
text = "hello"

# String -> Bytes
b = bytes(text, "utf-8")  # O(n)

# Bytes -> String
decoded = str(b, "utf-8")    # O(n)
# or
decoded = b.decode("utf-8")  # O(n) - same complexity

# Round trip
text2 = str(bytes(text, "utf-8"), "utf-8")
assert text == text2
```

## Performance Patterns

### Batch Encoding

```python
# O(n * m) - n strings, m = avg length
texts = ["hello", "world", "python"]
encoded = [bytes(t, "utf-8") for t in texts]  # O(n * m)

# Using map - same complexity
encoded = list(map(lambda x: bytes(x, "utf-8"), texts))
```

### File I/O

```python
# O(n) - read as bytes
with open("file.bin", "rb") as f:
    data = f.read()  # bytes

# O(n) - write bytes
with open("output.bin", "wb") as f:
    f.write(bytes("hello", "utf-8"))  # O(n)
```

### Network Transmission

```python
# O(n) - convert and send
import socket

message = "Hello, Server!"
data = bytes(message, "utf-8")  # O(n)

# socket.send(data)  # Sends bytes
```

## Practical Examples

### HTTP Request

```python
# O(n) - build request
def build_request(method, path, body):
    request = f"{method} {path} HTTP/1.1\r\n"
    request += f"Content-Length: {len(body)}\r\n\r\n"
    request += body
    
    return bytes(request, "utf-8")  # O(n)

req = build_request("GET", "/api", "")
```

### Cryptography

```python
# O(n) - encode for hashing
import hashlib

text = "password123"
hashed = hashlib.sha256(bytes(text, "utf-8")).hexdigest()  # O(n)
```

### Base64 Encoding

```python
# O(n) - convert to bytes then encode
import base64

text = "Hello, World!"
text_bytes = bytes(text, "utf-8")  # O(n)
encoded = base64.b64encode(text_bytes)  # O(n)
# b'SGVsbG8sIFdvcmxkIQ=='
```

### Binary Protocol

```python
# O(n) - create binary message
def create_packet(header, payload):
    header_bytes = bytes(header, "utf-8")  # O(h)
    payload_bytes = bytes(payload, "utf-8")  # O(p)
    
    # Combine (simplified)
    return header_bytes + payload_bytes  # O(h+p)

packet = create_packet("HEADER", "DATA")
```

## Edge Cases

### Empty String

```python
# O(1)
b = bytes("", "utf-8")  # b''
```

### Zero-size Allocation

```python
# O(1)
b = bytes(0)  # b'' - empty bytes
```

### Invalid Encoding

```python
# O(n) - error during conversion
try:
    b = bytes("café", "ascii")  # UnicodeEncodeError
except UnicodeEncodeError:
    pass
```

### Invalid Iterable Values

```python
# O(n) - error checking
try:
    b = bytes([0, 256, 128])  # ValueError - 256 > 255
except ValueError:
    pass

try:
    b = bytes([-1, 50, 100])  # ValueError - negative
except ValueError:
    pass
```

### Large Allocations

```python
# O(n) - allocate and zero-fill
huge = bytes(10**7)  # 10MB of zeros - slower
# Useful but memory intensive
```

## Comparison with bytearray()

```python
# bytes() - immutable
b = bytes("hello", "utf-8")
# b[0] = 65  # TypeError - can't modify

# bytearray() - mutable
ba = bytearray("hello", "utf-8")
ba[0] = 72  # OK - changed to 'H'

# Both O(n) to create, but different mutability
```

## String Methods

```python
# encode() method - equivalent to bytes()
text = "hello"
b1 = bytes(text, "utf-8")
b2 = text.encode("utf-8")
# b1 == b2 - same result

# decode() method - inverse
b = b"hello"
text = b.decode("utf-8")
# "hello"
```

## Best Practices

✅ **Do**:

- Specify encoding explicitly: `bytes(text, "utf-8")`
- Use UTF-8 as default encoding
- Handle encoding errors: `errors="strict"` (default) or other options
- Cache encoded values if used repeatedly

❌ **Avoid**:

- Assuming ASCII encoding (won't work with accents)
- Forgetting encoding parameter in bytes()
- Creating large bytes objects unnecessarily
- Confusing bytes with strings in Python 3

## Related Functions

- **[str()](str_func.md)** - Convert to string
- **[bytearray()](index.md)** - Mutable bytes
- **[encode()](str.md)** - String method to bytes
- **[decode()](bytes.md)** - Bytes method to string

## Version Notes

- **Python 2.x**: str is bytes, unicode is text
- **Python 3.x**: str is text, bytes is binary data
- **All versions**: UTF-8 is recommended encoding
