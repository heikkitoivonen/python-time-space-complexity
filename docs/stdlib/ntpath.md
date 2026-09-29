# ntpath Module Complexity

The `ntpath` module is `os.path` on Windows: string operations on Windows paths, plus the few
functions that ask the filesystem. It is pure Python and imports on every platform, so Linux and
macOS code can use it to take Windows paths apart. On Windows it binds C helpers from
[`nt`](nt.md) at import for several functions; where `nt` is absent, and on older versions, a
Python fallback runs instead. For most functions the two share a bound. `normpath()` does not,
nor do the functions that call it, and the functions that resolve a path change what they do: off
Windows they answer from the string and the working directory alone, and `realpath()` resolves
nothing.

`L` is the length of a path argument in characters, and of all of them together where a function
takes several, as `join()` does; `n` is the number of arguments `join()` takes. `S` is the length
of `relpath()`'s `start`, `B` the characters of every path given to `commonpath()` or
`commonprefix()`, and `C` the length of the working directory. `V` is the characters `expandvars()` substitutes in and `H` the home directory
`expanduser()` splices in. For `realpath()` on Windows, `F` is the length of the path it resolves
to, and `m` the trailing components of a path that it cannot open: ones that do not exist, or
that Windows refuses with an error such as access denied or a sharing violation. `W` is the
characters `realpath()` reads out of links itself, which it does only for a link Windows will not
resolve: the length of every path it reaches that way, so it grows with the number of links as
well as with their length. A system call counts as O(1), as it does on the [os page](os.md).
"Windows" below means a Windows build, where `nt` exists; "elsewhere" means every other platform.

## Complexity Reference

### Splitting and joining

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ntpath.splitroot(p)` | O(L) | O(L) | 3.12+; `(drive, root, tail)`. On Windows from 3.13 it is `nt._path_splitroot_ex()`, elsewhere Python, with the same bound |
| `ntpath.splitdrive(p)` | O(L) | O(L) | A drive letter or a UNC share, such as `\\server\share` |
| `ntpath.split(p)` | O(L) | O(L) | `(head, tail)` at the last separator |
| `ntpath.basename(p)`, `ntpath.dirname(p)` | O(L) | O(L) | Each is one `split()` |
| `ntpath.splitext(p)` | O(L) | O(L) | |
| `ntpath.join(path, *paths)` | O(L); O(n·L) for bytes | O(L) | An argument on another drive discards everything before it; one with a root but no drive keeps only the drive. Bytes has no in-place concatenation, so each argument copies the result so far |
| `ntpath.commonprefix(list)` | O(B) | O(B) | Character by character and case-sensitive, so it can end mid-component |
| `ntpath.commonpath(paths)` | O(B) | O(B) | Whole components, compared case-insensitively; the result keeps the first path's case |

### Normalising and inspecting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ntpath.normpath(path)` | O(L) | O(L) | On Windows from 3.11 `nt._path_normpath()`, one pass. On Windows 3.10, and on every version elsewhere, a Python loop that deletes list items in place: O(L²) for a path of many `.` or `..` components |
| `ntpath.normcase(path)` | O(L) | O(L) | Lower-cases and turns `/` into `\`; through `LCMapStringEx` on Windows, `str.lower()` elsewhere |
| `ntpath.isabs(path)` | O(1) | O(1) | Reads the first three characters from 3.11; 3.10 rewrites the separators of the whole path first, O(L). From 3.13 a rooted path with no drive, such as `\x`, is not absolute |
| `ntpath.isreserved(path)` | O(L) | O(L) | 3.13+; checks each component's name and characters, without the filesystem |
| `ntpath.expandvars(path)` | O(L + V) | O(L + V) | `%name%`, `$name` and `${name}`; an unknown name is left as it is |
| `ntpath.expanduser(path)` | O(L + H) | O(L + H) | The home directory comes from `USERPROFILE`, or `HOMEDRIVE` and `HOMEPATH`; `~user` is guessed as a sibling of it, with no account lookup |

### Resolving against the filesystem

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ntpath.abspath(path)` | O(L + C) | O(L + C) | Windows: `normpath()`, then one `nt._getfullpathname()` (on 3.10 the call first, then `normpath()`). Elsewhere: `os.getcwd()` joined on for a relative path, then the Python `normpath()`, with its quadratic case |
| `ntpath.relpath(path, start=os.curdir)` | O(L + S + C) | O(L + S + C) | An `abspath()` of each argument; raises `ValueError` for two different drives. Where `normpath()` is Python (Windows 3.10, and every version elsewhere) it runs over each argument, with its quadratic case |
| `ntpath.realpath(path)`, Windows, a path it can open | O(L + C + F) | O(L + C + F) | Two `nt._getfinalpathname()` calls, however many components the path has and through as many links as Windows follows in one open; there is no lstat per component. On 3.10 the `normpath()` it starts with is O(L²) for many `.` or `..` components |
| `ntpath.realpath(path)`, Windows, `m` trailing components it cannot open | O(m·(L + C) + F) | O(L + C + F) | One `nt._getfinalpathname()` and one `nt.readlink()` per such component, walking up until a prefix opens; the result is that prefix resolved, with the tail joined on. None of the components may be a link Windows will not resolve (next row). 3.10's first `normpath()` as above |
| `ntpath.realpath(path)`, Windows, through a link Windows will not resolve | O(m·(L + C) + F + W) | O(L + C + F + W) | A link to a missing target, a loop, or a chain longer than Windows follows in one open. The walk up stops at the link, and `realpath()` follows it in Python: one `nt.readlink()` per link, every path it reaches kept in a set so that a loop ends. The result is the last target reached, not resolved further, with the tail joined on. On 3.10 each relative symlink's target is also normalised by the Python `normpath()`, quadratic in that path's length for many `.` or `..` components |
| `ntpath.realpath(path, strict=True)`, Windows | O(L + C + F) | O(L + C + F) | No walk: the first component that fails to open raises. `strict=ntpath.ALLOW_MISSING` walks a missing tail as above and raises for any other error. 3.10's first `normpath()` as above |
| `ntpath.realpath(path)`, elsewhere | O(L + C) | O(L + C) | It is `abspath()`, with the Python `normpath()`'s quadratic case: no link is resolved and the filesystem is not asked |
| `ntpath.ismount(path)` | O(L + C) | O(L + C) | Windows: an `abspath()`, then one `nt._getvolumepathname()` unless the path is a drive root or share root; no `realpath()`, on every supported version. Elsewhere: an `abspath()`, with the Python `normpath()`'s quadratic case, then those two roots answer `True` and every other path `False`, without the filesystem |
| `ntpath.isdevdrive(path)` | O(L + C) | O(L + C) | 3.12+. Windows: an `abspath()`, then one volume query, `False` if it fails. Elsewhere: O(1), always `False` |

### Predicates and metadata

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ntpath.exists(path)`, `ntpath.isdir(path)`, `ntpath.isfile(path)`, `ntpath.islink(path)` | O(1) | O(1) | Windows 3.12+: the C helpers `nt._path_exists()` and so on, which do not go through `os.stat()`. Otherwise one `os.stat()`, or `os.lstat()` for `islink()` |
| `ntpath.lexists(path)` | O(1) | O(1) | Windows 3.13+: `nt._path_lexists()`. Otherwise one `os.lstat()` |
| `ntpath.isjunction(path)` | O(1) | O(1) | 3.12+. Windows: one `os.lstat()` on 3.12, `nt._path_isjunction()` from 3.13. Elsewhere: `False`, without the filesystem |
| `ntpath.getsize(path)`, `ntpath.getmtime(path)`, `ntpath.getatime(path)`, `ntpath.getctime(path)` | O(1) | O(1) | One `os.stat()` each |
| `ntpath.samefile(f1, f2)` | O(1) | O(1) | Two `os.stat()` calls |
| `ntpath.sameopenfile(fp1, fp2)` | O(1) | O(1) | Two `os.fstat()` calls |
| `ntpath.samestat(s1, s2)` | O(1) | O(1) | Compares two results already fetched |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ntpath.sep`, `ntpath.altsep`, `ntpath.curdir`, `ntpath.pardir`, `ntpath.extsep`, `ntpath.pathsep`, `ntpath.defpath`, `ntpath.devnull` | O(1) | O(1) | `'\\'`, `'/'`, `'.'`, `'..'`, `'.'`, `';'`, `'.;C:\\bin'` and `'nul'`, on every platform |
| `ntpath.supports_unicode_filenames` | O(1) | O(1) | `True` from 3.12; on 3.10 and 3.11 it is `True` on Windows and `False` elsewhere |
| `ntpath.ALLOW_MISSING` | O(1) | O(1) | The `strict=` value for `realpath()` that tolerates a missing tail only |

## Windows and Everywhere Else

The string functions split, join and test paths the same way on every platform, and at the same
bound: on Windows some of them are C, elsewhere they are Python, and both are linear in the path.
Only `normpath()`, below, and the functions that call it change their bound with the
implementation.

```python
import ntpath

path = r"\\server\share\dir\report.txt"
assert ntpath.splitdrive(path) == (r"\\server\share", r"\dir\report.txt")  # O(L)
assert ntpath.split(path) == (r"\\server\share\dir", "report.txt")  # O(L)
assert ntpath.splitext(path)[1] == ".txt"  # O(L)

assert ntpath.join("C:\\", "Users", "me") == r"C:\Users\me"  # O(L)
assert ntpath.join(r"C:\a", r"D:\b") == r"D:\b"  # another drive discards the prefix

assert ntpath.normcase("C:/Users/ME") == r"c:\users\me"  # O(L)
assert ntpath.isabs(r"C:\x") and not ntpath.isabs("x")  # O(1)
```

## Normalising a Path

`normpath()` on Windows from 3.11 is `nt._path_normpath()`, one pass in C. Where `nt` is not
there - on Windows 3.10, or `ntpath` imported on Linux or macOS - it is a Python loop that deletes
each `.` and each `..` pair from a list as it goes, and a path made of many of them costs O(L²).
`abspath()`, `relpath()`, `realpath()` and `ismount()` run that loop over their argument off
Windows, and `relpath()` and `realpath()` do on Windows 3.10, so they are quadratic there too.

```python
import ntpath

assert ntpath.normpath("C:/a/./b/../c") == r"C:\a\c"  # O(L)

dotted = "a" + "\\." * 1_000
assert ntpath.normpath(dotted) == "a"  # O(L) in C; O(L²) as the Python fallback
```

## Resolving a Path

`os.path.realpath()` on POSIX stats one component at a time, so its cost follows the path and
every symlink spliced into it. On Windows the kernel resolves the whole path when
`_getfinalpathname()` opens it, links and junctions included, so a path it can open costs the
same two calls however deep it is. Only a tail it cannot open is walked in Python: a missing one,
or an existing file or directory that refuses the open, such as one locked by the system or
denied to this user. `realpath()` strips one component at a time until what is left opens,
trying each prefix, and joins the tail back onto the prefix's resolved path.

A link Windows will not resolve is walked in Python too: one whose target is missing, a loop, or a
chain of more links than Windows follows in one open. When the walk up reaches such a link,
`realpath()` reads it and each link after it with `readlink()`, keeping every path it reaches so
that a loop ends, and returns the last target with the tail joined on. That cost follows the
chain, as it does on POSIX, and neither the argument nor the result shows it.

With `strict=True` there is no walk: the first failure raises. Off Windows there is nothing to
walk either, because `realpath()` is `abspath()` there.

```python
import ntpath
import os
import tempfile

with tempfile.TemporaryDirectory() as root:
    root = ntpath.realpath(root)  # O(L + C + F) - two calls
    deep = ntpath.join(root, *["d"] * 20)
    os.makedirs(deep)

    assert ntpath.realpath(deep) == deep  # O(L + C + F) - still two calls, at 20 levels

    missing = ntpath.join(deep, "a", "b", "c")
    assert ntpath.realpath(missing) == missing  # O(m·(L + C) + F) - m = 3, a call for each

    try:
        ntpath.realpath(missing, strict=True)  # O(L + C + F) - raises instead of walking
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("a missing path resolved under strict=True")
```

## Absolute Paths and Mount Points

On Windows `abspath()` is the string work and one `nt._getfullpathname()` call, and `ismount()`
adds one volume query to that. Off Windows `abspath()` joins `os.getcwd()` on instead, and
`ismount()` answers from the string alone: a drive root or a share root is a mount point and
nothing else is.

```python
import ntpath
import os

absolute = ntpath.abspath("file.txt")  # O(L + C) - one _getfullpathname()
assert absolute == ntpath.join(os.getcwd(), "file.txt")

assert ntpath.ismount(absolute[:3])  # O(L + C) - a drive root
assert not ntpath.ismount(absolute)  # one volume query
```

## Common Patterns

### Comparing Paths

`commonpath()` compares whole components without regard to case; `commonprefix()` compares
characters exactly. `relpath()` takes an `abspath()` of both arguments, and refuses two drives.

```python
import ntpath

paths = [r"C:\Proj\src\a.py", r"c:\proj\SRC\b.py", r"C:\Proj\tests\t.py"]
assert ntpath.commonpath(paths) == r"C:\Proj"  # O(B), in the first path's case
assert ntpath.commonprefix(paths) == ""  # O(B) - 'C' and 'c' already differ

assert ntpath.relpath(r"C:\Proj\src\a.py", r"C:\Proj\tests") == r"..\src\a.py"  # O(L + S + C)

try:
    ntpath.relpath(r"D:\data", r"C:\Proj")
except ValueError as error:
    assert "mount" in str(error)
else:
    raise AssertionError("a path on another drive was made relative")
```

## Performance Best Practices

✅ **Do**:

- Resolve paths that exist, that this process can open, and whose links Windows can follow:
  `realpath()` then costs two calls however deep the path is
- Use `ntpath` off Windows for Windows path strings, and nothing more: there `realpath()`,
  `ismount()` and `isdevdrive()` never consult the filesystem

❌ **Avoid**:

- `normpath()` on long untrusted paths where it runs as Python (Windows 3.10, or any version off
  Windows), and the functions that pass it their argument there: a path of many `.` or `..`
  components is quadratic
- `realpath()` on a path whose long tail does not exist yet, which costs a call per missing
  component; resolve the existing prefix and join the rest
- `realpath()` through dangling links or long chains of them, where it reads every link in the
  chain with its own `readlink()` call
- `commonprefix()` to find a shared directory: it compares characters, so it is case-sensitive
  where Windows is not, and can stop mid-component

## Version Notes

- **Python 3.11+**: `normpath()` on Windows runs through `nt._path_normpath()` in O(L); through
  3.10 it is Python and O(L²) for a path of many `.` or `..` components, and so is the
  `normpath()` that `realpath()` and `relpath()` start with. `isabs()` reads a three-character
  prefix instead of rewriting the separators of the whole path, so it is O(1)
- **Python 3.12+**: adds `splitroot()`, `isjunction()` and `isdevdrive()`
- **Python 3.13+**: adds `isreserved()`. `isabs()` no longer treats a rooted path without a drive,
  such as `\x`, as absolute
- **All Python 3**: importable on every platform; off Windows `realpath()` resolves nothing and
  `ismount()` recognises only drive and share roots

## Related Modules

- **[os](os.md)** - `os.path` is this module on Windows, and the os page prices it generically
- **[nt](nt.md)** - the C helpers `ntpath` binds on Windows
- **[posixpath](posixpath.md)** - the POSIX counterpart, `os.path` everywhere else
- **[pathlib](pathlib.md)** - object-oriented Windows paths with `PureWindowsPath`
