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
| `compress(data)` | O(n) | O(n) | n = input size; constant varies by level |
| `decompress(data)` | O(n) | O(m) | m = decompressed size (can be >> n) |
| `ZstdCompressor.compress()` | O(n) | O(1)* | Streaming with buffer reuse |
| `ZstdDecompressor.decompress()` | O(n) | O(1)* | Streaming |
| `open(filename)` | O(1) | O(1) | File handle creation |
| `train_dict(samples)` | O(n×k) | O(d) | n=samples, k=avg size, d=dict size |

*Amortized with buffer reuse in streaming mode

## Compression Level Trade-offs

| Level | Time Constant | Ratio | Use Case |
|-------|---------------|-------|----------|
| 1-3 | Low | Lower | Real-time, streaming |
| 3 (default) | Medium | Good | General purpose |
| 10-15 | High | High | Storage, archival |
| 19-22 | Very high | Maximum | Maximum compression |

```python
from compression import zstd

# All O(n) time, but vastly different constants:
data = b"x" * 1000000

fast = zstd.compress(data, level=1)   # ~50 MB/s
default = zstd.compress(data, level=3) # ~30 MB/s  
slow = zstd.compress(data, level=19)   # ~2 MB/s
```

## Algorithm Comparison

```python
import zlib
import lzma
from compression import zstd

data = b"x" * 1000000

# All O(n) but different constants:
zlib.compress(data)    # Baseline
lzma.compress(data)    # ~10x slower, best ratio
zstd.compress(data)    # ~3x faster than zlib, similar ratio

# Decompression (all O(n)):
# zstd > zlib > lzma (zstd fastest)
```

## Streaming vs One-Shot

```python
from compression.zstd import compress, ZstdCompressor

# One-shot: O(n) time, O(n) space - holds all in memory
result = compress(large_data)  # Peak memory: 2×n

# Streaming: O(n) time, O(1) space - constant memory
compressor = ZstdCompressor()
for chunk in chunks:
    yield compressor.compress(chunk)  # Peak memory: chunk_size
yield compressor.flush()
```

## Dictionary Compression

For small, similar data (JSON records, log lines):

```python
from compression import zstd

# Training: O(n×k) where n=samples, k=avg size
dictionary = zstd.train_dict(samples, dict_size=100*1024)

# With dictionary: better ratio for small data (<1KB)
# Without dictionary: overhead not worth it for large data (>100KB)
compressed = zstd.compress(small_record, zstd_dict=dictionary)
```

## Version Notes

- **Python 3.14+**: `compression` package introduced
- **Python 3.14+**: `compression.zstd` module added (Zstandard support)
- **All versions**: `zlib`, `gzip`, `bz2`, `lzma` available as standalone modules

## Related Documentation

- [Zlib Module](zlib.md)
- [Gzip Module](gzip.md)
- [Bz2 Module](bz2.md)
- [Lzma Module](lzma.md)
- [Python 3.14](../versions/py314.md)
