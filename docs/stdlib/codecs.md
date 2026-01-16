# codecs Module Complexity

The `codecs` module provides codec registry and base classes for codec implementations, including character encoding/decoding.

## Functions & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.encode(obj, encoding)` | O(n) | O(n) | Encode to bytes, n = input size |
| `codecs.decode(obj, encoding)` | O(n) | O(n) | Decode from bytes |
| `codecs.open(filename, mode, encoding)` | O(1) | O(1) | Open file with codec |
| `StreamWriter.write(obj)` | O(n) | O(n) | Encode and write |
| `StreamReader.read()` | O(n) | O(n) | Read and decode |
| `getencoder(encoding)` | O(1) | O(1) | Get encoder function |
| `getdecoder(encoding)` | O(1) | O(1) | Get decoder function |

## Encoding Operations

### Time Complexity: O(n)

Where n = input string size.

```python
import codecs

# Encode string to bytes: O(n)
text = "Hello, 世界" * 1000  # n = 5000 characters

# UTF-8 encoding: O(n)
encoded = codecs.encode(text, 'utf-8')  # O(n)

# ASCII encoding (subset): O(n)
text_ascii = "Hello World" * 1000
encoded = codecs.encode(text_ascii, 'ascii')  # O(n)

# Other encodings: O(n)
encoded = codecs.encode(text, 'utf-16')  # O(n)
encoded = codecs.encode(text, 'latin-1')  # O(n)
```

### Space Complexity: O(n)

```python
import codecs

# Output size depends on encoding
text = "Hello, 世界" * 1000

# UTF-8: variable size (1-4 bytes per char)
# Output: O(n), typically 1-2x input
encoded = codecs.encode(text, 'utf-8')  # O(n) space

# UTF-16: fixed 2 bytes per char (+ BOM)
# Output: O(2n)
encoded = codecs.encode(text, 'utf-16')  # O(n) space

# ASCII: 1 byte per char
# Output: O(n)
text_ascii = "Hello" * 1000
encoded = codecs.encode(text_ascii, 'ascii')  # O(n) space
```

## Decoding Operations

### Time Complexity: O(n)

Where n = input bytes size.

```python
import codecs

# Decode bytes to string: O(n)
encoded = b"Hello, \xe4\xb8\x96\xe7\x95\x8c" * 1000

# UTF-8 decoding: O(n)
text = codecs.decode(encoded, 'utf-8')  # O(n)

# ASCII decoding: O(n)
encoded_ascii = b"Hello World" * 1000
text = codecs.decode(encoded_ascii, 'ascii')  # O(n)

# UTF-16 decoding: O(n)
encoded_utf16 = b"\xff\xfeH\x00e\x00l\x00l\x00o\x00" * 1000
text = codecs.decode(encoded_utf16, 'utf-16')  # O(n)
```

### Space Complexity: O(n)

```python
import codecs

# Output string size
encoded = b"Hello, \xe4\xb8\x96\xe7\x95\x8c" * 1000

# UTF-8 decoded: variable size
# Output: O(n) for result string
text = codecs.decode(encoded, 'utf-8')  # O(n) space

# UTF-16 decoded: typically smaller
# Output: O(n) for result
text = codecs.decode(encoded, 'utf-16')  # O(n) space
```

## File I/O with Codecs

### Time Complexity: O(n)

Where n = file size.

```python
import codecs

# Open file with encoding: O(1) open + O(n) read/write
with codecs.open('file.txt', 'r', encoding='utf-8') as f:
    # Read and decode: O(n)
    text = f.read()  # O(n) to read and decode

    # Write and encode: O(n)
    # f.write(new_text)  # O(n)
```

### Space Complexity: O(n) or O(k)

```python
import codecs

# Full read: O(n) memory
with codecs.open('large.txt', 'r', encoding='utf-8') as f:
    text = f.read()  # O(n) memory

# Streaming read: O(k) memory
with codecs.open('large.txt', 'r', encoding='utf-8') as f:
    while True:
        chunk = f.read(4096)  # O(k) per chunk
        if not chunk:
            break
        process(chunk)
```

## StreamWriter and StreamReader

### StreamWriter - Encode and Write

```python
import codecs

# Create writer: O(1)
writer = codecs.getwriter('utf-8')(open('file.bin', 'wb'))

# Write and encode: O(n)
writer.write("Hello, 世界")  # O(n) to encode
writer.write("More text")  # O(m)

# Total: O(sum of all writes)
writer.close()
```

### StreamReader - Read and Decode

```python
import codecs

# Create reader: O(1)
reader = codecs.getreader('utf-8')(open('file.bin', 'rb'))

# Read and decode: O(n)
text = reader.read()  # O(n) to read and decode

# Or read in chunks
reader = codecs.getreader('utf-8')(open('file.bin', 'rb'))
while True:
    chunk = reader.read(4096)  # O(k) per chunk
    if not chunk:
        break
```

## Getting Codec Functions

### Time Complexity: O(1)

```python
import codecs

# Get encoder: O(1) lookup
encoder = codecs.getencoder('utf-8')  # O(1)
result = encoder("Hello")  # O(n) to use

# Get decoder: O(1) lookup
decoder = codecs.getdecoder('utf-8')  # O(1)
result = decoder(b"Hello")  # O(n) to use

# Get reader factory: O(1)
reader_factory = codecs.getreader('utf-8')  # O(1)

# Get writer factory: O(1)
writer_factory = codecs.getwriter('utf-8')  # O(1)
```

### Space Complexity: O(1)

```python
import codecs

# Just returns function reference
encoder = codecs.getencoder('utf-8')  # O(1) space
decoder = codecs.getdecoder('utf-8')  # O(1) space
```

## Common Encodings and Performance

### UTF-8 (Variable-length)

```python
import codecs

# Time: O(n) where n = character count
text = "Hello, 世界" * 1000
encoded = codecs.encode(text, 'utf-8')  # O(n)

# Space: 1-4 bytes per character
# ASCII chars: 1 byte
# Most European: 2 bytes
# CJK chars: 3-4 bytes
# Output typically 1-2x input size
```

### UTF-16 (Fixed 2 bytes)

```python
import codecs

# Time: O(n)
text = "Hello" * 1000
encoded = codecs.encode(text, 'utf-16')  # O(n)

# Space: Fixed 2 bytes per char + BOM (2 bytes)
# Output: 2n + 2 bytes
# Larger than UTF-8 for ASCII
```

### ASCII (1 byte per char)

```python
import codecs

# Time: O(n)
text = "Hello, World" * 1000
encoded = codecs.encode(text, 'ascii')  # O(n)

# Space: Exactly 1 byte per char
# Output: n bytes
# Fastest for ASCII-only text
```

### Latin-1 (1 byte per char)

```python
import codecs

# Time: O(n)
text = "Café" * 1000
encoded = codecs.encode(text, 'latin-1')  # O(n)

# Space: Exactly 1 byte per char
# Output: n bytes
# For Western European characters
```

## Error Handling

### Time Complexity: O(n)

```python
import codecs

# Strict mode: O(n), raises on error
text = "Hello, 世界"
try:
    encoded = codecs.encode(text, 'ascii', errors='strict')  # O(n)
except UnicodeEncodeError:
    pass

# Replace mode: O(n)
encoded = codecs.encode(text, 'ascii', errors='replace')  # O(n)
# Non-ASCII becomes '?'

# Ignore mode: O(n)
encoded = codecs.encode(text, 'ascii', errors='ignore')  # O(n)
# Non-ASCII is dropped

# Other modes: O(n)
encoded = codecs.encode(text, 'ascii', errors='xmlcharrefreplace')  # O(n)
# '世' → '&#19990;'
```

### Space Complexity: O(n)

```python
import codecs

text = "Hello, 世界"

# Output size depends on error handling
# strict/replace/ignore: O(n)
# xmlcharrefreplace: O(n) or larger
encoded = codecs.encode(text, 'ascii', errors='replace')  # O(n)
```

## Common Patterns

### Text File Processing

```python
import codecs

def process_text_file(filename, input_encoding, output_encoding):
    """Process text file with encoding conversion."""
    # Open and read: O(n)
    with codecs.open(filename, 'r', encoding=input_encoding) as f:
        text = f.read()  # O(n) to read and decode

    # Process: depends on operation
    processed = text.upper()  # O(n)

    # Write with different encoding: O(n)
    with codecs.open(filename + '.out', 'w', encoding=output_encoding) as f:
        f.write(processed)  # O(n) to encode and write

    # Total: O(n)
```

### Streaming with Codecs

```python
import codecs

def stream_process(input_file, output_file, from_encoding, to_encoding):
    """Stream process large file with encoding conversion."""
    reader = codecs.getreader(from_encoding)(open(input_file, 'rb'))
    writer = codecs.getwriter(to_encoding)(open(output_file, 'wb'))

    while True:
        chunk = reader.read(4096)  # O(k) per chunk
        if not chunk:
            break
        
        # Process
        processed = chunk.upper()  # O(k)
        writer.write(processed)  # O(k)

    reader.close()
    writer.close()
    # Total: O(n) time, O(k) memory
```

### Codec Lookup and Registration

```python
import codecs

# Get encoder: O(1)
encode_func, decode_func, reader_factory, writer_factory = codecs.lookup('utf-8')

# Use encoder: O(n)
encoded, length = encode_func("Hello, 世界")  # O(n)

# Use decoder: O(n)
decoded, length = decode_func(encoded)  # O(n)

# Use reader/writer factories: O(1)
reader = reader_factory(input_stream)
writer = writer_factory(output_stream)
```

## Performance Characteristics

### Best Practices

```python
import codecs

# Good: Specify encoding explicitly
with codecs.open('file.txt', 'r', encoding='utf-8') as f:
    text = f.read()  # Clear intent

# Avoid: Relying on system encoding
with codecs.open('file.txt', 'r') as f:
    text = f.read()  # May vary by system

# Good: Use appropriate encoding
# UTF-8 for web/general: O(n), 1-4 bytes/char
encoded = codecs.encode(text, 'utf-8')

# Good: Stream large files
reader = codecs.getreader('utf-8')(file_obj)
for chunk in iter(lambda: reader.read(65536), ''):
    process(chunk)  # O(k) memory

# Avoid: Load entire large file
text = reader.read()  # O(n) memory
```

### Encoding Selection

```python
import codecs

text = "Sample text 你好"

# UTF-8: Default, universal
# Time: O(n), Space: 1-4 bytes/char
encoded = codecs.encode(text, 'utf-8')

# ASCII: Fastest if text is ASCII-only
# Time: O(n), Space: 1 byte/char
text_ascii = "Hello World"
encoded = codecs.encode(text_ascii, 'ascii')

# Latin-1: For Western European
# Time: O(n), Space: 1 byte/char
text_european = "Café"
encoded = codecs.encode(text_european, 'latin-1')

# UTF-16: For Windows APIs
# Time: O(n), Space: 2 bytes/char
encoded = codecs.encode(text, 'utf-16')
```

## Version Notes

- **Python 2.0+**: Basic codecs module
- **Python 3.0+**: Enhanced Unicode support
- **Python 3.3+**: Better error handling
- **Python 3.7+**: Performance improvements

## Related Documentation

- [base64 Module](base64.md) - Base64 encoding
- [io Module](io.md) - I/O operations with encoding
- [sys Module](sys.md) - Default encoding/decoding
- [unicodedata Module](unicodedata.md) - Unicode information
