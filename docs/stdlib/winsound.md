# winsound Module Complexity

The `winsound` module is a thin layer over three Windows calls: `PlaySound()` for WAV audio,
`Beep()` for a tone, and `MessageBeep()` for the system alert sounds. What a call costs is
mostly how long it blocks, and for `PlaySound()` also what Windows reads and keeps in memory
on the way.

It is Windows-only. On other platforms `import winsound` raises `ModuleNotFoundError`.

`d` is how long a sound plays: a synchronous call blocks for all of it, and the work of
streaming the audio to the device is counted in it. `f` is the bytes of the WAV file a sound
comes from, the whole file rather than just its audio data. A WAV image passed from memory has
no size term: it is read in place, so a larger image with the same audio costs the same.

## Complexity Reference

### PlaySound

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `winsound.PlaySound(sound, SND_MEMORY)` | O(d) | O(1) | `sound` is a bytes-like WAV image, read in place rather than copied; blocks until the sound ends |
| `winsound.PlaySound(sound, SND_FILENAME)` | O(f + d) | O(f) | Windows reads the whole file and keeps it until the next `PlaySound()` call; accepts `os.PathLike` on Python 3.12+ |
| `winsound.PlaySound(sound, SND_ALIAS)` | O(f + d) | O(f) | Looks up the event's file in the registry, then plays it as `SND_FILENAME` does |
| `winsound.PlaySound(sound, flags \| SND_ASYNC)` | O(1) | O(f) | Returns without waiting for the file to be read, which Windows does in the background; with `SND_MEMORY` it raises `RuntimeError` instead |
| `winsound.PlaySound(None, flags)` | O(1) | O(1) | Stops an asynchronous sound and releases the kept file, whatever the flags; a synchronous play in another thread runs to its end |

### Tones and alerts

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `winsound.Beep(frequency, duration)` | O(d) | O(1) | d = `duration` in milliseconds, for which the call blocks; a `frequency` outside 37 to 32,767 raises `ValueError` before anything plays |
| `winsound.MessageBeep(type=MB_OK)` | O(1) | O(1) | Queues the system sound for `type` and returns without waiting for it |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `winsound.SND_FILENAME`, `winsound.SND_ALIAS`, `winsound.SND_MEMORY` | O(1) | O(1) | Integer flags saying what `sound` is: a path, a registry event name, or a WAV image |
| `winsound.SND_APPLICATION` | O(1) | O(1) | With `SND_ALIAS`, looks the name up among the running program's own events |
| `winsound.SND_ASYNC` | O(1) | O(1) | Return without waiting for the sound; not allowed with `SND_MEMORY` |
| `winsound.SND_SYNC` | O(1) | O(1) | `0`, the default: wait for the sound to end. Python 3.14+ |
| `winsound.SND_LOOP` | O(1) | O(1) | Repeat until the next `PlaySound()` call; needs `SND_ASYNC`, so a sound from memory cannot loop |
| `winsound.SND_NODEFAULT` | O(1) | O(1) | A sound that cannot be found or played raises `RuntimeError` instead of playing the default sound |
| `winsound.SND_NOSTOP` | O(1) | O(1) | While an earlier asynchronous sound still plays, `PlaySound()` raises `RuntimeError` instead of stopping it |
| `winsound.SND_NOWAIT`, `winsound.SND_PURGE` | O(1) | O(1) | Accepted, but on Windows 11 a sound played with either while another plays is neither refused nor cut short |
| `winsound.SND_SENTRY`, `winsound.SND_SYSTEM` | O(1) | O(1) | A SoundSentry visual cue, and the system notification audio session. Python 3.14+ |
| `winsound.MB_OK`, `winsound.MB_ICONASTERISK`, `winsound.MB_ICONEXCLAMATION`, `winsound.MB_ICONHAND`, `winsound.MB_ICONQUESTION` | O(1) | O(1) | The alert a `MessageBeep()` call plays |
| `winsound.MB_ICONERROR`, `winsound.MB_ICONINFORMATION`, `winsound.MB_ICONSTOP`, `winsound.MB_ICONWARNING` | O(1) | O(1) | Other names for `MB_ICONHAND`, `MB_ICONASTERISK`, `MB_ICONHAND` and `MB_ICONEXCLAMATION`. Python 3.14+ |

## Playing From Memory

`SND_MEMORY` plays a WAV image you already hold, `bytes` or any other bytes-like object, without
copying it. The call blocks for the whole sound, and there is no asynchronous form: combining it
with `SND_ASYNC` raises before anything plays.

```python
import io
import wave
import winsound

buffer = io.BytesIO()
with wave.open(buffer, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(1)
    w.setframerate(8000)
    w.writeframes(b"\x80" * 800)  # 0.1 s of silence
data = buffer.getvalue()

flags = winsound.SND_MEMORY | winsound.SND_NODEFAULT
winsound.PlaySound(data, flags)  # O(d) - returns when the sound ends
winsound.PlaySound(bytearray(data), flags)  # any bytes-like object

try:
    winsound.PlaySound(data, flags | winsound.SND_ASYNC)
except RuntimeError as error:
    assert "asynchronously from memory" in str(error)
else:
    raise AssertionError("an asynchronous play from memory was accepted")
```

## Playing a File

A file is not streamed. Windows reads the whole of it, including any chunks around the audio,
and keeps it after the call returns until the next `PlaySound()` call. `PlaySound(None, 0)`
releases it, and also stops a sound started with `SND_ASYNC`.

```python
import os
import tempfile
import wave
import winsound

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "silence.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(8000)
        w.writeframes(b"\x80" * 8000)  # 1 s of silence

    flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT
    winsound.PlaySound(path, flags)  # O(f + d) - reads the file, then plays it to the end
    winsound.PlaySound(path, flags | winsound.SND_ASYNC)  # O(1) - does not wait for the read
    winsound.PlaySound(None, 0)  # O(1) - stops it and releases the file's bytes
```

### Missing Sounds

A file or alias that cannot be found is not an error by default: Windows plays the default
system sound instead. `SND_NODEFAULT` turns that into a `RuntimeError`.

```python
import os
import tempfile
import winsound

with tempfile.TemporaryDirectory() as tmp:
    missing = os.path.join(tmp, "missing.wav")
    try:
        winsound.PlaySound(missing, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    except RuntimeError as error:
        assert str(error) == "Failed to play sound"
    else:
        raise AssertionError("a missing file played")
```

## Looping

`SND_LOOP` repeats the sound until the next `PlaySound()` call, and Windows loops only a sound
played with `SND_ASYNC`. Memory cannot play asynchronously, so a loop needs a file or an alias.

```python
import os
import tempfile
import wave
import winsound

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "silence.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(8000)
        w.writeframes(b"\x80" * 800)

    flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT
    winsound.PlaySound(path, flags | winsound.SND_ASYNC | winsound.SND_LOOP)  # O(1) - loops
    winsound.PlaySound(None, 0)      # O(1) - ends the loop

    with open(path, "rb") as f:
        data = f.read()
    try:
        winsound.PlaySound(data, winsound.SND_MEMORY | winsound.SND_ASYNC | winsound.SND_LOOP)
    except RuntimeError as error:
        assert "asynchronously from memory" in str(error)
    else:
        raise AssertionError("a loop from memory was accepted")
```

## Tones and System Sounds

`Beep()` blocks for its duration. `MessageBeep()` hands the alert to Windows and returns at
once. Both make a sound, so this example is not run by the test suite.

```python
import winsound

winsound.Beep(440, 500)  # O(d) - blocks for 500 ms
winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)  # O(1) - returns without waiting
```

## Common Patterns

### Playing Generated Audio Without Blocking

A WAV image built in memory cannot play asynchronously. Write it to a file and play that, then
stop it and remove the file when it is no longer needed.

```python
import io
import os
import tempfile
import wave
import winsound

buffer = io.BytesIO()
with wave.open(buffer, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(1)
    w.setframerate(8000)
    w.writeframes(b"\x80" * 4000)

fd, path = tempfile.mkstemp(suffix=".wav")
with os.fdopen(fd, "wb") as f:
    f.write(buffer.getvalue())  # O(f)

flags = winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC
winsound.PlaySound(path, flags)  # O(1)
# ... carry on while it plays ...
winsound.PlaySound(None, 0)  # O(1)
os.remove(path)
```

## Performance Best Practices

✅ **Do**:

- Pass `SND_ASYNC` from a thread that must stay responsive; the default blocks for the sound
- Use `SND_MEMORY` for a sound you already hold: it is read in place, not copied
- Add `SND_NODEFAULT` when a file or alias may be missing, so the failure raises instead of
  playing the default sound
- Call `PlaySound(None, 0)` after a large file, which releases the copy Windows kept

❌ **Avoid**:

- `SND_ASYNC` with `SND_MEMORY` - it raises `RuntimeError` on every version
- Playing a short sound from a large file - Windows reads the whole file, not just the audio
- Relying on `SND_PURGE` or `SND_NOWAIT`; stop a sound with `PlaySound(None, 0)`
- Stopping a synchronous play from another thread - `PlaySound(None, 0)` does not reach it

## Version Notes

- **Python 3.12+**: `PlaySound()` accepts an `os.PathLike` path; earlier versions accept only `str`
- **Python 3.14+**: Added `SND_SYNC`, `SND_SENTRY`, `SND_SYSTEM`, `MB_ICONERROR`,
  `MB_ICONINFORMATION`, `MB_ICONSTOP` and `MB_ICONWARNING`
- **All Python 3**: Windows only, and `SND_MEMORY` cannot be combined with `SND_ASYNC`

## Related Modules

- **[wave](wave.md)** - builds and reads the WAV images `PlaySound()` plays
- **[winreg](winreg.md)** - the registry, where `SND_ALIAS` looks up event sounds
- **[tempfile](tempfile.md)** - a file for audio built in memory that has to play asynchronously
