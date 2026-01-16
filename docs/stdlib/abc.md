# abc Module Complexity

The `abc` module provides infrastructure for defining abstract base classes (ABCs) in Python, enforcing that derived classes implement specified methods.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `@abstractmethod` decorator | O(1) | O(1) | Mark method abstract |
| Class instantiation attempt | O(n) | O(n) | n = abstract methods |
| `isinstance(obj, ABC)` | O(n) | O(1) | n = parent classes |
| `issubclass(cls, ABC)` | O(n) | O(1) | n = parent classes |
| Method resolution (MRO) | O(n) | O(n) | n = class hierarchy depth |
| Register virtual subclass | O(1) | O(n) | n = registered classes |

## Abstract Base Classes

### Basic Abstract Class

```python
from abc import ABC, abstractmethod

# Define abstract base class - O(1)
class Animal(ABC):
    
    # Mark as abstract - O(1)
    @abstractmethod
    def make_sound(self):
        """Subclasses must implement this"""
        pass
    
    # Concrete method in ABC - O(1)
    def sleep(self):
        return "Zzz..."

# Attempt instantiation - O(n) check for abstract methods
try:
    animal = Animal()  # TypeError
except TypeError as e:
    print("Cannot instantiate ABC")

# Concrete subclass - O(1)
class Dog(Animal):
    def make_sound(self):
        return "Woof!"

# Can instantiate concrete class - O(n)
dog = Dog()
print(dog.make_sound())  # Woof!
```

### Abstract Properties

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    
    # Abstract property - O(1)
    @property
    @abstractmethod
    def area(self):
        pass
    
    @property
    @abstractmethod
    def perimeter(self):
        pass

# Concrete implementation - O(1)
class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height
    
    @property
    def area(self):
        return self.width * self.height
    
    @property
    def perimeter(self):
        return 2 * (self.width + self.height)

# Create instance - O(n)
rect = Rectangle(5, 3)

# Access properties - O(1)
print(rect.area)       # 15
print(rect.perimeter)  # 16
```

### Abstract Class Methods

```python
from abc import ABC, abstractmethod

class DatabaseConnection(ABC):
    
    # Abstract class method - O(1)
    @classmethod
    @abstractmethod
    def from_config(cls, config):
        pass

class PostgresConnection(DatabaseConnection):
    @classmethod
    def from_config(cls, config):
        return cls(config['host'], config['port'])

# Use class method - O(1)
conn = PostgresConnection.from_config({'host': 'localhost', 'port': 5432})
```

### Abstract Static Methods

```python
from abc import ABC, abstractmethod

class Validator(ABC):
    
    # Abstract static method - O(1)
    @staticmethod
    @abstractmethod
    def validate(value):
        pass

class EmailValidator(Validator):
    @staticmethod
    def validate(value):
        return '@' in value

# Use static method - O(1)
is_valid = EmailValidator.validate("user@example.com")
```

## Multiple Abstract Methods

### Enforcing Multiple Implementations

```python
from abc import ABC, abstractmethod

class DataStore(ABC):
    
    # Multiple abstract methods - O(n) to enforce
    @abstractmethod
    def read(self, key):
        pass
    
    @abstractmethod
    def write(self, key, value):
        pass
    
    @abstractmethod
    def delete(self, key):
        pass

# Incomplete implementation - TypeError
class PartialStore(DataStore):
    def read(self, key):
        return None
    # Missing write() and delete()

try:
    store = PartialStore()  # O(n) - checks all 3 methods
except TypeError:
    print("Must implement all abstract methods")

# Complete implementation - O(1)
class MemoryStore(DataStore):
    def __init__(self):
        self.data = {}
    
    def read(self, key):
        return self.data.get(key)
    
    def write(self, key, value):
        self.data[key] = value
    
    def delete(self, key):
        del self.data[key]

# Create instance - O(n)
store = MemoryStore()
```

## Virtual Subclasses

### Register Virtual Subclass

```python
from abc import ABC, abstractmethod

class PluginInterface(ABC):
    @abstractmethod
    def execute(self):
        pass

# Existing class not inheriting from ABC
class LegacyPlugin:
    def execute(self):
        return "Legacy execution"

# Register as virtual subclass - O(1) per registration
PluginInterface.register(LegacyPlugin)

# Check relationship - O(n) against inheritance chain
obj = LegacyPlugin()
print(isinstance(obj, PluginInterface))   # True
print(issubclass(LegacyPlugin, PluginInterface))  # True
```

### Virtual Subclass Benefits

```python
from abc import ABC, abstractmethod

class Drawable(ABC):
    @abstractmethod
    def draw(self):
        pass

# Register multiple unrelated classes
class Circle:
    def draw(self):
        return "Drawing circle..."

class Rectangle:
    def draw(self):
        return "Drawing rectangle..."

# Register both - O(1) each
Drawable.register(Circle)
Drawable.register(Rectangle)

# Polymorphic usage - O(n) per check
def render(obj):
    if isinstance(obj, Drawable):
        return obj.draw()
    return "Not drawable"

# Works without inheritance
circle = Circle()
print(render(circle))  # Drawing circle...
```

## Inheritance Hierarchies

### Multi-Level Inheritance

```python
from abc import ABC, abstractmethod

# Level 1 - Abstract base
class Vehicle(ABC):
    @abstractmethod
    def start(self):
        pass

# Level 2 - Intermediate abstract
class Car(Vehicle):
    @abstractmethod
    def open_trunk(self):
        pass

# Level 3 - Concrete implementation
class Sedan(Car):
    def start(self):
        return "Engine running"
    
    def open_trunk(self):
        return "Trunk opened"

# Create instance - O(n) checks hierarchy
sedan = Sedan()
print(sedan.start())        # Engine running
print(sedan.open_trunk())   # Trunk opened
```

### Mixin with Abstract Base

```python
from abc import ABC, abstractmethod

class Logger:
    """Mixin - not abstract"""
    def log(self, message):
        return f"LOG: {message}"

class Serializable(ABC):
    """Abstract mixin"""
    @abstractmethod
    def to_dict(self):
        pass

class User(Logger, Serializable):
    def __init__(self, name, email):
        self.name = name
        self.email = email
    
    def to_dict(self):
        return {'name': self.name, 'email': self.email}

# Create instance - O(n)
user = User("Alice", "alice@example.com")

# Use mixin methods - O(1)
print(user.log("User created"))     # LOG: User created
print(user.to_dict())               # {'name': 'Alice', ...}
```

## Common Patterns

### Factory Pattern with ABC

```python
from abc import ABC, abstractmethod

class Driver(ABC):
    @abstractmethod
    def connect(self):
        pass

class PostgresDriver(Driver):
    def connect(self):
        return "Connected to PostgreSQL"

class MySQLDriver(Driver):
    def connect(self):
        return "Connected to MySQL"

class DriverFactory:
    # O(1) factory lookup
    @staticmethod
    def create_driver(db_type):
        drivers = {
            'postgres': PostgresDriver,
            'mysql': MySQLDriver
        }
        driver_class = drivers.get(db_type)
        if driver_class:
            return driver_class()
        raise ValueError(f"Unknown driver: {db_type}")

# Use factory - O(1)
driver = DriverFactory.create_driver('postgres')
print(driver.connect())  # Connected to PostgreSQL
```

### Template Method Pattern

```python
from abc import ABC, abstractmethod

class DataProcessor(ABC):
    
    # Template method - defines algorithm structure
    def process(self, data):
        validated = self.validate(data)  # O(?)
        transformed = self.transform(validated)  # O(?)
        return self.save(transformed)  # O(?)
    
    @abstractmethod
    def validate(self, data):
        pass
    
    @abstractmethod
    def transform(self, data):
        pass
    
    @abstractmethod
    def save(self, data):
        pass

class CSVProcessor(DataProcessor):
    def validate(self, data):
        return len(data) > 0
    
    def transform(self, data):
        return data.upper()
    
    def save(self, data):
        return f"Saved CSV: {data}"

# Use - O(?) based on implementation
processor = CSVProcessor()
result = processor.process("csv data")
```

## Checking Implementation

### Verification Methods

```python
from abc import ABC, abstractmethod

class Interface(ABC):
    @abstractmethod
    def required_method(self):
        pass

class Implementation(Interface):
    def required_method(self):
        return "Implemented"

# Check if subclass - O(n)
print(issubclass(Implementation, Interface))  # True

# Check if instance - O(n)
obj = Implementation()
print(isinstance(obj, Interface))  # True

# Check abstract methods - O(n) to compute set
abstract_methods = Interface.__abstractmethods__
print(abstract_methods)  # frozenset({'required_method'})
```

## Performance Considerations

### Instantiation Cost

```python
from abc import ABC, abstractmethod
import time

class AbstractBase(ABC):
    @abstractmethod
    def method(self):
        pass

class Concrete(AbstractBase):
    def method(self):
        return None

# Instantiation checks abstracts - O(n)
start = time.time()
for _ in range(100000):
    obj = Concrete()
elapsed = time.time() - start

# Cost is O(1) per instance, n checks at class definition time
```

### Virtual Subclass Lookups

```python
from abc import ABC

class MyABC(ABC):
    pass

# Register many - O(k) total for k registrations
for i in range(1000):
    class DummyClass:
        pass
    MyABC.register(DummyClass)

# isinstance checks - O(n) in worst case
class TestClass:
    pass
MyABC.register(TestClass)

# Check - O(n) through registered classes
result = isinstance(TestClass(), MyABC)
```

## Best Practices

### Do's
- Use ABC for interface definition
- Clearly document abstract methods
- Use `@abstractmethod` consistently
- Provide concrete implementations in subclasses

```python
from abc import ABC, abstractmethod

class Cache(ABC):
    """Cache interface for different backends"""
    
    @abstractmethod
    def get(self, key):
        """Retrieve value by key"""
        pass
    
    @abstractmethod
    def set(self, key, value):
        """Store key-value pair"""
        pass
```

### Avoid's
- Don't create ABCs for single-use classes
- Don't use virtual registration excessively
- Don't override abstract methods to remove implementation
- Don't use ABC when simple inheritance suffices

## Related Documentation

- [Enum Module](enum.md)
- [Collections Module](collections.md)
- [Typing Module](typing.md)
