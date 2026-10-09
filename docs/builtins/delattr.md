# delattr() Function Complexity

The `delattr()` function removes a named attribute from an object. `delattr(obj, "name")` is
exactly `del obj.name`: both call `type(obj).__delattr__`, so a property deleter, a descriptor's
`__delete__` or a class's own `__delattr__` runs in the same way.

`d` is the classes in `type(obj).__mro__`, `s` is the subclasses of a class, direct and indirect,
and `k` is the cost of a user-defined `__delattr__` or `__delete__`. Attribute names are treated
as hashing and comparing in O(1). The bounds assume cached type lookups; a type
attribute cache miss adds O(d).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `delattr(obj, name)`, instance attribute | O(1) avg | O(1) | Deletes from the instance's `__dict__` once no data descriptor on the class claims the name |
| `delattr(obj, name)`, `__slots__` attribute | O(1) | O(1) | Clears the slot |
| `delattr(obj, name)`, property or descriptor | O(k) | O(k) | Runs the deleter or `__delete__`, not the dict deletion |
| `delattr(obj, name)`, custom `__delattr__` | O(k) | O(k) | Runs the class's `__delattr__` |
| `delattr(cls, name)`, class attribute | O(s) | O(1) | Invalidates the attribute cache of the class and of each subclass whose cache is still valid |
| `delattr(module, name)` | O(1) avg | O(1) | Deletes from the module's `__dict__` |
| Missing attribute | O(1) avg | O(1) | Raises `AttributeError` |

## Instance Attributes

Deleting an attribute that lives in the instance's `__dict__` is one hash-table deletion. A class
attribute is not on the instance, so deleting it through the instance raises:

```python
class Config:
    default = 42

config = Config()
config.host = "localhost"
config.port = 8000

delattr(config, "host")  # O(1) avg
del config.port  # O(1) avg - the same operation
assert vars(config) == {}

try:
    delattr(config, "default")  # lives on the class, not the instance
except AttributeError as e:
    assert "default" in str(e)
else:
    raise AssertionError("expected AttributeError")
assert config.default == 42
```

### `__slots__`

A slot is cleared in place. Deleting a slot that holds no value raises `AttributeError`:

```python
class Point:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
delattr(p, "x")  # O(1)
assert not hasattr(p, "x")

try:
    delattr(p, "x")
except AttributeError:
    pass
else:
    raise AssertionError("expected AttributeError")
```

## Properties, Descriptors and `__delattr__`

A data descriptor on the class takes priority over the instance's `__dict__`, so `delattr()` costs
whatever its deleter costs. A property without a deleter raises `AttributeError`:

```python
class Cached:
    def __init__(self):
        self._value = 1
        self.log = []

    @property
    def value(self):
        return self._value

    @value.deleter
    def value(self):
        self.log.append("deleted")
        del self._value

obj = Cached()
delattr(obj, "value")  # O(k) - runs the deleter
assert obj.log == ["deleted"]
assert not hasattr(obj, "_value")


class ReadOnly:
    @property
    def value(self):
        return 1

try:
    delattr(ReadOnly(), "value")
except AttributeError:
    pass
else:
    raise AssertionError("expected AttributeError")
```

A class that defines `__delattr__` sees every deletion, whether written as `del` or `delattr()`:

```python
class Tracked:
    def __init__(self):
        object.__setattr__(self, "deleted", [])

    def __delattr__(self, name):
        self.deleted.append(name)
        super().__delattr__(name)

obj = Tracked()
obj.x = 1
obj.y = 2
delattr(obj, "x")  # O(k) - calls Tracked.__delattr__
del obj.y
assert obj.deleted == ["x", "y"]
```

## Deleting Class Attributes

Python caches attribute lookups per class. Deleting (or setting) an attribute on a class
invalidates that cache for the class and its subclasses, so the cost grows with the size of the
class hierarchy below it. Change class attributes at setup time, not in a hot loop:

```python
class Base:
    flag = True

class Child(Base):
    pass

assert Child().flag
delattr(Base, "flag")  # O(s) - s = subclasses of Base
assert not hasattr(Child(), "flag")
```

## Deleting Many Attributes

For ordinary instance attributes each `delattr()` call is O(1), so deleting `n` of them is O(n).
To drop everything in the instance `__dict__`, `vars(obj).clear()` does it in one call without
naming the attributes; it bypasses any `__delattr__` the class defines and leaves `__slots__`
values alone:

```python
class State:
    pass

state = State()
for i in range(100):
    setattr(state, f"attr{i}", i)

for i in range(50):
    delattr(state, f"attr{i}")  # O(1) each, O(n) in total
assert len(vars(state)) == 50

vars(state).clear()  # O(n)
assert vars(state) == {}
```

## Common Patterns

### Invalidating a Cached Value

Deleting a cached attribute makes the next access recompute it. `functools.cached_property`
stores its value in the instance `__dict__`, so `delattr()` is the way to reset it:

```python
from functools import cached_property

class Report:
    def __init__(self, rows):
        self.rows = rows
        self.computed = 0

    @cached_property
    def total(self):
        self.computed += 1
        return sum(self.rows)

report = Report([1, 2, 3])
assert report.total == 6
report.rows.append(4)
assert report.total == 6  # cached

delattr(report, "total")  # O(1) avg - drops the cached value
assert report.total == 10
assert report.computed == 2
```

### Removing Optional Attributes

`delattr()` raises on a missing name. Catching the exception keeps it to one call per name;
checking with `hasattr()` first adds a full attribute read to each one:

```python
class Session:
    def __init__(self):
        self.user = "alice"
        self.token = "abc"

def drop(obj, names):
    for name in names:  # O(n)
        try:
            delattr(obj, name)  # O(1) avg
        except AttributeError:
            pass

session = Session()
drop(session, ["token", "password"])
assert vars(session) == {"user": "alice"}
```

## Performance Best Practices

✅ **Do**:

- Use `delattr()` when the attribute name is only known at run time; write `del obj.name`
  otherwise
- Use `vars(obj).clear()` to empty the instance `__dict__` at once
- Delete a `cached_property` value to force it to be recomputed

❌ **Avoid**:

- Deleting or setting class attributes in a hot loop: each change is O(s) in the subclasses
- Expecting `delattr()` on an instance to remove a class attribute
- Assuming `delattr()` is O(1) when the class defines `__delattr__` or the name is a property

## Version Notes

- **All Python 3**: `delattr(obj, name)` is equivalent to `del obj.name`; `name` must be a string

## Related Functions

- **[getattr()](getattr.md)** - Read an attribute by name
- **[setattr()](setattr.md)** - Set an attribute by name
- **[hasattr()](hasattr.md)** - Check whether an attribute exists
- **[vars()](vars.md)** - The instance `__dict__`, for bulk changes
- **[property()](property.md)** - Deleters run by `delattr()`
