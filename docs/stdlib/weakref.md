# Weakref Module

The `weakref` module provides utilities for creating weak references to objects, allowing garbage collection when objects are no longer strongly referenced.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ref(obj)` | O(1) | O(1) | Create weak reference |
| `proxy(obj)` | O(1) | O(1) | Create proxy object |
| `getweakrefcount(obj)` | O(1) | O(1) | Count weak refs |
| `getweakrefs(obj)` | O(n) | O(n) | n = weak refs |
| `WeakKeyDictionary` operations | O(1) avg | O(n) | n = entries |
| `WeakValueDictionary` operations | O(1) avg | O(n) | n = entries |

## Common Operations

### Creating Weak References

```python
import weakref

class MyClass:
    pass

obj = MyClass()

# O(1) - create weak reference
weak_ref = weakref.ref(obj)

# O(1) - dereference (get original object)
original = weak_ref()
if original is not None:
    print("Object still exists")
else:
    print("Object was garbage collected")

# When obj is deleted, weak_ref() returns None
del obj
print(weak_ref())  # None
```

### Creating Proxies

```python
import weakref

class MyClass:
    def method(self):
        return "Hello"

obj = MyClass()

# O(1) - create proxy
proxy = weakref.proxy(obj)

# Use like the original object
result = proxy.method()  # O(1) lookup + O(n) method execution

# After deletion, proxy raises ReferenceError
del obj
try:
    proxy.method()  # Raises ReferenceError
except ReferenceError:
    print("Object was garbage collected")
```

### Callbacks on Object Deletion

```python
import weakref

class Resource:
    def __init__(self, name):
        self.name = name

def cleanup_callback(weak_ref):
    """Called when object is garbage collected - O(1)"""
    print("Resource was cleaned up!")

resource = Resource("data.txt")

# O(1) - create reference with callback
weak_ref = weakref.ref(resource, cleanup_callback)

# When resource is deleted, callback is invoked - O(1)
del resource  # Prints: "Resource was cleaned up!"
```

## Common Use Cases

### Caching with Automatic Cleanup

```python
import weakref

class CachedResource:
    """Cache that auto-cleans when objects are GC'd"""
    
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()
    
    def register(self, key, obj):
        """O(1) - add to cache"""
        self._cache[key] = obj
    
    def get(self, key):
        """O(1) - retrieve from cache"""
        return self._cache.get(key)
    
    def size(self):
        """O(1) - active entries only"""
        # Dead entries auto-removed during iteration
        return len(self._cache)

# Usage
cache = CachedResource()
obj1 = {"data": "value"}
cache.register("key1", obj1)

retrieved = cache.get("key1")  # O(1)
print(retrieved)  # {"data": "value"}

del obj1
print(cache.size())  # obj1 auto-removed - O(1)
```

### Observing Object Lifecycle

```python
import weakref

class LifecycleObserver:
    """Track object creation and destruction"""
    
    def __init__(self):
        self._objects = {}
        self._count = 0
    
    def register(self, obj):
        """O(1) - track object"""
        obj_id = id(obj)
        
        def on_delete(ref):
            del self._objects[obj_id]
            self._count -= 1
        
        weak_ref = weakref.ref(obj, on_delete)
        self._objects[obj_id] = weak_ref
        self._count += 1
        return self._count
    
    def alive_count(self):
        """O(1) - count alive objects"""
        return self._count

# Usage
observer = LifecycleObserver()

obj1 = [1, 2, 3]
obj2 = [4, 5, 6]

observer.register(obj1)  # O(1)
observer.register(obj2)  # O(1)
print(observer.alive_count())  # 2

del obj1
print(observer.alive_count())  # 1
```

### Circular Reference Prevention

```python
import weakref

class Parent:
    def __init__(self, name):
        self.name = name
        self.children = []
    
    def add_child(self, child):
        self.children.append(child)
        child.parent = weakref.ref(self)  # O(1) - weak reference

class Child:
    def __init__(self, name):
        self.name = name
        self.parent = None  # Will be weakref
    
    def get_parent(self):
        """O(1) - dereference weak ref"""
        if self.parent is None:
            return None
        parent = self.parent()
        if parent is None:
            print("Parent was garbage collected")
        return parent

# No circular reference!
parent = Parent("Dad")
child = Child("Son")
parent.add_child(child)  # O(1)

print(child.get_parent().name)  # O(1) dereference

del parent
print(child.get_parent())  # None (parent deleted)
```

### Registry Pattern

```python
import weakref

class Registry:
    """Register objects and query them later - O(1) add/remove"""
    
    def __init__(self):
        self._registry = weakref.WeakSet()
    
    def register(self, obj):
        """O(1) - add to registry"""
        self._registry.add(obj)
    
    def count(self):
        """O(n) - count active objects where n = registered"""
        # Dead objects auto-removed
        return len(self._registry)
    
    def iterate_active(self):
        """O(n) - iterate only live objects"""
        for obj in self._registry:
            yield obj

# Usage
registry = Registry()

obj1 = {"id": 1}
obj2 = {"id": 2}
obj3 = {"id": 3}

registry.register(obj1)  # O(1)
registry.register(obj2)  # O(1)
registry.register(obj3)  # O(1)

print(f"Registered: {registry.count()}")  # O(1) = 3

del obj2
print(f"Registered: {registry.count()}")  # O(1) = 2

for obj in registry.iterate_active():  # O(n) = 2 iterations
    print(obj)
```

## Performance Tips

### Use WeakKeyDictionary for Object-Based Keys

```python
import weakref

# Bad: Strong references keep objects alive
strong_cache = {}

# Good: Weak references allow GC
weak_cache = weakref.WeakKeyDictionary()

class Key:
    pass

key = Key()
weak_cache[key] = "value"  # O(1)

# Object can be GC'd even with key in dict
del key
print(len(weak_cache))  # 0 - auto-cleaned
```

### Cache Query Without Keeping References

```python
import weakref

class TransientCache:
    """Query cache without holding references"""
    
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()
    
    def query(self, key):
        """O(1) - may return None if GC'd"""
        return self._cache.get(key)
    
    def query_exists(self, key):
        """O(1) - check existence without strong ref"""
        return key in self._cache

# Usage
cache = TransientCache()
obj = {"data": "value"}
cache._cache["key"] = obj  # O(1)

# Query without keeping obj alive
data = cache.query("key")  # O(1)
# obj might be GC'd here

exists = cache.query_exists("key")  # O(1) - won't prevent GC
```

## Version Notes

- **Python 2.6+**: Basic weakref support
- **Python 3.x**: All features available
- **Python 3.13+**: Performance improvements

## Related Documentation

- [Gc Module](gc.md) - Garbage collection control
- [Collections Module](collections.md) - OrderedDict alternatives
