# deque - Double-Ended Queue Complexity

`collections.deque` stores its items in a doubly linked chain of fixed-size
blocks, so adding or removing at either end never moves the other items.
That is the trade: O(1) at both ends, but reaching an item in the middle
means walking blocks from the nearer end.

Size variables: `n` is `len(d)`, `k` the number of items added, moved or
repeated, `i`, `start` and `stop` positions counted from the left (a negative
value is normalised first; `insert()`, `start` and `stop` clamp an
out-of-range value, indexing raises `IndexError`), and `m` the length of the
other operand. Bounds count each item comparison as O(1).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `deque(iterable, maxlen)` | O(k) | O(k) | k = items in the iterable; a bounded deque never holds more than `maxlen` of them, yet still consumes every one |
| `d.append(x)` / `d.appendleft(x)` | O(1) | O(1) | On a full bounded deque the item at the opposite end is discarded |
| `d.pop()` / `d.popleft()` | O(1) | O(1) | `IndexError` when empty |
| `d[i]` / `d[i] = x` | O(min(i, n - i)) | O(1) | O(1) at the ends; the middle walks blocks from the nearer end, so it is O(n). No slicing |
| `del d[i]` / `d.insert(i, x)` | O(min(i, n - i)) | O(1) | Rotates the position to an end and back. `insert()` on a full bounded deque raises `IndexError` rather than discarding |
| `d.remove(x)` | O(n) | O(1) | Scans from the left, then deletes as `del d[i]` does |
| `d.extend(iterable)` / `d.extendleft(iterable)` | O(k) | O(k) | k = items in the iterable; `extendleft()` reverses their order. A bounded deque keeps the last `maxlen` and still consumes every item |
| `d += iterable` | O(k) | O(k) | The same as `extend()` |
| `d.rotate(steps)` | O(k) | O(1) | k = min(steps mod n, n - steps mod n): rotating by 1, -1 or nearly the whole length is O(1) |
| `d.reverse()` | O(n) | O(1) | In place |
| `d.clear()` | O(n) | O(1) | Releases every item |
| `d.copy()` / `copy.copy(d)` | O(n) | O(n) | Shallow; keeps `maxlen` |
| `pickle.dumps(d)` / `copy.deepcopy(d)` | O(n) + item cost | O(n) + item cost | Each item is pickled or deep-copied in turn; keeps `maxlen` |
| `d.count(x)` | O(n) | O(1) | Compares every item |
| `x in d` | O(n) | O(1) | Stops at the first match |
| `d.index(x, start, stop)` | O(stop) | O(1) | Skips to `start`, then compares until the first match or `stop` |
| `len(d)` / `d.maxlen` | O(1) | O(1) | `maxlen` is read-only; `None` when unbounded |
| `iter(d)` / `reversed(d)` | O(1) to create, O(n) to exhaust | O(1) | Adding, removing or rotating items during iteration raises `RuntimeError`; `d[i] = x` and `reverse()` do not |
| `d == e` / `d < e` | O(min(n, m)) | O(1) | Only against another deque, so `deque([1]) == [1]` is `False`; `==` on unequal lengths returns at once. Deques are unhashable |
| `d + e` | O(n + m) | O(n + m) | A new deque with `d`'s `maxlen`; `e` must be a deque |
| `d * k` / `d *= k` | O(n * k) | O(n * k) | k = repeat count. A bound caps both at O(n + maxlen). For k <= 0 both cost O(n): `d *= k` empties `d`, `d * k` copies it first |

## Basic Usage

```python
from collections import deque

# Create deque - O(k)
dq = deque([1, 2, 3, 4, 5])  # O(5)

# Add to right - O(1)
dq.append(6)  # O(1)

# Add to left - O(1)
dq.appendleft(0)  # O(1)

# Remove from right - O(1)
value = dq.pop()  # O(1) - removes 6

# Remove from left - O(1)
value = dq.popleft()  # O(1) - removes 0
```

## Queue Operations

### FIFO (First In First Out)

```python
from collections import deque

# Create queue - O(1)
queue = deque()

# Enqueue - O(1)
queue.append(1)  # O(1)
queue.append(2)  # O(1)
queue.append(3)  # O(1)

# Dequeue - O(1)
item = queue.popleft()  # O(1) - removes 1
item = queue.popleft()  # O(1) - removes 2
item = queue.popleft()  # O(1) - removes 3
```

### Stack Operations (LIFO)

```python
from collections import deque

# Create stack - O(1)
stack = deque()

# Push - O(1)
stack.append(1)  # O(1)
stack.append(2)  # O(1)
stack.append(3)  # O(1)

# Pop - O(1)
item = stack.pop()  # O(1) - removes 3
item = stack.pop()  # O(1) - removes 2
item = stack.pop()  # O(1) - removes 1
```

## Deque Operations

### Access

```python
from collections import deque

dq = deque([1, 2, 3, 4, 5])

# Index access - O(1) at the ends, O(min(i, n - i)) elsewhere
value = dq[0]  # O(1) - first element (direct access)
value = dq[-1]  # O(1) - last element (direct access)
value = dq[2]  # O(min(i, n - i)) - walks blocks from the nearer end

# Length - O(1)
length = len(dq)  # O(1)
```

A deque has no slices: `dq[1:3]` raises `TypeError`. Use
`itertools.islice(dq, 1, 3)`, which iterates from the left and so costs
O(max(start, stop)), not O(stop - start).

### Rotation

```python
from collections import deque

dq = deque([1, 2, 3, 4, 5])

# Rotate right - O(k)
dq.rotate(2)  # O(2) - [4, 5, 1, 2, 3]

# Rotate left - O(k)
dq.rotate(-1)  # O(1) - [5, 1, 2, 3, 4]

# Efficient rotation compared to list
# list: O(n) - lst[-k:] + lst[:-k] copies every element
# deque: O(k) - moves k pointers between the end blocks
```

### Extend Operations

```python
from collections import deque

dq = deque([1, 2, 3])

# Extend right - O(k), k = items added
dq.extend([4, 5, 6])  # O(3)

# Extend left - O(k), reverses the items' order
dq.extendleft([0, -1])  # O(2)

# Result: [-1, 0, 1, 2, 3, 4, 5, 6]
```

## Maxlen Parameter

```python
from collections import deque

# Create with max length - O(1)
dq = deque(maxlen=3)

# Append - O(1)
dq.append(1)  # [1]
dq.append(2)  # [1, 2]
dq.append(3)  # [1, 2, 3]
dq.append(4)  # [2, 3, 4] - oldest removed

# Useful for sliding windows
```

`insert()` is the one way of adding that does not discard: on a full
bounded deque it raises `IndexError`.

## Performance Comparison

### List vs Deque

```python
from collections import deque
import time

# List - O(n) popleft (must shift all elements)
lst = list(range(1000000))
start = time.time()
for _ in range(1000):
    lst.pop(0)  # O(n)
list_time = time.time() - start

# Deque - O(1) popleft
dq = deque(range(1000000))
start = time.time()
for _ in range(1000):
    dq.popleft()  # O(1)
deque_time = time.time() - start

# deque is much faster for queue operations
```

## Common Patterns

### Sliding Window

```python
from collections import deque
from itertools import islice

def sliding_window(iterable, window_size):
    """Yield each window as a tuple - O(n * window_size) for n items"""
    it = iter(iterable)

    # Fill initial window - O(window_size)
    window = deque(islice(it, window_size), maxlen=window_size)
    if len(window) < window_size:
        return

    yield tuple(window)  # O(window_size)

    # Slide window - O(1) to append, O(window_size) to snapshot the tuple
    for item in it:  # n - window_size iterations
        window.append(item)  # O(1) - automatically removes oldest
        yield tuple(window)  # O(window_size)

# Usage - O(n * window_size)
data = range(10)
for window in sliding_window(data, 3):
    print(window)
```

The deque slides in O(1); the tuple handed out each step is what costs
O(window_size). Yield the deque itself when the caller only needs to look at
the window before the next step.

### Breadth-First Search

```python
from collections import deque

def bfs(graph, start):
    """BFS using deque - O(V + E) time and space"""
    visited = set()
    queue = deque([start])  # O(1)

    while queue:
        vertex = queue.popleft()  # O(1)

        if vertex not in visited:
            visited.add(vertex)  # O(1)

            # Process neighbors - O(degree), O(E) over the whole search
            for neighbor in graph[vertex]:
                if neighbor not in visited:
                    queue.append(neighbor)  # O(1)

    return visited
```

## When to Use Deque

### Good For:
- Queue implementations (O(1) both ends)
- Stack implementations (O(1) both ends)
- Sliding windows
- BFS algorithms
- Rotating sequences

### Not Good For:
- Random access (use list)
- Searching (use set or dict)
- Sorting (there is no `sort()`; `sorted(dq)` returns a list)

## Version Notes

- **Python 3.1+**: `maxlen` attribute added
- **Python 3.2+**: `count()`, `reverse()` and `+=` added
- **Python 3.5+**: `copy()`, `index()`, `insert()` and the `+`, `*`, `*=` operators added
- **Python 3.9+**: `deque[int]` generic alias
- **All versions**: pickling and `copy.copy()` supported

## Related Modules

- **[list](../builtins/list.md)** - Dynamic array
- **[queue.Queue](queue.md)** - Blocking queue for threads, built on a deque
- **[heapq](heapq.md)** - Priority queue

## Best Practices

✅ **Do**:

- Use for queue/stack (O(1) both ends)
- Use for sliding windows
- Use for BFS algorithms
- Set maxlen for bounded collections

❌ **Avoid**:

- Random access (use list)
- When order of operation doesn't matter (use set)
- Sorting (`sorted(dq)` builds a list anyway; keep a list if you sort often)
