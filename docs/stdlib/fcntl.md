# fcntl Module

The `fcntl` module wraps three Unix system calls, `fcntl()`, `ioctl()` and `flock()`, plus `lockf()`, which is `fcntl()`'s record locking behind a simpler signature. Each is one call into the kernel, and the bounds below count that call as constant: what the kernel does with a lock table or a driver's `ioctl` handler is not priced. The only work Python adds is copying a bytes-like argument through a fixed 1024-byte buffer: in before the call, and out afterwards into a new `bytes` object of the same length or, for a buffer `ioctl()` mutates, back into that buffer. The one exception is a writable buffer longer than that, which a mutating `ioctl()` hands to the kernel as it is.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fcntl.fcntl(fd, cmd, arg=0)` with an integer `arg` | O(1) | O(1) | One system call; returns its integer result |
| `fcntl.fcntl(fd, cmd, arg)` with a `bytes` or str `arg` | O(n) | O(n) | n = length of `arg` in bytes, UTF-8 encoded for a str; at most 1024 or `ValueError`. Copied in, and the result is a new `bytes` of the same length. Other bytes-like objects such as `bytearray` are accepted from Python 3.14 |
| `fcntl.ioctl(fd, request, arg=0)` with an integer `arg` | O(1) | O(1) | One system call; returns its integer result |
| `fcntl.ioctl(fd, request, arg)` with a read-only bytes-like or str `arg`, or `mutate_flag=False` | O(n) | O(n) | Same copy and 1024-byte cap as `fcntl()` |
| `fcntl.ioctl(fd, request, buffer, mutate_flag=True)` with a writable buffer | O(n) | O(1) | n = buffer length. Up to 1024 bytes it is copied through the fixed buffer and back; a longer one is handed to the kernel uncopied, so the cap does not apply. The caller's buffer is changed in place and the integer result returned |
| `fcntl.flock(fd, operation)` | O(1) | O(1) | Locks the open file description, so a second `open()` of the file contends even in the same process; a system without `flock(2)` gets `lockf()`'s process-owned lock instead. Waits for a conflicting lock unless `LOCK_NB` is set, which raises `BlockingIOError` instead; the waiting is not work |
| `fcntl.lockf(fd, cmd, len=0, start=0, whence=0)` | O(1) | O(1) | A byte-range lock through `fcntl()`, owned by the process: another descriptor in the same process never contends, and closing any descriptor of the file releases it. An exclusive lock needs the file open for writing |
| `fcntl.LOCK_SH`, `fcntl.LOCK_EX`, `fcntl.LOCK_NB`, `fcntl.LOCK_UN` | O(1) | O(1) | Operation flags for `flock()` and `lockf()` |
| `fcntl.LOCK_MAND`, `fcntl.LOCK_READ`, `fcntl.LOCK_WRITE`, `fcntl.LOCK_RW` | O(1) | O(1) | Linux mandatory-lock flags for `flock()`; platform-dependent |
| `fcntl.F_DUPFD`, `fcntl.F_DUPFD_CLOEXEC`, `fcntl.F_GETFD`, `fcntl.F_SETFD`, `fcntl.F_GETFL`, `fcntl.F_SETFL`, `fcntl.FD_CLOEXEC`, `fcntl.FASYNC` | O(1) | O(1) | Descriptor commands and flag bits for `fcntl()` |
| `fcntl.F_GETLK`, `fcntl.F_SETLK`, `fcntl.F_SETLKW`, `fcntl.F_GETLK64`, `fcntl.F_SETLK64`, `fcntl.F_SETLKW64`, `fcntl.F_OFD_GETLK`, `fcntl.F_OFD_SETLK`, `fcntl.F_OFD_SETLKW`, `fcntl.F_RDLCK`, `fcntl.F_WRLCK`, `fcntl.F_UNLCK`, `fcntl.F_SHLCK`, `fcntl.F_EXLCK` | O(1) | O(1) | Record-lock commands and lock types for `fcntl()`; which exist is platform-dependent |
| `fcntl.F_GETOWN`, `fcntl.F_SETOWN`, `fcntl.F_GETSIG`, `fcntl.F_SETSIG`, `fcntl.F_NOTIFY`, `fcntl.DN_ACCESS`, `fcntl.DN_MODIFY`, `fcntl.DN_CREATE`, `fcntl.DN_DELETE`, `fcntl.DN_RENAME`, `fcntl.DN_ATTRIB`, `fcntl.DN_MULTISHOT`, `fcntl.F_GETLEASE`, `fcntl.F_SETLEASE`, `fcntl.F_GETPIPE_SZ`, `fcntl.F_SETPIPE_SZ` | O(1) | O(1) | Signal-driven I/O, directory notification, lease and pipe-size commands for `fcntl()`; platform-dependent |
| `fcntl.F_ADD_SEALS`, `fcntl.F_GET_SEALS`, `fcntl.F_SEAL_SEAL`, `fcntl.F_SEAL_SHRINK`, `fcntl.F_SEAL_GROW`, `fcntl.F_SEAL_WRITE` | O(1) | O(1) | File-sealing commands and seal bits for `fcntl()`; platform-dependent |
| `fcntl.F_GETPATH`, `fcntl.F_NOCACHE`, `fcntl.F_FULLFSYNC` | O(1) | O(1) | macOS commands for `fcntl()`; platform-dependent |
| `fcntl.I_ATMARK`, `fcntl.I_CANPUT`, `fcntl.I_CKBAND`, `fcntl.I_FDINSERT`, `fcntl.I_FIND`, `fcntl.I_FLUSH`, `fcntl.I_FLUSHBAND`, `fcntl.I_GETBAND`, `fcntl.I_GETCLTIME`, `fcntl.I_GETSIG`, `fcntl.I_GRDOPT`, `fcntl.I_GWROPT`, `fcntl.I_LINK`, `fcntl.I_LIST`, `fcntl.I_LOOK`, `fcntl.I_NREAD`, `fcntl.I_PEEK`, `fcntl.I_PLINK`, `fcntl.I_POP`, `fcntl.I_PUNLINK`, `fcntl.I_PUSH`, `fcntl.I_RECVFD`, `fcntl.I_SENDFD`, `fcntl.I_SETCLTIME`, `fcntl.I_SETSIG`, `fcntl.I_SRDOPT`, `fcntl.I_STR`, `fcntl.I_SWROPT`, `fcntl.I_UNLINK` | O(1) | O(1) | STREAMS requests for `ioctl()`; platform-dependent |
| `fcntl.F_DUP2FD`, `fcntl.F_DUP2FD_CLOEXEC` | O(1) | O(1) | Python 3.11+; FreeBSD commands for `fcntl()`, platform-dependent |
| `fcntl.FICLONE`, `fcntl.FICLONERANGE` | O(1) | O(1) | Python 3.12+; Linux copy-on-write clone requests for `ioctl()`, platform-dependent |
| `fcntl.F_GETOWN_EX`, `fcntl.F_SETOWN_EX`, `fcntl.F_OWNER_PID`, `fcntl.F_OWNER_PGRP`, `fcntl.F_OWNER_TID`, `fcntl.F_GET_RW_HINT`, `fcntl.F_SET_RW_HINT`, `fcntl.F_GET_FILE_RW_HINT`, `fcntl.F_SET_FILE_RW_HINT`, `fcntl.RWH_WRITE_LIFE_NOT_SET`, `fcntl.RWH_WRITE_LIFE_NONE`, `fcntl.RWH_WRITE_LIFE_SHORT`, `fcntl.RWH_WRITE_LIFE_MEDIUM`, `fcntl.RWH_WRITE_LIFE_LONG`, `fcntl.RWH_WRITE_LIFE_EXTREME`, `fcntl.F_SEAL_FUTURE_WRITE`, `fcntl.F_READAHEAD`, `fcntl.F_ISUNIONSTACK`, `fcntl.F_KINFO`, `fcntl.F_RDAHEAD`, `fcntl.F_CLOSEM`, `fcntl.F_MAXFD`, `fcntl.F_GETNOSIGPIPE`, `fcntl.F_SETNOSIGPIPE` | O(1) | O(1) | Python 3.13+; commands and values for `fcntl()`, each on the platforms that define it |
| `fcntl.F_DUPFD_QUERY` | O(1) | O(1) | Python 3.14+; Linux command for `fcntl()`, platform-dependent |

## File Locking and Control

### File Locking

```python
import fcntl

# Open without truncating: the file must not change before the lock is held
with open('data.txt', 'a+') as f:
    # Acquire lock - O(1)
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    try:
        # Replace the contents while locked; flush so the data lands before the lock goes
        f.seek(0)
        f.truncate()
        f.write('Protected data')
        f.flush()
    finally:
        # Release lock - O(1)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

### Non-blocking Lock

```python
import fcntl

# A flock() lock belongs to the open file description, so a second
# open() of the same file contends with the first even in one process
with open('file.txt', 'w') as holder, open('file.txt', 'w') as f:
    fcntl.flock(holder.fileno(), fcntl.LOCK_EX)
    try:
        # Non-blocking exclusive lock - O(1)
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        print("Lock acquired")
    except BlockingIOError:
        print("File is locked elsewhere")
```

## Related Documentation

- [os Module](os.md)
- [threading Module](threading.md)
