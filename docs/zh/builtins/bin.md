---
source_sha: f16060676aa9f2d794dfc1aee469b127e4b49ebc0c00e56f8cec60ab0149c663
translated: machine
---

# bin() 函数的复杂度

`bin()` 函数返回整数的二进制表示形式。
它为每个二进制位写出一个字符，因此其耗时和所返回字符串的大小都与该整数的位数成线性关系。

`n` 是该整数的绝对值，`b` 是结果中的二进制位数：即 `n.bit_length()`，约为 log₂ n；对零而言为 1。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 转换整数 | O(log n) | O(log n) | O(b)：每个二进制位一个字符 |
| 负整数 | O(log n) | O(log n) | 添加 '-0b' 前缀 |
| 大整数 | O(b) | O(b) | 不受 `sys.set_int_max_str_digits()` 限制，该限制不适用于 2 的幂次进制 |
| 带 `__index__` 的对象 | `__index__` + O(b) | `__index__` + O(b) | 其他非整数（如浮点数）会引发 `TypeError` |

## 基本用法

### 十进制转二进制

```python
# O(log n)
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
bin(big)  # O(b) - b = 101 binary digits
```

## 复杂度细节

### 对数时间

转换时间随位数增长：

```python
# Small number - few bits
bin(3)      # '0b11' - b = 2

# Large number - many bits
bin(2**64 - 1)  # b = 64

# Relationship: binary digits = bit_length()
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
x = 0b1100
y = 0b1010

print(f"x = {bin(x)}")           # x = 0b1100
print(f"y = {bin(y)}")           # y = 0b1010
print(f"x & y = {bin(x & y)}")   # x & y = 0b1000
print(f"x | y = {bin(x | y)}")   # x | y = 0b1110
print(f"x ^ y = {bin(x ^ y)}")   # x ^ y = 0b110
print(f"~x = {bin(~x)}")         # ~x = -0b1101
```

### 二进制字符串转整数

```python
# Linear in the string's length - parse binary string
binary_str = "0b1010"
value = int(binary_str, 2)  # O(len(binary_str))
assert value == 10

# Without prefix
value = int("1010", 2)  # Also linear in the length
assert value == 10
```

## 位操作运算

```python
# bin() shows the result of each bitwise operator
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
# O(k * b) - k numbers of up to b bits each
numbers = list(range(100))
binary_values = [bin(n) for n in numbers]
# k = 100, b = 7

# vs direct method
binary_values = [f"{n:b}" for n in numbers]
# Same digits, without the '0b' prefix
```

### 统计置位数

```python
# O(b) - builds a string of b + 2 or more characters, then scans it
def count_bits_bin(value):
    return bin(value).count('1')

# Better - also O(b), but builds no string
def count_bits_optimal(value):
    return value.bit_count()

# Both give the same result
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
- 用普通的 `int(s)` 解析 `bin()` 的输出，它不接受 '0b' 前缀；应使用 `int(s, 2)` 或 `int(s, 0)`

## 版本说明

- **Python 3.10+**：新增 `int.bit_count()` 用于位计数
- **所有 Python 3 版本**：`bin(x)` 返回带 '0b' 前缀的字符串，负数则为 '-0b'，并接受任何带 `__index__` 的对象

## 相关函数

- **[hex()](hex.md)** - 十六进制表示形式
- **[oct()](oct.md)** - 八进制表示形式
- **[int().bit_length()](int.md)** - 所需的位数
- **[int().bit_count()](int.md)** - 统计置位数（Python 3.10+）
- **[format()](format.md)** - 按规格格式化
