# Range Operations Complexity

The `range` type is an immutable sequence of integers. It stores only its `start`, `stop` and
`step` and its length, and computes each item when asked for it, so most operations cost the same
whatever the range's length. Only walking the items, or searching them for something other than an
exact `int` or a `bool`, depends on how long it is.

`n` is the range's length, `k` is an index, and `i:j` are slice bounds. The bounds count as
machine-sized integers: with bounds thousands of digits long, every row that does arithmetic on
them - building, indexing, an integer membership test - costs more as the digits grow.

## Complexity Reference

### range

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `range(stop)`, `range(start, stop[, step])` | O(1) | O(1) | Each argument must be an `int` or have `__index__`; a float raises `TypeError` even when it is whole, and a step of 0 raises `ValueError` |
| `len(r)` | O(1) | O(1) | The length is computed once, when the range is built; raises `OverflowError` beyond `sys.maxsize` |
| `bool(r)` | O(1) | O(1) | False exactly when the range is empty |
| `r.start`, `r.stop`, `r.step` | O(1) | O(1) | The arguments converted to `int`; `stop` is not moved to the last item, so `range(0, 10, 3).stop` is 10 |
| `r[k]` | O(1) | O(1) | Out of range raises `IndexError` |
| `r[i:j]`, `r[i:j:s]` | O(1) | O(1) | A new range, whatever the slice covers |
| `x in r` | O(1) | O(1) | For an exact `int` or a `bool`; any other type, an `int` subclass included, is searched in O(n) |
| `r.index(x)` | O(1) | O(1) | For an exact `int` or a `bool`; any other type is searched in O(n); an absent value raises `ValueError` |
| `r.count(x)` | O(1) | O(1) | For an exact `int` or a `bool`; any other type reads all n items |
| `r == other`, `r != other` | O(1) | O(1) | Ranges are equal when they give the same items, so `range(0) == range(5, 5)`; a range never equals a list or tuple |
| `r < other`, `<=`, `>`, `>=` | O(1) | O(1) | Raise `TypeError`: ranges are not ordered |
| `hash(r)` | O(1) | O(1) | Equal ranges hash alike |
| Iterating `r` | O(n) | O(1) | O(1) per item |
| `reversed(r)` | O(1) | O(1) | A lazy iterator; walking it is O(n) |
| `min(r)`, `max(r)` | O(n) | O(1) | The builtins iterate every item; `r[0]` and `r[-1]` are the ends in O(1) |
| `list(r)`, `tuple(r)` | O(n) | O(n) | Materializes every item |

## Membership and Search

For an exact `int` or a `bool`, `x in r`, `r.index(x)` and `r.count(x)` check that `x` lies between
the bounds and that `x - start` is a multiple of `step`, so they never walk the range. Any other
argument is compared with the items one at a time. A whole float, a `Decimal` or a `Fraction` still
gets the right answer, which is what makes the slow path easy to miss; an `int` subclass takes it
too.

```python
from fractions import Fraction

r = range(10, 100, 5)
assert 50 in r  # O(1): 50 - 10 is a multiple of 5
assert 51 not in r  # O(1)
assert r.index(50) == 8  # O(1)
assert r.count(50) == 1  # O(1)

assert 50.0 in r  # O(n): a float is compared with each item
assert Fraction(50) in r  # O(n)


class Number(int):
    pass


assert Number(50) in r  # O(n): only an exact int or a bool is checked arithmetically
assert int(Number(50)) in r  # O(1)

try:
    r.index(51)
except ValueError:
    pass
else:
    raise AssertionError("51 is not in the range")
```

## Length and Huge Ranges

A range's length is computed from `start`, `stop` and `step` when the range is built, and `len()`
returns the stored value. A range can be longer than `sys.maxsize`, but `len()` must return an
index-sized integer, so it raises `OverflowError` for such a range. Indexing, slicing and `in`
still work on it.

```python
import sys

r = range(0, 10**9, 3)
assert len(r) == 333_333_334  # O(1): stored when the range was built

huge = range(10**20)
assert huge[-1] == 10**20 - 1  # O(1)
assert 10**19 in huge  # O(1)
assert huge[::2] == range(0, 10**20, 2)  # O(1)
assert 10**20 > sys.maxsize

try:
    len(huge)
except OverflowError:
    pass
else:
    raise AssertionError("len() of a range beyond sys.maxsize must raise")
```

## Slicing, Equality and Hashing

A slice of a range is another range, built from the bounds, so it costs the same whether it covers
ten items or ten million. Two ranges are equal when they produce the same items, whatever arguments
built them, and equal ranges hash alike, so either can find the other in a dict or set.

```python
r = range(10, 100, 5)
assert r[1:4] == range(15, 30, 5)  # O(1)
assert r[::-2] == range(95, 5, -10)  # O(1)
assert type(r[2:]) is range

assert range(0, 10, 3) == range(0, 11, 3)  # O(1): both give 0, 3, 6, 9
assert range(0) == range(5, 5)  # O(1): both are empty
assert hash(range(0, 10, 3)) == hash(range(0, 11, 3))  # O(1)
assert range(3) != [0, 1, 2]  # a range never equals a list

seen = {range(0, 10, 3): "found"}
assert seen[range(0, 11, 3)] == "found"  # O(1)

try:
    _ = range(3) < range(4)
except TypeError:
    pass
else:
    raise AssertionError("ranges are not ordered")
```

## Range vs List

A range is the same size whatever its length, while a list of the same integers holds a reference
to each one. Iterating either is O(n); building the list first adds O(n) memory and a second pass.

```python
import sys

small, large = range(10), range(100_000)
assert sys.getsizeof(small) == sys.getsizeof(large)  # O(1) space, whatever the length

items = list(large)  # O(n) time and space
assert sys.getsizeof(items) > 100_000 * 8 // 2

assert sum(large) == sum(items)  # O(n) either way
assert 99_999 in large  # O(1)
assert 99_999 in items  # O(n): a list is searched
```

## Common Patterns

### Counting Down

A negative step, `reversed()` and a reversed slice all give a descending sequence without building
a list. Each is O(1) to create and O(n) to walk.

```python
n = 5
assert list(range(n - 1, -1, -1)) == [4, 3, 2, 1, 0]  # O(n) to walk
assert list(reversed(range(n))) == [4, 3, 2, 1, 0]  # O(n) to walk
assert range(n)[::-1] == range(4, -1, -1)  # O(1): still a range

r = range(10, 0, -2)
assert len(r) == 5  # O(1): n is the item count, not the span
assert (r[0], r[-1]) == (10, 2)  # O(1): the ends, without min() or max()
```

## Performance Best Practices

✅ **Do**:

- Test membership with an exact `int`, so `x in r` stays O(1); convert a float or `Decimal` with
  `int()` only once it is known to be whole, since `int()` truncates
- Read the ends as `r[0]` and `r[-1]` rather than calling `min()` or `max()`, which walk the range
- Iterate the range itself, or slice it, rather than building a list first

❌ **Avoid**:

- `x in r`, `r.index(x)` or `r.count(x)` with a float, `Decimal`, `Fraction` or `int` subclass -
  same answer, but O(n) instead of O(1)
- `list(range(n))` only to iterate it or test membership - O(n) memory for nothing

## Related Operations

- **[List](list.md)** - For materialized sequences
- **[len()](len.md)** - Containers that store their length, `range` among them
- **[Enumerate](enumerate.md)** - For indexed iteration
