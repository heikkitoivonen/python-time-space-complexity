---
source_sha: 4b6b1d20baacc7ebd5dcd5e6e38e7c1696ddd9d11e137a18d4f8963f5672c4c6
translated: machine
---

# any() 函数的复杂度

如果可迭代对象中存在任一为真的元素，`any()` 函数返回 `True`。

`n` 是可迭代对象产出的元素个数，`k` 是第一个真值元素的位置。产出一个元素和判断其真值都按
O(1) 计；对于生成器表达式，表达式本身的工作计入产出该元素的开销。

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
def expensive_function():
    return False

# ✅ O(1) - stops immediately at first truthy
checks = [lambda: True, expensive_function, expensive_function]
result = any(check() for check in checks)
# expensive_function() is never called

# ❌ O(n) - evaluates all
result = any([True] + [expensive_function() for _ in range(1000)])
# Calls expensive_function() 1000 times

# ✅ O(k) - generator stops early
result = any(x > 100 for x in range(10**9))
# Stops after checking 102 items (0 through 101)
```

### 生成器效率

```python
# O(k) - lazy evaluation with early exit
numbers = range(10**6)
result = any(x > 10**5 for x in numbers)
# Stops after checking 10**5 + 2 items

# vs list comprehension - O(n)
result = any([x > 10**5 for x in numbers])
# Builds all 10**6 results first
```

## 常见模式

### 检查值是否存在

```python
# O(k) - stops at first match
items = [1, 2, 3, 4, 5]
result = any(x == 3 for x in items)  # True - stops at 3

# Equivalent to:
result = 3 in items  # O(k) - same scan, more readable
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
numbers = [5, 50, 500, 5000]

# any() - O(k)
result = any(x > 100 for x in numbers)

# Manual loop - O(k) same complexity
result = False
for x in numbers:
    if x > 100:
        result = True
        break

# any() is preferred - same O(k), and shorter
```

### 与 in 运算符的比较

```python
# Check if value exists
items = [1, 2, 3, 4, 5]

# O(k) - early exit
result = any(x == 3 for x in items)

# O(k) - same scan, more readable
result = 3 in items

# any() is useful for complex conditions:
result = any(x > 3 for x in items)  # Condition
words = ["kiwi", "apple", "plum"]
result = any(w.startswith("a") for w in words)  # Complex check
```

### 与 or 运算符的比较

```python
def expensive1():
    return True

def expensive2():
    return False

def expensive3():
    return False

condition1, condition2, condition3 = 0, "yes", None

# Same truthiness as the or-chain below
result = any([condition1, condition2, condition3])  # True

# or returns the first truthy operand itself, not a bool
result = condition1 or condition2 or condition3  # "yes"

# A list is built before any() runs, so every call is made:
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

- **所有 Python 3 版本**：在第一个真值元素处停止，迭代器中其余元素保持未消费
