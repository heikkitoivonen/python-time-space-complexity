# id() Function Complexity

The `id()` function returns a unique identifier for an object. In CPython, this is the object's memory address, but the exact meaning depends on the Python implementation.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `id(object)` | O(1) | O(1) | Get object identity (memory address in CPython) |
| ID comparison | O(1) | O(1) | Compare two IDs (integer comparison) |
| `is` operator | O(1) | O(1) | Equivalent to `id(a) == id(b)` but faster |

## Basic Usage

### Getting Object Identity

```python
# Get unique ID - O(1)
x = 42
id_x = id(x)  # O(1) - unique number

y = 42
id_y = id(y)  # O(1)

# Same value doesn't mean same object
print(x == y)      # True - equal values
print(id(x) == id(y))  # Might be True (for small ints) or False

# Different objects always have different IDs
a = [1, 2, 3]
b = [1, 2, 3]
print(a == b)      # True - equal content
print(id(a) == id(b))  # False - different objects
```

### Object Identity

```python
# is operator uses id() comparison - O(1)
x = [1, 2, 3]
y = x  # Same reference

print(x is y)      # True - same object
print(id(x) == id(y))  # True - same ID

z = [1, 2, 3]
print(x is z)      # False - different objects
print(id(x) == id(z))  # False - different IDs
```

## Common Patterns

### Checking Object Identity

```python
# Use is/is not instead of id() directly - cleaner and faster
x = [1, 2, 3]
y = x
z = [1, 2, 3]

# Good - use is operator
if x is y:  # O(1) - equivalent to id(x) == id(y)
    print("Same object")

if x is not z:  # O(1)
    print("Different objects")

# Avoid - using id() directly (less readable and slower)
if id(x) == id(y):
    print("Same object")
```

### Tracking Object Lifecycle

```python
# Track when objects are created and destroyed
import weakref

objects = {}

class MyObject:
    def __init__(self, name):
        self.name = name
        # Store weak reference to track object
        obj_id = id(self)  # O(1)
        objects[obj_id] = self.name
        print(f"Created: {self.name} (ID: {obj_id})")
    
    def __del__(self):
        obj_id = id(self)  # O(1)
        if obj_id in objects:
            del objects[obj_id]
        print(f"Destroyed: {objects.get(obj_id, 'unknown')}")

# Usage
obj = MyObject("test")  # Created with ID
del obj  # Destroyed
```

### Cycle Detection

```python
# Detect cycles in object graph - O(n) with id()
def has_cycle(obj, visited=None):
    """Check if object has reference cycle"""
    if visited is None:
        visited = set()
    
    obj_id = id(obj)  # O(1)
    
    if obj_id in visited:
        return True  # Cycle detected!
    
    visited.add(obj_id)  # O(1)
    
    # Check attributes (simplified)
    if hasattr(obj, '__dict__'):
        for attr_val in obj.__dict__.values():
            if has_cycle(attr_val, visited):
                return True
    
    return False

# Usage
a = {}
b = {'a': a}
a['b'] = b  # Create cycle

print(has_cycle(a))  # True - cycle found
```

## Implementation Details

### CPython: ID is Memory Address

```python
# In CPython, id() returns memory address - O(1)
x = object()
memory_addr = id(x)  # O(1) - memory address

# This is why small integers have same ID
# They're cached in memory

# ID persists as long as object exists
print(id(x))  # Same memory address
print(id(x))  # Same memory address again
```

### Other Implementations

```python
# PyPy, Jython, IronPython may have different IDs
# But id() still O(1)

# ID not guaranteed to be memory address
# Just guaranteed to be unique per object

# id() is mainly for debugging
# Don't rely on specific ID values
```

## Performance Considerations

### ID Lookup Speed

```python
# id() is very fast - O(1)
import time

x = object()

start = time.time()
for _ in range(1000000):
    id(x)  # O(1) each
end = time.time()

print(f"1M calls: {end - start:.4f}s")  # Very fast!
```

### Using id() in Collections

```python
# Can use object ID as dict key - O(1) lookup
cache = {}

obj = object()
obj_id = id(obj)  # O(1)

cache[obj_id] = "data"  # O(1)
value = cache[obj_id]   # O(1)

# But prefer using object itself as key
cache = {}
cache[obj] = "data"     # O(1) - cleaner
value = cache[obj]      # O(1)
```

## Version Notes

- **Python 2.x**: id() available, returns memory address in CPython
- **Python 3.x**: Same behavior as Python 2
- **All implementations**: id() guaranteed O(1)

## Related Functions

- **[hash()](hash.md)** - Different from ID; used for dict/set
- **[isinstance()](isinstance.md)** - Check type, not identity
- **type()** - Get object type

## Best Practices

✅ **Do**:

- Use `is` operator instead of `id(x) == id(y)`
- Use `is None` for None checks (standard)
- Use id() for debugging and object tracking

❌ **Avoid**:

- Using id() in regular code (use `is` instead)
- Relying on ID across Python sessions
- Using ID as hash for collections (use hash() or object itself)
