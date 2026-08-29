---
source_sha: 8bfb851d8a96095493ad930e71dce6a005258780f53354bdce9f6aba331e6613
translated: machine
---

# Collections 模块的复杂度

`collections` 模块提供针对特定场景优化的专用数据结构。

## deque

### 时间复杂度

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `append(x)` | O(1) | O(1) | 从右端添加 |
| `appendleft(x)` | O(1) | O(1) | 从左端添加 |
| `pop()` | O(1) | O(1) | 从右端移除 |
| `popleft()` | O(1) | O(1) | 从左端移除 |
| `access[i]` | O(1) ends, O(n) middle | O(1) | 两端（d[0]、d[-1]）为 O(1)；受分块结构影响，中间元素为 O(n) |
| `extend(iterable)` | O(k) | O(k) | k = 可迭代对象长度 |
| `extendleft(iterable)` | O(k) | O(k) | k = 可迭代对象长度；注意：会反转顺序 |
| `rotate(n)` | O(k) | O(1) | k = min(n, len(d) - n) |
| `clear()` | O(n) | O(1) | 移除所有元素 |
| `copy()` | O(n) | O(n) | 浅拷贝 |
| `count(x)` | O(n) | O(1) | 统计 x 出现的次数 |
| `index(x)` | O(n) | O(1) | 查找 x 第一次出现的位置 |
| `insert(i, x)` | O(n) | O(1) | 在位置 i 插入 x |
| `remove(x)` | O(n) | O(1) | 移除 x 第一次出现的位置 |
| `reverse()` | O(n) | O(1) | 原地反转 |
| `in` (membership) | O(n) | O(1) | 线性查找 |

### 属性

| 属性 | 说明 |
|-----------|-------|
| `maxlen` | 最大容量（无限制时为 None）；只读 |

### 空间复杂度

- 存储：n 个元素占 O(n)
- 操作：追加与弹出操作为 O(1)

### 使用场景

```python
from collections import deque

# Process items from both ends - very efficient
queue = deque([1, 2, 3])
queue.appendleft(0)  # O(1) - add to front
queue.pop()  # O(1) - remove from back

# Much faster than list for this pattern:
# list.insert(0, x) is O(n)
# list.pop(0) is O(n)
```

## DefaultDict

### 时间复杂度

与 `dict` 相同：

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `d[key]` | 平均 O(1) | O(1) | 缺失时返回默认值；哈希冲突下最坏为 O(n) |
| `d[key] = value` | 平均 O(1) | O(1) | 哈希冲突下最坏为 O(n) |
| `del d[key]` | 平均 O(1) | O(1) | 哈希冲突下最坏为 O(n) |
| `copy()` | O(n) | O(n) | 浅拷贝 |
| 其他字典操作 | 与 dict 相同 | - | |

### 属性

| 属性 | 说明 |
|-----------|-------|
| `default_factory` | 提供默认值的可调用对象；可以为 None |

### 空间复杂度

- n 个键值对占 O(n)
- 只有在访问缺失键时才调用默认工厂

### 使用场景

```python
# Avoid: Manual checking
from collections import defaultdict

data = defaultdict(list)
data['key'].append('value')  # O(1) avg - key auto-created as empty list

# Avoid: Clunky dict.get()
count = d.get('key', 0)  # O(1) avg, but two statements per increment
count += 1

# Better: defaultdict with int
from collections import defaultdict
count = defaultdict(int)
count['key'] += 1  # O(1) avg - one lookup, default supplied by the factory
```

## Counter

### 时间复杂度

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `Counter(iterable)` | O(n) | O(k) | n = 可迭代对象长度，k = 唯一元素个数 |
| `c[item]` | 平均 O(1) | O(1) | 缺失时返回 0；哈希冲突下最坏为 O(n) |
| `c.most_common(k)` | O(n log k) | O(k) | 基于堆；若 k 为 None 则为 O(n log n) |
| `c.update(iterable)` | O(n) | O(k) | n = 可迭代对象长度 |
| `c.subtract(iterable)` | O(n) | O(1) | 减去计数；保留负值 |
| `c.total()` | O(n) | O(1) | 所有计数之和（Python 3.10+） |
| `c.elements()` | O(1) init, O(total) iter | O(1) | 迭代元素，每个按其计数重复 |
| `c.copy()` | O(n) | O(n) | 浅拷贝 |
| `c.fromkeys(iterable)` | N/A | - | 对 Counter 无用；继承自 dict |
| `c + c2` | O(n) | O(n) | 合并计数器；保留正计数 |
| `c - c2` | O(n) | O(n) | 相减；保留正计数 |

### 使用场景

```python
from collections import Counter

# Count items - O(n) for n items
words = ['apple', 'banana', 'apple', 'cherry', 'apple']
c = Counter(words)
# Counter({'apple': 3, 'banana': 1, 'cherry': 1})

# Most common items - O(n log k) for k items, O(n log n) if k is None
top_3 = c.most_common(3)  # [('apple', 3), ('banana', 1), ('cherry', 1)]

# Arithmetic - O(n) over the combined keys
c1 = Counter('aab')
c2 = Counter('abc')
c1 + c2  # Counter({'a': 3, 'b': 2, 'c': 1})
```

## NamedTuple

### 时间复杂度

所有操作与元组相同：

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| 创建 | O(1) | O(1) | 字段数量固定 |
| 按索引访问 | O(1) | O(1) | 与元组相同 |
| 按名称访问 | O(1) | O(1) | 与元组相同 |
| 迭代 | O(n) | O(1) | n = 字段数量 |

### 使用场景

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])
p = Point(11, y=22)

# Better than plain tuple
print(p.x)  # More readable than p[0]

# Create from dict
d = {'x': 1, 'y': 2}
p = Point(**d)

# Replace values
p2 = p._replace(x=5)
```

## OrderedDict

### 时间复杂度

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| 与 dict 相同 | O(1) | O(1) | 所有字典操作 |
| `move_to_end(key)` | O(1) | O(1) | 将键移到末尾 |

### 说明

- **Python 3.6+**：普通 `dict` 已保留顺序，因此 `OrderedDict` 主要用于：

  - 与旧代码保持兼容
  - 使用 `move_to_end()` 方法重新排序
  - 在代码中明确表达意图

```python
from collections import OrderedDict

# Useful method: move_to_end()
od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
od.move_to_end('a')  # O(1) - moves 'a' to end
```

## ChainMap

### 时间复杂度

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `access[key]` | O(n) | O(1) | n = 映射个数；逐个查找直到命中 |
| `set[key]` | 平均 O(1) | O(1) | 写入第一个映射；最坏为 O(m)，m 为第一个映射的大小 |
| `del[key]` | 平均 O(1) | O(1) | 从第一个映射删除；最坏为 O(m)，m 为第一个映射的大小 |
| `len()` | O(N) | O(N) | N = 所有映射中的键总数；内部会构建并集 |
| `in` | O(n) | O(1) | 检查所有映射 |

### 使用场景

```python
from collections import ChainMap

# Layer multiple dicts
defaults = {'timeout': 30, 'retries': 3}
user_config = {'timeout': 60}

config = ChainMap(user_config, defaults)
print(config['timeout'])  # 60 (from user_config)
print(config['retries'])  # 3 (from defaults)

# View layered configuration without merging
```

## 性能对比

| 操作 | dict | defaultdict | Counter | OrderedDict |
|-----------|------|-------------|---------|------------|
| `d[key]` | O(1) | O(1) | O(1) | O(1) |
| `d[key] = value` | O(1) | O(1) | O(1) | O(1) |
| 特有方法 | - | `__missing__` | `most_common()` | `move_to_end()` |
| 内存 | 基准 | +少量 | +计数存储 | +顺序跟踪 |

## UserDict

`UserDict` 用可由用户定制的类包装标准字典。

### 时间复杂度

大多数操作与 `dict` 相同：

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `d[key]` | 平均 O(1) | O(1) | 哈希冲突下最坏为 O(n) |
| `d[key] = value` | 平均 O(1) | O(1) | 最坏为 O(n) |
| `del d[key]` | 平均 O(1) | O(1) | 最坏为 O(n) |
| 迭代 | O(n) | O(1) | n = 元素数量 |

## UserList

`UserList` 用可由用户定制的类包装标准列表。

### 时间复杂度

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| 索引 | O(1) | O(1) | 按索引访问 |
| 尾部追加 | 均摊 O(1) | O(1) | 扩容时最坏为 O(n) |
| 插入/删除 | O(n) | O(1) | 需要移动元素 |
| 迭代 | O(n) | O(1) | n = 列表长度 |

## UserString

`UserString` 用可由用户定制的类包装标准字符串。

### 时间复杂度

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| 索引 | O(1) | O(1) | 按索引访问 |
| 拼接 | O(n) | O(n) | n = 总长度 |
| 切片 | O(k) | O(k) | k = 切片长度 |
| 迭代 | O(n) | O(1) | n = 长度 |

## 相关文档

- [内置的 dict](../builtins/dict.md)
- [内置的 tuple](../builtins/tuple.md)
- [Heapq 模块](heapq.md)
