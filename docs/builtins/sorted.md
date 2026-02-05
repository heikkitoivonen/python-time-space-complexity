# sorted() Function Complexity

The `sorted()` function returns a new sorted list from the items in an iterable.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Basic sorting | O(n log n) | O(n) | Timsort/Powersort |
| With key function | O(n log n + n*k) | O(n) | k = key function time; key computed once per element |
| Reverse sorting | O(n log n) | O(n) | No extra overhead |
| Already sorted | O(n) | O(n) | Best case |

## Basic Usage

### Simple Sorting

```python
# O(n log n) - Timsort (≤3.10) or Powersort (3.11+)
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
result = sorted(numbers)
# [1, 1, 2, 3, 4, 5, 6, 9]

# Works with any iterable
result = sorted((3, 1, 4))  # Tuple input
# [1, 3, 4]

result = sorted({3, 1, 4})  # Set input
# [1, 3, 4]

result = sorted("cadb")     # String input
# ['a', 'b', 'c', 'd']
```

### Reverse Sorting

```python
# O(n log n) - same complexity
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
result = sorted(numbers, reverse=True)
# [9, 6, 5, 4, 3, 2, 1, 1]

# Works with strings
words = ["apple", "pie", "cat"]
result = sorted(words, reverse=True)
# ["pie", "cat", "apple"]
```

## With Key Function

### Custom Comparisons

```python
# O(n log n + n*k) where k = key function time
# Key is computed once per element, then comparisons use cached keys
words = ["apple", "pie", "cat", "banana"]
result = sorted(words, key=len)  # Sort by length
# ["pie", "cat", "apple", "banana"]

# Sort by last character
result = sorted(words, key=lambda x: x[-1])
# ["apple", "banana", "pie", "cat"]
```

### Sorting Objects

```python
# O(n log n) - simple key extraction
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
    
    def __repr__(self):
        return f"Person({self.name}, {self.age})"

people = [
    Person("Alice", 30),
    Person("Bob", 25),
    Person("Charlie", 35),
]

# Sort by age
result = sorted(people, key=lambda p: p.age)
# [Person(Bob, 25), Person(Alice, 30), Person(Charlie, 35)]

# Using operator module (more efficient)
from operator import attrgetter
result = sorted(people, key=attrgetter('age'))  # Same O(n log n)
```

### Tuple Sorting

```python
# O(n log n) - lexicographic comparison
coords = [(1, 5), (3, 2), (2, 8)]
result = sorted(coords)
# [(1, 5), (2, 8), (3, 2)]

# Sort by second element
result = sorted(coords, key=lambda c: c[1])
# [(3, 2), (1, 5), (2, 8)]
```

## Sorting Algorithm

### How It Works

```
Python uses Timsort (Python 2.3-3.10) or Powersort (Python 3.11+).
Both are hybrid algorithms combining merge sort and insertion sort:
1. Divide array into small chunks (runs) - ~32-64 elements
2. Sort each run with insertion sort - O(k²) per run
3. Merge runs together - O(n log n) overall
4. Already sorted data: O(n) - detects and uses it

Powersort uses an improved merge policy but has the same complexity.
```

### Performance Characteristics

```python
# Best case - O(n) - already sorted or reverse sorted
numbers = list(range(1000000))
result = sorted(numbers)  # Nearly O(n) for nearly sorted data

# Average case - O(n log n)
import random
numbers = list(range(1000))
random.shuffle(numbers)
result = sorted(numbers)  # O(n log n)

# Worst case - O(n log n) - still guaranteed
numbers = [1000 - i for i in range(1000)]  # Reverse sorted
result = sorted(numbers)  # O(n log n) - handles well
```

## Performance Patterns

### Sorted vs sort()

```python
# sorted() - creates new list, O(n log n) time, O(n) space
original = [3, 1, 4, 1, 5]
result = sorted(original)  # [1, 1, 3, 4, 5]
# original unchanged

# list.sort() - in-place, O(n log n) time, O(n) space
original = [3, 1, 4, 1, 5]
original.sort()  # [1, 1, 3, 4, 5]
# original modified

# Both use same algorithm, same complexity but sorted() makes copy
```

### Expensive Key Functions

```python
# O(n*k + n log n) - key computed once per element, then cached
def expensive_key(x):
    # O(m) - expensive computation
    return sum(range(x))

numbers = list(range(1000))
result = sorted(numbers, key=expensive_key)
# Complexity: O(n*m + n log n) - key called n times, then n log n comparisons

# Better: pre-compute keys
from operator import itemgetter
keys = [(x, expensive_key(x)) for x in numbers]  # O(n*m)
result = sorted(keys, key=itemgetter(1))         # O(n log n)
# Total: O(n*m + n log n)
```

### Decorate-Sort-Undecorate (DSU)

```python
# O(n log n) - when computing key is expensive
def get_sort_key(item):
    # Some expensive computation
    return complex_calculation(item)

# With key: O(n*k + n log n) - key computed once per element
result = sorted(items, key=get_sort_key)

# Faster: O(n*k + n log n)
decorated = [(get_sort_key(item), item) for item in items]  # O(n*k)
sorted_decorated = sorted(decorated)                          # O(n log n)
result = [item for _, item in sorted_decorated]              # O(n)
```

## Sorting Stability

```python
# sorted() is stable - preserves order of equal elements
data = [(1, 'a'), (2, 'b'), (1, 'c'), (2, 'd')]
result = sorted(data, key=lambda x: x[0])
# [(1, 'a'), (1, 'c'), (2, 'b'), (2, 'd')]
# Among equal keys, original order preserved
```

## Common Patterns

### Multiple Sort Criteria

```python
# Sort by multiple attributes - O(n log n)
students = [
    ('Alice', 85),
    ('Bob', 85),
    ('Charlie', 90),
]

# Sort by score descending, then name ascending
result = sorted(students, key=lambda s: (-s[1], s[0]))
# [('Charlie', 90), ('Alice', 85), ('Bob', 85)]
```

### Case-Insensitive Sorting

```python
# O(n log n) - with case conversion
words = ["Apple", "banana", "Cherry", "date"]
result = sorted(words, key=str.lower)
# ["Apple", "banana", "Cherry", "date"]
```

### Sorting with Custom Order

```python
# O(n log n) - custom comparison key
priority = {'high': 0, 'medium': 1, 'low': 2}
tasks = [
    {'name': 'A', 'priority': 'low'},
    {'name': 'B', 'priority': 'high'},
    {'name': 'C', 'priority': 'medium'},
]

result = sorted(tasks, key=lambda t: priority[t['priority']])
# B (high), C (medium), A (low)
```

## Comparison with Sorting Methods

### sorted() vs list.sort()

```python
# sorted() - returns new list, original unchanged
original = [3, 1, 4, 1, 5]
result = sorted(original)

# list.sort() - modifies in-place, returns None
original = [3, 1, 4, 1, 5]
original.sort()

# Both: O(n log n) time, O(n) space for Timsort
# Choose based on whether you need original
```

### sorted() vs heapq.nsmallest()

```python
# sorted() - O(n log n), entire list sorted
numbers = list(range(1000000))
all_sorted = sorted(numbers)

# heapq.nsmallest() - O(n log k) for k items
import heapq
k_smallest = heapq.nsmallest(10, numbers)  # Much faster if k << n
```

## Edge Cases

### Empty List

```python
# O(1) - no sorting needed
result = sorted([])
# []
```

### Single Element

```python
# O(1) - nothing to sort
result = sorted([42])
# [42]
```

### Already Sorted

```python
# O(n) - Timsort detects and handles efficiently
numbers = list(range(1000000))
result = sorted(numbers)  # Nearly O(n)
```

### Reverse Sorted

```python
# O(n) - also handled efficiently
numbers = list(range(1000000, 0, -1))
result = sorted(numbers)  # Nearly O(n)
```

## Best Practices

✅ **Do**:

- Use `sorted()` to create new sorted list
- Use `key` parameter for custom sorting
- Use `operator.attrgetter()` instead of lambda for attributes
- Pre-compute expensive keys if sorting by them multiple times

❌ **Avoid**:

- Calling `sorted()` multiple times (cache result)
- Complex lambda functions (define function instead)
- Sorting by expensive computation in key (pre-compute)
- Forgetting that `sorted()` creates a new list (uses memory)

## Related Functions

- **[list.sort()](list.md)** - In-place sorting
- **[heapq.nsmallest()](../stdlib/heapq.md)** - k smallest items
- **[heapq.nlargest()](../stdlib/heapq.md)** - k largest items
- **[max()](max.md)** - Find maximum without sorting

## Version Notes

- **Python 2.3-3.10**: Uses Timsort algorithm
- **Python 3.11+**: Uses Powersort (improved merge policy, same complexity)
