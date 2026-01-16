# difflib Module Complexity

The `difflib` module provides tools for comparing sequences (lists, strings) and generating human-readable diffs, useful for text comparison, patching, and change detection.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SequenceMatcher()` init | O(1) | O(n) | Create matcher, n = combined length |
| `get_matching_blocks()` | O(n+m) | O(n+m) | Find longest matching blocks |
| `get_opcodes()` | O(n+m) | O(n+m) | Get edit operations |
| `ratio()` | O(n+m) | O(1) | Compute similarity ratio |
| `unified_diff()` | O(n+m) | O(n+m) | Generate unified diff |
| `context_diff()` | O(n+m) | O(n+m) | Generate context diff |
| `ndiff()` | O(n+m) | O(n+m) | Generate detailed diff |

## Sequence Matching

### Basic Comparison

```python
from difflib import SequenceMatcher

# Create matcher - O(1)
a = "kitten"
b = "sitting"

matcher = SequenceMatcher(None, a, b)

# Get similarity ratio - O(n+m)
ratio = matcher.ratio()
print(f"Similarity: {ratio:.2%}")  # 57.14%

# Get matching blocks - O(n+m)
blocks = matcher.get_matching_blocks()
for block in blocks:
    print(f"Match: a[{block.a}:{block.a+block.size}] = b[{block.b}:{block.b+block.size}]")
    # Match: a[0:1] = b[0:1] ('k'/'s')  - wait, this won't match
    # Actually shows longest common substrings
```

### List Comparison

```python
from difflib import SequenceMatcher

# Compare lists - O(1) init
list1 = [1, 2, 3, 4, 5]
list2 = [1, 2, 4, 5, 6]

matcher = SequenceMatcher(None, list1, list2)

# Similarity ratio - O(n+m)
ratio = matcher.ratio()
print(f"Match: {ratio:.2%}")  # 70%

# Find matching blocks - O(n+m)
matching = matcher.get_matching_blocks()
for m in matching:
    print(f"Block: {list1[m.a:m.a+m.size]} matches {list2[m.b:m.b+m.size]}")
```

## Edit Operations

### Get Opcodes

```python
from difflib import SequenceMatcher

# Compare strings - O(1) init
s1 = "eating"
s2 = "running"

matcher = SequenceMatcher(None, s1, s2)

# Get edit operations - O(n+m)
opcodes = matcher.get_opcodes()

for op, i1, i2, j1, j2 in opcodes:
    if op == 'equal':
        print(f"Equal: {s1[i1:i2]} == {s2[j1:j2]}")
    elif op == 'replace':
        print(f"Replace: {s1[i1:i2]} -> {s2[j1:j2]}")
    elif op == 'insert':
        print(f"Insert: {s2[j1:j2]} at position {i1}")
    elif op == 'delete':
        print(f"Delete: {s1[i1:i2]}")

# Output describes all changes
```

## String Diffs

### Unified Diff Format

```python
from difflib import unified_diff

# Compare lists of lines - O(n+m)
text1 = "The quick brown fox\njumps over the lazy dog\n".splitlines(keepends=True)
text2 = "The fast brown fox\njumps over the lazy cat\n".splitlines(keepends=True)

# Generate unified diff - O(n+m)
diff = unified_diff(text1, text2, fromfile='original', tofile='modified')

# Print diff
print(''.join(diff))

# Output:
# --- original
# +++ modified
# @@ -1,2 +1,2 @@
#  The quick brown fox
# -jumps over the lazy dog
# +jumps over the lazy cat
```

### Context Diff Format

```python
from difflib import context_diff

text1 = ["line1\n", "line2\n", "line3\n", "line4\n"]
text2 = ["line1\n", "modified2\n", "line3\n", "line4\n"]

# Generate context diff - O(n+m)
diff = context_diff(text1, text2, fromfile='old', tofile='new', n=1)

print(''.join(diff))

# Output shows 1 line of context around changes
```

### Ndiff Format

```python
from difflib import ndiff

# Detailed line-by-line diff - O(n+m)
text1 = ["apple\n", "banana\n", "cherry\n"]
text2 = ["apple\n", "blueberry\n", "cherry\n"]

diff = ndiff(text1, text2)

for line in diff:
    if line[0] == ' ':
        print(f"  {line[2:]}", end='')  # Unchanged
    elif line[0] == '+':
        print(f"+ {line[2:]}", end='')  # Added
    elif line[0] == '-':
        print(f"- {line[2:]}", end='')  # Removed

# Marks: '  ' for equal, '- ' for removed, '+ ' for added, '? ' for hints
```

## Close Matches

### Find Similar Items

```python
from difflib import get_close_matches

# Find close matches - O(n*m) where n = options, m = search string length
options = ["kitten", "sitting", "kitchen", "mittens", "bitten"]
search = "kitten"

# Get similar strings - O(n*m)
matches = get_close_matches(search, options, n=3, cutoff=0.6)
print(matches)  # ['kitten', 'kitchen', 'mittens']

# With different cutoff - O(n*m)
matches = get_close_matches("kiten", options, n=2, cutoff=0.8)
print(matches)  # ['kitten', 'kitchen']
```

## Advanced Patterns

### Diff Statistics

```python
from difflib import SequenceMatcher

text1 = "The quick brown fox jumps over the lazy dog"
text2 = "The fast brown fox leaps over the lazy cat"

matcher = SequenceMatcher(None, text1, text2)

# Get matching blocks - O(n+m)
blocks = matcher.get_matching_blocks()
total_matches = sum(b.size for b in blocks)

# Calculate stats - O(1)
ratio = matcher.ratio()
print(f"Length: {len(text1)} vs {len(text2)}")
print(f"Matching chars: {total_matches}")
print(f"Similarity: {ratio:.2%}")
```

### Three-way Merge

```python
from difflib import Differ

# Three-way comparison helper
original = "The quick brown fox".split()
current = "The fast brown fox".split()
other = "The quick dark fox".split()

differ = Differ()

# Show differences - O(n+m)
diff_current = list(differ.compare(original, current))
diff_other = list(differ.compare(original, other))

print("Current changes:")
for line in diff_current:
    print(line)

print("\nOther changes:")
for line in diff_other:
    print(line)

# Manual merge needed for conflicts
```

### HTML Report Generation

```python
from difflib import HtmlDiff

# Generate HTML diff - O(n+m)
text1 = ["line 1\n", "line 2\n", "line 3\n"]
text2 = ["line 1\n", "modified line 2\n", "line 3\n"]

h = HtmlDiff()
html = h.make_file(text1, text2, fromfile='old.txt', tofile='new.txt')

# html is a complete HTML document
with open('diff.html', 'w') as f:
    f.write(html)
```

## Use Cases

### File Comparison

```python
from difflib import unified_diff

def compare_files(file1, file2):
    """Compare two text files and show unified diff - O(n+m)"""
    
    with open(file1, 'r') as f:
        lines1 = f.readlines()
    
    with open(file2, 'r') as f:
        lines2 = f.readlines()
    
    # Generate diff - O(n+m)
    diff = unified_diff(lines1, lines2, 
                       fromfile=file1, tofile=file2)
    
    return ''.join(diff)

# Usage
result = compare_files('original.txt', 'modified.txt')
print(result)
```

### Spell Checker

```python
from difflib import get_close_matches

def spell_check(word, dictionary):
    """Find spelling suggestions - O(n*m)"""
    
    # Find close matches - O(n*m) where n = dict size
    suggestions = get_close_matches(word, dictionary, n=3, cutoff=0.6)
    
    if suggestions:
        return f"Did you mean: {', '.join(suggestions)}?"
    return "No suggestions found"

# Usage
dictionary = ['apple', 'application', 'apply', 'appreciate']
print(spell_check('aple', dictionary))
```

### Code Review Helper

```python
from difflib import SequenceMatcher, unified_diff

def analyze_changes(old_code, new_code):
    """Analyze code changes - O(n+m)"""
    
    # Quick similarity check - O(n+m)
    matcher = SequenceMatcher(None, old_code, new_code)
    similarity = matcher.ratio()
    
    print(f"Code similarity: {similarity:.1%}")
    
    # Show detailed changes - O(n+m)
    old_lines = old_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)
    
    diff = unified_diff(old_lines, new_lines)
    for line in diff:
        print(line, end='')

# Usage
old_code = "def add(a, b):\n    return a + b"
new_code = "def add(a, b):\n    \"\"\"Add two numbers\"\"\"\n    return a + b"
analyze_changes(old_code, new_code)
```

## Performance Characteristics

### Time Complexity
- **SequenceMatcher**: O(n+m) preprocessing, O(n*m) in worst case for matching
- **ratio()**: O(n+m) using cached matching blocks
- **unified_diff/context_diff/ndiff**: O(n+m) for comparison, O(n+m) for output
- **get_close_matches**: O(n*m) where n = choices, m = pattern length

### Space Complexity
- **SequenceMatcher**: O(n+m) to store matching blocks
- **Diffs**: O(n+m) for output generation

### Algorithm Notes

```python
from difflib import SequenceMatcher

# The algorithm is optimized but not optimal
# Best case: O(min(n,m)) for identical sequences
# Worst case: O(n*m) for completely different sequences

# Large file comparison can be slow
large_file1 = "x" * 1000000
large_file2 = "y" * 1000000

# This will take time proportional to size
matcher = SequenceMatcher(None, large_file1, large_file2)
ratio = matcher.ratio()  # Relatively quick
```

## Filtering Junk Elements

### Ignore Whitespace

```python
from difflib import SequenceMatcher

def is_whitespace(x):
    """Filter function to ignore whitespace"""
    return x.isspace()

text1 = "hello  world"
text2 = "hello world"

# Without filtering - shows difference
matcher1 = SequenceMatcher(None, text1, text2)
print(f"With spaces: {matcher1.ratio():.2%}")

# With filtering - ignores spaces
matcher2 = SequenceMatcher(is_whitespace, text1, text2)
print(f"Without spaces: {matcher2.ratio():.2%}")
```

## Best Practices

### Do's
- Use SequenceMatcher for sequence comparison
- Use get_close_matches for spell checking
- Use unified_diff for human-readable output
- Consider cutoff value for fuzzy matching
- Cache SequenceMatcher for repeated comparisons

### Avoid's
- Don't use for very large files without optimization
- Don't ignore important matching blocks
- Don't expect perfect spell checking with low cutoff
- Don't use for exact matching (use == instead)

## Limitations

- Not optimized for very large files
- Cannot detect moved blocks (only insertions/deletions)
- Similarity metric is heuristic-based
- No context-aware matching

## Alternatives

```python
# For version control quality diffs:
# - Use git diff, mercurial
# - Use external tools like 'diff', 'patch'

# For fuzzy matching:
# - Use fuzzywuzzy library (pip install fuzzywuzzy)
# - Use rapidfuzz for faster matching

# For language-aware diffs:
# - Use Pygments for syntax highlighting
# - Use specialized diff tools for code

# For ML-based similarity:
# - Use scikit-learn for text similarity
# - Use sentence-transformers for semantic similarity
```

## Related Documentation

- [re Module](re.md)
- [String Operations](../builtins/str.md)
- [Filecmp Module](filecmp.md)
