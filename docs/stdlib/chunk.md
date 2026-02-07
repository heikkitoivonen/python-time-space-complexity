# chunk Module

⚠️ **REMOVED IN PYTHON 3.13**: The `chunk` module was deprecated in Python 3.11 and removed in Python 3.13.

The `chunk` module provides support for reading IFF (Interchange File Format) chunks used by audio files (AIFF, WAV).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Read chunk | O(1) | O(1) | Header read |
| Parse chunks | O(n) | O(n) | n = chunk count |

## Reading IFF Chunks

### Parsing Chunk Structure

```python
import chunk

# Open chunk - O(1)
with open('audio.aiff', 'rb') as f:
    chk = chunk.Chunk(f)
    
    # Read chunk header - O(1)
    chunktype = chk.getname()
    chunksize = chk.getsize()
    
    # Process chunk data - O(n)
    data = chk.read()
    
    # Skip to next - O(1)
    chk.skip()
```

## Related Documentation

- [wave Module](wave.md)
- [aifc Module](aifc.md)
