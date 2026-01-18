# filter() Function Complexity

The `filter()` function constructs an iterator from items that pass a predicate function.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Filtering with function | O(n*k) | O(1)† | k = predicate time, † iterator only |
| Consuming iterator | O(n*k) | O(m) | m = number of matching items |
| Filtering with None | O(n) | O(1)† | Removes falsy values, k=1 for truthiness test |

## Basic Usage

### Filtering with Function

```python
# O(n*k) - iterator created, k = predicate time
numbers = [1, 2, 3, 4, 5]
evens = filter(lambda x: x % 2 == 0, numbers)  # Iterator

# O(n) - consumed when needed
result = list(evens)  # [2, 4]

# Common pattern - filter and iterate
for num in filter(lambda x: x > 2, numbers):
    print(num)  # O(n) - 3, 4, 5
```

### Filtering with None

```python
# O(n) - removes falsy values (None, 0, False, "", [], etc.)
values = [0, 1, False, 2, None, 3, "", 4]
truthy = list(filter(None, values))  # [1, 2, 3, 4]

# O(1) - creates iterator
evens = filter(None, [0, 0, 0])  # Iterator
result = list(evens)  # []
```

### Custom Predicate

```python
# O(n*k) where k = predicate time
def is_long(word):
    return len(word) > 3

words = ["cat", "dog", "elephant", "ant", "python"]
long_words = filter(is_long, words)  # O(1)

result = list(long_words)  # ["elephant", "python"] - O(n)
```

## Performance Patterns

### Lazy Evaluation

```python
# O(1) - creates iterator, doesn't process yet
huge_list = range(10**9)
filtered = filter(lambda x: x % 1000 == 0, huge_list)

# O(n/1000) - only processes needed items
count = 0
for item in filtered:
    count += 1
    if count >= 10:
        break  # Stops after 10 items

# vs list comprehension
result = [x for x in range(10**9) if x % 1000 == 0]  # O(10^9)!
```

### Expensive Predicate

```python
# O(n*k) where k = predicate time
def is_prime(n):
    # O(sqrt(n)) - expensive!
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

numbers = range(1, 1000)
primes = filter(is_prime, numbers)  # O(1) - iterator only

# O(n*sqrt(n)) - when consumed
result = list(primes)  # Expensive computation
```

## Common Patterns

### Removing None Values

```python
# O(n) - filters None from list
values = [1, None, 2, None, 3]
non_null = list(filter(None, values))  # [1, 2, 3]

# Equivalent to:
non_null = [x for x in values if x is not None]  # Same O(n)
```

### Type-based Filtering

```python
# O(n*k) where k = type check time
mixed = [1, "two", 3, "four", 5, "six"]

# Filter for integers
integers = list(filter(lambda x: isinstance(x, int), mixed))
# [1, 3, 5]

# Simpler with list comprehension
integers = [x for x in mixed if isinstance(x, int)]  # Same complexity
```

### Attribute Filtering

```python
# O(n*k) where k = attribute access time
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

people = [
    Person("Alice", 30),
    Person("Bob", 15),
    Person("Charlie", 25),
]

# O(n) - filter adults
adults = list(filter(lambda p: p.age >= 18, people))
# [Person("Alice", 30), Person("Charlie", 25)]

# More readable with function
def is_adult(person):
    return person.age >= 18

adults = list(filter(is_adult, people))  # Same O(n)
```

### Combining Conditions

```python
# O(n) - single condition
def is_valid(x):
    return x > 0 and x < 100

numbers = [-10, 5, 50, 150, 25]
valid = list(filter(is_valid, numbers))  # [5, 50, 25]

# Equivalent operations
valid = [x for x in numbers if x > 0 and x < 100]  # O(n)
valid = list(filter(lambda x: 0 < x < 100, numbers))  # O(n)
```

## Comparison with Alternatives

### filter vs List Comprehension

```python
# Both O(n*k), different readability
numbers = [1, 2, 3, 4, 5]

# filter - functional approach
evens = list(filter(lambda x: x % 2 == 0, numbers))

# List comprehension - more Pythonic in Python 3
evens = [x for x in numbers if x % 2 == 0]

# Both O(n), comprehension generally preferred
```

### filter vs for Loop

```python
# Same complexity, different style
numbers = [1, 2, 3, 4, 5]

# filter
result = list(filter(lambda x: x > 2, numbers))  # O(n)

# for loop
result = []
for x in numbers:
    if x > 2:
        result.append(x)  # O(n)

# List comprehension
result = [x for x in numbers if x > 2]  # O(n)

# All O(n), comprehension is most Pythonic
```

## Lazy vs Eager

### Memory Efficiency

```python
# ✅ Lazy - memory efficient for large datasets
big_list = range(10**8)
filtered = filter(lambda x: x % 2 == 0, big_list)

# Process without storing all results
for item in filtered:
    process(item)  # O(n/2) iterations, O(1) space

# ❌ Eager - creates intermediate list
filtered = [x for x in range(10**8) if x % 2 == 0]  # O(n) space
```

### Partial Consumption

```python
# ✅ filter - stops when you break
big_list = range(10**9)
filtered = filter(lambda x: x % 1000 == 0, big_list)

count = 0
for item in filtered:
    count += 1
    if count >= 5:
        break  # O(5000) - only processes what needed

# ❌ List comprehension - processes all
all_items = [x for x in range(10**9) if x % 1000 == 0]  # O(10^6)
```

## Performance Considerations

### Predicate Complexity

```python
# O(n) - simple predicate
result = list(filter(lambda x: x > 5, range(1000)))

# O(n*k) - expensive predicate
result = list(filter(is_prime, range(1000)))  # k = O(sqrt(n))

# O(n²) - very expensive predicate
result = list(filter(
    lambda x: sum(range(x)) > 100,  # Recomputes sum each time
    range(1000)
))
```

### Early Exit

```python
# ✅ Lazy evaluation allows early exit
numbers = range(10**9)
large_numbers = filter(lambda x: x > 10**8, numbers)

# Get first 10 quickly
first_10 = [next(large_numbers) for _ in range(10)]

# ❌ List comprehension doesn't support early exit
first_10 = [x for x in range(10**9) if x > 10**8][:10]  # O(10^8)
```

## Edge Cases

### Empty Iterable

```python
# O(1) - creates empty iterator
result = filter(lambda x: x > 5, [])
final = list(result)  # []
```

### All Items Pass

```python
# O(n) - all items retained
result = list(filter(lambda x: x > 0, [1, 2, 3, 4, 5]))
# [1, 2, 3, 4, 5]
```

### No Items Pass

```python
# O(n*k) - checks all items, returns empty
result = list(filter(lambda x: x > 100, [1, 2, 3, 4, 5]))
# []
```

## Best Practices

✅ **Do**:

- Use `filter()` for lazy evaluation with large datasets
- Use `filter(None, list)` to remove falsy values
- Use list comprehension for most filtering in Python 3
- Chain `filter()` with `map()` for complex transformations

❌ **Avoid**:

- Nested `filter()` calls - use list comprehension instead
- Complex predicates in `filter()` - define functions for clarity
- Forgetting that `filter()` returns an iterator, not a list
- Using `filter()` when list comprehension is more readable

## Related Functions

- **[map()](map.md)** - Apply function to all items
- **[zip()](zip.md)** - Combine iterables
- **[any()](any.md)** - Check if any item passes condition
- **[all()](all.md)** - Check if all items pass condition
- **[itertools.filterfalse()](../stdlib/itertools.md)** - Opposite of filter

## Version Notes

- **Python 2.x**: `filter()` returns a list
- **Python 3.x**: `filter()` returns an iterator (lazy evaluation)
- **Python 3.8+**: Same lazy behavior, consistent
