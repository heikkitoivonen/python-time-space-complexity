# Shutil Module Complexity

The `shutil` module provides high-level file operations like copying and removing directory trees.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copy(src, dst)` | O(n) | O(1) | Copy file and permissions |
| `copy2(src, dst)` | O(n) | O(1) | Copy with metadata |
| `copytree(src, dst)` | O(d*n) | O(d) | Copy directory tree |
| `rmtree(path)` | O(d) | O(d) | Remove directory tree |
| `move(src, dst)` | O(n) | O(1) | Move file/directory |
| `disk_usage(path)` | O(d) | O(1) | Get disk usage stats |

## File Copying

### copy()

#### Time Complexity: O(n)

Where n = file size.

```python
import shutil

# Copy file with permissions
shutil.copy('source.txt', 'dest.txt')  # O(n) to read/write

# To directory
shutil.copy('file.txt', '/path/to/dir/')

# Copy multiple files: O(k*n) where k = files
for src in sources:
    shutil.copy(src, dest_dir)  # O(n) per file
```

#### Space Complexity: O(1)

```python
import shutil

# Streaming copy - no buffer needed
shutil.copy('large_file.bin', 'copy.bin')  # O(1) extra space
```

### copy2()

#### Time Complexity: O(n)

```python
import shutil

# Copy with metadata (timestamps, permissions)
shutil.copy2('source.txt', 'dest.txt')  # O(n) + metadata

# Preserves all file attributes
import os
stat_before = os.stat('source.txt')
shutil.copy2('source.txt', 'dest.txt')
stat_after = os.stat('dest.txt')
# Timestamps preserved
```

#### Space Complexity: O(1)

```python
import shutil

# Streaming like copy()
shutil.copy2('file.bin', 'copy.bin')  # O(1) extra space
```

## Directory Tree Operations

### copytree()

#### Time Complexity: O(d*n)

Where d = total entries, n = average file size.

```python
import shutil

# Copy entire directory tree
shutil.copytree('src_dir', 'dst_dir')  # O(d*n) to copy all files

# With ignore patterns
shutil.copytree('src', 'dst', 
                ignore=shutil.ignore_patterns('*.pyc', '__pycache__'))

# Allow existing destination (merge)
shutil.copytree('src', 'dst', dirs_exist_ok=True)
```

#### Space Complexity: O(d)

```python
import shutil

# Maintains directory structure
shutil.copytree('src', 'dst')  # O(d) for directory entries
```

### rmtree()

#### Time Complexity: O(d)

Where d = total entries in tree.

```python
import shutil

# Remove directory and all contents
shutil.rmtree('old_dir')  # O(d) where d = total files/dirs

# Visit each file/directory once
# No additional sorting or processing needed
shutil.rmtree('/path/to/large/tree')  # O(d) regardless of depth
```

#### Space Complexity: O(d)

```python
import shutil

# Internal: may maintain entry list
shutil.rmtree('dir')  # O(d) space for directory listing
```

## File Movement

### move()

#### Time Complexity: O(1) or O(n)

- O(1) on same filesystem (rename)
- O(n) across filesystems (copy + delete)

```python
import shutil

# Rename (same filesystem): O(1)
shutil.move('old.txt', 'new.txt')  # O(1) - atomic rename

# Move to directory: O(1)
shutil.move('file.txt', '/path/to/dir/')  # O(1) if same filesystem

# Across filesystems: O(n)
shutil.move('local_file.txt', '/mnt/external/file.txt')
# Falls back to copy + delete: O(n)
```

#### Space Complexity: O(1) or O(n)

```python
import shutil

# Same filesystem: O(1) space
shutil.move('file1.txt', 'file2.txt')  # O(1)

# Cross-filesystem: O(n) if copy needed
shutil.move('src', '/different/mount')  # O(n) space for copy
```

### Disk Usage

#### Time Complexity: O(d)

Where d = total entries traversed.

```python
import shutil

# Calculate disk usage
total, used, free = shutil.disk_usage('/')  # O(1) system call

# For directory: O(d) where d = entries
def get_dir_size(path):
    total = 0
    for size in (f.stat().st_size 
                 for f in Path(path).rglob('*')):  # O(d)
        total += size
    return total
```

#### Space Complexity: O(1)

```python
import shutil

# Returns fixed tuple
usage = shutil.disk_usage('/')  # O(1) space
```

## Common Patterns

### Safe Directory Replacement

```python
import shutil
import tempfile
from pathlib import Path

# Create replacement directory safely
old_dir = 'current'
with tempfile.TemporaryDirectory() as tmpdir:
    # Build in temp location: O(d*n)
    shutil.copytree('source', tmpdir, dirs_exist_ok=True)
    
    # Atomic replacement
    old_backup = 'current_backup'
    Path(old_dir).replace(old_backup)  # O(1)
    Path(tmpdir).replace(old_dir)      # O(1)
```

### Selective Copy

```python
import shutil
from pathlib import Path

# Copy only Python files
shutil.copytree('src', 'dst',
                ignore=shutil.ignore_patterns('*', '!*.py'))

# Custom ignore function
def ignore_large_files(dir, files):
    return [f for f in files if Path(dir, f).stat().st_size > 1_000_000]

shutil.copytree('src', 'dst', ignore=ignore_large_files)
```

### Backup Before Replace

```python
import shutil
from pathlib import Path
import datetime

def safe_replace(source, target):
    # Backup existing
    if Path(target).exists():
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = f'{target}.backup_{timestamp}'
        Path(target).rename(backup)  # O(1)
    
    # Move new version
    shutil.move(source, target)  # O(1) or O(n)
```

### Copy with Progress

```python
import shutil
from pathlib import Path

# Track copy progress
def copy_with_progress(src, dst):
    size = Path(src).stat().st_size
    print(f'Copying {size} bytes...')
    
    shutil.copy2(src, dst)  # O(n)
    
    print(f'Done: {Path(dst).stat().st_size} bytes')
```

## Ignore Patterns

### Common Patterns

```python
import shutil

# Ignore patterns (glob-style)
ignore = shutil.ignore_patterns(
    '*.pyc',           # All .pyc files
    '__pycache__',     # Cache directories
    '.git',            # Version control
    'node_modules',    # Dependencies
    '*.egg-info',      # Package info
)

shutil.copytree('src', 'dst', ignore=ignore)
```

### Custom Ignore Function

```python
import shutil
from pathlib import Path

def ignore_function(directory, contents):
    """Return list of items to ignore."""
    ignored = []
    for item in contents:
        path = Path(directory) / item
        
        # Ignore symlinks
        if path.is_symlink():
            ignored.append(item)
        
        # Ignore hidden files
        elif item.startswith('.'):
            ignored.append(item)
        
        # Ignore large files
        elif path.is_file() and path.stat().st_size > 1_000_000:
            ignored.append(item)
    
    return ignored

shutil.copytree('src', 'dst', ignore=ignore_function)
```

## Performance Considerations

### Best Practices

```python
import shutil

# Good: Use shutil for tree operations
shutil.copytree('src', 'dst')  # Optimized tree copy

# Good: Batch operations when possible
shutil.move('old', 'new')  # Single operation

# Avoid: Manual file-by-file copy
from pathlib import Path
for f in Path('src').rglob('*'):
    if f.is_file():
        shutil.copy(f, f'dst/{f.name}')  # Less efficient
```

### Memory Efficiency

```python
import shutil
from pathlib import Path

# Good: Stream processing
shutil.copy('large_file.iso', 'backup.iso')  # Streaming copy

# Avoid: Loading entire file
with open('large_file', 'rb') as f:
    content = f.read()  # O(n) memory
```

## Error Handling

```python
import shutil
from pathlib import Path

# Handle errors during tree operations
try:
    shutil.copytree('src', 'dst')
except shutil.Error as e:
    # Multiple errors may occur
    for src, dst, err in e.args[0]:
        print(f'Failed: {src} -> {dst}: {err}')

# Check before operating
if not Path('src').exists():
    raise FileNotFoundError('Source not found')

# Safe move with error handling
try:
    shutil.move('src', 'dst')
except (OSError, shutil.Error):
    # Handle cross-filesystem move failure
    pass
```

## Atomic Operations

```python
import shutil
from pathlib import Path

# Most atomic: Rename on same filesystem
Path('old').rename('new')  # O(1) - atomic

# Less atomic: Move across filesystems
shutil.move('src', '/different/mount/dst')  # O(n) - not atomic

# Create in temp, then replace
import tempfile
with tempfile.NamedTemporaryFile(dir='.', delete=False) as tmp:
    shutil.copy(source, tmp.name)  # O(n) - safe
    Path(tmp.name).replace(dest)    # O(1) - atomic
```

## Version Notes

- **Python 3.8+**: `dirs_exist_ok` parameter added to `copytree()`
- **Python 3.10+**: `copy_function` parameter for custom copying

## Related Documentation

- [Pathlib Module](pathlib.md) - Object-oriented filesystem paths
- [OS Module](os.md) - Low-level filesystem operations
- [Tempfile Module](tempfile.md) - Temporary file handling
