---
source_sha: e370d4e9ed3bb1f46d4111acfc8084cd2aa8a3c647c5c5a3d1c13b5627850c5d
translated: machine
---

# abs() 函数的复杂度

`abs()` 函数返回数字的绝对值。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 整数 | O(1) | O(1) | 简单的符号判断 |
| 浮点数 | O(1) | O(1) | IEEE 754 符号位操作 |
| 复数 | O(1) | O(1) | 返回复数的模：sqrt(real² + imag²) |
| 自定义类 | O(k) | O(m) | 取决于 `__abs__()` 的实现 |

## 基本用法

### 绝对值

```python
# O(1) - simple arithmetic
abs(-5)        # 5
abs(5)         # 5
abs(0)         # 0
abs(-3.14)     # 3.14
abs(3.14)      # 3.14
```

### 复数

```python
# O(1) - magnitude calculation
abs(3 + 4j)    # 5.0 (sqrt(3^2 + 4^2))
abs(-3 + 4j)   # 5.0
abs(0j)        # 0.0
```

## 自定义 __abs__ 方法

```python
# O(k) where k = __abs__ time
class Distance:
    def __init__(self, value):
        self.value = value
    
    def __abs__(self):
        # O(1) - simple operation
        return abs(self.value)

d = Distance(-10)
result = abs(d)  # 10
```

## 性能模式

### 条件绝对值

```python
# O(1) - all constant time
numbers = [-5, 3, -2, 8, -1]
absolute = [abs(x) for x in numbers]  # O(n) - n simple O(1) operations

# Same with any numeric type
floats = [-1.5, 2.5, -3.5]
absolute = [abs(x) for x in floats]  # O(n)
```

### 距离计算

```python
# O(1) - simple absolute value
def manhattan_distance(x1, y1, x2, y2):
    return abs(x1 - x2) + abs(y1 - y2)

# Usage
dist = manhattan_distance(0, 0, 3, 4)  # 7

# O(n) - for n points
points = [(1, 2), (3, 4), (5, 6)]
distances = [abs(p[0]) + abs(p[1]) for p in points]  # O(n)
```

## 对比替代方案

### abs() vs 手动检查

```python
# abs() - O(1), clear, idiomatic
x = -5
result = abs(x)  # 5

# Manual - O(1), but unnecessary
result = x if x >= 0 else -x  # 5

# abs() is preferred for clarity
```

### abs() vs max()

```python
# Both O(1) for single value
abs(-5)      # 5
max(-5, 5)   # 5

# abs() is more direct for absolute value
# max() is for finding maximum of multiple items
```

## 使用场景

### 计算偏差

```python
# O(n) - find deviation from target
target = 100
values = [95, 102, 98, 105, 99]
deviations = [abs(v - target) for v in values]
# [5, 2, 2, 5, 1]

# Find maximum deviation
max_deviation = max(abs(v - target) for v in values)  # 5
```

### 去除符号

```python
# O(n) - strip negative signs
numbers = [-1, -2, -3, 4, 5]
unsigned = [abs(x) for x in numbers]
# [1, 2, 3, 4, 5]
```

### 比较大小

```python
# O(1) - compare absolute values
a = -5
b = 3

if abs(a) > abs(b):
    print("a has larger magnitude")
```

## 边界情况

### 零

```python
# O(1)
abs(0)      # 0
abs(-0)     # 0
abs(0.0)    # 0.0
abs(-0.0)   # 0.0
```

### 极值

```python
# O(1) - handles large numbers
abs(-10**100)  # Very large positive
abs(-sys.maxsize)  # Minimum integer
```

### 类型转换

```python
# O(1) - works with numeric types
abs(-5)          # int
abs(-5.0)        # float
abs(-5j)         # complex (returns float)

# Not with strings
try:
    abs("-5")  # TypeError
except TypeError:
    pass
```

## 性能说明

```python
# abs() is extremely fast - built-in C function
import timeit

# Timing shows abs() is optimized
t = timeit.timeit(lambda: abs(-5), number=10**7)
# Much faster than manual if/else due to C implementation
```

## 最佳实践

✅ **应该**：

- 使用 `abs()` 获取绝对值
- 在列表推导式中用于批量操作
- 用于距离/大小计算
- 用于偏差分析

❌ **避免**：

- 手动 if/else 检查（可读性差）
- 在 `abs()` 更清晰时使用 `max()`
- 假设类型兼容性

## 相关函数

- **[max()](max.md)** - 查找最大值
- **[min()](min.md)** - 查找最小值
- **[pow()](pow.md)** - 幂函数
- **[math.fabs()](../stdlib/math.md)** - 浮点绝对值

## 版本说明

- **Python 2.x**：基本功能可用
- **Python 3.x**：行为相同
- **Python 3.8+**：性能稳定
