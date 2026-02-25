# ord() Function Complexity

The `ord()` function returns the Unicode code point of a character.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Single ASCII character | O(1) | O(1) | Direct lookup |
| Single Unicode character | O(1) | O(1) | Direct lookup |
| Invalid input | O(1) | O(1) | Raises TypeError |

## Basic Usage

### ASCII Characters

```python
# O(1) - direct Unicode code point lookup
ord('a')       # 97
ord('A')       # 65
ord('0')       # 48
ord(' ')       # 32
```

### Unicode Characters

```python
# O(1) - works with any Unicode character
ord('π')       # 960
ord('€')       # 8364
ord('中')      # 20013
ord('😀')     # 128512
```

### Special Characters

```python
# O(1)
ord('\n')      # 10 (newline)
ord('\t')      # 9 (tab)
ord('\0')      # 0 (null)
ord('\\'')     # 92 (backslash)
```

## Comparison with chr()

```python
# ord() - character to code point
ord('A')       # 65

# chr() - code point to character
chr(65)        # 'A'

# Inverse operations - both O(1)
chr(ord('Z'))  # 'Z'
ord(chr(90))   # 90
```

## Performance Patterns

### Character Mapping

```python
# O(n) - map all characters
text = "hello"
codes = [ord(c) for c in text]  # [104, 101, 108, 108, 111]

# O(n) - each ord() is O(1)
for char in text:
    code = ord(char)  # O(1) operation
```

### Building Lookup Tables

```python
# O(k) where k = character set size
lowercase_codes = {ord(c): c for c in "abcdefghijklmnopqrstuvwxyz"}
# {97: 'a', 98: 'b', ..., 122: 'z'}

# Useful for fast lookups
for code, char in lowercase_codes.items():
    verify = chr(code) == char  # True
```

## Common Patterns

### Sorting Characters Alphabetically

```python
# O(1) - ord() returns comparable values
chars = ['z', 'a', 'm', 'b']
sorted_chars = sorted(chars, key=ord)
# ['a', 'b', 'm', 'z']

# But Python already sorts characters correctly
sorted_chars = sorted(chars)  # Same result, no need for ord()
```

### Converting Text to Numbers

```python
# O(n) - convert string to numeric codes
text = "ABC"
codes = [ord(c) for c in text]
# [65, 66, 67]

# Useful for encoding/cipher operations
def simple_cipher(text, shift=3):
    return ''.join(chr(ord(c) + shift) for c in text)

cipher_text = simple_cipher("ABC")
# "DEF"
```

### Checking Character Type

```python
# O(1) - check code point ranges
def is_digit_char(char):
    return ord('0') <= ord(char) <= ord('9')

is_digit_char('5')  # True
is_digit_char('a')  # False

# But use str methods instead
'5'.isdigit()  # True - clearer
```

## Unicode Handling

### Working with Unicode

```python
# O(1) - Unicode characters
ord('é')       # 233 (Latin small e with acute)
ord('ñ')       # 241 (Latin small n with tilde)
ord('ß')       # 223 (German eszett)

# High Unicode points
ord('𝔸')       # 119808 (Mathematical Alphanumeric Symbols)
ord('🎵')      # 127925 (Music note emoji)
```

### Character Ranges

```python
# O(1) - check character ranges
def is_ascii(char):
    return ord(char) < 128

def is_extended_ascii(char):
    return 128 <= ord(char) < 256

def is_greek(char):
    return 0x0370 <= ord(char) <= 0x03FF
```

## Edge Cases

### Single Character Requirement

```python
# O(1) - works only with single characters
ord('a')       # 97

# TypeError - requires single character
try:
    ord('ab')  # TypeError: ord() expected a character
except TypeError:
    pass

try:
    ord('')    # TypeError: ord() expected a character
except TypeError:
    pass
```

### Type Requirements

```python
# O(1) - works with strings only
ord('x')       # 120

# TypeError - not with integers
try:
    ord(120)   # TypeError
except TypeError:
    pass
```

## Performance Considerations

### Bulk Operations

```python
# O(n) - efficient for bulk operations
text = "hello world"
codes = [ord(c) for c in text]
# O(n) - linear time for n characters

# Using map
codes = list(map(ord, text))  # O(n) - slightly more efficient
```

## Best Practices

✅ **Do**:

- Use `map(ord, string)` for bulk operations

❌ **Avoid**:

- Using `ord()` for character type checking (use str methods)

## Related Functions

- **[chr()](chr.md)** - Convert code point to character
- **[str.encode()](str.md)** - Convert string to bytes
- **[bytes.decode()](bytes.md)** - Convert bytes to string
- **[ord() with map()](map.md)** - Bulk character conversion

## Version Notes

- **Python 2.x**: Works with Unicode strings (u"")
- **Python 3.x**: All strings are Unicode, ord() works seamlessly
- **Python 3.8+**: Same behavior, consistent Unicode support
