# Pathlib Module Complexity

The `pathlib` module provides an object-oriented approach to filesystem path handling.

## Classes and Methods

| Method | Time | Space | Notes |
|--------|------|-------|-------|
| `Path(str)` | O(n) | O(n) | Create Path from string |
| `Path.cwd()` | O(1) | O(n) | Get current directory |
| `Path.home()` | O(1) | O(n) | Get home directory |
| `Path.exists()` | O(1) | O(1) | Check if path exists |
| `Path.is_file()` | O(1) | O(1) | Check if path is file |
| `Path.is_dir()` | O(1) | O(1) | Check if path is directory |
| `Path.is_symlink()` | O(1) | O(1) | Check if path is symlink |
| `Path.stat()` | O(1) | O(1) | Get file stats |
| `Path.resolve()` | O(n) | O(n) | Resolve to absolute path |
| `Path.iterdir()` | O(d) | O(d) | Iterate directory contents |
| `Path.glob(pattern)` | O(n) | O(1) per item | n = directory entries checked, returns iterator |
| `Path.rglob(pattern)` | O(n) | O(1) per item | n = total tree entries, returns iterator |
| `Path.mkdir()` | O(1) | O(1) | Create directory |
| `Path.rename(target)` | O(1) | O(1) | Rename path |
| `Path.unlink()` | O(1) | O(1) | Delete file |
| `Path.rmdir()` | O(1) | O(1) | Delete empty directory |
| `Path.read_text()` | O(n) | O(n) | Read file as text |
| `Path.read_bytes()` | O(n) | O(n) | Read file as bytes |
| `Path.write_text()` | O(n) | O(n) | Write text to file |
| `Path.write_bytes()` | O(n) | O(n) | Write bytes to file |

## Path Construction

### Time Complexity: O(n)

Where n = length of the path string.

```python
from pathlib import Path

# Simple path: O(n) where n = path length
path = Path('/home/user/documents/file.txt')  # O(27)

# Relative path: O(n)
path = Path('docs/README.md')  # O(13)

# Current directory: O(1) - system call
cwd = Path.cwd()

# Home directory: O(1) - system call
home = Path.home()
```

### Space Complexity: O(n)

```python
from pathlib import Path

# Stores the path string
path = Path('/' + 'a' * 10000)  # O(n) space
```

## Path Operations

### exists(), is_file(), is_dir()

#### Time Complexity: O(1)

```python
from pathlib import Path

path = Path('file.txt')

# Single stat system call: O(1)
if path.exists():      # O(1) - stat call
    print('exists')

if path.is_file():     # O(1) - stat call
    print('is file')

if path.is_dir():      # O(1) - stat call
    print('is directory')
```

#### Space Complexity: O(1)

```python
from pathlib import Path

path = Path('large_name' * 100)

# No additional memory needed
exists = path.exists()  # O(1) space
```

## Path Resolution

### resolve()

#### Time Complexity: O(n)

Where n = number of symlinks to follow and path components.

```python
from pathlib import Path

# Simple resolution: O(n) where n = components
path = Path('docs/../files/./file.txt')
absolute = path.resolve()  # O(n) - normalize and resolve

# With symlinks: O(n) where n = symlinks + components
# Each symlink read is a system call
path = Path('/path/with/symlinks/file.txt')
absolute = path.resolve()  # O(n)
```

### Space Complexity: O(n)

```python
from pathlib import Path

# Stores resolved path
path = Path('relative/path').resolve()  # O(n) space
```

## Directory Operations

### iterdir()

#### Time Complexity: O(d)

Where d = number of directory entries.

```python
from pathlib import Path

path = Path('/home/user')

# List all entries: O(d) where d = entries
for item in path.iterdir():  # O(d)
    print(item)

# Count entries: O(d)
count = sum(1 for _ in path.iterdir())  # O(d)
```

#### Space Complexity: O(d)

```python
from pathlib import Path

path = Path('/home/user')

# Creates list of all entries
entries = list(path.iterdir())  # O(d) space

# Iterator uses O(1) space per entry
for item in path.iterdir():  # O(1) per iteration
    process(item)
```

### glob()

#### Time Complexity: O(d)

Where d = number of entries to check against pattern.

```python
from pathlib import Path

path = Path('.')

# Simple glob: O(d) where d = matching entries
py_files = list(path.glob('*.py'))  # O(d)

# Nested glob: O(d) for all matching
txt_files = list(path.glob('**/*.txt'))  # O(d)

# With pattern matching: O(d) where d = checked entries
results = list(path.glob('[a-z]*/data/*.json'))  # O(d)
```

#### Space Complexity: O(d)

```python
from pathlib import Path

# Results stored in memory
matches = list(Path('.').glob('*'))  # O(d) space

# Iterator approach: O(1) space
for match in Path('.').glob('*'):  # O(1) per iteration
    process(match)
```

### rglob()

#### Time Complexity: O(d)

Where d = total entries in directory tree.

```python
from pathlib import Path

path = Path('src')

# Recursive glob: O(d) where d = all entries
all_py = list(path.rglob('*.py'))  # O(d)

# Equivalent to glob('**/*pattern')
all_txt = list(path.rglob('*.txt'))  # O(d)
```

#### Space Complexity: O(d)

```python
from pathlib import Path

# All results in memory
matches = list(Path('.').rglob('*.py'))  # O(d) space
```

## File I/O

### read_text() / read_bytes()

#### Time Complexity: O(n)

Where n = file size.

```python
from pathlib import Path

path = Path('data.txt')

# Read entire file: O(n) where n = file size
content = path.read_text()  # O(n)

# Read binary: O(n)
data = path.read_bytes()  # O(n)

# Read with encoding: O(n)
content = path.read_text(encoding='utf-8')  # O(n)
```

#### Space Complexity: O(n)

```python
from pathlib import Path

# Stores entire file content
content = Path('large_file.txt').read_text()  # O(n) space
```

### write_text() / write_bytes()

#### Time Complexity: O(n)

Where n = content size.

```python
from pathlib import Path

path = Path('output.txt')

# Write text: O(n) where n = content size
path.write_text('Hello, World!')  # O(14)

# Write bytes: O(n)
path.write_bytes(b'Binary data')  # O(11)

# Overwrites file: O(n) regardless of original size
path.write_text('x' * 1000000)  # O(n)
```

#### Space Complexity: O(1)

```python
from pathlib import Path

# Streaming write - no buffer needed
content = 'x' * 1000000
Path('file.txt').write_text(content)  # O(1) extra space
```

## File System Modifications

### mkdir(), rmdir(), unlink(), rename()

#### Time Complexity: O(1)

```python
from pathlib import Path

# Create directory: O(1) - single system call
Path('new_dir').mkdir()  # O(1)

# Create with parents: O(d) where d = depth
Path('a/b/c/d').mkdir(parents=True, exist_ok=True)  # O(d)

# Remove file: O(1)
Path('file.txt').unlink()  # O(1)

# Remove directory: O(1) - must be empty
Path('empty_dir').rmdir()  # O(1)

# Rename: O(1) - same filesystem
Path('old.txt').rename('new.txt')  # O(1)
```

#### Space Complexity: O(1)

```python
from pathlib import Path

# No significant memory allocation
Path('dir').mkdir()  # O(1) space
Path('file.txt').unlink()  # O(1) space
```

## Common Patterns

### Safe File Operations

```python
from pathlib import Path

# Check before operating
path = Path('file.txt')

if path.exists() and path.is_file():  # O(1) + O(1)
    content = path.read_text()  # O(n)
```

### Directory Tree Processing

```python
from pathlib import Path

# Process all files: O(d) + O(n_i) for each file
for file in Path('src').rglob('*.py'):  # O(d) to find files
    content = file.read_text()  # O(n_i) per file
    process(content)  # Process file content
```

### Path Construction

```python
from pathlib import Path

# Build paths: O(1) per operation
base = Path('data')
file = base / 'subdir' / 'file.txt'  # O(1) per /

# Multiple files
for name in files:
    path = base / name  # O(1) per iteration
```

### Safe Deletion

```python
from pathlib import Path
import shutil

path = Path('directory')

# Delete directory and contents: O(d) where d = total items
if path.is_dir():  # O(1)
    shutil.rmtree(path)  # O(d)

# Or using pathlib
# Path.rmdir() only works on empty directories
```

## Comparison with os.path

```python
from pathlib import Path
import os

# pathlib (object-oriented)
p = Path('data') / 'file.txt'  # O(1)
exists = p.exists()  # O(1)
content = p.read_text()  # O(n)

# os.path (functional)
path = os.path.join('data', 'file.txt')  # O(n)
exists = os.path.exists(path)  # O(1)
with open(path) as f:  # O(1)
    content = f.read()  # O(n)

# Both have same algorithmic complexity
# pathlib is more convenient and cleaner
```

## Performance Characteristics

### Best Practices

```python
from pathlib import Path

# Good: Cache path objects
base = Path('/large/directory')
files = list(base.glob('*.py'))  # O(d) once

for file in files:  # Iterate cached results
    process(file)  # O(1) per file

# Bad: Repeated glob calls
for i in range(100):
    files = list(Path('.').glob('*.py'))  # O(d) * 100
```

### Avoiding Deep Recursion

```python
from pathlib import Path

# Good: Use glob for pattern matching
py_files = list(Path('src').rglob('*.py'))  # O(d) to find

# Avoid manual recursion if glob works
# Manual recursion has similar complexity but more overhead
```

## Version Notes

- **Python 3.4+**: pathlib introduced
- **Python 3.6+**: improved performance
- **Python 3.10+**: New methods and improvements
- **Python 3.13+**: Additional optimization

## Related Documentation

- [OS Module](os.md) - Low-level filesystem operations
- [Glob Module](glob.md) - Unix-style pathname expansion
