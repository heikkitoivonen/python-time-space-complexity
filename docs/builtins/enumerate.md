# enumerate() Function Complexity

The `enumerate()` function returns an iterator that produces tuples of (index, item) from an iterable.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Creating iterator | O(1) | O(1) | Just creates iterator |
| Consuming iterator | O(n*k) | O(1)† | k = processing time, † iterator only |
| With custom start | O(n*k) | O(1)† | start parameter doesn't change complexity |

## Basic Usage

### Simple Enumeration

```python
# O(1) - creates iterator
items = ['a', 'b', 'c']
enumerated = enumerate(items)  # Iterator

# O(n) - consumed when needed
for index, item in enumerated:
    print(index, item)
# 0 a
# 1 b
# 2 c

# Convert to list - O(n) time and space
result = list(enumerate(items))
# [(0, 'a'), (1, 'b'), (2, 'c')]
```

### Custom Start Index

```python
# O(1) - creates iterator
items = ['a', 'b', 'c']
enumerated = enumerate(items, start=1)

# O(n) - consumed
result = list(enumerated)
# [(1, 'a'), (2, 'b'), (3, 'c')]

# Works with any start value
result = list(enumerate(items, start=10))
# [(10, 'a'), (11, 'b'), (12, 'c')]
```

## Performance Patterns

### Lazy Evaluation

```python
# O(1) - creates iterator, doesn't process yet
big_list = range(10**9)
enumerated = enumerate(big_list)

# O(n) - only when you consume
for i, item in enumerate(big_list):
    print(i, item)
    if i >= 10:
        break  # O(10) - stops early

# vs list comprehension
result = [(i, x) for i, x in enumerate(range(10**9))]  # O(10^9)!
```

### Nested Enumeration

```python
# O(n*m*k) - enumerate nested structures
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

# O(n*m) - enumerate rows and columns
for i, row in enumerate(matrix):
    for j, item in enumerate(row):
        print(f"[{i}][{j}] = {item}")
```

## Common Patterns

### Iterating with Index

```python
# ✅ O(n) - preferred way
items = ['a', 'b', 'c', 'd', 'e']
for index, item in enumerate(items):
    print(index, item)

# ❌ O(n) but less Pythonic
for i in range(len(items)):
    print(i, items[i])

# ❌ O(n) with unnecessary zip
for i, item in zip(range(len(items)), items):
    print(i, item)
```

### Filtering with Index

```python
# O(n) - enumerate and filter
items = ['a', 'b', 'c', 'd', 'e']
result = [item for i, item in enumerate(items) if i % 2 == 0]
# ['a', 'c', 'e']

# Get only indices
indices = [i for i, item in enumerate(items) if 'a' in item]
# [0]
```

### Building New Structure

```python
# O(n) - enumerate to create dict
items = ['apple', 'banana', 'cherry']
item_dict = {i: item for i, item in enumerate(items)}
# {0: 'apple', 1: 'banana', 2: 'cherry'}

# With custom start
item_dict = {i: item for i, item in enumerate(items, start=1)}
# {1: 'apple', 2: 'banana', 3: 'cherry'}
```

## Working with Multiple Iterables

### Parallel Iteration with Index

```python
# O(n) - enumerate with zip
names = ['Alice', 'Bob', 'Charlie']
ages = [30, 25, 35]

for i, (name, age) in enumerate(zip(names, ages)):
    print(f"{i}: {name} is {age}")
# 0: Alice is 30
# 1: Bob is 25
# 2: Charlie is 35
```

### Nested Structures

```python
# O(n*m*k) - multiple levels of enumeration
data = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
]

for i, row in enumerate(data):
    for j, item in enumerate(row):
        print(f"[{i}][{j}] = {item}")
```

## Advanced Patterns

### Enumerate with Custom Index

```python
# O(n) - enumerate with offset
items = ['a', 'b', 'c', 'd', 'e']
for index, item in enumerate(items, start=100):
    print(index, item)
# 100 a
# 101 b
# ... etc
```

### Finding Position

```python
# O(n) - find position of element
items = ['apple', 'banana', 'cherry', 'date']
target = 'cherry'

for index, item in enumerate(items):
    if item == target:
        position = index
        break
# position = 2

# Alternative: use index() method
position = items.index(target)  # O(n) - same complexity
```

### Conditional Enumeration

```python
# O(n) - enumerate with filter
items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Only enumerate even items
for index, item in enumerate(items):
    if item % 2 == 0:
        print(index, item)
# 1 2
# 3 4
# ... etc
```

## Comparison with Alternatives

### enumerate vs range(len(...))

```python
# ✅ enumerate - preferred, more Pythonic
items = ['a', 'b', 'c']
for i, item in enumerate(items):
    print(i, item)

# ❌ range(len(...)) - less readable
for i in range(len(items)):
    print(i, items[i])

# Both O(n), enumerate is clearer
```

### enumerate vs zip with range

```python
# ✅ enumerate - simpler and faster
items = ['a', 'b', 'c']
for i, item in enumerate(items):
    process(i, item)

# ❌ zip with range - unnecessary overhead
for i, item in zip(range(len(items)), items):
    process(i, item)

# Both O(n), enumerate is more efficient
```

### enumerate vs Index Method

```python
# If finding position of one element
items = ['a', 'b', 'c', 'd', 'e']
target = 'c'

# O(n) - enumerate
for i, item in enumerate(items):
    if item == target:
        print(i)
        break

# O(n) - index method
print(items.index(target))

# If finding multiple positions
# enumerate is more efficient - single pass

# If finding one - index() is clearer
```

## Edge Cases

### Empty Iterable

```python
# O(1) - creates empty iterator
result = list(enumerate([]))
# []

for i, item in enumerate([]):
    print(i, item)  # Never executes
```

### Single Item

```python
# O(1) - creates iterator with one element
result = list(enumerate(['a']))
# [(0, 'a')]
```

### Large Start Value

```python
# O(1) - start value doesn't affect complexity
result = list(enumerate([1, 2, 3], start=10**9))
# [(1000000000, 1), (1000000001, 2), (1000000002, 3)]
```

### Generators

```python
# O(n) - enumerate can consume generators
def generator():
    yield 1
    yield 2
    yield 3

for i, value in enumerate(generator()):
    print(i, value)
# 0 1
# 1 2
# 2 3
```

## Performance Considerations

### Memory Efficiency

```python
# ✅ Iterator - memory efficient
big_list = range(10**9)
for i, item in enumerate(big_list):
    if i < 10:
        print(item)
# Only iterates 10 items

# ❌ List creation - uses memory
indices_items = list(enumerate(range(10**9)))  # Huge memory!
```

### Speed Comparison

```python
import timeit

items = list(range(1000))

# Time for enumerate
t1 = timeit.timeit(lambda: [x for i, x in enumerate(items)], number=10000)

# Time for range(len(...))
t2 = timeit.timeit(lambda: [items[i] for i in range(len(items))], number=10000)

# enumerate is generally faster due to optimizations
```

## Best Practices

✅ **Do**:
- Use `enumerate()` when you need both index and item
- Use `enumerate(iterable, start=1)` for 1-based indexing
- Use `enumerate()` with `break` for early exit
- Use `enumerate()` for lazy evaluation with large datasets

❌ **Avoid**:
- Using `range(len(...))` when `enumerate()` is clearer
- Using `zip(range(len(...)), iterable)` - use `enumerate()` instead
- Forgetting that `enumerate()` returns an iterator
- Creating intermediate lists unnecessarily

## Related Functions

- **[zip()](zip.md)** - Combine multiple iterables
- **[range()](range.md)** - Generate number sequences
- **[iter()](iter.md)** - Create iterators
- **[next()](next.md)** - Get next item from iterator

## Version Notes

- **Python 2.x**: `enumerate()` available, works similarly
- **Python 3.x**: Same behavior and performance
- **Python 3.8+**: Optimizations may improve performance but O(n) guaranteed
