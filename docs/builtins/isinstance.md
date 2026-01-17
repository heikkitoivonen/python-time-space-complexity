# isinstance() Function Complexity

The `isinstance()` function checks whether an object is an instance of a class or a tuple of classes, following inheritance relationships.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `isinstance(obj, type)` | O(d) | O(1) | d = MRO depth; effectively O(1) for typical hierarchies |
| `isinstance(obj, (type1, type2, ...))` | O(k*d) | O(1) | k = number of types; short-circuits on first match |
| `isinstance(obj, abstract_base)` | O(d) to O(n) | O(1) | Depends on ABC __subclasshook__ implementation |

## Basic Type Checking

### Simple Type Checks

```python
# Single type - O(1)
x = 42
isinstance(x, int)           # True - O(1)
isinstance(x, str)           # False - O(1)
isinstance(x, (int, float))  # True - O(2)

# Works with built-in types
isinstance([1, 2], list)     # True - O(1)
isinstance({'a': 1}, dict)   # True - O(1)
isinstance((1, 2), tuple)    # True - O(1)
```

### Tuple of Types

```python
# Multiple types - O(k) where k = number of types
numeric_types = (int, float, complex)
isinstance(42, numeric_types)           # True - O(3)
isinstance(3.14, numeric_types)         # True - O(3)
isinstance("3.14", numeric_types)       # False - O(3)

# Checking against all sequence types - O(k)
sequence_types = (list, tuple, range, str, bytes)
isinstance([1, 2, 3], sequence_types)   # True - O(5)
```

## Inheritance Checking

### Class Hierarchies

```python
# Define class hierarchy - O(1)
class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass

# Check inheritance - O(1)
dog = Dog()
isinstance(dog, Dog)      # True - O(1)
isinstance(dog, Animal)   # True - O(1) - follows inheritance
isinstance(dog, Cat)      # False - O(1)

# Check against base class
isinstance(dog, (Dog, Cat))  # True - O(2)
```

### Deep Inheritance Chains

```python
# Multi-level inheritance - O(1)
class A: pass
class B(A): pass
class C(B): pass
class D(C): pass

obj = D()
isinstance(obj, D)  # True - O(1)
isinstance(obj, A)  # True - O(1) - checks up the chain

# Multiple base classes (MRO) - O(1)
class X: pass
class Y: pass
class Z(X, Y): pass

z = Z()
isinstance(z, X)  # True - O(1)
isinstance(z, Y)  # True - O(1)
```

## Common Patterns

### Type-based Dispatching

```python
# Dispatch based on type - O(k) for checking, O(1) for dispatch
def process(obj):
    if isinstance(obj, int):
        return obj * 2  # O(1)
    elif isinstance(obj, str):
        return obj.upper()  # O(n) for string
    elif isinstance(obj, list):
        return len(obj)  # O(1)
    else:
        return None  # O(1)

# Total complexity: O(k) checks + O(operation complexity)
```

### Batch Type Checking

```python
# Check multiple items against types - O(n*k)
items = [1, "hello", 3.14, None, [1, 2]]
numeric_types = (int, float)

# Count numeric items - O(n*k)
count = sum(1 for item in items if isinstance(item, numeric_types))
# 2 items are numeric - O(5 * 2) = O(10)
```

### Filtering by Type

```python
# Filter items by type - O(n*k)
items = [1, "a", 2, "b", 3, "c"]
strings = [item for item in items if isinstance(item, str)]
# O(6 * 1) = O(6)

numbers = [item for item in items if isinstance(item, (int, float))]
# O(6 * 2) = O(12)
```

## Built-in Type Checking

### All Built-in Types

```python
# isinstance() works with all built-in types - O(1) each
isinstance(42, int)              # True
isinstance(3.14, float)          # True
isinstance("hello", str)         # True
isinstance([1, 2, 3], list)      # True
isinstance((1, 2), tuple)        # True
isinstance({1, 2, 3}, set)       # True
isinstance({'a': 1}, dict)       # True
isinstance(b'bytes', bytes)      # True
isinstance(True, bool)           # True
isinstance(True, int)            # True - bool is subclass of int!

# Check multiple built-in types
isinstance(42, (int, float))     # True - O(2)
isinstance("hello", (str, bytes))  # True - O(2)
```

### Important Relationship: bool is int

```python
# bool is a subclass of int - important!
isinstance(True, bool)           # True - O(1)
isinstance(True, int)            # True - O(1) - bool inherits from int
isinstance(1, bool)              # False - O(1) - int is not necessarily bool

# This matters in type checking
def check_bool_only(value):
    return isinstance(value, bool)  # O(1) - stricter check

def check_int_like(value):
    return isinstance(value, int)   # O(1) - includes bool!
```

## Abstract Base Classes (ABCs)

### Standard ABCs

```python
from collections.abc import Sequence, Mapping, Iterable

# ABC checking - O(1) typically
numbers = [1, 2, 3]
isinstance(numbers, Sequence)  # True - O(1)

d = {'a': 1}
isinstance(d, Mapping)         # True - O(1)

# Works with iterables
gen = (x for x in range(10))
isinstance(gen, Iterable)      # True - O(1)

# Check strings
isinstance("hello", Sequence)  # True - O(1)
isinstance("hello", str)       # True - O(1)
```

### Custom ABC Implementation

```python
from abc import ABC, abstractmethod

# Define custom ABC - O(1)
class DataProcessor(ABC):
    @abstractmethod
    def process(self, data):
        pass

class ListProcessor(DataProcessor):
    def process(self, data):
        return [x * 2 for x in data]

# Check against ABC - O(1)
proc = ListProcessor()
isinstance(proc, DataProcessor)     # True
isinstance(proc, DataProcessor.__subclasses__())  # O(subclasses)
```

## Performance Considerations

### Tuple vs Multiple isinstance Calls

```python
# Option 1: Single isinstance with tuple - O(k)
result = isinstance(obj, (int, float, complex, bool))  # O(4)

# Option 2: Multiple isinstance calls - O(k)
result = (isinstance(obj, int) or 
          isinstance(obj, float) or 
          isinstance(obj, complex) or
          isinstance(obj, bool))  # O(4) - short-circuits

# Same complexity but tuple is cleaner
```

### Avoid Expensive Checks in Loops

```python
# Bad: Check complex ABC in loop - O(n*k)
def is_valid_items(items):
    from collections.abc import Sequence
    for item in items:
        if not isinstance(item, Sequence):  # O(k) per item
            return False
    return True
# Total: O(n*k)

# Better: Check once, then iterate
def is_valid_items(items):
    if not isinstance(items, list):  # O(1)
        return False
    for item in items:
        # Process without checking
        process(item)  # O(1)
    return True
# Total: O(n)
```

### isinstance vs type()

```python
# isinstance checks inheritance - O(1)
class Animal: pass
class Dog(Animal): pass
dog = Dog()

isinstance(dog, Animal)  # True - checks inheritance
type(dog) is Animal      # False - exact type only
type(dog) is Dog         # True

# isinstance is preferred for flexibility
# type() is O(1) and exact, but less flexible
```

## Special Cases

### None Type

```python
# Check for None - O(1)
value = None
isinstance(value, type(None))  # True
isinstance(value, object)      # True - everything inherits from object

# Or use direct comparison
value is None  # True - preferred way for None
```

### Union Type Hints

```python
# Type hints don't affect isinstance behavior
def process(value: int | str):
    if isinstance(value, int):  # O(1)
        return value * 2
    elif isinstance(value, str):  # O(1)
        return value.upper()

# isinstance still O(1) per check
```

### isinstance with Generic Types

```python
from typing import List, Dict

# Generic types don't work directly with isinstance
lst = [1, 2, 3]
# isinstance(lst, List[int])  # TypeError

# Must use non-parameterized type
isinstance(lst, list)  # True - O(1)

# For runtime checking, use typing.get_args() - O(1)
import typing
if isinstance(lst, list):  # O(1)
    element_type = typing.get_args(List[int])  # O(1)
```

## Version Notes

- **Python 2.x**: Works with old-style and new-style classes
- **Python 3.x**: All classes are new-style, consistent behavior
- **Python 3.10+**: `isinstance()` can accept `|` union syntax in type hints (no change to isinstance performance)

## Related Functions

- **[issubclass()](builtins/issubclass.md)** - Check class inheritance (O(1))
- **[type()](builtins/type.md)** - Get exact type (O(1))
- **[callable()](builtins/callable.md)** - Check if callable (O(1))

## Best Practices

✅ **Do**:
- Use `isinstance(obj, (type1, type2))` for multiple types
- Use ABCs for flexible type checking
- Use `isinstance()` for inheritance-aware type checking
- Cache expensive type checks

❌ **Avoid**:
- `type(obj) is SomeType` for inheritance (doesn't follow inheritance)
- Expensive ABC checks in tight loops
- Checking against too many types at once (long tuples)
- Assuming `isinstance()` works with parameterized generics like `List[int]`
