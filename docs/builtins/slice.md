# slice() Function Complexity

The `slice()` function builds a slice object: the `start`, `stop` and `step` that `seq[start:stop:step]`
names, held as an object so it can be stored, passed around and reused. Building one costs O(1) and
copies nothing. Applying it is the sequence's own operation, and its cost belongs to the type: a
`list` copies the selected items, while a `range` or a `memoryview` returns a new view in O(1).

`k` is the items a slice selects, `n` is the items in the sequence, and `i` and `j` are the slice's
start and stop after `indices()` resolves them, with `j` raised to `i` when the stop falls before
the start. The parts are taken to be ints or `None`, so index arithmetic, comparing and hashing
them are O(1), as they are for ints that fit in a machine word; a custom `__getitem__` costs what
its own code does.

## Complexity Reference

### slice

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `slice(stop)`, `slice(start, stop, step=None)` | O(1) | O(1) | Stores the objects as given, without checking or converting them; missing parts are `None` |
| `slice.start`, `slice.stop`, `slice.step` | O(1) | O(1) | The objects passed in, not copies |
| `slice.indices(length)` | O(1) | O(1) | Fills in defaults and clamps to `length`, returning `(start, stop, step)`; `ValueError` for a zero step |
| `s == t`, `s < t` | O(1) | O(1) | Compared as the tuple `(start, stop, step)` |
| `hash(s)` | O(1) | O(1) | Python 3.12+; raises `TypeError` if a part is unhashable |

### Applying a slice

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `seq[s]` on a `list`, `tuple`, `str`, `bytes` or `bytearray` | O(k) | O(k) | Copies the k selected items, whatever `n` is; O(j - i) for a step of 1 |
| `seq[:]` on an exact `tuple`, `str` or `bytes` | O(1) | O(1) | Returns the object itself: it is immutable, so nothing is copied |
| `r[s]` on a `range` | O(1) | O(1) | Returns a new `range`; no items are produced |
| `v[s]` on a `memoryview` | O(1) | O(1) | Returns a new view on the same buffer; no bytes are copied |
| `lst[s] = t` on a list, step 1 | O(j - i) if `len(t) == j - i`, otherwise O(n - i + len(t)) amortized | O(j - i + len(t)) | Equal lengths overwrite in place; otherwise everything after `j` moves |
| `del lst[s]` on a list, step 1 | O(n - i) | O(j - i) | Everything after `j` moves left |
| `obj[s]` with a custom `__getitem__` | Cost of the method | Cost of the method | It receives the slice object itself; `obj[a:b, c:d]` passes a tuple of two slices |

## Creating Slice Objects

### Building a Slice

A slice holds whatever it was given. Nothing is checked until a sequence uses it, so a slice can
carry any objects a custom `__getitem__` wants to interpret.

```python
s = slice(2, 5)  # O(1)
assert (s.start, s.stop, s.step) == (2, 5, None)

assert slice(5) == slice(None, 5, None)  # One argument is the stop

key = ["a"]
labels = slice(key, "z")  # Any objects are accepted
assert labels.start is key  # Stored as given, not copied
```

### Resolving Indices for a Length

`indices(length)` turns a slice into concrete `range()` arguments for a sequence of that length, so
`range(*s.indices(len(seq)))` visits the same positions as `seq[s]`.

```python
s = slice(1, 10, 2)
assert s.indices(5) == (1, 5, 2)  # O(1) - stop clamped to the length

assert slice(None, None, -1).indices(5) == (4, -1, -1)
assert slice(-100, 100).indices(5) == (0, 5, 1)

data = [10, 20, 30, 40, 50]
assert [data[i] for i in range(*s.indices(len(data)))] == data[s]

try:
    slice(0, 5, 0).indices(5)
except ValueError as error:
    assert "cannot be zero" in str(error)
else:
    raise AssertionError("expected ValueError")
```

### Slices as Keys

From Python 3.12, a slice whose parts are hashable can be a dictionary key or a set member.

```python
import sys

if sys.version_info >= (3, 12):
    cache = {slice(0, 10): "first ten"}  # O(1) hash
    assert cache[slice(0, 10)] == "first ten"

assert slice(1, 2) < slice(1, 3)  # Compared like (start, stop, step)
```

## Applying Slices

### Copying Sequences

Slicing a `list`, `tuple`, `str`, `bytes` or `bytearray` builds a new object holding the selected
items, so the cost follows the items selected, not the length of the source. A step only changes
which items those are.

```python
data = list(range(1_000))

first = data[slice(3)]  # O(k) - 3 items, however long data is
assert first == [0, 1, 2]

every_100th = data[slice(None, None, 100)]  # O(k) - 10 items
assert every_100th == [0, 100, 200, 300, 400, 500, 600, 700, 800, 900]

backwards = data[slice(None, None, -1)]  # O(n) - every item, reversed
assert backwards[0] == 999 and len(backwards) == 1_000
```

### Slices That Copy Nothing

An exact `tuple`, `str` or `bytes` returns itself for a full slice. A `range` slice is another
`range`, and a `memoryview` slice is another view on the same memory, both O(1) at any size.

```python
t = (1, 2, 3)
assert t[:] is t  # O(1) - no copy of an immutable tuple
items = [1, 2, 3]
assert items[:] is not items  # O(n) - a list slice is always a new list

r = range(0, 10**12, 2)
assert r[slice(10, 20)] == range(20, 40, 2)  # O(1) - no items produced

buffer = bytearray(b"abcdef")
view = memoryview(buffer)[slice(1, 4)]  # O(1) - shares buffer
buffer[1] = ord("B")
assert bytes(view) == b"Bcd"
```

### Assigning and Deleting

On a list, replacing a step-1 slice with the same number of items overwrites them in place. Any
other length, and deleting a non-empty step-1 slice, moves every item after it.

```python
lst = list(range(10))

lst[slice(0, 3)] = ["a", "b", "c"]  # O(j - i) - same length, nothing moves
assert lst[:4] == ["a", "b", "c", 3]

lst[slice(0, 3)] = ["x"]  # O(n - i + len(t)) - the rest moves left
assert lst[:2] == ["x", 3] and len(lst) == 8

del lst[slice(-2, None)]  # O(n - i) - only the last two, nothing after them
assert lst == ["x", 3, 4, 5, 6, 7]
```

## Slices in Custom Classes

A custom `__getitem__` receives the slice object. Calling `indices()` with the sequence's length
gives the same clamping as the built-in types.

```python
class Squares:
    def __init__(self, n):
        self.n = n

    def __len__(self):
        return self.n

    def __getitem__(self, key):
        if isinstance(key, slice):
            return [i * i for i in range(*key.indices(self.n))]  # O(k)
        if not 0 <= key < self.n:
            raise IndexError(key)
        return key * key  # O(1)


squares = Squares(1_000_000)
assert squares[2:5] == [4, 9, 16]
assert squares[slice(None, 6, 2)] == [0, 4, 16]
assert squares[3] == 9


class Grid:
    def __getitem__(self, key):
        return key


assert Grid()[1:2, 3:4] == (slice(1, 2), slice(3, 4))  # A tuple of slices
```

## Common Patterns

### Iterating Without Copying

`data[s]` copies the k items before the loop starts. `range(*s.indices(len(data)))` visits the same
positions without the copy. `itertools.islice()` also avoids the copy, but it works on any iterator
by stepping through it, so it advances past the `start` items too.

```python
from itertools import islice

data = list(range(1_000))
s = slice(100, 110)

copied = data[s]  # O(k) time and space
total = sum(data[i] for i in range(*s.indices(len(data))))  # O(k) time, O(1) space
assert copied == list(range(100, 110)) and total == sum(copied)

taken = []
def numbers():
    for value in data:
        taken.append(value)
        yield value

assert list(islice(numbers(), 100, 110)) == copied
assert len(taken) == 110  # islice stepped through start + k items
```

## Performance Best Practices

✅ **Do**:

- Slice a `memoryview` of `bytes` or `bytearray` when you only need a window: it is O(1), where slicing the bytes copies k of them
- Use `range(*s.indices(len(seq)))` to visit a slice's positions without copying them
- Replace a list slice with the same number of items when you can, so nothing after it moves

❌ **Avoid**:

- `lst[:]` or `lst[::-1]` on a large list just to read it; both copy every item
- `del lst[:k]` repeatedly on a long list to consume it from the front; each deletion moves the rest
- `islice(seq, start, stop)` on an indexable sequence when `start` is large; it steps past the
  first `start` items one at a time

## Version Notes

- **Python 3.12+**: Slice objects are hashable when their parts are, so they can be dictionary keys

## Related Functions

- **[list](list.md)** - Slice reads, assignment and deletion on a list
- **[range()](range.md)** - O(1) slicing that returns another range
- **[memoryview()](memoryview_func.md)** - O(1) slicing without copying bytes
- **[itertools.islice()](../stdlib/itertools.md)** - Slicing any iterator, by stepping through it
