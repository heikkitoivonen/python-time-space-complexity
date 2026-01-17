# Annotationlib Module Complexity

The `annotationlib` module provides tools for introspecting annotations on modules, classes, and functions. Added in Python 3.14.

## Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `get_annotations(obj)` | O(n) | O(n) | n = number of annotations |
| `get_annotations(obj, format=STRING)` | O(n) | O(n) | String format, no evaluation |
| `get_annotations(obj, format=FORWARDREF)` | O(n) | O(n) | Returns ForwardRef for unresolved |
| `call_annotate_function()` | O(n) | O(n) | Calls annotate with format |
| `annotations_to_string()` | O(n) | O(n) | Convert annotations dict to strings |
| `type_repr()` | O(1) | O(1) | String representation of type |

## Format Enum

```python
from annotationlib import Format

# Three formats for retrieving annotations
Format.VALUE       # Evaluate annotations (may raise errors)
Format.FORWARDREF  # Return ForwardRef for unresolved names
Format.STRING      # Return as strings (like source code)
```

## get_annotations()

### Time Complexity: O(n)

Where n = number of annotations on the object.

```python
from annotationlib import get_annotations, Format

def greet(name: str, count: int) -> str:
    return name * count

# Get evaluated annotations - O(n)
annot = get_annotations(greet, format=Format.VALUE)
# {'name': <class 'str'>, 'count': <class 'int'>, 'return': <class 'str'>}

# Get as strings (no evaluation) - O(n)
annot_str = get_annotations(greet, format=Format.STRING)
# {'name': 'str', 'count': 'int', 'return': 'str'}
```

### Space Complexity: O(n)

Returns a new dict on each call.

## Forward References

```python
from annotationlib import get_annotations, Format, ForwardRef

class Node:
    # Self-reference before class is fully defined
    def set_next(self, node: "Node") -> None:
        pass

# VALUE format may fail with undefined names
# FORWARDREF returns ForwardRef objects instead
annot = get_annotations(Node.set_next, format=Format.FORWARDREF)
# {'node': ForwardRef('Node'), 'return': <class 'NoneType'>}
```

## ForwardRef Class

```python
from annotationlib import ForwardRef

ref = ForwardRef("SomeClass")

# Attributes
ref.__forward_arg__   # 'SomeClass' - the string being referenced
ref.__forward_module__  # Module where reference was created

# Evaluate when the name is available
ref.evaluate(globals={'SomeClass': MyClass})  # O(1)
```

## Deferred Evaluation (PEP 649)

Python 3.14 changes annotation semantics:

```python
# Before 3.14: Annotations evaluated at definition time
# Python 3.14+: Annotations evaluated lazily when accessed

class Example:
    value: UndefinedType  # No error until annotations accessed!

# Accessing annotations triggers evaluation
# get_annotations(Example)  # Would raise NameError
```

## Performance Considerations

### Caching

`get_annotations()` does NOT cache results:

```python
from annotationlib import get_annotations

def func(x: int) -> int:
    return x

# Each call creates new dict - O(n) each time
a1 = get_annotations(func)
a2 = get_annotations(func)
assert a1 is not a2  # Different objects

# Cache yourself if calling repeatedly
_cache = {}
def get_cached_annotations(obj):
    if obj not in _cache:
        _cache[obj] = get_annotations(obj)
    return _cache[obj]
```

### Format Performance

```python
from annotationlib import get_annotations, Format

# STRING is fastest (no evaluation)
# FORWARDREF is middle (partial evaluation)
# VALUE is slowest (full evaluation, may import modules)

# Use STRING for display/documentation
annot = get_annotations(func, format=Format.STRING)

# Use FORWARDREF when names may not exist
annot = get_annotations(func, format=Format.FORWARDREF)

# Use VALUE only when you need actual type objects
annot = get_annotations(func, format=Format.VALUE)
```

## Version Notes

- **Python 3.14+**: Module introduced (PEP 749)
- **Python 3.14+**: Deferred annotation evaluation default (PEP 649)

## Related Documentation

- [Typing Module](typing.md)
- [Inspect Module](inspect.md)
- [Python 3.14](../versions/py314.md)
