# chr() Function Complexity

The `chr()` function returns the one-character string for a Unicode code point.
Each call on an int is O(1): the argument is converted to a C integer, range-checked, and
turned into a string of length one, whatever the code point.

`n` is the number of code points when `chr()` is applied to a sequence of them.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Valid code point | O(1) | O(1) | Any code point from 0 to 0x10FFFF, surrogates included |
| Out of range | O(1) | O(1) | Raises `ValueError`; an int beyond the C `int` range raised `OverflowError` before Python 3.13 |
| Object with `__index__` | `__index__` + O(1) | `__index__` + O(1) | Any other non-int, such as a float or a str, raises `TypeError` |
| `n` code points to a string | O(n) | O(n) | `''.join(map(chr, codes))` |

## Basic Usage

### ASCII Characters

```python
# O(1) - code point to character
chr(65)        # 'A'
chr(97)        # 'a'
chr(48)        # '0'
chr(32)        # ' ' (space)
```

### Unicode Characters

```python
# O(1) - works with any valid code point
chr(960)       # 'π'
chr(8364)      # '€'
chr(20013)     # '中'
chr(128512)    # '😀'
```

### Special Characters

```python
# O(1)
chr(10)        # '\n' (newline)
chr(9)         # '\t' (tab)
chr(0)         # '\0' (null)
chr(92)        # '\\' (backslash)
```

## Comparison with ord()

```python
# chr() - code point to character
chr(65)        # 'A'

# ord() - character to code point
ord('A')       # 65

# Inverse operations - both O(1)
ord(chr(90))   # 90
chr(ord('Z'))  # 'Z'
```

## Performance Patterns

### Code Point to Character Conversion

```python
# O(n) - convert list of code points
codes = [72, 101, 108, 108, 111]
chars = [chr(c) for c in codes]
# ['H', 'e', 'l', 'l', 'o']

# Join to string
text = ''.join(chr(c) for c in codes)
# "Hello"

# Using map
text = ''.join(map(chr, codes))  # O(n), the same string
```

### Building Strings from Code Points

```python
# O(n) - construct string from codes
code_points = list(range(65, 91))  # A-Z
alphabet = ''.join(chr(cp) for cp in code_points)
# "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
```

## Common Patterns

### Reverse String Transformations

```python
# O(n) - encode to codes, then decode
text = "Hello"
codes = [ord(c) for c in text]     # O(n)
restored = ''.join(chr(c) for c in codes)  # O(n)
# "Hello"

# Total: O(n)
```

### Creating Character Maps

```python
# O(k) where k = character set size
ascii_chars = {i: chr(i) for i in range(32, 127)}
# {32: ' ', 33: '!', 34: '"', ..., 126: '~'}

# Reverse lookup
code_to_char = {ord(c): c for c in "abcdefghijklmnopqrstuvwxyz"}
```

### Simple Cipher/Encoding

```python
# O(n) - Caesar cipher
def caesar_cipher(text, shift=3):
    return ''.join(chr(ord(c) + shift) for c in text)

encrypted = caesar_cipher("ABC")
# "DEF"

# Reverse
def caesar_decipher(text, shift=3):
    return ''.join(chr(ord(c) - shift) for c in text)

decrypted = caesar_decipher("DEF")
# "ABC"
```

### Unicode Range Operations

```python
# O(1) - create character from range
lowercase_start = chr(ord('a'))    # 'a'
uppercase_start = chr(ord('A'))    # 'A'

# Generate range
lowercase_letters = ''.join(chr(i) for i in range(ord('a'), ord('z') + 1))
# "abcdefghijklmnopqrstuvwxyz"
```

## Unicode Handling

### Unicode Code Points

```python
# O(1) - all valid Unicode
chr(233)       # 'é'
chr(241)       # 'ñ'
chr(223)       # 'ß'

# High Unicode points
chr(119808)    # '𝐀' (Mathematical Bold Capital A)
chr(127925)    # '🎵' (Musical note emoji)

# Maximum valid code point
chr(0x10FFFF)  # Highest code point chr() accepts
```

### Character Category Ranges

```python
# O(k) - k = end - start + 1 characters
def create_chars_in_range(start, end):
    return ''.join(chr(i) for i in range(start, end + 1))

# Greek letters
greek = create_chars_in_range(0x0370, 0x03FF)

# Emoji range (simplified)
emoji = create_chars_in_range(0x1F300, 0x1F600)
```

## Edge Cases

### Valid Code Point Range

```python
# O(1) - valid ranges
chr(0)         # '\0' (null character)
chr(127)       # DEL character
chr(0x10FFFF)  # Highest valid Unicode

# ValueError - out of range
try:
    chr(-1)    # ValueError: chr() arg not in range(0x110000)
except ValueError:
    pass

try:
    chr(0x110000)  # ValueError: out of range
except ValueError:
    pass
```

### Type Requirements

```python
# O(1) - requires integer
chr(65)        # 'A'

# TypeError - non-integer
try:
    chr(65.0)  # TypeError - float not accepted
except TypeError:
    pass

try:
    chr("65")  # TypeError
except TypeError:
    pass
```

## Performance Considerations

### vs String Literals

```python
# Both O(1); a literal is a constant, chr() is a call
a = chr(65)    # 'A'
b = 'A'        # 'A' - literal

# chr() is for code points computed at run time
code = 65
char = chr(code)  # 'A'
```

### Building Strings Efficiently

```python
# O(n) - efficient string building
codes = range(65, 91)
result = ''.join(chr(c) for c in codes)
# "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Same complexity and result:
result = ''.join(map(chr, codes))
```

## Best Practices

✅ **Do**:

- Convert many code points with one `''.join(map(chr, codes))` - O(n) for the whole string

❌ **Avoid**:

- Calling `chr()` on a constant code point; write the literal instead

## Related Functions

- **[ord()](ord.md)** - Convert character to code point
- **[str.encode()](str.md)** - Convert string to bytes
- **[bytes.decode()](bytes.md)** - Convert bytes to string
- **[chr() with map()](map.md)** - Bulk character creation

## Version Notes

- **Python 3.13+**: Every out-of-range int raises `ValueError`; before 3.13 one outside the C `int` range, such as `2**31`, raised `OverflowError`
- **All Python 3**: `chr()` returns a `str` and accepts any object with `__index__`
