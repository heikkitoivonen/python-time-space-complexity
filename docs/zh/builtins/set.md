---
source_sha: 65a8e42df7b8e94caa84a3882f8713b92843278026321b9aa5d0c0ff5c017968
translated: machine
---

# 集合操作的复杂度

`set` 类型是由唯一元素组成的无序集合。在 CPython 中它以哈希表实现，与字典类似。

`n` 是集合中的元素个数，`m` 是另一个操作数中的元素个数。元素的哈希和比较视为 O(1)。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 直接计数 |
| `add(x)` | 平均 O(1)，最坏 O(n) | 均摊 O(1) | 哈希冲突会导致 O(n) |
| `remove(x)` | 平均 O(1)，最坏 O(n) | O(1) | 哈希查找 + 删除 |
| `discard(x)` | 平均 O(1)，最坏 O(n) | O(1) | 哈希查找 + 删除 |
| `pop()` | 平均 O(1) | O(1) | 移除任意一个元素 |
| `clear()` | O(n) | O(1) | 释放全部 |
| `x in set` | 平均 O(1)，最坏 O(n) | O(1) | 哈希查找；冲突会导致 O(n) |
| `copy()` | O(n) | O(n) | 浅拷贝 |
| `union(other)`, `s \| other` | O(n+m) | O(n+m) | n、m = 集合大小 |
| `intersection(other)`, `s & other` | O(min(n,m))；若 `other` 不是集合则为 O(m) | O(min(n,m)) | 遍历较小的集合 |
| `difference(other)`, `s - other` | O(n)；若 `other` 不是集合则为 O(n+m) | O(n) | n = 集合大小 |
| `symmetric_difference(other)`, `s ^ other` | O(n+m) | O(n+m) | 组合的集合操作 |
| `issubset()` | O(n)；若 `other` 不是集合则为 O(n+m) | O(1)；若 `other` 不是集合则为 O(m) | 检查所有元素 |
| `issuperset()` | O(m) | O(1) | m = 另一个集合的大小 |
| `isdisjoint()` | O(min(n,m))；若 `other` 不是集合则为 O(m) | O(1) | 可提前终止 |
| `update(other)`, `s \|= other` | O(m) | O(1) | 原地并集；m = len(other) |
| `difference_update(other)`, `s -= other` | O(min(n,m))；若 `other` 不是集合则为 O(m) | O(n) | 原地差集，遍历较小的一侧 |
| `intersection_update(other)`, `s &= other` | O(n)；若 `other` 不是集合则为 O(n+m) | O(min(n,m)) | 原地交集；重建集合并释放旧表，因此即使 `other` 很小也是 O(n) |
| `symmetric_difference_update(other)`, `s ^= other` | O(m) | O(1)；若 `other` 不是集合则为 O(m) | 原地对称差集 |

运算符形式只接受 set 和 frozenset；方法还接受任意可迭代对象。最坏情况下，当所有元素的哈希值相同时，O(1) 操作需要 O(n)，而在一个集合中查找另一个集合全部元素的操作也会相应变慢。

用 `remove()`、`discard()` 或 `pop()` 删除元素不会缩小哈希表。删除大部分元素后，遍历表的操作（迭代、`copy()`、`|`、`-`、`^`、比较和 `set(s)`）仍然耗费与集合先前大小成正比的时间，直到之后的插入触发重新调整大小。`len()` 和成员测试不受影响，用 `-=`、`&=` 或其对应方法删除大部分元素则会留下紧凑的表。

## 实现细节

### 哈希表实现

集合采用与字典相同的哈希表设计，但：

- 只存储键（没有值）
- 比字典更节省内存
- 平均查找同样是 O(1)

### 集合运算

```python
# Union: combines both sets
{1, 2} | {2, 3}  # {1, 2, 3} - O(len(s1) + len(s2))

# Intersection: common elements
{1, 2, 3} & {2, 3, 4}  # {2, 3} - O(min(len(s1), len(s2)))

# Difference: elements in first but not second
{1, 2, 3} - {2, 4}  # {1, 3} - O(len(s1))

# Symmetric difference: elements in either but not both
{1, 2} ^ {2, 3}  # {1, 3} - O(len(s1) + len(s2))
```

### 删除不会缩小哈希表

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

### 成员检测

```python
# Very fast - O(1) hash lookup
s = {1, 2, 3, 4, 5}
if 3 in s:  # O(1), not O(n)
    pass
```

## 与列表的对比

```python
# List membership: O(n) - must scan entire list
numbers_list = [1, 2, 3, 4, 5]
3 in numbers_list  # O(n)

# Set membership: O(1) - hash lookup
numbers_set = {1, 2, 3, 4, 5}
3 in numbers_set  # O(1) - much faster for large collections!
```

## 版本说明

- **所有 Python 3 版本**：核心复杂度未变

## 各实现对比

### CPython
标准哈希表实现。

### PyPy
JIT 编译可能带来额外优化。

### Jython
底层为 Java 的 HashSet，具有相同的 O(1) 特性。

## 最佳实践

✅ **推荐**：

- 在大型集合上做成员检测时使用集合
- 使用集合运算符（`|`、`&`、`-`、`^`）来组合集合
- 用集合去重：`set(list_with_dups)`
- 需要可哈希的唯一元素时使用 `frozenset`

❌ **避免**：

- 用列表做频繁的成员检测
- 依赖集合的顺序（并无保证）
- 在集合中放入不可哈希的类型（列表、字典）

## 常见用法

### 去重

```python
items = [3, 1, 3, 2, 1]

# Bad: preserves list, but O(n²)
unique = []
for item in items:
    if item not in unique:
        unique.append(item)

# Good: O(n), but loses order
unique = list(set(items))

# Best: O(n) and preserves order (Python 3.7+)
unique = list(dict.fromkeys(items))
```

### 快速过滤

```python
# Bad: O(n*m) - checks membership in list for each element
large_list = list(range(1000000))
exclusions = [1, 2, 3, ...]
filtered = [x for x in large_list if x not in exclusions]

# Good: O(n) - fast set lookup
exclusions_set = set(exclusions)
filtered = [x for x in large_list if x not in exclusions_set]
```

## 相关类型

- **[Frozenset](frozenset.md)** - 不可变集合
- **[Dict](dict.md)** - 可变映射
- **[Deque](../stdlib/collections.md#deque)** - 有序容器

## 延伸阅读

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的集合实现
