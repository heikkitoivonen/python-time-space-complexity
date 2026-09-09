---
source_sha: 1603bba545d860caf2e3fa43aa74bee5a44ca2d8e4a601ff3b157835354865ba
translated: machine
---

# bin() 函数的复杂度

`bin()` 函数返回整数的二进制表示形式。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 转换整数 | O(log n) | O(log n) | n = 整数值；log n = 位数 |
| 负整数 | O(log n) | O(log n) | 添加 '-0b' 前缀 |
| 大整数 | O(b) | O(b) | b = 位数 = log₂(n) |

*注：复杂度为 O(log n)，其中 n 是数值大小，它等于表示该数所需的位数。*

## 基本用法

### 十进制转二进制

```python
# O(log n) - where n = integer value
bin(0)      # '0b0'
bin(1)      # '0b1'
bin(2)      # '0b10'
bin(3)      # '0b11'
bin(8)      # '0b1000'
bin(255)    # '0b11111111'
```

### 负数

```python
# O(log n) - shows magnitude with minus
bin(-1)     # '-0b1'
bin(-8)     # '-0b1000'
bin(-255)   # '-0b11111111'
```

### 大整数

```python
# O(log n) - number of binary digits
bin(2**10)    # '0b10000000000'
bin(2**32)    # '0b100000000000000000000000000000000'

# Arbitrary precision
big = 2**100
bin(big)  # O(100) - 100+ binary digits
```

## 复杂度细节

### 对数时间

转换时间随位数增长：

```python
# Small number - few bits
bin(3)      # '0b11' - 2 bits, O(log 3) = O(2)

# Large number - many bits
bin(2**64 - 1)  # 64 bits
                # O(log(2**64)) = O(64)

# Relationship: binary digits = log₂(n)
import math
value = 255
digits = len(bin(value)) - 2  # Subtract '0b'
assert digits == value.bit_length()
```

## 常见模式

### 位操作

```python
# O(log n) - understand bit patterns
x = 42
print(bin(x))  # '0b101010'

# Check individual bits
def has_bit_set(value, bit_pos):
    return bool(value & (1 << bit_pos))

value = 0b1010  # 10 in decimal
print(has_bit_set(value, 0))  # False (bit 0)
print(has_bit_set(value, 1))  # True (bit 1)
```

### 调试位运算

```python
# O(log n) - show results clearly
a = 0b1100
b = 0b1010

print(f"a = {bin(a)}")           # a = 0b1100
print(f"b = {bin(b)}")           # b = 0b1010
print(f"a & b = {bin(a & b)}")   # a & b = 0b1000
print(f"a | b = {bin(a | b)}")   # a | b = 0b1110
print(f"a ^ b = {bin(a ^ b)}")   # a ^ b = 0b0110
print(f"~a = {bin(~a)}")         # ~a = -0b1101
```

### 二进制字符串转整数

```python
# O(log n) - parse binary string
binary_str = "0b1010"
value = int(binary_str, 2)  # O(log n)
assert value == 10

# Without prefix
value = int("1010", 2)  # Also O(log n)
assert value == 10
```

## 位操作运算

```python
# All O(1) in Python (fixed size, usually)
x = 0b1100  # 12
y = 0b1010  # 10

# Bitwise AND
result = x & y  # 0b1000 (8)
print(bin(result))  # '0b1000'

# Bitwise OR
result = x | y  # 0b1110 (14)
print(bin(result))  # '0b1110'

# Bitwise XOR
result = x ^ y  # 0b0110 (6)
print(bin(result))  # '0b110'

# Bitwise NOT (inverts all bits)
result = ~x     # -(13) due to two's complement
print(bin(result))  # '-0b1101'

# Left shift
result = x << 2  # 0b110000 (48)
print(bin(result))  # '0b110000'

# Right shift
result = x >> 1  # 0b110 (6)
print(bin(result))  # '0b110'
```

## 性能模式

### 批量转换

```python
# O(n * log m) - n numbers, each ~m value
numbers = list(range(100))
binary_values = [bin(n) for n in numbers]
# O(100 * log 100)

# vs direct method
binary_values = [f"{n:b}" for n in numbers]
# Similar, might be slightly faster with format
```

### 统计置位数

```python
# O(log n) - using bin()
def count_bits_bin(value):
    return bin(value).count('1')

# Better - O(1) with bit_count()
def count_bits_optimal(value):
    return value.bit_count()  # Python 3.10+

# Both give same result, bit_count() is faster
assert count_bits_bin(0b101010) == count_bits_optimal(0b101010)
```

## 实用示例

### 权限标志位

```python
# O(log n) - display permission bits
READ = 0b100
WRITE = 0b010
EXECUTE = 0b001

permissions = READ | WRITE  # 0b110 (read + write)
print(bin(permissions))      # '0b110'

# Check if permission set
has_read = bool(permissions & READ)
has_write = bool(permissions & WRITE)
has_execute = bool(permissions & EXECUTE)
```

### IP 地址操作

```python
# O(log n) - work with IP octets
ip = "192.168.1.1"
octets = [int(x) for x in ip.split('.')]

# Show first octet in binary
print(bin(octets[0]))  # '0b11000000' (192)

# Network mask
mask = 0b11111111_11111111_11111111_00000000  # /24
print(bin(mask))
```

### 用位做集合运算

```python
# O(log n) - use integers as efficient sets
SET_SIZE = 8  # Can represent 0-7

# Add elements (set bits)
my_set = 0  # Empty set
my_set |= (1 << 3)  # Add 3
my_set |= (1 << 5)  # Add 5

print(bin(my_set))  # '0b101000'

# Check membership
print(bool(my_set & (1 << 3)))  # True (has 3)
print(bool(my_set & (1 << 2)))  # False (no 2)

# Remove element (clear bit)
my_set &= ~(1 << 3)
print(bin(my_set))  # '0b100000'
```

## 最佳实践

✅ **推荐**：

- 调试位运算时使用 `bin()`
- 不需要 '0b' 前缀时使用 `format(value, 'b')`
- 计数用 `bit_length()` 或 `bit_count()`
- 解析二进制用 `int(binary_str, 2)`

❌ **避免**：

- 极高频操作中使用 `bin()`（应缓存结果）
- 想当然地认为二进制操作比普通操作更快
- 不理解转换原理就用十进制拼二进制
- 用 `int()` 解析时忘记 '0b' 前缀

## 相关函数

- **[hex()](hex.md)** - 十六进制表示形式
- **[oct()](oct.md)** - 八进制表示形式
- **[int().bit_length()](int.md)** - 所需的位数
- **[int().bit_count()](int.md)** - 统计置位数（Python 3.10+）
- **[format()](format.md)** - 按规格格式化

## 版本说明

- **Python 2.x**：适用于 int 和 long
- **Python 3.x**：适用于任意精度整数
- **Python 3.10+**：新增 `int.bit_count()` 用于位计数
- **所有版本**：返回带 '0b' 前缀的字符串
