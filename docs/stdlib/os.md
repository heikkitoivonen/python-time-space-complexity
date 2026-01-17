# os Module Complexity

The `os` module provides a way to use operating system-dependent functionality like reading or writing to the file system.

## File Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.path.exists(path)` | O(1) | O(1) | Check if path exists |
| `os.path.isfile(path)` | O(1) | O(1) | Check if file |
| `os.path.isdir(path)` | O(1) | O(1) | Check if directory |
| `os.listdir(path)` | O(n) | O(n) | List directory contents |
| `os.scandir(path)` | O(n) | O(1) | Lazy directory iterator |
| `os.walk(path)` | O(n) | O(d) | Walk directory tree, n = total entries, d = max depth for stack |
| `os.stat(path)` | O(1) | O(1) | Get file statistics |
| `os.lstat(path)` | O(1) | O(1) | Stat without following symlink |
| `os.remove(path)` | O(1) | O(1) | Delete file |
| `os.mkdir(path)` | O(1) | O(1) | Create directory |
| `os.makedirs(path)` | O(n) | O(1) | Create directories, n = depth |
| `os.rmdir(path)` | O(1) | O(1) | Remove empty directory |
| `os.rename(src, dst)` | O(1) | O(1) | Rename/move file |
| `os.chmod(path, mode)` | O(1) | O(1) | Change permissions |

## Path Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `os.path.join(paths)` | O(n) | O(n) | Join path components, n = total length |
| `os.path.split(path)` | O(n) | O(n) | Split head and tail |
| `os.path.dirname(path)` | O(n) | O(n) | Get directory part |
| `os.path.basename(path)` | O(n) | O(n) | Get filename part |
| `os.path.splitext(path)` | O(n) | O(n) | Split extension |
| `os.path.abspath(path)` | O(n) | O(n) | Get absolute path |
| `os.path.realpath(path)` | O(n) | O(n) | Resolve symlinks |
| `os.path.normpath(path)` | O(n) | O(n) | Normalize path |

## Common Operations

### Checking File Existence

```python
import os

# Fast existence check - O(1)
if os.path.exists("/path/to/file"):
    print("File exists")

# Check type - O(1)
if os.path.isfile("/path/to/file"):
    print("Is a file")

if os.path.isdir("/path/to/dir"):
    print("Is a directory")
```

### Listing Files

```python
import os

# Get all files - O(n) where n = number of items
files = os.listdir("/path/to/dir")

# Better: lazy iteration - O(1) per item
with os.scandir("/path/to/dir") as entries:
    for entry in entries:  # O(1) each
        print(entry.name)
        print(entry.is_file())  # O(1)
```

### Walking Directory Tree

```python
import os

# Walk recursively - O(n) where n = total files
for dirpath, dirnames, filenames in os.walk("/path/to/root"):
    # Process files
    for filename in filenames:
        path = os.path.join(dirpath, filename)
        # Do something - O(1) per file
```

### File Metadata

```python
import os

# Get file stats - O(1)
stats = os.stat("/path/to/file")
print(stats.st_size)      # File size
print(stats.st_mtime)     # Modification time
print(stats.st_mode)      # Permissions

# Check if readable - O(1)
if os.access("/path/to/file", os.R_OK):
    print("Readable")
```

## Path Manipulation

```python
import os

# Join paths - O(n)
path = os.path.join("/home", "user", "documents", "file.txt")

# Split path - O(n)
dirname, filename = os.path.split(path)
# dirname = "/home/user/documents"
# filename = "file.txt"

# Get extension - O(n)
name, ext = os.path.splitext("file.txt")
# name = "file"
# ext = ".txt"

# Get absolute path - O(n)
abs_path = os.path.abspath("./relative/path")
```

## Creating and Removing

```python
import os

# Create directory - O(1)
os.mkdir("/new/dir")

# Create all parent dirs - O(n) where n = depth
os.makedirs("/deep/nested/dir/structure")

# Remove file - O(1)
os.remove("/path/to/file")

# Remove empty dir - O(1)
os.rmdir("/empty/dir")

# Remove tree (careful!) - O(n)
import shutil
shutil.rmtree("/path/to/remove")
```

## Environment Variables

```python
import os

# Get environment - O(1)
home = os.environ['HOME']

# Get with default - O(1)
user = os.environ.get('USER', 'unknown')

# Set environment - O(1)
os.environ['MY_VAR'] = 'value'

# All environment variables - O(m) where m = number of vars
all_vars = os.environ.items()
```

## Process Information

```python
import os

# Current process ID - O(1)
pid = os.getpid()

# Parent process ID - O(1)
ppid = os.getppid()

# Current working directory - O(1)
cwd = os.getcwd()

# Change working directory - O(1)
os.chdir("/new/directory")
```

## Performance Notes

### Efficient File Listing

```python
import os

# Less efficient - returns all names, no file type info
files = os.listdir(".")  # Must separate files/dirs separately

# More efficient - lazy, includes file type info
with os.scandir(".") as entries:
    files = [e.name for e in entries if e.is_file()]
```

### Avoiding Unnecessary Stats

```python
import os

path = "/path/to/file"

# Bad: two stat calls
if os.path.exists(path) and os.path.getsize(path) > 0:
    pass

# Better: one stat call
try:
    size = os.path.getsize(path)  # O(1)
    if size > 0:
        pass
except FileNotFoundError:
    pass
```

## Version Notes

- **Python 2.x**: Basic functionality, limited Unicode support
- **Python 3.x**: Full Unicode path support
- **Python 3.5+**: `os.scandir()` is faster for directory iteration
- **Python 3.10+**: More type hints, better cross-platform support

## Platform Differences

- **POSIX** (Linux, macOS): Full feature set
- **Windows**: Some path operations differ (backslashes vs forward slashes)
- **Path handling**: Use `os.path.join()` or better: `pathlib.Path`

## Related Modules

- **[pathlib](pathlib.md)** - Object-oriented path handling (recommended)
- **[glob](glob.md)** - Unix-style pathname expansion
- **[shutil](shutil.md)** - High-level file operations
- **[tempfile](tempfile.md)** - Temporary files

## Best Practices

✅ **Do**:
- Use `os.path.join()` for cross-platform compatibility
- Use `os.scandir()` for directory listing (faster)
- Use `pathlib.Path` for modern code (more readable)
- Check existence before accessing files

❌ **Avoid**:
- Assuming forward slashes work on all platforms
- Using string concatenation for paths
- Multiple stat calls when one suffices
- Hardcoding paths (use environment variables)
