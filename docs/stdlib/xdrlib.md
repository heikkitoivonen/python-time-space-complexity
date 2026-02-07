# xdrlib Module

⚠️ **REMOVED IN PYTHON 3.13**: The `xdrlib` module was deprecated in Python 3.11 and removed in Python 3.13.

The `xdrlib` module provides tools for XDR (External Data Representation) serialization, used for network communication.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Packer()` | O(1) | O(1) | Create packer (legacy) |
| Pack data | O(n) | O(n) | n = data size |
| Unpack data | O(n) | O(n) | n = buffer size |

## XDR Serialization

### Packing and Unpacking Data

```python
import xdrlib

# Create packer - O(1)
p = xdrlib.Packer()

# Pack data - O(n)
p.pack_int(42)
p.pack_string('hello')
p.pack_list([1, 2, 3], p.pack_int)

# Get packed data - O(1)
data = p.get_buffer()

# Unpacking - O(n)
u = xdrlib.Unpacker(data)
num = u.unpack_int()
text = u.unpack_string()
nums = u.unpack_list(u.unpack_int)
```

## Related Documentation

- [pickle Module](pickle.md)
- [struct Module](struct.md)
