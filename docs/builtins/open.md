# open() Function Complexity

The `open()` function opens a file and returns a file object, allowing reading, writing, and manipulation of file contents.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `open(filename)` | O(1) | O(1) | Open file (system call) |
| `file.read()` | O(n) | O(n) | n = file size |
| `file.readline()` | O(k) | O(k) | k = line length |
| `file.readlines()` | O(n) | O(n) | n = file size |
| `file.write(data)` | O(k) | O(1) | k = data length |
| `file.close()` | O(1) | O(1) | Flush and close |
| `for line in file:` | O(n) | O(1) | n = file size (lazy iteration) |

## Opening Files

### Basic File Operations

```python
# Open for reading - O(1) system call
file = open('data.txt', 'r')  # O(1)
content = file.read()         # O(n) - read entire file
file.close()                  # O(1)

# Or use context manager (recommended)
with open('data.txt', 'r') as file:  # O(1)
    content = file.read()             # O(n)
# File automatically closed - O(1)
```

### File Modes

```python
# Read mode (default) - O(1)
file = open('file.txt', 'r')      # O(1) - text mode

# Binary mode - O(1)
file = open('file.bin', 'rb')     # O(1) - binary read

# Write mode - O(1)
file = open('output.txt', 'w')    # O(1) - text write

# Append mode - O(1)
file = open('log.txt', 'a')       # O(1) - append to end

# Read/Write - O(1)
file = open('data.txt', 'r+')     # O(1) - read and write
```

## Reading File Contents

### Read Methods

```python
with open('data.txt', 'r') as file:
    # Read entire file - O(n)
    content = file.read()  # O(file_size)
    
    # Read line by line - O(k) per line
    file.seek(0)  # O(1) - go to start
    line = file.readline()  # O(k) - k = line length
    
    # Read all lines into list - O(n)
    file.seek(0)
    lines = file.readlines()  # O(n) - creates list
    
    # Iterate lines (memory efficient) - O(1) per line
    file.seek(0)
    for line in file:  # O(1) per iteration, lazy
        process(line)
```

### Reading Line by Line (Memory Efficient)

```python
# Best for large files: iterate without loading all
with open('largefile.txt', 'r') as file:
    for line in file:  # O(1) per line, O(1) memory
        # Process one line at a time
        print(line.strip())

# vs. loading all at once - O(n) memory
with open('largefile.txt', 'r') as file:
    all_lines = file.readlines()  # O(n) memory!
    for line in all_lines:        # Still O(1) per iteration
        print(line.strip())
```

## Writing to Files

### Write Operations

```python
# Write string - O(k) where k = string length
with open('output.txt', 'w') as file:
    file.write('Hello')  # O(5)
    file.write(' ')      # O(1)
    file.write('World')  # O(5)

# Write multiple lines - O(n)
lines = ['Line 1\n', 'Line 2\n', 'Line 3\n']
with open('output.txt', 'w') as file:
    file.writelines(lines)  # O(n)

# Write with formatting - O(n)
with open('output.txt', 'w') as file:
    for i, item in enumerate(items):
        file.write(f"{i}: {item}\n")  # O(k) per write
```

## File Iteration

### Iterating Lines

```python
# Most efficient: lazy line iteration - O(1) memory per line
with open('data.txt', 'r') as file:
    for line in file:  # O(1) per iteration
        # Process line
        process(line)

# This is more efficient than:
with open('data.txt', 'r') as file:
    for line in file.readlines():  # O(n) memory upfront!
        process(line)

# For files with millions of lines:
# - Iteration: O(n) time, O(1) memory
# - readlines(): O(n) time, O(n) memory
```

## File Positioning

### Seek and Tell

```python
with open('data.txt', 'rb') as file:
    # Get current position - O(1)
    pos = file.tell()  # Usually 0 at start
    
    # Read some bytes - O(k)
    data = file.read(100)  # O(100)
    
    # Get new position - O(1)
    pos = file.tell()  # Around 100
    
    # Seek to beginning - O(1)
    file.seek(0)  # Go to start
    
    # Seek to end - O(1)
    file.seek(0, 2)  # Go to end
    
    # Get file size - O(1)
    size = file.tell()
```

### Random Access

```python
# Efficient seeking (in binary mode) - O(1)
with open('data.bin', 'rb') as file:
    # Jump to position - O(1)
    file.seek(1000)
    data = file.read(100)  # O(100)
    
    # Jump again - O(1)
    file.seek(2000)
    data = file.read(100)  # O(100)

# Note: seeking is fast; reading at new position is O(k)
```

## File Object Methods

### Useful Methods

```python
with open('data.txt', 'r') as file:
    # Check if writable - O(1)
    is_writable = file.writable()
    
    # Check if readable - O(1)
    is_readable = file.readable()
    
    # Check if seekable - O(1)
    is_seekable = file.seekable()
    
    # Get file name - O(1)
    name = file.name
    
    # Get file mode - O(1)
    mode = file.mode
    
    # Flush buffer - O(1) usually
    file.flush()
    
    # Truncate file - O(1) usually
    file.truncate()
```

## Common Patterns

### Read and Process

```python
# Read entire small file - O(n)
with open('config.json', 'r') as file:
    config = json.load(file)  # O(n)

# Read large file line by line - O(n) time, O(1) memory
with open('data.csv', 'r') as file:
    for line in file:  # O(1) per iteration
        row = parse_csv(line)  # O(k) per line
        process(row)
```

### Write Results

```python
# Write results - O(n)
with open('results.txt', 'w') as file:
    for result in results:  # O(n) iterations
        file.write(f"{result}\n")  # O(k) per write

# Write in bulk - O(n)
with open('results.txt', 'w') as file:
    file.writelines([f"{r}\n" for r in results])  # O(n)
```

### Line Counting

```python
# Efficient line counting - O(n) time, O(1) memory
def count_lines(filename):
    count = 0
    with open(filename, 'r') as file:
        for _ in file:  # O(1) per line
            count += 1
    return count

# vs. loading all lines - O(n) time, O(n) memory
def count_lines_bad(filename):
    with open(filename, 'r') as file:
        return len(file.readlines())  # O(n) memory!
```

## Binary vs Text Mode

### Text Mode

```python
# Text mode (default) - O(n)
with open('data.txt', 'r') as file:
    content = file.read()  # Decoded as UTF-8 by default

# With specific encoding - O(n)
with open('data.txt', 'r', encoding='utf-8') as file:
    content = file.read()  # O(n)
```

### Binary Mode

```python
# Binary mode - O(n)
with open('data.bin', 'rb') as file:
    content = file.read()  # No decoding, raw bytes

# Good for non-text files (images, executables)
with open('image.png', 'rb') as file:
    image_data = file.read()  # O(n) - raw bytes
```

## Performance Optimization

### Buffering

```python
# Buffering affects write performance
# Full buffering (default for files)
with open('output.txt', 'w', buffering=-1) as file:
    for _ in range(1000):
        file.write("x")  # Buffered, few actual system calls

# Line buffering (default for terminals)
with open('log.txt', 'w', buffering=1) as file:
    for _ in range(1000):
        file.write("x\n")  # Flushed on newline

# No buffering
with open('output.txt', 'w', buffering=0) as file:
    for _ in range(1000):
        file.write("x")  # Each write is system call - slow!
```

### Batch Processing

```python
# Inefficient: many small reads - O(n) with overhead
with open('data.txt', 'r') as file:
    while True:
        char = file.read(1)  # O(1) but with overhead
        if not char:
            break
        process(char)

# Efficient: read chunks - O(n) with less overhead
with open('data.txt', 'r') as file:
    chunk_size = 8192  # 8KB chunks
    while True:
        chunk = file.read(chunk_size)  # O(chunk_size)
        if not chunk:
            break
        for line in chunk.split('\n'):
            process(line)
```

## Context Manager Benefits

### Proper Cleanup

```python
# Manual file handling (error-prone)
file = open('data.txt', 'r')
try:
    data = file.read()  # If error here, file not closed!
finally:
    file.close()

# Context manager (guaranteed cleanup)
with open('data.txt', 'r') as file:  # O(1) - open
    data = file.read()  # O(n) - read
# O(1) - auto close, even if error!
```

## Special File Types

### File-like Objects

```python
# StringIO - in-memory file
from io import StringIO
file = StringIO("Hello\nWorld")  # O(n) to create
content = file.read()  # O(n)

# BytesIO - in-memory bytes
from io import BytesIO
file = BytesIO(b"Hello")  # O(n)
content = file.read()  # O(n)

# These behave like files but in memory
```

## Exception Handling

### Common Exceptions

```python
try:
    with open('missing.txt', 'r') as file:  # O(1)
        content = file.read()  # O(n)
except FileNotFoundError:
    print("File doesn't exist")
except PermissionError:
    print("No permission to read")
except IOError as e:
    print(f"IO error: {e}")
```

## Version Notes

- **Python 2.x**: `open()` vs `file()` (both work)
- **Python 3.x**: `open()` unified (recommended)
- **All versions**: Context manager support in 2.5+

## Related Functions

- **[pathlib.Path.open()](../stdlib/pathlib.md)** - Modern path-based file opening
- **[with statement](builtins/with.md)** - Context manager for safe resource handling
- **[io module](../stdlib/io.md)** - Low-level I/O operations

## Best Practices

✅ **Do**:
- Use context manager (`with` statement) for automatic cleanup
- Iterate large files line-by-line (lazy evaluation)
- Use binary mode for non-text files
- Specify encoding for text files
- Seek only in binary mode (text mode has issues)

❌ **Avoid**:
- Forgetting to close files (use `with`)
- Loading huge files entirely into memory (`readlines()`)
- Manual try/finally instead of context managers
- Seeking in text mode (complex due to encoding)
- Multiple small reads instead of buffered chunks
