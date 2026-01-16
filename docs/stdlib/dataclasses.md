# dataclasses Module Complexity

The `dataclasses` module provides a decorator to automatically generate special methods for classes that are primarily used to store data.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `@dataclass` decorator | O(n) | O(n) | n = number of fields |
| Field access | O(1) | O(1) | Direct attribute access |
| `__init__()` | O(n) | O(n) | n = number of fields |
| `__repr__()` | O(n) | O(n) | n = number of fields |
| `__eq__()` | O(n) | O(1) | n = number of fields |
| `replace()` | O(n) | O(n) | Creates new instance |
| `asdict()` | O(n) | O(n) | n = fields + nested depth |
| `astuple()` | O(n) | O(n) | n = fields + nested depth |

## Basic Dataclass

### Simple Definition

```python
from dataclasses import dataclass

# Define dataclass - O(n) for n fields
@dataclass
class Point:
    x: float
    y: float

# Create instance - O(n)
p = Point(x=1.0, y=2.0)

# Access fields - O(1)
print(p.x, p.y)  # 1.0 2.0

# Automatic __repr__ - O(n)
print(p)         # Point(x=1.0, y=2.0)

# Automatic __eq__ - O(n)
p2 = Point(1.0, 2.0)
print(p == p2)   # True
```

### Default Values

```python
from dataclasses import dataclass

@dataclass
class Config:
    name: str
    timeout: int = 30
    retries: int = 3
    tags: list = None  # Mutable default

# Create with defaults - O(n)
config1 = Config("api")              # O(1)
config2 = Config("service", timeout=60)  # O(1)

# Access - O(1)
print(config1.timeout)  # 30
print(config2.timeout)  # 60
```

### Default Factory

```python
from dataclasses import dataclass, field

@dataclass
class Task:
    name: str
    tags: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

# Create with separate instances - O(n)
task1 = Task("task1")
task2 = Task("task2")

# Different lists for each - O(1) per instance
task1.tags.append("urgent")
print(task1.tags)  # ['urgent']
print(task2.tags)  # [] - separate list
```

## Dataclass Features

### Optional Fields

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Person:
    name: str
    age: int
    email: Optional[str] = None

# Create - O(n)
person1 = Person("Alice", 30)
person2 = Person("Bob", 25, "bob@example.com")

# Access - O(1)
print(person1.email)  # None
print(person2.email)  # bob@example.com
```

### Frozen Dataclasses

```python
from dataclasses import dataclass

# Immutable dataclass - O(n)
@dataclass(frozen=True)
class Point:
    x: float
    y: float

p = Point(1.0, 2.0)

# Access - O(1)
print(p.x)

# Modification raises error - O(1) check
try:
    p.x = 3.0
except FrozenInstanceError:
    print("Cannot modify frozen dataclass")
```

### Post-Init Processing

```python
from dataclasses import dataclass

@dataclass
class Circle:
    radius: float
    
    # Called after __init__ - O(1)
    def __post_init__(self):
        if self.radius <= 0:
            raise ValueError("Radius must be positive")
    
    # Method - O(1)
    def area(self):
        import math
        return math.pi * self.radius ** 2

# Create - O(n) including validation
circle = Circle(5.0)

# Use method - O(1)
print(circle.area())  # 78.5...
```

## Dataclass Utilities

### Replace - Create Modified Copy

```python
from dataclasses import dataclass, replace

@dataclass
class User:
    username: str
    email: str
    active: bool = True

# Create - O(n)
user1 = User("alice", "alice@example.com")

# Replace fields - O(n) creates new instance
user2 = replace(user1, email="alice.new@example.com")

# Original unchanged - O(1)
print(user1.email)  # alice@example.com
print(user2.email)  # alice.new@example.com
```

### Convert to Dictionary

```python
from dataclasses import dataclass, asdict

@dataclass
class Book:
    title: str
    author: str
    pages: int

# Create - O(n)
book = Book("Python Guide", "John Doe", 350)

# Convert to dict - O(n + m) where m = nested depth
book_dict = asdict(book)
# {'title': 'Python Guide', 'author': 'John Doe', 'pages': 350}

# Handle nested dataclasses - O(n*m)
@dataclass
class Library:
    name: str
    books: list  # List of Book objects

library = Library("Central", [book, book])
lib_dict = asdict(library)  # Recursively converts nested dataclasses
```

### Convert to Tuple

```python
from dataclasses import dataclass, astuple

@dataclass
class Point:
    x: float
    y: float
    z: float

# Create - O(n)
p = Point(1.0, 2.0, 3.0)

# Convert to tuple - O(n)
p_tuple = astuple(p)  # (1.0, 2.0, 3.0)

# Handles nested - O(n*m)
@dataclass
class Polygon:
    points: list  # List of Point objects

poly = Polygon([p, p, p])
poly_tuple = astuple(poly)  # Recursively converts
```

## Comparison and Hashing

### Equality Comparison

```python
from dataclasses import dataclass

@dataclass
class Product:
    sku: str
    price: float

# Create instances - O(n)
prod1 = Product("ABC123", 29.99)
prod2 = Product("ABC123", 29.99)
prod3 = Product("XYZ789", 15.99)

# Equality - O(n) compares all fields
print(prod1 == prod2)  # True
print(prod1 == prod3)  # False
```

### Order Comparison

```python
from dataclasses import dataclass

@dataclass(order=True)
class Student:
    name: str
    grade: float

# Create instances - O(n)
s1 = Student("Alice", 3.8)
s2 = Student("Bob", 3.5)

# Comparisons enabled - O(n) for all fields
print(s1 > s2)  # True (3.8 > 3.5)
print(s1 < s2)  # False
print(s1 >= s2) # True
```

### Hashable Dataclasses

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Coordinates:
    x: int
    y: int

# Create - O(n)
c1 = Coordinates(1, 2)
c2 = Coordinates(1, 2)

# Use in set - O(1) per operation
locations = {c1, c2}  # Set deduplicates
print(len(locations))  # 1

# Use as dict key - O(1) per operation
location_names = {c1: "start", c2: "origin"}
print(len(location_names))  # 1
```

## Advanced Patterns

### Inheritance

```python
from dataclasses import dataclass

@dataclass
class Animal:
    name: str
    age: int

@dataclass
class Dog(Animal):
    breed: str

# Create - O(n)
dog = Dog("Buddy", 3, "Golden Retriever")

# Access all fields - O(1)
print(dog.name, dog.age, dog.breed)  # Buddy 3 Golden Retriever
```

### Init-Only Fields

```python
from dataclasses import dataclass, field

@dataclass
class Temperature:
    celsius: float
    fahrenheit: float = field(init=False)
    
    def __post_init__(self):
        self.fahrenheit = self.celsius * 9/5 + 32

# Create - O(n)
temp = Temperature(25.0)

# Access - O(1)
print(temp.celsius)     # 25.0
print(temp.fahrenheit)  # 77.0
```

### Class Variables

```python
from dataclasses import dataclass

@dataclass
class Counter:
    count: int
    instances: int = 0  # Class variable, not a field
    
    def __post_init__(self):
        Counter.instances += 1

# Create - O(n)
c1 = Counter(1)
c2 = Counter(2)

# Access class variable - O(1)
print(Counter.instances)  # 2
```

## Comparison: Dataclass vs Alternatives

### vs Regular Class

```python
# Regular class
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __repr__(self):
        return f"Point(x={self.x}, y={self.y})"
    
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

# Dataclass - much cleaner, same performance
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float
```

### vs NamedTuple

```python
from collections import namedtuple
from dataclasses import dataclass

# NamedTuple - immutable, smaller memory
Point_NT = namedtuple('Point', ['x', 'y'])

# Dataclass - mutable, more flexible
@dataclass
class Point_DC:
    x: float
    y: float

# Performance: nearly identical
# Memory: namedtuple slightly smaller
# Flexibility: dataclass wins
```

### vs TypedDict

```python
from typing import TypedDict
from dataclasses import dataclass

# TypedDict - runtime type info, dict-like
class PointDict(TypedDict):
    x: float
    y: float

# Dataclass - object with attributes
@dataclass
class Point:
    x: float
    y: float

# Use cases:
# TypedDict: interop with JSON, dicts
# Dataclass: internal data structures
```

## Performance Notes

### Time Complexity
- **Decorator**: O(n) where n = number of fields
- **Field access**: O(1) (standard attribute lookup)
- **Comparison**: O(n) (all fields compared)
- **Conversion (asdict/astuple)**: O(n*m) where m = nesting depth

### Space Complexity
- **Instance**: O(n) for n fields
- **Replace/asdict**: O(n) for copy
- **Inheritance**: O(n) total fields from all classes

### CPython Implementation
- Uses `__slots__` for memory efficiency (optional)
- Caches method generation
- Zero runtime overhead vs hand-written classes

## Best Practices

### Use Dataclasses For
- Data containers with multiple fields
- Configuration objects
- API request/response models
- Simple immutable records (with frozen=True)

```python
from dataclasses import dataclass

@dataclass
class ApiRequest:
    method: str
    url: str
    headers: dict = None
    body: str = None
```

### Avoid When
- Need complex validation (use __init__)
- Frequent dynamic attributes
- Very simple single-field objects
- Performance critical lookups

## Related Documentation

- [Collections Module](collections.md)
- [Typing Module](typing.md)
- [Enum Module](enum.md)
