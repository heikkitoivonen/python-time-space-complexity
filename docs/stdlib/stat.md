# stat Module Complexity

The `stat` module interprets the results of `os.stat()`, `os.lstat()` and `os.fstat()`: it names
the bits of `st_mode` and `st_flags`, the indices of the `os.stat_result` tuple, and the Windows
attribute bits, and its functions pull the file type and permissions out of a mode. It never
touches the filesystem itself. The functions and most constants come from the C `_stat` module,
which `Lib/stat.py` imports over its own pure-Python definitions; those definitions are what runs
where `_stat` is missing.

There is no size variable. Every function takes one mode, a fixed-width integer, and does a
fixed number of bit operations on it in both implementations, so every row below is O(1). The
cost worth planning around is outside the module: each `os.stat()` or `os.lstat()` is a system
call, and one result can answer every question this module asks of it.

## Complexity Reference

### File type tests

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stat.S_ISDIR(mode)`, `stat.S_ISREG(mode)` | O(1) | O(1) | Compare the file-type bits with one type |
| `stat.S_ISLNK(mode)` | O(1) | O(1) | `os.stat()` follows a link by default, so only a mode from `os.lstat()` or `follow_symlinks=False` can be a link |
| `stat.S_ISCHR(mode)`, `stat.S_ISBLK(mode)`, `stat.S_ISFIFO(mode)`, `stat.S_ISSOCK(mode)` | O(1) | O(1) | Character and block devices, named pipes, sockets |
| `stat.S_ISDOOR(mode)`, `stat.S_ISPORT(mode)`, `stat.S_ISWHT(mode)` | O(1) | O(1) | Solaris doors and event ports, BSD and macOS whiteouts; always `False` on a platform without the type |

### Mode functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stat.S_IFMT(mode)` | O(1) | O(1) | The file-type bits |
| `stat.S_IMODE(mode)` | O(1) | O(1) | The permission bits, as `os.chmod()` takes them |
| `stat.filemode(mode)` | O(1) | O(1) | Always ten characters, as `ls -l` prints them; `?` for an unknown file type |

### Tuple indices

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stat.ST_MODE`, `stat.ST_INO`, `stat.ST_DEV`, `stat.ST_NLINK`, `stat.ST_UID`, `stat.ST_GID`, `stat.ST_SIZE`, `stat.ST_ATIME`, `stat.ST_MTIME`, `stat.ST_CTIME` | O(1) | O(1) | Indices into an `os.stat_result`; `st[stat.ST_MODE]` is `st.st_mode` |

### File type and permission constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stat.S_IFSOCK`, `stat.S_IFLNK`, `stat.S_IFREG`, `stat.S_IFBLK`, `stat.S_IFDIR`, `stat.S_IFCHR`, `stat.S_IFIFO` | O(1) | O(1) | The values `S_IFMT(mode)` returns |
| `stat.S_IFDOOR`, `stat.S_IFPORT`, `stat.S_IFWHT` | O(1) | O(1) | 0 on a platform without the type, so test with `S_ISDOOR()` and its siblings rather than comparing |
| `stat.S_ISUID`, `stat.S_ISGID`, `stat.S_ISVTX` | O(1) | O(1) | Set-user-ID, set-group-ID and sticky bits |
| `stat.S_IRWXU`, `stat.S_IRUSR`, `stat.S_IWUSR`, `stat.S_IXUSR`, `stat.S_IRWXG`, `stat.S_IRGRP`, `stat.S_IWGRP`, `stat.S_IXGRP`, `stat.S_IRWXO`, `stat.S_IROTH`, `stat.S_IWOTH`, `stat.S_IXOTH` | O(1) | O(1) | Owner, group and other permission bits and their masks |
| `stat.S_IREAD`, `stat.S_IWRITE`, `stat.S_IEXEC`, `stat.S_ENFMT` | O(1) | O(1) | Aliases of `S_IRUSR`, `S_IWUSR` and `S_IXUSR`, owner bits only, and of `S_ISGID` |

### File flags

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stat.UF_NODUMP`, `stat.UF_IMMUTABLE`, `stat.UF_APPEND`, `stat.UF_OPAQUE`, `stat.UF_NOUNLINK`, `stat.UF_COMPRESSED`, `stat.UF_HIDDEN`, `stat.SF_ARCHIVED`, `stat.SF_IMMUTABLE`, `stat.SF_APPEND`, `stat.SF_NOUNLINK`, `stat.SF_SNAPSHOT` | O(1) | O(1) | Bits of `st_flags` and of `os.chflags()`, which BSD and macOS provide; the constants are defined everywhere |
| `stat.UF_SETTABLE`, `stat.UF_TRACKED`, `stat.UF_DATAVAULT`, `stat.SF_SETTABLE`, `stat.SF_RESTRICTED`, `stat.SF_FIRMLINK`, `stat.SF_DATALESS` | O(1) | O(1) | Python 3.13+ |
| `stat.SF_SUPPORTED`, `stat.SF_SYNTHETIC` | O(1) | O(1) | Python 3.13+, macOS |

### Windows attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stat.FILE_ATTRIBUTE_ARCHIVE`, `stat.FILE_ATTRIBUTE_COMPRESSED`, `stat.FILE_ATTRIBUTE_DEVICE`, `stat.FILE_ATTRIBUTE_DIRECTORY`, `stat.FILE_ATTRIBUTE_ENCRYPTED`, `stat.FILE_ATTRIBUTE_HIDDEN`, `stat.FILE_ATTRIBUTE_INTEGRITY_STREAM`, `stat.FILE_ATTRIBUTE_NORMAL`, `stat.FILE_ATTRIBUTE_NOT_CONTENT_INDEXED`, `stat.FILE_ATTRIBUTE_NO_SCRUB_DATA`, `stat.FILE_ATTRIBUTE_OFFLINE`, `stat.FILE_ATTRIBUTE_READONLY`, `stat.FILE_ATTRIBUTE_REPARSE_POINT`, `stat.FILE_ATTRIBUTE_SPARSE_FILE`, `stat.FILE_ATTRIBUTE_SYSTEM`, `stat.FILE_ATTRIBUTE_TEMPORARY`, `stat.FILE_ATTRIBUTE_VIRTUAL` | O(1) | O(1) | Bits of `st_file_attributes`, which only Windows fills in; the constants are defined everywhere |
| `stat.IO_REPARSE_TAG_SYMLINK`, `stat.IO_REPARSE_TAG_MOUNT_POINT`, `stat.IO_REPARSE_TAG_APPEXECLINK` | O(1) | O(1) | Values of `st_reparse_tag`; Windows only |

## Reading a Mode

### Many Tests From One Call

`os.path.isfile()`, `os.path.isdir()` and `os.path.exists()` each make a system call of their
own. Asking several questions about one path costs one call per question; one `os.stat()` and the
predicates here cost one call in all.

```python
import os
import stat
import tempfile

with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, 'data.txt')
    with open(path, 'w') as f:
        f.write('hello')

    st = os.stat(path)                # one system call
    mode = st.st_mode
    assert stat.S_ISREG(mode)         # O(1) - no further system calls
    assert not stat.S_ISDIR(mode)     # O(1)
    assert stat.S_IFMT(mode) == stat.S_IFREG  # O(1)
    assert st[stat.ST_SIZE] == st.st_size == 5  # O(1) - the same field by index

    assert stat.S_ISDIR(os.stat(root).st_mode)
```

### Symbolic Links

A mode from `os.stat()` with its default `follow_symlinks=True` describes the file a link points
to, so `S_ISLNK()` on it is never true. Ask `os.lstat()` when the link itself is the question.

```python
import os
import stat
import tempfile

with tempfile.TemporaryDirectory() as root:
    target = os.path.join(root, 'target.txt')
    open(target, 'w').close()
    link = os.path.join(root, 'link')
    os.symlink(target, link)

    assert stat.S_ISREG(os.stat(link).st_mode)       # followed to the target
    assert not stat.S_ISLNK(os.stat(link).st_mode)
    assert stat.S_ISLNK(os.lstat(link).st_mode)      # the link itself - O(1) test
```

### Turning a Mode Into Text

`filemode()` renders any mode as the ten characters `ls -l` prints: the file type, then three
permission triples with the set-ID and sticky bits folded in.

```python
import stat

assert stat.filemode(stat.S_IFREG | 0o644) == '-rw-r--r--'   # O(1)
assert stat.filemode(stat.S_IFDIR | 0o755) == 'drwxr-xr-x'
assert stat.filemode(stat.S_IFREG | 0o4755) == '-rwsr-xr-x'  # set-user-ID
assert stat.filemode(stat.S_IFDIR | 0o1777) == 'drwxrwxrwt'  # sticky
assert stat.filemode(0o644) == '?rw-r--r--'                   # no file type bits
```

## Permission Bits

`S_IMODE()` strips the file type, leaving what `os.chmod()` accepts, so on POSIX a permission
change is a read, one bit operation and a write. `S_IREAD`, `S_IWRITE` and `S_IEXEC` are the owner bits
alone: testing `S_IEXEC` does not say whether the group or others may execute the file.

```python
import os
import stat
import tempfile

with tempfile.TemporaryDirectory() as root:
    path = os.path.join(root, 'script.py')
    open(path, 'w').close()
    os.chmod(path, 0o644)

    mode = os.stat(path).st_mode
    assert stat.S_IMODE(mode) == 0o644                      # O(1)
    os.chmod(path, stat.S_IMODE(mode) | stat.S_IXUSR)       # add owner execute

    mode = os.stat(path).st_mode
    assert mode & stat.S_IEXEC                              # S_IEXEC is S_IXUSR
    assert not mode & (stat.S_IXGRP | stat.S_IXOTH)         # nobody else may run it
    assert stat.filemode(mode) == '-rwxr--r--'
```

## Platform-Specific Constants

Every name in the module except `SF_SUPPORTED`, `SF_SYNTHETIC` and the `IO_REPARSE_TAG_*` values
is defined on every platform, whether or not the platform uses it. A file type the platform lacks
has an `S_IF*` value of 0 and a predicate that always answers `False`, so the predicates are the
portable test.

```python
import stat

if stat.S_IFDOOR == 0:  # no doors here
    assert not stat.S_ISDOOR(stat.S_IFREG | 0o644)       # O(1)
    assert stat.S_IFMT(0o644) == stat.S_IFDOOR           # comparing matches a typeless mode

# The Windows and BSD bit names exist everywhere; only their platform fills in the fields
assert stat.FILE_ATTRIBUTE_HIDDEN == 2
assert stat.UF_HIDDEN == 0x8000
```

## Common Patterns

### Listing a Directory Like ls -l

`os.scandir()` reads the names, and `DirEntry.stat()` caches its result on the entry, so everything
after the first call is O(1) per entry.

```python
import os
import stat
import tempfile

with tempfile.TemporaryDirectory() as root:
    os.mkdir(os.path.join(root, 'sub'))
    open(os.path.join(root, 'file.txt'), 'w').close()
    os.symlink('file.txt', os.path.join(root, 'link'))

    listing = {}
    with os.scandir(root) as entries:
        for entry in entries:
            mode = entry.stat(follow_symlinks=False).st_mode  # cached on the entry
            listing[entry.name] = stat.filemode(mode)[0]      # O(1)

    assert listing == {'sub': 'd', 'file.txt': '-', 'link': 'l'}
```

## Performance Best Practices

✅ **Do**:

- Call `os.stat()` once and test its mode as many times as you need; each test is O(1) and makes
  no system call
- Use `os.lstat()`, or `follow_symlinks=False`, when you need to see links
- Test file types with the `S_IS*()` predicates, which stay correct where a type's constant is 0

❌ **Avoid**:

- Chaining `os.path.isfile()`, `os.path.isdir()` and `os.path.exists()` on one path - a system call
  each
- `S_ISLNK()` on a mode from `os.stat()` with links followed - it is never true
- Reading `S_IREAD`, `S_IWRITE` or `S_IEXEC` as "anyone may" - they are the owner's bits only

## Related Modules

- **[os](os.md)** - `os.stat()`, `os.lstat()` and `os.scandir()`, where the system calls are
- **[pathlib](pathlib.md)** - `Path.stat()` and `Path.lstat()` return the same `st_mode`
- **[shutil](shutil.md)** - `copymode()` and `copystat()` copy these bits between files
