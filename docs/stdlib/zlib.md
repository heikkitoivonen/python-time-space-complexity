# zlib Module Complexity

The `zlib` module compresses and decompresses DEFLATE data, the algorithm behind gzip and ZIP,
wrapped in the zlib format by default. Every operation is a single pass over the bytes it is
given: one-shot functions hold the whole input and the whole result, while compression and
decompression objects hold a fixed-size state and return output as it becomes ready.

`n` is the bytes passed to a call and `m` is the bytes it returns; `z` is the length of a
`zdict` preset dictionary, `t` the bytes held in `unconsumed_tail` and `u` the bytes held in
`unused_data`. The state a compression or decompression object keeps between calls - a sliding
window of 512 bytes to 32 KiB chosen by `wbits`, and match tables sized by `memLevel` - is fixed
by those parameters and does not grow with the data, so it is O(1) here. Decompressed output is
not bounded by its input: a small `n` can produce an `m` three orders of magnitude larger, which
is why the decompression rows are priced in both.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zlib.compress(data, /, level=-1, wbits=MAX_WBITS)` | O(n) | O(n) | Linear at every level; level 0 stores the data and returns slightly more than `n` bytes |
| `zlib.decompress(data, /, wbits=MAX_WBITS, bufsize=DEF_BUF_SIZE)` | O(n + m) | O(m) | No cap on `m`; `bufsize` is only the initial output buffer, grown as needed |
| `zlib.compressobj(level=-1, method=DEFLATED, wbits=MAX_WBITS, memLevel=DEF_MEM_LEVEL, strategy=Z_DEFAULT_STRATEGY[, zdict])` | O(z) | O(1) | Allocates the fixed state, which smaller `wbits` and `memLevel` shrink; for the zlib format a `zdict` is checksummed once |
| `zlib.decompressobj(wbits=MAX_WBITS, zdict=b'')` | O(1) | O(1) | Keeps a reference to `zdict` rather than a copy |
| `zlib.adler32(data, value=1)` | O(n) | O(1) | Checksum of `data`; pass the previous result as `value` to continue a running checksum |
| `zlib.crc32(data, value=0)` | O(n) | O(1) | As `adler32()`, computing CRC-32 |

### Compress

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Compress.compress(data)` | O(n) | O(n) | Returns whatever output is ready, often `b''`; the rest stays in the fixed state |
| `Compress.flush(mode=Z_FINISH)` | O(1) | O(1) | Emits what the state holds, however much was compressed before; `Z_FINISH` ends the stream |
| `Compress.copy()`, `copy.copy()`, `copy.deepcopy()` | O(1) | O(1) | Duplicates the fixed state |

### Decompress

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Decompress.decompress(data, max_length=0)` | O(n + m + u) | O(n + m + u) | `m` is at most `max_length` when that is positive; input left over at the cap is copied into `unconsumed_tail`; after `eof`, input is appended to a copy of `unused_data`; the call that first needs `zdict` adds O(z) |
| `Decompress.flush([length])` | O(t + m) | O(t + m) | Decompresses all of `unconsumed_tail` with no cap - `length` is only the initial buffer |
| `Decompress.copy()`, `copy.copy()`, `copy.deepcopy()` | O(1) | O(1) | Duplicates the fixed state |
| `Decompress.unconsumed_tail` | O(1) | O(1) | Input a capped call did not reach; pass it back in to continue |
| `Decompress.unused_data` | O(1) | O(1) | Bytes found after the end of the compressed stream, including every later call's input |
| `Decompress.eof` | O(1) | O(1) | `True` once the end of the stream has been reached |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zlib.Z_NO_COMPRESSION`, `zlib.Z_BEST_SPEED`, `zlib.Z_BEST_COMPRESSION`, `zlib.Z_DEFAULT_COMPRESSION` | O(1) | O(1) | Levels 0, 1, 9 and -1 (currently 6); every level is linear |
| `zlib.Z_DEFAULT_STRATEGY`, `zlib.Z_FILTERED`, `zlib.Z_HUFFMAN_ONLY`, `zlib.Z_RLE`, `zlib.Z_FIXED` | O(1) | O(1) | Strategies for `compressobj()`; they change the output, not the bound |
| `zlib.Z_NO_FLUSH`, `zlib.Z_PARTIAL_FLUSH`, `zlib.Z_SYNC_FLUSH`, `zlib.Z_FULL_FLUSH`, `zlib.Z_FINISH`, `zlib.Z_BLOCK` | O(1) | O(1) | Flush modes for `Compress.flush()` |
| `zlib.Z_TREES` | O(1) | O(1) | An inflate flush option in the zlib library; `Compress.flush()` rejects it |
| `zlib.MAX_WBITS`, `zlib.DEFLATED`, `zlib.DEF_MEM_LEVEL`, `zlib.DEF_BUF_SIZE` | O(1) | O(1) | Parameter defaults |
| `zlib.ZLIB_VERSION`, `zlib.ZLIB_RUNTIME_VERSION` | O(1) | O(1) | The zlib version built against and the one loaded |
| `zlib.ZLIBNG_VERSION` | O(1) | O(1) | Python 3.14+, and only when built with zlib-ng |
| `zlib.error` | O(1) | O(1) | Raised for corrupt or truncated input and invalid parameters |

## One-Shot Compression

`compress()` and `decompress()` hold the whole input and the whole result at once. That is fine
for data that fits comfortably in memory, but `decompress()` has no limit on what it returns, so
use it only on data you trust.

```python
import zlib

data = b'example data ' * 10_000

compressed = zlib.compress(data)  # O(n)
assert len(compressed) < len(data)

restored = zlib.decompress(compressed)  # O(n + m)
assert restored == data
```

### Compression Levels

Every level makes one linear pass. Level 0 stores the input without compressing it, so its
output is a little larger than the input; levels 1 to 9 search progressively harder for repeated
strings. Which of them is fastest or smallest depends on the data, so measure on your own.

```python
import zlib

data = b'log line with repeated words\n' * 50_000

stored = zlib.compress(data, level=zlib.Z_NO_COMPRESSION)  # O(n)
assert len(stored) > len(data)

for level in range(1, 10):
    compressed = zlib.compress(data, level=level)  # O(n) at every level
    assert len(compressed) < len(data)
    assert zlib.decompress(compressed) == data
```

### zlib, gzip and Raw DEFLATE

`wbits` chooses the wrapper around the same DEFLATE data: 9 to 15 for the zlib format (a 2-byte
header and an Adler-32 trailer), -9 to -15 for raw DEFLATE, and 16 + 9 to 16 + 15 for gzip. In
each range the 9 to 15 is the base-2 log of the window size. Decompressing with 32 + 15 accepts
either zlib or gzip input.

```python
import gzip
import zlib

data = b'shared payload ' * 1_000

def deflate(wbits):
    compressor = zlib.compressobj(wbits=wbits)  # O(1)
    return compressor.compress(data) + compressor.flush()  # O(n)

zlib_format, raw, gzip_format = deflate(15), deflate(-15), deflate(31)
assert zlib_format[2:-4] == raw  # the same DEFLATE stream, different wrapper
assert zlib.decompress(raw, wbits=-15) == data
assert gzip.decompress(gzip_format) == data
assert zlib.decompress(gzip_format, wbits=32 + 15) == data  # auto-detect
```

## Streaming

### Compressing a Stream

A compression object keeps only its fixed state, so memory follows the chunk you hand it rather
than the stream. Write each piece of output as it comes back instead of collecting the pieces.

```python
import io
import zlib

chunks = (b'%d,' % i * 1_000 for i in range(1_000))  # produced lazily
sink = io.BytesIO()

compressor = zlib.compressobj()  # O(1)
checksum = 0
for chunk in chunks:
    checksum = zlib.crc32(chunk, checksum)  # O(n)
    sink.write(compressor.compress(chunk))  # O(n) for this chunk
sink.write(compressor.flush())  # O(1) - whatever the state still holds

assert zlib.crc32(zlib.decompress(sink.getvalue())) == checksum
```

### Decompressing a Stream

Without `max_length`, one call returns everything its input decompresses to. With it, each call
returns at most `max_length` bytes and leaves the input it did not reach in `unconsumed_tail`.
That tail is a copy, so pass the input in chunks: passing one large buffer back through
`unconsumed_tail` with a small cap copies the rest of the buffer on every call, which is
quadratic in the buffer's size.

```python
import zlib

payload = b'record ' * 100_000
compressed = zlib.compress(payload)
CAP = 65_536

decompressor = zlib.decompressobj()  # O(1)
checksum = 0
for start in range(0, len(compressed), 4_096):
    data = compressed[start:start + 4_096]
    while data:
        piece = decompressor.decompress(data, CAP)  # O(n + m), m <= CAP
        assert len(piece) <= CAP
        checksum = zlib.crc32(piece, checksum)
        data = decompressor.unconsumed_tail  # at most the 4,096-byte chunk

assert decompressor.eof
assert checksum == zlib.crc32(payload)
```

### Capping Decompressed Output

`decompress()` and `Decompress.flush()` both run to the end of the stream with no limit, so a
small hostile input can expand to gigabytes. `max_length` on `Decompress.decompress()` is the cap.
Ask for one byte more than you accept, so output that reaches the limit is caught. Note that
`max_length=0` means no limit.

```python
import zlib

def bounded_decompress(compressed, max_size):
    decompressor = zlib.decompressobj()
    result = decompressor.decompress(compressed, max_size + 1)  # O(n + m), m <= max_size + 1
    if len(result) > max_size:
        raise ValueError(f'decompressed size exceeds {max_size}')
    return result

bomb = zlib.compress(b'\0' * 10_000_000)
assert len(bomb) < 20_000

try:
    bounded_decompress(bomb, 1_000_000)
except ValueError as error:
    assert 'exceeds' in str(error)
else:
    raise AssertionError('the bomb was decompressed')

assert bounded_decompress(zlib.compress(b'small'), 1_000_000) == b'small'
```

### Flush Modes

`Z_FINISH` ends the stream. `Z_SYNC_FLUSH` and `Z_FULL_FLUSH` emit everything compressed so far
and keep the stream open, so a reader can decode up to that point before the rest arrives. Each
one can cost compression ratio, and `Z_FULL_FLUSH` can cost more, because it also discards the
history that later data could have matched against.

```python
import zlib

compressor = zlib.compressobj()
decompressor = zlib.decompressobj()

first = compressor.compress(b'first message ' * 100)  # may be b''
first += compressor.flush(zlib.Z_SYNC_FLUSH)  # O(1)
assert decompressor.decompress(first) == b'first message ' * 100  # readable now

rest = compressor.compress(b'second message') + compressor.flush(zlib.Z_FINISH)
assert decompressor.decompress(rest) == b'second message'
assert decompressor.eof
```

### Copying a Stream's State

`copy()` duplicates the fixed state, so two continuations of the same prefix cost one pass over
the prefix rather than two.

```python
import copy
import zlib

prefix = b'shared header ' * 1_000
compressor = zlib.compressobj()
head = compressor.compress(prefix)  # O(n), paid once

branch = compressor.copy()  # O(1)
one = head + compressor.compress(b'ending one') + compressor.flush()
two = head + branch.compress(b'ending two') + branch.flush()

assert zlib.decompress(one) == prefix + b'ending one'
assert zlib.decompress(two) == prefix + b'ending two'
assert isinstance(copy.copy(zlib.decompressobj()), type(zlib.decompressobj()))
```

### Data After the Stream

A zlib stream knows where it ends. Bytes after the end land in `unused_data`, and `eof` says the
end was reached. Input passed after that is appended to `unused_data`, copying what it already
holds, so stop feeding a decompressor once `eof` is set: feeding it chunk after chunk costs time
quadratic in the bytes after the end.

```python
import zlib

stream = zlib.compress(b'body') + b'trailer'

decompressor = zlib.decompressobj()
assert decompressor.decompress(stream) == b'body'
assert decompressor.eof
assert decompressor.unused_data == b'trailer'
assert decompressor.unconsumed_tail == b''

try:
    zlib.decompress(zlib.compress(b'body')[:-3])
except zlib.error as error:
    assert 'incomplete or truncated' in str(error)
else:
    raise AssertionError('a truncated stream was accepted')
```

## Checksums

`adler32()` and `crc32()` read `data` once and keep nothing but a 32-bit value, which they
return. Passing that value back in continues the same checksum, so a stream can be checksummed a
chunk at a time in O(n) total time and O(1) memory, with the same result as one call over all of
it.

```python
import zlib

data = b"payload " * 100_000
view = memoryview(data)          # slices of a memoryview do not copy

crc = zlib.crc32(data)           # O(n)
adler = zlib.adler32(data)       # O(n)

running_crc, running_adler = 0, 1
for start in range(0, len(data), 65_536):
    chunk = view[start:start + 65_536]
    running_crc = zlib.crc32(chunk, running_crc)          # O(chunk)
    running_adler = zlib.adler32(chunk, running_adler)    # O(chunk)

assert running_crc == crc
assert running_adler == adler
assert zlib.crc32(b"") == 0 and zlib.adler32(b"") == 1  # the starting values
```

## Common Patterns

### Compressing and Decompressing a File

```python
import os
import tempfile
import zlib

def compress_file(source, target):
    compressor = zlib.compressobj()
    with open(source, 'rb') as f_in, open(target, 'wb') as f_out:
        while chunk := f_in.read(65_536):
            f_out.write(compressor.compress(chunk))  # O(n) per chunk
        f_out.write(compressor.flush())  # O(1)

def decompress_file(source, target, cap=65_536):
    decompressor = zlib.decompressobj()
    with open(source, 'rb') as f_in, open(target, 'wb') as f_out:
        while chunk := f_in.read(65_536):
            while chunk:
                f_out.write(decompressor.decompress(chunk, cap))  # m <= cap
                chunk = decompressor.unconsumed_tail
    if not decompressor.eof:
        raise ValueError('truncated stream')

with tempfile.TemporaryDirectory() as directory:
    original = os.path.join(directory, 'data.txt')
    packed = os.path.join(directory, 'data.z')
    unpacked = os.path.join(directory, 'copy.txt')
    with open(original, 'wb') as f:
        f.write(b'line of text\n' * 100_000)

    compress_file(original, packed)  # O(n) time, O(1) memory beyond the chunk
    decompress_file(packed, unpacked)  # O(n + m) time, memory bounded by cap

    with open(original, 'rb') as a, open(unpacked, 'rb') as b:
        assert a.read() == b.read()
```

## Performance Best Practices

✅ **Do**:

- Stream large data through `compressobj()` and `decompressobj()`, writing output as it is
  returned, so memory follows the chunk rather than the data
- Pass `max_length` when decompressing anything you did not produce, and ask for one byte more
  than you accept
- Feed compressed input in chunks, so `unconsumed_tail` never copies more than one chunk
- Continue a checksum with `value` instead of joining the data first

❌ **Avoid**:

- `zlib.decompress()` or `Decompress.flush()` on untrusted input - neither has a cap
- `max_length=0` as a limit - it means no limit
- Passing one large compressed buffer back through `unconsumed_tail` with a small cap - each call
  copies the rest of the buffer
- Feeding a decompressor after `eof` - each call copies the whole of `unused_data`
- `Z_SYNC_FLUSH` or `Z_FULL_FLUSH` after every small chunk when no reader needs the data yet -
  each flush can cost compression ratio

## Version Notes

- **Python 3.11+**: `zlib.compress()` accepts `wbits`
- **Python 3.14+**: `zlib.ZLIBNG_VERSION` exists when the module is built with zlib-ng
- **All Python 3**: `zlib.decompress()` and `Decompress.flush()` have no output limit

## Related Modules

- **[gzip](gzip.md)** - The gzip file format over the same DEFLATE stream
- **[zipfile](zipfile.md)** - ZIP archives; `ZIP_DEFLATED` members use zlib
- **[bz2](bz2.md)** - BZIP2 compression
- **[lzma](lzma.md)** - XZ and LZMA compression
- **[binascii](binascii.md)** - Another `crc32()`
