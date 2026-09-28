# zlib Module Complexity

The `zlib` module provides low-level compression and decompression functions using the DEFLATE algorithm (same as gzip but without headers).

## Functions & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zlib.compress(data)` | O(n) | O(n) | Compress bytes, n = input size |
| `zlib.decompress(data)` | O(m) | O(m) | Decompress bytes, m = uncompressed size |
| `zlib.compressobj()` | O(1) | O(1) | Create compressor object |
| `Compress.compress(data)` | O(n) | O(k) | Add data to compress, k = buffer |
| `Compress.flush()` | O(k) | O(k) | Finalize compression |
| `Decompress.decompress(data)` | O(m) | O(k) | Decompress data |
| `zlib.adler32(data, value=1)` | O(n) | O(1) | Checksum of `data`; pass the previous result as `value` to continue a running checksum |
| `zlib.crc32(data, value=0)` | O(n) | O(1) | As `adler32()`, computing CRC-32 |

## Compression Functions

### compress() - One-shot Compression

```python
import zlib

# Compress entire data: O(n) time, O(n) space
data = b'Large data...' * 10000
compressed = zlib.compress(data)  # O(n)

# Space: creates entire compressed result
# O(n) for output (typically 30-50% of input)

# With compression level
compressed = zlib.compress(data, level=6)  # O(n)
compressed = zlib.compress(data, level=9)  # O(n)
```

### decompress() - One-shot Decompression

```python
import zlib

compressed = zlib.compress(b'example data ' * 10_000)

# Decompress entire data: O(m) time, O(m) space
# m = uncompressed size
data = zlib.decompress(compressed)  # O(m)
assert data == b'example data ' * 10_000

# Space: creates entire decompressed result
# O(m) for output
```

## Streaming Compression

### Compressobj - Streaming Compression

```python
import zlib

data_chunks = [b'chunk %d ' % i * 1_000 for i in range(100)]

# Create compressor: O(1)
compressor = zlib.compressobj()  # O(1)

# Add data to compress: O(n) total for all data
parts = []
for chunk in data_chunks:  # O(n) iterations
    parts.append(compressor.compress(chunk))  # O(n) total

# Finalize: O(k)
parts.append(compressor.flush())  # O(k) for remaining
result = b''.join(parts)  # one O(n) join, not a copy per chunk

assert zlib.decompress(result) == b''.join(data_chunks)
```

### Space Complexity: O(k)

```python
import zlib

huge_data_chunks = (b'%d,' % i * 1_000 for i in range(1_000))  # produced lazily

# Streaming with small buffer: each piece of output goes straight to the file,
# so memory stays O(k) however much data passes through
compressor = zlib.compressobj()
checksum = 0
with open('output.z', 'wb') as sink:
    for chunk in huge_data_chunks:
        checksum = zlib.crc32(chunk, checksum)  # to verify the file below
        # compress() returns partial output
        sink.write(compressor.compress(chunk))  # O(k) memory, not O(n)

        # Optional: flush periodically for incremental output
        sink.write(compressor.flush(zlib.Z_SYNC_FLUSH))  # Incremental flush

    sink.write(compressor.flush())  # Final flush

# Verify by streaming the file back through a decompressor, O(k) memory too
decompressor = zlib.decompressobj()
restored = 0
with open('output.z', 'rb') as source:
    while block := source.read(65_536):
        piece = decompressor.decompress(block, 65_536)  # at most 64 KiB out
        restored = zlib.crc32(piece, restored)
        while decompressor.unconsumed_tail:
            piece = decompressor.decompress(decompressor.unconsumed_tail, 65_536)
            restored = zlib.crc32(piece, restored)
restored = zlib.crc32(decompressor.flush(), restored)
assert restored == checksum
```

## Streaming Decompression

### Decompressobj - Streaming Decompression

```python
import zlib

payload = b'record ' * 100_000
compressed = zlib.compress(payload)
compressed_chunks = [compressed[i:i + 256] for i in range(0, len(compressed), 256)]
assert len(compressed_chunks) > 1

# Create decompressor: O(1)
decompressor = zlib.decompressobj()  # O(1)

# Add compressed data: O(m) total
parts = []
for chunk in compressed_chunks:
    parts.append(decompressor.decompress(chunk))  # O(m) total
parts.append(decompressor.flush())

assert b''.join(parts) == payload
```

### Space Complexity: O(k)

```python
import zlib

payload = b'record ' * 100_000
compressed = zlib.compress(payload)
compressed_chunks = [compressed[i:i + 256] for i in range(0, len(compressed), 256)]
assert len(compressed_chunks) > 1

# Streaming with small buffer: max_length caps each piece of output,
# and each piece is consumed before the next is produced
decompressor = zlib.decompressobj()
checksum = 0
for chunk in compressed_chunks:
    piece = decompressor.decompress(chunk, 65_536)  # at most 64 KiB out
    checksum = zlib.crc32(piece, checksum)
    while decompressor.unconsumed_tail:
        piece = decompressor.decompress(decompressor.unconsumed_tail, 65_536)
        checksum = zlib.crc32(piece, checksum)
checksum = zlib.crc32(decompressor.flush(), checksum)

assert checksum == zlib.crc32(payload)
# Total: O(m) time, O(k) memory (k = the 64 KiB cap)
```

## Compression Levels

### Effect on Performance

```python
import zlib

data = b'x' * 1000000

# Level 0: No compression (STORED)
# Time: O(n), fastest
compressed = zlib.compress(data, level=0)  # Fastest, largest

# Level 1-3: Fast compression
# Time: O(n)
compressed = zlib.compress(data, level=1)  # Fast

# Level 6: Default, balanced
# Time: O(n)
compressed = zlib.compress(data, level=6)  # Balanced

# Level 9: Maximum compression
# Time: O(n), slowest
compressed = zlib.compress(data, level=9)  # Slowest, smallest
```

### Trade-offs

```python
import zlib

data = b'log line with repeated words\n' * 50_000

# Speed critical: level 1
compressed = zlib.compress(data, level=1)  # Fastest

# Balanced: level 6 (default)
compressed = zlib.compress(data)  # Default balance

# Storage critical: level 9
compressed = zlib.compress(data, level=9)  # Best ratio
```

## Common Patterns

### Basic Compression/Decompression

```python
import zlib

# Compress: O(n)
data = b'Hello, World!' * 1000
compressed = zlib.compress(data)  # O(n)

# Decompress: O(m)
decompressed = zlib.decompress(compressed)  # O(m)

# Verify
assert data == decompressed
```

### Streaming Large File Compression

```python
import zlib

def compress_file(input_path, output_path):
    """Compress file with streaming."""
    compressor = zlib.compressobj()
    
    with open(input_path, 'rb') as f_in:
        with open(output_path, 'wb') as f_out:
            while True:
                chunk = f_in.read(65536)  # 64KB chunks
                if not chunk:
                    break
                
                # Compress: O(n) total
                compressed = compressor.compress(chunk)
                if compressed:
                    f_out.write(compressed)
            
            # Final flush: O(k)
            f_out.write(compressor.flush())
    
    # Total: O(n) time, O(k) memory
```

### Streaming Large File Decompression

```python
import zlib

def decompress_file(input_path, output_path):
    """Decompress file with streaming."""
    decompressor = zlib.decompressobj()
    
    with open(input_path, 'rb') as f_in:
        with open(output_path, 'wb') as f_out:
            while True:
                chunk = f_in.read(65536)  # 64KB chunks
                if not chunk:
                    break
                
                # Decompress: O(m) total
                decompressed = decompressor.decompress(chunk)
                if decompressed:
                    f_out.write(decompressed)
    
    # Total: O(m) time, O(k) memory
```

### Incremental Compression

```python
import zlib

# Create compressor
compressor = zlib.compressobj(level=6)

# Add data incrementally
compressed_parts = []

data1 = b'Part 1' * 10000
compressed_parts.append(compressor.compress(data1))

data2 = b'Part 2' * 10000
compressed_parts.append(compressor.compress(data2))

# Finalize
compressed_parts.append(compressor.flush())

# Combine results
final_compressed = b''.join(compressed_parts)

# Time: O(n) total
# Space: O(k) during processing
```

## Advanced Options

### Compression Parameters

```python
import zlib

# Method parameter (usually not changed)
compressor = zlib.compressobj(
    level=6,  # Compression level 0-9
    method=zlib.DEFLATED,  # Compression method
    wbits=15,  # Window size (15 = 32KB window)
    memLevel=8  # Memory level for compression
)

# wbits affects compression ratio and memory:
# 15 (default): 32KB window, good compression
# 9: 512 byte window, less compression, less memory
```

### Incremental Flushing

```python
import zlib

data = b'streamed payload ' * 10_000
compressor = zlib.compressobj()

# Z_NO_FLUSH: Default, maximum compression
# Wait until buffer full to output
result = compressor.compress(data)  # May return empty

# Z_SYNC_FLUSH: Output partial result
# Allows decompressor to decode up to this point
result += compressor.flush(zlib.Z_SYNC_FLUSH)  # Incremental

# Z_FULL_FLUSH: Maximum sync point
result += compressor.flush(zlib.Z_FULL_FLUSH)

# Z_FINISH: Final flush
result += compressor.flush(zlib.Z_FINISH)

assert zlib.decompress(result) == data
```

## Decompression Limits

### Preventing Decompression Bombs

```python
import zlib

# Malicious data can expand massively during decompression
# Example: highly compressible data can expand 1000x+

# Safe decompression with size limit
def safe_decompress(compressed, max_size=10*1024*1024):
    """Decompress with size limit to prevent DoS."""
    decompressor = zlib.decompressobj()
    
    try:
        result = []
        remaining = compressed
        total = 0
        while remaining:
            decompressed = decompressor.decompress(remaining, max_size - total)
            total += len(decompressed)
            result.append(decompressed)
            if total > max_size:
                raise ValueError(f"Decompressed size exceeds {max_size}")
            remaining = decompressor.unconsumed_tail
            if not remaining:
                break
        return b"".join(result)
    except zlib.error as e:
        raise ValueError(f"Decompression error: {e}")
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

## Performance Characteristics

### Best Practices

```python
import zlib

data_chunks = [b'row %d\n' % i for i in range(10_000)]
data = b''.join(data_chunks)
MAX_SIZE = 10 * 1024 * 1024

# Good: Use streaming for large data, writing output as it is produced
compressor = zlib.compressobj()
with open('rows.z', 'wb') as sink:
    for chunk in data_chunks:
        sink.write(compressor.compress(chunk))  # O(k) working memory
    sink.write(compressor.flush())
with open('rows.z', 'rb') as source:
    assert zlib.decompress(source.read()) == data

# Avoid when the input is huge: holds the input and output at once
assert zlib.compress(data) != b''  # O(n) memory

# Good: Use appropriate compression level
# Default (6) is usually best balance
compressed = zlib.compress(data)

# Avoid: Using level 9 for real-time compression
# 9 is usually slower for little gain
compressed = zlib.compress(data, level=9)

# Good: Cap decompressed output before trusting it
decompressor = zlib.decompressobj()
result = decompressor.decompress(compressed, MAX_SIZE + 1)
if len(result) > MAX_SIZE:
    raise ValueError("Data too large")
assert result == data
```

### Compression Level Selection

```python
import zlib

data = b'sample text, somewhat repetitive. ' * 10_000

# Real-time/streaming: level 1-3
# Fast compression, reasonable ratio
compressed = zlib.compress(data, level=3)

# Default/balanced: level 6 (default)
# Good balance of speed and compression
compressed = zlib.compress(data)

# Archival/storage: level 9
# Best compression, slow, rarely needed
# Usually not worth the slowness for zlib
compressed = zlib.compress(data, level=9)
```

## Differences from gzip

```python
import zlib
import gzip

# DEFLATE (zlib):
# - Raw DEFLATE data
# - No headers/metadata
# - Slightly smaller than gzip

# GZIP:
# - DEFLATE with headers
# - Includes filename, timestamp, etc.
# - Adds 10-18 bytes overhead
# - More portable

# Both use same compression algorithm
# zlib is more low-level and efficient
# gzip is better for files and interoperability
```

## Related Documentation

- [gzip Module](gzip.md) - GZIP compression (higher level)
- [bz2 Module](bz2.md) - BZIP2 compression
- [lzma Module](lzma.md) - XZ compression (better ratio)
- [zipfile Module](zipfile.md) - ZIP archive handling (uses zlib)
- [io Module](io.md) - I/O operations
