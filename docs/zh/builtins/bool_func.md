---
source_sha: ad95cb242f5e6951b808e6e7ab7ff7d86f11a196210e1d2e406ba286915af9cd
translated: machine
---

# bool() 函数的复杂度

`bool()` 函数通过真值判断（truthiness）将对象转换为布尔值。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 转换数字（int、float、complex） | O(1) | O(1) | 判断是否为零；不随数值大小增长 |
| 转换内置容器（str、list、dict、set、range 等） | O(1) | O(1) | 根据已存储的长度判断是否为空；不逐个计数元素 |
| 定义了 `__bool__()` 的类 | O(k) | O(1) | k = `__bool__()` 的开销（通常为 O(1)）；不会调用 `__len__()` |
| 只定义了 `__len__()` 的类 | O(k) | O(1) | k = `__len__()` 的开销 |
| 两者都未定义的类 | O(1) | O(1) | 总是 `True` |

`bool()` 至多调用一次 `__bool__()` 或 `__len__()`，自定义方法本身的时间和空间开销要另外加到对应行上。
结果是 `True` 和 `False` 这两个单例之一，因此不会为结果分配任何内存。

## 基本用法

### 布尔值

```python
# O(1) - direct conversion
bool(True)   # True
bool(False)  # False
```

### 整数与浮点数

```python
# O(1) - zero/non-zero check
bool(0)      # False
bool(1)      # True
bool(-1)     # True
bool(0.0)    # False
bool(3.14)   # True
```

### 字符串

```python
# O(1) - empty/non-empty check
bool("")     # False (empty string)
bool("a")    # True (non-empty)
bool("0")    # True (non-empty, not zero!)
```

### 容器

```python
# O(1) - check if empty (uses __len__)
bool([])           # False
bool([1, 2, 3])    # True
bool({})           # False
bool({"a": 1})     # True
bool(set())        # False
bool({1, 2})       # True
bool(())           # False
bool((1, 2))       # True
```

### None

```python
# O(1) - None is always falsy
bool(None)  # False
```

## 复杂度细节

### 容器真值判断

```python
# O(1) - uses __bool__() or __len__()
# Python checks for __bool__() first, then __len__()

class CustomClass:
    def __init__(self, size):
        self.size = size
    
    def __len__(self):
        # O(1) - just return stored size
        return self.size

obj = CustomClass(0)
bool(obj)  # False - calls __len__(), returns 0

obj = CustomClass(5)
bool(obj)  # True - calls __len__(), returns 5
```

### 自定义 `__bool__()` 方法

```python
# O(k) - depends on __bool__() implementation

class Expensive:
    def __init__(self, data):
        self.data = data
    
    def __bool__(self):
        # O(n) worst case - any() stops at the first truthy item
        return any(self.data)

obj = Expensive([0, 0, 0])
bool(obj)  # False - O(n), all three items checked

# Without __bool__, __len__() decides - O(1) for a list
# It answers a different question: non-empty, not "any item truthy"
class Efficient:
    def __init__(self, data):
        self.data = data
    
    def __len__(self):
        # O(1) - quick
        return len(self.data)

obj = Efficient([0, 0, 0])
bool(obj)  # True - O(1), calls __len__()
```

## 真值判断规则

```python
# O(1) - these are always falsy:
bool(None)      # False
bool(False)     # False
bool(0)         # False
bool(0.0)       # False
bool(0j)        # False (complex)
bool("")        # False (empty string)
bool([])        # False (empty list)
bool({})        # False (empty dict)
bool(set())     # False (empty set)
bool(())        # False (empty tuple)
bool(range(0))  # False (empty range)

# O(1) - these values are truthy:
bool(True)      # True
bool(1)         # True
bool(-1)        # True
bool(0.1)       # True
bool("0")       # True (non-empty!)
bool([0])       # True (non-empty!)
bool([None])    # True (non-empty!)
bool([False])   # True (non-empty!)
```

## 常见模式

### 条件检查

```python
# O(1) - implicit bool conversion
def process(items):
    return len(items)

items = []

if items:           # O(1) - checks truthiness
    process(items)

# Explicit conversion
if bool(items):     # O(1) - same thing
    process(items)

# More Pythonic - just use implicit
if items:           # Preferred
    process(items)
```

### 取反

```python
# O(1) - logical not
not True    # False
not False   # True

# With objects
items = []
if not items:  # O(1) - equivalent to if len(items) == 0
    print("empty")
```

### 按真值过滤

```python
# O(n) - check each item
items = [0, 1, "", "hello", [], [1], None, False, True]

# Remove falsy values - O(n)
truthy_items = [x for x in items if x]
# [1, "hello", [1], True]

# Using filter - O(n)
truthy_items = list(filter(bool, items))
# Same result, O(n)
```

### 布尔列表

```python
# O(n) - convert each element
values = [0, 1, 2, 3, 0, 5]
bools = [bool(x) for x in values]
# [False, True, True, True, False, True]

# Using map - O(n)
bools = list(map(bool, values))
# Same result
```

## 性能模式

### 检查容器是否为空

```python
# All O(1) with __len__
items = [1, 2, 3]

if items:              # O(1) - uses __len__()
    pass

if len(items) > 0:     # O(1) - explicit
    pass

if len(items) != 0:    # O(1) - also explicit
    pass

# Idiomatic - let Python do implicit bool
if items:              # Best
    pass
```

### 与显式比较的对比

```python
obj = [1, 2, 3]

# Truthiness - O(1) for built-in types, else __bool__() or __len__()
if obj:
    pass

# None check - O(1) for any type, but a different question:
# an empty list is not None
if obj is not None:
    pass

# len() - for a type with no __bool__(), the same __len__() call
# that `if obj:` makes
if len(obj) > 0:
    pass
```

## 实用示例

### 默认参数处理

```python
# O(1) - check if argument provided
default_value = 10

def process(value=None):
    if value is None:  # O(1)
        value = default_value
    return value

process(0)  # 0 - `if not value:` would replace it with 10

# With optional list
def extend_list(items=None):
    if items is None:  # O(1)
        items = []
    return items
```

### 校验

```python
# O(1) - check required fields
def validate_data(data):
    if not data:       # O(1) - check if dict is empty
        raise ValueError("Data required")
    
    required_fields = ["id", "name"]
    for field in required_fields:
        if not data.get(field):  # O(1) - get and check
            raise ValueError(f"{field} required")
```

### 布尔聚合

```python
# O(n) - check multiple conditions
items = [1, 2, 3, 4, 5]

# Check if any item is truthy (short-circuits)
if any(items):  # Stops at the first truthy item - here the first
    pass

# Check if all items are truthy
if all(items):  # O(n) - checks all
    pass

# With conditions
if any(x > 10 for x in items):  # O(n) or early exit
    pass

if all(x > 0 for x in items):   # O(n) or early exit
    pass
```

## 边界情况

### 空值、None 与 False 的区别

```python
# All falsy, but different
bool(None)   # False - no value
bool([])     # False - empty container
bool(False)  # False - explicit false
bool("")     # False - empty string

# All truthy
bool([0])    # True - non-empty
bool([None]) # True - non-empty
bool([False])# True - non-empty
```

### 自定义假值对象

```python
# O(1) - return False from __bool__
class AlwaysFalse:
    def __bool__(self):
        return False

obj = AlwaysFalse()
bool(obj)  # False

# But object exists
if obj:    # False
    pass

if obj is not None:  # True - object exists!
    pass
```

### 除零检查

```python
# O(1) - check for zero before division
divisor = 4

if divisor:  # O(1) - checks if non-zero
    result = 100 / divisor
else:
    result = None

# vs explicit check
if divisor != 0:     # O(1)
    result = 100 / divisor
```

## 最佳实践

✅ **应该**：

- 使用隐式真值判断：`if items:` 而非 `if len(items) > 0:`
- 显式检查 `is None`：`if value is None:` 而非 `if not value:`
- 需要显式布尔值时使用 `bool()` 转换
- 如果类的 `__len__()` 代价高昂，为它定义 `__bool__()`，这样真值判断就不必调用 `__len__()`

❌ **避免**：

- 混淆空值与 False：`[]` 和 `False` 都是假值，但二者不同
- 在条件中不必要地使用 `bool()`
- 假设所有假值都是 False
- 复杂的 `__bool__()` 实现（应保持 O(1)）

## 版本说明

- **Python 2.x**：使用 `__nonzero__()` 而非 `__bool__()`
- **Python 3.x**：使用 `__bool__()` 方法
- **Python 3.14+**：`bool(NotImplemented)` 会引发 `TypeError`；3.10 至 3.13 返回 `True` 并发出 `DeprecationWarning`
- **所有版本**：假值保持一致（None、False、0、""、[]、{} 等）

## 相关函数

- **[all()](all.md)** - 检查是否所有元素均为真值
- **[any()](any.md)** - 检查是否存在为真值的元素
- **[len()](len.md)** - 获取容器长度
- **[bool 类型](bool.md)** - 布尔类型文档
