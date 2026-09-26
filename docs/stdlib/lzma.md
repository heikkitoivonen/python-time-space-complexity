# lzma Module Complexity

The `lzma` module compresses and decompresses data in the xz and legacy `.lzma` formats, through
one-shot functions, streaming compressor and decompressor objects, and a file interface. liblzma
works through a sliding window rather than in blocks: the decompressor produces output as input
arrives, and the window's size, not the input's, sets how much working memory either side needs.

`m` is uncompressed bytes and `n` is compressed bytes. `D` is the dictionary size a stream is
written with: the preset sets it, from 256 KiB at preset 0 to 64 MiB at preset 9, and a
custom filter chain sets it with `dict_size`. `c` is the bytes passed to one streaming call, `r`
the larger of the bytes a read asks for and the bytes it returns, `k` the uncompressed bytes a
seek passes over, `s` the streams concatenated in one input, and `h` the unconsumed input a
decompressor holds from earlier calls.
A compressor allocates O(D) working memory when it is built. A decompressor allocates the D its
stream was written with when it reads the stream's header, however short the stream is; `memlimit`
caps it. Encoding one byte costs at most a fixed amount at a given preset, so time is linear in
the input at every preset; the preset and `PRESET_EXTREME` change that amount, not the bound.

## Complexity Reference

### One-Shot Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `lzma.compress(data, format=FORMAT_XZ, check=-1, preset=None, filters=None)` | O(m + D) | O(n + D) | Builds a compressor, so a tiny input at preset 9 still pays for D; memory follows the output, not the input |
| `lzma.decompress(data, format=FORMAT_AUTO, memlimit=None, filters=None)` | O(n + m) | O(m + D) | One stream. m can be far larger than n |
| `lzma.decompress(data)` over s concatenated streams | O(s·n + m) | O(n + m + D) | Each stream after the first copies the rest of the input again; an `LZMAFile` over the same bytes recopies at most one read buffer per stream |

### LZMACompressor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `lzma.LZMACompressor(format=FORMAT_XZ, check=-1, preset=None, filters=None)` | O(D) | O(D) | Allocates the working memory for D up front; `preset` defaults to `PRESET_DEFAULT` (6) |
| `LZMACompressor.compress(data)` | O(c + D) | O(c + D) | Returns once the input is taken in, which can be before it is encoded: up to about D bytes of input can be held, and later calls or `flush()` encode them |
| `LZMACompressor.flush()` | O(D) | O(D) | Encodes what is held and ends the stream; the compressor cannot be used again |

### LZMADecompressor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `lzma.LZMADecompressor(format=FORMAT_AUTO, memlimit=None, filters=None)` | O(1); O(D) for `FORMAT_RAW` | O(1); O(D) for `FORMAT_RAW` | Allocates nothing for D until the stream header arrives. `FORMAT_RAW` has no header: its `filters` set D, allocated here |
| `LZMADecompressor.decompress(data, max_length=-1)` | O(h + c + r) | O(h + c + r) | r ≤ `max_length` when it is set. The call that reads the header allocates O(D), or raises `LZMAError` if that exceeds `memlimit`. Input left unconsumed is copied and held for the next call. One stream only: a call after `eof` raises `EOFError` |
| `LZMADecompressor.check` | O(1) | O(1) | `CHECK_UNKNOWN` until the header is read, then the stream's integrity check |
| `LZMADecompressor.eof`, `LZMADecompressor.needs_input` | O(1) | O(1) | `needs_input` is `False` while `max_length` held back output |
| `LZMADecompressor.unused_data` | O(1) | O(1) | Bytes after the end of the stream, set when it is reached; `b''` before |

### LZMAFile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `lzma.open(filename, mode='rb', *, format=None, check=-1, preset=None, filters=None, encoding=None, errors=None, newline=None)` | O(1) read, O(D) write | O(1) read, O(D) write | Reads nothing yet; a write mode builds the compressor. Text modes wrap the `LZMAFile` in `io.TextIOWrapper` |
| `lzma.LZMAFile(filename=None, mode='r', *, format=None, check=-1, preset=None, filters=None)` | O(1) read, O(D) write | O(1) read, O(D) write | Binary only; closes `filename` on `close()` only if it opened it |
| `LZMAFile.read(size=-1)`, `LZMAFile.read1(size=-1)`, `LZMAFile.readinto(b)` | O(r) | O(r) | Takes compressed input one read buffer at a time; `read()` with no size is O(n + m). The first read of each stream allocates its O(D). Concatenated streams are read in turn |
| `LZMAFile.readline(size=-1)`, `LZMAFile.readlines(hint=-1)`, iterating an `LZMAFile` | O(r) | O(r) | |
| `LZMAFile.peek(size=-1)` | O(1) | O(1) | Returns what is buffered, decompressing one read buffer's worth only when nothing is; does not move the position |
| `LZMAFile.seek(offset, whence=io.SEEK_SET)` | O(k) | O(1) | Emulated by decompressing: forward from the current position, or from the start of the file for a backward seek past the read buffer. The first `SEEK_END` decompresses to the end to learn the size, which is then kept |
| `LZMAFile.tell()` | O(1) | O(1) | Uncompressed position |
| `LZMAFile.write(data)`, `LZMAFile.writelines(lines)` | O(c + D) | O(c + D) | c counts every item of `lines`. As with `LZMACompressor.compress()`, input can be held unencoded, and output reaches the file only as it is encoded |
| `LZMAFile.flush()` | O(1) | O(1) | Does not encode what is held or end the stream; only `close()` ends it |
| `LZMAFile.close()` | O(D) | O(D) | In write mode encodes what is held and ends the stream |
| `LZMAFile.mode`, `LZMAFile.name`, `LZMAFile.closed`, `LZMAFile.fileno()`, `LZMAFile.readable()`, `LZMAFile.writable()`, `LZMAFile.seekable()` | O(1) | O(1) | `mode` is `'rb'` or `'wb'`; `name` is the underlying file's. `mode` and `name` are Python 3.13+ |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `lzma.is_check_supported(check)` | O(1) | O(1) | Whether this build of liblzma can verify that integrity check |
| `lzma.FORMAT_AUTO`, `lzma.FORMAT_XZ`, `lzma.FORMAT_ALONE`, `lzma.FORMAT_RAW` | O(1) | O(1) | Container formats; `FORMAT_AUTO` detects xz or `.lzma` when decompressing. `FORMAT_RAW` needs `filters` |
| `lzma.CHECK_NONE`, `lzma.CHECK_CRC32`, `lzma.CHECK_CRC64`, `lzma.CHECK_SHA256`, `lzma.CHECK_ID_MAX`, `lzma.CHECK_UNKNOWN` | O(1) | O(1) | Integrity check IDs for `check` |
| `lzma.PRESET_DEFAULT`, `lzma.PRESET_EXTREME` | O(1) | O(1) | `PRESET_EXTREME` is OR-ed into a preset and keeps its D |
| `lzma.FILTER_LZMA1`, `lzma.FILTER_LZMA2`, `lzma.FILTER_DELTA`, `lzma.FILTER_X86`, `lzma.FILTER_IA64`, `lzma.FILTER_ARM`, `lzma.FILTER_ARMTHUMB`, `lzma.FILTER_POWERPC`, `lzma.FILTER_SPARC` | O(1) | O(1) | Filter IDs for a custom chain; the LZMA filter's `dict_size` is D |
| `lzma.MF_HC3`, `lzma.MF_HC4`, `lzma.MF_BT2`, `lzma.MF_BT3`, `lzma.MF_BT4`, `lzma.MODE_FAST`, `lzma.MODE_NORMAL` | O(1) | O(1) | Match finder and mode options for a custom LZMA filter |
| `lzma.LZMAError` | O(1) | O(1) | Raised for corrupt or truncated input, an unsupported format, or a stream that needs more than `memlimit` |

## The Dictionary Sets the Memory

D is chosen when a stream is written, and the reader pays for it: a decompressor allocates the
stream's D however short the stream is. Pass `memlimit` when the input is untrusted, since a few
bytes of header can ask for a large dictionary.

```python
import lzma

data = b"payload " * 1000

small = lzma.compress(data, preset=0)  # O(m + D) - D = 256 KiB
default = lzma.compress(data)          # O(m + D) - preset 6, D = 8 MiB
assert len(small) < 200 and len(default) < 200  # the same few bytes out

assert lzma.decompress(small, memlimit=1 << 20) == data  # O(n + m)
try:
    lzma.decompress(default, memlimit=1 << 20)  # would allocate D = 8 MiB
except lzma.LZMAError as error:
    assert 'Memory usage limit' in str(error)
else:
    raise AssertionError('an 8 MiB dictionary fitted a 1 MiB limit')
```

## The Compressor Holds Input

`LZMACompressor.compress()` returns once liblzma has taken the input into its window, and that can
be before the input is encoded. A large call can return almost nothing and leave up to about D
bytes for later calls or `flush()` to encode, so the cost of one call does not follow its own
input.

```python
import lzma
import random

data = random.Random(0).randbytes(1_000_000)

compressor = lzma.LZMACompressor(preset=2)  # O(D) - D = 2 MiB
first = compressor.compress(data)  # returns once the input is taken in
assert len(first) < 100_000        # most of it is held, not yet encoded

rest = compressor.flush()  # O(D) - encodes what is held
assert len(rest) > 800_000
assert lzma.decompress(first + rest) == data
```

## One-Shot vs Streaming

`compress()` and `decompress()` hold the whole result. A decompressor asked for at most
`max_length` bytes at a time holds one chunk's worth plus whatever it has not yet consumed, and
because LZMA is not block-based, it returns output as soon as the input for it has arrived.

```python
import lzma

data = b"log line\n" * 100_000

one_shot = lzma.compress(data, preset=1)  # O(m + D) time, O(n + D) memory
assert lzma.decompress(one_shot) == data  # O(n + m) time, O(m + D) memory

# Output arrives before the stream is complete
decompressor = lzma.LZMADecompressor()  # O(1)
partial = decompressor.decompress(one_shot[:-50])  # O(c + r)
assert data.startswith(partial) and len(partial) > 800_000
assert decompressor.check == lzma.CHECK_CRC64  # O(1) - known once the header is in

# Decompress a bomb without holding its output
bomb = lzma.compress(b"\0" * 10_000_000, preset=1)
decompressor = lzma.LZMADecompressor()
chunk = decompressor.decompress(bomb, max_length=4096)  # O(n + 4096)
assert chunk == b"\0" * 4096
assert decompressor.needs_input is False  # more output is waiting
total = len(chunk)
while not decompressor.eof:
    total += len(decompressor.decompress(b"", max_length=1_000_000))  # O(h + r)
assert total == 10_000_000
```

## Concatenated Streams

An xz file may hold several streams one after another: appending to a file adds one, and so does
concatenating two files. `decompress()` reads them all, but hands each new decompressor the rest
of the input as a fresh copy, so it costs O(s·n). An `LZMAFile` reads the same bytes a buffer at a
time and recopies at most one buffer per stream.

```python
import io
import lzma

target = io.BytesIO()
with lzma.LZMAFile(target, "wb", preset=0) as f:
    f.write(b"first ")
with lzma.LZMAFile(target, "ab", preset=0) as f:  # appends a second stream
    f.write(b"second")

assert lzma.decompress(target.getvalue()) == b"first second"  # O(s·n + m)

target.seek(0)
with lzma.LZMAFile(target) as f:
    assert f.read() == b"first second"  # O(n + m) plus one buffer per stream

# One stream per LZMADecompressor; the rest is left in unused_data
decompressor = lzma.LZMADecompressor()
assert decompressor.decompress(target.getvalue()) == b"first "
assert decompressor.eof
assert lzma.decompress(decompressor.unused_data) == b"second"  # O(1) to read the attribute
try:
    decompressor.decompress(b"more")
except EOFError as error:
    assert 'end of stream' in str(error)
else:
    raise AssertionError('a finished decompressor accepted more input')
```

## Reading and Writing Files

### Reading and Seeking

Opening reads nothing. A read decompresses about as much as it returns, and `seek()` is emulated
by decompressing, so a backward seek past the read buffer starts again from the beginning.

```python
import io
import lzma

data = b"".join(b"record %06d\n" % i for i in range(50_000))
source = io.BytesIO(lzma.compress(data, preset=1))

with lzma.open(source) as f:  # O(1) - nothing read yet
    assert f.readline() == b"record 000000\n"  # O(r)
    f.seek(350_000)  # O(k) - decompresses forward
    assert f.read(14) == b"record 025000\n"
    f.seek(14)  # O(k) - backward: rewinds to the start
    assert f.tell() == 14  # O(1)
    assert f.read(14) == b"record 000001\n"

# Text mode wraps the same file object
source.seek(0)
with lzma.open(source, "rt", encoding="ascii") as f:
    lines = sum(1 for _ in f)  # O(m) time, one line held at a time
assert lines == 50_000
```

### Writing

Opening for writing builds the compressor, which allocates for D. `write()` passes output on only
as it is encoded, and `flush()` does not change that: it does not encode what is held, and only
`close()` ends the stream.

```python
import io
import lzma

target = io.BytesIO()
f = lzma.LZMAFile(target, "wb", preset=0)  # O(D) - builds the compressor
f.write(b"small record\n")  # O(c) - held by the compressor
f.flush()  # O(1) - writes nothing held
assert lzma.LZMADecompressor().decompress(target.getvalue()) == b""

f.close()  # O(D) - encodes what is held and ends the stream
assert lzma.decompress(target.getvalue()) == b"small record\n"
assert not target.closed  # a file object passed in stays open
```

## Common Patterns

### Compressing a File in Chunks

```python
import io
import lzma
import shutil

source = io.BytesIO(b"payload " * 500_000)
target = io.BytesIO()

with lzma.LZMAFile(target, "wb", preset=1) as f:
    shutil.copyfileobj(source, f, 1024 * 1024)  # O(m) time, one chunk plus D held

target.seek(0)
with lzma.LZMAFile(target) as f:
    size = sum(len(chunk) for chunk in iter(lambda: f.read(1024 * 1024), b""))  # O(m)
assert size == 4_000_000
```

## Performance Best Practices

✅ **Do**:

- Choose the preset for its memory as well as its ratio: D, and the compressor's working memory
  with it, grows with the preset, and every reader of the stream pays for the same D
- Pass `memlimit` when decompressing untrusted input, and `max_length` to
  `LZMADecompressor.decompress()`, since both D and m can be far larger than n
- Read a large file in chunks or lines, so memory follows the chunk rather than m
- Read files of many concatenated streams through `LZMAFile`, which recopies one buffer per stream
  where `decompress()` recopies the rest of the input

❌ **Avoid**:

- A high preset for many small inputs - each `compress()` call builds a compressor sized for D
- Timing a compressor by one `compress()` call - the encoding it defers lands in a later call or
  in `flush()`
- Seeking backward past the read buffer of an `LZMAFile` - it decompresses again from the start
- Expecting `flush()` to make written data readable - only `close()` ends the stream

## Version Notes

- **Python 3.13+**: Added `LZMAFile.mode` and `LZMAFile.name`
- **Python 3.14+**: The module is also available as `compression.lzma`

## Related Modules

- **[compression](compression.md)** - `compression.lzma` re-exports this module
- **[bz2](bz2.md)** - bzip2 files with the same file interface
- **[gzip](gzip.md)** - DEFLATE files with the same file interface
- **[zlib](zlib.md)** - DEFLATE streams without a file format
- **[tarfile](tarfile.md)** - reads and writes `.tar.xz` archives through this module
- **[zipfile](zipfile.md)** - `ZIP_LZMA` members compress through this module
