# tempfile Module Complexity

The `tempfile` module creates files and directories that nobody else can have claimed first,
and can remove them when you are done. Creating one is a loop: draw a random name, try to create
it exclusively, and draw again if the name is taken. Everything after that is ordinary file I/O
on the object you get back.

`r` is the name attempts one creation makes: 1 unless randomly drawn names collide with entries
already in the directory, and never more than `tempfile.TMP_MAX`. `c` is the candidate
directories the first `gettempdir()` probes, `n` is the bytes (characters, in text mode) a file
holds, `k` is the bytes one read or write moves, and `s` is a `SpooledTemporaryFile`'s
`max_size`. `m` is the entries in a temporary directory's tree at cleanup, `d` its depth and `w`
the entries in its largest directory. One filesystem call - a create, a stat, an unlink - is
priced at O(1). A creation with `dir=None` also pays `gettempdir()`'s one-time probe on the
first use in the process.

## Complexity Reference

### Creating files and directories

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tempfile.mkstemp(suffix=None, prefix=None, dir=None, text=False)` | O(r) | O(1) | One exclusive `os.open` per attempt; returns an open descriptor and a path, both the caller's to close and remove |
| `tempfile.mkdtemp(suffix=None, prefix=None, dir=None)` | O(r) | O(1) | One `os.mkdir` per attempt; the caller removes the directory |
| `tempfile.mktemp(suffix='', prefix='tmp', dir=None)` | O(r) | O(1) | Deprecated and unsafe: one `lstat` per attempt and nothing is created, so the name can be taken before you use it |

### NamedTemporaryFile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tempfile.NamedTemporaryFile(mode='w+b', buffering=-1, encoding=None, newline=None, suffix=None, prefix=None, dir=None, delete=True, *, errors=None, delete_on_close=True)` | O(r) | O(1) | Created as `mkstemp()` does; the data lives on disk, so memory is the file buffer |
| `NamedTemporaryFile.name`, `NamedTemporaryFile.file` | O(1) | O(1) | The path, visible in the directory while the file is open, and the underlying file object |
| Writing k bytes | O(k) | O(1) | Buffered file I/O |
| Reading k bytes | O(k) | O(k) | The result is the only thing held |
| `close()`, leaving the `with` block | O(1) | O(1) | One unlink when `delete=True`; with `delete_on_close=False` (Python 3.12+) closing keeps the file and leaving the `with` block removes it |

### TemporaryFile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tempfile.TemporaryFile(mode='w+b', buffering=-1, encoding=None, newline=None, suffix=None, prefix=None, dir=None, *, errors=None)` | O(r) | O(1) | On Linux, where the filesystem supports `O_TMPFILE`, no name is drawn at all; otherwise on POSIX the file is created under a name and unlinked at once. On Windows this is `NamedTemporaryFile` |
| Reading and writing | O(k) | O(k) to read, O(1) to write | As for `NamedTemporaryFile`; there is no name to see |

### SpooledTemporaryFile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tempfile.SpooledTemporaryFile(max_size=0, mode='w+b', buffering=-1, encoding=None, newline=None, suffix=None, prefix=None, dir=None, *, errors=None)` | O(1) | O(1) | Starts as an in-memory buffer and creates no file |
| `SpooledTemporaryFile.write(s)` | O(k) | O(k) in memory, O(1) once rolled over | The write that takes the position past `max_size` also pays `rollover()`, once; `max_size=0` never rolls over on its own |
| `SpooledTemporaryFile.writelines(lines)` | O(n) | O(s + k) | Rolls over as soon as a line crosses `max_size`; 3.10, 3.11, 3.12.0-3.12.9 and 3.13.0-3.13.2 hold the whole iterable in memory first, O(n) |
| `SpooledTemporaryFile.rollover()` | O(r + n) | O(1) | Creates a `TemporaryFile`, copies the n held bytes to it and frees the in-memory buffer; does nothing once rolled over |
| `SpooledTemporaryFile.fileno()` | O(r + n) first call, then O(1) | O(1) | Needs a real descriptor, so it forces `rollover()` |
| `SpooledTemporaryFile.truncate(size=None)` | O(r + n) if `size > max_size`, else O(1) | O(1) | A size past `max_size` forces `rollover()` first |
| `SpooledTemporaryFile.read(size)`, `read1()`, `readinto(b)`, `readinto1(b)`, `readline()`, `readlines()`, iterating | O(k) | O(k) | Passed to the in-memory buffer or the file, whichever holds the data; k = what is returned. `read1()` and the `readinto` pair are Python 3.11+ |
| `SpooledTemporaryFile.seek()`, `tell()`, `flush()`, `close()`, `detach()`, `isatty()`, `readable()`, `seekable()`, `writable()` | O(1) | O(1) | Passed through as well; `detach()`, `readable()`, `seekable()` and `writable()` are Python 3.11+ |
| `SpooledTemporaryFile.closed`, `mode`, `name`, `encoding`, `errors`, `newlines` | O(1) | O(1) | `name` is `None` until the file rolls over |

### TemporaryDirectory

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tempfile.TemporaryDirectory(suffix=None, prefix=None, dir=None, ignore_cleanup_errors=False, *, delete=True)` | O(r) | O(1) | `mkdtemp()` plus a finalizer that cleans up if the object is collected |
| `TemporaryDirectory.name` | O(1) | O(1) | The path; `with` binds this string, not the object |
| `TemporaryDirectory.cleanup()`, leaving the `with` block | O(m) | O(d·w) | `shutil.rmtree` over the tree; a `PermissionError` makes it reset permissions and retry, and `ignore_cleanup_errors=True` leaves what still cannot be removed instead of raising. A second call does nothing; `delete=False` (Python 3.12+) skips it on exit |

### Locations and constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tempfile.gettempdir()` | O(c) first call, then O(1) | O(c) first call, then O(1) | Probes `TMPDIR`, `TEMP`, `TMP`, the platform's usual directories and the working directory by creating and deleting a file in each, and caches the first that works |
| `tempfile.gettempdirb()` | O(c) first call, then O(1) | O(c) first call, then O(1) | The same directory, and the same cache, as bytes |
| `tempfile.gettempprefix()`, `tempfile.gettempprefixb()` | O(1) | O(1) | `'tmp'` and `b'tmp'` |
| `tempfile.tempdir` | O(1) | O(1) | The cache itself; assign it before first use to skip the probe |
| `tempfile.TMP_MAX` | O(1) | O(1) | The ceiling on r; exhausting it raises `FileExistsError` |

## Creating Temporary Files

### Named vs Unnamed Files

A `NamedTemporaryFile` has a path other code can open, and it is removed when it closes.
A `TemporaryFile` has no path at all, which on Linux means it can skip naming altogether.
Neither holds its data in memory.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as workdir:
    with tempfile.NamedTemporaryFile(dir=workdir) as named:  # O(r)
        named.write(b'x' * 100_000)  # O(k) time, O(1) memory - it goes to disk
        named.flush()
        assert os.listdir(workdir) == [os.path.basename(named.name)]
        assert os.path.getsize(named.name) == 100_000
    assert os.listdir(workdir) == []  # unlinked on exit - O(1)

    with tempfile.TemporaryFile(dir=workdir) as unnamed:  # O(r), no name at all on Linux
        unnamed.write(b'data')
        unnamed.seek(0)
        assert unnamed.read() == b'data'  # O(k)
        assert os.listdir(workdir) == []  # nothing to see on POSIX, even while open
```

### Keeping What Would Be Deleted

Three switches hand removal back to you. `delete=False` keeps a `NamedTemporaryFile` for good.
`delete_on_close=False` keeps it through `close()`, so another opener can use the path, and
removes it when the `with` block ends. `TemporaryDirectory(delete=False)` skips the cleanup on
exit. The last two need Python 3.12.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as workdir:
    with tempfile.NamedTemporaryFile('w', dir=workdir, delete_on_close=False) as f:
        f.write('config')
        f.close()  # O(1) - the file stays
        with open(f.name) as reader:
            assert reader.read() == 'config'
    assert not os.path.exists(f.name)  # removed on exit

    kept = tempfile.NamedTemporaryFile(dir=workdir, delete=False)  # O(r)
    kept.close()
    assert os.path.exists(kept.name)  # still there: removing it is your job
    os.unlink(kept.name)  # O(1)

    held = tempfile.TemporaryDirectory(dir=workdir, delete=False)  # O(r)
    with held as name:
        pass
    assert os.path.isdir(name)  # left in place
    held.cleanup()  # an explicit call still removes it
    assert not os.path.exists(name)
```

### mkstemp and mkdtemp

The low-level pair return what they made and forget about it. Both try names until one is free,
so a crowded directory costs extra attempts, never a scan of what is already there.

```python
import os
import tempfile

workdir = tempfile.mkdtemp(prefix='job_')  # O(r)
assert os.path.basename(workdir).startswith('job_')
assert os.path.isabs(workdir)

fd, path = tempfile.mkstemp(suffix='.txt', dir=workdir)  # O(r)
os.write(fd, b'payload')
os.close(fd)
assert os.path.dirname(path) == workdir and path.endswith('.txt')

os.unlink(path)  # nothing removes them for you
os.rmdir(workdir)
```

### Why mktemp Is Unsafe

`mktemp()` checks that a name is free and returns it without creating anything. Whatever
creates the file later is racing every other process for that name; `mkstemp()` creates it in
the same step that checks it.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as workdir:
    name = tempfile.mktemp(dir=workdir)  # O(r) - one lstat per attempt, nothing created
    assert not os.path.exists(name)

    open(name, 'w').close()  # another process gets there first

    try:
        os.open(name, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        pass
    else:
        raise AssertionError('the name was still free')
```

## Spooling in Memory

A `SpooledTemporaryFile` keeps what you write in memory until the position passes `max_size`.
The write that crosses it calls `rollover()`, which creates a real temporary file and copies
everything written so far into it - O(n) once - and from then on memory stays flat. With the
default `max_size=0` it never rolls over on its own.

```python
import tempfile

with tempfile.TemporaryDirectory() as workdir:
    with tempfile.SpooledTemporaryFile(max_size=1_000, dir=workdir) as spool:  # O(1)
        spool.write(b'x' * 1_000)  # O(k), held in memory
        assert spool.name is None  # still no file

        spool.write(b'y')  # past max_size: rollover() copies all 1,001 bytes - O(n)
        assert spool.name is not None

        spool.seek(0)
        assert spool.read() == b'x' * 1_000 + b'y'

    with tempfile.SpooledTemporaryFile(dir=workdir) as unbounded:  # max_size=0
        unbounded.write(b'z' * 100_000)
        assert unbounded.name is None  # everything is still in memory
        unbounded.fileno()  # O(n) - a descriptor forces rollover()
        assert unbounded.name is not None
```

## Temporary Directories

`TemporaryDirectory` is `mkdtemp()` plus cleanup. Leaving the `with` block removes the whole
tree with `shutil.rmtree`, so the exit costs what you put inside, and it runs even when the block
raises.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as parent:
    with tempfile.TemporaryDirectory(dir=parent) as workdir:  # O(r)
        for index in range(100):
            with open(os.path.join(workdir, f'chunk{index}'), 'w') as f:
                f.write('x')
        os.mkdir(os.path.join(workdir, 'nested'))
        assert len(os.listdir(workdir)) == 101
    assert not os.path.exists(workdir)  # O(m) - all 101 entries removed

    try:
        with tempfile.TemporaryDirectory(dir=parent) as workdir:
            open(os.path.join(workdir, 'partial'), 'w').close()
            raise RuntimeError('job failed')
    except RuntimeError:
        pass
    assert not os.path.exists(workdir)  # cleaned up anyway
```

## The Default Directory

`gettempdir()` works out where temporary files go by trying to create a file in each candidate
directory in turn. It does that once per process and keeps the answer in `tempfile.tempdir`,
which every later call - and every creation with `dir=None` - reads.

```python
import os
import tempfile

first = tempfile.gettempdir()  # O(c) the first time
assert tempfile.tempdir == first  # the cached answer
assert tempfile.gettempdir() == first  # O(1) afterwards
assert tempfile.gettempdirb() == os.fsencode(first)  # the same cache, as bytes

assert tempfile.gettempprefix() == 'tmp'  # O(1)
assert tempfile.gettempprefixb() == b'tmp'
```

## Common Patterns

### Replacing a File Atomically

Write the new contents to a temporary file in the target's own directory, then rename it over
the target. The rename is O(1), and on POSIX readers see either the old file or the new one,
never half of it.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as workdir:
    target = os.path.join(workdir, 'settings.txt')
    with open(target, 'w') as f:
        f.write('old')

    with tempfile.NamedTemporaryFile('w', dir=workdir, delete=False) as tmp:  # O(r)
        tmp.write('new')  # O(k)
    os.replace(tmp.name, target)  # O(1) - same filesystem, so a rename

    with open(target) as f:
        assert f.read() == 'new'
    assert os.listdir(workdir) == ['settings.txt']
```

### Buffering Uploads of Unknown Size

```python
import tempfile

chunks = [b'a' * 64_000 for _ in range(10)]

with tempfile.TemporaryDirectory() as workdir:
    # Small bodies stay in memory; large ones go to disk after one O(n) copy
    with tempfile.SpooledTemporaryFile(max_size=256_000, dir=workdir) as body:
        body.writelines(chunks)  # O(n) - rolls over once past max_size
        assert body.name is not None
        body.seek(0)
        assert len(body.read()) == 640_000  # O(k)
```

## Performance Best Practices

✅ **Do**:

- Use `TemporaryFile` when nothing else needs the path: on Linux it skips naming entirely
- Pick a `max_size` for `SpooledTemporaryFile`, so memory is capped and only large files pay the
  rollover copy
- Create the temporary file in the target's directory when you will rename it into place:
  `os.replace()` is an O(1) rename only within one filesystem
- Use a context manager, so cleanup runs even when the block raises

❌ **Avoid**:

- `mktemp()` - it returns a name another process can take before you create it
- `SpooledTemporaryFile()` with the default `max_size=0` for data of unknown size - it never
  leaves memory unless something forces `rollover()`

## Version Notes

- **Python 3.10+**: `TemporaryDirectory` accepts `ignore_cleanup_errors`
- **Python 3.11+**: `SpooledTemporaryFile` implements the full `io.BufferedIOBase` or
  `io.TextIOBase` interface, adding `read1()`, `readinto()`, `readinto1()`, `detach()`,
  `readable()`, `seekable()` and `writable()`
- **Python 3.12+**: `NamedTemporaryFile` accepts `delete_on_close`, `TemporaryDirectory`
  accepts `delete`, and `mkdtemp()` always returns an absolute path
- **Python 3.12.10+, 3.13.3+**: `SpooledTemporaryFile.writelines()` rolls over as soon as a
  line crosses `max_size`; earlier 3.12 and 3.13 releases, and all of 3.10 and 3.11, hold the
  whole iterable in memory before checking
- **Python 3.13.13+, 3.14.4+**: `TMP_MAX` is 20, so a creation gives up after 20 collisions;
  earlier releases use the platform's `os.TMP_MAX`, which is far larger
- **All Python 3**: `mktemp()` is deprecated but issues no warning

## Related Modules

- **[shutil](shutil.md)** - `rmtree()`, which is what `TemporaryDirectory` cleanup costs
- **[os](os.md)** - `os.open`, `os.replace` and the descriptor `mkstemp()` returns
- **[io](io.md)** - `BytesIO`, the in-memory buffer a `SpooledTemporaryFile` starts as
- **[pathlib](pathlib.md)** - wrapping the returned paths
