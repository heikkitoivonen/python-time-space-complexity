# object() Function Complexity

`object` is the base class of every Python class, and `object()` creates a bare instance of it: a
fixed-size object with no `__dict__`, useful mainly as a unique sentinel. The equality, hashing,
`repr()` and attribute-access behaviour every class starts with comes from `object`, so its costs
are the defaults a class has until it overrides them.

`d` is the length of a class's MRO, `len(cls.__mro__)`, and `a` is the attributes an instance
stores in its `__dict__`. Hash-table operations on attribute names are priced as O(1) on average
and amortized, a class's module and qualified names as constant length, and a class's `__init__`
or other overriding method costs what its own code does. The attribute rows assume the class-side
lookup is cached, as it is after a type's first lookup of a name; an uncached lookup costs O(d)
time and up to O(d) stack.

## Complexity Reference

### object()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `object()` | O(1) | O(1) | Every instance has the same fixed size; any argument raises `TypeError` |
| Setting an attribute on an `object()` instance | O(1) | O(1) | Raises `AttributeError`: the instance has no `__dict__` |

### Inherited Defaults

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `a == b`, `a != b` | O(1) | O(1) | Identity: an object is equal only to itself |
| `a < b`, `a <= b`, `a > b`, `a >= b` | O(1) | O(1) | Raise `TypeError` |
| `hash(obj)` | O(1) | O(1) | Derived from the object's identity and constant for its lifetime; a class that defines `__eq__` without `__hash__` is unhashable |
| `repr(obj)`, `str(obj)` | O(1) | O(1) | `<module.QualName object at 0x...>`; `str()` falls back to `repr()` |
| `format(obj, spec)` | O(1) | O(1) | An empty `spec` gives `str(obj)`; any other raises `TypeError` |

### Subclass Instances

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cls()` where `cls` keeps `object.__new__` and `object.__init__` | O(1) | O(1) | Without `__slots__`, which add one field each to every instance; does not grow with d; arguments raise `TypeError` unless the class defines `__init__` or `__new__`, which then adds its own cost |
| Freeing an instance when its last reference goes | O(d) | O(1) | Walks up the base classes to the nearest built-in one, plus freeing what the instance holds |
| `obj.attr`, found or missing | O(1) | O(1) | Class-side lookups are cached per type; modifying a class on the MRO makes the next lookup uncached |
| `obj.attr = value`, `del obj.attr` | O(1) | O(1) | The same class-side lookup as reading, then one entry in the instance's `__dict__` |
| Storing a attributes on an instance | O(a) | O(a) | One `__dict__` entry each; a class has no `__dict__` when it and every base other than `object` define `__slots__` without listing `__dict__` |

## Creating Objects

### Sentinels

Each `object()` call returns a new, distinct instance, so one makes a marker no caller can pass by
accident. Compare it with `is`, which is O(1).

```python
_MISSING = object()

def lookup(mapping, key):
    value = mapping.get(key, _MISSING)  # O(1) average
    if value is _MISSING:  # O(1) - identity
        return "absent"
    return value

data = {"a": None}
assert lookup(data, "a") is None  # A stored None is still found
assert lookup(data, "b") == "absent"
assert object() is not object()
```

### object() Instances Hold No Attributes

A bare instance has no `__dict__`, so it cannot store attributes, and every instance has the same
size. Define a class, even an empty one, to get a namespace.

```python
import sys

obj = object()
assert not hasattr(obj, "__dict__")
assert sys.getsizeof(obj) == sys.getsizeof(object())  # O(1) - fixed size

try:
    obj.name = "x"
except AttributeError:
    pass
else:
    raise AssertionError("expected AttributeError")

try:
    object(1)
except TypeError as error:
    assert "takes no arguments" in str(error)
else:
    raise AssertionError("expected TypeError")

class Namespace:
    pass

ns = Namespace()
ns.name = "x"  # O(1) - stored in ns.__dict__
assert ns.__dict__ == {"name": "x"}
```

## Inherited Defaults

### Equality and Hashing

The default `==` is identity, and the default hash is derived from identity, so both are O(1)
whatever the object holds. Defining `__eq__` without `__hash__` sets `__hash__` to `None`: the
instances can no longer be set members or dict keys.

```python
a, b = object(), object()
assert a == a and a != b  # O(1) - identity
assert hash(a) == hash(a)  # O(1) - stable for the object's lifetime
assert len({a, b, a}) == 2

class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __eq__(self, other):
        return (self.x, self.y) == (other.x, other.y)

assert Point(1, 2) == Point(1, 2)
assert Point.__hash__ is None
try:
    {Point(1, 2)}
except TypeError as error:
    assert "unhashable" in str(error)
else:
    raise AssertionError("expected TypeError")
```

### Ordering, repr and format

`object` defines no ordering, so `<` and the other ordering operators raise `TypeError` until a
class implements them. `repr()` names the class and the address; `format()` accepts only an empty
format spec.

```python
a, b = object(), object()

try:
    a < b
except TypeError as error:
    assert "not supported" in str(error)
else:
    raise AssertionError("expected TypeError")

text = repr(a)  # O(1)
assert text.startswith("<object object at 0x")
assert str(a) == text  # str() falls back to repr()
assert format(a, "") == text

try:
    format(a, ">20")
except TypeError as error:
    assert "unsupported format string" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Subclasses

### Constructor Arguments

A class that defines neither `__init__` nor `__new__` inherits both from `object`, and they reject
arguments. Creating an instance does not grow with the depth of the class hierarchy, and an
`__init__` adds whatever it does. Freeing an instance does grow with it: deallocation walks up the
base classes to the nearest built-in one, which matters only for unusually deep hierarchies.

```python
class Plain:
    pass

assert isinstance(Plain(), Plain)  # O(1)
try:
    Plain(1)
except TypeError as error:
    assert "takes no arguments" in str(error)
else:
    raise AssertionError("expected TypeError")

class Named:
    def __init__(self, name):
        self.name = name  # O(1)

assert Named("x").name == "x"
```

### Attribute Lookup

Reading an attribute looks it up on the class first, through the MRO, then in the instance's
`__dict__`. The class-side result is cached per type, so even a name inherited from far up a deep
hierarchy is found in O(1). Modifying a class invalidates the cache for it and its subclasses, and
the next lookup walks the MRO once.

```python
class Root:
    greeting = "hello"

cls = Root
for i in range(50):
    cls = type(f"Level{i}", (cls,), {})

obj = cls()
assert len(type(obj).__mro__) == 52
assert obj.greeting == "hello"  # O(1) once cached
obj.own = 1  # O(1) - into obj.__dict__
assert obj.own == 1

Root.greeting = "hi"  # Invalidates the cache below Root
assert obj.greeting == "hi"  # O(d) once, then O(1) again
```

### __slots__ and the Instance __dict__

An instance with a attributes holds a `__dict__` of a entries. A class that lists its attributes
in `__slots__` stores them at fixed offsets instead. When every base class other than `object` does
the same and none lists `__dict__`, the instance has no `__dict__` and cannot gain attributes it did not declare.

```python
class WithDict:
    def __init__(self):
        self.x = 1
        self.y = 2

class WithSlots:
    __slots__ = ("x", "y")

    def __init__(self):
        self.x = 1
        self.y = 2

assert WithDict().__dict__ == {"x": 1, "y": 2}  # O(a) entries
assert not hasattr(WithSlots(), "__dict__")

slotted = WithSlots()
try:
    slotted.z = 3
except AttributeError:
    pass
else:
    raise AssertionError("expected AttributeError")
```

## Performance Best Practices

✅ **Do**:

- Use a module-level `object()` as a sentinel and test it with `is`
- Define `__hash__` alongside `__eq__` when instances must be dict keys or set members
- Use `__slots__` for classes with many instances and a fixed set of attributes

❌ **Avoid**:

- Setting attributes on a bare `object()`; it has no `__dict__`
- Modifying classes on a hot path; each change makes the next attribute lookup walk the MRO
- Relying on `<` between instances of a class that does not define ordering

## Version Notes

- **All Python 3**: every class inherits from `object`, whether or not its definition names it.

## Related Functions

- **[type()](type_func.md)** - Inspect a class or create one dynamically
- **[isinstance()](isinstance.md)** - Check an instance against a class and its MRO
- **[id()](id.md)** - The identity that the default `==` and `hash()` use
- **[hash()](hash.md)** - Hash an object, including the identity-based default
- **[dir()](dir.md)** - List the attributes an object and its classes provide
- **[vars()](vars.md)** - The instance `__dict__` that subclass attributes live in
