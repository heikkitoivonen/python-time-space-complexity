# zipfile Module Complexity

The `zipfile` module reads and writes ZIP archives. An archive ends in a central directory that
lists every member, so opening one reads the end of the file and that directory, and loads no
member: member data is read only when a member is, and it can be streamed rather than loaded
whole.

`n` is the members in the archive, `m` is the uncompressed bytes of the one member an operation
reads or writes, `t` is the total uncompressed bytes of all the members an operation touches, and
`k` is the bytes one call on a member stream reads or writes. Member names are treated as short,
so a name's length and its directory depth are O(1), and a member's compressed size is treated
as O(m).

## Complexity Reference

### ZipFile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zipfile.ZipFile(file, mode='r', compression=ZIP_STORED, allowZip64=True, compresslevel=None, *, strict_timestamps=True, metadata_encoding=None)` | O(n) | O(n) | Mode `'r'` reads the central directory into one `ZipInfo` per member; no member is loaded |
| `ZipFile(file, 'w')`, `ZipFile(file, 'x')` | O(1) | O(1) | Nothing is read; `'w'` truncates an existing file |
| `ZipFile(file, 'a')` | O(n) | O(n) | Reads the central directory, then writes new members over it |
| `ZipFile.close()` | O(n) | O(1) | After any change in `'w'`, `'x'` or `'a'`, writes the central directory for every member, old ones included; otherwise only closes the file |
| `ZipFile.namelist()` | O(n) | O(n) | A new list on every call |
| `ZipFile.infolist()` | O(1) | O(1) | The archive's own list of `ZipInfo` objects, not a copy |
| `ZipFile.getinfo(name)` | O(1) | O(1) | Dict lookup; raises `KeyError` for a missing name |
| `ZipFile.open(name, mode='r', pwd=None, *, force_zip64=False)` | O(1) | O(1) | Reads the member's local header; data is read as the stream is |
| `ZipFile.read(name, pwd=None)` | O(m) | O(m) | The whole member in one `bytes`, CRC checked |
| `ZipFile.extract(member, path=None, pwd=None)` | O(m) | O(1) | Streamed to disk; missing parent directories are created |
| `ZipFile.extractall(path=None, members=None, pwd=None)` | O(n + t) | O(n) | Takes a `namelist()` when `members` is omitted, then streams each member |
| `ZipFile.write(filename, arcname=None, compress_type=None, compresslevel=None)` | O(m) | O(1) | Streams the file from disk in fixed-size chunks |
| `ZipFile.writestr(zinfo_or_arcname, data, compress_type=None, compresslevel=None)` | O(m) | O(m) | `data` is the whole member, in memory; a `str` is encoded to a copy first |
| `ZipFile.mkdir(zinfo_or_directory_name, mode=511)` | O(1) | O(1) | Python 3.11+; a directory entry with no data |
| `ZipFile.testzip()` | O(n + t) | O(1) | Opens each entry by name and reads it in fixed-size chunks to check its CRC; returns the first bad name, or `None`. With a duplicate name, only the last entry is checked |
| `ZipFile.printdir(file=None)` | O(n) | O(1) | One line per member |
| `ZipFile.setpassword(pwd)` | O(1) | O(1) | The default password for encrypted members |
| `ZipFile.comment` | O(1) | O(1) | `bytes`; in `'w'`, `'x'` or `'a'`, assigning it makes `close()` rewrite the directory |
| `ZipFile.filename`, `ZipFile.debug` | O(1) | O(1) | Attributes |

### ZipExtFile

`ZipFile.open(name)` returns a `ZipExtFile`, a buffered binary stream over one member.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ZipExtFile.read(size=-1)`, `ZipExtFile.read1(size)` | O(k) | O(k) | `k` = bytes returned; the default reads to the end, O(m) |
| `ZipExtFile.readline(limit=-1)`, `ZipExtFile.peek(n=1)` | O(k) | O(k) | `k` = bytes of the line, or the `n` asked for |
| `ZipExtFile.seek(offset, whence=0)` | O(1) stored, O(d) compressed | O(1) | Python 3.12+ for O(1) on a stored, unencrypted member. Otherwise `d` is the distance moved forward; a backward seek past the read buffer restarts from the member's start, so `d` is the target position |
| `ZipExtFile.tell()`, `ZipExtFile.seekable()`, `ZipExtFile.readable()`, `ZipExtFile.close()` | O(1) | O(1) | |
| `write(b)` on `ZipFile.open(name, 'w')` | O(k) | O(k) | `k = len(b)`; the member is added to the directory when the stream closes |

### ZipInfo

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zipfile.ZipInfo(filename='NoName', date_time=(1980, 1, 1, 0, 0, 0))` | O(1) | O(1) | |
| `ZipInfo.from_file(filename, arcname=None, *, strict_timestamps=True)` | O(1) | O(1) | One `stat()`; the file is not read |
| `ZipInfo.is_dir()` | O(1) | O(1) | The name ends in `/` |
| `ZipInfo._for_archive(archive)` | O(1) | O(1) | Python 3.14+; fills in the archive's compression settings |
| `ZipInfo.compress_level` | O(1) | O(1) | Python 3.13+; the level a member is written with |
| `ZipInfo.filename`, `ZipInfo.date_time`, `ZipInfo.compress_type`, `ZipInfo.comment`, `ZipInfo.extra`, `ZipInfo.create_system`, `ZipInfo.create_version`, `ZipInfo.extract_version`, `ZipInfo.reserved`, `ZipInfo.flag_bits`, `ZipInfo.volume`, `ZipInfo.internal_attr`, `ZipInfo.external_attr`, `ZipInfo.header_offset`, `ZipInfo.CRC`, `ZipInfo.compress_size`, `ZipInfo.file_size` | O(1) | O(1) | Parsed from the central directory when the archive is opened |

### Path

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zipfile.Path(root, at='')` | O(1) | O(1) | Given a filename, opens it first, O(n); given a read-mode `ZipFile`, switches that object to a subclass that caches its name index |
| `Path.exists()`, `Path.is_file()`, `Path.joinpath(*other)`, `Path / other` | O(n) first, then O(1) | O(n) | The first call builds an index of names and implied directories; on a writable `ZipFile` the index is rebuilt on every call |
| `Path.is_dir()` | O(1) | O(1) | Decided by a trailing `/`, which `joinpath()` adds only for a directory in the archive |
| `Path.iterdir()` | O(n) | O(n) first, then O(1) | Lazily filters every name in the archive, however few are in the directory; the name list is built as for `exists()` |
| `Path.glob(pattern)`, `Path.rglob(pattern)` | O(n) | O(n) first, then O(1) | Python 3.12+; lazily matches every name in the archive against one regex |
| `Path.open(mode='r', *args, pwd=None, **kwargs)` | O(1) | O(1) | After the index; as `ZipFile.open()`, wrapped in a text stream unless `mode` has `'b'` |
| `Path.read_text(*args, **kwargs)`, `Path.read_bytes()` | O(m) | O(m) | The whole member |
| `Path.name`, `Path.filename`, `Path.parent` | O(1) | O(1) | String operations on the path |
| `Path.suffix`, `Path.suffixes`, `Path.stem` | O(1) | O(1) | Python 3.11+ |
| `Path.match(path_pattern)`, `Path.relative_to(other, *extra)`, `Path.is_symlink()` | O(1) | O(1) | Python 3.12+; `is_symlink()` is `False` for every entry on 3.12 and reads the entry's mode bits from 3.13 |

### PyZipFile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zipfile.PyZipFile(file, mode='r', compression=ZIP_STORED, allowZip64=True, optimize=-1)` | O(n) | O(n) | As `ZipFile` |
| `PyZipFile.writepy(pathname, basename='', filterfunc=None)` | O(e log e + s) | O(e + s) | `e` = directory entries listed and sorted, `s` = bytes of the modules added; a package directory is added recursively. Compiling a module with no up-to-date `.pyc` is extra |

### Functions, constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zipfile.is_zipfile(filename)` | O(1) | O(1) | Reads a bounded tail of the file to find the end-of-archive record; the members are not checked. Python 3.14+ restores a file object's position |
| `zipfile.ZIP_STORED`, `zipfile.ZIP_DEFLATED`, `zipfile.ZIP_BZIP2`, `zipfile.ZIP_LZMA` | O(1) | O(1) | Compression methods; `ZIP_STORED` is the default. They change the constant factor, not the bound |
| `zipfile.ZIP_ZSTANDARD` | O(1) | O(1) | Python 3.14+ |
| `zipfile.BadZipFile`, `zipfile.error`, `zipfile.BadZipfile` | O(1) | O(1) | One class under three names; raised for a file that is not a ZIP archive or a member that fails its CRC |
| `zipfile.LargeZipFile` | O(1) | O(1) | Raised when an archive would need ZIP64 and `allowZip64=False` |

## Opening an Archive

Opening reads the central directory at the end of the file: O(n) in the member count, whether
the members hold ten bytes or ten gigabytes. After that, `getinfo()` is a dict
lookup and `infolist()` hands back the list the archive already holds.

```python
import io
import zipfile

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:  # O(1)
    archive.writestr('a.txt', b'alpha')        # O(m)
    archive.writestr('b.txt', b'beta')
# close() wrote the central directory - O(n)

with zipfile.ZipFile(buffer) as archive:       # O(n) - directory only
    assert archive.getinfo('b.txt').file_size == 4  # O(1)
    assert archive.infolist() is archive.infolist()  # O(1) - the same list
    assert archive.namelist() == ['a.txt', 'b.txt']  # O(n) - a new list
```

### Checking for a Member

`name in archive.namelist()` builds a list of every name to answer one question. `getinfo()`
answers it with a dict lookup; for many checks, build a set once.

```python
import io
import zipfile

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:
    for index in range(100):
        archive.writestr(f'file{index}.txt', b'x')

with zipfile.ZipFile(buffer) as archive:
    try:
        archive.getinfo('missing.txt')  # O(1)
    except KeyError as error:
        assert 'missing.txt' in str(error)
    else:
        raise AssertionError('a missing member was found')

    names = set(archive.namelist())  # O(n) once
    assert 'file7.txt' in names       # O(1) per check
```

## Reading Members

### Whole Member vs Streaming

`read()` returns the whole member as one `bytes`. `open()` returns a stream that decompresses as
it is read, so memory follows the chunk size instead of the member.

```python
import hashlib
import io
import zipfile

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('data.bin', bytes(range(256)) * 1000)

with zipfile.ZipFile(buffer) as archive:
    whole = archive.read('data.bin')  # O(m) time and memory

    digest = hashlib.sha256()
    with archive.open('data.bin') as stream:  # O(1)
        while chunk := stream.read(4096):      # O(k) per chunk
            digest.update(chunk)

assert digest.digest() == hashlib.sha256(whole).digest()
```

### Seeking Within a Member

A stored, unencrypted member seeks in O(1) on Python 3.12+. A compressed member cannot jump: a
forward seek decompresses the bytes it skips, and a backward seek past what is buffered starts
again from the beginning of the member. Read a compressed member in order rather than jumping around in it.

```python
import io
import zipfile

payload = bytes(range(256)) * 400

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:
    archive.writestr('stored.bin', payload)  # ZIP_STORED is the default
    archive.writestr('packed.bin', payload, compress_type=zipfile.ZIP_DEFLATED)

with zipfile.ZipFile(buffer) as archive:
    with archive.open('stored.bin') as stream:
        stream.seek(90_000)                 # O(1) on 3.12+
        assert stream.read(3) == payload[90_000:90_003]

    with archive.open('packed.bin') as stream:
        stream.seek(90_000)                 # O(d) - decompresses 90,000 bytes
        stream.seek(10)                     # backward: restarts from byte 0
        assert stream.read(3) == payload[10:13]
```

## Writing Archives

### Adding Files

`write()` streams a file from disk and never holds it. `writestr()` takes the member's bytes as
one object, so the data is in memory already. For data produced piece by piece, `open(name, 'w')`
gives a stream to write it through.

```python
import os
import tempfile
import zipfile

with tempfile.TemporaryDirectory() as folder:
    source = os.path.join(folder, 'source.txt')
    with open(source, 'wb') as handle:
        handle.write(b'line\n' * 1000)

    target = os.path.join(folder, 'out.zip')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(source, arcname='source.txt')  # O(m) time, O(1) memory
        archive.writestr('note.txt', 'short text')    # O(m) - data held in memory
        with archive.open('generated.txt', 'w') as stream:
            for index in range(100):
                stream.write(b'%d\n' % index)          # O(k) per write

    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ['source.txt', 'note.txt', 'generated.txt']
        assert archive.getinfo('source.txt').file_size == 5000
        assert archive.testzip() is None  # O(n + t) - reads every member
```

### Appending

Mode `'a'` adds members without rewriting the existing members' data. It is still not O(m):
opening reads the central directory, and closing writes it again for every member, so adding one
member to an archive of n costs O(n + m).

```python
import io
import zipfile

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:
    archive.writestr('old.txt', b'old data')
before = buffer.getvalue()

with zipfile.ZipFile(buffer, 'a') as archive:  # O(n) - reads the directory
    archive.writestr('new.txt', b'new data')    # O(m)
# close() rewrote the directory - O(n)

after = buffer.getvalue()
member_bytes = before.index(b'PK\x01\x02')     # where the old directory began
assert after[:member_bytes] == before[:member_bytes]  # old member data untouched

with zipfile.ZipFile(buffer) as archive:
    assert archive.namelist() == ['old.txt', 'new.txt']
```

### Replacing or Removing a Member

No method replaces or removes a member. Writing a name that already exists adds a second entry
with a `UserWarning`, and `getinfo()` returns the later one. To drop or replace a member, copy the
archive into a new one: O(n + t).

```python
import io
import warnings
import zipfile

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:
    archive.writestr('keep.txt', b'keep')
    archive.writestr('drop.txt', b'drop')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        archive.writestr('keep.txt', b'newer')
    assert 'Duplicate name' in str(caught[0].message)

with zipfile.ZipFile(buffer) as archive:
    assert archive.namelist() == ['keep.txt', 'drop.txt', 'keep.txt']
    assert archive.read('keep.txt') == b'newer'  # the later entry wins

    rewritten = io.BytesIO()
    with zipfile.ZipFile(rewritten, 'w') as copy:
        for info in archive.infolist():            # O(n)
            if info.filename != 'drop.txt' and archive.getinfo(info.filename) is info:
                copy.writestr(info.filename, archive.read(info))  # O(m) per member

with zipfile.ZipFile(rewritten) as archive:
    assert archive.namelist() == ['keep.txt']
    assert archive.read('keep.txt') == b'newer'
```

## Extracting Archives

`extractall()` takes the member list, then streams each member to disk, so memory follows the
member count and not the data. `extract()` does the same for one member.

```python
import io
import os
import tempfile
import zipfile

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:
    archive.writestr('docs/readme.txt', b'hello')
    archive.writestr('docs/deep/nested.txt', b'nested')

with tempfile.TemporaryDirectory() as folder, zipfile.ZipFile(buffer) as archive:
    path = archive.extract('docs/readme.txt', folder)  # O(m)
    assert os.path.relpath(path, folder) == os.path.join('docs', 'readme.txt')

    archive.extractall(folder)  # O(n + t) time, O(n) memory
    with open(os.path.join(folder, 'docs', 'deep', 'nested.txt'), 'rb') as handle:
        assert handle.read() == b'nested'
```

## Navigating with zipfile.Path

`zipfile.Path` looks like `pathlib`, but the archive has no directory tree to walk. The first
lookup on a read-mode archive builds an index of every name and implied directory, O(n), and
later lookups are O(1). `iterdir()` gets no help from it: each call filters every name in the
archive, so walking a tree with `iterdir()` costs O(n) per directory. One `namelist()` or one
`rglob()` visits each name once.

```python
import io
import zipfile

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:
    archive.writestr('top.txt', b'top')
    for index in range(100):
        archive.writestr(f'pkg/sub{index % 4}/mod{index}.py', b'')

with zipfile.ZipFile(buffer) as archive:
    root = zipfile.Path(archive)             # O(1)
    package = root / 'pkg'                   # O(n) builds the index once
    assert package.is_dir()                  # O(1)
    assert (root / 'top.txt').exists()       # O(1) after the index
    assert (root / 'top.txt').read_text(encoding='utf-8') == 'top'  # O(m)

    children = sorted(child.name for child in package.iterdir())  # O(n)
    assert children == ['sub0', 'sub1', 'sub2', 'sub3']

    modules = [name for name in archive.namelist() if name.endswith('.py')]  # O(n)
    assert len(modules) == 100
```

A read-mode `ZipFile` passed to `Path` becomes that caching subclass, and stays one: its
`namelist()` returns the same cached list from then on, with implied directories such as
`'pkg/'` added. Pass a filename, or a separate `ZipFile`, to keep the original behaviour.

## Common Patterns

### Filtering Members by Name

```python
import io
import zipfile

buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w') as archive:
    archive.writestr('a.txt', b'one\ntwo\n')
    archive.writestr('b.log', b'ignored')
    archive.writestr('c.txt', b'three\n')

lines = 0
with zipfile.ZipFile(buffer) as archive:
    for info in archive.infolist():       # O(1) to get, O(n) to walk
        if info.filename.endswith('.txt') and not info.is_dir():
            with archive.open(info) as stream:  # streamed, O(k) memory
                lines += sum(1 for _ in stream)

assert lines == 3
```

### Building an Archive from a Directory

```python
import os
import tempfile
import zipfile

with tempfile.TemporaryDirectory() as folder:
    tree = os.path.join(folder, 'tree')
    os.makedirs(os.path.join(tree, 'sub'))
    for name in ('a.txt', os.path.join('sub', 'b.txt')):
        with open(os.path.join(tree, name), 'w', encoding='utf-8') as handle:
            handle.write(name)

    target = os.path.join(folder, 'tree.zip')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for directory, _, files in os.walk(tree):
            for name in files:
                path = os.path.join(directory, name)
                archive.write(path, os.path.relpath(path, tree))  # O(m) per file
    # O(n + t) for the archive, and O(1) memory per file

    with zipfile.ZipFile(target) as archive:
        assert sorted(archive.namelist()) == ['a.txt', 'sub/b.txt']
```

## Performance Best Practices

✅ **Do**:

- Check for a member with `getinfo()`, or a set built once, rather than `in namelist()`
- Stream large members with `open()` instead of `read()`, so memory follows the chunk
- Add files from disk with `write()`, which streams, rather than reading them into `writestr()`
- Read compressed members front to back; seeking backward past the buffer restarts decompression
- Batch additions into one `'a'` session: each open and close costs O(n)
- Walk an archive with one `namelist()` or `rglob()`, not recursive `iterdir()` calls

❌ **Avoid**:

- `name in archive.namelist()` in a loop - a new O(n) list per check
- Reopening an archive in `'a'` mode for each new member - O(n) per member on top of its data
- Writing a name twice to replace it - the old entry stays in the archive
- `is_zipfile()` as a completeness check - it reads only the end record, not the members

## Version Notes

- **Python 3.11+**: Added `ZipFile.mkdir()`, the `metadata_encoding` argument, and
  `Path.stem`, `Path.suffix` and `Path.suffixes`
- **Python 3.12+**: Seeking a stored, unencrypted member is O(1); before, it read through the
  bytes skipped, and a backward seek re-read from the start. Added `Path.glob()`, `Path.rglob()`,
  `Path.match()`, `Path.is_symlink()` and `Path.relative_to()`
- **Python 3.13+**: `Path.is_symlink()` reports symlink entries; on 3.12 it is always `False`
- **Python 3.14+**: Added `ZIP_ZSTANDARD`, which needs the `compression.zstd` module.
  `is_zipfile()` restores the position of a file object it is given
- **All Python 3**: No method removes or replaces a member; rewrite the archive to do either

## Related Modules

- **[tarfile](tarfile.md)** - tar archives
- **[shutil](shutil.md)** - `make_archive()` and `unpack_archive()` for whole-directory work
- **[zipimport](zipimport.md)** - importing modules straight from a ZIP archive
- **[zlib](zlib.md)** - the compressor behind `ZIP_DEFLATED`
- **[io](io.md)** - `BytesIO` for building and reading archives in memory
