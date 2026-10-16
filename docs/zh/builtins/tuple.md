---
source_sha: 94b8516e62742f8991e48fca56d762ca55a09160a862913d1a31bbcba081e372
translated: machine
---

# 元组操作的复杂度

`tuple` 类型是不可变的有序序列。不可变性使 CPython 得以进行多种优化。

`n` 是元组长度，`k` 是索引或重复次数，`i:j` 是切片边界，`len(t1)`、`len(t2)` 是操作数的长度。比较或哈希一个元素按 O(1) 计。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len(t)` | O(1) | O(1) | 长度保存在元组中，无需计数 |
| `t[k]` | O(1) | O(1) | 直接索引 |
| `index(x)` | O(n) | O(1) | 线性查找 |
| `count(x)` | O(n) | O(1) | 线性扫描 |
| `x in t`（成员检测） | O(n) | O(1) | 线性查找 |
| `tuple(t)`, `copy.copy(t)` | O(1) | O(1) | `t` 类型恰为 `tuple` 时返回 `t` 本身；元组没有 `copy()` 方法 |
| `t1 + t2`（拼接） | O(len(t1)+len(t2)) | O(len(t1)+len(t2)) | |
| `t * k`（重复） | O(nk) | O(nk) | |
| `for x in t`（迭代） | O(n) | O(1) | 每步 O(1) |
| `min(t)`, `max(t)` | O(n) | O(1) | n-1 次比较 |
| `hash()` | 首次 O(n)；3.14+ 之后为 O(1) | O(1) | 3.14+ 将哈希值缓存在 `ob_hash` 中；3.11-3.13 每次调用都重新计算 |
| `reversed()` | O(1) | O(1) | 返回迭代器，不会物化 |
| `tuple()` 构造函数 | O(n) | O(n) | n = 可迭代对象长度；类型恰为 `tuple` 的参数原样返回 |
| `t[i:j]`（切片） | O(j-i) | O(j-i) | 带步长时为 O(结果长度) |

## 实现细节

### 不可变性的优势

```python
# Tuples of hashable elements are hashable - can be dict keys or set members
d = {(1, 2): 'point', (3, 4): 'another'}
s = {(0, 0), (1, 1)}

# Lists cannot - they're mutable
# d[[1, 2]] = 'fails'  # TypeError: unhashable type
```

### 哈希值的计算

```python
# hash() computes hash value by iterating all elements
t = tuple([1, 2, 3])  # built at run time, so not hashed yet
h1 = hash(t)  # O(n) first call - computes by iterating elements

# Python 3.14+ caches the hash in the tuple's ob_hash field;
# 3.11-3.13 recompute it on every call
h2 = hash(t)  # O(1) on 3.14+, O(n) on 3.11-3.13
assert h1 == h2
```

### 引用与拷贝

```python
# Tuple "copy" doesn't copy - returns same object
t1 = (1, 2, 3)
t2 = tuple(t1)
assert t1 is t2  # True - same object in memory!

# This is safe because tuples are immutable
```

## 与列表的性能对比

```python
# List access: O(1) with bounds checking
lst = [0] * 1000000
value = lst[500000]  # O(1)

# Tuple access: O(1) same as list
tup = tuple(lst)
value = tup[500000]  # O(1)

# But tuple creation from list: O(n)
tup = tuple(lst)  # O(n) - must copy all elements
```

## 版本说明

- **Python 3.8+**：部分场景下元组解包有所改进
- **Python 3.11+**：自适应特化可优化重复的元组操作
- **Python 3.14+**：`hash()` 会把结果缓存在元组中，因此重复调用为 O(1)

## 各实现对比

### CPython
直接的序列类型，带有针对不可变性的优化。

### PyPy
JIT 编译配合逃逸分析可进一步优化。

### Jython
特性类似，底层由 Java 数组支撑。

## 最佳实践

✅ **推荐**：

- 需要不可变序列时使用元组
- 需要结构化的键时，用元组作字典的键
- 用元组返回多个值
- 使用元组解包：`x, y = point`

❌ **避免**：

- 在循环中反复拼接：`t += (item,)` —— 改用列表
- 在循环里从大型可迭代对象创建元组

## 常见用法

### 具名返回值

```python
# Basic tuples
def get_coordinates():
    return (10, 20)

x, y = get_coordinates()

# Better: use named tuples
from collections import namedtuple
Point = namedtuple('Point', ['x', 'y'])

def get_point():
    return Point(10, 20)

p = get_point()
print(p.x, p.y)  # More readable
```

### 元组与列表的性能

```python
# Tuple creation: O(n) once, then fast access
tup = tuple(range(1000000))
for i in range(1000):
    x = tup[i]  # O(1)

# List creation: O(n) once, then fast access
lst = list(range(1000000))
for i in range(1000):
    x = lst[i]  # O(1)

# Both have O(1) indexing; tuple is hashable and immutable
```

## 相关类型

- **[列表](list.md)** - 可变的替代方案
- **[Namedtuple](../stdlib/collections.md#namedtuple)** - 带具名字段的元组
- **[Dataclass](../stdlib/dataclasses.md)** - 功能更强的结构类型

## 延伸阅读

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的元组实现
