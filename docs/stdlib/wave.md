# wave Module Complexity

The `wave` module reads and writes uncompressed PCM WAV files. It is pure Python and works a call
at a time: opening a file reads its header, `readframes()` returns the frames you ask for, and
`writeframes()` passes your bytes straight to the file. Nothing in the module holds the audio
unless you read it all at once.

Frames are the unit throughout. `k` is the frames read or written in one call and `w` is the
bytes in one frame (`nchannels × sampwidth`), so one call moves `k·w` bytes. `c` is the chunks
stored ahead of the `data` chunk, and `s` is their size in bytes. Space bounds assume a
little-endian host; on a big-endian one, samples wider than a byte are swapped into a copy.

## Complexity Reference

### open and Error

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wave.open(file, mode=None)` | O(c) to read, O(1) to write | O(1) | `'rb'` returns a `Wave_read`, `'wb'` a `Wave_write`; without a mode, `file.mode` decides, else `'rb'` |
| `wave.Error` | O(1) | O(1) | Raised for a format the module does not support, and for a parameter that is invalid, missing or set too late |

### Wave_read

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wave.Wave_read(file)`, `wave.open(file, 'rb')` | O(c) | O(1) | Reads chunk headers up to `data` and seeks past the rest; an unseekable stream reads through them instead, O(c + s). No samples are read |
| `Wave_read.readframes(n)` | O(k·w) | O(k·w) | k = frames returned, which is fewer than n at the end of the data |
| `Wave_read.setpos(pos)`, `Wave_read.rewind()` | O(1) | O(1) | Records the position; the next `readframes()` seeks there, and raises `OSError` if the stream cannot seek |
| `Wave_read.tell()` | O(1) | O(1) | Frames read so far, or the position set |
| `Wave_read.getnchannels()`, `Wave_read.getsampwidth()`, `Wave_read.getframerate()`, `Wave_read.getnframes()` | O(1) | O(1) | Read from the header when the file was opened |
| `Wave_read.getcomptype()`, `Wave_read.getcompname()` | O(1) | O(1) | Always `'NONE'` and `'not compressed'` |
| `Wave_read.getparams()` | O(1) | O(1) | A named tuple of the six values above |
| `Wave_read.getmarkers()`, `Wave_read.getmark(id)` | O(1) | O(1) | `getmarkers()` returns `None` and `getmark()` raises `wave.Error`; both deprecated from Python 3.13 |
| `Wave_read.close()` | O(1) | O(1) | Closes the file only if it was opened from a file name |

### Wave_write

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `wave.Wave_write(file)`, `wave.open(file, 'wb')` | O(1) | O(1) | Writes nothing; the header goes out with the first frames or at `close()` |
| `Wave_write.setnchannels(n)`, `Wave_write.setsampwidth(n)`, `Wave_write.setframerate(n)`, `Wave_write.setnframes(n)`, `Wave_write.setcomptype(type, name)` | O(1) | O(1) | Raise `wave.Error` once frames have been written; all but `setnframes()` also reject a bad value |
| `Wave_write.setparams(tuple)` | O(1) | O(1) | The five setters in one call |
| `Wave_write.writeframes(data)` | O(k·w) | O(1) | The bytes are written as given, not copied; whenever the frames written so far differ from the header's count, its two length fields are patched in place |
| `Wave_write.writeframesraw(data)` | O(k·w) | O(1) | The same without the patch, which is left to `close()` |
| `Wave_write.tell()`, `Wave_write.getnframes()` | O(1) | O(1) | Frames written so far |
| `Wave_write.getnchannels()`, `Wave_write.getsampwidth()`, `Wave_write.getframerate()` | O(1) | O(1) | Raise `wave.Error` until set |
| `Wave_write.getcomptype()`, `Wave_write.getcompname()` | O(1) | O(1) | Raise `AttributeError` until `setcomptype()` or `setparams()` is called |
| `Wave_write.getparams()` | O(1) | O(1) | Raises until channels, sample width, frame rate and compression type are set |
| `Wave_write.close()` | O(1) | O(1) | Writes the header if no frames were, patches it if the frame count is wrong, then flushes |

## Reading WAV Files

### Opening Reads Only the Header

Opening a file walks its chunk headers until it reaches `data`, and stops there. The frame count
comes from the size of that chunk, so the length of the audio does not enter the cost.

```python
import io
import wave

buffer = io.BytesIO()
with wave.open(buffer, 'wb') as out:
    out.setnchannels(2)
    out.setsampwidth(2)
    out.setframerate(44100)
    out.writeframes(bytes(4 * 44100))  # one second of stereo silence

buffer.seek(0)
with wave.open(buffer, 'rb') as wav:  # O(c) - the samples are not read
    assert buffer.tell() < 100
    assert wav.getnframes() == 44100  # O(1)
    assert wav.getparams() == (2, 2, 44100, 44100, 'NONE', 'not compressed')
```

### Reading in Blocks

`readframes()` returns what you ask for as one `bytes` object, so memory follows the request, not
the file. Reading a fixed block at a time holds one block; `readframes(getnframes())` holds the
whole file.

```python
import io
import wave

buffer = io.BytesIO()
with wave.open(buffer, 'wb') as out:
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(8000)
    out.writeframes(bytes(2 * 10_000))

buffer.seek(0)
with wave.open(buffer, 'rb') as wav:
    frames = 0
    while block := wav.readframes(4096):  # O(k·w) per block
        assert len(block) <= 4096 * 2
        frames += len(block) // 2
    assert frames == 10_000
    assert wav.readframes(4096) == b''  # at the end
```

### Seeking

`setpos()` and `rewind()` only record where the next read starts; `readframes()` does the seek,
so the frames skipped are never read.

```python
import io
import wave

buffer = io.BytesIO()
with wave.open(buffer, 'wb') as out:
    out.setnchannels(1)
    out.setsampwidth(1)
    out.setframerate(8000)
    out.writeframes(bytes(range(256)) * 4)

buffer.seek(0)
with wave.open(buffer, 'rb') as wav:
    wav.setpos(1000)  # O(1)
    assert wav.tell() == 1000
    assert wav.readframes(10) == bytes(range(232, 242))  # a seek, then O(k·w)
    wav.rewind()  # O(1)
    assert wav.readframes(3) == bytes([0, 1, 2])

    try:
        wav.setpos(wav.getnframes() + 1)
    except wave.Error as error:
        assert 'not in range' in str(error)
    else:
        raise AssertionError('a position past the end was accepted')
```

## Writing WAV Files

### Writing Frames

`writeframes()` hands your bytes to the file without copying them. The header goes out with the
first frames, and after every call `writeframes()` makes it match the frames written so far: when
they differ, it seeks back and rewrites the two length fields, a constant cost per call.

```python
import io
import wave

buffer = io.BytesIO()
out = wave.open(buffer, 'wb')  # O(1) - nothing written yet
out.setnchannels(2)       # Stereo
out.setsampwidth(2)       # 16-bit
out.setframerate(44100)   # 44.1 kHz
assert buffer.getvalue() == b''

out.writeframes(bytes(4 * 100))  # O(k·w), header written first
out.writeframes(bytes(4 * 100))  # O(k·w), header lengths patched
assert out.tell() == 200
out.close()

buffer.seek(0)
with wave.open(buffer, 'rb') as wav:
    assert wav.getnframes() == 200

# Parameters are fixed once frames are written
late = wave.open(io.BytesIO(), 'wb')
late.setparams((1, 1, 8000, 0, 'NONE', 'not compressed'))  # O(1)
late.writeframes(b'\x80')
try:
    late.setframerate(16000)
except wave.Error as error:
    assert 'cannot change parameters' in str(error)
else:
    raise AssertionError('a parameter changed after writing')
late.close()
```

### Writing to an Unseekable Stream

A pipe or socket cannot be patched, and `writeframes()` patches after any call that leaves the
header's count behind, including a correct `setnframes()` total written in several calls. Declare
the total, write with `writeframesraw()`, and `close()` finds nothing to patch.

```python
import wave

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
with wave.open(pipe, 'wb') as out:
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(8000)
    out.setnframes(1000)  # O(1) - the header will be right
    out.writeframesraw(bytes(2 * 500))  # O(k·w), no patch
    out.writeframesraw(bytes(2 * 500))

assert sum(map(len, pipe.chunks)) == 44 + 2 * 1000
```

## Common Patterns

### Transforming Samples a Block at a Time

Frames are raw bytes. `array.array` turns a block into samples and back in O(k·w), and doing it
per block keeps memory at one block however long the file is.

```python
import array
import io
import wave

source = io.BytesIO()
with wave.open(source, 'wb') as out:
    out.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
    out.writeframes(array.array('h', range(-5000, 5000)).tobytes())

source.seek(0)
target = io.BytesIO()
with wave.open(source, 'rb') as wav, wave.open(target, 'wb') as out:
    out.setparams(wav.getparams())  # O(1)
    while block := wav.readframes(1024):  # O(k·w)
        samples = array.array('h', block)  # O(k·w)
        out.writeframes(array.array('h', (s // 2 for s in samples)))  # O(k·w)

target.seek(0)
with wave.open(target, 'rb') as wav:
    halved = array.array('h', wav.readframes(wav.getnframes()))
assert halved[0] == -2500 and halved[-1] == 4999 // 2
assert len(halved) == 10_000
```

## Performance Best Practices

✅ **Do**:

- Read with a fixed block size, so memory is one block rather than the file
- Use `setpos()` to jump; on a seekable file the skipped frames are never read
- Write an unseekable output with `setnframes()` and `writeframesraw()`, so no call needs to seek
- Pass an `array.array` or other buffer to `writeframes()` directly; it is written without a copy

❌ **Avoid**:

- `readframes(getnframes())` on a long file - the one call here that holds every frame at once
- Setting parameters once frames are written - it raises `wave.Error`
- `setpos()` or `rewind()` on a stream that cannot seek - the next `readframes()` raises `OSError`

## Version Notes

- **Python 3.12+**: Reads `WAVE_FORMAT_EXTENSIBLE` headers whose subformat is PCM; earlier versions
  raise `wave.Error` on them
- **Python 3.13+**: `Wave_read.getmarkers()` and `Wave_read.getmark()` emit `DeprecationWarning`
- **All Python 3**: Only uncompressed PCM is read or written; any other format raises `wave.Error`

## Related Modules

- **[array](array.md)** - Turn a block of frames into samples and back
- **[io](io.md)** - `BytesIO` for building or parsing a WAV file in memory
- **[aifc](aifc.md)** - AIFF files, removed in Python 3.13
- **[sunau](sunau.md)** - Sun AU files, removed in Python 3.13
