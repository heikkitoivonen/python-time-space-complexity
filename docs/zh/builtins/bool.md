---
source_sha: f04ebea57c29b2fe7ca41800fa33365218c37847620186e2c9c9aca4bfa1fcc1
translated: machine
---

# 布尔类型的复杂度

`bool` 类型是 `int` 的子类，表示真值：`True` 和 `False`。它们是该类型仅有的两个实例，在比较和算术运算中分别等同于整数 `1` 和 `0`。

操作表中的每个操作在 `bool` 操作数上都是 O(1)，因为它们只取两个固定的值，所以这些行没有规模变量。用于其他操作数时，`and`、`or`、`not` 和 `bool(x)` 还要付出对每个操作数求值的开销，以及对它们所检查的每个操作数进行一次真值测试的开销；对内置类型而言，这次真值测试是 O(1)（参见 [bool()](bool_func.md)）。

## 操作

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `and` | O(1) | O(1) | 短路与 |
| `or` | O(1) | O(1) | 短路或 |
| `not` | O(1) | O(1) | 逻辑非 |
| `==` | O(1) | O(1) | 相等比较 |
| `!=` | O(1) | O(1) | 不等比较 |
| `<`, `>`, `<=`, `>=` | O(1) | O(1) | 数值比较 |
| `&`, `\|`, `^` | O(1) | O(1) | 两个操作数都是 `bool` 时返回 `bool`；不短路 |
| `~x` | O(1) | O(1) | 返回整数 `-2` 或 `-1`，而不是取反结果；自 3.12 起已弃用 |
| `+`, `-`, `*` | O(1) | O(1) | 整数运算；结果是 `int`（`True + True == 2`） |
| `bool(x)` | O(1) | O(1) | `x` 是 `bool` 时返回 `x` 本身 |
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
calls = 0

def expensive_function():
    global calls
    calls += 1
    return True

# 'and' operator - stops at the first falsy operand
x = False and expensive_function()  # expensive_function() NOT called
assert calls == 0
y = True and expensive_function()   # expensive_function() IS called
assert calls == 1

# 'or' operator - stops at the first truthy operand
a = True or expensive_function()    # expensive_function() NOT called
assert calls == 1
b = False or expensive_function()   # expensive_function() IS called
assert calls == 2

# Returns an operand, not necessarily True/False
assert ("hello" or "world") == "hello"
assert ("" or "world") == "world"
assert (5 and 10) == 10
assert (0 and 10) == 0
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
| 自定义对象 | 视情况而定 | 定义了 `__bool__` 就用它，否则用 `__len__`；两者都没有则为真 |

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
# All O(1) - a bool compares as the int 0 or 1
assert True == 1
assert False == 0
assert True > False  # 1 > 0

# Comparisons with other types
assert (True == "True") is False  # a str never equals a number
assert True is True               # the only True object
assert False is False             # the only False object
```

## 常见使用模式

### 条件表达式

```python
condition = True
value_if_true, value_if_false = "yes", "no"

# Simple condition - O(1)
if condition:
    result = value_if_true
else:
    result = value_if_false
assert result == "yes"

# Ternary operator - O(1)
result = value_if_true if condition else value_if_false
assert result == "yes"

# Short-circuit with 'and'/'or' - O(1), but wrong when value_if_true is falsy
result = condition and value_if_true or value_if_false
assert result == "yes"
assert (condition and 0 or "no") == "no"  # not 0
```

### 布尔聚合

n 是条件的个数。

```python
x, y, z = 1, -2, 3

# O(n) worst case - stops at the first false condition (y > 0 here)
if x > 0 and y > 0 and z > 0:
    pass

# O(n) always - the list evaluates every condition before all() sees one
if all([x > 0, y > 0, z > 0]):
    pass

# O(n) worst case - stops at the first true condition (x > 0 here)
if x > 0 or y > 0 or z > 0:
    pass

# O(n) always - the same holds for any() over a list
if any([x > 0, y > 0, z > 0]):
    pass
```

### 数据过滤中的真值判断

```python
# Filter falsy values - O(n) for n items
items = [1, 0, 2, None, 3, "", 4, []]
truthy = [x for x in items if x]  # O(n)
assert truthy == [1, 2, 3, 4]

# Check if all items are truthy - stops at the first falsy item (0 here)
has_all = all(items)
assert has_all is False
```

## 布尔值缓存

`True` 和 `False` 是 `bool` 仅有的两个实例，这一点由语言保证：

```python
# Every bool is one of the two objects
a = True
b = 1 > 0
assert a is b  # same object

# bool() returns one of them, never a new object
assert bool(1) is True
assert bool([]) is False

# But True == 1 and False == 0, as different types
assert True == 1
assert type(True) is not type(1)  # bool, not int
```

## 性能特征

### 短路优化

```python
calls = 0

def expensive_operation():
    global calls
    calls += 1
    return True

# Good: short-circuits prevent function calls
condition = False
result = condition and expensive_operation()  # expensive_operation() NOT called
assert calls == 0

# Bad: always evaluates both sides
result = condition & expensive_operation()    # bitwise AND, not short-circuit
assert calls == 1
```

## 最佳实践

✅ **推荐**：

- 使用短路运算符（`and`、`or`）获得更好性能
- 将 `all()` 和 `any()` 与生成器配合使用，使它们能够提前停止
- 需要时与 `True`/`False` 显式比较
- 简单条件直接依赖真值判断

❌ **避免**：

- `if x == True:`（用 `if x:` 就够了）
- `if x == False:`（用 `if not x:` 就够了）
- 在优先级不清晰时混用 `and`/`or`
- 用位运算符（`&`、`|`）做布尔逻辑——它们会对两边都求值
- 用 `~x` 对布尔值取反——请用 `not x`

## 版本说明

- **Python 2.x**：`bool` 类型于 Python 2.3 引入
- **Python 3.x**：`bool` 始终是 `int` 的子类
- **Python 3.12+**：对 `bool` 使用 `~` 会发出 `DeprecationWarning`
- **所有版本**：`True` 和 `False` 是单例对象

## 相关类型

- **[bool()](bool_func.md)** - 任意对象的真值测试
- **[Int](int.md)** - bool 的父类
- **[None](none.md)** - 在布尔上下文中同样为假
