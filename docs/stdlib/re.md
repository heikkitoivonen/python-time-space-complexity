# re Module Complexity

The `re` module provides regular expression matching operations.

Throughout, `n` is the length of a pattern, `m` the length of the subject
string, `k` the number of matches, `c` the number of capturing groups, and `g`
the total length of the text captured or matched.

## Pattern Compilation and Matching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `re.compile(pattern)` | O(n) | O(n) | n = pattern length |
| `pattern.match(string)` | O(m) typical, O(exp) worst | O(m) | Worst case from backtracking |
| `pattern.fullmatch(string)` | O(m) typical, O(exp) worst | O(m) | Match entire string |
| `pattern.search(string)` | O(m) typical, O(exp) worst | O(m) | Searches full string |
| `pattern.findall(string)` | O(m) typical, O(exp) worst | O(k + g) | A list of k copies, so the matched text counts too |
| `pattern.finditer(string)` | O(m) typical, O(exp) worst | O(1) | Lazy: the whole scan still costs O(m), spread across the steps |
| `pattern.sub(repl, string)` | O(m) typical, O(exp) worst | O(m) | Match + build output |
| `pattern.subn(repl, string)` | O(m) typical, O(exp) worst | O(m) | Like sub, returns (newstr, count) |
| `pattern.split(string)` | O(m) typical, O(exp) worst | O(m) | Split by pattern |
| `re.match(pattern, string)` | O(n + m) typical, O(exp) worst | O(m) | Compiles on cache miss; cached up to ~512 |
| `re.search(pattern, string)` | O(n + m) typical, O(exp) worst | O(m) | Compiles on cache miss; cached up to ~512 |
| `re.escape(string)` | O(n) | O(n) | Escape special regex characters |
| `re.purge()` | O(cache) | O(1) | Empties the compiled-pattern caches and the replacement-template cache |
| `re.error` | - | - | Exception for invalid patterns |

*Note: "O(exp)" denotes exponential time in m from catastrophic backtracking; typical cases are much better.

## Match Objects

A match records positions into the subject string. Reading a position is
constant; asking for the text at that position copies it.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `match.span()`, `match.start()`, `match.end()` | O(1) | O(1) | Two integers, already held |
| `match.group(i)` | O(g) | O(g) | Slices the subject, so it copies the captured text; a group spanning the whole subject is returned unchanged |
| `match.groups()` | O(c + g) | O(c + g) | One slice per capturing group |
| `match.groupdict()` | O(c + g) | O(c + g) | The same slices, in a dict, for the *named* groups only |
| `match.expand(template)` | O(t + g) | O(t + g) | t = template length |
| `match.lastindex`, `match.re`, `match.string` | O(1) | O(1) | Attribute access |

When only the positions matter, `span()` avoids building the substring at all.

## Pattern Caching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `re.match(pattern, s)` | O(n + m) | O(n+m) | Compiles on cache miss; cached up to ~512 |
| `compiled = re.compile(p)` | O(n) | O(n) | Explicit compilation |
| `compiled.match(s)` | O(m) typical, O(exp) worst | O(m) | Uses the already-compiled pattern |

CPython caches the last ~512 compiled patterns automatically. The cache is an
LRU: passing a 513th pattern drops the least recently used entry rather than
emptying the cache, so a working set that fits keeps hitting. Python 3.13
added a 256-entry FIFO in front of it as a fast path.

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
    print(match.group())  # O(g) - the matched text is copied out
```

### Finding All Matches

```python
import re

pattern = re.compile(r'\w+')
text = "Hello world from Python"

# Find all - O(m) where m = text length
matches = pattern.findall(text)  # O(m)
# Result: ['Hello', 'world', 'from', 'Python']

# Lazy iteration - O(1) memory, but the scan still costs O(m) overall:
# each step scans forward to the next match
for match in pattern.finditer(text):
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
    full = match.group(0)    # O(g) - copies the matched text
    num = match.group(1)     # O(g) - copies the first group
    word = match.group(2)    # O(g) - copies the second group

# Positions instead of text - O(1), nothing is copied
start, end = match.span(1)

# Get all groups - O(c + g) for c capturing groups of total length g
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

The blow-up needs a subject that *fails* to match. `(a+)+$` against a string
of nothing but `a` succeeds on the first attempt and returns immediately; add
one character that cannot match and the same pattern has to try every way of
splitting the `a`s between the two quantifiers.

```python
import re
import sys

# AVOID: nested quantifiers, on input that does not match
bad_pattern = re.compile(r'(a+)+b')
bad_pattern.search('a' * 8)      # fine at this size
# bad_pattern.search('a' * 24)   # seconds, and doubling with each extra 'a'

# BETTER: remove the nesting, so there is nothing to redistribute
good_pattern = re.compile(r'a+b')
good_pattern.search('a' * 24)

# Python 3.11+: keep the nesting but forbid the backtracking
if sys.version_info >= (3, 11):
    atomic = re.compile(r'(?>a+)+b')
    possessive = re.compile(r'(a++)+b')
    atomic.search('a' * 24)
    possessive.search('a' * 24)
```

## Performance Tips

### Compile Patterns Once

```python
import re

lines = ["no digits here", "order 66", "still nothing"]
matched = []

# Bad: looks the pattern up in the cache on every call
for line in lines:
    if re.search(r'\d+', line):  # cache hit, but still a lookup
        matched.append(line)

# Good: compile once - O(n)
pattern = re.compile(r'\d+')  # O(n)
for line in lines:
    if pattern.search(line):  # O(m) per line
        matched.append(line)
```

### Use Lazy Iteration

```python
import re

pattern = re.compile(r'\w+')
text = " ".join(f"word{i}" for i in range(10000))
longest = 0

# Bad: materializes every match - O(k + g) memory for k matches
all_matches = pattern.findall(text)  # All in memory at once

# Good: lazy iteration - O(1) memory, one match alive at a time
for match in pattern.finditer(text):
    longest = max(longest, match.end() - match.start())
```

### Anchors for Efficiency

An unanchored `search` retries at every position in the subject, so a pattern
that cannot match anywhere costs O(m) attempts. From Python 3.11 a leading `^`
lets the engine give up after the first attempt, which is where the saving is -
not in backtracking within a match. Before 3.11 the anchor bought nothing: the
retry loop ran anyway, and the assertion simply failed at each position, which
made the anchored form the slower of the two.

```python
import re

unanchored = re.compile(r'start.*end')
anchored = re.compile(r'^start.*end')

# Matches at position 0: nothing to save, and the anchor is not free
text = "start middle end"
unanchored.search(text)  # O(m)
anchored.search(text)    # O(m)

# No match anywhere: on 3.11+ the anchor stops the retry at every offset
haystack = "x" * 100_000
unanchored.search(haystack)  # one attempt per position
anchored.search(haystack)    # one attempt, then done - O(1) from 3.11
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
- **Python 3.11+**: atomic groups `(?>...)` and possessive quantifiers `*+`,
  `++`, `?+` - the direct fix for catastrophic backtracking, since they keep
  the pattern's meaning and forbid the redistribution that causes it
- **Python 3.11+**: a `search` for a pattern anchored with `^` stops after the
  first attempt instead of retrying at every position; before that, anchoring
  made an unmatchable search slower rather than faster
- **Python 3.13+**: a 256-entry FIFO cache sits in front of the 512-entry LRU
  of compiled patterns

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
- Use anchors (^, $) to limit search - on Python 3.11+ this ends it after one attempt

❌ **Avoid**:

- Nested quantifiers (a+)+; on Python 3.11+ make them atomic instead
- Alternation with overlap (`foo|fo`)
- Recompiling patterns in loops
- Greedy quantifiers where not needed (use .*?)
- Testing without considering catastrophic backtracking
- Calling `group()` when `span()` would do - it copies the matched text

## Further Reading

- [CPython Internals: re](https://zpoint.github.io/CPython-Internals/Modules/re/re.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's re implementation
