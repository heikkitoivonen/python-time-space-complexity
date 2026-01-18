# False Constant Complexity

The `False` constant is one of Python's two boolean values, representing a false condition. It's a singleton instance of the `bool` type with integer value 0.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Comparison | O(1) | O(1) | Uses `is` operator |
| Truthiness test | O(1) | O(1) | Always falsy |
| Type check | O(1) | O(1) | `type(False)` |
| Conversion | O(1) | O(1) | `bool(x)` |
| Assignment | O(1) | O(1) | Single object |

## Basic Usage

### Boolean Value

```python
# O(1) - False is a singleton
flag = False

# Use in conditions
if not flag:  # O(1) - inverts truthiness
    print("Condition is false")

# Explicit comparison (redundant)
if flag is False:  # O(1) - identity check
    print("Explicitly False")

# vs truthiness check (preferred)
if not flag:  # O(1) - clearer, preferred
    print("Falsy value")
```

### Boolean Conversion

```python
# O(1) - convert to boolean
values = [0, 1, "", "text", [], [1], None, True, False]

# O(1) - convert each (False for empty, falsy values)
bools = [bool(x) for x in values]
# [False, True, False, True, False, True, False, True, False]

# Direct boolean values
print(bool(False))  # False
print(bool(0))      # False
print(bool(""))     # False
print(bool([]))     # False
```

### Default Return Value

```python
# O(1) - return False for failure
def check_permissions(user):
    if user is None:  # O(1)
        return False  # O(1)
    
    if not user.is_admin:  # O(1)
        return False  # O(1)
    
    return True  # O(1)

# O(1) - use result
if not check_permissions(user):
    print("Access denied")
```

## Complexity Details

### Singleton Pattern

```python
# O(1) - False is a singleton
false1 = False
false2 = False

# Both refer to same object
print(false1 is false2)  # True - O(1)
print(id(false1) == id(false2))  # True - O(1)

# Cannot create new False instances
# False = True  # NameError in Python 3
```

### Type System

```python
# O(1) - False is instance of bool
value = False

# Type checking
type(value)  # <class 'bool'> - O(1)
isinstance(value, bool)  # True - O(1)
isinstance(value, int)  # True - O(1) bool subclasses int!

# Integer value
int(False)  # 0 - O(1)
```

### Falsy vs Identity

```python
# O(1) - multiple ways to check
value = False

# Truthiness check (most common)
if not value:  # O(1) - uses __bool__
    print("Falsy")

# Identity check
if value is False:  # O(1) - fastest for exact False
    print("Exactly False")

# Equality check
if value == False:  # O(1) but slower
    print("Equals False")

# Type check
if type(value) is bool:  # O(1)
    print("Is bool type")

# Truthiness check is preferred
```

## Performance Patterns

### Boolean Logic

```python
# O(1) - boolean logic operations
a = True
b = False

# Logical AND (False if either is False)
result = a and b  # False - O(1)

# Logical OR (False only if both are False)
result = a or b  # True - O(1)

# Logical NOT
result = not b  # True - O(1)

# Short-circuit: if first is False, second not evaluated
result = False and expensive_function()  # O(1) - function not called
```

### Negation

```python
# O(1) - negate boolean
flag = True

# Invert
flag = not flag  # False - O(1)

# Toggle pattern
flag = not flag  # True - O(1)
flag = not flag  # False - O(1)

# vs assignment
enabled = False  # O(1)
enabled = True   # O(1)
```

## Common Use Cases

### Flags and Controls

```python
# O(1) - use False for disabled/off state
class Feature:
    def __init__(self):
        self.enabled = False  # O(1)
        self.verbose = False  # O(1)
        self.debug = False    # O(1)
    
    def enable(self):
        self.enabled = True  # O(1)
    
    def disable(self):
        self.enabled = False  # O(1)

# O(1) - manage features
feature = Feature()

if not feature.enabled:  # O(1) - check it's disabled
    feature.enable()  # O(1)
```

### Validation Results

```python
# O(n) - validate with boolean result
def is_valid_email(email):
    """Validate email format - O(n)"""
    if '@' not in email:  # O(n)
        return False  # O(1)
    
    if email.count('@') != 1:  # O(n)
        return False  # O(1)
    
    local, domain = email.split('@')  # O(n)
    
    if not local or not domain:  # O(1)
        return False  # O(1)
    
    if '.' not in domain:  # O(n)
        return False  # O(1)
    
    return True  # O(1)

# O(n) - validate
is_valid_email("bad@email")  # False
is_valid_email("user@example.com")  # True
```

### Conditional Execution

```python
# O(1) - conditional with False
SKIP_EXPENSIVE_OPERATION = False

def process(data):
    if not SKIP_EXPENSIVE_OPERATION:  # O(1)
        result = expensive_computation(data)  # O(exp)
    else:
        result = None
    
    return result

# O(1) when skipped, O(exp) otherwise
```

### Collection Filtering

```python
# O(n) - filter with boolean predicate
items = [1, 2, 3, 4, 5]

def is_odd(x):
    return x % 2 != 0  # Returns boolean: True or False

# O(n) - filter using predicate
odd_items = [x for x in items if is_odd(x)]
# [1, 3, 5]

# O(n) - filter using lambda returning False
even_items = [x for x in items if x % 2 == 0]
# [2, 4]
```

### Default Arguments

```python
# O(1) - False as default
def save_file(path, overwrite=False):
    if overwrite is False:  # O(1)
        if file_exists(path):  # O(1)
            raise ValueError("File exists")
    
    with open(path, 'w') as f:  # O(file)
        f.write(data)

# O(1) - call with default
save_file("data.txt")  # Raises if exists

# O(1) - override default
save_file("data.txt", overwrite=True)  # Overwrites
```

## Advanced Usage

### Type Annotations

```python
# O(1) - use bool in type hints
def is_admin(user: User) -> bool:
    """Check if user is admin - O(1)"""
    return hasattr(user, 'admin_role')

# O(1) - variable annotation
is_valid: bool = False

# Later:
is_valid = True  # O(1)
```

### Assertion

```python
# O(1) - assertions with False
debug_mode = False

# Assertion passes (condition is True)
assert True, "This should pass"

# Assertion fails (condition is False)
# assert False, "This will raise AssertionError"

# Conditional assertion
if debug_mode:  # O(1)
    assert False, "Debug assertion"  # O(1)
```

### Boolean Algebra

```python
# O(1) - boolean algebra
a = True
b = False

# De Morgan's Laws
result1 = not (a and b)      # True
result2 = (not a) or (not b) # True
# Both are equivalent - O(1)

# Distributivity
result1 = (a or b) and True  # True
result2 = a or (b and True)  # True
# Both evaluate to - O(1)
```

## Practical Examples

### Feature Toggle

```python
# O(1) - feature flags
class FeatureFlags:
    def __init__(self):
        self.new_ui = False      # Disabled
        self.beta_features = False  # Disabled
        self.experimental = False  # Disabled
    
    def get(self, feature):
        return getattr(self, feature, False)  # O(1)

# O(1) - use flags
flags = FeatureFlags()

if not flags.new_ui:  # O(1)
    print("Using legacy UI")

# Enable feature
flags.new_ui = True  # O(1)
```

### Error Handling

```python
# O(1) - error indication
success = False

try:
    result = risky_operation()
    success = True  # O(1) - mark success
except Exception:
    success = False  # O(1) - mark failure

if not success:  # O(1)
    print("Operation failed")
```

### Lazy Initialization

```python
# O(1) - track initialization state
class Resource:
    def __init__(self):
        self._initialized = False
        self._data = None
    
    def initialize(self):
        if not self._initialized:  # O(1)
            self._data = load_data()  # O(load)
            self._initialized = True  # O(1)
    
    def get_data(self):
        if not self._initialized:  # O(1)
            self.initialize()
        return self._data

# O(1) or O(load) - depending on initialization state
```

## Edge Cases

### Falsy Values

```python
# O(1) - distinguish False from other falsy values
false_value = False
none_value = None
zero_value = 0
empty_string = ""
empty_list = []

# All are falsy
falsy_values = [False, None, 0, "", []]

# O(n) - check which are falsy
for val in falsy_values:
    print(f"{val!r} is falsy: {not val}")

# But only False is False
print(False is False)  # True
print(0 is False)      # False - different objects!
print(None is False)   # False
print("" is False)     # False
```

### Boolean in Arithmetic

```python
# O(1) - False is 0 in arithmetic
count = 0

# O(1) - add/subtract booleans
if condition:
    count += True  # count += 1
else:
    count += False  # count += 0

# O(1) - multiply by boolean
result = 100 * False  # 0
result = 100 * True   # 100
```

### Dictionary with False Keys

```python
# O(1) - False as dictionary key
data = {True: "yes", False: "no", 0: "zero", 1: "one"}

# False and 0 are equal but same key!
print(data[False])  # "no" or "zero"? (False == 0)
print(data[0])      # "no" or "zero"?

# Both refer to same key (False == 0)
# Last assignment wins
data = {False: "no"}
print(data[0])  # "no" - O(1)
```

## Performance Considerations

### Short-Circuit with False

```python
# O(1) - AND with False short-circuits
result = False and expensive_function()  # O(1) - function not called!

# O(1) - OR with non-False continues
result = False or expensive_function()  # O(exp) - function is called

# Leverage for conditional expensive operations
if cache_valid and not force_refresh:  # O(1) if cache_valid is False
    use_cache()
```

## Best Practices

✅ **Do**:

- Use False for disabled/off/no states
- Return False for failed validations
- Use in type hints: `-> bool`
- Use `if not value:` for falsy checks
- Use False in boolean expressions
- Use short-circuit evaluation

❌ **Avoid**:

- Confusing False with other falsy values
- Using `== False` (just use `not value`)
- Using `is False` except when checking exact type
- Returning 0 instead of False
- Complex boolean expressions without parentheses
- Using False for values that could be None

## Related Constants

- **[True](true.md)** - Boolean true value
- **[None](none.md)** - Null value
- **[NotImplemented](notimplemented.md)** - Not implemented marker
- **[bool type](bool.md)** - Boolean type

## Version Notes

- **Python 2.x**: `True` and `False` are singletons (could be reassigned)
- **Python 3.x**: `True` and `False` are keywords, cannot be reassigned
- **All versions**: `bool` subclasses `int` (True == 1, False == 0)
