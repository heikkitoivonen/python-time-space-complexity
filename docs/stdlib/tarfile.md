# tarfile Module Complexity

The `tarfile` module reads and writes tar archives, plain or compressed with gzip, bzip2, lzma or
Zstandard. A tar archive has no index: it is a sequence of members, each a header block followed by
its data, so finding anything means walking headers from the start. Data is copied in fixed-size
chunks, so what a `TarFile` holds grows with its member count, not with the size of the archive.

`n` is members in the archive, `s` is the data bytes of one member, `S` is the data bytes of every
member an operation extracts or adds, and `B` is the uncompressed archive bytes before the point an
operation has to reach. `e` is the files and directories under a directory passed to `add()`, and
`d` is the directory members `extractall()` creates. A header is priced at O(1), and so is a
filter's path resolution: each grows with the length of one member's name, not with the archive.

## Complexity Reference

### Opening and Closing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tarfile.open(name=None, mode='r', fileobj=None, bufsize=10240, **kwargs)` | O(1) | O(1) | Reading reads the first header only; `'r'` and `'r:*'` try each decompressor on the start of the file first |
| `tarfile.open(name, 'a')` | O(n) | O(n) | Appending walks every header to find the end of the archive, and keeps them |
| `tarfile.open(..., stream=True)` | O(1) | O(1) | Python 3.13+: headers are not cached, so iterating holds one at a time and `getmembers()` returns an empty list |
| `tarfile.TarFile(name=None, mode='r', fileobj=None, format=DEFAULT_FORMAT, ...)` | O(1) | O(1) | Uncompressed only; `open()` picks the compression and calls it |
| `tarfile.is_tarfile(name)` | O(1) | O(1) | Opens the archive and reads its first header; Python 3.11+ restores a file object's position |
| `TarFile.close()` | O(1) | O(1) | Writing modes append two zero blocks and pad the archive to a multiple of 10,240 bytes |

### TarFile Reading

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TarFile.getmembers()` | O(n) first call on a plain seekable file, O(B) compressed or streamed; then O(1) | O(n) | Seeks past member data when it can, and must decompress through it when it cannot; returns the same cached list every time |
| `TarFile.getnames()` | O(n), plus `getmembers()` on the first call | O(n) | A new list per call |
| `TarFile.getmember(name)` | O(n), plus `getmembers()` on the first call | O(1) | Every call scans the member list from the end, so the last duplicate wins |
| `TarFile.next()`, iterating a `TarFile` | O(1) per member plain, O(s) compressed or streamed | O(1) per member | Each header is appended to the member cache, in stream modes too, so iterating to the end holds O(n) unless `stream=True` |
| `TarFile.extractfile(member)` | O(1) for a regular file's `TarInfo`, plus `getmember()` for a name | O(1) | Returns a buffered reader; nothing is read until you read it. A link's target is looked up by name, as `getmember()` does |
| Reading an `extractfile()` object | O(s), plus O(B) to rewind a compressed archive | O(s) for `read()`, O(k) for `read(k)` | k = bytes asked for. A compressed archive can seek backwards only by decompressing again from the start; a stream cannot at all |
| `TarFile.list(verbose=True, *, members=None)` | O(n) after iterating the archive | O(n) | Prints one line per member to standard output |

### TarFile Extraction

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TarFile.extract(member, path='', set_attrs=True, *, numeric_owner=False, filter=None)` | O(s), plus `getmember()` for a name | O(1) | Copies in fixed-size chunks; a member behind the current position of a compressed archive costs a rewind, as reading does |
| `TarFile.extractall(path='.', members=None, *, numeric_owner=False, filter=None)` | O(n + S + d log d) plain, O(B + d log d) compressed | O(n) | One pass when `members` is omitted or in archive order; directory attributes are set last, after their contents are written |
| `TarFile.extraction_filter` | O(1) | O(1) | The filter used when a call passes none; `None` means the version's default |
| `TarFile.errorlevel` | O(1) | O(1) | 0 skips a member that fails to extract, 1 raises fatal errors (the default), 2 raises `ExtractError` too |

### TarFile Writing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TarFile.add(name, arcname=None, recursive=True, *, filter=None)` | O(s) for a file, O(e log e + S) for a directory | O(e) | Each directory's entries are sorted; each member written joins the member cache |
| `TarFile.addfile(tarinfo, fileobj=None)` | O(s) | O(1) | Reads `tarinfo.size` bytes from `fileobj` in chunks; Python 3.13+ raises `ValueError` if a non-empty regular file has none |
| `TarFile.gettarinfo(name=None, arcname=None, fileobj=None)` | O(1) | O(1) | One `stat` call, plus a user and group name lookup |
| `TarFile.pax_headers` | O(1) | O(1) | Global pax headers: written at the start when given in `PAX_FORMAT`, filled from the archive when reading |

### TarInfo

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tarfile.TarInfo(name='')` | O(1) | O(1) | A header with defaults: a regular file of size 0 |
| `TarInfo.frombuf(buf, encoding, errors)` | O(1) | O(1) | Parses one 512-byte block; raises `HeaderError` on a bad one |
| `TarInfo.fromtarfile(tarfile)` | O(1) | O(1) | Reads the next header, including any long-name or pax blocks, from an open `TarFile` |
| `TarInfo.tobuf(format=DEFAULT_FORMAT, encoding=ENCODING, errors='surrogateescape')` | O(1) | O(1) | A multiple of 512 bytes; a long name adds extended blocks |
| `TarInfo.replace(**attrs, deep=True)` | O(1) | O(1) | Returns a copy; `deep=True` also copies `pax_headers` |
| `TarInfo.isfile()`, `TarInfo.isreg()`, `TarInfo.isdir()`, `TarInfo.issym()`, `TarInfo.islnk()`, `TarInfo.ischr()`, `TarInfo.isblk()`, `TarInfo.isfifo()`, `TarInfo.isdev()` | O(1) | O(1) | Compare `type` against the type constants |
| `TarInfo.name`, `TarInfo.size`, `TarInfo.mtime`, `TarInfo.mode`, `TarInfo.type`, `TarInfo.linkname`, `TarInfo.uid`, `TarInfo.gid`, `TarInfo.uname`, `TarInfo.gname`, `TarInfo.chksum`, `TarInfo.devmajor`, `TarInfo.devminor`, `TarInfo.offset`, `TarInfo.offset_data`, `TarInfo.sparse`, `TarInfo.pax_headers` | O(1) | O(1) | Plain attributes |

### Extraction Filters

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tarfile.data_filter(member, path)` | O(1) | O(1) | Strips leading slashes; rejects paths and links leaving `path`, absolute links and special files; drops ownership and unsafe mode bits |
| `tarfile.tar_filter(member, path)` | O(1) | O(1) | Strips leading slashes; rejects paths leaving `path`; strips high mode bits and group and other write |
| `tarfile.fully_trusted_filter(member, path)` | O(1) | O(1) | Returns `member` unchanged |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tarfile.TarError` | O(1) | O(1) | Base class of every exception below |
| `tarfile.ReadError`, `tarfile.CompressionError`, `tarfile.StreamError`, `tarfile.ExtractError`, `tarfile.HeaderError` | O(1) | O(1) | Not a tar archive; a compression method is unavailable or unknown; a stream was asked to go backwards; a non-fatal extraction error; a bad header block |
| `tarfile.FilterError` | O(1) | O(1) | Base of the filter errors; `FilterError.tarinfo` is the rejected member |
| `tarfile.AbsolutePathError`, `tarfile.OutsideDestinationError`, `tarfile.SpecialFileError`, `tarfile.AbsoluteLinkError`, `tarfile.LinkOutsideDestinationError`, `tarfile.LinkFallbackError` | O(1) | O(1) | The reasons a filter rejects a member |

## Reading Archives

### Listing Walks Every Header

A tar archive has no table of contents, so `getmembers()` reads every header. On a plain file it
seeks past each member's data, so the cost follows the member count. Through a decompressor there
is nothing to seek past, and the whole archive is decompressed to reach the last header.

```python
import io
import tarfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w') as tar:
    for index in range(3):
        info = tarfile.TarInfo(f'file{index}.txt')
        info.size = 5
        tar.addfile(info, io.BytesIO(b'hello'))  # O(s)

buffer.seek(0)
with tarfile.open(fileobj=buffer, mode='r') as tar:  # O(1) - reads the first header
    members = tar.getmembers()  # O(n) - reads the rest
    assert [member.name for member in members] == ['file0.txt', 'file1.txt', 'file2.txt']
    assert tar.getmembers() is members  # O(1) - the cached list, not a copy
    assert tar.getnames() == ['file0.txt', 'file1.txt', 'file2.txt']  # O(n)
```

### Looking Up a Member by Name

`getmember()` has no index to use. Every call scans the cached list from the end, so looking up
every member by name is quadratic. Build a dictionary once, or pass the `TarInfo` you already have.

```python
import io
import tarfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w') as tar:
    for name in ['a.txt', 'b.txt', 'a.txt']:
        info = tarfile.TarInfo(name)
        info.size = len(name)
        tar.addfile(info, io.BytesIO(name.encode()))

buffer.seek(0)
with tarfile.open(fileobj=buffer) as tar:
    latest = tar.getmember('a.txt')  # O(n) on every call
    assert latest.offset > tar.getmember('b.txt').offset  # the last duplicate wins

    by_name = {member.name: member for member in tar}  # O(n) once
    assert by_name['a.txt'] is latest  # O(1) per lookup afterwards
```

### Reading Member Data

For a regular file, `extractfile()` returns a reader and reads nothing. `read()` holds the whole
member; `read(k)` holds `k` bytes. Passing the `TarInfo` skips the name lookup.

```python
import io
import tarfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w') as tar:
    info = tarfile.TarInfo('data.bin')
    info.size = 10_000
    tar.addfile(info, io.BytesIO(bytes(10_000)))

buffer.seek(0)
with tarfile.open(fileobj=buffer) as tar:
    member = tar.next()  # O(1) - the first header
    reader = tar.extractfile(member)  # O(1) - no name lookup, nothing read yet
    total = 0
    for chunk in iter(lambda: reader.read(4096), b''):  # O(k) memory per chunk
        total += len(chunk)
    assert total == 10_000

    whole = tar.extractfile('data.bin').read()  # O(n) lookup, then O(s) memory
    assert len(whole) == 10_000

    folder = tarfile.TarInfo('folder')
    folder.type = tarfile.DIRTYPE
    assert tar.extractfile(folder) is None  # no data to read
```

## Compressed Archives and Streams

### Random Access Decompresses Again

A compressed archive can only move backwards by starting its decompressor over. After the members
are loaded, reading one near the end decompresses almost the whole archive again; a plain `.tar`
seeks straight to it. Where members are read out of order, read them in one forward pass instead.

```python
import io
import tarfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
    for index in range(3):
        info = tarfile.TarInfo(f'part{index}')
        info.size = 4
        tar.addfile(info, io.BytesIO(b'data'))

buffer.seek(0)
with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
    last = tar.getmembers()[-1]  # O(B) - decompresses to the end
    assert tar.extractfile(last).read() == b'data'  # rewinds: O(B) again

buffer.seek(0)
with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
    contents = {member.name: tar.extractfile(member).read() for member in tar}  # one pass
    assert contents == {'part0': b'data', 'part1': b'data', 'part2': b'data'}
```

### Stream Modes

A `|` mode reads or writes a non-seekable stream such as a pipe or socket. Each member can be read
only while it is current: going back raises `StreamError`. A `|` mode does not bound memory, as
every header read is still cached; on Python 3.13+, `stream=True` stops that in any reading mode.

```python
import io
import tarfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w|gz') as tar:
    for name in ['first', 'second']:
        info = tarfile.TarInfo(name)
        info.size = 3
        tar.addfile(info, io.BytesIO(b'abc'))

buffer.seek(0)
with tarfile.open(fileobj=buffer, mode='r|gz') as tar:
    first = tar.next()
    assert tar.extractfile(first).read() == b'abc'  # fine while it is current
    tar.next()  # O(s) - reads past the first member's data
    try:
        tar.extractfile(first).read()
    except tarfile.StreamError as error:
        assert 'backwards' in str(error)
    else:
        raise AssertionError('a stream sought backwards')

    assert len(tar.getmembers()) == 2  # O(n) headers held, even streaming
```

```python
import io
import sys
import tarfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w|gz') as tar:
    for name in ['first', 'second']:
        info = tarfile.TarInfo(name)
        info.size = 3
        tar.addfile(info, io.BytesIO(b'abc'))

if sys.version_info >= (3, 13):
    buffer.seek(0)
    with tarfile.open(fileobj=buffer, mode='r|gz', stream=True) as tar:
        sizes = [member.size for member in tar]  # O(1) space per header
        assert sizes == [3, 3]
        assert tar.getmembers() == []  # nothing was kept
```

## Extracting Safely

### Filters

A filter sees each member before it is written and can reject or rewrite it. `'data'` is the one
to use for archives from anywhere else: it strips leading slashes and refuses `..` escapes, links
that point outside the destination and device files. Its checks cost O(1) per member, and the
default changed between releases, so pass `filter=` explicitly.

```python
import io
import os
import tarfile
import tempfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w') as tar:
    for name in ['safe.txt', '../escape.txt']:
        info = tarfile.TarInfo(name)
        info.size = 2
        tar.addfile(info, io.BytesIO(b'ok'))

with tempfile.TemporaryDirectory() as root:
    buffer.seek(0)
    with tarfile.open(fileobj=buffer) as tar:
        tar.extract('safe.txt', root, filter='data')  # O(n) lookup + O(s) copy
        try:
            tar.extract('../escape.txt', root, filter='data')
        except tarfile.OutsideDestinationError as error:
            assert error.tarinfo.name == '../escape.txt'
        else:
            raise AssertionError('a member escaped the destination')
    assert os.listdir(root) == ['safe.txt']
```

### Extracting Everything

`extractall()` makes one forward pass when it extracts members in archive order, which it does
unless you pass `members` in another order, so it suits compressed archives and streams alike. It
applies the filter to each member and sets directory attributes at the end, after their contents
are written.

```python
import io
import os
import tarfile
import tempfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
    folder = tarfile.TarInfo('folder')
    folder.type = tarfile.DIRTYPE
    tar.addfile(folder)
    for name in ['folder/a.txt', 'folder/b.txt']:
        info = tarfile.TarInfo(name)
        info.size = 1
        tar.addfile(info, io.BytesIO(b'x'))

with tempfile.TemporaryDirectory() as root:
    buffer.seek(0)
    with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
        tar.extractall(root, filter='data')  # O(B + d log d) through gzip, one pass
    assert sorted(os.listdir(os.path.join(root, 'folder'))) == ['a.txt', 'b.txt']
```

## Writing Archives

### Adding Files and Directories

`add()` streams each file into the archive in chunks. Given a directory it recurses, sorting each
directory's entries so the archive order does not depend on the filesystem. `addfile()` takes a
`TarInfo` you built and a file object to read `size` bytes from, with no file on disk needed.

```python
import io
import os
import tarfile
import tempfile

with tempfile.TemporaryDirectory() as root:
    source = os.path.join(root, 'src')
    os.mkdir(source)
    for name in ['b.txt', 'a.txt']:
        with open(os.path.join(source, name), 'w') as f:
            f.write(name)

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        tar.add(source, arcname='src')  # O(e log e + S)
        info = tarfile.TarInfo('src/generated.txt')
        info.size = 9
        tar.addfile(info, io.BytesIO(b'generated'))  # O(s)

buffer.seek(0)
with tarfile.open(fileobj=buffer) as tar:
    assert tar.getnames() == ['src', 'src/a.txt', 'src/b.txt', 'src/generated.txt']
```

### Building Headers by Hand

A header is one 512-byte block, plus extended blocks for a name that does not fit. `replace()`
copies one with some attributes changed.

```python
import tarfile

info = tarfile.TarInfo('notes.txt')  # O(1)
info.size = 100
block = info.tobuf(tarfile.USTAR_FORMAT)  # O(1)
assert len(block) == 512

parsed = tarfile.TarInfo.frombuf(block, tarfile.ENCODING, 'surrogateescape')  # O(1)
assert (parsed.name, parsed.size, parsed.isfile()) == ('notes.txt', 100, True)

long_name = tarfile.TarInfo('d/' * 100 + 'file')
assert len(long_name.tobuf(tarfile.PAX_FORMAT)) > 512  # extended blocks for the name

renamed = info.replace(name='renamed.txt', deep=False)  # O(1)
assert renamed is not info and renamed.name == 'renamed.txt' and info.name == 'notes.txt'
```

## Common Patterns

### Selecting Members in One Pass

```python
import io
import tarfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
    for name in ['keep.txt', 'skip.log', 'also.txt']:
        info = tarfile.TarInfo(name)
        info.size = len(name)
        tar.addfile(info, io.BytesIO(name.encode()))

buffer.seek(0)
texts = {}
with tarfile.open(fileobj=buffer, mode='r:gz') as tar:
    for member in tar:  # O(1) per header, O(s) to pass each member's data
        if member.isfile() and member.name.endswith('.txt'):
            texts[member.name] = tar.extractfile(member).read()  # O(s)

assert texts == {'keep.txt': b'keep.txt', 'also.txt': b'also.txt'}
```

### Checking Before Opening

```python
import io
import tarfile

buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w') as tar:
    tar.addfile(tarfile.TarInfo('empty'))

buffer.seek(0)
assert tarfile.is_tarfile(buffer)  # O(1) - the first header only
assert not tarfile.is_tarfile(io.BytesIO(b'not an archive' * 100))
```

## Performance Best Practices

✅ **Do**:

- Iterate the archive, or call `extractall()`, to process members in one forward pass
- Keep the `TarInfo` from iteration and pass it to `extractfile()` and `extract()`, so no name is looked up
- Build a dictionary from `getmembers()` when looking up many members by name
- Use a plain `.tar` when members are read in random order: it seeks, where a compressed archive decompresses again
- Read large members with `read(k)` in a loop, so memory follows the chunk
- Open an archive with too many members to hold with `stream=True` on Python 3.13+, and iterate it
- Pass `filter='data'` for archives you did not create

❌ **Avoid**:

- `getmember()` in a loop - O(n) per call
- Reading members of a `.tar.gz` out of order - each step backwards decompresses from the start
- Expecting a `|` stream mode to bound memory - every header is still cached
- `extractfile(member).read()` on a member too large to hold in memory
- Relying on the default extraction filter - it differs between releases

## Version Notes

- **Python 3.14+**: `extractall()` and `extract()` use the `'data'` filter when none is given; the `zst` modes read and write Zstandard
- **Python 3.13+**: `stream=True` stops the member cache; `addfile()` raises `ValueError` for a non-empty regular file with no `fileobj`
- **Python 3.12 and 3.13**: Extracting without a filter emits a `DeprecationWarning` and trusts the archive fully
- **Python 3.11+**: `is_tarfile()` restores the position of a file object it is given
- **Python 3.10.12+ and 3.11.4+**: Extraction filters; extracting without one trusts the archive fully and does not warn

## Related Modules

- **[zipfile](zipfile.md)** - Reads a central directory when opened, so a lookup by name is O(1) where tar's is O(n)
- **[gzip](gzip.md)** - The single-file compression behind `'r:gz'`, and the reason seeking backwards restarts
- **[shutil](shutil.md)** - `shutil.make_archive()` and `unpack_archive()` wrap this module
