# True Constant Complexity

The `True` constant is one of Python's two boolean values, representing a true condition. It's a singleton instance of the `bool` type.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Comparison | O(1) | O(1) | Uses `is` operator |
| Truthiness test | O(1) | O(1) | Always truthy |
| Type check | O(1) | O(1) | `type(True)` |
| Conversion | O(1) | O(1) | `bool(x)` |
| Assignment | O(1) | O(1) | Single object |

## Basic Usage

### Boolean Value

```python
# O(1) - True is a singleton
flag = True

# Use in conditions
if flag:  # O(1) - tests truthiness
    print("Condition is true")

# Explicit comparison (redundant)
if flag is True:  # O(1) - identity check
    print("Explicitly True")

# vs truthiness check (preferred)
if flag:  # O(1) - clearer, preferred
    print("Truthy value")
```

### Boolean Conversion

```python
# O(1) - convert to boolean
values = [0, 1, "", "text", [], [1], None, True, False]

# O(1) - convert each
bools = [bool(x) for x in values]
# [False, True, False, True, False, True, False, True, False]

# Direct boolean values
print(bool(True))   # True
print(bool(False))  # False
```

### Return Values

```python
# O(1) - return boolean
def is_valid(data):
    if isinstance(data, dict) and len(data) > 0:
        return True  # O(1)
    return False  # O(1)

# O(1) - use result
result = is_valid({'key': 'value'})
if result:
    print("Valid")
```

## Complexity Details

### Singleton Pattern

```python
# O(1) - True is a singleton
true1 = True
true2 = True

# Both refer to same object
print(true1 is true2)  # True - O(1)
print(id(true1) == id(true2))  # True - O(1)

# Cannot create new True instances
# True = False  # NameError in Python 3
```

### Type System

```python
# O(1) - True is instance of bool
value = True

# Type checking
type(value)  # <class 'bool'> - O(1)
isinstance(value, bool)  # True - O(1)
isinstance(value, int)  # True - O(1) bool subclasses int!

# Integer value
int(True)  # 1 - O(1)
```

### Truthiness vs Identity

```python
# O(1) - multiple ways to check
value = True

# Truthiness check (most common)
if value:  # O(1) - uses __bool__
    print("Truthy")

# Identity check
if value is True:  # O(1) - fastest
    print("Exactly True")

# Equality check
if value == True:  # O(1) but slower
    print("Equals True")

# Type check
if type(value) is bool:  # O(1)
    print("Is bool type")

# Use first form (truthiness) unless exact True needed
```

## Performance Patterns

### Boolean Operations

```python
# O(1) - boolean logic
a = True
b = False

# Logical AND
result = a and b  # False - O(1)

# Logical OR
result = a or b  # True - O(1)

# Logical NOT
result = not a  # False - O(1)

# Short-circuit evaluation
result = True or some_expensive_function()  # O(1) - function not called!
```

### Comparison Operations

```python
# O(1) - comparison returns boolean
x = 5

# Comparison creates boolean
result = x > 3  # True - O(1)
result = x < 3  # False - O(1)
result = x == 5  # True - O(1)

# Chain comparisons
result = 3 < x < 10  # True - O(1)
```

### vs Explicit Returns

```python
# Less efficient
def is_positive_verbose(x):
    if x > 0:
        return True  # O(1)
    else:
        return False  # O(1)

# More efficient
def is_positive(x):
    return x > 0  # O(1) - returns boolean directly

# Both O(1) but second is cleaner
result1 = is_positive_verbose(5)  # True
result2 = is_positive(5)  # True
```

## Common Use Cases

### Condition Testing

```python
# O(1) - use True in conditions
def process(data, debug=False):
    if debug is True or debug == 1:  # O(1)
        print("Debug mode")
    
    # vs preferred
    if debug:  # O(1) - cleaner
        print("Debug mode")

# O(1) - call
process([1, 2, 3], debug=True)
```

### Boolean Flags

```python
# O(1) - track state with boolean
class Application:
    def __init__(self):
        self.running = False
        self.paused = False
        self.debug = True
    
    def start(self):
        self.running = True  # O(1)
    
    def pause(self):
        self.paused = True  # O(1)
    
    def toggle_debug(self):
        self.debug = not self.debug  # O(1)

app = Application()
app.start()  # O(1)
print(app.running)  # True
```

### List Comprehension Filter

```python
# O(n) - filter with boolean
items = [1, 2, 3, 4, 5]

# Filter items > 2
filtered = [x for x in items if x > 2]  # O(n)
# [3, 4, 5]

# More complex filter
def is_even(x):
    return x % 2 == 0  # O(1) returns boolean

evens = [x for x in items if is_even(x)]  # O(n)
# [2, 4]
```

### Default Arguments

```python
# O(1) - boolean default
def configure(verbose=False, debug=False):
    if verbose:  # O(1)
        print("Verbose mode")
    
    if debug:  # O(1)
        print("Debug mode")

# O(1) - call with defaults
configure()  # No output
configure(verbose=True)  # Prints "Verbose mode"
```

### Boolean Collections

```python
# O(n) - work with boolean collections
flags = [True, False, True, False, True]

# O(n) - check if all true
all_true = all(flags)  # False

# O(n) - check if any true
any_true = any(flags)  # True

# O(n) - count true values
true_count = sum(flags)  # 3 (True == 1)

# O(n) - find true values
true_indices = [i for i, x in enumerate(flags) if x]
# [0, 2, 4]
```

## Advanced Usage

### Type Annotations

```python
# O(1) - use bool in type hints
def is_valid(data: dict) -> bool:
    """Check if data is valid - O(1)"""
    return len(data) > 0

# O(1) - call
result: bool = is_valid({'key': 'value'})
```

### Boolean as Integer

```python
# O(1) - True is 1, False is 0
print(True == 1)   # True
print(False == 0)  # True

# O(1) - use in arithmetic
count = 5
if valid:
    count += True  # count += 1

# O(1) - sum booleans (count True values)
items = [True, False, True, True]
total = sum(items)  # 3
```

### Ternary Operation

```python
# O(1) - conditional expression with boolean
value = 10
result = "positive" if value > 0 else "non-positive"
# "positive"

# vs explicit boolean
is_positive = value > 0  # True
result = "positive" if is_positive else "non-positive"
```

## Practical Examples

### State Machine

```python
# O(1) - state tracking with booleans
class Door:
    def __init__(self):
        self.is_open = False
        self.is_locked = True
    
    def unlock(self):
        self.is_locked = False  # O(1)
    
    def open(self):
        if self.is_locked:  # O(1)
            raise ValueError("Door is locked")
        self.is_open = True  # O(1)

# O(1) - use state machine
door = Door()
door.unlock()  # O(1)
door.open()    # O(1)
```

### Validation

```python
# O(n) - validate with boolean checks
def validate_password(password):
    """Validate password - O(n)"""
    has_upper = any(c.isupper() for c in password)  # O(n)
    has_lower = any(c.islower() for c in password)  # O(n)
    has_digit = any(c.isdigit() for c in password)  # O(n)
    has_length = len(password) >= 8  # O(1)
    
    # O(1) - combine checks
    is_valid = has_upper and has_lower and has_digit and has_length
    
    return is_valid

# O(n) - validate
valid = validate_password("MyPass123")  # True
```

### Configuration Flags

```python
# O(1) - use booleans for configuration
class Settings:
    def __init__(self):
        self.enable_cache = True
        self.enable_logging = False
        self.enable_compression = True
    
    def should_cache(self):
        return self.enable_cache  # O(1)

settings = Settings()

# O(1) - check flags
if settings.enable_logging:  # O(1)
    print("Logging enabled")

# O(1) - conditional logic
cache_enabled = settings.should_cache()
```

## Edge Cases

### Implicit Boolean Conversion

```python
# O(1) - implicit conversion in conditions
value = 5

if value:  # Converts to boolean: True - O(1)
    print("Non-zero is truthy")

# vs explicit
if bool(value):  # O(1) explicit conversion
    print("Truthy")

# Falsy values: None, False, 0, "", [], {}, etc.
falsy_values = [None, False, 0, "", [], {}]

# O(n) - all are falsy
for val in falsy_values:
    print(f"{val!r} is falsy: {not bool(val)}")
```

### Boolean as Index

```python
# O(1) - use boolean as list index (True=1, False=0)
values = ["first", "second"]

index = True
print(values[index])  # "second" (True == 1)

index = False
print(values[index])  # "first" (False == 0)

# O(1) - dictionary key
data = {True: "yes", False: "no"}
print(data[True])   # "yes"
print(data[False])  # "no"
```

### Comparison Chains

```python
# O(1) - chain with booleans
x = 5
result = 0 < x <= 10 and True  # True

# Multiple booleans
a = True
b = True
c = False

result = a and b or c  # True (short-circuit evaluation)
```

## Performance Considerations

### Short-Circuit Evaluation

```python
# O(1) - AND short-circuits on False
result = False and expensive_function()  # Function not called!

# O(1) - OR short-circuits on True
result = True or expensive_function()  # Function not called!

# Leverage this for efficiency
if user_exists and is_admin:  # Checks user_exists first
    grant_access()
```

## Best Practices

✅ **Do**:

- Use boolean values for flags and conditions
- Return boolean from validation functions
- Use truthiness checks in conditions
- Use short-circuit evaluation for efficiency
- Use `and`/`or` for boolean logic
- Use in type hints: `-> bool`

❌ **Avoid**:

- Returning 1/0 instead of True/False
- Explicit `is True` checks (use truthiness)
- Complex boolean expressions without parentheses
- Using `== True` (just use the value)
- Confusing boolean True with truthy values
- Unnecessary boolean intermediate variables

## Related Constants

- **[False](false.md)** - Boolean false value
- **[None](none.md)** - Null value
- **[NotImplemented](notimplemented.md)** - Not implemented marker
- **[bool type](bool.md)** - Boolean type

## Version Notes

- **Python 2.x**: `True` and `False` are singletons (could be reassigned)
- **Python 3.x**: `True` and `False` are keywords, cannot be reassigned
- **All versions**: `bool` subclasses `int` (True == 1, False == 0)
