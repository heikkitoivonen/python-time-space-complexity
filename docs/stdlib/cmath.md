# cmath Module Complexity

The `cmath` module provides complex-number versions of the `math` functions. Every function
works on fixed-width C doubles, a pair per complex argument, and keeps nothing between calls.

There are no size variables: every bound on this page is O(1) per call. Arguments are converted
first - a complex argument through `__complex__`, `__float__` or `__index__`, a real one such as
`rect()`'s through `__float__` or `__index__` - and that conversion is the one cost a caller
controls. An `int` too
large for a float raises `OverflowError` instead of being converted.

## Complexity Reference

### Power and Logarithmic Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cmath.exp(z)` | O(1) | O(1) | |
| `cmath.log(z[, base])` | O(1) | O(1) | Natural log unless `base` is given |
| `cmath.log10(z)` | O(1) | O(1) | |
| `cmath.sqrt(z)` | O(1) | O(1) | Principal square root, so `sqrt(-4)` is `2j` |

### Trigonometric Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cmath.sin(z)`, `cmath.cos(z)`, `cmath.tan(z)` | O(1) | O(1) | |
| `cmath.asin(z)`, `cmath.acos(z)`, `cmath.atan(z)` | O(1) | O(1) | |

### Hyperbolic Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cmath.sinh(z)`, `cmath.cosh(z)`, `cmath.tanh(z)` | O(1) | O(1) | |
| `cmath.asinh(z)`, `cmath.acosh(z)`, `cmath.atanh(z)` | O(1) | O(1) | |

### Conversions to and from Polar Coordinates

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cmath.phase(z)` | O(1) | O(1) | A `float`; on the negative real axis the sign of a zero imaginary part picks π or -π |
| `cmath.polar(z)` | O(1) | O(1) | A new `(abs(z), phase(z))` tuple |
| `cmath.rect(r, phi)` | O(1) | O(1) | The inverse of `polar()` |

### Classification Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cmath.isfinite(z)` | O(1) | O(1) | True only when both parts are finite |
| `cmath.isinf(z)`, `cmath.isnan(z)` | O(1) | O(1) | True when either part is infinite, or NaN |
| `cmath.isclose(a, b, *, rel_tol=1e-09, abs_tol=0.0)` | O(1) | O(1) | |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cmath.pi`, `cmath.e`, `cmath.tau`, `cmath.inf`, `cmath.nan` | O(1) | O(1) | `float` values, as in `math` |
| `cmath.infj`, `cmath.nanj` | O(1) | O(1) | `complex` values with a zero real part |

## Complex Arithmetic

Every function returns a `complex`, even when the input and the answer are real; `phase()`,
`polar()` and the classification functions return a `float`, a tuple or a `bool` instead.

```python
import cmath

z = 1 + 2j
value = cmath.sin(z)  # O(1)
assert isinstance(value, complex)

assert cmath.sqrt(-4) == 2j  # O(1) - math.sqrt(-4) raises instead
assert cmath.sqrt(4) == 2 + 0j and isinstance(cmath.sqrt(4), complex)
assert cmath.isclose(cmath.log(8, 2), 3)  # O(1)
assert cmath.isclose(cmath.exp(1j * cmath.pi), -1, abs_tol=1e-15)
```

### Domain and Range Errors

A finite input where the function is undefined raises `ValueError`, and one whose result is too
large for a double raises `OverflowError`, instead of returning NaN or an infinity.

```python
import cmath

try:
    cmath.log(0)
except ValueError as error:
    assert 'math domain error' in str(error)
else:
    raise AssertionError('log(0) returned a value')

try:
    cmath.exp(1000)
except OverflowError as error:
    assert 'math range error' in str(error)
else:
    raise AssertionError('exp(1000) returned a value')
```

## Argument Conversion

Arguments other than `complex` are converted before the function runs, once per argument. An
object's own `__complex__` or `__float__` is called once, so its cost is added to the call's;
an `int` is O(1) to convert because any `int` a double can hold is at most 1,024 bits.

```python
import cmath

class Meters:
    calls = 0

    def __init__(self, value):
        self.value = value

    def __float__(self):
        Meters.calls += 1
        return float(self.value)

assert cmath.sqrt(Meters(9)) == 3 + 0j  # O(1) plus one __float__ call
assert Meters.calls == 1

try:
    cmath.sqrt(10**400)
except OverflowError as error:
    assert 'too large to convert to float' in str(error)
else:
    raise AssertionError('an int beyond float range was converted')
```

## Polar and Rectangular Forms

`polar()` builds a two-item tuple; `abs(z)` and `phase(z)` return each part on its own.

```python
import cmath

z = 3 + 4j
r, phi = cmath.polar(z)  # O(1)
assert r == abs(z) == 5.0
assert phi == cmath.phase(z)  # O(1)

back = cmath.rect(r, phi)  # O(1)
assert cmath.isclose(back, z)

# The sign of a zero imaginary part chooses the side of the branch cut
assert cmath.phase(complex(-1.0, 0.0)) == cmath.pi
assert cmath.phase(complex(-1.0, -0.0)) == -cmath.pi
```

## Classification

```python
import cmath

z = complex('nan')
assert cmath.isnan(z)  # O(1)
assert cmath.isnan(complex(1, float('nan')))  # either part
assert cmath.isinf(cmath.infj) and not cmath.isfinite(cmath.infj)

# Compare computed values with a tolerance, not ==
assert cmath.sqrt(2) ** 2 != 2
assert cmath.isclose(cmath.sqrt(2) ** 2, 2)  # O(1)
```

## Common Patterns

### Applying a Function to Many Values

`cmath` works on one value per call, so a sequence of n values costs n calls.

```python
import cmath

roots_of_unity = [cmath.rect(1, 2 * cmath.pi * k / 4) for k in range(4)]  # O(n)
assert all(cmath.isclose(w ** 4, 1, abs_tol=1e-12) for w in roots_of_unity)  # O(n)
assert cmath.isclose(sum(roots_of_unity), 0, abs_tol=1e-12)
```

## Performance Best Practices

✅ **Do**:

- Use `abs(z)` or `cmath.phase(z)` when only one polar part is needed; `polar()` builds a tuple
- Pass `complex` or `float` values; anything else pays for its own `__complex__` or `__float__`
- Compare results with `cmath.isclose()`

❌ **Avoid**:

- Passing an object with a costly `__complex__` or `__float__` to several calls - convert it once
  with `complex(x)` and reuse the result
- Checking results for NaN to catch a domain error - an undefined point raises `ValueError`

## Related Modules

- **[math](math.md)** - the real-valued versions, which raise `ValueError` where `cmath` returns
  a complex result
- **[complex() Function](../builtins/complex_func.md)** - building complex numbers and their
  arithmetic
