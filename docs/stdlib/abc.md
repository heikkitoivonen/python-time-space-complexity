# abc Module Complexity

The `abc` module defines abstract base classes: classes whose abstract methods must be overridden
before they can be instantiated, and which can claim unrelated classes as virtual subclasses. Its work
happens when a class is created and when `isinstance()` or `issubclass()` meets a class for the
first time; instances carry nothing extra. The bounds below price that work, on top of what
building or instantiating a plain class costs.

`m` is the entries in a class body's namespace, `b` is the direct bases plus the abstract names
they declare, `a` is the abstract methods a class is left with, and `g` is the registration and
subclass links an ABC can reach: to its registered classes and its subclasses, followed recursively
through every ABC among them. Attribute lookup, a plain class's MRO test, comparing and joining
method names, and `__subclasshook__` are priced as O(1), as the default hook is.

## Complexity Reference

### Decorators

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `@abc.abstractmethod` | O(1) | O(1) | Sets `__isabstractmethod__` on the function; only an `ABCMeta` class enforces it |
| `abc.abstractclassmethod(callable)`, `abc.abstractstaticmethod(callable)`, `abc.abstractproperty(fget)` | O(1) | O(1) | Deprecated; stack `classmethod`, `staticmethod` or `property` over `abstractmethod` instead |

### ABCMeta

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `abc.ABCMeta(name, bases, namespace)`, `class C(metaclass=ABCMeta)` | O(m + b) | O(m + b) | Tests every namespace value and every abstract name of the direct bases, once |
| `C.__abstractmethods__` | O(1) | O(1) | The frozenset stored at class creation, not recomputed |
| Instantiating a concrete ABC subclass | O(1) | O(1) | Beyond `__init__`; the abstract methods are not looked at again |
| Instantiating a class with abstract methods | O(a log a) | O(a) | `TypeError` naming every abstract method, sorted |
| `isinstance(obj, C)`, `issubclass(cls, C)`: first check of a class | O(g) | O(g) | Walks registered classes and subclasses recursively, caching the answer in every ABC it visits unless the registry holds the class directly |
| `isinstance(obj, C)`, `issubclass(cls, C)`: cached | O(1) | O(1) | A positive answer stays cached; a negative one only until any ABC registers a new virtual subclass. A class registered directly is found in the registry instead, also O(1) |
| `ABCMeta.register(subclass)` | O(g) | O(g) | Checks `issubclass(subclass, C)` first, then the reverse to refuse a cycle, so `g` includes `subclass`'s links when it is an ABC; unless already a subclass, adds one weak reference and a new cache token. Returns `subclass` |
| `ABCMeta.__subclasshook__(subclass)` | O(1) | O(1) | Override as a classmethod; returning `True` or `False` answers an uncached check before registration and inheritance are consulted |

### ABC

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `class C(ABC)` | O(m + b) | O(m + b) | The same as `metaclass=ABCMeta`; `ABC` has empty `__slots__` and adds nothing to instances |

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `abc.get_cache_token()` | O(1) | O(1) | Changes whenever any ABC registers a new virtual subclass |
| `abc.update_abstractmethods(cls)` | O(m + b) | O(m + b) | Recomputes `__abstractmethods__` from the class body and its direct bases; returns a class without that attribute unchanged |

## Defining an ABC

### Abstract Methods Are Checked Once

Class creation decides which methods are still abstract and stores them in `__abstractmethods__`.
Instantiation does not look at them again, so a concrete subclass costs no more to instantiate than
a plain class, however many abstract methods its bases declared.

```python
from abc import ABC, abstractmethod

class DataStore(ABC):  # O(m + b), once
    @abstractmethod
    def read(self, key): ...

    @abstractmethod
    def write(self, key, value): ...

assert DataStore.__abstractmethods__ == frozenset({'read', 'write'})  # O(1)

class PartialStore(DataStore):
    def read(self, key):
        return None

try:
    PartialStore()  # O(a log a) - builds the message
except TypeError as error:
    assert 'write' in str(error) and 'read' not in str(error)
else:
    raise AssertionError('a class with an abstract method was instantiated')

class MemoryStore(DataStore):
    def __init__(self):
        self.data = {}

    def read(self, key):
        return self.data.get(key)

    def write(self, key, value):
        self.data[key] = value

store = MemoryStore()  # O(1) - no abstract-method scan
store.write('k', 1)
assert store.read('k') == 1
```

### Properties, Class Methods and Static Methods

`abstractmethod` goes innermost. The wrapper reports the function's flag, so the class treats it
as abstract like any other method.

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    @property
    @abstractmethod
    def area(self): ...

    @classmethod
    @abstractmethod
    def unit(cls): ...

    @staticmethod
    @abstractmethod
    def sides(): ...

assert Shape.__abstractmethods__ == frozenset({'area', 'unit', 'sides'})

class Square(Shape):
    def __init__(self, side):
        self.side = side

    @property
    def area(self):
        return self.side * self.side

    @classmethod
    def unit(cls):
        return cls(1)

    @staticmethod
    def sides():
        return 4

assert Square(3).area == 9
assert Square.unit().area == 1
assert Square.sides() == 4
```

### Adding Methods After Creation

Because the set is computed once, a method attached to the class later does not change it.
`update_abstractmethods()` recomputes it with the same O(m + b) scan class creation ran, which
makes it the tool for class decorators that add methods.

```python
from abc import ABC, abstractmethod, update_abstractmethods

class Greeter(ABC):
    @abstractmethod
    def greet(self): ...

class Late(Greeter):
    pass

Late.greet = lambda self: 'hi'
assert Late.__abstractmethods__ == frozenset({'greet'})  # still recorded as abstract

update_abstractmethods(Late)  # O(m + b)
assert Late.__abstractmethods__ == frozenset()
assert Late().greet() == 'hi'
```

## isinstance and issubclass

### Caching

Each ABC caches the answers it has worked out. The first check walks its registry and its
subclasses, recursively; a repeat is a set lookup, as is any check of a class registered directly
on that ABC. A negative answer is dropped as soon as any ABC
registers a new virtual subclass, so the next negative check walks again, while a positive answer is
kept. The hook below counts the ABCs a check visits.

```python
from abc import ABC

visits = []

class Plugin(ABC):
    @classmethod
    def __subclasshook__(cls, subclass):
        visits.append(cls)
        return NotImplemented

subclasses = [type(f'Plugin{i}', (Plugin,), {}) for i in range(10)]

class Unrelated:
    pass

assert not issubclass(Unrelated, Plugin)  # O(g) - Plugin and its 10 subclasses
assert len(visits) == 11

visits.clear()
assert not issubclass(Unrelated, Plugin)  # O(1) - cached
assert visits == []

class Other(ABC):
    pass

Other.register(int)  # any registration invalidates negative answers
assert not issubclass(Unrelated, Plugin)  # O(g) again
assert len(visits) == 11

visits.clear()
assert issubclass(subclasses[0], Plugin)
visits.clear()
Other.register(float)
assert issubclass(subclasses[0], Plugin)  # O(1) - positive answers survive
assert visits == []
```

## Virtual Subclasses

### Registering

`register()` makes `issubclass()` and `isinstance()` answer `True` without inheritance, unless a
`__subclasshook__` answers first. It checks
nothing about the class's methods, and the registered class does not gain the ABC in its MRO.
Each call starts with an `issubclass()` check, which walks the classes already registered,
so registering k classes one at a time into one ABC is O(k²) in total.

```python
from abc import ABC, abstractmethod

class Drawable(ABC):
    @abstractmethod
    def draw(self): ...

@Drawable.register  # O(g) - returns the class, so it works as a decorator
class Circle:
    def draw(self):
        return 'circle'

@Drawable.register
class Blank:  # no draw() - registration does not check
    pass

assert isinstance(Circle(), Drawable)
assert issubclass(Blank, Drawable)
assert Drawable not in Circle.__mro__
assert Blank() is not None  # virtual subclasses are not held to the abstract methods
```

### Structural Checks with __subclasshook__

A hook answers for classes that were neither registered nor derived. It runs on every check the
caches cannot answer, and a check the registry answers directly is one of those: the registry is
consulted after the hook and does not fill the cache.

```python
from abc import ABC, abstractmethod

class Closeable(ABC):
    @abstractmethod
    def close(self): ...

    @classmethod
    def __subclasshook__(cls, subclass):
        if cls is Closeable:
            return any('close' in vars(klass) for klass in subclass.__mro__)
        return NotImplemented

class Resource:
    def close(self):
        return 'closed'

assert issubclass(Resource, Closeable)  # O(1) plus the hook
assert not issubclass(int, Closeable)
```

### The Cache Token

`get_cache_token()` changes whenever any ABC registers a new virtual subclass, so code that caches its own
results derived from ABC checks can compare tokens to know when to drop them.

```python
from abc import ABC, get_cache_token

class Interface(ABC):
    pass

class Newcomer:
    pass

token = get_cache_token()  # O(1)
Interface.register(Newcomer)
assert get_cache_token() != token

token = get_cache_token()
Interface.register(Newcomer)  # already registered - nothing changes
assert get_cache_token() == token
```

## Performance Best Practices

✅ **Do**:

- Put abstract methods on a base freely: a concrete subclass's instantiation pays nothing for them
- Register virtual subclasses at import time, before the checks that depend on them run
- Call `update_abstractmethods()` from a class decorator that adds methods after class creation

❌ **Avoid**:

- Registering classes in a loop that also runs negative `isinstance()` checks: every new
  registration sends each ABC's next negative check back through its registry and subclasses
- Registering many classes one at a time into one ABC; each call walks the registry built so far
- A `__subclasshook__` that does expensive work: an uncached check pays it at every ABC visited

## Version Notes

- **All Python 3**: `abstractclassmethod`, `abstractstaticmethod` and `abstractproperty` are
  deprecated; they remain importable on every supported version

## Related Modules

- **[collections.abc](collections.abc.md)** - ready-made ABCs, several with a `__subclasshook__`
- **[functools](functools.md)** - `singledispatch` dispatches on ABCs, virtual subclasses included
- **[typing](typing.md)** - `Protocol` for structural typing checked statically
