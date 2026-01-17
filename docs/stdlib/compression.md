# Compression Package Complexity

The `compression` package provides a unified interface to compression algorithms. Added in Python 3.14.

## Package Structure

| Module | Description | Notes |
|--------|-------------|-------|
| `compression.zlib` | zlib compression | Re-exports `zlib` |
| `compression.gzip` | gzip compression | Re-exports `gzip` |
| `compression.bz2` | bzip2 compression | Re-exports `bz2` |
| `compression.lzma` | LZMA compression | Re-exports `lzma` |
| `compression.zstd` | Zstandard compression | **New in 3.14** |

## compression.zstd Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compress(data)` | O(n) | O(n) | n = input size |
| `decompress(data)` | O(n) | O(m) | m = decompressed size |
| `ZstdCompressor.compress()` | O(n) | O(1)* | Streaming, buffer reuse |
| `ZstdDecompressor.decompress()` | O(n) | O(1)* | Streaming |
| `open(filename)` | O(1) | O(1) | File handle creation |
| `train_dict(samples)` | O(n*k) | O(d) | n=samples, k=size, d=dict size |

*Amortized with buffer reuse

## One-Shot Compression

### compress()

#### Time Complexity: O(n)

Where n = input data size. Actual time depends on compression level.

```python
from compression import zstd

data = b"example data" * 10000

# Default compression (level 3) - O(n)
compressed = zstd.compress(data)

# Higher level = slower but smaller - still O(n) but larger constant
compressed_max = zstd.compress(data, level=19)

# Lower level = faster but larger
compressed_fast = zstd.compress(data, level=1)
```

#### Space Complexity: O(n)

Output size depends on data compressibility.

### decompress()

#### Time Complexity: O(n)

Where n = compressed data size.

```python
from compression import zstd

# Decompress - O(n) where n = compressed size
original = zstd.decompress(compressed)

# Multi-frame support (automatic)
multi_frame = zstd.decompress(frame1 + frame2 + frame3)
```

#### Space Complexity: O(m)

Where m = decompressed size (can be much larger than input).

## Streaming Compression

### ZstdCompressor

```python
from compression.zstd import ZstdCompressor

compressor = ZstdCompressor(level=3)

# Incremental compression - O(n) per chunk
chunk1 = compressor.compress(data1, mode=ZstdCompressor.CONTINUE)
chunk2 = compressor.compress(data2, mode=ZstdCompressor.CONTINUE)

# Finish frame - O(1) flush
final = compressor.flush(mode=ZstdCompressor.FLUSH_FRAME)

# Total output
compressed = chunk1 + chunk2 + final
```

### ZstdDecompressor

```python
from compression.zstd import ZstdDecompressor

decompressor = ZstdDecompressor()

# Incremental decompression - O(n) per chunk
part1 = decompressor.decompress(compressed[:1000])
part2 = decompressor.decompress(compressed[1000:])

# Check completion
if decompressor.eof:
    print("Frame complete")
```

## File Operations

### ZstdFile

```python
from compression.zstd import open, ZstdFile

# Write compressed file - O(n)
with open("data.zst", "wb") as f:
    f.write(b"data to compress")

# Read compressed file - O(n)
with open("data.zst", "rb") as f:
    data = f.read()

# Explicit class usage
with ZstdFile("data.zst", "rb") as f:
    for line in f:  # O(n) total, O(k) per line
        process(line)
```

## Dictionary Compression

For small, similar data (e.g., JSON records):

```python
from compression import zstd

# Train dictionary on sample data - O(n*k)
samples = [record.encode() for record in similar_records]
dictionary = zstd.train_dict(samples, dict_size=100*1024)

# Compress with dictionary - better ratio for small data
compressed = zstd.compress(data, zstd_dict=dictionary)

# Decompress with same dictionary
original = zstd.decompress(compressed, zstd_dict=dictionary)
```

## Compression Levels

| Level | Speed | Ratio | Use Case |
|-------|-------|-------|----------|
| 1-3 | Fast | Lower | Real-time, streaming |
| 3 (default) | Balanced | Good | General purpose |
| 10-15 | Slow | High | Storage, archival |
| 19-22 | Very slow | Maximum | Maximum compression |

```python
from compression import zstd

# Get valid level range
bounds = zstd.CompressionParameter.compression_level.bounds()
# (-131072, 22) - negative = fast modes
```

## Comparison with Other Algorithms

```python
import zlib
import lzma
from compression import zstd

data = b"x" * 1000000

# zlib: Good balance, widely compatible
zlib_out = zlib.compress(data)  # O(n)

# lzma: Best ratio, slowest
lzma_out = lzma.compress(data)  # O(n), high constant

# zstd: Fast with good ratio
zstd_out = zstd.compress(data)  # O(n), low constant

# Typical results (vary by data):
# zstd level 3:  ~3x faster than zlib level 6, similar ratio
# zstd level 19: Similar speed to lzma, slightly worse ratio
```

## Version Notes

- **Python 3.14+**: `compression` package introduced
- **Python 3.14+**: `compression.zstd` module added
- **All versions**: `zlib`, `gzip`, `bz2`, `lzma` available directly

## Related Documentation

- [Zlib Module](zlib.md)
- [Gzip Module](gzip.md)
- [Bz2 Module](bz2.md)
- [Lzma Module](lzma.md)
- [Python 3.14](../versions/py314.md)
