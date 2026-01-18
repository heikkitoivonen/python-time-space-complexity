# super() Function Complexity

The `super()` function provides access to methods in a parent or sibling class in a multiple inheritance hierarchy. It's essential for calling parent class methods and implementing cooperative multiple inheritance.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Lookup in MRO | O(d) | O(1) | d = MRO depth; MRO is cached |
| Bind method | O(1) | O(1) | Create bound method |
| Call parent method | O(1) | O(1) | Method invocation |
| MRO resolution | O(d) | O(d) | d = inheritance depth |
| Total operation | O(d) | O(d) | May traverse full MRO |

## Basic Usage

### Call Parent Constructor

```python
# O(d) - initialize parent class
class Parent:
    def __init__(self, name):
        self.name = name

class Child(Parent):
    def __init__(self, name, age):
        super().__init__(name)  # O(d) - call parent __init__
        self.age = age

# O(d) - create instance
child = Child("Alice", 30)
print(child.name, child.age)  # Alice 30
```

### Call Parent Method

```python
# O(d) - override method but call parent
class Parent:
    def greet(self):
        return "Hello from Parent"

class Child(Parent):
    def greet(self):
        parent_greeting = super().greet()  # O(d)
        return f"{parent_greeting}, Child"

# O(d) - call overridden method
child = Child()
print(child.greet())  # Hello from Parent, Child
```

### Multiple Inheritance

```python
# O(d) - resolve method order with MRO
class A:
    def method(self):
        return "A"

class B(A):
    def method(self):
        return f"{super().method()} -> B"

class C(A):
    def method(self):
        return f"{super().method()} -> C"

class D(B, C):
    def method(self):
        return f"{super().method()} -> D"

# O(d) - follows C3 MRO linearization
d = D()
print(d.method())  # A -> C -> B -> D
```

## Complexity Details

### Method Resolution Order (MRO)

```python
# O(d) - super() uses MRO to find next method
class A:
    def method(self):
        return "A"

class B(A):
    def method(self):
        # MRO: [B, A, object]
        # super() finds next in line after B
        return f"{super().method()} + B"

obj = B()
result = obj.method()  # O(d) - lookup takes O(d) time

# Display MRO
print(B.__mro__)  # (<class 'B'>, <class 'A'>, <class 'object'>)
```

### C3 Linearization

```python
# O(d) - complex MRO computation
class A:
    pass

class B(A):
    pass

class C(A):
    pass

class D(B, C):
    pass

# MRO computed at class creation: O(n log n) where n = classes
# But lookup at runtime: O(d) where d = MRO depth
mro = D.__mro__  # [D, B, C, A, object]

# super() traverses this in O(d) time
```

### super() with Explicit Arguments

```python
# O(1) - explicit form (rarely used)
class Parent:
    def method(self):
        return "parent"

class Child(Parent):
    def method(self):
        # Both forms are O(d):
        # 1. Implicit: super().method()
        # 2. Explicit: super(Child, self).method()
        return super(Child, self).method()

# O(d) - both have same complexity
child = Child()
result = child.method()
```

## Performance Patterns

### super() Overhead

```python
# Direct parent call - O(1)
class Parent:
    def method(self):
        return 42

class Child(Parent):
    def method(self):
        return Parent.method(self)  # O(1) - direct reference

# super() - O(d)
class WithSuper(Parent):
    def method(self):
        return super().method()  # O(d) - MRO lookup

# Direct parent call is ~10% faster but inflexible
# super() is slower but essential for multiple inheritance
```

### vs Explicit Parent Name

```python
# Explicit parent - O(1) hardcoded
class Parent:
    def setup(self):
        self.ready = True

class Child(Parent):
    def setup(self):
        Parent.setup(self)  # O(1) - hardcoded
        self.extra = "data"

# vs super() - O(d) flexible
class BetterChild(Parent):
    def setup(self):
        super().setup()  # O(d) - works with inheritance
        self.extra = "data"

# For single inheritance, little difference
# For multiple inheritance, super() is necessary
```

### Cooperative Multiple Inheritance

```python
# O(d) - cooperative pattern with super()
class Mixin1:
    def process(self):
        print("Mixin1")
        super().process()  # O(d) - find next in MRO

class Mixin2:
    def process(self):
        print("Mixin2")
        super().process()  # O(d)

class Base:
    def process(self):
        print("Base")

class Combined(Mixin1, Mixin2, Base):
    pass

# O(d) - calls in MRO order
obj = Combined()
obj.process()
# Output: Mixin1, Mixin2, Base

# MRO: [Combined, Mixin1, Mixin2, Base, object]
```

## Common Use Cases

### Initializing Parent Classes

```python
# O(d) - initialize entire hierarchy
class Vehicle:
    def __init__(self, color):
        self.color = color

class Engine:
    def __init__(self, power):
        self.power = power

class Car(Vehicle, Engine):
    def __init__(self, color, power, brand):
        super().__init__(color)  # O(d) - initialize Vehicle
        Engine.__init__(self, power)  # O(d) - initialize Engine
        self.brand = brand

# O(d) - initialization
car = Car("red", 150, "Toyota")
print(car.color, car.power, car.brand)  # red 150 Toyota
```

### Method Chaining

```python
# O(d) - method chaining through hierarchy
class BaseLogger:
    def log(self, message):
        print(f"[LOG] {message}")

class TimestampLogger(BaseLogger):
    def log(self, message):
        import datetime
        timestamp = datetime.datetime.now()
        print(f"[{timestamp}] {message}")
        super().log(message)  # O(d) - call parent

class FileLogger(TimestampLogger):
    def log(self, message):
        with open('log.txt', 'a') as f:
            f.write(message + '\n')
        super().log(message)  # O(d) - call parent chain

# O(d) - logs through entire chain
logger = FileLogger()
logger.log("test")
```

### Mixin Pattern

```python
# O(d) - mixin classes extend functionality
class JSONMixin:
    def to_json(self):
        """Convert to JSON - O(1)"""
        import json
        return json.dumps(self.__dict__)
    
    def from_json(self, json_str):
        """Load from JSON - O(1)"""
        import json
        data = json.loads(json_str)
        self.__dict__.update(data)

class ValidationMixin:
    def validate(self):
        """Validate state - O(n)"""
        for key, value in self.__dict__.items():
            if value is None:
                raise ValueError(f"{key} cannot be None")

class User(ValidationMixin, JSONMixin):
    def __init__(self, name, email):
        self.name = name
        self.email = email

# O(1) - use mixins
user = User("Alice", "alice@example.com")
json_str = user.to_json()
user.validate()
```

### Context Manager Inheritance

```python
# O(d) - proper cleanup through inheritance
class BaseContext:
    def __enter__(self):
        print("Opening base")
        return self
    
    def __exit__(self, *args):
        print("Closing base")

class LoggingContext(BaseContext):
    def __enter__(self):
        print("Opening logger")
        super().__enter__()  # O(d)
        return self
    
    def __exit__(self, *args):
        print("Closing logger")
        super().__exit__(*args)  # O(d)

# O(d) - proper cleanup order
with LoggingContext() as ctx:
    print("Working")
# Output:
# Opening logger
# Opening base
# Working
# Closing logger
# Closing base
```

## Advanced Usage

### super() in Multiple Inheritance

```python
# O(d) - complex MRO resolution
class A:
    def method(self):
        return "A"

class B(A):
    def method(self):
        return f"{super().method()} -> B"

class C(A):
    def method(self):
        return f"{super().method()} -> C"

class D(B, C):
    def method(self):
        return f"{super().method()} -> D"

# O(d) - follows MRO: [D, B, C, A, object]
d = D()
print(d.method())  # A -> C -> B -> D
```

### Diamond Inheritance

```python
# O(d) - handle diamond pattern
class Root:
    def __init__(self):
        print("Root init")

class Left(Root):
    def __init__(self):
        print("Left init")
        super().__init__()  # O(d)

class Right(Root):
    def __init__(self):
        print("Right init")
        super().__init__()  # O(d)

class Diamond(Left, Right):
    def __init__(self):
        print("Diamond init")
        super().__init__()  # O(d)

# O(d) - Root initialized only once!
d = Diamond()
# Output:
# Diamond init
# Left init
# Right init
# Root init
```

### Property Override

```python
# O(d) - override property with super()
class Parent:
    @property
    def value(self):
        return self._value if hasattr(self, '_value') else 0
    
    @value.setter
    def value(self, val):
        self._value = val

class Child(Parent):
    @property
    def value(self):
        """Override with validation - O(d)"""
        return super().value  # O(d) - get parent property
    
    @value.setter
    def value(self, val):
        """Override with validation - O(1)"""
        if val < 0:
            raise ValueError("Value must be non-negative")
        super(Child, self.__class__).value.fset(self, val)

# O(d) - validated property
child = Child()
child.value = 10  # Valid
# child.value = -5  # Raises ValueError
```

## Practical Examples

### Plugin System with super()

```python
# O(d) - plugin base class with hooks
class PluginBase:
    def initialize(self):
        """Initialize plugin - O(1)"""
        print("Base initialized")
    
    def process(self, data):
        """Process data - O(1)"""
        print(f"Base processing: {data}")
    
    def cleanup(self):
        """Cleanup - O(1)"""
        print("Base cleanup")

class CachingPlugin(PluginBase):
    def __init__(self):
        self.cache = {}
    
    def process(self, data):
        """Add caching - O(1)"""
        if data not in self.cache:
            super().process(data)  # O(d)
            self.cache[data] = True
        else:
            print(f"Cache hit: {data}")

class LoggingPlugin(PluginBase):
    def process(self, data):
        """Add logging - O(1)"""
        print(f"Processing: {data}")
        super().process(data)  # O(d)

class EnhancedPlugin(CachingPlugin, LoggingPlugin, PluginBase):
    pass

# O(d) - chain of responsibility
plugin = EnhancedPlugin()
plugin.process("test")
```

### Schema Validation

```python
# O(n) - validate with parent validation
class BaseValidator:
    def validate(self, data):
        """Base validation - O(n)"""
        if not isinstance(data, dict):
            raise TypeError("Must be dict")
        return True

class SchemaValidator(BaseValidator):
    def __init__(self, schema):
        self.schema = schema
    
    def validate(self, data):
        """Validate schema - O(n)"""
        super().validate(data)  # O(d) - check base
        
        for key, required in self.schema.items():
            if required and key not in data:
                raise ValueError(f"Missing {key}")
        
        return True

class TypeValidator(SchemaValidator):
    def __init__(self, schema, types):
        super().__init__(schema)  # O(d)
        self.types = types
    
    def validate(self, data):
        """Type check - O(n)"""
        super().validate(data)  # O(d) - check schema
        
        for key, expected_type in self.types.items():
            if key in data and not isinstance(data[key], expected_type):
                raise TypeError(f"{key} must be {expected_type}")
        
        return True

# O(n) - full validation chain
schema = {'name': True, 'age': False}
types = {'name': str, 'age': int}
validator = TypeValidator(schema, types)

validator.validate({'name': 'Alice', 'age': 30})  # Valid
```

### Serialization with Inheritance

```python
# O(n) - serialize entire hierarchy
class Serializable:
    def to_dict(self):
        """Get representation - O(n)"""
        return vars(self)

class Timestamped(Serializable):
    def __init__(self):
        import datetime
        self.created = datetime.datetime.now().isoformat()
    
    def to_dict(self):
        """Include timestamp - O(n)"""
        data = super().to_dict()  # O(d)
        return data

class Versioned(Timestamped):
    def __init__(self, version='1.0'):
        super().__init__()  # O(d) - initialize parent
        self.version = version
    
    def to_dict(self):
        """Include version - O(n)"""
        data = super().to_dict()  # O(d)
        data['version'] = self.version
        return data

# O(n) - serialize with all data
obj = Versioned()
print(obj.to_dict())
```

## Edge Cases

### super() Without Arguments

```python
# O(d) - implicit form (Python 3+)
class Parent:
    def method(self):
        return "parent"

class Child(Parent):
    def method(self):
        # Python 3 implicit form
        return super().method()  # O(d) - works in methods
    
    @classmethod
    def class_method(cls):
        # Also works in classmethods
        return super().method(None)  # O(d)
    
    @staticmethod
    def static_method():
        # Cannot use super() here - no class context
        return Parent.method(None)

# Implicit form only works inside class methods
```

### super() with Objects Without __init__

```python
# O(d) - parent may not have __init__
class Base:
    pass  # No __init__

class Child(Base):
    def __init__(self, value):
        super().__init__()  # O(d) - safe even if parent has no __init__
        self.value = value

# O(d) - works safely
child = Child(42)
```

### super() in __del__

```python
# O(d) - cleanup through inheritance
class Parent:
    def __del__(self):
        print("Parent cleanup")

class Child(Parent):
    def __del__(self):
        print("Child cleanup")
        super().__del__()  # O(d) - call parent cleanup

# O(d) - cleanup order
obj = Child()
del obj  # Prints: Child cleanup, Parent cleanup
```

## Performance Considerations

### Caching MRO Results

```python
# O(d) - MRO computation happens once
class Base:
    pass

class Derived(Base):
    pass

# MRO computed at class definition: O(n log n)
# Stored in __mro__ tuple
mro = Derived.__mro__  # O(1) - cached

# super() lookups use cached MRO: O(d)
```

### Avoiding super() in Hot Paths

```python
# Direct parent call - faster in performance-critical code
class Parent:
    def compute(self, x):
        return x * 2

class Child(Parent):
    def compute(self, x):
        # For single inheritance in tight loops:
        result = Parent.compute(self, x)  # O(1) - slightly faster
        
        # vs
        # result = super().compute(x)  # O(d)
        
        return result

# Difference is small (~5%) but matters in hot paths
```

## Best Practices

✅ **Do**:

- Use `super()` for parent method calls
- Use in cooperative multiple inheritance
- Use in mixins and plugin systems
- Keep parent calls near the top of __init__
- Use implicit form in Python 3 (no arguments)
- Document MRO in complex hierarchies

❌ **Avoid**:

- Mixing `super()` and explicit parent calls
- Forgetting to call `super()` in __init__
- Deep inheritance chains (limit to 3-4 levels)
- Circular dependencies in super() chains
- Complex logic in methods using super()
- Using super() outside class methods (requires arguments)

## Related Functions

- **[classmethod()](classmethod.md)** - Decorator for class methods
- **type()** - Get object type
- **[isinstance()](isinstance.md)** - Check instance type
- **[issubclass()](issubclass.md)** - Check class hierarchy
- **[__mro__](https://docs.python.org/3/library/stdtypes.html#class.__mro__)** - Method resolution order

## Version Notes

- **Python 2.x**: `super()` requires arguments: `super(ClassName, self)`
- **Python 3.x**: Implicit form `super()` automatically finds class and self
- **All versions**: Uses MRO for method resolution
- **Python 3.6+**: super() is optimized for performance
