# msvcrt Module Complexity

The `msvcrt` module wraps a few routines of the Microsoft C runtime: keyboard input and output on
the console, byte-range file locking, the mapping between C file descriptors and Win32 handles,
and the process's error mode. Each function is one C runtime call. Nothing is buffered or cached
in Python.

It is Windows-only. On other platforms `import msvcrt` raises `ModuleNotFoundError`.

A console or file-system call counts as O(1) here, the way a syscall does on the [os](os.md)
page. `n` is the console input events waiting in total: key releases, mouse, focus and window
events queue in the console beside the key presses. `e` is the part of them ahead of the next key
press, so `e` is at most `n`. `h` is the blocks in the C runtime heap.

## Complexity Reference

### Console input and output

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `msvcrt.kbhit()` | O(n) | O(n) | Never waits; copies every waiting event to look for a key press, including those behind a key press at the front. Also nonzero while `ungetch()` holds a byte |
| `msvcrt.getch()` | O(e) | O(1) | One key press as `bytes`, not echoed; waits if none is waiting, discards the events ahead of it one at a time, and leaves those behind it. A function or arrow key takes two calls: `b'\x00'` or `b'\xe0'`, then the key code |
| `msvcrt.getwch()` | O(e) | O(1) | `getch()` returning `str` |
| `msvcrt.getche()`, `msvcrt.getwche()` | O(e) | O(1) | `getch()` and `getwch()` that echo the key to the console |
| `msvcrt.putch(char)`, `msvcrt.putwch(unicode_char)` | O(1) | O(1) | One character straight to the console, bypassing `sys.stdout` and any redirection |
| `msvcrt.ungetch(char)` | O(1) | O(1) | Pushes a byte back; the next `getch()` or `getche()` returns it without waiting. The buffer is small, returns bytes in the order pushed, and raises `OSError` when full |
| `msvcrt.ungetwch(unicode_char)` | O(1) | O(1) | Holds one character for `getwch()` and `getwche()`; a second raises `OSError`, and `kbhit()` does not see it |

### Files and descriptors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `msvcrt.locking(fd, mode, nbytes)` | O(1) | O(1) | Locks or unlocks `nbytes` from the current position, which it does not move; `LK_LOCK` and `LK_RLCK` retry for about ten seconds before raising `OSError` |
| `msvcrt.setmode(fd, flags)` | O(1) | O(1) | `os.O_TEXT` or `os.O_BINARY`; returns the previous mode |
| `msvcrt.get_osfhandle(fd)` | O(1) | O(1) | The Win32 handle behind a descriptor; `OSError` for an unknown one |
| `msvcrt.open_osfhandle(handle, flags)` | O(1) | O(1) | A new descriptor that owns the handle: closing it closes the handle |
| `msvcrt.heapmin()` | O(h) | O(1) | Returns the C runtime heap's unused memory to Windows. Depending on the heap Windows gives the process, it may walk every block |

### Error mode

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `msvcrt.GetErrorMode()` | O(1) | O(1) | The process's `SEM_*` flags |
| `msvcrt.SetErrorMode(mode)` | O(1) | O(1) | Replaces the flags for the whole process and returns the previous ones |

### Debug builds

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `msvcrt.CrtSetReportFile(type, file)`, `msvcrt.CrtSetReportMode(type, mode)`, `msvcrt.set_error_mode(mode)` | O(1) | O(1) | Only in a debug build of Python |
| `msvcrt.CRT_WARN`, `msvcrt.CRT_ERROR`, `msvcrt.CRT_ASSERT`, `msvcrt.CRTDBG_MODE_DEBUG`, `msvcrt.CRTDBG_MODE_FILE`, `msvcrt.CRTDBG_MODE_WNDW`, `msvcrt.CRTDBG_REPORT_MODE`, `msvcrt.CRTDBG_FILE_STDERR`, `msvcrt.CRTDBG_FILE_STDOUT`, `msvcrt.CRTDBG_REPORT_FILE` | O(1) | O(1) | Only in a debug build of Python |
| `msvcrt.OUT_TO_DEFAULT`, `msvcrt.OUT_TO_STDERR`, `msvcrt.OUT_TO_MSGBOX`, `msvcrt.REPORT_ERRMODE` | O(1) | O(1) | Only in a debug build of Python 3.13+ |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `msvcrt.LK_LOCK`, `msvcrt.LK_RLCK`, `msvcrt.LK_NBLCK`, `msvcrt.LK_NBRLCK`, `msvcrt.LK_UNLCK` | O(1) | O(1) | `locking()` modes. The `R` forms are not shared read locks: they exclude everyone else too |
| `msvcrt.SEM_FAILCRITICALERRORS`, `msvcrt.SEM_NOALIGNMENTFAULTEXCEPT`, `msvcrt.SEM_NOGPFAULTERRORBOX`, `msvcrt.SEM_NOOPENFILEERRORBOX` | O(1) | O(1) | Flags for `SetErrorMode()` |
| `msvcrt.CRT_ASSEMBLY_VERSION` | O(1) | O(1) | The C runtime version Python was built with, as a string |

## Reading Keys

### Polling Without Blocking

`getch()` waits for a key press. Asking `kbhit()` first turns the wait into a poll, and a read
after a nonzero `kbhit()` returns at once. `kbhit()` copies every event the console is holding,
so a loop that polls while input piles up unread pays for the pile on every call.

```python
import msvcrt

msvcrt.ungetch(b"q")  # O(1) - stands in for a key press

keys = []
while True:
    if msvcrt.kbhit():  # O(n) - never waits
        key = msvcrt.getch()  # returns at once: a key is waiting
        keys.append(key)
        if key == b"q":
            break
    # ...other work between polls

assert keys == [b"q"]
```

### Pushing Keys Back

`ungetch()` and `ungetwch()` fill two separate buffers, and each family of readers reads only its
own: a byte pushed back is invisible to `getwch()`, which waits for a key instead. `kbhit()` sees
a pushed-back byte but not a pushed-back character.

```python
import msvcrt

msvcrt.ungetch(b"y")  # O(1)
msvcrt.ungetwch("é")  # O(1) - a separate one-character buffer

assert msvcrt.kbhit()  # the byte
assert msvcrt.getwch() == "é"  # returns without waiting
assert msvcrt.getch() == b"y"

msvcrt.ungetwch("x")
try:
    msvcrt.ungetwch("z")
except OSError:
    pass
else:
    raise AssertionError("a second character was pushed back")
assert not msvcrt.kbhit()  # does not see "x"
assert msvcrt.getwch() == "x"
```

## Locking a File Region

`locking()` locks `nbytes` starting at the current position, and the region may run past the end
of the file. Windows locks are exclusive and enforced: another descriptor cannot lock the region
or write into it. `LK_NBLCK` fails at once with `PermissionError`, while `LK_LOCK` retries once a
second and raises `OSError` after about ten seconds, so a program that must not stall should try
`LK_NBLCK` and retry on its own schedule.

```python
import msvcrt
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "data.bin")
    first = os.open(path, os.O_RDWR | os.O_CREAT | os.O_BINARY)
    second = os.open(path, os.O_RDWR | os.O_BINARY)

    msvcrt.locking(first, msvcrt.LK_NBLCK, 1024)  # O(1) - bytes 0 to 1023
    assert os.lseek(first, 0, os.SEEK_CUR) == 0  # the position did not move

    try:
        msvcrt.locking(second, msvcrt.LK_NBLCK, 1024)  # O(1) - fails at once
    except PermissionError:
        pass
    else:
        raise AssertionError("the region was locked twice")

    msvcrt.locking(first, msvcrt.LK_UNLCK, 1024)  # the same region, from the same position
    msvcrt.locking(second, msvcrt.LK_NBLCK, 1024)
    os.close(second)  # closing a descriptor releases its locks
    os.close(first)
```

Two locked regions next to each other stay two regions: unlock each as it was locked, since one
unlock spanning both raises `PermissionError`.

## Descriptors and Handles

A C descriptor and a Win32 handle name the same open file at two levels. `get_osfhandle()` looks
the handle up, and `setmode()` switches the descriptor between text and binary translation.

```python
import msvcrt
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "notes.txt")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_BINARY)

    assert msvcrt.get_osfhandle(fd) > 0  # O(1)
    assert msvcrt.setmode(fd, os.O_TEXT) == os.O_BINARY  # O(1) - returns the old mode
    os.write(fd, b"a\nb")  # translated on the way out
    os.close(fd)

    with open(path, "rb") as f:
        assert f.read() == b"a\r\nb"
```

## Common Patterns

### Waiting for a Key With a Deadline

```python
import msvcrt
import time

def key_within(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if msvcrt.kbhit():  # O(n)
            return msvcrt.getch()  # a key is waiting, so no wait here
        time.sleep(0.05)
    return None

assert key_within(0.2) is None  # nothing pressed
msvcrt.ungetch(b"y")  # stands in for a key press
assert key_within(0.2) == b"y"
```

## Performance Best Practices

✅ **Do**:

- Guard `getch()` with `kbhit()` in a loop that must not wait
- Lock with `LK_NBLCK` and retry on your own schedule when a ten-second stall is too long
- Unlock exactly the regions you locked, or close the descriptor to release them all
- Read keys as they arrive: `kbhit()` costs every event waiting, and `getch()` the events ahead of
  the key

❌ **Avoid**:

- `LK_RLCK` expecting a shared read lock: it excludes other readers as well
- Mixing `ungetch()` with `getwch()`, or `ungetwch()` with `getch()` and `kbhit()`: each reads
  only its own buffer
- Calling `heapmin()` routinely: it can walk the whole C runtime heap each time
- `SetErrorMode()` as a local setting: it changes the whole process

## Version Notes

- **All Python 3**: Windows only. The bounds above hold on every supported version

## Related Modules

- **[os](os.md)** - `os.open()`, `os.O_BINARY` and `os.O_TEXT`, the descriptors these functions take
- **[getpass](getpass.md)** - reads a password on Windows with `getwch()`
- **[fcntl](fcntl.md)** - `lockf()` and `flock()`, file locking on Unix
- **[winreg](winreg.md)** - another Windows-only module
