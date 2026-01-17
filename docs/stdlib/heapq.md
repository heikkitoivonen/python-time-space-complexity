# Heapq Module Complexity

The `heapq` module provides heap implementations for priority queue operations.

## Min-Heap Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `heapify(x)` | O(n) | O(1) | In-place transformation |
| `heappush(heap, item)` | O(log n) | O(1) | Add item to heap |
| `heappop(heap)` | O(log n) | O(1) | Remove and return min item |
| `heappushpop(heap, item)` | O(log n) | O(1) | Push then pop (more efficient than separate calls) |
| `heapreplace(heap, item)` | O(log n) | O(1) | Pop then push (more efficient than separate calls) |
| `nlargest(n, iterable)` | O(k log n) | O(n) | k = iterable length, maintains heap of n items |
| `nsmallest(n, iterable)` | O(k log n) | O(n) | k = iterable length, maintains heap of n items |
| `merge(*iterables)` | O(n log k) | O(k) | n = total items, k = count of iterables |

## Max-Heap Operations (Python 3.14+)

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `heapify_max(x)` | O(n) | O(1) | In-place max-heap transformation |
| `heappush_max(heap, item)` | O(log n) | O(1) | Add item to max-heap |
| `heappop_max(heap)` | O(log n) | O(1) | Remove and return max item |
| `heappushpop_max(heap, item)` | O(log n) | O(1) | Push then pop max |
| `heapreplace_max(heap, item)` | O(log n) | O(1) | Pop max then push |

## Space Complexity Notes

- `heapify()`: O(1) in-place transformation
- `heappush()`: O(1) - modifies existing list
- `heappop()`: O(1) - modifies existing list
- `nlargest(n, ...)`: O(n) for result list of n items

## Implementation Details

### Min-Heap Property

```python
import heapq

# Min-heap: parent <= children
heap = [1, 3, 5, 7, 9, 11]
#        0  1  2  3  4   5
# Parent at i: children at 2*i+1, 2*i+2
```

### Heapify Transform

```python
import heapq

# Transform list into heap - O(n)
data = [5, 3, 7, 1, 9]
heapq.heapify(data)  # In-place, O(n)
# data is now [1, 3, 7, 5, 9] (heap property satisfied)
```

### Iterative Operations

```python
import heapq

heap = [5, 3, 7]
heapq.heapify(heap)  # [3, 5, 7]

# Add items
heapq.heappush(heap, 1)  # O(log n), now [1, 3, 7, 5]
heapq.heappush(heap, 6)  # O(log n)

# Remove min
min_val = heapq.heappop(heap)  # O(log n), returns 1

# Peek at min without removing
print(heap[0])  # O(1) - minimum is always at root
```

## Common Use Cases

### Priority Queue

```python
import heapq

# Simple priority queue
tasks = [(3, 'low'), (1, 'high'), (2, 'medium')]
heapq.heapify(tasks)

while tasks:
    priority, task = heapq.heappop(tasks)
    print(f"Execute {task}")  # Executes high, medium, low

# Output:
# Execute high
# Execute medium
# Execute low
```

### Top-K Elements

```python
import heapq

# Find k largest elements - O(n log k)
data = [3, 1, 4, 1, 5, 9, 2, 6]
top_3 = heapq.nlargest(3, data)  # [9, 6, 5]
bottom_3 = heapq.nsmallest(3, data)  # [1, 1, 2]
```

### Merge Sorted Sequences

```python
import heapq

# Merge multiple sorted iterables efficiently
seq1 = [1, 3, 5]
seq2 = [2, 4, 6]
seq3 = [1.5, 2.5, 3.5]

merged = heapq.merge(seq1, seq2, seq3)
# merged is iterator that yields in order
list(merged)  # [1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6]
```

## Advanced: Custom Priority

### Using Tuples

```python
import heapq

# Priority queue with custom objects
heap = []
heapq.heappush(heap, (3, 'low-priority-task'))
heapq.heappush(heap, (1, 'high-priority-task'))
heapq.heappush(heap, (2, 'medium-priority-task'))

# Tasks ordered by priority (first element of tuple)
while heap:
    priority, task = heapq.heappop(heap)
    print(task)
```

### Using Dataclass with functools

```python
import heapq
from dataclasses import dataclass
from functools import total_ordering

@total_ordering
@dataclass
class Task:
    priority: int
    name: str
    
    def __lt__(self, other):
        return self.priority < other.priority

heap = [
    Task(3, 'low'),
    Task(1, 'high'),
    Task(2, 'medium')
]
heapq.heapify(heap)

while heap:
    task = heapq.heappop(heap)
    print(f"{task.priority}: {task.name}")
```

## Performance Comparison

### Top-K Problem

```python
import heapq

data = list(range(1000000))

# Bad: Full sort - O(n log n)
top_10 = sorted(data, reverse=True)[:10]  # Sorts all!

# Good: Heap nlargest - O(n log k), k=10
top_10 = heapq.nlargest(10, data)  # Only sorts top 10

# For small k, nlargest much faster than sort
```

### Priority Queue Simulation

```python
import heapq
from collections import deque

# Simulated queue with priorities
heap_queue = []  # heapq-based
fifo_queue = deque()  # Simple FIFO

# Add task
heapq.heappush(heap_queue, (priority, task))  # O(log n)
fifo_queue.append(task)  # O(1)

# Get task with priority
task = heapq.heappop(heap_queue)  # O(log n), gets highest priority
task = fifo_queue.popleft()  # O(1), gets oldest
```

## Implementation Notes

### CPython
Uses array-based binary heap, highly optimized.

### PyPy
JIT compilation provides additional optimization for repeated operations.

## Max-Heap Usage (Python 3.14+)

```python
import heapq

# Create a max-heap
data = [3, 1, 4, 1, 5, 9, 2, 6]
heapq.heapify_max(data)  # O(n)

# Peek at max
print(data[0])  # 9 - maximum is always at root

# Add and remove from max-heap
heapq.heappush_max(data, 10)      # O(log n)
max_val = heapq.heappop_max(data)  # O(log n), returns 10

# Efficient combined operations
heapq.heapreplace_max(data, 7)    # O(log n) - pop max, push 7
heapq.heappushpop_max(data, 8)    # O(log n) - push 8, pop max
```

### Max-Heap Priority Queue

```python
import heapq

# Priority queue returning highest priority first
tasks = [(1, "low"), (5, "urgent"), (3, "medium")]
heapq.heapify_max(tasks)

while tasks:
    priority, task = heapq.heappop_max(tasks)
    print(f"{priority}: {task}")
# Output: 5: urgent, 3: medium, 1: low
```

### Pre-3.14 Max-Heap Workaround

```python
import heapq

# Before 3.14: Negate values for max-heap behavior
data = [3, 1, 4, 1, 5]
max_heap = [-x for x in data]  # O(n)
heapq.heapify(max_heap)        # O(n)

# Get max
max_val = -heapq.heappop(max_heap)  # Negate back

# Python 3.14+: Use native max-heap functions instead
```

## Version Notes

- **Python 3.14+**: Native max-heap functions added
- **All versions**: Min-heap functions available

## Related Documentation

- [Collections Module](collections.md)
- [Bisect Module](bisect.md)
- [Python 3.14](../versions/py314.md)
- [Sorted Builtin](../builtins/index.md)
