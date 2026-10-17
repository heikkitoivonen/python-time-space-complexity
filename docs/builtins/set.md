# Set Operations Complexity

The `set` type is a mutable, unordered collection of unique hashable elements. It is a hash table,
like `dict` without the values, so membership, adding and removing cost O(1) on average, and set
algebra costs the elements it has to look up.

`n` is the number of elements in the set and `m` is the number of elements in the other operand, or
the items an iterable operand yields. The rows price one operand; a method given several applies
them one after another, at the sum of their costs. Element hashing and comparison are treated as
O(1).

## Complexity Reference

### set

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(s)` | O(1) | O(1) | The count is stored |
| `x in s` | O(1) avg, O(n) worst | O(1) | Hash lookup; worst case with hash collisions. A set `x` is hashed as a frozenset: O(k) for its k elements, and O(k) space before 3.14 |
| Iterating a `set` | O(n) | O(1) | Arbitrary order |
| `s.add(x)` | O(1) amortized | O(1) amortized | A resize occasionally rebuilds the table in O(n) |
| `s.remove(x)`, `s.discard(x)` | O(1) avg, O(n) worst | O(1) | `remove()` raises `KeyError` when `x` is absent; a set `x` is hashed as for `x in s` |
| `s.pop()` | O(1) amortized while draining | O(1) | Removes an arbitrary element, starting where the last `pop()` stopped; raises `KeyError` when empty. After other removals, one call can cost the table's former size |
| `s.clear()` | O(n) | O(1) | Releases every element |
| `s.copy()` | O(n) | O(n) | Shallow; the copy is sized for the elements it holds |
| `s == other`, `s != other` | O(n) | O(1) | O(1) when the lengths differ |
| `s <= other`, `s < other` | O(n) | O(1) | Same as `issubset()` with a set |
| `s >= other`, `s > other` | O(m) | O(1) | Same as `issuperset()` with a set |

### Set Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `s.union(other)`, `s \| other` | O(n+m) | O(n+m) | Returns a new set |
| `s.intersection(other)`, `s & other` | O(min(n,m)); O(m) if `other` is not a set | O(min(n,m)) | Looks up the smaller set's elements in the larger |
| `s.difference(other)`, `s - other` | O(n); O(n+m) if `other` is not a set | O(n) | Returns a new set |
| `s.symmetric_difference(other)`, `s ^ other` | O(n+m) | O(n+m) | Returns a new set |
| `s.issubset(other)` | O(n); O(n+m) if `other` is not a set | O(1); O(m) if `other` is not a set | O(1) when `other` is a shorter set |
| `s.issuperset(other)` | O(m) | O(1) | Stops at the first element of `other` missing from `s` |
| `s.isdisjoint(other)` | O(min(n,m)); O(m) if `other` is not a set | O(1) | Stops at the first common element; a set subclass is iterated like any iterable |

### In-Place Updates

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `s.update(other)`, `s \|= other` | O(m) amortized | O(m) amortized | `s` grows by up to m elements |
| `s.intersection_update(other)`, `s &= other` | O(min(n,m)) amortized; O(m) amortized if `other` is not a set | O(min(n,m)) | Builds the intersection and swaps it in; freeing the old table is O(n), paid for by the insertions that filled it |
| `s.difference_update(other)`, `s -= other` | O(min(n,m)) amortized; O(m) amortized if `other` is not a set | O(n) | Removes from `s` in place |
| `s.symmetric_difference_update(other)`, `s ^= other` | O(m) amortized | O(m) amortized | `s` grows by up to m elements; a non-set `other` is first copied into a set |

The operators accept only sets and frozensets; the methods also take any iterable. In the worst
case, when every element hashes to the same value, the O(1) operations take O(n), and operations
that look up every element of one set in another degrade accordingly.

Removing elements with `remove()`, `discard()` or `pop()` does not shrink the table. After most
elements are removed, operations that walk it - iteration, `copy()`, `clear()`, `|`, `-`, `^`,
`&=`, comparisons and `set(s)` - still take time proportional to the set's former size, until later
insertions trigger a resize, and so can a single `pop()`. `len()` and membership tests are
unaffected. `&=` and its method always leave a compact table.

## Set Operations

The operators take only sets and frozensets, so a list on the right is a `TypeError`; the methods
take any iterable and turn it into elements as they go.

```python
a = {1, 2, 3}
b = {2, 3, 4}

assert a | b == {1, 2, 3, 4}     # O(n+m)
assert a & b == {2, 3}           # O(min(n,m))
assert a - b == {1}              # O(n)
assert a ^ b == {1, 4}           # O(n+m)

assert a.union([3, 4]) == {1, 2, 3, 4}  # O(n+m): a method takes any iterable
try:
    a | [3, 4]
except TypeError as error:
    assert 'unsupported operand' in str(error)
else:
    raise AssertionError('an operator takes only sets')

a |= b                           # O(m): grows a in place
assert a == {1, 2, 3, 4}
```

## Membership Testing

A list compares `x` with its elements one by one; a set hashes `x` once and probes a few slots on
average. Converting a list to a set costs O(n) once, so it pays off when you look up many values.

```python
numbers = list(range(1_000))
lookup = set(numbers)          # O(n) once

assert 999 in numbers          # O(n): scans the whole list
assert 999 in lookup           # O(1) avg
assert -1 not in lookup        # O(1) avg, found or not

# A set can be looked up in a set of frozensets, hashed as a frozenset
groups = {frozenset({1, 2}), frozenset({3})}
assert {1, 2} in groups        # O(k) to hash the k-element key
```

## Removing Does Not Shrink the Table

Removal leaves the table at its largest size, so walking it still costs what it did when it was
full. `copy()` gives back a compact table.

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

Draining a set with `pop()` alone visits each slot once, because every call starts where the last
one stopped. A `pop()` after other removals has to skip the empty slots in front of it first.

```python
s = set(range(1_000))
drained = 0
while s:
    s.pop()                        # O(1) amortized: the n calls walk the table once
    drained += 1
assert drained == 1_000

try:
    s.pop()
except KeyError as error:
    assert 'pop from an empty set' in str(error)
else:
    raise AssertionError('pop() on an empty set raises')
```

## Common Patterns

### Remove Duplicates

```python
items = [3, 1, 3, 2, 1]

# Bad: O(n²) - each `in` scans the list built so far
unique = []
for item in items:
    if item not in unique:
        unique.append(item)
assert unique == [3, 1, 2]

# Good: O(n), but the order is arbitrary
unique = set(items)
assert unique == {1, 2, 3}

# Best when order matters: O(n), keeping the first occurrence of each
assert list(dict.fromkeys(items)) == [3, 1, 2]
```

### Fast Filtering

```python
values = list(range(10_000))
excluded = [3, 30, 300, 3_000]

# Bad: O(n·m) - scans the excluded list for every value
slow = [x for x in values if x not in excluded]

# Good: O(n + m) - one O(m) conversion, then O(1) per value
excluded_set = set(excluded)
fast = [x for x in values if x not in excluded_set]

assert slow == fast and len(fast) == 10_000 - 4
```

## Performance Best Practices

✅ **Do**:

- Use a set for repeated membership tests: O(1) each, where a list costs O(n)
- Intersect sets in either order: `&` and `intersection()` with a set operand walk only the smaller
- Use `dict.fromkeys()` when you need unique items in their original order
- Copy a set that has lost most of its elements before walking it often, so walks cost what it holds

❌ **Avoid**:

- `x in some_list` inside a loop over another collection - O(n·m) where a set gives O(n + m)
- Relying on iteration order; it follows the hash table, not insertion
- Expecting `pop()` to be O(1) after removing most elements some other way

## Version Notes

- **Python 3.14+**: Looking up a set as an element (`{1, 2} in s`, `s.discard({1, 2})`) hashes it
  in place in O(1) space; earlier versions copy it into a temporary frozenset, O(k) space

## Related Types

- **[Frozenset](frozenset.md)** - Immutable, hashable set with the same lookup costs
- **[set()](set_func.md)** - Building a set from an iterable
- **[Dict](dict.md)** - The same hash table with values; `dict.fromkeys()` keeps insertion order

## Further Reading

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's set implementation
