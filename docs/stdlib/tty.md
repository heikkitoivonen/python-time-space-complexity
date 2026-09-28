# tty Module Complexity

The `tty` module switches a Unix terminal between its line-buffered default, cbreak mode and raw
mode. It is a thin layer over `termios`: each mode is a handful of bit operations on the
seven-item attribute list that `termios.tcgetattr()` returns.

Every operation here is O(1). The attribute list has a fixed length, and its control-character
list holds `termios.NCCS` entries, a constant of the platform, so nothing on this page grows
with an input. The one wait is outside that bound: with `TCSADRAIN` or the default `TCSAFLUSH`,
`tcsetattr()` does not return until output already queued for the terminal has been sent.

## Complexity Reference

### Changing a terminal's mode

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tty.setraw(fd, when=termios.TCSAFLUSH)` | O(1) | O(1) | One `tcgetattr()` and one `tcsetattr()`; also turns off signal keys and output processing |
| `tty.setcbreak(fd, when=termios.TCSAFLUSH)` | O(1) | O(1) | One `tcgetattr()` and one `tcsetattr()`; turns off echo and line buffering, keeps signal keys and output processing |
| Restoring with `termios.tcsetattr(fd, when, saved)` | O(1) | O(1) | `saved` from `termios.tcgetattr()`, or from the return value of `setraw()`/`setcbreak()` on 3.12+ |

### Editing an attribute list

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tty.cfmakeraw(mode)` | O(1) | O(1) | Edits `mode` in place and makes no system call; 3.12+ |
| `tty.cfmakecbreak(mode)` | O(1) | O(1) | Edits `mode` in place and makes no system call; 3.12+ |

## Raw and Cbreak Mode

Both modes deliver input a byte at a time without echoing it. Raw mode also turns off the
keys that raise signals and the terminal's output processing, so Ctrl-C arrives as a byte
rather than as `KeyboardInterrupt`. Save the attributes first and restore them in a
`finally` block; the saved list is all that restoring needs.

```python
import os
import termios
import tty

controller, terminal = os.openpty()
try:
    saved = termios.tcgetattr(terminal)       # O(1)
    try:
        tty.setcbreak(terminal)               # O(1)
        mode = termios.tcgetattr(terminal)
        assert not mode[tty.LFLAG] & (termios.ECHO | termios.ICANON)
        assert mode[tty.LFLAG] & termios.ISIG # Ctrl-C still interrupts

        tty.setraw(terminal)                  # O(1)
        mode = termios.tcgetattr(terminal)
        assert not mode[tty.LFLAG] & termios.ISIG
        assert not mode[tty.OFLAG] & termios.OPOST
    finally:
        termios.tcsetattr(terminal, termios.TCSADRAIN, saved)  # O(1)
    assert termios.tcgetattr(terminal) == saved
finally:
    os.close(terminal)
    os.close(controller)
```

## Building a Mode Without Touching the Terminal

`cfmakeraw()` and `cfmakecbreak()` do the bit operations of `setraw()` and `setcbreak()` on a
list you pass in, and return `None`. They make no system call, so a mode can be prepared once
and applied with `termios.tcsetattr()` whenever it is needed.

```python
import os
import termios
import tty

controller, terminal = os.openpty()
try:
    mode = termios.tcgetattr(terminal)
    assert tty.cfmakeraw(mode) is None        # O(1), edits mode in place
    assert not mode[tty.LFLAG] & termios.ECHO
    assert mode[tty.CC][termios.VMIN] == 1
    assert termios.tcgetattr(terminal)[tty.LFLAG] & termios.ECHO  # not applied yet

    termios.tcsetattr(terminal, termios.TCSANOW, mode)  # O(1)
    assert not termios.tcgetattr(terminal)[tty.LFLAG] & termios.ECHO
finally:
    os.close(terminal)
    os.close(controller)
```

## Version Notes

- **Python 3.12+**: Added `cfmakeraw()` and `cfmakecbreak()`; `setraw()` and `setcbreak()` return
  the attributes they replaced
- **Python 3.12.2+**: `setcbreak()` and `cfmakecbreak()` leave carriage-return translation
  (`ICRNL`) on

## Related Modules

- **[termios](termios.md)** - `tcgetattr()` and `tcsetattr()`, the calls these functions wrap
- **[pty](pty.md)** - pseudo-terminal pairs, and `spawn()`, which puts the caller's terminal in raw mode
- **[curses](curses.md)** - `cbreak()` and `raw()` for full-screen programs
