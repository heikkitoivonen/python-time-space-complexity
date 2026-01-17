# Ntpath Module Complexity

The `ntpath` module provides Windows-compliant path operations. It's automatically used on Windows, but can be imported directly for cross-platform code.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `join(*paths)` | O(n) | O(n) | Join path components |
| `split(path)` | O(n) | O(n) | Split path into head/tail |
| `dirname(path)` | O(n) | O(n) | Get directory path |
| `basename(path)` | O(n) | O(n) | Get filename |
| `splitdrive(path)` | O(n) | O(n) | Split drive letter |
| `abspath(path)` | O(n) | O(n) | Make absolute path |
| `normpath(path)` | O(n) | O(n) | Normalize path |

## Path Joining

### join()

#### Time Complexity: O(n)

Where n = total length of all path components.

```python
import ntpath

# Join components: O(n)
path = ntpath.join('Users', 'user', 'Documents')  # O(n)
# Result: 'Users\\user\\Documents'

# With absolute component: O(n)
path = ntpath.join('path', 'C:\\absolute')  # O(n)
# Result: 'C:\\absolute'

# Drive handling: O(n)
path = ntpath.join('C:\\home', 'D:\\other')  # O(n)
```

#### Space Complexity: O(n)

```python
import ntpath

# Result string stored
path = ntpath.join('a' * 1000, 'b' * 1000)  # O(n) space
```

## Drive and Path Splitting

### splitdrive()

#### Time Complexity: O(n)

```python
import ntpath

# Split drive from path: O(n)
drive, path = ntpath.splitdrive('C:\\Users\\file.txt')
# drive: 'C:', path: '\\Users\\file.txt'

# UNC paths: O(n)
drive, path = ntpath.splitdrive('\\\\server\\share\\file')
# drive: '\\\\server\\share', path: '\\file'

# No drive: O(n)
drive, path = ntpath.splitdrive('relative\\path')
# drive: '', path: 'relative\\path'
```

#### Space Complexity: O(n)

```python
import ntpath

# Result strings
drive, path = ntpath.splitdrive('C:\\Users\\file')  # O(n) space
```

### split()

#### Time Complexity: O(n)

```python
import ntpath

# Split path: O(n)
head, tail = ntpath.split('C:\\Users\\Documents\\file.txt')
# head: 'C:\\Users\\Documents', tail: 'file.txt'

# With drive: O(n)
head, tail = ntpath.split('C:\\')
# head: 'C:\\', tail: ''
```

#### Space Complexity: O(n)

```python
import ntpath

# Results stored
head, tail = ntpath.split('C:\\path\\to\\file')  # O(n) space
```

### dirname() and basename()

#### Time Complexity: O(n)

```python
import ntpath

# Get directory: O(n)
dirname = ntpath.dirname('C:\\Users\\file.txt')  # O(n)
# Result: 'C:\\Users'

# Get filename: O(n)
basename = ntpath.basename('C:\\Users\\file.txt')  # O(n)
# Result: 'file.txt'
```

#### Space Complexity: O(n)

```python
import ntpath

# Result strings
d = ntpath.dirname('C:\\path\\to\\file.txt')  # O(n) space
```

## Path Normalization

### normpath()

#### Time Complexity: O(n)

```python
import ntpath

# Normalize: O(n)
path = ntpath.normpath('C:\\path\\.\\to\\..\\file.txt')  # O(n)
# Result: 'C:\\path\\file.txt'

# Forward slashes: O(n)
path = ntpath.normpath('C:/path/to/file.txt')  # O(n)
# Result: 'C:\\path\\to\\file.txt'

# Case normalization: O(n)
path = ntpath.normpath('C:\\PATH\\To\\File.TXT')  # O(n)
```

#### Space Complexity: O(n)

```python
import ntpath

# Result path stored
path = ntpath.normpath('C:\\' + 'a\\' * 1000)  # O(n) space
```

## Common Patterns

### Handle UNC Paths

```python
import ntpath

# UNC path (network share)
unc_path = '\\\\server\\share\\file.txt'
drive, path = ntpath.splitdrive(unc_path)  # O(n)
# drive: '\\\\server\\share', path: '\\file.txt'

# Reconstruct
full = ntpath.join(drive, path)  # O(n)
```

### Drive-Aware Path Operations

```python
import ntpath

path = 'C:\\Users\\Documents\\file.txt'

# Extract components: O(n) each
drive, path_part = ntpath.splitdrive(path)
directory = ntpath.dirname(path_part)
filename = ntpath.basename(path_part)

# Reconstruct: O(n)
new_path = ntpath.join(drive, directory, 'new_' + filename)
```

### Cross-Platform Path Handling

```python
import ntpath
import posixpath
import os

def to_ntpath(path):
    """Convert to Windows path: O(n)"""
    return ntpath.normpath(path)

def to_posixpath(path):
    """Convert to Unix path: O(n)"""
    # Replace backslashes with forward slashes
    return path.replace('\\', '/')

path = 'dir\\subdir\\file.txt'
# Both conversions are O(n)
```

## Performance Characteristics

### Best Practices

```python
import ntpath

# Good: Join multiple components at once
path = ntpath.join('C:\\', 'Users', 'Documents', 'file.txt')  # O(n)

# Avoid: Repeated joins
path = 'C:\\'
for component in components:
    path = ntpath.join(path, component)  # O(n*k) total

# Better: Single join
path = ntpath.join('C:\\', *components)  # O(n)
```

### UNC Performance

```python
import ntpath

# splitdrive on UNC paths still O(n)
unc = '\\\\server\\share\\dir\\file'
drive, path = ntpath.splitdrive(unc)  # O(n)

# Normalize complex paths
normalized = ntpath.normpath(unc + '\\.\\to\\..\\file')  # O(n)
```

## Comparison with posixpath

```python
import ntpath
import posixpath

# ntpath (Windows-style)
ntpath.join('Users', 'Documents')  # 'Users\\Documents'

# posixpath (Unix-style)
posixpath.join('Users', 'Documents')  # 'Users/Documents'

# Both have same complexity O(n)
```

## Comparison with pathlib

```python
import ntpath
from pathlib import PureWindowsPath

# ntpath (functional)
path = ntpath.join('C:\\', 'Users')  # O(n) string
dirname = ntpath.dirname(path)  # O(n)

# pathlib (object-oriented)
path = PureWindowsPath('C:\\') / 'Users'  # O(n) string
dirname = path.parent  # O(n) internally

# Similar complexity, pathlib more Pythonic
```

## Special Path Formats

```python
import ntpath

# Regular path
path = 'C:\\Users\\file.txt'
drive, _ = ntpath.splitdrive(path)  # 'C:'

# UNC network path
unc = '\\\\server\\share\\file'
drive, _ = ntpath.splitdrive(unc)  # '\\\\server\\share'

# Relative path
rel = 'folder\\file.txt'
drive, _ = ntpath.splitdrive(rel)  # ''

# All O(n) complexity
```

## Version Notes

- **Python 3.x**: Full Unicode support
- **All versions**: Available on all platforms

## Related Documentation

- [Posixpath Module](posixpath.md) - Unix path operations
- [Pathlib Module](pathlib.md) - Object-oriented paths
- [OS Module](os.md) - Platform-specific operations
