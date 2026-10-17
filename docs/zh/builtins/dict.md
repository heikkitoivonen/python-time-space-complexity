---
source_sha: a15a59a2e896d04888dafc57e64dd677615bec4310ef7fc6de1e8eb9c35a355e
translated: machine
---

# 字典操作的复杂度

`dict` 类型是一种可变映射，按插入顺序保存键值对。在 CPython 中它是哈希表，因此查找、插入和删除不依赖
字典的大小，而触及每个元素的操作——复制、迭代、比较——都是线性的。

`n` 是字典中的元素个数，`m` 是另一个操作数中的元素个数：传给 `update()` 或 `fromkeys()` 的映射或
可迭代对象，或者 `|` 及视图集合运算的右操作数。键的哈希与比较视为 O(1)，比较两个值也是如此。O(1)
的查找是平均情况：如果所有键的哈希值都相同，每次查找都会变为 O(n)。

## 复杂度参考

### dict

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `len(d)` | O(1) | O(1) | 元素个数已保存 |
| `d[key]`, `d.get(key, default=None)` | 平均 O(1)，最坏 O(n) | O(1) | 键不存在时 `d[key]` 抛出 `KeyError` |
| `key in d` | 平均 O(1)，最坏 O(n) | O(1) | |
| `d[key] = value` | 摊还 O(1) | O(1) | 使哈希表增长的那次调用以 O(n) 重建它 |
| `del d[key]`, `d.pop(key[, default])` | 平均 O(1)，最坏 O(n) | O(1) | 键不存在时抛出 `KeyError`，除非给 `pop()` 提供默认值；哈希表不会缩小 |
| `d.setdefault(key, default=None)` | 摊还 O(1) | O(1) | 一次查找，键不存在时再加一次插入 |
| `d.popitem()` | 摊还 O(1) | O(1) | 移除最后插入的键值对；字典为空时抛出 `KeyError` |
| `d.clear()` | O(n) | O(1) | 释放每个键和值 |
| `d.copy()` | O(n) | O(n) | 浅拷贝：键和值是共享的，不会被复制 |
| `dict.fromkeys(iterable, value=None)` | O(m) | O(m) | 每个键都映射到同一个 `value` 对象 |
| `d.update(other)`, `d \|= other` | 摊还 O(m) | O(m) | 原地修改，另加迭代 `other` 的开销：映射或键值对的可迭代对象 |
| `d \| other` | O(n + m) | O(n + m) | 新字典：`d` 的副本再用 `other` 更新。`dict` 只处理 `dict` 或 `frozendict` 类型的 `other`，其他情况交给 `other.__ror__` |
| 迭代 `d`、`reversed(d)` | O(n) | O(1) | 按插入顺序或其逆序 |
| `d == other`, `d != other` | O(n) | O(1) | 忽略顺序；长度不同时为 O(1) |

### 视图

`d.keys()`、`d.values()` 和 `d.items()` 是视图：它们持有对 `d` 的引用，能看到之后对 `d` 的每一处
修改，而不复制任何内容。

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `d.keys()`, `d.values()`, `d.items()` | O(1) | O(1) | |
| `len(view)`, `view.mapping` | O(1) | O(1) | `mapping` 是 `d` 的只读代理 |
| 迭代视图、`reversed(view)` | O(n) | O(1) | |
| `key in d.keys()`, `(key, value) in d.items()` | 平均 O(1)，最坏 O(n) | O(1) | 一次键查找，`items()` 还要再比较一次值 |
| `value in d.values()` | O(n) | O(1) | 值没有索引，因此需要逐个扫描 |
| `view & other` | O(m) | O(min(n, m)) | 适用于 `keys()` 和 `items()` 视图；`other` 是集合或 `keys()`、`items()` 视图时，时间为 O(min(n, m)) |
| `view \| other`, `view - other`, `view ^ other` | O(n + m) | O(n + m) | 各自构建一个新的 `set` |
| `view.isdisjoint(other)` | O(m) | O(1) | `other` 是集合或 `keys()`、`items()` 视图时为 O(min(n, m))；遇到第一个共同元素即停止 |

删除元素不会缩小哈希表。移除大部分元素后，遍历哈希表的操作——迭代 `d` 或视图、`copy()`、
`d | other`、`other.update(d)`、`d == other` 和 `dict(d)`——所需时间仍与字典以前的大小成正比，
直到之后的插入触发扩容重建。`len()` 和查找不受影响。

## 查找与冲突

查找会计算键的哈希，并且只与哈希值相同的已存键进行比较。哈希分布良好时最多比较一次。当许多键的哈希值
相同时，查找会依次与它们逐一比较，因此退化为 O(n)。

```python
class Key:
    comparisons = 0

    def __init__(self, name, hash_value):
        self.name = name
        self.hash_value = hash_value

    def __hash__(self):
        return self.hash_value

    def __eq__(self, other):
        Key.comparisons += 1
        return self.name == other.name

spread = {Key(i, i): i for i in range(100)}     # O(n)
Key.comparisons = 0
assert spread[Key(99, 99)] == 99                # O(1)
assert Key.comparisons == 1                     # only the key with the same hash

colliding = {Key(i, 1): i for i in range(100)}  # O(n²) - each insertion compares
Key.comparisons = 0
assert colliding[Key(99, 1)] == 99              # O(n) - compares every key before it
assert Key.comparisons == 100
```

## 删除不会缩小哈希表

`del` 和 `pop()` 会让哈希表保持在其最大尺寸，因此遍历时仍会访问它曾经拥有的每个槽位。对丢失了大部分
元素的字典调用 `copy()` 会构建一个紧凑的字典，使之后的遍历重新变得廉价。

```python
import sys

d = {i: i for i in range(100_000)}
full = sys.getsizeof(d)
for i in range(10, 100_000):
    del d[i]                       # O(1) each

assert len(d) == 10                # O(1)
assert sys.getsizeof(d) == full    # still sized for 100,000 items
keys = list(d)                     # O(100,000): walks the old table

d = d.copy()                       # O(100,000) once
assert sys.getsizeof(d) < full     # sized for 10 items
assert list(d) == keys             # O(10)
```

### 移除最旧的元素

哈希表的前端也是如此。`next(iter(d))` 会跳过之前删除所腾空的每个槽位，因此在循环中移除最旧的键，
每次调用花费 O(n)，整个字典总共花费 O(n²)。`collections.OrderedDict.popitem(last=False)` 以 O(1)
移除最旧的元素。

```python
from collections import OrderedDict

d = dict.fromkeys(range(5))
oldest = next(iter(d))      # O(1) here; O(deleted so far) in a loop
del d[oldest]
assert list(d) == [1, 2, 3, 4]

od = OrderedDict.fromkeys(range(5))
assert od.popitem(last=False) == (0, None)   # O(1)
assert list(od) == [1, 2, 3, 4]
```

## 视图

视图以 O(1) 创建，并反映使用时字典的状态。在 `keys()` 和 `items()` 中判断成员是哈希查找；在
`values()` 中判断成员是扫描。`keys()` 和 `items()` 的集合运算返回一个新的 `set`。

```python
d = {'a': 1, 'b': 2}
keys = d.keys()                 # O(1) - no copy
d['c'] = 3
assert list(keys) == ['a', 'b', 'c']  # O(n) - sees the new key

assert 'b' in keys              # O(1)
assert ('b', 2) in d.items()    # O(1) - key lookup, then one value comparison
assert 3 in d.values()          # O(n) - a scan

assert keys & {'a', 'z'} == {'a'}           # O(min(n, m)) with a set
assert keys - ['a'] == {'b', 'c'}           # O(n + m)
assert keys.isdisjoint({'x', 'y'})          # O(min(n, m)) with a set
assert keys.mapping['a'] == 1               # O(1) - a read-only proxy
```

## 使用 | 和 update() 合并

`d | other` 先复制 `d`，再插入 `other` 的每个元素，因此无论哪一边更大，都是 O(n + m)。
`d |= other` 和 `d.update(other)` 直接插入 `d` 本身，只需 O(m)。`update()` 还接受键值对的可迭代对象
和关键字参数。

```python
defaults = {'color': 'red', 'size': 10}
overrides = {'size': 12}

merged = defaults | overrides       # O(n + m) - a new dict
assert merged == {'color': 'red', 'size': 12}
assert defaults['size'] == 10

config = defaults
config |= overrides                 # O(m) - in place
assert config is defaults and defaults['size'] == 12

config.update([('debug', True)], verbose=False)  # O(m)
assert list(config) == ['color', 'size', 'debug', 'verbose']
```

## 插入顺序

迭代遵循插入顺序，`reversed()` 则反向遍历。给已存在的键赋值会保留它的位置。`popitem()` 移除最后插入的
键值对。

```python
d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
d['a'] = 10                         # O(1) - keeps its position

assert list(d) == ['a', 'b', 'c']   # O(n)
assert list(reversed(d)) == ['c', 'b', 'a']  # O(n)
assert d.popitem() == ('c', 3)      # O(1) - last in, first out
assert d == {'b': 2, 'a': 10}       # O(n) - order is ignored
```

## 键必须可哈希

每次查找和每次 `d[key] = value` 都会对键求哈希。列表、字典和集合是可变的、不可哈希的，因此不能作为键；
由相同的可哈希元素组成的元组或 `frozenset` 则可以。

```python
d = {
    (1, 2): 'tuple_key',
    'string': 'str_key',
    42: 'int_key',
    frozenset([1, 2]): 'frozen_key',
}
assert d[frozenset([2, 1])] == 'frozen_key'   # O(1) after hashing the key

for key in ([1, 2], {1, 2}, {'a': 1}):
    try:
        d[key] = 'fails'
    except TypeError as error:
        assert 'unhashable' in str(error)
    else:
        raise AssertionError(f'{type(key).__name__} must not be usable as a key')
```

## 性能最佳实践

✅ **推荐**：

- 按键查找时使用字典：O(1)，而不是列表所需的 O(n) 扫描
- 用 `get()` 或 `setdefault()` 处理缺失的键，只查找一次而不是两次
- 用 `d |= other` 或 `update()` 以 O(m) 向字典添加内容；`d | other` 会先复制 `d`
- 复制丢失了大部分元素的字典，使之后的遍历只花费其当前大小的开销

❌ **避免**：

- 在循环中使用 `value in d.values()` —— 每次判断都是 O(n)；改为维护一个反向字典或值的集合
- 在循环中用 `del d[next(iter(d))]` 移除最旧的键 —— 总共 O(n²)；改用
  `OrderedDict.popitem(last=False)`
- 反复用 `d = d | other` 构建字典 —— 每一步都复制到目前为止的全部内容
- 使用 `__hash__` 质量差的键 —— 大量冲突时，每次查找都退化为 O(n)

## 版本说明

- **Python 3.7+**：插入顺序成为语言规范的一部分；CPython 3.6 已经保持了这一顺序
- **Python 3.9+**：合并运算符 `|` 和更新运算符 `|=`
- **Python 3.15+**：[`frozendict`](frozendict.md)，不可变且可哈希的字典

## 相关类型

- **[集合](set.md)** - 无序的唯一元素
- **[frozendict](frozendict.md)** - 不可变、可哈希的字典（Python 3.15+）
- **[Defaultdict](../stdlib/collections.md#defaultdict)** - 自动提供默认值
- **[OrderedDict](../stdlib/collections.md#ordereddict)** - 两端 O(1) 移除以及 `move_to_end()`
- **[ChainMap](../stdlib/collections.md#chainmap)** - 多个字典的视图

## 延伸阅读

- [CPython Internals: dict](https://zpoint.github.io/CPython-Internals/BasicObject/dict/dict.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的字典实现
