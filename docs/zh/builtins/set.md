---
source_sha: bc1c0d5a1529618fadecea5515f24b98a32b01bad53b2296163318b2ea145d27
translated: machine
---

# 集合操作的复杂度

`set` 类型是由唯一且可哈希的元素组成的可变、无序容器。它是一张哈希表，就像没有值的 `dict`，因此成员检测、
添加和删除平均为 O(1)，而集合运算的代价取决于需要查找的元素数量。

`n` 是集合中的元素数，`m` 是另一个操作数的元素数，或可迭代操作数产生的元素数。表中各行按单个操作数计价；
接受多个操作数的方法会依次处理它们，代价为各次之和。元素的哈希与比较视为 O(1)。

## 复杂度参考

### set

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `len(s)` | O(1) | O(1) | 元素数量已存储 |
| `x in s` | 平均 O(1)，最坏 O(n) | O(1) | 哈希查找；最坏情况出现在哈希冲突时。集合类型的 `x` 会按 frozenset 计算哈希：对其 k 个元素为 O(k)，3.14 之前空间也为 O(k) |
| 迭代 `set` | O(n) | O(1) | 顺序任意 |
| `s.add(x)` | 均摊 O(1) | 均摊 O(1) | 偶尔调整哈希表大小时以 O(n) 重建哈希表 |
| `s.remove(x)`, `s.discard(x)` | 平均 O(1)，最坏 O(n) | O(1) | `x` 不存在时 `remove()` 抛出 `KeyError`；集合类型的 `x` 的哈希计算与 `x in s` 相同 |
| `s.pop()` | 连续弹出直至清空时均摊 O(1) | O(1) | 从上一次 `pop()` 停下的位置开始，移除任意一个元素；集合为空时抛出 `KeyError`。经过其他方式的删除后，单次调用的代价可能达到哈希表先前的大小 |
| `s.clear()` | O(n) | O(1) | 释放所有元素 |
| `s.copy()` | O(n) | O(n) | 浅拷贝；副本的大小与其所含元素相称 |
| `s == other`, `s != other` | O(n) | O(1) | 长度不同时为 O(1) |
| `s <= other`, `s < other` | O(n) | O(1) | 等同于对集合调用 `issubset()` |
| `s >= other`, `s > other` | O(m) | O(1) | 等同于对集合调用 `issuperset()` |

### 集合运算

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `s.union(other)`, `s \| other` | O(n+m) | O(n+m) | 返回新集合 |
| `s.intersection(other)`, `s & other` | O(min(n,m))；若 `other` 不是集合则为 O(m) | O(min(n,m)) | 在较大的集合中查找较小集合的元素 |
| `s.difference(other)`, `s - other` | O(n)；若 `other` 不是集合则为 O(n+m) | O(n) | 返回新集合 |
| `s.symmetric_difference(other)`, `s ^ other` | O(n+m) | O(n+m) | 返回新集合 |
| `s.issubset(other)` | O(n)；若 `other` 不是集合则为 O(n+m) | O(1)；若 `other` 不是集合则为 O(m) | 当 `other` 是更短的集合时为 O(1) |
| `s.issuperset(other)` | O(m) | O(1) | 遇到第一个不在 `s` 中的 `other` 元素即停止 |
| `s.isdisjoint(other)` | O(min(n,m))；若 `other` 不是集合则为 O(m) | O(1) | 遇到第一个公共元素即停止；集合的子类会像普通可迭代对象一样被迭代 |

### 原地更新

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `s.update(other)`, `s \|= other` | 均摊 O(m) | 均摊 O(m) | `s` 最多增加 m 个元素 |
| `s.intersection_update(other)`, `s &= other` | 均摊 O(min(n,m))；若 `other` 不是集合则为均摊 O(m) | O(min(n,m)) | 构建交集并替换进去；释放旧哈希表需 O(n)，这部分已由填满它的插入操作支付 |
| `s.difference_update(other)`, `s -= other` | 均摊 O(min(n,m))；若 `other` 不是集合则为均摊 O(m) | O(n) | 原地从 `s` 中删除 |
| `s.symmetric_difference_update(other)`, `s ^= other` | 均摊 O(m) | 均摊 O(m) | `s` 最多增加 m 个元素；非集合的 `other` 会先被复制成集合 |

运算符只接受 set 和 frozenset；方法还接受任意可迭代对象。在最坏情况下，即所有元素的哈希值都相同时，
O(1) 操作会变为 O(n)，而在另一个集合中查找某个集合全部元素的操作也会相应变慢。

用 `remove()`、`discard()` 或 `pop()` 删除元素不会缩小哈希表。删除大部分元素后，遍历哈希表的操作
(迭代、`copy()`、`clear()`、`|`、`-`、`^`、`&=`、比较以及 `set(s)`) 所需时间仍与集合先前的大小成正比，
直到之后的插入触发哈希表大小调整为止，单次 `pop()` 也可能如此。`len()` 和成员检测不受影响。`&=` 及其方法总会留下
紧凑的哈希表。

## 集合运算

运算符只接受 set 和 frozenset，因此右侧是列表会引发 `TypeError`；方法接受任意可迭代对象，并在处理过程中
将其逐个转换为元素。

```python
a = {1, 2, 3}
b = {2, 3, 4}

assert a | b == {1, 2, 3, 4}     # O(n+m)
assert a & b == {2, 3}           # O(min(n,m))
assert a - b == {1}              # O(n)
assert a ^ b == {1, 4}           # O(n+m)

assert a.union([3, 4]) == {1, 2, 3, 4}  # O(n+m): a method takes any iterable
try:
    a | [3, 4]
except TypeError as error:
    assert 'unsupported operand' in str(error)
else:
    raise AssertionError('an operator takes only sets')

a |= b                           # O(m): grows a in place
assert a == {1, 2, 3, 4}
```

## 成员检测

列表要把 `x` 与元素逐一比较；集合只需对 `x` 计算一次哈希，平均探测少数几个槽位。把列表转换为集合需要一次
O(n)，因此在需要查找许多值时是值得的。

```python
numbers = list(range(1_000))
lookup = set(numbers)          # O(n) once

assert 999 in numbers          # O(n): scans the whole list
assert 999 in lookup           # O(1) avg
assert -1 not in lookup        # O(1) avg, found or not

# A set can be looked up in a set of frozensets, hashed as a frozenset
groups = {frozenset({1, 2}), frozenset({3})}
assert {1, 2} in groups        # O(k) to hash the k-element key
```

## 删除不会缩小哈希表

删除会让哈希表保持其最大时的大小，因此遍历它的代价仍与满载时相同。`copy()` 会返回紧凑的哈希表。

```python
import sys

s = set(range(100_000))
full = sys.getsizeof(s)
for i in range(10, 100_000):
    s.discard(i)                   # O(1) each

assert len(s) == 10                # O(1)
assert sys.getsizeof(s) == full    # still sized for 100,000 elements
items = list(s)                    # O(100,000): walks the old table

s = s.copy()                       # O(100,000) once
assert sys.getsizeof(s) < full     # sized for 10 elements
assert sorted(s) == sorted(items)  # O(10)
```

只用 `pop()` 清空集合时，每次调用都从上一次停下的位置开始，所以每个槽位只访问一次。经过其他方式的删除后，
`pop()` 必须先跳过前方的空槽位。

```python
s = set(range(1_000))
drained = 0
while s:
    s.pop()                        # O(1) amortized: the n calls walk the table once
    drained += 1
assert drained == 1_000

try:
    s.pop()
except KeyError as error:
    assert 'pop from an empty set' in str(error)
else:
    raise AssertionError('pop() on an empty set raises')
```

## 常见用法

### 去重

```python
items = [3, 1, 3, 2, 1]

# Bad: O(n²) - each `in` scans the list built so far
unique = []
for item in items:
    if item not in unique:
        unique.append(item)
assert unique == [3, 1, 2]

# Good: O(n), but the order is arbitrary
unique = set(items)
assert unique == {1, 2, 3}

# Best when order matters: O(n), keeping the first occurrence of each
assert list(dict.fromkeys(items)) == [3, 1, 2]
```

### 快速过滤

```python
values = list(range(10_000))
excluded = [3, 30, 300, 3_000]

# Bad: O(n·m) - scans the excluded list for every value
slow = [x for x in values if x not in excluded]

# Good: O(n + m) - one O(m) conversion, then O(1) per value
excluded_set = set(excluded)
fast = [x for x in values if x not in excluded_set]

assert slow == fast and len(fast) == 10_000 - 4
```

## 性能最佳实践

✅ **推荐**：

- 重复的成员检测使用集合：每次 O(1)，而列表需要 O(n)
- 求交集时顺序无所谓：以集合为操作数的 `&` 和 `intersection()` 只遍历较小的一方
- 需要保留原始顺序的唯一元素时使用 `dict.fromkeys()`
- 对已失去大部分元素的集合，在频繁遍历之前先复制，使遍历代价与其所含元素相称

❌ **避免**：

- 在遍历另一个容器的循环中使用 `x in some_list`：O(n·m)，而集合只需 O(n + m)
- 依赖迭代顺序；它取决于哈希表，而不是插入顺序
- 在以其他方式删除大部分元素后，仍期望 `pop()` 为 O(1)

## 版本说明

- **Python 3.14+**：把集合作为元素查找时 (`{1, 2} in s`、`s.discard({1, 2})`)，会原地计算其哈希，
  空间为 O(1)；更早的版本会把它复制成临时 frozenset，空间为 O(k)

## 相关类型

- **[Frozenset](frozenset.md)** - 不可变、可哈希的集合，查找代价相同
- **[set()](set_func.md)** - 从可迭代对象构建集合
- **[Dict](dict.md)** - 带值的同一种哈希表；`dict.fromkeys()` 保留插入顺序

## 延伸阅读

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的集合实现
