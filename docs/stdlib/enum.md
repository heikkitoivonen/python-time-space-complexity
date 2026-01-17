# enum Module Complexity

The `enum` module provides a way to define a set of symbolic names (members) bound to unique, constant values.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Enum()` class definition | O(n) | O(n) | n = number of members |
| Access member by name | O(1) | O(1) | Direct attribute lookup |
| Access member by value | O(n) | O(1) | Linear search through members |
| Iteration `for e in EnumClass` | O(n) | O(1) | n = number of members |
| `len(EnumClass)` | O(1) | O(1) | Cached member count |
| `name` / `value` access | O(1) | O(1) | Direct attribute |

## Enum Basics

### Creating an Enum

```python
from enum import Enum

# Define enum - O(n) for n members
class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

# Access by name - O(1)
print(Color.RED)       # Color.RED
print(Color.RED.name)  # 'RED'
print(Color.RED.value) # 1
```

### Member Access

```python
from enum import Enum

class Status(Enum):
    PENDING = 'pending'
    ACTIVE = 'active'
    DONE = 'done'

# By name - O(1)
status = Status.ACTIVE      # Direct lookup
print(status.name)          # 'ACTIVE'

# By value - O(n)
status = Status('active')   # Must search all members
print(status.value)         # 'active'
```

### Iteration

```python
from enum import Enum

class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

# Iterate all members - O(n)
for priority in Priority:
    print(f"{priority.name}: {priority.value}")

# Output:
# LOW: 1
# MEDIUM: 2
# HIGH: 3
```

## Enum Types

### IntEnum - Integer-like

```python
from enum import IntEnum

# IntEnum allows comparison with integers - O(1)
class Code(IntEnum):
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    NOT_FOUND = 404

# Compare with integers - O(1)
if Code.OK == 200:          # True
    print("Success")

if Code.NOT_FOUND > 400:    # True
    print("Client error")

# Can be used in arithmetic - O(1)
total = Code.OK + Code.CREATED  # 401
```

### Flag - Bitwise Operations

```python
from enum import Flag, auto

# Flag enum for combining values - O(1) per operation
class Permission(Flag):
    READ = auto()      # 1
    WRITE = auto()     # 2
    EXECUTE = auto()   # 4

# Combine flags - O(1)
user_perms = Permission.READ | Permission.WRITE

# Check flags - O(1)
if Permission.READ in user_perms:
    print("Can read")

if Permission.EXECUTE not in user_perms:
    print("Cannot execute")

# Remove flags - O(1)
user_perms = user_perms & ~Permission.WRITE
```

### IntFlag - Integer Flag Combination

```python
from enum import IntFlag, auto

class Status(IntFlag):
    READY = auto()        # 1
    WAITING = auto()      # 2
    ERROR = auto()        # 4

# Combine with | operator - O(1)
task_status = Status.READY | Status.WAITING

# Test with & operator - O(1)
if task_status & Status.READY:
    print("Task is ready")

# Convert from integer - O(n) for lookup
s = Status(3)  # Status.READY | Status.WAITING
```

## Common Operations

### Comparison

```python
from enum import Enum

class Environment(Enum):
    DEV = 'development'
    PROD = 'production'

env = Environment.DEV

# Identity comparison - O(1)
if env is Environment.DEV:
    print("Development environment")

# Equality comparison - O(1)
if env == Environment.DEV:
    print("Using DEV")

# String comparison - O(1)
if env.value == 'development':
    print("Match by value")
```

### Member Lookup

```python
from enum import Enum

class Animal(Enum):
    DOG = 1
    CAT = 2
    BIRD = 3

# Get by name - O(1)
animal = Animal['DOG']          # Animal.DOG
print(animal.value)              # 1

# Get by value - O(n)
animal = Animal(2)               # Animal.CAT (searches all)

# Safe get by name - O(1)
try:
    animal = Animal['FISH']
except KeyError:
    print("Not found")
```

### Check Membership

```python
from enum import Enum

class Size(Enum):
    SMALL = 'S'
    MEDIUM = 'M'
    LARGE = 'L'

# Check by name - O(1)
if 'SMALL' in Size.__members__:
    print("Size.SMALL exists")

# Check by member - O(1)
if Size.SMALL in Size:
    print("SMALL is valid size")

# Get all names - O(n)
names = list(Size.__members__.keys())  # ['SMALL', 'MEDIUM', 'LARGE']
```

## Advanced Patterns

### Enum with Methods

```python
from enum import Enum

class Status(Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    DONE = 'done'
    
    # Method - O(1)
    def is_final(self):
        return self == Status.DONE
    
    # Method - O(1)
    def is_active(self):
        return self in (Status.PENDING, Status.PROCESSING)

# Use methods - O(1)
status = Status.PROCESSING
if status.is_active():
    print("Task is running")
```

### Enum Aliases

```python
from enum import Enum

class Color(Enum):
    RED = 1
    CRIMSON = 1      # Alias for RED
    GREEN = 2
    BLUE = 3

# All refer to same member - O(1)
print(Color.RED is Color.CRIMSON)  # True
print(len(Color))                  # 3 (aliases don't count)
```

### Functional API

```python
from enum import Enum

# Create enum from list - O(n)
Animal = Enum('Animal', 'DOG CAT BIRD')
# Equivalent to:
# class Animal(Enum):
#     DOG = 1
#     CAT = 2
#     BIRD = 3

# Access - O(1)
print(Animal.DOG)      # Animal.DOG
print(Animal.DOG.value) # 1
```

### Custom Value Processing

```python
from enum import Enum

class HttpStatus(Enum):
    OK = (200, 'OK')
    CREATED = (201, 'Created')
    BAD_REQUEST = (400, 'Bad Request')
    
    def __init__(self, code, message):
        self.code = code
        self.message = message
    
    # O(1)
    def __str__(self):
        return f"{self.code} {self.message}"

# Access - O(1)
status = HttpStatus.OK
print(status.code)      # 200
print(status.message)   # 'OK'
print(str(status))      # '200 OK'
```

## Performance Comparison

### Access Methods

```python
from enum import Enum

class Day(Enum):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7

# By name - O(1), fastest
day = Day.MONDAY

# By name with getattr - O(1)
day = getattr(Day, 'MONDAY')

# By name dict - O(1)
day = Day.__members__['MONDAY']

# By value - O(n), iterates all members
day = Day(1)
```

### Iteration vs Lookup

```python
from enum import Enum

class Status(Enum):
    PENDING = 'pending'
    ACTIVE = 'active'
    DONE = 'done'

# Get all - O(n)
all_statuses = list(Status)  # 3 operations

# Get one by name - O(1)
status = Status.PENDING

# Get one by value - O(n)
status = Status('pending')   # Must search
```

## When to Use Enum

### Good For
- Fixed set of named constants
- Type safety (prevents invalid values)
- Better readability than magic numbers/strings
- Clear intent and documentation

```python
from enum import Enum

# Good: Type-safe status
class OrderStatus(Enum):
    PENDING = 'pending'
    SHIPPED = 'shipped'
    DELIVERED = 'delivered'

def process_order(status: OrderStatus) -> None:
    if status == OrderStatus.PENDING:
        send_to_warehouse()
```

### Avoid When
- Set changes frequently
- Need dynamic values
- Simple flags where tuples work
- Performance-critical lookup by value

```python
from enum import Enum

# Avoid: Frequent changes needed
# Use dict or database instead
STATUSES = {1: 'pending', 2: 'active'}  # Easier to modify
```

## Memory Efficiency

### Enum Instance Caching

```python
from enum import Enum

class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

# All references same instance - O(1) memory per unique value
color1 = Color.RED
color2 = Color.RED
color3 = Color.RED

print(id(color1) == id(color2) == id(color3))  # True
```

### Small Memory Footprint

```python
from enum import Enum
import sys

class Status(Enum):
    OK = 1
    ERROR = 2

# Enum members are cached singletons
status = Status.OK
print(sys.getsizeof(status))  # Very small, reused instance
```

## Related Documentation

- [Collections Module](collections.md)
- [Typing Module](typing.md)
- [Dataclasses Module](dataclasses.md)
