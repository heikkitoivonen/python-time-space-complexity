---
source_sha: 2c9b1483aa05e2e0dbb6693a2258ac1a811fbbbb06b82e37147b372fe2ca1fc9
translated: machine
---

# 列表操作的复杂度

`list` 类型是可变的有序序列。在 CPython 中它以动态数组实现。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 直接查询 |
| `access[i]` | O(1) | O(1) | 直接索引 |
| `append(x)` | 均摊 O(1) | 均摊 O(1) | 可能扩容；需要重新分配时最坏为 O(n) |
| `insert(0, x)` | O(n) | O(1) | 需要移动所有元素 |
| `insert(i, x)` | O(n-i) | O(1) | 从索引 i 开始移动元素 |
| `remove(x)` | O(n) | O(1) | 需要先查找再移动 |
| `pop()` | O(1) | O(1) | 移除最后一个元素 |
| `pop(0)` | O(n) | O(1) | 移动其余元素 |
| `pop(i)` | O(n-i) | O(1) | 移动 i 之后的元素 |
| `clear()` | O(n) | O(1) | 释放内存 |
| `index(x)` | O(n) | O(1) | 线性查找 |
| `count(x)` | O(n) | O(1) | 线性扫描 |
| `sort()` | 平均/最坏 O(n log n)，最好 O(n) | O(n) | Timsort/Powersort；对部分有序的数据自适应 |
| `reverse()` | O(n) | O(1) | 原地反转 |
| `copy()` | O(n) | O(n) | 浅拷贝 |
| `extend(iterable)` | O(k) | O(k) | k = 可迭代对象的长度；可能触发 O(n) 扩容 |
| `in`（成员检测） | O(n) | O(1) | 线性查找 |
| `x + y`（拼接） | O(m+n) | O(m+n) | m、n 为长度 |
| `[::2]`（切片） | O(k) | O(k) | k = 切片长度 |

## 实现细节

### 动态数组扩容

CPython 的列表采用一种增长因子策略：

```
If size >= capacity:
    new_capacity = (newsize + newsize // 8 + 6) & ~3  # Aligned to multiple of 4
```

这意味着：

- 追加操作是均摊 O(1)
- 并非每次追加都会扩容
- 超额分配降低了扩容频率

### 追加操作的性能

```python
# O(1) amortized
lst = []
for i in range(1000000):
    lst.append(i)  # Resizes ~log(n) times
```

### 插入操作的性能

```python
# O(n) - must shift all elements after insertion point
lst = [0] * 1000000
lst.insert(0, -1)  # Shifts 1,000,000 elements!
```

## 版本说明

- **Python 3.8+**：当前行为已稳定
- **Python 3.11+**：`append()` 快约 15%，列表推导式快 20-30%
- **Python 3.12+**：推导式被内联（最多快 2 倍）
- **所有版本**：核心复杂度自 Python 3.x 早期以来未变

## 各实现对比

### CPython
标准参考实现，使用动态数组。

### PyPy
得益于 JIT 优化，复杂度特性相同。

### Jython
类似，但基于 Java 数组，扩容因子可能不同。

## 最佳实践

✅ **推荐**：

- 使用 `append()` 添加元素
- 添加多个元素时使用 `extend()`
- 若需要在头部插入，可先追加再反转

❌ **避免**：

- 频繁使用 `insert(0, x)` —— 改用 `collections.deque`
- 反复调用 `pop(0)` —— 改用 `deque.popleft()`
- 用拼接（`+`）而不是 `append()` 或 `extend()` 构建大列表

## 相关类型

- **[Deque](../stdlib/collections.md#deque)** - 头尾插入均为 O(1)
- **[Array](../stdlib/array.md)** - 对大型数值列表更省内存
- **[元组](tuple.md)** - 不可变的替代方案

## 延伸阅读

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的列表实现
