# sndhdr Module

⚠️ **REMOVED IN PYTHON 3.13**: The `sndhdr` module was deprecated in Python 3.11 and removed in Python 3.13.

The `sndhdr` module identified the format of sound files and returned information about sound file headers.

## Removal Notice

```python
# ❌ DON'T: Use sndhdr (deprecated, removed in 3.13)
import sndhdr
info = sndhdr.what('sound.au')

# ✅ DO: Use modern alternatives
# - scipy.io.wavfile
# - soundfile library
# - audioread library
# - wave module (for WAV files)
```

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `what()` | O(1) | O(1) | Read file header |
| Header parsing | O(1) | O(1) | Small fixed header |

## File Format Detection

### Identify Sound Format

```python
# ❌ DEPRECATED: Use modern libraries instead
import sndhdr

# Identify format - O(1)
try:
    params = sndhdr.what('audio.au')
    if params:
        (channels, sample_width, sample_rate, nframes, compression_type, compression_name) = params
        print(f"Channels: {channels}")
        print(f"Sample rate: {sample_rate} Hz")
        print(f"Frames: {nframes}")
except Exception as e:
    print(f"Error: {e}")
```

## Modern Alternatives

### Using wave Module (Built-in)

```python
# ✅ RECOMMENDED: Use wave for WAV files
import wave

def inspect_wav(filepath):
    """
    Inspect WAV file header.
    
    Time: O(1)
    Space: O(1)
    """
    with wave.open(filepath, 'rb') as f:
        # Get parameters - O(1)
        (channels, sample_width, sample_rate, nframes, compression, compression_name) = f.getparams()
        
        return {
            'channels': channels,
            'sample_width': sample_width,
            'sample_rate': sample_rate,
            'frames': nframes,
            'duration': nframes / sample_rate
        }

info = inspect_wav('audio.wav')
print(f"Duration: {info['duration']:.2f} seconds")
print(f"Sample rate: {info['sample_rate']} Hz")
```

### Using scipy (Third-party)

```python
# ✅ RECOMMENDED: scipy for detailed analysis
from scipy.io import wavfile
import numpy as np

def inspect_audio_scipy(filepath):
    """
    Inspect audio file with scipy.
    
    Time: O(n) where n = file size
    Space: O(n)
    """
    sample_rate, data = wavfile.read(filepath)
    
    if len(data.shape) == 1:
        channels = 1
    else:
        channels = data.shape[1]
    
    return {
        'sample_rate': sample_rate,
        'channels': channels,
        'frames': len(data),
        'duration': len(data) / sample_rate,
        'data': data
    }

info = inspect_audio_scipy('audio.wav')
print(f"Sample rate: {info['sample_rate']} Hz")
print(f"Channels: {info['channels']}")
```

### Using soundfile (Third-party)

```python
# ✅ RECOMMENDED: soundfile (modern, reliable)
import soundfile as sf

def inspect_audio_soundfile(filepath):
    """
    Inspect audio file with soundfile.
    
    Time: O(1)
    Space: O(1) for metadata only
    """
    info = sf.info(filepath)
    
    return {
        'sample_rate': info.samplerate,
        'channels': info.channels,
        'frames': info.frames,
        'duration': info.duration,
        'format': info.format,
        'subtype': info.subtype
    }

# Install: pip install soundfile
info = inspect_audio_soundfile('audio.wav')
print(f"Format: {info['format']} {info['subtype']}")
print(f"Duration: {info['duration']:.2f} seconds")
```

## Complete Example - File Inspector

### Before (sndhdr - Deprecated)

```python
import sndhdr

# ❌ DEPRECATED
def inspect_sound(filepath):
    params = sndhdr.what(filepath)
    if params:
        channels, sample_width, sample_rate, nframes, compression, compression_name = params
        return {
            'channels': channels,
            'sample_rate': sample_rate,
            'frames': nframes
        }
    return None
```

### After (Modern)

```python
import wave
import soundfile as sf
from pathlib import Path

def inspect_sound(filepath):
    """
    Modern sound file inspector.
    
    Time: O(1)
    Space: O(1)
    """
    filepath = Path(filepath)
    suffix = filepath.suffix.lower()
    
    if suffix == '.wav':
        with wave.open(filepath, 'rb') as f:
            params = f.getparams()
            return {
                'format': 'WAV',
                'channels': params.nchannels,
                'sample_width': params.sampwidth,
                'sample_rate': params.framerate,
                'frames': params.nframes
            }
    
    # Fallback for other audio formats (including .au, if supported)
    info = sf.info(filepath)
    return {
        'format': info.format,
        'channels': info.channels,
        'sample_width': None,
        'sample_rate': info.samplerate,
        'frames': info.frames,
    }

# Usage
info = inspect_sound('audio.wav')
print(f"Format: {info['format']}")
print(f"Sample rate: {info['sample_rate']} Hz")
```

## Related Modules

- [wave Module](wave.md) - WAV file handling
- [aifc Module](aifc.md) - AIFF audio handling
- [struct Module](struct.md) - Binary data parsing
