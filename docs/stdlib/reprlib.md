# reprlib Module

The `reprlib` module provides an alternative repr() implementation that produces more readable representations of objects, especially useful for long lists or nested structures.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `repr()` | O(k) | O(k) | k = items/chars visited up to limits |
| Truncation | O(k) | O(1) | Limit reduces traversal/output, not O(1) |

## Creating Readable Representations

### Truncating Long Outputs

```python
import reprlib

# Create repr with limits - O(n)
repr_obj = reprlib.Repr()
repr_obj.maxlist = 3  # Max list items
repr_obj.maxstring = 20  # Max string length

# Generate representation - O(n)
long_list = list(range(100))
result = repr_obj.repr(long_list)
print(result)
# [0, 1, 2, ...]

long_string = "x" * 1000
result = repr_obj.repr(long_string)
print(result)
# 'xxxxxxxxxxxxxxxxxxxx'...
```

### Default Shorthand

```python
import reprlib

# Using default repr - O(n)
large_dict = {i: i**2 for i in range(1000)}
print(reprlib.repr(large_dict))
# {0: 0, 1: 1, 2: 4, ...}
```

## Related Documentation

- [pprint Module](pprint.md)
