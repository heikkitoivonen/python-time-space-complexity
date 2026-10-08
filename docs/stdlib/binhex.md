# binhex Module Complexity

The `binhex` module converts files to and from the legacy BinHex 4.0 format: run-length
compression of repeated bytes, then a 6-bit text encoding. Both functions stream the file in
fixed-size chunks, so neither holds a whole file in memory.

!!! warning "Removed in Python 3.11"
    Deprecated in Python 3.9 and removed in Python 3.11. The examples need Python 3.10.

`n` is the bytes read plus the bytes written. Run-length compression makes an encoded file of
repeated bytes far smaller than what it decodes to, so the two sides are counted together rather
than either one alone. File-name handling is priced at O(1). Space is auxiliary memory: it
excludes the files themselves and the buffer of a file object you pass in. The bounds are for
well-formed input.

## Complexity Reference

### Functions and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binhex.binhex(input, output)` | O(n) | O(1) | `input` is a file name; `output` is a file name or a binary file object, which is closed when done |
| `binhex.hexbin(input, output)` | O(n) | O(1) | `input` is a file name or a binary file object, which is closed when done; with `output=None` it writes to the name stored in the file. A truncated file can make it loop forever instead of raising `Error` |
| `binhex.Error` | O(1) | O(1) | Raised for input with no BinHex data, a CRC mismatch, some truncated input, or an input file name over 63 characters, not counting its directory; a character outside the BinHex alphabet raises `binascii.Error` instead |

## Converting Files

Encoding and decoding each make one pass over the file, a chunk at a time. Memory stays bounded
however large the file is.

```python
import binhex
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as directory:
    source = Path(directory) / "input.bin"
    encoded = Path(directory) / "encoded.hqx"
    restored = Path(directory) / "restored.bin"
    source.write_bytes(b"hello\x00world" * 1000)

    binhex.binhex(str(source), str(encoded))  # O(n)
    assert encoded.read_bytes().startswith(b"(This file must be converted with BinHex 4.0)")

    binhex.hexbin(str(encoded), str(restored))  # O(n)
    assert restored.read_bytes() == source.read_bytes()
```

### Malformed Input

A corrupted file raises `binhex.Error` on a CRC mismatch, except for a character outside the
BinHex alphabet, which `binascii` rejects first. A truncated file may not fail at all: depending
on where it ends, `hexbin()` either raises `binhex.Error` or keeps reading past the end of the
file forever.

```python
import binascii
import binhex
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as directory:
    bad = Path(directory) / "bad.hqx"
    output = str(Path(directory) / "output.bin")

    bad.write_bytes(b"no encoded data")
    try:
        binhex.hexbin(str(bad), output)
    except binhex.Error as error:
        assert "No binhex data found" in str(error)
    else:
        raise AssertionError("text with no BinHex data was decoded")

    bad.write_bytes(b":~")
    try:
        binhex.hexbin(str(bad), output)
    except binascii.Error as error:
        assert "Illegal char" in str(error)
    else:
        raise AssertionError("a character outside the alphabet was decoded")
```

## Performance Best Practices

✅ **Do**:

- Pass file names: both functions then stream the file, and memory stays bounded
- Catch `binascii.Error` as well as `binhex.Error` when decoding files you did not write

❌ **Avoid**:

- Wrapping data in `io.BytesIO` to pass it in or out - the stream holds the whole file, O(n)
- Decoding a file that may be truncated without a time limit - `hexbin()` can loop forever on it

## Version Notes

- **Python 3.9+**: Importing the module emits a `DeprecationWarning`
- **Python 3.11+**: Removed; `import binhex` raises `ModuleNotFoundError`, and `binascii` drops
  the BinHex helpers it was built on except `crc_hqx()`

## Related Modules

- **[binascii](binascii.md)** - the encoding, run-length and CRC helpers this module calls
- **[base64](base64.md)** - text encodings of binary data that remain in the standard library
