# bz2 Module Complexity

The `bz2` module compresses and decompresses data in the bzip2 format, through one-shot
functions, streaming compressor and decompressor objects, and a file interface. libbzip2 works a
block at a time: the compressor sorts each block of input on its own, and the decompressor has to
take in a whole compressed block before it can return any of it.

`m` is uncompressed bytes and `n` is compressed bytes. `B` is the block size a stream is written
with, `compresslevel` × 100 kB, so at most 900 kB. `c` is the bytes passed to one streaming call,
`r` the larger of the bytes a read asks for and the bytes it returns, `k` the uncompressed bytes a
seek passes over, `s` the streams concatenated in one input, and `h` the unconsumed input a
decompressor holds from earlier calls.
Sorting or decoding one block costs at most a fixed amount at a given level, so a B term marks
where that work lands: the call that completes a block pays for it. The Space column counts the
buffers Python sees. libbzip2's own working memory is set by the block size and does not grow with
the input.

## Complexity Reference

### One-Shot Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bz2.compress(data, compresslevel=9)` | O(m) | O(n) | Each block is sorted on its own, so time is linear in m at any level; memory follows the output, not the input |
| `bz2.decompress(data)` | O(n + m) | O(m) | One stream. m can be far larger than n |
| `bz2.decompress(data)` over s concatenated streams | O(s·n + m) | O(n + m) | Each stream after the first copies the rest of the input again; a `BZ2File` over the same bytes recopies at most one read buffer per stream |

### BZ2Compressor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bz2.BZ2Compressor(compresslevel=9)` | O(1) | O(1) | `compresslevel` sets B, and with it the working memory |
| `BZ2Compressor.compress(data)` | O(c + B) | O(c + B) | Returns `b''` until a block fills; the call that fills one sorts it and returns its compressed bytes |
| `BZ2Compressor.flush()` | O(B) | O(B) | Compresses the last, partial block and ends the stream; the compressor cannot be used again |

### BZ2Decompressor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bz2.BZ2Decompressor()` | O(1) | O(1) | |
| `BZ2Decompressor.decompress(data, max_length=-1)` | O(h + c + r + B) | O(h + c + r) | r ≤ `max_length` when it is set; nothing comes out until a whole compressed block is in. Input left unconsumed is copied and held for the next call. One stream only: a call after `eof` raises `EOFError` |
| `BZ2Decompressor.eof`, `BZ2Decompressor.needs_input` | O(1) | O(1) | `needs_input` is `False` while `max_length` held back output |
| `BZ2Decompressor.unused_data` | O(1) | O(1) | Bytes after the end of the stream, copied when it is reached; `b''` before |

### BZ2File

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bz2.open(filename, mode='rb', compresslevel=9, encoding=None, errors=None, newline=None)` | O(1) | O(1) | Reads and writes nothing yet; text modes wrap the `BZ2File` in `io.TextIOWrapper` |
| `bz2.BZ2File(filename, mode='r', *, compresslevel=9)` | O(1) | O(1) | Binary only; closes `filename` on `close()` only if it opened it |
| `BZ2File.read(size=-1)`, `BZ2File.read1(size=-1)`, `BZ2File.readinto(b)` | O(r + B) | O(r) | A read that reaches a new block decompresses the whole block first; `read()` with no size is O(m). Concatenated streams are read in turn |
| `BZ2File.readline(size=-1)`, `BZ2File.readlines(size=-1)`, iterating a `BZ2File` | O(r + B) | O(r) | |
| `BZ2File.peek(n=0)` | O(B) | O(1) | Returns what is buffered, decompressing more only when nothing is; the size argument is ignored |
| `BZ2File.seek(offset, whence=io.SEEK_SET)` | O(k + B) | O(1) | Emulated by decompressing: forward from the current position, or from the start of the file for a backward seek past the read buffer. The first `SEEK_END` decompresses to the end to learn the size, which is then kept |
| `BZ2File.tell()` | O(1) | O(1) | Uncompressed position |
| `BZ2File.write(data)`, `BZ2File.writelines(seq)` | O(c + B) | O(c + B) | c counts every item of `seq`. Output reaches the file only as blocks fill |
| `BZ2File.flush()` | O(1) | O(1) | Writes nothing: the last block reaches the file only on `close()` |
| `BZ2File.close()` | O(B) | O(B) | In write mode compresses the last block and ends the stream |
| `BZ2File.mode`, `BZ2File.name`, `BZ2File.closed`, `BZ2File.fileno()`, `BZ2File.readable()`, `BZ2File.writable()`, `BZ2File.seekable()` | O(1) | O(1) | `mode` is `'rb'` or `'wb'`; `name` is the underlying file's. `mode` and `name` are Python 3.13+ |

## Blocks Are the Unit of Work

A compressor holds input until a block fills, so a small `compress()` call returns nothing and
the work arrives in lumps of B. A decompressor cannot reverse a block's sort until all of it has
arrived, so the first byte out of a block costs the whole block.

```python
import bz2
import random

rng = random.Random(0)
words = [rng.choice(["alpha", "beta", "gamma", "delta"]) for _ in range(20_000)]
data = " ".join(words).encode()[:90_000]  # one block at level 1

compressor = bz2.BZ2Compressor(1)  # O(1) - B = 100 kB
assert compressor.compress(data[:50_000]) == b''  # O(c) - the block is not full yet
compressed = compressor.compress(data[50_000:]) + compressor.flush()  # O(B) per block

decompressor = bz2.BZ2Decompressor()
assert decompressor.decompress(compressed[:-100]) == b''  # the block is incomplete
assert decompressor.decompress(compressed[-100:]) == data  # O(B) - now it decodes
assert decompressor.eof
```

## One-Shot vs Streaming

`compress()` and `decompress()` hold the whole result. A `BZ2Compressor` fed in chunks, or a
`BZ2Decompressor` asked for at most `max_length` bytes at a time, holds one chunk's worth plus
whatever the decompressor has not yet consumed.

```python
import bz2
import io

data = b"log line\n" * 100_000

one_shot = bz2.compress(data)  # O(m) time, O(n) memory
assert bz2.decompress(one_shot) == data  # O(n + m) time, O(m) memory

compressor = bz2.BZ2Compressor()  # O(1)
sink = io.BytesIO()
for start in range(0, len(data), 64_000):
    sink.write(compressor.compress(data[start:start + 64_000]))  # O(c + B)
sink.write(compressor.flush())  # O(B)
assert bz2.decompress(sink.getvalue()) == data

# Decompress a bomb without holding its output
bomb = bz2.compress(b"\0" * 10_000_000)
decompressor = bz2.BZ2Decompressor()
chunk = decompressor.decompress(bomb, max_length=4096)  # O(n + 4096 + B)
assert chunk == b"\0" * 4096
assert decompressor.needs_input is False  # more output is waiting
total = len(chunk)
while not decompressor.eof:
    total += len(decompressor.decompress(b"", max_length=1_000_000))  # O(h + r + B)
assert total == 10_000_000
```

## Concatenated Streams

A bzip2 file may hold several streams one after another: appending to a file adds one, and so
does concatenating two files. `decompress()` reads them all, but hands each new decompressor the
rest of the input as a fresh copy, so it costs O(s·n). A `BZ2File` reads the same bytes a buffer
at a time and recopies at most one buffer per stream.

```python
import bz2
import io

target = io.BytesIO()
with bz2.BZ2File(target, "wb") as f:
    f.write(b"first ")
with bz2.BZ2File(target, "ab") as f:  # appends a second stream
    f.write(b"second")

assert bz2.decompress(target.getvalue()) == b"first second"  # O(s·n + m)

target.seek(0)
with bz2.BZ2File(target) as f:
    assert f.read() == b"first second"  # O(n + m) plus one buffer per stream

# One stream per BZ2Decompressor; the rest is left in unused_data
decompressor = bz2.BZ2Decompressor()
assert decompressor.decompress(target.getvalue()) == b"first "
assert decompressor.eof
assert bz2.decompress(decompressor.unused_data) == b"second"  # O(1) to read the attribute
try:
    decompressor.decompress(b"more")
except EOFError as error:
    assert 'already reached' in str(error)
else:
    raise AssertionError('a finished decompressor accepted more input')
```

## Reading and Writing Files

### Reading and Seeking

Opening reads nothing. A read decompresses as much as it returns, rounded up to the blocks it
touches, and `seek()` is emulated by decompressing, so a backward seek past the read buffer starts
again from the beginning.

```python
import bz2
import io

data = b"".join(b"record %06d\n" % i for i in range(50_000))
source = io.BytesIO(bz2.compress(data))

with bz2.open(source) as f:  # O(1) - nothing read yet
    assert f.readline() == b"record 000000\n"  # O(r + B)
    f.seek(350_000)  # O(k + B) - decompresses forward
    assert f.read(14) == b"record 025000\n"
    f.seek(14)  # O(k + B) - backward: rewinds to the start
    assert f.tell() == 14  # O(1)
    assert f.read(14) == b"record 000001\n"

# Text mode wraps the same file object
source.seek(0)
with bz2.open(source, "rt", encoding="ascii") as f:
    lines = sum(1 for _ in f)  # O(m) time, one line held at a time
assert lines == 50_000
```

### Writing

`write()` passes output on only when a block fills, and `flush()` does not change that: the last
block reaches the file when the `BZ2File` is closed.

```python
import bz2
import io

target = io.BytesIO()
f = bz2.BZ2File(target, "wb", compresslevel=1)  # O(1)
assert f.write(b"small record\n") == 13  # O(c) - held in the block
f.flush()  # O(1) - writes nothing
assert target.getvalue() == b""

f.close()  # O(B) - compresses the last block and ends the stream
assert bz2.decompress(target.getvalue()) == b"small record\n"
assert not target.closed  # a file object passed in stays open
```

## Common Patterns

### Compressing a File in Chunks

```python
import bz2
import io
import shutil

source = io.BytesIO(b"payload " * 500_000)
target = io.BytesIO()

with bz2.BZ2File(target, "wb") as f:
    shutil.copyfileobj(source, f, 1024 * 1024)  # O(m) time, one chunk held

target.seek(0)
with bz2.BZ2File(target) as f:
    size = sum(len(chunk) for chunk in iter(lambda: f.read(1024 * 1024), b""))  # O(m)
assert size == 4_000_000
```

## Performance Best Practices

✅ **Do**:

- Read a large file in chunks or lines, so memory follows the chunk rather than m
- Pass `max_length` to `BZ2Decompressor.decompress()` for untrusted input, since m can be far
  larger than n
- Read files of many concatenated streams through `BZ2File`, which recopies one buffer per
  stream where `decompress()` recopies the rest of the input
- Lower `compresslevel` to shrink B, and with it libbzip2's working memory and the cost of the
  first byte out of each block

❌ **Avoid**:

- Seeking backward past the read buffer of a `BZ2File` - it decompresses again from the start
- Expecting `flush()` to make written data readable - only `close()` ends the stream
- Reading a few bytes at a time for low latency - each new block costs the whole block first

## Version Notes

- **Python 3.13+**: Added `BZ2File.mode` and `BZ2File.name`
- **Python 3.14+**: The module is also available as `compression.bz2`

## Related Modules

- **[compression](compression.md)** - `compression.bz2` re-exports this module
- **[gzip](gzip.md)** - DEFLATE files with the same file interface
- **[lzma](lzma.md)** - XZ and LZMA files with the same file interface
- **[zlib](zlib.md)** - DEFLATE streams without a file format
- **[tarfile](tarfile.md)** - reads and writes `.tar.bz2` archives through this module
