---
source_sha: ea4f8b32c47a9951d364d070e44ddc25ab93c4bb79e0e11e0590f61fa3c0e688
translated: machine
---

# 字符串操作的复杂度

`str` 类型是不可变的 Unicode 字符序列。Python 的字符串经过大量优化，在 Python 3 中尤为明显。

## 复杂度参考

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 直接查询 |
| `access[i]` | O(1) | O(1) | 直接索引 |
| `in` (substring) | O(n + m) avg | O(1) | CPython 中使用 Two-Way / fastsearch 算法 |
| `s + s` (concatenation) | O(n+m) | O(n+m) | 创建新字符串 |
| `s * n` (repetition) | O(n\*len(s)) | O(n\*len(s)) | 创建新字符串 |
| `slice [::2]` | O(k) | O(k) | k = 切片长度 |
| **查找** ||||
| `find(sub)` | O(n + m) avg | O(1) | CPython 中使用 Two-Way / fastsearch 算法 |
| `rfind(sub)` | O(n*m) worst | O(1) | 使用反向 Boyer-Moore-Horspool 算法 |
| `index(sub)` | O(n + m) | O(1) | 与 find() 相同，但找不到时抛出 ValueError |
| `rindex(sub)` | O(n*m) worst | O(1) | 与 rfind() 相同，但找不到时抛出 ValueError |
| `count(sub)` | O(n + m) avg | O(1) | n = 字符串，m = 子串 |
| `startswith(prefix)` | O(m) | O(1) | m = 前缀长度 |
| `endswith(suffix)` | O(m) | O(1) | m = 后缀长度 |
| **替换与转换** ||||
| `replace(old, new)` | O(n) | O(n) | 单次遍历 |
| `translate(table)` | O(n) | O(n) | 单次遍历，配合表查找 |
| `maketrans()` | O(k) | O(k) | k = 映射数量；静态方法 |
| `expandtabs(tabsize)` | O(n) | O(n) | 用空格替换制表符 |
| `removeprefix(prefix)` | O(n) | O(n) | 前缀匹配时返回切片 |
| `removesuffix(suffix)` | O(n) | O(n) | 后缀匹配时返回切片 |
| **拆分与拼接** ||||
| `split(sep)` | O(n) | O(n) | 单次遍历 |
| `rsplit(sep)` | O(n) | O(n) | 从右侧拆分 |
| `splitlines()` | O(n) | O(n) | 按行边界拆分 |
| `partition(sep)` | O(n) | O(n) | 在第一个分隔符处拆成三元组 |
| `rpartition(sep)` | O(n) | O(n) | 在最后一个分隔符处拆成三元组 |
| `join(iterable)` | O(n) | O(n) | n = 输出字符总数 |
| **大小写转换** ||||
| `upper()` | O(n) | O(n) | 需要处理每个字符 |
| `lower()` | O(n) | O(n) | 需要处理每个字符 |
| `capitalize()` | O(n) | O(n) | 首字母大写，其余小写 |
| `title()` | O(n) | O(n) | 每个单词首字母大写 |
| `swapcase()` | O(n) | O(n) | 互换大小写 |
| `casefold()` | O(n) | O(n) | 更彻底的小写转换，用于忽略大小写的匹配 |
| **去除空白** ||||
| `strip(chars)` | O(n) | O(n) | 从两端移除 |
| `lstrip(chars)` | O(n) | O(n) | 从左端移除 |
| `rstrip(chars)` | O(n) | O(n) | 从右端移除 |
| **填充与对齐** ||||
| `center(width)` | O(n) | O(n) | 两侧填充 |
| `ljust(width)` | O(n) | O(n) | 右侧填充 |
| `rjust(width)` | O(n) | O(n) | 左侧填充 |
| `zfill(width)` | O(n) | O(n) | 用零填充 |
| **判定方法** ||||
| `isalnum()` | O(n) | O(1) | 检查是否为字母或数字 |
| `isalpha()` | O(n) | O(1) | 检查是否为字母 |
| `isascii()` | O(n) | O(1) | 检查是否为 ASCII（Python 3.7+） |
| `isdecimal()` | O(n) | O(1) | 检查是否为十进制数字字符 |
| `isdigit()` | O(n) | O(1) | 检查是否为数字字符 |
| `isidentifier()` | O(n) | O(1) | 检查是否为合法标识符 |
| `islower()` | O(n) | O(1) | 检查是否为小写 |
| `isnumeric()` | O(n) | O(1) | 检查是否为数值字符 |
| `isprintable()` | O(n) | O(1) | 检查是否可打印 |
| `isspace()` | O(n) | O(1) | 检查是否为空白字符 |
| `istitle()` | O(n) | O(1) | 检查是否为标题格式 |
| `isupper()` | O(n) | O(1) | 检查是否为大写 |
| **格式化** ||||
| `format(*args)` | O(n) | O(n) | n = 模板长度 |
| `format_map(mapping)` | O(n) | O(n) | 与 format() 相同，但接受映射 |
| **编码** ||||
| `encode(encoding)` | O(n) | O(n) | 转换为字节 |

## 实现细节

### 字符串驻留

```python
# Small strings and identifiers are interned (reused)
s1 = "hello"
s2 = "hello"
print(s1 is s2)  # Likely True - same object

# Large strings are not interned
s3 = "x" * 1000
s4 = "x" * 1000
print(s3 is s4)  # False - different objects
```

### Python 3 的 Unicode 优化

```python
# Python 3 uses adaptive string representation
# ASCII strings use less memory than full Unicode

# Compact representation for ASCII
s = "hello"  # Uses 1 byte per character

# Full Unicode representation
s = "hello 世界"  # Uses more bytes for non-ASCII
```

### 字符串拼接的性能

```python
# Inefficient: O(n²) - creates new strings repeatedly
result = ""
for i in range(10000):
    result += str(i)  # Copies entire string each time

# Efficient: O(n) - single allocation
result = "".join(str(i) for i in range(10000))
```

## 进阶特性

### 子串查找

```python
# Linear time on average for substring search
s = "a" * 1000000 + "b"
result = s.find("b")  # Usually O(n) avg, not O(n²)

# CPython uses optimized algorithms (similar to Boyer-Moore)
```

## 版本说明

| 版本 | 变化 |
|---------|--------|
| Python 3.0+ | 默认使用 Unicode |
| Python 3.3+ | 灵活的字符串表示（PEP 393） |
| Python 3.8+ | f-string 性能改进 |
| Python 3.11+ | 字符串操作更快，内联更好 |

## 各实现对比

### CPython
高度优化，具备字符串驻留和灵活的表示方式。

### PyPy
JIT 编译为重复操作提供额外优化。

### Jython
底层为 Java 字符串，性能特性类似。

## 最佳实践

✅ **推荐**：

- 用 `str.join()` 合并多个字符串
- 使用 f-string 做格式化（Python 3.6+）
- 用 `in` 检查子串（平均 O(n)）
- 用 `.find()` 和 `.replace()` 做高效处理

❌ **避免**：

- 在循环中用 `+` 拼接字符串
- 反复调用 `.replace()` —— 一次完成或改用正则
- 在嵌套循环中用 `in` 做成员检测却不做缓存
- 创建大量中间字符串对象

## 常见用法

### 高效构建字符串

```python
# Bad: O(n²)
result = ""
for word in words:
    result += word

# Good: O(n)
result = "".join(words)

# Also good: list comprehension with join
result = "".join([w.upper() for w in words])
```

### 字符串格式化

```python
# Python 3.6+ f-strings (preferred)
name = "World"
message = f"Hello, {name}!"  # Efficient and readable

# Older style (still works)
message = "Hello, {}!".format(name)

# Avoid %
message = "Hello, %s!" % name
```

### 模式匹配

```python
# Use str methods for simple patterns
if s.startswith("test_"):  # O(m) where m = prefix length
    pass

# Use regex for complex patterns
import re
pattern = re.compile(r"test_\d+")  # Compile once
if pattern.match(s):  # Reuse compiled pattern
    pass
```

## 相关类型

- **[Bytes](bytes_func.md)** - 不可变的字节序列
- **[Bytearray](bytearray_func.md)** - 可变的字节序列
- **[正则表达式 (re)](../stdlib/re.md)** - 模式匹配

## 延伸阅读

- [CPython Internals: str](https://zpoint.github.io/CPython-Internals/BasicObject/str/str.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的字符串实现
