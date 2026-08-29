# fnmatch Module Complexity

The `fnmatch` module provides Unix filename pattern matching using shell-style wildcards, useful for filtering filenames and simple pattern matching without regular expressions.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fnmatch()` | O(n) | O(1) | n = string length |
| `fnmatchcase()` | O(n) | O(1) | Case-sensitive version |
| `filter()` | O(k*n) | O(k) | k = items, n = string length |
| `translate()` | O(n) | O(n) | Convert pattern to regex |
| `filterfalse()` | O(k*n) | O(k) | Invert filter results |

## Pattern Matching

### Basic Patterns

```python
import fnmatch

# Basic pattern matching - O(n)
print(fnmatch.fnmatch('hello.txt', '*.txt'))      # True
print(fnmatch.fnmatch('test.py', '*.txt'))        # False
print(fnmatch.fnmatch('file123.txt', 'file*.txt')) # True

# ? matches single character - O(n)
print(fnmatch.fnmatch('test1.txt', 'test?.txt'))  # True
print(fnmatch.fnmatch('test12.txt', 'test?.txt')) # False

# [abc] matches any in brackets - O(n)
print(fnmatch.fnmatch('testa.txt', 'test[abc].txt'))  # True
print(fnmatch.fnmatch('testd.txt', 'test[abc].txt'))  # False

# [!abc] negation - O(n)
print(fnmatch.fnmatch('testd.txt', 'test[!abc].txt')) # True
print(fnmatch.fnmatch('testa.txt', 'test[!abc].txt')) # False
```

### Pattern Wildcards

```python
import fnmatch

# Every match below is O(n) in the name length - the pattern is compiled to
# a regex and cached, so the wildcard used does not change the cost
# * - matches zero or more characters
print(fnmatch.fnmatch('file.txt', 'f*le.txt'))      # True

# ? - matches exactly one character
print(fnmatch.fnmatch('file.txt', 'fil?.txt'))      # True

# [seq] - matches any character in sequence
print(fnmatch.fnmatch('file1.txt', 'file[0-9].txt')) # True

# [!seq] - matches any character not in sequence
print(fnmatch.fnmatch('fileA.txt', 'file[!0-9].txt')) # True
```

## Filtering Lists

### Filter Filenames

```python
import fnmatch

# Filter list of filenames - O(k*n)
filenames = ['test.py', 'data.csv', 'script.py', 'config.json', 'readme.txt']

# Find all Python files - O(k) items
py_files = fnmatch.filter(filenames, '*.py')
print(py_files)  # ['test.py', 'script.py']

# Find files starting with 'test' - O(k)
test_files = fnmatch.filter(filenames, 'test*')
print(test_files)  # ['test.py']

# Find config files - O(k)
configs = fnmatch.filter(filenames, 'config*')
print(configs)  # ['config.json']
```

### Case-Sensitive vs Insensitive

```python
import fnmatch
import fnmatch

# Case-sensitive (default) - O(n)
print(fnmatch.fnmatch('Test.TXT', '*.txt'))      # False
print(fnmatch.fnmatch('test.txt', '*.txt'))      # True

# Case-insensitive version - O(n)
print(fnmatch.fnmatchcase('Test.TXT', '*.txt'))  # False (always case-sensitive)

# Manual case-insensitive - O(n)
filename = 'Test.TXT'
pattern = '*.txt'
result = fnmatch.fnmatch(filename.lower(), pattern.lower())
print(result)  # True
```

## Advanced Usage

### Translate to Regex

```python
import fnmatch
import re

# Convert fnmatch pattern to regex - O(n)
pattern = fnmatch.translate('test*.py')
print(pattern)  # Returns regex pattern

# Can use with re module - O(n)
regex = re.compile(pattern)
print(regex.match('test_script.py'))  # Match object
print(regex.match('test.py'))         # Match object
print(regex.match('other.py'))        # None
```

## Use Cases

### File Filter Class

```python
import fnmatch
import os

class FileFilter:
    """Filter files by pattern"""
    
    def __init__(self, *patterns):
        self.patterns = patterns
    
    # Match filename - O(n) per pattern
    def matches(self, filename):
        for pattern in self.patterns:  # O(m) patterns
            if fnmatch.fnmatch(filename, pattern):
                return True
        return False
    
    # Filter list - O(k*m*n)
    def filter_files(self, filenames):
        result = []
        for filename in filenames:  # O(k) files
            if self.matches(filename):
                result.append(filename)
        return result

# Usage
filter = FileFilter('*.py', 'test_*.txt', 'data.*')
files = ['script.py', 'test_data.txt', 'readme.md', 'data.csv']
matching = filter.filter_files(files)
print(matching)  # ['script.py', 'test_data.txt', 'data.csv']
```

### Glob Alternative

```python
import fnmatch
import os

def glob_alternative(directory, pattern):
    """Simulate glob using fnmatch - O(n)"""
    
    result = []
    # List all files - O(n)
    for filename in os.listdir(directory):
        # Check pattern - O(m) per file
        if fnmatch.fnmatch(filename, pattern):
            result.append(os.path.join(directory, filename))
    
    return result

# Usage
py_files = glob_alternative('.', '*.py')
print(py_files)
```

### Configuration Matcher

```python
import fnmatch

class ConfigMatcher:
    """Match configuration entries"""
    
    def __init__(self):
        self.config = {
            'app.name': 'MyApp',
            'app.version': '1.0',
            'db.host': 'localhost',
            'db.port': '5432'
        }
    
    # Find config by pattern - O(k*n)
    def find_configs(self, pattern):
        result = {}
        for key, value in self.config.items():  # O(k) items
            if fnmatch.fnmatch(key, pattern):   # O(n) per match
                result[key] = value
        return result

# Usage
config = ConfigMatcher()
app_configs = config.find_configs('app.*')
print(app_configs)  # {'app.name': 'MyApp', 'app.version': '1.0'}

db_configs = config.find_configs('db.*')
print(db_configs)  # {'db.host': 'localhost', 'db.port': '5432'}
```

### Log Entry Filtering

```python
import fnmatch

def filter_logs(log_entries, pattern):
    """Filter log entries by pattern - O(k*n)"""
    
    matching = []
    for entry in log_entries:  # O(k) entries
        # Match against pattern - O(n)
        if fnmatch.fnmatch(entry, pattern):
            matching.append(entry)
    
    return matching

# Usage
logs = [
    'ERROR: Database connection failed',
    'INFO: Server started',
    'ERROR: Authentication failed',
    'DEBUG: Cache hit',
    'WARNING: Low memory'
]

error_logs = filter_logs(logs, 'ERROR*')
print(error_logs)
```

## Performance Characteristics

### Time Complexity
- **fnmatch()**: O(n) where n = string length
- **fnmatchcase()**: O(n) case-sensitive matching
- **filter()**: O(k*n) where k = list size, n = string length
- **translate()**: O(n) to convert to regex

### Space Complexity
- **fnmatch()**: O(1) - no extra space
- **filter()**: O(k) for result list
- **translate()**: O(n) for regex string

### Benchmark

```python
import fnmatch
import time

# Create test data
filenames = [f'file{i:04d}.txt' for i in range(1000)]

# Test fnmatch filter - O(k*n)
start = time.time()
for _ in range(100):
    result = fnmatch.filter(filenames, 'file00*.txt')
fnmatch_time = time.time() - start

# Test list comprehension - O(k*n)
start = time.time()
for _ in range(100):
    result = [f for f in filenames if fnmatch.fnmatch(f, 'file00*.txt')]
comp_time = time.time() - start

print(f"fnmatch.filter: {fnmatch_time:.4f}s")
print(f"List comprehension: {comp_time:.4f}s")
```

## When to Use fnmatch

### Good For
- Simple filename pattern matching
- Filtering lists of strings
- No need for complex regex
- Case-sensitive filename matching
- Shell-style pattern matching

### Better Alternatives

```python
# For more complex patterns, use regex
import re
result = re.match(r'test[0-9]{3}\.txt', filename)  # O(n), same as fnmatch

# For filesystem globbing, use glob
import glob
files = glob.glob('*.txt')  # O(n) in directory entries - it also does I/O,
                            # which fnmatch does not

# For case-insensitive matching on Windows
# Use glob with pathlib
from pathlib import Path
files = list(Path('.').glob('*.PY'))

# For complex filtering, use filter() or comprehensions
files = [f for f in filenames if 'test' in f and f.endswith('.py')]
```

## Pattern Comparison

### fnmatch vs glob vs re

```python
import fnmatch
import glob
import re

filename = 'test_data_123.txt'

# fnmatch - simple shell patterns - O(n)
result = fnmatch.fnmatch(filename, 'test_*.txt')

# glob - filesystem patterns - O(n)
# glob is for filesystem, not just strings

# re - full regex - O(n)
result = re.match(r'test_.*\.txt', filename)

# fnmatch best for simple cases
```

## Best Practices

### Do's
- Use fnmatch for simple filename patterns
- Use filter() for batch matching
- Use fnmatchcase() when needed
- Translate to regex for complex patterns

### Avoid's
- Don't use for complex regex needs
- Don't use for filesystem globbing (use glob)
- Don't assume case-insensitive on all systems
- Don't create regex for simple patterns

## Common Patterns

### Common Filter Patterns

```python
import fnmatch

# Each filter() is O(k*n) - k names, n = name length
# Text files
text_files = fnmatch.filter(files, '*.txt')

# Python or JavaScript - two passes over the list, so 2 * O(k*n)
code_files = fnmatch.filter(files, '*.py') + fnmatch.filter(files, '*.js')

# Test files
test_files = fnmatch.filter(files, 'test_*.py') + fnmatch.filter(files, '*_test.py')

# Backup files (to exclude)
backups = fnmatch.filter(files, '*.bak') + fnmatch.filter(files, '*~')

# Configuration files
configs = fnmatch.filter(files, '*.conf') + fnmatch.filter(files, '*.ini')
# For many patterns, one pass with a compiled alternation beats k passes
```

## Related Documentation

- [Glob Module](glob.md)
- [RE Module](re.md)
- [OS Module](os.md)
- [Pathlib Module](pathlib.md)
