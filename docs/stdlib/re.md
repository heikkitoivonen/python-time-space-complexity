# re Module Complexity

The `re` module provides regular expression matching operations.

## Pattern Compilation and Matching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `re.compile(pattern)` | O(n) | O(n) | n = pattern length |
| `pattern.match(string)` | O(m) typical, O(exp) worst | O(m) | Worst case from backtracking |
| `pattern.fullmatch(string)` | O(m) typical, O(exp) worst | O(m) | Match entire string |
| `pattern.search(string)` | O(m) typical, O(exp) worst | O(m) | Searches full string |
| `pattern.findall(string)` | O(m) typical, O(exp) worst | O(k) | k = total matches |
| `pattern.finditer(string)` | O(m) typical, O(exp) worst | O(1) | Lazy iteration |
| `pattern.sub(repl, string)` | O(m) typical, O(exp) worst | O(m) | Match + build output |
| `pattern.subn(repl, string)` | O(m) typical, O(exp) worst | O(m) | Like sub, returns (newstr, count) |
| `pattern.split(string)` | O(m) typical, O(exp) worst | O(m) | Split by pattern |
| `re.match(pattern, string)` | O(n + m) typical, O(exp) worst | O(m) | Compiles on cache miss; cached up to ~512 |
| `re.search(pattern, string)` | O(n + m) typical, O(exp) worst | O(m) | Compiles on cache miss; cached up to ~512 |
| `re.escape(string)` | O(n) | O(n) | Escape special regex characters |
| `re.purge()` | O(c) | O(1) | Clear compiled pattern cache (c = cache size) |
| `re.error` | - | - | Exception for invalid patterns |

*Note: "O(exp)" denotes exponential time in m from catastrophic backtracking; typical cases are much better.

## Pattern Caching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `re.match(pattern, s)` | O(n + m) | O(n+m) | Compiles on cache miss; cached up to ~512 |
| `compiled = re.compile(p)` | O(n) | O(n) | Explicit compilation |
| `compiled.match(s)` | O(m) typical, O(exp) worst | O(m) | Uses the already-compiled pattern |

CPython caches the last ~512 compiled patterns automatically.

## Common Operations

### Basic Pattern Matching

```python
import re

# Compile pattern once - O(n) where n = pattern length
pattern = re.compile(r'\d+')  # O(n)

# Use compiled pattern - O(m) per match, m = string length
text = "Number: 12345"
match = pattern.search(text)  # O(m)

if match:
    print(match.group())  # O(1)
```

### Finding All Matches

```python
import re

pattern = re.compile(r'\w+')
text = "Hello world from Python"

# Find all - O(m) where m = text length
matches = pattern.findall(text)  # O(m)
# Result: ['Hello', 'world', 'from', 'Python']

# Lazy iteration - O(1) per match
for match in pattern.finditer(text):  # O(1) each
    print(match.group())
```

### Substitution

```python
import re

pattern = re.compile(r'\d+')
text = "Numbers: 10, 20, 30"

# Replace all - O(m)
result = pattern.sub('X', text)  # O(m)
# Result: "Numbers: X, X, X"

# Replace with function - O(m) for matching, O(f) for replacements
def replace_func(match):
    return str(int(match.group()) * 2)

result = pattern.sub(replace_func, text)  # O(m + f)
# Result: "Numbers: 20, 40, 60"
```

### Splitting

```python
import re

pattern = re.compile(r',\s*')
text = "apple, banana, cherry"

# Split by pattern - O(m)
parts = pattern.split(text)  # O(m)
# Result: ['apple', 'banana', 'cherry']
```

## Grouping and Extraction

```python
import re

pattern = re.compile(r'(\d+)-(\w+)')
text = "123-abc"

# Extract groups - O(m)
match = pattern.search(text)  # O(m)
if match:
    full = match.group(0)    # O(1) - full match
    num = match.group(1)     # O(1) - first group
    word = match.group(2)    # O(1) - second group
    
# Get all groups - O(1) per group
groups = match.groups()  # All groups as tuple
```

## Pattern Complexity

### Simple Patterns (Linear Matching)

```python
import re

# Simple patterns - O(m) matching
pattern = re.compile(r'hello')
text = "hello world" * 1000

match = pattern.search(text)  # O(m) - linear scan
```

### Complex Patterns (Potential Exponential)

```python
import re

# Be careful with patterns that can cause backtracking
# This pattern can cause exponential backtracking on non-matches
pattern = re.compile(r'(a+)+b')
text = 'a' * 25  # No 'b' at end

# This can be very slow!
# match = pattern.search(text)  # Potentially exponential!
```

### Catastrophic Backtracking Examples

```python
import re
import time

# AVOID: Nested quantifiers cause backtracking
bad_pattern = re.compile(r'(a+)+$')

# Time how long matching takes
start = time.time()
bad_pattern.search('a' * 20)
end = time.time()
print(f"Time: {end - start}s")  # Can be very slow!

# BETTER: Rewrite pattern to be atomic or non-backtracking
good_pattern = re.compile(r'a+$')
start = time.time()
good_pattern.search('a' * 1000000)
end = time.time()
print(f"Time: {end - start}s")  # Fast!
```

## Performance Tips

### Compile Patterns Once

```python
import re

# Bad: recompiles pattern each time
for line in large_file:
    if re.search(r'\d+', line):  # Recompiles each time!
        process(line)

# Good: compile once - O(n)
pattern = re.compile(r'\d+')  # O(n)
for line in large_file:
    if pattern.search(line):  # O(m) per line
        process(line)
```

### Use Lazy Iteration

```python
import re

pattern = re.compile(r'\w+')
text = "word1 word2 word3 ... word10000"

# Bad: materializes all matches - O(m) memory
all_matches = pattern.findall(text)  # All in memory

# Good: lazy iteration - O(1) memory
for match in pattern.finditer(text):  # O(1) memory
    process(match)
```

### Anchors for Efficiency

```python
import re

# Bad: searches entire string
pattern = re.compile(r'start.*end')
text = "start middle end"
match = pattern.search(text)  # O(m)

# Better: use anchors to limit backtracking
pattern = re.compile(r'^start.*?end$')
text = "start middle end"
match = pattern.search(text)  # More efficient
```

## Special Considerations

### Raw Strings

```python
import re

# Use raw strings to avoid double escaping
pattern = re.compile(r'\d+')  # O(n)
# NOT: re.compile('\\d+')  # confusing

# For file paths
pattern = re.compile(r'C:\\Users\\.*')  # Windows paths
```

### Groups and Performance

```python
import re

# Capturing groups have slight overhead
pattern = re.compile(r'(\d+)')  # With group
text = "12345"
match = pattern.search(text)  # O(m) + group overhead

# Non-capturing group - slightly faster
pattern = re.compile(r'(?:\d+)')  # Non-capturing
match = pattern.search(text)  # O(m)
```

## Version Notes

- **Third-party**: The `regex` package provides additional features
- **Python 3.x**: `re` module is standard
- **Python 2.x**: Similar but with different Unicode handling

## Related Modules

- **[string](string.md)** - String constants
- **[difflib](difflib.md)** - Sequence comparison
- **[textwrap](textwrap.md)** - Text wrapping

## Best Practices

✅ **Do**:

- Compile patterns once, reuse them
- Use raw strings (r'...')
- Use `pattern.finditer()` for lazy matching
- Test patterns on realistic data
- Use anchors (^, $) to limit search

❌ **Avoid**:

- Nested quantifiers (a+)+
- Alternation with overlap (`foo|fo`)
- Recompiling patterns in loops
- Greedy quantifiers where not needed (use .*?)
- Testing without considering catastrophic backtracking

## Further Reading

- [CPython Internals: re](https://zpoint.github.io/CPython-Internals/Modules/re/re.html) -
  Deep dive into CPython's re implementation
