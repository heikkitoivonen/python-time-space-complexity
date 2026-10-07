---
source_sha: a94d3e8a9450b59cb245eb0f1ed57d4adf9f9336e3b33dadbbff5a31abbd09b2
translated: machine
---

# bisect 模块复杂度

`bisect` 模块在调用方保持有序的序列中查找位置。它从不排序，也从不检查顺序：每次查找都把给定的范围
减半，每一步读取一个元素，额外内存为常数。插入函数把这种查找与序列自身的 `insert()` 组合起来，
对列表而言，开销在于插入，而不在于查找。

`n` 是序列的长度。查找的上界按探测次数计算：每次探测包括读取一个元素、给定键函数时调用一次 `key`，
以及一次 `<` 比较，均按 O(1) 计价。做更多工作的键函数或比较会按其开销放大查找的成本。索引与列表
一样是 O(1)。这里两个元素相等是指二者都不 `<` 对方；给定 `key` 时比较的是键。

## 复杂度参考

### 查找

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `bisect.bisect_left(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | 位于与 `x` 相等的元素段之前的位置；`key` 作用于每个被探测的元素，从不作用于 `x` |
| `bisect.bisect_right(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | 位于与 `x` 相等的元素段之后的位置 |
| `bisect.bisect(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | 与 `bisect_right` 是同一个函数 |

### 插入

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `bisect.insort_left(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | O(log n) 查找，然后调用 `a.insert()`，对列表而言会移动其后的元素；`key` 作用于 `x` 一次 |
| `bisect.insort_right(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | 插入到与 `x` 相等的元素段之后 |
| `bisect.insort(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | 与 `insort_right` 是同一个函数 |

## 在有序列表中查找

### 左与右

两种查找的区别只在于落在相等元素段的哪一侧：`bisect_left` 落在段之前，`bisect_right` 落在段之后。
两者都仍然把范围减半，因此查找一段重复值与其他查找一样是 O(log n)，两者合用可以确定这一段的两端，
无论它有多长。

```python
import bisect

values = [1, 3, 3, 3, 5, 7, 9]

left = bisect.bisect_left(values, 3)    # O(log n)
right = bisect.bisect_right(values, 3)  # O(log n)
assert (left, right) == (1, 4)
assert values[left:right] == [3, 3, 3]
assert right - left == 3                # occurrences counted without a scan

def contains(sorted_list, x):
    i = bisect.bisect_left(sorted_list, x)  # O(log n), against O(n) for `x in sorted_list`
    return i < len(sorted_list) and sorted_list[i] == x

assert contains(values, 5)
assert not contains(values, 4)
```

### 用 lo 和 hi 缩小范围

`lo` 和 `hi` 限定被查找的切片，查找的开销是 O(log(hi - lo))，与序列长度无关。但 `insort`
仍要为整个列表的插入付出开销。负的 `lo` 会引发 `ValueError`。

```python
import bisect

values = list(range(0, 1_000, 2))

assert bisect.bisect_left(values, 100, lo=40, hi=60) == 50  # O(log 20)

try:
    bisect.bisect_left(values, 100, lo=-1)
except ValueError as error:
    assert 'lo must be non-negative' in str(error)
else:
    raise AssertionError('a negative lo was accepted')
```

### 按键查找

`key` 在每次探测时对被探测的元素调用一次，因此带键的查找只需 O(log n) 次键调用，也不需要并行列表。
它不会对 `x` 调用：查找函数把 `x` 当作已经是键值。`insort` 是例外——它插入的是记录本身，因此会调用
一次 `key(x)` 来确定位置。

```python
import bisect

records = [('a', 1), ('b', 3), ('c', 5)]
by_count = lambda record: record[1]

pos = bisect.bisect_right(records, 4, key=by_count)  # O(log n) key calls; x is the key value
assert pos == 2

bisect.insort(records, ('d', 4), key=by_count)  # O(n); key(x) is called here
assert records == [('a', 1), ('b', 3), ('d', 4), ('c', 5)]
```

当许多查找共享同一个列表时，可以改用键的并行列表：构建它需要 O(n)，并且每次插入都必须同步更新，
但之后每次查找都不再调用键函数。

```python
import bisect

records = [('a', 1), ('b', 3), ('c', 5)]
keys = [record[1] for record in records]  # O(n) once

pos = bisect.bisect_right(keys, 4)  # O(log n), no key calls
records.insert(pos, ('d', 4))       # O(n)
keys.insert(pos, 4)                 # O(n) - keys must follow every insert
assert keys == [record[1] for record in records] == [1, 3, 4, 5]
```

### 未排序的输入

没有任何东西检查切片是否有序。对未排序的输入，查找仍会返回一个位置而不引发异常，但不能保证它是
正确的位置：在那里插入后，列表仍可能无序。

```python
import bisect

unsorted = [3, 1, 4, 1, 5]

pos = bisect.bisect(unsorted, 2)  # O(log n), no error
result = unsorted[:pos] + [2] + unsorted[pos:]
assert result != sorted(result)
```

## 保持列表有序

### 逐个插入还是批量处理

对列表的每次 `insort` 都是 O(n)，因此向 n 个元素的列表插入 k 次的开销是 O(k·(n + k))。
当这些插入一起到来、中间没有查找时，先追加再排序一次的开销则是 O((n + k) log(n + k))。
当查找与插入交替进行时，`insort` 是合适的工具。

```python
import bisect

values = [1, 3, 5, 7]
bisect.insort(values, 4)  # O(n) - the tail shifts
assert values == [1, 3, 4, 5, 7]

# Many inserts at once: O(k·(n + k)) one at a time
one_at_a_time = [1, 3, 5, 7, 9]
for item in [8, 2, 6, 4]:
    bisect.insort(one_at_a_time, item)  # O(n) each

# ... or O((n + k) log(n + k)) as one sort
batch = [1, 3, 5, 7, 9]
batch.extend([8, 2, 6, 4])
batch.sort()
assert batch == one_at_a_time
```

## 常见模式

### 把分数映射到等级区间

```python
import bisect

breakpoints = [60, 70, 80, 90]
grades = 'FDCBA'

def grade(score):
    return grades[bisect.bisect(breakpoints, score)]  # O(log b), b = breakpoints

assert [grade(score) for score in (33, 60, 77, 89, 90, 100)] == list('FDCBAA')
```

### 时间窗口内的事件

```python
import bisect
from datetime import datetime

events = [
    (datetime(2024, 1, 1, 10), 'event1'),
    (datetime(2024, 1, 1, 12), 'event2'),
    (datetime(2024, 1, 1, 15), 'event3'),
    (datetime(2024, 1, 1, 18), 'event4'),
]
when = lambda event: event[0]

start = bisect.bisect_left(events, datetime(2024, 1, 1, 11), key=when)  # O(log n)
end = bisect.bisect_right(events, datetime(2024, 1, 1, 15), key=when)   # O(log n)
assert [name for _, name in events[start:end]] == ['event2', 'event3']  # O(m), m = matches
```

## 性能最佳实践

✅ **推荐**：

- 判断有序列表中的成员关系时，用 `bisect_left` 加一次比较，而不是 O(n) 的 `in`
- 用 `bisect_right - bisect_left` 在 O(log n) 内统计相等元素段的长度
- 已知答案位于列表的某一部分时，传入 `lo` 和 `hi`
- 偶尔在记录上查找时使用 `key`；许多查找共享时保留一个键的并行列表

❌ **避免**：

- 为一次查找构建键列表——为 O(log n) 的答案付出 O(n)
- 反复调用 `insort` 把一批数据装入列表——应追加后排序一次
- 在没有保持有序的列表上查找——结果不可靠，而且不会引发任何异常

## 版本说明

- **Python 3.10+**：六个函数都新增了 `key` 参数

## 相关模块

- **[heapq](heapq.md)** - 只需要最小元素而不需要有序列表时，push 和 pop 为 O(log n)
- **[list](../builtins/list.md)** - `insort` 和批量排序所依赖的 `insert()` 与 `sort()` 的开销
