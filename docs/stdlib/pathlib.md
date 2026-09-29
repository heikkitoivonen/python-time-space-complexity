# pathlib Module Complexity

The `pathlib` module wraps filesystem paths in objects. It has two halves: pure paths, which are
string manipulation with a path-shaped API and never touch the filesystem, and concrete `Path`
objects, which add the operations that make system calls. Most of the cost of the second half is
the syscalls themselves; most of the cost of the first is building and parsing strings.

`n` is the components in a path and `L` its characters, and `c` is the characters in its final
component. `s` is the segments a path was built from: from 3.12 a path keeps its constructor's
arguments unparsed, and a path joined onto another keeps all of that path's segments as well as its
own. For directory work, `w` is the entries in one directory (the widest, where an operation opens
several), `E` the entries examined across every directory an operation opens, and `P` the total length of the directory paths a walk has queued but not yet opened. `b` is
bytes of file content, and `k` the directories `mkdir(parents=True)` has to create. A syscall
counts as O(1), as on the [os](os.md) page: the kernel still resolves a path component by
component, but that is not what a caller chooses between. Glob patterns are treated as fixed size.
A pure-path bound assumes the path is already parsed; from 3.12 parsing is deferred, and the first
operation that needs it pays O(L) once.

## Complexity Reference

### PurePath

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pathlib.PurePath(*pathsegments)`, `pathlib.PurePosixPath(*pathsegments)`, `pathlib.PureWindowsPath(*pathsegments)` | O(L); O(s) from 3.12 | O(L); O(s) from 3.12 | From 3.12 the segments are stored and parsed on first use; either flavour works on any platform |
| `path / segment`, `PurePath.joinpath(*pathsegments)` | O(L); O(s) from 3.12 | O(L); O(s) from 3.12 | From 3.12 the new path copies every segment of the old one, so a path grown one name at a time pays for all the names before it |
| `PurePath.with_segments(*pathsegments)` | O(s) | O(s) | Python 3.12+; builds a path of the same type, and every derived path goes through it |
| `PurePath.parts` | O(n) | O(n) | A fresh tuple on every access from 3.12; cached after the first before that |
| `PurePath.parent` | O(L) | O(L) | A new path |
| `PurePath.parents` | O(1) | O(1) | A lazy sequence: `parents[i]` is O(L), and `list(parents)` is O(n·L) |
| `PurePath.name`, `PurePath.anchor`, `PurePath.drive`, `PurePath.root` | O(1) | O(1) | Read from the parsed path |
| `PurePath.stem`, `PurePath.suffix`, `PurePath.suffixes` | O(c) | O(c) | Sliced from the final component |
| `PurePath.with_name(name)`, `PurePath.with_stem(stem)`, `PurePath.with_suffix(suffix)` | O(L) | O(L) | A new path |
| `PurePath.relative_to(other)` | O(L); O(n·L) from 3.12 | O(L); O(n·L) on 3.12 | From 3.12 each ancestor is compared by building its string; 3.12 also lists every ancestor of `other`. Bounds are for the default `walk_up=False` |
| `PurePath.is_relative_to(other)` | O(L); O(n·L) from 3.12 | O(L) | The same search as `relative_to()` |
| `PurePath.match(pattern)`, `PurePath.full_match(pattern)` | O(L) | O(L) | `full_match()` is Python 3.13+ |
| `str(path)`, `PurePath.as_posix()` | O(L) | O(L) | `str()` is cached after its first call |
| `PurePath.as_uri()` | O(L) | O(L) | Deprecated on `PurePath` in 3.14; call it on a `Path` |
| `PurePath.is_absolute()` | O(1) | O(1) | Reads the anchor |
| `PurePath.is_reserved()` | O(L) | O(L) | Windows names only; deprecated in 3.13, which also made it check every component rather than the final one |
| `PurePath.parser` | O(1) | O(1) | Python 3.13+; the `posixpath` or `ntpath` module behind the flavour |

### Path

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pathlib.Path(*pathsegments)`, `pathlib.PosixPath(*pathsegments)`, `pathlib.WindowsPath(*pathsegments)` | O(L); O(s) from 3.12 | O(L); O(s) from 3.12 | As `PurePath`; `Path()` builds the running platform's flavour, and the other flavour cannot be built |
| `Path.cwd()`, `Path.home()` | O(L) | O(L) | L = length of the directory's path |
| `Path.absolute()` | O(L) | O(L) | Joins onto the working directory; no stat |
| `Path.expanduser()` | O(L) | O(L) | `~user` is looked up in the user database |
| `Path.resolve(strict=False)` | O(n·L) | O(L) | One lstat per component, each on the path so far built as a new string; n and L include every symlink target spliced into the path |
| `Path.stat()`, `Path.lstat()` | O(1) | O(1) | One syscall |
| `Path.exists()`, `Path.is_file()`, `Path.is_dir()`, `Path.is_symlink()`, `Path.is_socket()`, `Path.is_fifo()`, `Path.is_block_device()`, `Path.is_char_device()` | O(1) | O(1) | One stat call each, an lstat for `is_symlink()`; the directory holding the path is not read |
| `Path.is_junction()` | O(1) | O(1) | Python 3.12+; always `False` off Windows |
| `Path.is_mount()` | O(1); O(n·L) on 3.12 | O(1); O(L) on 3.12 | Stats the path and its parent; 3.12 resolves the parent instead, as `resolve()` does |
| `Path.samefile(other)` | O(1) | O(1) | Two stat calls |
| `Path.owner()`, `Path.group()` | O(1) | O(1) | One stat call plus a user- or group-database lookup |
| `Path.info` | O(1) | O(1) | Python 3.14+; a `PathInfo` cached on the path, see below |
| `Path.as_uri()`, `Path.from_uri(uri)` | O(L) | O(L) | `from_uri()` is Python 3.13+ |

### Directories

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Path.iterdir()` | O(w) | O(w) | The whole directory is read before the first item: when `iterdir()` is called from 3.13, at the first `next()` before |
| `Path.glob(pattern)` | O(E) | O(w) | For a pattern without `**`; E counts every entry scanned, matching or not |
| `Path.glob('**/' + pattern)`, `Path.rglob(pattern)` | O(E) | O(w + P); O(A + Y) through 3.11 | `rglob(pattern)` is `glob('**/' + pattern)`. Through 3.11 it holds the listing of every directory on the branch being scanned (A = the total length of those entries' paths) and every path it has yielded (Y = their total length); bounds are for one `**` |
| `Path.walk(top_down=True, on_error=None, follow_symlinks=False)` | O(E) | O(w + P) | Python 3.12+; `top_down=False` also holds every ancestor's listing until its subtree is done |
| `Path.mkdir(mode=0o777, parents=False, exist_ok=False)` | O(1); O(k·L) with `parents=True` | O(1); O(k·L) with `parents=True` | Recurses once per missing component, like `os.makedirs()` |
| `Path.rmdir()` | O(1) | O(1) | The directory must be empty |

### Files and links

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Path.open(mode='r', buffering=-1, encoding=None, errors=None, newline=None)` | O(1) | O(1) | Opens the file as `open()` does |
| `Path.read_text(encoding=None, errors=None)`, `Path.read_bytes()` | O(b) | O(b) | The whole file is held |
| `Path.write_text(data, encoding=None, errors=None, newline=None)` | O(b) | O(b) | The string is encoded whole before it is written |
| `Path.write_bytes(data)` | O(b) | O(1) | Writes the buffer it is given without copying it |
| `Path.touch()`, `Path.unlink()` | O(1) | O(1) | |
| `Path.rename(target)`, `Path.replace(target)` | O(1) | O(1) | One rename; neither copies across filesystems |
| `Path.symlink_to(target)`, `Path.hardlink_to(target)` | O(1) | O(1) | |
| `Path.link_to(target)` | O(1) | O(1) | Removed in 3.12; `hardlink_to()` takes its arguments the other way round |
| `Path.readlink()` | O(L) | O(L) | L = length of the link's target |
| `Path.chmod(mode)`, `Path.lchmod(mode)` | O(1) | O(1) | |
| `Path.copy(target)`, `Path.copy_into(target_dir)` | O(b); O(E + b) for a directory | O(1) for a file | Python 3.14+; a file is streamed, a directory copied entry by entry |
| `Path.move(target)`, `Path.move_into(target_dir)` | O(1) | O(1) | Python 3.14+; a rename within one filesystem; across two, a copy and delete at `copy()`'s cost |

### PathInfo

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pathlib.types`, `pathlib.types.PathInfo` | O(1) | O(1) | Python 3.14+; the protocol `Path.info` implements |
| `PathInfo.exists()`, `PathInfo.is_dir()`, `PathInfo.is_file()` | O(1) | O(1) | At most one stat call, on the first query, shared by the three and kept for the object's life; on Windows each of the three makes at most one query of its own, kept the same way. A path from `iterdir()` answers `is_dir()` and `is_file()` from its directory entry instead |
| `PathInfo.is_symlink()` | O(1) | O(1) | One lstat call, kept separately |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pathlib.UnsupportedOperation` | O(1) | O(1) | Python 3.13+; a `NotImplementedError`, raised for instance by building a `WindowsPath` on POSIX |

## Building Paths

### Construction Is Deferred From Python 3.12

Before 3.12 the constructor splits the string into components straight away. From 3.12 it keeps the
arguments and splits them on the first operation that needs it, caching the result, so a path that
is built and never inspected costs no more than holding its arguments.

```python
from pathlib import PurePosixPath

source = '/' + 'a' * 100_000
path = PurePosixPath(source)  # O(L); O(1) from 3.12 - nothing is parsed yet

text = str(path)  # O(L) - builds the string; from 3.12 the deferred parse too
assert str(path) is text  # O(1) - cached
```

### Joining Copies the Segments

From 3.12 a joined path keeps the unparsed segments of the path it was joined onto as well as its
own, and copies them. Joining onto a path built from one string is O(1); joining onto a path that
was itself grown one name at a time costs as many segments as that path already holds. Before 3.12
each join copies the parsed parts instead, O(L). On every version, then, a loop that extends one
path by a name per step is quadratic in the number of steps, and one `joinpath()` call is not.

```python
from pathlib import PurePosixPath

names = [f'd{index}' for index in range(100)]

# Grown in place: each step copies every segment before it - quadratic in the names
grown = PurePosixPath('/data')
for name in names:
    grown = grown / name

# Joined once: one path of 101 segments, O(s)
joined = PurePosixPath('/data').joinpath(*names)

assert grown == joined
assert len(joined.parts) == 102  # O(n)
```

## Pure Paths Never Touch the Filesystem

`PurePath` and its two flavours are string manipulation. None of their operations can fail because
a file is missing, and `PureWindowsPath` gives Windows semantics on any platform.

```python
from pathlib import PurePosixPath, PureWindowsPath

p = PurePosixPath('/nowhere/at/all/report.tar.gz')  # no such directory anywhere

assert p.name == 'report.tar.gz'         # O(1)
assert p.stem == 'report.tar'            # O(c)
assert p.suffixes == ['.tar', '.gz']     # O(c)
assert p.parts == ('/', 'nowhere', 'at', 'all', 'report.tar.gz')  # O(n)
assert p.with_suffix('.zip').name == 'report.tar.zip'  # O(L)
assert p.match('*.gz')                   # O(L)

assert PureWindowsPath('C:/Users/x').drive == 'C:'  # O(1)
assert PureWindowsPath('C:/Users/x').as_posix() == 'C:/Users/x'  # O(L)
```

## Components and Ancestors

### parts Is Rebuilt on Every Access From Python 3.12

Up to 3.11 `parts` is cached on the path after the first access. From 3.12 each access builds a
new tuple, so reading it in a loop pays O(n) every time round; read it once.

```python
from pathlib import PurePosixPath

p = PurePosixPath('/a/b/c/d/e/f.txt')

parts = p.parts  # O(n), and again on every access from 3.12
first, last = parts[0], parts[-1]
assert (first, last) == ('/', 'f.txt')
```

### parents Is Lazy

`parents` costs nothing to obtain, and `parents[i]` builds only the path it returns. Materialising
the whole sequence is O(n·L), because each of the n ancestors is a path of its own.

```python
from pathlib import PurePosixPath

p = PurePosixPath('/a/b/c/d.txt')

ancestors = p.parents  # O(1)
assert ancestors[0] == PurePosixPath('/a/b/c')  # O(L)
assert list(ancestors) == [
    PurePosixPath('/a/b/c'), PurePosixPath('/a/b'), PurePosixPath('/a'), PurePosixPath('/'),
]  # O(n·L)
```

### relative_to() Is Quadratic From Python 3.12

From 3.12 `relative_to()` and `is_relative_to()` look for `other` among the path's ancestors, and
compare each candidate by building its string: O(n·L), which with components of similar length is
quadratic in the depth. Before 3.12 it is one slice comparison. On 3.12 alone `relative_to()` also
lists every ancestor of `other` before it starts, so a deep base costs quadratic space too.

```python
from pathlib import PurePosixPath

deep = PurePosixPath('/' + '/'.join(f'd{i}' for i in range(200)) + '/f.txt')

tail = deep.relative_to('/d0')  # O(n·L) from 3.12, O(L) before
assert tail.parts[0] == 'd1'
assert deep.is_relative_to('/d0')  # the same search
```

## Querying the Filesystem

### One Stat Call per Predicate

Each predicate makes one stat call, whatever the path's length or the size of the directory
holding it. Asking three questions of the same path makes three calls.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'file.txt'
    path.write_text('contents')  # O(b)

    assert path.exists()        # O(1) - one stat
    assert path.is_file()       # O(1) - another
    assert not path.is_dir()    # O(1) - and another
    assert path.stat().st_size == 8  # O(1)
    assert path.samefile(Path(tmp, 'file.txt'))  # O(1) - two stats
```

### Path.info Caches the Answer (Python 3.14)

On a `Path` you build, `Path.info` takes one stat call on its first query and answers `exists()`,
`is_file()` and `is_dir()` from it after that; `is_symlink()` takes one lstat, cached the same way.
On Windows each of the three makes at most one query of its own, cached the same way.
A path yielded by `iterdir()` answers `is_file()`, `is_dir()` and `is_symlink()` from the directory
entry it came from, which usually needs no call at all. The cache lives as long as the `Path` object, so a long-lived `Path` whose file changes underneath it keeps
answering from the old stat. Build a fresh `Path` where that matters.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'report.txt'
    path.write_text('contents')

    info = path.info  # O(1)
    assert info.exists() and info.is_file() and not info.is_dir()  # one stat between them on POSIX

    path.unlink()
    assert info.exists()  # still the cached answer
    assert not Path(tmp, 'report.txt').info.exists()  # a fresh Path stats again
```

## Listing Directories

### iterdir() Reads the Whole Directory

`iterdir()` returns an iterator, but not a streaming one: the directory is read in full before the
first item is produced. Iterating instead of calling `list()` avoids holding the `Path` objects, not
the listing they are built from, so taking the first entry of a large directory still costs O(w).

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    for index in range(5):
        (base / f'f{index}.txt').touch()

    first = next(base.iterdir())  # O(w) - the whole listing is read first
    assert first.parent == base
    assert len(list(base.iterdir())) == 5  # O(w)
```

!!! warning "A big directory costs memory even if you stop early"
    `next(path.iterdir())` reads the whole directory. Where that matters, `os.scandir()` is the
    streaming alternative - see [os](os.md).

### glob() Scans Entries, Not Matches

`glob()` pays for every entry in every directory the pattern opens, whether or not it matches, and
lists each directory whole before yielding from it. A wildcard pattern that finds one file in a
directory of ten thousand still reads ten thousand names.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    for index in range(100):
        (base / f'f{index}.dat').touch()
    (base / 'needle.txt').touch()

    matches = list(base.glob('*.txt'))  # O(E) = 101 entries scanned for one match
    assert matches == [base / 'needle.txt']
```

### Recursive Globs and walk()

`rglob(pattern)` is `glob('**/' + pattern)`, and both walk the whole tree below the starting point.
From 3.12 they hold one directory's listing and the directories still queued, so iterating the
results costs no more than the walk. Through 3.11 they also keep the listing of every directory on
the branch being scanned and every path already yielded, to drop duplicates: there, iterating saves
no memory over `list()`. `walk()` holds the same listing and queue, plus, when walking bottom-up,
each ancestor's listing until its subtree is done.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    (base / 'a' / 'b').mkdir(parents=True)  # O(k·L)
    (base / 'a' / 'x.py').touch()
    (base / 'a' / 'b' / 'y.py').touch()
    (base / 'z.txt').touch()

    found = sorted(base.rglob('*.py'))  # O(E) - every entry in the tree, then the sort
    assert found == sorted(base.glob('**/*.py'))
    assert sorted(p.name for p in found) == ['x.py', 'y.py']

    visited = [(d.name, sorted(files)) for d, _, files in base.walk()]  # O(E) + sorts, 3.12+
    assert ('b', ['y.py']) in visited
```

## Reading, Writing and Copying

### Whole-File Reads and Writes

`read_text()` and `read_bytes()` return the whole file, so they hold O(b). `write_text()` encodes
its string whole before writing it; `write_bytes()` writes the buffer it is given without copying.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'data.txt'

    path.write_text('x' * 1000, encoding='utf-8')  # O(b) time and memory
    assert path.read_text(encoding='utf-8') == 'x' * 1000  # O(b)

    path.write_bytes(b'\x00\xff' * 500)  # O(b) time, O(1) extra memory
    assert len(path.read_bytes()) == 1000  # O(b)
```

### Renaming Is a Syscall, Not a Copy

`rename()` and `replace()` are one syscall each within a filesystem and never copy; across
filesystems they fail rather than fall back. `mkdir(parents=True)` recurses once per missing
component.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    (base / 'a' / 'b' / 'c').mkdir(parents=True)  # O(k·L) for k missing components

    source = base / 'a' / 'b' / 'c' / 'f.txt'
    source.write_text('payload')
    moved = source.rename(base / 'f.txt')  # O(1)
    assert moved.read_text() == 'payload' and not source.exists()

    moved.unlink()  # O(1)
    (base / 'a' / 'b' / 'c').rmdir()  # O(1) - it must be empty
```

### copy() and move() (Python 3.14)

`copy()` streams a file, so it is O(b) in time and O(1) in memory however large the file is; a
directory is copied entry by entry. `move()` within one filesystem is a rename and costs neither.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / 'report.txt'
    source.write_text('contents')

    backup = source.copy(Path(tmp) / 'backup.txt')  # O(b) time, O(1) memory
    archive = source.move(Path(tmp) / 'archive.txt')  # O(1) on the same filesystem

    assert backup.read_text() == archive.read_text() == 'contents'
    assert not source.exists()
```

## Common Patterns

### Processing a Tree

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    (base / 'pkg').mkdir()
    (base / 'pkg' / 'a.py').write_text('print(1)\n')
    (base / 'b.py').write_text('x = 1\ny = 2\n')

    lines = 0
    for file in base.rglob('*.py'):  # O(E) to find the files
        lines += len(file.read_text().splitlines())  # O(b) per file

    assert lines == 3
```

### Comparing With os.path

The filesystem calls cost the same either way. The string handling does not: `os.path.join()`
always builds the joined string, while `/` leaves the string for the first operation that needs it,
and from 3.12 leaves the parsing too.

```python
import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / 'file.txt'  # O(L); O(s) from 3.12
    s = os.path.join(tmp, 'file.txt')  # O(L)

    assert str(p) == s  # O(L) - the string is built here, on first use
    assert not p.exists() and not os.path.exists(s)  # O(1) each - one stat
```

## Performance Best Practices

✅ **Do**:

- Build a deep path with one `joinpath(*names)` call rather than a `/` per name in a loop
- Read `parts` once into a local instead of in a loop
- Use `Path.info` on 3.14 to ask several questions of one file for one stat call (one per question on Windows)
- Glob once and reuse the list, rather than globbing the same directory repeatedly
- Use `os.scandir()` for a huge directory you only need the start of

❌ **Avoid**:

- `next(path.iterdir())` to test whether a large directory is empty - it reads the whole directory
- `relative_to()` on deep paths in a hot loop on 3.12+, where it is quadratic in the depth
- Iterating `rglob()` over a big tree on 3.10 and 3.11 in the belief that it saves memory - it keeps every match
- `read_text()` on a file too large to hold; open it and read it in chunks

## Version Notes

- **Python 3.12+**: `Path.walk()`, `Path.is_junction()` and `PurePath.with_segments()` added;
  construction and joining store segments and defer parsing to first use; `parts` is rebuilt on
  every access; `relative_to()` and `is_relative_to()` become O(n·L); recursive globs stop holding
  every match and every ancestor's listing; `Path.link_to()` removed
- **Python 3.13+**: `Path.from_uri()`, `PurePath.full_match()`, `PurePath.parser` and
  `UnsupportedOperation` added; `iterdir()` reads the directory when it is called rather than at
  the first `next()`; a pattern ending in `**` also yields files; `PurePath.is_reserved()`
  deprecated, and checks every component
- **Python 3.14+**: `Path.copy()`, `Path.copy_into()`, `Path.move()`, `Path.move_into()`,
  `Path.info` and `pathlib.types` added; `PurePath.as_uri()` deprecated in favour of
  `Path.as_uri()`

## Related Modules

- **[os](os.md)** - the syscalls underneath, and `os.scandir()` for streaming a directory
- **[glob](glob.md)** - the same pattern matching over strings
- **[shutil](shutil.md)** - `rmtree()` and `copytree()` for whole trees
