# compression Package Complexity

The `compression` package, new in Python 3.14, gathers the standard library's compression
modules under one name. `compression.zlib`, `compression.gzip`, `compression.bz2` and
`compression.lzma` re-export the standalone modules, so they cost what those pages say.
`compression.zstd` is new: Zstandard compression, with one-shot functions, streaming
compressor and decompressor objects, a file interface, and trained dictionaries.

`m` is uncompressed bytes and `n` is compressed bytes. `c` is the bytes passed to one streaming
call, `r` the bytes a read returns, `k` the uncompressed bytes a seek passes over, `f` the frames
concatenated in one input, `b` the blocks in one frame, `u` the bytes after the end of a frame,
`h` the unconsumed input a decompressor holds from earlier calls, `d` dictionary bytes, and `s`
the total bytes of the training samples. Bounds hold at a fixed compression level with the
default single-threaded compressor (`nb_workers` 0). The Space column counts the buffers Python
sees; libzstd's own working memory is not counted.

## Complexity Reference

### Package Modules

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compression.zlib`, `compression.gzip`, `compression.bz2`, `compression.lzma` | O(1) | O(1) | The standalone modules' public names, as the same objects; see their pages |
| `compression.zstd` | O(1) | O(1) | Optional: a CPython built without libzstd has no `compression.zstd` |

### One-Shot Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zstd.compress(data, level=None, options=None, zstd_dict=None)` | O(m) | O(m) | Memory is O(m) however well the data compresses: the output buffer is sized for incompressible input before compressing starts |
| `zstd.compress(data, zstd_dict=zd)` | O(m + d) | O(m) | A plain or `as_undigested_dict` dictionary is loaded again on every call; `zd.as_digested_dict` is O(m) after the first call at each level |
| `zstd.decompress(data, zstd_dict=None, options=None)` | O(n + m) | O(m) | One frame. m can be far larger than n; use `ZstdDecompressor` with `max_length` to bound it |
| `zstd.decompress(data)` over f concatenated frames | O(f·n + m) | O(n + m) | Each frame after the first copies the rest of the input again; splitting the input with `get_frame_size()` first keeps it O(n + m) |

### ZstdCompressor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zstd.ZstdCompressor(level=None, options=None, zstd_dict=None)` | O(1) | O(1) | O(d) with a plain or undigested dictionary, and with a digested one the first time at each level |
| `ZstdCompressor.compress(data, mode=ZstdCompressor.CONTINUE)` | O(c) | O(c) | Returns whatever compressed output is ready, possibly `b''`; memory follows the chunk, not the stream |
| `ZstdCompressor.flush(mode=ZstdCompressor.FLUSH_FRAME)` | O(1) | O(1) | Emits what is still buffered, at most about one block, however much was fed |
| `ZstdCompressor.set_pledged_input_size(size)` | O(1) | O(1) | Records the next frame's size in its header; raises `ValueError` unless `last_mode` is `FLUSH_FRAME` |
| `ZstdCompressor.last_mode` | O(1) | O(1) | `FLUSH_FRAME` at the start of a frame |
| `ZstdCompressor.CONTINUE`, `ZstdCompressor.FLUSH_BLOCK`, `ZstdCompressor.FLUSH_FRAME` | O(1) | O(1) | Modes: keep buffering, end a block, end the frame |

### ZstdDecompressor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zstd.ZstdDecompressor(zstd_dict=None, options=None)` | O(1) | O(1) | O(d) the first time a `ZstdDict` is used, which digests it and keeps the result on the `ZstdDict`; O(d) every time for `as_undigested_dict` |
| `ZstdDecompressor.decompress(data, max_length=-1)` | O(h + c + r) | O(h + c + r) | r ≤ `max_length` when it is set; input left unconsumed is copied and held for the next call, and new input is appended to what is held. One frame only: another call after it raises `EOFError` |
| `ZstdDecompressor.eof`, `ZstdDecompressor.needs_input` | O(1) | O(1) | `needs_input` is `False` while `max_length` held back output |
| `ZstdDecompressor.unused_data` | O(u) | O(u) | Bytes after the frame; built on the first access after `eof`, the same object afterwards |

### ZstdFile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zstd.open(file, /, mode='rb', *, level=None, options=None, zstd_dict=None, encoding=None, errors=None, newline=None)` | O(1) | O(1) | Reads and writes nothing yet; text modes wrap the `ZstdFile` in `io.TextIOWrapper` |
| `zstd.ZstdFile(file, /, mode='rb', *, level=None, options=None, zstd_dict=None)` | O(1) | O(1) | Binary only; closes `file` on `close()` only if it opened it |
| `ZstdFile.read(size=-1)`, `ZstdFile.read1(size=-1)`, `ZstdFile.readinto(b)`, `ZstdFile.readinto1(b)` | O(r) | O(r) | `read()` with no size is O(m). Concatenated frames are read in turn, each boundary passed recopying up to one 128 KiB read buffer of input |
| `ZstdFile.readline(size=-1)`, iterating a `ZstdFile` | O(r) | O(r) | r = the line's length |
| `ZstdFile.peek(size=-1)` | O(1) | O(1) | Returns what is buffered, decompressing more only when nothing is; `size` is ignored |
| `ZstdFile.seek(offset, whence=io.SEEK_SET)` | O(k) | O(1) | Emulated by decompressing: forward from the current position, or from the start of the file for a backward seek past the read buffer. The first `SEEK_END` decompresses to the end to learn the size, which is then kept |
| `ZstdFile.tell()` | O(1) | O(1) | Uncompressed position |
| `ZstdFile.write(data)` | O(c) | O(c) | Compresses and writes what is ready at once |
| `ZstdFile.flush(mode=ZstdFile.FLUSH_BLOCK)` | O(1) | O(1) | Ends a block, so everything written so far can be decompressed |
| `ZstdFile.close()` | O(1) | O(1) | Ends the frame in write mode |
| `ZstdFile.mode`, `ZstdFile.name`, `ZstdFile.closed`, `ZstdFile.fileno()`, `ZstdFile.readable()`, `ZstdFile.writable()`, `ZstdFile.seekable()` | O(1) | O(1) | `mode` is `'rb'` or `'wb'`; `name` is the underlying file's |
| `ZstdFile.FLUSH_BLOCK`, `ZstdFile.FLUSH_FRAME` | O(1) | O(1) | The compressor's modes |

### ZstdDict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zstd.train_dict(samples, dict_size)` | O(s) | O(s) | The samples are joined into one buffer first |
| `zstd.finalize_dict(zstd_dict, /, samples, dict_size, level)` | O(s) | O(s) | Turns raw content into a regular dictionary tuned for `level` |
| `zstd.ZstdDict(dict_content, /, *, is_raw=False)` | O(d) | O(d) | Copies the content; raises `ValueError` for bytes that are not a dictionary unless `is_raw` |
| `ZstdDict.dict_content` | O(d) | O(d) | A new `bytes` copy on every access |
| `ZstdDict.dict_id`, `len(zd)` | O(1) | O(1) | `dict_id` is 0 for a raw-content dictionary |
| `ZstdDict.as_digested_dict`, `ZstdDict.as_undigested_dict` | O(1) | O(1) | Pass as `zstd_dict`; the cost arrives when it is used (see the one-shot rows) |

### Frames

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zstd.get_frame_info(frame_buffer)` | O(1) | O(1) | Reads the frame header only |
| `FrameInfo.decompressed_size`, `FrameInfo.dictionary_id` | O(1) | O(1) | `decompressed_size` is `None` when the header does not record it |
| `zstd.get_frame_size(frame_buffer)` | O(b) | O(1) | Walks the frame's block headers without decompressing |

### Parameters, Constants and Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zstd.CompressionParameter`, `zstd.DecompressionParameter` | O(1) | O(1) | `IntEnum` keys for the `options` dictionary |
| `CompressionParameter.bounds()`, `DecompressionParameter.bounds()` | O(1) | O(1) | Inclusive `(lower, upper)` |
| `CompressionParameter.compression_level`, `window_log`, `hash_log`, `chain_log`, `search_log`, `min_match`, `target_length`, `strategy`, `enable_long_distance_matching`, `ldm_hash_log`, `ldm_min_match`, `ldm_bucket_size_log`, `ldm_hash_rate_log`, `content_size_flag`, `checksum_flag`, `dict_id_flag`, `nb_workers`, `job_size`, `overlap_log` | O(1) | O(1) | Compression parameters |
| `DecompressionParameter.window_log_max` | O(1) | O(1) | Caps the window a frame may ask the decompressor for |
| `zstd.Strategy` (`fast`, `dfast`, `greedy`, `lazy`, `lazy2`, `btlazy2`, `btopt`, `btultra`, `btultra2`) | O(1) | O(1) | Fastest to strongest; only the order is stable across libzstd versions |
| `zstd.COMPRESSION_LEVEL_DEFAULT` | O(1) | O(1) | 3 |
| `zstd.zstd_version`, `zstd.zstd_version_info` | O(1) | O(1) | The runtime libzstd's version, as a string and a tuple |
| `zstd.ZstdError` | O(1) | O(1) | Raised for malformed or truncated compressed data; an out-of-range level or parameter raises `ValueError` |

## One-Shot vs Streaming

`compress()` sizes its output buffer for incompressible input before it starts, so it needs
memory for the whole input's worth of output even when the result is a few bytes. A
`ZstdCompressor` fed in chunks needs memory for one chunk at a time.

```python
import io
from compression import zstd

data = b"log line\n" * 10_000

one_shot = zstd.compress(data)  # O(m) time and memory
assert zstd.decompress(one_shot) == data  # O(n + m)

compressor = zstd.ZstdCompressor()  # O(1)
sink = io.BytesIO()
for start in range(0, len(data), 4096):
    sink.write(compressor.compress(data[start:start + 4096]))  # O(c) per chunk
sink.write(compressor.flush())  # O(1) - at most about one block is still buffered
assert zstd.decompress(sink.getvalue()) == data
```

### Bounding Decompressed Output

A few compressed bytes can expand to far more, so `decompress()` on untrusted input is O(m) in
memory for an m the input chooses. `ZstdDecompressor.decompress()` with `max_length` returns at
most that much, and `needs_input` says whether more output is waiting.

```python
from compression import zstd

bomb = zstd.compress(b"\0" * 1_000_000)
assert len(bomb) < 100

decompressor = zstd.ZstdDecompressor()
chunk = decompressor.decompress(bomb, max_length=4096)  # O(h + c + r), r <= 4096
assert len(chunk) == 4096
assert decompressor.needs_input is False  # more output is held back

total = len(chunk)
while not decompressor.eof:
    total += len(decompressor.decompress(b"", max_length=4096))
assert total == 1_000_000
```

## Concatenated Frames

`decompress()` handles input made of several frames, such as a file appended to more than once,
but it copies the rest of the input again for each frame, so f frames cost O(f·n + m). Finding each
frame's end with `get_frame_size()` and decompressing the frames one at a time is O(n + m).

```python
from compression import zstd

records = [f"record {i}\n".encode() for i in range(500)]
frames = b"".join(zstd.compress(record) for record in records)  # 500 frames
expected = b"".join(records)

assert zstd.decompress(frames) == expected  # O(f·n + m)

view = memoryview(frames)
parts = []
start = 0
while start < len(view):
    end = start + zstd.get_frame_size(view[start:])  # O(b)
    parts.append(zstd.decompress(view[start:end]))  # one frame
    start = end
assert b"".join(parts) == expected  # O(n + m) in all

# A ZstdDecompressor stops at the end of the first frame
decompressor = zstd.ZstdDecompressor()
assert decompressor.decompress(frames) == records[0]
assert decompressor.eof
assert len(decompressor.unused_data) == len(frames) - zstd.get_frame_size(frames)
```

## Reading and Seeking Files

A `ZstdFile` decompresses as it is read, so memory follows the read size, not the file. Seeking
is emulated: moving forward decompresses and discards up to the target, and moving backward
past the read buffer starts again from the beginning of the file.

```python
import io
from compression import zstd

lines = b"".join(f"line {i}\n".encode() for i in range(1000))
buffer = io.BytesIO()
with zstd.open(buffer, "wb") as f:  # O(1)
    f.write(lines)  # O(c)
assert buffer.getvalue()  # closing a wrapped file ends the frame but leaves the buffer open

buffer.seek(0)
with zstd.open(buffer) as f:
    assert f.readline() == b"line 0\n"  # O(r)
    f.seek(len(lines) - 9)  # O(k) - decompresses forward to the target
    assert f.read() == b"line 999\n"
    f.seek(0)  # O(k) - rewinds and starts again from the beginning
    assert f.tell() == 0  # O(1)

buffer.seek(0)
with zstd.open(buffer, "rt", encoding="ascii") as text:  # O(1) - wraps in io.TextIOWrapper
    assert sum(1 for _ in text) == 1000  # O(r) per line
```

## Dictionaries

Small records compress poorly on their own, because each frame starts with no history. A
dictionary trained on samples of them supplies that history. Training is linear in the samples.
Passing the `ZstdDict` itself loads it again on every `compress()` call, which costs O(d) each
time; `as_digested_dict` digests it once per level and reuses it.

```python
import json
from compression import zstd

samples = [
    json.dumps({"id": i, "user": f"user{i % 50}", "action": "login", "ok": True}).encode()
    for i in range(2000)
]
dictionary = zstd.train_dict(samples, 4096)  # O(s)
assert dictionary.dict_id != 0
assert len(dictionary.dict_content) <= 4096  # O(d) - a fresh copy each time

record = json.dumps({"id": 5000, "user": "user7", "action": "login", "ok": True}).encode()
plain = zstd.compress(record)
digested = dictionary.as_digested_dict  # O(1)
with_dict = zstd.compress(record, zstd_dict=digested)  # O(m) after the first call
assert len(with_dict) < len(plain)

assert zstd.get_frame_info(with_dict).dictionary_id == dictionary.dict_id  # O(1)
assert zstd.decompress(with_dict, zstd_dict=dictionary) == record
```

## Frame Metadata

`get_frame_info()` reads only the frame header. The header records the uncompressed size when
the compressor knew it up front: `compress()` does unless `content_size_flag` is off, and a
streaming compressor does when `set_pledged_input_size()` was called before the frame began. `get_frame_size()` finds
where a frame ends by walking its block headers, without decompressing anything.

```python
from compression import zstd

data = b"payload " * 1000
assert zstd.get_frame_info(zstd.compress(data)).decompressed_size == len(data)  # O(1)

streamed = zstd.ZstdCompressor()
unsized = streamed.compress(data) + streamed.flush()
assert zstd.get_frame_info(unsized).decompressed_size is None

pledged = zstd.ZstdCompressor()
pledged.set_pledged_input_size(len(data))  # O(1)
sized = pledged.compress(data) + pledged.flush()
assert zstd.get_frame_info(sized).decompressed_size == len(data)

# Only at the start of a frame
pledged.compress(b"more")
try:
    pledged.set_pledged_input_size(10)
except ValueError as error:
    assert "FLUSH_FRAME" in str(error)
else:
    raise AssertionError("a size was pledged in the middle of a frame")

assert zstd.get_frame_size(sized + b"trailing") == len(sized)  # O(b)
```

## Compression Levels

Every level is linear in the input. The level sets how hard each byte is searched for a match:
higher levels take much longer, usually for a smaller result.
`CompressionParameter` exposes the finer controls the level stands for.

```python
from compression import zstd

data = b"".join(f"{i} {i * i} {i % 7}\n".encode() for i in range(20_000))

fast = zstd.compress(data, level=1)  # O(m), cheapest search
small = zstd.compress(data, level=19)  # O(m), far more search per byte
assert len(small) < len(fast)

lower, upper = zstd.CompressionParameter.compression_level.bounds()  # O(1)
assert lower < 0 < zstd.COMPRESSION_LEVEL_DEFAULT < upper

options = {
    zstd.CompressionParameter.compression_level: 5,
    zstd.CompressionParameter.checksum_flag: 1,
}
assert zstd.decompress(zstd.compress(data, options=options)) == data

try:
    zstd.compress(data, level=upper + 1)
except ValueError as error:
    assert "valid range" in str(error)
else:
    raise AssertionError("a level above the upper bound was accepted")
```

## Common Patterns

### Compressing a File in Chunks

```python
import os
import shutil
import tempfile
from compression import zstd

with tempfile.TemporaryDirectory() as directory:
    source = os.path.join(directory, "data.txt")
    target = os.path.join(directory, "data.txt.zst")
    with open(source, "wb") as f:
        f.write(b"row\n" * 100_000)

    with open(source, "rb") as src, zstd.open(target, "wb") as dst:
        shutil.copyfileobj(src, dst)  # O(m) time, one buffer of memory

    with zstd.open(target) as f:
        assert sum(1 for _ in f) == 100_000  # O(r) per line
    assert os.path.getsize(target) < os.path.getsize(source)
```

## Performance Best Practices

✅ **Do**:

- Stream with `ZstdCompressor` or `zstd.open()` when the input is large: memory follows the chunk,
  where `compress()` needs memory for the whole input's worth of output
- Pass `max_length` to `ZstdDecompressor.decompress()` for untrusted input, so the output is
  bounded by you rather than by the data
- Pass `zd.as_digested_dict` when compressing many records with one dictionary
- Split input made of many frames with `get_frame_size()` rather than passing it all to
  `decompress()`

❌ **Avoid**:

- `decompress()` on untrusted data without a size limit - m is whatever the input says
- Seeking a `ZstdFile` far backward in a loop - each such seek decompresses from the start again
- Passing a plain `ZstdDict` to `compress()` in a loop - it is loaded again on every call
- Reading `dict_content` repeatedly - every access copies the dictionary

## Version Notes

- **Python 3.14+**: Added the `compression` package with `compression.zstd`; `compression.bz2`,
  `compression.gzip`, `compression.lzma` and `compression.zlib` re-export the standalone modules,
  which remain available
- **Python 3.14+**: `compression.zstd` is optional; CPython built without libzstd lacks it

## Related Modules

- **[zlib](zlib.md)** - DEFLATE, the algorithm behind `compression.zlib` and `compression.gzip`
- **[gzip](gzip.md)** - `.gz` files; `compression.gzip` re-exports it
- **[bz2](bz2.md)** - bzip2; `compression.bz2` re-exports it
- **[lzma](lzma.md)** - xz and LZMA; `compression.lzma` re-exports it
- **[tarfile](tarfile.md)** - Reads and writes `.tar.zst` archives through `compression.zstd`
- **[zipfile](zipfile.md)** - `ZIP_ZSTANDARD` members use `compression.zstd`
