# zip() Function Complexity

The `zip()` function combines elements from multiple iterables into tuples.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Creating iterator | O(1) | O(1) | Just creates iterator |
| Consuming iterator | O(n) | O(1) per tuple | n = items; creates tuples lazily |
| With unequal lengths | O(n) | O(n) | Stops at shortest iterable |

## Basic Usage

### Pairing Elements

```python
# O(1) - creates iterator
list1 = [1, 2, 3]
list2 = ['a', 'b', 'c']
zipped = zip(list1, list2)  # Iterator

# O(n) - consumed when needed
result = list(zipped)
# [(1, 'a'), (2, 'b'), (3, 'c')]

# Common pattern - iterate directly
for num, letter in zip(list1, list2):
    print(num, letter)  # O(n)
```

### Multiple Iterables

```python
# O(1) - creates iterator
list1 = [1, 2, 3]
list2 = ['a', 'b', 'c']
list3 = [10, 20, 30]
zipped = zip(list1, list2, list3)

# O(n*k) - consumed, k = number of iterables
result = list(zipped)
# [(1, 'a', 10), (2, 'b', 20), (3, 'c', 30)]
```

### Unequal Length Iterables

```python
# O(1) - creates iterator
list1 = [1, 2, 3, 4, 5]
list2 = ['a', 'b', 'c']
zipped = zip(list1, list2)

# O(n) - stops at shortest (3 items)
result = list(zipped)
# [(1, 'a'), (2, 'b'), (3, 'c')]
# Elements 4, 5 are ignored
```

## Performance Patterns

### Lazy Evaluation

```python
# O(1) - creates iterator, doesn't process yet
iter1 = range(10**9)
iter2 = range(10**9, 2*10**9)
zipped = zip(iter1, iter2)  # Iterator only

# O(n) - only when you consume
for a, b in zipped:
    print(a, b)
    break  # O(1) - stops after first

# vs list comprehension
result = list(zip(iter1, iter2))  # O(10^9) - consumes all
```

### Processing in Parallel

```python
# O(n*k) - parallel processing of k sequences
names = ["Alice", "Bob", "Charlie"]
ages = [30, 25, 35]
cities = ["NYC", "LA", "Chicago"]

# O(n) - single pass through all sequences
for name, age, city in zip(names, ages, cities):
    print(f"{name} is {age} in {city}")
```

## Common Patterns

### Transposing

```python
# O(n*m) where n = rows, m = cols
matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
]

# O(n*m) - consumes all
transposed = list(zip(*matrix))
# [(1, 4, 7), (2, 5, 8), (3, 6, 9)]

# Equivalent to:
transposed = [
    [matrix[i][j] for i in range(len(matrix))]
    for j in range(len(matrix[0]))
]
```

### Pairing with Indices

```python
# O(n) - zip with enumerate
items = ['a', 'b', 'c']
for index, item in enumerate(items):
    print(index, item)

# Less efficient alternative
for i, item in zip(range(len(items)), items):
    print(i, item)  # Slower due to range + len
```

### Creating Dictionaries

```python
# O(n) - zip keys and values
keys = ['name', 'age', 'city']
values = ['Alice', 30, 'NYC']

# O(n) - creates dict from zipped pairs
data = dict(zip(keys, values))
# {'name': 'Alice', 'age': 30, 'city': 'NYC'}

# Equivalent to:
data = {k: v for k, v in zip(keys, values)}  # Same O(n)
```

## Advanced Usage

### Grouped Elements

```python
# O(n) - group elements
items = [1, 2, 3, 4, 5, 6]

# Group into pairs
grouped = list(zip(items[::2], items[1::2]))
# [(1, 2), (3, 4), (5, 6)]

# More efficient with itertools
from itertools import zip_longest
grouped = list(zip_longest(iter(items), iter(items)))
```

### Sliding Window

```python
# O(n) - create sliding window
items = [1, 2, 3, 4, 5]

# O(n) - window of size 2
windows = list(zip(items, items[1:]))
# [(1, 2), (2, 3), (3, 4), (4, 5)]

# Works because zip stops at shortest
```

### Unzipping

```python
# O(n) - unzip using zip again
zipped = [(1, 'a'), (2, 'b'), (3, 'c')]

# O(n) - unzip with zip(*...)
list1, list2 = zip(*zipped)
# list1 = (1, 2, 3)
# list2 = ('a', 'b', 'c')

# Note: results are tuples, not lists
```

## Comparison with Alternatives

### zip vs Index Loop

```python
# Both O(n), different readability
list1 = [1, 2, 3]
list2 = ['a', 'b', 'c']

# ✅ zip - more Pythonic
for a, b in zip(list1, list2):
    print(a, b)

# ❌ Index loop - less readable
for i in range(len(list1)):
    print(list1[i], list2[i])

# ❌ Range with zip - redundant
for i, (a, b) in enumerate(zip(list1, list2)):
    print(i, a, b)
```

### zip vs Manual List

```python
# All O(n), different trade-offs
list1 = [1, 2, 3]
list2 = ['a', 'b', 'c']

# ✅ zip - memory efficient (iterator)
for a, b in zip(list1, list2):
    process(a, b)

# ❌ List - uses extra memory
result = list(zip(list1, list2))  # O(n) space

# ❌ Manual - verbose
result = [(a, b) for a, b in zip(list1, list2)]  # O(n) space
```

## Performance Considerations

### Iterator Efficiency

```python
# ✅ Lazy - doesn't create intermediate lists
for a, b in zip(iter1, iter2):
    if condition(a, b):
        break  # Can exit early

# ❌ Eager - creates list first
all_pairs = list(zip(iter1, iter2))  # O(n) space
for a, b in all_pairs:
    if condition(a, b):
        break
```

### Large Datasets

```python
# ✅ Lazy evaluation - memory efficient
iter1 = range(10**9)
iter2 = range(10**9)
for a, b in zip(iter1, iter2):
    # Process one pair at a time
    pass

# ❌ Creating list - uses huge memory
all_pairs = list(zip(range(10**9), range(10**9)))  # Out of memory!
```

## Edge Cases

### Empty Iterables

```python
# O(1) - creates empty iterator
result = list(zip([], []))
# []

# One empty - zip stops
result = list(zip([1, 2], []))
# []
```

### Single Iterable

```python
# O(n) - creates tuples of single elements
result = list(zip([1, 2, 3]))
# [(1,), (2,), (3,)]
```

### Unequal Lengths

```python
# O(n) - stops at shortest
result = list(zip([1, 2, 3, 4, 5], ['a', 'b', 'c']))
# [(1, 'a'), (2, 'b'), (3, 'c')]

# Use zip_longest for padding
from itertools import zip_longest
result = list(zip_longest([1, 2, 3, 4, 5], ['a', 'b', 'c'], fillvalue=None))
# [(1, 'a'), (2, 'b'), (3, 'c'), (4, None), (5, None)]
```

## Best Practices

✅ **Do**:

- Use `zip()` to combine multiple iterables
- Use `zip()` for iterating in parallel
- Use `enumerate()` instead of `zip(range(len(...)), ...)`
- Use `zip_longest()` when lengths differ and you need all items

❌ **Avoid**:

- Converting to list immediately - keep as iterator
- `zip()` with deeply nested iterables (becomes unreadable)
- Forgetting that `zip()` returns an iterator, not a list
- Using `zip()` with very different iteration speeds

## Related Functions

- **[enumerate()](enumerate.md)** - Iterate with indices
- **[map()](map.md)** - Apply function to iterables
- **[itertools.zip_longest()](../stdlib/itertools.md)** - Zip with padding
- **[itertools.chain()](../stdlib/itertools.md)** - Chain iterables

## Version Notes

- **Python 2.x**: `zip()` returns a list
- **Python 3.x**: `zip()` returns an iterator (lazy evaluation)
- **Python 3.8+**: Same lazy behavior, consistent
