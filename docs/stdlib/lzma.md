# lzma Module Complexity

The `lzma` module provides XZ compression and decompression functionality.

## Functions & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `lzma.open(filename)` | O(1) | O(1) | Open file handle |
| `LZMAFile.read()` | O(m) | O(m) | Decompress all, m = uncompressed size |
| `LZMAFile.write(data)` | O(n) | O(k) | Compress and write, n = input size |
| `compress(data)` | O(n log n) | O(n) | Compress bytes |
| `decompress(data)` | O(m) | O(m) | Decompress bytes |

## Opening Files

### Time Complexity: O(1)

```python
import lzma

# Opening LZMA file: O(1) time
# Just opens file handle
f = lzma.open('file.xz', 'rb')  # O(1)

# With context manager
with lzma.open('file.xz', 'rb') as f:
    data = f.read()  # O(m) to decompress
```

### Space Complexity: O(1)

```python
import lzma

# Just file handle, minimal memory
f = lzma.open('file.xz', 'rb')  # O(1) space
```

## Reading (Decompression)

### Time Complexity: O(m)

Where m = uncompressed file size.

```python
import lzma

# Full read: O(m)
with lzma.open('file.xz', 'rb') as f:
    data = f.read()  # O(m) to decompress entire file

# Partial read: O(k)
with lzma.open('file.xz', 'rb') as f:
    chunk = f.read(4096)  # O(k) per chunk, k = chunk size

# Read all chunks: O(m) total
with lzma.open('file.xz', 'rb') as f:
    while True:
        chunk = f.read(4096)  # O(k) per iteration
        if not chunk:
            break  # Total: O(m)
```

### Space Complexity: O(m) or O(k)

```python
import lzma

# Full decompression: O(m)
with lzma.open('file.xz', 'rb') as f:
    data = f.read()  # O(m) memory for entire file

# Streaming decompression: O(k)
with lzma.open('file.xz', 'rb') as f:
    while True:
        chunk = f.read(4096)  # O(k) memory, k = chunk size
        if not chunk:
            break
        process(chunk)
```

## Writing (Compression)

### Time Complexity: O(n log n) to O(n log^2 n)

Where n = input size. XZ compression is CPU-intensive.

```python
import lzma

# Write compressed: O(n log n) to O(n log^2 n)
with lzma.open('output.xz', 'wb') as f:
    f.write(data)  # O(n log^2 n) with XZ compression

# Multiple writes: O(sum * log^2(sum))
with lzma.open('output.xz', 'wb') as f:
    for chunk in chunks:  # O(n log^2 n) total
        f.write(chunk)
```

### Space Complexity: O(k)

Where k = compression buffer size (large dictionary).

```python
import lzma

# Streaming compression: O(k) space
with lzma.open('output.xz', 'wb') as f:
    for chunk in large_chunks:
        f.write(chunk)  # O(k) buffer, not O(n)
```

## Compress/Decompress Functions

### compress() - One-shot Compression

```python
import lzma

# Compress entire data: O(n log^2 n) time, O(n) space
data = b'Large data...' * 10000
compressed = lzma.compress(data)  # O(n log^2 n)

# Space: creates entire compressed result
# O(n) space for output (best compression ratio)
```

### decompress() - One-shot Decompression

```python
import lzma

# Decompress entire data: O(m) time, O(m) space
compressed = b'7zXZ...'  # LZMA compressed data
data = lzma.decompress(compressed)  # O(m)

# m = uncompressed size
# Space: creates entire uncompressed result O(m)
```

## LZMACompressor/LZMADecompressor

### LZMACompressor - Streaming Compression

```python
import lzma

# Streaming compression: O(n log^2 n) time, O(k) space
compressor = lzma.LZMACompressor()

result = b''
for chunk in data_chunks:
    result += compressor.compress(chunk)  # O(n log^2 n) total
result += compressor.flush()  # Finalize

# Memory: large dictionary buffer, not entire data
```

### LZMADecompressor - Streaming Decompression

```python
import lzma

# Streaming decompression: O(m) time, O(k) space
decompressor = lzma.LZMADecompressor()

result = b''
for chunk in compressed_chunks:
    result += decompressor.decompress(chunk)  # O(m) total

# Memory: decompression buffer
```

## Compression Presets

### Effect on Performance

```python
import lzma

data = b'x' * 1000000

# Preset 0-2: Fast but less compression
# O(n log n) time
fast = lzma.compress(data, preset=0)  # Fastest

# Preset 6: Default, balanced
medium = lzma.compress(data, preset=6)  # Balanced

# Preset 9: Maximum compression, slowest
# O(n log^2 n) time
best = lzma.compress(data, preset=9)  # Best ratio, very slow
```

### Trade-offs

```python
import lzma

data = large_data

# Fast: preset 0 (still slower than gzip)
compressed = lzma.compress(data, preset=0)  # O(n log n)
# Size reduction: ~30%

# Default: preset 6
compressed = lzma.compress(data, preset=6)  # O(n log^2 n)
# Size reduction: ~50%

# Maximum: preset 9
compressed = lzma.compress(data, preset=9)  # O(n log^2 n)
# Size reduction: ~55% (best ratio)
```

## Streaming Decompression

### Time Complexity: O(m)

```python
import lzma

# Streaming: memory efficient
with lzma.open('large.xz', 'rb') as f:
    for chunk in iter(lambda: f.read(8192), b''):
        process_chunk(chunk)  # O(m) total time, O(k) memory
```

### Space Complexity: O(k)

```python
import lzma

# Only keeps buffer, not entire file
with lzma.open('large.xz', 'rb') as f:
    buffer_size = 8192
    while True:
        chunk = f.read(buffer_size)  # O(k) memory
        if not chunk:
            break
        process(chunk)
```

## Common Patterns

### Reading Compressed File

```python
import lzma

# Simple: O(m) time and space
with lzma.open('file.xz', 'rb') as f:
    content = f.read().decode('utf-8')  # O(m)

# Streaming: O(m) time, O(k) space (better for large files)
with lzma.open('file.xz', 'rb') as f:
    for line in f:  # Iterates line by line
        process_line(line)  # Total: O(m), memory: O(k)
```

### Writing Compressed Data

```python
import lzma

# Simple one-shot: O(n log^2 n)
with lzma.open('output.xz', 'wb') as f:
    f.write(large_data)  # O(n log^2 n)

# Streaming write: O(n log^2 n), O(k) memory
with lzma.open('output.xz', 'wb') as f:
    for chunk in data_chunks:
        f.write(chunk)  # O(sum log^2 sum) total
```

### Compress/Decompress Bytes

```python
import lzma

# Compress: O(n log^2 n)
data = b'Hello world' * 100000
compressed = lzma.compress(data)  # O(n log^2 n)

# Decompress: O(m)
decompressed = lzma.decompress(compressed)  # O(m)
```

### Processing Line by Line

```python
import lzma

# Memory efficient: O(m) time, O(k) space
with lzma.open('data.xz', 'rt') as f:  # text mode
    for line in f:  # Iterates efficiently
        process(line)
```

## Performance Characteristics

### Best Practices

```python
import lzma

# Good: Use streaming for large files
with lzma.open('large.xz', 'rb') as f:
    for chunk in iter(lambda: f.read(65536), b''):
        process(chunk)  # O(k) memory

# Avoid: Load entire large file
with lzma.open('large.xz', 'rb') as f:
    data = f.read()  # O(m) memory

# Good: Use streaming compressor for large data
compressor = lzma.LZMACompressor()
for chunk in chunks:
    compressed += compressor.compress(chunk)  # O(k) memory
compressed += compressor.flush()

# Avoid: Compress entire large data at once
compressed = lzma.compress(huge_data)  # O(n) memory, very slow
```

### Preset Selection

```python
import lzma

# Speed critical: preset 0-2
compressed = lzma.compress(data, preset=0)  # Fastest (still slow)

# Balanced: preset 6 (default)
compressed = lzma.compress(data)  # Good ratio, reasonable time

# Storage critical: preset 9
compressed = lzma.compress(data, preset=9)  # Best ratio, slow
```

## LZMA vs GZIP vs BZIP2

### Compression Ratios and Speed

```python
import lzma
import gzip
import bz2

data = large_data

# GZIP: Fast, moderate compression
# Time: O(n log n)
# Ratio: ~40%
gzip_result = gzip.compress(data)

# BZIP2: Medium speed, good compression
# Time: O(n log^2 n)
# Ratio: ~50%
bz2_result = bz2.compress(data)

# LZMA (XZ): Slow, best compression
# Time: O(n log^2 n)
# Ratio: ~55%
lzma_result = lzma.compress(data)
```

### When to Use Each

```python
import lzma
import gzip
import bz2

# GZIP: Fast compression, reasonable ratio
# Use for: logs, temporary backups
gzip.compress(data)

# BZIP2: Better ratio than GZIP, slower
# Use for: archives that will be stored
bz2.compress(data)

# LZMA (XZ): Best ratio, very slow
# Use for: long-term storage, final archives
# Not recommended for real-time compression
lzma.compress(data)
```

## Memory Considerations

```python
import lzma

# Bad: Unlimited read for large file
with lzma.open('huge.xz') as f:
    data = f.read()  # O(m) memory - could be GBs

# Good: Read in chunks
with lzma.open('huge.xz') as f:
    while True:
        chunk = f.read(1024*1024)  # 1MB chunks
        if not chunk:
            break
        process(chunk)  # O(1MB) memory

# Good: Iterate lines (text)
with lzma.open('huge.xz', 'rt') as f:
    for line in f:  # Auto-chunked
        process(line)  # O(line_size) memory

# Note: Compression with preset 9 uses significant memory
# Consider using lower presets for embedded systems
```

## Version Notes

- **Python 3.3+**: LZMA module introduced
- **Python 3.4+**: Enhanced performance
- **Python 3.6+**: Performance improvements
- **Python 3.9+**: Better compression options

## Related Documentation

- [gzip Module](gzip.md) - GZIP compression (faster)
- [bz2 Module](bz2.md) - BZIP2 compression
- [zipfile Module](zipfile.md) - ZIP archive handling
- [tarfile Module](tarfile.md) - TAR archive handling
- [io Module](io.md) - I/O operations
