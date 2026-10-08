# sndhdr Module Complexity

The `sndhdr` module guesses a sound file's format from its header. `what()` opens a path, reads
its first 512 bytes, and hands them with the open file to each function in `sndhdr.tests` in turn
until one recognises the format. Most formats are decided from those bytes alone; a WAV or AIFF
file is handed on to `wave` or `aifc`, which read its chunk headers but not its samples.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The examples that import
    it need Python 3.10, 3.11 or 3.12.

`t` is the functions in `sndhdr.tests`, eight built in, and `c` is the chunk headers read from a
WAV or AIFF file: those up to the `data` chunk in a WAV file, and every chunk in an AIFF or AIFC
file. The other built-in functions look only at those header bytes, so each is O(1); a function
you append costs whatever it does. Opening the file and one read or seek on it are priced at
O(1), and the bounds leave out the marker list `aifc` keeps from an AIFF `MARK` chunk.

## Complexity Reference

### Functions and data

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sndhdr.what(filename)` | O(t + c) | O(1) | Returns the first `SndHeaders` a function in `tests` produces, or `None`. Takes a path, not an open file; raises `OSError` if it cannot be opened. Beyond the first 512 bytes, only a WAV or AIFF file is read further, and not its samples, so a recording's length does not enter the cost. A WAV file whose first chunk is not `fmt `, or a format `wave` or `aifc` does not read, such as a floating-point WAV, is `None` |
| `sndhdr.whathdr(filename)` | O(t + c) | O(1) | What `what()` calls; the same result |
| `sndhdr.tests` | O(1) | O(1) | The functions tried in order; append a function `test(h, f)` that takes up to 512 header bytes and the open file and returns a five-item tuple or `None` |

### SndHeaders

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sndhdr.SndHeaders` | O(1) | O(1) | The named tuple `what()` returns |
| `SndHeaders.filetype`, `SndHeaders.framerate`, `SndHeaders.nchannels`, `SndHeaders.nframes`, `SndHeaders.sampwidth` | O(1) | O(1) | The tuple's fields, in this order |

## Identifying a Sound File

A format such as AU states its rate, channels and data size in a fixed header, so `what()` answers
from the first 512 bytes however long the file is.

```python
import os
import struct
import tempfile
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)  # 3.11 and 3.12 warn on import
    import sndhdr

# AU: magic, header size, data size, encoding 3 (16-bit linear), rate, channels
header = struct.pack('>4s5I', b'.snd', 24, 16000, 3, 8000, 1)

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'speech.au')
    with open(path, 'wb') as f:
        f.write(header + bytes(16000))

    info = sndhdr.what(path)  # O(t) - one 512-byte read
    assert info.filetype == 'au'
    assert (info.framerate, info.nchannels, info.sampwidth) == (8000, 1, 16)
    assert info.nframes == 8000  # 16,000 data bytes / 2 bytes per frame
    assert sndhdr.whathdr(path) == info

    # Text no function recognises is None, not an error
    text = os.path.join(directory, 'notes.txt')
    with open(text, 'wb') as f:
        f.write(b'not a sound file')
    assert sndhdr.what(text) is None

    try:
        sndhdr.what(os.path.join(directory, 'missing.au'))
    except OSError:
        pass
    else:
        raise AssertionError('a missing file was not reported')
```

## WAV and AIFF Files

These two are handed to `wave` and `aifc`, which read chunk headers to find the format chunk and
the frame count. `wave` stops at the `data` chunk and `aifc` seeks past the samples to the end, so
the cost follows the number of chunks, not the length of the audio.

```python
import os
import tempfile
import warnings
import wave

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sndhdr

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'tone.wav')
    with wave.open(path, 'wb') as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(44100)
        out.writeframes(bytes(44100 * 4))  # one second of stereo silence

    info = sndhdr.what(path)  # O(t + c) - the recording's length does not matter
    assert info == ('wav', 44100, 2, 44100, 16)
```

## Adding a Format

Appending to `sndhdr.tests` adds one more call to every file no earlier function recognises. A
function sees up to 512 header bytes and the open file.

```python
import os
import tempfile
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sndhdr

def test_flac(h, f):
    if h[:4] == b'fLaC':
        return ('flac', 0, 0, -1, 0)  # filetype, framerate, nchannels, nframes, sampwidth

sndhdr.tests.append(test_flac)
try:
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'song.flac')
        with open(path, 'wb') as f:
            f.write(b'fLaC' + bytes(100))
        assert sndhdr.what(path).filetype == 'flac'  # O(t), now one longer
finally:
    sndhdr.tests.remove(test_flac)
```

## Without sndhdr

From Python 3.13, `wave` still reads WAV files. Telling the other formats apart means comparing
their first bytes yourself, which is still a fixed-size read.

```python
import io
import wave

def sound_type(header):
    """The format the first 12 bytes name, or None."""
    if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
        return 'wav'
    if header[:4] == b'FORM' and header[8:12] in (b'AIFF', b'AIFC'):
        return header[8:12].decode('ascii').lower()
    if header[:4] == b'.snd':
        return 'au'
    return None

buffer = io.BytesIO()
with wave.open(buffer, 'wb') as out:
    out.setnchannels(1)
    out.setsampwidth(2)
    out.setframerate(8000)
    out.writeframes(bytes(16000))

buffer.seek(0)
assert sound_type(buffer.read(12)) == 'wav'  # O(1)

buffer.seek(0)
with wave.open(buffer, 'rb') as wav:  # O(c) - the samples are not read
    params = wav.getparams()
assert (params.framerate, params.nchannels, params.nframes) == (8000, 1, 8000)
```

## Performance Best Practices

✅ **Do**:

- Call `what()` on long recordings without worry: it reads headers, not the recording
- Treat `None` as "not a format this module can read", not "not a sound file": a floating-point
  WAV is `None`, and so is a WAV whose first chunk is not `fmt `, such as one led by a `JUNK` chunk
- Catch exceptions on files you did not write: a truncated header, such as an AU file shorter than
  its 24-byte header, can raise `IndexError` instead of returning `None`
- Treat `'sndr'` as a guess: two zero bytes and a plausible rate are all it checks

❌ **Avoid**:

- Passing an open file: `what()` takes a path and raises `TypeError` for a file object
- Appending a slow function to `sndhdr.tests`: every file no earlier function recognises pays for it

## Version Notes

- **Python 3.11 and 3.12**: Importing the module emits a `DeprecationWarning`
- **Python 3.12**: A PCM WAV file in the `WAVE_FORMAT_EXTENSIBLE` layout is recognised as `'wav'`;
  3.10 and 3.11 return `None` for it
- **Python 3.13+**: Removed by PEP 594, with `aifc` and `sunau`; `import sndhdr` raises
  `ModuleNotFoundError`

## Related Modules

- **[wave](wave.md)** - reads WAV headers and frames, and remains after 3.13; `what()` uses it
- **[aifc](aifc.md)** - what `what()` uses for AIFF and AIFC files, removed in 3.13 too
- **[sunau](sunau.md)** - reads the AU files `what()` recognises from their header, removed in 3.13
  too
- **[imghdr](imghdr.md)** - the same header-sniffing design for images, removed in 3.13 too
