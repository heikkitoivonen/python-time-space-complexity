# Tuple Operations Complexity

The `tuple` type is an immutable, ordered sequence. Being immutable allows various optimizations in CPython.

`n` is the tuple's length, `k` is an index or a repeat count, `i:j` are slice bounds, and
`len(t1)`, `len(t2)` are operand lengths. Comparing or hashing one element counts as O(1).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(t)` | O(1) | O(1) | The length is stored in the tuple, not counted |
| `t[k]` | O(1) | O(1) | Direct indexing |
| `index(x)` | O(n) | O(1) | Linear search |
| `count(x)` | O(n) | O(1) | Linear scan |
| `x in t` (membership) | O(n) | O(1) | Linear search |
| `tuple(t)`, `copy.copy(t)` | O(1) | O(1) | Returns `t` itself when `t` is an exact tuple; tuples have no `copy()` method |
| `t1 + t2` (concatenation) | O(len(t1)+len(t2)) | O(len(t1)+len(t2)) | |
| `t * k` (repetition) | O(nk) | O(nk) | |
| `for x in t` (iteration) | O(n) | O(1) | O(1) per step |
| `min(t)`, `max(t)` | O(n) | O(1) | n-1 comparisons |
| `hash()` | O(n) first call; O(1) after it on 3.14+ | O(1) | 3.14+ caches the hash in `ob_hash`; 3.11-3.13 recompute it every call |
| `reversed()` | O(1) | O(1) | Iterator, not materialized |
| `tuple()` constructor | O(n) | O(n) | n = iterable length; an exact tuple is returned as is |
| `t[i:j]` (slicing) | O(j-i) | O(j-i) | With a step, O(length of the result) |

## Implementation Details

### Immutability Advantages

```python
# Tuples of hashable elements are hashable - can be dict keys or set members
d = {(1, 2): 'point', (3, 4): 'another'}
s = {(0, 0), (1, 1)}

# Lists cannot - they're mutable
# d[[1, 2]] = 'fails'  # TypeError: unhashable type
```

### Hash Computation

```python
# hash() computes hash value by iterating all elements
t = tuple([1, 2, 3])  # built at run time, so not hashed yet
h1 = hash(t)  # O(n) first call - computes by iterating elements

# Python 3.14+ caches the hash in the tuple's ob_hash field;
# 3.11-3.13 recompute it on every call
h2 = hash(t)  # O(1) on 3.14+, O(n) on 3.11-3.13
assert h1 == h2
```

### Reference vs Copy

```python
# Tuple "copy" doesn't copy - returns same object
t1 = (1, 2, 3)
t2 = tuple(t1)
assert t1 is t2  # True - same object in memory!

# This is safe because tuples are immutable
```

## Performance Compared to Lists

```python
# List access: O(1) with bounds checking
lst = [0] * 1000000
value = lst[500000]  # O(1)

# Tuple access: O(1) same as list
tup = tuple(lst)
value = tup[500000]  # O(1)

# But tuple creation from list: O(n)
tup = tuple(lst)  # O(n) - must copy all elements
```

## Version Notes

- **Python 3.8+**: Improved tuple unpacking in some cases
- **Python 3.11+**: Adaptive specialization may optimize repeated tuple operations
- **Python 3.14+**: `hash()` caches its result in the tuple, so repeat calls are O(1)

## Implementation Comparison

### CPython
Direct sequence type with immutability optimizations.

### PyPy
JIT compilation with escape analysis may further optimize.

### Jython
Similar characteristics, backed by Java arrays.

## Best Practices

✅ **Do**:

- Use tuples for immutable sequences
- Use tuples as dict keys when you need structured keys
- Use tuples for multiple return values
- Use tuple unpacking: `x, y = point`

❌ **Avoid**:

- Repeated concatenation: `t += (item,)` in loops - use list instead
- Creating tuples from large iterables in loops

## Common Patterns

### Named Return Values

```python
# Basic tuples
def get_coordinates():
    return (10, 20)

x, y = get_coordinates()

# Better: use named tuples
from collections import namedtuple
Point = namedtuple('Point', ['x', 'y'])

def get_point():
    return Point(10, 20)

p = get_point()
print(p.x, p.y)  # More readable
```

### Tuple vs List Performance

```python
# Tuple creation: O(n) once, then fast access
tup = tuple(range(1000000))
for i in range(1000):
    x = tup[i]  # O(1)

# List creation: O(n) once, then fast access
lst = list(range(1000000))
for i in range(1000):
    x = lst[i]  # O(1)

# Both have O(1) indexing; tuple is hashable and immutable
```

## Related Types

- **[List](list.md)** - Mutable alternative
- **[Namedtuple](../stdlib/collections.md#namedtuple)** - Tuples with named fields
- **[Dataclass](../stdlib/dataclasses.md)** - More powerful structure type

## Further Reading

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's tuple implementation
