# setattr() Function Complexity

The `setattr()` function assigns a value to a named attribute of an object. `setattr(obj, "name",
value)` is exactly `obj.name = value` with the name supplied at run time: both call
`type(obj).__setattr__`, so a property setter, a descriptor's `__set__` or a class's own
`__setattr__` runs in the same way.

`d` is the classes in `type(obj).__mro__`, `s` is the subclasses of a class, direct and indirect,
and `k` is the cost, in time and space, of a user-defined `__setattr__`, property setter or
`__set__`. Attribute names are treated as hashing and comparing in O(1), and the C stack used by
recursion over a class's bases or subclasses is not counted in the Space column.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `setattr(obj, name, value)` | O(1) avg | O(1) | One class-side lookup for a data descriptor, cached per class and name, then one store in the instance's `__dict__`; adding a new attribute is amortized |
| `setattr(obj, name, value)` with a name built at run time | O(1) avg | O(1) | An exact `str` name is interned first, so a name rebuilt on every call still hits the class-side cache, unlike [`getattr()`](getattr.md) |
| `setattr(obj, name, value)` with a `str` subclass or a name over 100 characters | O(d) | O(1) | Such a name is never cached: every call walks the MRO |
| First `setattr(obj, ...)` after the class or a base changed | O(d) | O(1) | Walks the MRO once and caches the result. From Python 3.13, once a class has been changed and looked up again more than 1,000 times it is never cached again, and every assignment on its instances pays O(d) |
| `setattr(obj, name, value)`, property or data descriptor | O(k) | O(k) | Runs the setter or `__set__` instead of the store, even when the instance's `__dict__` holds the name; a property without a setter raises `AttributeError` |
| `setattr(obj, name, value)`, custom `__setattr__` | O(k) | O(k) | Runs on every assignment, including those in `__init__` |
| `setattr(obj, name, value)`, slot declared on `type(obj)` | O(1) | O(1) | Stores in the slot; without a `__dict__`, a name with no slot or other descriptor raises `AttributeError` |
| `setattr(obj, name, value)`, slot declared on a base class | O(d) | O(1) | Checks that `type(obj)` derives from the declaring class by scanning its MRO; an `obj.name = value` statement the interpreter has specialized skips the check |
| `setattr(cls, name, value)` | O(s) | O(1) | Invalidates the attribute cache of the class and of each subclass whose cache is still valid |
| `setattr(cls, name, value)` for a special method such as `__eq__` | O(s·m) | O(1) | m = the longest MRO among the subclasses: on every assignment, each subclass that inherits the method looks it up again along its MRO |
| `setattr(module, name, value)` | O(1) avg | O(1) | Stores in the module's `__dict__` |
| Built-in type, such as `setattr(int, "x", 1)` | O(1) | O(1) | Raises `TypeError` |
| Object without a `__dict__`, such as `object()` | O(1) | O(1) | Raises `AttributeError` |
| Non-`str` name | O(1) | O(1) | Raises `TypeError` |

## Setting Attributes by Name

### The Same as Assignment

`setattr()` and the assignment statement go through the same `__setattr__`, so they trigger the
same hooks and, apart from slots declared on a base class, cost the same.

```python
class Config:
    pass

config = Config()
config.host = "localhost"  # O(1) avg
setattr(config, "port", 8000)  # O(1) avg - the same operation

assert vars(config) == {"host": "localhost", "port": 8000}

for key, value in {"debug": True, "retries": 3}.items():
    setattr(config, key, value)  # O(1) avg each
assert config.debug is True and config.retries == 3
```

### Names Built at Run Time

`setattr()` interns an exact `str` name before looking it up, so the instance stores the shared
interned object and the class-side cache hits even when the name was just built. A `str`
subclass is not interned, and a lookup with it walks the MRO every time.

```python
import sys

class Record:
    pass

record = Record()
name = "".join(["col", "or"])  # A new string object
assert name is not sys.intern("color")

setattr(record, name, "red")  # O(1) avg - the name is interned first
stored = next(iter(vars(record)))
assert stored is sys.intern("color")
assert record.color == "red"
```

## Descriptors and Hooks

### Property Setters

A property on the class takes priority over the instance's `__dict__`, so `setattr()` runs the
setter on every call, and a property without one refuses the assignment.

```python
class Temperature:
    def __init__(self):
        self._celsius = 0.0

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("below absolute zero")
        self._celsius = value

    @property
    def kelvin(self):
        return self._celsius + 273.15

t = Temperature()
setattr(t, "celsius", 21.5)  # O(k) - runs the setter
assert t.celsius == 21.5 and "celsius" not in vars(t)

try:
    setattr(t, "kelvin", 300)  # No setter
except AttributeError:
    pass
else:
    raise AssertionError("expected AttributeError")
```

### Custom __setattr__

A class that defines `__setattr__` pays for it on every assignment, including the ones its own
`__init__` makes.

```python
class Tracked:
    def __init__(self):
        object.__setattr__(self, "changes", [])
        self.name = "initial"  # Goes through __setattr__ too

    def __setattr__(self, name, value):
        self.changes.append(name)
        object.__setattr__(self, name, value)

obj = Tracked()
setattr(obj, "name", "renamed")  # O(k) - runs __setattr__
obj.size = 3

assert obj.changes == ["name", "name", "size"]
assert obj.name == "renamed"
```

### __slots__

A slot is a data descriptor on the class, so assigning to it stores in a fixed field. When the
class and its bases declare `__slots__` without listing `__dict__`, instances have no `__dict__`,
and a name with no slot or other descriptor is refused. For a slot declared on a base class,
`setattr()` also checks that the instance's type derives from that base, which scans the MRO.

```python
class Point:
    __slots__ = ("x", "y")

p = Point()
setattr(p, "x", 1)  # O(1)
setattr(p, "y", 2)
assert (p.x, p.y) == (1, 2)

try:
    setattr(p, "z", 3)
except AttributeError:
    pass
else:
    raise AssertionError("expected AttributeError")
```

## Setting Class Attributes

### Subclasses Pay for Class Changes

Assigning to a class invalidates the attribute cache of every subclass that has a valid one, so
it is O(s); the next attribute lookup on each class walks its MRO once. Assigning a special method
also updates every subclass that inherits it, so the new method takes effect on their instances;
each one looks the method up along its own MRO, so a deep line of subclasses costs more than a wide
set of direct ones.

```python
class Base:
    def __eq__(self, other):
        return False

class Child(Base):
    pass

class Own(Base):
    def __eq__(self, other):
        return False

setattr(Base, "__eq__", lambda self, other: True)  # O(s) - Child is updated
assert Child() == Child()
assert not Own() == Own()  # Own keeps its own __eq__

setattr(Base, "limit", 10)  # O(s) - invalidates the caches below Base
assert Child.limit == 10
```

## Common Patterns

### Initializing from a Dictionary

Calling `setattr()` once per item makes n assignments for n items, O(n) when each is O(1), and
runs any setter or `__setattr__` for each one. Updating `vars(obj)` directly is also O(n) but skips them, which is only correct when
nothing should see the values.

```python
class User:
    def __init__(self, **fields):
        for key, value in fields.items():
            setattr(self, key, value)  # O(1) avg each, O(n) in all

user = User(name="Alice", email="alice@example.com", age=30)
assert vars(user) == {"name": "Alice", "email": "alice@example.com", "age": 30}

class Checked:
    def __setattr__(self, name, value):
        if name == "age" and value < 0:
            raise ValueError("age must be non-negative")
        object.__setattr__(self, name, value)

c = Checked()
vars(c).update({"age": -1})  # O(n) - bypasses __setattr__
assert c.age == -1
```

## Performance Best Practices

✅ **Do**:

- Use `setattr()` when the name is known only at run time; it runs the same hooks as `obj.name = value`
- Set class attributes when the class is created rather than reassigning them while instances are in use
- Update `vars(obj)` directly only when no property, descriptor or `__setattr__` should see the values

❌ **Avoid**:

- Reassigning a class attribute in a hot loop, such as a counter on the class: each assignment
  invalidates the caches of the class and its subclasses, and from Python 3.13 a class changed
  and looked up again more than 1,000 times stops being cached
- Reassigning special methods on a class with many subclasses
- `str` subclasses or names over 100 characters as attribute names on deep hierarchies

## Version Notes

- **Python 3.13+**: A class changed and looked up again more than 1,000 times is never cached
  again, so every assignment on its instances walks the MRO

## Related Functions

- **[getattr()](getattr.md)** - Get an attribute by name
- **[delattr()](delattr.md)** - Delete an attribute by name
- **[hasattr()](hasattr.md)** - Check whether an attribute exists
- **[vars()](vars.md)** - The instance's `__dict__`
- **[object()](object_func.md)** - The default `__setattr__` every class inherits
