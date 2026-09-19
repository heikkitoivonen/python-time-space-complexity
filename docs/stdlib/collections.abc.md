# collections.abc Module Complexity

The `collections.abc` module does two jobs. Its abstract base classes answer `isinstance()`
and `issubclass()` for the container protocols, some structurally, by looking for the required
methods, and the rest only through inheritance or `register()`. They also carry mixin methods:
give a `Sequence` subclass `__getitem__` and `__len__` and it gains `__iter__`, `__contains__`,
`index()` and `count()` for free. Free to write, not free to run. Every mixin is a Python loop
over the abstract methods you supplied, so its cost is a count of those calls, and it never
knows about a faster path your storage might offer.

Mixins are priced here in calls to the abstract methods, each counted as O(1); a subclass whose
`__getitem__` is O(log n) multiplies accordingly. `n` is `len(self)`, `k` is the size of the
other operand or the number of items supplied, and `i` is the position of the first match (`n`
for a miss), and `d` is the slots that earlier deletions left in a dict or set table. For the
runtime checks, `L` is the length of the checked class's MRO, `S` the ABC's subclasses, counted
transitively, and `R` the classes registered on the ABC or on any of those subclasses.

## Complexity Reference

### Runtime checks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `isinstance(obj, ABC)`, `issubclass(cls, ABC)` on a repeated class | O(1) | O(1) | Both outcomes are cached per ABC, keyed by class; a `register()` that adds a new relationship, on any ABC anywhere, stales every negative cache, which is dropped at that ABC's next check |
| First check against `Hashable`, `Awaitable`, `Coroutine`, `AsyncIterable`, `AsyncIterator`, `AsyncGenerator`, `Iterable`, `Iterator`, `Reversible`, `Generator`, `Sized`, `Container`, `Collection`, `Callable`, `Buffer` | O(L) | O(1) | `__subclasshook__` looks for the required methods in each class of the MRO; a class that lacks one falls through to the walk below |
| First check against `Set`, `MutableSet`, `Mapping`, `MutableMapping`, `MappingView`, `KeysView`, `ItemsView`, `ValuesView`, `Sequence`, `MutableSequence`, `ByteString` | O(L·(1 + R + S)) | O(R + S) | No structural hook: the MRO, then every registered class, then every subclass recursively, each of them rescanning the MRO; the registry and subclass lists are copied on the way |
| `ABC.register(cls)` | O(L·(1 + R + S)) | O(R + S) | Two `issubclass()` checks, then one weak-set entry; a new relationship bumps the token that stales every negative cache, and a class that already is a subclass is a no-op |
| `Iterable[int]`, `Mapping[str, int]`, `Callable[[int], str]` and the other subscriptions | O(a) | O(a) | a = type arguments; `Callable` flattens the parameter list into `__args__` |
| `collections.abc.Buffer` | O(L) | O(1) | Python 3.12+; a structural check for `__buffer__` |
| `collections.abc.ByteString` | O(L·(1 + R + S)) | O(R + S) | Deprecated since 3.12: each `isinstance()` check and each subclass definition also emits a `DeprecationWarning`; `ByteString.index()` and the rest are the `Sequence` mixins |

### Iterators, generators and coroutines

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Iterator.__iter__()`, `AsyncIterator.__aiter__()` | O(1) | O(1) | Return `self` |
| `Generator.__next__()` | O(1) | O(1) | One `send(None)` |
| `Generator.close()`, `Coroutine.close()` | O(1) | O(1) | One `throw(GeneratorExit)`; `RuntimeError` if the generator yields instead of stopping |
| `AsyncGenerator.__anext__()` | O(1) | O(1) | One `asend(None)` |
| `AsyncGenerator.aclose()` | O(1) | O(1) | One `athrow(GeneratorExit)` |
| `Generator.send(value)`, `Generator.throw(typ)`, `Coroutine.send(value)`, `Coroutine.throw(typ)`, `AsyncGenerator.asend(value)`, `AsyncGenerator.athrow(typ)` | O(1) | O(1) | Abstract: the ABC's own bodies only raise, and the mixins above are counts of these |
| `Hashable`, `Awaitable`, `Iterable`, `Reversible`, `Sized`, `Container`, `Collection`, `Callable` | O(1) | O(1) | Protocol checks only; they add no mixin methods |

### Sequence

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `iter(seq)` (`Sequence.__iter__()`) | O(n) | O(1) | n + 1 `__getitem__` calls, from index 0 until `IndexError`; the mixin never calls `__len__` |
| `value in seq` (`Sequence.__contains__()`) | O(i) | O(1) | Iterates as above and stops at the first `==` |
| `reversed(seq)` (`Sequence.__reversed__()`) | O(n) | O(1) | One `__len__`, then n `__getitem__` calls from the end |
| `Sequence.index(value, start=0, stop=None)` | O(i) | O(1) | One `__getitem__` per position from `start`; a negative bound costs a `__len__`, and a miss ends at `stop` or on `IndexError` |
| `Sequence.count(value)` | O(n) | O(1) | Iterates, n + 1 `__getitem__` calls |

### MutableSequence

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `MutableSequence.append(value)` | O(1) | O(1) | One `__len__` and one `insert()` |
| `MutableSequence.extend(values)`, `seq += values` | O(k) | O(1) | One `append()` per value; `values is self` is copied to a list first, O(k) space |
| `MutableSequence.pop(index=-1)` | O(1) | O(1) | One `__getitem__` and one `__delitem__` |
| `MutableSequence.remove(value)` | O(i) | O(1) | `index()`, then one `__delitem__` |
| `MutableSequence.reverse()` | O(n) | O(1) | One `__len__`, then two `__getitem__` and two `__setitem__` calls per swap, n // 2 swaps from both ends |
| `MutableSequence.clear()` | O(n) | O(1) | `pop()` until `IndexError`: n + 1 `__getitem__` calls, the last one raising, and n `__delitem__` calls from the end |
| `MutableSequence.insert(index, value)` | O(1) | O(1) | Abstract |

### Set

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `s <= other`, `s < other`, `s == other` | O(n) | O(1) | Two `__len__` calls settle a size mismatch; otherwise one `other.__contains__` per element of `s`, stopping at the first miss |
| `s >= other`, `s > other` | O(k) | O(1) | The same with the sides swapped: one `s.__contains__` per element of `other` |
| `s & other` | O(k) | O(min(n, k)) | Iterates `other` with one `s.__contains__` per element; `other` may be any iterable |
| `s \| other` | O(n + k) | O(n + k) | Iterates both into the constructor, which removes the duplicates; no `__contains__` calls |
| `s - other` | O(n + k) | O(n + k) | One `other.__contains__` per element of `s`; an `other` that is not a `Set` is first built into one through `_from_iterable()`, O(k) |
| `other - s` | O(n + k) | O(k) | One `s.__contains__` per element of `other`, after the same conversion |
| `s ^ other` | O(n + k) | O(n + k) | `(s - other) \| (other - s)`: n `other.__contains__` calls, k `s.__contains__` calls and three intermediate sets |
| `Set.isdisjoint(other)` | O(k) | O(1) | One `s.__contains__` per element of `other`, stopping at the first shared one |
| `Set._hash()` | O(n) | O(1) | One `hash()` per element, combined the way `frozenset` does; call it from your `__hash__` |
| `Set._from_iterable(it)` | O(k) | O(k) | The constructor every operator uses for its result, `cls(it)` by default; override it when the class does not take an iterable |

### MutableSet

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `MutableSet.add(value)`, `MutableSet.discard(value)` | O(1) | O(1) | Abstract |
| `MutableSet.remove(value)` | O(1) | O(1) | One `__contains__`, raising `KeyError`, then one `discard()` |
| `MutableSet.pop()` | O(n + d) | O(1) | A fresh iterator's first element, then one `discard()`; over a `set`, the iterator scans the sparse table from its start, past empty slots and the d slots earlier discards emptied |
| `MutableSet.clear()` | O(n·(n + d)) | O(1) | `pop()` until `KeyError`, each call skipping every slot the earlier ones emptied; over a `set` |
| `s \|= it` | O(k) | O(1) | One `add()` per element |
| `s &= it` | O(n + k) | O(n + k) | Builds `s - it`, converting `it` first when it is not a `Set`, then one `discard()` per element of the difference |
| `s ^= it` | O(k) | O(k) | One `__contains__` and one `add()` or `discard()` per element of `it`, after converting it; `s ^= s` is `clear()`, at its cost |
| `s -= it` | O(k) | O(1) | One `discard()` per element of `it`; `s -= s` is `clear()`, at its cost |

### Mapping

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Mapping.get(key, default=None)` | O(1) | O(1) | One `__getitem__`, catching `KeyError` |
| `key in m` (`Mapping.__contains__()`) | O(1) | O(1) | The same |
| `Mapping.keys()`, `Mapping.items()`, `Mapping.values()` | O(1) | O(1) | Views holding a reference to the mapping; nothing is copied until they are iterated |
| `m == other` | O(n + k) | O(n + k) | `dict(m.items()) == dict(other.items())`: both sides are flattened into new dicts, n and k `__getitem__` calls |
| `reversed(m)` | O(1) | O(1) | `TypeError`: `Mapping.__reversed__` is `None`, so a subclass has to supply its own |
| `Mapping.__getitem__(key)` | O(1) | O(1) | Abstract |

### MappingView, KeysView, ItemsView and ValuesView

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(view)` (`MappingView.__len__()`) | O(1) | O(1) | One `__len__` on the mapping |
| Iterating a `KeysView` | O(n) | O(1) | The mapping's `__iter__` |
| Iterating an `ItemsView` or `ValuesView` | O(n) | O(1) | The mapping's `__iter__`, plus one `__getitem__` per key |
| `key in keys_view` (`KeysView.__contains__()`) | O(1) | O(1) | One `__contains__` on the mapping |
| `(key, value) in items_view` (`ItemsView.__contains__()`) | O(1) | O(1) | One `__getitem__` and one `==` |
| `value in values_view` (`ValuesView.__contains__()`) | O(i) | O(1) | One `__getitem__` and one `==` per key until the first match |
| `keys_view & other`, `items_view \| other` and the other `Set` operators | as for `Set` | O(n + k) | The `Set` mixins, with the result built as a plain `set` |

### MutableMapping

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `MutableMapping.pop(key, default)` | O(1) | O(1) | One `__getitem__` and one `__delitem__` |
| `MutableMapping.popitem()` | O(d) | O(1) | A fresh iterator's first key, then `__getitem__` and `__delitem__`; over a dict, the iterator skips the d slots earlier deletions emptied |
| `MutableMapping.clear()` | O(n·(n + d)) | O(1) | `popitem()` until `KeyError`, each call skipping every slot the earlier ones emptied; over a dict |
| `MutableMapping.update(other=(), /, **kwargs)` | O(k) | O(1) | One `__setitem__` per item; a `Mapping`, or anything with `keys()`, also costs one `other[key]` per key |
| `MutableMapping.setdefault(key, default=None)` | O(1) | O(1) | One `__getitem__`, plus one `__setitem__` on a miss |
| `MutableMapping.__setitem__(key, value)`, `MutableMapping.__delitem__(key)` | O(1) | O(1) | Abstract |

## Checking Against an ABC

The one-method ABCs are structural: `isinstance(x, Sized)` is true for anything whose class
defines `__len__`, found by scanning the MRO once and cached from then on. The container ABCs
with mixins are not. A class with `__getitem__`, `__iter__` and `__len__` is not a `Mapping`
until it inherits from one or is registered, and a first check against it walks the ABC's
registry and every subclass before caching the `False`. A `register()` that adds a new
relationship stales the negative cache of every ABC, so registering in a loop makes every
following miss pay the walk again.

```python
from abc import get_cache_token
from collections.abc import Mapping, Sized

class HasLen:
    def __len__(self):
        return 0

class DuckMapping:
    def __getitem__(self, key):
        raise KeyError(key)

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

assert isinstance(HasLen(), Sized)  # O(L) - __len__ found in the MRO, then cached
assert not isinstance(DuckMapping(), Mapping)  # O(L·(1 + R + S)) - no hook, nothing registered
assert isinstance(DuckMapping(), Sized)  # O(L) - the structural check still applies

token = get_cache_token()
Mapping.register(DuckMapping)  # O(L·(1 + R + S)) - and every negative cache goes stale
assert get_cache_token() != token
assert isinstance(DuckMapping(), Mapping)  # O(L·(1 + R + S)) once more, then O(1)
```

## Mixins Cost a Call Per Item

`Sequence.__iter__` does not know your storage. It asks for index 0, 1, 2 and so on until
`__getitem__` raises `IndexError`, which makes iteration n + 1 calls, `in` a call per position
up to the match, and `count()` a full pass. Give the subclass its own `__iter__` when the
storage can do better, and its own `__contains__` when it can do better than a scan.

```python
from collections.abc import MutableSequence

class Recorded(MutableSequence):
    def __init__(self, items):
        self._items = list(items)
        self.reads = self.writes = self.deletes = 0

    def __getitem__(self, index):
        self.reads += 1
        return self._items[index]

    def __setitem__(self, index, value):
        self.writes += 1
        self._items[index] = value

    def __delitem__(self, index):
        self.deletes += 1
        del self._items[index]

    def __len__(self):
        return len(self._items)

    def insert(self, index, value):
        self._items.insert(index, value)

seq = Recorded([10, 20, 30, 40])

assert list(seq) == [10, 20, 30, 40]  # O(n) - n + 1 reads, the last one raising IndexError
assert seq.reads == 5

seq.reads = 0
assert 20 in seq  # O(i) - stops at the match
assert seq.reads == 2

seq.reads = 0
seq.reverse()  # O(n) - n reads and n writes
assert seq.reads == 4 and seq.writes == 4 and list(seq) == [40, 30, 20, 10]

seq.reads = 0
seq.clear()  # O(n) - pop() from the end until a read raises IndexError
assert seq.reads == 5 and seq.deletes == 4 and len(seq) == 0
```

## Set Operators Build Through the Constructor

Every binary operator on a `Set` subclass produces its result by calling `_from_iterable()`,
which is `cls(iterable)` unless you override it. The class must therefore accept an iterable,
or the operators raise. The costs follow the loop each operator runs: `&` iterates the other
operand and tests membership in `self`, `-` does the reverse, and `|` tests nothing and lets the
constructor drop the duplicates.

```python
from collections.abc import Set

class Tagged(Set):
    def __init__(self, items=()):
        self._items = frozenset(items)
        self.membership = 0

    def __contains__(self, value):
        self.membership += 1
        return value in self._items

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

evens = Tagged(range(0, 10, 2))
small = Tagged(range(4))

both = evens & small  # O(k) - one evens.__contains__ per element of small
assert type(both) is Tagged and set(both) == {0, 2}
assert evens.membership == 4

evens.membership = 0
either = evens | small  # O(n + k) - no membership tests; the constructor dedupes
assert set(either) == {0, 1, 2, 3, 4, 6, 8}
assert evens.membership == 0

only = evens - small  # O(n + k) - one small.__contains__ per element of evens
assert set(only) == {4, 6, 8}
assert small.membership == 5

assert not evens.isdisjoint([1, 3, 0, 5])  # O(k) - stops at the first shared element
assert evens.membership == 3
```

## Emptying a Mapping Through the Mixins

`MutableMapping.clear()` is `popitem()` in a loop, and `popitem()` takes the first key of a
fresh iterator. Over a dict-backed store that is quadratic, O(n·(n + d)): each new iterator has to skip the
slots the earlier deletions left empty. The same shape makes `MutableSet.clear()` quadratic
over a `set`. A subclass that owns a real store should define `clear()` itself. `__eq__` has a
cost of its own: it flattens both mappings into dicts before comparing.

```python
from collections.abc import MutableMapping

class Store(MutableMapping):
    def __init__(self, **items):
        self._data = dict(items)
        self.iterators = 0

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def __iter__(self):
        self.iterators += 1
        return iter(self._data)

    def __len__(self):
        return len(self._data)

store = Store(a=1, b=2, c=3)

assert store.popitem() == ("a", 1)  # O(d) - the first key a fresh iterator yields
assert store.iterators == 1

store.clear()  # O(n·(n + d)) - one fresh iterator per remaining key, plus the one that finds none
assert store.iterators == 4 and len(store) == 0

store.update(x=1, y=2)  # O(k) - one __setitem__ per item
assert store == {"x": 1, "y": 2}  # O(n + k) - both sides copied into dicts first
assert store.get("z", 0) == 0  # O(1) - one __getitem__, KeyError caught
assert type(store.keys() & {"x"}) is set  # the Set mixins build a plain set
```

## Performance Best Practices

✅ **Do**:

- Define `__iter__` on a `Sequence` subclass whose storage can iterate faster than repeated indexing; the mixin costs a call per index
- Define `__contains__` on a `Sequence` or `Mapping` subclass with a real index, so `in` is not a scan or a `__getitem__` round trip
- Define `clear()` on a `MutableMapping` or `MutableSet` subclass with a real store; the mixin is quadratic over a dict or set
- Test against `Sized`, `Iterable` or `Container` when a structural check is what you mean; the mixin ABCs need inheritance or `register()`

❌ **Avoid**:

- `register()` inside a loop or a hot path: each new registration stales every ABC's negative cache, so each following miss walks the registry and subclass tree again
- A `Set` subclass whose constructor does not take an iterable without overriding `_from_iterable()`; every operator builds its result through it
- Comparing `Mapping` subclasses with `==` in a loop: each comparison copies both sides into dicts
- `isinstance(obj, ByteString)` on 3.12+: a `DeprecationWarning` per check on top of the walk; test for `Buffer` or the concrete types

## Version Notes

- **Python 3.12+**: `Buffer` is added, and `ByteString` is deprecated: checking against it or subclassing it emits a `DeprecationWarning`
- **All Python 3**: the negative cache of every ABC is invalidated by any `register()` call that adds a new relationship, through the token `abc.get_cache_token()` exposes

## Related Modules

- **[collections](collections.md)** - `UserDict`, `UserList` and `UserString`, the wrappers that inherit these mixins
- **[abc](abc.md)** - the metaclass, its caches and `register()`
- **[typing](typing.md)** - the aliases that point at these ABCs, and runtime-checkable protocols as the other structural check
