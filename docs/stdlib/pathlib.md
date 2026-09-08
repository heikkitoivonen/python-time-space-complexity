# Pathlib Module Complexity

The `pathlib` module provides an object-oriented approach to filesystem path handling.

## Complexity Reference

Unless a row says otherwise, n is the number of components in the path and the
bound covers one call on an already-parsed path. Nothing in the first table
touches the filesystem.

### Classes

| Name | Time | Space | Notes |
|------|------|-------|-------|
| `PurePath`, `PurePosixPath`, `PureWindowsPath` | O(n) | O(n) | Construction only; these never touch the filesystem |
| `Path`, `PosixPath`, `WindowsPath` | O(n) | O(n) | `Path()` returns the flavour matching the running platform |
| `UnsupportedOperation` | O(1) | O(1) | Python 3.13+; raised where a flavour has no such operation |

### Pure Path Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `PurePath(str)` | O(n) | O(n) | n = length of the string; from 3.12 both are O(1), the string being stored and parsed on first use |
| `path / segment`, `PurePath.joinpath()` | O(n) | O(n) | n = combined length; from 3.12 the segments are stored unparsed and the cost is deferred with the rest |
| `PurePath.parts` | O(n) | O(n) | Rebuilt on every access from 3.12; cached after the first before that |
| `PurePath.parent` | O(n) | O(n) | Builds a new path from the tail |
| `PurePath.parents` | O(1) | O(1) | A lazy sequence; `parents[i]` costs O(n - i) and `list(parents)` is O(n²) |
| `PurePath.name/stem/suffix/anchor/drive/root` | O(1) | O(1) | Read from the parsed path |
| `PurePath.suffixes` | O(m) | O(m) | m = length of the final component |
| `PurePath.with_name()`, `.with_stem()`, `.with_suffix()`, `.with_segments()` | O(n) | O(n) | `with_segments()` is 3.12+ |
| `PurePath.relative_to()`, `.is_relative_to()` | O(n²) | O(n) | O(n) before 3.12, which walks the parents of both paths |
| `PurePath.match()`, `.full_match()` | O(p + n) | O(1) | p = components in the pattern; `full_match()` is 3.13+ |
| `PurePath.as_posix()`, `str(path)` | O(n) | O(n) | The string is cached after the first build |
| `PurePath.as_uri()` | O(n) | O(n) | Return file:// URI; deprecated on `PurePath` in 3.14, so call it on a `Path` |
| `PurePath.is_absolute()` | O(1) | O(1) | Reads the anchor |
| `PurePath.is_reserved()` | O(1) | O(1) | Windows names only; deprecated in 3.13 |
| `PurePath.parser` | O(1) | O(1) | Python 3.13+; the `posixpath` or `ntpath` module behind this flavour |

### Filesystem Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Path.cwd()` | O(n) | O(n) | n = length of current directory |
| `Path.home()` | O(n) | O(n) | n = length of home directory |
| `Path.exists()` | O(1) | O(1) | One stat call |
| `Path.is_file()` | O(1) | O(1) | One stat call |
| `Path.is_dir()` | O(1) | O(1) | One stat call |
| `Path.is_symlink()` | O(1) | O(1) | One lstat call |
| `Path.is_junction()` | O(1) | O(1) | Python 3.12+; always False on POSIX |
| `Path.is_mount()` | O(1) | O(1) | Stats the path and its parent; on 3.12 it resolves the parent instead, at one lstat per component |
| `Path.is_socket()` | O(1) | O(1) | One stat call |
| `Path.is_fifo()` | O(1) | O(1) | One stat call |
| `Path.is_block_device()` | O(1) | O(1) | One stat call |
| `Path.is_char_device()` | O(1) | O(1) | One stat call |
| `Path.stat()` | O(1) | O(1) | Get file stats |
| `Path.lstat()` | O(1) | O(1) | Like stat but don't follow symlinks |
| `Path.info` | O(1) | O(1) | Python 3.14+; caches what it stats, so repeated queries cost one syscall between them |
| `Path.resolve()` | O(n) | O(n) | n = path components; one lstat each |
| `Path.absolute()` | O(n) | O(n) | Make absolute without resolving symlinks |
| `Path.expanduser()` | O(n) | O(n) | Expand ~ to home directory |
| `Path.iterdir()` | O(d) | O(d) | d = directory entries; the whole listing is read before the first item |
| `Path.walk()` | O(n) | O(w + d) | Python 3.12+; n = total entries, d = max depth, w = entries queued but not yet walked |
| `Path.glob(pattern)` | O(n) | O(w); O(w + d) with `**` | n = entries scanned, not entries matched; w = entries of the largest directory scanned, d = depth reached |
| `Path.rglob(pattern)` | O(n) | O(w + d) | `glob('**/' + pattern)`; n = entries in the tree, d = depth reached |
| `Path.mkdir()` | O(1) | O(1) | O(d) for d missing components with `parents=True` |
| `Path.touch()` | O(1) | O(1) | Create file or update timestamp |
| `Path.rename(target)` | O(1) | O(1) | Rename path |
| `Path.replace(target)` | O(1) | O(1) | Rename, overwriting target if exists |
| `Path.unlink()` | O(1) | O(1) | Delete file |
| `Path.rmdir()` | O(1) | O(1) | Delete empty directory |
| `Path.symlink_to(target)` | O(1) | O(1) | Create symlink |
| `Path.hardlink_to(target)` | O(1) | O(1) | Create hard link |
| `Path.link_to(target)` | O(1) | O(1) | Removed in 3.12; use `hardlink_to()`, whose arguments are the other way round |
| `Path.readlink()` | O(n) | O(n) | n = length of symlink target |
| `Path.chmod(mode)` | O(1) | O(1) | Change file mode |
| `Path.lchmod(mode)` | O(1) | O(1) | chmod without following symlinks |
| `Path.owner()` | O(1) | O(1) | One stat call plus a user-database lookup |
| `Path.group()` | O(1) | O(1) | One stat call plus a group-database lookup |
| `Path.samefile(other)` | O(1) | O(1) | Two stat calls |
| `Path.open(mode)` | O(1) | O(1) | Open file (returns file object) |
| `Path.read_text()` | O(n) | O(n) | Read file as text |
| `Path.read_bytes()` | O(n) | O(n) | Read file as bytes |
| `Path.write_text()` | O(n) | O(n) | Write text to file |
| `Path.write_bytes()` | O(n) | O(n) | Write bytes to file |
| `Path.copy(target)`, `.copy_into(dir)` | O(b) | O(1) | Python 3.14+; b = bytes copied, streamed rather than held |
| `Path.move(target)`, `.move_into(dir)` | O(1) | O(1) | Python 3.14+; O(b) across filesystems, where it copies and deletes |
| `Path.from_uri(uri)` | O(n) | O(n) | Create Path from URI (Python 3.13+) |

## Path Construction

### Time Complexity: O(n)

Where n = length of the path string.

```python
from pathlib import Path

# Simple path: O(n) in the length of the string
path = Path('/home/user/documents/file.txt')

# Relative path: O(n)
path = Path('docs/README.md')

# Current directory: O(n) in path length
cwd = Path.cwd()

# Home directory: O(n) in path length
home = Path.home()
```

### Space Complexity: O(n)

```python
from pathlib import Path

# Stores the path string
path = Path('/' + 'a' * 10000)  # O(n) space
```

### Construction Is Deferred From Python 3.12

Before 3.12 the constructor splits the string into components immediately.
From 3.12 it only keeps the arguments; the split happens on the first
operation that needs it, and the result is cached on the object. Building a
path costs O(1) there, and building paths you never use costs nothing beyond
the reference.

```python
from pathlib import Path

# 3.12+: O(1) - nothing is parsed yet
path = Path('/' + 'a' * 100000)

# The deferred parse is paid here, once
text = str(path)  # O(n)

# Cached: subsequent uses do not pay it again
text = str(path)  # O(1)
```

The same applies to joining, which is why `/` is cheap on recent versions and
proportional to the path on older ones.

## Pure Paths Never Touch the Filesystem

`PurePath` and its two flavours are string manipulation with a path-shaped
API. Every operation in the pure table above costs what parsing and rebuilding
a string costs, and none of them can fail because a file is missing or a
directory is unreadable.

```python
from pathlib import PurePosixPath, PureWindowsPath

# No such directory anywhere; all of this still works
p = PurePosixPath('/nowhere/at/all/report.tar.gz')

p.name        # 'report.tar.gz'  O(1)
p.stem        # 'report.tar'     O(1)
p.suffix      # '.gz'            O(1)
p.suffixes    # ['.tar', '.gz']  O(m) in the final component
p.parts       # ('/', 'nowhere', 'at', 'all', 'report.tar.gz')  O(n)

# Windows semantics on any platform
PureWindowsPath('C:/Users/x').drive   # 'C:'  O(1)
```

`Path` inherits all of it and adds the operations that do make system calls.

## Two Things That Cost More Than They Look

### relative_to() Is Quadratic From Python 3.12

`relative_to()` and `is_relative_to()` walk the parents of one path looking for
the other, and testing each candidate scans the parents again. Before 3.12 the
comparison was a slice; from 3.12 the search is quadratic in the number of
components, which turns a deep path into real work.

```python
from pathlib import PurePosixPath

deep = PurePosixPath('/' + '/'.join(f'd{i}' for i in range(200)) + '/f.txt')

# O(n²) from 3.12, O(n) before it
deep.relative_to('/d0')
```

For a path a handful of components long this is invisible. For one two hundred
deep, called in a loop over many paths, it is the loop's dominant cost.

### parts Is Rebuilt On Every Access From Python 3.12

`parts` returns a fresh tuple each time it is read. Up to 3.11 the tuple was
cached after the first access; from 3.12 it is not, so reading it inside a loop
pays O(n) each time round.

```python
from pathlib import PurePosixPath

p = PurePosixPath('/a/b/c/d/e/f.txt')

# Read once, use many times
parts = p.parts
first, last = parts[0], parts[-1]
```

`parents` is the opposite: it is a lazy sequence, O(1) to obtain, and
`parents[i]` builds only the path it returns. Materialising the whole of it
with `list()` is O(n²), because each of the n parents holds up to n components.

## Path Operations

### exists(), is_file(), is_dir()

#### Time Complexity: O(1)

Each makes exactly one stat call, whatever the path's length or the size of
the directory holding it.

```python
from pathlib import Path

path = Path('file.txt')

# Single stat system call: O(1)
if path.exists():      # O(1) - stat call
    print('exists')

if path.is_file():     # O(1) - stat call
    print('is file')

if path.is_dir():      # O(1) - stat call
    print('is directory')
```

#### Space Complexity: O(1)

```python
from pathlib import Path

path = Path('large_name' * 20)

# No additional memory needed
exists = path.exists()  # O(1) space
```

## Path Resolution

### resolve()

#### Time Complexity: O(n)

Where n = number of path components; each one costs an lstat call, and a
symlink adds the components of its target.

```python
from pathlib import Path

# Simple resolution: O(n) where n = components
path = Path('docs/../files/./file.txt')
absolute = path.resolve()  # O(n) - normalize and resolve

# With symlinks: O(n) where n = symlinks + components
# Each symlink read is a system call
path = Path('/path/with/symlinks/file.txt')
absolute = path.resolve()  # O(n)
```

### Space Complexity: O(n)

```python
from pathlib import Path

# Stores resolved path
path = Path('relative/path').resolve()  # O(n) space
```

## Directory Operations

### iterdir()

#### Time Complexity: O(d)

Where d = number of directory entries.

```python
from pathlib import Path

path = Path.home()

# List all entries: O(d) where d = entries
for item in path.iterdir():  # O(d)
    print(item)

# Count entries: O(d)
count = sum(1 for _ in path.iterdir())  # O(d)
```

#### Space Complexity: O(d)

`iterdir()` returns an iterator, but it is not a streaming one: the directory
is read in full and every name is materialised before the first item is
yielded. Iterating instead of calling `list()` avoids holding the `Path`
objects, not the listing they are built from.

```python
from pathlib import Path

path = Path.home()

# The listing is already in memory by the time this yields anything
for item in path.iterdir():  # O(d) space, not O(1)
    print(item)

# Building a list on top of it costs the Path objects as well
entries = list(path.iterdir())  # O(d) space
```

!!! warning "A big directory costs memory even if you stop early"
    `next(iter(path.iterdir()))` reads the whole directory. Where that
    matters, `os.scandir()` is the streaming alternative - see
    [OS Module](os.md).

### glob()

#### Time Complexity: O(n)

Where n = number of entries scanned, which is every entry of every directory
the pattern opens, not the number of entries that match.

```python
from pathlib import Path

path = Path('.')

# Simple glob: O(n) where n = entries in this directory
py_files = list(path.glob('*.py'))  # O(n)

# Nested glob: O(n) over every entry in the subtree
txt_files = list(path.glob('**/*.txt'))  # O(n)

# A non-matching leading component still costs the scan that rejects it
results = list(path.glob('[a-z]*/data/*.json'))  # O(n)
```

#### Space Complexity: O(w)

Where w = entries of the largest directory scanned. Like `iterdir()`, `glob()`
reads a directory in one go, so the peak follows the widest directory it opens
rather than the number of matches it yields. A `**` in the pattern walks the
tree as `rglob()` does, and pays its O(w + d) space instead.

```python
from pathlib import Path

# Iterating does not make the scan incremental within a directory
for match in Path('.').glob('*'):  # O(w) space
    print(match)

# Collecting the results adds the matches on top
matches = list(Path('.').glob('*'))  # O(w + matches) space

# A ** pattern pays rglob's depth term instead of the flat O(w)
txt_files = list(Path('.').glob('**/*.txt'))  # O(w + d) space
```

### rglob()

#### Time Complexity: O(n)

Where n = total entries in the directory tree.

```python
from pathlib import Path

path = Path('.')

# Recursive glob: O(n) where n = all entries in the tree
all_py = list(path.rglob('*.py'))  # O(n)

# rglob(pattern) is glob('**/' + pattern)
all_txt = list(path.rglob('*.txt'))  # O(n)
```

#### Space Complexity: O(w + d)

Where w = entries of the largest directory scanned and d = depth reached.
Depth does not fold into width: a deeper tree costs more than a shallow one
holding the same entries.

```python
from pathlib import Path

# All results in memory, on top of the walk's own O(w + d)
matches = list(Path('.').rglob('*.py'))  # O(matches) space
```

## File I/O

### read_text() / read_bytes()

#### Time Complexity: O(n)

Where n = file size.

```python
from pathlib import Path

path = Path('data.txt')
path.write_text('example')

# Read entire file: O(n) where n = file size
content = path.read_text()  # O(n)

# Read binary: O(n)
data = path.read_bytes()  # O(n)

# Read with encoding: O(n)
content = path.read_text(encoding='utf-8')  # O(n)
```

#### Space Complexity: O(n)

```python
from pathlib import Path

Path('large_file.txt').write_text('x' * 1000)

# Stores entire file content
content = Path('large_file.txt').read_text()  # O(n) space
```

### write_text() / write_bytes()

#### Time Complexity: O(n)

Where n = content size.

```python
from pathlib import Path

path = Path('output.txt')

# Write text: O(n) in the length of the string
path.write_text('Hello, World!')

# Write bytes: O(n)
path.write_bytes(b'Binary data')

# Overwrites file: O(n) regardless of original size
path.write_text('x' * 1000000)
```

#### Space Complexity: O(n)

```python
from pathlib import Path

# Encodes to bytes before writing
content = 'x' * 1000000
Path('file.txt').write_text(content)  # O(n) extra space
```

## File System Modifications

### mkdir(), rmdir(), unlink(), rename()

#### Time Complexity: O(1)

```python
from pathlib import Path

# Create directory: O(1) - single system call
Path('new_dir').mkdir()  # O(1)

# Create with parents: O(d) where d = missing components
Path('a/b/c/d').mkdir(parents=True, exist_ok=True)  # O(d)

# Remove empty directory: O(1)
Path('new_dir').rmdir()  # O(1)

# Rename: O(1) - same filesystem
Path('a/b/c/d').rename('a/b/c/e')  # O(1)

# Remove file: O(1)
Path('file.txt').touch()  # O(1)
Path('file.txt').unlink()  # O(1)
```

#### Space Complexity: O(1)

```python
from pathlib import Path

# No significant memory allocation
Path('dir').mkdir()  # O(1) space
Path('dir').rmdir()  # O(1) space
```

## Common Patterns

### Safe File Operations

```python
from pathlib import Path

# Check before operating
path = Path('file.txt')
path.write_text('contents')

if path.exists() and path.is_file():  # O(1) + O(1)
    content = path.read_text()  # O(n)
```

### Directory Tree Processing

```python
from pathlib import Path

def process(text):
    return len(text)

# Process all files: O(n) to walk, plus the size of each file read
for file in Path('.').rglob('*.py'):  # O(n) to find files
    content = file.read_text()  # O(size) per file
    process(content)
```

### Path Construction

```python
from pathlib import Path

names = ['a.txt', 'b.txt']

# Build paths: O(n) in total path length, O(1) from Python 3.12
base = Path('data')
file = base / 'subdir' / 'file.txt'

# Multiple files
for name in names:
    path = base / name
```

### Safe Deletion

```python
from pathlib import Path
import shutil

path = Path('directory')

# Delete directory and contents: O(n) where n = total entries
if path.is_dir():  # O(1)
    shutil.rmtree(path)  # O(n)

# Or using pathlib
# Path.rmdir() only works on empty directories
```

## Comparison with os.path

```python
from pathlib import Path
import os

# pathlib (object-oriented)
p = Path('data') / 'file.txt'  # O(n), O(1) from Python 3.12
exists = p.exists()  # O(1)

# os.path (functional)
path = os.path.join('data', 'file.txt')  # O(n)
exists = os.path.exists(path)  # O(1)

# The filesystem calls cost the same either way. The string handling does not:
# from 3.12 pathlib defers it, so a path that is built and never used is free,
# while os.path.join always produces the joined string.
```

## Performance Characteristics

### Best Practices

```python
from pathlib import Path

def process(path):
    return path.name

# Good: scan once
base = Path('.')
files = list(base.glob('*.py'))  # O(n) once

for file in files:  # Iterate cached results
    process(file)  # O(1) per file

# Bad: repeated glob calls rescan the directory every time
for i in range(100):
    files = list(Path('.').glob('*.py'))  # O(n) * 100
```

## Python 3.14: info, copy and move

`Path.info` is a cached view of what one stat call already told the
interpreter. Each query on the same object is free; each `Path.exists()` is
another syscall.

```python
from pathlib import Path

path = Path('report.txt')
path.write_text('contents')

# One stat call answers all three
info = path.info
info.exists(), info.is_file(), info.is_dir()

# Three separate stat calls
path.exists(), path.is_file(), path.is_dir()
```

The cache never expires, so a long-lived `Path` whose file changes underneath
it keeps answering from the old stat. Build a fresh `Path` where that matters.

`copy()` streams, so it is O(b) in the bytes moved and O(1) in space however
large the file is. `move()` on one filesystem is a rename and costs neither.

```python
from pathlib import Path

source = Path('report.txt')
source.write_text('contents')

source.copy(Path('backup.txt'))   # O(b) time, O(1) space
source.move(Path('archive.txt'))  # O(1) on the same filesystem
```

## Version Notes

- **Python 3.4+**: pathlib introduced
- **Python 3.10+**: `Path.hardlink_to()` added, deprecating `Path.link_to()`
- **Python 3.12+**: `Path.walk()`, `Path.is_junction()` and
  `PurePath.with_segments()` added; construction and joining defer parsing to
  first use; `parts` is rebuilt per access and `relative_to()` becomes
  quadratic; `Path.link_to()` removed
- **Python 3.13+**: `Path.from_uri()`, `PurePath.full_match()`,
  `PurePath.parser` and `UnsupportedOperation` added; `iterdir()` reads the
  directory when it is called rather than at the first `next()`;
  `PurePath.is_reserved()` deprecated
- **Python 3.14+**: `Path.copy()`, `Path.copy_into()`, `Path.move()`,
  `Path.move_into()` and `Path.info` added; `PurePath.as_uri()` deprecated in
  favour of `Path.as_uri()`

## Related Documentation

- [OS Module](os.md) - Low-level filesystem operations
- [Glob Module](glob.md) - Unix-style pathname expansion
