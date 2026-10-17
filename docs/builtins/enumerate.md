# enumerate() Function Complexity

The `enumerate(iterable, start=0)` function returns an iterator of `(index, item)` tuples. It
is lazy: building it calls `iter(iterable)` and consumes nothing, and each step takes one item
from that iterator and pairs it with a counter.

`n` is the number of items taken from the enumerate object. Getting each item from the
underlying iterator is priced at O(1), as it is for lists, tuples, strings and ranges; an
iterator that does more work per item adds that cost to every step. Each index is priced at O(1),
which holds for a `start` that fits in a machine word.

## Complexity Reference

### enumerate

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enumerate(iterable, start=0)` | O(1) | O(1) | Calls `iter(iterable)` once and takes no items; a non-iterable raises `TypeError` here |
| `next()` on an enumerate object | O(1) | O(1) | Takes one item from the underlying iterator |
| Iterating an enumerate object | O(n) | O(1) | Tuples are produced one at a time, not accumulated |
| `list(enumerate(iterable))` | O(n) | O(n) | Holds all n tuples |
| `enumerate[T]` | O(1) | O(1) | A generic alias for type hints |

## Basic Usage

### Simple Enumeration

```python
items = ['a', 'b', 'c']

pairs = []
for index, item in enumerate(items):      # O(n)
    pairs.append((index, item))
assert pairs == [(0, 'a'), (1, 'b'), (2, 'c')]

assert list(enumerate(items)) == [(0, 'a'), (1, 'b'), (2, 'c')]   # O(n) time and space
```

### Custom Start Index

`start` sets the first index. It must be an int, or an object with `__index__`.

```python
items = ['a', 'b', 'c']

assert list(enumerate(items, start=1)) == [(1, 'a'), (2, 'b'), (3, 'c')]
assert list(enumerate(items, 10)) == [(10, 'a'), (11, 'b'), (12, 'c')]
assert list(enumerate(items, -1)) == [(-1, 'a'), (0, 'b'), (1, 'c')]

try:
    enumerate(items, start=1.5)
except TypeError as exc:
    assert "cannot be interpreted as an integer" in str(exc)
else:
    raise AssertionError("a float start did not raise")
```

## Lazy, Single-Pass Iteration

Building an enumerate object takes no items, and a loop that stops early pays only for the
items it took. The object is an iterator over its iterator, so it can be consumed once.

```python
taken = []

def numbers():
    for value in range(10**9):
        taken.append(value)
        yield value

pairs = enumerate(numbers())      # O(1) - nothing is taken yet
assert taken == []

for index, value in pairs:        # O(k) for k items taken
    if index == 3:
        break
assert taken == [0, 1, 2, 3]

assert next(pairs) == (4, 4)      # O(1) - resumes where the loop stopped
```

```python
pairs = enumerate(['a', 'b'])
assert list(pairs) == [(0, 'a'), (1, 'b')]
assert list(pairs) == []          # already exhausted

try:
    len(enumerate(['a', 'b']))
except TypeError as exc:
    assert "has no len()" in str(exc)
else:
    raise AssertionError("len() did not raise")

try:
    enumerate(['a', 'b'])[0]
except TypeError as exc:
    assert "not subscriptable" in str(exc)
else:
    raise AssertionError("indexing did not raise")
```

To reverse or index the pairs, build a list first, which costs O(n) time and space:

```python
pairs = list(enumerate(['a', 'b', 'c']))      # O(n)
assert pairs[::-1] == [(2, 'c'), (1, 'b'), (0, 'a')]
assert pairs[1] == (1, 'b')
```

## enumerate() vs range(len(...))

`for i in range(len(seq))` with `seq[i]` needs a sequence that supports `len()` and indexing, and
each `seq[i]` adds the cost of indexing that sequence. On a list that is O(1), so both loops are
O(n). On a `deque`, indexing away from the ends is O(n), which makes the loop O(n²), while
`enumerate()` walks the deque once. `enumerate()` also works on generators, files and other
iterables that cannot be indexed.

```python
from collections import deque

d = deque(range(1000))

by_index = [(i, d[i]) for i in range(len(d))]    # O(n²) - each d[i] walks the deque
by_enumerate = list(enumerate(d))               # O(n)
assert by_index == by_enumerate

lines = iter(['first', 'second'])
assert list(enumerate(lines, start=1)) == [(1, 'first'), (2, 'second')]
```

## Common Patterns

### Finding Every Position

One pass with `enumerate()` finds every match in O(n). `list.index()` returns only the first
match, and raises `ValueError` when there is none.

```python
items = ['apple', 'banana', 'cherry', 'banana']

positions = [i for i, item in enumerate(items) if item == 'banana']   # O(n)
assert positions == [1, 3]

assert items.index('banana') == 1     # O(n) - first match only

try:
    items.index('date')
except ValueError:
    pass
else:
    raise AssertionError("index() found a missing item")
```

### Pairing with zip()

```python
names = ['Alice', 'Bob', 'Charlie']
ages = [30, 25, 35]

rows = [f"{i}: {name} is {age}" for i, (name, age) in enumerate(zip(names, ages))]   # O(n)
assert rows == ["0: Alice is 30", "1: Bob is 25", "2: Charlie is 35"]
```

### Building a Lookup Table

```python
items = ['apple', 'banana', 'cherry']

by_number = dict(enumerate(items, start=1))               # O(n)
assert by_number == {1: 'apple', 2: 'banana', 3: 'cherry'}

position = {item: i for i, item in enumerate(items)}      # O(n) once, then O(1) lookups
assert position['cherry'] == 2
```

## Edge Cases

```python
assert list(enumerate([])) == []
assert list(enumerate('ab')) == [(0, 'a'), (1, 'b')]
assert list(enumerate({'x': 1, 'y': 2})) == [(0, 'x'), (1, 'y')]   # dict keys

try:
    enumerate(42)
except TypeError as exc:      # raised when the object is built, not when it is iterated
    assert "not iterable" in str(exc)
else:
    raise AssertionError("enumerate(42) did not raise")
```

## Performance Best Practices

✅ **Do**:

- Use `enumerate()` when you need both the index and the item - one O(n) pass over any iterable
- Use `break` to stop early - only the items taken are paid for
- Build an `{item: index}` dict once when you look up positions of distinct, hashable items repeatedly

❌ **Avoid**:

- `range(len(seq))` with `seq[i]` on a `deque` or another sequence with costly indexing - O(n²)
- `list(enumerate(...))` when one loop over the pairs is enough - O(n) space for nothing
- Iterating an exhausted enumerate object again - the second pass is empty

## Version Notes

- **All Python 3**: `enumerate()` is lazy and single-pass, and its bounds are the same on every supported version

## Related Functions

- **[zip()](zip.md)** - Combine multiple iterables
- **[range()](range.md)** - Generate number sequences
- **[iter()](iter.md)** - Create iterators
- **[next()](next.md)** - Get next item from iterator
