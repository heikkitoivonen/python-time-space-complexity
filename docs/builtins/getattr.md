# getattr() Function Complexity

The `getattr()` function retrieves the value of a named attribute from an
object: `getattr(obj, 'name')` does the same lookup as `obj.name`, with the
name supplied at run time. It costs what that lookup costs: a cached
class-level lookup plus an instance dict probe, or whatever a user-defined
hook does.

## Complexity Reference

Let `d` be the length of the object's class MRO and `g` the cost, in time and
space, of a user-defined hook: `__getattr__`, `__getattribute__`, or a
descriptor such as a property getter.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getattr(obj, name)` | O(1) avg | O(1) | The class-level lookup is cached per class and name object, for misses as well as hits, so `d` does not matter once the cache is warm - provided `name` is the same `str` object each time, as a literal in the source or a `sys.intern()` result is. A miss raises `AttributeError` |
| `getattr(obj, name)` with a name built at run time | O(d) | O(1) | An f-string, a concatenation or a string read from input is usually a new object on every call, and the cache matches name objects rather than their text, so every call walks the MRO. `sys.intern(name)` returns one shared object per text and restores the cached cost. A `str` subclass, or a name longer than 100 characters, is never cached |
| `getattr(obj, name, default)` | O(1) avg | O(1) | The same lookup; `default` is returned only when the lookup raises `AttributeError`. Any other exception propagates. The `default` expression is evaluated before the call, whether or not it is used |
| `getattr(obj, name)`, first lookup after the class or a base changed | O(d) | O(1) | Walks the MRO once and caches the result. From Python 3.13, once a class has been changed and looked up again more than 1,000 times it is never cached again, and every lookup on it pays O(d) |
| `getattr(obj, name)` through a hook | O(g) | O(g) | On top of the lookup above. A property getter runs on every call, and `__getattr__` runs on every miss |
| `getattr(obj, name)` with a non-`str` name | O(1) | O(1) | Raises `TypeError` before any lookup, with or without a default |

## Basic Usage

### Dynamic Attribute Names

```python
# O(1) avg per name - the same lookup as obj.name
class Config:
    host = "localhost"
    port = 8000
    debug = True

config = Config()

assert getattr(config, 'host') == config.host  # O(1) avg

values = {name: getattr(config, name) for name in ['host', 'port', 'debug']}
assert values == {'host': 'localhost', 'port': 8000, 'debug': True}
```

### Get with Default Value

```python
# O(1) avg - the default replaces an AttributeError, nothing else
class User:
    name = "Alice"
    email = None

user = User()

phone = getattr(user, 'phone', 'Not provided')  # O(1) avg - a miss
email = getattr(user, 'email', 'no@email.com')  # O(1) avg - a hit

assert phone == 'Not provided'
assert email is None  # the attribute exists, so its value wins over the default

try:
    getattr(user, 'phone')
except AttributeError as error:
    assert "'phone'" in str(error)
else:
    raise AssertionError("a miss without a default should raise")
```

## Lookup Cost

### Inheritance Chain Traversal

```python
# The first lookup of a name on a class walks the MRO - O(d)
# Later lookups of that name on that class are cached - O(1) avg
class A:
    attr_a = 'A'

class B(A):
    attr_b = 'B'

class C(B):
    attr_c = 'C'

class D(C):
    attr_d = 'D'

obj = D()
assert D.__mro__ == (D, C, B, A, object)

val = getattr(obj, 'attr_a')  # O(d) once: D, C, B, then found in A
assert val == 'A'
val = getattr(obj, 'attr_a')  # O(1) avg: cached for (D, 'attr_a')
assert val == 'A'

missing = getattr(obj, 'attr_x', None)  # O(d) once, then the miss is cached too
assert missing is None

# Assigning to a class, or to any of its bases, invalidates its cache
C.attr_c = 'C2'
val = getattr(obj, 'attr_a')  # O(d) again, once
assert val == 'A' and getattr(obj, 'attr_c') == 'C2'
```

### What the Default Catches

```python
# Only AttributeError becomes the default; every other exception propagates
class Strict:
    @property
    def broken(self):
        raise KeyError("not an AttributeError")

    @property
    def absent(self):
        raise AttributeError("absent")

obj = Strict()

assert getattr(obj, 'missing', None) is None
assert getattr(obj, 'absent', None) is None  # the getter's AttributeError counts

try:
    getattr(obj, 'broken', None)
except KeyError:
    pass
else:
    raise AssertionError("the KeyError should propagate")

try:
    getattr(obj, 42, None)
except TypeError as error:
    assert "must be string" in str(error)
else:
    raise AssertionError("a non-str name should raise even with a default")
```

### The Default Is Evaluated Eagerly

```python
# The default is an ordinary argument: it is built before getattr() runs
calls = 0

def expensive_default():
    global calls
    calls += 1
    return []

class Cache:
    items = [1, 2, 3]

cache = Cache()

items = getattr(cache, 'items', expensive_default())  # pays for the default anyway
assert items == [1, 2, 3] and calls == 1

# Build the default only on a miss - a private sentinel, since None may be a real value
_missing = object()
items = getattr(cache, 'items', _missing)
if items is _missing:
    items = expensive_default()
assert items == [1, 2, 3] and calls == 1

orders = getattr(cache, 'orders', _missing)
if orders is _missing:
    orders = expensive_default()
assert orders == [] and calls == 2
```

## Performance Patterns

### getattr vs hasattr

```python
# getattr() with a default - one lookup
class Settings:
    timeout = 30

obj = Settings()

value = getattr(obj, 'timeout', None)  # O(1) avg - one lookup
assert value == 30

# hasattr() then getattr() - two lookups of the same name
if hasattr(obj, 'timeout'):
    value = getattr(obj, 'timeout')
else:
    value = None

assert value == 30
```

### Direct Access vs getattr

```python
# Both do the same O(1) avg lookup; getattr() adds one builtin call
class Data:
    value = 42

obj = Data()

direct = obj.value  # name fixed in the source
dynamic = getattr(obj, 'value')  # name chosen at run time
assert direct == dynamic == 42

# With a name known in advance, write obj.value; getattr() is for names held in variables
```

## Common Patterns

### Dispatch by Name

```python
# O(1) avg - one lookup picks the handler, once the built name is interned
import sys

class Processor:
    def process_int(self, val):
        return val * 2

    def process_str(self, val):
        return val.upper()

    def process_list(self, val):
        return len(val)

    def process(self, val):
        """Dispatch on the value's type name - one lookup"""
        # The f-string is a new object per call; interned, it hits the lookup cache
        name = sys.intern(f"process_{type(val).__name__}")
        method = getattr(self, name, None)
        if method is None:
            return None
        return method(val)

processor = Processor()

assert processor.process(5) == 10
assert processor.process("hello") == "HELLO"
assert processor.process([1, 2, 3]) == 3
assert processor.process(1.5) is None
```

### Optional Hooks

```python
# O(1) avg per event - call a handler only if the object defines one
class Plugin:
    def __init__(self):
        self.calls = []

    def on_init(self):
        self.calls.append('init')

    def on_start(self):
        self.calls.append('start')

def trigger(obj, event_name):
    """Call an event handler if it exists - one lookup"""
    handler = getattr(obj, event_name, None)
    if callable(handler):
        handler()

plugin = Plugin()

trigger(plugin, 'on_init')
trigger(plugin, 'on_start')
trigger(plugin, 'on_stop')  # no handler, no error
assert plugin.calls == ['init', 'start']
```

### Reading Several Names

```python
# O(n) - one lookup per name, for n names
class Settings:
    debug = False
    timeout = 30
    max_connections = 100

def snapshot(obj, names):
    """Read the named attributes into a dict - O(n)"""
    return {name: getattr(obj, name) for name in names}

assert snapshot(Settings(), ['debug', 'timeout']) == {'debug': False, 'timeout': 30}

# dir() lists and sorts every attribute of the object and its whole MRO,
# so copying "everything" grows with that count, not with the names wanted
public = [name for name in dir(Settings()) if not name.startswith('_')]
assert public == ['debug', 'max_connections', 'timeout']
```

## Edge Cases

### Hooks Run Inside getattr()

```python
# A property getter runs on every getattr(); __getattr__ runs on every miss
class Example:
    present = 1

    def __init__(self):
        self.getter_runs = 0
        self.misses = []

    @property
    def computed(self):  # its cost is the call's
        self.getter_runs += 1
        return 100

    def __getattr__(self, name):  # reached only when the normal lookup fails
        self.misses.append(name)
        raise AttributeError(name)

obj = Example()

assert getattr(obj, 'computed') == 100
assert getattr(obj, 'computed') == 100
assert obj.getter_runs == 2

assert getattr(obj, 'present') == 1
assert obj.misses == []
assert getattr(obj, 'missing', None) is None
assert obj.misses == ['missing']
```

### __getattribute__ Sees Every Lookup

```python
# __getattribute__ replaces the lookup itself - every getattr() call runs it
lookups = 0

class Counting:
    attr = 1

    def __getattribute__(self, name):
        global lookups
        lookups += 1
        return super().__getattribute__(name)

obj = Counting()

getattr(obj, 'attr')  # one lookup
getattr(obj, 'missing', None)  # one lookup, then the default
assert lookups == 2
```

## Performance Best Practices

✅ **Do**:

- Use `getattr()` with a default instead of `hasattr()` followed by `getattr()` - one lookup, not two
- Pass a private sentinel as the default and build the real fallback only when it comes back, when the fallback is expensive
- Write `obj.name` when the name is fixed in the source
- Pass a name built at run time through `sys.intern()` when it is looked up repeatedly on a deep hierarchy - a fresh string object misses the lookup cache
- Expect property getters and `__getattr__` to run inside it

❌ **Avoid**:

- An expensive expression as the default - it runs even when the attribute exists
- Relying on the default to swallow anything but `AttributeError`
- `dir()` as a way to read a few known names - it builds and sorts the whole attribute list
- Reassigning a class's attributes in a hot loop on Python 3.13 or later - after more than 1,000 rounds of change and lookup the class is never cached again

## Version Notes

- **Python 3.13+**: A class that has been changed and looked up again more than 1,000 times stops being cached, so lookups on it are O(d) from then on
- **All Python 3**: A non-`str` name raises `TypeError`, with or without a default

## Related Functions

- **[hasattr()](hasattr.md)** - Check attribute existence
- **[setattr()](setattr.md)** - Set attribute value
- **[delattr()](delattr.md)** - Delete attribute
- **[dir()](dir.md)** - List attributes
- **[vars()](vars.md)** - Get __dict__
- **[type()](type_func.md)** - Get object type
