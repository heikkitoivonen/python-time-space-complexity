# gzip Module Complexity

The `gzip` module provides GZIP compression and decompression functionality.

## Functions & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gzip.open(filename)` | O(1) | O(1) | Open file handle |
| `GzipFile.read()` | O(m) | O(m) | Decompress all, m = uncompressed size |
| `GzipFile.write(data)` | O(n) | O(k) | Compress and write, n = input size, k = buffer |
| `compress(data)` | O(n) | O(n) | Compress bytes (DEFLATE is linear in practice) |
| `decompress(data)` | O(m) | O(m) | Decompress bytes |
| `GzipFile()` | O(1) | O(1) | Create file object |
| `BadGzipFile` | O(1) | O(1) | Exception for invalid gzip data |

## Opening Files

### Time Complexity: O(1)

```python
import gzip

# Opening gzip file: O(1) time
# Just opens file handle, doesn't read headers
f = gzip.open('file.gz', 'rb')  # O(1)

# Or with context manager
with gzip.open('file.gz', 'rb') as f:
    data = f.read()  # O(m) to decompress
```

### Space Complexity: O(1)

```python
import gzip

# Just file handle, minimal memory
f = gzip.open('file.gz', 'rb')  # O(1) space
```

## Reading (Decompression)

### Time Complexity: O(m)

Where m = uncompressed file size.

```python
import gzip

# Full read: O(m)
with gzip.open('file.gz', 'rb') as f:
    data = f.read()  # O(m) to decompress entire file
    
# Partial read: O(k)
with gzip.open('file.gz', 'rb') as f:
    chunk = f.read(4096)  # O(k) per chunk, k = chunk size
    
# Read all chunks: O(m) total
with gzip.open('file.gz', 'rb') as f:
    while True:
        chunk = f.read(4096)  # O(k) per iteration
        if not chunk:
            break  # Total: O(m)
```

### Space Complexity: O(m) or O(k)

```python
import gzip

# Full decompression: O(m)
with gzip.open('file.gz', 'rb') as f:
    data = f.read()  # O(m) memory for entire file

# Streaming decompression: O(k)
with gzip.open('file.gz', 'rb') as f:
    while True:
        chunk = f.read(4096)  # O(k) memory, k = chunk size
        if not chunk:
            break
        process(chunk)
```

## Writing (Compression)

### Time Complexity: O(n)

Where n = input size. DEFLATE compression is linear in practice.

```python
import gzip

# Write compressed: O(n)
with gzip.open('output.gz', 'wb') as f:
    f.write(data)  # O(n) with compression
    
# Multiple writes: O(n) total
with gzip.open('output.gz', 'wb') as f:
    for chunk in chunks:  # O(n) total
        f.write(chunk)
```

### Space Complexity: O(k)

Where k = compression buffer size (typically 8KB window).

```python
import gzip

# Streaming compression: O(k) space
with gzip.open('output.gz', 'wb') as f:
    for chunk in large_chunks:
        f.write(chunk)  # O(k) buffer, not O(n)
```

## Compress/Decompress Functions

### compress() - One-shot Compression

```python
import gzip

# Compress entire data: O(n) time, O(n) space
data = b'Large data...' * 10000
compressed = gzip.compress(data)  # O(n)

# Space: creates entire compressed result
# O(n) space for output (compressed data smaller)
```

### decompress() - One-shot Decompression

```python
import gzip

# Decompress entire data: O(m) time, O(m) space
compressed = b'\x1f\x8b...'  # compressed data
data = gzip.decompress(compressed)  # O(m)

# m = uncompressed size
# Space: creates entire uncompressed result O(m)
```

## Compression Levels

### Effect on Performance

```python
import gzip

# Compression level 1 (fastest): O(n)
data = b'x' * 1000000
compressed = gzip.compress(data, compresslevel=1)  # Fastest

# Compression level 6 (balanced): O(n)
compressed = gzip.compress(data, compresslevel=6)  # Balanced

# Compression level 9 (default, best): O(n) but with higher constant factor
compressed = gzip.compress(data, compresslevel=9)  # Slowest, best ratio
```

### Trade-offs

```python
import gzip

# Fast compression, poor ratio
fast = gzip.compress(data, compresslevel=1)  # O(n) time

# Default balance
default = gzip.compress(data)  # O(n) time

# Best compression, slower (higher constant factor)
best = gzip.compress(data, compresslevel=9)  # O(n) time
```

## Streaming Decompression

### Time Complexity: O(m)

```python
import gzip

# Streaming: memory efficient
with gzip.open('large.gz', 'rb') as f:
    for chunk in iter(lambda: f.read(8192), b''):
        process_chunk(chunk)  # O(m) total time, O(k) memory
```

### Space Complexity: O(k)

```python
import gzip

# Only keeps buffer, not entire file
with gzip.open('large.gz', 'rb') as f:
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
import gzip

# Simple: O(m) time and space
with gzip.open('file.gz', 'rb') as f:
    content = f.read().decode('utf-8')  # O(m)

# Streaming: O(m) time, O(k) space (better for large files)
with gzip.open('file.gz', 'rb') as f:
    for line in f:  # Iterates line by line
        process_line(line)  # Total: O(m), memory: O(k)
```

### Writing Compressed Data

```python
import gzip

# Simple one-shot: O(n)
with gzip.open('output.gz', 'wb') as f:
    f.write(large_data)  # O(n) - DEFLATE is linear

# Streaming write: O(n), O(k) memory
with gzip.open('output.gz', 'wb') as f:
    for chunk in data_chunks:
        f.write(chunk)  # O(n) total
```

### Compress String to Bytes

```python
import gzip

# String → compressed bytes: O(n)
text = "Hello world" * 100000
compressed = gzip.compress(text.encode('utf-8'))  # O(n) - DEFLATE is linear

# Decompress back: O(m)
decompressed = gzip.decompress(compressed)  # O(m)
text = decompressed.decode('utf-8')
```

### Processing Line by Line

```python
import gzip

# Memory efficient: O(m) time, O(k) space
with gzip.open('data.gz', 'rt') as f:  # text mode
    for line in f:  # Iterates efficiently
        process(line)
```

## Performance Characteristics

### Best Practices

```python
import gzip

# Good: Use streaming for large files
with gzip.open('large.gz', 'rb') as f:
    for chunk in iter(lambda: f.read(65536), b''):
        process(chunk)  # O(k) memory

# Avoid: Load entire large file
with gzip.open('large.gz', 'rb') as f:
    data = f.read()  # O(m) memory

# Good: Use text mode for text
with gzip.open('text.gz', 'rt') as f:  # 't' = text mode
    for line in f:
        process(line)

# Avoid: Binary then decode
with gzip.open('text.gz', 'rb') as f:  # 'b' = binary
    data = f.read().decode('utf-8')
```

### Compression Level Selection

```python
import gzip

# For streaming: use default (9)
# Already optimized for sequential compression

# For one-shot:
data = large_data

# Speed critical: level 1
compressed = gzip.compress(data, compresslevel=1)  # Fastest

# Storage critical: level 9
compressed = gzip.compress(data, compresslevel=9)  # Best ratio

# Default: level 9 (best compression)
compressed = gzip.compress(data)
```

## Memory Considerations

```python
import gzip

# Bad: Unlimited read for large file
with gzip.open('huge.gz') as f:
    data = f.read()  # O(m) memory - could be GBs

# Good: Read in chunks
with gzip.open('huge.gz') as f:
    while True:
        chunk = f.read(1024*1024)  # 1MB chunks
        if not chunk:
            break
        process(chunk)  # O(1MB) memory

# Good: Iterate lines (text)
with gzip.open('huge.gz', 'rt') as f:
    for line in f:  # Auto-chunked
        process(line)  # O(line_size) memory
```

## Version Notes

- **Python 2.3+**: Basic gzip support
- **Python 3.0+**: Enhanced API
- **Python 3.8+**: Performance improvements
- **Python 3.10+**: Better compression options

## Related Documentation

- [zipfile Module](zipfile.md) - ZIP archive handling
- [tarfile Module](tarfile.md) - TAR archive handling
- [bz2 Module](bz2.md) - BZIP2 compression
- [io Module](io.md) - I/O operations
