# isinstance() Function Complexity

The `isinstance()` function checks whether an object is an instance of a class or a tuple of classes, following inheritance relationships.

`d` is the length of the object's MRO, `len(type(obj).__mro__)`, and `k` is the classes in a tuple or `|` union. For an abstract base class, `g` is the registration and subclass links the ABC can reach, followed recursively, as defined on the [abc page](../stdlib/abc.md); a `__subclasshook__` is priced at O(d), as the default and `collections.abc` hooks are.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `isinstance(obj, type)` | O(d) | O(1) | O(1) when `type(obj)` is exactly the class; otherwise scans the MRO, so a `False` answer walks all of it |
| `isinstance(obj, (type1, type2, ...))` | O(k*d) | O(1) | Checks the classes in order and stops at the first match; an ABC or hooked entry costs as in its own row |
| `isinstance(obj, type1 \| type2)` | O(k*d) | O(1) | Checked as the tuple of the union's members |
| `isinstance(obj, abstract_base)`: first check of a class | O(g*d) | O(g) | Walks the ABC's registered classes and subclasses recursively, testing `type(obj)`'s MRO at each, and caches the answer |
| `isinstance(obj, abstract_base)`: cached | O(1) | O(1) | A positive answer stays cached; a negative one only until any ABC registers a new virtual subclass |
| `isinstance(obj, cls)` with a custom `__instancecheck__` | Cost of the hook | Cost of the hook | The metaclass method decides the answer, except that an object whose type is exactly the class matches in O(1) without calling it |

## Basic Type Checking

### Simple Type Checks

```python
# Single type - O(1) on an exact type match
x = 42
assert isinstance(x, int)            # O(1) - exact type
assert not isinstance(x, str)        # O(d) - scans int's MRO
assert isinstance(x, (int, float))   # O(1) - first entry matches exactly

# Works with built-in types
assert isinstance([1, 2], list)      # O(1)
assert isinstance({'a': 1}, dict)    # O(1)
assert isinstance((1, 2), tuple)     # O(1)
```

### Tuple of Types

```python
# Multiple types - O(k*d), stops at the first match
numeric_types = (int, float, complex)
assert isinstance(42, numeric_types)          # matches the 1st entry
assert isinstance(3.14, numeric_types)        # matches the 2nd entry
assert not isinstance("3.14", numeric_types)  # checks all k = 3

# Checking against all sequence types - O(k*d)
sequence_types = (list, tuple, range, str, bytes)
assert isinstance([1, 2, 3], sequence_types)  # matches the 1st entry
```

## Inheritance Checking

### Class Hierarchies

```python
# Define class hierarchy
class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass

# Check inheritance - O(d), d = 3 for Dog: Dog, Animal, object
dog = Dog()
assert isinstance(dog, Dog)          # O(1) - exact type
assert isinstance(dog, Animal)       # O(d) - follows inheritance
assert not isinstance(dog, Cat)      # O(d) - walks the whole MRO

# Check against a tuple of classes
assert isinstance(dog, (Dog, Cat))   # O(1) - first entry matches exactly
```

### Deep Inheritance Chains

```python
# Multi-level inheritance - O(d), d = 5 for D
class A: pass
class B(A): pass
class C(B): pass
class D(C): pass

obj = D()
assert len(D.__mro__) == 5    # D, C, B, A, object
assert isinstance(obj, D)     # O(1) - exact type
assert isinstance(obj, A)     # O(d) - scans up the MRO

# Multiple base classes - the MRO holds every base
class X: pass
class Y: pass
class Z(X, Y): pass

z = Z()
assert len(Z.__mro__) == 4    # Z, X, Y, object
assert isinstance(z, X)       # O(d)
assert isinstance(z, Y)       # O(d)
```

## Common Patterns

### Type-based Dispatching

```python
# Dispatch based on type - each branch adds one isinstance() check
def process(obj):
    if isinstance(obj, int):
        return obj * 2
    elif isinstance(obj, str):
        return obj.upper()  # O(len(obj))
    elif isinstance(obj, list):
        return len(obj)  # O(1)
    else:
        return None

assert process(21) == 42
assert process("hi") == "HI"
assert process([1, 2]) == 2
assert process(None) is None
# Total: one check per branch tried, plus the branch's own work
```

### Batch Type Checking

```python
# Check multiple items against types - O(n*k*d) for n items
items = [1, "hello", 3.14, None, [1, 2]]
numeric_types = (int, float)

count = sum(1 for item in items if isinstance(item, numeric_types))
assert count == 2  # 1 and 3.14
```

### Filtering by Type

```python
# Filter items by type - O(n*k*d) for n items
items = [1, "a", 2, "b", 3, "c"]
strings = [item for item in items if isinstance(item, str)]
assert strings == ["a", "b", "c"]

numbers = [item for item in items if isinstance(item, (int, float))]
assert numbers == [1, 2, 3]
```

## Built-in Type Checking

### All Built-in Types

```python
# isinstance() works with all built-in types - O(1) on an exact match
assert isinstance(42, int)
assert isinstance(3.14, float)
assert isinstance("hello", str)
assert isinstance([1, 2, 3], list)
assert isinstance((1, 2), tuple)
assert isinstance({1, 2, 3}, set)
assert isinstance({'a': 1}, dict)
assert isinstance(b'bytes', bytes)
assert isinstance(True, bool)
assert isinstance(True, int)              # bool is a subclass of int!

# Check multiple built-in types
assert isinstance(42, (int, float))
assert isinstance("hello", (str, bytes))
```

### Important Relationship: bool is int

```python
# bool is a subclass of int - important!
assert isinstance(True, bool)           # O(1) - exact type
assert isinstance(True, int)            # O(d) - bool inherits from int
assert not isinstance(1, bool)          # an int is not a bool

# This matters in type checking
def check_bool_only(value):
    return isinstance(value, bool)  # stricter check

def check_int_like(value):
    return isinstance(value, int)   # includes bool!

assert not check_bool_only(1)
assert check_int_like(True)
```

## Abstract Base Classes (ABCs)

### Standard ABCs

An ABC answers through its `__instancecheck__`, which caches the answer per class. The first check of a class walks the ABC's registered classes and subclasses, O(g*d); a repeat check of the same class is a set lookup, O(1).

```python
from collections.abc import Sequence, Mapping, Iterable

# First check of each class - O(g*d); repeats - O(1)
numbers = [1, 2, 3]
assert isinstance(numbers, Sequence)

d = {'a': 1}
assert isinstance(d, Mapping)

# Works with iterables
gen = (x for x in range(10))
assert isinstance(gen, Iterable)

# Check strings
assert isinstance("hello", Sequence)
assert isinstance("hello", str)       # O(1) - exact type
```

### Custom ABC Implementation

```python
from abc import ABC, abstractmethod

class DataProcessor(ABC):
    @abstractmethod
    def process(self, data):
        pass

class ListProcessor(DataProcessor):
    def process(self, data):
        return [x * 2 for x in data]

# Check against ABC - O(g*d) the first time, then O(1) from its cache
proc = ListProcessor()
assert isinstance(proc, DataProcessor)
assert isinstance(proc, DataProcessor)  # cached

# A tuple, never a list, of classes
assert isinstance(proc, tuple(DataProcessor.__subclasses__()))  # O(k*d)
```

## Performance Considerations

### Tuple vs Multiple isinstance Calls

```python
obj = 2.5

# Option 1: Single isinstance with tuple - O(k*d)
result = isinstance(obj, (int, float, complex))

# Option 2: Multiple isinstance calls - O(k*d), short-circuits
result2 = (isinstance(obj, int) or
           isinstance(obj, float) or
           isinstance(obj, complex))

# Same complexity and answer, but the tuple is cleaner
assert result is result2 is True
```

### Negative ABC Checks and Registration

A negative ABC answer stays cached only until any ABC anywhere registers a virtual subclass. Code that calls `register()` while it runs negative checks pays the O(g*d) walk again after each registration; registering everything up front keeps repeat checks at O(1).

```python
from abc import ABC
from collections.abc import Sequence

class Point:
    pass

p = Point()
assert not isinstance(p, Sequence)  # O(g*d) - first check of Point
assert not isinstance(p, Sequence)  # O(1) - cached negative answer

class Plugin(ABC):
    pass

Plugin.register(Point)              # invalidates every ABC's negative answers
assert not isinstance(p, Sequence)  # O(g*d) again
```

### isinstance vs type()

```python
# isinstance checks inheritance - O(d)
class Animal: pass
class Dog(Animal): pass
dog = Dog()

assert isinstance(dog, Animal)  # checks inheritance
assert type(dog) is not Animal  # exact type only
assert type(dog) is Dog

# isinstance is preferred for flexibility
# type(obj) is C is O(1) and exact, but ignores subclasses
```

## Special Cases

### None Type

```python
# Check for None - O(1)
value = None
assert isinstance(value, type(None))  # O(1) - exact type
assert isinstance(value, object)      # everything inherits from object

# Or use direct comparison
assert value is None  # preferred way for None
```

### Union Types

```python
# An annotation does not affect isinstance(); a union can be its argument
def process(value: int | str):
    if isinstance(value, int):
        return value * 2
    elif isinstance(value, str):
        return value.upper()

assert process(2) == 4
assert process("a") == "A"

# int | str is checked as the tuple (int, str) - O(k*d)
assert isinstance("a", int | str)
assert not isinstance(1.0, int | str)
```

### isinstance with Generic Types

```python
from typing import List

# Parameterized generics raise TypeError
lst = [1, 2, 3]
try:
    isinstance(lst, List[int])
except TypeError as exc:
    assert "generic" in str(exc)
else:
    raise AssertionError("isinstance() accepted List[int]")

# Must use non-parameterized type
assert isinstance(lst, list)  # O(1) - exact type

# typing.get_args() reads the parameters back, without checking elements - O(1)
import typing
element_type = typing.get_args(List[int])
assert element_type == (int,)
```

## Best Practices

✅ **Do**:

- Use `isinstance(obj, (type1, type2))` for multiple types
- Use ABCs for flexible type checking; repeat checks of a class are cached
- Use `isinstance()` for inheritance-aware type checking
- Register virtual subclasses up front, before negative ABC checks run

❌ **Avoid**:

- `type(obj) is SomeType` when subclasses should match (it ignores inheritance)
- Calling `register()` between negative ABC checks in a loop
- Checking against too many types at once (long tuples cost O(k*d))
- Assuming `isinstance()` works with parameterized generics like `List[int]`

## Version Notes

- **Python 3.10+**: `isinstance()` accepts a `|` union such as `int | str` as its second argument, checked like a tuple of the same classes

## Related Functions

- **[issubclass()](issubclass.md)** - Check class inheritance (O(d))
- **[type()](type_func.md)** - Get exact type (O(1))
- **[callable()](callable.md)** - Check if callable (O(1))
- **[abc](../stdlib/abc.md)** - How ABC checks walk and cache their answers
