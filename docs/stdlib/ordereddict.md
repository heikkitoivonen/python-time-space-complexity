# OrderedDict Complexity

`collections.OrderedDict` is a `dict` subclass that also keeps its entries on a doubly-linked
list. Lookups are the inherited `dict` code; the list is what makes reordering and popping from
either end O(1), and it is also what every insertion, deletion and iteration has to maintain or
walk.

`n` is the entries in the `OrderedDict`, and `m` is the entries supplied by the other mapping,
iterable or keyword arguments an operation takes. Bounds treat hashing a key and comparing keys
or values as O(1). Iterating is the one place that assumption matters more than for a `dict`: each step looks
its key up again, so the key's `__hash__` runs on every step.

!!! note "OrderedDict or dict"
    A plain `dict` keeps insertion order too. Reach for `OrderedDict` when you need
    `move_to_end()`, `popitem(last=False)`, or equality that compares order.

## Complexity Reference

### OrderedDict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `OrderedDict(iterable=(), /, **kwds)` | O(m) | O(m) | One linked node per new key |
| `od[key]`, `od.get(key)`, `key in od`, `len(od)` | O(1) | O(1) | Inherited from `dict` unchanged |
| `od[key] = value` | O(1) amortized | O(1) amortized | A new key is linked at the end; updating an existing key keeps its position |
| `del od[key]` | O(1) amortized | O(1) | Unlinks the node; raises `KeyError` if the key is missing |
| `OrderedDict.move_to_end(key, last=True)` | O(1) amortized | O(1) | `last=False` moves it to the front; raises `KeyError` if the key is missing |
| `OrderedDict.popitem(last=True)` | O(1) amortized | O(1) | Last entry by default, first with `last=False`; raises `KeyError` when empty |
| `OrderedDict.pop(key[, default])` | O(1) amortized | O(1) | Raises `KeyError` for a missing key without a default |
| `OrderedDict.setdefault(key, default=None)` | O(1) amortized | O(1) amortized | Inserts at the end only if the key is missing |
| `OrderedDict.update(other=(), /, **kwds)` | O(m) | O(m) | New keys go to the end in the order supplied |
| `OrderedDict.fromkeys(iterable, value=None)` | O(m) | O(m) | A class method; every key shares one value object |
| `OrderedDict.copy()` | O(n) | O(n) | Shallow copy in the same order |
| `OrderedDict.clear()` | O(n) | O(1) | Frees every node |
| `OrderedDict.keys()`, `OrderedDict.values()`, `OrderedDict.items()` | O(1) | O(1) | Live views; iterating one is O(n) and `reversed()` works on each |
| Iterating an `OrderedDict`, `reversed(od)` | O(1) to start, O(n) to exhaust | O(1) | Walks the linked list, looking each key up again; adding, removing or moving a key meanwhile raises `RuntimeError` |
| `od == other` | O(n) | O(1) | Order-sensitive when both sides are `OrderedDict`; against a plain `dict`, order is ignored |
| `od \| other` | O(n + m) | O(n + m) | A new `OrderedDict`; keys new to `od` follow its own |
| `od \|= other` | O(m) | O(m) | Same as `update(other)` |

## Reordering and Popping

The linked list is what `dict` does not have. Moving a key to either end and popping from either
end each touch one node, so an `OrderedDict` works as a deque that also supports O(1) lookup by
key.

```python
from collections import OrderedDict

od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])  # O(m)

od.move_to_end('a')              # O(1) - to the back
assert list(od) == ['b', 'c', 'a']
od.move_to_end('a', last=False)  # O(1) - to the front
assert list(od) == ['a', 'b', 'c']

assert od.popitem() == ('c', 3)            # O(1) - last in, first out
assert od.popitem(last=False) == ('a', 1)  # O(1) - first in, first out
assert list(od) == ['b']

try:
    od.move_to_end('missing')
except KeyError as error:
    assert error.args == ('missing',)
else:
    raise AssertionError('a missing key was moved')
```

### Popping the Oldest Entry

`dict.popitem()` takes no argument and always removes the newest entry. Emulating a pop from
the front with `next(iter(d))` scans past every slot that earlier front deletions left empty, so
draining a `dict` that way is O(n²); `popitem(last=False)` keeps it O(n).

```python
from collections import OrderedDict

queue = OrderedDict.fromkeys(range(1000))  # O(m)
while queue:
    queue.popitem(last=False)  # O(1) each, O(n) to drain

try:
    {'a': 1}.popitem(last=False)
except TypeError as error:
    assert 'keyword arguments' in str(error)
else:
    raise AssertionError('dict.popitem() accepted last=False')
```

## Iteration

Iteration walks the list in insertion order, and `reversed()` walks it backwards without building
a copy. Each step looks the current key up in the table to find the next node, which is why an
`OrderedDict` iterates more slowly than a `dict` and calls a key's `__hash__` on every step,
where iterating a `dict` hashes nothing.
Adding, removing or moving a key while iterating raises `RuntimeError`; assigning to an existing
key does not.

```python
from collections import OrderedDict

od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])

assert list(od) == ['a', 'b', 'c']                  # O(n)
assert list(reversed(od)) == ['c', 'b', 'a']        # O(n); reversed() copies nothing
assert list(reversed(od.items()))[0] == ('c', 3)    # views reverse too

for key in od:
    od[key] *= 10  # values may change
assert list(od.values()) == [10, 20, 30]

try:
    for key in od:
        od.move_to_end(key)
except RuntimeError as error:
    assert 'mutated during iteration' in str(error)
else:
    raise AssertionError('reordering during iteration went unnoticed')
```

## Equality

Two `OrderedDict` objects are equal only if they hold the same entries in the same order.
Against a plain `dict` the order is ignored. Both comparisons are O(n), and together they make
equality non-transitive.

```python
from collections import OrderedDict

first = OrderedDict([('x', 1), ('y', 2)])
reordered = OrderedDict([('y', 2), ('x', 1)])
plain = {'y': 2, 'x': 1}

assert first != reordered  # O(n), order compared
assert first == plain      # O(n), order ignored
assert plain == reordered
```

## Building and Copying

Construction, `update()`, `fromkeys()` and `|` each insert one key at a time, linking a node per
new key. Updating a key that is already present changes its value but not its position.

```python
from collections import OrderedDict

od = OrderedDict(a=1, b=2)       # O(m)
od.update([('c', 3), ('a', 9)])  # O(m) - 'a' keeps its place
assert list(od.items()) == [('a', 9), ('b', 2), ('c', 3)]

merged = od | {'d': 4}  # O(n + m), a new OrderedDict
assert list(merged) == ['a', 'b', 'c', 'd'] and list(od) == ['a', 'b', 'c']

od |= {'e': 5}  # O(m), in place
assert list(od) == ['a', 'b', 'c', 'e']

copied = od.copy()  # O(n), same order
assert copied == od and copied is not od

defaults = OrderedDict.fromkeys('xyz', 0)  # O(m)
assert list(defaults.items()) == [('x', 0), ('y', 0), ('z', 0)]

assert od.setdefault('b', 7) == 2   # O(1), present: unchanged
assert od.setdefault('f', 6) == 6   # O(1), missing: appended
assert od.pop('a') == 9 and od.pop('a', None) is None  # O(1)
od.clear()                          # O(n)
assert not od
```

## Common Patterns

### LRU Cache

Every step of a least-recently-used cache is O(1) amortized: a hit moves its key to the back, and an
eviction pops the front.

```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.entries = OrderedDict()

    def get(self, key):
        if key not in self.entries:  # O(1)
            return None
        self.entries.move_to_end(key)  # O(1) - now the most recent
        return self.entries[key]

    def put(self, key, value):
        self.entries[key] = value  # O(1) amortized
        self.entries.move_to_end(key)  # O(1)
        if len(self.entries) > self.capacity:
            self.entries.popitem(last=False)  # O(1) - evict the least recent

cache = LRUCache(2)
cache.put('a', 1)
cache.put('b', 2)
assert cache.get('a') == 1  # 'b' is now the least recent
cache.put('c', 3)           # evicts 'b'
assert list(cache.entries) == ['a', 'c']
assert cache.get('b') is None
```

## Performance Best Practices

✅ **Do**:

- Use `popitem(last=False)` for FIFO eviction: it is O(1), where emulating it on a `dict` drains in O(n²)
- Use `reversed(od)` to walk backwards; it copies nothing

❌ **Avoid**:

- `OrderedDict` where a `dict` would do: lookups cost the same, but every node costs memory and iteration is slower
- Iterating an `OrderedDict` whose keys are expensive to hash; each step hashes its key again
- Relying on `==` between an `OrderedDict` and a `dict` to compare order; it ignores it

## Version Notes

- **All Python 3**: Equality between two `OrderedDict` objects is order-sensitive; against a `dict` it is not

## Related Modules

- **[dict](../builtins/dict.md)** - the base type; insertion-ordered, smaller and faster to iterate
- **[collections](collections.md)** - the module `OrderedDict` belongs to, with `deque` for a pure queue
- **[functools](functools.md)** - `lru_cache` when the cache is around a function
