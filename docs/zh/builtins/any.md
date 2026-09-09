---
source_sha: 4986cd2cdbf0f4e76eccafca68e381976e54cac8590eba28f052b75e09ace1ad
translated: machine
---

# any() 函数的复杂度

如果可迭代对象中存在任一为真的元素，`any()` 函数返回 `True`。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 第一个元素为真 | O(1) | O(1) | 立即提前退出 |
| 提前退出（发现真值） | O(k) | O(1) | k = 第一个真值的位置 |
| 所有元素均为假 | O(n) | O(1) | 必须检查所有元素 |
| 空可迭代对象 | O(1) | O(1) | 立即返回 False |

## 基本用法

### 检查是否存在真值

```python
# O(k) where k = position of first truthy
numbers = [0, 0, 1, 2, 3]
result = any(numbers)  # True - stops at 1

# Early exit
numbers = [0, 0, 0, 0, 5]
result = any(numbers)  # True - stops at 5

# All falsy - O(n)
result = any([0, False, None, "", []])  # False - checks all
```

### 配合条件使用

```python
# O(k) where k = position of first match, each predicate is O(1)
numbers = [1, 2, 3, 4, 5]
result = any(x > 3 for x in numbers)  # True - stops at 4

# Early exit when condition met
result = any(x > 2 for x in numbers)  # True - stops at 3 (index 2)
```

## 性能模式

### 短路求值

```python
# ✅ O(1) - stops immediately at first truthy
checks = [lambda: True, expensive_function, expensive_function]
result = any(check() for check in checks)
# expensive_function() is never called

# ❌ O(n) - evaluates all
result = any([True] + [expensive_function() for _ in range(1000)])
# Calls expensive_function() 1000 times

# ✅ O(k) - generator stops early
result = any(x > 100 for x in range(10**9))
# Stops after checking 101 items
```

### 生成器效率

```python
# O(k) - lazy evaluation with early exit
large_list = range(10**9)
result = any(x > 10**8 for x in large_list)
# O(10^8) - stops when condition met

# vs list comprehension - O(n)
result = any([x > 10**8 for x in range(10**9)])
# O(10^9) - creates entire list first
```

## 常见模式

### 检查值是否存在

```python
# O(k) - stops at first match
items = [1, 2, 3, 4, 5]
result = any(x == 3 for x in items)  # True - stops at 3

# Equivalent to:
result = 3 in items  # O(k) - same speed, more readable
```

### 带提前退出的校验

```python
# O(k) - stops at the first non-int; O(n) when every item is an int
def has_invalid_item(items):
    return any(not isinstance(item, int) for item in items)

valid = has_invalid_item([1, 2, 3, 4, 5])  # False - checks all
invalid = has_invalid_item([1, 2, "three"])  # True - stops at "three"
```

### 检查条件

```python
# O(k) - stops when condition met
numbers = [2, 4, 6, 8, 10]
has_odd = any(x % 2 == 1 for x in numbers)  # False - checks all

numbers = [2, 4, 5, 8, 10]
has_odd = any(x % 2 == 1 for x in numbers)  # True - stops at 5
```

## 与 all() 的比较

```python
# any() - True if any are truthy
any([False, False, False])  # False
any([False, True, False])   # True
any([])                     # False

# all() - True if all are truthy
all([True, True, True])     # True
all([True, False, True])    # False
all([])                     # True
```

## 边界情况

### 空可迭代对象

```python
# O(1) - returns False immediately
any([])  # False
any(())  # False
any(set())  # False
any(x for x in [])  # False

# This is correct (empty set has no truthy members)
```

### 单个元素

```python
# O(1) - checks one item
any([True])   # True
any([False])  # False
any([1])      # True - truthy
any([0])      # False - falsy
```

### 不同类型

```python
# O(k) - stops at first truthy
any([0, "", None])  # False - all falsy
any([0, "", 1])     # True - stops at 1

any([False, [], {}, "hello"])  # True - stops at "hello"
```

## 性能考量

### 与循环的比较

```python
# any() - O(k), optimized
result = any(x > 100 for x in numbers)

# Manual loop - O(k) same complexity
result = False
for x in numbers:
    if x > 100:
        result = True
        break

# any() is preferred - cleaner and equally fast
```

### 与 in 运算符的比较

```python
# Check if value exists
items = [1, 2, 3, 4, 5]

# O(k) - early exit
result = any(x == 3 for x in items)

# O(k) - faster, more readable
result = 3 in items

# any() is useful for complex conditions:
result = any(x > 3 for x in items)  # Condition
result = any(x.startswith("a") for x in items)  # Complex check
```

### 与 or 运算符的比较

```python
# Short-circuit evaluation works similarly
result = any([condition1, condition2, condition3])

# Equivalent to:
result = condition1 or condition2 or condition3

# But condition1, condition2, condition3 are evaluated before any()
# With any() and generators, short-circuit happens inside:
result = any([expensive1(), expensive2(), expensive3()])  # Evaluates all

# Generator version stops early:
result = any(f() for f in [expensive1, expensive2, expensive3])
```

## 最佳实践

✅ **推荐**：

- 用 `any()` 检查是否有元素满足条件
- 配合生成器表达式实现惰性求值
- 记住 `any([])` 返回 `False`
- 对开销大的检查利用提前退出

❌ **避免**：

- 用推导式创建列表（应使用生成器）
- 当 `in` 运算符更清晰时仍使用 `any()`
- 条件中不必要的嵌套
- 忽略短路求值行为

## 相关函数

- **[all()](all.md)** - 检查是否所有元素都为真
- **[filter()](filter.md)** - 按谓词过滤元素
- **[内置类型总览](index.md)** - 各内置类型中 `in` 的成员测试

## 版本说明

- **Python 2.x**：提供基本功能
- **Python 3.x**：行为相同
- **Python 3.8+**：优化可能提升性能
