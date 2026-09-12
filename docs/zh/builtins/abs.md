---
source_sha: c418fa09ab8f6b63a6787718bcf0d678e3e9360b15bd8666421a91b2daf2aec5
translated: machine
---

# abs() 函数的复杂度

`abs()` 函数返回数字的绝对值。它调用操作数的 `__abs__()`，因此成本取决于操作数的类型：
`float` 或 `complex` 为常数时间，负 `int` 则与其位宽成线性关系。

## 复杂度分析

对于整数操作数，设 `d` 为其数字位数，与 `x.bit_length()` 成正比。空间不包括操作数本身。

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 非负 `int` | O(1) | O(1) | 返回 `x` 本身；继承 `__abs__` 的 `int` 子类会被复制为普通 `int`，O(d) |
| 负 `int` | O(d) | O(d) | 逐位复制并翻转符号 |
| `float` | O(1) | O(1) | 清除符号位并生成新的 `float`，与数值大小无关 |
| `complex` | O(1) | O(1) | 以 `float` 返回模；有限的实部和虚部得到的模超出浮点范围时抛出 `OverflowError` |
| 其他任意类型 | `type(x).__abs__` | — | `Fraction`、`Decimal` 等均委托给该类型；没有 `__abs__` 的类型抛出 `TypeError` |

## 基本用法

### 绝对值

```python
# O(1) - a machine-word int or a float
abs(-5)        # 5
abs(5)         # 5
abs(0)         # 0
abs(-3.14)     # 3.14
abs(3.14)      # 3.14
```

### 复数

```python
# O(1) - the magnitude, computed as hypot(real, imag)
abs(3 + 4j)    # 5.0
abs(-3 + 4j)   # 5.0
abs(0j)        # 0.0

# hypot() does not square the parts first, so this stays finite
abs(1e200 + 1e200j)   # 1.414213562373095e+200

# Only the magnitude itself can overflow
try:
    abs(1.5e308 + 1.5e308j)
except OverflowError:
    pass       # absolute value too large
```

### 大整数

```python
# O(1) - a non-negative int comes back as the same object
big = 10**100
abs(big) is big        # True

# O(d) - a negative int is copied, digit by digit
abs(-big)              # 10**100, a new object
```

## 自定义 __abs__ 方法

```python
# The cost is whatever __abs__ costs; abs() adds one call
class Distance:
    def __init__(self, value):
        self.value = value

    def __abs__(self):
        # O(1) for a machine-word value
        return abs(self.value)

d = Distance(-10)
result = abs(d)  # 10
```

## 性能模式

### 批量绝对值

```python
# O(n) - n items, each O(1) for a machine-word int
numbers = [-5, 3, -2, 8, -1]
absolute = [abs(x) for x in numbers]

# Same with any numeric type
floats = [-1.5, 2.5, -3.5]
absolute = [abs(x) for x in floats]  # O(n)
```

### 距离计算

```python
# O(1) for machine-word coordinates - two subtractions and two absolute values
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
# abs() - clear, idiomatic
x = -5
result = abs(x)  # 5

# Manual - the same work: -x copies a negative int exactly as abs() does
result = x if x >= 0 else -x  # 5
```

两种写法的复杂度界相同：对负 `int`，`-x` 与 `abs()` 做的是同一次复制。`abs()` 更清晰，也适用于任何实现了 `__abs__()` 的类型，因此更推荐使用。

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
# O(1) - a negative zero float loses its sign
abs(0)      # 0
abs(-0)     # 0
abs(0.0)    # 0.0
abs(-0.0)   # 0.0
```

### 极值

```python
import sys

# O(d) - the negative value is copied; ints do not overflow
abs(-10**100)          # 10**100
abs(-sys.maxsize - 1)  # sys.maxsize + 1

# O(1) - a float's magnitude does not change the cost
abs(-1.7e308)          # 1.7e308
```

### 类型转换

```python
# int and float keep their type; complex gives a float
abs(-5)          # int
abs(-5.0)        # float
abs(-5j)         # 5.0, a float

# A str has no __abs__
try:
    abs("-5")
except TypeError:
    pass         # bad operand type for abs(): 'str'
```

## 最佳实践

✅ **应该**：

- 使用 `abs()` 获取绝对值
- 在列表推导式中用于批量操作
- 用于距离/大小计算
- 用于偏差分析

❌ **避免**：

- 手动 if/else 检查（可读性差，复杂度界也相同）
- 假设类型兼容性

## 相关函数

- **[int](int.md)** - 任意精度整数运算，包括 `-x`
- **[max()](max.md)** - 查找最大值
- **[min()](min.md)** - 查找最小值
- **[pow()](pow.md)** - 幂函数
- **[math.fabs()](../stdlib/math.md)** - 浮点绝对值
