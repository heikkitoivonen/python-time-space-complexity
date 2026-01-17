# tarfile Module Complexity

The `tarfile` module provides tools for working with TAR archives.

## Functions & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TarFile.open(name)` | O(n) | O(n) | Open and read directory |
| `TarFile.getmembers()` | O(n) | O(n) | Get all member info, n = file count |
| `TarFile.getmember(name)` | O(n) | O(1) | Linear search through headers |
| `TarFile.extractfile(name)` | O(m) | O(m) | Extract single file, m = size |
| `TarFile.extract(name)` | O(m) | O(m) | Extract to filesystem |
| `TarFile.extractall()` | O(m) | O(m) | Extract all files |
| `TarFile.add(name)` | O(m) | O(k) | Add file, k = buffer size |

## Opening Archives

### Time Complexity: O(n)

Where n = number of files in archive (reading headers).

```python
import tarfile

# Opening TAR: O(n) where n = number of files
# Reads all headers sequentially
with tarfile.open('archive.tar', 'r') as tar:
    # O(n) to process headers
    members = tar.getmembers()  # O(n)
```

### Space Complexity: O(n)

```python
import tarfile

# Memory for member information
with tarfile.open('archive.tar', 'r') as tar:
    # Stores info for all files: O(n)
    members = tar.getmembers()  # O(n) memory
```

## Reading Members

### Time Complexity: O(n) for lookup, O(m) for read

Where n = number of files, m = file size.

```python
import tarfile

with tarfile.open('archive.tar', 'r') as tar:
    # Finding member: O(n) linear search
    # (no index, searches headers sequentially)
    member = tar.getmember('file.txt')  # O(n)
    
    # Reading file: O(m)
    f = tar.extractfile('file.txt')  # O(m)
    content = f.read()  # O(m)
```

### Space Complexity: O(m)

```python
import tarfile

with tarfile.open('archive.tar', 'r') as tar:
    # Full file loaded to memory
    f = tar.extractfile('large.bin')
    content = f.read()  # O(m) space
    
    # Streaming alternative
    f = tar.extractfile('file.txt')
    while True:
        chunk = f.read(4096)  # O(k) per chunk
        if not chunk:
            break
        process(chunk)
```

## Listing Contents

### Time Complexity: O(n)

Where n = number of files in archive.

```python
import tarfile

with tarfile.open('archive.tar', 'r') as tar:
    # Get all members: O(n)
    # Parses all headers
    members = tar.getmembers()  # O(n)
    
    # List names: O(n)
    names = tar.getnames()  # O(n)
    
    # Get single member: O(n)
    # Must search through headers
    member = tar.getmember('specific.txt')  # O(n)
```

### Space Complexity: O(n)

```python
import tarfile

with tarfile.open('archive.tar', 'r') as tar:
    # Stores all member information
    members = tar.getmembers()  # O(n) memory
```

## Extracting Files

### Time Complexity: O(m)

Where m = total size of extracted files.

```python
import tarfile

with tarfile.open('archive.tar', 'r') as tar:
    # Extract single file: O(m)
    # m = file size
    tar.extract('file.txt')  # O(m)
    
    # Extract all: O(sum of sizes)
    # Processes each file sequentially
    tar.extractall()  # O(m) where m = total uncompressed size
    
    # Extract with path: O(m) + filesystem I/O
    tar.extractall(path='output_dir')  # O(m)
```

### Space Complexity: O(k)

Where k = buffer size during extraction.

```python
import tarfile

# Extraction uses streaming buffers
with tarfile.open('archive.tar', 'r') as tar:
    tar.extractall()  # O(k) space, k = buffer size
                      # NOT O(m), memory efficient
```

## Creating Archives

### Time Complexity: O(m)

Where m = total size of files added.

```python
import tarfile

# Creating TAR: O(m) per file added
with tarfile.open('output.tar', 'w') as tar:
    # Add single file: O(m)
    tar.add('file.txt')  # O(m)
    
    # Add multiple: O(sum of sizes)
    tar.add('dir/')  # O(m) for directory contents
```

### Space Complexity: O(k)

Where k = buffer size (not O(m) for entire file).

```python
import tarfile

# TAR uses streaming buffers
with tarfile.open('output.tar', 'w') as tar:
    # Efficient streaming
    tar.add('large_file.bin')  # O(k) buffer, not O(m)
```

## Compression Methods

### Uncompressed (tar)

```python
import tarfile

# No compression: fastest
with tarfile.open('archive.tar', 'w') as tar:
    tar.add('file.txt')  # O(m) time, minimal overhead
```

### GZIP Compression (tar.gz)

```python
import tarfile

# GZIP compression: O(m) time with constant factor for compression
with tarfile.open('archive.tar.gz', 'w:gz') as tar:
    tar.add('file.txt')  # O(m) with compression overhead
```

### BZIP2 Compression (tar.bz2)

```python
import tarfile

# BZIP2: Better compression, slower (block sorting)
with tarfile.open('archive.tar.bz2', 'w:bz2') as tar:
    tar.add('file.txt')  # O(m) with higher constant factor than gzip
```

### XZ Compression (tar.xz)

```python
import tarfile

# XZ: Best compression ratio, slowest
with tarfile.open('archive.tar.xz', 'w:xz') as tar:
    tar.add('file.txt')  # O(m) with highest constant factor
```

## Common Patterns

### Iterating Members

```python
import tarfile

# Efficient streaming: O(n) iterations
with tarfile.open('archive.tar', 'r') as tar:
    for member in tar:  # O(n) members
        if member.isfile():
            f = tar.extractfile(member)  # O(m) per file
            data = f.read()  # O(m)
            # Process data
```

### Selective Extraction

```python
import tarfile

# Extract only matching files: O(n) to scan, O(subset size) to extract
with tarfile.open('archive.tar', 'r') as tar:
    for member in tar:  # O(n) to iterate
        if member.name.endswith('.txt'):
            tar.extract(member)  # O(m) for this file
```

### Creating Archive from Directory

```python
import tarfile
import os

# Add entire directory: O(sum of all file sizes)
with tarfile.open('backup.tar.gz', 'w:gz') as tar:
    tar.add('my_dir')  # O(m) for all files in directory
                       # Compression adds constant factor overhead
```

### Streaming Large Archives

```python
import tarfile

# Memory-efficient streaming: O(k) memory
with tarfile.open('archive.tar.gz', 'r:gz') as tar:
    for member in tar:  # Streams through archive
        if member.isfile():
            f = tar.extractfile(member)
            while True:
                chunk = f.read(4096)  # O(k) buffer
                if not chunk:
                    break
                process_chunk(chunk)
```

## Performance Characteristics

### Best Practices

```python
import tarfile

# Good: Use context manager
with tarfile.open('archive.tar', 'r') as tar:
    data = tar.extractfile('file.txt').read()  # Auto cleanup

# Avoid: Manual file handling
tar = tarfile.open('archive.tar', 'r')
data = tar.extractfile('file.txt').read()
tar.close()  # Must remember to close

# Good: Stream large files
with tarfile.open('archive.tar', 'r') as tar:
    f = tar.extractfile('huge.bin')
    for chunk in iter(lambda: f.read(8192), b''):
        process(chunk)  # O(k) memory per chunk

# Avoid: Load entire large file
with tarfile.open('archive.tar', 'r') as tar:
    data = tar.extractfile('huge.bin').read()  # O(m) memory
```

### Compression Trade-offs

```python
import tarfile

# No compression: fastest write, largest file
with tarfile.open('archive.tar', 'w') as tar:
    tar.add('files')  # Fastest

# GZIP: Good balance, moderate compression
with tarfile.open('archive.tar.gz', 'w:gz') as tar:
    tar.add('files')  # Medium speed, good ratio

# BZIP2: Better compression, slower
with tarfile.open('archive.tar.bz2', 'w:bz2') as tar:
    tar.add('files')  # Slower but better compression

# XZ: Best compression, slowest
with tarfile.open('archive.tar.xz', 'w:xz') as tar:
    tar.add('files')  # Slowest, best compression ratio
```

## Differences from ZIP

```python
# TAR: Streaming, O(k) memory for extraction
# ZIP: Requires reading central directory, O(n) initial memory
# TAR: Sequential access, O(n) to find file
# ZIP: Random access, O(n) but more predictable
```

## Version Notes

- **Python 2.3+**: Basic tarfile support
- **Python 2.7+**: Enhanced features
- **Python 3.0+**: Improved compression support
- **Python 3.3+**: Support for XZ compression

## Related Documentation

- [zipfile Module](zipfile.md) - ZIP archive handling
- [gzip Module](gzip.md) - GZIP compression
- [bz2 Module](bz2.md) - BZIP2 compression
