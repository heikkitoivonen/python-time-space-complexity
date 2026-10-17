# property() Decorator Complexity

`property` builds a data descriptor that routes reading, assigning and deleting one class attribute
through functions. The property object holds those functions and a docstring, and keeps no
per-instance state and no cached value, so every access calls the matching function again.

A getter, setter or deleter costs what its own body does; the bounds below are the work the
property adds to it. `d` is the length of a class's MRO, `len(cls.__mro__)`. Class-side attribute
lookups are cached per type, as described on the [object() page](object_func.md), so the access
rows assume the cache is warm; an uncached lookup costs O(d).

## Complexity Reference

### property

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `property(fget=None, fset=None, fdel=None, doc=None)` | O(1) | O(1) | Stores the three functions; calls none of them; without `doc`, takes the getter's docstring |
| `@property` on a function | O(1) | O(1) | The same as `property(func)` |
| `prop.getter(f)`, `prop.setter(f)`, `prop.deleter(f)` | O(1) | O(1) | Return a new property of the same type with one function replaced; the original is unchanged |
| `prop.fget`, `prop.fset`, `prop.fdel` | O(1) | O(1) | The stored function, or `None` |
| `prop.__doc__` | O(1) | O(1) | `doc`, or the getter's docstring |
| `prop.__name__` | O(1) | O(1) | Python 3.13+: the name it was bound to in a class body, else the getter's `__name__` |

### Attribute Access

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `obj.attr` | O(1) | O(1) | Plus one call of the getter, on every access; without one, raises `AttributeError`; an instance `__dict__` entry of the same name is ignored |
| `obj.attr = value` | O(1) | O(1) | Plus one call of the setter; without one, raises `AttributeError` and stores nothing |
| `del obj.attr` | O(1) | O(1) | Plus one call of the deleter; without one, raises `AttributeError` |
| `Class.attr` | O(1) | O(1) | Returns the property object itself and calls nothing |
| `obj.attr` where a base class defines the property | O(1) | O(1) | The cached lookup does not grow with d |

## Defining Properties

### Getter, Setter and Deleter

Each operation on the attribute calls exactly one of the three functions.

```python
calls = []

class Account:
    def __init__(self, balance):
        self._balance = balance

    @property
    def balance(self):
        calls.append("get")
        return self._balance

    @balance.setter
    def balance(self, amount):
        calls.append("set")
        if amount < 0:
            raise ValueError("balance cannot be negative")
        self._balance = amount

    @balance.deleter
    def balance(self):
        calls.append("del")
        self._balance = 0

account = Account(100)
assert account.balance == 100  # O(1) plus the getter
account.balance = 250          # O(1) plus the setter
assert account.balance == 250
del account.balance            # O(1) plus the deleter
assert account.balance == 0
assert calls == ["get", "set", "get", "del", "get"]

try:
    account.balance = -5
except ValueError as error:
    assert "negative" in str(error)
else:
    raise AssertionError("expected ValueError")
assert account.balance == 0
```

### Read-Only Properties

A property without a setter refuses assignment instead of falling back to the instance's
`__dict__`, so a read-only attribute stays read-only.

```python
class Point:
    def __init__(self, x):
        self._x = x

    @property
    def x(self):
        return self._x

p = Point(3)
try:
    p.x = 10
except AttributeError as error:
    assert "has no setter" in str(error)
else:
    raise AssertionError("expected AttributeError")

assert p.x == 3
assert "x" not in vars(p)  # Nothing was stored
```

### Each Decorator Returns a New Property

`setter()`, `getter()` and `deleter()` copy the property with one function replaced. Reusing the
same name, as the decorator form does, rebinds it to the copy.

```python
class Temperature:
    @property
    def celsius(self):
        """Degrees Celsius."""
        return self._celsius

read_only = Temperature.__dict__["celsius"]
read_write = read_only.setter(lambda self, value: setattr(self, "_celsius", value))  # O(1)

assert read_write is not read_only
assert read_only.fset is None  # The original is unchanged
assert read_write.fget is read_only.fget
assert read_write.__doc__ == "Degrees Celsius."
```

## Accessing Properties

### The Getter Runs on Every Access

A property computes its value each time it is read. When the value cannot change, a
[`functools.cached_property`](../stdlib/functools.md) computes it once per instance and stores it in
the instance's `__dict__`, so later reads call nothing.

```python
from functools import cached_property

computed = []

class Report:
    def __init__(self, values):
        self.values = values

    @property
    def total(self):
        computed.append("property")
        return sum(self.values)  # Runs on every access

    @cached_property
    def cached_total(self):
        computed.append("cached")
        return sum(self.values)  # Runs once per instance

report = Report(range(1_000))
for _ in range(3):
    assert report.total == 499_500
    assert report.cached_total == 499_500

assert computed.count("property") == 3
assert computed.count("cached") == 1
```

### Properties Take Precedence Over the Instance Dictionary

A property is a data descriptor, so it wins over an entry of the same name in the instance's
`__dict__`. The getter is called even when such an entry exists.

```python
class Box:
    @property
    def size(self):
        return 42

box = Box()
vars(box)["size"] = 7  # Bypasses the property
assert box.size == 42  # The property still answers
assert vars(box)["size"] == 7
```

### Inherited Properties

A property defined on a base class is found through the class's cached attribute lookup, so a deep
hierarchy costs no more per access than a shallow one. Reading the attribute from the class returns
the property object itself.

```python
class Base:
    @property
    def kind(self):
        return type(self).__name__

class Middle(Base):
    pass

class Leaf(Middle):
    pass

assert Leaf().kind == "Leaf"  # O(1) - cached lookup
assert isinstance(Leaf.kind, property)  # The descriptor, not a value
assert Leaf.kind is Base.__dict__["kind"]
```

## Common Patterns

### Validation in a Setter

Validation runs once per assignment, including the one in `__init__` when it assigns through the
property.

```python
class Person:
    def __init__(self, age):
        self.age = age  # Goes through the setter

    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError("age must be a non-negative int")
        self._age = value

assert Person(30).age == 30

try:
    Person(-1)
except ValueError as error:
    assert "non-negative" in str(error)
else:
    raise AssertionError("expected ValueError")
```

## Performance Best Practices

✅ **Do**:

- Keep getters cheap: every read of the attribute calls the getter again
- Use `functools.cached_property` for a value computed once per instance and never changed
- Define a property without a setter to make an attribute read-only

❌ **Avoid**:

- Reading an expensive property repeatedly in a loop; read it once into a local
- Expecting an instance `__dict__` entry to override a property; the property always answers

## Version Notes

- **Python 3.13+**: `property.__name__` gives the name the property was bound to in a class body, or
  its getter's name

## Related Functions

- **[classmethod()](classmethod.md)** - Another descriptor, for methods bound to the class
- **[staticmethod()](staticmethod.md)** - A descriptor for methods bound to nothing
- **[getattr()](getattr.md)** - Reading an attribute by name, which calls a property's getter
- **[setattr()](setattr.md)** - Assigning by name, which calls a property's setter
- **[object()](object_func.md)** - The cached class-side attribute lookup every access goes through
