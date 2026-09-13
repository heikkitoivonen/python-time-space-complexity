# vars() Function Complexity

The `vars()` function returns an object's `__dict__`, or acts like
`locals()` when called without arguments. With an argument it is one attribute
lookup: an instance or module hands back its own namespace dict, a class hands
back a read-only `mappingproxy` over its namespace, and a class that defines
`__dict__` as a descriptor pays whatever that descriptor costs. Nothing is
copied until the caller copies it. Without an argument, the result inside a
function is a copy of the frame's locals.

## Complexity Analysis

Let `k` be the number of attributes in the namespace and `n` the number of
local variables in the calling function.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `vars(obj)` on an instance or module | O(1) | O(1) | Returns `obj.__dict__` itself, not a copy |
| `vars(cls)` | O(1) | O(1) | A fresh read-only `mappingproxy` over the class namespace |
| `vars()` at module or class scope | O(1) | O(1) | The namespace dict itself, as `locals()` |
| `vars()` in a function | O(n²) from Python 3.13, O(n) before | O(n) | A snapshot of the frame's locals; writes to it do not reach the function. From 3.13 each of the `n` names is found by a linear scan of the frame |
| Read or write a key of the result | O(1) avg | O(1) | Dict operations; a write reaches an instance or module, and raises `TypeError` on a class's proxy |
| Copy the result: `.copy()`, `dict()`, `**vars(obj)` | O(k) | O(k) | Every attribute is copied |
| Object without `__dict__` | O(1) | O(1) | Raises `TypeError` |

## Basic Usage

### Get Object's Attributes Dictionary

```python
# O(1) - get reference to __dict__
class MyClass:
    x = 1
    y = 2

obj = MyClass()
obj.z = 3

# O(1) - return reference to __dict__
attrs = vars(obj)  # {'z': 3}

# Note: class attributes (x, y) not included
# vars() returns only instance attributes
```

### No-Argument Form

```python
# vars() with no argument is equivalent to locals()
def f():
    x = 1
    return vars()  # Builds a snapshot dict: O(n²) in the number of locals
                   # from Python 3.13, O(n) before. vars(obj) hands back
                   # __dict__ in O(1)
```

### Inspect Object State

```python
# O(1) - examine object's state
class Config:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

config = Config(host='localhost', port=8000, debug=True)

# O(1) - get all instance attributes
state = vars(config)

print(state)  # {'host': 'localhost', 'port': 8000, 'debug': True}

# Equivalent to config.__dict__
print(vars(config) is config.__dict__)  # True
```

### Modify Attributes Indirectly

```python
# O(1) - modify through vars() reference
class Data:
    pass

obj = Data()

# O(1) - get dict
attrs = vars(obj)

# O(1) - modify through returned reference
attrs['x'] = 1  # Changes obj.x
attrs['y'] = 2  # Changes obj.y

print(obj.x)  # 1
print(obj.y)  # 2
```

## Complexity Details

### Direct __dict__ Access

```python
# O(1) - all equivalent
class Simple:
    pass

obj = Simple()
obj.attr = 42

# All of these are O(1):
dict1 = vars(obj)            # O(1) - get __dict__
dict2 = obj.__dict__         # O(1) - direct access
dict3 = vars(obj) is dict2   # True - same object

# vars() is just a convenience wrapper
```

### What vars() Returns

```python
# O(1) - returns same dict, not a copy
class Data:
    pass

obj = Data()

# Get the dict
d = vars(obj)  # O(1)

# Modifications affect original
d['x'] = 1  # O(1)

# obj is updated
print(obj.x)  # 1

# Changes to obj affect the dict
obj.y = 2  # O(1)
print(d['y'])  # 2
```

## Performance Patterns

### vars() vs dir()

```python
# vars() - O(1), instance attributes only
class Data:
    class_attr = 10
    
    def __init__(self):
        self.instance_attr = 20

obj = Data()

# O(1) - instance attributes only
inst_attrs = vars(obj)  # {'instance_attr': 20}

# O(n log n) - all accessible attributes, sorted
all_attrs = dir(obj)  # ['__class__', ..., 'class_attr', 'instance_attr']

# vars() is narrower: instance attributes only
```

### vars() vs getattr Loop

```python
# O(1) - vars() approach
class Data:
    pass

obj = Data()
obj.x, obj.y, obj.z = 1, 2, 3

# O(1) - get all at once
all_attrs = vars(obj)  # O(1)

# vs O(n) - getattr approach
attrs = {}
for attr in dir(obj):  # O(n log n)
    try:
        attrs[attr] = getattr(obj, attr)  # O(1) each
    except AttributeError:
        pass
# Total: O(n log n) for dir(), plus n attribute accesses

# vars() is much faster
```

## Common Use Cases

### Object Serialization

```python
# O(n) - convert object to dictionary
class User:
    def __init__(self, name, age, email):
        self.name = name
        self.age = age
        self.email = email
    
    def to_dict(self):
        """Export as dictionary - O(1)"""
        return vars(self)  # O(1) - get __dict__

user = User("Alice", 30, "alice@example.com")

# O(1) - convert to dict
data = user.to_dict()

# Can serialize to JSON
import json
json_str = json.dumps(data)  # O(n) - serialize
```

### Object Comparison

```python
# O(n) - compare object states
def objects_equal(obj1, obj2):
    """Compare object attributes - O(n) value comparisons"""
    return vars(obj1) == vars(obj2)  # O(n) - dict comparison

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

p1 = Point(1, 2)
p2 = Point(1, 2)
p3 = Point(2, 3)

# O(n) - compare attributes
print(objects_equal(p1, p2))  # True
print(objects_equal(p1, p3))  # False
```

### Object Copying

```python
# O(n) - shallow copy of object
def shallow_copy(obj):
    """Copy object attributes - O(n)"""
    if not hasattr(obj, '__dict__'):
        return obj  # No __dict__ to copy
    
    # Create new instance
    copy = obj.__class__.__new__(obj.__class__)
    
    # O(n) - copy attributes
    copy.__dict__.update(vars(obj))
    
    return copy

class Data:
    def __init__(self, value):
        self.value = value
        self.items = [1, 2, 3]

original = Data(42)

# O(n) - create shallow copy
copy = shallow_copy(original)

copy.value = 100
copy.items.append(4)

print(original.value)  # 42 (copied)
print(original.items)  # [1, 2, 3, 4] (shared reference)
```

### Object Merging

```python
# O(m + K) - merge attributes from m objects holding K attributes in total
def merge_objects(*objs):
    """Merge attributes from all objects - O(m + K)"""
    result = {}
    
    for obj in objs:  # O(m) - m = number of objects
        result.update(vars(obj))  # O(k) - k = attributes per object
    
    return result

class Config1:
    def __init__(self):
        self.host = "localhost"

class Config2:
    def __init__(self):
        self.port = 8000

obj1 = Config1()
obj2 = Config2()

# O(m + K) - merge all attributes
merged = merge_objects(obj1, obj2)
# {'host': 'localhost', 'port': 8000}
# Class attributes are not in vars(); only instance attributes merge
```

### Constructor Parameter Passing

```python
# O(n) - extract parameters for reconstruction
class Point:
    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        self.z = z
    
    def transform(self, scale):
        """Apply transformation - O(1)"""
        self.x *= scale
        self.y *= scale
        self.z *= scale
        return self
    
    def copy(self):
        """Create similar instance - O(n)"""
        # O(n) - ** copies the attributes into keyword arguments
        return Point(**vars(self))

p1 = Point(1, 2, 3)
p1.transform(2)

# O(n) - create copy with same attributes
p2 = p1.copy()

print(vars(p2))  # {'x': 2, 'y': 4, 'z': 6}
```

## Advanced Usage

### Attribute Validation

```python
# O(n) - validate all attributes
class ValidatedObject:
    def validate(self, schema):
        """Validate attributes against schema - O(n) validator calls"""
        attrs = vars(self)  # O(1)
        
        for attr_name, validator in schema.items():  # O(n)
            if attr_name not in attrs:  # O(1)
                raise ValueError(f"Missing {attr_name}")
            
            if not validator(attrs[attr_name]):  # the validator's own cost
                raise ValueError(f"Invalid {attr_name}")
        
        return True

class User(ValidatedObject):
    def __init__(self, name, age):
        self.name = name
        self.age = age

user = User("Alice", 30)

schema = {
    'name': lambda x: isinstance(x, str),
    'age': lambda x: isinstance(x, int) and x > 0
}

# O(n) - validate
user.validate(schema)  # Succeeds
```

### Object Filtering

```python
# O(n) - filter attributes
def extract_public(obj):
    """Get public attributes only - O(n)"""
    return {k: v for k, v in vars(obj).items()  # O(n)
            if not k.startswith('_')}  # O(1) per attribute

class Data:
    def __init__(self):
        self.public = "visible"
        self._private = "hidden"
        self.__dunder = "secret"

obj = Data()

# O(n) - extract public only
public = extract_public(obj)
# {'public': 'visible'}
```

### Object Difference

```python
# O(n) - find differences between objects
def object_diff(obj1, obj2):
    """Find attribute differences - O(n) value comparisons"""
    dict1 = vars(obj1)  # O(1)
    dict2 = vars(obj2)  # O(1)
    
    only_in_1 = set(dict1) - set(dict2)  # O(n)
    only_in_2 = set(dict2) - set(dict1)  # O(n)
    
    modified = {}
    for key in set(dict1) & set(dict2):  # O(n)
        if dict1[key] != dict2[key]:  # one value comparison
            modified[key] = (dict1[key], dict2[key])
    
    return {
        'only_in_1': only_in_1,
        'only_in_2': only_in_2,
        'modified': modified
    }

class v1:
    def __init__(self):
        self.x = 1
        self.y = 2

class v2:
    def __init__(self):
        self.x = 10
        self.z = 3

obj1 = v1()
obj2 = v2()

# O(n) - find differences
diff = object_diff(obj1, obj2)
```

## Practical Examples

### Configuration Export

```python
# O(n) - export configuration
class Settings:
    def __init__(self):
        self.debug = False
        self.timeout = 30
        self.max_retries = 3
    
    def to_dict(self):
        """Export settings - O(1)"""
        return vars(self)
    
    def from_dict(self, data):
        """Import settings - O(n)"""
        self.__dict__.update(data)  # O(n)

settings = Settings()

# O(1) - export
exported = settings.to_dict()

# Modify some settings
exported['debug'] = True
exported['timeout'] = 60

# O(n) - import
new_settings = Settings()
new_settings.from_dict(exported)

print(new_settings.debug)     # True
print(new_settings.timeout)   # 60
```

### Object State Snapshot

```python
# O(n) - capture object state
class StatefulObject:
    def __init__(self):
        self.x = 1
        self.y = 2
    
    def snapshot(self):
        """Capture state - O(n)"""
        # Make a copy of __dict__
        return vars(self).copy()  # O(n) - shallow copy
    
    def restore(self, snapshot):
        """Restore state - O(n)"""
        self.__dict__.clear()  # O(n)
        self.__dict__.update(snapshot)  # O(n)

obj = StatefulObject()

# O(n) - save state
state1 = obj.snapshot()

obj.x = 100
obj.y = 200

# O(n) - restore state
obj.restore(state1)

print(obj.x, obj.y)  # 1, 2
```

### Data Class Conversion

```python
# O(n) - convert to dict
from dataclasses import dataclass

@dataclass
class Person:
    name: str
    age: int
    email: str

person = Person("Alice", 30, "alice@ex.com")

# O(1) - get all attributes
person_dict = vars(person)

# Unlike dataclasses.asdict(), which builds a new dict and copies
# nested values recursively, this is the instance's own __dict__
print(person_dict)
# {'name': 'Alice', 'age': 30, 'email': 'alice@ex.com'}
```

## Edge Cases

### Objects Without __dict__

```python
# O(1) - raises TypeError for objects without __dict__
import sys

# Modules have __dict__
vars(sys)  # O(1) - returns sys.__dict__

# Classes have __dict__
class MyClass:
    pass

vars(MyClass)  # O(1) - a read-only mappingproxy over the class namespace

# But some objects don't have __dict__
try:
    vars(42)  # TypeError - int has no __dict__
except TypeError:
    print("No __dict__ attribute")

# __slots__ without '__dict__', here and in every base, leaves no __dict__
class Slotted:
    __slots__ = ['x']

obj = Slotted()
try:
    vars(obj)  # TypeError - no '__dict__' slot
except TypeError:
    print("Slotted objects have no __dict__")
```

### __slots__ Alternative

```python
# O(n) - get slot values manually
class Slotted:
    __slots__ = ['x', 'y', 'z']
    
    def to_dict(self):
        """Convert slots to dict - O(n)"""
        return {attr: getattr(self, attr)  # O(1) per attr
                for attr in self.__slots__}  # O(n) iterations

obj = Slotted()
obj.x = 1
obj.y = 2
obj.z = 3

# O(n) - manually extract slot values
slot_dict = obj.to_dict()  # {'x': 1, 'y': 2, 'z': 3}
```

### Modules and Classes

```python
# O(1) - modules return their namespace
import os

# O(1) - get module's attributes
os_attrs = vars(os)  # Returns os.__dict__

# O(1) - classes return a read-only view of their namespace
str_attrs = vars(str)  # mappingproxy({'__new__': ..., 'join': ..., ...})

# Both are O(1) - nothing is copied
```

## Performance Considerations

### vars() vs __dict__ Direct Access

```python
# Both are O(1)
class Data:
    pass

obj = Data()

# Direct access - O(1)
d1 = obj.__dict__

# Via vars() - O(1)
d2 = vars(obj)

# They're the same object
print(d1 is d2)  # True
```

### Copying vs Referencing

```python
class Data:
    pass

obj = Data()

# Referencing - O(1)
attrs = vars(obj)  # Reference to __dict__

# Modifications affect object
attrs['x'] = 1
print(obj.x)  # 1 - changed!

# Copying - O(n)
attrs_copy = vars(obj).copy()  # Shallow copy
attrs_copy['y'] = 2
print(hasattr(obj, 'y'))  # False - not changed

# Use .copy() if you don't want side effects
```

## Best Practices

✅ **Do**:

- Use `vars()` for quick attribute dictionary access
- Use for serialization (objects to dicts)
- Use for object copying and comparison
- Use for attribute inspection in debugging
- Copy the result (`dict(vars(obj))`) before mutating it if the object must not change

❌ **Avoid**:

- Using `vars()` on objects without __dict__ (check first)
- Writing to `vars(cls)`: a class's namespace comes back as a read-only `mappingproxy`
- Using on instances of built-in types such as `int` or `list` (they have no __dict__)
- Assuming vars() returns all attributes (only instance attrs)
- Treating `vars()` inside a function as a live view: it is a snapshot, rebuilt on every call

## Related Functions

- **[dir()](dir.md)** - List all attributes (including inherited)
- **[getattr()](getattr.md)** - Get attribute value
- **[setattr()](setattr.md)** - Set attribute value
- **[delattr()](delattr.md)** - Delete attribute
- **[hasattr()](hasattr.md)** - Check attribute existence

## Version Notes

- **Python 3.13**: PEP 667: `vars()` in a function, like `locals()`, builds a fresh snapshot dict on every call, and builds it in O(n²) by looking each name up in the frame. Earlier versions fill the frame's one dict in O(n) and return it, so two snapshots taken in the same call are the same object and the earlier one shows the later values
- **All versions**: `vars(obj)` returns `obj.__dict__` itself, not a copy; a class's is a read-only `mappingproxy`
