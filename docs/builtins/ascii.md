# ascii() Function Complexity

The `ascii()` function returns a printable representation of an object with non-ASCII characters escaped.
It calls `repr()` on the object, then makes one escaping pass over the result
if it contains any non-ASCII character, so the cost is `repr()`'s plus a pass
linear in the length of what `repr()` returned.

## Complexity Analysis

For a string, `n` is its length. For any other object, `r` is the length of
`repr(x)`.

| Case | Time | Space | Notes |
|------|------|-------|-------|
| ASCII string | O(n) | O(n) | |
| Unicode string | O(n) | O(n) | Each non-ASCII character becomes a 4-, 6- or 10-character escape |
| Container | `repr(x)` + O(r) | `repr(x)` + O(r) | One escaping pass over the whole `repr()`, not one per element |
| Custom object | `__repr__` + O(r) | `__repr__` + O(r) | `__repr__` is called once; only the non-ASCII characters in its result are escaped |

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

# Each non-ASCII character becomes \xHH, \uHHHH or \UHHHHHHHH
```

## Complexity Details

### Character Escaping

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

### Escape Sequences

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

## Common Patterns

### Debugging Non-ASCII Content

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
# Filename might contain Unicode
filename = "documento_españa.txt"
ascii(filename)
# "'documento_espa\\xf1a.txt'"

# Safe for logging
path = "/home/用户/文件.txt"
ascii(path)
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
large_text = "Grüße aus 東京\n" * 10_000
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

# Output is the input with quotes added, because it has no quotes,
# backslashes or control characters for repr() to escape
```

### Only Non-ASCII

```python
# O(n) - all characters escaped
ascii("日本語")   # "'\\u65e5\\u672c\\u8a9e'"

# Everything between the quotes is an escape sequence
```

## Best Practices

✅ **Do**:

- Use `ascii()` for logging with non-ASCII content
- Use `ascii()` when ASCII-only output is required
- Use for debugging to see non-ASCII characters as well as the whitespace and control characters `repr()` already escapes

❌ **Avoid**:

- Using `ascii()` for user-facing output (use `str()`)
- Assuming `ascii()` output is smaller (it's usually larger)
- Using `ascii()` when you can use proper encoding
- Forgetting that `ascii()` doesn't decode escape sequences

## Version Notes

- **All Python 3**: `ascii(x)` is `repr(x)` with every non-ASCII character escaped as `\xHH`, `\uHHHH` or `\UHHHHHHHH`; a string argument comes back quoted, other objects in whatever form their `repr()` takes

## Related Functions

- **[repr()](repr.md)** - Python representation (keeps printable non-ASCII characters)
- **[str()](str.md)** - String representation (human-readable)
- **[encode()](str.md)** - Encode to bytes with specific encoding
- **[bytes()](bytes_func.md)** - Convert to bytes
