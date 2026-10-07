# posixpath Module Complexity

The `posixpath` module is `os.path` on Linux, macOS and every other POSIX platform: string
operations on `/`-separated paths, plus the few functions that ask the filesystem. It is pure
Python and imports on every platform, so Windows code can use it to take POSIX paths apart. Where
the `posix` module exists it binds C helpers for `normpath()` (3.11+) and `splitroot()` (3.13+);
on Windows, which has no `posix`, Python fallbacks run instead, at the same bounds.

`L` is the length of a path argument in characters, and of all of them together where a function
takes several, as `join()` does. `n` is the number of paths a function is given: `join()`'s
arguments, or the items in the list passed to `commonpath()` or `commonprefix()`. `B` is the total
length of those items and `t` the length of the prefix `commonprefix()` returns. `S` is the length
of `relpath()`'s `start` and `C` the length of the working directory. `V` is the characters
`expandvars()` substitutes in and `H` the home directory `expanduser()` splices in. For
`realpath()`, `R` is the text it walks: the argument, behind the working directory if it is
relative, with the target of every symlink it follows spliced in; `k` is the components of that
text and `j` the symlinks followed. The bounds are for `str` paths; bytes paths are priced only
in the `join()` row. A system call counts as O(1), as it does on the [os page](os.md).

## Complexity Reference

### Splitting and joining

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `posixpath.split(p)` | O(L) | O(L) | `(head, tail)` at the last `/` |
| `posixpath.basename(p)`, `posixpath.dirname(p)` | O(L) | O(L) | |
| `posixpath.splitext(p)` | O(L) | O(L) | |
| `posixpath.splitdrive(p)` | O(1) | O(1) | The drive is always empty, and the tail is the argument itself |
| `posixpath.splitroot(p)` | O(L) | O(L) | 3.12+; `(drive, root, tail)`, with a root of `''`, `'/'` or exactly `'//'` |
| `posixpath.join(a, *p)` | O(n + L); O(n·L) for bytes | O(L) | An absolute argument discards everything before it. Bytes has no in-place concatenation, so each argument copies the result so far |
| `posixpath.commonprefix(list)` | O(n + B) | O(n + t) | The [genericpath](genericpath.md) function: character by character, so it can end mid-component |
| `posixpath.commonpath(paths)` | O(n + B) | O(n + B) | Whole components, ignoring empty and `.` ones; mixing absolute and relative paths raises `ValueError` |

### Normalising and inspecting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `posixpath.normpath(path)` | O(L) | O(L) | Lexical: `..` removes the component before it even when that is a symlink |
| `posixpath.normcase(s)` | O(1) | O(1) | Returns the argument itself, on macOS too |
| `posixpath.isabs(s)` | O(1) | O(1) | Checks for a leading `/` |
| `posixpath.expandvars(path)` | O(L + V) | O(L + V) | `$name` and `${name}`; an unknown name is left as it is. Releases before 3.14.1, 3.13.10, 3.12.13, 3.11.15 and 3.10.20 rebuild the path for each substitution: O(e·(L + V)) for e substitutions |
| `posixpath.expanduser(path)` | O(L + H) | O(L + H) | `~` is `HOME`; `~user`, and `~` with `HOME` unset, ask the password database, at whatever that backend costs. Windows has no `pwd` module, and returns those unchanged |

### Resolving against the filesystem

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `posixpath.abspath(path)` | O(L + C) | O(L + C) | One `os.getcwd()` for a relative path and none for an absolute one, then `normpath()`; no stat |
| `posixpath.relpath(path, start=os.curdir)` | O(L + S + C) | O(L + S + C) | An `abspath()` of each argument, compared component by component |
| `posixpath.realpath(path, *, strict=False)` | O(k·R) | O((j + 1)·R) | One `os.lstat()` per named component and one `os.readlink()` per symlink. Each component builds the resolved path so far as a new string, so a path of very many components is quadratic. A missing component does not end the walk: the components after it are lstat'ed too |
| `posixpath.realpath(path, *, strict=True)` | O(k·R) | O((j + 1)·R) | Raises the first error instead of walking past it; `strict=ALLOW_MISSING` walks past a missing component and raises any other error |
| `posixpath.ismount(path)` | O(L) from 3.13 when `path/..` can be lstat'ed; otherwise O(k·R) | O(L) from 3.13 when `path/..` can be lstat'ed; otherwise O((j + 1)·R) | 3.13+: an `os.lstat()` of the path and one of `path/..`, with a `realpath()` of `path/..` only if that fails, as it does for a regular file or a directory without search permission. Through 3.12 the parent goes through `realpath()` after the initial checks pass |

### Predicates and metadata

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `posixpath.exists(path)`, `posixpath.isdir(path)`, `posixpath.isfile(path)` | O(1) | O(1) | One `os.stat()` |
| `posixpath.islink(path)`, `posixpath.lexists(path)` | O(1) | O(1) | One `os.lstat()` |
| `posixpath.isjunction(path)` | O(1) | O(1) | 3.12+; `False`, without the filesystem |
| `posixpath.isdevdrive(path)` | O(1) | O(1) | 3.13+; `False`, without the filesystem |
| `posixpath.getsize(path)`, `posixpath.getmtime(path)`, `posixpath.getatime(path)`, `posixpath.getctime(path)` | O(1) | O(1) | One `os.stat()` each |
| `posixpath.samefile(f1, f2)` | O(1) | O(1) | Two `os.stat()` calls |
| `posixpath.sameopenfile(fp1, fp2)` | O(1) | O(1) | Two `os.fstat()` calls |
| `posixpath.samestat(s1, s2)` | O(1) | O(1) | Compares two results already fetched |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `posixpath.sep`, `posixpath.altsep`, `posixpath.curdir`, `posixpath.pardir`, `posixpath.extsep`, `posixpath.pathsep`, `posixpath.defpath`, `posixpath.devnull` | O(1) | O(1) | `'/'`, `None`, `'.'`, `'..'`, `'.'`, `':'`, `'/bin:/usr/bin'` and `'/dev/null'`, on every platform |
| `posixpath.supports_unicode_filenames` | O(1) | O(1) | `True` on macOS, `False` elsewhere |
| `posixpath.ALLOW_MISSING` | O(1) | O(1) | The `strict=` value for `realpath()` that tolerates a missing component only |

## Paths as Strings

Everything in the first two tables but `expanduser()` works on the string alone and never asks
the filesystem, so a path that does not exist splits, joins and normalises like one that does.
Each is linear in its arguments, except `join()` of bytes, and `splitdrive()`, `normcase()` and
`isabs()` do not read the whole path at all.

```python
import posixpath

path = "/srv/app/../data//report.tar.gz"
assert posixpath.split(path) == ("/srv/app/../data", "report.tar.gz")  # O(L)
assert posixpath.splitext(path)[1] == ".gz"  # O(L)
assert posixpath.normpath(path) == "/srv/data/report.tar.gz"  # O(L) - no filesystem

assert posixpath.join("srv", "app", "data") == "srv/app/data"  # O(n + L)
assert posixpath.join("srv", "/etc", "hosts") == "/etc/hosts"  # an absolute argument resets

assert posixpath.normcase(path) is path  # O(1) - returned unchanged
assert posixpath.isabs(path) and not posixpath.isabs("srv")  # O(1)
```

## Resolving a Path

`realpath()` is the one function here whose cost the argument does not show. It lstats every
component, and each symlink it meets splices its target into the components still to walk, so two
arguments that resolve to the same path can cost very differently. When the links do not matter,
`abspath()` gives the lexical answer from the string and the working directory alone.

```python
import os
import posixpath
import tempfile

with tempfile.TemporaryDirectory() as root:
    root = posixpath.realpath(root)  # O(k·R)
    os.makedirs(posixpath.join(root, "data", "2024"))
    os.symlink(posixpath.join(root, "data", "2024"), posixpath.join(root, "current"))

    via_link = posixpath.join(root, "current", "..", "notes")
    assert posixpath.abspath(via_link) == posixpath.join(root, "notes")  # O(L + C) - lexical
    assert posixpath.realpath(via_link) == posixpath.join(root, "data", "notes")  # O(k·R)

    missing = posixpath.join(root, "data", "a", "b")
    assert posixpath.realpath(missing) == missing  # walks past the missing components
    try:
        posixpath.realpath(missing, strict=True)  # raises at "a"
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("a missing path resolved under strict=True")

    assert not posixpath.ismount(root)  # O(L) from 3.13 - two lstats
assert posixpath.ismount("/")
```

## Expanding Variables and the Home Directory

On the releases its row names, `expandvars()` substitutes every `$name` and `${name}` it can
resolve in one pass, so its cost follows the result, which can be far longer than the argument. `expanduser()` reads `HOME` for a
bare `~`; `~user` is a password-database lookup.

```python
import os
import posixpath

os.environ["DATA"] = "/srv/data"
os.environ["HOME"] = "/home/me"
os.environ.pop("NO_SUCH_NAME", None)

expanded = posixpath.expandvars("$DATA/logs:${DATA}/tmp:$NO_SUCH_NAME")  # O(L + V)
assert expanded == "/srv/data/logs:/srv/data/tmp:$NO_SUCH_NAME"
assert posixpath.expanduser("~/notes") == "/home/me/notes"  # O(L + H)
assert posixpath.expanduser("notes/~") == "notes/~"  # only a leading ~ expands
```

## Common Patterns

### Comparing Paths

`commonpath()` compares whole components; `commonprefix()` compares characters and can stop
mid-name. `relpath()` takes an `abspath()` of both arguments, so it works from the strings and the
working directory, never from what is on disk.

```python
import posixpath

paths = ["/srv/app/src/a.py", "/srv/app/src/b.py", "/srv/application/c.py"]
assert posixpath.commonpath(paths) == "/srv"  # O(n + B) - whole components
assert posixpath.commonprefix(paths) == "/srv/app"  # O(n + B) - stops mid-component

assert posixpath.relpath("/srv/app/src/a.py", "/srv/app/tests") == "../src/a.py"  # O(L + S + C)

try:
    posixpath.commonpath(["/srv", "srv"])
except ValueError as error:
    assert "absolute and relative" in str(error)
else:
    raise AssertionError("an absolute and a relative path were compared")
```

## Performance Best Practices

✅ **Do**:

- Use `normpath()` or `abspath()` when symlinks do not matter: they are linear in the string and
  ask the filesystem for nothing more than the working directory
- Use `commonpath()` to find a shared directory

❌ **Avoid**:

- `realpath()` where `abspath()` will do: it makes a system call per component, and its string
  work is quadratic in a path of very many components
- `commonprefix()` to find a shared directory: it compares characters and can stop mid-component
- `join()` of many bytes arguments in one call, which copies the result per argument

## Version Notes

- **Python 3.12+**: adds `splitroot()` and `isjunction()`
- **Python 3.13+**: adds `isdevdrive()`. `ismount()` lstats `path/..` directly and runs
  `realpath()` only when that fails, so a directory that can be searched costs two lstats
- **Python 3.14.1+**, also 3.13.10, 3.12.13, 3.11.15 and 3.10.20: `expandvars()` is one pass,
  O(L + V); earlier releases are O(e·(L + V)) for e substitutions
- **Python 3.13.4+**, also 3.10.18, 3.11.13 and 3.12.11: adds `ALLOW_MISSING`
- **All Python 3**: importable on every platform; on Windows the string functions give the same
  results at the same bounds

## Related Modules

- **[os](os.md)** - `os.path` is this module on POSIX, and the os page prices it generically
- **[genericpath](genericpath.md)** - the stat-based predicates and `commonprefix()` this module
  re-exports
- **[ntpath](ntpath.md)** - the Windows counterpart, `os.path` there
- **[pathlib](pathlib.md)** - object-oriented POSIX paths with `PurePosixPath`
