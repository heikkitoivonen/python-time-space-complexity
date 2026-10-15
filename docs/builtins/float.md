# Float Type Complexity

A `float` is a fixed-size object holding one C `double`, which is an IEEE 754 binary64 value on
every platform CPython supports: 53 significant bits, and a finite range up to about 1.8e308.
Its width never depends on its value, so arithmetic between floats, comparison and hashing are
O(1), and so is every conversion whose output that width bounds: `repr()`, `int()`, `hex()`,
`as_integer_ratio()`.

Three size variables appear below: `n` is the length of a string being parsed, `p` is the
precision or width a format specification asks for, and `d` is the length in digits of an `int`
operand that has to be converted to a float. An operation that produces a float returns
a new fixed-size object, except where a row says it returns `x` itself. That holds for an exact
float; an instance of a subclass gets a new plain `float` instead.

## Complexity Reference

### Arithmetic

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x + y`, `x - y`, `x * y`, `x / y` | O(1); O(d) at worst for an int | O(1) | O(d) at worst with an `int` operand, which is converted to float first; one beyond the float range raises `OverflowError`. A float result that overflows is `inf` |
| `x // y`, `x % y`, `divmod(x, y)` | O(1); O(d) at worst for an int | O(1) | O(d) at worst with an `int` operand, as for `+` |
| `x ** y`, `pow(x, y)` | O(1); O(d) at worst for an int | O(1) | O(1) for any float `y`; O(d) at worst for an `int` `y`, as for `+`. A negative `x` with a non-integer `y` returns a `complex`; a result beyond the float range raises `OverflowError` |
| `-x`, `abs(x)` | O(1) | O(1) | |
| `+x` | O(1) | O(1) | Returns `x` itself |
| `bool(x)` | O(1) | O(1) | `False` only for `0.0` and `-0.0` |

### Comparison

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x == y`, `x != y` | O(1) | O(1) | Exact against an `int` of any size: the int is not rounded to a float, and its size does not change the cost |
| `x < y`, `x <= y`, `x > y`, `x >= y` | O(1) | O(1) | Exact against an `int` of any size, as for `==` |

### Conversion and Formatting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hash(x)` | O(1) | O(1) | Equals `hash(int(x))` when `x` is integral, so `1.0` and `1` are the same dict key |
| `str(x)`, `repr(x)`, `f"{x}"` | O(1) | O(1) | The fewest significant digits that read back as `x` |
| `format(x, spec)`, `f"{x:{spec}}"` | O(p) | O(p) | `'f'` and `'e'` write every digit of the precision; `'f'` also writes every integer digit, up to 309 for the largest floats |
| `int(x)`, `math.trunc(x)`, `math.floor(x)`, `math.ceil(x)`, `round(x)` | O(1) | O(1) | The int returned is at most 1,024 bits wide. `OverflowError` for an infinity, `ValueError` for a NaN |
| `round(x, ndigits)` | O(1) | O(1) | Returns a float |
| `float(x)` | O(n) for a string; O(d) at worst for an int; O(1) for a float | O(1) | For a string; O(n) space when it contains underscores or non-ASCII characters. O(d) at worst for an `int`; O(1) for a `float`, and returns an exact float `x` itself. See [float()](float_func.md) |

### float Methods and Attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x.is_integer()` | O(1) | O(1) | |
| `x.as_integer_ratio()` | O(1) | O(1) | Exact and in lowest terms; the denominator is a power of two, at most 2**1074 |
| `x.hex()` | O(1) | O(1) | Exact; `float.fromhex()` reads it back |
| `float.fromhex(s)` | O(n) | O(1) | Class method. O(1) space holds for ASCII text; a non-ASCII string is copied to UTF-8 before it is rejected with `ValueError` |
| `x.conjugate()`, `x.real` | O(1) | O(1) | Return `x` itself |
| `x.imag` | O(1) | O(1) | Always `0.0` |
| `float.from_number(x)` | O(1); O(d) at worst for an int | O(1) | Class method, Python 3.14+. Returns an exact float `x` itself; for a non-float, adds the cost of its `__float__()` or `__index__()`, and an int that `__index__()` returns is converted in O(d) at worst. Unlike `float()`, rejects strings |

## Arithmetic

Every operator works on two doubles, so `x ** y` costs the same for a huge float `y` as
for a small one. Overflow is where the operators differ: `*` and `+` return `inf`, while `**`
raises.

```python
import math

x = 3.14
y = 2.71

assert math.isclose(x + y, 5.85)       # O(1)
assert math.isclose(x * y, 8.5094)     # O(1)
assert 0.5 ** 1e15 == 0.0              # O(1) - not 1e15 multiplications
assert 1e308 * 10 == math.inf          # O(1) - overflow gives inf

try:
    10.0 ** 400
except OverflowError:
    pass
else:
    raise AssertionError('10.0 ** 400 did not overflow')

root = (-8.0) ** (1 / 3)               # O(1) - a complex result
assert isinstance(root, complex)
assert math.isclose(root.real, 1.0)
```

## Mixing Floats and Ints

A comparison between a float and an int is exact, whatever the int's size, and costs the same
for a 100,000-digit int as for a small one. Arithmetic converts the int to a float first, which
rounds it to 53 bits and fails for an int beyond the float range. The conversion reads the int's
top bits and then scans the lower ones until one is nonzero, so it is O(d) at worst: an int such
as `2**k`, whose lower bits are all zero, is read in full, even when it is too large and is then
rejected.

```python
big = 10 ** 100_000

assert 1.5 < big                       # O(1) - big is not converted
assert 2 ** 53 + 1 != float(2 ** 53 + 1)   # exact: the float rounded down
assert float(2 ** 53 + 1) == 2 ** 53

try:
    1.5 + big                          # O(d) at worst - the int must become a float first
except OverflowError as error:
    assert 'too large to convert to float' in str(error)
else:
    raise AssertionError('a huge int was added to a float')
```

## Converting and Formatting

`str()` and `repr()` write the fewest significant digits that read back as the same float, so
their output is bounded. A precision in a format specification is not: with `'f'` or `'e'`,
`format()` writes every digit asked for. Conversions to `int` are bounded by the largest float, whose integer value is 1,024
bits wide.

```python
import math

x = 0.1

assert repr(x) == '0.1'                         # O(1) - fewest digits that round-trip
assert len(format(x, '.1000f')) == 1002         # O(p) - every digit requested
assert len(format(1e300, '.0f')) == 301         # 'f' writes every integer digit

assert int(1.7976931348623157e308).bit_length() == 1024   # O(1)
assert x.as_integer_ratio() == (3602879701896397, 2 ** 55)

text = x.hex()                                  # O(1) - exact
assert text == '0x1.999999999999ap-4'
assert float.fromhex(text) == x                 # O(n), n = len(text)

for bad, error in ((math.inf, OverflowError), (math.nan, ValueError)):
    try:
        int(bad)
    except error:
        pass
    else:
        raise AssertionError(f'int({bad}) did not raise')
```

## Rounding and Truncation

`round(x)` and the `math` functions return ints; `round(x, ndigits)` returns a float.
`round()` works on the binary value, so a decimal halfway case stored as slightly less than half
rounds down.

```python
import math

x = 3.14159

assert round(x, 2) == 3.14             # O(1) - a float
assert round(x) == 3                   # O(1) - an int
assert math.floor(x) == 3              # O(1)
assert math.ceil(x) == 4               # O(1)
assert math.trunc(-x) == -3            # O(1) - toward zero

assert round(2.675, 2) == 2.67         # 2.675 is stored as 2.67499999...
```

## Performance Best Practices

✅ **Do**:

- Compare a float with an int directly: it is exact and O(1) for any int
- Use `repr()` or `str()` when a round-trip string is enough; its length is bounded
- Use `hex()` and `float.fromhex()` for an exact text form of a float

❌ **Avoid**:

- Arithmetic between a float and an int that may exceed the float range: it raises
  `OverflowError`
- A format precision larger than the digits you need: `'f'` and `'e'` write all of them
- Comparing computed floats with `==` when rounding error is possible; use `math.isclose()`

## Version Notes

- **Python 3.14+**: Added `float.from_number()`

## Related Types

- **[Int](int.md)** - Arbitrary precision integers
- **[float()](float_func.md)** - Parsing strings and converting other objects
- **[Complex](complex_func.md)** - Complex floating-point numbers
- **[Decimal](../stdlib/decimal.md)** - Arbitrary precision decimal
- **[Fraction](../stdlib/fractions.md)** - Rational numbers

## Further Reading

- [CPython Internals: float](https://zpoint.github.io/CPython-Internals/BasicObject/float/float.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's float implementation
