# ord() Function Complexity

The `ord()` function returns the integer code point of a one-character string, or the byte value
of a one-byte `bytes` or `bytearray`. Each call is O(1): it reads the argument's length, rejects
anything but 1, and reads the single character or byte, whatever its value.

`n` is the characters in a string, or the bytes in a `bytes` object, when `ord()` is applied to
each of them.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ord(c)`, `c` a one-character `str` | O(1) | O(1) | Any code point from 0 to 0x10FFFF; `str` subclasses are accepted |
| `ord(b)`, `b` a one-byte `bytes` or `bytearray` | O(1) | O(1) | A value from 0 to 255 |
| `ord(s)` with `len(s) != 1` | O(1) | O(1) | Raises `TypeError`; the length is read, not counted, so a long string fails as fast as a short one |
| `ord(x)` on any other type | O(1) | O(1) | Raises `TypeError`, including for an `int` and a `memoryview`; `__index__` is not consulted |
| `[ord(c) for c in s]`, `list(map(ord, s))` | O(n) | O(n) | One O(1) call per character |
| `list(data)`, `data[i]` on `bytes` | O(n), O(1) | O(n), O(1) | Indexing or iterating `bytes` already yields ints, so `ord()` is not needed |

## Basic Usage

### Characters

Every code point costs the same, from ASCII to the supplementary planes.

```python
assert ord('a') == 97        # O(1)
assert ord('A') == 65
assert ord(' ') == 32
assert ord('\n') == 10
assert ord('\\') == 92

assert ord('é') == 233       # O(1) - Latin-1
assert ord('€') == 8364      # O(1) - Basic Multilingual Plane
assert ord('中') == 20013
assert ord('😀') == 128512   # O(1) - beyond U+FFFF
```

### Bytes

A one-byte `bytes` or `bytearray` gives its byte value. Indexing a `bytes` object already returns
an int, so `ord()` is for a length-1 slice or a one-byte literal.

```python
assert ord(b'a') == 97             # O(1)
assert ord(bytearray(b'\xff')) == 255

data = b'hello'
assert data[0] == 104              # O(1) - already an int
assert ord(data[0:1]) == 104       # O(1) - a one-byte slice
assert list(data) == [104, 101, 108, 108, 111]  # O(n) - no ord() needed
```

### The Inverse of chr()

`chr()` maps a code point back to its character, so the two round-trip.

```python
assert chr(ord('Z')) == 'Z'   # O(1)
assert ord(chr(90)) == 90     # O(1)
assert ord(chr(0x10FFFF)) == 0x10FFFF
```

## Invalid Arguments

### Wrong Length

Anything but exactly one character or byte raises `TypeError`. The length is read from the object,
so a long string is rejected in O(1).

```python
for bad in ['ab', '', b'', 'x' * 1_000_000]:
    try:
        ord(bad)
    except TypeError as error:
        assert 'expected a character' in str(error)
    else:
        raise AssertionError(f'expected TypeError for length {len(bad)}')
```

### Wrong Type

An `int` is not converted, and `memoryview` is not accepted even with one byte.

```python
for bad in [120, memoryview(b'a')]:
    try:
        ord(bad)
    except TypeError as error:
        assert 'expected string of length 1' in str(error)
    else:
        raise AssertionError(f'expected TypeError for {type(bad).__name__}')
```

## Common Patterns

### Converting Text to Code Points

Applying `ord()` to each character is O(n), and `chr()` turns the codes back into a string.

```python
text = "ABC"
codes = [ord(c) for c in text]  # O(n)
assert codes == [65, 66, 67]
assert list(map(ord, text)) == codes  # O(n)

def shift(text, by=3):
    return ''.join(chr(ord(c) + by) for c in text)  # O(n)

assert shift("ABC") == "DEF"
```

### Checking Code Point Ranges

A range check on one character is O(1).

```python
def is_ascii_char(char):
    return ord(char) < 128  # O(1)

def is_greek(char):
    return 0x0370 <= ord(char) <= 0x03FF  # O(1)

assert is_ascii_char('a') and not is_ascii_char('é')
assert is_greek('π') and not is_greek('p')
assert "plain text".isascii()  # O(1) - a str records whether it is ASCII
```

### Sorting Characters

Strings compare by code point, so single characters sort the same without a key; `key=ord` only
adds a call per item.

```python
chars = ['z', 'a', 'M', 'é', 'b']
assert sorted(chars) == ['M', 'a', 'b', 'z', 'é']
assert sorted(chars, key=ord) == sorted(chars)
```

## Performance Best Practices

✅ **Do**:

- Index or iterate `bytes` directly to get byte values; each item is already an int
- Use `str.isascii()` to check a whole string: it is O(1), where `ord()` on every character is O(n)

❌ **Avoid**:

- `ord(data[i])` on `bytes`: `data[i]` is an int, and `ord()` raises `TypeError`
- `sorted(chars, key=ord)` on single characters: the default comparison gives the same order without the calls

## Related Functions

- **[chr()](chr.md)** - Convert a code point back to a character
- **[str](str.md)** - `str.encode()` turns a string into bytes, and `str.isascii()` checks a whole string
- **[bytes](bytes.md)** - Indexing and iteration yield ints directly
- **[map()](map.md)** - Apply `ord()` lazily across a string
