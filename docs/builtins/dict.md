# Dictionary Operations Complexity

The `dict` type is a mutable mapping that stores key-value pairs in insertion order. In CPython
it is a hash table, so lookups, insertions and deletions do not depend on the dict's size, and the
operations that touch every item - copying, iterating, comparing - are linear.

`n` is the number of items in the dict and `m` is the number of items in the other operand: the
mapping or iterable passed to `update()` or `fromkeys()`, or the right-hand side of `|` or of a
view's set operation. Key hashing and comparison are treated as O(1), and so is comparing two
values. The O(1) lookups are average cases: if every key hashes to the same value, each one
instead takes O(n).

## Complexity Reference

### dict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(d)` | O(1) | O(1) | The count is stored |
| `d[key]`, `d.get(key, default=None)` | O(1) avg, O(n) worst | O(1) | `d[key]` raises `KeyError` for a missing key |
| `key in d` | O(1) avg, O(n) worst | O(1) | |
| `d[key] = value` | O(1) amortized | O(1) | A call that grows the table rebuilds it in O(n) |
| `del d[key]`, `d.pop(key[, default])` | O(1) avg, O(n) worst | O(1) | A missing key raises `KeyError` unless `pop()` is given a default; the table is not shrunk |
| `d.setdefault(key, default=None)` | O(1) amortized | O(1) | One lookup, plus an insertion when the key is missing |
| `d.popitem()` | O(1) amortized | O(1) | Removes the last inserted pair; raises `KeyError` when the dict is empty |
| `d.clear()` | O(n) | O(1) | Releases every key and value |
| `d.copy()` | O(n) | O(n) | Shallow: the keys and values are shared, not copied |
| `dict.fromkeys(iterable, value=None)` | O(m) | O(m) | Every key maps to the same `value` object |
| `d.update(other)`, `d \|= other` | O(m) amortized | O(m) | In place, plus the cost of iterating `other`: a mapping or an iterable of pairs |
| `d \| other` | O(n + m) | O(n + m) | A new dict: a copy of `d`, updated from `other`. `dict` handles only a `dict` or `frozendict` `other`; anything else is left to `other.__ror__` |
| Iterating `d`, `reversed(d)` | O(n) | O(1) | Insertion order, or its reverse |
| `d == other`, `d != other` | O(n) | O(1) | Order is ignored; O(1) when the lengths differ |

### Views

`d.keys()`, `d.values()` and `d.items()` are views: they hold a reference to `d` and see every
later change to it, without copying anything.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `d.keys()`, `d.values()`, `d.items()` | O(1) | O(1) | |
| `len(view)`, `view.mapping` | O(1) | O(1) | `mapping` is a read-only proxy of `d` |
| Iterating a view, `reversed(view)` | O(n) | O(1) | |
| `key in d.keys()`, `(key, value) in d.items()` | O(1) avg, O(n) worst | O(1) | One key lookup, plus a value comparison for `items()` |
| `value in d.values()` | O(n) | O(1) | Values are not indexed, so this scans them |
| `view & other` | O(m) | O(min(n, m)) | `keys()` and `items()` views; O(min(n, m)) time when `other` is a set or a `keys()` or `items()` view |
| `view \| other`, `view - other`, `view ^ other` | O(n + m) | O(n + m) | Each builds a new `set` |
| `view.isdisjoint(other)` | O(m) | O(1) | O(min(n, m)) when `other` is a set or a `keys()` or `items()` view; stops at the first shared item |

Deleting items does not shrink the table. After most items are removed, operations that walk it -
iterating `d` or a view, `copy()`, `d | other`, `other.update(d)`, `d == other` and `dict(d)` -
still take time proportional to the dict's former size, until later insertions trigger a resize.
`len()` and lookups are unaffected.

## Lookups and Collisions

A lookup hashes the key and compares it only with stored keys whose hash is the same. With a
well-spread hash that is at most one comparison. When many keys share a hash, the lookup compares against
each of them in turn, so it degrades to O(n).

```python
class Key:
    comparisons = 0

    def __init__(self, name, hash_value):
        self.name = name
        self.hash_value = hash_value

    def __hash__(self):
        return self.hash_value

    def __eq__(self, other):
        Key.comparisons += 1
        return self.name == other.name

spread = {Key(i, i): i for i in range(100)}     # O(n)
Key.comparisons = 0
assert spread[Key(99, 99)] == 99                # O(1)
assert Key.comparisons == 1                     # only the key with the same hash

colliding = {Key(i, 1): i for i in range(100)}  # O(n²) - each insertion compares
Key.comparisons = 0
assert colliding[Key(99, 1)] == 99              # O(n) - compares every key before it
assert Key.comparisons == 100
```

## Deleting Does Not Shrink the Table

`del` and `pop()` leave the table at its largest size, so walking it still visits every slot it
had. `copy()` of a dict that has lost most of its items builds a compact one, which makes later
walks cheap again.

```python
import sys

d = {i: i for i in range(100_000)}
full = sys.getsizeof(d)
for i in range(10, 100_000):
    del d[i]                       # O(1) each

assert len(d) == 10                # O(1)
assert sys.getsizeof(d) == full    # still sized for 100,000 items
keys = list(d)                     # O(100,000): walks the old table

d = d.copy()                       # O(100,000) once
assert sys.getsizeof(d) < full     # sized for 10 items
assert list(d) == keys             # O(10)
```

### Removing the Oldest Item

The same holds at the front of the table. `next(iter(d))` skips every slot that earlier deletions
emptied, so removing the oldest key in a loop costs O(n) per call and O(n²) for the whole dict.
`collections.OrderedDict.popitem(last=False)` removes the oldest item in O(1).

```python
from collections import OrderedDict

d = dict.fromkeys(range(5))
oldest = next(iter(d))      # O(1) here; O(deleted so far) in a loop
del d[oldest]
assert list(d) == [1, 2, 3, 4]

od = OrderedDict.fromkeys(range(5))
assert od.popitem(last=False) == (0, None)   # O(1)
assert list(od) == [1, 2, 3, 4]
```

## Views

A view is created in O(1) and reflects the dict as it is when you use it. Membership in
`keys()` and `items()` is a hash lookup; membership in `values()` is a scan. The set operations
on `keys()` and `items()` return a new `set`.

```python
d = {'a': 1, 'b': 2}
keys = d.keys()                 # O(1) - no copy
d['c'] = 3
assert list(keys) == ['a', 'b', 'c']  # O(n) - sees the new key

assert 'b' in keys              # O(1)
assert ('b', 2) in d.items()    # O(1) - key lookup, then one value comparison
assert 3 in d.values()          # O(n) - a scan

assert keys & {'a', 'z'} == {'a'}           # O(min(n, m)) with a set
assert keys - ['a'] == {'b', 'c'}           # O(n + m)
assert keys.isdisjoint({'x', 'y'})          # O(min(n, m)) with a set
assert keys.mapping['a'] == 1               # O(1) - a read-only proxy
```

## Merging With | and update()

`d | other` copies `d` and then inserts every item of `other`, so it is O(n + m) whichever side is
larger. `d |= other` and `d.update(other)` insert into `d` itself and cost only O(m). `update()`
also accepts an iterable of pairs and keyword arguments.

```python
defaults = {'color': 'red', 'size': 10}
overrides = {'size': 12}

merged = defaults | overrides       # O(n + m) - a new dict
assert merged == {'color': 'red', 'size': 12}
assert defaults['size'] == 10

config = defaults
config |= overrides                 # O(m) - in place
assert config is defaults and defaults['size'] == 12

config.update([('debug', True)], verbose=False)  # O(m)
assert list(config) == ['color', 'size', 'debug', 'verbose']
```

## Insertion Order

Iteration follows insertion order, and `reversed()` walks it backwards. Assigning to an existing
key keeps its position. `popitem()` removes the most recently inserted pair.

```python
d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
d['a'] = 10                         # O(1) - keeps its position

assert list(d) == ['a', 'b', 'c']   # O(n)
assert list(reversed(d)) == ['c', 'b', 'a']  # O(n)
assert d.popitem() == ('c', 3)      # O(1) - last in, first out
assert d == {'b': 2, 'a': 10}       # O(n) - order is ignored
```

## Keys Must Be Hashable

Every lookup and every `d[key] = value` hashes the key. Lists, dicts and sets are mutable and
unhashable, so they cannot be keys; a tuple or a `frozenset` of the same hashable items can.

```python
d = {
    (1, 2): 'tuple_key',
    'string': 'str_key',
    42: 'int_key',
    frozenset([1, 2]): 'frozen_key',
}
assert d[frozenset([2, 1])] == 'frozen_key'   # O(1) after hashing the key

for key in ([1, 2], {1, 2}, {'a': 1}):
    try:
        d[key] = 'fails'
    except TypeError as error:
        assert 'unhashable' in str(error)
    else:
        raise AssertionError(f'{type(key).__name__} must not be usable as a key')
```

## Performance Best Practices

✅ **Do**:

- Use a dict for lookups by key: O(1) instead of the O(n) scan a list needs
- Use `get()` or `setdefault()` to handle a missing key with one lookup instead of two
- Use `d |= other` or `update()` to add to a dict in O(m); `d | other` copies `d` first
- Copy a dict that has lost most of its items, so later walks cost its current size

❌ **Avoid**:

- `value in d.values()` in a loop - each test is O(n); keep a reverse dict or a set of values
- Removing the oldest key with `del d[next(iter(d))]` in a loop - O(n²) overall; use
  `OrderedDict.popitem(last=False)`
- Building a dict up with repeated `d = d | other` - each step copies everything so far
- Keys with a poor `__hash__` - when many collide, every lookup degrades to O(n)

## Version Notes

- **Python 3.7+**: Insertion order is part of the language; CPython 3.6 already kept it
- **Python 3.9+**: Merge `|` and update `|=` operators
- **Python 3.15+**: [`frozendict`](frozendict.md), an immutable and hashable dict

## Related Types

- **[Set](set.md)** - Unordered unique items
- **[frozendict](frozendict.md)** - Immutable, hashable dict (Python 3.15+)
- **[Defaultdict](../stdlib/collections.md#defaultdict)** - Auto-default values
- **[OrderedDict](../stdlib/collections.md#ordereddict)** - O(1) removal from either end and `move_to_end()`
- **[ChainMap](../stdlib/collections.md#chainmap)** - Multiple dict views

## Further Reading

- [CPython Internals: dict](https://zpoint.github.io/CPython-Internals/BasicObject/dict/dict.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's dict implementation
