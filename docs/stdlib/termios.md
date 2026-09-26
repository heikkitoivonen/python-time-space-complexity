# termios Module Complexity

The `termios` module wraps the POSIX terminal-control calls, and exists only on Unix. Each
function is one or two system calls on a fixed-size kernel structure: a terminal's attributes, its
window size, or its input and output queues. Every function takes a file descriptor or an object
with a `fileno()` method, such as `sys.stdin`; the examples below use a pseudo-terminal pair from
`os.openpty()`, so they need no real terminal.

No operation here has an input that grows. The attribute list has seven entries and its
control-character list has `termios.NCCS` entries, a constant of the platform, so every bound is
O(1), and the bounds count each system call as constant. Some calls wait on the device - until
queued output has been transmitted, or for the length of a break - and that wait is the
terminal's, not work done here.

## Complexity Reference

### Attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `termios.tcgetattr(fd)` | O(1) | O(1) | A new list `[iflag, oflag, cflag, lflag, ispeed, ospeed, cc]` on every call; `cc` is a list of `NCCS` entries, one-byte `bytes` except `cc[VMIN]` and `cc[VTIME]`, which are integers while `ICANON` is off |
| `termios.tcsetattr(fd, when, attributes)` | O(1) | O(1) | `attributes` is a list shaped like `tcgetattr()`'s. `TCSANOW` applies the change at once, `TCSADRAIN` first waits for queued output to be transmitted, and `TCSAFLUSH` also discards input not yet read |

### Queues and line control

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `termios.tcdrain(fd)` | O(1) | O(1) | Blocks until the output written to `fd` has been transmitted; how long depends on the device and on what is queued |
| `termios.tcflush(fd, queue)` | O(1) | O(1) | Discards input not yet read (`TCIFLUSH`), output not yet transmitted (`TCOFLUSH`), or both (`TCIOFLUSH`) |
| `termios.tcflow(fd, action)` | O(1) | O(1) | Returns at once. `TCOOFF` suspends output until `TCOON`; on a Linux pseudo-terminal a write in between waits, or raises `BlockingIOError` on a non-blocking descriptor; `TCIOFF` and `TCION` send the terminal's STOP and START characters |
| `termios.tcsendbreak(fd, duration)` | O(1) | O(1) | A zero `duration` holds a serial line in the break state for 0.25 to 0.5 seconds; a nonzero one has a system-dependent meaning |

### Window size

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `termios.tcgetwinsize(fd)` | O(1) | O(1) | Python 3.11+; returns `(rows, columns)` |
| `termios.tcsetwinsize(fd, winsize)` | O(1) | O(1) | Python 3.11+; `winsize` is a `(rows, columns)` pair like the one `tcgetwinsize()` returns |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `termios.TCSANOW`, `termios.TCSADRAIN`, `termios.TCSAFLUSH` | O(1) | O(1) | The `when` argument of `tcsetattr()` |
| `termios.TCIFLUSH`, `termios.TCOFLUSH`, `termios.TCIOFLUSH`, `termios.TCOOFF`, `termios.TCOON`, `termios.TCIOFF`, `termios.TCION` | O(1) | O(1) | Selectors for `tcflush()` and `tcflow()` |
| `termios.ECHO`, `termios.ICANON`, `termios.VMIN`, `termios.VTIME` and the other flag bits and `cc` indices | O(1) | O(1) | Integers named as in C; which ones exist, and their values, depend on the platform |
| `termios.NCCS` | O(1) | O(1) | The length of the `cc` list |
| `termios.error` | O(1) | O(1) | Raised with `(errno, message)` when a system call fails, such as on a descriptor that is not a terminal |

## Reading and Changing Attributes

### Changing One Mode

Reading the attributes builds a fresh seven-entry list; writing them back is a fixed number of
system calls however many flags change. Turning `ICANON` off ends line-at-a-time input and turns
`cc[VMIN]` and `cc[VTIME]` into integers; with `VMIN` 1 and `VTIME` 0, as below, a read returns
after one byte.

```python
import os
import termios

master, slave = os.openpty()

attributes = termios.tcgetattr(slave)  # O(1)
assert len(attributes) == 7 and len(attributes[6]) == termios.NCCS
assert attributes[3] & termios.ICANON
assert isinstance(attributes[6][termios.VMIN], bytes)  # canonical mode: bytes

attributes[3] &= ~termios.ICANON
attributes[6][termios.VMIN] = 1  # return from read() after one byte
attributes[6][termios.VTIME] = 0
termios.tcsetattr(slave, termios.TCSANOW, attributes)  # O(1)

current = termios.tcgetattr(slave)  # O(1) - a new list every call
assert current is not attributes
assert not current[3] & termios.ICANON
assert current[6][termios.VMIN] == 1  # an integer once ICANON is off

os.write(master, b"x")  # no newline needed now
assert os.read(slave, 1) == b"x"

os.close(master)
os.close(slave)
```

### Copying an Attribute List

`attributes[:]` and `list(attributes)` copy the outer list only: the `cc` list inside is shared,
so changing a control character through the copy changes the saved list too. Call
`tcgetattr()` twice, or use `copy.deepcopy()`, when one list is to be restored later.

```python
import copy
import os
import termios

master, slave = os.openpty()
saved = termios.tcgetattr(slave)  # O(1)

shallow = saved[:]
assert shallow[6] is saved[6]  # the cc list is shared

separate = termios.tcgetattr(slave)  # O(1) - its own cc list
deep = copy.deepcopy(saved)          # O(1) - NCCS entries
assert separate[6] is not saved[6] and deep[6] is not saved[6]

separate[6][termios.VEOF] = b"\x01"
assert saved[6][termios.VEOF] == b"\x04"  # untouched

os.close(master)
os.close(slave)
```

### When a Change Takes Effect

The `when` argument decides what happens to data already queued. `TCSANOW` changes the settings
at once, `TCSADRAIN` waits for queued output first, and `TCSAFLUSH` also throws away input that has
arrived but not been read.

```python
import os
import select
import termios

master, slave = os.openpty()
attributes = termios.tcgetattr(slave)

os.write(master, b"typed ahead\n")
assert select.select([slave], [], [], 5)[0]  # the line is waiting to be read

termios.tcsetattr(slave, termios.TCSAFLUSH, attributes)  # O(1) - discards it
assert not select.select([slave], [], [], 0.2)[0]

os.close(master)
os.close(slave)
```

## Queue Control

`tcflush()` throws queued data away and `tcflow()` suspends or resumes transmission, and both
return at once. `tcdrain()` and `tcsendbreak()` return when the device is done, which on a pseudo-terminal is
at once and on a slow serial line can be a noticeable wait.

```python
import os
import select
import termios

master, slave = os.openpty()

# Suspend output: a non-blocking write cannot proceed until it resumes
termios.tcflow(slave, termios.TCOOFF)  # O(1)
os.set_blocking(slave, False)
try:
    os.write(slave, b"held")
except BlockingIOError:
    pass
else:
    raise AssertionError('a write went through while output was suspended')
termios.tcflow(slave, termios.TCOON)  # O(1)
os.set_blocking(slave, True)
os.write(slave, b"sent")
assert select.select([master], [], [], 5)[0]
assert os.read(master, 100) == b"sent"

# Discard input nobody has read yet
os.write(master, b"stale\n")
assert select.select([slave], [], [], 5)[0]
termios.tcflush(slave, termios.TCIFLUSH)  # O(1)
assert not select.select([slave], [], [], 0.2)[0]

termios.tcdrain(slave)  # O(1) - waits for the device, not for Python

os.close(master)
os.close(slave)
```

## Window Size

`tcgetwinsize()` and `tcsetwinsize()`, added in Python 3.11, read and set the rows and columns a
terminal reports, the numbers a full-screen program lays itself out by.

```python
import os
import termios

master, slave = os.openpty()

termios.tcsetwinsize(slave, (24, 80))  # O(1)
assert termios.tcgetwinsize(slave) == (24, 80)  # O(1)
assert termios.tcgetwinsize(master) == (24, 80)  # both ends share it

os.close(master)
os.close(slave)
```

## Errors

A call on a descriptor that is not a terminal fails in the system call and raises
`termios.error` with the error number and its message.

```python
import errno
import os
import termios

read_end, write_end = os.pipe()
try:
    termios.tcgetattr(read_end)
except termios.error as error:
    assert error.args[0] == errno.ENOTTY
else:
    raise AssertionError('a pipe had terminal attributes')

os.close(read_end)
os.close(write_end)
```

## Common Patterns

### Reading Without Echo

Save the attributes, change a separate copy, and restore the saved list in `finally`, so the
terminal is left as it was found even if the read raises.

```python
import os
import select
import termios

master, slave = os.openpty()

saved = termios.tcgetattr(slave)     # O(1)
quiet = termios.tcgetattr(slave)     # O(1) - a separate list to change
quiet[3] &= ~termios.ECHO
try:
    termios.tcsetattr(slave, termios.TCSADRAIN, quiet)  # O(1)
    os.write(master, b"secret\n")
    assert os.read(slave, 100) == b"secret\n"
finally:
    termios.tcsetattr(slave, termios.TCSADRAIN, saved)  # O(1)

assert not select.select([master], [], [], 0.2)[0]  # nothing was echoed
assert termios.tcgetattr(slave)[3] & termios.ECHO

os.close(master)
os.close(slave)
```

## Performance Best Practices

✅ **Do**:

- Save the attributes once and restore them in `finally`: both are O(1), and a terminal left in a
  changed mode outlives the program
- Change a list from a second `tcgetattr()` call, or a `copy.deepcopy()`, so the saved `cc` list
  stays as it was
- Set a mode once around a loop of reads rather than once per read; each change is its own
  system calls

❌ **Avoid**:

- `TCSAFLUSH` when input typed ahead matters - it is discarded, not delayed
- `tcdrain()` or `TCSADRAIN` in a latency-sensitive path on a slow line - each waits for the queued
  output to go out
- Assuming a constant exists everywhere - the set in the module is the platform's

## Version Notes

- **Python 3.11+**: Added `tcgetwinsize()` and `tcsetwinsize()`
- **All Python 3**: Unix only; which constants exist depends on the platform

## Related Modules

- **[tty](tty.md)** - `setraw()` and `setcbreak()`, the common mode changes built on these calls
- **[pty](pty.md)** - pseudo-terminal pairs, for driving a terminal with none attached
- **[fcntl](fcntl.md)** - `ioctl()` for terminal requests this module has no function for
- **[getpass](getpass.md)** - reading a password with echo turned off
