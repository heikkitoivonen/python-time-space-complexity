# Frozenset Operations Complexity

The `frozenset` type is an immutable set that can be hashed and used as a dictionary key or set member.

`n` is the number of elements in the frozenset and `m` is the number of elements in the other
operand or in the iterable it is built from. Element hashing and comparison are treated as O(1).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `frozenset(iterable)` | O(m) | O(n) | Create from iterable |
| `len()` | O(1) | O(1) | Direct count |
| `in` (membership) | O(1) avg, O(n) worst | O(1) | Hash lookup; worst case with hash collisions |
| `union(\|)` | O(n+m) | O(n+m) | Combine sets |
| `intersection(&)` | O(min(n,m)); O(m) if `other` is not a set | O(min(n,m)) | Common elements |
| `difference(-)` | O(n); O(n+m) if `other` is not a set | O(n) | Elements in first |
| `symmetric_difference(^)` | O(n+m) | O(n+m) | Exclusive elements |
| `issubset()` | O(n); O(n+m) if `other` is not a set | O(1); O(m) if `other` is not a set | Check containment |
| `issuperset()` | O(m) | O(1) | Check containment |
| `isdisjoint()` | O(min(n,m)); O(m) if `other` is not a set | O(1) | Check overlap |
| `copy()` | O(1) | O(1) | Returns same object (immutable); an instance of a subclass is copied in O(n) |
| `hash()` | O(n) first call, O(1) cached | O(1) | Hash value computed once, then cached |
| `frozenset(set)` | O(n) | O(n) | Convert from set |
| `frozenset(fs)` | O(1) | O(1) | Returns `fs` itself when it is an exact frozenset |

The operators accept only sets and frozensets; the methods also take any iterable. In the worst
case, when every element hashes to the same value, the O(1) operations take O(n), and operations
that look up every element of one set in another degrade accordingly.

## Implementation Details

### Hashability

```python
# Frozenset is hashable - can be used as dict key
fs1 = frozenset([1, 2, 3])  # O(n) to build
fs2 = frozenset([4, 5, 6])  # O(n) to build

d = {fs1: 'first', fs2: 'second'}  # Works! O(n) first hash, then O(1) avg
s = {fs1, fs2}                      # Works!

# Set is not hashable
regular_set = {1, 2, 3}
try:
    d[regular_set] = 'value'
except TypeError as error:
    assert 'unhashable' in str(error)
else:
    raise AssertionError('a set cannot be a dict key')
```

### Immutability Benefits

```python
# Frozenset is immutable and hashable
fs = frozenset([1, 2, 3])

# Can be dictionary key
cache = {fs: 'result'}

# Can be in another set
nested = {fs, frozenset([4, 5])}

# Hash is stable (doesn't change)
h1 = hash(fs)    # O(n) - computed once, then cached on the object
# ... time passes ...
h2 = hash(fs)    # O(1) - reads the cached value
assert h1 == h2  # Always true
# Caching removes the rehash from every later lookup. It does not make a
# collision free: comparing two equal-hashing frozensets still scans them
```

## Performance Considerations

### Copy is O(1)

```python
# Frozenset copy returns same object (since immutable)
fs1 = frozenset([1, 2, 3])
fs2 = frozenset(fs1)
print(fs1 is fs2)  # True - same object!

# Contrast with set
s1 = {1, 2, 3}
s2 = set(s1)
print(s1 is s2)    # False - different objects
```

### Set Operations

```python
# Union: O(n+m)
fs1 = frozenset([1, 2, 3])
fs2 = frozenset([3, 4, 5])
fs3 = fs1 | fs2        # O(n+m)

# Intersection: O(min(n,m))
fs4 = fs1 & fs2        # O(min(n,m))

# Difference: O(n)
fs5 = fs1 - fs2        # O(n)

# All create new frozensets
```

## Use Cases

### As Dictionary Keys

```python
from collections import Counter

# Count coordinate pairs - frozenset as key
moves = [(0, 1), (1, 0), (0, 1), (1, 0), (0, 1)]
move_counts = Counter(tuple(m) for m in moves)  # O(n)

# Or with frozenset for unordered pairs
edges = frozenset([(0, 1), (2, 3), (0, 1)])  # O(n) - deduplicates while building
print(len(edges))  # O(1) - 2, duplicate removed
```

### In Graph Algorithms

```python
# Store visited states as frozensets
def dfs(node, visited=None):
    if visited is None:
        visited = frozenset()
    
    visited = visited | {node}  # O(n+1)
    # ... process node ...
    
    for neighbor in node.neighbors:
        if neighbor not in visited:  # O(1)
            dfs(neighbor, visited)
```

### Function Memoization

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def process_items(items):
    # items must be hashable - use frozenset
    return sum(items)

# Calling with frozenset
result = process_items(frozenset([1, 2, 3]))  # O(n) hash on the first call, then cached
```

## Memory Considerations

```python
import sys

# Frozenset overhead
fs = frozenset([1, 2, 3])
print(sys.getsizeof(fs))      # ~216+ bytes

# Similar to set
s = {1, 2, 3}
print(sys.getsizeof(s))       # ~216+ bytes

# Immutable, so can be shared
fs1 = frozenset([1, 2, 3])
fs2 = frozenset(fs1)          # Same object, no copy
print(fs1 is fs2)             # True
```

## Comparison with Set

| Operation | Set | Frozenset |
|-----------|-----|-----------|
| Hashable | No | Yes |
| Mutable | Yes | No |
| Dict key | No | Yes |
| Copy cost | O(n) | O(1) |
| Hash cost | - | O(n) first call, O(1) after |
| Memory | Similar | Similar |

## Version Notes

- **All Python 3.x**: Core complexity unchanged
- **Python 3.5+**: Some optimization improvements

## Related Types

- **[Set](set.md)** - Mutable alternative
- **[Dict](dict.md)** - For ordered key-value pairs
- **[Tuple](tuple.md)** - For ordered hashable sequences
