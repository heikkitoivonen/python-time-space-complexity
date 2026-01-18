# dir() Function Complexity

The `dir()` function returns a list of valid attributes for an object. It's essential for object introspection and exploring available methods and properties.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Collect attributes | O(n) | O(n) | n = number of attributes in MRO |
| MRO traversal | O(d) | O(1) | d = inheritance depth |
| Sort results | O(n log n) | O(n) | Results are sorted alphabetically |
| Total operation | O(n log n) | O(n) | Dominated by sorting |

*Note: dir() collects all attributes from the object's class hierarchy (MRO) and returns them sorted alphabetically.*

## Basic Usage

### List Object Attributes

```python
# O(n) - where n = number of attributes
my_list = [1, 2, 3]
attrs = dir(my_list)  # Returns all list methods and attributes

# Example output
# ['__add__', '__class__', '__contains__', ..., 'append', 'clear', 'copy', ...]

# Count attributes
num_attrs = len(dir(my_list))  # O(n)
```

### Explore Built-in Types

```python
# O(n) - enumerate all methods
string_methods = dir("")
list_methods = dir([])
dict_methods = dir({})

# Find specific methods
if 'append' in dir(list):  # O(n) - list search
    print("Lists have append method")
```

### Discover Class Members

```python
# O(n) - includes inherited members
class MyClass:
    class_var = 10
    
    def method1(self):
        pass
    
    def method2(self):
        pass

obj = MyClass()
attributes = dir(obj)  # O(n) - includes inherited from object

# Typical output: ['__class__', '__delattr__', ..., 'class_var', 'method1', 'method2']
```

## Complexity Details

### Linear Time Traversal

```python
# O(n) - iterates through all attributes
def custom_dir(obj):
    """Simulates how dir() works internally"""
    attributes = []
    
    # Check object's __dict__
    if hasattr(obj, '__dict__'):
        attributes.extend(obj.__dict__.keys())  # O(k) - k = instance attributes
    
    # Check class and inherited classes (MRO)
    for cls in type(obj).__mro__:  # O(d) - d = MRO depth
        if hasattr(cls, '__dict__'):
            attributes.extend(cls.__dict__.keys())  # O(m) - m = class attributes
    
    # Sort alphabetically
    return sorted(set(attributes))  # O(n log n) - n = total unique attributes
```

### Method Resolution Order (MRO) Traversal

```python
# O(n log n) - includes MRO traversal
class A:
    def method_a(self):
        pass

class B(A):
    def method_b(self):
        pass

class C(B):
    def method_c(self):
        pass

obj = C()
# dir() traverses: C -> B -> A -> object
# Total complexity still O(n log n) where n = total attributes in hierarchy
attrs = dir(obj)
```

### Performance with Inheritance

```python
# O(n log n) - grows with inheritance depth and attribute count
# Shallow class
class Simple:
    pass

# Deep hierarchy
class Level1:
    attr1 = 1

class Level2(Level1):
    attr2 = 2

class Level3(Level2):
    attr3 = 3

class Level4(Level3):
    attr4 = 4

obj = Level4()
# dir(obj) still O(n log n) but n is larger
attrs = dir(obj)  # ~40 attributes (including inherited)
```

## Filtering Attributes

### Finding Specific Types

```python
# O(n) - filter attributes after dir() call
class Data:
    public_attr = 1
    _private_attr = 2
    __dunder_attr = 3
    
    def public_method(self):
        pass
    
    def _private_method(self):
        pass

obj = Data()

# Get all attributes - O(n log n)
all_attrs = dir(obj)

# Filter to public only - O(n)
public = [attr for attr in all_attrs if not attr.startswith('_')]

# Filter methods only - O(n)
import inspect
methods = [attr for attr in all_attrs if callable(getattr(obj, attr))]

# Filter to dunder methods - O(n)
dunders = [attr for attr in all_attrs if attr.startswith('__')]
```

### Exclude Special Attributes

```python
# O(n) - filter out implementation details
class MyClass:
    user_method = lambda self: None
    data = "user data"

def get_user_attributes(obj):
    """Get non-dunder attributes - O(n)"""
    return [attr for attr in dir(obj) 
            if not attr.startswith('_')]

obj = MyClass()
user_attrs = get_user_attributes(obj)  # Only user-defined items
```

## Performance Patterns

### vs Accessing __dict__ Directly

```python
# Direct __dict__ access - O(1)
obj = object()
if hasattr(obj, '__dict__'):
    attrs = obj.__dict__  # O(1) - just instance attributes
    
# vs full dir() - O(n log n)
all_attrs = dir(obj)  # O(n log n) - all accessible attributes

# Use cases:
# - Want instance-only attributes? Use __dict__ (O(1))
# - Want all accessible attributes? Use dir() (O(n log n))
```

### vs inspect Module

```python
# dir() - O(n log n) and simple
simple_attrs = dir(obj)

# inspect.getmembers() - O(n²) due to getattr calls
import inspect
detailed = inspect.getmembers(obj)  # O(n²) - calls getattr() on each attribute

# Use dir() for simple listing, inspect for detailed analysis
```

## Common Use Cases

### Interactive Exploration

```python
# O(n log n) - exploring object capabilities
import json

# What can I do with json?
json_funcs = dir(json)

# What methods does a list have?
list_methods = dir([])

# Typical usage in Python REPL:
# >>> import os
# >>> dir(os)
# >>> [attr for attr in dir(os) if 'path' in attr.lower()]
```

### Discovering Available Methods

```python
# O(n log n) - find methods by name pattern
class API:
    def get_user(self): pass
    def get_posts(self): pass
    def set_user(self): pass
    def delete_user(self): pass

api = API()

# Find all 'get' methods - O(n)
get_methods = [m for m in dir(api) if m.startswith('get')]

# Output: ['get_posts', 'get_user']
```

### Avoiding AttributeError

```python
# O(n log n) - check before accessing
def safe_access(obj, attr_name):
    """Safely access attribute - O(n log n) check"""
    if attr_name in dir(obj):  # O(n log n)
        return getattr(obj, attr_name)  # O(1)
    else:
        return None

class MyClass:
    my_attr = 42

obj = MyClass()
val = safe_access(obj, 'my_attr')  # Returns 42
val = safe_access(obj, 'missing')  # Returns None
```

## Advanced Usage

### Class Introspection

```python
# O(n log n) - analyze class structure
class Parent:
    parent_method = lambda self: None

class Child(Parent):
    child_method = lambda self: None

parent_attrs = set(dir(Parent))  # O(n log n)
child_attrs = set(dir(Child))    # O(n log n)

# Find newly added attributes
new_attrs = child_attrs - parent_attrs  # O(n)
print(new_attrs)  # {'child_method'}

# Find inherited attributes
inherited = parent_attrs & child_attrs  # O(n)
```

### Dynamic Attribute Discovery

```python
# O(n²) - discover and access attributes
def inspect_object(obj):
    """Get all attributes with their types - O(n²)"""
    attrs = dir(obj)  # O(n log n)
    
    results = {}
    for attr in attrs:  # O(n) iterations
        try:
            value = getattr(obj, attr)  # O(1) per call
            results[attr] = type(value).__name__
        except:
            results[attr] = 'Error accessing'
    
    return results

# Total: O(n) * O(1) = O(n²) due to getattr overhead
data = [1, 2, 3]
attr_types = inspect_object(data)
```

### Finding Callable Attributes

```python
# O(n²) - find methods vs properties
def get_methods(obj):
    """Extract all methods - O(n²)"""
    return {attr for attr in dir(obj)  # O(n log n)
            if callable(getattr(obj, attr))}  # O(1) per check

def get_properties(obj):
    """Extract all non-callable attributes - O(n²)"""
    return {attr for attr in dir(obj)  # O(n log n)
            if not callable(getattr(obj, attr))}  # O(1) per check

my_list = [1, 2, 3]
methods = get_methods(my_list)  # append, clear, copy, ...
properties = get_properties(my_list)  # Much smaller set
```

## Practical Examples

### Module Exploration

```python
# O(n log n) - explore standard library module
import math

# What's available in math?
math_attrs = dir(math)

# Filter to functions (skip constants)
import inspect
math_funcs = [attr for attr in dir(math) 
              if callable(getattr(math, attr)) 
              and not attr.startswith('_')]

print(math_funcs)  # ['acos', 'acosh', 'asin', ...]
```

### API Discovery

```python
# O(n log n) - discover API capabilities
class DataService:
    """Example API class"""
    
    def fetch_users(self): pass
    def fetch_posts(self): pass
    def create_user(self): pass
    def update_user(self): pass
    def delete_user(self): pass
    def _internal_cache(self): pass

service = DataService()

# List all public operations
public_ops = [op for op in dir(service) 
              if not op.startswith('_') 
              and callable(getattr(service, op))]

# Output: ['create_user', 'delete_user', 'fetch_posts', ...]
```

### Attribute Validation

```python
# O(n log n) - validate object has required attributes
def validate_interface(obj, required_attrs):
    """Check object implements interface - O(n log n)"""
    obj_attrs = dir(obj)  # O(n log n)
    
    missing = []
    for attr in required_attrs:  # O(m) - m = required attributes
        if attr not in obj_attrs:  # O(n) - list search
            missing.append(attr)
    
    return missing if missing else None

# Total: O(n log n) + O(m * n)

class FileWriter:
    def write(self): pass
    def close(self): pass

required = ['write', 'close', 'flush']
missing = validate_interface(FileWriter(), required)
# Returns: ['flush'] - missing required method
```

## Edge Cases

### Built-in Types

```python
# O(n log n) - but very fast for built-ins
int_attrs = dir(int)      # ~50 attributes
str_attrs = dir(str)      # ~100+ attributes
list_attrs = dir(list)    # ~50 attributes

# Built-ins are optimized, actual time very small
```

### Objects Without __dict__

```python
# O(n log n) - still works for objects without __dict__
class Slots:
    __slots__ = ['x', 'y']

obj = Slots()
attrs = dir(obj)  # O(n log n) - works despite __slots__

# Unlike __dict__, __slots__ objects still have accessible attributes
```

### Circular References

```python
# O(n log n) - handles circular references
class Node:
    def __init__(self, value):
        self.value = value
        self.next = None

node1 = Node(1)
node2 = Node(2)
node1.next = node2
node2.next = node1  # Circular reference

attrs = dir(node1)  # O(n log n) - safely handles cycle
```

## Performance Considerations

### Caching Results

```python
# Avoid repeated dir() calls
class Inspector:
    def __init__(self):
        self._cache = {}
    
    def get_attrs(self, obj):
        """Cache dir() results - O(1) after first call"""
        obj_id = id(obj)
        
        if obj_id not in self._cache:
            self._cache[obj_id] = dir(obj)  # O(n log n) - first call
        
        return self._cache[obj_id]  # O(1) - cached

inspector = Inspector()
attrs1 = inspector.get_attrs(my_list)  # O(n log n)
attrs2 = inspector.get_attrs(my_list)  # O(1) - from cache
```

### Filtering Efficiency

```python
# Better: filter before processing
def get_public_methods(obj):
    """More efficient filtering"""
    # Single pass through dir()
    return [attr for attr in dir(obj)  # O(n log n)
            if not attr.startswith('_')  # O(1)
            and callable(getattr(obj, attr))]  # O(1)

# vs: Multiple passes (slower)
def slow_approach(obj):
    attrs = dir(obj)  # O(n log n)
    public = [a for a in attrs if not a.startswith('_')]  # O(n)
    methods = [a for a in public if callable(getattr(obj, a))]  # O(n²)
    return methods  # Total: O(n²)
```

## Best Practices

✅ **Do**:

- Use `dir()` for interactive exploration
- Cache results if used multiple times on same object
- Filter results for specific attribute types
- Use with `help()` and `type()` for complete understanding
- Check before accessing with `in` operator on dir() result

❌ **Avoid**:

- Using `dir()` in tight loops without caching
- Assuming `dir()` output format is stable across versions
- Using it for performance-critical code (it's O(n log n))
- Forgetting that `dir()` includes inherited attributes
- Assuming all listed attributes are accessible (some may raise exceptions)

## Related Functions

- **[getattr()](getattr.md)** - Get attribute value
- **[hasattr()](hasattr.md)** - Check attribute existence
- **[setattr()](setattr.md)** - Set attribute value
- **[delattr()](delattr.md)** - Delete attribute
- **[vars()](vars.md)** - Get __dict__
- **[help()](help.md)** - Get documentation
- **type()** - Get object type
- **[inspect](https://docs.python.org/3/library/inspect.html)** - Advanced introspection

## Version Notes

- **Python 2.x**: `dir()` available, returns list of strings
- **Python 3.x**: Same behavior, returns alphabetically sorted list
- **All versions**: Returns attributes in alphabetical order (implementation detail)
