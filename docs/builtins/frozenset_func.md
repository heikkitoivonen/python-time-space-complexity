# frozenset() Function Complexity

The `frozenset()` function creates immutable sets from iterables.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Empty frozenset | O(1) | O(1) | frozenset() |
| From iterable | O(n) avg | O(n) | n = iterable length; O(n²) worst case with hash collisions |
| From string | O(n) avg | O(n) | n = string length; each char hashed |
| Duplicate removal | O(n) avg | O(n) | Automatic deduplication via hashing |
| Shallow copy | O(1) | O(1) | Returns same object (immutable) |

## Basic Usage

!!! note "Element order in examples"
    Frozensets are unordered. The element order shown in comments below is illustrative; actual `repr()` output is not guaranteed and may differ between runs, Python versions, or hash-randomization settings.

### Create Empty Frozenset

```python
# O(1)
fs = frozenset()  # frozenset()
```

### From List

```python
# O(n) - where n = list length
fs = frozenset([1, 2, 3])           # frozenset({2, 1, 3})
fs = frozenset([1, 2, 2, 3, 3, 3])  # frozenset({1, 3, 2})
```

### From String

```python
# O(n) - where n = string length
fs = frozenset("hello")    # frozenset({'h', 'l', 'e', 'o'})
fs = frozenset("aabbcc")   # frozenset({'c', 'b', 'a'})
```

### From Other Iterables

```python
# O(n) - where n = iterable length
fs = frozenset((1, 2, 3))         # frozenset({2, 1, 3})
fs = frozenset({1, 2, 3})         # frozenset({1, 2, 3})
fs = frozenset(range(5))          # frozenset({0, 2, 1, 3, 4})
fs = frozenset(map(str, [1, 2]))  # frozenset({'1', '2'})
```

## Complexity Details

### Hashing and Insertion

```python
# O(n) - same as set() but immutable
# Each item:
# 1. Hash - O(1) average
# 2. Check for duplicates - O(1) average
# 3. Insert - O(1) average
# Total: O(n)

items = [1, 2, 3, 4, 5]
fs = frozenset(items)  # O(5)
```

### Immutability

```python
# O(1) - immutable, cannot modify
fs = frozenset([1, 2, 3])

# Cannot add/remove
# fs.add(4)  # AttributeError
# fs.remove(1)  # AttributeError

# Can use in dict keys
data = {fs: "value"}  # OK - hashable
```

## Common Patterns

### Immutable Set

```python
# O(n) - create immutable set
original = frozenset([1, 2, 3])

# Safe to use as dict key
lookup = {original: "config"}  # OK

# Safe to use in set
sets = {frozenset([1, 2]), frozenset([3, 4])}  # OK
```

### Set Operations (Read-Only)

```python
# O(n) - all set operations available
fs1 = frozenset([1, 2, 3])
fs2 = frozenset([2, 3, 4])

intersection = fs1 & fs2      # frozenset({2, 3})
union = fs1 | fs2             # frozenset({1, 2, 3, 4})
difference = fs1 - fs2        # frozenset({1})
symmetric_diff = fs1 ^ fs2    # frozenset({1, 4})
```

### Use as Dict Key

```python
# O(1) - lookup, O(n) - creation
coordinates = frozenset([(1, 2), (3, 4)])
data = {coordinates: "polygon"}  # OK

# Can't use set as key
# locations = {set([1, 2]): "spot"}  # TypeError
```

### Cache Key

```python
# O(n) - create frozenset for cache
from functools import lru_cache

@lru_cache(maxsize=128)
def process_items(items):
    # items must be hashable
    return sum(items)

# Convert to frozenset before caching
result = process_items(frozenset([1, 2, 3]))  # O(n)
```

## Performance Patterns

### vs set()

```python
# Both O(n) to create
s = set([1, 2, 3])
fs = frozenset([1, 2, 3])

# set() is mutable, faster for dynamic changes
s.add(4)  # O(1)
s.remove(1)  # O(1)

# frozenset() is immutable, hashable
# fs.add(4)  # Not available
# Can use in dict: {fs: value}  # OK
```

### Set Operations

```python
# O(n) - both sets and frozensets support operations
s1 = set([1, 2, 3])
fs1 = frozenset([1, 2, 3])

s2 = set([2, 3, 4])
fs2 = frozenset([2, 3, 4])

# All O(n)
s1 & s2        # {2, 3}
fs1 & fs2      # frozenset({2, 3})
s1 & fs2       # {2, 3} - mixed works
```

## Edge Cases

### Empty Frozenset

```python
# O(1)
fs = frozenset()       # frozenset()
fs = frozenset([])     # frozenset()
fs = frozenset("")     # frozenset()
```

### Single Item

```python
# O(1)
fs = frozenset([1])    # frozenset({1})
fs = frozenset("a")    # frozenset({'a'})
```

### All Duplicates

```python
# O(n) - still must process all
items = [1, 1, 1, 1, 1]
fs = frozenset(items)  # O(5) - results in frozenset({1})
```

### Unhashable Items

```python
# O(n) - error for unhashable
try:
    fs = frozenset([[1, 2], [3, 4]])  # TypeError - lists not hashable
except TypeError:
    pass
```

### Nested Frozensets

```python
# O(n) - frozensets can contain frozensets
inner1 = frozenset([1, 2])
inner2 = frozenset([3, 4])
outer = frozenset([inner1, inner2])  # frozenset({...})

# Use as dict key
data = {outer: "nested"}  # OK - fully hashable
```

## Comparison with set()

```python
# Mutability
s = set([1, 2, 3])
s.add(4)  # O(1) - works

fs = frozenset([1, 2, 3])
# fs.add(4)  # AttributeError - not available

# Hashability
data = {fs: "value"}  # OK - frozenset is hashable
# data = {s: "value"}  # TypeError - set not hashable

# Performance
# Both O(1) for lookup
1 in s   # O(1)
1 in fs  # O(1)
```

## Memory Considerations

```python
# O(n) - memory proportional to frozenset size
small_fs = frozenset(range(10))      # 10 items
medium_fs = frozenset(range(10**4))  # 10,000 items
large_fs = frozenset(range(10**6))   # 1,000,000 items
```

## Best Practices

✅ **Do**:

- Use frozenset when you need a hashable set
- Use frozenset as dict key or in sets
- Use frozenset for immutable collections
- Use frozenset for cache keys with sets

❌ **Avoid**:

- Using frozenset when you need to modify (use set)
- Assuming frozenset is faster (usually slower to create)
- Putting unhashable items in frozensets
- Creating frozensets from mutable objects

## Related Functions

- **[set()](set_func.md)** - Mutable set
- **[tuple()](tuple_func.md)** - Immutable sequence
- **[dict()](dict_func.md)** - Dictionary (also hashable)

## Version Notes

- **Python 2.x**: frozenset() available
- **Python 3.x**: Same behavior
- **All versions**: Hashable, immutable, unordered
