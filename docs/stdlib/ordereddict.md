# OrderedDict - Insertion-Order Preserving Dictionary

The `OrderedDict` class from `collections` maintains insertion order of keys, guaranteeing that iteration order matches insertion order even in older Python versions.

!!! note "Python 3.7+ Note"
    Regular `dict` maintains insertion order as a language guarantee. Use `OrderedDict` for backwards compatibility with Python 3.6 and earlier, or when you need specialized methods like `move_to_end()`.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `OrderedDict()` | O(n) | O(n) | Create from dict/iterable |
| `__getitem__` | O(1) | O(1) | Access by key |
| `__setitem__` | O(1) | O(1) | Set/update item |
| `__delitem__` | O(1) | O(1) | Delete item (uses doubly-linked list) |
| `move_to_end()` | O(1) | O(1) | Move key to end |
| `popitem()` | O(1) | O(1) | Remove last (LIFO) |
| Iteration | O(n) | O(1) | Iterate in insertion order |

## Basic Usage

```python
from collections import OrderedDict

# Create empty OrderedDict - O(1)
od = OrderedDict()

# Create from dict - O(n)
od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
# Order: a, b, c (insertion order)

# Create from kwargs - O(n)
od = OrderedDict(a=1, b=2, c=3)

# Access - O(1)
print(od['a'])  # 1

# Update - O(1)
od['d'] = 4

# Iterate maintains insertion order - O(n)
for key, value in od.items():  # O(n)
    print(key, value)
```

## Move to End

```python
from collections import OrderedDict

# Create OrderedDict - O(n)
od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])

# Move to end - O(1)
od.move_to_end('a')
# Order: b, c, a

# Move to beginning - O(1)
od.move_to_end('b', last=False)
# Order: b, c, a (stays at front)
```

## FIFO / LIFO Access

```python
from collections import OrderedDict

# Create OrderedDict - O(n)
od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])

# Pop last (LIFO stack) - O(1)
last = od.popitem()  # ('c', 3)

# Pop first (FIFO queue) - O(1)
first = od.popitem(last=False)  # ('a', 1)

# Remaining order: b
```

## Reversing Insertion Order

```python
from collections import OrderedDict

# Create OrderedDict - O(n)
od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])

# Reverse iteration - O(n)
for key in reversed(od):  # O(n)
    print(key, od[key])
# Output: c, b, a

# Create reversed OrderedDict - O(n)
reversed_od = OrderedDict(reversed(od.items()))
# Order: c, b, a
```

## Equality Comparison

```python
from collections import OrderedDict

# Create OrderedDicts with same keys but different order
od1 = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
od2 = OrderedDict([('c', 3), ('a', 1), ('b', 2)])

# Order matters for equality - O(n) comparison
print(od1 == od2)  # False (different order)

# Same order - O(n) comparison
od3 = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
print(od1 == od3)  # True

# Regular dict doesn't care about order - O(n)
d = {'a': 1, 'b': 2, 'c': 3}
print(od1 == d)  # True (same keys/values, order ignored)
```

## LRU Cache Pattern

```python
from collections import OrderedDict

class LRUCache:
    """Simple LRU cache using OrderedDict - O(1) operations"""
    
    def __init__(self, capacity):
        self.cache = OrderedDict()  # O(1)
        self.capacity = capacity
    
    def get(self, key):
        """Get value and mark as recently used - O(1)"""
        if key not in self.cache:  # O(1)
            return None
        # Move to end (most recent) - O(1)
        self.cache.move_to_end(key)
        return self.cache[key]  # O(1)
    
    def put(self, key, value):
        """Put value and evict if over capacity - O(1)"""
        if key in self.cache:  # O(1)
            # Update and move to end - O(1)
            self.cache.move_to_end(key)
        self.cache[key] = value  # O(1)
        
        # Evict least recently used if over capacity - O(1)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)  # O(1) - remove first

# Usage
cache = LRUCache(2)
cache.put('a', 1)   # O(1)
cache.put('b', 2)   # O(1)
print(cache.get('a'))  # O(1), marks 'a' as recent
cache.put('c', 3)   # O(1), evicts 'b' (least recent)
```

## Common Patterns

### Preserving Insertion Order

```python
from collections import OrderedDict

# Creating from list of tuples preserves insertion order - O(n)
data = [('name', 'Alice'), ('age', 30), ('city', 'NYC')]
od = OrderedDict(data)  # O(n)

# Iteration order guaranteed - O(n)
for key in od:  # O(n)
    print(f"{key}: {od[key]}")
# Output: name: Alice, age: 30, city: NYC
```

### Deep Copy Preserving Order

```python
from collections import OrderedDict
import copy

# Original OrderedDict - O(n)
od1 = OrderedDict([('a', 1), ('b', 2), ('c', 3)])

# Deep copy preserves order - O(n)
od2 = copy.deepcopy(od1)

# Same order guaranteed
assert list(od1.keys()) == list(od2.keys())
```

### Comparison with Regular Dict

```python
from collections import OrderedDict

# Python 3.7+ - regular dict preserves insertion order
regular_dict = {'a': 1, 'b': 2, 'c': 3}

# OrderedDict also preserves insertion order
ordered_dict = OrderedDict([('a', 1), ('b', 2), ('c', 3)])

# Both maintain insertion order - O(n)
print(list(regular_dict.keys()))  # ['a', 'b', 'c']
print(list(ordered_dict.keys()))  # ['a', 'b', 'c']

# Key difference: OrderedDict has move_to_end() and stricter equality
ordered_dict.move_to_end('a')  # Available in OrderedDict
# regular_dict.move_to_end('a')  # Not available
```

## When to Use OrderedDict

### Good For:
- Backwards compatibility (Python 3.6 and earlier)
- Using `move_to_end()` for LRU/MRU patterns
- Explicit intent to preserve order
- JSON serialization with guaranteed order
- Strict equality based on insertion order

### Not Good For:
- Python 3.7+ without special ordering needs (use `dict`)
- When order doesn't matter (use `dict`)
- Memory-constrained environments
- When you need better performance (regular `dict` is faster)

## Comparison with Alternatives

```python
from collections import OrderedDict, defaultdict

# OrderedDict - for insertion-order preservation
od = OrderedDict([('a', 1), ('b', 2)])  # O(n)
od.move_to_end('a')  # O(1)

# defaultdict - for default values
dd = defaultdict(int)  # O(1)
dd['count'] += 1  # O(1)

# Regular dict - for simplicity in Python 3.7+
d = {'a': 1, 'b': 2}  # O(n)
```

## Version Notes

- **Python 2.7+**: OrderedDict available
- **Python 3.7+**: Regular `dict` maintains insertion order, but OrderedDict still useful for explicit semantics
- **All versions**: O(1) operations for access, insertion, deletion

## Related Modules

- **[dict](../builtins/dict.md)** - Standard dictionary
- **[defaultdict](defaultdict.md)** - Dict with default values
- **[Counter](counter.md)** - Dict subclass for counting
- **[collections](collections.md)** - Container data types

## Best Practices

✅ **Do**:

- Use for backwards compatibility with Python 3.6
- Use for LRU/MRU cache patterns with `move_to_end()`
- Use when strict insertion-order equality matters
- Use for explicit code intent

❌ **Avoid**:

- Using instead of regular `dict` in Python 3.7+ without special needs
- Assuming faster than regular `dict`
- Using for non-ordered operations
- Frequent copying (use references when possible)
