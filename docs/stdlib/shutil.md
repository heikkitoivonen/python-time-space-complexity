# shutil Module Complexity

The `shutil` module is the high-level layer over `os`: copy a file, copy a tree, delete a tree,
move something, find a program on `PATH`. Its cost is the filesystem's, and the module's own
contribution is how much it holds while the filesystem works.

**n** is bytes moved, **E** is total tree/archive entries, **e** is entries in one directory and
**d** is the depth of the deepest path. **M** is total archive metadata, including member records
and name text. A recursive walk holds the listings along its *active path*, so tree space is
O(d·e) — neither the largest directory alone nor the whole tree.
File buffers are fixed unless specified; custom callbacks and compression workspace are excluded.
Tree time bounds below count entry visits and payload bytes, assuming bounded metadata work per
entry; long paths and extended attributes add their processing costs.

## Complexity Reference

### Copying files

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shutil.copyfile(src, dst)` | O(n) | O(1) | n = bytes; on Linux `sendfile` moves them without passing through Python at all |
| `shutil.copyfileobj(fsrc, fdst, length)` | O(n) | O(b) | Ordinary binary files: positive length selects buffer b; default is fixed `shutil.COPY_BUFSIZE`. Negative length reads all remaining bytes, using O(n) space |
| `shutil.copy(src, dst)` | O(n) | O(1) | `copyfile` plus `copymode` |
| `shutil.copy2(src, dst)` | O(n) + copystat cost | O(1) + copystat space | Copies bytes, then metadata |
| `shutil.copymode(src, dst)` | O(1) | O(1) | One `stat` and one `chmod` |
| `shutil.copystat(src, dst)` | O(1 + x + a + v) | O(1 + x + a + v_max) | Where supported: x attribute names of total length a, total value bytes v, largest value v_max; retains all names and copies values individually |

!!! note "O(1) space means O(1) in the file, not zero"
    The copy runs through a fixed buffer — `shutil.COPY_BUFSIZE`, 64 KiB before Python 3.14 and
    256 KiB from it on non-Windows systems; Windows uses 1 MiB. A 1 MiB file and a 16 MiB file peak at the same allocation, which is the
    claim; that allocation is not nothing.

### Trees

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shutil.copytree(src, dst, ...)` | O(n + E) | O(d·e) | Each ancestor's listing stays live while the walk descends, so shape matters: two trees of equal E can differ several-fold |
| `shutil.rmtree(path, ...)` | O(E) | O(d·e) | The same active-path retention, whether the version keeps ancestor listings or an explicit traversal stack |
| `shutil.move(src, dst)` | O(1) or O(n + E) | O(1) or O(d·e) | A rename within one filesystem, keeping the inode; a copy and a delete across two |
| `shutil.ignore_patterns(*patterns)` | O(1) | O(1) | Returns a callable that then costs O(patterns · e) per directory |

### Archives

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shutil.make_archive(base, format, root)` | O(n + E) | O(M) | Built-in ZIP/TAR retain member metadata; add compression time and workspace |
| `shutil.unpack_archive(filename, dir, format)` | O(n + E) | O(M) | Built-in ZIP/TAR retain member metadata; add decompression time and workspace |
| `shutil.get_archive_formats()`, `shutil.get_unpack_formats()` | O(f log f) | O(f) | f registered formats; builds and sorts a fresh list, assuming bounded name comparisons |
| `shutil.register_archive_format(...)` | O(1) | O(1) | One dict insertion with fixed-size extra arguments |
| `shutil.register_unpack_format(...)` | O(u + v) | O(u + 1) | Validates u existing extensions against v supplied extensions using a temporary dictionary; assumes bounded extension lengths |
| `shutil.unregister_archive_format(name)`, `shutil.unregister_unpack_format(name)` | O(1) | O(1) | One dict removal |

### Querying

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shutil.disk_usage(path)` | O(1) | O(1) | One `statvfs` |
| `shutil.which(cmd, mode, path)` | O(p + L) | O(p + L) | p PATH entries, L total PATH characters; splits the whole PATH and tracks visited directories. Fixed command and Windows PATHEXT sizes |
| `shutil.get_terminal_size(fallback)` | O(1) | O(1) | An `ioctl`, or the `COLUMNS`/`LINES` environment variables |
| `shutil.chown(path, user, group)` | O(1) | O(1) | Name-to-id lookups then one `chown`; Unix only |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shutil.Error` | O(1) | O(1) | Carries the list of per-file failures `copytree()` collected |
| `shutil.SameFileError` | O(1) | O(1) | Source and destination are the same file |
| `shutil.SpecialFileError` | O(1) | O(1) | A named pipe or similar, which cannot be copied as a file |
| `shutil.ExecError` | O(1) | O(1) | Deprecated in Python 3.14 and no longer exported; nothing in `shutil` raises it |

## Copying a File

```python
import os
import shutil
import tempfile

with tempfile.TemporaryDirectory() as folder:
    source = os.path.join(folder, 'source.txt')
    with open(source, 'w') as handle:
        handle.write('contents')
    os.chmod(source, 0o640)

    # copyfile moves only the bytes - O(n)
    plain = os.path.join(folder, 'plain.txt')
    shutil.copyfile(source, plain)
    assert open(plain).read() == 'contents'

    # copy adds the permission bits
    with_mode = os.path.join(folder, 'with_mode.txt')
    shutil.copy(source, with_mode)
    assert os.stat(with_mode).st_mode == os.stat(source).st_mode

    # copy2 adds the timestamps too
    with_stat = os.path.join(folder, 'with_stat.txt')
    shutil.copy2(source, with_stat)
    assert os.stat(with_stat).st_mtime == os.stat(source).st_mtime

    # Copying a file onto itself is refused rather than truncating it
    try:
        shutil.copyfile(source, source)
    except shutil.SameFileError:
        pass
```

### The Buffer

```python
import shutil

# The size of the one buffer a copy streams through
assert shutil.COPY_BUFSIZE in (64 * 1024, 256 * 1024, 1024 * 1024)
```

## Copying and Removing Trees

`copytree()` retains each ancestor directory listing during recursion, so what it holds is the
listings along the path it is currently descending — O(d·e), not the whole tree and not one
directory. Shape decides it: a chain 50 deep with 40 entries per level and a two-level tree of 50
such directories hold the same 2,050 entries, yet the chain peaks several times higher. Python
3.10–3.11 `rmtree()` retains ancestor listings the same way; newer versions keep an explicit
traversal stack, which is bounded the same.

```python
import os
import shutil
import tempfile

with tempfile.TemporaryDirectory() as folder:
    source = os.path.join(folder, 'src', 'nested')
    os.makedirs(source)
    for name in ('a.txt', 'b.pyc', 'tmp1'):
        with open(os.path.join(source, name), 'w') as handle:
            handle.write('x')

    # O(n + E) - every byte copied and every entry walked
    target = os.path.join(folder, 'dst')
    shutil.copytree(os.path.join(folder, 'src'), target)
    assert sorted(os.listdir(os.path.join(target, 'nested'))) == ['a.txt', 'b.pyc', 'tmp1']

    # ignore is a callable, run once per directory - O(patterns * e)
    filtered = os.path.join(folder, 'filtered')
    shutil.copytree(
        os.path.join(folder, 'src'), filtered,
        ignore=shutil.ignore_patterns('*.pyc', 'tmp*'),
    )
    assert os.listdir(os.path.join(filtered, 'nested')) == ['a.txt']

    # O(E), and the tree is gone
    shutil.rmtree(target)
    assert not os.path.exists(target)
```

## Moving

Within one filesystem `move()` is a rename: the file is not read, and it keeps its inode. Across
filesystems there is no rename to make, so it becomes a copy followed by a delete.

```python
import os
import shutil
import tempfile

with tempfile.TemporaryDirectory() as folder:
    source = os.path.join(folder, 'a.txt')
    with open(source, 'w') as handle:
        handle.write('contents')
    inode = os.stat(source).st_ino

    target = os.path.join(folder, 'b.txt')
    shutil.move(source, target)   # O(1) - one rename

    assert os.stat(target).st_ino == inode   # the same file, renamed
    assert not os.path.exists(source)
```

!!! warning "The O(1) is the filesystem's, not the path's"
    `move()` tries `os.rename` first and falls back to `copy2` plus `rmtree`/`unlink` when the
    rename fails with `OSError`. Two paths under the same mount point are cheap; two paths that
    look adjacent but sit on different mounts are a full copy.

## Finding a Program

```python
import os
import shutil

# Checks stop at a match; splitting PATH still uses O(p + L) time and space
assert shutil.which('definitely-not-a-real-command') is None

found = shutil.which('python3')
if found is not None:
    assert os.path.isabs(found)
    assert os.access(found, os.X_OK)

# An explicit path replaces the environment's
assert shutil.which('anything', path='') is None
```

## Disk Usage and Terminal Size

```python
import shutil

usage = shutil.disk_usage('.')   # O(1) - one statvfs
assert usage.total >= usage.used
assert usage.total == usage.used + usage.free or usage.free <= usage.total

size = shutil.get_terminal_size()   # O(1)
assert size.columns > 0 and size.lines > 0
```

## Archives

```python
import os
import shutil
import tempfile

with tempfile.TemporaryDirectory() as folder:
    source = os.path.join(folder, 'payload')
    os.makedirs(source)
    with open(os.path.join(source, 'a.txt'), 'w') as handle:
        handle.write('contents')

    # O(n + E) - every entry walked and every byte compressed
    archive = shutil.make_archive(os.path.join(folder, 'bundle'), 'tar', source)
    assert archive.endswith('.tar')

    restored = os.path.join(folder, 'restored')
    shutil.unpack_archive(archive, restored)   # O(n + E)
    assert open(os.path.join(restored, 'a.txt')).read() == 'contents'

    # Fresh lists sorted by format name - O(f log f) worst-case time
    names = [name for name, _ in shutil.get_archive_formats()]
    assert 'tar' in names and 'zip' in names
    assert [name for name, _, _ in shutil.get_unpack_formats()]
```

### Registering a Format

```python
import shutil

def build(base_name, base_dir, **kwargs):
    return base_name + '.demo'

shutil.register_archive_format('demo', build, [], 'A demonstration format')   # O(1)
assert 'demo' in [name for name, _ in shutil.get_archive_formats()]

shutil.unregister_archive_format('demo')   # O(1)
assert 'demo' not in [name for name, _ in shutil.get_archive_formats()]
```

## Errors

`copytree()` collects per-entry copy failures and raises `Error` carrying their list.
`rmtree()` instead propagates a deletion exception immediately by default. Its `onexc` callback
(Python 3.12+) or older `onerror` callback can handle a failure and allow traversal to continue.

```python
import shutil

assert issubclass(shutil.SameFileError, shutil.Error)
assert issubclass(shutil.SpecialFileError, OSError)
assert issubclass(shutil.Error, OSError)

# Error carries what went wrong, per path
error = shutil.Error([('src', 'dst', 'permission denied')])
assert error.args[0][0] == ('src', 'dst', 'permission denied')
```

## Version Notes

- **Python 3.14**: on non-Windows systems, `COPY_BUFSIZE` rose from 64 KiB to 256 KiB; `zstdtar` joined the archive
  formats; `ExecError` was deprecated and dropped from `__all__`

## Related Documentation

- **[os](os.md)** - the layer underneath, including `os.rename` and `os.scandir`
- **[glob](glob.md)** - the other module whose cost is entries examined
- **[pathlib](pathlib.md)** - the object-oriented path API

## Best Practices

✅ **Do**:

- Use `copy2()` when timestamps matter and `copyfile()` when only the bytes do
- Budget for retained ancestor listings and paths as well as directory width
- Use `move()` within one filesystem when you want the rename; check the mount if it matters
- Pass `ignore=` to `copytree()` rather than copying and then deleting

❌ **Avoid**:

- Reading `copy()`'s O(1) space as zero; it is one `COPY_BUFSIZE` buffer
- Assuming `move()` is O(1) across mount points
- `rmtree()` on a path you have not checked — it does not ask
- `which()` in a loop; it walks `PATH` every call and caches nothing
