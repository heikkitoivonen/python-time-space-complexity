# nt Module

The `nt` module exposes low-level Windows system calls. On Windows, `os` is
implemented on top of `nt`, exactly as it is implemented on top of
[`posix`](posix.md) on Unix. Import `os` instead: it is the portable spelling
and provides the same functions.

`nt` exists only on Windows. On other platforms importing it raises
`ModuleNotFoundError`.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nt.open(path, flags, mode)` | O(1) + syscall | O(1) | Path lookup cost depends on filesystem |
| `nt.read(fd, n)` | O(n) + syscall | O(n) | n = bytes read |
| `nt.write(fd, data)` | O(n) + syscall | O(1) | n = bytes written |
| `nt.close(fd)` | O(1) + syscall | O(1) | Release descriptor |
| `nt.lseek(fd, pos, how)` | O(1) + syscall | O(1) | Adjust file offset |
| `nt.stat(path)` | O(1) + syscall | O(1) | Path lookup cost depends on filesystem |
| `nt.fstat(fd)` | O(1) + syscall | O(1) | Descriptor-based stat |
| `nt.listdir(path)` | O(m) + syscall | O(m) | m = directory entries returned |
| `nt.mkdir(path)` | O(1) + syscall | O(1) | Path lookup cost depends on filesystem |
| `nt.rmdir(path)` | O(1) + syscall | O(1) | Directory must be empty |
| `nt.unlink(path)` | O(1) + syscall | O(1) | Remove a file |
| `nt.rename(src, dst)` | O(1) + syscall | O(1) | Same-volume rename is metadata-only |
| `nt.getcwd()` | O(1) + syscall | O(1) | Current directory |

Complexity here describes work in the interpreter and the number of system
calls. Actual wall-clock time is dominated by the filesystem and the kernel,
not by Python.

## Use os Instead

```python
import os

# Portable: resolves to nt on Windows, posix on Unix
fd = os.open("example.txt", os.O_CREAT | os.O_WRONLY | os.O_TRUNC)
try:
    os.write(fd, b"hello\n")   # O(n) in bytes
finally:
    os.close(fd)

entries = os.listdir(".")      # O(m) in directory entries
```

Referencing `nt` directly pins the code to Windows for no benefit, since `os`
forwards to the same implementation.

## Checking the Platform

```python
import os

# The name of the underlying implementation module
print(os.name)          # 'nt' on Windows, 'posix' elsewhere

# Prefer capability checks over platform checks where possible
if hasattr(os, "startfile"):   # O(1) - Windows-only function
    ...
```

!!! warning "Windows only"
    `nt` is not importable on Linux or macOS. Write against `os` and check
    `os.name` or feature availability rather than importing `nt`.

## Version Notes

- **All Python 3 versions**: `nt` backs `os` on Windows; the split between
  `nt` and `posix` is an implementation detail of `os`
- **All versions**: per-call complexity is unchanged; costs are dominated by
  the underlying Windows API

## Related Documentation

- [OS Module](os.md)
- [Posix Module](posix.md)
- [Ntpath Module](ntpath.md)
- [Pathlib Module](pathlib.md)
