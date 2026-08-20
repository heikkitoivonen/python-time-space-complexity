---
source_sha: 713f953a7a1fceb9522785db68efc95213c93b61a90f241420e31ae85e2c432a
translated: machine
---

# Bisect 模块的复杂度

`bisect` 模块为有序列表提供二分查找操作。

## 操作

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `bisect_left(a, x)` | O(log n) | O(1) | 查找最左侧位置 |
| `bisect_right(a, x)` | O(log n) | O(1) | 查找最右侧位置 |
| `bisect(a, x)` | O(log n) | O(1) | bisect_right 的别名 |
| `insort_left(a, x)` | O(n) | O(1) | O(log n) 查找 + O(n) 插入（原地移动元素） |
| `insort_right(a, x)` | O(n) | O(1) | O(log n) 查找 + O(n) 插入（原地移动元素） |
| `insort(a, x)` | O(n) | O(1) | insort_right 的别名 |

## 空间复杂度

- 二分查找操作：额外空间 O(1)
- 插入操作：额外空间 O(1)（在已有列表内部移动元素）

## 实现细节

### 二分查找的前提

```python
import bisect

# Must be sorted!
sorted_list = [1, 3, 3, 3, 5, 7, 9]

# bisect_left: leftmost insertion point
pos = bisect.bisect_left(sorted_list, 3)  # pos = 1
# Insert here to keep list sorted (before all 3's)

# bisect_right: rightmost insertion point
pos = bisect.bisect_right(sorted_list, 3)  # pos = 4
# Insert here to keep list sorted (after all 3's)
```

### 查找元素

```python
import bisect

sorted_list = [1, 3, 5, 7, 9]

# Check if element exists
def exists(sorted_list, x):
    pos = bisect.bisect_left(sorted_list, x)
    return pos < len(sorted_list) and sorted_list[pos] == x

exists(sorted_list, 5)  # True - O(log n)
exists(sorted_list, 4)  # False - O(log n)
```

## 常见用例

### 保序插入

```python
import bisect

sorted_list = [1, 3, 5, 7]

# Insert while maintaining order - O(n) overall
# (O(log n) search + O(n) shift)
bisect.insort(sorted_list, 4)  # [1, 3, 4, 5, 7]

# Better for many insertions: use list, then sort
# Multiple inserts: O(n log n) with sort
# vs O(n²) with repeated insort
```

### 查找区间

```python
import bisect

# Find all equal elements
sorted_list = [1, 3, 3, 3, 5, 7, 9]
target = 3

left = bisect.bisect_left(sorted_list, target)
right = bisect.bisect_right(sorted_list, target)

equals = sorted_list[left:right]  # All 3's - O(log n) search
```

### 查找区间的插入位置

```python
import bisect

# Find where range [a, b] fits in sorted list
sorted_list = [1, 5, 10, 15, 20]
target_range = (7, 12)

# Position to insert start of range
start_pos = bisect.bisect_right(sorted_list, target_range[0])

# Position to insert end of range
end_pos = bisect.bisect_left(sorted_list, target_range[1])

print(f"Insert range {target_range} at positions {start_pos}-{end_pos}")
```

## 性能对比

### 在有序数据中查找

```python
import bisect

data = sorted(range(1000000))

# Bad: Linear search - O(n)
found = 500000 in data  # Scans linearly

# Good: Binary search - O(log n)
pos = bisect.bisect_left(data, 500000)  # Much faster!
found = pos < len(data) and data[pos] == 500000
```

### 维护有序列表

```python
import bisect

# Many insertions scenario
sorted_list = [1, 3, 5, 7, 9]

# Bad: Multiple insort - O(n²)
for item in [2, 4, 6, 8]:
    bisect.insort(sorted_list, item)  # O(n) each

# Better: Collect, sort once - O(n log n)
sorted_list.extend([2, 4, 6, 8])
sorted_list.sort()  # Single O(n log n) operation
```

## 详细示例

### 成绩区间

```python
import bisect

# Map scores to grades
grade_breaks = [60, 70, 80, 90]
grades = ['F', 'D', 'C', 'B', 'A']

def get_grade(score):
    i = bisect.bisect(grade_breaks, score)
    return grades[i]

print(get_grade(85))  # 'B' - O(log n)
print(get_grade(95))  # 'A' - O(log n)
```

### 时间戳查找

```python
import bisect
from datetime import datetime, timedelta

# Find events in a time range
events = [
    (datetime(2024, 1, 1, 10), 'event1'),
    (datetime(2024, 1, 1, 12), 'event2'),
    (datetime(2024, 1, 1, 15), 'event3'),
    (datetime(2024, 1, 1, 18), 'event4'),
]

timestamps = [e[0] for e in events]

# Find events after specific time
target = datetime(2024, 1, 1, 14)
idx = bisect.bisect_right(timestamps, target)
later_events = events[idx:]  # O(log n) search

print(later_events)  # Events at 3pm and 6pm
```

## 进阶：自定义 key 函数

```python
import bisect
from bisect import bisect_right

# Custom objects - compare by second element
data = [('a', 1), ('b', 3), ('c', 5)]
keys = [x[1] for x in data]

# Find position for ('d', 4)
pos = bisect_right(keys, 4)
data.insert(pos, ('d', 4))
```

## 重要提示

!!! warning "数据必须有序"
    输入列表**必须**已排序，二分查找才能正确工作。
    
    ```python
    # Wrong: Data not sorted
    unsorted = [3, 1, 4, 1, 5]
    pos = bisect.bisect(unsorted, 2)  # Incorrect result!
    ```

!!! tip "均摊效率"
    当插入次数很多时：

    - 多次调用 `insort()`：总体 O(n²)
    - 先收集再调用一次 `sort()`：总体 O(n log n)
    
    根据你的访问模式来选择。

## 相关文档

- [Heapq 模块](heapq.md)
- [Collections 模块](collections.md)
- [列表方法](../builtins/list.md)
