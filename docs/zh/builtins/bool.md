---
source_sha: 3d5cb2671865b2bf90e3ecef25ff9dbbae9a560c590502434e74fc77cbb82b17
translated: machine
---

# 布尔类型的复杂度

`bool` 类型是 `int` 的子类，表示真值：`True` 和 `False`。在 CPython 中，`bool` 是 `int` 的子类型，其中 `True == 1`、`False == 0`。

## 操作

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `and` | O(1) | O(1) | 短路与 |
| `or` | O(1) | O(1) | 短路或 |
| `not` | O(1) | O(1) | 逻辑非 |
| `==` | O(1) | O(1) | 相等比较 |
| `!=` | O(1) | O(1) | 不等比较 |
| `<`, `>`, `<=`, `>=` | O(1) | O(1) | 数值比较 |
| `bool(x)` | O(1) | O(1) | 转换为布尔值 |
| `hash(x)` | O(1) | O(1) | 哈希值 |
| `int(x)` | O(1) | O(1) | 转换为整数 |
| `str(x)` | O(1) | O(1) | 转换为字符串 |

## 逻辑运算

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `x and y` | O(1) | O(1) | 短路：返回第一个假值或最后一个值 |
| `x or y` | O(1) | O(1) | 短路：返回第一个真值或最后一个值 |
| `not x` | O(1) | O(1) | 逻辑取反 |

### 短路求值

```python
# 'and' operator - stops at first False
x = False and expensive_function()  # expensive_function() NOT called
y = True and expensive_function()   # expensive_function() IS called

# 'or' operator - stops at first True
a = True or expensive_function()    # expensive_function() NOT called
b = False or expensive_function()   # expensive_function() IS called

# Returns actual values, not True/False
result = "hello" or "world"         # "hello"
result = "" or "world"              # "world"
result = 5 and 10                   # 10
result = 0 and 10                   # 0
```

## 布尔上下文

| 值 | 布尔上下文 | 备注 |
|-------|-----------------|-------|
| `True` | 真 | |
| `False` | 假 | |
| `0` | 假 | 任何数值零 |
| 非零数值 | 真 | |
| `""`（空字符串） | 假 | |
| 非空字符串 | 真 | |
| `[]`（空列表） | 假 | |
| 非空列表 | 真 | |
| `None` | 假 | |
| 自定义对象 | 视情况而定 | 需实现 `__bool__` 或 `__len__` |

```python
# Truth value testing - O(1) for built-ins
if []:               # False - empty list
    pass
if [1, 2, 3]:        # True - non-empty
    pass
if "":               # False - empty string
    pass
if "hello":          # True - non-empty
    pass
if None:             # False - always
    pass
```

## 比较运算

```python
# All O(1) - True and False are cached singletons, so every comparison
# below is a pointer or small-int check, never a scan
# Bool values are integers: True == 1, False == 0
print(True == 1)     # True
print(False == 0)    # True
print(True > False)  # True (1 > 0)

# Comparisons with other types
print(True == "True")     # False (different types)
print(True is True)       # True (cached singleton)
print(False is False)     # True (cached singleton)
```

## 常见使用模式

### 条件表达式

```python
# Simple condition - O(1)
if condition:
    result = value_if_true
else:
    result = value_if_false

# Ternary operator - O(1)
result = value_if_true if condition else value_if_false

# Short-circuit with 'and'/'or' - O(1)
result = condition and value_if_true or value_if_false
```

### 布尔聚合

```python
# Check if all conditions are true
if x > 0 and y > 0 and z > 0:  # O(n) worst-case (all evaluated)
    pass

# Using all() - O(n) but short-circuits
if all([x > 0, y > 0, z > 0]):
    pass

# Check if any condition is true
if x > 0 or y > 0 or z > 0:   # O(n) worst-case
    pass

# Using any() - O(n) but short-circuits
if any([x > 0, y > 0, z > 0]):
    pass
```

### 数据过滤中的真值判断

```python
# Filter falsy values - O(n) for n items
items = [1, 0, 2, None, 3, "", 4, []]
truthy = [x for x in items if x]  # O(n)
# Result: [1, 2, 3, 4]

# Check if all items are truthy
has_all = all(items)  # O(n) but short-circuits
```

## 布尔值缓存

在 CPython 中，`True` 和 `False` 是单例对象：

```python
# Booleans are cached
a = True
b = True
print(a is b)  # True - same object!

# This is guaranteed by language
print(True is True)   # Always True
print(False is False) # Always True

# But True == 1 and False == 0
print(True == 1)      # True
print(True is 1)      # False - different types
```

## 性能特征

### 布尔运算速度

```python
import timeit

# All boolean operations are very fast - O(1)
timeit.timeit('x = True and False', number=1000000)
timeit.timeit('x = True or False', number=1000000)
timeit.timeit('x = not True', number=1000000)
```

### 短路优化

```python
# Good: short-circuits prevent function calls
condition = False
result = condition and expensive_operation()  # expensive_operation() NOT called

# Bad: always evaluates both sides
result = condition & expensive_operation()    # bitwise AND, not short-circuit
```

## 版本说明

- **Python 2.x**：`bool` 类型于 Python 2.3 引入
- **Python 3.x**：`bool` 始终是 `int` 的子类
- **所有版本**：`True` 和 `False` 是单例对象

## 相关类型

- **[Int](int.md)** - bool 的父类
- **[None](none.md)** - 在布尔上下文中同样为假

## 最佳实践

✅ **推荐**：

- 使用短路运算符（`and`、`or`）获得更好性能
- 对集合使用 `all()` 和 `any()`
- 需要时与 `True`/`False` 显式比较
- 简单条件直接依赖真值判断

❌ **避免**：

- `if x == True:`（用 `if x:` 就够了）
- `if x == False:`（用 `if not x:` 就够了）
- 在优先级不清晰时混用 `and`/`or`
- 用位运算符（`&`、`|`）做布尔逻辑
