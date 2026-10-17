# issubclass() Function Complexity

The `issubclass()` function checks whether a class is a subclass of another class, or of any class
in a tuple or union. For an ordinary class it scans the first argument's method resolution order
(MRO) by identity. An abstract base class adds a cache in front of that scan, and a check the
cache cannot answer can walk the ABC's whole hierarchy.

`d` is the length of the first argument's `__mro__`, `k` is the entries in a tuple or union
second argument, counting the entries of nested tuples too, and `t` is the classes registered with
an ABC and its subclasses, and theirs in turn. Identity
comparisons are O(1); a `__subclasshook__` or a custom `__subclasscheck__` costs whatever its own
code does.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `issubclass(cls, base)` | O(d) | O(1) | `base`'s metaclass does not override `__subclasscheck__`; scans `cls.__mro__` for `base`, so a match near the front returns early |
| `issubclass(cls, (base1, base2, ...))` | O(k·d) | O(1) | One check per class, in order, stopping at the first match; nested tuples are searched too; an ABC member costs its own row |
| `issubclass(cls, base1 \| base2)` | O(k·d) | O(1) | A union is checked as the tuple of its members |
| `issubclass(cls, abc)`, answer cached | O(1) | O(1) | Each ABC caches its true and false answers per class |
| `issubclass(cls, abc)`, answer not cached | O(t·d) | O(t) | Calls `__subclasshook__`, then checks the registered classes and the subclasses recursively, stopping at a match; each ABC visited caches its answer |
| `issubclass(cls, classinfo)`, custom `__subclasscheck__` | That method's cost | That method's cost | Defined on the metaclass of `classinfo`; its result is converted to `bool` |
| Non-class first argument | O(1) | O(1) | Raises `TypeError` against an ordinary class or an ABC |

## Basic Class Checking

### Simple Subclass Checks

```python
class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass

# Check subclass relationships - O(d)
assert issubclass(Dog, Animal)
assert issubclass(Cat, Animal)
assert not issubclass(Animal, Dog)
assert issubclass(Dog, Dog)  # a class is a subclass of itself
```

### Multiple Base Classes

A tuple or a union is tried one class at a time, in order, until one matches.

```python
class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass

# Check against several classes - O(k·d)
assert issubclass(Dog, (Animal, object))
assert issubclass(Cat, (Dog, Animal))  # Dog misses, Animal matches
assert not issubclass(str, (int, float))  # every class is tried

# A union is checked like the tuple of its members
assert issubclass(bool, int | str)  # O(k·d)
assert issubclass(bool, (str, (int,)))  # nested tuples are searched too
```

## Class Hierarchies

### Single Inheritance

```python
class A:
    pass

class B(A):
    pass

class C(B):
    pass

class D(C):
    pass

# Each check scans the first argument's MRO - O(d), d = 5 for D
assert issubclass(D, C)
assert issubclass(D, A)
assert issubclass(D, B)
assert not issubclass(C, D)
```

### Multiple Inheritance

```python
class X:
    pass

class Y:
    pass

class Z(X, Y):
    pass

# Both parents are in Z's MRO
assert issubclass(Z, X)  # O(d)
assert issubclass(Z, Y)  # O(d)
assert issubclass(Z, (X, Y))  # O(k·d), stops at X
```

### Method Resolution Order (MRO)

The MRO is stored on the class. `issubclass()` does not rebuild it; it scans the stored tuple, so
the cost is its length, not the depth of the inheritance graph.

```python
class A:
    pass

class B(A):
    pass

class C(A):
    pass

class D(B, C):
    pass

# Each check is a scan of D.__mro__ - O(d)
assert issubclass(D, B)
assert issubclass(D, C)
assert issubclass(D, A)

assert D.__mro__ == (D, B, C, A, object)  # reading __mro__ is O(1)
```

## Abstract Base Classes (ABCs)

### ABC Checking

An ABC's metaclass, `ABCMeta`, answers through its own `__subclasscheck__`. A class that inherits
from the ABC is found in its MRO. `list` is registered with `MutableSequence` rather than
inheriting from `Sequence`, so a check against `Sequence` has to walk the registries and
subclasses to find it.

```python
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence

class DataProcessor(ABC):
    @abstractmethod
    def process(self, data):
        pass

class ListProcessor(DataProcessor):
    def process(self, data):
        return [x * 2 for x in data]

# Check ABC relationship - O(t·d) the first time, O(1) after
assert issubclass(ListProcessor, DataProcessor)
assert not issubclass(list, DataProcessor)

# Check against built-in ABCs
assert issubclass(list, Sequence)
assert issubclass(dict, Mapping)
assert issubclass(str, Sequence)
```

### The ABC Cache

The first check of a class against an ABC can visit every class registered with the ABC and every
subclass of it. Each ABC remembers the answer, true or false, so asking again is a set lookup.
Registering a new class with any ABC forgets every ABC's false answers, because the registration
can turn one of them true.

```python
from abc import ABC

class Plugin(ABC):
    hook_calls = 0

    @classmethod
    def __subclasshook__(cls, subclass):
        Plugin.hook_calls += 1
        return NotImplemented

subclasses = [type(f"Plugin{i}", (Plugin,), {}) for i in range(100)]

assert not issubclass(int, Plugin)  # O(t·d) - visits Plugin and its 100 subclasses
assert Plugin.hook_calls == 101

assert not issubclass(int, Plugin)  # O(1) - answered by the cache
assert Plugin.hook_calls == 101

class Unrelated(ABC):
    pass

Unrelated.register(float)  # a new registration forgets every ABC's false answers
assert not issubclass(int, Plugin)  # O(t·d) again
assert Plugin.hook_calls == 202
```

## Built-in Type Checking

### Built-in Types

```python
# Built-in types have a hierarchy too - O(d)
assert issubclass(bool, int)  # bool inherits from int
assert issubclass(int, object)  # every class inherits from object
assert issubclass(list, object)
assert issubclass(dict, object)

# Unrelated types - O(d)
assert not issubclass(int, str)
assert not issubclass(list, dict)
```

## Common Patterns

### Type-based Dispatch

Each branch is one more check, so a chain of `k` branches costs O(k·d) in the worst case.

```python
def process(obj_class):
    if issubclass(obj_class, int):  # O(d)
        return "numeric"
    elif issubclass(obj_class, str):  # O(d)
        return "string"
    elif issubclass(obj_class, (list, dict)):  # O(k·d)
        return "container"
    else:
        return "other"

assert process(bool) == "numeric"  # bool is a subclass of int
assert process(dict) == "container"
assert process(float) == "other"
```

### Validating Input Types

```python
def create_instance(cls, *args, **kwargs):
    if not issubclass(cls, (list, dict, set)):  # O(k·d)
        raise TypeError(f"{cls} must be list, dict, or set")
    return cls(*args, **kwargs)

assert create_instance(dict, a=1) == {'a': 1}

try:
    create_instance(str)
except TypeError as error:
    assert 'must be list, dict, or set' in str(error)
else:
    raise AssertionError('str was accepted')
```

### Creating Registries

```python
from abc import ABC

class Plugin(ABC):
    pass

plugin_registry = []

def register_plugin(cls):
    if issubclass(cls, Plugin):  # O(t·d) first time per class, then O(1)
        plugin_registry.append(cls)
        return cls
    raise TypeError(f"{cls} must be Plugin subclass")

@register_plugin
class MyPlugin(Plugin):
    pass

assert plugin_registry == [MyPlugin]
```

## Exceptions vs issubclass()

### Exception Hierarchy

```python
# Exception hierarchy - O(d) per check
assert issubclass(ValueError, Exception)
assert issubclass(KeyError, LookupError)
assert issubclass(LookupError, Exception)
assert not issubclass(IndexError, (KeyError, ValueError))  # O(k·d)

# Catch either exception
try:
    {}['missing']
except (ValueError, KeyError) as error:
    assert isinstance(error, KeyError)
else:
    raise AssertionError('no exception was raised')
```

## Performance Considerations

### vs isinstance() vs type()

```python
class Dog:
    pass

dog = Dog()

# issubclass - class against class
assert issubclass(Dog, object)  # O(d)

# isinstance - an object against a class: scans type(dog).__mro__
assert isinstance(dog, object)  # O(d)

# type() - exact type only, no MRO
assert type(dog) is Dog  # O(1)

# isinstance accepts a class too, checked as an object
assert isinstance(list, type)  # list is an instance of type

# issubclass needs a class as its first argument
try:
    issubclass([1, 2, 3], list)
except TypeError as error:
    assert 'must be a class' in str(error)
else:
    raise AssertionError('an instance was accepted')
```

### Avoiding Exceptions

```python
def safe_issubclass(obj, base):
    """issubclass() that answers False for non-class arguments."""
    return isinstance(obj, type) and issubclass(obj, base)  # O(d) for a plain base

assert safe_issubclass(42, int) is False  # 42 is not a class
assert safe_issubclass(int, object) is True
assert safe_issubclass("not a class", int) is False
```

## Advanced Patterns

### Plugin System

```python
from abc import ABC, abstractmethod

class PluginBase(ABC):
    @abstractmethod
    def execute(self):
        pass

_plugins = {}

def register(name):
    def decorator(cls):
        if not issubclass(cls, PluginBase):  # O(t·d) first time per class, then O(1)
            raise TypeError(f"{cls} must inherit from PluginBase")
        _plugins[name] = cls
        return cls
    return decorator

@register("processor")
class DataProcessor(PluginBase):
    def execute(self):
        return "processing"

plugin_cls = _plugins["processor"]
assert plugin_cls().execute() == "processing"
```

### Mixins and Composition

```python
import time

class TimestampMixin:
    """Mixin to add timestamp capability"""
    def get_timestamp(self):
        return time.time()

class LoggingMixin:
    """Mixin to add logging"""
    def log(self, msg):
        return msg

class MyClass(TimestampMixin, LoggingMixin):
    pass

# Check if a mixin is in the hierarchy - O(d)
assert issubclass(MyClass, TimestampMixin)
assert issubclass(MyClass, LoggingMixin)
```

## Special Cases

### Checking Generic Types

A parameterized generic is neither a class nor a valid second argument.

```python
from typing import List

try:
    issubclass(List[int], list)
except TypeError as error:
    assert 'arg 1 must be a class' in str(error)
else:
    raise AssertionError('a parameterized generic was accepted')

try:
    issubclass(list, list[int])
except TypeError as error:
    assert 'parameterized generic' in str(error)
else:
    raise AssertionError('a parameterized generic was accepted')

# Check against the unparameterized class instead
assert issubclass(list, list)  # O(d)
assert issubclass(list, List)  # the bare typing alias works too
```

## Performance Best Practices

✅ **Do**:

- Use `issubclass()` to check class hierarchies; for a plain class it is one scan of the MRO
- Use `issubclass(cls, (base1, base2))` for several classes; it stops at the first match
- Put the likeliest match first in a tuple or union, since the rest are not checked
- Use ABCs for flexible type checking; their answers are cached after the first check

❌ **Avoid**:

- Calling `issubclass()` with non-class objects: against an ordinary class or an ABC it raises `TypeError`
- Parameterized generics such as `list[int]` as either argument
- Registering classes in a hot path: each new registration forgets every ABC's cached false answers
- Using `issubclass()` when `isinstance()` is appropriate

## Version Notes

- **Python 3.10+**: The second argument may be a union such as `int | str`

## Related Functions

- **[isinstance()](isinstance.md)** - Check an object against a class instead of a class
- **[type()](type_func.md)** - Get the exact type (O(1))
- **[super()](super.md)** - Call parent class methods through the MRO
