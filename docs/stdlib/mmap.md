# mmap Module Complexity

The `mmap` module provides memory-mapped file support for efficient random access to file contents.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mmap.mmap(fileno, length, ...)` | Varies | Varies | Depends on OS and mapping size |
| `mmap.read(n)` | O(n) | O(n) | n = bytes read |
| `mmap.write(data)` | O(n) | O(1) | n = bytes written |
| `mmap.seek(pos[, whence])` | O(1) | O(1) | Pointer movement |
| `mmap.find(sub[, start[, end]])` | O(n) | O(1) | n = search range |
| `mmap.flush()` | Varies | O(1) | Depends on OS and dirty pages |
| `mmap.close()` | O(1) | O(1) | Unmap and close |

!!! warning "Platform-dependent behavior"
    `mmap` performance depends on the operating system, filesystem, and page cache behavior.
    The costs shown here describe typical asymptotic behavior, not wall-clock guarantees.

## Common Operations

### Creating a Mapping

```python
import mmap

with open('data.bin', 'rb') as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    print(mm.size())  # total size
    mm.close()
```

### Reading and Writing

```python
import mmap

with open('data.bin', 'r+b') as f:
    mm = mmap.mmap(f.fileno(), 0)

    # Read 16 bytes
    chunk = mm.read(16)

    # Write bytes in place
    mm.seek(0)
    mm.write(b'HELLO')

    mm.flush()
    mm.close()
```

### Searching

```python
import mmap

with open('data.bin', 'rb') as f:
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

    idx = mm.find(b'needle')  # O(n) search
    if idx != -1:
        print('Found at', idx)

    mm.close()
```

## Performance Notes

- Mapping large files avoids copying data into Python space for random access.
- Reads/writes still move data between kernel and user space when accessed.
- For sequential reads of large files, buffered I/O can be comparable or faster.

## Related Modules

- [io Module](io.md)
- [os Module](os.md)
- [pathlib Module](pathlib.md)
