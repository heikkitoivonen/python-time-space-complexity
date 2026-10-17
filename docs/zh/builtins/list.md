---
source_sha: e5d540424cf900e9f6a380860ebd4036e31f6ee63640234552e2d102a7e0b262
translated: machine
---

# 列表操作的复杂度

`list` 类型是可变的有序序列。CPython 将它实现为引用的动态数组：它保存指向每个元素的引用，并预留额外空间，使在末尾增长时很少需要扩容。

`n` 是列表长度，`k` 是数值参数的值（索引或重复次数），`i:j` 是切片边界，`len(t)` 是另一个操作数的长度。步长为 `s` 的切片选中 `m` 个元素，其 `i` 是它选中的最小索引。索引按负值规范化之后计算。比较两个元素和调用 `key` 函数按 O(1) 计；迭代一个本身不是列表或元组的操作数会另加其自身的开销。“均摊”指单次调用偶尔可能承担一次 O(n) 的容量调整，但这一开销分摊到它之前的调用上。

## 复杂度参考

### list

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len(l)` | O(1) | O(1) | 长度保存在列表中，无需计数 |
| `l[k]` | O(1) | O(1) | 直接索引 |
| `l[k] = x` | O(1) | O(1) | 替换一个槽位 |
| `del l[k]` | O(n-k) | O(1) | 将 k 之后的元素左移一位 |
| `l.append(x)` | 均摊 O(1) | 均摊 O(1) | |
| `l.insert(0, x)` | O(n) | 均摊 O(1) | 每个元素都右移一位 |
| `l.insert(k, x)` | 均摊 O(n-k) | 均摊 O(1) | 将从 k 开始的元素右移一位 |
| `l.remove(x)` | O(n) | O(1) | 从头查找，然后移动匹配项之后的元素 |
| `l.pop()` | 均摊 O(1) | O(1) | 移除最后一个元素；不移动任何元素 |
| `l.pop(0)` | O(n) | O(1) | 其余每个元素都左移一位 |
| `l.pop(k)` | 均摊 O(n-k) | O(1) | 将 k 之后的元素左移一位 |
| `l.clear()` | O(n) | O(1) | 释放每个元素 |
| `l.index(x)` | O(n) | O(1) | 线性查找；`l.index(x, i, j)` 只查找 `l[i:j]`，为 O(j-i) |
| `l.count(x)` | O(n) | O(1) | 线性扫描 |
| `l.sort(key=None, reverse=False)` | O(n log n) | O(n) | 已排序或逆序输入只需 O(n) 次比较；`key` 对每个元素调用一次 |
| `l.reverse()` | O(n) | O(1) | 原地进行 |
| `l.copy()` | O(n) | O(n) | 浅拷贝 |
| `l.extend(t)` | 均摊 O(len(t)) | O(len(t)) | 另加迭代 t 的开销 |
| `l += t` | 均摊 O(len(t)) | O(len(t)) | 与 `l.extend(t)` 相同；列表仍是同一个对象 |
| `l[i:j]`（切片） | O(j-i) | O(j-i) | 带步长时为 O(m) |
| `l[i:j] = t` | 若 len(t) == j-i 为 O(j-i)，否则均摊 O(n-i+len(t)) | O(j-i+len(t)) | 长度相等时原地覆盖；否则 j 之后的所有元素都要移动 |
| `l[i:j:s] = t`（s ≠ 1） | O(m) | O(m) | t 必须恰好有 m 个元素，因此不移动任何元素 |
| `del l[i:j]` | O(n-i) | O(j-i) | j 之后的所有元素左移 |
| `del l[i:j:s]` | O(n-i) | O(m) | i 之后的所有元素向前收拢 |
| `l1 + l2`（拼接） | O(len(l1)+len(l2)) | O(len(l1)+len(l2)) | 新列表 |
| `l * k`（重复） | O(nk) | O(nk) | 含 n·k 个引用的新列表；k ≤ 0 时得到空列表 |
| `l *= k` | O(nk) | O(nk) | 原地进行；k ≤ 0 时以 O(n) 清空列表 |
| `l1 == l2` | O(n) | O(1) | 长度不同时为 O(1)；否则在第一对不相等的元素处停止 |
| `l1 < l2`, `<=`, `>`, `>=` | O(min(len(l1), len(l2))) | O(1) | 在第一对不相等的元素处停止 |
| `for x in l`（迭代） | O(n) | O(1) | 每步 O(1) |
| `reversed(l)` | O(1) | O(1) | 惰性迭代器；遍历它为 O(n) |
| `x in l`（成员检测） | O(n) | O(1) | 线性查找 |
| `min(l)`, `max(l)` | O(n) | O(1) | n-1 次比较 |

## 在末尾增长

`append()` 是均摊 O(1)，因为扩容会为之后的追加预留空间，所以大多数追加只是写入列表已经拥有的空间。

```python
import sys

lst = []
resizes = 0
size = sys.getsizeof(lst)
for i in range(10_000):
    lst.append(i)  # O(1) amortized
    if sys.getsizeof(lst) != size:
        resizes += 1
        size = sys.getsizeof(lst)

assert len(lst) == 10_000
assert resizes < 100
```

## 在头部操作

在索引 0 处插入或删除会移动其他所有元素，因此每次调用都是 O(n)，循环执行则为 O(n²)。`collections.deque` 在两端添加和删除都是 O(1)。

```python
from collections import deque

lst = list(range(10_000))
lst.insert(0, -1)  # O(n): every element moves one slot right
assert lst[0] == -1 and len(lst) == 10_001
assert lst.pop(0) == -1  # O(n): every element moves back

queue = deque(range(10_000))
queue.appendleft(-1)  # O(1)
assert queue.popleft() == -1  # O(1)
```

## 切片赋值

用相同数量的元素替换一个切片会原地覆盖。其他任何长度都会打开或闭合一个空隙，因此切片之后的所有元素都要移动。扩展切片（步长不为 1）只接受与其选中元素数量完全相同的元素。

```python
lst = list(range(10))
lst[2:5] = ["a", "b", "c"]  # O(j-i): same length, overwritten in place
assert lst == [0, 1, "a", "b", "c", 5, 6, 7, 8, 9]

lst[2:5] = ["x"]  # O(n-i+len(t)): the tail moves left to close the gap
assert lst == [0, 1, "x", 5, 6, 7, 8, 9]

lst[::2] = "ABCD"  # O(m)
assert lst == ["A", 1, "B", 5, "C", 7, "D", 9]

try:
    lst[::2] = "AB"
except ValueError as exc:
    assert "sequence of size 2 to extended slice of size 4" in str(exc)
else:
    raise AssertionError("expected ValueError")
```

## 构建列表

`l + t` 会构建一个新列表，因此在循环中使用 `l = l + t` 每一步都会复制到目前为止构建的全部内容。`l += t` 和 `extend()` 以均摊 O(len(t)) 向现有列表添加元素。

```python
parts = [[i] for i in range(1_000)]

slow = []
for part in parts:
    slow = slow + part  # O(len(slow)): copies the list each time

fast = []
for part in parts:
    fast += part  # O(len(part)) amortized

assert slow == fast == list(range(1_000))
```

## 排序

`sort()` 是稳定且自适应的：已排序或逆序的输入只需 O(n) 次比较。`key` 函数对每个元素调用一次，而不是每次比较调用一次。

```python
calls = 0


def key(word):
    global calls
    calls += 1
    return word.lower()


words = ["pear", "Apple", "fig", "banana"]
words.sort(key=key)  # O(n log n)
assert words == ["Apple", "banana", "fig", "pear"]
assert calls == len(words)
```

## 性能最佳实践

✅ **推荐**：

- 用 `append()` 或 `extend()` 在末尾添加：每个元素均摊 O(1)
- 需要逆序构建列表时，先追加，再调用一次 `reverse()`：总计 O(n)
- 用 `len(t) == j - i` 的 `l[i:j] = t` 覆盖一段元素：其后的元素都不会移动
- 给 `sort()` 传 `key=`，而不是 `functools.cmp_to_key()` 比较函数：键函数调用 n 次，比较函数每次比较调用一次

❌ **避免**：

- 在循环中使用 `insert(0, x)` 或 `pop(0)`：每次都是 O(n) —— 改用 `collections.deque`
- 在循环中使用 `l = l + [x]`：每一步都复制列表，总计 O(n²)
- 在另一个循环内使用 `x in l`：每次检测 O(n) —— 先构建一次 [集合](set.md)，查找平均为 O(1)

## 相关类型

- **[Deque](../stdlib/collections.md#deque)** - 两端添加和弹出均为 O(1)
- **[Array](../stdlib/array.md)** - 对大型数值列表更省内存
- **[元组](tuple.md)** - 不可变的替代方案
- **[list()](list_func.md)** - 从可迭代对象构建列表

## 延伸阅读

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的列表实现
