---
source_sha: ec504b5b92c746504f94fdd152feeacc24d552795359d63db896da03d453d2ff
translated: machine
---

# sorted() 函数的复杂度

`sorted()` 函数根据可迭代对象中的元素返回一个新的已排序列表。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 基本排序 | O(n log n) | O(n) | 把输入复制到新列表，再原地排序 |
| 使用 key 函数 | O(n log n + n*k) | O(n) | k = key 函数耗时；每个元素只调用一次 key，比较使用保存的键 |
| 逆序排序 | O(n log n) | O(n) | 稳定；排序前后各反转一次列表，额外 O(n) |
| 已经有序 | O(n) | O(n) | 最好情况：输入是单个连续段；完全逆序的输入开销相同 |

n 为元素个数；一次比较按 O(1) 计，键本身的大小不计入空间复杂度。

## 基本用法

### 简单排序

```python
# O(n log n) - Timsort (≤3.10) or Powersort (3.11+)
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
result = sorted(numbers)
# [1, 1, 2, 3, 4, 5, 6, 9]

# Works with any iterable
result = sorted((3, 1, 4))  # Tuple input
# [1, 3, 4]

result = sorted({3, 1, 4})  # Set input
# [1, 3, 4]

result = sorted("cadb")     # String input
# ['a', 'b', 'c', 'd']
```

### 逆序排序

```python
# O(n log n) - same complexity
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
result = sorted(numbers, reverse=True)
# [9, 6, 5, 4, 3, 2, 1, 1]

# Works with strings
words = ["apple", "pie", "cat"]
result = sorted(words, reverse=True)
# ["pie", "cat", "apple"]
```

## 使用 key 函数

### 自定义比较

```python
# O(n log n + n*k) where k = key function time
# Key is computed once per element, then comparisons use the stored keys
words = ["apple", "pie", "cat", "banana"]
result = sorted(words, key=len)  # Sort by length
# ["pie", "cat", "apple", "banana"]

# Sort by last character
result = sorted(words, key=lambda x: x[-1])
# ["banana", "apple", "pie", "cat"]
```

### 对象排序

```python
# O(n log n) - simple key extraction
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def __repr__(self):
        return f"Person({self.name}, {self.age})"

people = [
    Person("Alice", 30),
    Person("Bob", 25),
    Person("Charlie", 35),
]

# Sort by age
result = sorted(people, key=lambda p: p.age)
# [Person(Bob, 25), Person(Alice, 30), Person(Charlie, 35)]

# The same key via the operator module
from operator import attrgetter
result = sorted(people, key=attrgetter('age'))  # Same O(n log n)
```

### 元组排序

```python
# O(n log n) - lexicographic comparison
coords = [(1, 5), (3, 2), (2, 8)]
result = sorted(coords)
# [(1, 5), (2, 8), (3, 2)]

# Sort by second element
result = sorted(coords, key=lambda c: c[1])
# [(3, 2), (1, 5), (2, 8)]
```

## 排序算法

### 工作原理

```
Python sorts with Timsort (through 3.10) or Powersort (3.11+): a merge sort
that starts from the runs already present in the input.
1. Scan for natural runs - ascending, or descending, which are reversed in place
2. Extend short runs to 32-64 elements with binary insertion sort
3. Merge runs - O(n log n) comparisons overall
4. Input that is already one run: O(n) - nothing to merge

Powersort changes the order in which runs are merged, not the bound.
```

### 性能特性

```python
# Best case - O(n): the input is already one run
numbers = list(range(100000))
result = sorted(numbers)  # n - 1 comparisons

numbers = list(range(100000, 0, -1))  # Reverse sorted
result = sorted(numbers)  # One descending run, also O(n)

# Average and worst case - O(n log n)
import random
numbers = list(range(100000))
random.shuffle(numbers)
result = sorted(numbers)  # O(n log n)
```

## 性能模式

### sorted() 与 sort() 的对比

```python
# sorted() - creates new list, O(n log n) time, O(n) space
original = [3, 1, 4, 1, 5]
result = sorted(original)  # [1, 1, 3, 4, 5]
# original unchanged

# list.sort() - in-place, O(n log n) time, O(n) space
original = [3, 1, 4, 1, 5]
original.sort()  # [1, 1, 3, 4, 5]
# original modified

# Both use same algorithm, same complexity but sorted() makes copy
```

### 开销较大的 key 函数

```python
# O(n*m + n log n) - n key calls of O(m) each, then O(n log n) comparisons on the stored keys
def expensive_key(x):
    # O(m) - expensive computation, m = x here
    return sum(range(x))

numbers = list(range(1000))
result = sorted(numbers, key=expensive_key)

# Storing the keys pays only when the same keys serve more than one sort
from operator import itemgetter
keyed = [(x, expensive_key(x)) for x in numbers]  # O(n*m), once
ascending = sorted(keyed, key=itemgetter(1))                 # O(n log n)
descending = sorted(keyed, key=itemgetter(1), reverse=True)  # O(n log n), expensive_key not called again
```

### 装饰-排序-去装饰（DSU）

```python
# key= is decorate-sort-undecorate done for you: n key calls, then the
# sort compares only the stored keys, never the items themselves
items = [{"name": "b", "rank": 1}, {"name": "a", "rank": 1}]
result = sorted(items, key=lambda d: d["rank"])  # O(n*k + n log n)
# [{'name': 'b', 'rank': 1}, {'name': 'a', 'rank': 1}] - ties keep input order

# Building (key, item) tuples by hand costs the same n key calls, and on a
# tied key the comparison falls through to the items
decorated = [(d["rank"], d) for d in items]
try:
    sorted(decorated)
except TypeError:
    pass  # dicts do not order; key= never compared them
```

## 排序的稳定性

```python
# sorted() is stable - preserves order of equal elements
data = [(1, 'a'), (2, 'b'), (1, 'c'), (2, 'd')]
result = sorted(data, key=lambda x: x[0])
# [(1, 'a'), (1, 'c'), (2, 'b'), (2, 'd')]
# Among equal keys, original order preserved
```

## 常见用法

### 多重排序条件

```python
# Sort by multiple attributes - O(n log n)
students = [
    ('Alice', 85),
    ('Bob', 85),
    ('Charlie', 90),
]

# Sort by score descending, then name ascending
result = sorted(students, key=lambda s: (-s[1], s[0]))
# [('Charlie', 90), ('Alice', 85), ('Bob', 85)]
```

### 忽略大小写的排序

```python
# O(L + n log n) - str.lower() costs each word's length, L = total characters
words = ["Apple", "banana", "Cherry", "date"]
result = sorted(words, key=str.lower)
# ["Apple", "banana", "Cherry", "date"]
```

### 按自定义顺序排序

```python
# O(n log n) - custom comparison key
priority = {'high': 0, 'medium': 1, 'low': 2}
tasks = [
    {'name': 'A', 'priority': 'low'},
    {'name': 'B', 'priority': 'high'},
    {'name': 'C', 'priority': 'medium'},
]

result = sorted(tasks, key=lambda t: priority[t['priority']])
# B (high), C (medium), A (low)
```

## 与其他排序方式的比较

### sorted() vs list.sort()

```python
# sorted() - returns new list, original unchanged
original = [3, 1, 4, 1, 5]
result = sorted(original)

# list.sort() - modifies in-place, returns None
original = [3, 1, 4, 1, 5]
original.sort()

# Both: O(n log n) time, O(n) space for Timsort/Powersort
# Choose based on whether you need original
```

### sorted() vs heapq.nsmallest()

```python
import random
numbers = list(range(1000000))
random.shuffle(numbers)

# sorted() - O(n log n), entire list sorted
all_sorted = sorted(numbers)

# heapq.nsmallest() - O(n log k) for k items
import heapq
k_smallest = heapq.nsmallest(10, numbers)  # Wins when k << n
```

## 边界情况

### 空列表

```python
# O(1) - no sorting needed
result = sorted([])
# []
```

### 单个元素

```python
# O(1) - nothing to sort
result = sorted([42])
# [42]
```

### 已经有序

```python
# O(n) - one ascending run, n - 1 comparisons
numbers = list(range(1000000))
result = sorted(numbers)
```

### 完全逆序

```python
# O(n) - one descending run, reversed in place
numbers = list(range(1000000, 0, -1))
result = sorted(numbers)
```

## 最佳实践

✅ **推荐**：

- 用 `sorted()` 创建新的已排序列表
- 用 `key` 参数实现自定义排序
- 用 `key=`，而不是手工构造 `(key, item)` 元组
- 若同一组开销较大的键要用于多次排序，只保存一次

❌ **避免**：

- 多次调用 `sorted()`（应缓存结果）
- 只需要最小的 k 个元素却对整个输入排序（用 `heapq.nsmallest()`）
- key 函数够用时仍使用 `functools.cmp_to_key()`（每次比较都要调用一次 Python 函数，而不是每个元素一次）
- 忘记 `sorted()` 会创建新列表（占用内存）

## 相关函数

- **[list.sort()](list.md)** - 原地排序
- **[heapq.nsmallest()](../stdlib/heapq.md)** - 最小的 k 个元素
- **[heapq.nlargest()](../stdlib/heapq.md)** - 最大的 k 个元素
- **[max()](max.md)** - 不排序即可求最大值

## 版本说明

- **Python 2.3-3.10**：使用 Timsort 算法
- **Python 3.11+**：使用 Powersort（归并策略改进，复杂度不变）
