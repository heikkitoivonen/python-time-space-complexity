# getattr() Function Complexity

The `getattr()` function retrieves the value of a named attribute from an object. It's the programmatic way to access object attributes dynamically.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Attribute lookup | O(1) avg | O(1) | Average case for direct instance attributes (dict lookup) |
| MRO traversal | O(d) | O(1) | d = depth of inheritance hierarchy; typically small (<10) |
| Call __getattribute__ | O(1) | O(1) | Direct attribute fetch |
| Call __getattr__ | O(k) | O(1) | k = custom __getattr__ implementation time |
| Total operation | O(d) | O(1) | d = MRO depth, typically constant for most hierarchies |

## Basic Usage

### Get Attribute by Name

```python
# O(1) - direct attribute access
class MyClass:
    value = 42

obj = MyClass()

# Direct access - O(1)
val = obj.value  # 42

# Using getattr - O(1)
val = getattr(obj, 'value')  # 42

# Both have same complexity, getattr is programmatic
```

### Dynamic Attribute Names

```python
# O(1) - programmatic attribute access
class Config:
    host = "localhost"
    port = 8000
    debug = True

config = Config()

# Get attribute by variable name - O(1)
for attr_name in ['host', 'port', 'debug']:
    value = getattr(config, attr_name)  # O(1)
    print(f"{attr_name}: {value}")
```

### Get with Default Value

```python
# O(1) - returns default if not found
class User:
    name = "Alice"
    email = None

user = User()

# With default - O(1)
phone = getattr(user, 'phone', 'Not provided')
email = getattr(user, 'email', 'no@email.com')

# Avoids AttributeError - O(1)
# Instead of:
# if hasattr(user, 'phone'):
#     phone = user.phone
# else:
#     phone = 'Not provided'
```

## Complexity Details

### Direct Attribute Lookup

```python
# O(1) - simple lookup
class Simple:
    x = 1

obj = Simple()

# Direct lookup in object's namespace
value = getattr(obj, 'x')  # O(1)

# Python's attribute resolution:
# 1. Check instance.__dict__ - O(1) hash table lookup
# 2. If not found, return default - O(1)
```

### Inheritance Chain Traversal

```python
# O(d) - where d = MRO depth
class A:
    attr_a = 'A'

class B(A):
    attr_b = 'B'

class C(B):
    attr_c = 'C'

class D(C):
    attr_d = 'D'

obj = D()

# Lookup in own attributes - O(1)
val1 = getattr(obj, 'attr_d')  # O(1)

# Lookup in parent - O(d) where d = MRO depth
val2 = getattr(obj, 'attr_a')  # O(4) - traverse D -> C -> B -> A

# MRO for D: [D, C, B, A, object]
# Linear search through MRO: O(d) where d = 5
```

### Custom __getattr__

```python
# O(1) - custom implementation
class Dynamic:
    def __getattribute__(self, name):
        # Called for every attribute access
        # Even existing attributes go through this
        print(f"Accessing: {name}")
        return super().__getattribute__(name)  # O(1)
    
    def __getattr__(self, name):
        # Called only if attribute not found
        print(f"Attribute not found: {name}")
        return f"Generated: {name}"

obj = Dynamic()

# Calls __getattribute__ - O(1)
val = getattr(obj, 'existing')

# Calls __getattribute__ then __getattr__ - O(1)
val = getattr(obj, 'missing')
```

## Performance Patterns

### Direct Access vs getattr

```python
# Direct attribute access - marginally faster
class Data:
    value = 42

obj = Data()

# Direct - O(1), very fast
direct = obj.value

# getattr - O(1), slight overhead for name lookup
dynamic = getattr(obj, 'value')

# Both O(1), direct is ~5% faster in practice
# Use getattr when you need dynamic access
```

### getattr vs hasattr

```python
# getattr with default - O(1)
value = getattr(obj, 'attr', None)  # O(1)

# vs hasattr + getattr - O(2)
if hasattr(obj, 'attr'):  # O(1)
    value = getattr(obj, 'attr')  # O(1)
else:
    value = None  # Total: O(2) - worse!

# Use getattr with default for better performance
```

### Dynamic Method Lookup

```python
# O(d) - lookup in class hierarchy
class Handler:
    def handle_request(self):
        return "handled"

class VerboseHandler(Handler):
    def log(self, msg):
        print(msg)

handler = VerboseHandler()

# Lookup method - O(d) where d = MRO depth
method = getattr(handler, 'handle_request')  # O(2)
method()

# More practical - use in callbacks
def call_method(obj, method_name, *args):
    """Generic method caller - O(d)"""
    method = getattr(obj, method_name, None)  # O(d)
    if method and callable(method):  # O(1)
        return method(*args)
    return None
```

## Common Use Cases

### Generic Property Access

```python
# O(1) - implement generic accessors
class Record:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    
    def get(self, key, default=None):
        """Generic getter - O(1)"""
        return getattr(self, key, default)

record = Record(name="Alice", age=30)

# O(1) - programmatic access
print(record.get('name'))        # 'Alice'
print(record.get('missing'))     # None
print(record.get('missing', 'N/A'))  # 'N/A'
```

### Plugin System

```python
# O(d) - dynamically call plugin methods
class Plugin:
    def on_init(self):
        pass
    
    def on_start(self):
        pass

class EventSystem:
    def trigger(self, obj, event_name):
        """Call event handler if exists - O(d)"""
        handler = getattr(obj, event_name, None)  # O(d)
        if callable(handler):  # O(1)
            handler()  # O(1)

plugin = Plugin()
system = EventSystem()

# O(d) - trigger event
system.trigger(plugin, 'on_init')   # Calls on_init()
system.trigger(plugin, 'on_start')  # Calls on_start()
system.trigger(plugin, 'missing')   # No error, just skipped
```

### Object Copying

```python
# O(n) - copy attributes from one object to another
def copy_attributes(source, dest):
    """Copy attributes between objects - O(n)"""
    for attr in dir(source):  # O(n log n)
        if not attr.startswith('_'):  # O(1)
            try:
                value = getattr(source, attr)  # O(d)
                setattr(dest, attr, value)  # O(1)
            except:
                pass  # Skip attributes that can't be accessed

class A:
    x = 1
    y = 2

class B:
    pass

a = A()
b = B()
copy_attributes(a, b)
print(b.x, b.y)  # 1, 2
```

### Type-Based Dispatch

```python
# O(d) - select method by type
class Processor:
    def process_int(self, val):
        return val * 2
    
    def process_str(self, val):
        return val.upper()
    
    def process_list(self, val):
        return len(val)
    
    def process(self, val):
        """Dispatch based on type - O(d)"""
        type_name = type(val).__name__
        method_name = f"process_{type_name}"
        
        # O(d) - lookup method
        method = getattr(self, method_name, None)
        
        if method:
            return method(val)
        return None

processor = Processor()

print(processor.process(5))        # 10
print(processor.process("hello"))  # HELLO
print(processor.process([1,2,3])) # 3
```

### Configuration Loading

```python
# O(n * d) - load config properties
class Settings:
    debug = False
    timeout = 30
    max_connections = 100

def apply_config(obj, config_dict):
    """Apply config dictionary to object - O(n * d)"""
    for key, value in config_dict.items():  # O(n)
        if hasattr(obj, key):  # O(1)
            setattr(obj, key, value)  # O(1)
        # Could use: getattr(obj, key, None)

settings = Settings()
config = {
    'debug': True,
    'timeout': 60
}

apply_config(settings, config)
print(settings.debug)      # True
print(settings.timeout)    # 60
```

## Advanced Usage

### Meta-Programming

```python
# O(d) - implement property-like behavior
class SmartObject:
    def __init__(self):
        self._values = {}
    
    def __getattribute__(self, name):
        if name.startswith('_'):
            return super().__getattribute__(name)
        
        # Custom logic for non-private attributes
        values = super().__getattribute__('_values')
        if name in values:
            print(f"Retrieving {name}")
            return values[name]
        
        return super().__getattribute__(name)

obj = SmartObject()
obj._values['x'] = 42

# Calls __getattribute__ - O(1)
val = getattr(obj, 'x')  # Prints "Retrieving x"
```

### Lazy Attribute Loading

```python
# O(d) - compute attributes on demand
class LazyObject:
    def __init__(self):
        self._cache = {}
    
    def __getattr__(self, name):
        """Called when attribute not found - O(1)"""
        if name in self._cache:
            return self._cache[name]
        
        # Expensive computation
        result = self._compute(name)
        self._cache[name] = result
        return result
    
    def _compute(self, name):
        # Simulate expensive operation
        return f"computed_{name}"

obj = LazyObject()

# First access - O(1) + computation
val1 = getattr(obj, 'attr1')  # Computes value

# Second access - O(1) from cache
val2 = getattr(obj, 'attr1')  # Returns from cache
```

## Practical Examples

### Attribute Validation

```python
# O(d) - validate object attributes
def has_method(obj, method_name):
    """Check if object has callable method - O(d)"""
    attr = getattr(obj, method_name, None)  # O(d)
    return callable(attr)  # O(1)

class API:
    def fetch(self):
        pass

class BadAPI:
    fetch_data = "not a method"

api = API()
bad = BadAPI()

print(has_method(api, 'fetch'))  # True
print(has_method(bad, 'fetch_data'))  # False
```

### Generic Method Invocation

```python
# O(d) - call method by name with fallback
def invoke_method(obj, method_name, *args, **kwargs):
    """Safely invoke method - O(d)"""
    method = getattr(obj, method_name, None)  # O(d)
    
    if not callable(method):
        return None
    
    try:
        return method(*args, **kwargs)  # O(1)
    except Exception as e:
        return None

class Calculator:
    def add(self, a, b):
        return a + b
    
    def multiply(self, a, b):
        return a * b

calc = Calculator()

# O(d) - call method dynamically
result = invoke_method(calc, 'add', 5, 3)  # 8
```

### Attribute Default Factory

```python
# O(d) - get with default factory
class LazyDict:
    def get(self, key, factory=None):
        """Get attribute with default factory - O(d)"""
        value = getattr(self, key, None)  # O(d)
        
        if value is None and factory:
            value = factory()  # O(1)
            setattr(self, key, value)
        
        return value

obj = LazyDict()

# O(d) - creates default on first access
items = obj.get('items', list)  # Creates empty list
items.append(1)

# O(d) - returns existing value
items2 = obj.get('items', list)  # Returns same list
print(items2)  # [1]
```

## Edge Cases

### Descriptors

```python
# O(d) - descriptor protocol
class DescriptorExample:
    @property
    def computed(self):
        return "computed value"

obj = DescriptorExample()

# O(d) - property descriptor is called
value = getattr(obj, 'computed')  # Calls property getter
```

### __slots__

```python
# O(d) - works with __slots__
class Slotted:
    __slots__ = ['x', 'y']
    
    def __init__(self):
        self.x = 1
        self.y = 2

obj = Slotted()

# O(d) - lookup in slots
value = getattr(obj, 'x')  # O(1) - faster than __dict__
```

### Accessing Non-Existent Attributes

```python
# O(d) - safe way to check
class Simple:
    pass

obj = Simple()

# Raises AttributeError
try:
    val = obj.missing  # AttributeError
except AttributeError:
    print("Not found")

# Better - use getattr with default
val = getattr(obj, 'missing', None)  # O(d), returns None
```

## Performance Considerations

### Caching Attribute Lookups

```python
# O(1) - cached lookups vs O(d) repeated
class CachedLookup:
    def __init__(self, obj):
        self.obj = obj
        self._cache = {}
    
    def get(self, attr_name):
        if attr_name not in self._cache:
            self._cache[attr_name] = getattr(self.obj, attr_name)  # O(d)
        return self._cache[attr_name]  # O(1)

obj = type('Obj', (), {'x': 1, 'y': 2})()
cached = CachedLookup(obj)

val1 = cached.get('x')  # O(d) - first access
val2 = cached.get('x')  # O(1) - from cache
```

## Best Practices

✅ **Do**:

- Use `getattr()` with default value instead of try/except
- Cache results for repeated attribute lookups
- Use for dynamic attribute access in loops
- Document which attributes objects are expected to have
- Use with `hasattr()` for complex validation

❌ **Avoid**:

- Accessing attributes in tight O(n) loops without caching
- Assuming all accessed attributes are safe (may raise exceptions)
- Using `getattr()` when direct access is clearer
- Forgetting that attribute lookup traverses MRO
- Complex __getattr__ implementations (hard to debug)

## Related Functions

- **[hasattr()](hasattr.md)** - Check attribute existence
- **[setattr()](setattr.md)** - Set attribute value
- **[delattr()](delattr.md)** - Delete attribute
- **[dir()](dir.md)** - List attributes
- **[vars()](vars.md)** - Get __dict__
- **type()** - Get object type

## Version Notes

- **Python 2.x**: `getattr()` available with 2-3 arguments
- **Python 3.x**: Same behavior with optional default
- **All versions**: MRO traversal depth depends on inheritance
