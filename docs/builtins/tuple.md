# Tuple Operations Complexity

The `tuple` type is an immutable, ordered sequence. CPython stores it as a fixed-size array of
references, so indexing is direct and nothing ever has to be inserted, deleted or resized. Because a
tuple cannot change, copying an exact tuple returns the tuple itself.

`n` is the tuple's length, `k` is the value of a numeric argument (an index or a repeat count),
`i:j` are slice bounds, and `len(t1)`, `len(t2)` are operand lengths. A slice with a step selects
`m` elements. Indices are counted after negative values are normalized. Comparing or hashing one
element counts as O(1).

## Complexity Reference

### tuple

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(t)` | O(1) | O(1) | The length is stored in the tuple, not counted |
| `t[k]` | O(1) | O(1) | Direct indexing |
| `t[i:j]` (slicing) | O(j-i) | O(j-i) | With a step, O(m); `t[:]` of an exact tuple returns `t` itself |
| `t.index(x)` | O(n) | O(1) | Linear search; `t.index(x, i, j)` searches only `t[i:j]`, O(j-i) |
| `t.count(x)` | O(n) | O(1) | Linear scan |
| `x in t` (membership) | O(n) | O(1) | Linear search |
| `tuple(t)`, `copy.copy(t)` | O(1) | O(1) | Return `t` itself when `t` is an exact tuple; tuples have no `copy()` method |
| `tuple(iterable)` | O(n) | O(n) | n = items the iterable yields; see [tuple()](tuple_func.md) |
| `t1 + t2` (concatenation) | O(len(t1)+len(t2)) | O(len(t1)+len(t2)) | |
| `t * k` (repetition) | O(nk) | O(nk) | k ≤ 0 gives an empty tuple |
| `t1 == t2` | O(min(len(t1), len(t2))) | O(1) | Compares elements even when the lengths differ; stops at the first unequal pair |
| `t1 < t2`, `<=`, `>`, `>=` | O(min(len(t1), len(t2))) | O(1) | Stops at the first unequal pair |
| `for x in t` (iteration) | O(n) | O(1) | O(1) per step |
| `reversed(t)` | O(1) | O(1) | A lazy iterator; walking it is O(n) |
| `min(t)`, `max(t)` | O(n) | O(1) | n-1 comparisons |
| `hash(t)` | O(n) first call; O(1) after it on 3.14+ | O(1) | 3.11-3.13 recompute it on every call; an unhashable element raises `TypeError` and nothing is cached |

## Copying Returns the Same Tuple

A copy of an exact tuple could never differ from the original, so `tuple(t)`, `copy.copy(t)` and
`t[:]` hand back `t` itself in O(1). A subclass instance is copied in O(n).

```python
import copy

t = tuple(range(1_000))
assert tuple(t) is t  # O(1)
assert copy.copy(t) is t  # O(1)
assert t[:] is t  # O(1)


class Pair(tuple):
    pass


p = Pair((1, 2))
assert tuple(p) is not p and type(tuple(p)) is tuple  # O(n): a subclass is copied
```

## Hashing

`hash(t)` combines the hash of every element, so the first call is O(n). From 3.14 the result is
kept in the tuple and later calls are O(1); on 3.11-3.13 every call walks the elements again. The
cache belongs to the object: an equal tuple built separately pays its own first hash.

```python
import sys

calls = 0


class Key:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, Key) and self.value == other.value

    def __hash__(self):
        global calls
        calls += 1
        return hash(self.value)


t = tuple(Key(i) for i in range(100))
hash(t)  # O(n): hashes every element
assert calls == 100

calls = 0
hash(t)  # O(1) on 3.14+, O(n) before
assert calls == (0 if sys.version_info >= (3, 14) else 100)

try:
    hash((1, []))
except TypeError as exc:
    assert "unhashable type: 'list'" in str(exc)
else:
    raise AssertionError("expected TypeError")
```

## Comparing Tuples

`==` does not check the lengths first. It walks the common prefix, stops at the first unequal pair,
and looks at the lengths only when the shorter tuple runs out with every pair equal. Unlike
[list](list.md), tuples of different lengths still compare their common prefix.

```python
compared = 0


class Item:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        global compared
        compared += 1
        return self.value == other.value

    __hash__ = None


short = tuple(Item(i) for i in range(999))
long = tuple(Item(i) for i in range(1_000))
assert short != long  # O(min(len(t1), len(t2))): the common prefix is compared
assert compared == 999

compared = 0
assert list(short) != list(long)  # a list answers from the lengths alone
assert compared == 0
```

## Building a Tuple

`t += (x,)` builds a new tuple, so in a loop it copies everything gathered so far on every step:
O(n²) in total. Collect into a list and convert once.

```python
slow = ()
for i in range(1_000):
    slow += (i,)  # O(len(slow)): copies the tuple each time

items = []
for i in range(1_000):
    items.append(i)  # O(1) amortized
fast = tuple(items)  # O(n), once

assert slow == fast == tuple(range(1_000))
```

## Performance Best Practices

✅ **Do**:

- Copy freely: `tuple(t)` and `t[:]` of an exact tuple are O(1)
- Use a tuple as a dict key or set member when its elements are hashable; from 3.14 its hash is
  computed once per tuple
- Gather items in a list and call `tuple()` once: O(n) in total

❌ **Avoid**:

- `t += (x,)` in a loop: each step copies the tuple, O(n²) in total
- `x in t` inside another loop: O(n) per test - build a [set](set.md) once for O(1) average lookups

## Version Notes

- **Python 3.14+**: `hash(t)` keeps its result in the tuple, so repeat calls are O(1)

## Related Types

- **[List](list.md)** - Mutable alternative
- **[tuple()](tuple_func.md)** - Building a tuple from an iterable
- **[namedtuple](../stdlib/namedtuple.md)** - Tuples with named fields
- **[Dataclass](../stdlib/dataclasses.md)** - Mutable records with named fields

## Further Reading

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's tuple implementation
