# glob Module Complexity

The `glob` module provides Unix shell-style pathname expansion using wildcard patterns to find files matching specific criteria.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `glob()` function | O(n) | O(n) | n = matching files |
| `iglob()` function | O(1) init | O(1) per item | Iterator, lazy evaluation |
| Pattern matching | O(n) | O(1) | n = files in directory |
| Recursive search `**` | O(d) | O(1) per file | d = depth of directory tree |

## Basic Globbing

### Simple Patterns

```python
import glob

# Find all Python files - O(n)
py_files = glob.glob('*.py')
print(py_files)  # ['script.py', 'test.py', ...]

# Find all files in directory - O(n)
all_files = glob.glob('*')
print(all_files)  # All files in current directory

# Find specific pattern - O(n)
data_files = glob.glob('data/*.csv')
print(data_files)  # ['data/file1.csv', 'data/file2.csv', ...]
```

### Pattern Wildcards

```python
import glob

# * - matches any sequence of characters
# [abc] - matches any character in brackets
# [a-z] - matches character range
# ? - matches single character
# ** - matches zero or more directories (recursive)

# Examples
print(glob.glob('test*.py'))      # test_*.py files
print(glob.glob('file?.txt'))     # file1.txt, fileA.txt, etc.
print(glob.glob('[a-c]*.txt'))    # a*, b*, or c* txt files
print(glob.glob('**/*.py'))       # All .py files recursively
```

## Iterator vs List

### Using iglob for Large Directories

```python
import glob

# glob() returns list - O(n) space, all at once
files = glob.glob('*.py')  # O(n) - loads all results
for file in files:
    print(file)

# iglob() returns iterator - O(1) space, lazy evaluation
files = glob.iglob('*.py')  # O(1) - returns iterator
for file in files:
    print(file)  # Each iteration finds one match
```

### Memory Efficiency

```python
import glob
import sys

# Large directory with many matches
# glob() - loads all in memory
all_files = glob.glob('**/*.txt', recursive=True)
print(f"Memory used by glob: {sys.getsizeof(all_files)} bytes")

# iglob() - loads one at a time
file_iter = glob.iglob('**/*.txt', recursive=True)
print(f"Memory used by iglob: {sys.getsizeof(file_iter)} bytes")

# For large results, iglob is better
for file in file_iter:
    process(file)  # Process one at a time
```

## Recursive Globbing

### Find Files in Subdirectories

```python
import glob

# Recursive search with ** - O(d) where d = tree depth
# Must use recursive=True parameter

# Find all Python files recursively
py_files = glob.glob('**/*.py', recursive=True)
print(py_files)

# Find files at specific depth
# All .txt files in any subdirectory
txt_files = glob.glob('*/*.txt')  # One level deep

# All .txt files recursively
txt_files = glob.glob('**/*.txt', recursive=True)

# Find in nested structure
nested = glob.glob('src/**/test_*.py', recursive=True)
```

## Common Patterns

### Find Configuration Files

```python
import glob

# Find all config files - O(n)
configs = glob.glob('**/*.conf', recursive=True)
configs.extend(glob.glob('**/*.ini', recursive=True))
configs.extend(glob.glob('**/*.yaml', recursive=True))

print(f"Found {len(configs)} config files")
```

### Find Files by Extension

```python
import glob

class FileCollector:
    """Collect files by extension"""
    
    def __init__(self, root_dir='.'):
        self.root = root_dir
    
    # Find by extension - O(n)
    def find_by_extension(self, ext):
        pattern = f'{self.root}/**/*.{ext}'
        return glob.glob(pattern, recursive=True)
    
    # Find multiple extensions - O(n*m)
    def find_by_extensions(self, *exts):
        files = []
        for ext in exts:  # O(m) extensions
            pattern = f'{self.root}/**/*.{ext}'
            files.extend(glob.glob(pattern, recursive=True))  # O(n)
        return files
    
    # Find in specific directory - O(n)
    def find_in_dir(self, subdir, ext):
        pattern = f'{self.root}/{subdir}/*.{ext}'
        return glob.glob(pattern)

# Usage
collector = FileCollector('.')
py_files = collector.find_by_extension('py')
all_code = collector.find_by_extensions('py', 'js', 'ts')
```

### Batch File Processing

```python
import glob
import os

def process_images(directory):
    """Process all images in directory - O(n)"""
    
    image_exts = ['*.jpg', '*.jpeg', '*.png', '*.gif']
    patterns = [f'{directory}/**/{ext}' for ext in image_exts]
    
    total_size = 0
    count = 0
    
    # Process each pattern - O(n*m)
    for pattern in patterns:
        for image_path in glob.iglob(pattern, recursive=True):
            # Process each image
            size = os.path.getsize(image_path)
            total_size += size
            count += 1
            
            print(f"Processing: {image_path} ({size} bytes)")
    
    return count, total_size

# Usage
count, total = process_images('photos')
print(f"Processed {count} images, {total} bytes")
```

### Compare with os.listdir

```python
import glob
import os

# os.listdir() - non-recursive, simple
files = os.listdir('.')  # O(n) - one level only
print(files)

# glob.glob() - pattern matching, can recurse
files = glob.glob('**/*.txt', recursive=True)  # O(n) - all levels
print(files)

# glob is better for searching, os.listdir better for listing
```

## Pattern Escaping

### Handle Special Characters

```python
import glob

# Filenames with special characters need escaping
# * ? [ ] { } are glob metacharacters

# Files that contain brackets
# File: test[1].txt

# Escape with [brackets]
pattern = glob.escape('test[1].txt')  # Returns 'test[[]1].txt'
result = glob.glob(pattern)

# Escape before using in patterns
filename = "data[backup].csv"
pattern = glob.escape(filename)
result = glob.glob(pattern)
```

## Common Use Cases

### Find Recent Files

```python
import glob
import os
import time

def find_recent_files(directory, minutes=60):
    """Find files modified in last N minutes - O(n)"""
    
    cutoff_time = time.time() - (minutes * 60)
    recent = []
    
    # Get all files recursively - O(n)
    for file_path in glob.iglob(f'{directory}/**/*', recursive=True):
        if os.path.isfile(file_path):
            mtime = os.path.getmtime(file_path)
            if mtime > cutoff_time:
                recent.append((file_path, mtime))
    
    return sorted(recent, key=lambda x: x[1], reverse=True)

# Usage
recent = find_recent_files('.', minutes=30)
for path, mtime in recent:
    print(f"{path}: {time.ctime(mtime)}")
```

### Build System File Finding

```python
import glob

class BuildSystem:
    """Find source files for building"""
    
    def __init__(self, project_root):
        self.root = project_root
    
    # Find source files
    def find_sources(self, language):
        """Find source files - O(n)"""
        
        patterns = {
            'python': '**/*.py',
            'javascript': '**/*.js',
            'cpp': ['**/*.cpp', '**/*.h'],
            'java': '**/*.java'
        }
        
        if language not in patterns:
            return []
        
        pattern_list = patterns[language]
        if isinstance(pattern_list, str):
            pattern_list = [pattern_list]
        
        files = []
        for pattern in pattern_list:
            full_pattern = f'{self.root}/{pattern}'
            files.extend(glob.glob(full_pattern, recursive=True))
        
        return files
    
    # Find test files
    def find_tests(self):
        """Find test files - O(n)"""
        patterns = [
            f'{self.root}/**/test_*.py',
            f'{self.root}/**/*_test.py',
            f'{self.root}/**/tests.py'
        ]
        
        tests = []
        for pattern in patterns:
            tests.extend(glob.glob(pattern, recursive=True))
        
        return list(set(tests))  # Remove duplicates

# Usage
build = BuildSystem('.')
py_sources = build.find_sources('python')
tests = build.find_tests()
```

### Package Discovery

```python
import glob
import os

def find_python_packages(directory):
    """Find all Python packages - O(n)"""
    
    packages = []
    
    # Find __init__.py files - O(n)
    init_files = glob.glob(f'{directory}/**/__init__.py', recursive=True)
    
    for init_file in init_files:
        # Package is directory containing __init__.py
        package_dir = os.path.dirname(init_file)
        # Convert path to module name
        module_name = package_dir.replace(os.sep, '.')
        packages.append(module_name)
    
    return sorted(packages)

# Usage
packages = find_python_packages('src')
print("Found packages:", packages)
```

## Performance Characteristics

### Time Complexity
- **glob()**: O(n) where n = total matching files
- **iglob()**: O(1) initialization + O(k) for first k items
- **Pattern matching**: O(n) to scan all files
- **Recursive search**: O(d) proportional to directory depth

### Space Complexity
- **glob()**: O(n) for result list
- **iglob()**: O(1) memory, iterator-based
- **Pattern processing**: O(1) per match

### Performance Tips

```python
import glob
import time

# Slow: Multiple glob calls
start = time.time()
py_files = glob.glob('*.py')
txt_files = glob.glob('*.txt')
md_files = glob.glob('*.md')
time1 = time.time() - start

# Better: Single glob with pattern
start = time.time()
all_files = glob.glob('[!_]*.[pytm]*')
time2 = time.time() - start

# Fast: Using iglob for processing
start = time.time()
for file in glob.iglob('**/*', recursive=True):
    if file.endswith('.py'):
        process(file)
time3 = time.time() - start

print(f"Multiple: {time1:.4f}s")
print(f"Single: {time2:.4f}s")
print(f"Iterator: {time3:.4f}s")
```

## Limitations

- Cannot check file type before returning
- No built-in size filtering
- No date/time filtering
- Patterns are shell-style, not regex

## Alternatives

```python
# For more control, use pathlib
from pathlib import Path

# glob with pathlib
path = Path('.')
py_files = list(path.glob('**/*.py'))

# For regex patterns, use os.walk + re
import os
import re

for root, dirs, files in os.walk('.'):
    for file in files:
        if re.match(r'test_.*\.py$', file):
            print(os.path.join(root, file))

# For filtering by attributes
from pathlib import Path
import os

py_files = [f for f in Path('.').glob('**/*.py') 
            if f.stat().st_size < 1000]  # < 1KB
```

## Best Practices

### Do's
- Use glob for simple wildcard matching
- Use iglob for large result sets
- Escape filenames with special characters
- Use recursive=True for deep searches
- Cache results if used multiple times

### Avoid's
- Don't use glob for complex filtering
- Don't use glob inside tight loops
- Don't assume pattern will find files quickly
- Don't rely on glob for file existence checking

## Related Documentation

- [Fnmatch Module](fnmatch.md)
- [Pathlib Module](pathlib.md)
- [OS Module](os.md)
- [Filecmp Module](filecmp.md)
