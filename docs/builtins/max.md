# max() Function Complexity

The `max()` function returns the largest item in an iterable or among multiple arguments.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Single iterable | O(n) | O(1) | Must compare all items |
| Multiple arguments | O(n) | O(1) | n = number of arguments |
| With key function | O(n*k) | O(1) | k = key function time |

## Basic Usage

### Finding Maximum in Iterable

```python
# O(n) - must scan all items
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
max_val = max(numbers)  # 9

# O(n) for any iterable
max_val = max([1, 2, 3])      # 3
max_val = max((1, 2, 3))      # 3
max_val = max({1, 2, 3})      # 3
max_val = max("abc")          # 'c'
```

### Multiple Arguments

```python
# O(n) where n is number of arguments
max_val = max(5, 2, 8, 1)     # 8
max_val = max(3.14, 2.71, 1.41)  # 3.14
```

## With Key Function

```python
# O(n*k) - evaluates key for each item
words = ["apple", "pie", "cat"]
longest = max(words, key=len)  # O(n) - key is O(1)

# More expensive key function
numbers = [1, 2, 3, 4, 5]
max_val = max(numbers, key=lambda x: expensive_function(x))
# O(n*k) where k = time for expensive_function
```

## Performance Patterns

### Scanning Collections

```python
# O(n) - makes one pass through data
lst = list(range(1000000))
result = max(lst)  # ~1M comparisons

# Same complexity with generators
result = max(x**2 for x in range(10000))  # O(n)
```

### Working with Different Types

```python
# All O(n) - must compare all items
max([1, 2, 3])              # O(n) for list
max({1, 2, 3})              # O(n) for set
max("abcdef")               # O(n) for string
max(range(1000000))         # O(n) - iterates range
max(iter([1, 2, 3]))        # O(n) - iterates iterator
```

### Using Generators

```python
# O(n) but space-efficient
# Generator doesn't store all values
max(x for x in range(1000000) if x % 7 == 0)

# Better than:
# O(n) time but O(n) space
max([x for x in range(1000000) if x % 7 == 0])
```

## Complex Keys

### String Sorting with Key

```python
# O(n) - simple key function
data = ["apple", "pie", "cat", "banana"]
longest = max(data, key=len)  # "apple" or "banana" (3 letters)

# O(n) - extract attribute
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

people = [Person("Alice", 30), Person("Bob", 25), Person("Charlie", 35)]
oldest = max(people, key=lambda p: p.age)  # Charlie
```

### Tuple Unpacking

```python
# O(n) - compare tuples lexicographically
coords = [(1, 5), (3, 2), (2, 8)]
max_coord = max(coords)  # (3, 2) - compared by first element
# If first equal, compares second element, etc.

# With key to compare by second element
max_by_y = max(coords, key=lambda c: c[1])  # (2, 8)
```

## Comparison with Sorting

```python
# max() is much more efficient than sorting
numbers = list(range(10000))

# O(n) - just find maximum
result = max(numbers)

# O(n log n) - overkill if you just need max
result = sorted(numbers)[-1]

# Even worse - O(n^2) if comparing inefficiently
result = max(numbers, key=lambda x: expensive_function(x))
```

## Edge Cases

### Empty Sequences

```python
# Raises ValueError
try:
    max([])
except ValueError as e:
    print(e)  # max() arg is an empty sequence

# Provide default
max([], default=0)  # O(n) but returns 0 if empty
```

### Single Item

```python
# O(1) - already the maximum
result = max([42])  # 42

# O(1) - single argument
result = max(42)  # Still O(n) where n=1
```

### Non-Comparable Types

```python
# Raises TypeError if types can't be compared
try:
    max([1, "string"])
except TypeError:
    print("Can't compare int and str")
```

## Best Practices

✅ **Do**:
- Use `max()` to find maximum element
- Use key parameter for custom comparisons
- Use generators with `max()` for memory efficiency
- Provide `default` parameter for possibly empty sequences

❌ **Avoid**:
- Sorting just to find maximum (use `max()` instead)
- Unnecessary key function evaluations
- Finding max without checking if sequence is empty

## Related Functions

- **[min()](min.md)** - Find minimum value
- **[sorted()](sorted.md)** - Sort all items
- **[sum()](sum.md)** - Sum all items
- **[heapq.nlargest()](../stdlib/heapq.md)** - Find k largest items efficiently

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior
- **Python 3.8+**: Same behavior, consistent
