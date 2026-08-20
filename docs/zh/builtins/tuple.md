---
source_sha: c0bc8604cd865955e9bee5e9ce07ac587f5fc37659a6f2d952c5a11560725f18
translated: machine
---

# 元组操作的复杂度

`tuple` 类型是不可变的有序序列。不可变性使 CPython 得以进行多种优化。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 直接查询 |
| `access[i]` | O(1) | O(1) | 直接索引 |
| `index(x)` | O(n) | O(1) | 线性查找 |
| `count(x)` | O(n) | O(1) | 线性扫描 |
| `in`（成员检测） | O(n) | O(1) | 线性查找 |
| `copy()` | O(1) | O(1) | 仅增加引用计数 |
| `x + y`（拼接） | O(m+n) | O(m+n) | m、n 为长度 |
| `t * n`（重复） | O(n*len(t)) | O(n*len(t)) | 创建新元组 |
| `hash()` | 首次 O(n)，之后缓存为 O(1) | O(1) | 哈希值只计算一次，缓存在 `ob_hash` 中 |
| `reversed()` | O(1) | O(1) | 返回迭代器，不会物化 |
| `tuple()` 构造函数 | O(n) | O(n) | n = 可迭代对象长度 |
| `slice [::2]` | O(k) | O(k) | k = 切片长度 |

## 实现细节

### 不可变性的优势

```python
# Tuples are hashable - can be dict keys or set members
d = {(1, 2): 'point', (3, 4): 'another'}
s = {(0, 0), (1, 1)}

# Lists cannot - they're mutable
# d[[1, 2]] = 'fails'  # TypeError: unhashable type
```

### 哈希值的计算

```python
# hash() computes hash value by iterating all elements
t = (1, 2, 3)
h1 = hash(t)  # O(n) first call - computes by iterating elements

# CPython caches the hash in the tuple's ob_hash field
# Subsequent calls return the cached value
h2 = hash(t)  # O(1) - returns cached hash
```

### 引用与拷贝

```python
# Tuple "copy" doesn't copy - returns same object
t1 = (1, 2, 3)
t2 = tuple(t1)
print(t1 is t2)  # True - same object in memory!

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

- **所有版本**：核心复杂度稳定
- **Python 3.8+**：部分场景下元组解包有所改进
- **Python 3.11+**：自适应特化可优化重复的元组操作

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
- 想当然认为元组拷贝很快 —— 它仍然引用相同的元素

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

# Both have same access time; tuple is hashable and immutable
```

## 相关类型

- **[列表](list.md)** - 可变的替代方案
- **[Namedtuple](../stdlib/collections.md#namedtuple)** - 带具名字段的元组
- **[Dataclass](../stdlib/dataclasses.md)** - 功能更强的结构类型

## 延伸阅读

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的元组实现
