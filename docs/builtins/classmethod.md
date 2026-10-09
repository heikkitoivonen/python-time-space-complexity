# classmethod() Decorator Complexity

The `classmethod()` decorator wraps a function so that it receives the class as its first
argument instead of an instance. Applying it builds one small descriptor when the class body
runs; each later access that reaches it, through the class or an instance, binds the function
to the class.

`d` is the number of classes in the class's MRO, `len(cls.__mro__)`. The bounds exclude the
method body, which costs what it does.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `classmethod(func)`, `@classmethod` | O(1) | O(1) | Once, when the class body runs |
| `Cls.method`, `obj.method` | O(1) | O(1) | Builds a new bound method on each access, with the class as `__self__` |
| `Cls.method(...)` | O(1) | O(1) | Plus the method body; the class is passed as the first argument |
| Looking up an inherited classmethod | O(1) | O(1) | The type attribute cache answers repeated lookups at any depth |
| First lookup after the class or a base changes | O(d) | O(d) | Walks the MRO, then the result is cached again |
| Lookup on a class modified and read over and over (3.13+) | O(d) | O(1) | The class stops being cached; see [Class State and the Attribute Cache](#class-state-and-the-attribute-cache) |

## Basic Usage

### Define a Class Method

```python
class Counter:
    created = 0

    @classmethod
    def create(cls):
        cls.created += 1  # O(1) - modifies the class
        return cls()

first = Counter.create()  # O(1)
second = Counter.create()
assert Counter.created == 2
assert isinstance(first, Counter)
```

### Alternative Constructors

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    @classmethod
    def from_tuple(cls, point_tuple):
        x, y = point_tuple
        return cls(x, y)  # O(1)

    @classmethod
    def from_string(cls, point_str):
        x, y = map(float, point_str.split(","))  # O(len(point_str))
        return cls(x, y)

p1 = Point.from_tuple((1, 2))
p2 = Point.from_string("3.5,4.5")
assert (p1.x, p1.y) == (1, 2)
assert (p2.x, p2.y) == (3.5, 4.5)
```

## Binding the Class

The class stores the `classmethod` object itself. Reading the attribute calls its `__get__()`,
which builds a bound method whose `__self__` is the class - also when the attribute is read
through an instance, whose only contribution is its type. An instance attribute of the same
name shadows the classmethod, because it is a non-data descriptor.

```python
class Example:
    @classmethod
    def info(cls):
        return f"I am {cls.__name__}"

descriptor = Example.__dict__["info"]
assert type(descriptor) is classmethod

bound = Example.info  # O(1) - a new bound method
assert bound.__self__ is Example
assert Example.info is not Example.info  # a fresh object on each access
assert Example.info == Example.info  # but equal ones

obj = Example()
assert obj.info.__self__ is Example  # the instance is not passed
assert obj.info() == Example.info() == "I am Example"
```

## Inheritance and the MRO

An inherited classmethod receives the class it was looked up on, so a factory written once
builds instances of every subclass. Finding the method on a deep subclass walks the MRO only
when the type attribute cache misses; repeated lookups cost the same at any depth.

```python
class Base:
    @classmethod
    def create(cls):
        return cls()

class Child(Base):
    pass

obj = Child.create()  # O(d) the first time, then O(1) while cached
assert type(obj) is Child

# A staticmethod receives no class, so this factory names one
class HardcodedBase:
    @staticmethod
    def create():
        return HardcodedBase()

class HardcodedChild(HardcodedBase):
    pass

assert type(HardcodedChild.create()) is HardcodedBase
```

## Class State and the Attribute Cache

Assigning a class attribute - `cls.created += 1` in a classmethod - modifies the class, so the
next lookup of an attribute found through the MRO of it or its subclasses misses the cache and
walks the MRO. On Python 3.13+ a class that is modified and then read over and over - a counter
bumped by every call - stops being cached at all, and from then on every lookup on it is O(d). Keep state that changes on every call in a mutable object the class
holds: changing that object does not modify the class.

```python
import itertools

class Order:
    _ids = itertools.count(1)  # the counter changes, the class does not

    def __init__(self, order_id):
        self.order_id = order_id

    @classmethod
    def create(cls):
        return cls(next(cls._ids))  # O(1) - no class attribute is assigned

first = Order.create()
second = Order.create()
assert (first.order_id, second.order_id) == (1, 2)
```

## classmethod vs staticmethod

Both are found by the same attribute lookup. A `staticmethod` returns the plain function, so
reading it builds nothing; a `classmethod` binds the class on every access.

```python
class Both:
    @classmethod
    def from_class(cls):
        return cls

    @staticmethod
    def plain():
        return "no binding"

assert Both.plain is Both.plain  # O(1) - the function itself
assert Both.from_class is not Both.from_class  # O(1) - a new bound method each time
assert Both.from_class() is Both
```

## Common Patterns

### Plugin Registry

```python
class Plugin:
    plugins = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Plugin.plugins[cls.__name__] = cls  # O(1) - once per subclass definition

    @classmethod
    def create(cls, plugin_name):
        plugin_class = cls.plugins.get(plugin_name)  # O(1) average
        return plugin_class() if plugin_class else None

class AudioPlugin(Plugin):
    def play(self):
        return "Playing audio"

class VideoPlugin(Plugin):
    def play(self):
        return "Playing video"

assert Plugin.create("AudioPlugin").play() == "Playing audio"
assert Plugin.create("VideoPlugin").play() == "Playing video"
assert Plugin.create("Missing") is None
```

### Conversion Constructors

```python
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    @classmethod
    def from_list(cls, lst):
        return cls(lst[0], lst[1])  # O(1)

    @classmethod
    def from_dict(cls, d):
        return cls(d["x"], d["y"])  # O(1) average

    def to_list(self):
        return [self.x, self.y]

assert Vector.from_list([1, 2]).to_list() == [1, 2]
assert Vector.from_dict({"x": 3, "y": 4}).to_list() == [3, 4]
```

## Performance Best Practices

✅ **Do**:

- Use a classmethod for alternative constructors, so subclasses get instances of themselves
- Keep per-call state, such as an ID counter, in a mutable object the class holds
- Use `staticmethod` when the function needs neither the class nor an instance - reading it builds no bound method

❌ **Avoid**:

- Assigning a class attribute on every call in a hot path - each assignment costs the class and its subclasses their cached lookups, and on 3.13+ can stop the class being cached at all
- Hardcoding the class name in a factory, which builds the base class for every subclass
- Wrapping `property` in `classmethod` - it computes a value on 3.10 to 3.12 only

## Version Notes

- **Python 3.13+**: `classmethod` no longer wraps other descriptors: `@classmethod` over `@property` gives a bound method, not the property's value. The chaining was deprecated in 3.11
- **Python 3.13+**: A class modified and read over and over stops using the type attribute cache, and lookups on it are O(d)
- **Python 3.10+**: A `classmethod` copies `__name__`, `__qualname__`, `__module__` and `__doc__` from its function, and exposes the function as `__wrapped__`

## Related Functions

- **[staticmethod()](staticmethod.md)** - A method with no implicit first argument, returned unbound
- **[property()](property.md)** - A computed attribute, the other common descriptor
- **[type()](type_func.md)** - The class a classmethod receives when called through an instance
- **[super()](super.md)** - Call the parent class's classmethod
- **[isinstance()](isinstance.md)** - Check instance type
