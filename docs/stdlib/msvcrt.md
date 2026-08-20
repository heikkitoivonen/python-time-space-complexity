# msvcrt Module

The `msvcrt` module exposes a handful of routines from the Microsoft Visual C++
runtime: unbuffered console I/O, file locking, and conversion between C file
descriptors and Win32 handles.

It is Windows-only. On other platforms importing it raises
`ModuleNotFoundError`.

## Complexity Reference

### Console I/O

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getch()` | O(1) + blocks | O(1) | Reads one keypress, no echo; blocks until a key is pressed |
| `getwch()` | O(1) + blocks | O(1) | Wide-character variant |
| `getche()` | O(1) + blocks | O(1) | Like `getch()` but echoes |
| `getwche()` | O(1) + blocks | O(1) | Wide-character variant |
| `kbhit()` | O(1) | O(1) | Non-blocking check for a pending keypress |
| `putch(c)` | O(1) + syscall | O(1) | Write one byte to the console |
| `putwch(c)` | O(1) + syscall | O(1) | Wide-character variant |
| `ungetch(c)` | O(1) | O(1) | Push one character back; one pending char only |
| `ungetwch(c)` | O(1) | O(1) | Wide-character variant |

### Files and Descriptors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `locking(fd, mode, nbytes)` | O(1) + syscall | O(1) | Lock a byte range; may block or retry |
| `setmode(fd, flags)` | O(1) + syscall | O(1) | Switch between text and binary mode |
| `open_osfhandle(handle, flags)` | O(1) + syscall | O(1) | Win32 handle to C descriptor |
| `get_osfhandle(fd)` | O(1) + syscall | O(1) | C descriptor to Win32 handle |
| `heapmin()` | O(n) | O(1) | Releases unused heap blocks to the OS |

`getch()` and friends are O(1) in work but block indefinitely, so treat them as
I/O waits rather than computation.

## Reading Keypresses Without Enter

```python
import msvcrt

# Poll without blocking - O(1) per check
while True:
    if msvcrt.kbhit():
        key = msvcrt.getch()      # O(1), returns immediately after kbhit()
        if key == b"q":
            break
        print(key)
```

## Locking a File Region

```python
import msvcrt
import os

fd = os.open("data.bin", os.O_RDWR)
try:
    # Lock 1024 bytes from the current position - O(1) + syscall
    msvcrt.locking(fd, msvcrt.LK_LOCK, 1024)
    try:
        os.write(fd, b"exclusive")
    finally:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1024)
finally:
    os.close(fd)
```

!!! warning "Windows only"
    For portable console input use `input()`, or a cross-platform library. For
    portable file locking, see `fcntl.flock()` on Unix and select the
    implementation at runtime.

!!! tip "kbhit() before getch()"
    `getch()` blocks. Guarding it with `kbhit()` turns an indefinite wait into
    an O(1) poll, which is what you want inside an event loop.

## Version Notes

- **All Python 3 versions**: available on Windows builds only
- **All versions**: per-call complexity is unchanged; costs are dominated by
  the underlying C runtime and console

## Related Documentation

- [OS Module](os.md)
- [NT Module](nt.md)
- [Fcntl Module](fcntl.md)
- [Curses Module](curses.md)
