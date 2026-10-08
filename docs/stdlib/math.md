# math Module Complexity

The `math` module wraps the C math library for floats and adds a handful of exact integer
functions. The float functions take and return a fixed-width C double, so each is a constant
amount of work; the integer functions work on arbitrary-precision ints and scale with their
digits. Nothing in the module keeps state between calls.

`m` is the values in an iterable or the coordinates passed, `w` is the digits of an int argument
(the wider operand of `gcd` and `lcm`), `s` is the digits of the narrower `gcd` or `lcm` operand,
and `d` is the digits of an integer result. `n` and `k` are function arguments, never sizes.
One libm call or float operation counts as O(1); an int passed to a float function is converted
first, at the cost *Integer Arguments* below gives.
The integer bounds count digit operations with schoolbook multiplication and division; CPython
multiplies large ints with Karatsuba, so big operands can beat them.

## Complexity Reference

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.pi`, `math.e`, `math.tau`, `math.inf`, `math.nan` | O(1) | O(1) | Module attributes holding floats |

### Powers, roots and logarithms

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.sqrt(x)`, `math.cbrt(x)` | O(1) | O(1) | `cbrt` is Python 3.11+ |
| `math.exp(x)`, `math.exp2(x)`, `math.expm1(x)` | O(1) | O(1) | `exp2` is Python 3.11+ |
| `math.pow(x, y)` | O(1) | O(1) | Always a float: raises `OverflowError` where the builtin `pow` returns an exact int |
| `math.log(x[, base])`, `math.log2(x)`, `math.log10(x)` | O(1) | O(1) | Also take an int too large for any float |
| `math.log1p(x)` | O(1) | O(1) | |

### Trigonometric, hyperbolic and special functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.sin(x)`, `math.cos(x)`, `math.tan(x)`, `math.asin(x)`, `math.acos(x)`, `math.atan(x)`, `math.atan2(y, x)` | O(1) | O(1) | |
| `math.sinh(x)`, `math.cosh(x)`, `math.tanh(x)`, `math.asinh(x)`, `math.acosh(x)`, `math.atanh(x)` | O(1) | O(1) | |
| `math.degrees(x)`, `math.radians(x)` | O(1) | O(1) | |
| `math.erf(x)`, `math.erfc(x)`, `math.gamma(x)`, `math.lgamma(x)` | O(1) | O(1) | `lgamma(n + 1)` is the natural log of `n!` without building `n!` |

### Floating-point manipulation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.fabs(x)`, `math.copysign(x, y)` | O(1) | O(1) | |
| `math.fmod(x, y)`, `math.remainder(x, y)`, `math.modf(x)` | O(1) | O(1) | |
| `math.frexp(x)`, `math.ldexp(x, i)` | O(1) | O(1) | |
| `math.nextafter(x, y, steps=None)`, `math.ulp(x)` | O(1) | O(1) | `steps` is Python 3.12+, and any number of steps is one jump rather than a walk |
| `math.fma(x, y, z)` | O(1) | O(1) | Python 3.13+ |

### Rounding and classification

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.floor(x)`, `math.ceil(x)`, `math.trunc(x)` | O(1) | O(1) | An int argument is returned unchanged, however many digits it has |
| `math.isfinite(x)`, `math.isinf(x)`, `math.isnan(x)` | O(1) | O(1) | An int beyond the float range raises `OverflowError` rather than answering |
| `math.isclose(a, b, *, rel_tol=1e-09, abs_tol=0.0)` | O(1) | O(1) | |

### Sums and products

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.fsum(iterable)` | O(m) | O(1) | Tracks partial sums, whose number is capped by the float exponent range, not by m |
| `math.sumprod(p, q)` | O(m) | O(1) | Python 3.12+; float inputs |
| `math.prod(iterable, *, start=1)` | O(m) | O(1) | Float values. With nonzero int values the running product grows: O(d·(m + d)) time and O(d) space |
| `math.hypot(*coordinates)` | O(m) | O(m) | Holds every coordinate before it scales them |
| `math.dist(p, q)` | O(m) | O(m) | Holds every coordinate difference, like `hypot` |

### Integer functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.gcd(*integers)` | O(w·s) | O(w) | Two operands; O(w²) when they are of equal size. Further arguments are taken one at a time against the running result |
| `math.lcm(*integers)` | O(w·s) | O(w + s) | Two operands; the result can carry both of their digits. Further arguments are taken one at a time against the running result |
| `math.isqrt(n)` | O(w²) | O(w) | Exact at any size |
| `math.factorial(n)` | O(d²) | O(d) | d grows as n log n |
| `math.comb(n, k)` | O(d²) | O(d) | Driven by min(k, n - k): `comb(n, n - k)` costs what `comb(n, k)` does |
| `math.perm(n, k=None)` | O(d²) | O(d) | Driven by k, with no mirror; `perm(n)` is `factorial(n)` |

## Float Functions

### Integer Arguments

The float functions convert an int argument to a float first. The conversion reads the int's
leading digits, so it is O(1) for most ints and O(w) at worst, and a value beyond the float range
raises `OverflowError` - the predicates included. Two groups are exempt: `floor()`, `ceil()` and
`trunc()` hand an int back unchanged, and `log()`, `log2()` and `log10()` take an int of any size.

```python
import math

big = (1 << 2000) + 1

# Returned unchanged - O(1)
assert math.floor(big) is big

# The logarithms take an int no float can hold
assert math.isclose(math.log2(big), 2000.0)
assert math.isclose(math.log(big), 2000 * math.log(2))

# Everything else converts first, and no float holds this
for function in (math.sqrt, math.exp, math.isfinite):
    try:
        function(big)
    except OverflowError as error:
        assert 'too large' in str(error)
    else:
        raise AssertionError(f'{function.__name__} took an int beyond the float range')
```

### math.pow and the Builtin pow

`math.pow()` converts both arguments and returns a float, so it is O(1) and overflows where an
exact answer would not fit. The builtin `pow()` keeps ints exact and pays for the digits.

```python
import math

assert math.pow(2, 10) == 1024.0  # O(1), always a float

try:
    math.pow(2, 2000)
except OverflowError:
    pass
else:
    raise AssertionError('math.pow returned a float beyond the float range')

assert pow(2, 2000).bit_length() == 2001  # exact, and sized by its digits
```

## Sums and Products

### Which Ones Hold Their Input

All five are O(m) in time. `hypot()` and `dist()` hold every coordinate before they scale
them, so their memory grows with the input; `fsum()`, `sumprod()` and `prod()` over floats keep a
constant.

```python
import math
import sys

# O(m) time and O(m) space
assert math.hypot(3.0, 4.0) == 5.0
assert math.hypot(1.0, 2.0, 2.0) == 3.0
assert math.dist((0.0, 0.0), (3.0, 4.0)) == 5.0

# O(m) time and O(1) space
assert math.fsum([0.1] * 10) == 1.0
assert math.prod([2.0, 3.0, 7.0]) == 42.0
if sys.version_info >= (3, 12):
    assert math.sumprod([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]) == 32.0
```

`prod()` over ints is the exception. The running product gains digits with every nonzero factor
other than ±1, so the cost follows the result as well as the number of terms:

```python
import math

result = math.prod([3] * 2000)  # O(d·(m + d)), d = digits of the result
assert result.bit_length() == 3170
```

### Accurate Summation

`fsum()` avoids loss of precision by tracking intermediate partial sums. From Python 3.12 the
builtin `sum()` carries a compensation term when it adds floats, which is enough for the textbook
example but not for every input:

```python
import math
import sys

values = [1e100, 1.0, -1e100]
assert math.fsum(values) == 1.0  # O(m), O(1) space
assert sum(values) == (1.0 if sys.version_info >= (3, 12) else 0.0)

# Three magnitudes still separate them on every version
values = [1e16, 1.0, 1e-16, -1e16, -1.0]
assert math.fsum(values) == 1e-16
assert sum(values) != math.fsum(values)
```

## Integer Functions

### gcd and lcm

`gcd()` reduces the wider operand by the narrower one first, so it costs O(w·s): a huge int and a
small one cost time linear in the huge one, and two operands of equal size cost O(w²). `lcm()`
calls `gcd()` and then divides and multiplies, which costs the same order.

```python
import math

assert math.gcd(84, 30) == 6  # O(w·s)
assert math.lcm(6, 10) == 30  # O(w·s)

# Both take any number of arguments
assert math.gcd(12, 18, 30) == 6
assert math.lcm(4, 6, 10) == 60
```

### factorial, comb and perm

All three cost O(d²) in the digits of the result, so the cost variable is the size of the answer,
not of the arguments; only an n of many digits adds anything, the O(w) of reading it. What sets
the size of the answer for `comb()` is min(k, n - k): `comb(n, k) == comb(n, n - k)`, and a k
near n costs what the small k it mirrors costs. `perm()` has no such identity, so a large k is a
large result. n on its own barely matters to either: it widens each factor only by log n.

```python
import math

assert math.factorial(10) == 3628800  # O(d²)
assert math.comb(10, 3) == 120        # O(d²)
assert math.perm(10, 3) == 720        # O(d²)

# comb mirrors, so these two are the same value and the same work
assert math.comb(1000, 5) == math.comb(1000, 995) == 8250291250200

# perm does not: k = 995 is a result of thousands of bits
assert math.perm(1000, 5) == 990034950024000
assert math.perm(1000, 995).bit_length() > 100 * math.perm(1000, 5).bit_length()
```

### isqrt

`isqrt()` is exact on ints of any size, where `sqrt()` converts to a float first and overflows.

```python
import math

assert math.isqrt(10**40) == 10**20  # O(w²)

try:
    math.sqrt(10**400)
except OverflowError:
    pass
else:
    raise AssertionError('sqrt took an int beyond the float range')
assert math.isqrt(10**400) == 10**200
```

## Common Patterns

### Log-Space Combinatorics

When only the magnitude of a factorial or a binomial coefficient matters - a probability, a
likelihood - `lgamma()` gives its natural log in O(1), where building the exact int costs O(d²).

```python
import math

# log(comb(1000, 500)) without the 995-bit int
log_comb = math.lgamma(1001) - 2 * math.lgamma(501)  # O(1)
assert math.isclose(log_comb, math.log(math.comb(1000, 500)))

# log(n!) for an n whose factorial would have millions of digits
assert math.lgamma(10**6 + 1) > 1.2e7  # O(1)
```

## Performance Best Practices

✅ **Do**:

- Use `fsum()` when the precision `sum()` loses matters; it holds a constant however long the input
- Use `sumprod()` (3.12+) for a dot product, rather than building a list of products first
- Use `isqrt()`, not `int(sqrt(n))`, for an exact root of a large int
- Work in log space with `lgamma()` when only the magnitude of a factorial or binomial matters

❌ **Avoid**:

- `math.pow()` where the result must be an exact int - it is a float, and overflows
- Calling `perm(n, k)` for a k near n expecting the `comb()` mirror - its cost follows k
- `hypot(*values)` or `dist()` over a very long sequence when memory is tight - both hold it

## Version Notes

- **Python 3.9+**: `math.lcm()` added, and `math.gcd()` takes any number of arguments
- **Python 3.11+**: `math.cbrt()` and `math.exp2()` added
- **Python 3.12+**: `math.sumprod()` added; the builtin `sum()` compensates when adding floats,
  which narrows its accuracy gap to `fsum()` without closing it
- **Python 3.13+**: `math.fma()` added

## Related Modules

- **[cmath](cmath.md)** - The same functions over complex numbers
- **[decimal](decimal.md)** - Exact decimal arithmetic where binary floats round
- **[fractions](fractions.md)** - Exact rational arithmetic
- **[statistics](statistics.md)** - Means and spreads over whole datasets
