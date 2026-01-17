# delattr() Function Complexity

The `delattr()` function removes a named attribute from an object. It's the programmatic way to delete object attributes dynamically.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Attribute lookup | O(1) avg | O(1) | Find in instance dict |
| Delete from dict | O(1) avg | O(1) | Hash table deletion |
| Property deleter call | O(k) | O(1) | k = deleter method complexity |
| __delattr__ call | O(k) | O(1) | k = custom implementation complexity |
| Total operation | O(1) avg | O(1) | Hash table deletion for simple attrs |

*Note: Deletion from instance `__dict__` is O(1) average case. Custom `__delattr__` or property deleters may have different complexity.*

## Basic Usage

### Delete Attribute by Name

```python
# O(1) - direct attribute deletion
class MyClass:
    attr = 42

obj = MyClass()

# Direct deletion - O(1)
del obj.attr

# Using delattr - O(1)
delattr(obj, 'attr')

# Both equivalent, delattr is programmatic
```

### Remove Dynamic Attributes

```python
# O(1) - delete programmatically created attributes
class Config:
    pass

config = Config()

# Create attributes - O(1)
setattr(config, 'host', 'localhost')
setattr(config, 'port', 8000)

# Delete attributes - O(1) each
delattr(config, 'host')  # O(1)
delattr(config, 'port')  # O(1)

# Check deletion
try:
    print(config.host)  # AttributeError - attribute deleted
except AttributeError:
    print("Attribute deleted successfully")
```

### Cleanup Pattern

```python
# O(n) - delete multiple attributes
class Resource:
    def __init__(self):
        self.file_handle = "file"
        self.connection = "db"
        self.buffer = []
    
    def cleanup(self):
        """Release resources - O(n)"""
        attrs_to_remove = ['file_handle', 'connection', 'buffer']
        
        for attr in attrs_to_remove:  # O(n)
            try:
                delattr(self, attr)  # O(1)
            except AttributeError:
                pass  # Already deleted

resource = Resource()
resource.cleanup()  # O(n)
```

## Complexity Details

### Direct Deletion from Instance Dictionary

```python
# O(1) - hash table deletion
class Simple:
    pass

obj = Simple()

# Add attribute
obj.x = 1  # O(1) - insert into __dict__

# Delete attribute - O(1)
delattr(obj, 'x')  # Removes from obj.__dict__

# Python's deletion:
# 1. Get instance.__dict__ (O(1))
# 2. Delete key-value pair (O(1) average)
# Total: O(1)
```

### Property Deleter Protocol

```python
# O(1) - calls property deleter if exists
class WithProperty:
    def __init__(self):
        self._value = 0
    
    @property
    def value(self):
        return self._value
    
    @value.setter
    def value(self, val):
        self._value = val
    
    @value.deleter
    def value(self):
        print("Deleting value property")
        del self._value

obj = WithProperty()
obj.value = 42

# O(1) - calls value.deleter
delattr(obj, 'value')  # Prints "Deleting value property"
```

### Custom __delattr__

```python
# O(1) - calls custom implementation
class TrackedDeletions:
    def __init__(self):
        self._deleted = []
    
    def __delattr__(self, name):
        """Track deletions - O(1)"""
        deleted = super().__getattribute__('_deleted')
        deleted.append(name)
        
        super().__delattr__(name)

obj = TrackedDeletions()
obj.x = 1
obj.y = 2

# O(1) - calls __delattr__
delattr(obj, 'x')  # Tracked in _deleted
delattr(obj, 'y')  # Tracked in _deleted

print(obj._deleted)  # ['x', 'y']
```

## Performance Patterns

### Deletion vs Setting to None

```python
# Option 1: Delete - O(1)
obj.attr = 42
delattr(obj, 'attr')  # O(1) - completely removes

# Option 2: Set to None - O(1)
obj.attr = 42
obj.attr = None  # O(1) - keeps attribute, changes value

# Both are O(1), but have different semantics
# Delete if you want to remove the attribute
# Set None if you want to indicate "no value"

# Check existence
if hasattr(obj, 'attr'):  # O(1)
    print("Has attribute")

# Check for None
if obj.attr is not None:  # O(1)
    print("Has non-empty value")
```

### Batch Deletion

```python
# O(n) - delete multiple attributes
class Cleanup:
    pass

obj = Cleanup()

# Create attributes - O(n)
for i in range(1000):
    setattr(obj, f'attr{i}', i)

# Inefficient deletion
for i in range(1000):  # O(n)
    delattr(obj, f'attr{i}')  # O(1) per call

# Better - clear __dict__
obj.__dict__.clear()  # O(n) - single bulk operation

# Or replace with new object
obj = Cleanup()  # Start fresh
```

## Common Use Cases

### Cleanup After Use

```python
# O(1) - clean up temporary attributes
class TemporaryData:
    def process(self):
        # Create temporary
        self.temp_buffer = []  # O(1)
        self.temp_state = {}   # O(1)
        
        # ... do work ...
        
        # Cleanup - O(2)
        delattr(self, 'temp_buffer')  # O(1)
        delattr(self, 'temp_state')   # O(1)

data = TemporaryData()
data.process()
```

### Removing Sensitive Data

```python
# O(n) - clean up sensitive attributes
class SecureData:
    def __init__(self):
        self.public_id = 12345
        self.password = "secret123"
        self.api_key = "key_xyz"
    
    def sanitize(self):
        """Remove sensitive data - O(n)"""
        sensitive = ['password', 'api_key', 'token', 'secret']
        
        for attr in sensitive:  # O(n)
            if hasattr(self, attr):  # O(1)
                delattr(self, attr)  # O(1)

data = SecureData()
data.sanitize()  # O(n)

print(data.public_id)  # OK
try:
    print(data.password)  # AttributeError
except AttributeError:
    print("Password removed")
```

### Lazy Attribute Loading

```python
# O(1) - delete cached values to reload
class LazyLoader:
    def __init__(self, path):
        self.path = path
        self._data = None
    
    @property
    def data(self):
        """Load on demand - O(1) or O(load time)"""
        if not hasattr(self, '_loaded_data'):
            self._loaded_data = self._load()  # O(load time)
        return self._loaded_data
    
    def reload(self):
        """Force reload - O(1)"""
        if hasattr(self, '_loaded_data'):
            delattr(self, '_loaded_data')  # O(1) - invalidate cache

loader = LazyLoader('data.json')
val1 = loader.data  # O(load time) - loads from file
val2 = loader.data  # O(1) - returns cached

loader.reload()  # O(1) - invalidates cache
val3 = loader.data  # O(load time) - reloads
```

### Cache Invalidation

```python
# O(n) - invalidate cached properties
class CachedComputation:
    def __init__(self):
        self._cache = {}
    
    def _compute_expensive(self):
        return sum(range(1000000))
    
    @property
    def result(self):
        """Get cached result - O(1) or O(compute)"""
        if 'result' not in self._cache:
            self._cache['result'] = self._compute_expensive()
        return self._cache['result']
    
    def invalidate_cache(self):
        """Clear all cached values - O(n)"""
        keys_to_delete = list(self._cache.keys())
        
        for key in keys_to_delete:  # O(n)
            del self._cache[key]  # O(1)
        
        # Or simpler:
        self._cache.clear()  # O(n) - single call

compute = CachedComputation()
val1 = compute.result  # O(compute time) - calculates
val2 = compute.result  # O(1) - cached

compute.invalidate_cache()  # O(n)
val3 = compute.result  # O(compute time) - recalculates
```

### Object Reset

```python
# O(n) - reset object state
class StatefulObject:
    def __init__(self):
        self.state = {}
        self.history = []
    
    def update(self, **kwargs):
        """Update state - O(n)"""
        self.state.update(kwargs)  # O(n)
        self.history.append(kwargs)  # O(1)
    
    def reset(self):
        """Reset to initial state - O(n)"""
        # Delete all state attributes
        for key in list(self.state.keys()):  # O(n)
            del self.state[key]  # O(1)
        
        # Or simpler:
        self.state.clear()  # O(n)
        self.history.clear()  # O(n)

obj = StatefulObject()
obj.update(x=1, y=2)  # O(2)
obj.update(x=10)      # O(1)

obj.reset()  # O(n) - clears everything
```

## Advanced Usage

### Property Deletion Hooks

```python
# O(1) - cleanup on deletion
class ManagedResource:
    def __init__(self, resource):
        self._resource = resource
        self._cleanup_funcs = []
    
    def on_delete(self, func):
        """Register cleanup function - O(1)"""
        self._cleanup_funcs.append(func)  # O(1)
    
    def __del__(self):
        """Cleanup on garbage collection - O(n)"""
        for func in self._cleanup_funcs:  # O(n)
            func(self._resource)  # O(1)

class Resource:
    def __init__(self, name):
        self.name = name
    
    def close(self):
        print(f"Closing {self.name}")

# Usage
resource = Resource("database")
managed = ManagedResource(resource)

# O(1) - register cleanup
managed.on_delete(lambda r: r.close())

# When deleted, O(n) cleanup occurs
del managed  # Prints "Closing database"
```

## Practical Examples

### Temporary Attribute Management

```python
# O(1) - manage temporary attributes
class TemporaryAttributes:
    def __init__(self):
        self.persistent = "keep me"
    
    def with_temp(self, name, value):
        """Context manager for temp attributes"""
        setattr(self, name, value)  # O(1)
        try:
            yield self
        finally:
            delattr(self, name)  # O(1) - cleanup

obj = TemporaryAttributes()

# O(1) - create and delete
with obj.with_temp('temp', 'value'):
    print(obj.temp)  # Accessible inside context

try:
    print(obj.temp)  # AttributeError - outside context
except AttributeError:
    print("Temp attribute cleaned up")
```

### Attribute Filtering

```python
# O(n) - remove unwanted attributes
def remove_attributes(obj, patterns):
    """Remove attributes matching patterns - O(n)"""
    to_remove = []
    
    for attr in dir(obj):  # O(n log n)
        for pattern in patterns:  # O(m) - m = patterns
            if pattern in attr:  # O(1)
                to_remove.append(attr)
                break
    
    for attr in to_remove:  # O(k) - k = matched
        try:
            delattr(obj, attr)  # O(1)
        except:
            pass  # Can't delete some attributes

class Data:
    public_data = 1
    _private_data = 2
    __dunder__ = 3

obj = Data()

# O(n * m) - remove private attributes
remove_attributes(obj, ['_'])

print(hasattr(obj, '_private_data'))  # False
print(hasattr(obj, 'public_data'))    # True
```

### Object Serialization Cleanup

```python
# O(n) - remove unserializable attributes
import json

def prepare_for_serialization(obj):
    """Remove non-serializable attributes - O(n)"""
    non_serializable = ['_file_handle', '_connection', '_socket']
    
    for attr in non_serializable:  # O(n)
        if hasattr(obj, attr):  # O(1)
            delattr(obj, attr)  # O(1)
    
    return obj

class Data:
    def __init__(self):
        self.name = "Alice"
        self._file_handle = "file object"
        self.age = 30
        self._connection = "db connection"

data = Data()
prepare_for_serialization(data)

# Now serializable
json_str = json.dumps(data.__dict__)
```

## Edge Cases

### Deleting Non-Existent Attributes

```python
# O(1) - raises error on missing attribute
class Simple:
    pass

obj = Simple()

# Raises AttributeError
try:
    delattr(obj, 'missing')  # O(1) but raises
except AttributeError:
    print("Attribute doesn't exist")

# Better - check first
if hasattr(obj, 'attr'):  # O(1)
    delattr(obj, 'attr')  # O(1)
```

### Deleting Class vs Instance Attributes

```python
# O(1) - different for class vs instance
class MyClass:
    class_attr = 42

obj = MyClass()

# Delete class attribute
delattr(MyClass, 'class_attr')  # O(1)

# Can't delete instance attribute that doesn't exist
obj.instance_attr = 100  # O(1)
delattr(obj, 'instance_attr')  # O(1) - succeeds

# Instance deletion doesn't affect class
delattr(obj, 'class_attr')  # AttributeError - not on instance
```

### Descriptors with Deleter

```python
# O(1) - descriptor protocol
class Descriptor:
    def __set_name__(self, owner, name):
        self.name = f'_{name}'
    
    def __get__(self, obj, objtype=None):
        return getattr(obj, self.name, None)
    
    def __set__(self, obj, value):
        setattr(obj, self.name, value)
    
    def __delete__(self, obj):
        print(f"Deleting {self.name}")
        delattr(obj, self.name)

class MyClass:
    prop = Descriptor()

obj = MyClass()
obj.prop = 42

# O(1) - calls Descriptor.__delete__
del obj.prop  # Prints "Deleting _prop"
```

## Performance Considerations

### Deletion vs Clear

```python
# Individual deletions - O(n)
for i in range(1000):
    if hasattr(obj, f'attr{i}'):  # O(1)
        delattr(obj, f'attr{i}')  # O(1)
# Total: O(1000)

# Bulk clear - O(n)
obj.__dict__.clear()  # Single operation, faster

# Clear is 5-10% faster for large objects
```

### Avoiding Attribution Errors

```python
# Safe deletion pattern - O(n) safe
def safe_delete_attrs(obj, attrs):
    """Delete attributes safely - O(n)"""
    for attr in attrs:  # O(n)
        try:
            delattr(obj, attr)  # O(1)
        except AttributeError:
            pass  # Ignore missing attributes

# Better - check first
def safe_delete_checked(obj, attrs):
    """Delete with existence check - O(n)"""
    for attr in attrs:  # O(n)
        if hasattr(obj, attr):  # O(1)
            delattr(obj, attr)  # O(1)

# The try/except version is marginally faster
# The checked version is clearer
```

## Best Practices

✅ **Do**:
- Use `delattr()` to completely remove attributes
- Check with `hasattr()` before deleting
- Use in cleanup routines and context managers
- Clean up sensitive data before object disposal
- Use try/except for graceful failure handling

❌ **Avoid**:
- Deleting attributes that don't exist (check first)
- Deleting in __del__ unless necessary (GC may fail)
- Assuming deletion affects class-level attributes
- Frequent deletion/creation cycles (use None instead)
- Deleting within property setters (causes confusion)

## Related Functions

- **[getattr()](getattr.md)** - Get attribute value
- **[setattr()](setattr.md)** - Set attribute value
- **[hasattr()](hasattr.md)** - Check attribute existence
- **[dir()](dir.md)** - List attributes
- **[vars()](vars.md)** - Get __dict__

## Version Notes

- **Python 2.x**: `delattr()` available, basic functionality
- **Python 3.x**: Same behavior, optimized in CPython
- **All versions**: Returns None, respects descriptor protocol
