# winsound Module

The `winsound` module provides access to the basic sound-playing machinery in
Windows: a tone generator, WAV playback, and the system alert sounds.

It is Windows-only. On other platforms importing it raises
`ModuleNotFoundError`.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Beep(frequency, duration)` | O(1) + blocks | O(1) | Blocks for `duration` milliseconds |
| `PlaySound(sound, flags)` | O(1) or O(n) | O(1) or O(n) | O(1) for a filename or alias; O(n) when passing WAV bytes |
| `MessageBeep(type)` | O(1) | O(1) | Plays a system alert; returns immediately |

The interesting cost here is not algorithmic but whether the call blocks:

| Flag | Behavior |
|------|----------|
| `SND_ASYNC` | Returns immediately; sound plays in the background |
| `SND_SYNC` | Blocks for the full duration of the sound (default) |
| `SND_MEMORY` | `sound` is a bytes-like WAV image; O(n) in its size |
| `SND_FILENAME` | `sound` is a path; the OS streams it |
| `SND_ALIAS` | `sound` names a system event sound |
| `SND_LOOP` | Repeats until the next `PlaySound` call; requires `SND_ASYNC` |
| `SND_NOSTOP` | Do not interrupt a sound already playing |

## Playing a WAV File

```python
import winsound

# Blocking - returns when playback finishes
winsound.PlaySound("alert.wav", winsound.SND_FILENAME)

# Non-blocking - returns immediately, O(1)
winsound.PlaySound("alert.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)

# Stop whatever is playing - O(1)
winsound.PlaySound(None, winsound.SND_PURGE)
```

## Tones and System Sounds

```python
import winsound

# 440 Hz for 500 ms - blocks for the full duration
winsound.Beep(440, 500)

# System alert, returns immediately - O(1)
winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
```

## Playing From Memory

```python
import winsound

with open("alert.wav", "rb") as f:
    data = f.read()          # O(n) in file size

# O(n) - the whole WAV image must be in memory
winsound.PlaySound(data, winsound.SND_MEMORY)
```

!!! warning "Windows only"
    There is no cross-platform sound module in the standard library. For
    portable audio, use a third-party library and select the backend at
    runtime.

!!! tip "Do not block a UI thread"
    The default is `SND_SYNC`, which blocks for the length of the sound. In an
    interactive or server process, pass `SND_ASYNC`.

## Version Notes

- **All Python 3 versions**: available on Windows builds only
- **All versions**: per-call complexity is unchanged; wall-clock time is
  governed by the sound's duration, not by input size

## Related Documentation

- [Wave Module](wave.md)
- [OS Module](os.md)
- [Platform Module](platform.md)
- [Time Module](time.md)
