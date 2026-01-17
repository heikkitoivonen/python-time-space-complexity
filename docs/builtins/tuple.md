# Tuple Operations Complexity

The `tuple` type is an immutable, ordered sequence. Being immutable allows various optimizations in CPython.

## Time Complexity

| Operation | Time | Notes |
|-----------|------|-------|
| `len()` | O(1) | Direct lookup |
| `access[i]` | O(1) | Direct indexing |
| `index(x)` | O(n) | Linear search |
| `count(x)` | O(n) | Linear scan |
| `in` (membership) | O(n) | Linear search |
| `copy()` | O(1) | Just increments reference count |
| `x + y` (concatenation) | O(m+n) | m, n are lengths |
| `t * n` (repetition) | O(n*len(t)) | Creates new tuple |
| `hash()` | O(n) first, O(1) after | First call computes, then cached |
| `reversed()` | O(1) | Iterator, not materialized |
| `tuple()` constructor | O(n) | n = iterable length |
| `slice [::2]` | O(k) | k = slice length |

## Space Complexity

| Operation | Space |
|-----------|-------|
| Creation | O(1) reference |
| Copy | O(1) (same object) |
| Concatenation | O(m+n) new tuple |
| Repetition | O(n*len(t)) |
| Reversed iterator | O(1) |

## Implementation Details

### Immutability Advantages

```python
# Tuples are hashable - can be dict keys or set members
d = {(1, 2): 'point', (3, 4): 'another'}
s = {(0, 0), (1, 1)}

# Lists cannot - they're mutable
# d[[1, 2]] = 'fails'  # TypeError: unhashable type
```

### Hash Caching

```python
# First hash() call computes hash value
t = (1, 2, 3)
h1 = hash(t)  # O(n) - computes by iterating elements

# Subsequent calls use cached value
h2 = hash(t)  # O(1) - returns cached value
```

### Reference vs Copy

```python
# Tuple "copy" doesn't copy - returns same object
t1 = (1, 2, 3)
t2 = tuple(t1)
print(t1 is t2)  # True - same object in memory!

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

- **All versions**: Core complexity stable
- **Python 3.8+**: Improved tuple unpacking in some cases
- **Python 3.11+**: Adaptive specialization may optimize repeated tuple operations

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
- Assuming tuple copy is fast - it still references same elements

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

# Both have same access time; tuple is hashable and immutable
```

## Related Types

- **[List](list.md)** - Mutable alternative
- **[Namedtuple](../stdlib/collections.md#namedtuple)** - Tuples with named fields
- **[Dataclass](../stdlib/dataclasses.md)** - More powerful structure type
