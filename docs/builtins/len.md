# len() Function Complexity

`len(obj)` returns the number of items in a container. Every built-in container keeps its item
count in the object, so `len()` reads it instead of counting, whatever the container's size. For
any other object, `len()` calls the `__len__` method its class defines and costs what that method
costs.

The built-in rows do not depend on the container's size. `f` is the time the method a class
defines - `__len__`, `__bool__` or `__length_hint__` - takes, on top of the O(1) call; whatever the
method allocates comes on top of the O(1) space. For a `ChainMap`, `m` is its maps, `t` is their
keys summed over all of them, duplicates included, and `u` is the distinct keys among them.

## Complexity Reference

### Built-in types

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(lst)`, `len(tpl)` | O(1) | O(1) | `list` and `tuple` |
| `len(s)` | O(1) | O(1) | `str`: counts characters (code points), not encoded bytes |
| `len(b)`, `len(ba)` | O(1) | O(1) | `bytes` and `bytearray`: counts bytes |
| `len(mv)` | O(1) | O(1) | `memoryview` with at least one dimension: the length of the first dimension, not the total item count |
| `len(d)`, `len(d.keys())`, `len(d.values())`, `len(d.items())` | O(1) | O(1) | `dict` and its views |
| `len(fd)` | O(1) | O(1) | `frozendict`, Python 3.15+ |
| `len(st)`, `len(fs)` | O(1) | O(1) | `set` and `frozenset` |
| `len(r)` | O(1) | O(1) | `range`: the length is computed once, when the range is built; raises `OverflowError` beyond `sys.maxsize` |

### Standard library containers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(dq)` | O(1) | O(1) | `collections.deque` |
| `len(dd)`, `len(od)`, `len(c)` | O(1) | O(1) | `defaultdict`, `OrderedDict` and `Counter` are `dict` subclasses |
| `len(cm)` | O(m + t) | O(m + u) | `collections.ChainMap` builds a set of every key in every map on each call |

### Other objects

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(obj)` | O(f) | O(1) | Calls `type(obj).__len__`; an instance attribute named `__len__` is ignored. The result must be an integer (an `int`, or an object with `__index__`) from 0 to `sys.maxsize` |
| `len(gen)`, `len(iterator)` | O(1) | O(1) | Generators, and iterators without `__len__`, have no length: raises `TypeError` |
| `bool(obj)`, `if obj:` | O(1), or O(f) | O(1) | O(1) for a built-in container; a class with `__len__` and no `__bool__` is true when `__len__` returns non-zero |
| `operator.length_hint(obj, default=0)` | O(1), or O(f) | O(1) | `len(obj)` if it has one, else `obj.__length_hint__()`, else `default`; never iterates `obj` itself |

## Built-in Containers

`len()` costs the same on a container of three items as on one of a million. On a `str` it counts
characters, so it can differ from the length of the encoded `bytes`.

```python
items = list(range(1_000_000))
assert len(items) == 1_000_000  # O(1)
assert len((1, 2, 3)) == 3  # O(1)

d = {"a": 1, "b": 2}
assert len(d) == len(d.keys()) == len(d.items()) == 2  # O(1)
assert len({1, 2, 2, 3}) == 3  # O(1)

s = "café"
assert len(s) == 4  # O(1) - characters
assert len(s.encode("utf-8")) == 5  # O(1) - bytes, after an O(n) encode

grid = memoryview(bytes(12)).cast("B", shape=[3, 4])
assert len(grid) == 3  # O(1) - the first dimension
assert grid.nbytes == 12
```

## Ranges

A range computes its length from `start`, `stop` and `step` when it is built, and `len()` returns
the stored value. A range can be longer than `sys.maxsize`, but `len()` must return an index-sized
integer, so it raises `OverflowError` for such a range. Indexing and `in` still work on it.

```python
import sys

r = range(0, 10**9, 3)
assert len(r) == 333_333_334  # O(1)

huge = range(10**20)
try:
    len(huge)
except OverflowError as error:
    assert "too large" in str(error)
else:
    raise AssertionError("expected OverflowError")

assert 10**20 > sys.maxsize
assert huge[-1] == 10**20 - 1  # O(1)
assert 10**19 in huge  # O(1)
```

## Classes With __len__

`len(obj)` calls `__len__` on the object's class, so the method decides the cost. One that keeps a
count, or delegates to a built-in container, is O(1); one that counts by iterating is O(n) on
every call. `len()` checks the result: a negative value raises `ValueError`, and a value that is
not an integer raises `TypeError`.

```python
class Stored:
    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return len(self.items)  # O(1) - delegates to the list


class Counted:
    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return sum(1 for _ in self.items)  # O(n) - walks every item on each call


assert len(Stored(range(5))) == len(Counted(range(5))) == 5


class Negative:
    def __len__(self):
        return -1


try:
    len(Negative())
except ValueError as error:
    assert ">= 0" in str(error)
else:
    raise AssertionError("expected ValueError")
```

Truth testing uses `__len__` too when a class does not define `__bool__`, so `if obj:` costs
whatever `len(obj)` costs.

```python
class Box:
    calls = 0

    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        Box.calls += 1
        return len(self.items)


assert not Box([])  # calls __len__
assert Box([1])
assert Box.calls == 2
```

## Iterators and Generators

A generator, like any iterator without `__len__`, does not know how many items it will produce,
so `len()` raises `TypeError`. Counting the items consumes them, in O(n). `operator.length_hint()`
asks without iterating: it gives the exact number left for an iterator over a built-in container,
and its `default` for a generator.

```python
import operator

gen = (x * x for x in range(5))
try:
    len(gen)
except TypeError as error:
    assert "has no len()" in str(error)
else:
    raise AssertionError("expected TypeError")

assert operator.length_hint(gen, -1) == -1  # O(1) - a generator gives no hint
assert sum(1 for _ in gen) == 5  # O(n) - and the generator is now exhausted
assert list(gen) == []

it = iter([10, 20, 30])
next(it)
assert operator.length_hint(it) == 2  # O(1)
assert list(it) == [20, 30]  # nothing was consumed
```

## ChainMap

A `ChainMap` stores no count. Each `len()` call builds a set of the keys of every map, so it costs
every map and every key in it, and a key present in several maps is counted once.

```python
from collections import ChainMap

defaults = {"color": "red", "size": 10}
overrides = {"color": "blue"}
settings = ChainMap(overrides, defaults)

assert len(settings) == 2  # O(m + t) - "color" is in both maps
```

## Performance Best Practices

✅ **Do**:

- Call `len()` freely on built-in containers, including inside loop conditions; it is O(1)
- Use `if container:` for an emptiness check; it is O(1) on built-in containers
- Keep a count in your own container, or delegate to a built-in one, so `__len__` is O(1)
- Use `operator.length_hint()` to size a buffer from a built-in container's iterator without
  consuming it

❌ **Avoid**:

- `len(list(iterator))` just to count: it builds an O(n) list; `sum(1 for _ in iterator)` counts in
  O(1) space, but either way the iterator is consumed
- A `__len__` that iterates; `if obj:` calls it too when the class has no `__bool__`
- `len()` on a `ChainMap` in a loop: every call walks every map

## Version Notes

- **Python 3.15+**: `len()` on a `frozendict` is O(1)

## Related Functions

- **[bool()](bool_func.md)** - Truth testing falls back to `__len__`
- **[iter()](iter.md)** - Generators and most iterators have no length
- **[range](range.md)** - Ranges compute their length when they are built
- **[sum()](sum.md)** - Counting the items of an iterator
- **[collections](../stdlib/collections.md)** - `deque`, `Counter` and `ChainMap`
- **[operator](../stdlib/operator.md)** - `length_hint()` for iterators
