# Standard Library Complexity

The Python standard library provides highly optimized data structures and algorithms for common tasks.

## Core Collections

- **[Collections](collections.md)** - `deque`, `namedtuple`, `defaultdict`, `OrderedDict`, `ChainMap`, `Counter`
- **[Itertools](itertools.md)** - Efficient looping tools and iterators
- **[Heapq](heapq.md)** - Heap queue operations
- **[Bisect](bisect.md)** - Binary search and insertion

## Functional & Utilities

- **[Functools](functools.md)** - Higher-order functions and memoization
- **[JSON](json.md)** - JSON serialization and parsing

## Search & Sort

| Module | Purpose | Time |
|--------|---------|------|
| `bisect` | Binary search in sorted lists | O(log n) |
| `heapq` | Heap operations | O(log n) |
| `sorted()` | Sort any iterable | O(n log n) |

## Frequently Used

### Collections Module

```python
from collections import deque, defaultdict, Counter

# deque: Fast append/prepend
d = deque([1, 2, 3])
d.appendleft(0)  # O(1)

# defaultdict: Auto-default values
d = defaultdict(list)
d[key].append(value)  # Key created if missing

# Counter: Count items
c = Counter(['a', 'a', 'b'])
c['a']  # Returns 2
```

### Heapq Module

```python
import heapq

# Min heap operations
heap = [3, 1, 4, 1, 5]
heapq.heapify(heap)  # O(n)
heapq.heappop(heap)  # O(log n)
heapq.heappush(heap, 2)  # O(log n)
```

### Bisect Module

```python
import bisect

# Binary search in sorted lists
arr = [1, 3, 3, 3, 5]
bisect.bisect_left(arr, 3)  # O(log n)
bisect.insort(arr, 4)  # O(n) - must shift
```

## Data Structure Quick Reference

| Type | Append | Prepend | Access | Contains |
|------|--------|---------|--------|----------|
| list | O(1)* | O(n) | O(1) | O(n) |
| deque | O(1) | O(1) | O(n) | O(n) |
| heapq | O(log n) | - | O(1) min | O(n) |
| set | - | - | - | O(1) |
| dict | - | - | O(1) | O(1) |

## Version Highlights

- **Python 3.7+**: `dict` insertion order preserved
- **Python 3.8+**: Assignment expressions (walrus operator)
- **Python 3.10+**: Pattern matching with dataclasses

## See Also

- [Built-in Types](../builtins/index.md)
- [Implementations](../implementations/index.md)
