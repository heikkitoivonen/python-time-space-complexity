# pipes Module Complexity

The `pipes` module builds `/bin/sh` command lines from a list of steps and runs them. A
`Template` holds the steps; `copy()` runs the pipeline from one file to another and waits for it,
and `open()` starts it and hands back the end Python reads or writes. The data moves from command
to command through the shell's pipes and temporary files, so the Python process touches only what
it reads or writes itself.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The page covers Python 3.10
    to 3.12 on Unix; the examples need one of those versions and a POSIX `/bin/sh`.

`n` is the steps in a template, `b` is the characters read or written through the object `open()`
returns, and `k` is the characters of the string given to `quote()`. Commands and file names are
treated as short, so the command line built for n steps is O(n) characters. The bounds price the
Python process's work; starting the shell and the commands, and the commands' own work, are outside
every bound.

## Complexity Reference

### Template

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pipes.Template()` | O(1) | O(1) | An empty pipeline; nothing runs until `open()` or `copy()` |
| `Template.append(cmd, kind)` | O(1) amortized | O(1) | Adds a step at the end. Raises `ValueError` for an unknown kind, a step after a `'-.'` step, a `'.-'` step, or a file kind whose command lacks `$IN` or `$OUT` |
| `Template.prepend(cmd, kind)` | O(n) | O(1) | Adds a step at the front, shifting every other step. The same checks, with `'.-'` and `'-.'` swapped |
| `Template.reset()` | O(n) | O(1) | Removes every step |
| `Template.clone()` | O(n) | O(n) | A new template with its own copy of the steps and the same debug flag; changing one does not change the other |
| `Template.debug(flag)` | O(1) | O(1) | When true, `open()` and `copy()` print the command line and run it under `set -x` |
| `Template.open(file, rw)` | O(n²) | O(n) | Builds the command line, starts it with `os.popen()` and returns without waiting. `rw` is `'r'` or `'w'`; with no steps, it is the built-in `open(file, rw)`. Reading or writing the returned object is O(b); closing it waits for the pipeline and returns the status `copy()` would, or `None` for 0 |
| `Template.copy(infile, outfile)` | O(n²) | O(n) | Builds the command line and runs it with `os.system()`, waiting for it to finish. Returns the wait status of the last command the shell runs: normally the last step, or with temporary files the `rm` that deletes them, so a failed step can still return 0. A failing command raises nothing |

### Module constants and functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pipes.STDIN_STDOUT`, `pipes.STDIN_FILEOUT`, `pipes.FILEIN_STDOUT`, `pipes.FILEIN_FILEOUT`, `pipes.SOURCE`, `pipes.SINK` | O(1) | O(1) | The kind strings `'--'`, `'-f'`, `'f-'`, `'ff'`, `'.-'` and `'-.'`; undocumented names, so pass the strings |
| `pipes.quote(s)` | O(k) | O(k) | `shlex.quote` under another name; undocumented, so import it from `shlex` |

## Building a Template

A kind is two characters, for the step's input and then its output: `-` is a pipe, `f` is a file
the command names as `$IN` or `$OUT`, and `.` is none, which makes the step the first (`'.-'`) or
the last (`'-.'`). Adding a step runs nothing. `append()` costs the same whatever the template
holds; `prepend()` shifts every step already there.

```python
import pipes

t = pipes.Template()          # O(1)
t.append('tr a-z A-Z', '--')  # O(1) - reads a pipe, writes a pipe
t.prepend('sort', '--')       # O(n) - shifts every step

try:
    t.append('sort', 'ff')    # a file kind must name $IN and $OUT
except ValueError as error:
    assert 'missing $IN' in str(error)
else:
    raise AssertionError('a file step without $IN was accepted')
```

## Running a Pipeline

### Copying Between Files

`copy()` runs the whole pipeline under one shell and waits for it. The data never passes through
Python, so the process's own share is the same for a large file as for a small one; what it
returns is the shell's wait status, not an exception.

```python
import os
import pipes
import tempfile

t = pipes.Template()
t.append('sort', '--')
t.append('tr a-z A-Z', '--')

with tempfile.TemporaryDirectory() as tmp:
    source = os.path.join(tmp, 'in.txt')
    target = os.path.join(tmp, 'out.txt')
    with open(source, 'w') as f:
        f.write('pear\napple\n')

    status = t.copy(source, target)  # O(n²), then waits for sort and tr
    assert status == 0
    with open(target) as f:
        assert f.read() == 'APPLE\nPEAR\n'

    upper = t.clone()  # O(n) - its own copy of the steps
    t.reset()          # O(n) - t is empty, so it copies the file unchanged
    assert t.copy(source, target) == 0
    with open(target) as f:
        assert f.read() == 'pear\napple\n'
    assert upper.copy(source, target) == 0
    with open(target) as f:
        assert f.read() == 'APPLE\nPEAR\n'

    failing = pipes.Template()
    failing.append('exit 3', '--')
    status = failing.copy(source, target)
    assert os.waitstatus_to_exitcode(status) == 3  # a failure is a status, not an error
```

### Reading and Writing Through a Pipeline

`open()` starts the pipeline and returns at once. Python then holds one end of it: what you write
goes into the first step, and what you read comes from the last, so that end costs O(b). Closing
the object waits for the pipeline to finish.

```python
import os
import pipes
import tempfile

t = pipes.Template()
t.append('tr a-z A-Z', '--')

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, 'pipefile')

    with t.open(path, 'w') as f:  # O(n²) - starts the shell, does not wait
        f.write('hello world')    # O(b) - into tr, which writes the file
    with open(path) as f:
        assert f.read() == 'HELLO WORLD'

    with t.open(path, 'r') as f:  # tr reads the file; Python reads tr
        assert f.read() == 'HELLO WORLD'  # O(b)
```

### File Steps Use Temporary Files

Where either side of a boundary between two steps is a file, the module creates a temporary file
for it when the command line is built, and the shell deletes it when the pipeline ends. Everything
the earlier step writes goes to disk before the later step starts, so pipe ends, `-`, are the
cheaper choice wherever the command can use them.

```python
import os
import pipes
import tempfile

t = pipes.Template()
t.append('sort $IN > $OUT', 'ff')  # file in, file out
t.append('tr a-z A-Z', '--')       # one temporary file between the two

with tempfile.TemporaryDirectory() as tmp:
    source = os.path.join(tmp, 'in.txt')
    target = os.path.join(tmp, 'out.txt')
    with open(source, 'w') as f:
        f.write('pear\napple\n')

    assert t.copy(source, target) == 0
    with open(target) as f:
        assert f.read() == 'APPLE\nPEAR\n'
```

## Common Patterns

### Replacing pipes With subprocess

From Python 3.13 the same work is `subprocess`, which takes the arguments as a list and needs no
shell, and `shlex.quote` where a shell command line is still wanted.

```python
import shlex
import subprocess

result = subprocess.run(
    ['tr', 'a-z', 'A-Z'], input='hello world', capture_output=True, text=True, check=True
)
assert result.stdout == 'HELLO WORLD'

assert shlex.quote("it's") == "'it'\"'\"'s'"  # O(k)
```

## Performance Best Practices

✅ **Do**:

- Use `copy()` when Python does not need the data; nothing passes through the process
- Give a step pipe ends, `-`, wherever its command can use them; only a boundary where both sides
  are pipes needs no temporary file
- Check the status `copy()` and `close()` return, knowing it reports only the shell's last command;
  a failing command raises nothing
- Use `subprocess` and `shlex.quote`, which outlive this module

❌ **Avoid**:

- `'f'` kinds between steps on large data: each such boundary writes the whole intermediate result
  to a temporary file
- Templates of thousands of steps: building the command line is O(n²)

## Version Notes

- **Python 3.11+**: Importing the module emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import pipes` raises `ModuleNotFoundError`

## Related Modules

- **[subprocess](subprocess.md)** - the replacement, with the arguments as a list and no shell
- **[shlex](shlex.md)** - `quote()` for building shell command lines by hand
- **[tempfile](tempfile.md)** - where the temporary files between file steps come from
- **[os](os.md)** - `os.system()` and `os.popen()`, which run the command line
