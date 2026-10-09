# any() Function Complexity

The `any()` function returns `True` if any item in an iterable is truthy.

`n` is the number of items the iterable yields and `k` is the position of the
first truthy one. Producing one item and testing its truth are treated as
O(1); with a generator expression, the expression's own work is part of
producing the item.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| First item truthy | O(1) | O(1) | Early exit immediately |
| Early exit (truthy found) | O(k) | O(1) | k = position of first truthy item |
| All items falsy | O(n) | O(1) | Must check all items |
| Empty iterable | O(1) | O(1) | Returns False immediately |

## Basic Usage

### Checking Any True

```python
# O(k) where k = position of first truthy
numbers = [0, 0, 1, 2, 3]
result = any(numbers)  # True - stops at 1

# Early exit
numbers = [0, 0, 0, 0, 5]
result = any(numbers)  # True - stops at 5

# All falsy - O(n)
result = any([0, False, None, "", []])  # False - checks all
```

### With Conditions

```python
# O(k) where k = position of first match, each predicate is O(1)
numbers = [1, 2, 3, 4, 5]
result = any(x > 3 for x in numbers)  # True - stops at 4

# Early exit when condition met
result = any(x > 2 for x in numbers)  # True - stops at 3 (index 2)
```

## Performance Patterns

### Short-Circuit Evaluation

```python
def expensive_function():
    return False

# ✅ O(1) - stops immediately at first truthy
checks = [lambda: True, expensive_function, expensive_function]
result = any(check() for check in checks)
# expensive_function() is never called

# ❌ O(n) - evaluates all
result = any([True] + [expensive_function() for _ in range(1000)])
# Calls expensive_function() 1000 times

# ✅ O(k) - generator stops early
result = any(x > 100 for x in range(10**9))
# Stops after checking 102 items (0 through 101)
```

### Generator Efficiency

```python
# O(k) - lazy evaluation with early exit
numbers = range(10**6)
result = any(x > 10**5 for x in numbers)
# Stops after checking 10**5 + 2 items

# vs list comprehension - O(n)
result = any([x > 10**5 for x in numbers])
# Builds all 10**6 results first
```

## Common Patterns

### Checking If Value Exists

```python
# O(k) - stops at first match
items = [1, 2, 3, 4, 5]
result = any(x == 3 for x in items)  # True - stops at 3

# Equivalent to:
result = 3 in items  # O(k) - same scan, more readable
```

### Validation with Early Exit

```python
# O(k) - stops at the first non-int; O(n) when every item is an int
def has_invalid_item(items):
    return any(not isinstance(item, int) for item in items)

valid = has_invalid_item([1, 2, 3, 4, 5])  # False - checks all
invalid = has_invalid_item([1, 2, "three"])  # True - stops at "three"
```

### Checking Conditions

```python
# O(k) - stops when condition met
numbers = [2, 4, 6, 8, 10]
has_odd = any(x % 2 == 1 for x in numbers)  # False - checks all

numbers = [2, 4, 5, 8, 10]
has_odd = any(x % 2 == 1 for x in numbers)  # True - stops at 5
```

## Comparison with all()

```python
# any() - True if any are truthy
any([False, False, False])  # False
any([False, True, False])   # True
any([])                     # False

# all() - True if all are truthy
all([True, True, True])     # True
all([True, False, True])    # False
all([])                     # True
```

## Edge Cases

### Empty Iterable

```python
# O(1) - returns False immediately
any([])  # False
any(())  # False
any(set())  # False
any(x for x in [])  # False

# This is correct (empty set has no truthy members)
```

### Single Item

```python
# O(1) - checks one item
any([True])   # True
any([False])  # False
any([1])      # True - truthy
any([0])      # False - falsy
```

### Different Types

```python
# O(k) - stops at first truthy
any([0, "", None])  # False - all falsy
any([0, "", 1])     # True - stops at 1

any([False, [], {}, "hello"])  # True - stops at "hello"
```

## Performance Considerations

### vs Loop

```python
numbers = [5, 50, 500, 5000]

# any() - O(k)
result = any(x > 100 for x in numbers)

# Manual loop - O(k) same complexity
result = False
for x in numbers:
    if x > 100:
        result = True
        break

# any() is preferred - same O(k), and shorter
```

### vs in Operator

```python
# Check if value exists
items = [1, 2, 3, 4, 5]

# O(k) - early exit
result = any(x == 3 for x in items)

# O(k) - same scan, more readable
result = 3 in items

# any() is useful for complex conditions:
result = any(x > 3 for x in items)  # Condition
words = ["kiwi", "apple", "plum"]
result = any(w.startswith("a") for w in words)  # Complex check
```

### vs "or" Operator

```python
def expensive1():
    return True

def expensive2():
    return False

def expensive3():
    return False

condition1, condition2, condition3 = 0, "yes", None

# Same truthiness as the or-chain below
result = any([condition1, condition2, condition3])  # True

# or returns the first truthy operand itself, not a bool
result = condition1 or condition2 or condition3  # "yes"

# A list is built before any() runs, so every call is made:
result = any([expensive1(), expensive2(), expensive3()])  # Evaluates all

# Generator version stops early:
result = any(f() for f in [expensive1, expensive2, expensive3])
```

## Best Practices

✅ **Do**:

- Use `any()` to check if any item meets a condition
- Use generator expressions with `any()` for lazy evaluation
- Remember `any([])` returns `False`
- Use for early exit with expensive checks

❌ **Avoid**:

- Creating lists with comprehensions (use generators)
- Using `any()` when `in` operator is clearer
- Unnecessary nesting in conditions
- Forgetting short-circuit behavior

## Version Notes

- **All Python 3**: Stops at the first truthy item and leaves the rest of an iterator unconsumed

## Related Functions

- **[all()](all.md)** - Check if all items are truthy
- **[filter()](filter.md)** - Filter items based on predicate
- **[Builtins overview](index.md)** - Membership testing with `in` across built-in types
