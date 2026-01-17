# Annotationlib Module Complexity

The `annotationlib` module provides tools for introspecting annotations. Added in Python 3.14.

## Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `get_annotations(obj)` | O(n) | O(n) | n = number of annotations; new dict each call |
| `get_annotations(obj, format=STRING)` | O(n) | O(n) | Fastest: no evaluation |
| `get_annotations(obj, format=FORWARDREF)` | O(n) | O(n) | Partial evaluation |
| `get_annotations(obj, format=VALUE)` | O(n) | O(n) | Slowest: full evaluation, may import |
| `call_annotate_function()` | O(n) | O(n) | Calls __annotate__ with format |
| `annotations_to_string()` | O(n) | O(n) | Convert dict values to strings |
| `ForwardRef.evaluate()` | O(1) | O(1) | Resolve single forward reference |

## Performance Characteristics

### No Caching

`get_annotations()` creates a new dict on every call:

```python
from annotationlib import get_annotations

def func(x: int) -> int:
    return x

# O(n) each call - no caching
a1 = get_annotations(func)
a2 = get_annotations(func)
assert a1 is not a2  # Different dict objects

# Cache if calling repeatedly
_cache = {}
def cached_annotations(obj):
    if obj not in _cache:
        _cache[obj] = get_annotations(obj)
    return _cache[obj]
```

### Format Performance Comparison

```python
from annotationlib import get_annotations, Format

# Performance order (fastest to slowest):
# 1. STRING - no evaluation, just string conversion
# 2. FORWARDREF - partial evaluation, unresolved become ForwardRef
# 3. VALUE - full evaluation, may trigger imports

# For display/docs: use STRING (fastest)
get_annotations(obj, format=Format.STRING)

# For inspection with possible undefined names: use FORWARDREF
get_annotations(obj, format=Format.FORWARDREF)

# Only when you need actual type objects: use VALUE (slowest)
get_annotations(obj, format=Format.VALUE)
```

### Deferred Evaluation Impact (PEP 649)

```python
# Python 3.14+: Annotations NOT evaluated at definition
# This means import time is faster for heavily-annotated modules

class HeavilyAnnotated:
    a: ComplexType1
    b: ComplexType2
    # ...100 more annotations...
    
# 3.13: All 100+ types evaluated at class definition (slow import)
# 3.14: Evaluated only when get_annotations() called (fast import)
```

## Version Notes

- **Python 3.14+**: Module introduced (PEP 749)
- **Python 3.14+**: Deferred annotation evaluation default (PEP 649)

## Related Documentation

- [Typing Module](typing.md)
- [Inspect Module](inspect.md)
- [Python 3.14](../versions/py314.md)
