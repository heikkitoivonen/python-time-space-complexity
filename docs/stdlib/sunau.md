# sunau Module

⚠️ **REMOVED IN PYTHON 3.13**: The `sunau` module was deprecated in Python 3.11 and removed in Python 3.13.

The `sunau` module reads and writes Sun AU audio files, a simple uncompressed audio format.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `open()` | O(1) | O(1) | Open file |
| Read/write frames | O(n) | O(n) | n = frame count |

## Working with AU Files

### Reading Audio

```python
import sunau

# Open - O(1)
with sunau.open('sound.au', 'rb') as f:
    channels = f.getnchannels()
    framerate = f.getframerate()
    frames = f.getnframes()
    
    # Read - O(n)
    audio = f.readframes(frames)
```

### Writing Audio

```python
import sunau

# Create - O(1)
with sunau.open('output.au', 'wb') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(8000)
    
    # Write - O(n)
    f.writeframes(audio_data)
```

## Related Documentation

- [wave Module](wave.md)
- [aifc Module](aifc.md)
