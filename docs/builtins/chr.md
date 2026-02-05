# chr() Function Complexity

The `chr()` function returns the character corresponding to a Unicode code point.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Valid code point | O(1) | O(1) | Direct character lookup |
| Invalid range | O(1) | O(1) | Raises ValueError |
| High Unicode | O(1) | O(1) | Works for all valid points |

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
text = ''.join(map(chr, codes))  # O(n) - slightly more efficient
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
chr(119808)    # '𝔸' (Mathematical Alphanumeric)
chr(127925)    # '🎵' (Music note emoji)

# Maximum valid code point
chr(0x10FFFF)  # Last valid Unicode character
```

### Character Category Ranges

```python
# O(1) - create characters from ranges
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
    chr(-1)    # ValueError: chr() arg not in valid range
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

## Surrogates and Edge Cases

```python
# Valid surrogate pairs (combined characters)
# These are valid Unicode code points
chr(0xDC00)    # Surrogate character (valid as standalone)

# But combining characters exist
chr(0x0301)    # Combining acute accent
# Used with other characters: 'e' + chr(0x0301) = 'é'
```

## Performance Considerations

### vs String Literals

```python
# Same performance - O(1) both
a = chr(65)    # 'A'
b = 'A'        # 'A' - literal

# But chr() useful when code point is computed
code = 65
char = chr(code)  # 'A'

# Bulk operations
import timeit
t1 = timeit.timeit(lambda: chr(65), number=10**7)
t2 = timeit.timeit(lambda: 'A', number=10**7)
# chr() slightly slower but trivial difference
```

### Building Strings Efficiently

```python
# O(n) - efficient string building
codes = range(65, 91)
result = ''.join(chr(c) for c in codes)
# "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Same complexity as:
result = ''.join(map(chr, codes))
# map() slightly more efficient
```

## Best Practices

✅ **Do**:

- Use `chr()` to create characters from code points
- Use with `ord()` for bidirectional conversion
- Use `map(chr, codes)` for bulk conversion
- Use for encoding/decoding operations

❌ **Avoid**:

- Creating strings character by character (use join)
- Assuming ASCII-only (support Unicode)
- Using string literals when code points are computed
- Unnecessary intermediate lists

## Related Functions

- **[ord()](ord.md)** - Convert character to code point
- **[str.encode()](str.md)** - Convert string to bytes
- **[bytes.decode()](bytes.md)** - Convert bytes to string
- **[chr() with map()](map.md)** - Bulk character creation

## Version Notes

- **Python 2.x**: Returns unicode with u prefix (u'A')
- **Python 3.x**: Returns str, all strings are Unicode
- **Python 3.8+**: Consistent Unicode support across versions
