# namedtuple - Tuple with Named Fields Complexity

The `namedtuple` factory function creates a tuple subclass with named fields, providing readable and efficient alternative to tuples with positional indexing.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `namedtuple()` | O(1) | O(1) | Create class |
| `Point(x, y)` | O(1) | O(1) | Create instance |
| Attribute access | O(1) | O(1) | Access by name |
| Indexing | O(1) | O(1) | Access by index |
| Unpacking | O(n) | O(1) | Unpack all fields |

## Basic Usage

```python
from collections import namedtuple

# Create namedtuple class - O(1)
Point = namedtuple('Point', ['x', 'y'])  # O(1)

# Create instance - O(1)
p = Point(3, 4)  # O(1)

# Access by name - O(1)
print(p.x)  # 3
print(p.y)  # 4

# Access by index - O(1)
print(p[0])  # 3
print(p[1])  # 4
```

## Field Definition Options

```python
from collections import namedtuple

# List of field names - O(1)
Point = namedtuple('Point', ['x', 'y'])

# String of field names - O(1)
Point = namedtuple('Point', 'x y')

# String with spaces - O(1)
Point = namedtuple('Point', 'x, y')

# Using indices - O(1)
Point = namedtuple('Point', 'x y', defaults=[0, 0])
```

## Common Use Cases

### Data Structures

```python
from collections import namedtuple

# Define structure - O(1)
Person = namedtuple('Person', ['name', 'age', 'email'])

# Create instances - O(1) each
person1 = Person('Alice', 30, 'alice@example.com')  # O(1)
person2 = Person('Bob', 25, 'bob@example.com')      # O(1)

# Access fields - O(1)
print(person1.name)  # 'Alice'
print(person1.age)   # 30
```

### Return Multiple Values

```python
from collections import namedtuple

# Define return type - O(1)
Result = namedtuple('Result', ['success', 'message', 'data'])

def process_data(filename):
    """Return structured result - O(1)"""
    try:
        with open(filename) as f:
            data = f.read()  # O(n)
        return Result(True, 'Success', data)  # O(1)
    except FileNotFoundError:
        return Result(False, 'File not found', None)  # O(1)

# Usage - O(1)
result = process_data('data.txt')
if result.success:
    print(result.data)
```

### Database Results

```python
from collections import namedtuple

# Define schema - O(1)
User = namedtuple('User', ['id', 'name', 'email', 'created_at'])

# Simulate database query - O(n)
def query_users(db, limit):
    """Return user records - O(n)"""
    users = []
    for row in db.execute('SELECT * FROM users LIMIT ?', (limit,)):
        users.append(User(*row))  # O(1) per row
    return users

# Usage - O(n)
users = query_users(db, 10)
for user in users:  # O(1) each
    print(user.name, user.email)
```

## Advanced Features

### Default Values

```python
from collections import namedtuple

# Define with defaults - O(1)
Point = namedtuple('Point', ['x', 'y', 'z'], defaults=[0, 0, 0])

# Create with defaults - O(1)
p1 = Point(1)  # Point(x=1, y=0, z=0)
p2 = Point(1, 2)  # Point(x=1, y=2, z=0)
p3 = Point(1, 2, 3)  # Point(x=1, y=2, z=3)
```

### Conversion Methods

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])

# Create instance - O(1)
p = Point(3, 4)

# Convert to dict - O(n)
d = p._asdict()  # O(2) -> {'x': 3, 'y': 4}

# Create from dict - O(1)
p2 = Point(**d)  # O(1)

# Get field names - O(1)
fields = p._fields  # O(1) -> ('x', 'y')

# Replace field values - O(n)
p3 = p._replace(x=5)  # O(2) -> Point(x=5, y=4)

# Index of field - O(n)
idx = p._fields.index('x')  # O(2)
```

## Performance Comparison

### namedtuple vs dict

```python
from collections import namedtuple
import sys

# namedtuple - more memory efficient
Point_NT = namedtuple('Point', ['x', 'y'])
p_nt = Point_NT(3, 4)
nt_size = sys.getsizeof(p_nt)

# dict - more flexible
p_dict = {'x': 3, 'y': 4}
dict_size = sys.getsizeof(p_dict)

# namedtuple is more memory efficient
print(f"namedtuple size: {nt_size}")
print(f"dict size: {dict_size}")

# namedtuple is immutable
# p_nt.x = 5  # AttributeError

# dict is mutable
p_dict['x'] = 5  # OK
```

### namedtuple vs Class

```python
from collections import namedtuple

# namedtuple - lightweight - O(1)
Point_NT = namedtuple('Point', ['x', 'y'])
p = Point_NT(3, 4)

# Regular class - more flexible
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(3, 4)

# Both O(1) to create and access
# namedtuple uses less memory
# Class supports methods and inheritance
```

## When to Use namedtuple

### Good For:
- Simple data containers
- Return multiple values
- Lightweight immutable objects
- Memory-constrained environments
- Record-like structures

### Not Good For:
- Complex objects with methods
- Mutable data (need to change fields)
- When you need type flexibility
- Performance critical code (class may be faster)

## Unpacking

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])
p = Point(3, 4)

# Unpack all - O(n)
x, y = p  # O(2)

# Unpack with * - O(n)
coords = [0] + list(p)  # O(2)
```

## Common Patterns

### Batch Processing

```python
from collections import namedtuple

# Define record type - O(1)
Transaction = namedtuple('Transaction', ['id', 'amount', 'date'])

# Process records - O(n)
transactions = [
    Transaction(1, 100, '2024-01-01'),
    Transaction(2, 200, '2024-01-02'),
]

total = sum(t.amount for t in transactions)  # O(n)
```

## Version Notes

- **Python 2.6+**: namedtuple available
- **Python 3.x**: Same functionality
- **Python 3.7+**: defaults parameter added
- **Python 3.13+**: Additional features

## Related Modules

- **[typing.NamedTuple](typing.md)** - Type-hinted version
- **[dataclasses.dataclass](dataclasses.md)** - Modern alternative
- **[tuple](../builtins/tuple.md)** - Regular tuples

## Best Practices

✅ **Do**:

- Use for simple data containers
- Use for returning multiple values
- Use _asdict() for serialization
- Use defaults for optional fields

❌ **Avoid**:

- Complex logic (use classes)
- Mutable data (use dataclass)
- When inheritance needed
- Over-engineering simple tuples
