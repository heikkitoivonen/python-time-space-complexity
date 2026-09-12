# sorted() Function Complexity

The `sorted()` function returns a new sorted list from the items in an iterable.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Basic sorting | O(n log n) | O(n) | Copies the input into a new list, then sorts that in place |
| With key function | O(n log n + n*k) | O(n) | k = key function time; key called once per element, comparisons use the stored keys |
| Reverse sorting | O(n log n) | O(n) | Stable; the list is reversed before and after the sort, O(n) extra |
| Already sorted | O(n) | O(n) | Best case: the input is one run; reverse-sorted input costs the same |

n is the number of items; one comparison counts as O(1), and the size of a key is not counted in the space bound.

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
# Key is computed once per element, then comparisons use the stored keys
words = ["apple", "pie", "cat", "banana"]
result = sorted(words, key=len)  # Sort by length
# ["pie", "cat", "apple", "banana"]

# Sort by last character
result = sorted(words, key=lambda x: x[-1])
# ["banana", "apple", "pie", "cat"]
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

# The same key via the operator module
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
Python sorts with Timsort (through 3.10) or Powersort (3.11+): a merge sort
that starts from the runs already present in the input.
1. Scan for natural runs - ascending, or descending, which are reversed in place
2. Extend short runs to 32-64 elements with binary insertion sort
3. Merge runs - O(n log n) comparisons overall
4. Input that is already one run: O(n) - nothing to merge

Powersort changes the order in which runs are merged, not the bound.
```

### Performance Characteristics

```python
# Best case - O(n): the input is already one run
numbers = list(range(100000))
result = sorted(numbers)  # n - 1 comparisons

numbers = list(range(100000, 0, -1))  # Reverse sorted
result = sorted(numbers)  # One descending run, also O(n)

# Average and worst case - O(n log n)
import random
numbers = list(range(100000))
random.shuffle(numbers)
result = sorted(numbers)  # O(n log n)
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
# O(n*m + n log n) - n key calls of O(m) each, then O(n log n) comparisons on the stored keys
def expensive_key(x):
    # O(m) - expensive computation, m = x here
    return sum(range(x))

numbers = list(range(1000))
result = sorted(numbers, key=expensive_key)

# Storing the keys pays only when the same keys serve more than one sort
from operator import itemgetter
keyed = [(x, expensive_key(x)) for x in numbers]  # O(n*m), once
ascending = sorted(keyed, key=itemgetter(1))                 # O(n log n)
descending = sorted(keyed, key=itemgetter(1), reverse=True)  # O(n log n), expensive_key not called again
```

### Decorate-Sort-Undecorate (DSU)

```python
# key= is decorate-sort-undecorate done for you: n key calls, then the
# sort compares only the stored keys, never the items themselves
items = [{"name": "b", "rank": 1}, {"name": "a", "rank": 1}]
result = sorted(items, key=lambda d: d["rank"])  # O(n*k + n log n)
# [{'name': 'b', 'rank': 1}, {'name': 'a', 'rank': 1}] - ties keep input order

# Building (key, item) tuples by hand costs the same n key calls, and on a
# tied key the comparison falls through to the items
decorated = [(d["rank"], d) for d in items]
try:
    sorted(decorated)
except TypeError:
    pass  # dicts do not order; key= never compared them
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
# O(L + n log n) - str.lower() costs each word's length, L = total characters
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

# Both: O(n log n) time, O(n) space for Timsort/Powersort
# Choose based on whether you need original
```

### sorted() vs heapq.nsmallest()

```python
import random
numbers = list(range(1000000))
random.shuffle(numbers)

# sorted() - O(n log n), entire list sorted
all_sorted = sorted(numbers)

# heapq.nsmallest() - O(n log k) for k items
import heapq
k_smallest = heapq.nsmallest(10, numbers)  # Wins when k << n
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
# O(n) - one ascending run, n - 1 comparisons
numbers = list(range(1000000))
result = sorted(numbers)
```

### Reverse Sorted

```python
# O(n) - one descending run, reversed in place
numbers = list(range(1000000, 0, -1))
result = sorted(numbers)
```

## Best Practices

✅ **Do**:

- Use `sorted()` to create new sorted list
- Use `key` parameter for custom sorting
- Use `key=` rather than building `(key, item)` tuples by hand
- Store expensive keys once when the same keys serve several sorts

❌ **Avoid**:

- Calling `sorted()` multiple times (cache result)
- Sorting the whole input when only the k smallest are needed (use `heapq.nsmallest()`)
- `functools.cmp_to_key()` when a key function will do (a Python call per comparison instead of per element)
- Forgetting that `sorted()` creates a new list (uses memory)

## Related Functions

- **[list.sort()](list.md)** - In-place sorting
- **[heapq.nsmallest()](../stdlib/heapq.md)** - k smallest items
- **[heapq.nlargest()](../stdlib/heapq.md)** - k largest items
- **[max()](max.md)** - Find maximum without sorting

## Version Notes

- **Python 2.3-3.10**: Uses Timsort algorithm
- **Python 3.11+**: Uses Powersort (improved merge policy, same complexity)
