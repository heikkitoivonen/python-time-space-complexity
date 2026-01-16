# filecmp Module Complexity

The `filecmp` module provides tools for comparing files and directories, with shallow and deep comparison modes for detecting differences in content and attributes.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cmp()` shallow | O(1) | O(1) | Compare file metadata only |
| `cmp()` deep | O(n) | O(1) | n = file size, read all content |
| `cmpfiles()` | O(k*n) | O(1) | k = files, n = avg file size |
| `dircmp()` init | O(1) | O(1) | Create directory comparator |
| `dircmp.report()` | O(k*n) | O(k) | k = files, n = avg size |
| `dircmp.report_full_closure()` | O(k*d*n) | O(k*d) | Recursive, d = depth |

## File Comparison

### Simple File Comparison

```python
import filecmp

# Shallow comparison (metadata only) - O(1)
# Compares size and modification time
result = filecmp.cmp('file1.txt', 'file2.txt', shallow=True)
print(f"Files match (shallow): {result}")

# Deep comparison (full content) - O(n)
# Reads entire files for byte-by-byte comparison
result = filecmp.cmp('file1.txt', 'file2.txt', shallow=False)
print(f"Files match (deep): {result}")
```

### Shallow vs Deep

```python
import filecmp
import shutil
import time

# Create test files
with open('original.txt', 'w') as f:
    f.write('Test content')

# Copy file
shutil.copy2('original.txt', 'copy.txt')

# Shallow comparison (checks size and mtime) - O(1)
print(filecmp.cmp('original.txt', 'copy.txt', shallow=True))   # True

# Modify copy
time.sleep(1)
with open('copy.txt', 'w') as f:
    f.write('Different content')

# Shallow still matches (same size, ignores time)
print(filecmp.cmp('original.txt', 'copy.txt', shallow=True))   # True

# Deep detects difference - O(n)
print(filecmp.cmp('original.txt', 'copy.txt', shallow=False))  # False
```

## Directory Comparison

### Compare Directories

```python
import filecmp

# Create comparator - O(1)
dcmp = filecmp.dircmp('dir1', 'dir2')

# Get comparison results
print(f"Same files: {dcmp.same_files}")       # Files with same content
print(f"Different files: {dcmp.diff_files}")  # Files with different content
print(f"Left only: {dcmp.left_only}")         # Files only in dir1
print(f"Right only: {dcmp.right_only}")       # Files only in dir2
print(f"Subdirs: {dcmp.subdirs}")             # Common subdirectories

# Print report - O(k*n)
dcmp.report()
```

### Detailed Report

```python
import filecmp

# Compare directories - O(1) init
dcmp = filecmp.dircmp('dir1', 'dir2')

# Simple report - O(k*n)
print("=== Directory Comparison Report ===")
dcmp.report()

# More detailed report - O(k*d*n)
print("\n=== Full Closure Report ===")
dcmp.report_full_closure()

# Report shows:
# - Files that are identical
# - Files that differ
# - Files only in left directory
# - Files only in right directory
```

### Recursive Comparison

```python
import filecmp

class RecursiveComparator:
    """Recursively compare directory trees"""
    
    def __init__(self, dir1, dir2):
        self.dir1 = dir1
        self.dir2 = dir2
    
    # Recursively compare - O(k*d*n)
    def compare_trees(self):
        dcmp = filecmp.dircmp(self.dir1, self.dir2)
        return self._gather_all_results(dcmp)
    
    # Helper to gather results recursively
    def _gather_all_results(self, dcmp):
        results = {
            'same': dcmp.same_files,
            'different': dcmp.diff_files,
            'left_only': dcmp.left_only,
            'right_only': dcmp.right_only,
            'subdirs': {}
        }
        
        # Recurse into subdirectories - O(d) depth
        for subdir in dcmp.subdirs.values():
            # Each subdir comparison - O(k*n)
            results['subdirs'][subdir.get_rel()] = self._gather_all_results(subdir)
        
        return results

# Usage
comp = RecursiveComparator('backup1', 'backup2')
results = comp.compare_trees()
```

## Use Cases

### File Synchronization

```python
import filecmp
import shutil
import os

class FileSync:
    """Synchronize files between two directories"""
    
    def __init__(self, source, dest):
        self.source = source
        self.dest = dest
    
    # Sync files - O(k*n)
    def sync(self):
        dcmp = filecmp.dircmp(self.source, self.dest)
        
        # Copy files that are different - O(diff count)
        for file in dcmp.diff_files:
            src_path = os.path.join(self.source, file)
            dst_path = os.path.join(self.dest, file)
            print(f"Updating {dst_path}")
            shutil.copy2(src_path, dst_path)
        
        # Copy files only in source - O(left_only count)
        for file in dcmp.left_only:
            src_path = os.path.join(self.source, file)
            dst_path = os.path.join(self.dest, file)
            print(f"Copying {dst_path}")
            shutil.copy2(src_path, dst_path)
        
        # Remove files only in dest - O(right_only count)
        for file in dcmp.right_only:
            dst_path = os.path.join(self.dest, file)
            print(f"Removing {dst_path}")
            os.remove(dst_path)
        
        # Recurse to subdirectories - O(d) depth
        for subdir in dcmp.subdirs:
            sub_source = os.path.join(self.source, subdir)
            sub_dest = os.path.join(self.dest, subdir)
            
            sub_sync = FileSync(sub_source, sub_dest)
            sub_sync.sync()

# Usage
sync = FileSync('backup_source', 'backup_dest')
sync.sync()
```

### Backup Verification

```python
import filecmp
import os

class BackupVerifier:
    """Verify backup integrity"""
    
    def __init__(self, original, backup):
        self.original = original
        self.backup = backup
    
    # Verify backup - O(k*d*n)
    def verify(self):
        dcmp = filecmp.dircmp(self.original, self.backup)
        
        issues = {
            'missing': dcmp.right_only,      # In backup but not original
            'outdated': dcmp.diff_files,     # Different content
            'extra': dcmp.left_only          # In original but not backup
        }
        
        return issues
    
    # Get verification report
    def report(self):
        issues = self.verify()
        
        if not any(issues.values()):
            print("✓ Backup is complete and up-to-date")
        else:
            if issues['missing']:
                print(f"⚠ {len(issues['missing'])} unexpected files in backup")
            if issues['outdated']:
                print(f"⚠ {len(issues['outdated'])} files are outdated")
            if issues['extra']:
                print(f"✗ {len(issues['extra'])} files missing from backup")
        
        return issues

# Usage
verifier = BackupVerifier('/home/user/important', '/backup/important')
issues = verifier.report()
```

### Finding Duplicate Files

```python
import filecmp
import os

class DuplicateFinder:
    """Find duplicate files in directories"""
    
    def __init__(self, *directories):
        self.directories = directories
    
    # Find duplicates - O(k²*n) in worst case
    def find_duplicates(self):
        duplicates = []
        
        # Get all files from first directory
        files1 = []
        for root, dirs, files in os.walk(self.directories[0]):
            for file in files:
                files1.append(os.path.join(root, file))
        
        # Compare with other directories - O(k²*n)
        for dir in self.directories[1:]:
            for root, dirs, files in os.walk(dir):
                for file in files:
                    path2 = os.path.join(root, file)
                    
                    for path1 in files1:
                        # Deep comparison - O(n)
                        if filecmp.cmp(path1, path2, shallow=False):
                            duplicates.append((path1, path2))
        
        return duplicates

# Usage
finder = DuplicateFinder('~/Documents', '~/Downloads')
dupes = finder.find_duplicates()
for path1, path2 in dupes:
    print(f"Duplicate: {path1} ≈ {path2}")
```

### Directory Diff Report

```python
import filecmp
import os

def generate_diff_report(dir1, dir2, output_file=None):
    """Generate detailed diff report - O(k*d*n)"""
    
    dcmp = filecmp.dircmp(dir1, dir2)
    
    lines = []
    lines.append(f"Comparing: {dir1}")
    lines.append(f"      with: {dir2}\n")
    
    # Recursive report function
    def report_helper(dcmp, indent=''):
        if dcmp.same_files:
            lines.append(f"{indent}✓ Identical files ({len(dcmp.same_files)}):")
            for file in dcmp.same_files[:5]:
                lines.append(f"{indent}  - {file}")
            if len(dcmp.same_files) > 5:
                lines.append(f"{indent}  ... and {len(dcmp.same_files) - 5} more")
        
        if dcmp.diff_files:
            lines.append(f"{indent}≠ Different files ({len(dcmp.diff_files)}):")
            for file in dcmp.diff_files:
                lines.append(f"{indent}  - {file}")
        
        if dcmp.left_only:
            lines.append(f"{indent}← Left only ({len(dcmp.left_only)}):")
            for file in dcmp.left_only:
                lines.append(f"{indent}  - {file}")
        
        if dcmp.right_only:
            lines.append(f"{indent}→ Right only ({len(dcmp.right_only)}):")
            for file in dcmp.right_only:
                lines.append(f"{indent}  - {file}")
        
        # Recurse to subdirs
        for subdir in dcmp.subdirs:
            lines.append(f"\n{indent}Subdir: {subdir}/")
            report_helper(dcmp.subdirs[subdir], indent + '  ')
    
    report_helper(dcmp)
    
    report = '\n'.join(lines)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report)
    
    return report

# Usage
report = generate_diff_report('dir1', 'dir2', 'diff_report.txt')
print(report)
```

## Performance Characteristics

### Time Complexity
- **cmp() shallow**: O(1) - metadata only
- **cmp() deep**: O(n) - read entire files
- **dircmp**: O(k*n) where k = files, n = avg size
- **report_full_closure**: O(k*d*n) where d = tree depth

### Space Complexity
- **dircmp**: O(k*d) for storing file lists
- **Recursive comparison**: O(d) call stack depth

### Optimization Strategies

```python
import filecmp

# Prefer shallow comparison when possible
result = filecmp.cmp('file1', 'file2', shallow=True)  # Fast

# For directory comparison, use shallow first
dcmp = filecmp.dircmp('dir1', 'dir2')
# Files already compared with shallow comparison

# Only do deep compare on suspected differences
for diff_file in dcmp.diff_files:
    path1 = os.path.join(dcmp.left, diff_file)
    path2 = os.path.join(dcmp.right, diff_file)
    
    # Verify with deep comparison
    confirmed = filecmp.cmp(path1, path2, shallow=False)
```

## Common Issues

### Symlinks and Special Files

```python
import filecmp
import os

# dircmp follows symlinks by default
# May cause infinite recursion if circular

# Use shallow comparison for large files
dcmp = filecmp.dircmp('dir1', 'dir2')
# dircmp automatically uses shallow comparison

# For custom handling:
def safe_compare(dir1, dir2):
    dcmp = filecmp.dircmp(dir1, dir2)
    
    # Filter out symlinks if needed
    same = [f for f in dcmp.same_files 
            if not os.path.islink(os.path.join(dir1, f))]
    
    return same
```

## Best Practices

### Do's
- Use shallow comparison by default (fast)
- Use deep comparison when needed for verification
- Cache dcmp objects for multiple operations
- Handle symlinks carefully

### Avoid's
- Don't use deep comparison for large files unnecessarily
- Don't ignore dircmp.subdirs for recursive comparison
- Don't assume shallow comparison for all use cases
- Don't follow symlinks blindly in recursive operations

## Alternatives

```python
# For more advanced comparison:
# - Use external tools: diff, rsync
# - Use third-party libraries: deepdiff

# For efficient large file comparison:
import hashlib

def file_hash(path):
    """Hash file for quick comparison"""
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

# For structured data:
import json
# Compare JSON files semantically
```

## Related Documentation

- [Difflib Module](difflib.md)
- [Glob Module](glob.md)
- [OS Module](os.md)
- [Pathlib Module](pathlib.md)
