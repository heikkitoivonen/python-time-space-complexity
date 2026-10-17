# round() Function Complexity

The `round()` function rounds a number to the nearest integer, or to a multiple of `10**-ndigits`,
and rounds exact halves to the even neighbour. It calls the number's `__round__` method, so the
cost belongs to the type: a float is converted to decimal digits and back, an int with a negative
`ndigits` is divided by a power of ten, and `Decimal` and `Fraction` do their own arithmetic.

`d` is the decimal digits `round(x, ndigits)` produces for a float: from `x`'s leading digit down to
the `10**-ndigits` place, stopping early where `x`'s exact decimal expansion ends. It is a few
digits for ordinary values, and reaches the hundreds for a huge `abs(x)`, or for a large `ndigits`
on a value whose expansion is long. For an int `n`, `b` is `abs(n).bit_length()` and `k` is
`-ndigits` when `ndigits` is negative.

## Complexity Reference

### float

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `round(x)`, `round(x, None)` | O(1) | O(1) | Returns an `int`; the result has at most 1,024 bits. `OverflowError` for an infinity, `ValueError` for a NaN |
| `round(x, ndigits)` | O(1); O(d²) at worst | O(d) | Returns a `float`: a correctly rounded conversion to decimal digits down to the `10**-ndigits` place, then back to binary |
| `round(x, ndigits)`, `ndigits > 323` or `ndigits < -308` | O(1) | O(1) | No conversion: returns `x` unchanged, or a zero with `x`'s sign |
| `round(x, ndigits)`, `x` infinite or NaN | O(1) | O(1) | Returns `x` |

### int

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `round(n)`, `round(n, ndigits)` with `ndigits >= 0` | O(1) | O(1) | An exact `int` is returned itself; nothing to round |
| `round(n, ndigits)` with `ndigits < 0` | O(b·k + k²) | O(b + k) | Builds `10**k`, then one division rounding half to even. A grade-school bound: CPython's Karatsuba multiplication beats the k² term. `10**k` is built even when `n` is far smaller |

### Other types

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `round(x)`, `round(x, ndigits)`, any other type | Cost of `__round__` | Cost of `__round__` | See [Decimal](../stdlib/decimal.md) and [Fraction](../stdlib/fractions.md); a type without `__round__` raises `TypeError` |
| `round(x, ndigits)`, float or int `x`, non-integer `ndigits` | O(1) | O(1) | Raises `TypeError`; another type's `__round__` receives `ndigits` as given |

## Rounding Floats

### Halves Round to Even

An exact half goes to the even neighbour, both for whole numbers and for decimal places.

```python
assert round(0.5) == 0      # O(1)
assert round(1.5) == 2
assert round(2.5) == 2
assert round(-2.5) == -2
assert round(5.4) == 5
assert isinstance(round(5.6), int)  # No ndigits: an int

assert round(0.125, 2) == 0.12  # 0.125 is exact in binary: a true half
assert round(0.375, 2) == 0.38
```

### Decimal Places Are Rounded on the Binary Value

`round(x, ndigits)` rounds the value the float actually holds. `2.675` is stored as slightly less
than 2.675, so it rounds down; a `Decimal` built from the string holds the half exactly.

```python
from decimal import Decimal

assert Decimal(2.675) < Decimal("2.675")  # The float is just below the half
assert round(2.675, 2) == 2.67            # O(1) - a few digits produced

assert round(Decimal("2.675"), 2) == Decimal("2.68")  # Half to even on an exact half
```

### Digits Produced

The conversion produces every digit from `x`'s leading digit down to the rounding place, so a
huge float produces hundreds. Past the end of `x`'s exact expansion there is nothing left to
produce, and an `ndigits` beyond the float's range skips the conversion.

```python
huge = 1.2345e300
assert round(huge, 2) == huge     # O(d²) - d is about 300 digits
assert round(-huge, -2) == -huge

assert round(1.5, 300) == 1.5     # O(1) - the expansion ends after one decimal
assert round(1.5, 400) == 1.5     # O(1) - beyond 323 places: returned unchanged
assert str(round(-3.0, -400)) == "-0.0"  # O(1) - a zero with x's sign
```

### Infinities and NaN

```python
inf = float("inf")
assert round(inf, 2) == inf  # O(1) - returned as is

try:
    round(inf)
except OverflowError as error:
    assert "infinity" in str(error)
else:
    raise AssertionError("expected OverflowError")

try:
    round(float("nan"))
except ValueError as error:
    assert "NaN" in str(error)
else:
    raise AssertionError("expected ValueError")
```

## Rounding Integers

### Negative ndigits

A non-negative `ndigits` leaves an int as it is. A negative one rounds to a multiple of `10**k`,
and builds that power of ten first, so its cost follows `k` even when `n` is small.

```python
n = 123_456_789
assert round(n) is n          # O(1) - the same object
assert round(n, 3) is n       # O(1)

assert round(1234, -2) == 1200  # O(b·k + k²)
assert round(1250, -2) == 1200  # Half to even
assert round(1350, -2) == 1400
assert round(-1250, -2) == -1200
assert round(5, -3) == 0        # 10**3 is built to find that out
```

## Other Numeric Types

`Decimal` and `Fraction` implement `__round__` themselves. With `ndigits`, both return their own
type; without it, both return an `int`.

```python
from decimal import Decimal
from fractions import Fraction

assert round(Decimal("2.675"), 2) == Decimal("2.68")  # O(r + n), see the decimal page
assert isinstance(round(Decimal("2.5")), int)
assert round(Decimal("2.5")) == 2

assert round(Fraction(5, 2)) == 2                     # Half to even
assert round(Fraction(31415, 10000), 3) == Fraction(1571, 500)

try:
    round("1.5")
except TypeError as error:
    assert "__round__" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Common Patterns

### Rounding a Collection

Rounding is one call per item, so a collection of ordinary floats costs time linear in its length.

```python
measurements = [1.234, 1.256, 1.267, 1.278]
rounded = [round(m, 2) for m in measurements]

assert rounded == [1.23, 1.26, 1.27, 1.28]
```

### round(), int() and Formatting

`round()` rounds to the nearest value, `int()` truncates toward zero, and an f-string produces
text instead of a number.

```python
assert round(5.6) == 6 and int(5.6) == 5
assert round(-5.6) == -6 and int(-5.6) == -5

x = 3.14159
assert round(x, 2) == 3.14          # A float
assert f"{x:.2f}" == "3.14"         # A string
assert round(1234.5, -1) == 1230.0  # Negative ndigits on a float returns a float
```

## Performance Best Practices

✅ **Do**:

- Rely on `round(n)` and `round(n, ndigits)` with `ndigits >= 0` being O(1) for an int: it returns the int itself

❌ **Avoid**:

- `round(n, -k)` with a `k` far beyond the digits of `n`: it builds `10**k` first, at a cost that grows with `k`
- Rounding floats of huge magnitude to decimal places in a hot loop: each call produces every digit before the rounding place

## Related Functions

- **[int()](int.md)** - Truncates toward zero instead of rounding
- **[format()](format.md)** - Rounds for display and returns a string
- **[decimal.Decimal](../stdlib/decimal.md)** - Exact decimal values, rounded by `quantize()` or `round(d, k)`
- **[fractions.Fraction](../stdlib/fractions.md)** - Exact rationals with their own `__round__`
