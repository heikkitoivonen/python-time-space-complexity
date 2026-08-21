---
source_sha: 699f54d0f15380f0acf2cc37e53cc5f55cb222c850ade1649086deaeb841be2c
translated: machine
---

# 标准库的复杂度

Python 标准库为常见任务提供了高度优化的数据结构和算法。

## 核心容器

- **[Collections](collections.md)** - `deque`, `namedtuple`, `defaultdict`, `OrderedDict`, `ChainMap`, `Counter`
- **[Itertools](itertools.md)** - 高效的循环工具与迭代器
- **[Heapq](heapq.md)** - 堆队列操作
- **[Bisect](bisect.md)** - 二分查找与插入

## 函数式与实用工具

- **[Functools](functools.md)** - 高阶函数与记忆化
- **[JSON](json.md)** - JSON 序列化与解析

## 查找与排序

| 模块 | 用途 | 时间 |
|--------|---------|------|
| `bisect` | 在有序列表中二分查找 | O(log n) |
| `heapq` | 堆操作 | O(log n) |
| `sorted()` | 对任意可迭代对象排序 | O(n log n) |

## 常用模块

### Collections 模块

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

### Heapq 模块

```python
import heapq

# Min heap operations
heap = [3, 1, 4, 1, 5]
heapq.heapify(heap)  # O(n)
heapq.heappop(heap)  # O(log n)
heapq.heappush(heap, 2)  # O(log n)
```

### Bisect 模块

```python
import bisect

# Binary search in sorted lists
arr = [1, 3, 3, 3, 5]
bisect.bisect_left(arr, 3)  # O(log n)
bisect.insort(arr, 4)  # O(n) - must shift
```

## 数据结构速查

| 类型 | 尾部追加 | 头部插入 | 访问 | 成员检测 |
|------|--------|---------|--------|----------|
| list | O(1)* | O(n) | O(1) | O(n) |
| deque | O(1) | O(1) | O(n) | O(n) |
| heapq | O(log n) | - | O(1) 取最小 | O(n) |
| set | - | - | - | O(1) |
| dict | - | - | O(1) | O(1) |

## 版本要点

- **Python 3.7+**：`dict` 保留插入顺序
- **Python 3.8+**：赋值表达式（海象运算符）
- **Python 3.10+**：支持对数据类进行模式匹配

## 另请参阅

- [内置](../builtins/index.md)
- [实现](../implementations/index.md)
