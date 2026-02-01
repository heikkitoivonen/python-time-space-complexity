# type() Function

The `type()` function returns the type of an object or creates a new type (class) dynamically.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `type(obj)` | O(1) | O(1) | Get object type |
| `type(name, bases, dict)` | O(n) | O(n) | Create class, n = dict size |

## Getting Object Type

### Basic Type Checking - Time: O(1)

```python
# Get type of object - O(1)
print(type(42))           # <class 'int'>
print(type("hello"))      # <class 'str'>
print(type([1, 2, 3]))    # <class 'list'>
print(type({'a': 1}))     # <class 'dict'>
print(type(True))         # <class 'bool'>
```

### Comparing Types

```python
value = 42

# Check type - O(1)
if type(value) == int:
    print("Is integer")

if type(value) is int:  # Preferred
    print("Is integer")

# Use isinstance() for subclass checking - O(1)
if isinstance(value, (int, float)):
    print("Is number")
```

### Type of Classes

```python
class MyClass:
    pass

obj = MyClass()

# Type of instance - O(1)
print(type(obj))  # <class '__main__.MyClass'>

# Type of class - O(1)
print(type(MyClass))  # <class 'type'>

# Get class from instance - O(1)
cls = type(obj)
print(cls.__name__)  # 'MyClass'
```

## Creating Classes Dynamically

### Type Constructor - Time: O(n) where n = attributes

```python
# Create class dynamically - O(n)
# type(name, bases, dict)

# Equivalent to:
# class MyClass:
#     x = 10
#     def method(self): return self.x

MyClass = type('MyClass', (), {
    'x': 10,
    'method': lambda self: self.x
})

obj = MyClass()
print(obj.x)        # 10
print(obj.method()) # 10
```

### Dynamic Class with Methods

```python
# Create class with methods - O(n)
def __init__(self, name):
    self.name = name

def greet(self):
    return f"Hello, {self.name}"

Person = type('Person', (), {
    '__init__': __init__,
    'greet': greet
})

p = Person("Alice")
print(p.greet())  # Hello, Alice
```

### Class with Inheritance

```python
# Create class with base - O(n)
class Base:
    def base_method(self):
        return "from base"

Derived = type('Derived', (Base,), {
    'derived_method': lambda self: "from derived"
})

obj = Derived()
print(obj.base_method())     # from base
print(obj.derived_method())  # from derived
```

## Practical Examples

### Introspection

```python
class MyClass:
    def method(self):
        pass

obj = MyClass()

# Get type information - O(1)
print(f"Type: {type(obj)}")
print(f"Name: {type(obj).__name__}")
print(f"Module: {type(obj).__module__}")
print(f"Bases: {type(obj).__bases__}")

# List attributes - O(n)
print(f"Dict: {type(obj).__dict__}")
```

### Type Conversion Check

```python
def process(value):
    # Check type and convert - O(1)
    if type(value) is str:
        return value.upper()
    elif type(value) is int:
        return value * 2
    elif type(value) is list:
        return len(value)
    else:
        raise TypeError(f"Unsupported type: {type(value)}")

print(process("hello"))    # HELLO
print(process(21))         # 42
print(process([1, 2, 3]))  # 3
```

### Dynamic Attribute Access

```python
# Get type and access attributes - O(1)
def get_info(obj):
    obj_type = type(obj)
    
    return {
        'type_name': obj_type.__name__,
        'module': obj_type.__module__,
        'dict': obj_type.__dict__,
        'mro': obj_type.__mro__  # Method resolution order
    }

info = get_info([1, 2, 3])
print(info['type_name'])  # 'list'
```

## type() vs isinstance()

```python
# type() - exact type match - O(1)
if type(value) is int:
    print("Exact integer")

# isinstance() - checks subclass too - O(1)
if isinstance(value, int):
    print("Integer or subclass")

# isinstance() preferred for most cases
class MyInt(int):
    pass

val = MyInt(5)

print(type(val) is int)       # False
print(isinstance(val, int))   # True (preferred)
```

## Metaclasses

### Using type as Metaclass

```python
# type is the metaclass of all classes
class MyMeta(type):
    def __new__(mcs, name, bases, namespace):
        print(f"Creating class {name}")
        return super().__new__(mcs, name, bases, namespace)

# Create class with metaclass - O(n)
MyClass = MyMeta('MyClass', (), {})
# Output: Creating class MyClass
```

## Best Practices

```python
# ✅ DO: Use isinstance() for type checking
if isinstance(value, (int, float)):
    print("Is number")

# ✅ DO: Use type() for exact type match when needed
if type(value) is int:
    print("Exactly int, not subclass")

# ✅ DO: Use __class__ for more specific type
print(obj.__class__.__name__)

# ❌ DON'T: Use type() for isinstance() purposes
if type(value) == int:
    print("Doesn't check subclasses")

# ❌ DON'T: Compare types with ==, use 'is'
if type(value) == int:  # Works but less preferred
    pass
if type(value) is int:  # Preferred
    pass
```

## Related Functions

- [isinstance() Function](isinstance.md) - Type checking with inheritance
- [issubclass() Function](issubclass.md) - Subclass checking
- [dir() Function](dir.md) - List attributes
- [vars() Function](vars.md) - Get __dict__

## Further Reading

- [CPython Internals: type](https://zpoint.github.io/CPython-Internals/BasicObject/type/type.html) -
  Deep dive into CPython's type implementation
