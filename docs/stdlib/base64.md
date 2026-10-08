# base64 Module Complexity

The `base64` module turns binary data into ASCII text and back: Base64 (standard and URL-safe),
Base32, Base16, Ascii85, Base85 and Z85. Every encoder and decoder is linear in its input and
returns a new `bytes` object, so each costs its input length in time and in memory. The legacy
`encode()` and `decode()` copy between files and hold one line.

How fast that pass runs depends on the encoding. Base64, Base16 and the legacy file functions
hand the work to `binascii`, which is C; Base32, Ascii85, Base85 and Z85 loop over each 5- or
4-byte group in Python, so they are many times slower per byte at the same O(n).

`n` is the input length: bytes for an encoder, encoded characters for a decoder. An encoder's
output is at most a fixed multiple of its input, plus padding - 4/3 for Base64, 8/5 for Base32, 2
for Base16 and 5/4 for the 85 family. `L` is the longest line in a file passed to `decode()`. The
legacy functions' space is working memory; it excludes what the output file keeps.

## Complexity Reference

### Base64

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `base64.b64encode(s, altchars=None)` | O(n) | O(n) | `altchars` replaces `+` and `/` with one extra translation pass |
| `base64.b64decode(s, altchars=None, validate=False)` | O(n) | O(n) | Discards characters outside the alphabet; `validate=True` raises `binascii.Error` instead |
| `base64.standard_b64encode(s)`, `base64.standard_b64decode(s)` | O(n) | O(n) | `b64encode()` and `b64decode()` with the standard alphabet |
| `base64.urlsafe_b64encode(s)`, `base64.urlsafe_b64decode(s)` | O(n) | O(n) | `-` and `_` instead of `+` and `/` |

### Base32 and Base16

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `base64.b32encode(s)` | O(n) | O(n) | A Python loop over 5-byte groups |
| `base64.b32decode(s, casefold=False, map01=None)` | O(n) | O(n) | A Python loop over 8-character groups |
| `base64.b32hexencode(s)`, `base64.b32hexdecode(s, casefold=False)` | O(n) | O(n) | Base32 with the extended hex alphabet |
| `base64.b16encode(s)` | O(n) | O(n) | Uppercase hexadecimal |
| `base64.b16decode(s, casefold=False)` | O(n) | O(n) | Rejects lowercase unless `casefold=True` |

### Ascii85, Base85 and Z85

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `base64.a85encode(b, *, foldspaces=False, wrapcol=0, pad=False, adobe=False)` | O(n) | O(n) | A Python loop over 4-byte groups |
| `base64.a85decode(b, *, foldspaces=False, adobe=False, ignorechars=b' \t\n\r\v')` | O(n) | O(n) | A Python loop over each character; skips `ignorechars` |
| `base64.b85encode(b, pad=False)`, `base64.b85decode(b)` | O(n) | O(n) | The same loops with the Base85 alphabet |
| `base64.z85encode(s)`, `base64.z85decode(s)` | O(n) | O(n) | Base85 plus one translation pass; Python 3.13+ |

### Legacy interface

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `base64.encode(input, output)` | O(n) | O(1) | Reads 57 bytes at a time and writes one 76-character line for each |
| `base64.decode(input, output)` | O(n) | O(L) | Decodes one line at a time |
| `base64.encodebytes(s)` | O(n) | O(n) | Base64 with a newline after every 76 characters |
| `base64.decodebytes(s)` | O(n) | O(n) | Accepts the lines `encodebytes()` writes |
| `base64.main()` | O(n) | O(1) to encode, O(L) to decode | `python -m base64 [-d] [file]`: `encode()` or `decode()` from a file or pipe to stdout |

## Encoding and Decoding

Encoders take a bytes-like object. The `b64`, `b32`, `b16`, `a85`, `b85` and `z85` decoders also
accept an ASCII `str`, which they encode first; `decodebytes()` does not.

```python
import base64

data = b"Hello, World!"
encoded = base64.b64encode(data)  # O(n)
assert encoded == b'SGVsbG8sIFdvcmxkIQ=='

assert base64.b64decode(encoded) == data  # O(n)
assert base64.b64decode('SGVsbG8sIFdvcmxkIQ==') == data  # an ASCII str works too

# Encoders refuse str: encode the text first
try:
    base64.b64encode("Hello")
except TypeError as error:
    assert 'bytes-like object' in str(error)
else:
    raise AssertionError('an encoder accepted str')

text = base64.b64encode("Hello".encode('utf-8')).decode('ascii')
assert text == 'SGVsbG8='
```

### Output Size

Each encoding expands its input by a fixed ratio, plus padding, so the choice of encoding sets
the size of what you store or send. Ascii85 can come out shorter: it writes an all-zero group as
`z`.

```python
import base64

original = b"x" * 100

assert len(base64.b64encode(original)) == 136  # 4/3, padded to a multiple of 4
assert len(base64.b32encode(original)) == 160  # 8/5
assert len(base64.b16encode(original)) == 200  # 2
assert len(base64.b85encode(original)) == 125  # 5/4
assert len(base64.a85encode(original)) == 125  # 5/4
assert base64.a85encode(b"\0" * 8) == b'zz'     # one character per zero group
```

### Choosing an Alphabet

```python
import base64

data = b"\xfb\xff"

assert base64.b64encode(data) == b'+/8='          # O(n)
assert base64.urlsafe_b64encode(data) == b'-_8='  # O(n) - safe in URLs and file names
assert base64.urlsafe_b64decode(b'-_8=') == data

assert base64.b32encode(b"Hello") == b'JBSWY3DP'     # O(n)
assert base64.b32hexencode(b"Hello") == b'91IMOR3F'  # O(n)
assert base64.b16encode(b"Hello") == b'48656C6C6F'   # O(n)
assert base64.b16decode(b'48656c6c6f', casefold=True) == b"Hello"
assert base64.b85encode(b"Hello") == b'NM&qnZv'      # O(n)
assert base64.a85encode(b"Hello") == b'87cURDZ'      # O(n)
```

## Decoding Untrusted Input

By default `b64decode()` drops every character outside the alphabet, so stray whitespace or
line breaks decode without complaint. `validate=True` rejects them instead. Either way, a
missing `=` raises `binascii.Error`; the decoder does not guess the padding.

```python
import base64
import binascii

assert base64.b64decode(b"SGVs bG8=") == b"Hello"  # the space is discarded

try:
    base64.b64decode(b"SGVs bG8=", validate=True)
except binascii.Error as error:
    assert 'base64' in str(error)
else:
    raise AssertionError('validate=True accepted a space')

try:
    base64.b64decode(b"SGVsbG8")
except binascii.Error as error:
    assert 'padding' in str(error)
else:
    raise AssertionError('missing padding was accepted')

# Restore the padding when a producer strips it
stripped = b"SGVsbG8"
assert base64.b64decode(stripped + b"=" * (-len(stripped) % 4)) == b"Hello"
```

## Streaming Files

`encode()` and `decode()` copy from one binary file to another a line at a time, so memory
follows the line rather than the file. `encode()` writes 76-character lines; `decode()` reads
whatever lines it is given, so a file that is one long line is held whole.

```python
import base64
import io

source = io.BytesIO(b"x" * 1000)
encoded = io.BytesIO()
base64.encode(source, encoded)  # O(n) time, O(1) working memory; `encoded` keeps the output
lines = encoded.getvalue().splitlines()
assert max(len(line) for line in lines) == 76

decoded = io.BytesIO()
base64.decode(io.BytesIO(encoded.getvalue()), decoded)  # O(n) time, O(L) working memory
assert decoded.getvalue() == b"x" * 1000

# encodebytes() is the in-memory form: the same 76-character lines
assert base64.encodebytes(b"x" * 1000) == encoded.getvalue()  # O(n)
assert base64.decodebytes(encoded.getvalue()) == b"x" * 1000  # O(n)
```

## Common Patterns

### Binary Data in JSON

```python
import base64
import json

payload = json.dumps({'content': base64.b64encode(b"\x00\x01\x02").decode('ascii')})  # O(n)

content = base64.b64decode(json.loads(payload)['content'])  # O(n)
assert content == b"\x00\x01\x02"
```

### Data URLs

```python
import base64

image = b"\x89PNG\r\n\x1a\n"
data_url = "data:image/png;base64," + base64.b64encode(image).decode('ascii')  # O(n)

header, _, body = data_url.partition(',')
assert header == 'data:image/png;base64'
assert base64.b64decode(body) == image  # O(n)
```

## Performance Best Practices

✅ **Do**:

- Use Base64 or Base16 for bulk data: they run in C, while the other encodings loop in Python
- Stream large files with `encode()` and `decode()` when 76-character lines are acceptable output
- Pass `validate=True` when stray characters in the input should be an error
- Use the URL-safe alphabet for data that goes into URLs or file names

❌ **Avoid**:

- Base32 or the 85 family for large payloads unless the format requires them
- Encoding a large file in fixed-size chunks with `b64encode()` and joining the pieces: a chunk
  whose length is not a multiple of 3 puts padding in the middle
- Treating Base64 as protection: anyone can decode it

## Version Notes

- **Python 3.13+**: Added `z85encode()` and `z85decode()`

## Related Modules

- **[binascii](binascii.md)** - The C conversions under Base64 and Base16
- **[codecs](codecs.md)** - `codecs.encode(data, 'base64')` uses `encodebytes()`
- **[json](json.md)** - Carrying encoded binary data in text
