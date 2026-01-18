# hasattr() Function Complexity

The `hasattr()` function checks whether an object has a named attribute. It's the standard way to safely test for attribute existence before accessing.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Attribute lookup | O(d) | O(1) | d = MRO depth; typically small (<10) |
| Catch AttributeError | O(1) | O(1) | Exception handling overhead |
| Total operation | O(d) | O(1) | d = inheritance depth; effectively O(1) for flat hierarchies |

## Basic Usage

### Check Attribute Existence

```python
# O(d) - where d = MRO depth
class MyClass:
    attr = 42

obj = MyClass()

# Safe check - O(d)
if hasattr(obj, 'attr'):
    print(obj.attr)  # 42

# Check non-existent attribute - O(d)
if hasattr(obj, 'missing'):
    print("Has missing")
else:
    print("No missing attribute")
```

### Avoid AttributeError

```python
# O(d) - safe attribute access pattern
class User:
    name = "Alice"

user = User()

# Bad - O(1) but risky
try:
    email = user.email
except AttributeError:
    email = "no@email.com"

# Better - O(d) and clearer
if hasattr(user, 'email'):
    email = user.email
else:
    email = "no@email.com"

# Best - use getattr with default O(d)
email = getattr(user, 'email', "no@email.com")
```

## Complexity Details

### Inheritance Chain Traversal

```python
# O(d) - traverses MRO for each check
class A:
    a_attr = 1

class B(A):
    b_attr = 2

class C(B):
    c_attr = 3

class D(C):
    d_attr = 4

obj = D()

# Lookup in own class - O(1)
has_d = hasattr(obj, 'd_attr')  # True, O(1)

# Lookup in parent chain - O(d)
has_a = hasattr(obj, 'a_attr')  # True, O(4) - traverse MRO

# MRO: [D, C, B, A, object]
# Lookup traces: D.__dict__ -> C.__dict__ -> B.__dict__ -> A.__dict__ -> found
```

### Exception Handling

```python
# O(d) - hasattr() implements like this internally
def hasattr_simulation(obj, name):
    """How hasattr() works - O(d)"""
    try:
        getattr(obj, name)  # O(d) - traverse MRO
        return True  # O(1)
    except AttributeError:
        return False  # O(1)

# Each check involves getattr() which is O(d)
class Data:
    value = 42

obj = Data()
result = hasattr_simulation(obj, 'value')  # O(d)
```

## Performance Patterns

### Multiple Checks

```python
# O(n * d) - multiple hasattr() calls
class Config:
    host = "localhost"
    port = 8000
    debug = True

config = Config()

# Multiple hasattr() calls - O(3 * d)
if hasattr(config, 'host') and hasattr(config, 'port'):  # O(2d)
    print("Ready")

if hasattr(config, 'debug'):  # O(d)
    print("Debug mode")

# Total: O(3d) - multiple MRO traversals
```

### hasattr vs getattr with Default

```python
# hasattr + getattr - O(2d)
if hasattr(obj, 'attr'):  # O(d)
    value = getattr(obj, 'attr')  # O(d)
else:
    value = None  # O(2d) - total

# vs getattr alone - O(d)
value = getattr(obj, 'attr', None)  # O(d) - single lookup

# Better: use getattr with default (half the lookups)
```

### Checking Multiple Attributes

```python
# O(n * d) - inefficient for many checks
class Message:
    to = "user@example.com"
    subject = "Hello"
    body = "Content"

msg = Message()

# Multiple checks - O(3d)
required = ['to', 'subject', 'body']
valid = all(hasattr(msg, attr) for attr in required)  # O(n * d)

# Better - use getattr
attrs = {attr: getattr(msg, attr, None) for attr in required}
valid = all(v is not None for v in attrs.values())
```

## Common Use Cases

### Optional Feature Detection

```python
# O(d) - check if feature is available
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

# O(d) - check for optional method
if hasattr(store, 'backup'):
    store.backup()  # Call if available
```

### Protocol Checking

```python
# O(n * d) - check if object implements protocol
def is_iterable(obj):
    """Check for iterator protocol - O(d)"""
    return hasattr(obj, '__iter__')  # O(d)

def is_context_manager(obj):
    """Check for context manager protocol - O(2d)"""
    return (hasattr(obj, '__enter__') and  # O(d)
            hasattr(obj, '__exit__'))  # O(d)

class MyIterator:
    def __iter__(self):
        pass
    
    def __next__(self):
        pass

obj = MyIterator()

# O(d) - check protocol
if is_iterable(obj):
    for item in obj:
        print(item)
```

### Safe Method Invocation

```python
# O(d) - call method if exists
class Handler:
    def process(self, data):
        return f"Processed: {data}"

class MinimalHandler:
    pass

def safe_process(obj, data):
    """Call method if exists - O(d)"""
    if hasattr(obj, 'process'):  # O(d)
        return obj.process(data)  # O(1)
    return None

handler = Handler()
minimal = MinimalHandler()

result1 = safe_process(handler, "data")    # Processed: data
result2 = safe_process(minimal, "data")    # None
```

### Attribute Filtering

```python
# O(n * d) - find attributes by predicate
class Settings:
    timeout = 30
    retries = 3
    debug = False
    _internal = "hidden"

settings = Settings()

# O(n * d) - filter using hasattr
public_attrs = []
for attr in dir(settings):  # O(n log n)
    if not attr.startswith('_'):  # O(1)
        if hasattr(settings, attr):  # O(d) - redundant!
            public_attrs.append(attr)

# Better approach - avoid hasattr in loop
public_attrs = [attr for attr in dir(settings)  # O(n log n)
                if not attr.startswith('_')]  # O(1) - no hasattr needed
```

## Advanced Usage

### Dynamic Behavior Routing

```python
# O(n * d) - route to correct handler
class Plugin:
    def on_start(self):
        pass
    
    def on_stop(self):
        pass

class AdvancedPlugin(Plugin):
    def on_update(self):
        pass

def trigger_event(obj, event_name):
    """Safely trigger event - O(d)"""
    if hasattr(obj, event_name):  # O(d)
        getattr(obj, event_name)()  # O(d)

plugin = AdvancedPlugin()

# O(d) - check and invoke
trigger_event(plugin, 'on_start')   # Works
trigger_event(plugin, 'on_update')  # Works
trigger_event(plugin, 'missing')    # No error
```

### Attribute Validation

```python
# O(n * d) - validate object structure
def validate_object(obj, required_attrs):
    """Check object has all required attributes - O(n * d)"""
    missing = []
    
    for attr in required_attrs:  # O(n) iterations
        if not hasattr(obj, attr):  # O(d) per iteration
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
# O(n * d) - implement duck typing
def process_data(obj):
    """Work with any object that has required methods - O(n * d)"""
    
    # O(d) - check read capability
    if hasattr(obj, 'read'):
        data = obj.read()
    else:
        raise TypeError("Object doesn't support read")
    
    # O(d) - check write capability
    if hasattr(obj, 'write'):
        obj.write(process(data))
    else:
        raise TypeError("Object doesn't support write")

# Works with file-like objects
import io
buffer = io.StringIO()

# O(n * d) - checks satisfied
process_data(buffer)
```

## Practical Examples

### Conditional Initialization

```python
# O(d) - conditional attribute setup
class FlexibleConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    
    def get_port(self):
        """Get port with fallback - O(d)"""
        if hasattr(self, 'port'):  # O(d)
            return self.port
        elif hasattr(self, 'default_port'):  # O(d)
            return self.default_port
        else:
            return 8000

# O(2d) - checks in sequence
config = FlexibleConfig(default_port=9000)
port = config.get_port()  # 9000
```

### Plugin System

```python
# O(n * d) - discover available features
class PluginManager:
    def get_capabilities(self, plugin):
        """List plugin capabilities - O(n * d)"""
        capabilities = []
        
        features = ['process', 'validate', 'transform', 'cache']
        
        for feature in features:  # O(n)
            if hasattr(plugin, feature):  # O(d)
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

### Backward Compatibility

```python
# O(d) - handle old API
class Service:
    """New API with old method support"""
    
    def fetch_data(self):
        return "data"
    
    def fetch(self):
        """Old API - calls new"""
        if hasattr(self, 'fetch_data'):  # O(d)
            return self.fetch_data()
        else:
            raise NotImplementedError()

service = Service()

# O(d) - check for new method
data = service.fetch()  # Uses fetch_data internally
```

## Edge Cases

### Callable vs Attribute

```python
# O(d) - hasattr finds both properties and methods
class Example:
    value = 42  # Attribute
    
    def method(self):  # Callable
        pass
    
    @property
    def computed(self):  # Property
        return 100

obj = Example()

# All return True - hasattr doesn't distinguish types
print(hasattr(obj, 'value'))      # True - attribute
print(hasattr(obj, 'method'))     # True - callable
print(hasattr(obj, 'computed'))   # True - property
```

### Side Effects of __getattr__

```python
# O(d) - may trigger __getattr__ side effects
class WithSideEffect:
    def __getattr__(self, name):
        print(f"Looking up: {name}")
        raise AttributeError(name)

obj = WithSideEffect()

# O(d) - prints side effect
result = hasattr(obj, 'missing')  # Prints "Looking up: missing"
# hasattr returns False but side effect occurred!

# Note: hasattr() can have unexpected side effects
```

### Performance Impact of __getattr__

```python
# O(d) - slow if __getattr__ is expensive
class ExpensiveGetattr:
    def __getattr__(self, name):
        # Simulate expensive operation
        import time
        time.sleep(0.1)  # Slow!
        return None

obj = ExpensiveGetattr()

# O(d) + expensive operation
has = hasattr(obj, 'anything')  # Takes ~0.1 seconds!

# Better to use getattr with cached result
```

## Performance Considerations

### Avoiding Repeated Checks

```python
# Bad - O(n * d) - multiple hasattr calls
class BadExample:
    def check_all(self, obj):
        return (hasattr(obj, 'x') and      # O(d)
                hasattr(obj, 'y') and      # O(d)
                hasattr(obj, 'z'))         # O(d)
                # Total: O(3d)

# Good - single pass with dir()
class GoodExample:
    def check_all(self, obj):
        attrs = set(dir(obj))  # O(n log n) - single pass
        return {'x', 'y', 'z'}.issubset(attrs)  # O(1)

# Better for single check - use getattr
value = getattr(obj, 'x', None)  # O(d) - single lookup
```

### Caching hasattr Results

```python
# O(d) + O(1) cache lookups
class CachedAttributeChecker:
    def __init__(self, obj):
        self.obj = obj
        self._cache = {}
    
    def has_attr(self, name):
        """Check with caching - O(d) or O(1)"""
        if name not in self._cache:
            self._cache[name] = hasattr(self.obj, name)  # O(d)
        
        return self._cache[name]  # O(1) from cache

obj = type('Obj', (), {'x': 1})()
checker = CachedAttributeChecker(obj)

result1 = checker.has_attr('x')  # O(d) - first check
result2 = checker.has_attr('x')  # O(1) - cached
```

## Best Practices

✅ **Do**:

- Use `hasattr()` to safely check before accessing
- Use `getattr()` with default instead of hasattr + getattr
- Cache results if checking many attributes
- Use `dir()` if checking multiple attributes at once
- Use for duck typing and protocol checking

❌ **Avoid**:

- Using hasattr() repeatedly on same attribute (cache instead)
- hasattr() + getattr() together (use getattr with default)
- Checking many attributes with multiple hasattr() calls
- Calling hasattr() on objects with expensive __getattr__
- Assuming hasattr() won't trigger side effects

## Related Functions

- **[getattr()](getattr.md)** - Get attribute with default
- **[setattr()](setattr.md)** - Set attribute value
- **[delattr()](delattr.md)** - Delete attribute
- **[dir()](dir.md)** - List all attributes
- **[vars()](vars.md)** - Get __dict__
- **[callable()](callable.md)** - Check if callable

## Version Notes

- **Python 2.x**: `hasattr()` available, uses getattr internally
- **Python 3.x**: Same behavior, optimized in CPython
- **All versions**: Returns True/False, no exceptions raised
