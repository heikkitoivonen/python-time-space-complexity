---
source_sha: 45e6ee6587007e1eab2d114700afa7e63063edb6439cf6702f07a5f279051faf
translated: machine
---

# Collections 模块的复杂度

`collections` 模块提供针对特定场景优化的专用数据结构。

## deque

操作、复杂度和示例请参阅 [deque](deque.md)。

## DefaultDict

操作、复杂度和示例请参阅 [defaultdict](defaultdict.md)。

## Counter

操作、复杂度和示例请参阅 [Counter](counter.md)。

## NamedTuple

操作、复杂度和示例请参阅 [namedtuple](namedtuple.md)。

## OrderedDict

操作、复杂度和示例请参阅 [OrderedDict](ordereddict.md)。

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
