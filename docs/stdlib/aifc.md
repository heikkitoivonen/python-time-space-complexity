# aifc Module Complexity

The `aifc` module reads and writes AIFF and AIFF-C audio files. It is pure Python and works a call
at a time: opening a file walks its chunk headers, `readframes()` returns a block of frames,
and `writeframes()` passes your bytes to the file. Nothing in the module holds the audio unless
you read it all at once.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 (PEP 594). The page covers the module
    as it is on Python 3.10 to 3.12, and its examples run only there; from 3.11, `import aifc`
    emits a `DeprecationWarning`.

Frames are the unit throughout. `k` is the frames read or written in one call and `w` is the
bytes in one frame (`nchannels × sampwidth`), so one call moves `k·w` bytes. `c` is the chunks in
the file and `m` is its markers. Frame counts and positions are exact for uncompressed files,
whose samples are stored big-endian and returned as stored, on every host.

## Complexity Reference

### open and Error

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `aifc.open(file, mode=None)` | O(c + m) to read, O(1) to write | O(m) to read, O(1) to write | `'r'` or `'rb'` returns an `Aifc_read`, `'w'` or `'wb'` an `Aifc_write`; without a mode, `file.mode` decides, else `'rb'` |
| `aifc.Error` | O(1) | O(1) | Raised for a file that is not AIFF or AIFF-C, an unsupported compression type, and a parameter that is invalid, missing or set too late |

### Aifc_read

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `aifc.Aifc_read(file)`, `aifc.open(file, 'rb')` | O(c + m) | O(m) | Reads every chunk header to the end of the file, seeking past the bodies, and keeps the markers; no samples are read. The file must be seekable: an unseekable stream is read through to the end, and the first `readframes()` then raises `OSError` |
| `Aifc_read.readframes(nframes)` | O(k·w) | O(k·w) | k = frames returned, which is fewer than `nframes` at the end of the data; a compressed file is decoded into a new buffer |
| `Aifc_read.setpos(pos)`, `Aifc_read.rewind()` | O(1) | O(1) | Records the position; the next `readframes()` seeks there |
| `Aifc_read.tell()` | O(1) | O(1) | Frames read so far, or the position set |
| `Aifc_read.getnchannels()`, `Aifc_read.getsampwidth()`, `Aifc_read.getframerate()`, `Aifc_read.getnframes()` | O(1) | O(1) | Read from the `COMM` chunk when the file was opened |
| `Aifc_read.getcomptype()`, `Aifc_read.getcompname()` | O(1) | O(1) | Bytes: `b'NONE'` and `b'not compressed'` for an AIFF file |
| `Aifc_read.getparams()` | O(1) | O(1) | A named tuple of the six values above |
| `Aifc_read.getmarkers()` | O(1) | O(1) | The list built when the file was opened, not a copy, or `None` when there are no markers |
| `Aifc_read.getmark(id)` | O(m) | O(1) | Scans the markers in order; raises `aifc.Error` if none has that id |
| `Aifc_read.close()` | O(1) | O(1) | Closes the file, including one passed in as a file object |

### Aifc_write

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `aifc.Aifc_write(file)`, `aifc.open(file, 'wb')` | O(1) | O(1) | Writes nothing; the header goes out with the first frames or at `close()`. A file name ending in `.aiff` writes AIFF, anything else AIFF-C |
| `Aifc_write.aiff()`, `Aifc_write.aifc()` | O(1) | O(1) | Choose AIFF or AIFF-C; raise `aifc.Error` once frames have been written |
| `Aifc_write.setnchannels(nchannels)`, `Aifc_write.setsampwidth(width)`, `Aifc_write.setframerate(rate)`, `Aifc_write.setnframes(nframes)`, `Aifc_write.setcomptype(type, name)` | O(1) | O(1) | Raise `aifc.Error` once frames have been written; all but `setnframes()` also reject a bad value |
| `Aifc_write.setparams(params)` | O(1) | O(1) | The five setters in one call |
| `Aifc_write.setmark(id, pos, name)` | O(m) | O(1) | Scans for a marker with the same id to replace, else appends; markers are written at `close()` |
| `Aifc_write.getmarkers()` | O(1) | O(1) | The writer's own list, not a copy, or `None` when there are no markers |
| `Aifc_write.getmark(id)` | O(m) | O(1) | Scans the markers in order; raises `aifc.Error` if none has that id |
| `Aifc_write.writeframes(data)` | O(k·w) | O(1), O(k·w) compressed | Uncompressed bytes are written as given, not copied; whenever the frames written so far differ from the header's count, its frame count and two length fields are patched in place |
| `Aifc_write.writeframesraw(data)` | O(k·w) | O(1), O(k·w) compressed | The same without the patch, which is left to `close()` |
| `Aifc_write.tell()`, `Aifc_write.getnframes()` | O(1) | O(1) | Frames written so far |
| `Aifc_write.getnchannels()`, `Aifc_write.getsampwidth()`, `Aifc_write.getframerate()` | O(1) | O(1) | Raise `aifc.Error` until set |
| `Aifc_write.getcomptype()`, `Aifc_write.getcompname()` | O(1) | O(1) | `b'NONE'` and `b'not compressed'` until `setcomptype()` |
| `Aifc_write.getparams()` | O(1) | O(1) | Raises `aifc.Error` until channels, sample width and frame rate are set |
| `Aifc_write.close()` | O(m) | O(1) | Writes the header if no frames were, then the markers, and patches the header if its count is wrong or there are markers; closes the file, including one passed in as a file object |

## Reading AIFF Files

### Opening a File

Opening a file reads the header of every chunk in it, seeking past each body, and parses the
`MARK` chunk into a list. The frame count comes from the `COMM` chunk, so the length of the audio
does not enter the cost.

```python
import aifc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'second.aiff')
    with aifc.open(path, 'wb') as out:
        out.setparams((2, 2, 44100, 0, b'NONE', b'not compressed'))
        out.writeframes(bytes(4 * 44100))  # one second of stereo silence

    with aifc.open(path, 'rb') as audio:  # O(c + m) - the samples are not read
        assert audio.getnframes() == 44100  # O(1)
        assert audio.getparams() == (2, 2, 44100, 44100, b'NONE', b'not compressed')
        assert audio.getmarkers() is None  # O(1)
```

### Reading in Blocks

`readframes()` returns what you ask for as one `bytes` object, so memory follows the request, not
the file. Reading a fixed block at a time holds one block; `readframes(getnframes())` holds the
whole file.

```python
import aifc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'tone.aiff')
    with aifc.open(path, 'wb') as out:
        out.setparams((1, 2, 8000, 0, b'NONE', b'not compressed'))
        out.writeframes(bytes(2 * 10_000))

    with aifc.open(path, 'rb') as audio:
        frames = 0
        while block := audio.readframes(4096):  # O(k·w) per block
            assert len(block) <= 4096 * 2
            frames += len(block) // 2
        assert frames == 10_000
        assert audio.readframes(4096) == b''  # at the end
```

### Seeking

`setpos()` and `rewind()` only record where the next read starts; `readframes()` does the seek,
so the frames skipped are never read.

```python
import aifc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'ramp.aiff')
    with aifc.open(path, 'wb') as out:
        out.setparams((1, 1, 8000, 0, b'NONE', b'not compressed'))
        out.writeframes(bytes(range(256)) * 4)

    with aifc.open(path, 'rb') as audio:
        audio.setpos(1000)  # O(1)
        assert audio.tell() == 1000
        assert audio.readframes(10) == bytes(range(232, 242))  # a seek, then O(k·w)
        audio.rewind()  # O(1)
        assert audio.readframes(3) == bytes([0, 1, 2])

        try:
            audio.setpos(audio.getnframes() + 1)
        except aifc.Error as error:
            assert 'not in range' in str(error)
        else:
            raise AssertionError('a position past the end was accepted')
```

### Markers

A marker is an id, a frame position and a name. Setting one scans the markers for its id, and so
does looking one up, so both cost O(m); the whole list comes back without a copy.

```python
import aifc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'marked.aiff')
    with aifc.open(path, 'wb') as out:
        out.setparams((1, 1, 8000, 0, b'NONE', b'not compressed'))
        out.setmark(1, 0, b'start')  # O(m)
        out.setmark(2, 50, b'middle')
        out.setmark(2, 60, b'moved')  # same id: replaced, not added
        out.writeframes(bytes(100))
    # close() wrote the markers, O(m)

    with aifc.open(path, 'rb') as audio:  # O(c + m)
        markers = audio.getmarkers()  # O(1)
        assert markers == [(1, 0, b'start'), (2, 60, b'moved')]
        assert audio.getmarkers() is markers
        assert audio.getmark(2) == (2, 60, b'moved')  # O(m)
```

## Writing AIFF Files

### Writing Frames

`writeframes()` hands uncompressed bytes to the file without copying them. The header goes out
with the first frames, and after every call `writeframes()` makes it match the frames written so
far: when they differ, it seeks back and rewrites the length fields, a constant cost per call.

```python
import aifc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'out.aifc')
    out = aifc.open(path, 'wb')  # O(1) - nothing written yet
    out.setnchannels(2)       # Stereo
    out.setsampwidth(2)       # 16-bit
    out.setframerate(44100)   # 44.1 kHz
    assert os.path.getsize(path) == 0

    out.writeframes(bytes(4 * 100))  # O(k·w), header written first
    out.writeframes(bytes(4 * 100))  # O(k·w), header lengths patched
    assert out.tell() == 200

    # Parameters are fixed once frames are written
    try:
        out.setframerate(22050)
    except aifc.Error as error:
        assert 'cannot change parameters' in str(error)
    else:
        raise AssertionError('a parameter changed after writing')
    out.close()

    with aifc.open(path, 'rb') as audio:
        assert audio.getnframes() == 200
        assert audio.getcomptype() == b'NONE'  # an AIFF-C file, uncompressed
```

### Writing to an Unseekable Stream

A pipe or socket cannot be patched, and `writeframes()` patches after any call that leaves the
header's count behind. Declare the total, write with `writeframesraw()`, and `close()` finds
nothing to patch. Markers always need a patch, so they need a seekable file.

```python
import aifc

class Pipe:
    """Accepts writes but cannot seek, like a pipe."""
    def __init__(self):
        self.chunks = []
    def write(self, data):
        self.chunks.append(bytes(data))
        return len(data)
    def close(self):
        pass

pipe = Pipe()
with aifc.open(pipe, 'wb') as out:
    out.aiff()
    out.setparams((1, 2, 8000, 1000, b'NONE', b'not compressed'))  # O(1)
    out.writeframesraw(bytes(2 * 500))  # O(k·w), no patch
    out.writeframesraw(bytes(2 * 500))

assert sum(map(len, pipe.chunks)) == 54 + 2 * 1000  # AIFF header + samples
```

## Common Patterns

### Transforming Samples a Block at a Time

Uncompressed frames are raw big-endian bytes. `array.array` turns a block into samples and back in O(k·w),
with a byte swap on a little-endian host, and doing it per block keeps memory at one block
however long the file is.

```python
import aifc
import array
import os
import sys
import tempfile

def samples(block):
    values = array.array('h', block)  # O(k·w)
    if sys.byteorder == 'little':
        values.byteswap()  # O(k·w)
    return values

def frames(values):
    values = array.array('h', values)
    if sys.byteorder == 'little':
        values.byteswap()
    return values.tobytes()

with tempfile.TemporaryDirectory() as directory:
    source = os.path.join(directory, 'source.aiff')
    target = os.path.join(directory, 'target.aiff')
    with aifc.open(source, 'wb') as out:
        out.setparams((1, 2, 8000, 0, b'NONE', b'not compressed'))
        out.writeframes(frames(range(-5000, 5000)))

    with aifc.open(source, 'rb') as audio, aifc.open(target, 'wb') as out:
        out.setparams(audio.getparams())  # O(1)
        while block := audio.readframes(1024):  # O(k·w)
            out.writeframes(frames(s // 2 for s in samples(block)))  # O(k·w)

    with aifc.open(target, 'rb') as audio:
        halved = samples(audio.readframes(audio.getnframes()))
    assert halved[0] == -2500 and halved[-1] == 4999 // 2
    assert len(halved) == 10_000
```

## Performance Best Practices

✅ **Do**:

- Read with a fixed block size, so memory is one block rather than the file
- Use `setpos()` to jump; the skipped frames are never read
- Write an unseekable output with `setnframes()` and `writeframesraw()`, so no call needs to seek
- Pass `bytes` or another buffer to `writeframes()` directly; uncompressed frames are written
  without a copy

❌ **Avoid**:

- `readframes(getnframes())` on a long file - the one call here that holds every frame at once
- Reading from an unseekable stream - opening reads through the whole stream, and
  `readframes()` then raises `OSError`
- Setting parameters once frames are written - it raises `aifc.Error`
- Using the file object after `close()` - `aifc` closes it, even one you opened yourself

## Version Notes

- **Python 3.11+**: `import aifc` emits `DeprecationWarning`; reads and writes the `sowt`
  (little-endian) compression type, which earlier versions reject with `aifc.Error`
- **Python 3.13+**: The module is removed; `import aifc` raises `ModuleNotFoundError`
- **All Python 3**: Uncompressed samples are returned and written as stored, big-endian

## Related Modules

- **[wave](wave.md)** - The same frame-at-a-time interface for WAV files, still in the standard
  library
- **[array](array.md)** - Turn a block of frames into samples and back
- **[sunau](sunau.md)** - Sun AU files, removed in Python 3.13
- **[audioop](audioop.md)** - The sample conversions `aifc` uses for compressed files, removed in
  Python 3.13
