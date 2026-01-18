# setattr() Function Complexity

The `setattr()` function sets the value of a named attribute on an object. It's the programmatic way to assign object attributes dynamically.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Direct assignment | O(1) | O(1) | Set in instance dict |
| Property setter call | O(1) | O(1) | Call property __set__ |
| __setattr__ call | O(1) | O(1) | Custom implementation |
| Descriptor protocol | O(1) | O(1) | Data descriptors |
| Total operation | O(1) | O(1) | Hash table insertion |

## Basic Usage

### Set Attribute by Name

```python
# O(1) - direct attribute setting
class MyClass:
    pass

obj = MyClass()

# Direct assignment - O(1)
obj.value = 42

# Using setattr - O(1)
setattr(obj, 'value', 42)

# Both equivalent, setattr is programmatic
```

### Dynamic Attribute Names

```python
# O(1) - programmatic attribute setting
class Config:
    pass

config = Config()

# Set attributes dynamically - O(1) per attribute
for key, value in {'host': 'localhost', 'port': 8000}.items():
    setattr(config, key, value)  # O(1)

print(config.host)  # localhost
print(config.port)  # 8000
```

### Bulk Initialization

```python
# O(n) - set multiple attributes
class Record:
    pass

record = Record()

# Initialize from dictionary - O(n)
data = {'name': 'Alice', 'age': 30, 'email': 'alice@example.com'}

for key, value in data.items():  # O(n)
    setattr(record, key, value)  # O(1) per attribute

print(record.name)   # Alice
print(record.age)    # 30
```

## Complexity Details

### Direct Assignment to Instance

```python
# O(1) - hash table insertion into __dict__
class Simple:
    pass

obj = Simple()

# O(1) - insert into obj.__dict__
setattr(obj, 'x', 1)
setattr(obj, 'y', 2)
setattr(obj, 'z', 3)

# Python's attribute storage:
# 1. Get instance.__dict__ (O(1))
# 2. Insert key-value pair (O(1) average)
# Total: O(1)
```

### Property Descriptor Protocol

```python
# O(1) - calls property setter if exists
class WithProperty:
    def __init__(self):
        self._value = 0
    
    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, val):
        self._value = val

obj = WithProperty()

# O(1) - calls setter, not direct assignment
setattr(obj, 'value', 42)  # Calls value.setter
```

### Custom __setattr__

```python
# O(1) - calls custom implementation
class TrackedChanges:
    def __init__(self):
        self._changes = {}
    
    def __setattr__(self, name, value):
        # Custom behavior on every assignment
        if name == '_changes':
            # Avoid recursion for tracking dict
            super().__setattr__(name, value)
        else:
            changes = super().__getattribute__('_changes')
            changes[name] = value
            super().__setattr__(name, value)

obj = TrackedChanges()

# O(1) - calls __setattr__
setattr(obj, 'x', 1)  # Tracked in _changes

print(obj._changes)  # {'x': 1}
```

## Performance Patterns

### Direct vs setattr Performance

```python
# Direct assignment - slightly faster O(1)
obj.attr = value  # Marginally faster

# setattr - O(1) with slight overhead
setattr(obj, 'attr', value)  # Lookup overhead

# Both are O(1), setattr has ~5% overhead for name lookup
# Use direct assignment in performance-critical code
```

### Batch Assignment

```python
# O(n) - multiple assignments
class Batch:
    pass

obj = Batch()

# Inefficient - multiple function calls
for i in range(1000):  # O(n)
    setattr(obj, f'attr{i}', i)  # O(1) per call

# Better - use __dict__.update
values = {f'attr{i}': i for i in range(1000)}  # O(n) - create dict
obj.__dict__.update(values)  # O(n) - bulk insert

# Second approach is ~10% faster for large batches
```

### vs Direct __dict__ Manipulation

```python
# Direct __dict__ - O(1), bypasses descriptor protocol
class Data:
    pass

obj = Data()

# Direct dict assignment - O(1), no descriptor calls
obj.__dict__['x'] = 1

# vs setattr - O(1), respects descriptors
setattr(obj, 'x', 1)

# Direct __dict__ is faster but skips property setters
# Use setattr for proper initialization, __dict__ for performance
```

## Common Use Cases

### Object Initialization from Dictionary

```python
# O(n) - initialize from dict
class User:
    def __init__(self, **kwargs):
        """Initialize from keyword arguments - O(n)"""
        for key, value in kwargs.items():  # O(n)
            setattr(self, key, value)  # O(1) per attribute

# O(n) - data = {name, email, age}
user = User(name='Alice', email='alice@ex.com', age=30)

print(user.name)    # Alice
print(user.email)   # alice@ex.com
```

### Configuration Management

```python
# O(n) - apply configuration
class Settings:
    """Base configuration with defaults"""
    timeout = 30
    retries = 3
    debug = False

def apply_config(obj, config_dict):
    """Apply config overrides - O(n)"""
    for key, value in config_dict.items():  # O(n)
        if hasattr(obj, key):  # O(1)
            setattr(obj, key, value)  # O(1)

settings = Settings()
overrides = {'timeout': 60, 'debug': True}

# O(n) - apply overrides
apply_config(settings, overrides)

print(settings.timeout)  # 60
print(settings.debug)    # True
```

### Object Cloning

```python
# O(n) - copy attributes from source to destination
def clone_object(source, dest):
    """Clone attributes - O(n)"""
    for attr in dir(source):  # O(n log n)
        if not attr.startswith('_'):  # O(1)
            try:
                value = getattr(source, attr)  # O(1)
                setattr(dest, attr, value)  # O(1)
            except:
                pass  # Skip read-only or property attributes

class Original:
    x = 1
    y = 2
    z = 3

class Empty:
    pass

orig = Original()
copy = Empty()

clone_object(orig, copy)  # O(n) - copy all public attributes
print(copy.x, copy.y)  # 1, 2
```

### Data Validation

```python
# O(1) - validate on assignment
class ValidatedData:
    def __setattr__(self, name, value):
        """Validate data before setting - O(1)"""
        if name == 'age':
            if not isinstance(value, int) or value < 0:
                raise ValueError("Age must be non-negative integer")
        
        super().__setattr__(name, value)

obj = ValidatedData()

setattr(obj, 'age', 30)      # O(1) - valid
# setattr(obj, 'age', -5)    # Raises ValueError
```

### Builder Pattern

```python
# O(n) - builder with fluent interface
class QueryBuilder:
    def __init__(self):
        self.filters = []
        self.limit_value = None
        self.offset_value = None
    
    def filter(self, condition):
        """Add filter - O(1)"""
        self.filters.append(condition)
        return self
    
    def limit(self, value):
        """Set limit - O(1)"""
        setattr(self, 'limit_value', value)
        return self
    
    def offset(self, value):
        """Set offset - O(1)"""
        setattr(self, 'offset_value', value)
        return self
    
    def build(self):
        return {
            'filters': self.filters,
            'limit': self.limit_value,
            'offset': self.offset_value
        }

# O(n) - n = 4 operations
query = (QueryBuilder()
         .filter('x > 10')
         .filter('y < 20')
         .limit(100)
         .offset(10)
         .build())
```

## Advanced Usage

### Meta-Programming

```python
# O(1) - set descriptor
class Descriptor:
    def __set__(self, obj, value):
        obj.__dict__['_value'] = value

class MyClass:
    prop = Descriptor()

obj = MyClass()

# O(1) - calls descriptor protocol
setattr(obj, 'prop', 42)  # Calls Descriptor.__set__

print(obj.__dict__)  # {'_value': 42}
```

### Computed Properties

```python
# O(1) - set triggers computation
class ComputedObject:
    def __init__(self):
        self._x = 0
        self._y = 0
    
    @property
    def x(self):
        return self._x
    
    @x.setter
    def x(self, value):
        self._x = value
        self._invalidate_cache()
    
    @property
    def y(self):
        return self._y
    
    @y.setter
    def y(self, value):
        self._y = value
        self._invalidate_cache()
    
    def _invalidate_cache(self):
        """Called on any coordinate change - O(1)"""
        print("Cache invalidated")

obj = ComputedObject()

# O(1) - triggers _invalidate_cache
setattr(obj, 'x', 10)  # Prints "Cache invalidated"
```

## Practical Examples

### Attribute Mapper

```python
# O(n) - map source to destination attributes
def map_attributes(source, dest, mapping):
    """Map attributes with renaming - O(n)"""
    for src_attr, dest_attr in mapping.items():  # O(n)
        if hasattr(source, src_attr):  # O(1)
            value = getattr(source, src_attr)  # O(1)
            setattr(dest, dest_attr, value)  # O(1)

class ApiResponse:
    user_id = 123
    user_name = "Alice"
    user_email = "alice@ex.com"

class User:
    pass

response = ApiResponse()
user = User()

mapping = {
    'user_id': 'id',
    'user_name': 'name',
    'user_email': 'email'
}

# O(n) - map all attributes
map_attributes(response, user, mapping)

print(user.id)     # 123
print(user.name)   # Alice
```

### Default Values

```python
# O(n) - set defaults for missing attributes
def set_defaults(obj, defaults):
    """Set default values - O(n)"""
    for key, value in defaults.items():  # O(n)
        if not hasattr(obj, key):  # O(1)
            setattr(obj, key, value)  # O(1)

class Settings:
    debug = True

settings = Settings()

defaults = {
    'timeout': 30,
    'retries': 3,
    'debug': False  # Already exists, won't override
}

# O(n) - set missing defaults
set_defaults(settings, defaults)

print(settings.timeout)  # 30
print(settings.debug)    # True (not overridden)
```

### Dynamic Enum Creation

```python
# O(n) - create enum-like classes
def create_flags(names):
    """Create flag class dynamically - O(n)"""
    flags = type('Flags', (), {})
    
    for i, name in enumerate(names):  # O(n)
        setattr(flags, name, 1 << i)  # O(1) per flag
    
    return flags

# O(n) - n = 5
Flags = create_flags(['READ', 'WRITE', 'EXECUTE', 'DELETE', 'ADMIN'])

print(Flags.READ)     # 1
print(Flags.WRITE)    # 2
print(Flags.ADMIN)    # 16
```

## Edge Cases

### Property Without Setter

```python
# O(1) - raises error if property has no setter
class ReadOnly:
    @property
    def value(self):
        return 42

obj = ReadOnly()

# Raises AttributeError - property has no setter
try:
    setattr(obj, 'value', 100)  # O(1) but raises
except AttributeError:
    print("Cannot set read-only property")
```

### __slots__

```python
# O(1) - works with __slots__
class Slotted:
    __slots__ = ['x', 'y']

obj = Slotted()

# O(1) - set slot attribute
setattr(obj, 'x', 1)
setattr(obj, 'y', 2)

# O(1) - faster than __dict__ objects
# But cannot add new attributes
try:
    setattr(obj, 'z', 3)  # AttributeError - no slot for z
except AttributeError:
    print("No slot for 'z'")
```

### Immutable Objects

```python
# O(1) - cannot set attributes on immutable types
class Immutable:
    __slots__ = []  # No slots for instances

obj = Immutable()

# Raises AttributeError
try:
    setattr(obj, 'x', 1)  # O(1) but raises
except AttributeError:
    print("Cannot set attributes on this object")
```

## Performance Considerations

### Avoiding __setattr__ Overhead

```python
# Direct __dict__ assignment - O(1) faster
class FastInit:
    def __init__(self, **kwargs):
        # Bypass __setattr__ by direct dict assignment
        self.__dict__.update(kwargs)  # O(n) - single call

# vs with setattr
class SlowInit:
    def __init__(self, **kwargs):
        # Calls __setattr__ for each attribute
        for k, v in kwargs.items():
            setattr(self, k, v)  # O(1) each, but more calls

# __dict__.update is ~30% faster for bulk initialization
```

### Batch vs Individual Updates

```python
# Individual updates - O(n) but multiple operations
obj = object.__new__(type('Obj', (), {}))

for i in range(100):
    setattr(obj, f'attr{i}', i)  # 100 function calls

# Batch update - O(n) but single operation
obj.__dict__ = {f'attr{i}': i for i in range(100)}

# Batch is ~20% faster
```

## Best Practices

✅ **Do**:

- Use `setattr()` for dynamic attribute assignment
- Use `setattr()` to respect property setters
- Use `__dict__.update()` for bulk initialization
- Cache attribute names if setting repeatedly
- Use descriptors for computed properties

❌ **Avoid**:

- Using `setattr()` in tight O(n) loops repeatedly
- Assuming all attributes can be set (check hasattr first)
- Direct `__dict__` assignment when descriptors should be called
- Expensive operations in `__setattr__` (consider caching)
- Setting private/internal attributes (use setattr carefully)

## Related Functions

- **[getattr()](getattr.md)** - Get attribute value
- **[hasattr()](hasattr.md)** - Check attribute existence
- **[delattr()](delattr.md)** - Delete attribute
- **[dir()](dir.md)** - List attributes
- **[vars()](vars.md)** - Get __dict__

## Version Notes

- **Python 2.x**: `setattr()` available, basic functionality
- **Python 3.x**: Same behavior, optimized in CPython
- **All versions**: Returns None, respects descriptor protocol
