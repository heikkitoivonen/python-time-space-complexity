# math Module Complexity

The `math` module provides fast floating-point math functions and a few integer-specific helpers.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `math.pi`, `math.e`, `math.tau`, `math.inf`, `math.nan` | O(1) | O(1) | Module constants; no call is made |
| `math.sin/cos/tan(x)`, `math.asin/acos/atan(x)`, `math.atan2(y, x)` | O(1) | O(1) | One libm call on a fixed-width operand |
| `math.sinh/cosh/tanh(x)`, `math.asinh/acosh/atanh(x)` | O(1) | O(1) | One libm call |
| `math.exp(x)`, `math.exp2(x)`, `math.expm1(x)`, `math.pow(x, y)` | O(1) | O(1) | `exp2` is 3.11+; `math.pow` always returns a float and overflows where the builtin `pow` returns an exact int |
| `math.log(x[, base])`, `math.log2(x)`, `math.log10(x)`, `math.log1p(x)` | O(1) | O(1) | All but `log1p` take a separate path for an int too large for a float, costing O(n) in its digits |
| `math.sqrt(x)`, `math.cbrt(x)` | O(1) | O(1) | `cbrt` is 3.11+ |
| `math.erf/erfc(x)`, `math.gamma/lgamma(x)` | O(1) | O(1) | One libm call |
| `math.degrees/radians(x)`, `math.fabs(x)`, `math.copysign(x, y)` | O(1) | O(1) | |
| `math.fmod(x, y)`, `math.remainder(x, y)`, `math.modf(x)`, `math.frexp(x)`, `math.ldexp(x, i)` | O(1) | O(1) | |
| `math.nextafter(x, y)`, `math.ulp(x)`, `math.fma(x, y, z)` | O(1) | O(1) | `fma` is 3.13+ |
| `math.isfinite/isinf/isnan(x)`, `math.isclose(a, b)` | O(1) | O(1) | These convert an int argument too, so a value beyond the float range raises rather than answering |
| `math.floor(x)`, `math.ceil(x)`, `math.trunc(x)` | O(1) | O(1) | An int argument is returned unchanged, however many digits it has |
| `math.hypot(*coords)` | O(n) | O(n) | n = number of coordinates; they are buffered, not folded in one at a time |
| `math.dist(p, q)` | O(n) | O(n) | n = dimensions; buffered like `hypot` |
| `math.fsum(iterable)` | O(n) | O(1) | n = values; the partial sums it carries are bounded by the float exponent range, not by n |
| `math.sumprod(p, q)` | O(n) | O(1) | Python 3.12+; unlike `dist`, it holds nothing per element |
| `math.prod(iterable)` | O(n) | O(1) | n = values; with int values the product grows, making it O(d²) time and O(d) space in the result's digits |
| `math.isqrt(n)` | O(n²) | O(n) | n = digits of the argument |
| `math.gcd(*integers)` | O(n²) | O(n) | n = digits of the smaller operand |
| `math.lcm(*integers)` | O(n²) | O(n) | n = digits; the gcd dominates, and the result carries up to the operands' digits combined |
| `math.factorial(n)` | O(d²) | O(d) | d = digits of the result, itself Θ(n log n) bits |
| `math.comb(n, k)` | O(d²) | O(d) | d = digits of the result; driven by min(k, n - k), barely by n |
| `math.perm(n, k)` | O(d²) | O(d) | d = digits of the result; driven by k, with no comb symmetry to fall back on |

!!! warning "Floating-point precision"
    Most `math` functions operate on binary floating-point numbers. Results are fast but may be imprecise
    for some decimal fractions. Use `decimal` for exact decimal arithmetic.

## Common Operations

### Basic Transcendentals

```python
import math

x = 2.0

# O(1)
root = math.sqrt(x)
log2 = math.log(x, 2)
angle = math.sin(math.pi / 6)
```

### Integer Arguments to the Float Functions

Every function in the rows above takes a C double. An `int` argument is
converted first, which costs O(n) in its digits and raises `OverflowError` once
the value exceeds the float range - the predicates included, so
`math.isfinite()` raises on such a value rather than answering.

Two groups are exempt:

- `floor()`, `ceil()` and `trunc()` return an int argument unchanged, at O(1)
  whatever its size
- `log()`, `log2()` and `log10()` have a large-int path of their own, costing
  O(n) in the argument's digits

```python
import math

big = (1 << 2000) + 1

# A path of its own: O(n) in the digits of `big`
math.log(big)   # 1386.29...

# Returned unchanged, at O(1)
math.floor(big) is big  # True

# Converted, and no float can hold it
for name in ('sqrt', 'exp', 'isfinite'):
    try:
        getattr(math, name)(big)
    except OverflowError as error:
        print(name, '->', error)
```

### Which of the Sequence Functions Hold Their Input

Four functions walk a sequence of floats, and they divide on space rather than
on time. `hypot()` and `dist()` hold the coordinates: their peak grows with the
input. `fsum()` and `sumprod()` do not.

```python
import math

# O(n) time and O(n) space in the number of coordinates
r2 = math.hypot(3.0, 4.0)          # 5.0
r3 = math.hypot(1.0, 2.0, 2.0)     # 3.0
d = math.dist((0.0, 0.0), (3.0, 4.0))  # 5.0

# O(n) time, O(1) space - neither holds anything per element
total = math.fsum([0.1] * 10)      # 1.0
product = math.prod([2.0, 3.0, 7.0])  # 42.0
```

Where a dot product is what you want, `sumprod()` (3.12+) is the O(1)-space
member of the family; `dist()` is the one that buffers.

### Accurate Summation

`fsum()` returns the correctly rounded sum of its input. `sum()` does not, but
it is much closer than it once was: from Python 3.12 it carries a compensation
term when adding floats, which is enough for the textbook example.

```python
import math

values = [1e100, 1.0, -1e100]

# Loses the 1.0 entirely before 3.12; from 3.12 it does not
regular = sum(values)

# fsum has always been exact here
accurate = math.fsum(values)  # 1.0
```

One compensation term is not exactness, though. Three magnitudes at once still
separate them on every supported version:

```python
import math

values = [1e16, 1.0, 1e-16, -1e16, -1.0]

sum(values)        # -1.0 before 3.12, 0.0 from 3.12 - wrong either way
math.fsum(values)  # 1e-16, the correctly rounded answer
```

`fsum()` is O(1) in space however long the iterable is. It carries a set of
non-overlapping partial sums, and a float's exponent range caps how many of
those can exist at once, so the working set does not grow with the input.

### Integers: gcd, lcm, factorial, comb, perm

```python
import math

# gcd/lcm: O(n²) in the digits of the smaller operand
g = math.gcd(84, 30)   # 6
l = math.lcm(6, 10)    # 30

# Both take any number of arguments
g3 = math.gcd(12, 18, 30)  # 6
l3 = math.lcm(4, 6, 10)    # 60

# factorial, combinations, permutations: O(d²) in the digits of the result
f = math.factorial(10)     # 3628800
c = math.comb(10, 3)       # 120
p = math.perm(10, 3)       # 720

# isqrt: O(n²) in the digits of the argument, and exact where sqrt() is not
r = math.isqrt(10**40)     # 100000000000000000000
```

`prod()` sits in both camps. Over floats it is O(n) time and O(1) space, like
`fsum()`. Over ints the running product grows with every factor, so the cost
follows the digits of the result rather than the number of terms:

```python
import math

# O(n) over floats, holding nothing
math.prod([1.5] * 1000)

# Over ints the product itself is the cost: 2000 factors, a 3170-bit result
math.prod([3] * 2000)  # O(d²) in the digits of the result
```

### What Drives comb() and perm()

`n` is barely a cost variable for either: its only effect is the digit count of
the individual factors, which grows as log n. `k` is the one that matters, and
the two functions differ in what they can do about it.

`comb(n, k) == comb(n, n - k)`, and a `k` near `n` costs what the small `k` it
mirrors costs. `perm()` has no such identity, so the two diverge sharply as
`k` approaches `n`:

```python
import math

# comb: mirrored, so both of these are equally cheap
math.comb(1000, 5)     # 8250291250200
math.comb(1000, 995)   # the same value, and the same work

# perm: k factors, so a large k really does cost more
math.perm(1000, 5)     # 990034950024000
```

### Robust Comparisons

```python
import math

# Avoid direct equality for floats
math.isclose(0.1 + 0.2, 0.3)  # True
```

## Performance Notes

- Floating-point operations are constant time and CPU-bound.
- The integer functions (`factorial`, `comb`, `perm`, `gcd`, `lcm`) scale with
  the digit counts in the table, not with the numeric value of their arguments.
  The quadratic bounds are grade-school ones; CPython's Karatsuba multiplication
  beats them for large operands.

## Version Notes

- **Python 3.9+**: `math.lcm()` added, and `math.gcd()` became variadic
- **Python 3.11+**: `math.cbrt()` and `math.exp2()` added
- **Python 3.12+**: `math.sumprod()` added; the builtin `sum()` compensates when
  adding floats, which narrows the accuracy gap to `fsum()` without closing it
- **Python 3.13+**: `math.fma()` added

## Related Modules

- [cmath Module](cmath.md) - Complex-number math
- [decimal Module](decimal.md) - Decimal arithmetic
- [fractions Module](fractions.md) - Rational arithmetic
- [statistics Module](statistics.md) - Descriptive statistics
- [random Module](random.md) - Random numbers
