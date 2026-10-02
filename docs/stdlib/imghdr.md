# imghdr Module Complexity

The `imghdr` module guesses an image's format from its first bytes. `what()` reads up to 32 bytes
from a path, or from an open binary file at its current position, or takes the bytes you pass as
`h` as they are, and hands them to each check in `imghdr.tests` in turn until one names a
format. The built-in checks read nothing more of the image, and the file name plays no part.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The examples need
    Python 3.10, 3.11 or 3.12.

`t` is the checks in `imghdr.tests`, 13 built in. Each built-in check compares a fixed-length
prefix of the header, so it is O(1) however long a header you pass; a check you append costs
whatever it does. Opening a file and one `read()`, `tell()` or `seek()` on it are priced at O(1).

## Complexity Reference

### Functions and data

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `imghdr.what(file, h=None)` | O(t) | O(1) | Returns the first format a check names, or `None`. A path is opened, read for 32 bytes and closed; an open file is read for 32 bytes and sought back to where it was, so it must support `tell()` and `seek()`. With `h` given, `file` is ignored and nothing is read |
| `imghdr.tests` | O(1) | O(1) | The list of checks, tried in order; append a function `check(h, f)` that returns a format name or `None`. `f` is the open file only when `what()` was given a path, and `None` otherwise |

## Detecting Image Types

### From a File, a Stream, or Bytes

Every form reads the same 32 bytes at most. A path is opened and closed by `what()`; an open file
is left where it was, so a caller can sniff and then read the image from the start.

```python
import io
import os
import tempfile
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)  # 3.11 and 3.12 warn on import
    import imghdr

png = b'\x89PNG\r\n\x1a\n' + bytes(1000)
gif = b'GIF89a' + bytes(1000)

# From bytes you already hold: nothing is read, `file` is ignored
assert imghdr.what(None, h=png) == 'png'  # O(t)

# From an open file: 32 bytes are read, then the position is restored
stream = io.BytesIO(gif)
assert imghdr.what(stream) == 'gif'  # O(t)
assert stream.tell() == 0

# From a path: opened, 32 bytes read, closed
with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'photo.jpg')  # the extension is not consulted
    with open(path, 'wb') as f:
        f.write(png)
    assert imghdr.what(path) == 'png'  # O(t)

# Unrecognised data is None, not an error
assert imghdr.what(None, h=b'not an image') is None
```

### Order and Weak Signatures

The checks run in list order and the first match wins. Some signatures are only two bytes
(`'tiff'` for `II` or `MM`, `'bmp'` for `BM`), so text that happens to start with them is
reported as an image. JPEG is recognised by `JFIF` or `Exif` at bytes 6 to 9, or from Python
3.11 by a file starting `FF D8 FF DB`; a JPEG with neither returns `None`.

```python
import sys
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import imghdr

assert imghdr.what(None, h=b'MMORPG notes') == 'tiff'  # two bytes decide it
assert imghdr.what(None, h=b'BMW service log') == 'bmp'

jfif = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00'
icc = b'\xff\xd8\xff\xe2\x0c\x58ICC_PROFILE'
raw = b'\xff\xd8\xff\xdb\x00\x43\x00'

assert imghdr.what(None, h=jfif) == 'jpeg'
assert imghdr.what(None, h=icc) is None  # a JPEG, but not one imghdr knows
assert imghdr.what(None, h=raw) == ('jpeg' if sys.version_info >= (3, 11) else None)
```

## Adding a Format

Appending to `imghdr.tests` adds one more check to every later miss. A check sees the header
bytes; it gets the open file as well only when `what()` was given a path.

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import imghdr

def test_ico(h, f):
    if h[:4] == b'\x00\x00\x01\x00':
        return 'ico'

imghdr.tests.append(test_ico)
try:
    assert imghdr.what(None, h=b'\x00\x00\x01\x00\x01\x00') == 'ico'  # O(t), now one longer
    assert imghdr.what(None, h=b'\x89PNG\r\n\x1a\n') == 'png'  # an earlier check still wins
finally:
    imghdr.tests.remove(test_ico)
```

## Performance Best Practices

✅ **Do**:

- Pass `h=` when the bytes are already in memory; it skips the open and the read
- Treat the answer as a hint: two-byte signatures misfire on text, and a JPEG without a JFIF or
  Exif marker can return `None`

❌ **Avoid**:

- Reading a whole file to pass as `h`; `what()` itself never reads more than 32 bytes
- Passing an unseekable stream such as a pipe: `what()` calls `tell()` and `seek()` on it

## Version Notes

- **Python 3.11+**: Importing the module emits a `DeprecationWarning`
- **Python 3.11+**: A JPEG starting `FF D8 FF DB` is recognised without a JFIF or Exif marker
- **Python 3.13+**: Removed by PEP 594; `import imghdr` raises `ModuleNotFoundError`

## Related Modules

- **[mimetypes](mimetypes.md)** - guesses a type from the file name, without reading the file
- **[sndhdr](sndhdr.md)** - the same header-sniffing design for sound files, removed in 3.13 too
