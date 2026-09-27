# queue Module Complexity

The `queue` module provides synchronized queues for handing work between threads. `Queue`,
`LifoQueue` and `PriorityQueue` share one lock-protected implementation that differs only in the
container underneath: a deque, a list used as a stack, and a list kept as a binary heap.
`SimpleQueue` is a separate, smaller C type with no size limit and no task tracking.

`n` is the items currently in the queue and `w` is the threads blocked in `put()`, `get()` or
`join()` on it. Every bound excludes time spent waiting - for an item, for room, or for
outstanding tasks - and prices acquiring the queue's lock and comparing two items as O(1).

## Complexity Reference

### Queue

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `queue.Queue(maxsize=0)` | O(1) | O(1) | Nothing is sized by `maxsize`; `maxsize <= 0` means unbounded |
| `Queue.put(item, block=True, timeout=None)` | O(1) | O(1) | Appends to a deque; waits for room only when `maxsize > 0` and the queue is full |
| `Queue.put_nowait(item)` | O(1) | O(1) | `put(item, block=False)`: raises `Full` instead of waiting |
| `Queue.get(block=True, timeout=None)` | O(1) | O(1) | Removes the oldest item; waits while the queue is empty |
| `Queue.get_nowait()` | O(1) | O(1) | `get(block=False)`: raises `Empty` instead of waiting |
| `Queue.qsize()`, `Queue.empty()`, `Queue.full()` | O(1) | O(1) | A snapshot: another thread can change the queue before the answer is used |
| `Queue.task_done()` | O(1); O(w) for the last item | O(1) | Marks one item from `get()` finished; the call that finishes the last outstanding item wakes every thread in `join()`. Raises `ValueError` when called more often than items were put |
| `Queue.join()` | O(1) | O(1) | Waits until every item put has had its `task_done()`; returns at once when none is outstanding |
| `Queue.shutdown(immediate=False)` | O(w) | O(1) | Python 3.13+. Wakes every thread blocked in `put()` or `get()`; later `put()` calls raise `ShutDown`, and `get()` does once the queue is empty |
| `Queue.shutdown(immediate=True)` | O(n + w) | O(1) | Python 3.13+. Also discards all n items and counts each as done, so `join()` waits only for items already taken; on a `PriorityQueue` that is n heap pops, O(n log n + w) |

### PriorityQueue

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `queue.PriorityQueue(maxsize=0)` | O(1) | O(1) | Same interface as `Queue`, over a list kept as a heap |
| `PriorityQueue.put(item, block=True, timeout=None)` | O(log n) | O(1) amortized | Heap push; items must be comparable with each other, usually as `(priority, data)` tuples |
| `PriorityQueue.get(block=True, timeout=None)` | O(log n) | O(1) | Heap pop of the smallest item |

### LifoQueue

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `queue.LifoQueue(maxsize=0)` | O(1) | O(1) | Same interface as `Queue`, over a list used as a stack |
| `LifoQueue.put(item, block=True, timeout=None)` | O(1) amortized | O(1) amortized | List append |
| `LifoQueue.get(block=True, timeout=None)` | O(1) | O(1) | Removes the newest item |

### SimpleQueue

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `queue.SimpleQueue()` | O(1) | O(1) | Unbounded FIFO; no `maxsize`, `task_done()`, `join()` or `shutdown()` |
| `SimpleQueue.put(item, block=True, timeout=None)`, `SimpleQueue.put_nowait(item)` | O(1) amortized | O(1) amortized | Never waits; `block` and `timeout` are accepted and ignored. Safe to call from `__del__` or a signal handler |
| `SimpleQueue.get(block=True, timeout=None)` | O(1) amortized | O(1) amortized | Removes the oldest item; waits while the queue is empty |
| `SimpleQueue.get_nowait()` | O(1) amortized | O(1) amortized | `get(block=False)`: raises `Empty` instead of waiting |
| `SimpleQueue.qsize()`, `SimpleQueue.empty()` | O(1) | O(1) | A snapshot, as for `Queue` |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `queue.Empty` | O(1) | O(1) | Raised by a non-blocking `get()` on an empty queue, or when a `get()` timeout expires |
| `queue.Full` | O(1) | O(1) | Raised by a non-blocking `put()` on a full queue, or when a `put()` timeout expires |
| `queue.ShutDown` | O(1) | O(1) | Python 3.13+. Raised by `put()` after `shutdown()`, and by `get()` once a shut-down queue is empty |

## Choosing a Queue Class

The three `Queue` classes differ only in which item `get()` returns. First-in-first-out and
last-in-first-out are O(1) per item, amortized for a `LifoQueue` put; keeping the smallest item
at the front costs O(log n) on both sides.

```python
from queue import LifoQueue, PriorityQueue, Queue

fifo = Queue()  # O(1)
for item in ['a', 'b', 'c']:
    fifo.put(item)  # O(1)
assert [fifo.get() for _ in range(3)] == ['a', 'b', 'c']  # O(1) each

lifo = LifoQueue()  # O(1)
for item in ['a', 'b', 'c']:
    lifo.put(item)  # O(1) amortized
assert [lifo.get() for _ in range(3)] == ['c', 'b', 'a']  # O(1) each

pq = PriorityQueue()  # O(1)
pq.put((3, 'low'))     # O(log n)
pq.put((1, 'high'))    # O(log n)
pq.put((2, 'medium'))  # O(log n)
assert pq.get() == (1, 'high')  # O(log n) - smallest first
assert pq.get() == (2, 'medium')
assert pq.get() == (3, 'low')
```

### Priorities With Uncomparable Data

A heap compares whole items, so two entries with the same priority fall back to comparing their
data. Put a counter between the priority and the data when the data does not support `<`.

```python
from itertools import count
from queue import PriorityQueue

pq = PriorityQueue()
try:
    pq.put((1, {'job': 'a'}))
    pq.put((1, {'job': 'b'}))  # the tie compares the two dicts
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError('two dicts were compared')

pq = PriorityQueue()
order = count()
pq.put((1, next(order), {'job': 'a'}))  # O(log n)
pq.put((1, next(order), {'job': 'b'}))  # the counter breaks the tie
assert pq.get()[2] == {'job': 'a'}  # equal priorities come out in insertion order
```

## Blocking, Timeouts and Non-blocking Calls

`put()` waits only on a bounded queue that is full, and `get()` only on an empty queue. The
`_nowait` forms and `block=False` raise instead, and a `timeout` raises once it expires. None of
this changes the cost of the operation once it proceeds.

```python
from queue import Empty, Full, Queue

q = Queue(maxsize=2)  # O(1)
q.put_nowait('item1')  # O(1)
q.put_nowait('item2')  # O(1)
assert q.full()        # O(1)

try:
    q.put_nowait('item3')
except Full:
    pass
else:
    raise AssertionError('a full queue accepted an item')

try:
    q.put('item3', timeout=0.01)  # waits up to 10 ms for room
except Full:
    pass
else:
    raise AssertionError('a full queue accepted an item')

assert q.get_nowait() == 'item1'  # O(1)
assert q.get(timeout=0.01) == 'item2'  # an item is there, so no wait
assert q.empty()

try:
    q.get(timeout=0.01)  # waits up to 10 ms for an item
except Empty:
    pass
else:
    raise AssertionError('an empty queue returned an item')

unbounded = Queue()  # maxsize=0: put() never waits
for i in range(1000):
    unbounded.put_nowait(i)  # O(1)
assert unbounded.qsize() == 1000  # O(1)
```

## Tracking Completion

Every `put()` adds one to a count of unfinished tasks and every `task_done()` removes one.
`join()` waits for that count to reach zero, so it waits for items to be processed, not merely
taken.

```python
import threading
from queue import Queue

q = Queue()
results = []

def worker():
    while True:
        item = q.get()        # O(1), waits while empty
        results.append(item * 2)
        q.task_done()         # O(1)

threading.Thread(target=worker, daemon=True).start()

for item in range(10):
    q.put(item)               # O(1)

q.join()                      # returns once all 10 have had task_done()
assert sorted(results) == [i * 2 for i in range(10)]

try:
    q.task_done()             # one more than items put
except ValueError as error:
    assert 'too many times' in str(error)
else:
    raise AssertionError('an extra task_done() was accepted')
```

## Shutting Down

From Python 3.13, `shutdown()` ends a queue's life without a sentinel item per consumer. Every
caller blocked in `put()` or `get()` is woken, `put()` raises `ShutDown` from then on, and `get()` keeps returning what
is left before it raises too. `immediate=True` discards the remaining items instead, which is the
one operation here that walks the queue.

```python
import sys
from queue import Queue

if sys.version_info >= (3, 13):
    from queue import ShutDown

    q = Queue()
    for item in ['a', 'b']:
        q.put(item)
    q.shutdown()                  # O(w)

    try:
        q.put('c')
    except ShutDown:
        pass
    else:
        raise AssertionError('a shut-down queue accepted an item')

    assert q.get() == 'a'         # items already queued still come out
    assert q.get() == 'b'
    try:
        q.get()                   # empty and shut down: raises, never waits
    except ShutDown:
        pass
    else:
        raise AssertionError('get() returned from an empty shut-down queue')

    q = Queue()
    for item in range(100):
        q.put(item)
    q.shutdown(immediate=True)    # O(n + w) - discards all 100 items
    assert q.qsize() == 0
    q.join()                      # the discarded items count as done
```

## SimpleQueue

`SimpleQueue` trades the task count, the size limit and `shutdown()` for a `put()` that never
waits and is safe to call from `__del__` or a signal handler. Its buffer grows and shrinks with
the queue, so both ends are O(1) amortized rather than O(1) every time.

```python
from queue import Empty, SimpleQueue

sq = SimpleQueue()  # O(1)
sq.put('simple')              # O(1) amortized, never waits
sq.put('fast', block=False)   # accepted and ignored: it never blocks anyway
assert sq.qsize() == 2        # O(1)

assert sq.get() == 'simple'   # O(1) amortized
assert sq.get_nowait() == 'fast'
assert sq.empty()

try:
    sq.get(timeout=0.01)
except Empty:
    pass
else:
    raise AssertionError('an empty SimpleQueue returned an item')

assert not hasattr(sq, 'task_done') and not hasattr(sq, 'join')
```

## Queue vs deque

A `collections.deque` has the same O(1) ends, and each append or pop is atomic on its own. What
a `Queue` adds is waiting: `get()` waits for an item and a bounded `put()` for room, where
`popleft()` on an empty deque raises at once.

```python
from collections import deque
from queue import Queue

q = Queue()
q.put('item')     # O(1)
assert q.get() == 'item'  # O(1); on an empty queue this would wait

d = deque()
d.append('item')  # O(1), safe from several threads
assert d.popleft() == 'item'  # O(1)
try:
    d.popleft()   # an empty deque raises instead of waiting
except IndexError:
    pass
else:
    raise AssertionError('an empty deque returned an item')

# A check-then-pop such as `if d: d.popleft()` can race between the two
# steps: another thread can empty the deque in between. Use a Queue when a
# consumer must wait for work, and a deque when nothing needs to block.
```

## Common Patterns

### Worker Pool

A bounded queue keeps a fast producer from getting more than `maxsize` items ahead of the
workers, so at most `maxsize` items wait in the queue however much work is submitted.

```python
import threading
from queue import Queue

tasks = Queue(maxsize=4)   # the producer waits when 4 items are pending
results = Queue()
workers = 3

def worker():
    while True:
        item = tasks.get()     # O(1)
        if item is None:       # one sentinel per worker
            break
        results.put(item * item)  # O(1)

threads = [threading.Thread(target=worker) for _ in range(workers)]
for thread in threads:
    thread.start()

for item in range(100):
    tasks.put(item)            # O(1), waits while 4 are pending
for _ in range(workers):
    tasks.put(None)
for thread in threads:
    thread.join()

squares = sorted(results.get_nowait() for _ in range(results.qsize()))
assert squares == [i * i for i in range(100)]
```

## Performance Best Practices

✅ **Do**:

- Use `Queue` or `SimpleQueue` for FIFO hand-off: both ends are O(1), amortized for `SimpleQueue`
- Bound a producer-consumer queue with `maxsize`, so the items waiting in it, and their memory, stay capped
- Put `(priority, counter, data)` in a `PriorityQueue` when data may tie and does not compare
- Pair every `get()` with `task_done()` when anything calls `join()`
- Use `shutdown()` on Python 3.13+ to release blocked consumers instead of one sentinel each

❌ **Avoid**:

- `PriorityQueue` when arrival order will do: it pays O(log n) at both ends for ordering you do not use
- Acting on `qsize()`, `empty()` or `full()` from another thread: the answer can be stale before it is used
- A `Queue` in single-threaded code: a `deque` has the same O(1) ends without the lock
- A consumer's blocking `get()` with no timeout, sentinel or `shutdown()` to end it: once the producers stop, it waits forever

## Version Notes

- **Python 3.13+**: Added `Queue.shutdown()` and `queue.ShutDown`

## Related Modules

- **[deque](deque.md)** - The container under `Queue`; atomic appends and pops that never wait
- **[heapq](heapq.md)** - The heap under `PriorityQueue`, for single-threaded priority queues
- **[threading](threading.md)** - The threads these queues connect, and the locks they use
- **[asyncio](asyncio.md)** - `asyncio.Queue`, a similar interface for coroutines
- **[multiprocessing](multiprocessing.md)** - Queues that cross process boundaries
