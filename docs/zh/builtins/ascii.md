---
source_sha: fbbf2ba113c9ef6235c50530fa4d018fd52f9aa28915243186037fc5ab0984f1
translated: machine
---

# ascii() 函数的复杂度

`ascii()` 函数返回对象的可打印表示形式，其中非 ASCII 字符会被转义。
它先对对象调用 `repr()`，若结果中含有任何非 ASCII 字符，再对结果做一遍转义，
因此其开销是 `repr()` 的开销，加上与 `repr()` 返回结果长度成线性关系的一遍处理。

## 复杂度分析

对字符串而言，`n` 是其长度。对其他任何对象，`r` 是 `repr(x)` 的长度。

| 情况 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| ASCII 字符串 | O(n) | O(n) | |
| Unicode 字符串 | O(n) | O(n) | 每个非 ASCII 字符变为 4、6 或 10 个字符的转义序列 |
| 容器 | `repr(x)` + O(r) | `repr(x)` + O(r) | 对整个 `repr()` 结果做一遍转义，而不是每个元素一遍 |
| 自定义对象 | `__repr__` + O(r) | `__repr__` + O(r) | `__repr__` 只调用一次；只转义其结果中的非 ASCII 字符 |

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

# Each non-ASCII character becomes \xHH, \uHHHH or \UHHHHHHHH
```

## 复杂度细节

### 字符转义

```python
# O(n) - linear in string length
# Each character may expand to multiple chars

# Short ASCII
ascii("abc")  # n = 3

# Long ASCII
ascii("a" * 1000)  # n = 1000

# Unicode requiring escaping
ascii("é" * 100)   # n = 100 - each é becomes \xe9 (4 chars)
```

### 转义序列

```python
# Printable ASCII - unchanged, apart from what repr() escapes
# (quotes, backslashes, control characters)
# Code points 0x80-0xff - use \xHH format (4 chars total)
ascii("\xe9")  # "'\\xe9'" - é in Latin-1

# Code points 0x100-0xffff - use \uHHHH format (6 chars total)
ascii("\u0101")  # "'\\u0101'" - ā (a with macron)

# Code points above 0xffff - use \UHHHHHHHH format (10 chars total)
ascii("\U0001f600")  # "'\\U0001f600'" - 😀 emoji
```

## 常见模式

### 调试非 ASCII 内容

```python
# O(n) - show hidden non-ASCII characters
text = "Hello\nWorld\t!"
ascii(text)  # "'Hello\\nWorld\\t!'"

# vs str/repr
str(text)    # The text itself, with real newlines/tabs
repr(text)   # "'Hello\\nWorld\\t!'" - repr() escapes control characters too

# repr() keeps printable non-ASCII characters; ascii() escapes them
text_unicode = "Héllo"
repr(text_unicode)   # "'Héllo'" (shows Unicode char)
ascii(text_unicode)  # "'H\\xe9llo'" (escaped)
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
# Filename might contain Unicode
filename = "documento_españa.txt"
ascii(filename)
# "'documento_espa\\xf1a.txt'"

# Safe for logging
path = "/home/用户/文件.txt"
ascii(path)
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
large_text = "Grüße aus 東京\n" * 10_000
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

# Output is the input with quotes added, because it has no quotes,
# backslashes or control characters for repr() to escape
```

### 仅含非 ASCII

```python
# O(n) - all characters escaped
ascii("日本語")   # "'\\u65e5\\u672c\\u8a9e'"

# Everything between the quotes is an escape sequence
```

## 最佳实践

✅ **推荐**：

- 日志中含非 ASCII 内容时使用 `ascii()`
- 需要 ASCII-only 输出时使用 `ascii()`
- 调试时用它查看非 ASCII 字符，以及 `repr()` 已会转义的空白符和控制字符

❌ **避免**：

- 面向用户的输出使用 `ascii()`（应使用 `str()`）
- 以为 `ascii()` 的输出更短（通常反而更长）
- 能用正确编码时仍使用 `ascii()`
- 忘记 `ascii()` 不会解码转义序列

## 版本说明

- **所有 Python 3**：`ascii(x)` 即 `repr(x)`，其中每个非 ASCII 字符都转义为 `\xHH`、`\uHHHH` 或 `\UHHHHHHHH`；字符串参数返回时带引号，其他对象则采用其 `repr()` 的形式

## 相关函数

- **[repr()](repr.md)** - Python 表示形式（保留可打印的非 ASCII 字符）
- **[str()](str.md)** - 字符串表示形式（人类可读）
- **[encode()](str.md)** - 按指定编码编码为字节
- **[bytes()](bytes_func.md)** - 转换为字节
