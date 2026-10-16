---
source_sha: 4be9c7effa33db1176d1ac0933f57739a43404edc602043c8eb1ae684c37985d
translated: machine
---

# 列表操作的复杂度

`list` 类型是可变的有序序列。在 CPython 中它以动态数组实现。

`n` 是列表长度，`k` 是索引或重复次数，`i:j` 是切片边界，`len(t)` 是另一个操作数的长度。比较两个元素按 O(1) 计。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len(l)` | O(1) | O(1) | 长度保存在列表中，无需计数 |
| `l[k]` | O(1) | O(1) | 直接索引 |
| `l[k] = x` | O(1) | O(1) | 替换一个槽位 |
| `del l[k]` | O(n-k) | O(1) | 将 k 之后的元素左移一位 |
| `append(x)` | 均摊 O(1) | 均摊 O(1) | 可能扩容；需要重新分配时最坏为 O(n) |
| `insert(0, x)` | O(n) | 均摊 O(1) | 需要移动所有元素 |
| `insert(k, x)` | 均摊 O(n-k) | 均摊 O(1) | 将从 k 开始的元素右移一位 |
| `remove(x)` | O(n) | O(1) | 需要先查找再移动 |
| `pop()` | 均摊 O(1) | O(1) | 移除最后一个元素；不移动任何元素 |
| `pop(0)` | O(n) | O(1) | 移动其余元素 |
| `pop(k)` | 均摊 O(n-k) | O(1) | 将 k 之后的元素左移一位 |
| `clear()` | O(n) | O(1) | 释放内存 |
| `index(x)` | O(n) | O(1) | 线性查找 |
| `count(x)` | O(n) | O(1) | 线性扫描 |
| `sort()` | 最坏 O(n log n)，已排序或逆序输入为 O(n) | O(n) | Timsort/Powersort；自适应，已有序的片段所需比较更少 |
| `reverse()` | O(n) | O(1) | 原地反转 |
| `copy()` | O(n) | O(n) | 浅拷贝 |
| `extend(t)` | 均摊 O(len(t)) | O(len(t)) | 另加迭代 t 的开销；可能触发 O(n) 扩容 |
| `l[i:j]`（切片） | O(j-i) | O(j-i) | 带步长时为 O(结果长度) |
| `l[i:j] = t` | 若 len(t) == j-i 为 O(j-i)，否则均摊 O(n-i+len(t)) | O(j-i+len(t)) | 长度相等时原地覆盖；否则 j 之后的所有元素都要移动 |
| `del l[i:j]` | O(n-i) | O(j-i) | j 之后的所有元素左移 |
| `l1 + l2`（拼接） | O(len(l1)+len(l2)) | O(len(l1)+len(l2)) | 新列表 |
| `l * k`（重复） | O(nk) | O(nk) | 含 n·k 个引用的新列表 |
| `for x in l`（迭代） | O(n) | O(1) | 每步 O(1) |
| `x in l`（成员检测） | O(n) | O(1) | 线性查找 |
| `min(l)`, `max(l)` | O(n) | O(1) | n-1 次比较 |

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
assert len(lst) == 1000000
```

### 插入操作的性能

```python
# O(n) - must shift all elements after insertion point
lst = [0] * 1000000
lst.insert(0, -1)  # Shifts 1,000,000 elements!
assert lst[0] == -1 and len(lst) == 1000001
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
