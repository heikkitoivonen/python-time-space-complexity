# uu Module

⚠️ **REMOVED IN PYTHON 3.13**: The `uu` module was deprecated in Python 3.11 and removed in Python 3.13.

The `uu` module provides uuencoding/uudecoding for transmitting binary data over text channels (legacy, rarely used).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `encode()` | O(n) | O(n) | n = input bytes; deprecated, use base64 |
| `decode()` | O(n) | O(n) | n = encoded bytes; deprecated, use base64 |

## Encoding and Decoding

### Uuencoding Files

```python
import uu
import io

# Encode - O(n)
with open('binary.dat', 'rb') as f:
    with open('binary.uu', 'w') as out:
        uu.encode(f, out)

# Decode - O(n)
with open('binary.uu', 'r') as f:
    with open('binary.dat', 'wb') as out:
        uu.decode(f, out)
```

## Related Documentation

- [base64 Module](base64.md)
- [binascii Module](binascii.md)
