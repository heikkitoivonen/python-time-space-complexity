---
source_sha: c1b5f1ee5978dde99e9799f5f90d36c53c47949cd101d739d756649cb9c23ab7
translated: machine
---

# Heapq 模块的复杂度

`heapq` 模块提供堆的实现，用于优先队列操作。

## 最小堆操作

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `heapify(x)` | O(n) | O(1) | 原地转换 |
| `heappush(heap, item)` | O(log n) | O(1) | 向堆中添加元素 |
| `heappop(heap)` | O(log n) | O(1) | 移除并返回最小元素 |
| `heappushpop(heap, item)` | O(log n) | O(1) | 先入堆再出堆（比分别调用更高效） |
| `heapreplace(heap, item)` | O(log n) | O(1) | 先出堆再入堆（比分别调用更高效） |
| `nlargest(k, iterable)` | O(N log k) | O(k) | N = 可迭代对象长度；维护 k 个元素的堆；若 k ≥ N 则为 O(N log N) |
| `nsmallest(k, iterable)` | O(N log k) | O(k) | N = 可迭代对象长度；维护 k 个元素的堆；若 k ≥ N 则为 O(N log N) |
| `merge(*iterables)` | O(n log k) | O(k) | n = 元素总数，k = 可迭代对象的个数 |

## 最大堆操作（Python 3.14+）

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `heapify_max(x)` | O(n) | O(1) | 原地转换为最大堆 |
| `heappush_max(heap, item)` | O(log n) | O(1) | 向最大堆添加元素 |
| `heappop_max(heap)` | O(log n) | O(1) | 移除并返回最大元素 |
| `heappushpop_max(heap, item)` | O(log n) | O(1) | 先入堆再弹出最大值 |
| `heapreplace_max(heap, item)` | O(log n) | O(1) | 先弹出最大值再入堆 |

## 空间复杂度说明

- `heapify()`：原地转换，O(1)
- `heappush()`：O(1) —— 修改已有列表
- `heappop()`：O(1) —— 修改已有列表
- `nlargest(k, ...)`：结果列表含 k 个元素，占 O(k)

## 实现细节

### 最小堆性质

```python
import heapq

# Min-heap: parent <= children
heap = [1, 3, 5, 7, 9, 11]
#        0  1  2  3  4   5
# Parent at i: children at 2*i+1, 2*i+2
```

### heapify 转换

```python
import heapq

# Transform list into heap - O(n)
data = [5, 3, 7, 1, 9]
heapq.heapify(data)  # In-place, O(n)
# data is now [1, 3, 7, 5, 9] (heap property satisfied)
```

### 迭代式操作

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

## 常见用例

### 优先队列

```python
import heapq

# Simple priority queue
tasks = [(3, 'low'), (1, 'high'), (2, 'medium')]
heapq.heapify(tasks)  # O(n)

while tasks:
    priority, task = heapq.heappop(tasks)  # O(log n) each, O(n log n) to drain
    print(f"Execute {task}")  # Executes high, medium, low

# Output:
# Execute high
# Execute medium
# Execute low
```

### 前 K 个元素

```python
import heapq

# Find k largest elements - O(n log k)
data = [3, 1, 4, 1, 5, 9, 2, 6]
top_3 = heapq.nlargest(3, data)  # [9, 6, 5]
bottom_3 = heapq.nsmallest(3, data)  # [1, 1, 2]
```

### 合并有序序列

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

## 进阶：自定义优先级

### 使用元组

```python
import heapq

# Priority queue with custom objects
heap = []
heapq.heappush(heap, (3, 'low-priority-task'))    # O(log n)
heapq.heappush(heap, (1, 'high-priority-task'))   # O(log n)
heapq.heappush(heap, (2, 'medium-priority-task'))  # O(log n)

# Tasks ordered by priority (first element of tuple)
# Tuples compare element by element: equal priorities fall through to the
# next field, so a tie costs more to order than a plain int key would
while heap:
    priority, task = heapq.heappop(heap)  # O(log n)
    print(task)
```

### 结合 functools 使用数据类

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
heapq.heapify(heap)  # O(n), but each comparison is a Python __lt__ call

while heap:
    task = heapq.heappop(heap)  # O(log n)
    print(f"{task.priority}: {task.name}")
```

## 性能对比

### Top-K 问题

```python
import heapq

data = list(range(1000000))

# Bad: Full sort - O(n log n)
top_10 = sorted(data, reverse=True)[:10]  # Sorts all!

# Good: Heap nlargest - O(n log k), k=10
top_10 = heapq.nlargest(10, data)  # Only sorts top 10

# For small k, nlargest much faster than sort
```

### 优先队列 Simulation

```python
import heapq
from collections import deque

# Simulated queue with priorities
heap_queue = []  # heapq-based
fifo_queue = deque()  # Simple FIFO

# Add task
priority, task = 1, 'render'
heapq.heappush(heap_queue, (priority, task))  # O(log n)
fifo_queue.append(task)  # O(1)

# Get task with priority (smallest priority value first)
task = heapq.heappop(heap_queue)  # O(log n)
task = fifo_queue.popleft()  # O(1), gets oldest
```

## 实现说明

### CPython
使用基于数组的二叉堆，高度优化。

### PyPy
JIT 编译为重复操作提供额外优化。

## 最大堆的用法（Python 3.14+）

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

### 基于最大堆的优先队列

```python
import heapq

# Priority queue returning highest priority first
tasks = [(1, "low"), (5, "urgent"), (3, "medium")]
heapq.heapify_max(tasks)  # O(n)

while tasks:
    priority, task = heapq.heappop_max(tasks)  # O(log n) each, O(n log n) to drain
    print(f"{priority}: {task}")
# Output: 5: urgent, 3: medium, 1: low
```

### 3.14 之前实现最大堆的变通方法

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

## 版本说明

- **Python 3.14+**：新增原生的最大堆函数
- **所有版本**：最小堆函数均可用

## 相关文档

- [Collections 模块](collections.md)
- [Bisect 模块](bisect.md)
- [Python 3.14](../versions/py314.md)
- [内置的 sorted()](../builtins/sorted.md)
