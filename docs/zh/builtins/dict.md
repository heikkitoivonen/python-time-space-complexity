---
source_sha: 8fd3d66178b61ce76428fd4d9d654b6858f39d3c2870bb746da072fd9957bab2
translated: machine
---

# 字典操作的复杂度

`dict` 类型是存储键值对的可变映射。在 CPython 中它以哈希表实现。

`n` 是字典中的元素个数，`k` 是另一个操作数或可迭代对象中的元素个数。键的哈希和比较视为 O(1)。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 直接计数 |
| `access[key]` | 平均 O(1)，最坏 O(n) | O(1) | 哈希查找；发生冲突时为最坏情况 |
| `set[key] = value` | 均摊 O(1) | O(1) | 哈希插入；可能触发扩容 |
| `del[key]` | 平均 O(1)，最坏 O(n) | O(1) | 哈希删除 |
| `key in dict` | 平均 O(1)，最坏 O(n) | O(1) | 哈希查找 |
| `get(key)` | 平均 O(1)，最坏 O(n) | O(1) | 哈希查找 |
| `pop(key)` | 平均 O(1)，最坏 O(n) | O(1) | 哈希删除 |
| `clear()` | O(n) | O(1) | 需要释放所有条目 |
| `keys()` | O(1) | O(1) | 视图对象（迭代为 O(n)） |
| `values()` | O(1) | O(1) | 视图对象（迭代为 O(n)） |
| `items()` | O(1) | O(1) | 视图对象（迭代为 O(n)） |
| 遍历 `d` | O(n) | O(1) | 按插入顺序 |
| `copy()` | O(n) | O(n) | 所有键值对的浅拷贝 |
| `update(other)`, `d \|= other` | O(k) | O(1) | k = len(other)，均摊，另加遍历 `other` 的开销；原地修改 |
| `d \| other` | O(n + k) | O(n + k) | 新字典：先复制 `d`，再用 `other` 更新 |
| `setdefault(key, val)` | 平均 O(1) | O(1) | 哈希查找 + 插入 |
| `fromkeys(keys)` | O(k) | O(k) | k = len(keys) |
| `popitem()` | O(1) | O(1) | 移除最后插入的键值对（3.7 起为 LIFO） |

*说明：平均 O(1) 的前提是哈希分布良好。最坏情况 O(n) 出现在极端的哈希冲突下，而 Python 的随机化哈希使这种情况很少发生。*

删除元素不会缩小哈希表。删除大部分元素后，遍历表的操作（迭代、`copy()`、`other.update(d)`、`|`、`==` 和 `dict(d)`）仍然耗费与字典先前大小成正比的时间，直到之后的插入触发重新调整大小。`len()` 和查找不受影响。

## 实现细节

### 哈希表结构

CPython 使用的哈希表具有以下特点：

- **哈希函数**：`str`/`bytes` 使用 SipHash13（自 Python 3.11 起为默认）；其他类型使用各自的哈希方式
- **冲突处理**：开放寻址加探测
- **增长因子**：超过装载因子时约扩大 2-4 倍
- **Python 3.6（CPython）**：紧凑字典保留插入顺序，属于实现细节

### 哈希冲突的影响

```python
# Best case: perfect hashing (O(1))
d = {i: i for i in range(1000)}
value = d[500]  # O(1)

# Worst case: hash collisions (degraded, but very rare)
# CPython mitigates this with randomized hashing
```

### 删除不会缩小哈希表

`del` 和 `pop()` 会让表保持在最大尺寸，因此遍历时仍会访问它曾有的每个槽位。对于已失去大部分元素的字典，`copy()` 会构建一个紧凑的字典，使之后的遍历重新变得廉价。

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

### 插入顺序的保证

```python
# Python 3.7+ guarantees insertion order (language guarantee)
d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
# Iteration order: a, b, c (guaranteed)
```

## 版本说明

| 版本 | 变化 |
|---------|--------|
| Python 3.6 | CPython 的紧凑字典保留插入顺序（实现细节） |
| Python 3.7+ | 语言规范保证插入顺序 |
| Python 3.9+ | 字典合并与更新运算符（`\|`、`\|=`） |
| Python 3.10+ | 支持对字典进行模式匹配 |
| Python 3.11+ | 当所有键均为 Unicode 字符串时体积减小 23% |
| Python 3.15+ | [`frozendict`](frozendict.md)：不可变且可哈希的字典 |

## 各实现对比

### CPython
标准哈希表实现，高度优化。

### PyPy
复杂度相近，JIT 编译可能带来进一步优化。

### Jython
底层使用 Java 的 HashMap，具有相同的 O(1) 特性。

### IronPython
与 CPython 类似的哈希表实现。

## 最佳实践

✅ **推荐**：

- 用字典做键值查找
- 善用字典推导式：`{k: v for k, v in items}`
- 用 `setdefault()` 做条件插入

❌ **避免**：

- 在 Python < 3.7 中依赖插入顺序来实现可移植行为
- 用不可哈希的类型作键（列表、字典、集合）
- 在哈希函数质量差的情况下使用超大字典

## 关于哈希函数的注意事项

```python
# Hashable types work as keys
d = {
    (1, 2): 'tuple_key',
    'string': 'str_key',
    42: 'int_key',
    frozenset([1, 2]): 'frozen_key'
}

# Unhashable types will fail
# d[[1, 2]] = 'fails'  # TypeError
# d[{1, 2}] = 'fails'  # TypeError
```

## 相关类型

- **[集合](set.md)** - 无序的唯一元素
- **[frozendict](frozendict.md)** - 不可变、可哈希的字典（Python 3.15+）
- **[Defaultdict](../stdlib/collections.md#defaultdict)** - 自动提供默认值
- **[OrderedDict](../stdlib/collections.md#ordereddict)** - 显式保序（3.6 之前）
- **[ChainMap](../stdlib/collections.md#chainmap)** - 多个字典的视图

## 延伸阅读

- [CPython Internals: dict](https://zpoint.github.io/CPython-Internals/BasicObject/dict/dict.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的字典实现
