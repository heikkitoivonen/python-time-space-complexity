# None Constant Complexity

The `None` constant represents the absence of a value. It's Python's null value and is returned by functions that don't explicitly return a value.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Comparison | O(1) | O(1) | Uses `is` operator |
| Truthiness test | O(1) | O(1) | Always falsy |
| Type check | O(1) | O(1) | `type(None)` |
| Assignment | O(1) | O(1) | Single object |

## Basic Usage

### Null Value

```python
# O(1) - None is a singleton
value = None

# Check for None
if value is None:  # O(1) - use 'is', not '=='
    print("No value")

# Default return value
def function():
    pass  # Returns None implicitly

result = function()  # None
```

### Default Arguments

```python
# O(1) - None as default
def process(data=None):
    if data is None:  # O(1)
        data = []
    return data

# O(1) - call with None
result1 = process()        # Returns []
result2 = process([1, 2])  # Returns [1, 2]
```

### Initialization

```python
# O(1) - initialize to None
class Data:
    def __init__(self):
        self.value = None  # O(1)
        self.items = None  # O(1)

obj = Data()

# Check and initialize
if obj.value is None:  # O(1)
    obj.value = []
```

## Complexity Details

### Singleton Pattern

```python
# O(1) - None is a singleton
none1 = None
none2 = None

# Both refer to same object
print(none1 is none2)  # True - O(1)
print(id(none1) == id(none2))  # True - O(1)

# Cannot create new None instances
# None = "something"  # NameError in Python 3
```

### Type and Identity

```python
# O(1) - type checking
value = None

# Type is NoneType
type(value)  # <class 'NoneType'> - O(1)

# Type comparison
type(value) is type(None)  # True - O(1)

# Identity check (preferred over equality)
value is None  # True - O(1)
value == None  # True - O(1) but slower
```

### Truthiness

```python
# O(1) - None is falsy
if None:
    print("Won't execute")
else:
    print("None is falsy")  # Executes

# Explicit check
value = None

if not value:  # O(1)
    print("Value is falsy")

# vs explicit None check (preferred)
if value is None:  # O(1) - clearer intent
    print("Value is None")
```

## Performance Patterns

### is vs == Comparison

```python
# is operator - O(1), recommended for None
value = None

if value is None:  # O(1) - fastest, recommended
    pass

# == operator - O(1) but slower
if value == None:  # O(1) but ~10% overhead
    pass

# Always use 'is' for None checking
# It's clearer and slightly faster
```

### Explicit vs Implicit None

```python
# Implicit None return - O(1)
def implicit():
    pass  # Returns None implicitly

# Explicit None return - O(1)
def explicit():
    return None  # Explicit is clearer

# Performance identical
result1 = implicit()  # None - O(1)
result2 = explicit()  # None - O(1)

# Explicit is preferred for clarity
```

## Common Use Cases

### Optional Parameters

```python
# O(1) - None indicates "no value provided"
def greet(name=None):
    if name is None:  # O(1)
        name = "World"
    return f"Hello, {name}"

# O(1) - use with or without argument
print(greet())           # Hello, World
print(greet("Alice"))    # Hello, Alice
```

### Sentinel Value

```python
# O(1) - use None as sentinel
def find_item(items, target):
    for item in items:
        if item == target:
            return item
    
    return None  # Indicates not found

# O(n) - search
result = find_item([1, 2, 3, 4], 3)
if result is None:  # O(1)
    print("Not found")
else:
    print(f"Found: {result}")
```

### Lazy Initialization

```python
# O(1) - lazy initialization pattern
class Cache:
    def __init__(self):
        self._data = None  # O(1)
    
    def get_data(self):
        if self._data is None:  # O(1)
            self._data = self._load()  # O(load)
        return self._data
    
    def _load(self):
        # Expensive operation
        return list(range(1000000))

cache = Cache()

# First access: O(load)
data1 = cache.get_data()

# Subsequent accesses: O(1)
data2 = cache.get_data()
```

### Optional Values

```python
# O(1) - represent missing values
class Optional:
    def __init__(self, value=None):
        self.value = value
    
    def has_value(self):
        return self.value is not None  # O(1)
    
    def get_or_default(self, default):
        if self.value is None:  # O(1)
            return default
        return self.value

# O(1) - work with optional
opt1 = Optional(42)
opt2 = Optional()  # None

print(opt1.has_value())           # True
print(opt2.has_value())           # False
print(opt2.get_or_default(0))     # 0
```

### Dictionary Operations

```python
# O(1) - None as missing key indicator
data = {'a': 1, 'b': None, 'c': 3}

# get() returns None for missing keys
value = data.get('d')  # None - O(1)

if value is None:  # O(1)
    print("Key not found")

# Distinguish between missing and None
if 'd' in data:  # O(1)
    print("Key exists")
else:
    print("Key missing")  # This executes
```

## Advanced Usage

### Type Annotations

```python
# O(1) - None in type hints
from typing import Optional

def process(value: Optional[int] = None) -> None:
    """Process optional value - O(1)"""
    if value is None:  # O(1)
        print("No value provided")
    else:
        print(f"Value: {value}")

# O(1) - call function
process()        # No value provided
process(42)      # Value: 42

# None as return type annotation
def cleanup() -> None:  # Returns None
    print("Cleaning up")
```

### None Coalescing Pattern

```python
# O(1) - find first non-None value
def coalesce(*values):
    """Return first non-None value - O(n)"""
    for value in values:  # O(n)
        if value is not None:  # O(1)
            return value
    return None

# O(n) - find first non-None
result = coalesce(None, None, 5, 10)
print(result)  # 5

# Python 3.10+ walrus and match
value = None
if (result := coalesce(None, None, 42)) is not None:
    print(result)
```

### Comparison with Empty Values

```python
# O(1) - None vs empty values
value1 = None
value2 = []
value3 = {}
value4 = ""

# None is distinct from empty values
print(value1 is None)  # True
print(value2 is None)  # False - empty list, not None
print(value3 is None)  # False - empty dict, not None
print(value4 is None)  # False - empty string, not None

# All are falsy but only None is None
print(bool(value1))  # False
print(bool(value2))  # False
print(bool(value3))  # False
print(bool(value4))  # False

# Always check explicitly if needed
if value2 is None:
    print("No list")
elif len(value2) == 0:
    print("Empty list")
```

## Practical Examples

### JSON Serialization

```python
# O(1) - None converts to null in JSON
import json

data = {
    'name': 'Alice',
    'email': None,
    'age': 30
}

# O(n) - serialize
json_str = json.dumps(data)
# '{"name": "Alice", "email": null, "age": 30}'

# O(n) - deserialize
loaded = json.loads(json_str)
print(loaded['email'] is None)  # True - O(1)
```

### Function Chaining

```python
# O(1) - None indicates chain break
class Builder:
    def __init__(self):
        self.value = None
    
    def add(self, x):
        if self.value is None:  # O(1)
            self.value = x
        else:
            self.value += x
        return self
    
    def build(self):
        if self.value is None:  # O(1)
            return 0
        return self.value

# O(1) - chain operations
result = Builder().add(5).add(3).build()
print(result)  # 8
```

### Default Factory Pattern

```python
# O(1) - use None as trigger for default
class Config:
    def __init__(self, value=None):
        self.value = value if value is not None else self._default()
    
    def _default(self):
        return {
            'debug': False,
            'timeout': 30
        }

# O(1) - with explicit value
config1 = Config({'debug': True})

# O(1) - with None (uses default)
config2 = Config()
```

## Edge Cases

### None in Collections

```python
# O(1) - None can be stored in collections
items = [1, None, 3, None, 5]

# O(n) - count None values
none_count = sum(1 for x in items if x is None)  # 2

# O(n) - find None
has_none = None in items  # True

# O(1) - first None is different from no elements
single_none = [None]
print(len(single_none))    # 1
print(single_none[0] is None)  # True
```

### Multiple None Values

```python
# O(1) - unpacking None
a, b, c = None, None, None

# All refer to same object
print(a is b is c)  # True - O(1)

# In list/dict
values = [None, None, None]
print(values[0] is values[1])  # True - O(1)
```

### Comparison Chains

```python
# O(1) - None in comparisons
x = None

# Works in comparisons
if x is None:  # O(1)
    print("x is None")

# Multiple checks
y = None
if x is None and y is None:  # O(1)
    print("Both None")

# Identity check chain
if x is y is None:  # O(1)
    print("x and y are both None")
```

## Performance Considerations

### Caching None Checks

```python
# Avoid repeated None checks
class OptimizedProcessor:
    def process(self, data):
        # Check once at start
        if data is None:  # O(1)
            return None
        
        # Now safe to use data
        return self._do_process(data)

# vs repeated checks (slower in loops)
def slow_process(items):
    result = []
    for item in items:
        if item is None:  # O(1) repeated
            continue
        result.append(item * 2)
    return result

# Better: filter first
def fast_process(items):
    return [x * 2 for x in items if x is not None]  # O(n)
```

## Best Practices

✅ **Do**:

- Use `is None` for checking (not `== None`)
- Use `is not None` for non-None check
- Use None as default argument value
- Use None as sentinel value
- Use in type hints as `Optional[T]`
- Explicitly return None when appropriate

❌ **Avoid**:

- Using `== None` (use `is None` instead)
- Returning None implicitly when unclear
- Confusing None with empty values ([], {}, "")
- Using None as a mutable default argument
- Mixing None with other falsy values in conditions
- Overriding None behavior

## Related Constants

- **[True](true.md)** - Boolean true value
- **[False](false.md)** - Boolean false value
- **[NotImplemented](notimplemented.md)** - Not implemented marker
- **[Ellipsis](ellipsis.md)** - Ellipsis object (...)

## Version Notes

- **Python 2.x**: `None` is a singleton, same as Python 3
- **Python 3.x**: `None` is a singleton, keyword, cannot be reassigned
- **All versions**: Represents absence of value, not false
