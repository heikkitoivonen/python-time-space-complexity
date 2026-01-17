# pickletools Module

The `pickletools` module provides tools for analyzing pickle files, showing the disassembled contents of Python pickle data.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dis()` | O(n) | O(n) | n = pickle size; sequential disassembly |
| Parse pickle | O(n) | O(n) | Sequential parse through opcodes |

## Disassembling Pickle Data

### Analyzing Pickle Files

```python
import pickle
import pickletools
import io

# Create pickled data - O(n)
data = {'name': 'Alice', 'age': 30}
pickled = pickle.dumps(data)

# Disassemble - O(n)
pickletools.dis(io.BytesIO(pickled))

# Output shows:
#     0: \x80 PROTO      3
#     2: } EMPTY_DICT
#     3: ( MARK
#     4: X    SHORT_BINUNICODE 'name'
#    ...
```

## Related Documentation

- [pickle Module](pickle.md)
- [marshal Module](marshal.md)
