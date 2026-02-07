# min() Function Complexity

The `min()` function returns the smallest item in an iterable or among multiple arguments.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Single iterable | O(n) | O(1) | Must compare all items |
| Multiple arguments | O(n) | O(1) | n = number of arguments |
| With key function | O(n*k) | O(1) | k = key function time; keeps only current best item/key |
| Empty iterable | O(1) | O(1) | Raises ValueError unless default provided |

## Basic Usage

### Finding Minimum in Iterable

```python
# O(n) - must scan all items
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
min_val = min(numbers)  # 1

# O(n) for any iterable
min_val = min([1, 2, 3])      # 1
min_val = min((1, 2, 3))      # 1
min_val = min({1, 2, 3})      # 1
min_val = min("abc")          # 'a'
```

### Multiple Arguments

```python
# O(n) where n is number of arguments
min_val = min(5, 2, 8, 1)     # 1
min_val = min(3.14, 2.71, 1.41)  # 1.41
```

## With Key Function

```python
# O(n*k) - evaluates key for each item
words = ["apple", "pie", "cat"]
shortest = min(words, key=len)  # "pie" (3 letters)

# More expensive key function
numbers = [1, 2, 3, 4, 5]
min_val = min(numbers, key=lambda x: expensive_function(x))
# O(n*k) where k = time for expensive_function
```

## Performance Patterns

### Scanning Collections

```python
# O(n) - makes one pass through data
lst = list(range(1000000))
result = min(lst)  # ~1M comparisons

# Same complexity with generators
result = min(x**2 for x in range(10000))  # O(n)
```

### Working with Different Types

```python
# All O(n) - must compare all items
min([1, 2, 3])              # O(n) for list
min({1, 2, 3})              # O(n) for set
min("abcdef")               # O(n) for string
min(range(1000000))         # O(n) - iterates range
min(iter([1, 2, 3]))        # O(n) - iterates iterator
```

### Using Generators

```python
# O(n) but space-efficient
# Generator doesn't store all values
min(x for x in range(1000000) if x % 7 == 0)

# Less efficient:
# O(n) time but O(n) space
min([x for x in range(1000000) if x % 7 == 0])
```

## Complex Keys

### Finding Item with Minimum Property

```python
# O(n) - evaluate key for each item
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

people = [Person("Alice", 30), Person("Bob", 25), Person("Charlie", 35)]
youngest = min(people, key=lambda p: p.age)  # Bob

# Find string with minimum length
words = ["python", "code", "programming"]
shortest = min(words, key=len)  # "code"
```

### Tuple Comparison

```python
# O(n) - compare tuples lexicographically
coords = [(1, 5), (3, 2), (2, 8)]
min_coord = min(coords)  # (1, 5) - compared by first element

# Compare by second element instead
min_by_y = min(coords, key=lambda c: c[1])  # (3, 2)
```

### Distance Calculation

```python
# O(n*k) - evaluate distance for each item
def distance(point):
    return (point[0]**2 + point[1]**2)**0.5

points = [(1, 1), (0, 5), (3, 4)]
closest = min(points, key=distance)  # (1, 1) - closest to origin

# More expensive calculation
def expensive_distance(p1, p2):
    # Simulated expensive computation
    return sum((a - b)**2 for a, b in zip(p1, p2))**0.5

closest = min(points, key=lambda p: expensive_distance(p, (0, 0)))
```

## Comparison with Sorting

```python
# min() is much more efficient than sorting
numbers = list(range(10000))

# O(n) - just find minimum
result = min(numbers)

# O(n log n) - overkill if you just need min
result = sorted(numbers)[0]

# Finding n smallest items
# O(n*k) with key - worse than:
import heapq
result = heapq.nsmallest(10, numbers)  # More efficient
```

## Edge Cases

### Empty Sequences

```python
# Raises ValueError
try:
    min([])
except ValueError as e:
    print(e)  # min() arg is an empty sequence

# Provide default
min([], default=float('inf'))  # Returns infinity if empty
```

### Single Item

```python
# O(1) - already the minimum
result = min([42])  # 42

# O(1) - single argument
# result = min(42)  # TypeError: 'int' object is not iterable
```

### Non-Comparable Types

```python
# Raises TypeError if types can't be compared
try:
    min([1, "string"])
except TypeError:
    print("Can't compare int and str")
```

## Practical Examples

### Finding Minimum Distance

```python
# O(n) - single pass
def find_closest(target, points):
    return min(points, key=lambda p: abs(p - target))

closest = find_closest(5, [1, 3, 7, 9])  # 3
```

### Selecting Best Option

```python
# O(n) with complex key
def evaluate_option(option):
    return option['cost'] + option['time'] * 0.5

options = [
    {'cost': 10, 'time': 5},
    {'cost': 15, 'time': 2},
    {'cost': 8, 'time': 10},
]
best = min(options, key=evaluate_option)
```

## Best Practices

✅ **Do**:

- Use `min()` to find minimum element
- Use key parameter for custom comparisons
- Use generators with `min()` for memory efficiency
- Provide `default` parameter for possibly empty sequences

❌ **Avoid**:

- Sorting just to find minimum (use `min()` instead)
- Unnecessary key function evaluations
- Finding min without checking if sequence is empty

## Related Functions

- **[max()](max.md)** - Find maximum value
- **[sorted()](sorted.md)** - Sort all items
- **[sum()](sum.md)** - Sum all items
- **[heapq.nsmallest()](../stdlib/heapq.md)** - Find k smallest items efficiently

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior
- **Python 3.8+**: Same behavior, consistent
