# map() Function Complexity

The `map()` function applies a function to every item in an iterable and returns an iterator of results.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Mapping with function | O(n*k) | O(1)† | k = function time, † iterator only |
| Consuming iterator | O(n*k) | O(n) | If stored in list |
| Multiple iterables | O(n*k*m) | O(1)† | m = number of iterables |

## Basic Usage

### Simple Function Application

```python
# O(n) - iterator, doesn't consume yet
numbers = [1, 2, 3, 4, 5]
squared = map(lambda x: x**2, numbers)  # Iterator object

# O(n) - consumes iterator when needed
result = list(squared)  # [1, 4, 9, 16, 25]

# O(1) - creates iterator immediately
squared = map(int, ["1", "2", "3"])

# O(n) - consumed when iterating
for num in squared:
    print(num)
```

### Built-in Functions

```python
# O(n) - using built-in functions
strings = ["1", "2", "3"]
numbers = list(map(int, strings))  # [1, 2, 3]

floats = ["1.5", "2.5", "3.5"]
numbers = list(map(float, floats))  # [1.5, 2.5, 3.5]

strings = [1, 2, 3]
result = list(map(str, strings))  # ["1", "2", "3"]
```

## Performance Patterns

### Lazy Evaluation

```python
# O(1) - creates iterator, doesn't process yet
huge_list = range(10**9)
mapped = map(lambda x: x**2, huge_list)

# O(n) - only when you consume iterator
for i, val in enumerate(mapped):
    if i >= 10:
        break  # O(10) - only processed 10 items

# vs list comprehension
result = [x**2 for x in range(10**9)]  # O(10^9) and O(10^9) space!
```

### Multiple Iterables

```python
# O(n*k) where k = function time, n = min length
list1 = [1, 2, 3]
list2 = [4, 5, 6]
list3 = [7, 8, 9]

# O(n) - adds corresponding elements
sums = list(map(lambda a, b, c: a + b + c, list1, list2, list3))
# [(12, 15, 18)]
```

### Expensive Function

```python
# O(n*k) where k = function time
def expensive_operation(x):
    # O(m) where m = 10000
    return sum(range(x))

numbers = [1, 2, 3, 4, 5]
results = map(expensive_operation, numbers)  # O(1) - iterator created

# O(n*m) - when consumed
final = list(results)  # Expensive!
```

## Common Patterns

### Type Conversion

```python
# O(n*k) where k = conversion time
strings = ["1", "2", "3", "4", "5"]
integers = list(map(int, strings))  # O(n) conversion

floats = list(map(float, strings))  # O(n) conversion

# Alternative: list comprehension (same complexity)
integers = [int(s) for s in strings]  # O(n)
```

### Attribute Extraction

```python
# O(n) - simple attribute access
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

people = [
    Person("Alice", 30),
    Person("Bob", 25),
    Person("Charlie", 35),
]

# O(n) - extract names
names = list(map(lambda p: p.name, people))
# ["Alice", "Bob", "Charlie"]

# Better with operator module
from operator import attrgetter
names = list(map(attrgetter('name'), people))  # Same O(n)
```

### Chaining Operations

```python
# O(n) - each step is O(1) per element
numbers = [1, 2, 3, 4, 5]
result = map(lambda x: x**2, numbers)
result = map(lambda x: x + 1, result)  # Chained

# O(n) - consumed once
final = list(result)  # [2, 5, 10, 17, 26]

# vs multiple list comprehensions - same complexity but more memory
squared = [x**2 for x in numbers]  # O(n) time and space
incremented = [x + 1 for x in squared]  # O(n) time and space
# Total: O(n) time, O(n) space for intermediate list
```

## Comparison with Alternatives

### map vs List Comprehension

```python
# Both O(n*k) where k = function time
numbers = range(1000000)

# map - lazy, space efficient
result = map(lambda x: x**2, numbers)  # O(1) - iterator only
# Consume: O(n)

# List comprehension - eager
result = [x**2 for x in numbers]  # O(n) time, O(n) space

# For-loop
result = []
for x in numbers:
    result.append(x**2)  # O(n) time, O(n) space
```

### map vs for Loop

```python
# Same complexity, different style
numbers = [1, 2, 3, 4, 5]

# map - O(n) to create, O(n) to consume
squared = list(map(lambda x: x**2, numbers))

# for loop - O(n)
squared = []
for x in numbers:
    squared.append(x**2)

# List comprehension - O(n)
squared = [x**2 for x in numbers]

# All are O(n), map is lazy until consumed
```

## Multiple Iterables

### Parallel Processing

```python
# O(n*k) - processes corresponding elements
list1 = [1, 2, 3]
list2 = [10, 20, 30]

# O(n) - simple operation
results = list(map(lambda a, b: a + b, list1, list2))
# [11, 22, 33]

# Stops at shortest iterable
list3 = [100, 200]
results = list(map(lambda a, b: a + b, list1, list3))
# [101, 202] - stops when list3 ends
```

## Performance Considerations

### Large Datasets

```python
# ✅ Memory efficient - lazy evaluation
big_list = range(10**8)
squared = map(lambda x: x**2, big_list)
result = next(squared)  # Only computes one

# ❌ Memory expensive
big_list = range(10**8)
squared = [x**2 for x in big_list]  # Creates huge list
```

### Function Overhead

```python
# O(n) - built-in functions are optimized
numbers = ["1", "2", "3"]
result = list(map(int, numbers))  # Fast

# O(n*k) where k > 1 due to lambda overhead
result = list(map(lambda x: int(x), numbers))  # Slower

# Prefer direct function reference when possible
from operator import methodcaller
numbers = ["1", "2", "3"]
result = list(map(int, numbers))  # Best
```

## Edge Cases

### Empty Iterable

```python
# O(1) - creates empty iterator
result = map(lambda x: x**2, [])
final = list(result)  # [] - consumes immediately
```

### Single Element

```python
# O(1) - iterator created
result = map(lambda x: x**2, [5])
final = list(result)  # [25]
```

### Unequal Iterables

```python
# O(n) - stops at shortest
result = list(map(lambda a, b: a + b, [1, 2, 3], [10, 20]))
# [11, 22] - third element ignored
```

## Best Practices

✅ **Do**:

- Use `map()` for lazy evaluation with large datasets
- Use `map(function, iterable)` instead of `list(map(lambda x: function(x), iterable))`
- Use `map()` with built-in functions like `int`, `str`, `float`
- Use generator expressions for complex transformations

❌ **Avoid**:

- `list(map(lambda x: ..., iterable))` - use list comprehension instead
- Forgetting that `map()` returns an iterator, not a list
- `map()` with expensive functions without understanding lazy evaluation
- Using `map()` with multiple iterables of different lengths

## Related Functions

- **[filter()](filter.md)** - Filter items based on predicate
- **[zip()](zip.md)** - Combine iterables
- **[reduce()](../stdlib/functools.md#reduce)** - Aggregate values
- **List comprehensions** - More Pythonic for most cases

## Version Notes

- **Python 2.x**: `map()` returns a list
- **Python 3.x**: `map()` returns an iterator (lazy evaluation)
- **Python 3.8+**: Same lazy behavior, consistent
