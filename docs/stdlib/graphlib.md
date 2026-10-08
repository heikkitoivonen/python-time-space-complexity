# graphlib Module Complexity

The `graphlib` module topologically sorts a graph of hashable nodes: it hands out nodes in an
order where every node comes after all of its predecessors, and detects cycles. It is pure Python,
built on one dictionary entry per node and one successor-list entry per edge, so a sorter holds
O(v + e) for as long as it lives.

`v` is nodes and `e` is edges, counting every predecessor passed to `add()` or in the `graph`
mapping, a repeated one included. `k` is the predecessors in one `add()` call, `r` is the nodes one
`get_ready()` call returns, and `d` is the successor entries of the nodes passed to one `done()`
call. Hashing and comparing a node are treated as O(1).

## Complexity Reference

### TopologicalSorter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `graphlib.TopologicalSorter(graph=None)` | O(1); O(v + e) with `graph` | O(1); O(v + e) with `graph` | `graph` maps each node to an iterable of its predecessors; each entry is one `add()` |
| `TopologicalSorter.add(node, *predecessors)` | O(k) | O(k) | Calls for the same node add to its predecessors; raises `ValueError` after `prepare()` |
| `TopologicalSorter.prepare()` | O(v + e) | O(v) | Finds the nodes with no predecessors and searches the whole graph for a cycle, raising `CycleError` if it finds one |
| `TopologicalSorter.get_ready()` | O(r) | O(r) | Returns every node made ready since the last call, as a tuple; each node is returned once, so a whole sort spends O(v) here |
| `TopologicalSorter.done(*nodes)` | O(len(nodes) + d) | O(len(nodes) + d) | Queues the successors it unblocks; over a whole sort, O(v + e) |
| `TopologicalSorter.is_active()`, `bool(sorter)` | O(1) | O(1) | `True` while a node is ready or handed out and not yet done |
| `TopologicalSorter.static_order()` | O(v + e) | O(v) | A generator: calls `prepare()` on the first `next()`, then hands out one ready group at a time |

### CycleError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `graphlib.CycleError` | O(1) | O(1) | A `ValueError` subclass raised by `prepare()`; `args[1]` is one cycle, its first node repeated at the end |

## Sorting a Graph

### Static Order

`static_order()` is the whole sort in one call: build the sorter, iterate. It is a generator, so
calling it does nothing; the `prepare()` inside it, and any `CycleError`, arrive on the first
`next()`.

```python
from graphlib import CycleError, TopologicalSorter

graph = {'cook': ['shop'], 'lunch': ['cook'], 'shop': []}
ts = TopologicalSorter(graph)  # O(v + e)
assert list(ts.static_order()) == ['shop', 'cook', 'lunch']  # O(v + e)

cyclic = TopologicalSorter({'a': ['b'], 'b': ['a']})
order = cyclic.static_order()  # O(1) - nothing has run yet
try:
    next(order)  # prepare() runs here
except CycleError as error:
    assert error.args[1] in (['a', 'b', 'a'], ['b', 'a', 'b'])
else:
    raise AssertionError('a cycle was sorted')
```

### Processing Ready Groups

`get_ready()` returns every node whose predecessors are all done, so each group can be worked on
in parallel. A node handed out stays active until it is passed to `done()`: `get_ready()` then
returns an empty tuple while `is_active()` is still `True`, which is how a worker pool waits for
results instead of finishing early.

```python
from graphlib import TopologicalSorter

ts = TopologicalSorter()
ts.add('compile', 'preprocess', 'fetch_headers')  # O(k)
ts.add('preprocess', 'download')
ts.add('test', 'compile')
ts.prepare()  # O(v + e)

first = ts.get_ready()  # O(r)
assert set(first) == {'download', 'fetch_headers'}
assert ts.get_ready() == ()  # nothing new until something is done
assert ts.is_active()  # O(1) - two nodes are still out

ts.done(*first)  # O(len(nodes) + d)
assert ts.get_ready() == ('preprocess',)

groups = [set(first), {'preprocess'}]
ts.done('preprocess')
while ts.is_active():
    group = ts.get_ready()
    groups.append(set(group))
    ts.done(*group)

assert groups == [{'download', 'fetch_headers'}, {'preprocess'}, {'compile'}, {'test'}]
```

### Order and Duplicates

Nodes in the same group carry no guaranteed order between them. Calling `add()` again for a node adds to its
predecessors, and a predecessor named twice is two edges that `done()` releases together.

```python
from graphlib import TopologicalSorter

ts = TopologicalSorter()
ts.add('app', 'lib')
ts.add('app', 'config', 'lib')  # union with the earlier call
order = list(ts.static_order())

assert order.index('app') == 2
assert set(order[:2]) == {'lib', 'config'}
```

## Cycles

`prepare()` searches the whole graph for a cycle before anything is handed out and reports the
first one it finds. The sorter stays usable: `get_ready()` still returns every node the cycle does
not block, and `is_active()` turns `False` once only blocked nodes are left.

```python
from graphlib import CycleError, TopologicalSorter

ts = TopologicalSorter({'a': ['b'], 'b': ['a'], 'c': [], 'd': ['c']})
try:
    ts.prepare()  # O(v + e)
except CycleError as error:
    assert isinstance(error, ValueError)
    cycle = error.args[1]
    assert cycle[0] == cycle[-1] and set(cycle) == {'a', 'b'}
else:
    raise AssertionError('the cycle went unreported')

done = []
while ts.is_active():
    group = ts.get_ready()
    done.extend(group)
    ts.done(*group)

assert done == ['c', 'd']  # the cycle's nodes are never handed out
```

## Sorting the Same Graph Twice

Once a sorter has handed out a node it cannot be prepared again, so one traversal uses it up, and
nodes cannot be added once it is prepared. To sort a graph again, keep the graph and build a new
sorter from it, which is O(v + e). Keep its predecessors in lists or other collections: an
iterator is consumed by the first sorter built from it.

```python
from graphlib import TopologicalSorter

graph = {'b': ['a'], 'c': ['b']}
ts = TopologicalSorter(graph)
assert list(ts.static_order()) == ['a', 'b', 'c']

try:
    list(ts.static_order())  # the sorter is spent
except ValueError:
    pass
else:
    raise AssertionError('a sorter was traversed twice')

try:
    ts.add('d', 'c')
except ValueError as error:
    assert 'prepare' in str(error)
else:
    raise AssertionError('a node was added after prepare()')

again = TopologicalSorter(graph)  # O(v + e) - rebuild from the graph
assert list(again.static_order()) == ['a', 'b', 'c']
```

## Common Patterns

### Build Stages

Each `get_ready()` group is a stage whose members can run in parallel; the whole schedule costs
O(v + e).

```python
from graphlib import TopologicalSorter

targets = {
    'prog': ['main.o', 'util.o'],
    'main.o': ['main.c', 'defs.h'],
    'util.o': ['util.c', 'defs.h'],
}

ts = TopologicalSorter(targets)  # O(v + e)
ts.prepare()  # O(v + e)

stages = []
while ts.is_active():  # O(1)
    stage = ts.get_ready()  # O(r)
    stages.append(set(stage))
    ts.done(*stage)  # O(len(nodes) + d)

assert stages == [{'defs.h', 'main.c', 'util.c'}, {'main.o', 'util.o'}, {'prog'}]
```

### Running Ready Tasks on a Pool

```python
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from graphlib import TopologicalSorter

graph = {'process': ['download'], 'upload': ['process'], 'report': ['download']}
ts = TopologicalSorter(graph)
ts.prepare()

finished = []
with ThreadPoolExecutor(max_workers=2) as pool:
    running = {}
    while ts.is_active():
        for node in ts.get_ready():  # O(r)
            running[pool.submit(str.upper, node)] = node
        completed, _ = wait(running, return_when=FIRST_COMPLETED)
        for future in completed:
            node = running.pop(future)
            finished.append(future.result())
            ts.done(node)  # unblocks its successors

assert finished[0] == 'DOWNLOAD'
assert finished.index('PROCESS') < finished.index('UPLOAD')
assert sorted(finished) == ['DOWNLOAD', 'PROCESS', 'REPORT', 'UPLOAD']
```

## Performance Best Practices

✅ **Do**:

- Use `static_order()` when one sequential order is all you need
- Use `get_ready()` and `done()` when work can run in parallel: each node is handed out and
  released once, so the bookkeeping stays O(v + e) for the whole sort
- Keep the graph, with its predecessors in lists, and build a new sorter to sort it again

❌ **Avoid**:

- Calling `prepare()` before `static_order()`: it repeats the O(v + e) cycle search on 3.14 and
  raises `ValueError` on earlier versions
- Relying on the order of nodes within one ready group
- Treating an empty `get_ready()` as the end of the sort; check `is_active()`

## Version Notes

- **Python 3.14+**: `prepare()` may be called again until a node has been handed out, each call
  a fresh O(v + e) cycle search; earlier versions raise `ValueError` on a second call

## Related Modules

- **[concurrent.futures](concurrent_futures.md)** - run each ready group on a pool
- **[collections](collections.md)** - `deque` and `defaultdict` for writing a custom graph walk
- **[heapq](heapq.md)** - when ready nodes must come out in priority order
