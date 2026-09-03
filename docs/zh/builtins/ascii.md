---
source_sha: f3da73a0aa7274df261f80a8ebb8ec4e8e71890246b89496a5a34ba9d6daab50
translated: machine
---

# ascii() 函数的复杂度

`ascii()` 函数返回对象的可打印表示形式，其中非 ASCII 字符会被转义。

## 复杂度分析

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| ASCII 字符串 | O(n) | O(n) | n = 字符串长度 |
| Unicode 字符串 | O(n) | O(n) | 非 ASCII 字符被转义 |
| 容器 | O(n) | O(n) | 递归转义其中的内容 |
| 自定义对象 | O(1)* | O(1)* | 取决于 `__repr__` |

## 基本用法

### ASCII 字符串

```python
# O(n) - where n = string length
ascii("hello")       # "'hello'"
ascii("Python")      # "'Python'"
ascii("123")         # "'123'"
```

### Unicode 字符串

```python
# O(n) - non-ASCII characters escaped
ascii("café")        # "'caf\\xe9'"
ascii("🎵")         # "'\\U0001f3b5'"
ascii("Ñoño")        # "'\\xd1o\\xf1o'"
ascii("日本語")       # "'\\u65e5\\u672c\\u8a9e'"
```

### 混合内容

```python
# O(n) - escapes all non-ASCII
text = "Hello, 世界"
ascii(text)  # "'Hello, \\u4e16\\u754c'"

# Each Unicode character escaped to \uXXXX or \UXXXXXXXX
```

## 复杂度细节

### 字符转义

```python
# O(n) - linear in string length
# Each character may expand to multiple chars

# Short ASCII
ascii("abc")  # O(3)

# Long ASCII
ascii("a" * 1000)  # O(1000)

# Unicode requiring escaping
ascii("é" * 100)   # O(100) - each é becomes \xé9 (5 chars)
```

### 转义序列

```python
# ASCII characters - no change
# Extended ASCII (127-255) - use \xHH format (4 chars total)
ascii("\xe9")  # "'\\xe9'" - é in Latin-1

# Unicode (>255) - use \uHHHH format (6 chars total)
ascii("\u0101")  # "'\\u0101'" - ā (a with macron)

# High Unicode - use \UHHHHHHHH format (10 chars total)
ascii("\U0001f600")  # "'\\U0001f600'" - 😀 emoji
```

## 常见模式

### 调试非 ASCII 内容

```python
# O(n) - show hidden non-ASCII characters
text = "Hello\nWorld\t!"
print(ascii(text))
# Output: 'Hello\\nWorld\\t!'

# vs str/repr
print(str(text))    # Shows actual newlines/tabs
print(repr(text))   # Shows escapes but uses non-ASCII if present

# ascii() always shows escapes
text_unicode = "Héllo"
print(repr(text_unicode))   # "'Héllo'" (shows Unicode char)
print(ascii(text_unicode))  # "'H\\xe9llo'" (escaped)
```

### 为受限字符集编码

```python
# O(n) - ensure output is 7-bit ASCII safe
def make_ascii_safe(text):
    return ascii(text)

data = "Café: 100€"
safe = make_ascii_safe(data)
# "'Caf\\xe9: 100\\u20ac'"

# Can send safely over ASCII-only channels
```

### 文件名与路径

```python
# O(n) - display paths with non-ASCII names
import os

# Filename might contain Unicode
filename = "documento_españa.txt"
print(ascii(filename))
# "'documento_espa\\xf1a.txt'"

# Safe for logging
path = "/home/用户/文件.txt"
print(ascii(path))
# "'/home/\\u7528\\u6237/\\u6587\\u4ef6.txt'"
```

## 性能模式

### 批量处理

```python
# O(n * m) - n strings, each ~m length
strings = ["Café", "Naïve", "Résumé"]
ascii_versions = [ascii(s) for s in strings]
# O(n * m)
```

### 大段文本

```python
# O(n) - entire text must be scanned
large_text = open("file.txt", "r", encoding="utf-8").read()
safe_version = ascii(large_text)  # O(len(large_text))

# Memory: output may be larger (each non-ASCII becomes \xXX, \uXXXX, etc)
```

## 特殊情况

### 空字符串

```python
# O(1)
ascii("")  # "''"
```

### 仅含 ASCII

```python
# O(n) - no escaping needed
ascii("abc123!@#")  # "'abc123!@#'"

# Output same as input (with quotes added)
```

### 仅含非 ASCII

```python
# O(n) - all characters escaped
ascii("日本語")   # "'\\u65e5\\u672c\\u8a9e'"

# Output is entirely escape sequences
```

## 最佳实践

✅ **推荐**：

- 日志中含非 ASCII 内容时使用 `ascii()`
- API 响应中使用 `ascii()` 以避免编码问题
- 需要 ASCII-only 输出时使用 `ascii()`
- 调试时用它查看所有空白符和控制字符

❌ **避免**：

- 面向用户的输出使用 `ascii()`（应使用 `str()`）
- 以为 `ascii()` 的输出更短（通常反而更长）
- 能用正确编码时仍使用 `ascii()`
- 忘记 `ascii()` 不会解码转义序列

## 相关函数

- **[repr()](repr.md)** - Python 表示形式（保留非 ASCII 字符）
- **[str()](str.md)** - 字符串表示形式（人类可读）
- **[encode()](str.md)** - 按指定编码编码为字节
- **[bytes()](bytes.md)** - 转换为字节

## 版本说明

- **Python 2.x**：对字符串的处理方式不同，Unicode 处理各有差异
- **Python 3.x**：一致的 Unicode 支持，使用 \uXXXX 格式
- **所有版本**：返回带引号的字符串，所有非 ASCII 字符均被转义
