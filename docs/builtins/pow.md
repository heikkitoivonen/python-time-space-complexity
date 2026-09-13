# pow() Function Complexity

The `pow()` function raises a base to an exponent. `pow(x, y)` is the `**`
operator; `pow(x, y, z)` is a separate algorithm that reduces modulo `z` at
every step, so it is not a shortcut spelling of `(x ** y) % z`.

## Complexity Analysis

For integer operands, let `b = max(1, abs(x).bit_length())`,
`e = max(1, abs(y).bit_length())`, and `m = abs(z).bit_length()` for a nonzero
modulus. For `abs(x) >= 2` and `y > 0`, the result width is
`r = floor(y * log2(abs(x))) + 1 = Θ(b * y)`; `b * y` is a size estimate,
not an exact bit count. Space includes the result and temporary allocations,
but excludes the input integers.

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Float base or exponent | O(1) | O(1) | One libm call, independent of magnitude |
| Integer base, `y < 0` | O(1) | O(1) | Returns a float; `OverflowError` once the base exceeds float range |
| Integer base, `y = 0` | O(1) | O(1) | Returns `1`, including `0 ** 0` |
| Integer base `0`, `1`, or `-1`, `y > 0` | O(e) | O(1) | The result is `0`, `1`, or `-1`; scanning the exponent still costs time |
| Integer base with `abs(x) >= 2`, `y > 0` | O(r²) | Θ(r) | The result grows with both base width and exponent |
| `pow(x, y, z)`, `y >= 0` | O(b * m + e * m²) | O(b + m) | Includes initial reduction of a wide base; subsequent modular arithmetic uses O(m)-bit values |
| `pow(x, y, z)`, `y < 0` | O(b * m + e * m²) | O(b + m + e) | 3.8+. Includes base inversion and an allocated copy of the exponent |
| Any other type | `type(x).__pow__` | — | `Decimal`, `Fraction`, `complex` and other types delegate; cost is the operand type's |

The modular bounds are worst-case upper bounds. With an already-reduced base
(`0 <= x < abs(z)`), they simplify to O(e * m²) time and O(m) space for
nonnegative exponents, or O(m + e) space for negative exponents. Reduction
limits residues to `m` bits; products before reduction can be wider.
[CPython's integer power implementation](https://github.com/python/cpython/blob/v3.14.7/Objects/longobject.c#L4584)
includes both base preprocessing and the negative-exponent copy.

Exponentiation by squaring uses O(e) multiplications. For a two-argument power
with `abs(x) >= 2`, those multiplications operate on growing integers, so their
count alone is not a time bound.

## Basic Usage

### Integer Powers

```python
# O(r²) for a result of r = Θ(b*y) bits
pow(2, 3)      # 8
pow(2, 10)     # 1024
pow(2, 100)    # 1267650600228229401496703205376

# The base's width counts as much as the exponent does
(2 ** 1000).bit_length()    # 1001
(10 ** 1000).bit_length()   # 3322

# Negative exponent - O(1), but the result is a float
pow(2, -1)     # 0.5
pow(2, -2)     # 0.25
```

### Float Powers

```python
# O(1) - one libm call, whatever the magnitude
pow(2.0, 3)           # 8.0
pow(2.5, 2)           # 6.25
pow(2.0, 0.5)         # 1.4142135623730951
pow(1.7e308, 0.99)    # 1.4065152073912217e+305, no dearer than the line above

# A negative base with a fractional exponent returns a complex number
pow(-8, 1 / 3)        # (1.0000000000000002+1.7320508075688772j)
```

### Modular Exponentiation

```python
# O(e * m²) for these already-reduced bases
pow(2, 10, 1000)      # 24
pow(3, 100, 7)        # 4
pow(2, 1000, 13)      # 3

# A negative modulus gives a negative result; a zero modulus is rejected
pow(2, 10, -1000)     # -976
try:
    pow(2, 10, 0)
except ValueError:
    pass              # pow() 3rd argument cannot be 0

# All three arguments must be integers
try:
    pow(2.0, 3, 5)
except TypeError:
    pass              # not allowed unless all arguments are integers
```

## Modular Inverse

A negative exponent alongside a modulus inverts the base, which is the cheapest
way to divide in modular arithmetic.

```python
# Python 3.8+. O(e * m²) time and O(m + e) space for a reduced base
pow(3, -1, 1000)      # 667, because 3 * 667 == 2001 == 1 (mod 1000)
pow(3, -5, 1000)      # 107

# The base has to be coprime with the modulus
try:
    pow(4, -1, 8)
except ValueError:
    pass              # base is not invertible for the given modulus
```

## Reducing During or After

After base preprocessing, the three-argument form uses O(m)-bit arithmetic
values. For `abs(x) >= 2` and `y > 0`, the two-step form builds the whole
Θ(b * y)-bit power first and reduces afterwards.

```python
# Both give 24. The full power is only 11 bits in this small example
pow(2, 10, 1000)
(2 ** 10) % 1000

# Both give 115812009. The two-step form builds a 353,397-bit intermediate;
# the three-argument form keeps residues within the 30-bit modulus
message, exponent, modulus = 42, 65537, 10**9 + 7
pow(message, exponent, modulus)
(message ** exponent) % modulus
```

Reach for `pow(x, y, z)` when `b * y` is large - RSA-sized exponents, rolling
hashes, number theory. Below that the spelling is a matter of taste.

## Exact Powers of Two

For an exact power of two, a shift replaces the exponentiation loop.

```python
n = 1_000_000
pow(2, n) == 1 << n   # True, but the shift is Θ(n) and squares nothing
```

## Edge Cases

```python
base = 7

# O(1) - the loop never runs
pow(base, 0)     # 1
pow(0, 0)        # 1, by convention
pow(-5, 0)       # 1
pow(2.5, 0)      # 1.0

# Returns the base value; a wide integer result takes O(b) space
pow(base, 1)     # 7
pow(2.5, 1)      # 2.5

# Zero base
pow(0, 5)        # 0
try:
    pow(0, -1)
except ZeroDivisionError:
    pass

# A negative exponent routes through float, which a wide base cannot reach
try:
    pow(10**1000, -1)
except OverflowError:
    pass         # int too large to convert to float
```

## Best Practices

✅ **Do**:

- Use `pow(x, y, z)` wherever `b * y` would be large, and `pow(x, -1, z)` for a
  modular inverse
- Use `1 << n` for an exact power of two
- Size an integer power from the width of its result, not from the exponent's
  magnitude

❌ **Avoid**:

- Reading `O(log y)` as a time bound - it counts multiplications, whose operands
  grow
- Building `(x ** y) % z` for cryptographic-sized exponents
- Calling `str()` on a wide result without raising
  `sys.set_int_max_str_digits()`

## Performance Notes

- The quadratic bounds are grade-school ones; CPython's Karatsuba
  multiplication beats them for large operands.
- `pow(x, y)` and `x ** y` are one operation. With literal operands `**` is
  folded at compile time, so only `pow()` is still a call at run time.

## Related Functions

- **[abs()](abs.md)** - Absolute value
- **[divmod()](divmod.md)** - Quotient and remainder in one call
- **[int](int.md)** - Arbitrary-precision integer arithmetic, including `**`
- **[math.pow()](../stdlib/math.md)** - Always returns a float, and overflows
  where `pow()` stays exact
- **[math.isqrt()](../stdlib/math.md)** - Exact integer square root

## Version Notes

- **Python 3.8+**: `pow(x, y, z)` accepts a negative `y` and returns the modular
  inverse; the arguments became keyword-capable as `base`, `exp` and `mod`
- **Python 3.11+, and 3.10.7+**: `str()` on an integer wider than 4300 digits
  raises `ValueError` until `sys.set_int_max_str_digits()` lifts the limit
