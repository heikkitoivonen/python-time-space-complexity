# gzip Module Complexity

The `gzip` module reads and writes the gzip file format: DEFLATE-compressed data from
[zlib](zlib.md) wrapped in a small header and a CRC trailer. It offers one-shot functions and
`GzipFile`, a file object that compresses as it is written and decompresses as it is read.
DEFLATE works through a fixed 32 KiB window, so a stream is decoded as its bytes arrive and
nothing in the module holds a whole file unless you ask it to.

`m` is uncompressed bytes and `n` is compressed bytes. `c` is the bytes passed to one write,
`r` the larger of the bytes a read asks for and the bytes it returns, `k` the uncompressed bytes a
seek passes over, and `s` the gzip members concatenated in one input. The DEFLATE window, zlib's
working memory and `GzipFile`'s read and write buffers are fixed sizes that do not grow with the
input, so the bounds price them at O(1). The bounds assume compressed bytes produce output: input
that produces none, such as empty members or long zero padding, is passed over in a read or seek
at a cost outside them.

## Complexity Reference

### One-Shot Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gzip.compress(data, compresslevel=9, *, mtime=0)` | O(m) | O(n) | Linear at every level; the level changes the constant, not the growth. Memory follows the output, not the input |
| `gzip.decompress(data)` | O(n + m) | O(n + m) | One member. m can be far larger than n |
| `gzip.decompress(data)` over s concatenated members | O(s·n + m) | O(n + m) | Python 3.11+: each member after the first copies the rest of the input again; a `GzipFile` over the same bytes recopies at most one read buffer per member |

### GzipFile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gzip.open(filename, mode='rb', compresslevel=9, encoding=None, errors=None, newline=None)` | O(1) | O(1) | Reads nothing yet; text modes wrap the `GzipFile` in `io.TextIOWrapper` |
| `gzip.GzipFile(filename=None, mode=None, compresslevel=9, fileobj=None, mtime=None)` | O(1) | O(1) | Binary only. Write modes write the header at once; `close()` closes the underlying file only if the `GzipFile` opened it |
| `GzipFile.read(size=-1)`, `GzipFile.read1(size=-1)`, `GzipFile.readinto(b)`, `GzipFile.readinto1(b)` | O(r) | O(r) | `read()` with no size is O(m); `read1()` with no size returns at most one buffer. Concatenated members are read in turn |
| `GzipFile.readline(size=-1)`, `GzipFile.readlines(size=-1)`, iterating a `GzipFile` | O(r) | O(r) | |
| `GzipFile.peek(n)` | O(1) | O(1) | Returns what is buffered, decompressing one buffer only when nothing is; `n` does not bound the result |
| `GzipFile.seek(offset, whence=io.SEEK_SET)` in read mode | O(k) | O(1) | Emulated by decompressing: forward from the current position, or from the start of the file for a backward seek past the read buffer. The first `SEEK_END` decompresses to the end to learn the size, which is then kept |
| `GzipFile.seek(offset, whence=io.SEEK_SET)` in write mode | O(k) | O(1) | Forward only: writes k zero bytes. A backward seek raises `OSError`, `SEEK_END` raises `ValueError` |
| `GzipFile.rewind()` | O(1) | O(1) | `seek(0)`: the next read past the read buffer decompresses again from the first byte. Raises `OSError` in write mode |
| `GzipFile.tell()` | O(1) | O(1) | Uncompressed position |
| `GzipFile.write(data)`, `GzipFile.writelines(seq)` | O(c) | O(c) | c counts every item of `seq`. Compressed output reaches the file as zlib's buffers fill |
| `GzipFile.flush(zlib_mode=zlib.Z_SYNC_FLUSH)` | O(1) | O(1) | With the default `zlib_mode`, everything written so far reaches the file and can be decompressed from it |
| `GzipFile.close()` | O(1) | O(1) | In write mode ends the member with its CRC and length |
| `GzipFile.mtime` | O(1) | O(1) | The timestamp in the last member header read; `None` until a read has passed the first header |
| `GzipFile.mode`, `GzipFile.name`, `GzipFile.closed`, `GzipFile.fileno()`, `GzipFile.readable()`, `GzipFile.writable()`, `GzipFile.seekable()` | O(1) | O(1) | `mode` is `'rb'` or `'wb'` from Python 3.13; `seekable()` is `True` in both modes |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gzip.BadGzipFile` | O(1) | O(1) | An `OSError` for a bad header, CRC or length, or trailing bytes that are neither a member nor zero padding. A member cut short after its first two bytes raises `EOFError` instead |

## One-Shot vs Streaming

`compress()` and `decompress()` hold the whole result. A `GzipFile` read in chunks holds one
chunk. For untrusted input without a file, a `zlib` decompressor with gzip framing and a
`max_length` returns at most one chunk per call, holding the input it has not yet consumed, since m
can be far larger than n.

```python
import gzip
import zlib

data = b"log line\n" * 100_000

one_shot = gzip.compress(data)  # O(m) time, O(n) memory
assert gzip.decompress(one_shot) == data  # O(n + m) time and memory

# Decompress a bomb without holding its output
bomb = gzip.compress(b"\0" * 10_000_000)
decompressor = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)  # expect a gzip header
chunk = decompressor.decompress(bomb, 4096)  # at most 4096 bytes out
assert chunk == b"\0" * 4096
total = len(chunk)
while not decompressor.eof:
    total += len(decompressor.decompress(decompressor.unconsumed_tail, 1_000_000))
assert total == 10_000_000
```

## Concatenated Members

A gzip file may hold several members one after another: appending to a file adds one, and so
does concatenating two files. `decompress()` reads them all, but from Python 3.11 it hands each
member the rest of the input as a fresh copy, so it costs O(s·n). A `GzipFile` reads the same
bytes a buffer at a time and recopies at most one buffer per member.

```python
import gzip
import io

target = io.BytesIO()
with gzip.GzipFile(fileobj=target, mode="wb") as f:
    f.write(b"first ")
with gzip.GzipFile(fileobj=target, mode="ab") as f:  # appends a second member
    f.write(b"second")

assert gzip.decompress(target.getvalue()) == b"first second"  # O(s·n + m)

target.seek(0)
with gzip.GzipFile(fileobj=target) as f:
    assert f.read() == b"first second"  # O(n + m) plus one buffer per member

# Zero padding after a member is skipped; anything else is an error
assert gzip.decompress(target.getvalue() + b"\0" * 16) == b"first second"
try:
    gzip.decompress(target.getvalue() + b"junk")
except gzip.BadGzipFile as error:
    assert 'Not a gzipped file' in str(error)
else:
    raise AssertionError('trailing garbage was accepted')
```

## Reading and Writing Files

### Reading and Seeking

Opening reads nothing. A read decompresses as much as it returns, and `seek()` is emulated by
decompressing, so a backward seek past the read buffer starts again from the beginning.

```python
import gzip
import io

data = b"".join(b"record %06d\n" % i for i in range(50_000))
source = io.BytesIO(gzip.compress(data, mtime=0))

with gzip.open(source) as f:  # O(1) - nothing read yet
    assert f.mtime is None  # no header read yet
    assert f.readline() == b"record 000000\n"  # O(r)
    assert f.mtime == 0  # O(1) - from the header just read
    f.seek(350_000)  # O(k) - decompresses forward
    assert f.read(14) == b"record 025000\n"
    f.seek(14)  # O(k) - backward: rewinds to the start
    assert f.tell() == 14  # O(1)
    assert f.read(14) == b"record 000001\n"

# Text mode wraps the same file object
source.seek(0)
with gzip.open(source, "rt", encoding="ascii") as f:
    lines = sum(1 for _ in f)  # O(m) time, one line held at a time
assert lines == 50_000
```

### Writing and Flushing

`write()` hands data to the compressor, which passes compressed output on as its buffers fill.
`flush()` forces out everything written so far, so a reader of the file can decompress it before
the `GzipFile` is closed; `close()` then writes the trailer.

```python
import gzip
import io
import zlib

target = io.BytesIO()
f = gzip.GzipFile(fileobj=target, mode="wb", mtime=0)  # O(1) - writes the header
assert f.write(b"small record\n") == 13  # O(c)
f.flush()  # O(1) - the record is now in the file
reader = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)
assert reader.decompress(target.getvalue()) == b"small record\n"

f.close()  # O(1) - writes the CRC and length
assert gzip.decompress(target.getvalue()) == b"small record\n"
assert not target.closed  # a file object passed in stays open
```

## Common Patterns

### Compressing a File in Chunks

```python
import gzip
import io
import shutil

source = io.BytesIO(b"payload " * 500_000)
target = io.BytesIO()

with gzip.GzipFile(fileobj=target, mode="wb") as f:
    shutil.copyfileobj(source, f, 1024 * 1024)  # O(m) time, one chunk held

target.seek(0)
with gzip.GzipFile(fileobj=target) as f:
    size = sum(len(chunk) for chunk in iter(lambda: f.read(1024 * 1024), b""))  # O(m)
assert size == 4_000_000
```

## Performance Best Practices

✅ **Do**:

- Read a large file in chunks or lines, so memory follows the chunk rather than m
- Decompress untrusted input through `GzipFile` reads of bounded size, or a `zlib` decompressor
  with `max_length`, since m can be far larger than n
- Read inputs of many concatenated members through `GzipFile`, which recopies one buffer per
  member where `decompress()` recopies the rest of the input
- Call `flush()` when another process must be able to read what has been written so far

❌ **Avoid**:

- Seeking backward past the read buffer of a `GzipFile` - it decompresses again from the start
- `gzip.decompress()` or `read()` with no size on input you did not produce - both hold all of m

## Version Notes

- **Python 3.11+**: `decompress()` decodes each member itself and copies the rest of the input
  per member, so s members cost O(s·n + m); on 3.10 it reads through a `GzipFile` in O(n + m)
- **Python 3.13+**: `GzipFile.mode` is `'rb'` or `'wb'`; before, it is the integer
  `gzip.READ` or `gzip.WRITE`
- **Python 3.14+**: `compress()` writes an mtime of 0 by default, so equal input gives equal
  output; before, it writes the current time
- **Python 3.14+**: The module is also available as `compression.gzip`

## Related Modules

- **[zlib](zlib.md)** - DEFLATE streams, and decompressor objects that accept gzip framing
- **[compression](compression.md)** - `compression.gzip` re-exports this module
- **[bz2](bz2.md)** - bzip2 files with the same file interface
- **[lzma](lzma.md)** - XZ and LZMA files with the same file interface
- **[tarfile](tarfile.md)** - reads and writes `.tar.gz` archives through this module
- **[zipfile](zipfile.md)** - ZIP archives, which compress each member with DEFLATE
