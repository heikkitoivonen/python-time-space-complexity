# Set Operations Complexity

The `set` type is an unordered collection of unique items. It's implemented as a hash table similar to dictionaries in CPython.

`n` is the number of elements in the set and `m` is the number of elements in the other operand.
Element hashing and comparison are treated as O(1).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Direct count |
| `add(x)` | O(1) avg, O(n) worst | O(1) amortized | Hash collisions cause O(n) |
| `remove(x)` | O(1) avg, O(n) worst | O(1) | Hash lookup + delete |
| `discard(x)` | O(1) avg, O(n) worst | O(1) | Hash lookup + delete |
| `pop()` | O(1) avg | O(1) | Remove arbitrary element |
| `clear()` | O(n) | O(1) | Deallocate all |
| `x in set` | O(1) avg, O(n) worst | O(1) | Hash lookup; collisions cause O(n) |
| `copy()` | O(n) | O(n) | Shallow copy |
| `union(other)`, `s \| other` | O(n+m) | O(n+m) | n, m = set lengths |
| `intersection(other)`, `s & other` | O(min(n,m)); O(m) if `other` is not a set | O(min(n,m)) | Iterate smaller set |
| `difference(other)`, `s - other` | O(n); O(n+m) if `other` is not a set | O(n) | n = set length |
| `symmetric_difference(other)`, `s ^ other` | O(n+m) | O(n+m) | Combined set ops |
| `issubset()` | O(n); O(n+m) if `other` is not a set | O(1); O(m) if `other` is not a set | Check all elements |
| `issuperset()` | O(m) | O(1) | m = other length |
| `isdisjoint()` | O(min(n,m)); O(m) if `other` is not a set | O(1) | Early termination |
| `update(other)`, `s \|= other` | O(m) | O(1) | In-place union; m = len(other) |
| `difference_update(other)`, `s -= other` | O(min(n,m)); O(m) if `other` is not a set | O(n) | In-place difference; scans whichever side is smaller |
| `intersection_update(other)`, `s &= other` | O(n); O(n+m) if `other` is not a set | O(min(n,m)) | In-place intersection; rebuilds the set and frees the old table, so O(n) even when `other` is small |
| `symmetric_difference_update(other)`, `s ^= other` | O(m) | O(1); O(m) if `other` is not a set | In-place symmetric difference |

The operator forms accept only sets and frozensets; the methods also take any iterable. In the worst
case, when every element hashes to the same value, the O(1) operations take O(n), and operations
that look up every element of one set in another degrade accordingly.

Removing elements with `remove()`, `discard()` or `pop()` does not shrink the table. After most
elements are removed, operations that walk it - iteration, `copy()`, `|`, `-`, `^`, comparisons
and `set(s)` - still take time proportional to the set's former size, until later insertions
trigger a resize. `len()` and membership tests are unaffected, and removing most elements with
`-=`, `&=` or their methods leaves a compact table.

## Implementation Details

### Hash Table Implementation

Sets use the same hash table design as dictionaries, but:

- Only stores keys (no values)
- More memory efficient than dict
- Same O(1) average case lookup

### Set Operations

```python
# Union: combines both sets
{1, 2} | {2, 3}  # {1, 2, 3} - O(len(s1) + len(s2))

# Intersection: common elements
{1, 2, 3} & {2, 3, 4}  # {2, 3} - O(min(len(s1), len(s2)))

# Difference: elements in first but not second
{1, 2, 3} - {2, 4}  # {1, 3} - O(len(s1))

# Symmetric difference: elements in either but not both
{1, 2} ^ {2, 3}  # {1, 3} - O(len(s1) + len(s2))
```

### Removing Does Not Shrink the Table

```python
import sys

s = set(range(100_000))
full = sys.getsizeof(s)
for i in range(10, 100_000):
    s.discard(i)                   # O(1) each

assert len(s) == 10                # O(1)
assert sys.getsizeof(s) == full    # still sized for 100,000 elements
items = list(s)                    # O(100,000): walks the old table

s = s.copy()                       # O(100,000) once
assert sys.getsizeof(s) < full     # sized for 10 elements
assert sorted(s) == sorted(items)  # O(10)
```

### Membership Testing

```python
# Very fast - O(1) hash lookup
s = {1, 2, 3, 4, 5}
if 3 in s:  # O(1), not O(n)
    pass
```

## Comparison with Lists

```python
# List membership: O(n) - must scan entire list
numbers_list = [1, 2, 3, 4, 5]
3 in numbers_list  # O(n)

# Set membership: O(1) - hash lookup
numbers_set = {1, 2, 3, 4, 5}
3 in numbers_set  # O(1) - much faster for large collections!
```

## Version Notes

- **All Python 3 versions**: Core complexity unchanged

## Implementation Comparison

### CPython
Standard hash table implementation.

### PyPy
JIT compilation may provide additional optimization.

### Jython
Underlying Java HashSet, same O(1) characteristics.

## Best Practices

✅ **Do**:

- Use sets for membership testing with large collections
- Use set operations (`|`, `&`, `-`, `^`) for combining sets
- Use sets to remove duplicates: `set(list_with_dups)`
- Use `frozenset` for hashable unique items

❌ **Avoid**:

- Using lists for frequent membership checks
- Relying on set order (not guaranteed)
- Unhashable types (lists, dicts) in sets

## Common Patterns

### Remove Duplicates

```python
items = [3, 1, 3, 2, 1]

# Bad: preserves list, but O(n²)
unique = []
for item in items:
    if item not in unique:
        unique.append(item)

# Good: O(n), but loses order
unique = list(set(items))

# Best: O(n) and preserves order (Python 3.7+)
unique = list(dict.fromkeys(items))
```

### Fast Filtering

```python
# Bad: O(n*m) - checks membership in list for each element
large_list = list(range(1000000))
exclusions = [1, 2, 3, ...]
filtered = [x for x in large_list if x not in exclusions]

# Good: O(n) - fast set lookup
exclusions_set = set(exclusions)
filtered = [x for x in large_list if x not in exclusions_set]
```

## Related Types

- **[Frozenset](frozenset.md)** - Immutable set
- **[Dict](dict.md)** - Mutable mapping
- **[Deque](../stdlib/collections.md#deque)** - Ordered collection

## Further Reading

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's set implementation
