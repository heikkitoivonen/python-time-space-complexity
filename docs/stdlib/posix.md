# posix Module

The `posix` module exposes low-level POSIX APIs. On POSIX platforms, `os` is
implemented on top of `posix`, and most users should prefer `os` for portability.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `posix.open(path, flags, mode=0o777)` | O(1) + syscall | O(1) | Path lookup cost depends on filesystem |
| `posix.read(fd, n)` | O(n) + syscall | O(n) | n = bytes read |
| `posix.write(fd, data)` | O(n) + syscall | O(1) | n = bytes written |
| `posix.close(fd)` | O(1) + syscall | O(1) | Release descriptor |
| `posix.lseek(fd, pos, how)` | O(1) + syscall | O(1) | Adjust file offset |
| `posix.stat(path)` | O(1) + syscall | O(1) | Path lookup cost depends on filesystem |
| `posix.fstat(fd)` | O(1) + syscall | O(1) | Descriptor-based stat |
| `posix.listdir(path)` | O(m) + syscall | O(m) | m = directory entries returned |
| `posix.mkdir(path, mode=0o777)` | O(1) + syscall | O(1) | Path lookup cost depends on filesystem |
| `posix.rmdir(path)` | O(1) + syscall | O(1) | Directory must be empty |
| `posix.unlink(path)` | O(1) + syscall | O(1) | Remove a name (file or symlink) |
| `posix.chmod(path, mode)` | O(1) + syscall | O(1) | Change permissions |
| `posix.chown(path, uid, gid)` | O(1) + syscall | O(1) | Change owner/group |

## Low-Level File I/O

```python
import posix

fd = posix.open("example.txt", posix.O_CREAT | posix.O_WRONLY | posix.O_TRUNC, 0o644)
try:
    posix.write(fd, b"hello\n")  # O(n) in bytes
finally:
    posix.close(fd)

fd = posix.open("example.txt", posix.O_RDONLY)
try:
    data = posix.read(fd, 1024)  # O(n) in bytes
    print(data.decode("utf-8"))
finally:
    posix.close(fd)
```

## File Descriptors and Stat

```python
import posix

fd = posix.open("example.txt", posix.O_RDONLY)
try:
    info = posix.fstat(fd)  # O(1)
    print(info.st_size)
finally:
    posix.close(fd)
```

## Directory Listing

```python
import posix

entries = posix.listdir(".")  # O(m) where m = directory entries
for name in entries:
    print(name)
```

## Notes

- Many functions raise `OSError` for permission or filesystem errors.
- `posix` is not available on Windows; use `os` for portability.

## Related Modules

- [os Module](os.md) - Portable OS interface (recommended)
- [posixpath Module](posixpath.md) - POSIX path operations
- [pathlib Module](pathlib.md) - Object-oriented paths
