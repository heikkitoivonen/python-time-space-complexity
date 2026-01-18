# property() Decorator Complexity

The `property()` decorator allows you to define custom getter, setter, and deleter methods for class attributes. It enables attribute-like access with custom logic.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Create property | O(1) | O(1) | Decorator application |
| Get value | O(1) | O(1) | Call getter function |
| Set value | O(1) | O(1) | Call setter function |
| Delete value | O(1) | O(1) | Call deleter function |
| Descriptor lookup | O(d) | O(1) | d = MRO depth |
| Total operation | O(d) | O(1) | MRO traversal may occur |

## Basic Usage

### Simple Getter

```python
# O(1) - define read-only property
class Circle:
    def __init__(self, radius):
        self._radius = radius
    
    @property
    def radius(self):
        """Get radius - O(1)"""
        return self._radius

# O(1) - access like attribute
circle = Circle(5)
r = circle.radius  # 5 (not a method call)

# Cannot set - read-only
# circle.radius = 10  # AttributeError
```

### Getter and Setter

```python
# O(1) - define read-write property
class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius
    
    @property
    def celsius(self):
        """Get temperature - O(1)"""
        return self._celsius
    
    @celsius.setter
    def celsius(self, value):
        """Set temperature - O(1)"""
        if value < -273.15:
            raise ValueError("Temperature below absolute zero")
        self._celsius = value

# O(1) - get and set
temp = Temperature(20)
print(temp.celsius)  # 20

temp.celsius = 25    # O(1) - calls setter
print(temp.celsius)  # 25
```

### Computed Property

```python
# O(1) - property computes value
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height
    
    @property
    def area(self):
        """Calculate area - O(1)"""
        return self.width * self.height

# O(1) - computed on access
rect = Rectangle(5, 10)
a = rect.area  # 50 (computed, not stored)

# Change dimensions
rect.width = 6
a = rect.area  # 60 (recomputed)
```

### Getter, Setter, and Deleter

```python
# O(1) - complete property control
class Data:
    def __init__(self):
        self._value = None
    
    @property
    def value(self):
        """Get value - O(1)"""
        print("Getting value")
        return self._value
    
    @value.setter
    def value(self, val):
        """Set value - O(1)"""
        print(f"Setting value to {val}")
        self._value = val
    
    @value.deleter
    def value(self):
        """Delete value - O(1)"""
        print("Deleting value")
        del self._value

# O(1) - use property
d = Data()
d.value = 42      # Prints: Setting value to 42
v = d.value       # Prints: Getting value, returns 42
del d.value       # Prints: Deleting value
```

## Complexity Details

### Descriptor Protocol

```python
# O(1) - property uses descriptor protocol
class WithProperty:
    @property
    def value(self):
        return 42

# When accessing:
# 1. Lookup 'value' in class dict - O(1)
# 2. Found descriptor (property object)
# 3. Call property.__get__() - O(1)
# 4. Calls getter function - O(1)

obj = WithProperty()
val = obj.value  # O(1)
```

### MRO Traversal

```python
# O(d) - inherited properties
class Parent:
    @property
    def value(self):
        return "parent"

class Child(Parent):
    pass

# O(d) - lookup via MRO
obj = Child()
val = obj.value  # O(d) - traverse MRO to find property
```

### Property Override

```python
# O(d) - child can override property
class Parent:
    @property
    def value(self):
        return "parent"

class Child(Parent):
    @property
    def value(self):
        return "child"

# O(d) - finds Child property first
parent_val = Parent().value  # "parent"
child_val = Child().value    # "child"
```

## Performance Patterns

### Property vs Direct Attribute

```python
# Direct attribute - O(1)
class Direct:
    def __init__(self):
        self.value = 42

# Property - O(1) + function call overhead
class WithProperty:
    def __init__(self):
        self._value = 42
    
    @property
    def value(self):
        return self._value

# Both O(1), but property has ~5% overhead
direct = Direct()
val1 = direct.value  # O(1)

with_prop = WithProperty()
val2 = with_prop.value  # O(1) + overhead
```

### Property vs Method Call

```python
# Method - O(1) with explicit call
class WithMethod:
    def __init__(self):
        self._value = 42
    
    def get_value(self):
        return self._value

# Property - O(1) with implicit call
class WithProperty:
    def __init__(self):
        self._value = 42
    
    @property
    def value(self):
        return self._value

# Both O(1), property looks cleaner
obj1 = WithMethod()
val1 = obj1.get_value()  # Explicit call

obj2 = WithProperty()
val2 = obj2.value  # Attribute access
```

### Caching in Properties

```python
# O(1) with caching - compute once
class Cached:
    def __init__(self):
        self._computed = None
    
    @property
    def value(self):
        """Compute once and cache - O(1)"""
        if self._computed is None:
            self._computed = expensive_computation()
        return self._computed
    
    def expensive_computation(self):
        # ... slow operation ...
        return 42

# vs recompute every time - O(f) where f = computation time
class NoCache:
    @property
    def value(self):
        """Recompute every time"""
        return expensive_computation()

# Caching significantly improves performance
```

## Common Use Cases

### Validation on Set

```python
# O(1) - validate input
class Person:
    def __init__(self, age):
        self._age = None
        self.age = age  # Calls setter
    
    @property
    def age(self):
        """Get age - O(1)"""
        return self._age
    
    @age.setter
    def age(self, value):
        """Set age with validation - O(1)"""
        if not isinstance(value, int) or value < 0:
            raise ValueError("Age must be non-negative integer")
        self._age = value

# O(1) - automatic validation
p = Person(30)
p.age = 35  # Valid

try:
    p.age = -5  # Invalid - raises ValueError
except ValueError as e:
    print(e)
```

### Computed Properties

```python
# O(1) - compute related value
class Distance:
    def __init__(self, kilometers):
        self.km = kilometers
    
    @property
    def miles(self):
        """Convert to miles - O(1)"""
        return self.km * 0.621371

# O(1) - accessed like attribute
d = Distance(10)
miles = d.miles  # 6.21371
```

### Lazy Loading

```python
# O(1) first access, O(n) computation
class Document:
    def __init__(self, filename):
        self.filename = filename
        self._content = None
    
    @property
    def content(self):
        """Load on first access - O(1) or O(n)"""
        if self._content is None:
            with open(self.filename) as f:
                self._content = f.read()  # O(n) - load file
        return self._content  # O(1) - return cached

# O(1) - first call loads file
# O(1) - subsequent calls return cached
doc = Document('large_file.txt')
text1 = doc.content  # O(n) - loads
text2 = doc.content  # O(1) - cached
```

### Read-Only Properties

```python
# O(1) - immutable attributes
class ImmutablePoint:
    def __init__(self, x, y):
        self._x = x
        self._y = y
    
    @property
    def x(self):
        """Get x - O(1), read-only"""
        return self._x
    
    @property
    def y(self):
        """Get y - O(1), read-only"""
        return self._y

# O(1) - get values
p = ImmutablePoint(1, 2)
x = p.x  # 1

# Cannot set - no setter defined
# p.x = 5  # AttributeError
```

### Type Conversion

```python
# O(1) - convert on access
class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius
    
    @property
    def celsius(self):
        """Get Celsius - O(1)"""
        return self._celsius
    
    @property
    def fahrenheit(self):
        """Get Fahrenheit - O(1)"""
        return self._celsius * 9/5 + 32
    
    @property
    def kelvin(self):
        """Get Kelvin - O(1)"""
        return self._celsius + 273.15

# O(1) - convert automatically
temp = Temperature(20)
c = temp.celsius      # 20
f = temp.fahrenheit   # 68.0
k = temp.kelvin       # 293.15
```

## Advanced Usage

### Property with Side Effects

```python
# O(1) - setter with side effects
class Volume:
    def __init__(self, value):
        self._value = value
        self.changed = False
    
    @property
    def value(self):
        """Get value - O(1)"""
        return self._value
    
    @value.setter
    def value(self, new_value):
        """Set value and track change - O(1)"""
        if new_value != self._value:
            self.changed = True
            self._value = new_value

# O(1) - track changes
vol = Volume(100)
vol.value = 150  # Sets changed = True
print(vol.changed)  # True
```

### Property Inheritance

```python
# O(d) - override property in subclass
class Parent:
    @property
    def name(self):
        return "Parent"

class Child(Parent):
    @property
    def name(self):
        return "Child"

# O(d) - finds correct property
parent = Parent()
child = Child()

print(parent.name)  # "Parent"
print(child.name)   # "Child"
```

### Dynamic Properties

```python
# O(1) - add properties dynamically
class Dynamic:
    def __init__(self):
        self._data = {}
    
    def add_property(self, name, getter, setter=None):
        """Add property dynamically - O(1)"""
        prop = property(getter, setter)
        setattr(self.__class__, name, prop)

# Create instance
obj = Dynamic()

# Add property dynamically
obj.add_property(
    'value',
    getter=lambda self: self._data.get('value', 0)
)

# Use property
obj.value = 42
```

## Practical Examples

### Account Balance with Limits

```python
# O(1) - property with validation and limits
class BankAccount:
    def __init__(self, initial_balance):
        self._balance = initial_balance
    
    @property
    def balance(self):
        """Get balance - O(1)"""
        return self._balance
    
    @balance.setter
    def balance(self, amount):
        """Set balance with validation - O(1)"""
        if amount < 0:
            raise ValueError("Balance cannot be negative")
        if amount > 1_000_000:
            raise ValueError("Balance exceeds limit")
        self._balance = amount
    
    @balance.deleter
    def balance(self):
        """Reset balance - O(1)"""
        self._balance = 0

# O(1) - use account
account = BankAccount(100)
print(account.balance)  # 100

account.balance = 500   # Valid
print(account.balance)  # 500

del account.balance     # Reset to 0
print(account.balance)  # 0
```

### Configuration Management

```python
# O(1) - validate configuration
class Config:
    def __init__(self):
        self._debug = False
        self._timeout = 30
    
    @property
    def debug(self):
        """Get debug flag - O(1)"""
        return self._debug
    
    @debug.setter
    def debug(self, value):
        """Set debug - O(1)"""
        if not isinstance(value, bool):
            raise TypeError("debug must be boolean")
        self._debug = value
    
    @property
    def timeout(self):
        """Get timeout - O(1)"""
        return self._timeout
    
    @timeout.setter
    def timeout(self, seconds):
        """Set timeout with bounds - O(1)"""
        if not (1 <= seconds <= 300):
            raise ValueError("timeout must be 1-300 seconds")
        self._timeout = seconds

# O(1) - validated configuration
config = Config()
config.debug = True
config.timeout = 60
```

### User Authentication

```python
# O(1) - property for authenticated user
class User:
    def __init__(self, username, password_hash):
        self.username = username
        self._password_hash = password_hash
        self._authenticated = False
    
    @property
    def authenticated(self):
        """Check authentication - O(1)"""
        return self._authenticated
    
    def authenticate(self, password):
        """Authenticate - O(1)"""
        import hashlib
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash == self._password_hash:
            self._authenticated = True
        return self._authenticated
    
    @authenticated.setter
    def authenticated(self, value):
        """Prevent direct setting - O(1)"""
        raise AttributeError("Cannot set authenticated directly")

# O(1) - use authentication
user = User("alice", "hash123")
is_auth = user.authenticated  # False

user.authenticate("mypassword")  # Authenticates if password matches
```

## Edge Cases

### Property Can't Have Same Name as __init__ Param

```python
# O(1) - attribute name matters
class Good:
    def __init__(self, value):
        self._value = value  # Different name
    
    @property
    def value(self):
        return self._value

# O(1) - works fine
obj = Good(42)
val = obj.value  # 42
```

### Deleter Without Setter

```python
# O(1) - can define deleter without setter
class OnlyDelete:
    def __init__(self):
        self.value = 42
    
    @property
    def value(self):
        return self._value if hasattr(self, '_value') else None
    
    @value.deleter
    def value(self):
        if hasattr(self, '_value'):
            del self._value

# O(1) - delete works
obj = OnlyDelete()
del obj.value
```

### Property on Module

```python
# O(1) - properties in classes, not modules
# (modules don't support property directly in Python 3.6+)

# But can be emulated with __getattr__
import sys

class ModuleProxy:
    def __init__(self, module):
        self.module = module
    
    @property
    def version(self):
        return "1.0.0"

# Access: ModuleProxy(sys).version
```

## Performance Considerations

### Avoiding Property Overhead

```python
# If performance critical, use direct attribute:
class Fast:
    def __init__(self):
        self.value = 42

# Slightly faster than property (no function call)
obj = Fast()
val = obj.value  # Very fast

# vs property (function call overhead)
class WithProperty:
    def __init__(self):
        self._value = 42
    
    @property
    def value(self):
        return self._value

# Overhead is minimal (~5%), only matters in extreme cases
```

### Caching Computed Properties

```python
# O(1) - cache expensive computation
class Cached:
    def __init__(self):
        self._cached_value = None
    
    @property
    def value(self):
        """Compute once - O(1) after first access"""
        if self._cached_value is None:
            self._cached_value = expensive_computation()
        return self._cached_value
    
    def expensive_computation(self):
        return sum(range(1_000_000))

# First access does computation, subsequent accesses are fast
```

## Best Practices

✅ **Do**:

- Use for read-only computed attributes
- Use to validate input in setters
- Use to implement lazy loading
- Use to provide clean attribute-like interface
- Document properties in docstrings
- Make getters fast (no I/O)

❌ **Avoid**:

- Complex logic in property methods (keep simple)
- I/O operations in getters (causes performance issues)
- Properties with unexpected side effects
- Using property when method is clearer
- Expensive computations without caching
- Hiding errors in property methods

## Related Functions

- **[classmethod()](classmethod.md)** - Decorator for class methods
- **[staticmethod()](staticmethod.md)** - Decorator for static methods
- **type()** - Get object type
- **[hasattr()](hasattr.md)** - Check attribute existence
- **[getattr()](getattr.md)** - Get attribute value

## Version Notes

- **Python 2.x**: `@property` available, same behavior
- **Python 3.x**: Same behavior, optimized in CPython
- **All versions**: Uses descriptor protocol for efficiency
