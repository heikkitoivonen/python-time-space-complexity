# reprlib Module

The `reprlib` module provides an alternative repr() implementation that produces more readable representations of objects, especially useful for long lists or nested structures.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `repr()` on `list`/`tuple`/`deque`/`array`/`str` | O(min(n, k)) | O(k) | n = input size, k = the relevant `max*`/`maxstring` limit. |
| `repr()` on `dict`/`set`/`frozenset` | O(n) best, O(n log n) worst | O(n + k) |  |
| `recursive_repr()` | O(1) | O(1) |  |


## Creating Readable Representations

### Truncating Long Outputs

```python
import reprlib

# Create repr with limits - O(1)
repr_obj = reprlib.Repr()
repr_obj.maxlist = 3  # Max list items
repr_obj.maxstring = 20  # Max string length

# Generate representation - O(min(n, k)); a fixed maxlist=3 means this
# would cost the same for a list of 100 or 100 million items
long_list = list(range(100))
result = repr_obj.repr(long_list)
print(result)
# [0, 1, 2, ...]

long_string = "x" * 1000
result = repr_obj.repr(long_string)
print(result)
# 'xxxxxxx...xxxxxxxx'
```

### Default Shorthand

```python
import reprlib

# Using default repr - the whole dict is sorted before the output is
# truncated, so maxdict does not bound the work. O(n) for this dict, whose
# keys are already ascending; scattered keys would make it O(n log n)
large_dict = {i: i**2 for i in range(1000)}
print(reprlib.repr(large_dict))
# {0: 0, 1: 1, 2: 4, 3: 9, ...}
```

### Guarding Against Recursive Structures

```python
import reprlib


class Node:
    def __init__(self):
        self.child = None

    @reprlib.recursive_repr("<...>")
    def __repr__(self):
        return f"Node({self.child!r})"


node = Node()
node.child = node  # a cycle: without the decorator this recurses forever

print(repr(node))
# Node(<...>)
```

## Related Documentation

- [pprint Module](pprint.md)
- [Functools Module](functools.md) - re-exports `recursive_repr` for its own `partial.__repr__`
