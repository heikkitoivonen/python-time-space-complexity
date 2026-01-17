# Posixpath Module Complexity

The `posixpath` module provides POSIX-compliant path operations. It's automatically used on Unix systems, but can be imported directly for cross-platform code.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `join(*paths)` | O(n) | O(n) | Join path components |
| `split(path)` | O(n) | O(n) | Split path into head/tail |
| `dirname(path)` | O(n) | O(n) | Get directory path |
| `basename(path)` | O(n) | O(n) | Get filename |
| `abspath(path)` | O(n) | O(n) | Make absolute path |
| `normpath(path)` | O(n) | O(n) | Normalize path |
| `exists(path)` | O(1) + syscall | O(1) | Single stat syscall |
| `isfile(path)` | O(1) + syscall | O(1) | Single stat syscall |
| `isdir(path)` | O(1) + syscall | O(1) | Single stat syscall |

## Path Joining

### join()

#### Time Complexity: O(n)

Where n = total length of all path components.

```python
import posixpath

# Join components: O(n)
path = posixpath.join('home', 'user', 'docs')  # O(n)
# Result: 'home/user/docs'

# With absolute component: O(n)
path = posixpath.join('home', '/abs', 'path')  # O(n)
# Result: '/abs/path' (previous parts discarded)

# Multiple joins: O(n*k) where k = number of joins
base = 'path'
for component in components:
    base = posixpath.join(base, component)  # O(n) per join
```

#### Space Complexity: O(n)

```python
import posixpath

# Result string stored
path = posixpath.join('a' * 1000, 'b' * 1000)  # O(n) space
```

## Path Splitting

### split()

#### Time Complexity: O(n)

```python
import posixpath

# Split path: O(n) to scan string
head, tail = posixpath.split('/home/user/file.txt')
# head: '/home/user', tail: 'file.txt'

# Empty tail
head, tail = posixpath.split('/home/user/')
# head: '/home/user', tail: ''

# Iteratively split: O(n*k) where k = depth
parts = []
path = '/a/b/c/d'
while path:
    path, tail = posixpath.split(path)  # O(n) per split
    if tail:
        parts.append(tail)
```

#### Space Complexity: O(n)

```python
import posixpath

# Results are strings
head, tail = posixpath.split('/path/to/file')  # O(n) space total
```

### dirname() and basename()

#### Time Complexity: O(n)

```python
import posixpath

# Get directory: O(n) to find separator
dirname = posixpath.dirname('/home/user/file.txt')  # O(n)
# Result: '/home/user'

# Get filename: O(n)
basename = posixpath.basename('/home/user/file.txt')  # O(n)
# Result: 'file.txt'
```

#### Space Complexity: O(n)

```python
import posixpath

# Result strings
d = posixpath.dirname('/path/to/file.txt')  # O(n) space
```

## Path Normalization

### normpath()

#### Time Complexity: O(n)

```python
import posixpath

# Normalize: O(n) to process all characters
path = posixpath.normpath('path/./to/../file.txt')  # O(n)
# Result: 'path/file.txt'

# Complex normalization
path = posixpath.normpath('/a//b/c///d/../e')  # O(n)
# Result: '/a/b/c/e'
```

#### Space Complexity: O(n)

```python
import posixpath

# Result path stored
path = posixpath.normpath('/a/' * 1000 + 'file')  # O(n) space
```

### abspath()

#### Time Complexity: O(n)

```python
import posixpath
import os

# Make absolute: O(n) to append to cwd
abs_path = posixpath.abspath('relative/path')  # O(n)

# Already absolute: O(n) to normalize
abs_path = posixpath.abspath('/absolute/path')  # O(n)
```

#### Space Complexity: O(n)

```python
import posixpath

# Result string
path = posixpath.abspath('file.txt')  # O(n) space
```

## Common Patterns

### Build Complex Paths

```python
import posixpath

# Construct path step-by-step: O(n*k) where k = components
base = '/home/user'
subdir = 'documents'
filename = 'report_2024.txt'
path = posixpath.join(base, subdir, filename)  # O(n)
```

### Extract Path Components

```python
import posixpath

# Get directory and filename: O(n)
full_path = '/home/user/file.txt'
directory = posixpath.dirname(full_path)  # O(n)
filename = posixpath.basename(full_path)   # O(n)

# Extract extension
name, ext = posixpath.splitext(filename)  # O(n)
# name: 'file', ext: '.txt'
```

### Cross-Platform Paths

```python
import posixpath
import ntpath

# Use posixpath on Windows for Unix paths
unix_path = posixpath.join('path', 'to', 'file')

# Convert to native
import os
native_path = os.path.normpath(unix_path)
```

## Performance Characteristics

### Best Practices

```python
import posixpath

# Good: Cache joined paths
base = '/data'
file1 = posixpath.join(base, 'file1.txt')  # O(n)
file2 = posixpath.join(base, 'file2.txt')  # O(n)

# Avoid: Repeated string concatenation
path = 'a'
for component in components:
    path = path + '/' + component  # O(n*k) in Python

# Better: Use join
path = posixpath.join(*components)  # O(n)
```

### Multiple Operations

```python
import posixpath

path = '/home/user/documents/file.txt'

# Efficient: Combine operations
directory = posixpath.dirname(path)  # O(n)
filename = posixpath.basename(path)   # O(n)

# Less efficient: Multiple splits
head, tail = posixpath.split(path)  # O(n)
# Then operate on head/tail
```

## Comparison with ntpath

```python
import posixpath
import ntpath

# posixpath: Unix-style
posixpath.join('home', 'user')  # 'home/user'

# ntpath: Windows-style
ntpath.join('home', 'user')     # 'home\\user'

# Both have same complexity
```

## Comparison with pathlib

```python
import posixpath
from pathlib import PurePosixPath

# posixpath (functional)
path = posixpath.join('a', 'b')  # O(n) string
dirname = posixpath.dirname(path)  # O(n)

# pathlib (object-oriented)
path = PurePosixPath('a') / 'b'  # O(n) string
dirname = path.parent  # O(n) internally

# Similar complexity, pathlib more Pythonic
```

## Version Notes

- **Python 3.x**: Full Unicode path support
- **All versions**: Available on all platforms

## Related Documentation

- [Ntpath Module](ntpath.md) - Windows path operations
- [Pathlib Module](pathlib.md) - Object-oriented paths
- [OS Module](os.md) - Platform-specific operations
