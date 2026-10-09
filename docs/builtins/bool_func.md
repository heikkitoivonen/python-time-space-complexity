# bool() Function Complexity

The `bool()` function converts an object to a boolean value using truthiness evaluation.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert number (int, float, complex) | O(1) | O(1) | Zero check; does not grow with the value's size |
| Convert built-in container (str, list, dict, set, range, etc) | O(1) | O(1) | Empty check on the stored length; items are not counted |
| Class defining `__bool__()` | O(k) | O(1) | k = `__bool__()`'s cost (usually O(1)); `__len__()` is not called |
| Class defining only `__len__()` | O(k) | O(1) | k = `__len__()`'s cost |
| Class defining neither | O(1) | O(1) | Always `True` |

`bool()` makes at most one call to `__bool__()` or `__len__()`, and a custom
method's own time and space add to the row. The result is one of the two
singletons `True` and `False`, so nothing is allocated for it.

## Basic Usage

### Boolean Values

```python
# O(1) - direct conversion
bool(True)   # True
bool(False)  # False
```

### Integers and Floats

```python
# O(1) - zero/non-zero check
bool(0)      # False
bool(1)      # True
bool(-1)     # True
bool(0.0)    # False
bool(3.14)   # True
```

### Strings

```python
# O(1) - empty/non-empty check
bool("")     # False (empty string)
bool("a")    # True (non-empty)
bool("0")    # True (non-empty, not zero!)
```

### Collections

```python
# O(1) - check if empty (uses __len__)
bool([])           # False
bool([1, 2, 3])    # True
bool({})           # False
bool({"a": 1})     # True
bool(set())        # False
bool({1, 2})       # True
bool(())           # False
bool((1, 2))       # True
```

### None

```python
# O(1) - None is always falsy
bool(None)  # False
```

## Complexity Details

### Container Truthiness

```python
# O(1) - uses __bool__() or __len__()
# Python checks for __bool__() first, then __len__()

class CustomClass:
    def __init__(self, size):
        self.size = size
    
    def __len__(self):
        # O(1) - just return stored size
        return self.size

obj = CustomClass(0)
bool(obj)  # False - calls __len__(), returns 0

obj = CustomClass(5)
bool(obj)  # True - calls __len__(), returns 5
```

### Custom `__bool__()` Method

```python
# O(k) - depends on __bool__() implementation

class Expensive:
    def __init__(self, data):
        self.data = data
    
    def __bool__(self):
        # O(n) worst case - any() stops at the first truthy item
        return any(self.data)

obj = Expensive([0, 0, 0])
bool(obj)  # False - O(n), all three items checked

# Without __bool__, __len__() decides - O(1) for a list
# It answers a different question: non-empty, not "any item truthy"
class Efficient:
    def __init__(self, data):
        self.data = data
    
    def __len__(self):
        # O(1) - quick
        return len(self.data)

obj = Efficient([0, 0, 0])
bool(obj)  # True - O(1), calls __len__()
```

## Truthiness Rules

```python
# O(1) - these are always falsy:
bool(None)      # False
bool(False)     # False
bool(0)         # False
bool(0.0)       # False
bool(0j)        # False (complex)
bool("")        # False (empty string)
bool([])        # False (empty list)
bool({})        # False (empty dict)
bool(set())     # False (empty set)
bool(())        # False (empty tuple)
bool(range(0))  # False (empty range)

# O(1) - these values are truthy:
bool(True)      # True
bool(1)         # True
bool(-1)        # True
bool(0.1)       # True
bool("0")       # True (non-empty!)
bool([0])       # True (non-empty!)
bool([None])    # True (non-empty!)
bool([False])   # True (non-empty!)
```

## Common Patterns

### Conditional Checks

```python
# O(1) - implicit bool conversion
def process(items):
    return len(items)

items = []

if items:           # O(1) - checks truthiness
    process(items)

# Explicit conversion
if bool(items):     # O(1) - same thing
    process(items)

# More Pythonic - just use implicit
if items:           # Preferred
    process(items)
```

### Negation

```python
# O(1) - logical not
not True    # False
not False   # True

# With objects
items = []
if not items:  # O(1) - equivalent to if len(items) == 0
    print("empty")
```

### Filtering by Truthiness

```python
# O(n) - check each item
items = [0, 1, "", "hello", [], [1], None, False, True]

# Remove falsy values - O(n)
truthy_items = [x for x in items if x]
# [1, "hello", [1], True]

# Using filter - O(n)
truthy_items = list(filter(bool, items))
# Same result, O(n)
```

### Boolean Lists

```python
# O(n) - convert each element
values = [0, 1, 2, 3, 0, 5]
bools = [bool(x) for x in values]
# [False, True, True, True, False, True]

# Using map - O(n)
bools = list(map(bool, values))
# Same result
```

## Performance Patterns

### Checking Container Emptiness

```python
# All O(1) with __len__
items = [1, 2, 3]

if items:              # O(1) - uses __len__()
    pass

if len(items) > 0:     # O(1) - explicit
    pass

if len(items) != 0:    # O(1) - also explicit
    pass

# Idiomatic - let Python do implicit bool
if items:              # Best
    pass
```

### vs Explicit Comparisons

```python
obj = [1, 2, 3]

# Truthiness - O(1) for built-in types, else __bool__() or __len__()
if obj:
    pass

# None check - O(1) for any type, but a different question:
# an empty list is not None
if obj is not None:
    pass

# len() - for a type with no __bool__(), the same __len__() call
# that `if obj:` makes
if len(obj) > 0:
    pass
```

## Practical Examples

### Default Parameter Handling

```python
# O(1) - check if argument provided
default_value = 10

def process(value=None):
    if value is None:  # O(1)
        value = default_value
    return value

process(0)  # 0 - `if not value:` would replace it with 10

# With optional list
def extend_list(items=None):
    if items is None:  # O(1)
        items = []
    return items
```

### Validation

```python
# O(1) - check required fields
def validate_data(data):
    if not data:       # O(1) - check if dict is empty
        raise ValueError("Data required")
    
    required_fields = ["id", "name"]
    for field in required_fields:
        if not data.get(field):  # O(1) - get and check
            raise ValueError(f"{field} required")
```

### Boolean Aggregation

```python
# O(n) - check multiple conditions
items = [1, 2, 3, 4, 5]

# Check if any item is truthy (short-circuits)
if any(items):  # Stops at the first truthy item - here the first
    pass

# Check if all items are truthy
if all(items):  # O(n) - checks all
    pass

# With conditions
if any(x > 10 for x in items):  # O(n) or early exit
    pass

if all(x > 0 for x in items):   # O(n) or early exit
    pass
```

## Edge Cases

### Empty vs None vs False

```python
# All falsy, but different
bool(None)   # False - no value
bool([])     # False - empty container
bool(False)  # False - explicit false
bool("")     # False - empty string

# All truthy
bool([0])    # True - non-empty
bool([None]) # True - non-empty
bool([False])# True - non-empty
```

### Custom Falsy Objects

```python
# O(1) - return False from __bool__
class AlwaysFalse:
    def __bool__(self):
        return False

obj = AlwaysFalse()
bool(obj)  # False

# But object exists
if obj:    # False
    pass

if obj is not None:  # True - object exists!
    pass
```

### Division by Zero Check

```python
# O(1) - check for zero before division
divisor = 4

if divisor:  # O(1) - checks if non-zero
    result = 100 / divisor
else:
    result = None

# vs explicit check
if divisor != 0:     # O(1)
    result = 100 / divisor
```

## Best Practices

✅ **Do**:

- Use implicit truthiness: `if items:` not `if len(items) > 0:`
- Check `is None` explicitly: `if value is None:` not `if not value:`
- Use `bool()` to convert to boolean explicitly when needed
- Define `__bool__()` on a class whose `__len__()` is expensive, so truth tests skip `__len__()`

❌ **Avoid**:

- Confusing empty with False: `[]` and `False` are both falsy but different
- Using `bool()` unnecessarily in conditions
- Assuming all falsy values are False
- Complex `__bool__()` implementations (should be O(1))

## Version Notes

- **Python 2.x**: Works with `__nonzero__()` instead of `__bool__()`
- **Python 3.x**: Uses `__bool__()` method
- **Python 3.14+**: `bool(NotImplemented)` raises `TypeError`; 3.10 to 3.13 return `True` with a `DeprecationWarning`
- **All versions**: Falsy values consistent (None, False, 0, "", [], {}, etc.)

## Related Functions

- **[all()](all.md)** - Check if all items are truthy
- **[any()](any.md)** - Check if any item is truthy
- **[len()](len.md)** - Get container length
- **[bool type](bool.md)** - Boolean type documentation
