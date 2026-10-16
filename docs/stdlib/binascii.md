# binascii Module Complexity

The `binascii` module converts between binary data and ASCII encodings - hex, base64,
quoted-printable and uuencode, plus Base32, Ascii85 and Base85 from Python 3.15 - and computes
CRC-32 and CRC-CCITT checksums. It is C code, and
each function converts the whole buffer it is given in one call. The checksums take the previous
result as a starting value, so a stream can be checksummed a chunk at a time.

`n` is the length of the input: bytes for a bytes-like argument, characters for the ASCII-only
`str` that the `a2b_*` functions also accept. Every encoder and decoder is linear in n and produces
output at most a fixed multiple of n long; the checksums return an `int` in O(1) space. The
`ignorechars` argument the 3.15 decoders take is a short set of bytes and is priced at O(1), as is
a custom `alphabet`, which has a fixed length.

## Complexity Reference

### Hex

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binascii.hexlify(data[, sep[, bytes_per_sep=1]])` | O(n) | O(n) | Two hex digits per byte, plus one `sep` between each group of `bytes_per_sep` bytes when a separator is given |
| `binascii.b2a_hex(data[, sep[, bytes_per_sep=1]])` | O(n) | O(n) | Same as `hexlify()` |
| `binascii.unhexlify(hexstr, *, ignorechars=b'')` | O(n) | O(n) | One byte per two digits; an odd number of digits or a non-hex digit raises `binascii.Error`. Python 3.15+ skips the bytes listed in `ignorechars` |
| `binascii.a2b_hex(hexstr, *, ignorechars=b'')` | O(n) | O(n) | Same as `unhexlify()` |

### Base64

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binascii.b2a_base64(data, *, padded=True, wrapcol=0, newline=True, alphabet=BASE64_ALPHABET)` | O(n) | O(n) | Four characters per three bytes, as one line unless `wrapcol` breaks it into lines of at most `wrapcol` characters. `newline=False` drops the trailing `\n`. `padded`, `wrapcol` and `alphabet` are Python 3.15+ |
| `binascii.a2b_base64(string, /, *, padded=True, alphabet=BASE64_ALPHABET, strict_mode=False, ignorechars=b'', canonical=False)` | O(n) | O(n) | Characters outside the base64 alphabet are skipped; `strict_mode=True` (Python 3.11+) raises `binascii.Error` instead. Python 3.15+: passing `ignorechars` makes `strict_mode` default to on, and strict mode then skips those bytes; `canonical=True` rejects non-zero padding bits |

### Base32

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binascii.b2a_base32(data, /, *, padded=True, wrapcol=0, alphabet=BASE32_ALPHABET)` | O(n) | O(n) | Python 3.15+. Eight characters per five bytes, padded with `=` unless `padded=False`; `wrapcol` breaks the output into lines of at most `wrapcol` characters |
| `binascii.a2b_base32(data, /, *, padded=True, alphabet=BASE32_ALPHABET, ignorechars=b'', canonical=False)` | O(n) | O(n) | Python 3.15+. Any byte outside the alphabet that `ignorechars` does not list raises `binascii.Error`, lowercase letters included |

### Ascii85 and Base85

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binascii.b2a_ascii85(data, /, *, foldspaces=False, wrapcol=0, pad=False, adobe=False)` | O(n) | O(n) | Python 3.15+. Five characters per four bytes; an all-zero group is written as `z`, and four spaces as `y` with `foldspaces=True`. `adobe=True` adds the `<~` `~>` frame |
| `binascii.a2b_ascii85(data, /, *, foldspaces=False, adobe=False, ignorechars=b'', canonical=False)` | O(n) | O(n) | Python 3.15+. Each `z` (or `y` with `foldspaces=True`) becomes four bytes, so the output is at most 4n bytes. Whitespace raises `binascii.Error` unless `ignorechars` lists it |
| `binascii.b2a_base85(data, /, *, pad=False, wrapcol=0, alphabet=BASE85_ALPHABET)` | O(n) | O(n) | Python 3.15+. Five characters per four bytes; `alphabet=binascii.Z85_ALPHABET` gives Z85 |
| `binascii.a2b_base85(data, /, *, alphabet=BASE85_ALPHABET, ignorechars=b'', canonical=False)` | O(n) | O(n) | Python 3.15+. Any byte outside the alphabet that `ignorechars` does not list raises `binascii.Error` |

### Quoted-printable

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binascii.b2a_qp(data, quotetabs=False, istext=True, header=False)` | O(n) | O(n) | An escaped byte takes three characters, and soft line breaks keep every line to 76 characters or fewer |
| `binascii.a2b_qp(data, header=False)` | O(n) | O(n) | `header=True` also decodes `_` as a space |

### Uuencode

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binascii.b2a_uu(data, *, backtick=False)` | O(n) | O(n) | Encodes one line: n is at most 45, and longer data raises `binascii.Error` |
| `binascii.a2b_uu(string)` | O(n) | O(1) | Decodes one line; its leading length character fixes the output at 63 bytes or fewer, and anything after the encoded data must be padding or a line ending |

### Checksums

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binascii.crc32(data[, value])` | O(n) | O(1) | Unsigned 32-bit result; pass the previous result as `value` to continue a checksum over the next chunk |
| `binascii.crc_hqx(data, value)` | O(n) | O(1) | 16-bit CRC-CCITT; `value` is required and is the previous result, or 0 to start |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binascii.Error` | O(1) | O(1) | A `ValueError` subclass, raised for malformed or over-long input |
| `binascii.Incomplete` | O(1) | O(1) | Raised by no function; the removed `a2b_hqx()` and `rledecode_hqx()` raised it on truncated input |

## Hex Encoding

```python
import binascii

data = b'\x01\x02\x03\x04\x05'

encoded = binascii.hexlify(data)  # O(n)
assert encoded == b'0102030405'
assert binascii.hexlify(data, '-', 2) == b'01-0203-0405'  # groups counted from the right
assert binascii.hexlify(data, b':', -2) == b'0102:0304:05'  # negative counts from the left

assert binascii.unhexlify(encoded) == data  # O(n)
assert binascii.unhexlify('0A0b') == b'\n\x0b'  # an ASCII str works too

try:
    binascii.unhexlify(b'abc')  # the message names the odd length
except binascii.Error:
    pass
else:
    raise AssertionError('an odd-length string was decoded')
```

## Base64 Encoding

`b2a_base64()` returns the whole input as one line, so wrapping it for MIME is the caller's job
before Python 3.15, where `wrapcol` does it in the same pass.
`a2b_base64()` skips characters outside the alphabet unless `strict_mode` asks it to reject them.

```python
import binascii
import sys

encoded = binascii.b2a_base64(b'abc')  # O(n)
assert encoded == b'YWJj\n'
assert binascii.b2a_base64(b'abc', newline=False) == b'YWJj'
assert binascii.b2a_base64(b'x' * 300).count(b'\n') == 1  # one line, however long
if sys.version_info >= (3, 15):
    wrapped = binascii.b2a_base64(b'x' * 300, wrapcol=76)  # O(n): a newline per 76 characters
    assert max(len(line) for line in wrapped.splitlines()) == 76

assert binascii.a2b_base64(encoded) == b'abc'  # O(n)
assert binascii.a2b_base64(b'YW!J\nj') == b'abc'  # '!' and the newline are skipped

try:
    binascii.a2b_base64(b'YW!Jj', strict_mode=True)
except binascii.Error as error:
    assert 'Only base64 data' in str(error)
else:
    raise AssertionError('strict mode accepted a non-base64 character')
```

### Base32, Ascii85 and Base85

From Python 3.15 these are C functions here too, and the `base64` module's Base32, Ascii85,
Base85 and Z85 functions call them.

```python
import binascii
import sys

if sys.version_info >= (3, 15):
    assert binascii.b2a_base32(b'Hello') == b'JBSWY3DP'  # O(n)
    assert binascii.a2b_base32(b'JBSWY3DP') == b'Hello'  # O(n)
    assert binascii.b2a_base32(b'Hi', padded=False) == b'JBUQ'

    assert binascii.b2a_ascii85(b'\0' * 8) == b'zz'  # one character per zero group
    assert binascii.a2b_ascii85(b'zz') == b'\0' * 8   # O(n) - and four bytes per z
    assert binascii.b2a_base85(b'Hello') == b'NM&qnZv'  # O(n)

    # Whitespace is an error unless ignorechars lists it
    assert binascii.a2b_base32(b'JBSW Y3DP', ignorechars=b' ') == b'Hello'
    try:
        binascii.a2b_ascii85(b'87cU RDZ')
    except binascii.Error:
        pass
    else:
        raise AssertionError('a space was accepted')
```

## Quoted-printable Encoding

```python
import binascii

encoded = binascii.b2a_qp(b'caf\xe9 ' + b'a' * 100)  # O(n)
assert encoded.startswith(b'caf=E9 ')
assert max(len(line) for line in encoded.split(b'\n')) <= 76  # soft line breaks

assert binascii.a2b_qp(encoded) == b'caf\xe9 ' + b'a' * 100  # O(n)
assert binascii.a2b_qp(b'Hello_World', header=True) == b'Hello World'
```

## Uuencoding

`b2a_uu()` encodes a single line of at most 45 bytes, so encoding more is a loop over 45-byte
chunks, and decoding is one `a2b_uu()` call per line.

```python
import binascii

payload = bytes(range(100))

lines = [binascii.b2a_uu(payload[i:i + 45]) for i in range(0, len(payload), 45)]  # O(n) total
assert len(lines) == 3

assert b''.join(binascii.a2b_uu(line) for line in lines) == payload  # O(n) total

try:
    binascii.b2a_uu(payload)
except binascii.Error as error:
    assert '45 bytes' in str(error)
else:
    raise AssertionError('more than 45 bytes were encoded as one line')
```

## Checksums

Both CRC functions take a starting value, so a checksum computed chunk by chunk equals the one
computed over the whole input.

```python
import binascii

data = b'hello world' * 1000

whole = binascii.crc32(data)  # O(n) time, O(1) space

running = 0
for start in range(0, len(data), 4096):
    running = binascii.crc32(data[start:start + 4096], running)  # O(chunk) per call
assert running == whole

assert binascii.crc_hqx(b'hello', 0) == binascii.crc_hqx(b'lo', binascii.crc_hqx(b'hel', 0))
```

## Common Patterns

### Checksumming a File in Chunks

```python
import binascii
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'data.bin')
    with open(path, 'wb') as f:
        f.write(os.urandom(100_000))

    crc = 0
    with open(path, 'rb') as f:
        while chunk := f.read(16_384):  # memory is one chunk, not the file
            crc = binascii.crc32(chunk, crc)

    with open(path, 'rb') as f:
        assert crc == binascii.crc32(f.read())
```

## Performance Best Practices

✅ **Do**:

- Feed `crc32()` and `crc_hqx()` a chunk at a time with the previous result, so memory is one
  chunk rather than the file
- Split base64 input into chunks that are a multiple of three bytes when encoding a stream, so
  only the last chunk is padded
- Pass `strict_mode=True` to `a2b_base64()` (Python 3.11+) when malformed input should fail
  rather than be skipped

❌ **Avoid**:

- Encoding a stream with `b2a_base64()` in chunks that are not a multiple of three bytes - each
  chunk is padded on its own, and the joined output is not the encoding of the whole stream
- Passing more than 45 bytes to `b2a_uu()` - it raises rather than wrapping

## Version Notes

- **Python 3.11+**: `a2b_hqx()`, `b2a_hqx()`, `rlecode_hqx()` and `rledecode_hqx()` are removed,
  along with the `binhex` module; on 3.10 each raises a `DeprecationWarning`
- **Python 3.11+**: `a2b_base64()` gains `strict_mode`
- **Python 3.15+**: Added `b2a_base32()`, `a2b_base32()`, `b2a_ascii85()`, `a2b_ascii85()`,
  `b2a_base85()` and `a2b_base85()`
- **Python 3.15+**: `b2a_base64()` gains `padded`, `wrapcol` and `alphabet`; `a2b_base64()` gains
  `padded`, `alphabet`, `ignorechars` and `canonical`; `unhexlify()` and `a2b_hex()` gain
  `ignorechars`
- **Python 3.15+**: `unhexlify()` reports an odd number of digits as "Odd number of hexadecimal
  digits", counted after `ignorechars` are skipped; earlier versions say "Odd-length string"

## Related Modules

- **[base64](base64.md)** - Base64, Base32, Base16 and Base85 encoders with line handling and
  URL-safe alphabets; on Python 3.15+ all of them call this module
- **[quopri](quopri.md)** - quoted-printable encoding of files
- **[uu](uu.md)** - uuencoding whole files, a line at a time; removed in Python 3.13
- **[zlib](zlib.md)** - the same CRC-32 as `zlib.crc32()`, plus Adler-32
- **[binhex](binhex.md)** - the BinHex format the 3.10-only HQX functions served
- **[bytes](../builtins/bytes.md)** - `bytes.hex()` and `bytes.fromhex()`, the hex conversion as
  methods
