# pty Module Complexity

The `pty` module opens pseudo-terminal pairs and drives a child process through
one. It is available on Unix only. Two costs are worth separating: opening a
pair or forking through one is a small fixed operation, while `spawn()` runs a
copy loop until the child's terminal closes and its cost is the traffic it
moves, not the call.

Size variables: b = total bytes copied between the child's terminal and the
parent's standard streams; m = the parent's memory mappings at fork time.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `openpty()` | O(1) | O(1) | Returns `(master_fd, slave_fd)` from `os.openpty()`. The generic fallback, reached only where `os.openpty()` is missing or fails, scans a fixed 256-entry device-name table |
| `fork()` | O(1) | O(1) | `os.forkpty()`: the kernel's page-table copy scales with the parent's mappings m, as `os.fork()`. The child returns as a session leader with the pty for its controlling terminal, and its `master_fd` is invalid |
| `spawn(argv, master_read=, stdin_read=)` | O(b) | O(1) | Runs the copy loop until the child's terminal reaches end of file, then waits for the child, so the call blocks for at least the child's whole lifetime. With the default readers it reads every byte in bounded chunks, so time is O(b) and space does not grow with b. Returns the child's `waitpid` status and emits the `pty.spawn` audit event |

## spawn blocks, and its buffers stay bounded

`spawn()` is not a launch that returns a handle. It forks the child, sets the
parent's standard input to raw mode when that input is a terminal, and then
copies in both directions until the child's terminal reaches end of file. Only
then does it wait for the child and return its exit status, so the call lasts
at least as long as the child does.

With the default readers the loop reads every byte the child writes in bounded
chunks, so the time is O(b) in that traffic. The space is not: the loop holds
a bounded buffer of chunks, hands them on, and does not accumulate the stream,
so memory does not grow with b however much data crosses. A custom reader adds
its own cost per call on top.

```python
import os
import pty
import sys

chunks = 0

def count(fd):
    global chunks
    data = os.read(fd, 1024)
    chunks += 1  # one call per block copied - the work is O(b)
    return data

# Copy the child's output until it exits - O(b) time, O(1) space
status = pty.spawn(
    [sys.executable, "-c", "print('x' * 4000)"],
    count,
    stdin_read=lambda fd: b"",  # do not forward this process's stdin to the child
)
assert os.waitstatus_to_exitcode(status) == 0
assert chunks >= 1
```

## Opening a pair, and forking through one

`openpty()` returns a master/slave descriptor pair and does no work
proportional to anything; writing to one end and reading the other goes through
the terminal's line discipline, which is why a bare newline comes back as
carriage-return newline.

```python
import os
import pty

master_fd, slave_fd = pty.openpty()  # O(1)
os.write(slave_fd, b"hello\n")
assert os.read(master_fd, 1024) == b"hello\r\n"  # output post-processing adds CR
os.close(master_fd)
os.close(slave_fd)
```

`fork()` forks the process and hands the child a pseudo-terminal as its
controlling terminal, returning in both processes at once. The parent gets the
child's pid and the master descriptor; the child gets pid 0 and an invalid
descriptor, and is a session leader. The fork itself copies the parent's page
tables, so its cost tracks the parent's mappings m the same way `os.fork()`
does, not the child's later work.

```python
import os
import pty

pid, master_fd = pty.fork()
if pid == 0:
    # Child: its stdin/stdout/stderr are the pty - O(1)
    os.write(1, b"in the child\n")
    os._exit(0)

# Parent: read the child's output until end of file - O(b)
chunks = []
while True:
    try:
        data = os.read(master_fd, 1024)
    except OSError:  # some platforms signal EOF with an error here
        break
    if not data:
        break
    chunks.append(data)
os.close(master_fd)
os.waitpid(pid, 0)
assert b"in the child" in b"".join(chunks)
```

## Related Documentation

- [tty Module](tty.md)
- [termios Module](termios.md)
- [os Module](os.md)
- [subprocess Module](subprocess.md)
