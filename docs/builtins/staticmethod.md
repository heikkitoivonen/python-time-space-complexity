# staticmethod() Decorator Complexity

The `staticmethod()` decorator modifies a function to remove the automatic binding of the first argument. Static methods are like regular functions but belong to a class namespace.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Create descriptor | O(1) | O(1) | Decorator application |
| Call static method | O(1) | O(1) | Access method on class |
| Call on instance | O(1) | O(1) | Access method on instance |
| MRO lookup | O(d) | O(1) | d = inheritance depth |
| Total operation | O(d) | O(1) | Lookup may traverse MRO |

## Basic Usage

### Define Static Method

```python
# O(1) - decorate function
class Math:
    @staticmethod
    def add(a, b):
        """Add two numbers - O(1)"""
        return a + b

# O(1) - call static method
result = Math.add(5, 3)  # 8

# Works on instance too
obj = Math()
result = obj.add(5, 3)  # 8 - same as class call
```

### Utility Functions in Classes

```python
# O(1) - organize utility functions
class StringUtils:
    @staticmethod
    def reverse(s):
        """Reverse string - O(n)"""
        return s[::-1]
    
    @staticmethod
    def is_palindrome(s):
        """Check palindrome - O(n)"""
        return s == s[::-1]
    
    @staticmethod
    def count_vowels(s):
        """Count vowels - O(n)"""
        return sum(1 for c in s.lower() if c in 'aeiou')

# O(1) - use utilities
result1 = StringUtils.reverse("hello")        # olleh
result2 = StringUtils.is_palindrome("racecar") # True
result3 = StringUtils.count_vowels("hello")   # 2
```

### No Access to Instance or Class

```python
# O(1) - static method cannot access instance or class
class Example:
    class_var = 42
    
    @staticmethod
    def static_func():
        """Cannot access self or cls - O(1)"""
        return "Just a function"
    
    def instance_func(self):
        """Can access self - O(1)"""
        return self.class_var

obj = Example()

# O(1) - static method doesn't receive self or cls
result = Example.static_func()  # "Just a function"

# O(1) - instance method receives self
result = obj.instance_func()    # 42
```

## Complexity Details

### Descriptor Protocol

```python
# O(1) - staticmethod uses descriptor protocol
class WithStaticMethod:
    @staticmethod
    def method(x, y):
        return x + y

# When accessing:
# 1. Lookup 'method' in class dict - O(1)
# 2. Found descriptor (staticmethod object)
# 3. Call descriptor.__get__() - O(1)
# 4. Returns underlying function (no binding)

result = WithStaticMethod.method(1, 2)  # O(1)
```

### Same on Class and Instance

```python
# O(1) - identical behavior from both
class Static:
    @staticmethod
    def compute(x):
        return x * 2

obj = Static()

# Both return same thing - no binding
from_class = Static.compute(5)     # 10
from_instance = obj.compute(5)     # 10

# They're literally the same function
print(Static.compute is obj.compute)  # True
```

### No MRO for Arguments

```python
# O(1) - static method lookup still uses MRO
class Parent:
    @staticmethod
    def helper():
        return "Parent"

class Child(Parent):
    pass

# O(d) - finds in Parent via MRO
result = Child.helper()  # "Parent"

# But method doesn't know it's being called on Child
# No special handling like classmethod
```

## Performance Patterns

### vs Regular Function

```python
# staticmethod - O(1), namespaced
class Utils:
    @staticmethod
    def parse(data):
        return data.split(',')

# Function lookup O(d) but faster than top-level
result = Utils.parse("a,b,c")  # O(1)

# vs top-level function - O(1)
def parse(data):
    return data.split(',')

result = parse("a,b,c")  # O(1)

# staticmethod is slightly slower (namespace lookup)
# ~2-5% overhead from descriptor protocol
```

### vs Classmethod

```python
# staticmethod - O(1), no class argument
class Static:
    @staticmethod
    def operate(x):
        return x * 2  # O(1)

# classmethod - O(1), receives cls
class WithClass:
    multiplier = 2
    
    @classmethod
    def operate(cls, x):
        return x * cls.multiplier  # O(1)

# staticmethod is marginally faster (no cls binding)
# But classmethod is more flexible for inheritance
```

### vs Instance Method

```python
# staticmethod - O(1), no instance binding
class Static:
    @staticmethod
    def calc(x):
        return x ** 2  # O(1)

# instance method - O(1), needs instance
class WithInstance:
    def calc(self, x):
        return x ** 2  # O(1)

# staticmethod doesn't require instance creation
result1 = Static.calc(5)       # O(1) - no instance needed

obj = WithInstance()           # O(1) - create instance
result2 = obj.calc(5)          # O(1) - use instance method
```

## Common Use Cases

### Utility Functions

```python
# O(n) - group related utility functions
class FileUtils:
    @staticmethod
    def read_file(path):
        """Read file - O(n)"""
        with open(path) as f:
            return f.read()
    
    @staticmethod
    def write_file(path, content):
        """Write file - O(n)"""
        with open(path, 'w') as f:
            f.write(content)
    
    @staticmethod
    def file_exists(path):
        """Check file - O(1)"""
        import os
        return os.path.exists(path)

# O(n) - use utilities
content = FileUtils.read_file('data.txt')
FileUtils.write_file('output.txt', content)

if FileUtils.file_exists('data.txt'):
    print("File found")
```

### Mathematical Operations

```python
# O(1) - group math functions
class Geometry:
    @staticmethod
    def distance(x1, y1, x2, y2):
        """Euclidean distance - O(1)"""
        return ((x2 - x1)**2 + (y2 - y1)**2)**0.5
    
    @staticmethod
    def circle_area(radius):
        """Circle area - O(1)"""
        import math
        return math.pi * radius**2
    
    @staticmethod
    def triangle_area(base, height):
        """Triangle area - O(1)"""
        return 0.5 * base * height

# O(1) - use geometry functions
dist = Geometry.distance(0, 0, 3, 4)        # 5.0
area = Geometry.circle_area(5)              # 78.54...
tri = Geometry.triangle_area(10, 5)         # 25.0
```

### Validation Functions

```python
# O(n) - group validation functions
class Validators:
    @staticmethod
    def is_email(email):
        """Validate email - O(n)"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_phone(phone):
        """Validate phone - O(n)"""
        import re
        pattern = r'^\d{10}$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def is_strong_password(password):
        """Validate password - O(n)"""
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        return len(password) >= 8 and has_upper and has_lower and has_digit

# O(n) - validate inputs
if Validators.is_email("user@example.com"):
    print("Valid email")

if Validators.is_strong_password("MyPass123"):
    print("Strong password")
```

### Conversion Functions

```python
# O(n) - group conversion functions
class Converters:
    @staticmethod
    def celsius_to_fahrenheit(celsius):
        """Convert temperature - O(1)"""
        return (celsius * 9/5) + 32
    
    @staticmethod
    def fahrenheit_to_celsius(fahrenheit):
        """Convert temperature - O(1)"""
        return (fahrenheit - 32) * 5/9
    
    @staticmethod
    def miles_to_km(miles):
        """Convert distance - O(1)"""
        return miles * 1.60934
    
    @staticmethod
    def kg_to_pounds(kg):
        """Convert weight - O(1)"""
        return kg * 2.20462

# O(1) - use conversions
c = Converters.fahrenheit_to_celsius(98.6)
km = Converters.miles_to_km(100)
```

### Parsing Functions

```python
# O(n) - group parsing functions
class Parsers:
    @staticmethod
    def parse_csv(csv_string):
        """Parse CSV - O(n)"""
        return [line.split(',') for line in csv_string.strip().split('\n')]
    
    @staticmethod
    def parse_json(json_string):
        """Parse JSON - O(n)"""
        import json
        return json.loads(json_string)
    
    @staticmethod
    def parse_url(url):
        """Parse URL - O(n)"""
        from urllib.parse import urlparse
        return urlparse(url)

# O(n) - use parsers
rows = Parsers.parse_csv("a,b,c\n1,2,3")
```

## Advanced Usage

### Static Methods in Inheritance

```python
# O(d) - inherited static methods
class Parent:
    @staticmethod
    def describe():
        return "Parent class"

class Child(Parent):
    pass

# O(d) - found via MRO
result = Child.describe()  # "Parent class"

# But static method can be overridden
class ChildOverride(Parent):
    @staticmethod
    def describe():
        return "Child class"

result = ChildOverride.describe()  # "Child class"
```

### Static Method Factory

```python
# O(1) - create instances without class access
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    @staticmethod
    def from_polar(r, theta):
        """Create from polar coordinates - O(1)"""
        import math
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        return Vector(x, y)

# O(1) - use factory (note: doesn't need cls)
v = Vector.from_polar(1, 0)
print(v.x, v.y)  # 1.0, 0.0
```

### Organizing Related Functions

```python
# O(n) - organize processing pipeline
class DataProcessor:
    @staticmethod
    def normalize(data):
        """Normalize data - O(n)"""
        min_val = min(data)
        max_val = max(data)
        return [(x - min_val) / (max_val - min_val) for x in data]
    
    @staticmethod
    def filter_outliers(data, threshold=3):
        """Remove outliers - O(n)"""
        mean = sum(data) / len(data)
        std = (sum((x - mean)**2 for x in data) / len(data))**0.5
        return [x for x in data if abs(x - mean) <= threshold * std]
    
    @staticmethod
    def smooth(data, window=3):
        """Smooth data - O(n)"""
        return [sum(data[i:i+window])/window 
                for i in range(len(data) - window + 1)]

# O(n) - process pipeline
data = [1, 2, 100, 3, 4]
filtered = DataProcessor.filter_outliers(data)
normalized = DataProcessor.normalize(filtered)
```

## Practical Examples

### Configuration Constants

```python
# O(1) - group configuration values
class Config:
    DEBUG = True
    TIMEOUT = 30
    MAX_RETRIES = 3
    
    @staticmethod
    def get_config():
        """Return all settings - O(1)"""
        return {
            'debug': Config.DEBUG,
            'timeout': Config.TIMEOUT,
            'retries': Config.MAX_RETRIES
        }

# O(1) - access config
if Config.DEBUG:
    print("Debug mode")

settings = Config.get_config()
```

### API Endpoint Mappings

```python
# O(1) - map endpoints to handlers
class API:
    @staticmethod
    def get_endpoints():
        """List all endpoints - O(1)"""
        return {
            '/users': 'list_users',
            '/posts': 'list_posts',
            '/comments': 'list_comments'
        }
    
    @staticmethod
    def is_valid_endpoint(path):
        """Check endpoint - O(1)"""
        return path in API.get_endpoints()

# O(1) - use API
endpoints = API.get_endpoints()
```

### JSON Serialization

```python
# O(n) - serialize/deserialize
class JSONHelper:
    @staticmethod
    def to_json(obj):
        """Serialize to JSON - O(n)"""
        import json
        return json.dumps(obj.__dict__)
    
    @staticmethod
    def from_json(json_str, cls):
        """Deserialize from JSON - O(n)"""
        import json
        data = json.loads(json_str)
        obj = cls.__new__(cls)
        obj.__dict__.update(data)
        return obj

# O(n) - serialization
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

p = Person("Alice", 30)
json_str = JSONHelper.to_json(p)
```

## Edge Cases

### No Access to Instance State

```python
# O(1) - static method can't access instance state
class Example:
    def __init__(self, value):
        self.value = value
    
    @staticmethod
    def compute(x):
        # Cannot access self.value
        return x * 2

obj = Example(42)

# Static method ignores instance
result = obj.compute(5)  # 10, not 5 * 42
```

### Calling Without Instance

```python
# O(1) - static method doesn't require instance
class Utils:
    @staticmethod
    def helper():
        return 42

# Works without creating instance
result = Utils.helper()  # 42

# vs instance method (needs instance)
class WithInstance:
    def helper(self):
        return 42

# obj = WithInstance()  # Must create instance
# result = obj.helper()
```

### Static Method Can't Call Other Methods

```python
# O(1) - static method limitation
class Example:
    def instance_method(self):
        return "instance"
    
    @staticmethod
    def static_method():
        # Cannot call self.instance_method()
        # No self available
        return "static"

obj = Example()
result = obj.static_method()  # O(1)
```

## Performance Considerations

### When to Use Static Methods

```python
# Use staticmethod when:
# 1. Function logically belongs to class
# 2. Don't need instance or class state
# 3. Could be a module function but class organization is clearer

class Statistics:
    @staticmethod  # Good - utility function
    def mean(data):
        return sum(data) / len(data)
    
    @staticmethod  # Good - pure function
    def variance(data):
        m = sum(data) / len(data)
        return sum((x - m)**2 for x in data) / len(data)

# vs module function (also fine)
def mean(data):
    return sum(data) / len(data)
```

## Best Practices

✅ **Do**:

- Use for utility and helper functions
- Use to organize related stateless functions
- Use when function doesn't need self or cls
- Keep static methods pure (no side effects)
- Document that method is static in docstrings

❌ **Avoid**:

- Using staticmethod when you need class or instance state
- Complex logic (keep simple)
- Mixing staticmethod with instance state access
- Using staticmethod when module function is clearer
- Making static methods depend on class attributes

## Related Functions

- **[classmethod()](classmethod.md)** - Decorator for class methods
- **[property()](property.md)** - Decorator for properties
- **type()** - Get object type
- **[callable()](callable.md)** - Check if callable

## Version Notes

- **Python 2.x**: `@staticmethod` available, same behavior
- **Python 3.x**: Same behavior, optimized in CPython
- **All versions**: First parameter is not automatic (no self/cls)
