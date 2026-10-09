# all() Function Complexity

The `all()` function returns `True` if all items in an iterable are truthy (or if the iterable is empty).

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| All items truthy | O(n) | O(1) | Must check all items |
| Early exit (falsy found) | O(k) | O(1) | k = position of first falsy item |
| Empty iterable | O(1) | O(1) | Returns True immediately |

n and k count the items all() receives. Producing them - the iterator's own
work, including any items it skips, and a generator expression's predicate -
and each item's truth test add their own cost on top.

## Basic Usage

### Checking All True

```python
# O(n) - must check all items
numbers = [1, 2, 3, 4, 5]
result = all(numbers)  # True - all truthy

# Early exit - O(k) where k = position of False
numbers = [1, 2, 0, 4, 5]
result = all(numbers)  # False - stops at 0

# Empty iterable
result = all([])  # True - all zero items are truthy
```

### With Conditions

```python
# O(n) where each predicate is O(1)
numbers = [1, 2, 3, 4, 5]
result = all(x > 0 for x in numbers)  # True

# Early exit - O(k) where k = position of first failure
result = all(x > 2 for x in numbers)  # False - stops at 1
```

## Performance Patterns

### Short-Circuit Evaluation

```python
def expensive_function():
    return sum(range(10_000)) > 0

# ✅ O(1) - stops immediately at first falsy
checks = [lambda: False, expensive_function, expensive_function]
result = all(check() for check in checks)
# expensive_function() is never called

# ❌ O(n) - evaluates all
result = all([False] + [expensive_function() for _ in range(1000)])
# Calls expensive_function() 1000 times

# ✅ O(k) - generator stops when predicate first fails
result = all(x < 100 for x in range(1000000))
# Stops after checking 101 items (0 through 100)
```

### Generator Efficiency

```python
# O(k) - lazy evaluation with early exit
large_range = range(10**7)
result = all(x < 100 for x in large_range)
# Stops after checking 101 items, however long the range

# vs list comprehension - O(n)
result = all([x < 100 for x in large_range])
# Builds the whole 10^7-item list first
```

## Common Patterns

### Validation

```python
# O(k) - stops at the first non-int; O(n) when every item is an int
def validate_data(items):
    return all(isinstance(item, int) for item in items)

valid = validate_data([1, 2, 3, 4, 5])  # True
valid = validate_data([1, 2, "three", 4, 5])  # False - stops at "three"
```

### Checking Conditions

```python
# O(n) - check all items meet condition
numbers = [2, 4, 6, 8, 10]
all_even = all(x % 2 == 0 for x in numbers)  # True

# Early exit
numbers = [2, 4, 5, 8, 10]
all_even = all(x % 2 == 0 for x in numbers)  # False - stops at 5
```

### Empty Sequence Handling

```python
# True for empty sequences
all([])  # True
all(())  # True
all(x > 0 for x in [])  # True

# Useful for "default to true" logic
def condition(x):
    return x > 0

items = []
result = all(condition(x) for x in items)  # True if items is empty
```

## Comparison with any()

```python
# all() - True if all are truthy
all([True, True, True])     # True
all([True, False, True])    # False
all([])                     # True

# any() - True if any are truthy
any([False, False, False])  # False
any([False, True, False])   # True
any([])                     # False
```

## Edge Cases

### Empty Iterable

```python
# O(1) - returns True immediately
all([])  # True
all(())  # True
all(set())  # True
all(x for x in [])  # True

# This is mathematically correct (vacuous truth)
# "All members of the empty set satisfy any property"
```

### Single Item

```python
# O(1) - checks one item
all([True])   # True
all([False])  # False
all([1])      # True - truthy
all([0])      # False - falsy
```

### Different Types

```python
# O(n) - checks truthiness of any type
all([1, "hello", [1, 2], {"key": "value"}])  # True - all truthy

all([1, "", [1, 2], {"key": "value"}])  # False - "" is falsy
```

## Performance Considerations

### vs Loop

```python
numbers = [1, 2, 3, 4, 5]

# all() - O(n), readable
result = all(x > 0 for x in numbers)

# Manual loop - O(n) same complexity
result = True
for x in numbers:
    if not (x > 0):
        result = False
        break

# all() is preferred - cleaner, same complexity
```

### vs any() Usage

```python
# Check if any item fails condition
numbers = [1, 2, 3, 4, 5]

# ✅ Clear intent - all pass condition
all(x > 0 for x in numbers)  # True

# ❌ Confusing - any fail condition
any(not (x > 0) for x in numbers)  # False

# ❌ Confusing - all fail condition
not any(x > 0 for x in numbers)  # False

# Use all() when checking "all meet condition"
# Use any() when checking "any meets condition"
```

## Best Practices

✅ **Do**:

- Use `all()` to check if all items meet a condition
- Use generator expressions with `all()` for lazy evaluation
- Remember `all([])` returns `True` (vacuous truth)
- Use short-circuit evaluation for expensive checks

❌ **Avoid**:

- Creating lists with comprehensions (use generators)
- Unnecessary nesting in conditions
- Using `all()` when checking just one item

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior

## Related Functions

- **[any()](any.md)** - Check if any item is truthy
- **[filter()](filter.md)** - Filter items based on predicate
