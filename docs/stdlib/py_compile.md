# py_compile Module

The `py_compile` module compiles Python source files to bytecode (.pyc files), useful for precompilation and optimization.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compile()` | O(n) | O(n) | n = source length; parses, compiles and writes |
| `invalidation_mode=` | O(n) | O(1) | Hashing the source adds about 3% to a compile |

## Compiling Python Files

### Basic Compilation

```python
import py_compile
import tempfile
from pathlib import Path

work = Path(tempfile.mkdtemp())
module = work / 'module.py'
module.write_text('value = 1\n')

# Compile file - O(n). Returns the path it wrote, or None on failure
written = py_compile.compile(module)
print(written)  # .../__pycache__/module.cpython-313.pyc (PEP 3147)

# Compile with custom output
py_compile.compile(module, cfile=work / 'module.pyc')
```

### Reporting Failures

`compile()` returns the path of the bytecode it wrote. On a compilation
error it returns `None` and prints the traceback; `doraise=True` raises
`PyCompileError` instead.

!!! warning "`quiet=2` overrides `doraise`"

    The raise is inside an `if quiet < 2:` branch, so `quiet=2` swallows the
    error entirely and returns `None` - a build step asking for both gets
    neither the exception nor the message. Use `quiet=1`, which suppresses
    the printed traceback but still raises.

A missing source file raises `FileNotFoundError` under every combination:
`doraise` governs compilation errors, not reading the file.

```python
import py_compile
import tempfile
from pathlib import Path

work = Path(tempfile.mkdtemp())
broken = work / 'broken.py'
broken.write_text('def (\n')

print(py_compile.compile(broken, quiet=2))  # None, and nothing printed

# quiet=1 still raises; quiet=2 would return None without raising
try:
    py_compile.compile(broken, doraise=True, quiet=1)
except py_compile.PyCompileError as error:
    print(f'failed: {error.file}')

assert py_compile.compile(broken, doraise=True, quiet=2) is None

try:
    py_compile.compile(work / 'absent.py', doraise=True)
except FileNotFoundError as error:
    print(f'no such source: {error.filename}')
```

### Choosing How Bytecode Is Invalidated

The default, `TIMESTAMP`, records the source's modification time and size.
That is the cheapest check, and it misses an edit that changes neither -
which a checkout, a restore, or a generator writing the same-length content
can produce. `CHECKED_HASH` records a hash of the source instead and costs
about 3% more to write.

```python
import py_compile
import tempfile
from pathlib import Path

modes = py_compile.PycInvalidationMode
module = Path(tempfile.mkdtemp()) / 'module.py'
module.write_text('value = 1\n')

# Default: mtime and size, and nothing else
py_compile.compile(module, invalidation_mode=modes.TIMESTAMP)

# Verify the source hash on every import - immune to mtime games
py_compile.compile(module, invalidation_mode=modes.CHECKED_HASH)

# Record the hash but never check it - for read-only deployments
py_compile.compile(module, invalidation_mode=modes.UNCHECKED_HASH)
```

### Batch Compilation

```python
import py_compile
import tempfile
from pathlib import Path

work = Path(tempfile.mkdtemp())
files = []
for name in ('script1.py', 'script2.py', 'module.py'):
    path = work / name
    path.write_text('value = 1\n')
    files.append(path)

# Compile several - O(k*n) for k files of n bytes
for f in files:
    py_compile.compile(f)  # O(n) per file

# compileall does this over a tree, and can use several processes
```

## Related Documentation

- [ast Module](ast.md)
- [compileall Module](compileall.md)
