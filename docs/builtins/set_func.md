# set() Function Complexity

The `set()` function creates sets from iterables or creates empty sets.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Empty set | O(1) | O(1) | set() |
| From iterable | O(n) avg, O(n²) worst | O(n) | n = iterable length; worst case with hash collisions |
| From string | O(n) | O(n) | n = string length |
| Duplicate removal | O(n) | O(n) | Automatic deduplication |
| Shallow copy | O(n) | O(n) | n = set size |

## Basic Usage

!!! note "Element order in examples"
    Sets are unordered. The element order shown in comments below is illustrative; actual `repr()` output is not guaranteed and may differ between runs, Python versions, or hash-randomization settings.

### Create Empty Set

```python
# O(1)
s = set()  # set()
```

### From List

```python
# O(n) - where n = list length
s = set([1, 2, 3])           # {3, 2, 1}
s = set([1, 2, 2, 3, 3, 3])  # {2, 1, 3} - duplicates removed
```

### From String

```python
# O(n) - where n = string length
s = set("hello")      # {'e', 'h', 'l', 'o'}
s = set("aabbcc")     # {'c', 'b', 'a'} - each char once
```

### From Other Iterables

```python
# O(n) - where n = iterable length
s = set((1, 2, 3))          # {2, 1, 3} (from tuple)
s = set({1, 2, 3})          # {1, 3, 2} (from set - copy)
s = set(range(5))           # {0, 2, 1, 3, 4}
s = set(map(str, [1, 2]))   # {'1', '2'} (from generator)
```

### From Dictionary

```python
# O(n) - uses dict keys
d = {"a": 1, "b": 2, "c": 3}
s = set(d)  # {'b', 'a', 'c'} - only keys, not values
```

## Complexity Details

### Hashing and Insertion

```python
# O(n) - hash each item and insert
# Each item:
# 1. Hash - O(1) average
# 2. Check for duplicates - O(1) average
# 3. Insert - O(1) average
# Total: O(n)

items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
s = set(items)  # O(10)
```

### Duplicate Removal

```python
# O(n) - automatic deduplication
items = [1, 1, 2, 2, 3, 3]
s = set(items)  # O(6) - creates {2, 1, 3}

# Useful for removing duplicates
unique = set("mississippi")  # {'i', 'm', 's', 'p'}
```

### From String

```python
# O(n) - iterate through string
short = set("ab")     # O(2) - {'a', 'b'}
long = set("a" * 1000)  # O(1000) - {'a'} (one item!)
```

## Common Patterns

### Remove Duplicates

```python
# O(n) - fastest way to remove duplicates
items = [1, 2, 2, 3, 3, 3, 4]
unique = set(items)  # O(7)
# {2, 1, 3, 4}

# Back to list if needed
unique_list = list(set(items))  # O(n)
```

### Find Unique Items

```python
# O(n) - check membership in set
items = [1, 2, 2, 3, 3, 3]
unique_count = len(set(items))  # O(n) - 3 unique items
```

### Set Operations

```python
# O(n) - after creating sets
s1 = set([1, 2, 3])
s2 = set([2, 3, 4])

intersection = s1 & s2      # {2, 3} - O(n)
union = s1 | s2            # {2, 1, 3, 4} - O(n)
difference = s1 - s2       # {1} - O(n)
symmetric_diff = s1 ^ s2   # {1, 4} - O(n)
```

### Membership Testing

```python
# O(1) - fast lookup
s = set([1, 2, 3, 4, 5])

if 3 in s:  # O(1)
    print("Found")

# vs list - O(n)
lst = [1, 2, 3, 4, 5]
if 3 in lst:  # O(n) - must scan
    print("Found")
```

## Performance Patterns

### vs List Creation

```python
# O(n) - set creation
s = set([1, 2, 3, 4, 5])

# O(n) - list creation
lst = [1, 2, 3, 4, 5]

# Similar complexity, but set has better lookup: O(1) vs O(n)
```

### Batch Operations

```python
# O(n * m) - n items, m = avg hash time (usually O(1))
items = range(1000)
s = set(items)  # O(n)

# Then operations are fast
if 500 in s:    # O(1)
    pass
```

## Edge Cases

### Empty Set

```python
# O(1)
s = set()       # set()
s = set([])     # set()
s = set("")     # set()
```

### Single Item

```python
# O(1)
s = set([1])    # {1}
s = set("a")    # {'a'}
```

### All Duplicates

```python
# O(n) - still must check all
items = [1, 1, 1, 1, 1]
s = set(items)  # O(5) - results in {1}
```

### Unhashable Items

```python
# O(n) - error for unhashable
try:
    s = set([[1, 2], [3, 4]])  # TypeError - lists not hashable
except TypeError:
    pass

# Use frozenset for nested immutable sets
s = set([frozenset([1, 2]), frozenset([3, 4])])  # OK
```

### Set vs frozenset

```python
# O(n) - both create from iterable
s = set([1, 2, 3])           # Mutable
fs = frozenset([1, 2, 3])    # Immutable

# frozenset can be in set, set cannot
s = {frozenset([1, 2]), frozenset([3, 4])}  # OK
# s = {{1, 2}, {3, 4}}  # TypeError
```

## Memory Considerations

```python
# O(n) - memory proportional to set size
small_set = set(range(10))      # 10 items
medium_set = set(range(10**4))  # 10,000 items
large_set = set(range(10**6))   # 1,000,000 items - uses significant memory
```

## Set Literal vs set()

```python
# Both O(n) but different syntax

# Literal - faster, no function call
s1 = {1, 2, 3, 4, 5}  # O(n)

# Function - more flexible
s2 = set([1, 2, 3, 4, 5])  # O(n)
s3 = set(range(5))  # O(n)

# Literal usually preferred for constants
```

## Best Practices

✅ **Do**:

- Use sets for membership testing (O(1) vs O(n) for lists)
- Use sets to remove duplicates
- Use set operations for intersection/union/difference
- Use {} literal for constants, set() for iterables

❌ **Avoid**:

- Using sets when order matters (they're unordered)
- Putting unhashable items in sets (lists, dicts)
- Creating sets of mutable objects (won't work)
- Assuming set order is consistent

## Related Functions

- **[frozenset()](frozenset_func.md)** - Immutable set
- **[list()](list_func.md)** - Convert to list
- **[dict()](dict_func.md)** - Convert to dictionary
- **[tuple()](tuple_func.md)** - Convert to tuple

## Version Notes

- **Python 2.x**: set() available, {} creates dict
- **Python 3.x**: set() and {} syntax available
- **All versions**: Unordered collection with O(1) lookup
