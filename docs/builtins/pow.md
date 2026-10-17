# pow() Function Complexity

The `pow()` function raises a base to an exponent. `pow(x, y)` is the `**`
operator; `pow(x, y, z)` is a separate algorithm that reduces modulo `z` at
every step, so it is not a shortcut spelling of `(x ** y) % z`.

An integer power's cost follows the width of its result, not the exponent's
magnitude: exponentiation by squaring makes O(e) multiplications, but their
operands grow, so their count alone is not a time bound.

For integer operands, `b = max(1, abs(x).bit_length())`,
`e = max(1, abs(y).bit_length())`, and `m = abs(z).bit_length()` for a nonzero
modulus. For `abs(x) >= 2` and `y > 0`, the result width is
`r = floor(y * log2(abs(x))) + 1 = Θ(b * y)`; `b * y` is a size estimate,
not an exact bit count. Space includes the result and temporary allocations,
but excludes the input integers.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pow(x, y)`, float base or exponent | O(1); O(b) or O(e) at worst for an int | O(1) | Fixed-precision arithmetic, independent of magnitude; a negative base with a fractional exponent returns a complex. An int on the other side is converted to a float first: O(1) for most ints, O(b) or O(e) at worst |
| `pow(x, y)`, integers, `y < 0` | O(b + e) | O(1) | Both operands are converted to floats, which reads their top bits and scans the lower ones until one is nonzero: O(1) for most ints, O(b + e) for a power of two. Returns a float; `OverflowError` once the base exceeds float range |
| `pow(x, 0)` | O(1) | O(1) | Returns `1`, including `0 ** 0` |
| `pow(x, y)`, `x` is `0`, `1` or `-1`, `y > 0` | O(e) | O(1) | The result is `0`, `1`, or `-1`; scanning the exponent still costs time |
| `pow(x, y)`, integers, `abs(x) >= 2`, `y > 0` | O(r²) | Θ(r) | A grade-school upper bound; CPython's Karatsuba multiplication beats it for large operands |
| `pow(x, y, z)`, `y >= 0` | O(b * m + e * m²) | O(b + m) | Includes initial reduction of a wide base; subsequent modular arithmetic uses O(m)-bit values |
| `pow(x, y, z)`, `y < 0` | O(b * m + e * m²) | O(b + m + e) | Inverts the base modulo `z`, and allocates a copy of the exponent |
| `x ** y` | Same as `pow(x, y)` | Same as `pow(x, y)` | One operation. CPython folds some literal powers with small results at compile time, such as `2 ** 8`; `2 ** 1000` is computed at run time |
| `pow(x, y)`, any other type | Cost of `__pow__` or `__rpow__` | Cost of `__pow__` or `__rpow__` | `Decimal`, `Fraction`, `complex` and other types delegate; `type(x).__pow__` receives the modulus too |

## Integer Powers

### Result Width

The result's width grows with both the base's width and the exponent, so the
base's width is a size variable of its own.

```python
assert pow(2, 3) == 8
assert pow(2, 100) == 1267650600228229401496703205376  # O(r²), r = 101 bits

# The base's width counts as much as the exponent does
assert pow(2, 1000).bit_length() == 1001
assert pow(10, 1000).bit_length() == 3322
```

### Negative Exponents

Without a modulus, a negative exponent sends both operands through `float`, so
the result is a float and a base beyond float range is rejected.

```python
assert pow(2, -1) == 0.5   # O(1) for most ints
assert pow(2, -2) == 0.25
assert isinstance(pow(2, -1), float)

try:
    pow(10**1000, -1)
except OverflowError as error:
    assert "too large to convert to float" in str(error)
else:
    raise AssertionError("expected OverflowError")
```

## Float Powers

A float operand makes the power fixed-precision arithmetic, whatever the magnitude.

```python
import math

assert pow(2.0, 3) == 8.0
assert pow(2.5, 2) == 6.25
assert pow(2.0, 0.5) == 1.4142135623730951
assert math.isclose(pow(1.7e308, 0.99), 1.4065152073912217e305)  # O(1) - no dearer than a small base

# A negative base with a fractional exponent returns a complex number
result = pow(-8, 1 / 3)
assert isinstance(result, complex)
assert abs(result - (1 + 1.7320508075688772j)) < 1e-12
```

## Modular Exponentiation

### Three-Argument pow()

With an already-reduced base (`0 <= x < abs(z)`), the modular bounds simplify
to O(e * m²) time and O(m) space for a nonnegative exponent, or O(m + e) space
for a negative one. Reduction limits residues to `m` bits; products before
reduction can be wider.

```python
assert pow(2, 10, 1000) == 24   # O(e * m²) for a reduced base
assert pow(3, 100, 7) == 4
assert pow(2, 1000, 13) == 3

# A negative modulus gives a result with the modulus's sign, or zero
assert pow(2, 10, -1000) == -976
assert pow(2, 3, -8) == 0

try:
    pow(2, 10, 0)
except ValueError as error:
    assert "cannot be 0" in str(error)
else:
    raise AssertionError("expected ValueError")

try:
    pow(2.0, 3, 5)
except TypeError as error:
    assert "all arguments are integers" in str(error)
else:
    raise AssertionError("expected TypeError")
```

### Reducing During or After

After base preprocessing, the three-argument form works on O(m)-bit values. For
`abs(x) >= 2` and `y > 0`, the two-step form builds the whole Θ(b * y)-bit
power first and reduces afterwards. The three-argument form wins once that
power is much wider than the modulus - RSA-sized exponents, rolling hashes,
number theory.

```python
# The full power is 11 bits, barely wider than the 10-bit modulus
assert pow(2, 10, 1000) == (2 ** 10) % 1000 == 24

message, exponent, modulus = 42, 65537, 10**9 + 7
assert pow(message, exponent, modulus) == 115812009       # residues within 30 bits
assert (message ** exponent) % modulus == 115812009       # a 353,397-bit intermediate
assert (message ** exponent).bit_length() == 353_397
```

### Modular Inverse

A negative exponent alongside a modulus inverts the base, then raises the
inverse to the exponent's magnitude.

```python
assert pow(3, -1, 1000) == 667   # O(e * m²) time, O(m + e) space for a reduced base
assert 3 * 667 % 1000 == 1
assert pow(3, -5, 1000) == pow(667, 5, 1000) == 107

# The base has to be coprime with the modulus
try:
    pow(4, -1, 8)
except ValueError as error:
    assert "not invertible" in str(error)
else:
    raise AssertionError("expected ValueError")
```

## Exact Powers of Two

For an exact power of two, a shift builds the result in Θ(n) and squares
nothing.

```python
n = 1_000_000
assert pow(2, n) == 1 << n   # the shift is Θ(n); pow() squares its way there
```

## Edge Cases

A zero exponent never enters the loop. An exponent of one still builds a new
integer, O(b) for a wide base.

```python
base = 7

assert pow(base, 0) == 1   # O(1)
assert pow(0, 0) == 1      # by convention
assert pow(-5, 0) == 1
assert pow(2.5, 0) == 1.0

assert pow(base, 1) == 7
assert pow(2.5, 1) == 2.5

assert pow(0, 5) == 0
try:
    pow(0, -1)
except ZeroDivisionError:
    pass
else:
    raise AssertionError("expected ZeroDivisionError")
```

## Performance Best Practices

✅ **Do**:

- Use `pow(x, y, z)` wherever `x ** y` would be much wider than `z`, and
  `pow(x, -1, z)` for a modular inverse
- Use `1 << n` for an exact power of two
- Size an integer power from the width of its result, not from the exponent's
  magnitude

❌ **Avoid**:

- Reading `O(log y)` as a time bound - it counts multiplications, whose operands
  grow
- Building `(x ** y) % z` for cryptographic-sized exponents
- Calling `str()` on a wide result without raising
  `sys.set_int_max_str_digits()`

## Version Notes

- **Python 3.8+**: `pow(x, y, z)` accepts a negative `y`, inverting the base
  modulo `z` first; the arguments became keyword-capable as `base`, `exp` and `mod`
- **Python 3.11+, and 3.10.7+**: `str()` on an integer wider than the default
  limit of 4300 digits raises `ValueError` until `sys.set_int_max_str_digits()`
  lifts it

## Related Functions

- **[abs()](abs.md)** - Absolute value
- **[divmod()](divmod.md)** - Quotient and remainder in one call
- **[int](int.md)** - Arbitrary-precision integer arithmetic, including `**`
- **[math.pow()](../stdlib/math.md)** - Always returns a float, and overflows
  where `pow()` stays exact
- **[math.isqrt()](../stdlib/math.md)** - Exact integer square root
