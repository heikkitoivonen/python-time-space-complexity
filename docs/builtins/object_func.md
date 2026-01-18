# object() Function Complexity

The `object()` function creates the base object instance. It's the root of Python's object hierarchy.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Create object | O(1) | O(1) | Base instance |
| Attribute access | O(1) | O(1) | Default behavior |
| Subclassing | O(1) | O(1) | Class creation |
| Instance creation | O(1) | O(k) | k = __init__ cost |

## Basic Usage

### Create Base Object

```python
# O(1) - create root object instance
obj = object()
# <object object at 0x...>
```

### Object Type

```python
# O(1) - all objects inherit from object
type(obj)  # <class 'object'>

# Check inheritance
isinstance(obj, object)  # True - all objects are objects
```

### Basic Attributes

```python
# O(1) - object has minimal attributes
obj = object()

# __class__ - type of object
obj.__class__  # <class 'object'>

# __doc__ - documentation
obj.__doc__  # "The base class of the class hierarchy."

# __hash__ - can be hashed
hash(obj)  # O(1)
```

## Complexity Details

### Object Creation

```python
# O(1) - instant creation, minimal overhead
obj1 = object()  # O(1)
obj2 = object()  # O(1)

# Each call creates distinct instance
obj1 is obj2  # False - different objects
id(obj1) != id(obj2)  # Different memory addresses
```

### Inheritance

```python
# O(1) - all classes implicitly inherit from object
class MyClass:
    pass

obj = MyClass()  # O(1) - inherits from object

# Explicitly inherit
class MyClass(object):
    pass

obj = MyClass()  # O(1) - same behavior
```

### Method Resolution Order

```python
# O(1) - check MRO
class Base:
    pass

class Derived(Base):
    pass

# MRO lookup
Derived.__mro__  # (Derived, Base, object)

# object is always last
```

## Common Patterns

### Base Class for Shared Behavior

```python
# O(1) - create base class
class Entity(object):
    def __init__(self, name):
        self.name = name  # O(1)
    
    def __str__(self):  # O(1)
        return f"Entity({self.name})"

# All subclasses inherit from object
class Person(Entity):
    pass

p = Person("Alice")  # O(1)
```

### Duck Typing

```python
# O(1) - leverage object interface
def describe(obj):
    # Works with any object
    return f"Type: {type(obj).__name__}, ID: {id(obj)}"

obj1 = object()
obj2 = "string"
obj3 = [1, 2, 3]

# All O(1) - all work with any object
describe(obj1)  # "Type: object, ID: ..."
describe(obj2)  # "Type: str, ID: ..."
describe(obj3)  # "Type: list, ID: ..."
```

### Identity vs Equality

```python
# O(1) - both operations
obj = object()
obj2 = object()

# Identity - is (checks same object)
obj is obj  # True - O(1)
obj is obj2  # False - O(1)

# Equality - == (default checks identity)
obj == obj  # True - O(1)
obj == obj2  # False - O(1) for base object
```

## Practical Examples

### Sentinel Value

```python
# O(1) - use object as unique sentinel
_MISSING = object()  # Unique marker

def get_value(d, key):
    result = d.get(key, _MISSING)
    if result is _MISSING:
        # Handle missing case
        return None
    return result

data = {'a': 1, 'b': 2}
get_value(data, 'a')  # 1
get_value(data, 'c')  # None
```

### Default Instance

```python
# O(1) - use object as default
def process(config=None):
    if config is None:
        config = object()  # Default
    
    # Process with config
    return config

result = process()  # Uses default object
```

### Type Checking

```python
# O(1) - check if something is an object (everything is)
def is_object(x):
    return isinstance(x, object)

is_object(42)           # True - all things
is_object("string")     # True
is_object([1, 2])       # True
is_object(object())     # True
```

## Object Interface

```python
# O(1) - common object methods/attributes
obj = object()

# Type
type(obj)              # <class 'object'>

# Identity
id(obj)                # Memory address - O(1)

# Representation
str(obj)               # '<object object at 0x...>'
repr(obj)              # '<object object at 0x...>'

# Hashing
hash(obj)              # O(1) - based on id

# Class
obj.__class__          # <class 'object'>

# Documentation
obj.__doc__            # String
```

## Class Creation

```python
# O(1) - define custom classes
class CustomClass(object):
    """A custom class."""
    
    def __init__(self, value):
        self.value = value  # O(1)
    
    def __str__(self):
        return f"Custom({self.value})"

# Create instance
obj = CustomClass(42)  # O(1) - __init__ is O(1)
```

## Multiple Inheritance

```python
# O(1) - object at end of MRO
class A(object):
    pass

class B(object):
    pass

class C(A, B):  # Multiple inheritance
    pass

C.__mro__  # (C, A, B, object)
# object is always last
```

## Attribute Access

```python
# O(1) - default attribute behavior
obj = object()

# Can't add attributes to base object
try:
    obj.name = "test"  # AttributeError
except AttributeError:
    pass

# But custom classes can
class Custom:
    pass

c = Custom()
c.name = "test"  # O(1) - works
```

## Edge Cases

### Singleton Pattern

```python
# O(1) - object() returns different instances
obj1 = object()
obj2 = object()

obj1 is obj2  # False - different instances

# Use object() for sentinel (unique identity)
NONE_SENTINEL = object()
EMPTY_SENTINEL = object()

# Each is unique
NONE_SENTINEL is EMPTY_SENTINEL  # False
```

### Identity Checking

```python
# O(1) - very fast identity check
obj = object()

# Identity with 'is' is fastest
obj is obj  # O(1) - just memory address comparison

# Equality with == (default is same as 'is' for object)
obj == obj  # O(1) - calls __eq__

# Hashing
hash(obj)  # O(1) - based on id
```

### Inheritance Chain

```python
# O(1) - traverse inheritance
class Root(object):
    pass

class Middle(Root):
    pass

class Leaf(Middle):
    pass

obj = Leaf()

# Check if object
isinstance(obj, object)  # True - O(1)

# Walk up MRO
Leaf.__mro__  # (Leaf, Middle, Root, object)
```

## Comparison with type

```python
# object - base class
# type - metaclass (creates classes)

obj = object()
MyClass = type('MyClass', (), {})  # Create class dynamically

type(obj)       # <class 'object'>
type(MyClass)   # <class 'type'>

# All classes are instances of type
# All instances are instances of object
```

## Best Practices

✅ **Do**:

- Inherit from object explicitly for clarity (Python 2 compatibility)
- Use object() for sentinel values
- Rely on object's default behavior
- Check isinstance(x, object) for type checking

❌ **Avoid**:

- Creating instances of object() for storage (use custom classes)
- Trying to add attributes to object() instances
- Assuming object() instances have special behavior
- Overriding object methods unless necessary

## Related Functions

- **type()** - Get or create types
- **[isinstance()](isinstance.md)** - Check instance type
- **[id()](id.md)** - Get object identity

## Version Notes

- **Python 2.x**: New-style classes inherit from object (old-style don't)
- **Python 3.x**: All classes implicitly inherit from object
- **All versions**: object() is the root of the hierarchy
