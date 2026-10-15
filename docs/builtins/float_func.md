# float() Function Complexity

The `float()` function converts a string, a number, or an object that defines `__float__` or
`__index__` to a float. The result is always one IEEE 754 double, the same size whatever the
input, so parsing a string is linear in its length.

`n` is the characters in a string argument, or the bytes in a `bytes`, `bytearray` or other
buffer argument. `d` is the length of an int argument, in digits of any fixed base.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `float()` | O(1) | O(1) | `0.0` |
| `float(x)`, `x` a float | O(1) | O(1) | An exact float is returned as the same object; a float subclass instance becomes a new float |
| `float(x)`, `x` an int or bool | O(d) | O(1) | O(d) at worst; a convertible int has at most 1,024 bits, and a larger one raises `OverflowError` after the same O(d) scan |
| `float(x)`, `x` defines `__float__` or `__index__` | method + O(1); + O(d) at worst for `__index__` | method + O(1) | `__float__` is tried first; an int returned by `__index__` is then converted as in the int row, O(d) at worst |
| `float(s)`, `s` an ASCII `str`, `bytes` or `bytearray` without underscores | O(n) | O(1) | Parsed in place; surrounding whitespace is skipped, and `inf`, `infinity` and `nan` are accepted in any case |
| `float(s)`, `s` with non-ASCII digits or whitespace, or with underscores | O(n) | O(n) | Copied to plain ASCII first |
| `float(buf)`, any other contiguous buffer, such as a `memoryview` | O(n) | O(n) | Copied into a `bytes` object first; a non-contiguous buffer raises `TypeError` |

## Converting Numbers

Converting an int takes its top 55 bits and then scans the bits below them, from the top, until
one is nonzero, to round correctly. Most ints stop the scan at once, but one such as `2**k`, whose
lower bits are all zero, is read in full: O(d) at worst. Every int a float can hold has at most
1,024 bits, so a successful conversion stays cheap. A larger int raises `OverflowError` rather
than becoming infinity, and only after the same scan, so rejecting a million-bit power of two
reads all million bits. An object of a user-defined type gets one call to `__float__`, or to
`__index__` if it has no `__float__`.

```python
assert float() == 0.0                     # O(1)
assert float(42) == 42.0                  # O(1)
assert float(True) == 1.0 and float(False) == 0.0
assert float(2**1023) == 8.98846567431158e307  # O(d), d at most 1,024 bits

x = 3.14
assert float(x) is x                      # O(1) - the same object back

try:
    float(2**1024)
except OverflowError as error:
    assert 'too large to convert to float' in str(error)
else:
    raise AssertionError('an int beyond the float range was converted')


class Meters:
    def __init__(self, value):
        self.value = value

    def __float__(self):                  # called once
        return float(self.value)


assert float(Meters(5)) == 5.0            # method + O(1)
```

## Parsing Strings

### Notation and Special Values

Decimal and exponent notation, a sign, and the special values are all parsed in O(n).

```python
import math

# O(n) - n = string length
assert float("3.14") == 3.14
assert float("-2.5") == -2.5
assert float("1.23e-4") == 0.000123
assert float("1E10") == 10000000000.0
assert float(".5") == 0.5
assert float("5.") == 5.0
assert float(b"2.5") == 2.5               # bytes parse in place too

# Special values, in any case
assert float("inf") == math.inf
assert float("-Infinity") == -math.inf
assert math.isnan(float("NaN"))
```

### Whitespace, Underscores and Non-ASCII Digits

Surrounding whitespace is skipped without a copy. Underscores between digits, and digits or
whitespace outside ASCII, are accepted too, but the string is first copied to plain ASCII, which
takes O(n) extra space.

```python
# O(n) time, O(1) space - parsed in place
assert float("  3.14  ") == 3.14
assert float("\t2.5\n") == 2.5

# O(n) time, O(n) space - copied first
assert float("1_000.5") == 1000.5
assert float("\u0663.\u0665") == 3.5     # ARABIC-INDIC DIGITS THREE and FIVE
assert float("\u20031.5") == 1.5         # EM SPACE
```

### Invalid Strings

A string that is empty, all whitespace, or not a number raises `ValueError`.

```python
for text in ["", "   ", "3.14.15", "1.5x", "x1.5", "1__0", "0x10"]:
    try:
        float(text)                       # O(n)
    except ValueError as error:
        assert 'could not convert string to float' in str(error)
    else:
        raise AssertionError(f'{text!r} was converted')

try:
    float([1.5])
except TypeError as error:
    assert 'must be a string or a real number' in str(error)
else:
    raise AssertionError('a list was converted')
```

### Range and Rounding

Parsing never raises for a value out of range: too large becomes infinity, too small becomes
zero, and digits beyond what a double holds are rounded away rather than kept.

```python
import math
import sys

assert float("1e308") < sys.float_info.max     # 1.7976931348623157e308
assert float("1e309") == math.inf              # overflows to infinity
assert float("1e-324") == 0.0                  # underflows to zero
assert float("9007199254740993") == 9007199254740992.0  # 2**53 + 1 rounds

# O(n) - a thousand digits still give one double
assert float("3." + "14" * 500) == 3.1414141414141414
```

## float() vs int() on Strings

`float()` parses in linear time because its result is fixed width. `int()` builds an
arbitrary-precision value from the digits, which is superlinear in their number, and so
`int()` refuses a decimal string over 4,300 digits by default while `float()` has no such limit.
See [int()](int_func.md).

```python
digits = "9" * 5_000

assert float(digits) == float("inf")   # O(n) - no digit limit
try:
    int(digits)
except ValueError as error:
    assert 'Exceeds the limit (4300 digits)' in str(error)
else:
    raise AssertionError('int() parsed more than 4300 digits')

# int() does not accept a decimal point
try:
    int("3.14")
except ValueError:
    pass
else:
    raise AssertionError('int() parsed a decimal point')
assert int(float("3.14")) == 3
```

## Common Patterns

### Batch Conversion

Converting many strings costs their total length, whether written as a comprehension or with
`map()`.

```python
strings = ["1.5", "2.7", "3.14", "10.0"]

values = [float(s) for s in strings]      # O(total characters)
assert values == [1.5, 2.7, 3.14, 10.0]
assert list(map(float, strings)) == values
```

### Parsing Input

```python
def parse_celsius(text):
    """Kelvin from a Celsius reading, or None if the text is not a number."""
    try:
        value = float(text)               # O(n)
    except ValueError:
        return None
    return value + 273.15


assert parse_celsius("25.5") == 298.65
assert parse_celsius("warm") is None
```

### Literal vs float()

A literal such as `3.14` is compiled into a constant once; `float("3.14")` parses the string
every time it runs.

```python
import dis

def literal():
    return 3.14

def parsed():
    return float("3.14")

assert literal() == parsed()
assert not any(i.opname.startswith("CALL") for i in dis.get_instructions(literal))
assert any(i.opname.startswith("CALL") for i in dis.get_instructions(parsed))
```

## Performance Best Practices

✅ **Do**:

- Write constants as literals: they are built once, at compile time
- Parse a string once and keep the float, rather than calling `float()` on it in a loop
- Use `float()` rather than `int()` for long digit strings when an approximate value is enough:
  it is linear and has no digit limit
- Use `decimal.Decimal` when every digit of the string must survive: a float keeps 53 bits
  however many digits it is given

❌ **Avoid**:

- Expecting `float()` to raise for an out-of-range string: it returns infinity or zero
- Converting an int you have not bounded: one over 1,024 bits raises `OverflowError`

## Version Notes

- **Python 3.14+**: `float.from_number()` converts a number but rejects a string; see
  [float](float.md)

## Related Functions

- **[float](float.md)** - Operations on float values
- **[int()](int_func.md)** - Convert to integer; superlinear on long digit strings
- **[str()](str_func.md)** - Convert to string
- **[round()](round.md)** - Round to nearest integer
- **[decimal](../stdlib/decimal.md)** - Exact decimal arithmetic
