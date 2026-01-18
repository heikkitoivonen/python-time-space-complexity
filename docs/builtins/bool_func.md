# bool() Function Complexity

The `bool()` function converts an object to a boolean value using truthiness evaluation.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert primitive (int, str, etc) | O(1) | O(1) | Direct truth value |
| Convert container | O(1) | O(1) | Checks if non-empty via `__len__()` |
| Call `__bool__()` | O(k) | O(1) | k = method complexity (usually O(1)) |
| Call `__len__()` | O(1) | O(1) | Built-in containers store length |

*Note: For built-in types (list, dict, set, etc.), `__len__()` is O(1) because the length is cached. Custom containers with expensive `__len__()` implementations would be slower.*

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
# O(m) - depends on __bool__() implementation

class Expensive:
    def __init__(self, data):
        self.data = data
    
    def __bool__(self):
        # O(n) - iterates through data
        return any(self.data)

obj = Expensive([1, 2, 3])
bool(obj)  # O(n) - calls __bool__

# Without __bool__, would use __len__() - O(1)
class Efficient:
    def __init__(self, data):
        self.data = data
    
    def __len__(self):
        # O(1) - quick
        return len(self.data)

obj = Efficient([1, 2, 3])
bool(obj)  # O(1) - calls __len__()
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

# O(1) - all other values are truthy:
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

# Fastest - let Python do implicit bool
if items:              # Best
    pass
```

### vs Explicit Comparisons

```python
# O(1) - bool conversion
if bool(obj):          # O(1)
    pass

# vs explicit comparison
if obj != None:        # O(1)
    pass

if obj is not None:    # O(1)
    pass

# vs using __len__
if len(obj) > 0:       # O(n) for some types
    pass
```

## Practical Examples

### Default Parameter Handling

```python
# O(1) - check if argument provided
def process(value=None):
    if not value:      # O(1)
        value = default_value
    return value

# With optional list
def extend_list(items=None):
    if not items:      # O(1)
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
if any(items):  # O(1) - first truthy wins
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
bool(0)      # False (exception!)
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
divisor = get_value()

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
- Define `__bool__()` for custom classes (not `__len__()` alone)

❌ **Avoid**:

- Confusing empty with False: `[]` and `False` are both falsy but different
- Using `bool()` unnecessarily in conditions
- Assuming all falsy values are False
- Complex `__bool__()` implementations (should be O(1))

## Related Functions

- **[all()](all.md)** - Check if all items are truthy
- **[any()](any.md)** - Check if any item is truthy
- **[len()](len.md)** - Get container length
- **[bool type](bool.md)** - Boolean type documentation

## Version Notes

- **Python 2.x**: Works with `__nonzero__()` instead of `__bool__()`
- **Python 3.x**: Uses `__bool__()` method
- **All versions**: Falsy values consistent (None, False, 0, "", [], {}, etc.)
