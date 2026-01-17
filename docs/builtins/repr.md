# repr() Function Complexity

The `repr()` function returns a printable representation of an object.

## Complexity Analysis

| Type | Time | Space | Notes |
|------|------|-------|-------|
| Primitive (int, float) | O(1) | O(1) | Direct conversion |
| String | O(n) | O(n) | n = string length; escapes special chars |
| Container (list, dict, set) | O(n) | O(n) | n = number of elements |
| Nested container | O(n) | O(n) | Recursively converts all items |
| String with escapes | O(n) | O(n) | n = string length |
| Custom object | O(1)* | O(1)* | Depends on `__repr__` implementation |

## Basic Usage

### Primitives

```python
# O(1) - simple conversions
repr(42)           # '42'
repr(3.14)         # '3.14'
repr(True)         # 'True'
repr(None)         # 'None'
```

### Strings

```python
# O(n) - where n = string length
repr("hello")      # "'hello'"
repr('test')       # "'test'"

# With special characters - escapes added
repr("hello\nworld")  # "'hello\\nworld'"
repr('quote\'test')   # '"quote\'test"'
repr("\t\n\r")       # "'\\t\\n\\r'"
```

### Collections

```python
# O(n) - n = number of elements
repr([1, 2, 3])         # '[1, 2, 3]'
repr((1, 2, 3))         # '(1, 2, 3)'
repr({1, 2, 3})         # '{1, 2, 3}' (order may vary)
repr({'a': 1, 'b': 2})  # "{'a': 1, 'b': 2}"
```

### Nested Structures

```python
# O(n) - recursively converts all items
nested = [[1, 2], [3, 4]]
repr(nested)  # O(4) - 4 elements

# O(n*m) for deeply nested structures
deep = [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
repr(deep)  # Recursively process all levels
```

## Performance Patterns

### String Representation Building

```python
# O(n) - builds complete string representation
lst = list(range(1000))
repr_str = repr(lst)  # O(1000) - must convert all

# Compare with str()
str_repr = str(lst)   # O(1000) - similar cost
```

### Custom Object Representations

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __repr__(self):
        # O(1) - simple string format
        return f"Point({self.x}, {self.y})"

# O(1) - fixed-size representation
p = Point(1, 2)
repr(p)  # "Point(1, 2)"

# Inefficient custom repr
class BadPoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __repr__(self):
        # O(n) - unnecessary processing
        values = [self.x, self.y]
        items = [repr(v) for v in values]  # Extra work
        return f"BadPoint({', '.join(items)})"

p = BadPoint(1, 2)
repr(p)  # O(n) - extra processing for no gain
```

### Collections with Custom Objects

```python
# O(n) - calls __repr__ for each element
class Item:
    def __init__(self, value):
        self.value = value
    
    def __repr__(self):
        return f"Item({self.value})"

items = [Item(i) for i in range(10)]
repr(items)  # O(10) - calls __repr__ on each item
```

## Difference from str()

```python
# str() - human-readable, may be different
class Value:
    def __str__(self):
        return "A nice value"
    
    def __repr__(self):
        return "Value()"

v = Value()
print(str(v))   # "A nice value"
print(repr(v))  # "Value()"

# repr() should return valid Python code if possible
x = 42
assert eval(repr(x)) == x  # True for most cases

s = "hello"
assert eval(repr(s)) == s  # True - repr() is evaluable
```

## String Escaping

```python
# O(n) - escapes special characters
# n = string length

# Simple string
repr("hello")        # "'hello'"

# String with quotes
repr('It\'s here')   # '"It\'s here"'

# String with newlines
repr("line1\nline2") # "'line1\\nline2'"

# String with tabs
repr("\ttab")        # "'\\ttab'"

# Unicode characters
repr("café")         # "'café'" (or "'caf\\xe9'" depending on encoding)
repr("🎵")          # "'🎵'"
```

## Common Patterns

### Debugging Output

```python
# O(n) - get detailed object information
data = {"name": "Alice", "age": 30, "scores": [85, 90, 88]}
print(repr(data))  # Complete, evaluable representation
# Output: {'name': 'Alice', 'age': 30, 'scores': [85, 90, 88]}

# vs str() - might be more concise
print(str(data))   # Same in this case, may differ for custom objects
```

### Logging

```python
# O(n) - full object representation for logging
import logging

obj = [1, 2, 3, {"key": "value"}]
logging.debug(f"Object: {repr(obj)}")  # Full details

# Better for debugging than str()
```

### Error Messages

```python
# O(n) - include full representation
def process(value):
    if not isinstance(value, int):
        raise TypeError(f"Expected int, got {repr(value)}")

process("string")  # TypeError: Expected int, got 'string'
```

## Edge Cases

### Circular References

```python
# O(n) - detects and handles circular references
lst = [1, 2, 3]
lst.append(lst)

# repr() shows [1, 2, 3, [...]]
print(repr(lst))  # [1, 2, 3, [...]]

# Dictionary with circular reference
dct = {'a': 1}
dct['self'] = dct
# This still works, showing {...}
```

### Large Collections

```python
# O(n) - but result string can be very large
huge_list = list(range(10000))
repr_str = repr(huge_list)
# String is very long, memory intensive

# Consider limiting output for display
repr_str = repr(huge_list)[:100] + "..."  # Truncate
```

### Special Numeric Values

```python
# O(1) - special cases
repr(float('inf'))      # 'inf'
repr(float('-inf'))     # '-inf'
repr(float('nan'))      # 'nan'

# Complex numbers
repr(1+2j)              # '(1+2j)'
```

## Performance Considerations

### vs format()

```python
# repr() - O(n), full representation
repr([1, 2, 3])

# format() - O(n), depends on format spec
format([1, 2, 3])  # Same complexity usually

# format() with custom spec - may differ
class Custom:
    def __format__(self, spec):
        return "custom"
    
    def __repr__(self):
        return "Custom()"

c = Custom()
repr(c)      # "Custom()"
format(c)    # "custom"
```

### Bulk Operations

```python
# O(n) - each repr() call
items = list(range(1000))
reprs = [repr(item) for item in items]  # O(1000)

# vs building repr of whole list
single_repr = repr(items)  # O(1000) - same complexity

# But collecting reprs lets you customize each
```

## Best Practices

✅ **Do**:
- Use `repr()` for debugging and logging
- Implement `__repr__()` to return evaluable code when possible
- Use `repr()` in error messages for clarity
- Let `repr()` handle string escaping

❌ **Avoid**:
- Assuming `repr()` will always be evaluable (it may not be for all objects)
- Using `repr()` for user-facing output (use `str()` instead)
- Implementing expensive `__repr__()` methods
- Calling `repr()` on very large collections repeatedly without caching

## Related Functions

- **[str()](str.md)** - Convert to human-readable string
- **[format()](format.md)** - Format strings with specifications
- **[ascii()](ascii.md)** - ASCII-safe representation
- **[print()](print.md)** - Print objects to output

## Version Notes

- **Python 2.x**: `repr()` and `str()` may behave differently
- **Python 3.x**: Consistent Unicode support in `repr()`
- **All versions**: `repr()` should aim to return valid Python code
