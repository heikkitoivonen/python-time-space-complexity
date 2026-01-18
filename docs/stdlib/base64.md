# base64 Module Complexity

The `base64` module provides encoding and decoding for base64, base32, base16, and other alphabet-based binary encodings, used for transmitting binary data over text channels.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `base64.b64encode(data)` | O(n) | O(n) | n = data size |
| `base64.b64decode(data)` | O(n) | O(n) | n = encoded size |
| `base64.b32encode(data)` | O(n) | O(n) | n = data size |
| `base64.b32decode(data)` | O(n) | O(n) | n = encoded size |
| `base64.b16encode(data)` | O(n) | O(n) | n = data size |
| `base64.b16decode(data)` | O(n) | O(n) | n = encoded size |

## Base64 Encoding/Decoding

### Basic Encoding

```python
import base64

# Encode bytes to base64 - O(n)
data = b"Hello, World!"
encoded = base64.b64encode(data)  # O(len(data))
# Result: b'SGVsbG8sIFdvcmxkIQ=='

# Decode base64 to bytes - O(n)
decoded = base64.b64decode(encoded)  # O(len(encoded))
# Result: b'Hello, World!'

assert decoded == data
```

### String Encoding

```python
import base64

# Encode string (requires encoding first) - O(n)
text = "Hello, World!"
encoded = base64.b64encode(text.encode('utf-8'))  # O(len(text))
# Result: b'SGVsbG8sIFdvcmxkIQ=='

# Decode and convert back - O(n)
decoded = base64.b64decode(encoded).decode('utf-8')  # O(len(encoded))
# Result: 'Hello, World!'
```

## Different Base64 Variants

### Standard Base64

```python
import base64

data = b"Hello"

# Standard (with + and /) - O(n)
encoded = base64.b64encode(data)  # O(5)
# May contain: + / =

# With newlines every 76 chars - O(n)
encoded_multiline = base64.b64encode(data)
# Standard base64 (no newlines added by default)
```

### URL-Safe Base64

```python
import base64

data = b"Hello?"

# URL-safe (- and _ instead of + /) - O(n)
encoded = base64.urlsafe_b64encode(data)  # O(6)
# Uses - and _ instead of + /

# Decode URL-safe - O(n)
decoded = base64.urlsafe_b64decode(encoded)  # O(len(encoded))
```

## Base32 and Base16

### Base32 Encoding

```python
import base64

data = b"Hello"

# Base32 (5 bits per char) - O(n)
encoded = base64.b32encode(data)  # O(5)
# Result: b'JBSWY3DPEBLW64TMMQ======'

# Decode Base32 - O(n)
decoded = base64.b32decode(encoded)  # O(len(encoded))
# Result: b'Hello'
```

### Base16 (Hex) Encoding

```python
import base64

data = b"Hello"

# Base16 (hex) - O(n)
encoded = base64.b16encode(data)  # O(5)
# Result: b'48656C6C6F'

# Decode Base16 - O(n)
decoded = base64.b16decode(encoded)  # O(len(encoded))
# Result: b'Hello'
```

## Common Patterns

### Encoding Binary Data

```python
import base64

# Binary data (e.g., image file) - O(n)
with open('image.png', 'rb') as f:
    image_data = f.read()  # O(n)

# Encode for transmission - O(n)
encoded = base64.b64encode(image_data)  # O(n)

# Send as text (email, JSON, etc.)
import json
payload = json.dumps({'image': encoded.decode('ascii')})

# Decode on other end - O(n)
decoded_image = base64.b64decode(encoded)  # O(n)
```

### Data URLs

```python
import base64

# Create data URL - O(n)
with open('logo.png', 'rb') as f:
    image_data = f.read()  # O(n)

encoded = base64.b64encode(image_data)  # O(n)
data_url = f"data:image/png;base64,{encoded.decode('ascii')}"

# Use in HTML
html = f'<img src="{data_url}">'

# Decode from data URL - O(n)
base64_part = data_url.split(',')[1]
decoded = base64.b64decode(base64_part)  # O(n)
```

### JSON Serialization

```python
import base64
import json

# Binary data to JSON - O(n)
binary_data = b"Some binary content"
encoded = base64.b64encode(binary_data)  # O(n)

# In JSON - O(n)
data = {
    'content': encoded.decode('ascii'),
    'type': 'binary'
}
json_str = json.dumps(data)  # O(n)

# From JSON - O(n)
loaded = json.loads(json_str)
decoded = base64.b64decode(loaded['content'])  # O(n)
```

## Streaming/Large Data

### Processing Large Files

```python
import base64

def encode_large_file(input_path, output_path):
    """Encode file in chunks - O(n)"""
    with open(input_path, 'rb') as infile:
        with open(output_path, 'wb') as outfile:
            # Process in chunks - O(n) total
            while True:
                chunk = infile.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                
                # Encode chunk - O(chunk_size)
                encoded = base64.b64encode(chunk)  # O(1MB)
                outfile.write(encoded)
                outfile.write(b'\n')  # Newline for readability

# Usage - O(n) where n = file size
encode_large_file('large.bin', 'large.b64')
```

### Memory-Efficient Decoding

```python
import base64

def decode_large_file(input_path, output_path):
    """Decode file in chunks - O(n)"""
    with open(input_path, 'rb') as infile:
        with open(output_path, 'wb') as outfile:
            # Process in chunks - O(n) total
            for line in infile:
                # Decode chunk - O(line_size)
                decoded = base64.b64decode(line)  # O(line_size)
                outfile.write(decoded)

# Usage - O(n)
decode_large_file('large.b64', 'large.bin')
```

## Performance Considerations

### Encoding Size

```python
import base64

# Base64 expands size by ~33%
original = b"x" * 100
encoded = base64.b64encode(original)

print(len(original))  # 100
print(len(encoded))   # ~137 (padded to multiple of 4)
print(len(encoded) / len(original))  # ~1.37

# Base32 expands size by ~60%
encoded32 = base64.b32encode(original)
print(len(encoded32))  # ~165

# Base16 (hex) doubles size
encoded16 = base64.b16encode(original)
print(len(encoded16))  # ~200
```

### Encoding vs Decoding Speed

```python
import base64
import time

data = b"x" * (1024 * 1024)  # 1MB

# Encoding
start = time.time()
encoded = base64.b64encode(data)  # O(n)
encode_time = time.time() - start

# Decoding
start = time.time()
decoded = base64.b64decode(encoded)  # O(n)
decode_time = time.time() - start

print(f"Encode: {encode_time:.4f}s")
print(f"Decode: {decode_time:.4f}s")
# Usually similar, both O(n)
```

## Use Cases

### Token/Session Encoding

```python
import base64
import json

# Create token - O(n)
token_data = {
    'user_id': 123,
    'expires': 1640995200,
    'scopes': ['read', 'write']
}

json_str = json.dumps(token_data)  # O(n)
token = base64.urlsafe_b64encode(json_str.encode())  # O(n)

# Send token
send_header(f"Authorization: Bearer {token.decode()}")

# Receive and decode - O(n)
decoded_json = base64.urlsafe_b64decode(token).decode()
decoded_data = json.loads(decoded_json)  # O(n)
```

### File Attachments

```python
import base64

# Email attachment - O(n)
with open('document.pdf', 'rb') as f:
    pdf_data = f.read()  # O(n)

# Encode for email - O(n)
encoded = base64.b64encode(pdf_data)  # O(n)

# Add to email
email_body = f"""
Content-Disposition: attachment; filename="document.pdf"
Content-Transfer-Encoding: base64

{encoded.decode('ascii')}
"""

# On receive side - O(n)
attachment_data = base64.b64decode(encoded)
```

## Avoiding Common Issues

```python
import base64

# Issue 1: Whitespace in encoded data
bad_encoded = b"SGVs bG8="  # Has space
try:
    decoded = base64.b64decode(bad_encoded)  # Might fail
except:
    # Solution: strip whitespace
    decoded = base64.b64decode(bad_encoded.replace(b' ', b''))

# Issue 2: Missing padding
bad_encoded = b"SGVsbG8"  # Missing =
try:
    decoded = base64.b64decode(bad_encoded)  # Might work or fail
except:
    # Solution: add padding
    padding = 4 - (len(bad_encoded) % 4)
    if padding != 4:
        bad_encoded += b'=' * padding
    decoded = base64.b64decode(bad_encoded)

# Issue 3: Unicode vs bytes
text = "SGVsbG8="
decoded = base64.b64decode(text.encode())  # Convert to bytes first
```

## Comparison: When to Use

```python
import base64
import binascii

data = b"Hello"

# Base64 - compact, readable, safe for text - O(n)
b64 = base64.b64encode(data)  # Most common

# Base32 - even safer, less compact - O(n)
b32 = base64.b32encode(data)

# Base16 (hex) - safest but large - O(n)
b16 = base64.b16encode(data)

# Hex string (similar to base16) - O(n)
hex_str = binascii.hexlify(data)

# Use base64 most of the time
```

## Version Notes

- **Python 2.x**: base64 module available
- **Python 3.x**: Consistent encoding/decoding
- **All versions**: O(n) complexity for n bytes

## Related Modules

- **[binascii](binascii.md)** - Hex and other encodings
- **[urllib.parse](urllib.md)** - URL quoting (similar purpose)
- **[hashlib](hashlib.md)** - Binary data hashing

## Best Practices

✅ **Do**:

- Use base64 for binary data in text protocols
- Use urlsafe variant for URLs/file names
- Process large files in chunks
- Remove whitespace when decoding untrusted input
- Document encoding used in serialized data

❌ **Avoid**:

- Using base64 for encryption (it's just encoding, not secure)
- Assuming base64 is one-way (it's trivially reversible)
- Forgetting to handle padding in edge cases
- Mixing encoding/decoding (encode with b64encode, decode with b64decode)
- Using base64 when JSON serialization is appropriate
