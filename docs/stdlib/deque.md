# deque - Double-Ended Queue Complexity

The `deque` (double-ended queue) class from `collections` provides O(1) append and pop from both ends, optimized for queue and stack operations.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `append()` | O(1) | O(1) | Add to right |
| `appendleft()` | O(1) | O(1) | Add to left |
| `pop()` | O(1) | O(1) | Remove from right |
| `popleft()` | O(1) | O(1) | Remove from left |
| Indexing | O(n) | O(1) | O(1) for ends, O(n) for middle due to block structure |
| Insert | O(n) | O(1) | Insert at position |
| Rotate | O(k) | O(1) | Rotate elements |

## Basic Usage

```python
from collections import deque

# Create deque - O(n)
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

# Index access - O(1) for ends, O(n) for middle
value = dq[0]  # O(1) - first element (direct access)
value = dq[-1]  # O(1) - last element (direct access)
value = dq[2]  # O(n) - middle element (requires block traversal)

# Length - O(1)
length = len(dq)  # O(1)
```

### Rotation

```python
from collections import deque

dq = deque([1, 2, 3, 4, 5])

# Rotate right - O(k)
dq.rotate(2)  # O(2) - [4, 5, 1, 2, 3]

# Rotate left - O(k)
dq.rotate(-1)  # O(1) - [5, 1, 2, 3, 4]

# Efficient rotation compared to list
# list: O(n) - must copy all elements
# deque: O(k) - only updates pointers
```

### Extend Operations

```python
from collections import deque

dq = deque([1, 2, 3])

# Extend right - O(n)
dq.extend([4, 5, 6])  # O(3)

# Extend left - O(n)
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

def sliding_window(iterable, window_size):
    """Get sliding window of specified size - O(n)"""
    it = iter(iterable)
    window = deque(maxlen=window_size)
    
    # Fill initial window - O(window_size)
    for _ in range(window_size):
        window.append(next(it))  # O(1)
    
    yield tuple(window)  # O(window_size)
    
    # Slide window - O(1) per iteration
    for item in it:  # O(n)
        window.append(item)  # O(1) - automatically removes oldest
        yield tuple(window)

# Usage - O(n)
data = range(10)
for window in sliding_window(data, 3):
    print(window)
```

### Breadth-First Search

```python
from collections import deque

def bfs(graph, start):
    """BFS using deque - O(V + E)"""
    visited = set()
    queue = deque([start])  # O(1)
    
    while queue:
        vertex = queue.popleft()  # O(1)
        
        if vertex not in visited:
            visited.add(vertex)  # O(1)
            
            # Process neighbors
            for neighbor in graph[vertex]:  # O(E)
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
- Sorting (use list + sorted)

## Version Notes

- **Python 2.x**: deque available in collections
- **Python 3.x**: Same functionality
- **Python 3.2+**: Pickling support added

## Related Modules

- **[list](../builtins/list.md)** - Dynamic array
- **[queue.Queue](queue.md)** - Thread-safe queue
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
- Sorting large deques (convert to list)
