# Tempfile Module Complexity

The `tempfile` module provides utilities for creating and managing temporary files and directories, automatically cleaned up after use.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `NamedTemporaryFile()` | O(r) | O(1) initial | r = name attempts (<= TMP_MAX) |
| `TemporaryFile()` | O(r) | O(1) initial | r = name attempts (<= TMP_MAX) |
| `TemporaryDirectory()` | O(r) | O(1) initial | r = name attempts (<= TMP_MAX) |
| `mktemp()` | O(r) | O(1) | Generate temp name (deprecated) |
| `mkdtemp()` | O(r) | O(1) | Create temp directory safely |
| `gettempdir()` | O(1) | O(1) | Get system temp directory |
| `gettempprefix()` | O(1) | O(1) | Get temp filename prefix |

## Named Temporary Files

### NamedTemporaryFile()

#### Time Complexity: O(r)

Where r = number of name attempts (<= TMP_MAX).

```python
import tempfile

# Create temporary file
with tempfile.NamedTemporaryFile(mode='w', delete=True) as f:
    f.write('temporary data')  # File exists during context
    # File deleted on exit

# File persists after context (delete=False)
temp = tempfile.NamedTemporaryFile(delete=False)
path = temp.name
temp.close()
# Must manually delete
import os
os.unlink(path)
```

#### Space Complexity: O(n)

Where n = data size written to file.

```python
import tempfile

# File storage
with tempfile.NamedTemporaryFile() as f:
    f.write(b'x' * 1000000)  # O(n) disk space
```

## Unnamed Temporary Files

### TemporaryFile()

#### Time Complexity: O(r)

Where r = number of name attempts (<= TMP_MAX).

```python
import tempfile

# Unnamed temp file; uses O_TMPFILE when supported, otherwise creates and unlinks
with tempfile.TemporaryFile(mode='w+') as f:
    f.write('data')
    f.seek(0)
    content = f.read()  # O(n) read
    # Auto-deleted

# File-based fallback (e.g., when O_TMPFILE is unsupported)
# Creation time still O(r) for name attempts
temp = tempfile.TemporaryFile()
temp.write(b'content')
temp.close()
```

#### Space Complexity: O(n)

```python
import tempfile

# Memory/disk storage for content
with tempfile.TemporaryFile() as f:
    f.write(b'x' * 1000000)  # O(n) space
```

## Temporary Directories

### TemporaryDirectory()

#### Time Complexity: O(r)

Where r = number of name attempts (<= TMP_MAX).

```python
import tempfile
from pathlib import Path

# Create temporary directory
with tempfile.TemporaryDirectory() as tmpdir:
    path = Path(tmpdir)
    (path / 'file.txt').write_text('data')
    # Directory and contents deleted on exit

# Create without context manager
tmpdir = tempfile.mkdtemp()
# Must manually clean up
import shutil
shutil.rmtree(tmpdir)
```

#### Space Complexity: O(d)

Where d = number and size of files in directory.

```python
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmpdir:
    # Creates files
    path = Path(tmpdir)
    for i in range(100):
        (path / f'file{i}.txt').write_text('content')  # O(d) space
```

## Name Generation

### mkdtemp()

#### Time Complexity: O(r)

Where r = number of name attempts (<= TMP_MAX).

```python
import tempfile

# Create safe temporary directory
tmpdir = tempfile.mkdtemp()
# Must manually delete

# With custom prefix
tmpdir = tempfile.mkdtemp(prefix='myapp_')

# With custom suffix
tmpdir = tempfile.mkdtemp(suffix='_backup')
```

#### Space Complexity: O(1)

```python
import tempfile

# Directory name stored
tmpdir = tempfile.mkdtemp()  # O(1) extra memory
```

### gettempdir()

#### Time Complexity: O(1)

```python
import tempfile

# Get system temp directory
temp_dir = tempfile.gettempdir()  # Returns '/tmp' or similar

# Use for manual operations
from pathlib import Path
temp_path = Path(tempfile.gettempdir()) / 'myfile'
```

#### Space Complexity: O(1)

```python
import tempfile

# Returns cached system value
temp_dir = tempfile.gettempdir()  # O(1) space
```

## Common Patterns

### Safe Temporary File Processing

```python
import tempfile
from pathlib import Path

# Read, process, replace original
# Creating the file is O(r) in name attempts; the replace() below is O(1),
# which is what makes this pattern atomic rather than a copy
with tempfile.NamedTemporaryFile(mode='w', dir='.', delete=False) as tmp:
    tmp_path = tmp.name
    try:
        # Write processed data
        for line in process_data():
            tmp.write(line)
        # Replace original
        Path(tmp_path).replace('original.txt')
    except:
        Path(tmp_path).unlink()
        raise
```

### Temporary Directory for Multiple Files

```python
import tempfile
from pathlib import Path

# Work with multiple temporary files
# O(r) to create the directory, then O(k) files to clean up on exit
with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)
    
    # Create multiple files
    for i in range(10):
        (tmpdir / f'chunk_{i}.tmp').write_bytes(data[i])
    
    # Process all
    for chunk_file in tmpdir.glob('chunk_*.tmp'):
        process(chunk_file)
    # All cleaned up
```

### Persistent Temporary File

```python
import tempfile
from pathlib import Path

# Create file that persists until deleted
tmp = tempfile.NamedTemporaryFile(delete=False)  # O(r) name attempts
path = tmp.name
tmp.close()  # O(1) - delete=False means cleanup is now your job

try:
    # Use the file
    Path(path).write_text('data')
    process(path)
finally:
    # Clean up
    Path(path).unlink()
```

## Performance Characteristics

### Best Practices

```python
import tempfile

# Good: Use context managers
with tempfile.NamedTemporaryFile() as f:
    f.write(data)  # Auto-cleanup

# Good: TemporaryDirectory for collections
with tempfile.TemporaryDirectory() as tmpdir:
    # Create multiple files
    pass  # All cleaned up

# Avoid: Forgetting to cleanup
tmp = tempfile.NamedTemporaryFile(delete=False)
# File persists until manually deleted
```

### Memory Efficiency

```python
import tempfile

# Good: Stream processing
with tempfile.TemporaryFile() as f:
    for chunk in large_data_generator():  # Process in chunks
        f.write(chunk)
    f.seek(0)
    process(f)  # O(1) memory per chunk

# Avoid: Loading all data
import tempfile
with tempfile.TemporaryFile() as f:
    f.write(all_data)  # O(n) memory if all_data is loaded
```

## Platform-Specific Behavior

```python
import tempfile
import os

# All platforms
temp_dir = tempfile.gettempdir()  # O(1) after the first call - it caches

# Platform-dependent defaults
if os.name == 'nt':  # Windows
    # Usually C:\Users\...\AppData\Local\Temp
    pass
else:  # Unix/Linux
    # Usually /tmp
    pass

# Explicit control
tmpdir = tempfile.mkdtemp(dir='/custom/path')  # O(r) name attempts
```

## Related Documentation

- [Pathlib Module](pathlib.md) - Object-oriented filesystem paths
- [OS Module](os.md) - Low-level filesystem operations
- [Shutil Module](shutil.md) - High-level file operations
