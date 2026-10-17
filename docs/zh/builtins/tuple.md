---
source_sha: 0f682082c1e815cf6cb74518bbbdc670c90d687d42c87d1afd5e6f989b5ac7c8
translated: machine
---

# 元组操作的复杂度

`tuple` 类型是不可变的有序序列。CPython 将它存储为固定大小的引用数组，因此索引是直接访问，也永远不需要插入、删除或调整大小。由于元组不能改变，复制一个类型恰好是 `tuple` 的元组会返回该元组本身。

`n` 是元组长度，`k` 是数值参数的值（索引或重复次数），`i:j` 是切片边界，`len(t1)`、`len(t2)` 是操作数的长度。带步长的切片选中 `m` 个元素。索引按负值规范化之后计算。比较或哈希一个元素按 O(1) 计。

## 复杂度参考

### tuple

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len(t)` | O(1) | O(1) | 长度存储在元组中，无需计数 |
| `t[k]` | O(1) | O(1) | 直接索引 |
| `t[i:j]`（切片） | O(j-i) | O(j-i) | 带步长时为 O(m)；类型恰好是 `tuple` 的元组的 `t[:]` 返回 `t` 本身 |
| `t.index(x)` | O(n) | O(1) | 线性搜索；`t.index(x, i, j)` 只搜索 `t[i:j]`，为 O(j-i) |
| `t.count(x)` | O(n) | O(1) | 线性扫描 |
| `x in t`（成员测试） | O(n) | O(1) | 线性搜索 |
| `tuple(t)`、`copy.copy(t)` | O(1) | O(1) | 当 `t` 的类型恰好是 `tuple` 时返回 `t` 本身；元组没有 `copy()` 方法 |
| `tuple(iterable)` | O(n) | O(n) | n = 可迭代对象产出的元素数；见 [tuple()](tuple_func.md) |
| `t1 + t2`（拼接） | O(len(t1)+len(t2)) | O(len(t1)+len(t2)) | |
| `t * k`（重复） | O(nk) | O(nk) | k ≤ 0 得到空元组 |
| `t1 == t2` | O(min(len(t1), len(t2))) | O(1) | 即使长度不同也会比较元素；在第一对不相等的元素处停止 |
| `t1 < t2`、`<=`、`>`、`>=` | O(min(len(t1), len(t2))) | O(1) | 在第一对不相等的元素处停止 |
| `for x in t`（迭代） | O(n) | O(1) | 每步 O(1) |
| `reversed(t)` | O(1) | O(1) | 惰性迭代器；遍历它为 O(n) |
| `min(t)`、`max(t)` | O(n) | O(1) | n-1 次比较 |
| `hash(t)` | 首次调用 O(n)；3.14+ 之后的调用为 O(1) | O(1) | 3.11-3.13 每次调用都重新计算；若有元素不可哈希则抛出 `TypeError`，且不缓存任何结果 |

## 复制返回同一个元组

类型恰好是 `tuple` 的元组，其副本永远不可能与原元组不同，因此 `tuple(t)`、`copy.copy(t)` 和 `t[:]` 以 O(1) 返回 `t` 本身。子类实例则以 O(n) 复制。

```python
import copy

t = tuple(range(1_000))
assert tuple(t) is t  # O(1)
assert copy.copy(t) is t  # O(1)
assert t[:] is t  # O(1)


class Pair(tuple):
    pass


p = Pair((1, 2))
assert tuple(p) is not p and type(tuple(p)) is tuple  # O(n): a subclass is copied
```

## 哈希

`hash(t)` 组合每个元素的哈希值，因此首次调用为 O(n)。从 3.14 起，结果保存在元组中，之后的调用为 O(1)；在 3.11-3.13 上，每次调用都会重新遍历元素。缓存属于对象本身：单独构建的相等元组要为自己的首次哈希付出代价。

```python
import sys

calls = 0


class Key:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, Key) and self.value == other.value

    def __hash__(self):
        global calls
        calls += 1
        return hash(self.value)


t = tuple(Key(i) for i in range(100))
hash(t)  # O(n): hashes every element
assert calls == 100

calls = 0
hash(t)  # O(1) on 3.14+, O(n) before
assert calls == (0 if sys.version_info >= (3, 14) else 100)

try:
    hash((1, []))
except TypeError as exc:
    assert "unhashable type: 'list'" in str(exc)
else:
    raise AssertionError("expected TypeError")
```

## 比较元组

`==` 不会先检查长度。它遍历公共前缀，在第一对不相等的元素处停止，只有当较短的元组在所有元素对都相等的情况下耗尽时才查看长度。与[列表](list.md)不同，长度不同的元组仍会比较它们的公共前缀。

```python
compared = 0


class Item:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        global compared
        compared += 1
        return self.value == other.value

    __hash__ = None


short = tuple(Item(i) for i in range(999))
long = tuple(Item(i) for i in range(1_000))
assert short != long  # O(min(len(t1), len(t2))): the common prefix is compared
assert compared == 999

compared = 0
assert list(short) != list(long)  # a list answers from the lengths alone
assert compared == 0
```

## 构建元组

`t += (x,)` 会构建一个新元组，因此在循环中它会在每一步复制到目前为止收集的全部内容：总计 O(n²)。应先收集到列表中，再一次性转换。

```python
slow = ()
for i in range(1_000):
    slow += (i,)  # O(len(slow)): copies the tuple each time

items = []
for i in range(1_000):
    items.append(i)  # O(1) amortized
fast = tuple(items)  # O(n), once

assert slow == fast == tuple(range(1_000))
```

## 性能最佳实践

✅ **推荐**：

- 放心复制：类型恰好是 `tuple` 的元组的 `tuple(t)` 和 `t[:]` 为 O(1)
- 当元素都可哈希时，把元组用作字典键或集合成员；从 3.14 起，每个元组的哈希值只计算一次
- 把元素收集到列表中，再调用一次 `tuple()`：总计 O(n)

❌ **避免**：

- 在循环中使用 `t += (x,)`：每一步都复制元组，总计 O(n²)
- 在另一个循环中使用 `x in t`：每次测试 O(n)——先构建一次[集合](set.md)，查找平均为 O(1)

## 版本说明

- **Python 3.14+**：`hash(t)` 将结果保存在元组中，因此重复调用为 O(1)

## 相关类型

- **[列表](list.md)** - 可变的替代方案
- **[tuple()](tuple_func.md)** - 从可迭代对象构建元组
- **[namedtuple](../stdlib/namedtuple.md)** - 带命名字段的元组
- **[Dataclass](../stdlib/dataclasses.md)** - 带命名字段的可变记录

## 延伸阅读

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的元组实现
