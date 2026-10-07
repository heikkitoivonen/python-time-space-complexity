# heapq Module Complexity

The `heapq` module keeps a binary heap inside an ordinary `list`: there is no heap type, only
functions that move items around a list you own so that `heap[0]` is always the smallest. Every
operation is in place, and only `nlargest`, `nsmallest` and `merge` keep anything of their own.

`n` is the items in the heap, `m` is the items taken from the input iterables, `k` is the items
`nlargest` or `nsmallest` is asked for, and `r` is the iterables passed to `merge`. Every bound
counts comparisons between items and treats one comparison, and one call of a `key` function,
as O(1).

## Complexity Reference

### Min-heap functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `heapq.heapify(x)` | O(n) | O(1) | In place |
| `heapq.heappush(heap, item)` | O(log n) amortized | O(1) amortized | The list grows the way `append` does |
| `heapq.heappop(heap)` | O(log n) amortized | O(1) | The list shrinks the way `pop` does; raises `IndexError` on an empty heap |
| `heapq.heappushpop(heap, item)` | O(log n) | O(1) | O(1), heap untouched, when the heap is empty or `item` is not larger than `heap[0]` |
| `heapq.heapreplace(heap, item)` | O(log n) | O(1) | Pops before it pushes, so it can return an item larger than `item`; raises `IndexError` on an empty heap |
| Reading `heap[0]` | O(1) | O(1) | The smallest item, without removing it |

### Max-heap functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `heapq.heapify_max(x)` | O(n) | O(1) | Python 3.14+; `heap[0]` is then the largest item |
| `heapq.heappush_max(heap, item)` | O(log n) amortized | O(1) amortized | Python 3.14+ |
| `heapq.heappop_max(heap)` | O(log n) amortized | O(1) | Python 3.14+; raises `IndexError` on an empty heap |
| `heapq.heappushpop_max(heap, item)` | O(log n) | O(1) | Python 3.14+; O(1), heap untouched, when the heap is empty or `item` is not smaller than `heap[0]` |
| `heapq.heapreplace_max(heap, item)` | O(log n) | O(1) | Python 3.14+; raises `IndexError` on an empty heap |

### Selecting and merging

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `heapq.nlargest(k, iterable, key=None)` | O(m log k) | O(k) | One comparison for an item that cannot enter the result, so random input with a small k costs close to O(m); ascending input makes every item enter. k = 1 is a `max()` pass, O(m). `key` is called once per item |
| `heapq.nsmallest(k, iterable, key=None)` | O(m log k) | O(k) | The mirror image: descending input is the worst case, and k = 1 is a `min()` pass |
| `heapq.merge(*iterables, key=None, reverse=False)` | O(r + m log r) | O(r) | Lazy: holds one item per input. Each input must already be sorted in the output's direction; this is not checked. `key` is called at most once per item |

## Heap Layout

A heap is a list in which the item at `i` is no larger than the two at `2*i + 1` and `2*i + 2`.
`heapify` establishes only that, in O(n): the list is not sorted, and only `heap[0]` is known to
be the smallest.

```python
import heapq

data = [5, 3, 7, 1, 9, 4]
heapq.heapify(data)  # O(n), in place

assert data[0] == 1          # O(1) - the root is the smallest
assert data != sorted(data)  # a heap, not a sorted list
for parent in range(len(data)):
    for child in (2 * parent + 1, 2 * parent + 2):
        if child < len(data):
            assert data[parent] <= data[child]
```

## Pushing and Popping

A push or a pop walks one path between the root and a leaf, so it costs the heap's height,
O(log n). Draining a whole heap is therefore O(n log n).

```python
import heapq

heap = []
for priority in [5, 1, 4, 2, 3]:
    heapq.heappush(heap, priority)  # O(log n) amortized

assert heap[0] == 1  # O(1) peek
drained = [heapq.heappop(heap) for _ in range(len(heap))]  # O(n log n) in total
assert drained == [1, 2, 3, 4, 5]

try:
    heapq.heappop(heap)
except IndexError as error:
    assert 'index out of range' in str(error)
else:
    raise AssertionError('popped from an empty heap')
```

### Ties and Uncomparable Payloads

Tuples compare field by field, so two entries with equal priorities go on to compare the next
field. Put a unique counter there and the payload is never compared: equal priorities then come
out in insertion order, and a payload that does not support `<` is never asked to.

```python
import heapq
import itertools

class Job:
    def __init__(self, name):
        self.name = name

heap = []
try:
    heapq.heappush(heap, (1, Job('a')))
    heapq.heappush(heap, (1, Job('b')))  # equal priority reaches Job < Job
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError('two Jobs were compared')

counter = itertools.count()
heap = []
for name in ['a', 'b', 'c']:
    heapq.heappush(heap, (1, next(counter), Job(name)))  # O(log n)

assert [heapq.heappop(heap)[2].name for _ in range(3)] == ['a', 'b', 'c']
```

## Combined Push and Pop

`heappushpop` and `heapreplace` do a push and a pop in one call that leaves the heap the same
size. They differ in order: `heappushpop` pushes first, so an item no larger than the root comes
straight back after one comparison; `heapreplace` pops first, so it always returns the old root,
even when that is larger than the new item.

```python
import heapq

heap = [2, 4, 6]
heapq.heapify(heap)

assert heapq.heappushpop(heap, 1) == 1  # O(1) here - 1 never enters the heap
assert heap == [2, 4, 6]

assert heapq.heapreplace(heap, 1) == 2  # O(log n) - pops 2, then pushes 1
assert sorted(heap) == [1, 4, 6]

assert heapq.heappushpop([], 7) == 7  # an empty heap returns the item
```

## Selecting the Top k

For k above 1, `nlargest` keeps the k best items seen so far in a heap and compares each new
item with the weakest of them. An item that cannot get in costs that one comparison, so on random
input with a small k the heap is rarely touched; an item that does get in costs O(log k). Input
already in ascending order is the worst case for `nlargest`, since every item beats everything
before it, and descending input is the worst case for `nsmallest`. Either way it is one pass
holding k items, against `sorted()`, which holds all m.

```python
import heapq

scores = [31, 7, 88, 54, 12, 99, 63, 5]

assert heapq.nlargest(3, scores) == [99, 88, 63]  # O(m log k), O(k) memory
assert heapq.nsmallest(2, scores) == [5, 7]       # O(m log k)
assert heapq.nlargest(3, scores) == sorted(scores, reverse=True)[:3]  # same answer, O(m log m)

# key is called once per item, and the items themselves are returned
words = ['pear', 'fig', 'banana', 'kiwi']
assert heapq.nlargest(2, words, key=len) == ['banana', 'pear']

# The input can be any iterable, consumed in one pass
assert heapq.nsmallest(2, (x * x for x in range(-3, 4))) == [0, 1]
```

## Merging Sorted Inputs

`merge` is a generator. The first `next()` takes one item from each input and heapifies them,
O(r); after that each item it yields costs at most one O(log r) sift to bring in that input's next
item. Nothing beyond one item per input is read ahead, so it can merge inputs too large for memory,
but it trusts the order it is given: an unsorted input produces unsorted output without an error.

```python
import heapq

merged = heapq.merge([1, 4, 7], [2, 5, 8], [3, 6, 9])  # O(1) - nothing is read yet
assert next(merged) == 1                               # O(r) - one item from each input
assert list(merged) == [2, 3, 4, 5, 6, 7, 8, 9]        # O(log r) per item

# key and reverse: each input must already be sorted that way
by_length = heapq.merge(['fig', 'pear'], ['kiwi', 'banana'], key=len)
assert list(by_length) == ['fig', 'pear', 'kiwi', 'banana']
descending = heapq.merge([9, 5, 1], [8, 2], reverse=True)
assert list(descending) == [9, 8, 5, 2, 1]

# Unsorted input is not detected
assert list(heapq.merge([3, 1], [2])) == [2, 3, 1]
```

## Max-Heaps

### The Max-Heap Functions

Python 3.14 adds a `_max` twin of each of the five heap functions. They have the same costs as
the min-heap functions, with `heap[0]` the largest item instead of the smallest.

```python
import heapq

data = [3, 1, 4, 1, 5, 9, 2, 6]
heapq.heapify_max(data)  # O(n)
assert data[0] == 9      # O(1) - the root is the largest

heapq.heappush_max(data, 10)          # O(log n) amortized
assert heapq.heappop_max(data) == 10  # O(log n) amortized

assert heapq.heapreplace_max(data, 7) == 9   # O(log n) - pops 9, then pushes 7
assert heapq.heappushpop_max(data, 8) == 8   # O(1) here - 8 is not smaller than the root
assert data[0] == 7
```

### Before Python 3.14

Negating numeric priorities turns the min-heap functions into a max-heap at the same cost.

```python
import heapq

data = [3, 1, 4, 1, 5]
max_heap = [-x for x in data]  # O(n)
heapq.heapify(max_heap)        # O(n)

assert -max_heap[0] == 5               # O(1) peek
assert -heapq.heappop(max_heap) == 5   # O(log n)
heapq.heappush(max_heap, -9)           # O(log n)
assert -max_heap[0] == 9
```

## Common Patterns

### A Bounded Top-k Over a Stream

When items arrive one at a time and only the k largest matter, a min-heap of k items keeps them:
the root is the weakest survivor, and `heappushpop` replaces it only when a new item beats it.

```python
import heapq

k = 3
best = []
for reading in [12, 40, 7, 33, 51, 8, 29, 60]:
    if len(best) < k:
        heapq.heappush(best, reading)      # O(log k)
    else:
        heapq.heappushpop(best, reading)   # O(log k), O(1) if it cannot get in

assert sorted(best, reverse=True) == [60, 51, 40]  # O(k) memory throughout
```

### A Priority Queue of Tasks

```python
import heapq
import itertools

counter = itertools.count()
queue = []

def submit(priority, task):
    heapq.heappush(queue, (priority, next(counter), task))  # O(log n)

def take():
    priority, _, task = heapq.heappop(queue)  # O(log n)
    return task

submit(2, 'write report')
submit(1, 'fix outage')
submit(2, 'answer email')

assert [take() for _ in range(3)] == ['fix outage', 'write report', 'answer email']
```

## Performance Best Practices

✅ **Do**:

- Read `heap[0]` to peek; it is O(1) and needs no pop and push
- Use `heappushpop` or `heapreplace` for a push and a pop together: one call, no resize, and
  `heappushpop` returns an item that cannot enter after one comparison
- Use `nlargest` or `nsmallest` for a few items from a large or streaming input; memory follows k
- Put a counter between the priority and the payload, so ties never compare payloads
- Use `merge` on inputs that are already sorted: it is lazy and holds one item per input

❌ **Avoid**:

- Sorting a whole list to take a few items from it - O(m log m) time and O(m) memory
- Draining a heap to find one item; a heap orders only the root
- Calling `heapify` after every push - O(n) each time against O(log n)
- Passing unsorted inputs to `merge`; the output will not be sorted and nothing says so

## Version Notes

- **Python 3.14+**: Added `heapify_max`, `heappush_max`, `heappop_max`, `heappushpop_max` and
  `heapreplace_max`

## Related Modules

- **[queue](queue.md)** - `PriorityQueue` is a locked `heapq` heap, for producer and consumer threads
- **[sched](sched.md)** - an event scheduler built on a heap of timed events
- **[bisect](bisect.md)** - keeps a list fully sorted instead, with O(n) insertion
- **[sorted()](../builtins/sorted.md)** - O(m log m) when every item, not just the top k, is needed
