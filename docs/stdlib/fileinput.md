# Fileinput Module Complexity

The `fileinput` module provides an iterator for processing lines from multiple input files in a uniform way.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `input(files)` | O(n) | O(1) | Iterate file lines |
| `input()` with backup | O(n) | O(1) | In-place edit with backup |
| `filename()` | O(1) | O(1) | Get current file name |
| `filelineno()` | O(1) | O(1) | Get current line in file |
| `lineno()` | O(1) | O(1) | Get total line count |
| `close()` | O(1) | O(1) | Close file iterator |

## Basic Line Iteration

### input()

#### Time Complexity: O(n)

Where n = total lines across all files.

```python
import fileinput

# Iterate lines from multiple files
for line in fileinput.input(['file1.txt', 'file2.txt']):
    print(line.rstrip())  # O(n) to process all lines

# With stdin
for line in fileinput.input():
    print(line)  # O(n) for all input
```

#### Space Complexity: O(1)

```python
import fileinput

# Lazy iteration - no buffering
for line in fileinput.input(['huge_file.txt']):
    # Process one line at a time
    process(line)  # O(1) memory per iteration
```

## In-Place Editing

### Backup Creation

#### Time Complexity: O(n)

```python
import fileinput

# Modify files in-place with backup
for line in fileinput.input(['file1.txt', 'file2.txt'], 
                           backup='.bak', inplace=True):
    # Original backed up as file1.txt.bak
    print(line.upper().rstrip())  # Write to stdout -> redirected to file
```

#### Space Complexity: O(1)

```python
import fileinput

# Streaming in-place edit
for line in fileinput.input(inplace=True):
    print(line.rstrip())  # O(1) memory
```

### In-Place Without Backup

#### Time Complexity: O(n)

```python
import fileinput

# Edit without backup
for line in fileinput.input(['file.txt'], inplace=True, 
                           backup=''):
    print(line.rstrip())  # No backup created

# Original file modified, no .bak
```

#### Space Complexity: O(1)

```python
import fileinput

# Direct modification
for line in fileinput.input(['large_file.txt'], inplace=True, 
                           backup=''):
    process(line)  # O(1) memory
```

## Line Number Tracking

### linenum() and fileno()

#### Time Complexity: O(1)

```python
import fileinput

# Track line numbers
for line in fileinput.input(['file1.txt', 'file2.txt']):
    total_line_num = fileinput.lineno()      # O(1)
    file_line_num = fileinput.filelineno()   # O(1)
    filename = fileinput.filename()          # O(1)
    
    print(f'{filename}:{file_line_num}: {line.rstrip()}')
```

#### Space Complexity: O(1)

```python
import fileinput

# Metadata stored during iteration
for line in fileinput.input():
    num = fileinput.lineno()  # O(1) space - counter
```

## Context Manager Usage

#### Time Complexity: O(n)

```python
import fileinput

# Use as context manager (Python 3.10+)
with fileinput.input(['file1.txt', 'file2.txt']) as f:
    for line in f:
        print(line.rstrip())  # O(n) for all lines
# Auto-cleanup
```

#### Space Complexity: O(1)

```python
import fileinput

with fileinput.input(['file.txt']) as f:
    for line in f:
        process(line)  # O(1) streaming
```

## Common Patterns

### Simple Line Processing

```python
import fileinput

# Process lines from multiple files
for line in fileinput.input(['input1.txt', 'input2.txt']):
    # Line already has newline
    if line.startswith('#'):
        continue  # Skip comments
    
    print(line.rstrip())  # Remove trailing newline, print
```

### In-Place Text Replacement

```python
import fileinput
import sys

# Replace pattern in-place
def replace_in_files(files, old, new):
    for line in fileinput.input(files, inplace=True, backup='.bak'):
        print(line.replace(old, new).rstrip())

# Usage
replace_in_files(['config.txt', 'data.txt'], 'old_value', 'new_value')
# Creates .bak files as backups
```

### Count Lines in Multiple Files

```python
import fileinput

# Count all lines
count = 0
for line in fileinput.input(['file1.txt', 'file2.txt']):
    count += 1
print(f'Total lines: {count}')  # O(n)

# Group by file
lines_per_file = {}
for line in fileinput.input(['file1.txt', 'file2.txt']):
    filename = fileinput.filename()
    lines_per_file[filename] = fileinput.filelineno()
```

### Filter Lines Across Files

```python
import fileinput

# Extract specific lines
for line in fileinput.input(['file1.txt', 'file2.txt']):
    if 'ERROR' in line:
        filename = fileinput.filename()
        lineno = fileinput.lineno()
        print(f'{filename}:{lineno}: {line.rstrip()}')
```

### Add Line Numbers to Files

```python
import fileinput

for line in fileinput.input(inplace=True):
    lineno = fileinput.lineno()
    print(f'{lineno:5d}: {line.rstrip()}')

# Reads from stdin, writes to stdout with line numbers
# Usage: python script.py < input.txt
```

## Input Modes

### Text Mode (Default)

```python
import fileinput

# Read as text (default)
for line in fileinput.input(['file.txt']):
    print(type(line))  # str
    print(line.rstrip())
```

### Binary Mode (Not Directly Supported)

```python
import fileinput

# fileinput works with text by default
# For binary, use regular file operations
with open('file.bin', 'rb') as f:
    for line in f:
        process(line)
```

## Encoding Support

```python
import fileinput

# Specify encoding (Python 3.10+)
for line in fileinput.input(['utf8_file.txt'], 
                           openhook=fileinput.hook_encoded("utf-8")):
    print(line.rstrip())
```

## Performance Characteristics

### Best Practices

```python
import fileinput

# Good: Stream processing
for line in fileinput.input(['large_file.txt']):
    process(line)  # O(1) memory per line

# Good: Use context manager
with fileinput.input(['file.txt']) as f:
    for line in f:
        print(line.rstrip())

# Avoid: Loading all lines first
lines = []
for line in fileinput.input(['file.txt']):
    lines.append(line)  # O(n) memory
```

### In-Place Editing Safety

```python
import fileinput

# Good: Create backup
for line in fileinput.input(['config.txt'], 
                           inplace=True, backup='.bak'):
    print(line.rstrip())

# Risky: No backup
for line in fileinput.input(['config.txt'], 
                           inplace=True, backup=''):
    print(line.rstrip())  # Lost on error
```

## Error Handling

```python
import fileinput
import sys

def process_files_safely(files):
    try:
        for line in fileinput.input(files):
            try:
                process(line)
            except ValueError as e:
                filename = fileinput.filename()
                lineno = fileinput.lineno()
                print(f'Error {filename}:{lineno}: {e}', 
                      file=sys.stderr)
    finally:
        fileinput.close()

# Handle file not found
try:
    for line in fileinput.input(['nonexistent.txt']):
        pass
except FileNotFoundError as e:
    print(f'File error: {e}')
```

## Comparison with Alternatives

```python
import fileinput
from pathlib import Path

# fileinput (good for multiple files)
for line in fileinput.input(['file1.txt', 'file2.txt']):
    print(line.rstrip())  # O(n), O(1) memory

# pathlib (good for single operations)
for line in Path('file.txt').read_text().splitlines():
    print(line)  # O(n) time, O(n) memory

# direct open (good for single file)
with open('file.txt') as f:
    for line in f:
        print(line.rstrip())  # O(n) time, O(1) memory

# All similar time complexity, fileinput best for multiple files
```

## Sys.argv Integration

```python
import fileinput
import sys

# Automatically use command-line files or stdin
for line in fileinput.input():
    # Reads from files in sys.argv[1:] or stdin
    print(line.rstrip())

# Usage: python script.py file1.txt file2.txt
# Or:    python script.py < input.txt
```

## Version Notes

- **Python 3.10+**: Context manager support (`with` statement)
- **Python 3.10+**: `openhook` parameter for encoding

## Related Documentation

- [Pathlib Module](pathlib.md) - Object-oriented file paths
- [IO Module](io.md) - Core I/O classes
- [OS Module](os.md) - Operating system interface
