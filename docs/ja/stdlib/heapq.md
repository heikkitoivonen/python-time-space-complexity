---
source_sha: fb99573c6c731125939b7ef5b3be9f797b8f106113c202b686d574b388b20d2e
translated: machine
---

# heapq モジュールの計算量

`heapq` モジュールは、優先度付きキューの操作のためのヒープ実装を提供します。

## 最小ヒープの操作

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `heapify(x)` | O(n) | O(1) | その場での変換 |
| `heappush(heap, item)` | O(log n) | O(1) | ヒープに要素を加える |
| `heappop(heap)` | O(log n) | O(1) | 最小の要素を取り除いて返す |
| `heappushpop(heap, item)` | O(log n) | O(1) | push してから pop（別々に呼ぶより効率的） |
| `heapreplace(heap, item)` | O(log n) | O(1) | pop してから push（別々に呼ぶより効率的） |
| `nlargest(k, iterable)` | O(N log k) | O(k) | N はイテラブルの長さ。k 個のヒープを保つ。k ≥ N なら O(N log N) |
| `nsmallest(k, iterable)` | O(N log k) | O(k) | N はイテラブルの長さ。k 個のヒープを保つ。k ≥ N なら O(N log N) |
| `merge(*iterables)` | O(n log k) | O(k) | n は要素の総数、k はイテラブルの個数 |

## 最大ヒープの操作（Python 3.14+）

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `heapify_max(x)` | O(n) | O(1) | その場での最大ヒープへの変換 |
| `heappush_max(heap, item)` | O(log n) | O(1) | 最大ヒープに要素を加える |
| `heappop_max(heap)` | O(log n) | O(1) | 最大の要素を取り除いて返す |
| `heappushpop_max(heap, item)` | O(log n) | O(1) | push してから最大を pop |
| `heapreplace_max(heap, item)` | O(log n) | O(1) | 最大を pop してから push |

## 空間計算量に関する注記

- `heapify()`: その場で変換するので O(1)
- `heappush()`: O(1) - 既存のリストを変更する
- `heappop()`: O(1) - 既存のリストを変更する
- `nlargest(n, ...)`: n 要素の結果リストに O(n)

## 実装の詳細

### 最小ヒープの性質

```python
import heapq

# Min-heap: parent <= children
heap = [1, 3, 5, 7, 9, 11]
#        0  1  2  3  4   5
# Parent at i: children at 2*i+1, 2*i+2
```

### heapify による変換

```python
import heapq

# Transform list into heap - O(n)
data = [5, 3, 7, 1, 9]
heapq.heapify(data)  # In-place, O(n)
# data is now [1, 3, 7, 5, 9] (heap property satisfied)
```

### 繰り返しの操作

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

## よくある使い方

### 優先度付きキュー

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

### 上位 k 個の要素

```python
import heapq

# Find k largest elements - O(n log k)
data = [3, 1, 4, 1, 5, 9, 2, 6]
top_3 = heapq.nlargest(3, data)  # [9, 6, 5]
bottom_3 = heapq.nsmallest(3, data)  # [1, 1, 2]
```

### 整列済み列のマージ

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

## 応用: 独自の優先度

### タプルを使う

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

### functools とデータクラスを使う

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

## 性能の比較

### 上位 k 個の問題

```python
import heapq

data = list(range(1000000))

# Bad: Full sort - O(n log n)
top_10 = sorted(data, reverse=True)[:10]  # Sorts all!

# Good: Heap nlargest - O(n log k), k=10
top_10 = heapq.nlargest(10, data)  # Only sorts top 10

# For small k, nlargest much faster than sort
```

### 優先度付きキューのシミュレーション

```python
import heapq
from collections import deque

# Simulated queue with priorities
heap_queue = []  # heapq-based
fifo_queue = deque()  # Simple FIFO

# Add task
heapq.heappush(heap_queue, (priority, task))  # O(log n)
fifo_queue.append(task)  # O(1)

# Get task with priority (smallest priority value first)
task = heapq.heappop(heap_queue)  # O(log n)
task = fifo_queue.popleft()  # O(1), gets oldest
```

## 実装に関する注記

### CPython
配列に基づく二分ヒープを使っており、高度に最適化されている。

### PyPy
JIT コンパイルにより、繰り返される操作がさらに最適化される。

## 最大ヒープの使い方（Python 3.14+）

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

### 最大ヒープによる優先度付きキュー

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

### 3.14 より前での最大ヒープの回避策

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

## バージョン別の注記

- **Python 3.14+**: 最大ヒープの関数が標準で追加された
- **すべてのバージョン**: 最小ヒープの関数は利用できる

## 関連するドキュメント

- [collections モジュール](collections.md)
- [bisect モジュール](bisect.md)
- [Python 3.14](../versions/py314.md)
- [sorted() 関数](../builtins/sorted.md)
