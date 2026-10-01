# chunk Module Complexity

The `chunk` module reads EA IFF 85 chunks: a 4-byte ID, a 4-byte size and a body, the layout
used by AIFF and AIFF-C, and with little-endian sizes by RIFF files such as WAV. A `Chunk` wraps
one chunk of an open binary file. Building it reads the 8-byte header and nothing else; the body
is read only when you ask for it, and nothing is buffered between calls.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The examples need
    Python 3.10, 3.11 or 3.12.

`c` is the bytes in a chunk's body, `r` is the bytes of the body not yet read, `k` is the bytes
one `read()` returns, and `n` is the chunks in a file. A `seek()` or `tell()` on the underlying
file, and a `read()` of the few bytes of a header, are priced at O(1); reading k bytes from it is
O(k).

## Complexity Reference

### Chunk

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `chunk.Chunk(file, align=True, bigendian=True, inclheader=False)` | O(1) | O(1) | Reads the 8-byte header; raises `EOFError` if the file ends before it. A file without `tell()`, or whose `tell()` raises `OSError`, is treated as unseekable |
| `Chunk.getname()` | O(1) | O(1) | The 4-byte ID, as `bytes` |
| `Chunk.getsize()` | O(1) | O(1) | The body size from the header; 8 less with `inclheader=True` |
| `Chunk.read(size=-1)` | O(k) | O(k) | k ≤ r; with no size, asks the file for the rest of the body. Returns `b''` once the body is consumed |
| `Chunk.skip()` | O(1) seekable, O(r) unseekable | O(1) | Moves to the next chunk, past the pad byte of an odd-sized body when `align` is true. An unseekable file, or one whose `seek()` raises `OSError`, is read and discarded in blocks of at most 8,192 bytes |
| `Chunk.seek(pos, whence=0)` | O(1) | O(1) | Within the body; raises `OSError` on an unseekable file and `RuntimeError` outside 0 to c |
| `Chunk.tell()` | O(1) | O(1) | Kept by the chunk; the file is not asked |
| `Chunk.close()` | O(1) seekable, O(r) unseekable | O(1) | Calls `skip()`; the underlying file stays open. Afterwards `read()`, `skip()`, `seek()`, `tell()` and `isatty()` raise `ValueError` |
| `Chunk.isatty()` | O(1) | O(1) | Always `False` |

## Walking a File

On a seekable file, `skip()` is one `seek()`, so listing the chunks of a file costs O(n) whatever
their sizes: no body is read.

```python
import chunk
import io
import struct

def make_chunk(name, body):
    pad = b'\0' if len(body) % 2 else b''
    return name + struct.pack('>L', len(body)) + body + pad

data = (
    make_chunk(b'NAME', b'tone')
    + make_chunk(b'SSND', bytes(100_000))
    + make_chunk(b'ANNO', b'odd')  # odd-sized, so a pad byte follows
)
f = io.BytesIO(data)

found = []
while True:
    try:
        ck = chunk.Chunk(f)  # O(1) - reads the 8-byte header
    except EOFError:
        break
    found.append((ck.getname(), ck.getsize()))  # O(1)
    ck.skip()  # O(1) - one seek, the body is not read

assert found == [(b'NAME', 4), (b'SSND', 100_000), (b'ANNO', 3)]
```

### Unseekable Streams

`Chunk` decides whether the file is seekable once, by calling its `tell()`. Without one, `skip()`
and `close()` read the rest of the body to discard it, so walking a pipe costs every byte in
it, and `seek()` raises `OSError`.

```python
import chunk
import io
import struct

class Pipe:
    """A file with read() only, like a socket's makefile()."""
    def __init__(self, data):
        self._f = io.BytesIO(data)
        self.bytes_read = 0
    def read(self, size=-1):
        data = self._f.read(size)
        self.bytes_read += len(data)
        return data

body = bytes(100_000)
pipe = Pipe(b'SSND' + struct.pack('>L', len(body)) + body)

ck = chunk.Chunk(pipe)  # O(1)
try:
    ck.seek(0)
except OSError as error:
    assert 'cannot seek' in str(error)
else:
    raise AssertionError('an unseekable chunk accepted seek()')

ck.skip()  # O(r) - reads the whole body to discard it
assert pipe.bytes_read == 8 + len(body)
```

## Reading a Body

`read()` with no argument asks for the whole remaining body as one `bytes` object. Pass a size
to hold at most that many bytes at a time.

```python
import chunk
import io
import struct

body = bytes(range(256)) * 40
f = io.BytesIO(b'SSND' + struct.pack('>L', len(body)) + body)

ck = chunk.Chunk(f)
total = 0
while block := ck.read(4096):  # O(k) time and memory per call
    total += len(block)
assert total == len(body)
assert ck.read() == b''  # the body is consumed

ck.seek(256)  # O(1) - offsets are relative to the body
assert ck.tell() == 256
assert ck.read(4) == bytes([0, 1, 2, 3])
```

### Byte Order and Header Size

RIFF files store sizes little-endian, so read them with `bigendian=False`. A RIFF file is itself
one chunk whose body starts with a 4-byte form type and holds the other chunks; read the form
type, then walk the rest of the file with a new `Chunk` for each.

```python
import chunk
import io
import wave

buffer = io.BytesIO()
with wave.open(buffer, 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(8000)
    w.writeframes(bytes(2000))
buffer.seek(0)

riff = chunk.Chunk(buffer, bigendian=False)  # O(1)
assert riff.getname() == b'RIFF'
assert riff.read(4) == b'WAVE'

names = []
while True:
    try:
        sub = chunk.Chunk(buffer, bigendian=False)  # O(1)
    except EOFError:
        break
    names.append((sub.getname(), sub.getsize()))
    sub.skip()  # O(1)

assert names == [(b'fmt ', 16), (b'data', 2000)]
```

## Performance Best Practices

✅ **Do**:

- Call `skip()` on chunks you do not need: on a seekable file it is one seek, not a read
- Read large bodies with a size, so memory follows the block rather than the chunk
- Pass `bigendian=False` for RIFF files such as WAV

❌ **Avoid**:

- `read()` with no size on a large chunk - it holds the whole body at once
- Walking an unseekable stream to find one chunk near the end - every body before it is read

## Version Notes

- **Python 3.11+**: Importing the module emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import chunk` raises `ModuleNotFoundError`

## Related Modules

- **[wave](wave.md)** - reads and writes WAV files, whose RIFF chunks this module can walk
- **[aifc](aifc.md)** - reads and writes AIFF files built from IFF chunks, removed in 3.13 too
- **[struct](struct.md)** - unpacks a chunk header's ID and size directly
