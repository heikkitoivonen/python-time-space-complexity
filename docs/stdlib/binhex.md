# binhex Module Complexity

`binhex` converts files to and from the legacy BinHex 4.0 format.

## Complexity Reference

Here, n is the total input and output byte count. Bounds describe successful
file conversion with fixed-length paths; space is auxiliary memory, excluding
files on disk and caller-provided stream storage.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `binhex(input, output)` | O(n) | O(1) | Encodes in bounded chunks |
| `hexbin(input, output)` | O(n) | O(1) | Decodes in bounded chunks |
| `Error(message)` | O(1) | O(1) | Stores a reference to the supplied message |

!!! warning "Removed in Python 3.11"
    Deprecated in Python 3.9 and removed in Python 3.11. This page covers the
    exported API (`__all__`) available in Python 3.10; implementation helpers
    and the alternative coder/decoder classes are outside its scope.

## File Conversion

Run this example on Python 3.10. Invalid BinHex data can raise `Error`.

```python
import binhex
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as directory:
    source = Path(directory) / "input.bin"
    encoded = Path(directory) / "encoded.hqx"
    restored = Path(directory) / "restored.bin"
    source.write_bytes(b"hello\x00world")
    binhex.binhex(str(source), str(encoded))  # O(n)
    binhex.hexbin(str(encoded), str(restored))  # O(n)
    assert restored.read_bytes() == source.read_bytes()
```

## Related Documentation

- [binascii](binascii.md)
- [Python 3.10 binhex documentation](https://docs.python.org/3.10/library/binhex.html)
- [CPython 3.10 implementation](https://github.com/python/cpython/blob/3.10/Lib/binhex.py)
- [Python 3.11 removal notice](https://docs.python.org/3.11/whatsnew/3.11.html#removed)
