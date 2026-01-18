# classmethod() Decorator Complexity

The `classmethod()` decorator modifies a function to receive the class as its first argument instead of an instance. It's used for factory methods and alternative constructors.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Create descriptor | O(1) | O(1) | Decorator application |
| Call class method | O(1) | O(1) | Access method on class |
| Call on instance | O(1) | O(1) | Access method on instance |
| MRO lookup | O(d) | O(1) | d = inheritance depth |
| Total operation | O(d) | O(1) | Lookup may traverse MRO |

## Basic Usage

### Define Class Method

```python
# O(1) - decorate method
class MyClass:
    count = 0
    
    @classmethod
    def create(cls):
        """Factory method - O(1)"""
        cls.count += 1
        return cls()

# O(1) - call class method
obj1 = MyClass.create()
obj2 = MyClass.create()

print(MyClass.count)  # 2
```

### Access Class Attributes

```python
# O(1) - class methods can access class state
class Config:
    default_timeout = 30
    
    @classmethod
    def get_timeout(cls):
        """Get class attribute - O(1)"""
        return cls.default_timeout
    
    @classmethod
    def set_timeout(cls, timeout):
        """Set class attribute - O(1)"""
        cls.default_timeout = timeout

# O(1) - access class methods
timeout = Config.get_timeout()  # 30

Config.set_timeout(60)
new_timeout = Config.get_timeout()  # 60
```

### Alternative Constructor

```python
# O(1) - use as alternative constructor
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    @classmethod
    def from_tuple(cls, point_tuple):
        """Create from tuple - O(1)"""
        x, y = point_tuple
        return cls(x, y)
    
    @classmethod
    def from_string(cls, point_str):
        """Create from string - O(1)"""
        x, y = map(float, point_str.split(','))
        return cls(x, y)

# O(1) - create via different constructors
p1 = Point.from_tuple((1, 2))
p2 = Point.from_string("3.5,4.5")

print(p1.x, p1.y)  # 1 2
print(p2.x, p2.y)  # 3.5 4.5
```

## Complexity Details

### Descriptor Protocol

```python
# O(1) - classmethod uses descriptor protocol
class WithClassMethod:
    @classmethod
    def method(cls):
        return cls.__name__

# When accessing:
# 1. Lookup 'method' in class dict - O(1)
# 2. Found descriptor (classmethod object)
# 3. Call descriptor.__get__() - O(1)
# 4. Returns bound method with cls

result = WithClassMethod.method()  # O(1)
```

### Inheritance and MRO

```python
# O(d) - MRO traversal for inherited class methods
class Parent:
    @classmethod
    def identify(cls):
        """Return class name - O(1)"""
        return cls.__name__

class Child(Parent):
    pass

# O(d) - lookup in Parent via MRO
name = Child.identify()  # 'Child' - MRO traversal
```

### Instance vs Class Access

```python
# O(1) - both access same method
class Example:
    @classmethod
    def info(cls):
        return f"I am {cls.__name__}"

obj = Example()

# O(1) - access from class
from_class = Example.info()  # "I am Example"

# O(1) - access from instance (converts to class)
from_instance = obj.info()  # "I am Example"

# Both work, classmethod automatically passes cls
```

## Performance Patterns

### vs Static Method

```python
# classmethod - O(1) + class access
class WithClassMethod:
    value = 42
    
    @classmethod
    def get_value(cls):
        return cls.value  # O(1)

# staticmethod - O(1), no class access
class WithStaticMethod:
    value = 42
    
    @staticmethod
    def get_value():
        # Cannot access cls, no class binding
        return WithStaticMethod.value  # O(1) hardcoded

# Both O(1), classmethod is more flexible
```

### vs Regular Method

```python
# classmethod - O(1), no instance needed
class A:
    @classmethod
    def class_op(cls):
        return cls.__name__  # O(1)
    
    def instance_op(self):
        return self.__class__.__name__  # O(1)

# classmethod - no instance required
result1 = A.class_op()  # O(1) - works on class directly

# instance method - needs instance
obj = A()  # O(1) - create instance
result2 = obj.instance_op()  # O(1) - call on instance
```

## Common Use Cases

### Factory Methods

```python
# O(1) - implement factory pattern
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height
    
    @classmethod
    def square(cls, side):
        """Create square - O(1)"""
        return cls(side, side)

# O(1) - use factory
rect = Rectangle(5, 10)
square = Rectangle.square(5)

print(square.width, square.height)  # 5 5
```

### Alternate Constructors

```python
# O(1) - multiple ways to construct
class Date:
    def __init__(self, year, month, day):
        self.year = year
        self.month = month
        self.day = day
    
    @classmethod
    def today(cls):
        """Create from today's date - O(1) + time lookup"""
        import datetime
        today = datetime.date.today()
        return cls(today.year, today.month, today.day)
    
    @classmethod
    def from_timestamp(cls, timestamp):
        """Create from timestamp - O(1) + conversion"""
        import datetime
        dt = datetime.datetime.fromtimestamp(timestamp)
        return cls(dt.year, dt.month, dt.day)

# O(1) - use different constructors
d1 = Date.today()
d2 = Date.from_timestamp(0)

print(d1.year, d1.month, d1.day)
```

### Tracking Subclasses

```python
# O(1) - track all subclass instances
class Registry:
    subclasses = {}
    
    def __init_subclass__(cls, **kwargs):
        """Called when subclass is created - O(1)"""
        super().__init_subclass__(**kwargs)
        Registry.subclasses[cls.__name__] = cls
    
    @classmethod
    def get_subclass(cls, name):
        """Lookup subclass - O(1)"""
        return cls.subclasses.get(name)

class DatabaseHandler(Registry):
    pass

class FileHandler(Registry):
    pass

# O(1) - look up registered subclass
handler = Registry.get_subclass('DatabaseHandler')
print(handler.__name__)  # DatabaseHandler
```

### Class-Level Configuration

```python
# O(1) - manage class-level state
class Logger:
    level = 'INFO'
    
    @classmethod
    def set_level(cls, level):
        """Set log level - O(1)"""
        cls.level = level
    
    @classmethod
    def get_level(cls):
        """Get log level - O(1)"""
        return cls.level
    
    def log(self, message):
        """Instance method using class state - O(1)"""
        if self.__class__.level == 'DEBUG':
            print(f"DEBUG: {message}")
        else:
            print(f"INFO: {message}")

# O(1) - configure class
Logger.set_level('DEBUG')

logger = Logger()
logger.log("test")  # Uses class-level DEBUG setting
```

## Advanced Usage

### Class Registry Pattern

```python
# O(1) - maintain registry of subclasses
class Plugin:
    plugins = {}
    
    def __init_subclass__(cls, **kwargs):
        """Register subclass - O(1)"""
        super().__init_subclass__(**kwargs)
        Plugin.plugins[cls.__name__] = cls
    
    @classmethod
    def create(cls, plugin_name):
        """Factory to create plugins - O(1)"""
        plugin_class = cls.plugins.get(plugin_name)
        if plugin_class:
            return plugin_class()
        return None

class AudioPlugin(Plugin):
    def play(self):
        return "Playing audio"

class VideoPlugin(Plugin):
    def play(self):
        return "Playing video"

# O(1) - create by name
audio = Plugin.create('AudioPlugin')
video = Plugin.create('VideoPlugin')

print(audio.play())  # Playing audio
print(video.play())  # Playing video
```

### Type Conversion Methods

```python
# O(1) - class methods for conversion
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    @classmethod
    def from_list(cls, lst):
        """Create from list - O(1)"""
        return cls(lst[0], lst[1])
    
    @classmethod
    def from_dict(cls, d):
        """Create from dict - O(1)"""
        return cls(d['x'], d['y'])
    
    def to_list(self):
        """Convert to list - O(1)"""
        return [self.x, self.y]

# O(1) - conversions
v1 = Vector.from_list([1, 2])
v2 = Vector.from_dict({'x': 3, 'y': 4})

print(v1.to_list())  # [1, 2]
```

### Inheritance with Classmethods

```python
# O(d) - subclass-aware class methods
class Base:
    @classmethod
    def create(cls):
        """Create instance of cls (not hardcoded Base)"""
        return cls()

class Child(Base):
    def describe(self):
        return "I am Child"

# O(d) - creates Child, not Base
obj = Child.create()
print(obj.describe())  # I am Child

# vs without classmethod - would create Base
class WrongBase:
    @staticmethod
    def create():
        return WrongBase()  # Always creates WrongBase!

class WrongChild(WrongBase):
    pass

obj = WrongChild.create()  # Creates WrongBase, not WrongChild
print(type(obj).__name__)  # WrongBase
```

## Practical Examples

### Date/Time Constructors

```python
# O(1) - convenient date/time creation
class Timestamp:
    def __init__(self, value):
        self.value = value
    
    @classmethod
    def now(cls):
        """Current time - O(1)"""
        import time
        return cls(time.time())
    
    @classmethod
    def from_seconds(cls, seconds):
        """From seconds since epoch - O(1)"""
        return cls(seconds)
    
    @classmethod
    def from_string(cls, date_str):
        """Parse string - O(n) for parsing"""
        import datetime
        dt = datetime.datetime.fromisoformat(date_str)
        return cls(dt.timestamp())

# O(1) - create different ways
ts1 = Timestamp.now()
ts2 = Timestamp.from_seconds(0)
ts3 = Timestamp.from_string("2024-01-01T00:00:00")
```

### Color Factory

```python
# O(1) - factory for color objects
class Color:
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b
    
    @classmethod
    def red(cls):
        return cls(255, 0, 0)
    
    @classmethod
    def green(cls):
        return cls(0, 255, 0)
    
    @classmethod
    def blue(cls):
        return cls(0, 0, 255)
    
    @classmethod
    def from_hex(cls, hex_str):
        """Parse hex color - O(1)"""
        r = int(hex_str[1:3], 16)
        g = int(hex_str[3:5], 16)
        b = int(hex_str[5:7], 16)
        return cls(r, g, b)

# O(1) - use factory methods
red = Color.red()
blue = Color.from_hex("#0000FF")
```

### Configuration Profiles

```python
# O(1) - predefined configurations
class DatabaseConfig:
    host = "localhost"
    port = 5432
    
    @classmethod
    def development(cls):
        """Dev configuration - O(1)"""
        config = cls()
        config.host = "localhost"
        config.port = 5432
        return config
    
    @classmethod
    def production(cls):
        """Prod configuration - O(1)"""
        config = cls()
        config.host = "prod.example.com"
        config.port = 5432
        return config

# O(1) - create profiles
dev_config = DatabaseConfig.development()
prod_config = DatabaseConfig.production()
```

## Edge Cases

### Calling on Instance

```python
# O(1) - can call class method on instance
class Example:
    name = "Example"
    
    @classmethod
    def get_name(cls):
        return cls.name

obj = Example()

# Both work - both pass class, not instance
class_name = Example.get_name()     # O(1) - pass Example
instance_name = obj.get_name()      # O(1) - pass Example (obj's class)

print(class_name)      # Example
print(instance_name)   # Example
```

### Inheritance Override

```python
# O(d) - subclass can override class method
class Parent:
    @classmethod
    def factory(cls):
        return f"Parent: {cls.__name__}"

class Child(Parent):
    @classmethod
    def factory(cls):
        return f"Child: {cls.__name__}"

# O(d) - correct method called based on class
print(Parent.factory())  # Parent: Parent
print(Child.factory())   # Child: Child
```

### First Argument Name

```python
# O(1) - cls name is conventional but flexible
class Flexible:
    @classmethod
    def method(klass):  # Can use any name
        return klass.__name__
    
    @classmethod
    def another(cls):   # Convention is 'cls'
        return cls.__name__

# Both work - first argument is always the class
print(Flexible.method())    # Flexible
print(Flexible.another())   # Flexible
```

## Performance Considerations

### Classmethod vs Hardcoded Class

```python
# Flexible with classmethod - O(d)
class Flexible:
    @classmethod
    def create(cls):
        return cls()

# Less flexible - O(1)
class Hardcoded:
    @staticmethod
    def create():
        return Hardcoded()

# For inheritance, classmethod is essential:
class Parent:
    @classmethod
    def from_classmethod(cls):
        return cls()  # Creates correct subclass

class Child(Parent):
    pass

# classmethod creates Child
obj1 = Child.from_classmethod()  # Works correctly
```

## Best Practices

✅ **Do**:

- Use for alternative constructors and factories
- Use for class-level state management
- Use for registry/plugin patterns
- Use when subclasses need custom behavior
- Document what the classmethod does clearly

❌ **Avoid**:

- Using classmethod when staticmethod suffices
- Modifying class state without clear intent
- Complex logic in classmethods (keep simple)
- Forgetting classmethod is called on class, not instance
- Hardcoding class names when cls can be used

## Related Functions

- **[staticmethod()](staticmethod.md)** - Decorator for static methods
- **[property()](property.md)** - Decorator for properties
- **type()** - Get object type
- **[super()](super.md)** - Call parent class method
- **[isinstance()](isinstance.md)** - Check instance type

## Version Notes

- **Python 2.x**: `@classmethod` available, same behavior
- **Python 3.x**: Same behavior, optimized in CPython
- **All versions**: First parameter is the class, not instance
