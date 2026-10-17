# oct() Function Complexity

The `oct()` function returns the octal (base 8) representation of an integer as a string with a
`'0o'` prefix. Because 8 is a power of two, each octal digit is read straight from three bits of
the integer, so the time and the size of the string are both linear in the number of digits.

`n` is the integer's absolute value and `d` is the number of octal digits in the result:
`n.bit_length()` divided by 3 and rounded up, about log₈ n, or 1 for zero. A user-defined
`__index__` costs what it does.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `oct(x)` | O(d) | O(d) | One character per octal digit, after `'0o'`, or `'-0o'` for a negative number |
| `oct(x)` on a very large int | O(d) | O(d) | Not limited by `sys.set_int_max_str_digits()`, which exempts power-of-two bases |
| `oct(obj)` with `__index__` | `__index__` + O(d) | `__index__` + O(d) | Any other non-int, such as a float, raises `TypeError` |
| `format(x, 'o')`, `f"{x:o}"` | O(d) | O(d) | The same digits without the prefix; `'#o'` adds it |
| `int(s, 8)`, `int(s, 0)` | O(d) | O(d) | Parse `oct()`'s output; also linear and exempt from the digit limit. Plain `int(s)` rejects the `'0o'` prefix |

## Converting Integers

### Basic Conversion

```python
assert oct(0) == '0o0'          # O(d), d = 1
assert oct(8) == '0o10'
assert oct(64) == '0o100'
assert oct(4095) == '0o7777'    # O(d), d = 4

# A negative number keeps its magnitude's digits behind a minus sign
assert oct(-8) == '-0o10'
assert oct(-64) == '-0o100'
```

### Digits Grow With the Bit Length

Each octal digit holds three bits, so the output length follows `bit_length()`.

```python
value = 2**24 - 1
assert oct(value) == '0o77777777'  # O(d), d = 8

digits = len(oct(value)) - 2       # Subtract '0o'
assert digits == (value.bit_length() + 2) // 3

big = 2**100
assert oct(big) == '0o2' + '0' * 33  # 101 bits, d = 34
```

### Objects With `__index__`

`oct()` accepts any object that converts itself to an int through `__index__`, and nothing else.

```python
class Mode:
    def __init__(self, bits):
        self.bits = bits

    def __index__(self):
        return self.bits

assert oct(Mode(0o644)) == '0o644'
assert oct(True) == '0o1'  # bool is an int

try:
    oct(8.0)
except TypeError as error:
    assert "integer" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Octal vs Decimal for Large Integers

`str()` of a large int is slower than linear in its digits, and refuses ints past
`sys.get_int_max_str_digits()` digits unless that limit is set to 0. `oct()` and `int(s, 8)` are
linear and have no such limit, which makes octal, hex or binary the safe text form for very large
integers.

```python
import sys

previous = sys.get_int_max_str_digits()
sys.set_int_max_str_digits(640)
try:
    big = 10**1000  # 1,001 decimal digits

    text = oct(big)               # O(d) - not limited
    assert int(text, 8) == big    # O(d) - not limited either

    try:
        str(big)
    except ValueError as error:
        assert "limit" in str(error)
    else:
        raise AssertionError("expected ValueError")
finally:
    sys.set_int_max_str_digits(previous)
```

## Parsing Octal Strings

`int()` reverses `oct()` when told the base. Base 8 accepts the string with or without the
prefix, base 0 reads the base from the prefix, and plain `int()` rejects it.

```python
text = oct(493)
assert text == '0o755'

assert int(text, 8) == 493   # O(d)
assert int('755', 8) == 493
assert int(text, 0) == 493   # Base from the '0o' prefix

try:
    int(text)
except ValueError as error:
    assert "0o755" in str(error)
else:
    raise AssertionError("expected ValueError")
```

## Common Patterns

### File Permissions

Unix permission bits group into threes, which is why modes are written in octal.

```python
import stat

mode = 0o755
assert (mode >> 6) & 0o7 == 7  # Owner
assert (mode >> 3) & 0o7 == 5  # Group
assert mode & 0o7 == 5         # Others

assert oct(mode) == '0o755'
assert format(mode, '03o') == '755'  # No prefix, padded to three digits

# A file's st_mode also carries its type; S_IMODE keeps the permission bits
st_mode = stat.S_IFREG | 0o644
assert oct(st_mode) == '0o100644'
assert oct(stat.S_IMODE(st_mode)) == '0o644'
```

### Converting Many Values

Each conversion is O(d), so a batch costs the total number of digits written.

```python
numbers = [0o100, 0o200, 0o400]

with_prefix = [oct(n) for n in numbers]
without_prefix = [f"{n:o}" for n in numbers]  # Same digits, no '0o'

assert with_prefix == ['0o100', '0o200', '0o400']
assert without_prefix == ['100', '200', '400']
```

## Performance Best Practices

✅ **Do**:

- Use `format(x, 'o')` or `f"{x:o}"` when you don't want the `'0o'` prefix, rather than slicing it off
- Use `int(s, 8)` or `int(s, 0)` to read `oct()`'s output back
- Use `oct()`, `hex()` or `bin()` to write very large integers as text: they are linear and not
  limited by `sys.set_int_max_str_digits()`

❌ **Avoid**:

- Parsing `oct()` output with plain `int(s)`, which rejects the `'0o'` prefix
- Slicing `oct(x)[2:]` to drop the prefix: for a negative number it gives `'o10'` from `'-0o10'`,
  where `format(x, 'o')` gives `'-10'`

## Version Notes

- **All Python 3**: `oct(x)` returns a lowercase `'0o'` prefix, `'-0o'` for a negative number,
  and accepts any object with `__index__`; an octal literal needs the prefix, and `0755` is a
  `SyntaxError`

## Related Functions

- **[hex()](hex.md)** - Hexadecimal representation, also linear in its digits
- **[bin()](bin.md)** - Binary representation
- **[int()](int.md)** - Parse an octal string with base 8 or 0
- **[format()](format.md)** - Octal digits without the prefix, with padding
