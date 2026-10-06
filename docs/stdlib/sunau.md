# sunau Module Complexity

The `sunau` module reads and writes Sun AU audio files: a short header followed by the samples.
It is pure Python and works a call at a time: opening a file reads only the header,
`readframes()` returns a block of frames, and `writeframes()` passes your bytes to the file,
encoding them first for u-law. Nothing in the module holds the audio unless you read it all at
once.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 (PEP 594). The page covers the module
    as it is on Python 3.10 to 3.12, and its examples run only there; from 3.11, `import sunau`
    emits a `DeprecationWarning`.

Frames are the unit throughout. `k` is the frames read or written in one call and `w` is the
bytes in one frame as your code sees it, `nchannels × sampwidth` (for A-law, `nchannels`), so one
call moves `k·w` bytes.
Uncompressed samples are stored big-endian and are returned and written as stored, on every host;
u-law samples are converted from and to native byte order. The official documentation calls the
two classes `AU_read` and `AU_write`; the module names them `Au_read` and `Au_write`.

## Complexity Reference

### open and Error

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sunau.open(f, mode=None)` | O(1) | O(1) | `'r'` or `'rb'` returns an `Au_read`, `'w'` or `'wb'` an `Au_write`; without a mode, `f.mode` decides, else `'rb'` |
| `sunau.Error` | O(1) | O(1) | Raised for a file that is not AU or has an unsupported encoding, and for a parameter that is invalid, missing or set too late. A file that ends inside the header's fixed fields raises `EOFError` instead |

### Au_read

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sunau.Au_read(f)`, `sunau.open(f, 'rb')` | O(1) | O(1) | Reads the header and nothing else. Needs only `read()`: on a stream that cannot report its position, frames still read in order, but `setpos()` and `rewind()` raise `OSError` |
| `Au_read.readframes(nframes)` | O(k·w) | O(k·w), O(nframes·w) from a file on disk | k = frames returned, which is fewer than `nframes` at the end of the data; a file on disk sizes its read buffer for the request, so asking far past the end costs that much memory. u-law is decoded into a new buffer of 16-bit samples; A-law is returned undecoded, one byte per sample, though `getsampwidth()` reports 2 |
| `Au_read.setpos(pos)`, `Au_read.rewind()` | O(1) | O(1) | Seek at once, reading nothing; `setpos()` raises `sunau.Error` for a position past the end |
| `Au_read.tell()` | O(1) | O(1) | Frames read so far, or the position set |
| `Au_read.getnchannels()`, `Au_read.getsampwidth()`, `Au_read.getframerate()`, `Au_read.getnframes()` | O(1) | O(1) | Read from the header when the file was opened. `getnframes()` returns `sunau.AUDIO_UNKNOWN_SIZE` when the header leaves the length unknown, and `readframes()` of that reads to the end |
| `Au_read.getcomptype()`, `Au_read.getcompname()` | O(1) | O(1) | `'NONE'`, `'ULAW'` or `'ALAW'`, and `'not compressed'`, `'CCITT G.711 u-law'` or `'CCITT G.711 A-law'` |
| `Au_read.getparams()` | O(1) | O(1) | A named tuple of the six values above |
| `Au_read.getmarkers()`, `Au_read.getmark(id)` | O(1) | O(1) | AU files have no markers: `getmarkers()` returns `None` and `getmark()` raises `sunau.Error` |
| `Au_read.close()` | O(1) | O(1) | Closes the file only if it was opened from a file name |

### Au_write

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sunau.Au_write(f)`, `sunau.open(f, 'wb')` | O(1) | O(1) | Writes nothing; the header goes out with the first frames or at `close()`. The compression type starts as `'ULAW'`, not `'NONE'` |
| `Au_write.setnchannels(n)`, `Au_write.setsampwidth(n)`, `Au_write.setframerate(n)`, `Au_write.setnframes(n)` | O(1) | O(1) | Raise `sunau.Error` once frames have been written; `setnchannels()` accepts 1, 2 or 4, `setsampwidth()` 1 to 4, and `setnframes()` no negative count |
| `Au_write.setcomptype(type, name)` | O(1) | O(1) | `'NONE'` or `'ULAW'`; any other type raises `sunau.Error`, and `name` is ignored. Not refused once frames have been written, though the header already names the first type |
| `Au_write.setparams(params)` | O(1) | O(1) | The five setters in one call |
| `Au_write.writeframes(data)` | O(k·w) | O(1), O(k·w) u-law | Uncompressed bytes are written as given, not copied; u-law is encoded into a new buffer. After every call the header's count is patched in place, unless the frames written so far match both the count declared with `setnframes()` and the count the header holds |
| `Au_write.writeframesraw(data)` | O(k·w) | O(1), O(k·w) u-law | The same without the patch, which is left to `close()` |
| `Au_write.tell()`, `Au_write.getnframes()` | O(1) | O(1) | Frames written so far |
| `Au_write.getnchannels()`, `Au_write.getsampwidth()`, `Au_write.getframerate()` | O(1) | O(1) | `getnchannels()` and `getframerate()` raise `sunau.Error` until set, and `getsampwidth()` until the frame rate is |
| `Au_write.getcomptype()`, `Au_write.getcompname()` | O(1) | O(1) | `'ULAW'` and `'CCITT G.711 u-law'` until `setcomptype()` |
| `Au_write.getparams()` | O(1) | O(1) | Raises `sunau.Error` until channels and frame rate are set |
| `Au_write.close()` | O(1) | O(1) | Writes the header if no frames were, patches it on the same condition as `writeframes()`, then flushes; closes the file only if it was opened from a file name |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sunau.AUDIO_FILE_MAGIC` | O(1) | O(1) | `.snd` read as a big-endian integer; every AU file starts with it |
| `sunau.AUDIO_FILE_ENCODING_MULAW_8`, `sunau.AUDIO_FILE_ENCODING_LINEAR_8`, `sunau.AUDIO_FILE_ENCODING_LINEAR_16`, `sunau.AUDIO_FILE_ENCODING_LINEAR_24`, `sunau.AUDIO_FILE_ENCODING_LINEAR_32`, `sunau.AUDIO_FILE_ENCODING_ALAW_8` | O(1) | O(1) | Header encodings the module reads; it writes all but A-law |
| `sunau.AUDIO_FILE_ENCODING_FLOAT`, `sunau.AUDIO_FILE_ENCODING_DOUBLE`, `sunau.AUDIO_FILE_ENCODING_ADPCM_G721`, `sunau.AUDIO_FILE_ENCODING_ADPCM_G722`, `sunau.AUDIO_FILE_ENCODING_ADPCM_G723_3`, `sunau.AUDIO_FILE_ENCODING_ADPCM_G723_5` | O(1) | O(1) | Known encodings the module does not support; opening such a file raises `sunau.Error` |
| `sunau.AUDIO_UNKNOWN_SIZE` | O(1) | O(1) | `0xFFFFFFFF`: the header's length when it is unknown, and what `getnframes()` then returns |

## Reading AU Files

### Opening Reads Only the Header

The header is a fixed set of fields plus a short description, so opening a file costs the same
however long the audio is. The frame count comes from the header's data size.

```python
import io
import sunau

buffer = io.BytesIO()
with sunau.open(buffer, 'wb') as out:
    out.setparams((2, 2, 44100, 0, 'NONE', ''))
    out.writeframes(bytes(4 * 44100))  # one second of stereo silence

buffer.seek(0)
with sunau.open(buffer, 'rb') as audio:  # O(1) - the samples are not read
    assert audio.getnframes() == 44100  # O(1)
    assert audio.getparams() == (2, 2, 44100, 44100, 'NONE', 'not compressed')
    assert audio.getmarkers() is None
```

### Reading in Blocks

`readframes()` returns what you ask for as one `bytes` object, so memory follows the request, not
the file. Reading a fixed block at a time holds one block; `readframes(getnframes())` holds the
whole file.

```python
import io
import sunau

buffer = io.BytesIO()
with sunau.open(buffer, 'wb') as out:
    out.setparams((1, 2, 8000, 0, 'NONE', ''))
    out.writeframes(bytes(2 * 10_000))

buffer.seek(0)
with sunau.open(buffer, 'rb') as audio:
    frames = 0
    while block := audio.readframes(4096):  # O(k·w) per block
        assert len(block) <= 4096 * 2
        frames += len(block) // 2
    assert frames == 10_000
    assert audio.readframes(4096) == b''  # at the end
```

### Seeking

`setpos()` and `rewind()` seek the file at once, so the frames skipped are never read. They need
a stream that can report its position; on one that cannot, both raise `OSError`.

```python
import io
import sunau

buffer = io.BytesIO()
with sunau.open(buffer, 'wb') as out:
    out.setparams((1, 1, 8000, 0, 'NONE', ''))
    out.writeframes(bytes(range(256)) * 4)

buffer.seek(0)
with sunau.open(buffer, 'rb') as audio:
    audio.setpos(1000)  # O(1)
    assert audio.tell() == 1000
    assert audio.readframes(10) == bytes(range(232, 242))  # O(k·w)
    audio.rewind()  # O(1)
    assert audio.readframes(3) == bytes([0, 1, 2])

    try:
        audio.setpos(audio.getnframes() + 1)
    except sunau.Error as error:
        assert 'not in range' in str(error)
    else:
        raise AssertionError('a position past the end was accepted')
```

### Reading from an Unseekable Stream

Opening reads the header straight through and `readframes()` reads on from there, so a pipe or
socket can be read from start to end. Only `setpos()` and `rewind()` need to seek.

```python
import io
import sunau

class Pipe:
    """Can be read from, but not sought or asked its position."""
    def __init__(self, data):
        self._data = io.BytesIO(data)
    def read(self, size=-1):
        return self._data.read(size)

buffer = io.BytesIO()
with sunau.open(buffer, 'wb') as out:
    out.setparams((1, 1, 8000, 0, 'NONE', ''))
    out.writeframes(bytes(range(100)))

with sunau.open(Pipe(buffer.getvalue()), 'rb') as audio:
    assert audio.readframes(60) == bytes(range(60))  # O(k·w)
    assert audio.readframes(60) == bytes(range(60, 100))
    try:
        audio.rewind()
    except OSError as error:
        assert 'cannot seek' in str(error)
    else:
        raise AssertionError('an unseekable stream was rewound')
```

## Writing AU Files

### The Default Compression Is u-law

A new writer encodes to u-law unless told otherwise, which halves 16-bit samples and loses
precision. Call `setcomptype('NONE', ...)`, or pass `'NONE'` to `setparams()`, to store the bytes
as given. A u-law writer encodes each call into a new buffer, and reading it back decodes into
another.

```python
import array
import io
import sunau

samples = array.array('h', [0, 1000, -1000, 32000])  # native byte order

buffer = io.BytesIO()
out = sunau.open(buffer, 'wb')  # O(1) - nothing written yet
out.setnchannels(1)
out.setsampwidth(2)
out.setframerate(8000)
assert out.getcomptype() == 'ULAW'
out.writeframes(samples)  # O(k·w), encoded to one byte per sample
out.close()
assert len(buffer.getvalue()) == 32 + len(samples)  # header + samples

buffer.seek(0)
with sunau.open(buffer, 'rb') as audio:
    assert audio.getsampwidth() == 2
    decoded = array.array('h', audio.readframes(4))  # O(k·w), decoded to 16 bits
    assert decoded[0] == 0 and decoded != samples  # close, but not the same
    assert all(abs(a - b) < 1000 for a, b in zip(decoded, samples))
```

### Patching the Header

The header records the data size. After every call, `writeframes()` seeks back to patch it, a
constant cost per call, unless the frames written so far match both the count declared with
`setnframes()` and the count the header holds. Without a declared count, every call patches;
declaring the total and writing it in one call needs none. `writeframesraw()`
never patches, and `close()` then patches once on the same condition.

```python
import io
import sunau

class Recorder(io.BytesIO):
    """A BytesIO that counts its seeks."""
    seeks = 0
    def seek(self, *args):
        self.seeks += 1
        return super().seek(*args)

in_parts = Recorder()
with sunau.open(in_parts, 'wb') as out:
    out.setparams((1, 2, 8000, 300, 'NONE', ''))
    for _ in range(3):
        out.writeframes(bytes(2 * 100))  # O(k·w), header patched each call
assert in_parts.seeks == 6  # two seeks per patch

declared = Recorder()
with sunau.open(declared, 'wb') as out:
    out.setparams((1, 2, 8000, 300, 'NONE', ''))  # O(1)
    out.writeframes(bytes(2 * 300))  # O(k·w), the header is already right
assert declared.seeks == 0

# Parameters are fixed once frames are written
out = sunau.open(io.BytesIO(), 'wb')
out.setparams((1, 2, 8000, 0, 'NONE', ''))
out.writeframes(bytes(2))
try:
    out.setframerate(22050)
except sunau.Error as error:
    assert 'cannot change parameters' in str(error)
else:
    raise AssertionError('a parameter changed after writing')
out.close()
```

### Writing to an Unseekable Stream

A pipe or socket cannot be patched. Declare the total, write with `writeframesraw()`, and
`close()` finds nothing to patch; the target needs `write()` and `flush()`, and nothing else.

```python
import sunau

class Pipe:
    """Accepts writes but cannot seek, like a pipe."""
    def __init__(self):
        self.chunks = []
    def write(self, data):
        self.chunks.append(bytes(data))
        return len(data)
    def flush(self):
        pass

pipe = Pipe()
with sunau.open(pipe, 'wb') as out:
    out.setparams((1, 2, 8000, 1000, 'NONE', ''))  # O(1)
    out.writeframesraw(bytes(2 * 500))  # O(k·w), no patch
    out.writeframesraw(bytes(2 * 500))

assert sum(map(len, pipe.chunks)) == 32 + 2 * 1000  # header + samples
```

## Common Patterns

### Converting AU to WAV a Block at a Time

Uncompressed AU samples are big-endian, while `wave` takes and returns samples in native byte
order, so 16-bit frames are byte-swapped on a little-endian host. Doing it a block at a time keeps memory at one block however
long the file is.

```python
import array
import io
import sunau
import sys
import wave

samples = array.array('h', range(-5000, 5000))
if sys.byteorder == 'little':
    samples.byteswap()  # AU stores big-endian

source = io.BytesIO()
with sunau.open(source, 'wb') as out:
    out.setparams((1, 2, 8000, 0, 'NONE', ''))
    out.writeframes(samples)

source.seek(0)
target = io.BytesIO()
with sunau.open(source, 'rb') as audio, wave.open(target, 'wb') as out:
    out.setnchannels(audio.getnchannels())
    out.setsampwidth(audio.getsampwidth())
    out.setframerate(audio.getframerate())
    while block := audio.readframes(1024):  # O(k·w)
        values = array.array('h', block)
        if sys.byteorder == 'little':
            values.byteswap()  # big-endian to native, O(k·w)
        out.writeframes(values)  # O(k·w), wave takes native order

target.seek(0)
with wave.open(target, 'rb') as audio:
    converted = array.array('h', audio.readframes(audio.getnframes()))
assert converted[0] == -5000 and converted[-1] == 4999
```

## Performance Best Practices

✅ **Do**:

- Read with a fixed block size, so memory is one block rather than the file
- Call `setcomptype('NONE', ...)` for uncompressed output; a new writer encodes to u-law
- Write an unseekable output with `setnframes()` and `writeframesraw()`, so no call needs to seek

❌ **Avoid**:

- `readframes(getnframes())` on a long file - the one call here that holds every frame at once
- `setpos()` or `rewind()` on a stream that cannot report its position - both raise `OSError`
- Setting parameters once frames are written - all but `setcomptype()` raise `sunau.Error`, and
  that one silently mixes encodings
- Expecting `close()` to close a file object you passed in - only a file opened by name is closed

## Version Notes

- **Python 3.11+**: `import sunau` emits `DeprecationWarning`
- **Python 3.13+**: The module is removed; `import sunau` raises `ModuleNotFoundError`
- **All Python 3**: Uncompressed samples are returned and written as stored, big-endian

## Related Modules

- **[wave](wave.md)** - The same frame-at-a-time interface for WAV files, still in the standard
  library
- **[array](array.md)** - Turn a block of frames into samples and back
- **[aifc](aifc.md)** - AIFF files, removed in Python 3.13
- **[audioop](audioop.md)** - The u-law conversions `sunau` uses, removed in Python 3.13
