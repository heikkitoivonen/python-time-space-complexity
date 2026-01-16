# reversed() Function Complexity

The `reversed()` function returns a reverse iterator over a sequence.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Creating iterator | O(1) | O(1) | Just creates iterator |
| Consuming iterator | O(n*k) | O(1)† | k = processing time, † iterator only |
| Works with | O(n) | O(1) | Sequences with __reversed__ |
| Unsupported types | N/A | N/A | Raises TypeError |

## Basic Usage

### Reversing Lists

```python
# O(1) - creates reverse iterator
numbers = [1, 2, 3, 4, 5]
reversed_iter = reversed(numbers)

# O(n) - consumed when needed
result = list(reversed_iter)
# [5, 4, 3, 2, 1]

# Or iterate directly
for num in reversed(numbers):
    print(num)  # 5, 4, 3, 2, 1
```

### Reversing Strings

```python
# O(1) - creates iterator
text = "hello"
reversed_iter = reversed(text)

# O(n) - consumed
result = ''.join(reversed_iter)
# "olleh"

# Direct iteration
for char in reversed(text):
    print(char)  # o, l, l, e, h
```

### Reversing Tuples

```python
# O(1) - creates iterator
numbers = (1, 2, 3)
reversed_iter = reversed(numbers)

# O(n) - consumed
result = tuple(reversed_iter)
# (3, 2, 1)
```

## Performance Patterns

### Lazy Evaluation

```python
# O(1) - creates iterator, doesn't process yet
big_list = list(range(10**9))
reversed_iter = reversed(big_list)

# O(k) - only processes k items
for i, item in enumerate(reversed_iter):
    print(item)
    if i >= 10:
        break  # Stops after 10 items
```

### Memory Efficiency

```python
# ✅ O(1) space - lazy evaluation
big_list = range(10**9)
for item in reversed(big_list):
    process(item)

# ❌ O(n) space - creates list
reversed_list = list(reversed(big_list))
for item in reversed_list:
    process(item)
```

## Common Patterns

### Reverse Iteration

```python
# O(n) - iterate in reverse
items = ['a', 'b', 'c', 'd']

# Using reversed()
for item in reversed(items):
    print(item)  # d, c, b, a

# Alternative: slicing (creates copy)
for item in items[::-1]:
    print(item)  # Same output, but O(n) space
```

### Reverse with Index

```python
# O(n) - combining enumerate and reversed
items = ['a', 'b', 'c', 'd']

# Get indices in reverse
for i, item in enumerate(reversed(items)):
    print(i, item)
# 0 d
# 1 c
# 2 b
# 3 a

# Note: indices are sequential, not reversed
# Use: len(items) - 1 - i to get original indices
```

### Reversing and Collecting

```python
# O(n) - reverse and collect in new structure
items = [1, 2, 3, 4, 5]

# Reverse to list
result = list(reversed(items))  # [5, 4, 3, 2, 1]

# Reverse to string
chars = "hello"
result = ''.join(reversed(chars))  # "olleh"

# Reverse to tuple
result = tuple(reversed(items))  # (5, 4, 3, 2, 1)
```

## Comparison with Alternatives

### reversed() vs Slicing

```python
# Both reverse the sequence
items = [1, 2, 3, 4, 5]

# reversed() - O(1) space, lazy
for item in reversed(items):
    process(item)

# Slicing - O(n) space, eager
for item in items[::-1]:
    process(item)

# reversed() is more memory efficient
```

### reversed() vs Reverse Method

```python
# List has reverse() method
items = [1, 2, 3, 4, 5]
items.reverse()  # O(n) in-place, modifies original

# reversed() doesn't modify original
items = [1, 2, 3, 4, 5]
for item in reversed(items):
    process(item)
# Original unchanged

# Use reversed() to preserve original
# Use reverse() to modify in-place
```

### reversed() vs Sorting

```python
# reversed() preserves order
items = [3, 1, 4, 1, 5, 9, 2, 6]
result = list(reversed(items))
# [6, 2, 9, 5, 1, 4, 1, 3]

# sorted with reverse=True sorts
result = sorted(items, reverse=True)
# [9, 6, 5, 4, 3, 2, 1, 1]

# Different operations - don't confuse them
```

## Supported Types

### Works With

```python
# Sequences with __reversed__ method
list_rev = reversed([1, 2, 3])  # O(1)
tuple_rev = reversed((1, 2, 3))  # O(1)
str_rev = reversed("hello")  # O(1)
range_rev = reversed(range(1, 4))  # O(1)

# All work efficiently
```

### Doesn't Work With

```python
# Types without __reversed__ method
try:
    reversed({1, 2, 3})  # TypeError - sets
except TypeError:
    pass

try:
    reversed({'a': 1, 'b': 2})  # TypeError - dicts
except TypeError:
    pass

try:
    reversed(42)  # TypeError - integers
except TypeError:
    pass

# But you can iterate them differently
reversed(list(my_set))  # Convert first
```

## Edge Cases

### Empty Sequence

```python
# O(1) - creates empty iterator
result = list(reversed([]))
# []

for item in reversed(():
    print(item)  # Never executes
```

### Single Element

```python
# O(1)
result = list(reversed([42]))
# [42]
```

### Custom Objects

```python
# O(1) - if class implements __reversed__
class CountDown:
    def __init__(self, n):
        self.n = n
    
    def __reversed__(self):
        for i in range(self.n, 0, -1):
            yield i

cd = CountDown(5)
result = list(reversed(cd))
# [5, 4, 3, 2, 1]
```

## Performance Considerations

### When to Use reversed()

```python
# Use when:
# 1. You need to preserve original
# 2. Iterating only once
# 3. Reverse iteration is an afterthought

# 1. Preserve original
original = [1, 2, 3]
for item in reversed(original):
    process(item)
# original is unchanged

# 2. One-pass iteration
if condition:
    for item in reversed(items):
        process(item)

# 3. Quick reverse
list(reversed(items))  # Lazily created
```

### Performance Comparison

```python
import timeit

items = list(range(1000))

# reversed() - creates iterator (fast)
t1 = timeit.timeit(lambda: list(reversed(items)), number=10000)

# Slicing - creates copy (slower)
t2 = timeit.timeit(lambda: items[::-1], number=10000)

# reversed() typically faster for iteration
# But slicing has optimizations in CPython
```

## Best Practices

✅ **Do**:
- Use `reversed()` to reverse sequences without modifying
- Use for lazy iteration over reversed sequences
- Combine with `enumerate()` for reverse iteration with indices
- Use for one-pass reverse iterations

❌ **Avoid**:
- Converting to list immediately (defeats laziness)
- Using with non-sequences (check type first)
- Using `reversed()` when `reverse()` modifies in-place
- Assuming reversed indices match original

## Related Functions

- **[list.reverse()](list.md)** - In-place list reversal
- **[sorted(reverse=True)](sorted.md)** - Reverse sorting
- **[slicing [::-1]](list.md)** - Reverse slicing
- **[enumerate()](enumerate.md)** - Iteration with indices

## Version Notes

- **Python 2.x**: Basic functionality available
- **Python 3.x**: Same behavior, consistent
- **Python 3.8+**: No changes to complexity
