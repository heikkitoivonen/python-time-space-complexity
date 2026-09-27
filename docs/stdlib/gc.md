# gc Module Complexity

The `gc` module controls the cyclic garbage collector. Reference counting frees most objects the
moment their last reference goes; the collector exists for reference cycles, which reference
counting cannot free. It tracks container objects - lists, dicts, class instances, functions - in
generations, and a collection walks the objects of the generations it examines and every reference
they hold. Apart from what it appends to `gc.garbage`, a collection allocates nothing per object:
its unit of work is objects and references visited, not memory.

`n` is the objects the collector tracks outside the permanent generation that `freeze()` fills, and
`e` is the references those objects hold, whether or not the referenced object is tracked: a list
of a million ints is one tracked object and a million references. References are counted as the
slots a container walks, so a dict or set costs its table size, which deletions do not shrink.
`g` is the objects in the generations one call names and `h` the references they hold, `f` is
frozen objects, `k` is the objects passed to `get_referrers()` or `get_referents()`, taken as at
least one, `a` is the references the arguments of `get_referents()` hold, `r` is the objects
returned, and `c` is the callbacks in `gc.callbacks`. Finalizers, weak reference callbacks and
`gc.callbacks` functions that a collection runs are the caller's code and are not priced. The
bounds are for the standard build; the free-threaded build has a different collector.

## Complexity Reference

### Collection

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gc.collect(generation=2)` | O(n + e) | O(1) | A full collection; frozen objects are skipped. Space excludes what `DEBUG_SAVEALL` keeps |
| `gc.collect(0)`, `gc.collect(1)` | O(g + h) | O(1) | Generation 0, or generations 0 and 1; older objects are not visited |
| Automatic collection | Amortized O(1 + e/n) per allocation | O(1) | Plus the new object's references; a full collection runs once the survivors grow by a quarter, and costs n + e |
| `gc.enable()`, `gc.disable()`, `gc.isenabled()` | O(1) | O(1) | Switch automatic collection only; `collect()` still works while disabled |
| `gc.get_threshold()`, `gc.set_threshold(threshold0[, threshold1[, threshold2]])` | O(1) | O(1) | A `threshold0` of 0 also disables automatic collection |
| `gc.get_count()` | O(1) | O(1) | The three counters the thresholds are compared against |
| `gc.get_stats()` | O(1) | O(1) | One dict per generation, three in all |

### Inspecting objects

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gc.get_objects(generation=None)` | O(n) | O(n) | Frozen objects are not included |
| `gc.get_objects(generation)` | O(g) | O(g) | Only the named generation is walked |
| `gc.get_referrers(*objs)` | O(n + k·e) | O(r) | Walks every tracked object and checks each reference against all k arguments; frozen objects are not searched |
| `gc.get_referents(*objs)` | O(k + a) | O(a) | Only the arguments' own direct references; the rest of the heap is not visited |
| `gc.is_tracked(obj)` | O(1) | O(1) | Ints, strings and other atomic objects are never tracked |
| `gc.is_finalized(obj)` | O(1) | O(1) | True once the interpreter has finalized the object; it never does so twice |

### Freezing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gc.freeze()` | O(1) | O(1) | Moves every tracked object into the permanent generation, which no collection visits |
| `gc.unfreeze()` | O(1) | O(1) | Moves the permanent generation back into the oldest one |
| `gc.get_freeze_count()` | O(f) | O(1) | Counts the permanent generation by walking it |

### Debugging, garbage and callbacks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gc.set_debug(flags)`, `gc.get_debug()` | O(1) | O(1) | |
| `gc.DEBUG_STATS`, `gc.DEBUG_COLLECTABLE`, `gc.DEBUG_UNCOLLECTABLE`, `gc.DEBUG_SAVEALL`, `gc.DEBUG_LEAK` | O(1) | O(1) | Integer flags; `DEBUG_SAVEALL`, part of `DEBUG_LEAK`, keeps every unreachable object in `gc.garbage` instead of freeing it |
| `gc.garbage` | O(1) | O(1) | A plain list; the collector appends to it and never empties it |
| `gc.callbacks` | O(1) | O(1) | A plain list; every collection calls each callback twice, adding O(c) calls |

## Collecting Cycles

### Full and Young Collections

A full collection costs every tracked object and every reference they hold, whether or not
anything is garbage. Collecting generation 0 visits only the objects that became tracked since the
last collection, so it stays cheap however large the rest of the heap is.

```python
import gc
import weakref

class Node:
    pass

node = Node()
node.self = node  # a cycle reference counting cannot free
alive = weakref.ref(node)
del node
assert alive() is not None

gc.collect()  # O(n + e) - a full collection
assert alive() is None

survivors = [[] for _ in range(1_000)]
gc.collect(0)  # O(g + h) - generation 0 only
assert gc.get_objects(0) == []  # O(g) - the survivors moved to an older generation
```

### Automatic Collection

Once allocations of container objects minus their deallocations exceed `threshold0`, generation 0
is collected; once that has happened more than `threshold1` times, generation 1 is collected with
it. A full collection also waits until the objects that survived since the last one number a
quarter of those it kept. Each full walk is paid for by the quarter that triggered it, so building
a large structure costs amortized O(1 + e/n) per object rather than a full walk every few thousand
allocations: O(1) while objects hold a few references each, more when a few old containers hold
most of the references. `gc.disable()` or a `threshold0` of 0 stops the
automatic collections; `collect()` works either way.

```python
import gc

previous = gc.get_threshold()  # O(1)
gc.set_threshold(100, 10, 10)  # O(1)
assert gc.get_threshold()[:2] == (100, 10)

runs = []
gc.callbacks.append(lambda phase, info: runs.append(info['generation']))
kept = [[] for _ in range(1_000)]  # amortized O(1 + e/n) per list
gc.callbacks.clear()
assert runs  # collections ran along the way, without a call to collect()

assert len(gc.get_count()) == 3  # O(1)
assert [set(stats) for stats in gc.get_stats()] == [  # O(1)
    {'collections', 'collected', 'uncollectable'}
] * 3

gc.disable()  # O(1)
assert not gc.isenabled()
gc.enable()
gc.set_threshold(*previous)
```

## Finding References

`get_referents()` reads only the arguments' own references. `get_referrers()` has no index to
consult: it walks every tracked object in the heap and checks each of its references against every
argument, so it is the costly direction and grows with the number of targets as well as the heap.

```python
import gc

target = {'value': 1}
holder = [target]

assert gc.get_referents(holder) == [target]  # O(k + a) - direct references only
assert any(r is holder for r in gc.get_referrers(target))  # O(n + k·e)

assert gc.is_tracked(holder)  # O(1)
assert not gc.is_tracked(42) and not gc.is_tracked('text')
```

## Freezing Before a Fork

`freeze()` moves every tracked object into a permanent generation that collections skip, which
keeps collections in a forked child from writing to the frozen objects, so their pages stay shared,
and makes later collections cheaper.
Freezing and unfreezing move whole generations at once; `get_freeze_count()` is the one that
walks, so it costs the frozen object count.

```python
import gc

held = [[] for _ in range(1_000)]
gc.freeze()  # O(1)
assert gc.get_freeze_count() >= 1_000  # O(f)

assert not any(o is held for o in gc.get_objects())  # frozen objects are not listed
assert gc.get_referrers(held[0]) == []  # nor searched
gc.collect()  # O(n + e) - n excludes the frozen objects

gc.unfreeze()  # O(1)
assert gc.get_freeze_count() == 0
assert any(r is held for r in gc.get_referrers(held[0]))
```

## Debugging Leaks

`DEBUG_SAVEALL` makes every collection append what it finds unreachable to `gc.garbage` instead of
freeing it, so memory grows with each collection until you empty the list. Callbacks in
`gc.callbacks` are called with `'start'` and `'stop'` around each collection.

```python
import gc

events = []

def record(phase, info):
    events.append((phase, info['generation']))

gc.callbacks.append(record)  # O(1)
gc.set_debug(gc.DEBUG_SAVEALL)  # O(1)
assert gc.get_debug() == gc.DEBUG_SAVEALL
assert gc.DEBUG_LEAK & gc.DEBUG_SAVEALL

cycle = []
cycle.append(cycle)
del cycle
gc.collect()
assert any(len(o) == 1 and o[0] is o for o in gc.garbage if isinstance(o, list))
assert events[-2:] == [('start', 2), ('stop', 2)]

gc.set_debug(0)
gc.garbage.clear()
gc.callbacks.remove(record)
```

### Finalized Objects

`is_finalized()` reports whether the interpreter has already run an object's `__del__` as its
finalizer, which matters for an object that `__del__` resurrected: it is not finalized a second
time. Calling `__del__` yourself does not count.

```python
import gc

saved = []

class Phoenix:
    def __del__(self):
        saved.append(self)  # resurrect it

bird = Phoenix()
assert not gc.is_finalized(bird)  # O(1)
bird.self = bird
del bird
gc.collect()
assert gc.is_finalized(saved[0])
```

## Common Patterns

### Building a Large Structure

Automatic collection keeps a bulk build of small objects linear, but each young collection still
walks the new objects, and each full one walks the whole heap. Pausing the collector for the build
removes those walks; switch it back on in a `finally` so an exception cannot leave it off.

```python
import gc

was_enabled = gc.isenabled()
gc.disable()  # O(1)
try:
    table = {i: [i] for i in range(10_000)}  # no collections during the build
finally:
    if was_enabled:
        gc.enable()

assert len(table) == 10_000
```

## Performance Best Practices

✅ **Do**:

- Walk outward from objects you hold with `get_referents()` where that answers the question:
  it reads those objects, while `get_referrers()` walks the heap
- Pass every target to one `get_referrers()` call rather than one call each: a call walks the
  whole heap once, however many targets it checks
- Call `gc.freeze()` before `fork()` in a server that preloads data, so neither process walks it
- Collect generation 0 when you only need recently created cycles gone

❌ **Avoid**:

- `gc.collect()` in a loop: each call walks every tracked object and reference
- `get_freeze_count()` in a hot path: it walks the frozen objects
- Leaving `DEBUG_SAVEALL` on: `gc.garbage` then keeps every unreachable object ever found

## Version Notes

- **Python 3.14.0 to 3.14.4**: the collector is incremental, with a young and an old generation.
  `collect(1)` collects the young generation and an increment of the old one, `get_objects(1)` is
  always empty, and `freeze()` walks the young generation and one of the old generation's two
  spaces, O(n). Python 3.14.5 restores the three generations
- **Python 3.14+**: `is_tracked()` is true for every dict; earlier releases untrack a dict whose
  keys and values are all atomic

## Related Modules

- **[sys](sys.md)** - `getrefcount()` and `getsizeof()`, which look at one object, not the heap
- **[weakref](weakref.md)** - references that do not keep an object alive, so form no cycle
- **[tracemalloc](tracemalloc.md)** - where memory was allocated, not who holds it
- **[timeit](timeit.md)** - turns the collector off while it measures
