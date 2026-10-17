# Frozenset Operations Complexity

The `frozenset` type is an immutable set. It uses the same hash table as [`set`](set.md), so
lookups and set algebra cost the same; what immutability adds is a hash, cached on the object
after the first `hash()`, and copies that cost nothing because they return the original object.

`n` is the number of elements in the frozenset and `m` is the number of elements in the other
operand, or the items an iterable yields. Element hashing and comparison are treated as O(1).

## Complexity Reference

### frozenset

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `frozenset(iterable)` | O(m) | O(n) | Duplicates are dropped while building; see [`frozenset()`](frozenset_func.md) |
| `frozenset(fs)` | O(1) | O(1) | Returns `fs` itself when it is an exact frozenset; an instance of a subclass is copied in O(n) |
| `len(fs)` | O(1) | O(1) | The count is stored |
| `x in fs` | O(1) avg, O(n) worst | O(1) | Hash lookup; worst case with hash collisions |
| Iterating a `frozenset` | O(n) | O(1) | Arbitrary order |
| `fs.copy()` | O(1) | O(1) | Returns `fs` itself; an instance of a subclass is copied in O(n) |
| `hash(fs)` | O(n) first call, then O(1) | O(1) | Cached on the object; an equal frozenset computes its own |
| `fs == other`, `fs != other` | O(n) | O(1) | O(1) when the lengths differ |
| `fs <= other`, `fs < other` | O(n) | O(1) | Same as `issubset()` with a set |
| `fs >= other`, `fs > other` | O(m) | O(1) | Same as `issuperset()` |

### Set Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fs.union(other)`, `fs \| other` | O(n+m) | O(n+m) | Combine sets |
| `fs.intersection(other)`, `fs & other` | O(min(n,m)); O(m) if `other` is not a set | O(min(n,m)) | Common elements |
| `fs.difference(other)`, `fs - other` | O(n); O(n+m) if `other` is not a set | O(n) | Elements in `fs` only |
| `fs.symmetric_difference(other)`, `fs ^ other` | O(n+m) | O(n+m) | Elements in exactly one |
| `fs.issubset(other)` | O(n); O(n+m) if `other` is not a set | O(1); O(m) if `other` is not a set | Check containment |
| `fs.issuperset(other)` | O(m) | O(1) | Check containment |
| `fs.isdisjoint(other)` | O(min(n,m)); O(m) if `other` is not a set | O(1) | Stops at the first common element |

The operators accept only sets and frozensets; the methods also take any iterable. Union,
intersection, difference and symmetric difference return a new object: `fs | s` is a frozenset and
`s | fs` a set. In the worst case, when every element hashes to the same value, the O(1)
operations take O(n), and operations that look up every element of one set in another degrade
accordingly.

Operations that walk a table - iteration, the first `hash()`, `|`, `&`, `-`, `^` and comparisons -
take time proportional to its size, which removing elements does not always shrink. A `set` operand
that has lost most of its elements, or a frozenset returned by `difference()` with a non-set
iterable that removed most of the elements, can keep a table of its former size - see
[Set](set.md).

## Hashing

### Hashable Where a Set Is Not

```python
fs1 = frozenset([1, 2, 3])  # O(n) to build
fs2 = frozenset([4, 5, 6])  # O(n) to build

d = {fs1: 'first', fs2: 'second'}  # O(n) first hash of each, then O(1) avg
s = {fs1, fs2}
assert d[frozenset([3, 2, 1])] == 'first'
assert fs1 in s

regular_set = {1, 2, 3}
try:
    d[regular_set] = 'value'
except TypeError as error:
    assert 'unhashable' in str(error)
else:
    raise AssertionError('a set cannot be a dict key')
```

### The Hash Is Cached per Object

The first `hash()` walks every element; later calls on the same object read the stored value. The
cache belongs to the object, not to its contents: an equal frozenset built separately pays for its
own first hash, and finding it in a dict then compares the elements, O(n), to confirm the match.

```python
fs = frozenset(range(1_000))

h1 = hash(fs)  # O(n) - computed once, then stored on fs
h2 = hash(fs)  # O(1) - reads the stored value
assert h1 == h2

table = {fs: 'found'}
twin = frozenset(range(1_000))      # equal, but a different object
assert twin is not fs
assert table[twin] == 'found'       # O(n): its own first hash, then an element-wise comparison
assert table[fs] == 'found'         # the same object matches by identity, with no comparison
```

## Copying

`copy()` and `frozenset(fs)` hand back the object itself, because an immutable value can be shared.
A `set` built from it is a real copy.

```python
fs1 = frozenset([1, 2, 3])
assert fs1.copy() is fs1      # O(1)
assert frozenset(fs1) is fs1  # O(1)

s = set(fs1)                  # O(n)
assert s == fs1 and s is not fs1
```

## Set Operations

```python
fs1 = frozenset([1, 2, 3])
fs2 = frozenset([3, 4, 5])

assert fs1 | fs2 == {1, 2, 3, 4, 5}  # O(n+m)
assert fs1 & fs2 == {3}              # O(min(n,m))
assert fs1 - fs2 == {1, 2}           # O(n)
assert fs1 ^ fs2 == {1, 2, 4, 5}     # O(n+m)

# A frozenset on the left gives a frozenset, a set on the left a set
assert type(fs1 | {9}) is frozenset
assert type({9} | fs1) is set
```

## Common Patterns

### Unordered Pairs as Keys

A frozenset key makes `(a, b)` and `(b, a)` the same key.

```python
from collections import Counter

moves = [(0, 1), (1, 0), (0, 1), (2, 3)]
edge_counts = Counter(frozenset(m) for m in moves)  # O(len(moves)) - each pair hashes in O(1)
assert edge_counts[frozenset([0, 1])] == 3
assert len(edge_counts) == 2
```

### Growing a Path Without Mutation

`path | {node}` copies the whole frozenset, so extending a path one node at a time costs O(d) per
step and O(d²) for a path of depth d. A mutable set with `add()` and `remove()` does the same walk
in O(1) per step, at the price of undoing each change on the way back.

```python
graph = {'a': ['b', 'c'], 'b': ['c'], 'c': ['a']}

def simple_paths(node, path=frozenset()):
    path = path | {node}  # O(d) - copies the d nodes already on the path
    count = 1
    for neighbor in graph[node]:
        if neighbor not in path:  # O(1) avg
            count += simple_paths(neighbor, path)
    return count

assert simple_paths('a') == 4  # a, a-b, a-b-c, a-c
```

### Function Memoization

`functools.lru_cache` needs hashable arguments, so pass a frozenset where a set would be rejected.
Each new frozenset pays its own first hash, so reuse one object across calls to keep that O(1).

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def total(items):
    return sum(items)

items = frozenset([1, 2, 3])
assert total(items) == 6  # O(n) hash on the first call
assert total(items) == 6  # cached hash and cached result
assert total.cache_info().hits == 1
```

## Memory Considerations

A frozenset has the same layout as a set, so the same elements added the same way take the same
memory.

```python
import sys

items = list(range(100))
assert sys.getsizeof(frozenset(items)) == sys.getsizeof(set(items))
```

## Comparison with Set

| Operation | Set | Frozenset |
|-----------|-----|-----------|
| Hashable | No | Yes |
| Mutable | Yes | No |
| Dict key | No | Yes |
| Copy cost | O(n) | O(1) |
| Hash cost | - | O(n) first call, O(1) after |
| Memory | Same | Same |

## Performance Best Practices

✅ **Do**:

- Use a frozenset as a dict key or set member when the key is an unordered group of values
- Keep and reuse one frozenset object as a key; its hash is cached on that object
- Call `copy()` or `frozenset(fs)` freely; neither copies anything

❌ **Avoid**:

- Building a frozenset per step to grow a collection: each `|` copies all n elements
- Rebuilding an equal frozenset for each lookup: it pays O(n) to hash and O(n) to compare

## Version Notes

- **All Python 3**: `copy()` and `frozenset(fs)` return `fs` itself, and the hash is cached on the
  object after the first `hash()`

## Related Types

- **[frozenset()](frozenset_func.md)** - Building a frozenset from an iterable
- **[Set](set.md)** - Mutable alternative
- **[Frozendict](frozendict.md)** - Immutable, hashable mapping (Python 3.15+)
- **[Tuple](tuple.md)** - For ordered hashable sequences
