# idlelib Module Complexity

The `idlelib` package implements IDLE, Python's editor and shell. Its public surface is starting
the application: `python -m idlelib` and the `idle` launcher scripts. Everything else
in the package - the editor, the shell, syntax colouring, the debugger - is private
implementation that can change in a bugfix release ([PEP 434](https://peps.python.org/pep-0434/)),
so this page does not price it.

IDLE is a Tk application and needs a display. By default it also starts a second Python process
to run user code, and talks to it over a local socket. `f` is the files named on the command
line, `s` is the characters in them in total, and `i` is the characters read from standard input.
Tk, the window system, the user-code process, and the code that `-c` or `-r` runs are not priced.

## Complexity Reference

### Starting IDLE

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import idlelib` | O(1) | O(1) | Defines one flag, `idlelib.testing`; imports no submodule and not `tkinter` |
| `python -m idlelib [options] [file ...]` | O(f² + s) | O(f + s) | At most one editor window per file, each file read whole into its window. Each file's directory joins `sys.path` unless already there, so files in f different directories cost O(f²). Needs a display: on Linux without one it exits with `TclError` |
| `python -m idlelib -` | O(i) | O(i) | Reads standard input to its end before creating any window, then runs it in the shell |
| `python -m idlelib -h` | O(1) | O(1) | Prints the usage and exits before creating any window, so it runs without a display |

## Importing the Package

`import idlelib` runs a package `__init__` that sets one flag. The modules that make up IDLE
load only when something imports them, which `python -m idlelib` does.

```python
import subprocess
import sys

code = 'import sys, idlelib; print(sorted(m for m in sys.modules if "idlelib" in m or "tk" in m))'
result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True)
assert result.stdout == "['idlelib']\n"  # O(1) - no submodule, no tkinter
```

## Starting IDLE Without a Window

`-h` is handled while the command line is parsed, before Tk is asked for a window, so it works on
a machine with no display.

```python
import subprocess
import sys

result = subprocess.run(
    [sys.executable, '-m', 'idlelib', '-h'], capture_output=True, text=True, check=True
)  # O(1) - prints the usage and exits
assert 'USAGE: idle' in result.stdout
```

## Performance Best Practices

✅ **Do**:

- Import `idlelib` freely; nothing loads until a submodule is imported

❌ **Avoid**:

- Starting IDLE on a machine without a display; it fails once Tk is asked for a window
- Building on `idlelib` submodules; they are private and their cost can change in a bugfix
  release

## Related Modules

- **[tkinter](tkinter.md)** - the GUI toolkit IDLE is built on
- **[code](code.md)** - the interactive interpreter classes IDLE's shell builds on
