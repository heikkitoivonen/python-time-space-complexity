# issubclass() Function Complexity

The `issubclass()` function checks whether a class is a subclass of another class, following the class hierarchy.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `issubclass(class, base)` | O(d) | O(1) | d = MRO depth; effectively O(1) for typical hierarchies |
| `issubclass(class, (base1, base2, ...))` | O(k*d) | O(1) | k = number of bases; short-circuits on first match |
| `issubclass(class, abc)` | O(d) | O(1) | May call __subclasshook__ for virtual subclass check |

## Basic Class Checking

### Simple Subclass Checks

```python
# Single base class - O(1)
class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass

# Check subclass relationships - O(1)
issubclass(Dog, Animal)     # True
issubclass(Cat, Animal)     # True
issubclass(Animal, Dog)     # False
issubclass(Dog, Dog)        # True (class is subclass of itself)
```

### Multiple Base Classes

```python
# Check against multiple bases - O(k) where k = number of bases
issubclass(Dog, (Animal, object))  # True - O(2)
issubclass(Cat, (Dog, Animal))     # True (finds Animal) - O(2)
issubclass(str, (int, float))      # False - O(2)
```

## Class Hierarchies

### Single Inheritance

```python
# Deep inheritance chain - O(1) per check
class A:
    pass

class B(A):
    pass

class C(B):
    pass

class D(C):
    pass

# Check inheritance - O(1)
issubclass(D, C)  # True
issubclass(D, A)  # True - follows chain
issubclass(D, B)  # True
issubclass(C, D)  # False
```

### Multiple Inheritance

```python
# Multiple inheritance - O(1)
class X:
    pass

class Y:
    pass

class Z(X, Y):
    pass

# Check both parent classes
issubclass(Z, X)  # True - O(1)
issubclass(Z, Y)  # True - O(1)
issubclass(Z, (X, Y))  # True - O(2)
```

### Method Resolution Order (MRO)

```python
# MRO is computed once, then O(1) to check
class A:
    pass

class B(A):
    pass

class C(A):
    pass

class D(B, C):
    pass

# All O(1)
issubclass(D, B)  # True
issubclass(D, C)  # True
issubclass(D, A)  # True

# Check MRO
print(D.__mro__)  # Computed once
# (<class 'D'>, <class 'B'>, <class 'C'>, <class 'A'>, <class 'object'>)
```

## Abstract Base Classes (ABCs)

### ABC Checking

```python
from abc import ABC, abstractmethod

# Define abstract base class
class DataProcessor(ABC):
    @abstractmethod
    def process(self, data):
        pass

class ListProcessor(DataProcessor):
    def process(self, data):
        return [x * 2 for x in data]

# Check ABC relationship - O(1)
issubclass(ListProcessor, DataProcessor)  # True
issubclass(list, DataProcessor)           # False

# Check against built-in ABCs
from collections.abc import Sequence, Mapping

issubclass(list, Sequence)    # True - O(1)
issubclass(dict, Mapping)     # True - O(1)
issubclass(str, Sequence)     # True - O(1)
```

## Built-in Type Checking

### Built-in Types

```python
# All built-in types have hierarchy - O(1)
issubclass(bool, int)         # True - bool inherits from int
issubclass(int, object)       # True - all inherit from object
issubclass(list, object)      # True
issubclass(dict, object)      # True

# Unrelated types - O(1)
issubclass(int, str)          # False
issubclass(list, dict)        # False
```

## Common Patterns

### Type-based Dispatch

```python
# Dispatch based on class - O(k) for checking
def process(obj_class):
    if issubclass(obj_class, int):          # O(1)
        return "numeric"
    elif issubclass(obj_class, str):        # O(1)
        return "string"
    elif issubclass(obj_class, (list, dict)):  # O(2)
        return "container"
    else:
        return "other"

result = process(bool)  # "numeric" - bool is subclass of int
```

### Validating Input Types

```python
# Check if input class is valid - O(k)
def create_instance(cls, *args, **kwargs):
    if not issubclass(cls, (list, dict, set)):  # O(3)
        raise TypeError(f"{cls} must be list, dict, or set")
    return cls(*args, **kwargs)

create_instance(dict, a=1)  # Works
create_instance(str)        # Raises TypeError
```

### Creating Registries

```python
# Registry pattern using ABC
from abc import ABC

class Plugin(ABC):
    pass

plugin_registry = []

def register_plugin(cls):
    if issubclass(cls, Plugin):  # O(1)
        plugin_registry.append(cls)
        return cls
    raise TypeError(f"{cls} must be Plugin subclass")

@register_plugin
class MyPlugin(Plugin):
    pass
```

## Exceptions vs issubclass()

### Exception Hierarchy

```python
# Exception hierarchy - O(1) per check
issubclass(ValueError, Exception)        # True
issubclass(KeyError, LookupError)        # True
issubclass(LookupError, Exception)       # True
issubclass(IndexError, (KeyError, ValueError))  # False - O(2)

# Check multiple exceptions
try:
    something()
except (ValueError, KeyError) as e:  # Checks both - O(2)
    pass
```

## Performance Considerations

### vs isinstance() vs type()

```python
# Check class vs instance
class Dog:
    pass

dog = Dog()

# issubclass - checks class (static)
issubclass(Dog, object)      # O(1)

# isinstance - checks instance against class (follows MRO)
isinstance(dog, object)      # O(1)

# type() - exact type only
type(dog) is Dog             # O(1)
```

### Pre-computing Subclass Relationships

```python
# For frequent checks, consider caching
class BaseClass:
    _subclasses = None
    
    @classmethod
    def get_subclasses(cls):
        if cls._subclasses is None:
            cls._subclasses = set(cls.__subclasses__())  # O(n)
        return cls._subclasses
    
    @classmethod
    def is_subclass_cached(cls, other):
        return other in cls.get_subclasses()  # O(1) lookup

# First call - O(n)
BaseClass.is_subclass_cached(DerivedClass)

# Subsequent calls - O(1)
BaseClass.is_subclass_cached(AnotherClass)
```

### Avoiding Exceptions

```python
# Safe issubclass() check
def safe_issubclass(obj, base):
    """Check issubclass, handling non-class arguments"""
    try:
        return isinstance(obj, type) and issubclass(obj, base)  # O(1)
    except TypeError:
        return False

safe_issubclass(42, int)           # False (42 is not a class)
safe_issubclass(int, object)       # True
safe_issubclass("not a class", int)  # False
```

## Advanced Patterns

### Plugin System

```python
from abc import ABC, abstractmethod

# Define plugin interface
class PluginBase(ABC):
    @abstractmethod
    def execute(self):
        pass

# Registry
_plugins = {}

def register(name):
    def decorator(cls):
        if not issubclass(cls, PluginBase):  # O(1)
            raise TypeError(f"{cls} must inherit from PluginBase")
        _plugins[name] = cls
        return cls
    return decorator

@register("processor")
class DataProcessor(PluginBase):
    def execute(self):
        return "processing"

# Later: get plugin
plugin_cls = _plugins["processor"]
plugin = plugin_cls()  # Create instance
```

### Mixins and Composition

```python
# Mixin pattern - O(1) to check
class TimestampMixin:
    """Mixin to add timestamp capability"""
    def get_timestamp(self):
        return time.time()

class LoggingMixin:
    """Mixin to add logging"""
    def log(self, msg):
        print(msg)

class MyClass(TimestampMixin, LoggingMixin):
    pass

# Check if mixin is in hierarchy - O(1)
issubclass(MyClass, TimestampMixin)  # True
issubclass(MyClass, LoggingMixin)    # True
```

## Special Cases

### Checking Generic Types

```python
from typing import List, Dict

# Generic types don't work with issubclass
try:
    issubclass(List[int], list)  # TypeError!
except TypeError as e:
    print("Can't check parameterized generics")

# Use non-parameterized instead
issubclass(list, object)  # True - O(1)
```

### Checking with object

```python
# Everything inherits from object - O(1)
issubclass(int, object)      # True
issubclass(str, object)      # True
issubclass(bool, object)     # True
issubclass(CustomClass, object)  # True

# In practice, rarely needed
```

## Difference: isinstance() vs issubclass()

```python
# isinstance - instance vs class
obj = [1, 2, 3]
isinstance(obj, list)        # True - O(1)

# issubclass - class vs class
issubclass(list, object)     # True - O(1)

# isinstance on class itself
isinstance(list, type)       # True - list is a type

# issubclass would fail
try:
    issubclass([1, 2, 3], list)  # TypeError!
except TypeError:
    print("issubclass needs classes, not instances")
```

## Version Notes

- **Python 2.x**: Works with new-style and old-style classes
- **Python 3.x**: All classes are new-style, consistent behavior
- **All versions**: O(1) for single base class checks

## Related Functions

- **[isinstance()](isinstance.md)** - Check instance type (O(k))
- **type()** - Get exact type (O(1))
- **[super()](super.md)** - Call parent class methods

## Best Practices

✅ **Do**:

- Use `issubclass()` to check class hierarchies
- Use `issubclass(cls, (base1, base2))` for multiple bases
- Use ABCs for flexible type checking
- Check only once and cache results if in tight loops

❌ **Avoid**:

- Calling `issubclass()` with non-class objects (raises TypeError)
- Assuming parameterized generics work with `issubclass()`
- Excessive subclass checks in tight loops (cache instead)
- Using `issubclass()` when `isinstance()` is appropriate
