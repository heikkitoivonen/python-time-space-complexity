# ossaudiodev Module Complexity

The `ossaudiodev` module drives OSS (Open Sound System) audio devices: an audio device such as
`/dev/dsp` for playback and recording, and a mixer device such as `/dev/mixer` for volume
control. Data moves straight between your `bytes` and the device's file descriptor, so the only
calls whose cost grows are `read()`, `write()` and `writeall()`; every other call is a fixed
number of system calls.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594, with no standard-library
    replacement. The page covers the module as it is on Python 3.10 to 3.12 on Linux and
    FreeBSD; the examples also need an OSS audio device and mixer.

`n` is the bytes passed to `write()` or `writeall()`, or the `size` asked of `read()`. The bounds
price the module's own work. Waiting for the device - to accept data, to capture it, or to play
out its buffer - takes real time proportional to the audio involved, and is outside every bound;
the Notes say where a call waits. Every function and method takes its arguments by position only.
`bufsize()`, `obufcount()` and `obuffree()` count samples per channel, not bytes: multiply by the
sample width times the channel count to get bytes.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ossaudiodev.open(mode)`, `ossaudiodev.open(device, mode)` | O(1) | O(1) | `mode` is `'r'`, `'w'` or `'rw'`; without `device`, the `AUDIODEV` environment variable, else `/dev/dsp`. A file that is not an audio device raises `OSError` here |
| `ossaudiodev.openmixer()`, `ossaudiodev.openmixer(device)` | O(1) | O(1) | Without `device`, the `MIXERDEV` environment variable, else `/dev/mixer`. A file that is not a mixer still opens, and fails at the first control call |

### oss_audio_device

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `oss_audio_device.read(size)` | O(n) | O(n) | Allocates `size` bytes before reading; in blocking mode, waits until all of them are captured |
| `oss_audio_device.write(data)` | O(n) | O(1) | Writes from the caller's buffer and returns the bytes written: all of them in blocking mode, possibly fewer after `nonblock()` |
| `oss_audio_device.writeall(data)` | O(n) | O(1) | Waits for the device and writes until all of `data` is gone; returns `None`. In blocking mode it has the same effect as `write()` |
| `oss_audio_device.setfmt(format)`, `oss_audio_device.channels(nchannels)`, `oss_audio_device.speed(samplerate)` | O(1) | O(1) | Each returns the value the device actually set, which may differ from the request |
| `oss_audio_device.setparameters(format, nchannels, samplerate[, strict])` | O(1) | O(1) | All three at once; returns `(format, nchannels, samplerate)` as set. With `strict` true, a value the device changed raises `OSSAudioError` |
| `oss_audio_device.getfmts()` | O(1) | O(1) | Bitmask of the supported `AFMT_*` formats |
| `oss_audio_device.bufsize()`, `oss_audio_device.obufcount()`, `oss_audio_device.obuffree()` | O(1) | O(1) | The whole output buffer, the part still to play, and the part free; in samples, not bytes |
| `oss_audio_device.nonblock()` | O(1) | O(1) | There is no way back to blocking mode |
| `oss_audio_device.sync()` | O(1) | O(1) | Waits until the buffer has played |
| `oss_audio_device.reset()` | O(1) | O(1) | Stops at once, discarding what is buffered |
| `oss_audio_device.post()` | O(1) | O(1) | Tells the driver a pause in output is likely |
| `oss_audio_device.fileno()` | O(1) | O(1) | |
| `oss_audio_device.close()` | O(1) | O(1) | Waits for buffered playback to finish, as `sync()` does. A second call does nothing; a `with` block calls it on exit. `fileno()` and every device call then raise `ValueError` |
| `oss_audio_device.closed`, `oss_audio_device.name`, `oss_audio_device.mode` | O(1) | O(1) | Read-only |

### oss_mixer_device

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `oss_mixer_device.controls()`, `oss_mixer_device.stereocontrols()`, `oss_mixer_device.reccontrols()` | O(1) | O(1) | Bitmasks of the available, the stereo and the recordable controls; bit `c` is the control numbered `c` |
| `oss_mixer_device.get(control)` | O(1) | O(1) | Returns `(left, right)`, each 0 to 100. A negative control number, or one above `SOUND_MIXER_NRDEVICES`, raises `OSSAudioError` |
| `oss_mixer_device.set(control, (left, right))` | O(1) | O(1) | Returns the volume as set. A control number `get()` rejects, or a volume outside 0 to 100, raises `OSSAudioError` |
| `oss_mixer_device.get_recsrc()`, `oss_mixer_device.set_recsrc(bitmask)` | O(1) | O(1) | Bitmask of the controls recording now; `set_recsrc()` returns the new one |
| `oss_mixer_device.fileno()` | O(1) | O(1) | |
| `oss_mixer_device.close()` | O(1) | O(1) | A second call does nothing; a `with` block calls it on exit. `fileno()` and every device call then raise `ValueError` |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ossaudiodev.OSSAudioError`, `ossaudiodev.error` | O(1) | O(1) | One class under two names, raised for a bad `open()` mode, a mixer control number or volume out of range, and a `strict` mismatch in `setparameters()`; failed system calls raise `OSError` |
| `ossaudiodev.control_labels`, `ossaudiodev.control_names` | O(1) | O(1) | Lists indexed by control number, one entry per control |
| `ossaudiodev.AFMT_*`, `ossaudiodev.SOUND_MIXER_*`, `ossaudiodev.SNDCTL_*` | O(1) | O(1) | Integer constants from the system's `soundcard.h`: sample formats, mixer control numbers, and raw `ioctl` requests |

## Playing Audio

Configure the device, then write. `writeall()` costs the bytes it is given, plus however long the
device takes to accept them; `sync()` then waits until the buffer has played.

```python
import ossaudiodev

with ossaudiodev.open("w") as dsp:  # O(1)
    # strict: raise rather than accept other values from the device
    fmt, channels, rate = dsp.setparameters(ossaudiodev.AFMT_S16_LE, 2, 44100, True)  # O(1)
    frame = 2 * channels  # bytes per sample: 16 bits for each channel
    pcm = bytes(frame * rate // 10)  # a tenth of a second of silence

    dsp.writeall(pcm)  # O(n), waits until all of it is written
    dsp.sync()  # O(1), waits until it has played

assert dsp.closed
```

## Recording Audio

`read(size)` allocates `size` bytes before it asks the device for them, so the chunk size, not
the recording, sets the memory one call needs. Keeping every chunk is what makes memory grow with
the whole recording.

```python
import ossaudiodev

with ossaudiodev.open("r") as dsp:
    dsp.setparameters(ossaudiodev.AFMT_S16_LE, 1, 16000)
    chunks = [dsp.read(4096) for _ in range(10)]  # O(4096) each, waits for the samples

audio = b"".join(chunks)  # linear in the bytes recorded
assert len(audio) == 10 * 4096
```

## Writing Without Waiting

A write of no more than `obuffree()` worth of samples fits in the buffer, so it does not wait.
`obuffree()` counts samples, not bytes, so scale it before comparing it with a length.

```python
import ossaudiodev

with ossaudiodev.open("w") as dsp:
    fmt, channels, rate = dsp.setparameters(ossaudiodev.AFMT_S16_LE, 2, 44100, True)
    frame = 2 * channels  # bytes per sample: 16 bits for each channel
    chunk = bytes(frame * 1024)  # 1,024 samples of silence

    room = dsp.obuffree() * frame  # O(1) - samples times bytes per sample
    if room >= len(chunk):
        assert dsp.write(chunk) == len(chunk)  # O(n), fits in the buffer
```

## Mixer Volumes

`get()` and `set()` check the control number, and `set()` the volume, before they ask the
device, and raise `OSSAudioError` for one out of range.

```python
import ossaudiodev

with ossaudiodev.openmixer() as mixer:  # O(1)
    pcm = ossaudiodev.SOUND_MIXER_PCM
    assert ossaudiodev.control_names[pcm] == 'pcm'

    if mixer.controls() & (1 << pcm):  # O(1) - one bit per control
        left, right = mixer.set(pcm, (80, 80))  # O(1)
        assert 0 <= left <= 100 and 0 <= right <= 100

    try:
        mixer.set(pcm, (101, 0))
    except ossaudiodev.OSSAudioError as error:
        assert 'between 0 and 100' in str(error)
    else:
        raise AssertionError('a volume over 100 was accepted')
```

## Performance Best Practices

✅ **Do**:

- Read in fixed-size chunks; each `read(size)` holds `size` bytes, whatever the recording's length
- Scale `obuffree()`, `obufcount()` and `bufsize()` by the bytes per sample before comparing them
  with a byte count
- Check what `setparameters()` returns, or pass `True` as its fourth argument, `strict`; the device
  may choose other values

❌ **Avoid**:

- `nonblock()` unless you mean it - it cannot be undone, and `write()` may then write less than
  it was given
- Calling `sync()` where latency matters - it waits for the whole buffer to play
- Assuming `openmixer()` succeeding means a mixer is there - the first control call is the check

## Version Notes

- **Python 3.11+**: `import ossaudiodev` emits a `DeprecationWarning`
- **Python 3.13+**: The module is removed; `import ossaudiodev` raises `ModuleNotFoundError`

## Related Modules

- **[wave](wave.md)** - reads and writes WAV files, the usual source and sink of the PCM bytes
  played and recorded here
- **[os](os.md)** - `os.read()` and `os.write()` on a file descriptor, which is what `read()` and
  `write()` amount to
