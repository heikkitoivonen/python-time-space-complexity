# format() Function Complexity

The `format(value, format_spec='')` function calls `type(value).__format__(value, format_spec)`
and returns the string it produces. Its cost is the cost of that method: for the built-in
types it is linear in the result's length, except decimal conversion of an `int`, and an exact
`str` that needs no padding or truncation comes back unchanged. f-strings and `str.format()` call the
same method for each replacement field.

`n` is the length of the result string, `d` is the number of digits of an `int` written in
decimal, and `p` is the precision a float specification asks for. A format specification is a few characters long and is priced at O(1); a type that
defines its own `__format__` adds whatever that method does.

## Complexity Reference

### format

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `format(value, format_spec='')` | O(1) + `__format__` | O(1) + `__format__` | Calls `type(value).__format__`; a result that is not a `str` raises `TypeError` |
| `format(obj)` on a class that inherits `object.__format__` | Cost of `str(obj)` | Cost of `str(obj)` | `object.__format__` returns `str(obj)` for an empty spec and raises `TypeError` for any other |

### str

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `format(s)`, `format(s, spec)` on an exact `str` | O(1) | O(1) | Returns `s` itself when the spec neither pads nor truncates |
| `format(s, spec)` that pads or truncates, or on a `str` subclass | O(n) | O(n) | A subclass is copied into a new exact `str` |

### int

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `format(x)`, `format(x, 'd')`, `format(x, ',')` | O(d² + n); 3.12+: subquadratic above 30,000 bits | O(n) | The decimal conversion `str(x)` performs; see [int](int.md). Raises `ValueError` beyond `sys.get_int_max_str_digits()`, 4,300 digits by default, which is below the subquadratic range |
| `format(x, 'b')`, `format(x, 'o')`, `format(x, 'x')`, `format(x, 'X')` | O(n) | O(n) | Power-of-two bases map bits straight to characters, with no digit limit |
| `format(x, 'e')`, `format(x, 'f')`, `format(x, 'g')`, `format(x, '%')` | O(d + n) | O(n + p) | Converts `x` to a `float` first; an int too large for one raises `OverflowError` |

### float and complex

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `format(f)`, `format(f, spec)` | O(n) | O(n + p) | `'f'` and `'e'` write every digit of the precision, and `'f'` every integer digit; `'g'` reserves room for the whole precision even when it drops trailing zeros; see [float](float.md) |
| `format(c)`, `format(c, spec)` | O(n) | O(n + p) | The precision and presentation type apply to both parts |

### f-strings, str.format() and %

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `f"{value}"`, `f"{value:spec}"` | Cost of `format(value, spec)` | Cost of `format(value, spec)` | A field alone, with no surrounding text, is the result itself |
| `f"text {a} {b:spec}"` | O(n) + each field's `format()` | O(n) + each field's `format()` | |
| `template.format(*args, **kwargs)` | O(n) + each field's `format()` | O(n) + each field's `format()` | Calls `__format__` per field like an f-string; see [str](str.md) |
| `template % values` | O(n) + each conversion | O(n) + each conversion | `%s` calls `str()`, not `__format__` |

## Returning a String Unchanged

`str.__format__` with nothing to pad or cut returns the string it was given, so formatting a
string that already has the right shape costs nothing, however long it is. A spec that widens or
truncates it builds a new string of the result's length.

```python
s = 'x' * 1_000_000

assert format(s) is s          # O(1) - the same object
assert format(s, 's') is s     # O(1)
assert format(s, '<10') is s   # O(1) - already wider than 10
assert f'{s}' is s             # O(1) - an f-string that is only one field

padded = format(s, '<1000005')  # O(n) - a new string
assert len(padded) == 1_000_005 and padded is not s
assert format(s, '.3') == 'xxx'  # O(n) - truncated to the precision
```

## Formatting Integers

Decimal output is the expensive case: it is the same conversion `str(x)` performs, quadratic in
the digit count up to the default limit, and CPython refuses it past that limit. Binary, octal and hexadecimal
need no arithmetic, so they stay linear and have no limit.

```python
import sys

x = 7 ** 6_000                   # about 5,000 decimal digits

try:
    format(x)                    # O(d²) - decimal, so the digit limit applies
except ValueError as error:
    assert 'limit' in str(error)
else:
    raise AssertionError('a decimal conversion past the limit succeeded')

assert len(format(x, 'x')) == (x.bit_length() + 3) // 4   # O(n) - no limit

limit = sys.get_int_max_str_digits()
sys.set_int_max_str_digits(0)    # 0 removes the limit
try:
    assert format(x) == str(x)
finally:
    sys.set_int_max_str_digits(limit)

# A float presentation type converts the int to a float first
try:
    format(10 ** 400, 'f')
except OverflowError as error:
    assert 'too large' in str(error)
else:
    raise AssertionError('an int beyond the float range was formatted as one')
```

## Format Specification Mini-language

The general form is `[[fill]align][sign]['z']['#']['0'][width][grouping]['.' precision[grouping]][type]`;
the grouping after the precision is Python 3.14+.

### Integers

```python
value = 42
assert format(value, 'd') == '42'
assert format(value, '05d') == '00042'      # zero-padded to width 5
assert format(value, 'x') == '2a'
assert format(value, 'b') == '101010'
assert format(value, 'o') == '52'

assert format(42, '+d') == '+42'            # always show the sign
assert format(42, ' d') == ' 42'            # a space where the sign would go
assert format(-42, '+d') == '-42'

assert format(255, '#x') == '0xff'          # alternate form adds the prefix
assert format(255, '#b') == '0b11111111'
assert format(255, '_b') == '1111_1111'     # binary groups by four digits

assert format(1_000_000, ',') == '1,000,000'
assert format(1_000_000, '_') == '1_000_000'
```

### Floats

```python
value = 3.14159265
assert format(value, '.2f') == '3.14'
assert format(value, '.4f') == '3.1416'
assert format(value, 'e') == '3.141593e+00'
assert format(value, 'g') == '3.14159'
assert format(0.42, '.1%') == '42.0%'
assert format(123456789.0, '.2e') == '1.23e+08'

# Precision is not capped: 'f' writes every digit it is asked for
assert len(format(0.1, '.1000f')) == 1002   # O(p)
assert format(1.1, '.1000g') == format(1.1, '.60g')  # O(n), with room reserved for p digits
assert format(-0.0001, 'z.1f') == '0.0'     # 'z' turns negative zero into zero
```

### Width and Alignment

Padding writes every fill character, so a width is paid for in full.

```python
value = 'hello'
assert format(value, '<10') == 'hello     '
assert format(value, '>10') == '     hello'
assert format(value, '^10') == '  hello   '
assert format(value, '.>10') == '.....hello'   # custom fill character

assert format(42, '10') == '        42'         # numbers align right by default
assert format(-42, '=+6') == '-   42'           # pad between the sign and the digits

assert len(format('', '<100000')) == 100_000     # O(n) for n = width
```

## Custom `__format__`

`format()` passes the spec string to the class's `__format__` and checks that a `str` comes back.
What the method does with the spec, and what that costs, is up to the class.

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __format__(self, spec):
        if spec == 'tuple':
            return f'({self.x}, {self.y})'
        if spec == 'verbose':
            return f'Point({self.x}, {self.y})'
        return f'{self.x:.1f},{self.y:.1f}'

p = Point(3.14, 2.71)
assert format(p, 'tuple') == '(3.14, 2.71)'
assert format(p, 'verbose') == 'Point(3.14, 2.71)'
assert f'{p}' == '3.1,2.7'
assert '{:tuple}'.format(p) == '(3.14, 2.71)'   # str.format() calls __format__ too
```

### Inheriting `object.__format__`

A class with no `__format__` of its own anywhere but `object` gets `object.__format__`, which
formats as `str()` for an empty spec and rejects any other.

```python
class Plain:
    def __str__(self):
        return 'plain'

assert format(Plain()) == 'plain'   # the cost of str()

try:
    format(Plain(), '>10')
except TypeError as error:
    assert 'unsupported format string' in str(error)
else:
    raise AssertionError('object.__format__ accepted a spec')

class Broken:
    def __format__(self, spec):
        return 42

try:
    format(Broken())
except TypeError as error:
    assert 'must return a str' in str(error)
else:
    raise AssertionError('a non-str __format__ result was accepted')
```

## f-strings, str.format() and %

f-strings and `str.format()` call `__format__` for each field; `%s` calls `str()`
instead. All three are O(n) in the result plus the cost of converting each field.

```python
class Both:
    def __str__(self):
        return 'str'

    def __format__(self, spec):
        return 'format'

b = Both()
assert f'{b}' == 'format'
assert '{}'.format(b) == 'format'
assert format(b) == 'format'
assert '%s' % b == 'str'          # % does not call __format__
assert f'{b!s}' == 'str'          # !s converts with str() before formatting

value = 42.567
assert format(value, '.2f') == f'{value:.2f}' == '{:.2f}'.format(value) == '%.2f' % value
```

## Common Patterns

### Dates and Times

`datetime` implements `__format__` with `strftime()`, so a spec is a `strftime` pattern.

```python
from datetime import datetime

dt = datetime(2024, 1, 15, 14, 30, 0)
assert f'{dt:%Y-%m-%d}' == '2024-01-15'
assert f'{dt:%H:%M:%S}' == '14:30:00'
assert format(dt, '%Y-%m-%d %H:%M:%S') == '2024-01-15 14:30:00'
assert format(dt, '%A') == dt.strftime('%A') == 'Monday'
assert format(dt) == str(dt)        # an empty spec formats as str()
```

### Booleans and Complex Numbers

`bool` is an `int` subclass, so a numeric spec formats it as 0 or 1; with no spec it formats as
`str()` does. `complex` accepts `'e'`, `'f'` and `'g'` and applies them to both parts.

```python
assert format(True) == 'True'
assert format(True, 'd') == '1'
assert format(True, '05d') == '00001'
assert format(False, 'd') == '0'

assert format(3 + 4j) == '(3+4j)'
assert format(3 + 4j, '.2f') == '3.00+4.00j'
assert f'{3.14 + 2.71j}' == '(3.14+2.71j)'
```

## Performance Best Practices

✅ **Do**:

- Pass a string through `format()` or `f'{s}'` freely when it needs no padding: it is returned as is
- Use `'x'` or `'b'` for a very large `int` you only need to compare or store, rather than decimal
- Size a width or precision to what you will display; each character of it is paid for

❌ **Avoid**:

- Decimal-formatting large ints in a loop - each one is superlinear in its digits
- Raising `sys.set_int_max_str_digits()` to format untrusted ints in decimal
- Passing a format spec to an object that only has `object.__format__`

## Version Notes

- **Python 3.6+**: f-strings, and `'_'` as a grouping separator in the format spec
- **Python 3.12+**: decimal conversion of very large ints is subquadratic; see [int](int.md)
- **Python 3.14+**: `'_'` and `','` can group the fractional digits of a float as well (`'.6_f'`)

## Related Functions

- **[str()](str.md)** - `str.format()`, f-strings and `%` formatting
- **[repr()](repr.md)** - The unambiguous representation, which `!r` uses
- **[int()](int.md)** - Decimal conversion cost and the digit limit
- **[float()](float.md)** - Precision and the digits `'f'` writes
