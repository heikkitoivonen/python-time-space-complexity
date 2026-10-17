# type() Function Complexity

`type(obj)` returns the class of an object. `type(name, bases, namespace)` creates a new class, which
is the same work a `class` statement does once its body has run: copy the namespace, compute the
method resolution order (MRO), and store both on the class. The MRO is computed when the class is
created and kept as `__mro__`.

`n` is the entries in the class namespace, `h` the classes in the resulting MRO,
`len(C.__mro__)`, `b` the direct bases, and `s` the direct subclasses of a class. Attribute names are
hashed in O(1), and a class's `__slots__` are treated as a few names. The bounds are for `type`
itself: a custom metaclass, `__prepare__`, `__init_subclass__` or `__set_name__` adds whatever work
its own code does.

## Complexity Reference

### type

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `type(obj)` | O(1) | O(1) | Returns the object's class itself; an overridden `__class__` attribute does not change it |
| `type(name, bases, namespace)`, zero or one base | O(n + h) | O(n + h) | Copies the namespace, and stores a new MRO tuple of h classes on the class |
| `type(name, bases, namespace)`, several bases | O(n + b²h²) worst case | O(n + h) | Adds the C3 merge that `type.mro()` performs |

### Method Resolution Order

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `C.__mro__` | O(1) | O(1) | The tuple stored when the class was created |
| `type.mro(C)`, `C.mro()`, zero or one base | O(h) | O(h) | Computes the order again and returns a new list |
| `type.mro(C)`, `C.mro()`, several bases | O(b²h²) worst case | O(h) | C3 merge; how close it comes to the worst case depends on the hierarchy's shape |

### Class Attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `C.__bases__`, `C.__base__`, `C.__name__`, `C.__qualname__` | O(1) | O(1) | Stored on the class |
| `C.__dict__` | O(1) | O(1) | A read-only `mappingproxy` view of the namespace, not a copy |
| `C.__subclasses__()` | O(s) | O(s) | A new list of the direct subclasses that are still alive |

## Getting an Object's Type

### type() Versus isinstance()

`type(obj)` reads the object's class, so `type(obj) is C` is an O(1) exact-class test that rejects
subclasses. [`isinstance()`](isinstance.md) accepts subclasses: it is O(1) when the class matches
exactly and otherwise scans the MRO.

```python
class Animal:
    pass

class Dog(Animal):
    pass

dog = Dog()

assert type(dog) is Dog             # O(1)
assert type(dog) is not Animal      # O(1) - exact class only
assert isinstance(dog, Dog)         # O(1) - exact match
assert isinstance(dog, Animal)      # O(h) - scans the MRO
assert type(Dog) is type            # The class of a class is its metaclass
```

### type() Versus __class__

`obj.__class__` is an attribute lookup, and a class can override it, as proxy objects do.
`type(obj)` cannot be overridden. `isinstance()` also consults `__class__`, so the two tests can
disagree.

```python
class Proxy:
    @property
    def __class__(self):
        return int

proxy = Proxy()

assert type(proxy) is Proxy          # O(1) - the real class
assert proxy.__class__ is int        # Whatever the attribute returns
assert isinstance(proxy, int)        # Falls back to __class__
assert type(proxy) is not int
```

## Creating Classes Dynamically

### The Three-Argument Form

The namespace is copied into the new class, so changing the dictionary afterwards does not change
the class.

```python
def greet(self):
    return f"Hello, {self.name}"

namespace = {"species": "human", "greet": greet}
Person = type("Person", (), namespace)  # O(n + h)

namespace["species"] = "changed"
assert Person.species == "human"        # The class holds its own copy

person = Person()
person.name = "Alice"
assert person.greet() == "Hello, Alice"
assert Person.__mro__ == (Person, object)
```

### Inheritance and the MRO

Every class stores its own MRO, so creating a class below a deep chain copies the h classes above
it. Read `C.__mro__` to get the stored order; `type.mro(C)` computes a new list from the bases each
time and leaves the stored tuple alone. A metaclass can override `C.mro()`; the bounds above are for
`type.mro(C)` itself.

```python
class Base:
    pass

class Child(Base):
    pass

stored = Child.__mro__              # O(1)
order = type.mro(Child)             # O(h), one base
assert order == [Child, Base, object]
assert Child.mro() == order
assert Child.__mro__ is stored

Leaf = type("Leaf", (Child,), {})   # O(n + h)
assert Leaf.__mro__ == (Leaf, Child, Base, object)
```

With several bases, the C3 merge places every class after all its subclasses and keeps each
class's bases in the order they were listed.

```python
class A:
    pass

class B(A):
    pass

class C(A):
    pass

D = type("D", (B, C), {})  # Includes the C3 merge
assert D.__mro__ == (D, B, C, A, object)
assert D.__bases__ == (B, C)
```

### Metaclasses

A class statement calls its metaclass with the name, the bases and the namespace the body built,
and `type` is the default metaclass. Hooks run as part of creating the class and add their own
cost: `__set_name__` once for each namespace value that defines it, and the base class's
`__init_subclass__` once.

```python
calls = []

class Recording(type):
    def __new__(mcs, name, bases, namespace):
        calls.append(name)
        return super().__new__(mcs, name, bases, namespace)

class Plugin(metaclass=Recording):
    pass

Tool = Recording("Tool", (Plugin,), {})  # The same call the class statement makes

assert calls == ["Plugin", "Tool"]
assert type(Tool) is Recording
```

## Inspecting Classes

`C.__dict__` is a live, read-only view of the class namespace; reading it copies nothing.
`C.__subclasses__()` lists only direct subclasses, in a new list each call.

```python
from types import MappingProxyType

class Base:
    limit = 10

class Left(Base):
    pass

class Right(Base):
    pass

class Far(Left):
    pass

view = Base.__dict__                # O(1) - no copy
assert isinstance(view, MappingProxyType)
Base.extra = 1
assert view["extra"] == 1           # The view sees later changes

try:
    view["limit"] = 20
except TypeError as error:
    assert "does not support item assignment" in str(error)
else:
    raise AssertionError("expected TypeError")

assert Base.__subclasses__() == [Left, Right]  # O(s) - Far is not direct
```

## Performance Best Practices

✅ **Do**:

- Read `C.__mro__`, which is stored, rather than calling `C.mro()`, which computes the order again
- Use `type(obj) is C` for an exact-class test and `isinstance()` when subclasses should match
- Create classes once, at module level, rather than inside a function called repeatedly

❌ **Avoid**:

- Creating a class per call or per object: each costs at least O(n + h) and keeps its own MRO tuple
- Relying on `obj.__class__` when the real class matters; `type(obj)` cannot be overridden

## Related Functions

- **[isinstance()](isinstance.md)** - Type checks that accept subclasses, and what they cost
- **[issubclass()](issubclass.md)** - Subclass checks between two classes
- **[object()](object_func.md)** - The cached class-side attribute lookup every class starts with
- **[setattr()](setattr.md)** - Assigning to a class invalidates its subclasses' attribute caches
- **[super()](super.md)** - Lookups that follow the MRO from a given position
- **[vars()](vars.md)** - The `__dict__` of an object or class

## Further Reading

- [CPython Internals: type](https://zpoint.github.io/CPython-Internals/BasicObject/type/type.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's type implementation
