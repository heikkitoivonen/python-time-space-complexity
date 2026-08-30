---
source_sha: 320ab71a8582ba423db896cd3827ab3721ab7052df231a69351e224a5dd031da
translated: machine
---

# all() 函数的复杂度

如果可迭代对象中的所有元素都为真（或可迭代对象为空），`all()` 函数返回 `True`。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 所有元素均为真 | O(n) | O(1) | 必须检查所有元素 |
| 提前退出（发现假值） | O(k) | O(1) | k = 第一个假值的位置 |
| 空可迭代对象 | O(1) | O(1) | 立即返回 True |

## 基本用法

### 检查是否全为真

```python
# O(n) - must check all items
numbers = [1, 2, 3, 4, 5]
result = all(numbers)  # True - all truthy

# Early exit - O(k) where k = position of False
numbers = [1, 2, 0, 4, 5]
result = all(numbers)  # False - stops at 0

# Empty iterable
result = all([])  # True - all zero items are truthy
```

### 配合条件使用

```python
# O(n) where each predicate is O(1)
numbers = [1, 2, 3, 4, 5]
result = all(x > 0 for x in numbers)  # True

# Early exit - O(k) where k = position of first failure
result = all(x > 2 for x in numbers)  # False - stops at 1
```

## 性能模式

### 短路求值

```python
# ✅ O(1) - stops immediately at first falsy
checks = [lambda: False, expensive_function, expensive_function]
result = all(check() for check in checks)
# expensive_function() is never called

# ❌ O(n) - evaluates all
result = all([False] + [expensive_function() for _ in range(1000)])
# Calls expensive_function() 1000 times

# ✅ O(k) - generator stops when predicate first fails
result = all(x < 100 for x in range(1000000))
# Stops after checking 100 items
```

### 生成器效率

```python
# O(n) - lazy evaluation with early exit
large_list = range(10**9)
result = all(x < 100 for x in large_list)
# O(100) - stops after checking 100 items

# vs list comprehension
result = all([x < 100 for x in range(10**9)])
# O(10^9) - creates entire list first
```

## 常见模式

### 数据校验

```python
# O(n*k) - validate all items
def validate_data(items):
    return all(isinstance(item, int) for item in items)

# O(n) early exit if any item is invalid
valid = validate_data([1, 2, 3, 4, 5])  # True
valid = validate_data([1, 2, "three", 4, 5])  # False - stops at "three"
```

### 检查条件

```python
# O(n) - check all items meet condition
numbers = [2, 4, 6, 8, 10]
all_even = all(x % 2 == 0 for x in numbers)  # True

# Early exit
numbers = [2, 4, 5, 8, 10]
all_even = all(x % 2 == 0 for x in numbers)  # False - stops at 5
```

### 空序列处理

```python
# True for empty sequences
all([])  # True
all(())  # True
all(x > 0 for x in [])  # True

# Useful for "default to true" logic
result = all(condition(x) for x in items)  # True if items is empty
```

## 与 any() 的比较

```python
# all() - True if all are truthy
all([True, True, True])     # True
all([True, False, True])    # False
all([])                     # True

# any() - True if any are truthy
any([False, False, False])  # False
any([False, True, False])   # True
any([])                     # False
```

## 边界情况

### 空可迭代对象

```python
# O(1) - returns True immediately
all([])  # True
all(())  # True
all(set())  # True
all(x for x in [])  # True

# This is mathematically correct (vacuous truth)
# "All members of the empty set satisfy any property"
```

### 单个元素

```python
# O(1) - checks one item
all([True])   # True
all([False])  # False
all([1])      # True - truthy
all([0])      # False - falsy
```

### 不同类型

```python
# O(n) - checks truthiness of any type
all([1, "hello", [1, 2], {"key": "value"}])  # True - all truthy

all([1, "", [1, 2], {"key": "value"}])  # False - "" is falsy
```

## 性能考量

### 与循环的比较

```python
# all() - O(n), optimized, readable
result = all(x > 0 for x in numbers)

# Manual loop - O(n) same complexity
result = True
for x in numbers:
    if not (x > 0):
        result = False
        break

# all() is preferred - cleaner and same performance
```

### 与 any() 的用法选择

```python
# Check if any item fails condition
numbers = [1, 2, 3, 4, 5]

# ✅ Clear intent - all pass condition
all(x > 0 for x in numbers)  # True

# ❌ Confusing - any fail condition
any(not (x > 0) for x in numbers)  # False

# ❌ Confusing - all fail condition
not any(x > 0 for x in numbers)  # False

# Use all() when checking "all meet condition"
# Use any() when checking "any meets condition"
```

## 最佳实践

✅ **推荐**：

- 用 `all()` 检查是否所有元素都满足条件
- 配合生成器表达式实现惰性求值
- 记住 `all([])` 返回 `True`（空真）
- 对开销大的检查利用短路求值

❌ **避免**：

- 用推导式创建列表（应使用生成器）
- 条件中不必要的嵌套
- 只检查单个元素时使用 `all()`

## 相关函数

- **[any()](any.md)** - 检查是否存在为真的元素
- **[filter()](filter.md)** - 按谓词过滤元素
- **[all() with min()](max.md)** - 组合使用操作

## 版本说明

- **Python 2.x**：提供基本功能
- **Python 3.x**：行为相同
- **Python 3.8+**：优化可能提升性能
