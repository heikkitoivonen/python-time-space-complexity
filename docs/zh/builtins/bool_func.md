---
source_sha: 6be1d1f816d9d59ca198a4db6580371a4c2b6387c719cdc4eb1619209bf68b58
translated: machine
---

# bool() 函数的复杂度

`bool()` 函数通过真值判断（truthiness）将对象转换为布尔值。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 转换基本类型（int、str 等） | O(1) | O(1) | 直接取真值 |
| 转换容器 | O(1) | O(1) | 通过 `__len__()` 检查是否非空 |
| 调用 `__bool__()` | O(k) | O(1) | k = 方法的复杂度（通常为 O(1)） |
| 调用 `__len__()` | O(1) | O(1) | 内置容器会缓存长度 |

*注意：对于内置类型（list、dict、set 等），`__len__()` 是 O(1)，因为长度已被缓存。`__len__()` 实现代价高昂的自定义容器会更慢。*

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
# O(m) - depends on __bool__() implementation

class Expensive:
    def __init__(self, data):
        self.data = data
    
    def __bool__(self):
        # O(n) - iterates through data
        return any(self.data)

obj = Expensive([1, 2, 3])
bool(obj)  # O(n) - calls __bool__

# Without __bool__, would use __len__() - O(1)
class Efficient:
    def __init__(self, data):
        self.data = data
    
    def __len__(self):
        # O(1) - quick
        return len(self.data)

obj = Efficient([1, 2, 3])
bool(obj)  # O(1) - calls __len__()
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

# O(1) - all other values are truthy:
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

# Fastest - let Python do implicit bool
if items:              # Best
    pass
```

### 与显式比较的对比

```python
# O(1) - bool conversion
if bool(obj):          # O(1)
    pass

# vs explicit comparison
if obj != None:        # O(1)
    pass

if obj is not None:    # O(1)
    pass

# vs using __len__
if len(obj) > 0:       # O(n) for some types
    pass
```

## 实用示例

### 默认参数处理

```python
# O(1) - check if argument provided
def process(value=None):
    if not value:      # O(1)
        value = default_value
    return value

# With optional list
def extend_list(items=None):
    if not items:      # O(1)
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
if any(items):  # O(1) - first truthy wins
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
bool(0)      # False (exception!)
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
divisor = get_value()

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
- 为自定义类定义 `__bool__()`（不要只定义 `__len__()`）

❌ **避免**：

- 混淆空值与 False：`[]` 和 `False` 都是假值，但二者不同
- 在条件中不必要地使用 `bool()`
- 假设所有假值都是 False
- 复杂的 `__bool__()` 实现（应保持 O(1)）

## 相关函数

- **[all()](all.md)** - 检查是否所有元素均为真值
- **[any()](any.md)** - 检查是否存在为真值的元素
- **[len()](len.md)** - 获取容器长度
- **[bool 类型](bool.md)** - 布尔类型文档

## 版本说明

- **Python 2.x**：使用 `__nonzero__()` 而非 `__bool__()`
- **Python 3.x**：使用 `__bool__()` 方法
- **所有版本**：假值保持一致（None、False、0、""、[]、{} 等）
