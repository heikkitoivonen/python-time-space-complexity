# iter() and next() Functions Complexity

The `iter()` function creates an iterator object from an iterable, and `next()` retrieves the next item from an iterator.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `iter(iterable)` | O(1) | O(1) | Create iterator from iterable |
| `iter(callable, sentinel)` | O(1) | O(1) | Create callable iterator |
| `next(iterator)` | O(1)* | O(1) | Get next item |
| `next(iterator, default)` | O(1)* | O(1) | Get next or default |

*O(1) for built-in types; may vary for custom iterators (e.g., filter iterator is O(k) where k items are skipped)

## Creating Iterators

### Basic Iterator Creation

```python
# Create iterator from list - O(1)
lst = [1, 2, 3, 4, 5]
it = iter(lst)  # O(1) - returns list iterator

# Create iterator from string - O(1)
s = "hello"
it = iter(s)  # O(1) - returns string iterator

# Create iterator from dict - O(1)
d = {'a': 1, 'b': 2}
it = iter(d)  # O(1) - returns dict_keyiterator

# Create iterator from set - O(1)
st = {1, 2, 3}
it = iter(st)  # O(1) - returns set iterator
```

### Iterating Over Sequences

```python
# Manual iteration using iter() and next() - O(1) per item
lst = [10, 20, 30]
iterator = iter(lst)

while True:
    try:
        item = next(iterator)  # O(1) per call
        print(item)
    except StopIteration:
        break

# Equivalent to for loop
for item in lst:  # for loop internally uses iter() and next()
    print(item)
```

## Callable Iterator Pattern

### Creating Iterator from Callable

```python
# Create iterator from callable with sentinel - O(1)
def read_line():
    """Simulate reading from a file"""
    # Would read actual file in real scenario
    pass

# Create iterator that calls function until sentinel reached
iterator = iter(read_line, "EOF")  # O(1)

# Get items until sentinel - O(1) per next() call
item = next(iterator)  # O(1)
```

### Real-world Example: File Reading

```python
# Read file without loading all in memory - O(1) per line
with open('largefile.txt') as f:
    # Create iterator from lambda until empty string
    iterator = iter(lambda: f.read(1024), '')  # O(1) to create
    
    for chunk in iterator:  # O(n) to iterate, O(1) per chunk
        process(chunk)  # O(1)
```

## Using next()

### Basic next() Usage

```python
# Get next item - O(1)
lst = [10, 20, 30]
it = iter(lst)

item1 = next(it)  # 10 - O(1)
item2 = next(it)  # 20 - O(1)
item3 = next(it)  # 30 - O(1)

# next() after exhaustion raises StopIteration
try:
    item4 = next(it)  # Raises StopIteration
except StopIteration:
    print("Iterator exhausted")
```

### Using Default Value

```python
# Use default if iterator exhausted - O(1)
it = iter([1, 2, 3])
next(it)  # 1
next(it)  # 2
next(it)  # 3
item = next(it, "END")  # "END" - returns default instead of raising

# Useful for safe iteration
def safe_next(iterator, default=None):
    return next(iterator, default)  # O(1)
```

## Custom Iterators

### Implementing Iterator Protocol

```python
# Custom iterator class - O(1) per operation
class CountUp:
    def __init__(self, max):
        self.max = max
        self.current = 0
    
    def __iter__(self):
        return self  # O(1) - return iterator itself
    
    def __next__(self):
        if self.current < self.max:
            self.current += 1
            return self.current  # O(1)
        else:
            raise StopIteration

# Usage
counter = CountUp(3)
it = iter(counter)  # O(1)

item1 = next(it)  # 1 - O(1)
item2 = next(it)  # 2 - O(1)
item3 = next(it)  # 3 - O(1)
```

### Custom Iterable with Iterator

```python
# Iterable that creates fresh iterator - O(1)
class Range:
    def __init__(self, start, stop):
        self.start = start
        self.stop = stop
    
    def __iter__(self):
        return RangeIterator(self.start, self.stop)  # O(1)

class RangeIterator:
    def __init__(self, start, stop):
        self.current = start
        self.stop = stop
    
    def __iter__(self):
        return self  # O(1)
    
    def __next__(self):
        if self.current < self.stop:
            value = self.current
            self.current += 1
            return value  # O(1)
        else:
            raise StopIteration

# Usage
r = Range(0, 3)
it1 = iter(r)  # O(1) - fresh iterator
it2 = iter(r)  # O(1) - another fresh iterator
```

## Generator Functions

### Generators use iter() and next()

```python
# Generator function returns iterator - O(1)
def count_up(max):
    i = 0
    while i < max:
        yield i  # Yields value, pauses execution
        i += 1

# Create iterator from generator - O(1)
gen = count_up(3)  # O(1) - returns generator object

# Iterate using next() - O(1) per call
item1 = next(gen)  # 0 - O(1), resumes at yield
item2 = next(gen)  # 1 - O(1)
item3 = next(gen)  # 2 - O(1)

# For loop equivalent
for item in count_up(3):  # Uses iter() and next() internally
    print(item)
```

### Generator Expression

```python
# Generator expression returns iterator - O(1)
gen = (x**2 for x in range(5))  # O(1) - lazy evaluation

# Iterate using next() - O(1) per item
item1 = next(gen)  # 0 - O(1)
item2 = next(gen)  # 1 - O(1)
item3 = next(gen)  # 4 - O(1)

# For loop
for item in (x**2 for x in range(5)):  # O(1) per iteration
    print(item)
```

## Common Patterns

### Converting to List (Forces Evaluation)

```python
# Create iterator - O(1)
it = iter([1, 2, 3, 4, 5])

# Convert to list - forces all iterations O(n)
lst = list(it)  # O(5) - calls next() 5 times

# Iterator is now exhausted
try:
    next(it)  # Raises StopIteration
except StopIteration:
    print("Exhausted")
```

### Chaining Multiple Iterators

```python
# Create multiple iterators - O(1) each
it1 = iter([1, 2, 3])
it2 = iter([4, 5, 6])
it3 = iter([7, 8, 9])

# Iterate through each - O(n) total
for it in [it1, it2, it3]:
    while True:
        try:
            item = next(it)  # O(1) per call
            print(item)
        except StopIteration:
            break
```

### Zip with Iterators

```python
# Create iterators - O(1) each
it1 = iter([1, 2, 3])
it2 = iter(['a', 'b', 'c'])

# zip pairs items from iterators - O(1) to create
paired = zip(it1, it2)

# Iterate - O(1) per pair
for num, letter in paired:  # O(n) total
    print(num, letter)

# Equivalent manual iteration
it1 = iter([1, 2, 3])
it2 = iter(['a', 'b', 'c'])
while True:
    try:
        item1 = next(it1)  # O(1)
        item2 = next(it2)  # O(1)
        print(item1, item2)
    except StopIteration:
        break
```

## Performance Considerations

### Iterator vs List Memory

```python
# Iterator - constant memory O(1)
def infinite_count():
    i = 0
    while True:
        yield i
        i += 1

gen = infinite_count()  # O(1) memory
item1 = next(gen)  # O(1)
item2 = next(gen)  # O(1)

# List - linear memory O(n)
lst = list(range(1000000))  # O(n) memory!
```

### Lazy Evaluation Benefits

```python
import itertools

# Create iterator (lazy) - O(1)
def get_data():
    for i in range(1000000):
        yield i

# Don't load all in memory
for item in get_data():  # O(1) per item, O(1) total memory
    if item > 100:
        break  # Can stop early without processing all

# Avoid with list
data = list(range(1000000))  # O(n) memory - loaded all upfront!
for item in data:
    if item > 100:
        break
```

### Efficient Filtering

```python
# Generator with filter (lazy) - O(1) per item
def filtered_data():
    for i in range(1000000):
        if i % 2 == 0:
            yield i

# Process only needed items
for item in filtered_data():  # O(1) per item, stop early
    print(item)
    if item > 100:
        break

# Vs materializing to list
data = [i for i in range(1000000) if i % 2 == 0]  # O(n) memory
for item in data:
    print(item)
    if item > 100:
        break
```

## Built-in Iterator Functions

### map() Returns Iterator

```python
# map creates iterator (lazy) - O(1)
def square(x):
    return x ** 2

it = map(square, [1, 2, 3, 4, 5])  # O(1)

# Iterate - O(1) per item
item1 = next(it)  # 1 - O(1)
item2 = next(it)  # 4 - O(1)
item3 = next(it)  # 9 - O(1)
```

### filter() Returns Iterator

```python
# filter creates iterator (lazy) - O(1)
def is_even(x):
    return x % 2 == 0

it = filter(is_even, [1, 2, 3, 4, 5])  # O(1)

# Iterate - O(1) per item
for item in it:  # O(n) total, O(1) per item
    print(item)
```

### enumerate() Returns Iterator

```python
# enumerate creates iterator - O(1)
it = enumerate(['a', 'b', 'c'])  # O(1)

# Iterate - O(1) per item
item1 = next(it)  # (0, 'a') - O(1)
item2 = next(it)  # (1, 'b') - O(1)
item3 = next(it)  # (2, 'c') - O(1)
```

## Version Notes

- **Python 2.x**: `range()` returns list, not iterator (use `xrange()` for iterator)
- **Python 3.x**: `range()` returns iterator-like object, `map()` and `filter()` return iterators
- **All versions**: Iterator protocol with `__iter__()` and `__next__()` (Python 3) or `next()` (Python 2)

## Related Functions

- **[zip()](zip.md)** - Iterate multiple sequences
- **[map()](map.md)** - Transform iterator items
- **[filter()](filter.md)** - Filter iterator items
- **[enumerate()](enumerate.md)** - Get index and value
- **[range()](range.md)** - Iterator-like sequence

## Best Practices

✅ **Do**:
- Use `iter()` and `next()` for custom iterators
- Use generators for memory-efficient iteration
- Use default value in `next()` to avoid exceptions
- Use `for` loops (they use `iter()` and `next()` internally)

❌ **Avoid**:
- Calling `next()` without handling `StopIteration`
- Creating iterators you won't use (lazy evaluation wasted)
- Assuming you can iterate an iterator twice (exhausts on first pass)
- Using `next()` in tight loops without performance profiling
