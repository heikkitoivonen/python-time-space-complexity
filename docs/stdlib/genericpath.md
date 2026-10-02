# genericpath Module Complexity

The `genericpath` module holds the path functions that `posixpath` and `ntpath` share; import
them from `os.path`. On POSIX `os.path` re-exports every one of them, and on Windows it replaces
several of the type checks with its own, priced on the [ntpath](ntpath.md) page. Apart from
`commonprefix()`, every function here is at most two calls to the stat family and holds nothing
between calls.

A syscall counts as O(1), as it does on the [os](os.md) page: the kernel still resolves the path
component by component, but that is not what a caller chooses between. For `commonprefix()`, `n`
is the items in the list, `B` their total length, and `p` the length of the prefix returned.

## Complexity Reference

### Path comparison

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `genericpath.commonprefix(m)` | O(n + B) | O(n + p) | Character by character, so it can end mid-component; a list of component lists compares whole components |

### File type checks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `genericpath.exists(path)` | O(1) | O(1) | One stat; `False` for a missing, unreachable or invalid path rather than an error |
| `genericpath.lexists(path)` | O(1) | O(1) | One lstat; `True` for a broken symlink. Python 3.13+ |
| `genericpath.isfile(path)` | O(1) | O(1) | One stat, following symlinks |
| `genericpath.isdir(path)` | O(1) | O(1) | One stat, following symlinks |
| `genericpath.islink(path)` | O(1) | O(1) | One lstat. Python 3.12+ |
| `genericpath.isjunction(path)` | O(1) | O(1) | Always `False` without touching the disk; Windows's `os.path` replaces it. Python 3.13+ |
| `genericpath.isdevdrive(path)` | O(1) | O(1) | Always `False` without touching the disk; Windows's `os.path` replaces it. Python 3.13+ |

### File statistics

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `genericpath.getsize(filename)` | O(1) | O(1) | One stat; raises rather than returning `False` |
| `genericpath.getmtime(filename)` | O(1) | O(1) | One stat |
| `genericpath.getatime(filename)` | O(1) | O(1) | One stat |
| `genericpath.getctime(filename)` | O(1) | O(1) | One stat; metadata change time on POSIX, creation time on Windows |

### File identity

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `genericpath.samefile(f1, f2)` | O(1) | O(1) | Two stats; raises if either fails |
| `genericpath.sameopenfile(fp1, fp2)` | O(1) | O(1) | Two fstats; takes file descriptors, not file objects |
| `genericpath.samestat(s1, s2)` | O(1) | O(1) | No syscall: compares the device and inode numbers of two results already fetched |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `genericpath.ALLOW_MISSING` | O(1) | O(1) | The `strict=` value for `os.path.realpath()` that tolerates a missing tail |

## Comparing Paths

### Characters vs Components

`commonprefix()` finds the smallest and largest item and walks them together. That is linear in
the item count and their total length, and it keeps only the item references and the answer. It compares characters, not
path components: pass lists of components when the result must be a directory.

```python
import genericpath

paths = ['/srv/app1/log', '/srv/app2/log']
assert genericpath.commonprefix(paths) == '/srv/app'  # O(n + B) - ends mid-component

parts = [path.split('/') for path in paths]
assert genericpath.commonprefix(parts) == ['', 'srv']  # O(n + B) - whole components

assert genericpath.commonprefix([]) == ''
assert genericpath.commonprefix(['abc', 'abd', 'xyz']) == ''
```

## Checking Files

### One Stat per Call

`exists()`, `lexists()`, `isfile()`, `isdir()`, `islink()` and each `get*()` function make their
own stat call. The checks return `False` for a path that is missing, unreachable or contains a NUL;
the `get*()` functions and `samefile()` raise instead.

```python
import genericpath
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'data.txt')
    with open(path, 'w') as file:
        file.write('hello')

    assert genericpath.exists(path)       # O(1) - one stat
    assert genericpath.isfile(path)       # O(1) - one stat
    assert genericpath.isdir(directory)   # O(1) - one stat
    assert genericpath.getsize(path) == 5  # O(1) - one stat

    missing = os.path.join(directory, 'missing.txt')
    assert not genericpath.exists(missing)
    assert not genericpath.isfile('bad\0name')  # invalid paths are False too
    try:
        genericpath.getsize(missing)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError('getsize() of a missing file returned')
```

### Junctions and Dev Drives

`isjunction()` and `isdevdrive()` here are the answer for platforms that have neither. They check
that the argument is a path and return `False` without a syscall; on Windows, `os.path` supplies
versions that ask the filesystem.

```python
import genericpath

assert genericpath.isjunction('/no/such/path') is False  # O(1) - no syscall
assert genericpath.isdevdrive('/no/such/path') is False  # O(1) - no syscall

try:
    genericpath.isjunction(42)
except TypeError:
    pass
else:
    raise AssertionError('a non-path was accepted')
```

## File Identity

Two names, or two descriptors, are the same file when their device and inode numbers match.
`samefile()` and `sameopenfile()` fetch both stat results each time; `samestat()` compares results
you already hold.

```python
import genericpath
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    original = os.path.join(directory, 'a.txt')
    alias = os.path.join(directory, 'b.txt')
    other = os.path.join(directory, 'c.txt')
    for name in (original, other):
        with open(name, 'w') as file:
            file.write('x')
    os.link(original, alias)

    assert genericpath.samefile(original, alias)       # O(1) - two stats
    assert not genericpath.samefile(original, other)

    with open(original) as first, open(alias) as second:
        assert genericpath.sameopenfile(first.fileno(), second.fileno())  # O(1) - two fstats

    stats = [os.stat(name) for name in (original, alias, other)]
    assert genericpath.samestat(stats[0], stats[1])     # O(1) - no syscall
    assert not genericpath.samestat(stats[0], stats[2])
```

## Common Patterns

### Reading Several Fields at Once

Each `get*()` call is a stat of its own. When you need more than one field, one `os.stat()` returns
them all.

```python
import genericpath
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'data.txt')
    with open(path, 'w') as file:
        file.write('hello')

    size = genericpath.getsize(path)    # O(1) - one stat
    mtime = genericpath.getmtime(path)  # O(1) - a second stat

    info = os.stat(path)  # O(1) - one stat for every field
    assert (info.st_size, info.st_mtime) == (size, mtime)
```

## Performance Best Practices

✅ **Do**:

- Call `isfile()` or `isdir()` directly; they already return `False` for a missing path, so an
  `exists()` before them is a second stat
- Call `os.stat()` once when you need several fields, instead of one `get*()` call per field
- Keep stat results you will compare again and use `samestat()`, which makes no syscall
- Pass component lists to `commonprefix()`, or use `os.path.commonpath()`, when the result must be
  a directory

❌ **Avoid**:

- `exists()` followed by `getsize()` - two stats, and the file can disappear in between
- Using `commonprefix()` on plain strings as a directory: it can stop mid-name

## Version Notes

- **Python 3.12+**: `genericpath.islink()`
- **Python 3.13+**: `genericpath.lexists()`, `isjunction()` and `isdevdrive()`
- **Python 3.13.4+**, also 3.10.18, 3.11.13 and 3.12.11: `ALLOW_MISSING`
- **All Python 3**: `genericpath` is an implementation module; `os.path` is the public name, and on
  Windows it replaces several of the type checks with its own

## Related Modules

- **[os](os.md)** - `os.stat()` and the `os.path` functions built on these
- **[posixpath](posixpath.md)** - `os.path` on POSIX, including `commonpath()`
- **[ntpath](ntpath.md)** - `os.path` on Windows, with its own type checks
- **[stat](stat.md)** - the mode tests behind `isfile()`, `isdir()` and `islink()`
- **[pathlib](pathlib.md)** - the same checks as methods on path objects
