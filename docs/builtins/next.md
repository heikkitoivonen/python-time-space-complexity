# next() Function Complexity

The `next()` function retrieves the next item from an iterator by calling its `__next__()` method.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `next(iterator)` | O(1)* | O(1) | Get next item from iterator |
| `next(iterator, default)` | O(1)* | O(1) | Get next or return default |

*O(1) for list/tuple/range iterators; filter/map iterators may skip items (O(k) where k items filtered)

## Basic Usage

### Getting Next Item

```python
# Create iterator - O(1)
it = iter([1, 2, 3])  # O(1)

# Get next items - O(1) each
item1 = next(it)  # 1 - O(1)
item2 = next(it)  # 2 - O(1)
item3 = next(it)  # 3 - O(1)

# next() raises StopIteration when exhausted
try:
    item4 = next(it)  # Raises StopIteration
except StopIteration:
    print("Iterator exhausted")
```

### Using Default Value

```python
# Use default to avoid exception - O(1)
it = iter([1, 2, 3])

next(it)  # 1
next(it)  # 2
next(it)  # 3
item = next(it, "END")  # "END" - returns default, no exception

# Useful for safe iteration
value = next(iterator, None)  # Returns None if exhausted
```

## Manual Iterator Control

### Step Through Sequences

```python
# Manually iterate - O(1) per step
it = iter("hello")

first = next(it)   # 'h' - O(1)
second = next(it)  # 'e' - O(1)
third = next(it)   # 'l' - O(1)

# Continue with rest
for char in it:  # O(1) each
    print(char)  # 'l', 'o'
```

### Mixing Manual and For Loop

```python
# Get first item manually
it = iter([10, 20, 30, 40])
first = next(it)  # 10 - O(1)

# Process rest in for loop
for item in it:  # O(1) each iteration
    print(item)  # 20, 30, 40
```

## Generator Functions

### Generators and next()

```python
# Generator function
def count_up(max):
    i = 0
    while i < max:
        yield i
        i += 1

# Create generator - O(1)
gen = count_up(3)  # O(1)

# Use next() to step through - O(1) per step
val1 = next(gen)  # 0 - O(1)
val2 = next(gen)  # 1 - O(1)
val3 = next(gen)  # 2 - O(1)

try:
    val4 = next(gen)  # Raises StopIteration
except StopIteration:
    print("Done")
```

## Common Patterns

### Pairwise Iteration

```python
# Iterate elements in pairs
def pairwise(iterable):
    """Yield consecutive pairs"""
    it = iter(iterable)
    a = next(it, None)  # O(1)
    
    for b in it:  # O(1) each
        yield (a, b)
        a = b

# Usage
items = [1, 2, 3, 4, 5]
for pair in pairwise(items):  # O(n) total
    print(pair)
# Output: (1,2), (2,3), (3,4), (4,5)
```

### Skip Items

```python
# Skip first n items
def skip_n(iterable, n):
    it = iter(iterable)
    
    # Skip n items - O(n)
    for _ in range(n):
        next(it, None)  # O(1) each
    
    # Return rest
    return it

# Usage
it = skip_n(range(10), 3)
for item in it:  # O(1) each
    print(item)  # 3, 4, 5, ..., 9
```

### Take First N

```python
# Take first n items - O(n)
def take(iterable, n):
    it = iter(iterable)
    for _ in range(n):
        yield next(it)  # O(1) each

# Usage
items = range(100)
first_five = take(items, 5)  # O(5)
```

## Error Handling

### Safe next() with Default

```python
# Avoid exceptions with default - O(1)
it = iter([1, 2, 3])

while True:
    value = next(it, None)  # O(1)
    if value is None:
        break
    print(value)
```

### Checking for Exhaustion

```python
# Sentinel pattern
it = iter([1, 2, 3])
sentinel = object()  # Unique marker

while True:
    value = next(it, sentinel)  # O(1)
    if value is sentinel:
        break
    process(value)
```

## Advanced Iterator Patterns

### Iterator with State

```python
# Iterator that maintains state
class CountUp:
    def __init__(self, max):
        self.max = max
        self.current = 0
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.current < self.max:
            val = self.current
            self.current += 1
            return val  # O(1)
        raise StopIteration

# Usage
counter = CountUp(3)
val1 = next(counter)  # 0 - O(1)
val2 = next(counter)  # 1 - O(1)
```

### Chained Iterators

```python
# Chain multiple iterators - O(1) per next()
from itertools import chain

it1 = iter([1, 2, 3])
it2 = iter([4, 5, 6])
combined = chain(it1, it2)  # O(1) to create

# Iterate through both - O(1) each
for item in combined:  # O(6) total
    print(item)
```

## Comparison with For Loop

```python
# For loop uses next() internally
items = [1, 2, 3]

# Manual with next() - O(n)
it = iter(items)
while True:
    try:
        item = next(it)  # O(1)
        print(item)
    except StopIteration:
        break

# For loop (equivalent) - O(n)
for item in items:  # O(1) each
    print(item)

# For loop is cleaner; use next() for special cases
```

## Performance Considerations

### next() vs Indexing

```python
# For lists, direct indexing is simpler
lst = [1, 2, 3, 4, 5]

# Using next() - O(1) per call
it = iter(lst)
next(it)  # O(1)
next(it)  # O(1)

# Direct indexing - O(1)
lst[0]  # O(1)
lst[1]  # O(1)

# Prefer indexing for lists; next() for iterators
```

### Generator Memory

```python
# Generator with next() - O(1) memory
def infinite_counter():
    i = 0
    while True:
        yield i
        i += 1

gen = infinite_counter()
val1 = next(gen)  # O(1) memory
val2 = next(gen)  # O(1) memory
val3 = next(gen)  # O(1) memory

# vs. list - O(n) memory
lst = list(range(1000000))  # O(n) memory!
```

## Version Notes

- **Python 2.x**: `next()` function available; `iterator.next()` method also works
- **Python 3.x**: `next()` function standard; `iterator.next()` removed
- **All versions**: Iterator protocol with `__next__()` method

## Related Functions

- **[iter()](iter.md)** - Create iterator from iterable
- **[for loop](control_flow.md)** - Iterate using `next()` internally
- **[zip()](zip.md)** - Combine multiple iterators
- **[enumerate()](enumerate.md)** - Iterator with index

## Best Practices

✅ **Do**:
- Use `for` loops for normal iteration
- Use `next()` with default to avoid exceptions
- Use `next()` for special iterator control
- Use generator functions with `next()` for lazy evaluation

❌ **Avoid**:
- Calling `next()` without handling `StopIteration`
- Using `next()` when `for` loop is clearer
- Assuming `next()` is faster than for loops (it's not)
- Calling `next()` on non-iterators (raises TypeError)
