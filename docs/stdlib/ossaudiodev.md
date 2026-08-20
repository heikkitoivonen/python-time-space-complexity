# ossaudiodev Module

⚠️ **REMOVED IN PYTHON 3.13**: The `ossaudiodev` module was deprecated in Python 3.11 and removed in Python 3.13.

The `ossaudiodev` module provides access to OSS (Open Sound System) audio
devices on Linux and FreeBSD: opening `/dev/dsp` for playback or recording, and
`/dev/mixer` for volume control.

Throughout, `n` is the number of bytes transferred.

## Complexity Reference

### Module

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `open(mode)` | O(1) + syscall | O(1) | Opens `/dev/dsp`; mode is `"r"`, `"w"`, or `"rw"` |
| `open(device, mode)` | O(1) + syscall | O(1) | Explicit device path |
| `openmixer(device=None)` | O(1) + syscall | O(1) | Opens `/dev/mixer` |

### Audio Device

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `read(size)` | O(n) + blocks | O(n) | Blocks until `size` bytes are captured |
| `write(data)` | O(n) + blocks | O(1) | Blocks until the buffer accepts the data |
| `writeall(data)` | O(n) + blocks | O(1) | Loops until everything is written |
| `setparameters(format, nchannels, samplerate)` | O(1) + syscall | O(1) | Configure the device |
| `setfmt(format)` | O(1) + syscall | O(1) | Sample format only |
| `channels(n)` | O(1) + syscall | O(1) | Channel count only |
| `speed(rate)` | O(1) + syscall | O(1) | Sample rate only |
| `bufsize()` | O(1) + syscall | O(1) | Buffer size in samples |
| `obufcount()` | O(1) + syscall | O(1) | Samples queued for playback |
| `obuffree()` | O(1) + syscall | O(1) | Space remaining in the buffer |
| `sync()` | O(1) + blocks | O(1) | Waits for the buffer to drain |
| `reset()` | O(1) + syscall | O(1) | Discards buffered audio |
| `close()` | O(1) + syscall | O(1) | Release the device |

### Mixer Device

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `controls()` | O(1) + syscall | O(1) | Bitmask of supported controls |
| `get(control)` | O(1) + syscall | O(1) | Current volume |
| `set(control, (left, right))` | O(1) + syscall | O(1) | Set volume |
| `stereocontrols()` | O(1) + syscall | O(1) | Which controls are stereo |

The data-transfer calls are linear in bytes; everything else is a constant-time
`ioctl`. The dominant cost in practice is blocking on the device, not CPU work.

## Playing Audio

```python
import ossaudiodev

# O(1) to open and configure
dsp = ossaudiodev.open("w")
try:
    dsp.setparameters(ossaudiodev.AFMT_S16_LE, 2, 44100)
    dsp.writeall(pcm_bytes)   # O(n), blocks until fully written
    dsp.sync()                # blocks until the buffer drains
finally:
    dsp.close()
```

## Recording Audio

```python
import ossaudiodev

dsp = ossaudiodev.open("r")
try:
    dsp.setparameters(ossaudiodev.AFMT_S16_LE, 1, 16000)
    # O(n) per chunk; blocks until the samples are captured
    chunks = [dsp.read(4096) for _ in range(100)]
finally:
    dsp.close()

audio = b"".join(chunks)   # O(total bytes)
```

## Avoiding Underruns

`write()` blocks when the device buffer is full. To keep a real-time loop
responsive, check the free space first:

```python
import ossaudiodev

dsp = ossaudiodev.open("w")
dsp.setparameters(ossaudiodev.AFMT_S16_LE, 2, 44100)

# O(1) - only write what fits, never block
free = dsp.obuffree()
if free >= len(chunk):
    dsp.write(chunk)
```

!!! warning "Removed in Python 3.13"
    There is no standard-library replacement. OSS itself is largely superseded
    by ALSA and PulseAudio on Linux; use a third-party binding for those.

!!! warning "Linux and FreeBSD only"
    The module was never available on Windows or macOS, and requires the OSS
    device nodes to be present.

## Version Notes

- **Python 3.11**: deprecated (PEP 594)
- **Python 3.13**: removed
- **Before 3.13**: available only on platforms with OSS device support
- **All versions**: transfer calls are linear in bytes; control calls are
  constant-time `ioctl`s

## Related Documentation

- [Wave Module](wave.md)
- [Audioop Module](audioop.md)
- [Sunau Module](sunau.md)
- [OS Module](os.md)
