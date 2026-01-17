# all() Function Complexity

The `all()` function returns `True` if all items in an iterable are truthy (or if the iterable is empty).

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| All items truthy | O(n) | O(1) | Must check all items |
| Early exit (falsy found) | O(k) | O(1) | k = position of first falsy item |
| Empty iterable | O(1) | O(1) | Returns True immediately |

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
# ✅ O(1) - stops immediately at first falsy
result = all([False, expensive_function(), expensive_function()])
# Doesn't call expensive_function()

# ❌ O(n) - evaluates all
result = all([False] + [expensive_function() for _ in range(1000)])
# Calls expensive_function() 1000 times

# ✅ O(1) - generator stops early
result = all(x > 0 for x in range(1000000) if x < 0)
# Stops immediately when x < 0 is False
```

### Generator Efficiency

```python
# O(n) - lazy evaluation with early exit
large_list = range(10**9)
result = all(x < 100 for x in large_list)
# O(100) - stops after checking 100 items

# vs list comprehension
result = all([x < 100 for x in range(10**9)])
# O(10^9) - creates entire list first
```

## Common Patterns

### Validation

```python
# O(n*k) - validate all items
def validate_data(items):
    return all(isinstance(item, int) for item in items)

# O(n) early exit if any item is invalid
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
# all() - O(n), optimized, readable
result = all(x > 0 for x in numbers)

# Manual loop - O(n) same complexity
result = True
for x in numbers:
    if not (x > 0):
        result = False
        break

# all() is preferred - cleaner and same performance
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

## Related Functions

- **[any()](any.md)** - Check if any item is truthy
- **[filter()](filter.md)** - Filter items based on predicate
- **[all() with min()](max.md)** - Combining operations

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior
- **Python 3.8+**: Optimizations may improve performance
