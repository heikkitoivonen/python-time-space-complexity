# bz2 Module Complexity

The `bz2` module provides BZIP2 compression and decompression functionality.

## Functions & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bz2.open(filename)` | O(1) | O(1) | Open file handle |
| `BZ2File.read()` | O(m) | O(m) | Decompress all, m = uncompressed size |
| `BZ2File.write(data)` | O(n) | O(k) | Compress and write, n = input size |
| `compress(data)` | O(n log n) | O(n) | BZIP2 uses BWT; may be O(n log²n) |
| `decompress(data)` | O(m) | O(m) | Decompress bytes |

## Opening Files

### Time Complexity: O(1)

```python
import bz2

# Opening bz2 file: O(1) time
# Just opens file handle
f = bz2.open('file.bz2', 'rb')  # O(1)

# With context manager
with bz2.open('file.bz2', 'rb') as f:
    data = f.read()  # O(m) to decompress
```

### Space Complexity: O(1)

```python
import bz2

# Just file handle, minimal memory
f = bz2.open('file.bz2', 'rb')  # O(1) space
```

## Reading (Decompression)

### Time Complexity: O(m)

Where m = uncompressed file size.

```python
import bz2

# Full read: O(m)
with bz2.open('file.bz2', 'rb') as f:
    data = f.read()  # O(m) to decompress entire file

# Partial read: O(k)
with bz2.open('file.bz2', 'rb') as f:
    chunk = f.read(4096)  # O(k) per chunk, k = chunk size

# Read all chunks: O(m) total
with bz2.open('file.bz2', 'rb') as f:
    while True:
        chunk = f.read(4096)  # O(k) per iteration
        if not chunk:
            break  # Total: O(m)
```

### Space Complexity: O(m) or O(k)

```python
import bz2

# Full decompression: O(m)
with bz2.open('file.bz2', 'rb') as f:
    data = f.read()  # O(m) memory for entire file

# Streaming decompression: O(k)
with bz2.open('file.bz2', 'rb') as f:
    while True:
        chunk = f.read(4096)  # O(k) memory, k = chunk size
        if not chunk:
            break
        process(chunk)
```

## Writing (Compression)

### Time Complexity: O(n log n)

Where n = input size. BZIP2 compression has logarithmic factor.

```python
import bz2

# Write compressed: O(n log n)
with bz2.open('output.bz2', 'wb') as f:
    f.write(data)  # O(n log n) with BZIP2 compression

# Multiple writes: O(sum * log(sum))
with bz2.open('output.bz2', 'wb') as f:
    for chunk in chunks:  # O(n log n) total
        f.write(chunk)
```

### Space Complexity: O(k)

Where k = compression buffer size (typically larger than gzip).

```python
import bz2

# Streaming compression: O(k) space
with bz2.open('output.bz2', 'wb') as f:
    for chunk in large_chunks:
        f.write(chunk)  # O(k) buffer, not O(n)
```

## Compress/Decompress Functions

### compress() - One-shot Compression

```python
import bz2

# Compress entire data: O(n log n) time, O(n) space
data = b'Large data...' * 10000
compressed = bz2.compress(data)  # O(n log n)

# Space: creates entire compressed result
# O(n) space for output (compressed data typically smaller than gzip)
```

### decompress() - One-shot Decompression

```python
import bz2

# Decompress entire data: O(m) time, O(m) space
compressed = b'BZ...'  # BZIP2 compressed data
data = bz2.decompress(compressed)  # O(m)

# m = uncompressed size
# Space: creates entire uncompressed result O(m)
```

## BZ2Compressor/BZ2Decompressor

### BZ2Compressor - Streaming Compression

```python
import bz2

# Streaming compression: O(n log n) time, O(k) space
compressor = bz2.BZ2Compressor()

result = b''
for chunk in data_chunks:
    result += compressor.compress(chunk)  # O(n log n) total
result += compressor.flush()  # Finalize

# Memory: compression buffer, not entire data
```

### BZ2Decompressor - Streaming Decompression

```python
import bz2

# Streaming decompression: O(m) time, O(k) space
decompressor = bz2.BZ2Decompressor()

result = b''
for chunk in compressed_chunks:
    result += decompressor.decompress(chunk)  # O(m) total

# Memory: decompression buffer
```

## Compression Quality

### Effect on Performance

```python
import bz2

# BZIP2 has only one compression level (9)
# Unlike gzip which has levels 1-9

# All BZIP2 compression: O(n log^2 n)
data = b'x' * 1000000
compressed = bz2.compress(data)  # Always O(n log^2 n)

# Better compression ratio than gzip
# But slower and more memory-intensive
```

## Streaming Decompression

### Time Complexity: O(m)

```python
import bz2

# Streaming: memory efficient
with bz2.open('large.bz2', 'rb') as f:
    for chunk in iter(lambda: f.read(8192), b''):
        process_chunk(chunk)  # O(m) total time, O(k) memory
```

### Space Complexity: O(k)

```python
import bz2

# Only keeps buffer, not entire file
with bz2.open('large.bz2', 'rb') as f:
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
import bz2

# Simple: O(m) time and space
with bz2.open('file.bz2', 'rb') as f:
    content = f.read().decode('utf-8')  # O(m)

# Streaming: O(m) time, O(k) space (better for large files)
with bz2.open('file.bz2', 'rb') as f:
    for line in f:  # Iterates line by line
        process_line(line)  # Total: O(m), memory: O(k)
```

### Writing Compressed Data

```python
import bz2

# Simple one-shot: O(n log n)
with bz2.open('output.bz2', 'wb') as f:
    f.write(large_data)  # O(n log n)

# Streaming write: O(n log n), O(k) memory
with bz2.open('output.bz2', 'wb') as f:
    for chunk in data_chunks:
        f.write(chunk)  # O(sum log sum) total
```

### Compress/Decompress Bytes

```python
import bz2

# Compress: O(n log n)
data = b'Hello world' * 100000
compressed = bz2.compress(data)  # O(n log n)

# Decompress: O(m)
decompressed = bz2.decompress(compressed)  # O(m)

# Data is already bytes, no encoding needed
```

### Processing Line by Line

```python
import bz2

# Memory efficient: O(m) time, O(k) space
with bz2.open('data.bz2', 'rt') as f:  # text mode
    for line in f:  # Iterates efficiently
        process(line)
```

## Performance Characteristics

### Best Practices

```python
import bz2

# Good: Use streaming for large files
with bz2.open('large.bz2', 'rb') as f:
    for chunk in iter(lambda: f.read(65536), b''):
        process(chunk)  # O(k) memory

# Avoid: Load entire large file
with bz2.open('large.bz2', 'rb') as f:
    data = f.read()  # O(m) memory

# Good: Use streaming compressor for large data
compressor = bz2.BZ2Compressor()
for chunk in chunks:
    compressed += compressor.compress(chunk)  # O(k) memory
compressed += compressor.flush()

# Avoid: Compress entire large data at once
compressed = bz2.compress(huge_data)  # O(n) memory
```

### BZIP2 vs GZIP

```python
import bz2
import gzip

# Compression time: BZIP2 slower
# BZIP2: O(n log^2 n)
# GZIP: O(n log n)

data = large_data

# GZIP: faster
gzip.compress(data)  # O(n log n)

# BZIP2: slower but better compression
bz2.compress(data)  # O(n log^2 n)

# Trade-off: speed vs compression ratio
# Use BZIP2 for maximum compression
# Use GZIP for faster processing
```

## Memory Considerations

```python
import bz2

# Bad: Unlimited read for large file
with bz2.open('huge.bz2') as f:
    data = f.read()  # O(m) memory - could be GBs

# Good: Read in chunks
with bz2.open('huge.bz2') as f:
    while True:
        chunk = f.read(1024*1024)  # 1MB chunks
        if not chunk:
            break
        process(chunk)  # O(1MB) memory

# Good: Iterate lines (text)
with bz2.open('huge.bz2', 'rt') as f:
    for line in f:  # Auto-chunked
        process(line)  # O(line_size) memory
```

## Version Notes

- **Python 2.3+**: Basic bz2 support
- **Python 3.0+**: Enhanced API
- **Python 3.1+**: BZ2Compressor/BZ2Decompressor
- **Python 3.10+**: Better compression options

## Related Documentation

- [gzip Module](gzip.md) - GZIP compression
- [zipfile Module](zipfile.md) - ZIP archive handling
- [tarfile Module](tarfile.md) - TAR archive handling
- [lzma Module](lzma.md) - XZ compression (newer, better ratio)
- [io Module](io.md) - I/O operations
