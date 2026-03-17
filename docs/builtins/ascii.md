# ascii() Function Complexity

The `ascii()` function returns a printable representation of an object with non-ASCII characters escaped.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| ASCII string | O(n) | O(n) | n = string length |
| Unicode string | O(n) | O(n) | Non-ASCII chars escaped |
| Container | O(n) | O(n) | Recursively escapes contents |
| Custom object | O(1)* | O(1)* | Depends on `__repr__` |

## Basic Usage

### ASCII Strings

```python
# O(n) - where n = string length
ascii("hello")       # "'hello'"
ascii("Python")      # "'Python'"
ascii("123")         # "'123'"
```

### Unicode Strings

```python
# O(n) - non-ASCII characters escaped
ascii("café")        # "'caf\\xe9'"
ascii("🎵")         # "'\\U0001f3b5'"
ascii("Ñoño")        # "'\\xd1o\\xf1o'"
ascii("日本語")       # "'\\u65e5\\u672c\\u8a9e'"
```

### Mixed Content

```python
# O(n) - escapes all non-ASCII
text = "Hello, 世界"
ascii(text)  # "'Hello, \\u4e16\\u754c'"

# Each Unicode character escaped to \uXXXX or \UXXXXXXXX
```

## Complexity Details

### Character Escaping

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

### Escape Sequences

```python
# ASCII characters - no change
# Extended ASCII (127-255) - use \xHH format (4 chars total)
ascii("\xe9")  # "'\\xe9'" - é in Latin-1

# Unicode (>255) - use \uHHHH format (6 chars total)
ascii("\u0101")  # "'\\u0101'" - ā (a with macron)

# High Unicode - use \UHHHHHHHH format (10 chars total)
ascii("\U0001f600")  # "'\\U0001f600'" - 😀 emoji
```

## Common Patterns

### Debugging Non-ASCII Content

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

### Encoding for Limited Charsets

```python
# O(n) - ensure output is 7-bit ASCII safe
def make_ascii_safe(text):
    return ascii(text)

data = "Café: 100€"
safe = make_ascii_safe(data)
# "'Caf\\xe9: 100\\u20ac'"

# Can send safely over ASCII-only channels
```

### File Names and Paths

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

## Performance Patterns

### Batch Processing

```python
# O(n * m) - n strings, each ~m length
strings = ["Café", "Naïve", "Résumé"]
ascii_versions = [ascii(s) for s in strings]
# O(n * m)
```

### Large Text

```python
# O(n) - entire text must be scanned
large_text = open("file.txt", "r", encoding="utf-8").read()
safe_version = ascii(large_text)  # O(len(large_text))

# Memory: output may be larger (each non-ASCII becomes \xXX, \uXXXX, etc)
```

## Special Cases

### Empty String

```python
# O(1)
ascii("")  # "''"
```

### Only ASCII

```python
# O(n) - no escaping needed
ascii("abc123!@#")  # "'abc123!@#'"

# Output same as input (with quotes added)
```

### Only Non-ASCII

```python
# O(n) - all characters escaped
ascii("日本語")   # "'\\u65e5\\u672c\\u8a9e'"

# Output is entirely escape sequences
```

## Best Practices

✅ **Do**:

- Use `ascii()` for logging with non-ASCII content
- Use `ascii()` for API responses to avoid encoding issues
- Use `ascii()` when ASCII-only output is required
- Use for debugging to see all whitespace and control characters

❌ **Avoid**:

- Using `ascii()` for user-facing output (use `str()`)
- Assuming `ascii()` output is smaller (it's usually larger)
- Using `ascii()` when you can use proper encoding
- Forgetting that `ascii()` doesn't decode escape sequences

## Related Functions

- **[repr()](repr.md)** - Python representation (keeps non-ASCII)
- **[str()](str.md)** - String representation (human-readable)
- **[encode()](str.md)** - Encode to bytes with specific encoding
- **[bytes()](bytes.md)** - Convert to bytes

## Version Notes

- **Python 2.x**: Treats strings differently, Unicode handling varies
- **Python 3.x**: Consistent Unicode support, uses \uXXXX format
- **All versions**: Returns string with quotes, all non-ASCII escaped
