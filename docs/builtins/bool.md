# Boolean Type Complexity

The `bool` type is a subclass of `int` representing truth values: `True` and `False`. They are its only two instances, and they compare and do arithmetic as the ints `1` and `0`.

Every operation in the operations tables is O(1) on `bool` operands, which take only two fixed values, so those rows have no size variable. Applied to other operands, `and`, `or`, `not` and `bool(x)` also pay for evaluating each operand and for one truth test per operand they examine; that truth test is O(1) for the built-in types (see [bool()](bool_func.md)).

## Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `and` | O(1) | O(1) | Short-circuit AND |
| `or` | O(1) | O(1) | Short-circuit OR |
| `not` | O(1) | O(1) | Logical NOT |
| `==` | O(1) | O(1) | Equality comparison |
| `!=` | O(1) | O(1) | Inequality comparison |
| `<`, `>`, `<=`, `>=` | O(1) | O(1) | Numeric comparison |
| `&`, `\|`, `^` | O(1) | O(1) | Return a `bool` when both operands are; no short-circuit |
| `~x` | O(1) | O(1) | Returns the int `-2` or `-1`, not the negation; deprecated since 3.12 |
| `+`, `-`, `*` | O(1) | O(1) | Int arithmetic; the result is an `int` (`True + True == 2`) |
| `bool(x)` | O(1) | O(1) | Returns `x` itself when it is a `bool` |
| `hash(x)` | O(1) | O(1) | Hash value |
| `int(x)` | O(1) | O(1) | Convert to int |
| `str(x)` | O(1) | O(1) | String conversion |

## Logical Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x and y` | O(1) | O(1) | Short-circuit: returns first falsy or last value |
| `x or y` | O(1) | O(1) | Short-circuit: returns first truthy or last value |
| `not x` | O(1) | O(1) | Logical negation |

### Short-circuit Evaluation

```python
calls = 0

def expensive_function():
    global calls
    calls += 1
    return True

# 'and' operator - stops at the first falsy operand
x = False and expensive_function()  # expensive_function() NOT called
assert calls == 0
y = True and expensive_function()   # expensive_function() IS called
assert calls == 1

# 'or' operator - stops at the first truthy operand
a = True or expensive_function()    # expensive_function() NOT called
assert calls == 1
b = False or expensive_function()   # expensive_function() IS called
assert calls == 2

# Returns an operand, not necessarily True/False
assert ("hello" or "world") == "hello"
assert ("" or "world") == "world"
assert (5 and 10) == 10
assert (0 and 10) == 0
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
| Custom objects | Depends | `__bool__` if defined, else `__len__`; truthy if neither |

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
# All O(1) - a bool compares as the int 0 or 1
assert True == 1
assert False == 0
assert True > False  # 1 > 0

# Comparisons with other types
assert (True == "True") is False  # a str never equals a number
assert True is True               # the only True object
assert False is False             # the only False object
```

## Common Usage Patterns

### Conditional Expressions

```python
condition = True
value_if_true, value_if_false = "yes", "no"

# Simple condition - O(1)
if condition:
    result = value_if_true
else:
    result = value_if_false
assert result == "yes"

# Ternary operator - O(1)
result = value_if_true if condition else value_if_false
assert result == "yes"

# Short-circuit with 'and'/'or' - O(1), but wrong when value_if_true is falsy
result = condition and value_if_true or value_if_false
assert result == "yes"
assert (condition and 0 or "no") == "no"  # not 0
```

### Boolean Aggregation

n is the number of conditions.

```python
x, y, z = 1, -2, 3

# O(n) worst case - stops at the first false condition (y > 0 here)
if x > 0 and y > 0 and z > 0:
    pass

# O(n) always - the list evaluates every condition before all() sees one
if all([x > 0, y > 0, z > 0]):
    pass

# O(n) worst case - stops at the first true condition (x > 0 here)
if x > 0 or y > 0 or z > 0:
    pass

# O(n) always - the same holds for any() over a list
if any([x > 0, y > 0, z > 0]):
    pass
```

### Truthiness in Data Filtering

```python
# Filter falsy values - O(n) for n items
items = [1, 0, 2, None, 3, "", 4, []]
truthy = [x for x in items if x]  # O(n)
assert truthy == [1, 2, 3, 4]

# Check if all items are truthy - stops at the first falsy item (0 here)
has_all = all(items)
assert has_all is False
```

## Boolean Caching

`True` and `False` are the only two instances of `bool`, and the language guarantees it:

```python
# Every bool is one of the two objects
a = True
b = 1 > 0
assert a is b  # same object

# bool() returns one of them, never a new object
assert bool(1) is True
assert bool([]) is False

# But True == 1 and False == 0, as different types
assert True == 1
assert type(True) is not type(1)  # bool, not int
```

## Performance Characteristics

### Short-circuit Optimization

```python
calls = 0

def expensive_operation():
    global calls
    calls += 1
    return True

# Good: short-circuits prevent function calls
condition = False
result = condition and expensive_operation()  # expensive_operation() NOT called
assert calls == 0

# Bad: always evaluates both sides
result = condition & expensive_operation()    # bitwise AND, not short-circuit
assert calls == 1
```

## Best Practices

✅ **Do**:

- Use short-circuit operators (`and`, `or`) for performance
- Use `all()` and `any()` with a generator, so they can stop early
- Compare with `True`/`False` explicitly when needed
- Rely on truthiness for simple conditions

❌ **Avoid**:

- `if x == True:` when `if x:` suffices
- `if x == False:` when `if not x:` suffices
- Mixing `and`/`or` without clear precedence
- Bitwise operators (`&`, `|`) for boolean logic - they evaluate both sides
- `~x` to negate a bool - use `not x`

## Version Notes

- **Python 2.x**: `bool` type introduced in Python 2.3
- **Python 3.x**: `bool` is consistently a subclass of `int`
- **Python 3.12+**: `~` on a `bool` emits a `DeprecationWarning`
- **All versions**: `True` and `False` are singleton objects

## Related Types

- **[bool()](bool_func.md)** - Truth testing for any object
- **[Int](int.md)** - Parent class of bool
- **[None](none.md)** - Also falsy in boolean context
