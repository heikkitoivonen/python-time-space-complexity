# dir() Function Complexity

The `dir()` function returns a new, sorted list of names. With no argument it lists the names in
the current local scope; with an argument it calls that object's `__dir__()`, turns whatever comes
back into a list and sorts it. Every call builds and sorts a fresh list, so it is an exploration
tool, not a fast membership test.

`n` is the names in the returned list, `k` is the entries in an instance's `__dict__`, and `p` is
the class-dictionary entries merged while walking the class's bases (defined in the next
paragraph). Bounds treat hashing and comparing one name as O(1).

For an ordinary instance, `object.__dir__` copies the instance `__dict__`, then merges the
`__dict__` of the class and recurses into each entry of `__bases__`. It follows `__bases__`, not
the MRO, and does not remember which classes it has visited: a class reachable along several
inheritance paths is merged once per path. With single inheritance `p` is the sum of the class
dictionaries along the MRO; with a chain of diamonds it doubles at every diamond.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dir(obj)`, default `object.__dir__` | O(k + p + n log n) | O(n) | Instance `__dict__` copy, class merge, then the sort |
| `dir(cls)`, `type.__dir__` | O(p + n log n) | O(n) | The class and its bases; metaclass attributes are not listed |
| `dir(module)` | O(n log n) | O(n) | n = module globals; a module-level `__dir__()` function replaces them |
| `dir(obj)` with a custom `__dir__()` | O(D + n log n) | O(n) | D = the cost of `__dir__()` and of iterating its result, which is copied to a list and sorted |
| `dir()` with no argument | O(n log n) | O(n) | n = names in the local scope |

## Basic Usage

### Instances and Classes

The result includes instance attributes, class attributes and everything inherited, sorted.

```python
class Base:
    shared = 1

class Child(Base):
    def method(self):
        pass

obj = Child()
obj.own = 2

names = dir(obj)  # O(k + p + n log n)
assert names == sorted(names)
assert {"own", "method", "shared", "__init__"} <= set(names)
assert "own" not in dir(Child)  # instance attributes belong to the instance only
```

### Custom __dir__ and Modules

`dir()` sorts whatever `__dir__()` returns, so the result is always a sorted list even when the
method returns another iterable.

```python
import math

class Proxy:
    def __dir__(self):
        return ("zeta", "alpha")

assert dir(Proxy()) == ["alpha", "zeta"]  # O(D + n log n)

names = dir(math)  # O(n log n) - n = module globals
assert "sqrt" in names and names == sorted(names)
```

## Complexity Details

### Shared Bases Are Merged Once Per Path

Each diamond in a chain doubles the number of paths to the classes above it, so `dir()` merges the
root's dictionary 2^d times for d diamonds even though the MRO has only 3d + 2 classes.

```python
def diamonds(depth):
    top = type("Top", (), {f"a{i}": i for i in range(100)})
    cls = top
    for i in range(depth):
        left = type(f"L{i}", (cls,), {})
        right = type(f"R{i}", (cls,), {})
        cls = type(f"J{i}", (left, right), {})
    return cls

deep = diamonds(12)
assert len(deep.__mro__) == 3 * 12 + 2
names = dir(deep)  # O(p + n log n) - p counts Top's 100 names 2**12 times
assert "a99" in names
```

### dir() Is Not a Complete Attribute List

`dir()` lists stored names. Attributes that `__getattr__` produces on demand, and methods defined on
a class's metaclass, are reachable without appearing.

```python
class Lazy:
    def __getattr__(self, name):
        return name.upper()

obj = Lazy()
assert obj.anything == "ANYTHING"
assert "anything" not in dir(obj)

assert hasattr(type, "mro") and "mro" not in dir(int)
assert int.mro() == [int, object]
```

## Common Patterns

### Checking for One Attribute

`name in dir(obj)` builds and sorts the whole list and then scans it; `hasattr()` does one
attribute lookup. It also sees attributes that `dir()` omits.

```python
class Config:
    debug = False

cfg = Config()
assert hasattr(cfg, "debug")  # one lookup
assert "debug" in dir(cfg)    # O(k + p + n log n), then an O(n) scan
```

### Filtering Public Names

Call `dir()` once and filter the list, rather than calling it per test.

```python
class Service:
    def fetch(self):
        pass

    def store(self):
        pass

    def _cache(self):
        pass

    limit = 10

service = Service()
public_methods = [
    name for name in dir(service)  # O(k + p + n log n)
    if not name.startswith("_") and callable(getattr(service, name))
]
assert public_methods == ["fetch", "store"]
```

### Instance Attributes Only

`vars(obj)` returns the instance `__dict__` itself, without copying, merging or sorting; use it
when inherited names are not wanted.

```python
class Point:
    dims = 2

    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
assert vars(p) is p.__dict__        # O(1) - no copy
assert sorted(vars(p)) == ["x", "y"]
assert "dims" in dir(p) and "dims" not in vars(p)
```

## Performance Best Practices

✅ **Do**:

- Use `hasattr()` or `getattr(obj, name, default)` to test one name
- Use `vars(obj)` for instance attributes alone
- Keep the list from one `dir()` call if you filter it several ways

❌ **Avoid**:

- `name in dir(obj)` in a loop: each test rebuilds and sorts the list
- Calling `dir()` on classes with repeated diamond inheritance in hot code
- Treating `dir()` as the full set of reachable attributes

## Version Notes

- **All Python 3**: the result is a sorted list; the default `__dir__` walks `__bases__`
  recursively without de-duplicating shared bases

## Related Functions

- **[vars()](vars.md)** - the instance `__dict__` itself, with no copy or sort
- **[hasattr()](hasattr.md)** - test one name with a single lookup
- **[getattr()](getattr.md)** - fetch a value, with a default for a missing name
- **[help()](help.md)** - documentation rather than a name list
- **[type()](type_func.md)** - the class whose bases `dir()` walks
