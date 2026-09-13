# hasattr() Function Complexity

The `hasattr()` function checks whether an object has a named attribute. It is
one `getattr()` whose `AttributeError` becomes `False`, so it costs exactly
what the attribute lookup costs: a cached class-level lookup plus an instance
dict probe, or whatever a user-defined hook does.

## Complexity Reference

Let `d` be the length of the object's class MRO and `g` the cost, in time and
space, of a user-defined hook: `__getattr__`, `__getattribute__`, or a
descriptor such as a property getter.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hasattr(obj, name)` | O(1) avg | O(1) | The class-level lookup of a plain `str` name is cached per class and name, for misses as well as hits, so `d` does not matter once the cache is warm |
| `hasattr(obj, name)`, first lookup after the class or a base changed | O(d) | O(1) | Walks the MRO once and caches the result. From Python 3.13, once a class has been changed and looked up again more than 1,000 times it is never cached again, and every lookup on it pays O(d) |
| `hasattr(obj, name)` through a hook | O(g) | O(g) | On top of the lookup above. A property getter runs, and `__getattr__` runs on every miss. Only `AttributeError` becomes `False`; any other exception propagates |
| `hasattr(obj, name)` with a non-`str` name | O(1) | O(1) | Raises `TypeError` before any lookup |

## Basic Usage

### Check Attribute Existence

```python
# O(1) avg - one cached lookup
class MyClass:
    attr = 42

obj = MyClass()

# Safe check - O(1) avg
if hasattr(obj, 'attr'):
    print(obj.attr)  # 42

# A miss is cached too - O(1) avg
if hasattr(obj, 'missing'):
    print("Has missing")
else:
    print("No missing attribute")
```

### Avoid AttributeError

```python
# All three forms do the same lookup; they differ in how many times they do it
class User:
    name = "Alice"

user = User()

# try/except - one lookup
try:
    email = user.email
except AttributeError:
    email = "no@email.com"

# hasattr() then access - two lookups when the attribute exists
if hasattr(user, 'email'):
    email = user.email
else:
    email = "no@email.com"

# getattr() with a default - one lookup either way, and the clearest
email = getattr(user, 'email', "no@email.com")
```

## Complexity Details

### Inheritance Chain Traversal

```python
# The first lookup of a name on a class walks the MRO - O(d)
# Later lookups of that name on that class are cached - O(1) avg
class A:
    a_attr = 1

class B(A):
    b_attr = 2

class C(B):
    c_attr = 3

class D(C):
    d_attr = 4

obj = D()

# MRO: [D, C, B, A, object]
has_a = hasattr(obj, 'a_attr')  # O(d) once: D, C, B, then found in A
has_a = hasattr(obj, 'a_attr')  # O(1) avg: cached for (D, 'a_attr')
has_x = hasattr(obj, 'x_attr')  # O(d) once, then the miss is cached too

# Assigning to a class, or to any of its bases, invalidates its cache
C.c_attr = 30
has_a = hasattr(obj, 'a_attr')  # O(d) again, once
```

### What hasattr() Catches

```python
# hasattr() is one getattr() call; only AttributeError means False
def hasattr_simulation(obj, name):
    """What hasattr() does - the cost is the lookup's"""
    if not isinstance(name, str):
        raise TypeError("attribute name must be string")
    try:
        getattr(obj, name)
    except AttributeError:
        return False
    return True

class Strict:
    @property
    def broken(self):
        raise KeyError("not an AttributeError")

obj = Strict()
print(hasattr(obj, 'missing'))  # False

try:
    hasattr(obj, 'broken')  # the KeyError propagates
except KeyError:
    print("only AttributeError means False")

try:
    hasattr(obj, 42)
except TypeError:
    print("the name must be a str")
```

## Performance Patterns

### hasattr vs getattr with Default

```python
# hasattr() then getattr() - two lookups
class Config:
    host = "localhost"

obj = Config()

if hasattr(obj, 'host'):  # lookup one
    value = getattr(obj, 'host')  # lookup two
else:
    value = None

# getattr() with a default - one lookup
value = getattr(obj, 'host', None)
```

### Checking Multiple Attributes

```python
# O(n) - one cached lookup per name checked
class Message:
    to = "user@example.com"
    subject = "Hello"
    body = "Content"

msg = Message()

required = ['to', 'subject', 'body']
valid = all(hasattr(msg, attr) for attr in required)  # O(n) - n names

# dir() is not a shortcut: it collects and sorts every attribute of the
# object and its whole MRO, so it grows with that attribute count where a
# few hasattr() calls do not
valid = {'to', 'subject', 'body'} <= set(dir(msg))  # at least O(a) in the a names listed
```

## Common Use Cases

### Optional Feature Detection

```python
# O(1) avg - check if feature is available
class DataStore:
    def load(self):
        pass

    def save(self):
        pass
    # backup() is optional

class DatabaseStore(DataStore):
    def backup(self):
        """Advanced feature"""
        pass

store = DatabaseStore()

# O(1) avg - check for optional method
if hasattr(store, 'backup'):
    store.backup()  # Call if available
```

### Protocol Checking

```python
# One cached lookup per protocol method
def is_iterable(obj):
    """Check for the iterator protocol - one lookup"""
    return hasattr(obj, '__iter__')

def is_context_manager(obj):
    """Check for the context manager protocol - one or two lookups"""
    return hasattr(obj, '__enter__') and hasattr(obj, '__exit__')

class Countdown:
    def __init__(self, start):
        self.current = start

    def __iter__(self):
        return self

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1

obj = Countdown(3)

if is_iterable(obj):
    for item in obj:
        print(item)  # 3, 2, 1
```

### Safe Method Invocation

```python
# hasattr() then the call - two lookups when the method exists
class Handler:
    def process(self, data):
        return f"Processed: {data}"

class MinimalHandler:
    pass

def safe_process(obj, data):
    """Call method if it exists"""
    if hasattr(obj, 'process'):  # O(1) avg
        return obj.process(data)
    return None

handler = Handler()
minimal = MinimalHandler()

result1 = safe_process(handler, "data")    # Processed: data
result2 = safe_process(minimal, "data")    # None
```

## Advanced Usage

### Dynamic Behavior Routing

```python
# Route to a handler by name
class Plugin:
    def on_start(self):
        pass

    def on_stop(self):
        pass

class AdvancedPlugin(Plugin):
    def on_update(self):
        pass

def trigger_event(obj, event_name):
    """Safely trigger an event - one lookup"""
    handler = getattr(obj, event_name, None)
    if handler is not None:
        handler()

plugin = AdvancedPlugin()

trigger_event(plugin, 'on_start')   # Works
trigger_event(plugin, 'on_update')  # Works
trigger_event(plugin, 'missing')    # No error
```

### Attribute Validation

```python
# O(n) - one lookup per required name
def validate_object(obj, required_attrs):
    """Return the required names the object lacks - O(n)"""
    missing = []

    for attr in required_attrs:  # n iterations
        if not hasattr(obj, attr):  # O(1) avg each
            missing.append(attr)

    return missing if missing else None

class FileWriter:
    def write(self):
        pass

    def close(self):
        pass

required = ['write', 'close', 'flush']
missing = validate_object(FileWriter(), required)
# Returns: ['flush'] - missing method
```

### Duck Typing Implementation

```python
# Two lookups per capability used: the check and the call
def transform(data):
    return data.upper()

def process_data(obj):
    """Work with any object that has the required methods"""
    if hasattr(obj, 'read'):
        data = obj.read()
    else:
        raise TypeError("Object doesn't support read")

    if hasattr(obj, 'write'):
        obj.write(transform(data))
    else:
        raise TypeError("Object doesn't support write")

# Works with file-like objects
import io
buffer = io.StringIO("content")

process_data(buffer)
print(buffer.getvalue())  # contentCONTENT
```

## Practical Examples

### Conditional Initialization

```python
# Up to three lookups: two checks and one read
class FlexibleConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def get_port(self):
        """Get port with fallback"""
        if hasattr(self, 'port'):  # O(1) avg
            return self.port
        elif hasattr(self, 'default_port'):  # O(1) avg
            return self.default_port
        else:
            return 8000

config = FlexibleConfig(default_port=9000)
port = config.get_port()  # 9000
```

### Plugin System

```python
# O(n) - one lookup per feature name
class PluginManager:
    def get_capabilities(self, plugin):
        """List plugin capabilities - O(n)"""
        capabilities = []

        features = ['process', 'validate', 'transform', 'cache']

        for feature in features:  # n iterations
            if hasattr(plugin, feature):  # O(1) avg each
                capabilities.append(feature)

        return capabilities

class SimplePlugin:
    def process(self):
        pass

    def validate(self):
        pass

manager = PluginManager()
caps = manager.get_capabilities(SimplePlugin())
# Returns: ['process', 'validate']
```

## Edge Cases

### Descriptors Run Inside hasattr()

```python
# hasattr() finds attributes, methods and properties alike - and runs getters
class Example:
    value = 42  # Attribute

    def method(self):  # Callable
        pass

    @property
    def computed(self):  # Property - its getter runs on every hasattr()
        print("computing")
        return 100

obj = Example()

print(hasattr(obj, 'value'))      # True - attribute
print(hasattr(obj, 'method'))     # True - callable
print(hasattr(obj, 'computed'))   # prints "computing", then True
```

### Side Effects of __getattr__

```python
# __getattr__ runs on every miss - its cost and side effects are hasattr()'s
class WithSideEffect:
    def __getattr__(self, name):
        print(f"Looking up: {name}")
        raise AttributeError(name)

obj = WithSideEffect()

result = hasattr(obj, 'missing')  # Prints "Looking up: missing"; result is False

# A __getattr__ that returns instead of raising makes every name exist
class Permissive:
    def __getattr__(self, name):
        return None

print(hasattr(Permissive(), 'anything'))  # True
```

## Best Practices

✅ **Do**:

- Use `hasattr()` to test for an attribute before acting on it
- Use `getattr()` with a default when the value is needed - it is one lookup, not two
- Use it for duck typing and protocol checking
- Expect property getters and `__getattr__` to run inside it

❌ **Avoid**:

- `hasattr()` followed by `getattr()` on the same name
- `dir()` as a way to check for a few names - it builds and sorts the whole attribute list
- Relying on `hasattr()` to swallow anything but `AttributeError`
- Reassigning a class's attributes in a hot loop on Python 3.13 or later - after more than 1,000 rounds of change and lookup the class is never cached again

## Related Functions

- **[getattr()](getattr.md)** - Get attribute with default
- **[setattr()](setattr.md)** - Set attribute value
- **[delattr()](delattr.md)** - Delete attribute
- **[dir()](dir.md)** - List all attributes
- **[vars()](vars.md)** - Get __dict__
- **[callable()](callable.md)** - Check if callable

## Version Notes

- **Python 2.x**: Any exception raised by the lookup, not only `AttributeError`, is swallowed and reported as `False`
- **Python 3.2+**: Only `AttributeError` becomes `False`; every other exception propagates
- **Python 3.13+**: A class that has been changed and looked up again more than 1,000 times stops being cached, so lookups on it are O(d) from then on
- **All versions**: A non-`str` name raises `TypeError`
