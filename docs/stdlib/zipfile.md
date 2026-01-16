# zipfile Module Complexity

The `zipfile` module provides tools for working with ZIP archives.

## Functions & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ZipFile(filename, 'r')` | O(n) | O(n) | Open and read central directory |
| `ZipFile.read(name)` | O(m) | O(m) | Read file, m = uncompressed size |
| `ZipFile.write(filename)` | O(m) | O(m) | Write file to archive |
| `ZipFile.namelist()` | O(n) | O(n) | List all files, n = file count |
| `ZipFile.getinfo(name)` | O(n) | O(1) | Get file info |
| `ZipFile.extractall()` | O(m) | O(m) | Extract all files |

## Opening Archives

### Time Complexity: O(n)

Where n = number of files in archive (reading central directory).

```python
from zipfile import ZipFile

# Opening ZIP: O(n) where n = number of files
# Reads central directory
with ZipFile('archive.zip', 'r') as zf:
    # O(n) to open and read directory
    files = zf.namelist()  # O(n)
```

### Space Complexity: O(n)

```python
from zipfile import ZipFile

# Memory for central directory
with ZipFile('archive.zip', 'r') as zf:
    # Stores info for all files: O(n)
    info = zf.infolist()  # O(n) memory
```

## Reading Files

### Time Complexity: O(m)

Where m = uncompressed file size.

```python
from zipfile import ZipFile

with ZipFile('archive.zip', 'r') as zf:
    # Reading single file: O(m)
    # m = file size in archive
    content = zf.read('file.txt')  # O(m)
    
    # Compressed: decompress O(m)
    # Uncompressed: just read O(m)
```

### Space Complexity: O(m)

```python
from zipfile import ZipFile

with ZipFile('archive.zip', 'r') as zf:
    # Full file loaded to memory
    content = zf.read('large_file.bin')  # O(m) memory
    
    # Streaming alternative
    with zf.open('file.txt') as f:
        # Can read chunks: O(k) memory per chunk
        while True:
            chunk = f.read(4096)  # O(k) memory, k = chunk size
            if not chunk:
                break
```

## Writing Archives

### Time Complexity: O(m)

Where m = total size of all files being added.

```python
from zipfile import ZipFile

with ZipFile('output.zip', 'w') as zf:
    # Writing single file: O(m)
    zf.write('file.txt')  # O(m) to read and compress
    
    # Multiple files: O(sum of sizes)
    for filename in ['a.txt', 'b.txt', 'c.txt']:
        zf.write(filename)  # O(m) per file
```

### Space Complexity: O(m)

```python
from zipfile import ZipFile

# Compression buffer
with ZipFile('output.zip', 'w', compression=ZIP_DEFLATED) as zf:
    # Space for compression buffers
    zf.write('large_file.bin')  # O(m) space for compression
```

## Listing Contents

### Time Complexity: O(n)

Where n = number of files in archive.

```python
from zipfile import ZipFile

with ZipFile('archive.zip', 'r') as zf:
    # List all files: O(n)
    names = zf.namelist()  # O(n)
    
    # Get all info: O(n)
    info_list = zf.infolist()  # O(n)
    
    # Individual lookup: O(n) in worst case
    # (linear search through central directory)
    info = zf.getinfo('specific.txt')  # O(n)
```

### Space Complexity: O(n)

```python
from zipfile import ZipFile

with ZipFile('archive.zip', 'r') as zf:
    # Stores list of all files
    names = zf.namelist()  # O(n) space
```

## Extracting Archives

### Time Complexity: O(m)

Where m = total uncompressed size of all files.

```python
from zipfile import ZipFile

with ZipFile('archive.zip', 'r') as zf:
    # Extract single file: O(m)
    # m = uncompressed size
    zf.extract('file.txt')  # O(m)
    
    # Extract all: O(sum of all sizes)
    zf.extractall()  # O(m) total
    
    # Extract with path: O(m) + file I/O
    zf.extractall(path='output_dir')  # O(m)
```

### Space Complexity: O(m)

```python
from zipfile import ZipFile

# Memory usage for extraction
with ZipFile('archive.zip', 'r') as zf:
    # Temporary buffers for decompression
    zf.extractall()  # O(k) space per file being extracted
                     # k = max file size in archive
```

## Compression Methods

### Uncompressed (STORED)

```python
from zipfile import ZipFile, ZIP_STORED

with ZipFile('archive.zip', 'w', compression=ZIP_STORED) as zf:
    # No compression overhead
    zf.write('file.txt')  # O(m) time, minimal CPU
```

### DEFLATE Compression (Default)

```python
from zipfile import ZipFile, ZIP_DEFLATED

with ZipFile('archive.zip', 'w', compression=ZIP_DEFLATED) as zf:
    # Compression adds CPU overhead: O(m log m)
    # But reduces file size
    zf.write('file.txt')  # O(m log m) time
```

## Common Patterns

### Reading with Context Manager

```python
from zipfile import ZipFile

# Safe handling: O(n) to open, O(m) to read
with ZipFile('archive.zip', 'r') as zf:
    if 'target.txt' in zf.namelist():  # O(n)
        data = zf.read('target.txt')    # O(m)
```

### Batch Operations

```python
from zipfile import ZipFile

# Process all files: O(sum of sizes)
with ZipFile('archive.zip', 'r') as zf:
    for file_info in zf.infolist():  # O(n)
        if file_info.filename.endswith('.txt'):
            content = zf.read(file_info.filename)  # O(m) per file
            # Process content
```

### Creating Archives from Directory

```python
from zipfile import ZipFile
import os

def create_archive(directory, archive_name):
    with ZipFile(archive_name, 'w') as zf:
        for root, dirs, files in os.walk(directory):
            for file in files:  # O(n) iterations
                file_path = os.path.join(root, file)
                zf.write(file_path)  # O(m) per file
                # Total: O(sum of file sizes)

# Time: O(n files * average size)
# Space: O(archive size)
create_archive('my_dir', 'backup.zip')
```

### Incremental Backup

```python
from zipfile import ZipFile

# Add files without rewriting entire archive
with ZipFile('archive.zip', 'a') as zf:  # 'a' = append
    # Appending: O(m) to add new file
    # Efficient: doesn't rewrite existing files
    zf.write('new_file.txt')  # O(m) for new file
```

## Performance Characteristics

### Best Practices

```python
from zipfile import ZipFile

# Good: Use context manager
with ZipFile('archive.zip', 'r') as zf:
    data = zf.read('file.txt')  # Automatic cleanup

# Avoid: Manual cleanup prone to errors
zf = ZipFile('archive.zip', 'r')
data = zf.read('file.txt')
zf.close()  # Could be skipped if exception occurs

# Good: Check existence before reading
if 'target.txt' in zf.namelist():
    data = zf.read('target.txt')

# Avoid: Try-catch for missing files (slower)
try:
    data = zf.read('target.txt')
except KeyError:
    pass
```

### Memory Efficiency

```python
from zipfile import ZipFile

# Bad: Load entire large file
with ZipFile('archive.zip', 'r') as zf:
    content = zf.read('huge_file.bin')  # All in memory

# Better: Stream large files
with ZipFile('archive.zip', 'r') as zf:
    with zf.open('huge_file.bin') as f:
        while True:
            chunk = f.read(4096)  # Process in chunks
            if not chunk:
                break
            process_chunk(chunk)
```

## Version Notes

- **Python 2.6+**: Basic zipfile support
- **Python 3.0+**: Enhanced features
- **Python 3.6+**: Support for bz2 and lzma compression
- **Python 3.8+**: Performance improvements

## Related Documentation

- [tarfile Module](tarfile.md) - TAR archive handling
- [gzip Module](gzip.md) - GZIP compression
- [bz2 Module](bz2.md) - BZIP2 compression
