# staticmethod() Decorator Complexity

`staticmethod` wraps a function so that looking it up on a class or an instance returns the
function itself, with nothing bound to it: no `self`, no `cls`. The wrapper holds the function and
copies of its name and docstring, and keeps no per-instance state.

The function costs what its own body does; the bounds below are the work the wrapper adds to it,
with a function's annotations and a call's arguments treated as fixed-size. `d` is the length of a class's MRO, `len(cls.__mro__)`. Class-side attribute lookups are cached
per type, as described on the [object() page](object_func.md), so the access rows assume the cache
is warm; an uncached lookup costs O(d).

## Complexity Reference

### staticmethod

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `staticmethod(function)` | O(1) | O(1) | Stores `function` without calling it, and copies its `__module__`, `__name__`, `__qualname__` and `__doc__`; any object is accepted, callable or not |
| `@staticmethod` on a function | O(1) | O(1) | The same as `staticmethod(func)` |
| `sm.__func__`, `sm.__wrapped__` | O(1) | O(1) | The wrapped object itself |
| `sm(*args, **kwargs)` | O(1) | O(1) | Plus one call of the wrapped function |

### Attribute Access

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Class.method`, `obj.method` | O(1) | O(1) | Returns the wrapped function itself; no bound method is created |
| `obj.method(*args)` | O(1) | O(1) | Plus one call of the function, with no `self` or `cls` argument |
| `obj.method` where a base class defines the static method | O(1) | O(1) | The cached lookup does not grow with d |
| `obj.method` where `obj.__dict__` has the same name | O(1) | O(1) | The instance entry wins: a static method is a non-data descriptor |

## Defining Static Methods

### Decorating a Function

A static method is called the same way from the class and from an instance, and receives only the
arguments it is given. The wrapper keeps the function and its name and docstring.

```python
class Temperature:
    @staticmethod
    def to_fahrenheit(celsius):
        """Convert Celsius to Fahrenheit."""
        return celsius * 9 / 5 + 32

assert Temperature.to_fahrenheit(100) == 212.0    # O(1) plus the body
assert Temperature().to_fahrenheit(0) == 32.0     # Same function, no self

wrapper = Temperature.__dict__["to_fahrenheit"]
assert isinstance(wrapper, staticmethod)
assert wrapper.__func__ is wrapper.__wrapped__ is Temperature.to_fahrenheit
assert wrapper.__name__ == "to_fahrenheit"
assert wrapper.__doc__ == "Convert Celsius to Fahrenheit."
assert wrapper(37) == 98.6  # The wrapper itself is callable
```

## Accessing Static Methods

### No Bound Object Is Created

Looking up an ordinary method on an instance builds a new bound method on every access. Looking up a
static method returns the same function object each time, from the class and from any instance.

```python
class Shapes:
    @staticmethod
    def square_area(side):
        return side * side

    def describe(self):
        return "shapes"

shapes = Shapes()
assert shapes.square_area is Shapes.square_area  # O(1) - the function itself
assert shapes.square_area is Shapes.__dict__["square_area"].__func__
assert shapes.describe is not shapes.describe    # A new bound method each time
assert shapes.square_area(3) == 9
```

### Instance Attributes Shadow a Static Method

A static method defines no `__set__`, so an attribute of the same name stored on an instance takes
precedence over it for that instance only.

```python
class Greeter:
    @staticmethod
    def greet():
        return "hello"

custom = Greeter()
custom.greet = lambda: "hi"  # Stored in the instance __dict__

assert custom.greet() == "hi"
assert Greeter().greet() == "hello"
assert Greeter.greet() == "hello"
```

### Inherited Static Methods

A static method defined on a base class is found through the class's cached attribute lookup, so a
deep hierarchy costs no more per access than a shallow one. A subclass can replace it with its own.

```python
class Base:
    @staticmethod
    def label():
        return "base"

class Middle(Base):
    pass

class Leaf(Middle):
    @staticmethod
    def label():
        return "leaf"

assert Middle().label() == "base"  # O(1) - cached lookup
assert Leaf().label() == "leaf"
assert Middle.label is Base.label
```

## Common Patterns

### Static Methods Versus Class Methods

A static method does not know which class it was called on. An alternative constructor written as a
static method builds the class it names, even when called on a subclass; a class method receives
the class it was called on.

```python
import math

class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    @staticmethod
    def from_polar_static(r, theta):
        return Vector(r * math.cos(theta), r * math.sin(theta))

    @classmethod
    def from_polar(cls, r, theta):
        return cls(r * math.cos(theta), r * math.sin(theta))

class Velocity(Vector):
    pass

assert type(Velocity.from_polar_static(1, 0)) is Vector  # Ignores the subclass
assert type(Velocity.from_polar(1, 0)) is Velocity

v = Vector.from_polar(2, 0)
assert (v.x, v.y) == (2.0, 0.0)
```

### Abstract Static Methods

`abc.abstractmethod` applied under `staticmethod` makes the class abstract until a subclass
supplies the method.

```python
from abc import ABC, abstractmethod

class Parser(ABC):
    @staticmethod
    @abstractmethod
    def parse(text):
        ...

class CommaParser(Parser):
    @staticmethod
    def parse(text):
        return text.split(",")

assert Parser.__abstractmethods__ == frozenset({"parse"})
assert CommaParser().parse("a,b") == ["a", "b"]

try:
    Parser()
except TypeError as error:
    assert "abstract" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Performance Best Practices

✅ **Do**:

- Use a static method for a helper that needs neither the instance nor the class
- Use a class method for an alternative constructor that subclasses should inherit

❌ **Avoid**:

- Expecting a static method to see the class it was called on; it receives nothing
- Assigning an instance attribute with a static method's name unless shadowing it is intended

## Related Functions

- **[classmethod()](classmethod.md)** - A descriptor that passes the class as the first argument
- **[property()](property.md)** - A data descriptor that routes attribute access through functions
- **[object()](object_func.md)** - The cached class-side attribute lookup every access goes through
- **[callable()](callable.md)** - Whether an object can be called
