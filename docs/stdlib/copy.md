# copy Module Complexity

The `copy` module provides shallow and deep copy operations for creating copies of objects.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copy.copy(x)` | O(n) | O(n) | Shallow copy, n = top-level elements |
| `copy.deepcopy(x)` | O(n) | O(n) | Deep copy, n = total objects; uses memo dict for cycles |
| Shallow copy (list/dict) | O(n) | O(n) | Copies references only |
| Deep copy (list/dict) | O(n*m) | O(n*m) | Recursively copies nested structures |

## Shallow vs Deep Copy

### Shallow Copy - O(n)

```python
import copy

# Original list with nested structure
original = [[1, 2], [3, 4]]

# Shallow copy - O(n), only top level copied
shallow = copy.copy(original)

# Modify nested element
shallow[0][0] = 999
print(original)   # [[999, 2], [3, 4]] - AFFECTED!
print(shallow)    # [[999, 2], [3, 4]]
```

### Deep Copy - O(n*m)

```python
import copy

# Original list with nested structure
original = [[1, 2], [3, 4]]

# Deep copy - O(n*m), recursively copies all
deep = copy.deepcopy(original)

# Modify nested element
deep[0][0] = 999
print(original)   # [[1, 2], [3, 4]] - NOT affected
print(deep)       # [[999, 2], [3, 4]]
```

## Common Operations

### Copy Simple Types

```python
import copy

# Strings - shallow and deep are same
s = "hello"
s_copy = copy.copy(s)      # O(n)
s_deep = copy.deepcopy(s)  # O(n)

# Numbers - shallow and deep are same
n = 42
n_copy = copy.copy(n)      # O(1)
n_deep = copy.deepcopy(n)  # O(1)

# Immutable types: shallow copy is usually sufficient
```

### Copy Collections

```python
import copy

# List shallow copy - O(n)
list_orig = [1, 2, 3]
list_copy = copy.copy(list_orig)  # O(3)

# Dict shallow copy - O(n)
dict_orig = {'a': 1, 'b': 2}
dict_copy = copy.copy(dict_orig)  # O(2)

# Set shallow copy - O(n)
set_orig = {1, 2, 3}
set_copy = copy.copy(set_orig)    # O(3)
```

### Copy Custom Objects

```python
import copy

class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

original = Person("Alice", 30)

# Shallow copy - creates new object, same attributes
shallow = copy.copy(original)     # O(1) for simple attributes
shallow.name = "Bob"
print(original.name)  # "Alice" - not affected

# Deep copy - recursively copies attributes
deep = copy.deepcopy(original)    # O(n) based on attribute depth
```

### Copy Nested Structures

```python
import copy

# Nested lists
nested = [[1, 2, 3], [4, 5, 6], {'key': [7, 8]}]

# Shallow copy - O(n) where n = 3 (top level)
shallow = copy.copy(nested)       # O(3)

# Deep copy - O(n*m) where n = total elements, m = depth
deep = copy.deepcopy(nested)      # O(n*m)
```

## Performance Comparison

### Shallow Copy Methods

```python
import copy

data = list(range(1000))

# Method 1: copy.copy() - O(n)
copy1 = copy.copy(data)           # O(1000)

# Method 2: list() constructor - O(n)
copy2 = list(data)                # O(1000)

# Method 3: slicing [:] - O(n)
copy3 = data[:]                   # O(1000)

# All are O(n), roughly equivalent performance
```

### Deep Copy Performance

```python
import copy
import time

# Create nested structure
nested = [list(range(100)) for _ in range(100)]

# Deepcopy - O(n*m)
start = time.time()
deep = copy.deepcopy(nested)      # O(10000) for 100*100
elapsed = time.time() - start

# Much slower than shallow copy for nested structures
```

## Copy Hooks

### Custom Copy Behavior

```python
import copy

class CustomObject:
    def __init__(self, data):
        self.data = data
        self.metadata = {'created': True}
    
    # Called by copy.copy()
    def __copy__(self):
        return CustomObject(self.data)  # Shallow copy
    
    # Called by copy.deepcopy()
    def __deepcopy__(self, memo):
        new_obj = CustomObject(copy.deepcopy(self.data, memo))
        new_obj.metadata = copy.deepcopy(self.metadata, memo)
        return new_obj

obj = CustomObject([1, 2, 3])
obj_copy = copy.copy(obj)          # Uses __copy__
obj_deep = copy.deepcopy(obj)      # Uses __deepcopy__
```

### Handling Circular References

```python
import copy

# Circular reference
circular = [1, 2, 3]
circular.append(circular)  # Points to itself

# deepcopy handles circular references with memo dict
deep = copy.deepcopy(circular)  # Works! Prevents infinite recursion
print(deep[3] is deep)  # True - points to new copy
```

## When to Use

### Use Shallow Copy When
- Copying simple types (strings, numbers, tuples)
- Top-level elements are immutable
- Performance is critical
- Memory constraints exist

```python
import copy

# Good use of shallow copy
config = {'timeout': 30, 'retries': 3}
backup = copy.copy(config)  # O(n)
```

### Use Deep Copy When
- Nested mutable structures exist
- Complete independence needed
- Modifying copies shouldn't affect original
- Complex object graphs with references

```python
import copy

# Need deep copy
data = {
    'users': [
        {'name': 'Alice', 'tags': ['admin']},
        {'name': 'Bob', 'tags': ['user']}
    ]
}
backup = copy.deepcopy(data)  # O(n*m) - independent copy
```

## Alternatives to copy

### Use Collection Constructors (Often Faster)

```python
# Shallow copy alternatives
lst = [1, 2, 3]
copy1 = list(lst)        # Slightly faster than copy.copy()
copy2 = lst[:]           # Also works
copy3 = lst.copy()       # Python 3.3+, similar performance
```

### Manual Copying for Control

```python
# When you need custom behavior
original = {'a': 1, 'b': [2, 3]}

# Selective shallow copy
custom = {k: v for k, v in original.items()}

# Selective deep copy
import copy
custom_deep = {k: copy.deepcopy(v) if isinstance(v, list) else v 
               for k, v in original.items()}
```

## Performance Notes

### Time Complexity
- **Shallow copy**: O(n) where n = number of top-level elements
- **Deep copy**: O(n*m) where n = total objects, m = average depth
- **Circular references**: Still O(n*m), memo dict tracks visited objects

### Space Complexity
- **Shallow copy**: O(n) for new container
- **Deep copy**: O(n*m) for all new objects and references

### CPython Implementation
- Uses `__copy__` and `__deepcopy__` methods
- Memo dictionary prevents infinite recursion
- Highly optimized for common types

## Related Documentation

- [List](../builtins/list.md)
- [Dict](../builtins/dict.md)
- [Pickle Module](pickle.md)
- [Functools Module](functools.md)
