# Boolean Type Complexity

The `bool` type is a subclass of `int` representing truth values: `True` and `False`. In CPython, `bool` is a subtype of `int` where `True == 1` and `False == 0`.

## Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `and` | O(1) | O(1) | Short-circuit AND |
| `or` | O(1) | O(1) | Short-circuit OR |
| `not` | O(1) | O(1) | Logical NOT |
| `==` | O(1) | O(1) | Equality comparison |
| `!=` | O(1) | O(1) | Inequality comparison |
| `<`, `>`, `<=`, `>=` | O(1) | O(1) | Numeric comparison |
| `bool(x)` | O(1) | O(1) | Conversion to bool |
| `hash(x)` | O(1) | O(1) | Hash value |
| `int(x)` | O(1) | O(1) | Convert to int |
| `str(x)` | O(1) | O(1) | String conversion |

## Logical Operations

| Operation | Time | Notes |
|-----------|------|-------|
| `x and y` | O(1) | Short-circuit: returns first falsy or last value |
| `x or y` | O(1) | Short-circuit: returns first truthy or last value |
| `not x` | O(1) | Logical negation |

### Short-circuit Evaluation

```python
# 'and' operator - stops at first False
x = False and expensive_function()  # expensive_function() NOT called
y = True and expensive_function()   # expensive_function() IS called

# 'or' operator - stops at first True
a = True or expensive_function()    # expensive_function() NOT called
b = False or expensive_function()   # expensive_function() IS called

# Returns actual values, not True/False
result = "hello" or "world"         # "hello"
result = "" or "world"              # "world"
result = 5 and 10                   # 10
result = 0 and 10                   # 0
```

## Boolean Context

| Value | Boolean Context | Notes |
|-------|-----------------|-------|
| `True` | Truthy | |
| `False` | Falsy | |
| `0` | Falsy | Any numeric zero |
| Non-zero numbers | Truthy | |
| `""` (empty string) | Falsy | |
| Non-empty string | Truthy | |
| `[]` (empty list) | Falsy | |
| Non-empty list | Truthy | |
| `None` | Falsy | |
| Custom objects | Depends | Implements `__bool__` or `__len__` |

```python
# Truth value testing - O(1) for built-ins
if []:               # False - empty list
    pass
if [1, 2, 3]:        # True - non-empty
    pass
if "":               # False - empty string
    pass
if "hello":          # True - non-empty
    pass
if None:             # False - always
    pass
```

## Comparison Operations

```python
# Bool values are integers: True == 1, False == 0
print(True == 1)     # True
print(False == 0)    # True
print(True > False)  # True (1 > 0)

# Comparisons with other types
print(True == "True")     # False (different types)
print(True is True)       # True (cached singleton)
print(False is False)     # True (cached singleton)
```

## Common Usage Patterns

### Conditional Expressions

```python
# Simple condition - O(1)
if condition:
    result = value_if_true
else:
    result = value_if_false

# Ternary operator - O(1)
result = value_if_true if condition else value_if_false

# Short-circuit with 'and'/'or' - O(1)
result = condition and value_if_true or value_if_false
```

### Boolean Aggregation

```python
# Check if all conditions are true
if x > 0 and y > 0 and z > 0:  # O(n) worst-case (all evaluated)
    pass

# Using all() - O(n) but short-circuits
if all([x > 0, y > 0, z > 0]):
    pass

# Check if any condition is true
if x > 0 or y > 0 or z > 0:   # O(n) worst-case
    pass

# Using any() - O(n) but short-circuits
if any([x > 0, y > 0, z > 0]):
    pass
```

### Truthiness in Data Filtering

```python
# Filter falsy values - O(n) for n items
items = [1, 0, 2, None, 3, "", 4, []]
truthy = [x for x in items if x]  # O(n)
# Result: [1, 2, 3, 4]

# Check if all items are truthy
has_all = all(items)  # O(n) but short-circuits
```

## Boolean Caching

In CPython, `True` and `False` are singleton objects:

```python
# Booleans are cached
a = True
b = True
print(a is b)  # True - same object!

# This is guaranteed by language
print(True is True)   # Always True
print(False is False) # Always True

# But True == 1 and False == 0
print(True == 1)      # True
print(True is 1)      # False - different types
```

## Performance Characteristics

### Boolean Operations Speed

```python
import timeit

# All boolean operations are very fast - O(1)
timeit.timeit('x = True and False', number=1000000)
timeit.timeit('x = True or False', number=1000000)
timeit.timeit('x = not True', number=1000000)
```

### Short-circuit Optimization

```python
# Good: short-circuits prevent function calls
condition = False
result = condition and expensive_operation()  # expensive_operation() NOT called

# Bad: always evaluates both sides
result = condition & expensive_operation()    # bitwise AND, not short-circuit
```

## Version Notes

- **Python 2.x**: `bool` type introduced in Python 2.3
- **Python 3.x**: `bool` is consistently a subclass of `int`
- **All versions**: `True` and `False` are singleton objects

## Related Types

- **[Int](int.md)** - Parent class of bool
- **[None](none.md)** - Also falsy in boolean context

## Best Practices

✅ **Do**:

- Use short-circuit operators (`and`, `or`) for performance
- Use `all()` and `any()` for collections
- Compare with `True`/`False` explicitly when needed
- Rely on truthiness for simple conditions

❌ **Avoid**:

- `if x == True:` when `if x:` suffices
- `if x == False:` when `if not x:` suffices
- Mixing `and`/`or` without clear precedence
- Bitwise operators (`&`, `|`) for boolean logic
