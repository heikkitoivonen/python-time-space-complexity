# compileall Module Complexity

The `compileall` module byte-compiles every Python source file in a directory tree, or on
`sys.path`, by calling `py_compile` once per file. A serial run walks the tree lazily, one directory
listing at a time, and skips any file whose timestamp-based `.pyc` is already current, so a second
run over an unchanged tree compiles nothing.

`e` is the directory entries examined - every file and subdirectory, not just `.py` files. `b` is
the bytes of source actually compiled, which excludes files whose `.pyc` is current. `m` is the
bytes in the largest of those sources: compiling one file holds its parse tree and code object,
O(m), and nothing once it is written. `w` is the entries in the directory being walked plus those
of its ancestors, which is what a serial walk holds; it is `e` for one flat directory and far less
for a bushy tree. Filesystem calls - a `stat`, reading a 12-byte `.pyc` header, writing a file -
are priced at O(1) apart from the bytes they move.

## Complexity Reference

### Compiling a tree

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compileall.compile_dir(dir, maxlevels=None, ddir=None, force=False, rx=None, quiet=0, legacy=False, optimize=-1, workers=1, invalidation_mode=None, *, stripdir=None, prependdir=None, limit_sl_dest=None, hardlink_dupes=False)` | O(e log e + b) | O(w + m) | Sorts each directory's names and passes every non-directory entry to `compile_file()`; `__pycache__` is never entered. Returns `False` only when a file fails to compile |
| `compile_dir(..., workers=j)` | O(e log e + b) | O(e + j·m) | Summed across processes. The parent submits every path before it starts collecting results; each of the j workers compiles one file at a time. `workers=0` lets the pool choose its default size |

### Compiling one file

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compileall.compile_file(fullname, ddir=None, force=False, rx=None, quiet=0, legacy=False, optimize=-1, invalidation_mode=None, *, stripdir=None, prependdir=None, limit_sl_dest=None, hardlink_dupes=False)` | O(m) | O(m) | m = this file's bytes. O(1) when the name does not end in `.py` or its `.pyc` is current; compiles once per level in `optimize` |

### sys.path and the command line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compileall.compile_path(skip_curdir=1, maxlevels=0, force=False, quiet=0, legacy=False, optimize=-1, invalidation_mode=None)` | O(e log e + b) | O(w + m) | e = entries of the `sys.path` directories, which `maxlevels=0` does not recurse into. Stops at the first directory that reports a failure |
| `compileall.main()` | O(a + e log e + b) | O(a + w + m) | `python -m compileall`; a = names given as arguments or read with `-i`, all held before the first is compiled. With no names it runs `compile_path()`. With `-j`, space is O(a + e + j·m), as for `workers=j` |

## Walking a Directory Tree

Every entry the walk reaches costs a `stat`, whether or not it is Python: a directory of data files
next to a few modules is paid for in full. Memory follows the listings currently open, not the
tree, so a tree of many small directories walks in far less than one flat directory of the same
size.

```python
import compileall
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    tree = Path(work)
    (tree / 'package').mkdir()
    (tree / 'package' / 'module.py').write_text('value = 1\n')
    (tree / 'top.py').write_text('value = 2\n')
    (tree / 'notes.txt').write_text('not Python\n')  # examined, never compiled

    assert compileall.compile_dir(tree, quiet=2)  # O(e log e + b)
    assert len(list((tree / 'package' / '__pycache__').glob('module.*.pyc'))) == 1

    # maxlevels=0 compiles the top directory only
    shallow = Path(work) / 'shallow'
    (shallow / 'sub').mkdir(parents=True)
    (shallow / 'sub' / 'deep.py').write_text('value = 3\n')
    assert compileall.compile_dir(shallow, maxlevels=0, quiet=2)
    assert not (shallow / 'sub' / '__pycache__').exists()
```

!!! warning "The return value only reports compilation failures"

    `compile_dir()` returns `False` when a file fails to compile, and `True`
    otherwise - including when it could not read the directory at all. A path
    that does not exist, or that is a file rather than a directory, is
    reported as success.

```python
import compileall
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    tree = Path(work)
    (tree / 'broken.py').write_text('def (\n')

    assert compileall.compile_dir(tree, quiet=2) is False              # a real failure
    assert compileall.compile_dir(tree / 'nowhere', quiet=2) is True   # listed nothing
    assert compileall.compile_dir(tree / 'broken.py', quiet=2) is True # not a directory
```

## Skipping Up-to-Date Files

Without `force`, each `.py` file costs a `stat` and a read of its `.pyc` header, and is compiled
only when that header does not record the running interpreter and the source's timestamp. Rerunning over an unchanged tree is O(e log
e) whatever the size of the source. `force=True` recompiles everything.

That check only understands timestamp `.pyc` files. Hash-based ones - `invalidation_mode`
`CHECKED_HASH` or `UNCHECKED_HASH`, which is also the default whenever the `SOURCE_DATE_EPOCH`
environment variable is set - never match it. So runs that keep writing hash-based `.pyc` files
recompile every file each time, as if `force` were passed.

```python
import compileall
import contextlib
import io
import py_compile
import tempfile
from pathlib import Path

def compiled(tree, **options):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        compileall.compile_dir(tree, quiet=0, **options)
    return output.getvalue().count('Compiling ')

with tempfile.TemporaryDirectory() as work:
    tree = Path(work)
    (tree / 'module.py').write_text('value = 1\n')

    assert compiled(tree) == 1              # O(b) - no .pyc yet
    assert compiled(tree) == 0              # O(e log e) - header check only
    assert compiled(tree, force=True) == 1  # O(b) again

    checked = py_compile.PycInvalidationMode.CHECKED_HASH
    assert compiled(tree, invalidation_mode=checked, force=True) == 1  # a hash-based .pyc
    assert compiled(tree, invalidation_mode=checked) == 1  # O(b) - recompiled
    assert compiled(tree, invalidation_mode=checked) == 1  # and again, every run
```

## Compiling One File

`compile_file()` is the per-entry step of `compile_dir()`: the same up-to-date check, then one
`py_compile.compile()` per optimization level. Anything not named `.py` returns `True` without
being read.

```python
import compileall
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    source = Path(work) / 'module.py'
    source.write_text('value = 1\n')

    assert compileall.compile_file(source, quiet=2, optimize=[0, 1, 2])  # O(m) per level
    assert len(list((Path(work) / '__pycache__').glob('module.*.pyc'))) == 3

    data = Path(work) / 'data.txt'
    data.write_text('not Python\n')
    assert compileall.compile_file(data, quiet=2)  # O(1) - not compiled
```

## Parallel Compilation

`workers` spreads the files over a process pool. The parent still walks the whole tree, and submits
every path before it starts collecting results, so its memory follows the entry count; each worker
holds only the file it is compiling.

```python
import compileall
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    tree = Path(work)
    for index in range(8):
        (tree / f'module{index}.py').write_text(f'value = {index}\n')

    assert compileall.compile_dir(tree, workers=2, quiet=2)  # O(e log e + b) over 2 workers
    assert len(list((tree / '__pycache__').glob('*.pyc'))) == 8

    try:
        compileall.compile_dir(tree, workers=-1, quiet=2)
    except ValueError as error:
        assert 'workers' in str(error)
    else:
        raise AssertionError('a negative worker count was accepted')
```

## Compiling sys.path

`compile_path()` runs `compile_dir()` over each `sys.path` entry without recursing, skipping the
current directory. It stops at the first directory that reports a failure: the entries after it are
not compiled at all.

```python
import compileall
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as work:
    first = Path(work) / 'first'
    second = Path(work) / 'second'
    first.mkdir()
    second.mkdir()
    (first / 'broken.py').write_text('def (\n')
    (second / 'fine.py').write_text('value = 1\n')

    saved = sys.path[:]
    sys.path[:] = [str(first), str(second)]
    try:
        assert compileall.compile_path(quiet=2) is False
    finally:
        sys.path[:] = saved

    assert not (second / '__pycache__').exists()  # never reached
```

## Common Patterns

### Precompiling a Tree in a Build Step

Check the path yourself, since a missing directory is reported as success, and force a rebuild of
every source rather than trusting the timestamps.

```python
import compileall
import tempfile
from pathlib import Path

def precompile(path):
    if not path.is_dir():
        raise NotADirectoryError(path)
    return compileall.compile_dir(path, force=True, quiet=1)  # O(e log e + b)

with tempfile.TemporaryDirectory() as work:
    tree = Path(work)
    (tree / 'module.py').write_text('value = 1\n')
    assert precompile(tree) is True

    try:
        precompile(tree / 'nowhere')
    except NotADirectoryError:
        pass
    else:
        raise AssertionError('a missing directory was accepted')
```

## Performance Best Practices

✅ **Do**:

- Rerun `compile_dir()` without `force` after a change: files whose `.pyc` is current cost a header
  read, not a compile
- Use `workers` for a large tree; total work is unchanged, but it is spread across processes
- Use `maxlevels` to keep the walk out of deep directories that hold no code you want compiled
- Check that the directory exists before trusting a `True` result

❌ **Avoid**:

- Hash-based invalidation, or `SOURCE_DATE_EPOCH`, for repeated incremental builds - every run
  recompiles every file
- Pointing `compile_dir()` at a tree full of data files; every entry is examined
- Relying on `compile_path()` to compile everything after one directory fails
- Expecting `rx` to prune the walk - it is matched against each file's path after the listing,
  so an excluded directory is still walked in full

## Version Notes

- **All Python 3**: `compile_dir()` returns `True` for a directory it could not list, and
  `compile_path()` stops at the first directory that reports a failure

## Related Modules

- **[py_compile](py_compile.md)** - compiles one file; what `compileall` calls for each entry
- **[importlib](importlib.md)** - `importlib.util.cache_from_source()` names the `.pyc` each file
  is written to
- **[os](os.md)** - the directory listing and `stat` calls the walk is made of
