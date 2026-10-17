# reversed() Function Complexity

The `reversed()` function returns an iterator that yields a sequence's items from last to first. It
copies nothing: a type with a `__reversed__` method, such as `list`, `range`, `dict` or `deque`,
returns its own reverse iterator, and any other sequence is read backwards through `len()` and
indexing, one item per `next()`.

`n` is the items the reverse iterator yields. A user-defined `__reversed__`, `__len__` or
`__getitem__` costs what it does; the bounds below are the work `reversed()` and the built-in
reverse iterators add to them.

## Complexity Reference

### reversed()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `reversed(seq)` on a `list`, `range`, `dict`, dict view, `OrderedDict` or `deque` | O(1) | O(1) | Returns the type's own reverse iterator, without copying |
| `reversed(seq)` on a `tuple`, `str`, `bytes`, `bytearray`, `memoryview`, `array.array` or user sequence | O(1) | O(1) | Calls `len(seq)` once; each `next()` then calls `seq[i]` for i = len - 1 down to 0 |
| `reversed(obj)` with a user-defined `__reversed__` | Cost of `__reversed__` | Cost of `__reversed__` | Returns whatever the method returns |
| `reversed(obj)` on a `set`, an iterator, a generator, or a class with `__reversed__ = None` | O(1) | O(1) | Raises `TypeError` |
| `reversed(obj)` with `__getitem__` but no `__len__` | O(1) | O(1) | Raises `TypeError` |

### Iterating the Result

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `next()` on a reverse iterator | O(1) | O(1) | For a sequence read by indexing, plus one `seq[i]` call |
| `next()` on a reverse `dict` or dict view iterator | O(1) amortized | O(1) | Starts at the newest entry. A full pass is O(n), but deleting the newest keys one at a time leaves slots it scans past: after deleting most of them a pass costs the table's former size |
| A full pass over a sequence | O(n) | O(1) | |
| `list(reversed(seq))` | O(n) | O(n) | Builds a new list |
| `lst[::-1]` on a list | O(n) | O(n) | For comparison: copies the whole list before the first item is used |

## Reversing Without a Copy

### Iterating Backwards

`reversed()` reads the original sequence, so iterating backwards needs no second copy of it, where
slicing a list with `[::-1]` builds one first.

```python
numbers = [1, 2, 3, 4, 5]

backwards = reversed(numbers)  # O(1) - no copy
assert list(backwards) == [5, 4, 3, 2, 1]  # O(n)

assert numbers[::-1] == [5, 4, 3, 2, 1]  # O(n) time and space - a reversed copy
assert numbers == [1, 2, 3, 4, 5]  # Neither changes the original
```

### Stopping Early

The iterator produces items only when asked, so stopping after k items costs O(k), however long the
sequence is.

```python
readings = list(range(100_000))

latest = []
for value in reversed(readings):  # O(1) to create
    latest.append(value)
    if len(latest) == 3:
        break  # Only 3 items were read

assert latest == [99_999, 99_998, 99_997]
```

### The Length Is Fixed When reversed() Is Called

A reverse iterator over a list, or over a sequence read by indexing, starts at the length the
sequence had when `reversed()` was called, so items appended later are not yielded.

```python
items = [1, 2, 3]
backwards = reversed(items)
items.append(4)

assert list(backwards) == [3, 2, 1]
```

## Sequences Without `__reversed__`

`tuple`, `str`, `bytes` and other sequences have no `__reversed__`. For them, and for a class that
defines `__len__` and `__getitem__`, `reversed()` calls `len()` once and then fetches one index per
`next()`.

```python
class Squares:
    def __init__(self, count):
        self.count = count
        self.fetched = []

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        if not 0 <= index < self.count:
            raise IndexError(index)
        self.fetched.append(index)
        return index * index

squares = Squares(1_000)
backwards = reversed(squares)  # O(1) - fetches nothing
assert squares.fetched == []

assert next(backwards) == 998_001  # One __getitem__ call, for index 999
assert squares.fetched == [999]

assert "".join(reversed("hello")) == "olleh"  # O(n)
assert tuple(reversed((1, 2, 3))) == (3, 2, 1)  # O(n)
```

## Dicts and Their Views

A `dict` and its `keys()`, `values()` and `items()` views iterate backwards in reverse insertion
order. The reverse iterator starts from the newest entry, so after the most recently inserted keys
are deleted one at a time, its first `next()` scans past their slots, the mirror of a forward
iterator after the oldest keys are deleted. Rebuilding the dict makes it compact again.

```python
prices = {"apple": 3, "pear": 5, "plum": 2}

assert list(reversed(prices)) == ["plum", "pear", "apple"]  # O(n)
assert list(reversed(prices.values())) == [2, 5, 3]
assert next(reversed(prices.items())) == ("plum", 2)  # O(1)

d = {i: i for i in range(10_000)}
for i in range(1, 10_000):
    del d[i]  # Deletes the 9,999 newest keys

assert next(reversed(d)) == 0  # Scans the deleted slots first
d = dict(d)  # One scan of the old table; the new one is sized for what is left
assert next(reversed(d)) == 0  # O(1)
```

## What reversed() Rejects

`reversed()` needs either `__reversed__` or both `__len__` and `__getitem__`. A `set` has no order
to reverse, and an iterator or generator has no length, so both raise `TypeError`. Turning an
iterator into a list first works, at O(n) space.

```python
for value in [{1, 2, 3}, iter([1, 2, 3]), (x for x in [1, 2, 3])]:
    try:
        reversed(value)
    except TypeError as error:
        assert "is not reversible" in str(error)
    else:
        raise AssertionError("expected TypeError")

assert list(reversed(list(x for x in [1, 2, 3]))) == [3, 2, 1]  # O(n) space for the list
```

## Custom `__reversed__`

A class can supply its own reverse iterator. `reversed()` calls the method and returns its result,
so the cost is whatever the method does.

```python
class CountDown:
    def __init__(self, start):
        self.start = start

    def __reversed__(self):
        for i in range(1, self.start + 1):
            yield i

assert list(reversed(CountDown(5))) == [1, 2, 3, 4, 5]
```

## Common Patterns

### Walking Backwards with the Original Indexes

`enumerate(reversed(items))` numbers the items 0, 1, 2 in the order they are yielded. To keep each
item's original index, reverse a `range` instead; neither builds a copy.

```python
items = ["a", "b", "c", "d"]

assert list(enumerate(reversed(items))) == [(0, "d"), (1, "c"), (2, "b"), (3, "a")]

original = [(i, items[i]) for i in reversed(range(len(items)))]  # O(n), O(1) per step
assert original == [(3, "d"), (2, "c"), (1, "b"), (0, "a")]
```

## Performance Best Practices

✅ **Do**:

- Use `reversed(seq)` to iterate backwards without copying the sequence
- Use `reversed(range(len(seq)))` when you need the original indexes
- Break out of the loop once you have what you need; the rest is never read

❌ **Avoid**:

- `lst[::-1]` or `list(reversed(lst))` on a list just to loop once; both build an O(n) copy
- `reversed()` on an iterator or generator; it raises `TypeError` until you build a list
- Iterating a `dict` backwards repeatedly after deleting its newest keys without rebuilding it

## Related Functions

- **[iter() and next()](iter.md)** - Forward iteration, and the sparse-table cost from the other end
- **[list](list.md)** - `list.reverse()` reverses the list in place
- **[range()](range.md)** - `reversed(range(...))` is O(1) and yields indexes backwards
- **[sorted()](sorted.md)** - `sorted(seq, reverse=True)` sorts in descending order
- **[enumerate()](enumerate.md)** - Numbers the items as they are yielded
