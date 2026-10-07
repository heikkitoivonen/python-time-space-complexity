# py_compile Module Complexity

The `py_compile` module compiles one Python source file to a bytecode (`.pyc`) file. A call reads
the whole source, compiles it, and writes the result: nothing is cached between calls, so compiling
a file twice does the work twice.

`n` is the bytes in the source file being compiled. The parse tree, the code object and the
serialized bytecode are each proportional to it, so a compile holds O(n) while it runs and nothing
afterwards. Filesystem operations - a `stat`, creating the cache directory, the atomic rename - are
priced at O(1).

## Complexity Reference

### compile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `py_compile.compile(file, cfile=None, dfile=None, doraise=False, optimize=-1, invalidation_mode=None, quiet=0)` | O(n) | O(n) | Returns the path written, or `None` on a compilation error; `doraise=True` raises instead unless `quiet=2` |
| `py_compile.main()` | O(total n) | O(largest n) | `python -m py_compile`; compiles the named files in order, one at a time, and exits 1 at the first failure. The list of names is held as well |

### PycInvalidationMode

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `py_compile.PycInvalidationMode` | O(1) | O(1) | Enum of the three modes below |
| `PycInvalidationMode.TIMESTAMP` | O(1) | O(1) | Records the source's mtime and size; the default unless `SOURCE_DATE_EPOCH` is non-empty |
| `PycInvalidationMode.CHECKED_HASH` | O(1) | O(1) | Records a hash of the source, checked when import loads the `.pyc`; hashing adds an O(n) pass, cheap next to compiling. The default when `SOURCE_DATE_EPOCH` is non-empty |
| `PycInvalidationMode.UNCHECKED_HASH` | O(1) | O(1) | Records the hash; import does not check it by default |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `py_compile.PyCompileError` | O(e) | O(e) | e = length of the error message, formatted once when the exception is constructed; `.msg`, `.file`, `.exc_type_name` and `.exc_value` are then O(1) attributes |

## Compiling Python Files

### Basic Compilation

By default the bytecode goes to the PEP 3147 location under `__pycache__`, named for the running
interpreter; `cfile` puts it exactly where you ask.

```python
import importlib.util
import py_compile
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    module = Path(work) / 'module.py'
    module.write_text('value = 1\n')

    written = py_compile.compile(module)  # O(n)
    tag = sys.implementation.cache_tag
    assert written == str(Path(work) / '__pycache__' / f'module.{tag}.pyc')

    target = Path(work) / 'module.pyc'
    assert py_compile.compile(module, cfile=target) == target  # O(n)
    assert target.read_bytes()[:4] == importlib.util.MAGIC_NUMBER
```

### Reporting Failures

On a compilation error `compile()` returns `None` and writes the error message to stderr.
`doraise=True` raises `PyCompileError` instead - but only when `quiet` is below 2: `quiet=2`
swallows the error entirely, so a build step asking for both gets neither the exception nor the
message. `quiet=0` and `quiet=1` behave the same inside `compile()`.

`doraise` governs compilation errors only. A missing source file raises `FileNotFoundError`, and a
`cfile` that is a symlink or a non-regular file raises `FileExistsError`, whatever the flags.

```python
import contextlib
import io
import py_compile
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    broken = Path(work) / 'broken.py'
    broken.write_text('def (\n')

    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        assert py_compile.compile(broken) is None  # O(n)
    assert 'SyntaxError' in stderr.getvalue()

    try:
        py_compile.compile(broken, doraise=True)
    except py_compile.PyCompileError as error:
        assert error.file == broken  # the path as passed
        assert error.exc_type_name == 'SyntaxError'
    else:
        raise AssertionError('doraise did not raise')

    # quiet=2 wins over doraise: no exception, and nothing written
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        assert py_compile.compile(broken, doraise=True, quiet=2) is None
    assert stderr.getvalue() == ''

    try:
        py_compile.compile(Path(work) / 'absent.py', doraise=True, quiet=2)
    except FileNotFoundError as error:
        assert error.filename.endswith('absent.py')
    else:
        raise AssertionError('a missing source was compiled')
```

## Choosing How Bytecode Is Invalidated

`TIMESTAMP` records the source's modification time and size, so the import check is a `stat`. It
misses an edit that changes neither - which a checkout, a restore, or a generator writing
same-length content can produce. `CHECKED_HASH` records a hash of the source and import re-hashes
the source to check it, which notices any edit. `UNCHECKED_HASH` records the hash and, by default,
import does not check it - for deployments where the source cannot change.

The default is not fixed: when `SOURCE_DATE_EPOCH` is set to a non-empty value, `compile()` uses
`CHECKED_HASH`, so a reproducible build gets hash invalidation without asking. The mode is
recorded in the flags word of the `.pyc` header (PEP 552).

```python
import os
import py_compile
import tempfile
from pathlib import Path

modes = py_compile.PycInvalidationMode

def flags(pyc):
    return int.from_bytes(Path(pyc).read_bytes()[4:8], 'little')

with tempfile.TemporaryDirectory() as work:
    module = Path(work) / 'module.py'
    module.write_text('value = 1\n')

    for mode, expected in [
        (modes.TIMESTAMP, 0),       # mtime and size
        (modes.CHECKED_HASH, 3),    # hash, checked on import
        (modes.UNCHECKED_HASH, 1),  # hash, not checked
    ]:
        target = Path(work) / f'{mode.name}.pyc'
        py_compile.compile(module, cfile=target, invalidation_mode=mode)  # O(n)
        assert flags(target) == expected

    os.environ.pop('SOURCE_DATE_EPOCH', None)
    assert flags(py_compile.compile(module)) == 0  # TIMESTAMP by default

    os.environ['SOURCE_DATE_EPOCH'] = '1700000000'
    assert flags(py_compile.compile(module)) == 3  # CHECKED_HASH by default
```

## Compiling From the Command Line

`python -m py_compile` compiles each named file in turn, or the names read from stdin when the
only argument is `-`. It stops at the first file that fails, so the files after it are not
compiled.

```python
import subprocess
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    good = Path(work) / 'good.py'
    broken = Path(work) / 'broken.py'
    later = Path(work) / 'later.py'
    good.write_text('value = 1\n')
    broken.write_text('def (\n')
    later.write_text('value = 2\n')

    result = subprocess.run(
        [sys.executable, '-m', 'py_compile', good, broken, later],
        capture_output=True, text=True,
    )  # O(total n) up to the first failure
    assert result.returncode == 1
    assert 'SyntaxError' in result.stderr

    cache = Path(work) / '__pycache__'
    assert [p.name.split('.')[0] for p in cache.iterdir()] == ['good']
```

## Common Patterns

### Compiling Several Files

Each call is independent, so a batch costs the sum of its files. `compileall` does the same over a
directory tree and can spread it across processes.

```python
import py_compile
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    files = []
    for name in ('script1.py', 'script2.py', 'module.py'):
        path = Path(work) / name
        path.write_text('value = 1\n')
        files.append(path)

    written = [py_compile.compile(f, doraise=True) for f in files]  # O(total n)
    assert all(Path(pyc).is_file() for pyc in written)
```

## Performance Best Practices

✅ **Do**:

- Pass `doraise=True` (with `quiet` below 2) in a build step, so a syntax error fails it instead of
  returning `None`
- Use `CHECKED_HASH` where sources can change without moving their mtime; the hash is an extra
  O(n) pass that compiling already dominates
- Use `compileall` for a whole tree rather than walking it yourself

❌ **Avoid**:

- `doraise=True` together with `quiet=2` - the error is silently dropped
- `UNCHECKED_HASH` for sources that can change: import keeps serving the old bytecode
- Recompiling an unchanged file on every run; nothing is cached, so each call costs O(n) again

## Version Notes

- **All Python 3**: `quiet=2` suppresses the exception that `doraise=True` asks for

## Related Modules

- **[compileall](compileall.md)** - compiles every file in a directory tree
- **[importlib](importlib.md)** - the import system that reads and validates `.pyc` files
- **[marshal](marshal.md)** - the serialization format inside a `.pyc`
- **[ast](ast.md)** - parsing source without producing bytecode
