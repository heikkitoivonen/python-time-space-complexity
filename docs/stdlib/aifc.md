# aifc Module

⚠️ **REMOVED IN PYTHON 3.13**: The `aifc` module was deprecated in Python 3.11 and removed in Python 3.13.

The `aifc` module provides support for reading and writing AIFF and AIFF-C audio files.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `open()` | O(1) | O(1) | Open file |
| Read/write frames | O(n) | O(n) | n = frame count |

## Working with AIFF Files

### Reading Audio File

```python
import aifc

# Open file - O(1)
with aifc.open('sound.aiff', 'rb') as f:
    # Get properties
    channels = f.getnchannels()
    width = f.getsampwidth()
    framerate = f.getframerate()
    frames = f.getnframes()
    
    # Read audio - O(n)
    audio_data = f.readframes(frames)
```

### Writing Audio File

```python
import aifc

# Create file - O(1)
with aifc.open('output.aiff', 'wb') as f:
    # Set properties
    f.setnchannels(2)        # Stereo
    f.setsampwidth(2)        # 16-bit
    f.setframerate(44100)    # CD quality
    
    # Write audio - O(n)
    f.writeframes(audio_data)
```

## Related Documentation

- [wave Module](wave.md)
- [sunau Module](sunau.md)
