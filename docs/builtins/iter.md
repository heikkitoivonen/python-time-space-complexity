# iter() and next() Functions Complexity

The `iter()` function gets an iterator from an iterable, and `next()` takes the next item from an
iterator. Neither copies anything: `iter()` wraps the object it was given or returns the object
itself, and `next()` produces one item at a time, so the items do not all have to exist at once.

`n` is the items an iterator yields. A user-defined `__iter__`, `__next__` or `__getitem__`, the
callable passed to `iter(callable, sentinel)`, and the function or predicate given to `map()` or
`filter()` cost what they do; the bounds below are the work `iter()` and `next()` add to them. `k` is the items a `filter` iterator examines to return
one: the items it skips, plus the one it returns.

## Complexity Reference

### iter()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `iter(iterable)` | O(1) | O(1) | Built-in containers return a new iterator over the same object, without copying it |
| `iter(iterator)` | O(1) | O(1) | Returns the iterator itself |
| `iter(sequence)` without `__iter__` | O(1) | O(1) | Falls back to `__getitem__`: each `next()` calls `sequence[i]` for i = 0, 1, ... until `IndexError` |
| `iter(callable, sentinel)` | O(1) | O(1) | Nothing is called until the first `next()` |

### next()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `next(iterator)` | O(1) | O(1) | Iterators over `list`, `tuple`, `str`, `bytes` and `range`; any other iterator costs what its `__next__` does |
| `next(iterator, default)` | Same as `next(iterator)` | Same as `next(iterator)` | Returns `default` instead of raising `StopIteration` |
| `next()` on a `dict` or `set` iterator | O(1) amortized | O(1) | A full pass is O(n), but deleting single keys (`del d[key]`, `d.pop(key)`, `s.remove(x)`, `s.discard(x)`) does not shrink the table: after deleting most entries a pass costs the table's former size |
| `next()` on `iter(callable, sentinel)` | O(1) | O(1) | Plus one call of the callable, whose result is compared with `sentinel` by `==`; once it matches, later calls raise without calling it |
| `next()` on a `filter` iterator | O(k) | O(1) | Plus one predicate call per examined item |
| `next()` on a `map` iterator | O(m) | O(m) | m = input iterables: one item is taken from each, plus one call of the function |

## Creating Iterators

### Iterating Over Sequences

A `for` loop calls `iter()` once and `next()` once per item, so a manual loop has the same O(n)
cost.

```python
lst = [10, 20, 30]
iterator = iter(lst)  # O(1) - no copy of the list

seen = []
while True:
    try:
        seen.append(next(iterator))  # O(1) per call
    except StopIteration:
        break
assert seen == [10, 20, 30]

# Equivalent for loop: iter() once, next() per item
assert [item for item in lst] == seen
```

### Iterators Return Themselves

`iter()` on an iterator returns the same object, which is why an iterator can be advanced by hand
and then handed to a `for` loop, and why it is exhausted after one pass.

```python
data = ["header", "row1", "row2", "row3"]
it = iter(data)
assert iter(it) is it  # O(1) - same object, no new iterator

header = next(it)  # O(1) - consume the first item separately
rows = [row for row in it]  # O(n) - continues from the second item
assert header == "header"
assert rows == ["row1", "row2", "row3"]

assert list(it) == []  # Exhausted: a second pass yields nothing
```

### The `__getitem__` Fallback

An object with `__getitem__` but no `__iter__` is still iterable: `iter()` wraps it, and each
`next()` asks for the next index until the object raises `IndexError`.

```python
class Squares:
    def __init__(self, count):
        self.count = count

    def __getitem__(self, index):
        if index >= self.count:
            raise IndexError(index)
        return index * index

it = iter(Squares(4))  # O(1) - nothing is fetched yet
assert next(it) == 0   # Calls __getitem__(0)
assert list(it) == [1, 4, 9]
```

## Callable Iterator Pattern

### Creating Iterator from Callable

`iter(callable, sentinel)` calls the callable once per `next()` and stops at the first result equal
to the sentinel. The sentinel itself is not yielded.

```python
values = [3, 1, 4, 0, 5]

def read_value():
    return values.pop(0)

iterator = iter(read_value, 0)  # O(1) - read_value is not called yet
assert values == [3, 1, 4, 0, 5]

assert next(iterator) == 3  # One call of read_value
assert list(iterator) == [1, 4]  # Stops at 0
assert values == [5]  # The 5 after the sentinel is never read
```

### Reading a File in Chunks

With a `read(size)` call as the callable, the loop holds one chunk at a time instead of the whole
file. The total cost is O(n) in the characters read; memory is O(chunk size).

```python
import io
from functools import partial

f = io.StringIO("x" * 2500)

total = 0
largest = 0
for chunk in iter(partial(f.read, 1024), ''):  # O(1) to create
    total += len(chunk)  # O(chunk size) per read
    largest = max(largest, len(chunk))

assert total == 2500
assert largest == 1024  # Each read returns at most 1024 characters
```

## Using next()

### Basic next() Usage

```python
lst = [10, 20, 30]
it = iter(lst)

assert next(it) == 10  # O(1)
assert next(it) == 20  # O(1)
assert next(it) == 30  # O(1)

# next() after exhaustion raises StopIteration
try:
    next(it)
except StopIteration:
    pass
else:
    raise AssertionError("expected StopIteration")
```

### Using Default Value

```python
it = iter([1, 2, 3])
assert [next(it), next(it), next(it)] == [1, 2, 3]
assert next(it, "END") == "END"  # O(1) - default instead of StopIteration

# The first item matching a condition, or None - stops at the first match
first_even = next((x for x in [1, 3, 4, 5, 6] if x % 2 == 0), None)
assert first_even == 4
```

### next() Needs an Iterator

`next()` accepts only an iterator. A list or a `range` is iterable but not an iterator: call
`iter()` on it first.

```python
try:
    next([1, 2, 3])
except TypeError as error:
    assert "is not an iterator" in str(error)
else:
    raise AssertionError("expected TypeError")

assert next(iter(range(3))) == 0
```

## Custom Iterators

### Implementing Iterator Protocol

```python
class CountUp:
    def __init__(self, maximum):
        self.maximum = maximum
        self.current = 0

    def __iter__(self):
        return self  # O(1) - an iterator returns itself

    def __next__(self):
        if self.current < self.maximum:
            self.current += 1
            return self.current  # O(1)
        raise StopIteration

counter = CountUp(3)
it = iter(counter)  # O(1)
assert it is counter

assert next(it) == 1  # O(1)
assert next(it) == 2  # O(1)
assert next(it) == 3  # O(1)
assert next(it, None) is None
```

### Custom Iterable with Iterator

`Range` below is not its own iterator: each `iter()` call returns a fresh one, so it can be
traversed more than once.

```python
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
        raise StopIteration

r = Range(0, 3)
it1 = iter(r)  # O(1) - fresh iterator
it2 = iter(r)  # O(1) - another fresh iterator
assert it1 is not it2
assert list(it1) == [0, 1, 2]
assert list(it2) == [0, 1, 2]  # Independent of it1
```

## Generator Functions

### Generators Use iter() and next()

```python
def count_up(maximum):
    i = 0
    while i < maximum:
        yield i  # Yields value, pauses execution
        i += 1

gen = count_up(3)  # O(1) - the body has not started
assert iter(gen) is gen  # A generator is its own iterator

assert next(gen) == 0  # Runs the body up to the first yield
assert next(gen) == 1  # O(1) - resumes after the yield
assert next(gen) == 2  # O(1)

assert [item for item in count_up(3)] == [0, 1, 2]
```

### Generator Expression

```python
gen = (x**2 for x in range(5))  # O(1) - nothing is squared yet

assert next(gen) == 0  # O(1)
assert next(gen) == 1  # O(1)
assert next(gen) == 4  # O(1)
assert list(gen) == [9, 16]  # The remaining items
```

## Common Patterns

### Converting to List (Forces Evaluation)

```python
it = iter([1, 2, 3, 4, 5])  # O(1)

lst = list(it)  # O(n) time and space - takes every remaining item
assert lst == [1, 2, 3, 4, 5]

# The iterator is now exhausted
assert next(it, None) is None
```

### Chaining Multiple Iterators

```python
from itertools import chain

it1 = iter([1, 2, 3])
it2 = iter([4, 5, 6])
it3 = iter([7, 8, 9])

# O(1) to create; O(n) in total over all three, one item at a time
assert list(chain(it1, it2, it3)) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
```

### Zip with Iterators

```python
it1 = iter([1, 2, 3])
it2 = iter(['a', 'b', 'c'])

paired = zip(it1, it2)  # O(1) to create
assert list(paired) == [(1, 'a'), (2, 'b'), (3, 'c')]  # O(n) total

# Equivalent manual iteration
it1 = iter([1, 2, 3])
it2 = iter(['a', 'b', 'c'])
pairs = []
while True:
    try:
        pairs.append((next(it1), next(it2)))  # O(1) each
    except StopIteration:
        break
assert pairs == [(1, 'a'), (2, 'b'), (3, 'c')]
```

## Performance Considerations

### Iterator vs List Memory

A generator holds its local variables and the current item, not the items it has produced, so a
generator whose state is a counter uses O(1) memory however many items it yields. A list of the
same items holds all n of them.

```python
def infinite_count():
    i = 0
    while True:
        yield i
        i += 1

gen = infinite_count()  # O(1) memory, even though it never ends
assert [next(gen) for _ in range(3)] == [0, 1, 2]

lst = list(range(10_000))  # O(n) memory - every item is stored
assert len(lst) == 10_000
```

### Lazy Evaluation Benefits

A loop over a generator can stop early, and the items it never reached are never produced. Building
a list first produces every item before the loop starts.

```python
produced = []

def get_data():
    for i in range(10_000):
        produced.append(i)
        yield i

for item in get_data():  # Stops early: later items are never made
    if item > 100:
        break
assert len(produced) == 102  # Items 0 to 101, nothing after

data = list(range(10_000))  # O(n) - every item made up front
for item in data:
    if item > 100:
        break
assert len(data) == 10_000
```

### Dict and Set Iterators After Removal

Iterating a `dict` or `set` scans its hash table, and deleting single keys (`del d[key]`,
`d.pop(key)`, `s.remove(x)`, `s.discard(x)`) does not shrink the table. After most keys are deleted,
a pass still takes time proportional to the size the table had, until a later insertion triggers a
resize. Rebuild the container, at the cost of one more pass over the old table, if a small survivor
will be iterated often.

```python
d = {i: i for i in range(10_000)}
for i in range(9_999):
    del d[i]

assert next(iter(d)) == 9_999  # Scans the deleted slots first
d = dict(d)  # One scan of the old table; the new one is sized for what is left
assert next(iter(d)) == 9_999  # O(1)
```

## Built-in Iterator Functions

### map() Returns Iterator

```python
calls = []

def square(x):
    calls.append(x)
    return x ** 2

it = map(square, [1, 2, 3, 4, 5])  # O(1) - nothing is called yet
assert calls == []

assert next(it) == 1  # One call of square
assert next(it) == 4
assert next(it) == 9
assert calls == [1, 2, 3]
```

### filter() Returns Iterator

One `next()` on a `filter` calls the predicate on each item it examines, so it costs O(k); a full
pass calls it once per input item, linear in the input in total.

```python
checked = []

def is_even(x):
    checked.append(x)
    return x % 2 == 0

it = filter(is_even, [1, 3, 5, 6, 7, 8])  # O(1)

assert next(it) == 6  # O(k) - examines 1, 3, 5 and 6
assert checked == [1, 3, 5, 6]

assert list(it) == [8]  # Examines the rest of the input
assert checked == [1, 3, 5, 6, 7, 8]
```

### enumerate() Returns Iterator

```python
it = enumerate(['a', 'b', 'c'])  # O(1)

assert next(it) == (0, 'a')  # O(1)
assert next(it) == (1, 'b')  # O(1)
assert next(it) == (2, 'c')  # O(1)
```

## Version Notes

- **All Python 3**: `range()` returns a lazy sequence, not an iterator: `next(range(3))` raises
  `TypeError`, and every `iter()` over it starts again from the beginning.

## Related Functions

- **[zip()](zip.md)** - Iterate multiple sequences
- **[map()](map.md)** - Transform iterator items
- **[filter()](filter.md)** - Filter iterator items
- **[enumerate()](enumerate.md)** - Get index and value
- **[range()](range.md)** - Lazy sequence, iterable many times

## Best Practices

✅ **Do**:

- Use `for` loops; they call `iter()` once and `next()` per item
- Use generators to avoid holding a long or unbounded stream in memory
- Use `next(iterator, default)` to take one item without handling `StopIteration`
- Use `iter(callable, sentinel)` to turn repeated `read()` calls into a loop

❌ **Avoid**:

- Iterating an iterator twice: the second pass yields nothing
- `list()` on an iterator you will stop reading early; it produces every item first
- Iterating a `dict` or `set` repeatedly after deleting most of its entries without rebuilding it
