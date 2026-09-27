# fractions Module Complexity

The `fractions` module provides `Fraction`, an exact rational number kept as a pair of Python
integers in lowest terms with a positive denominator. It is pure Python on top of `int`, so every
operation costs what the integer arithmetic under it costs, and that grows with the size of the
numerator and denominator rather than staying fixed as `float` arithmetic does.

`b` is the bit length of the larger of the numerators and denominators involved; decimal digits
are about `0.3·b`. `M(b)` is the cost of multiplying two `b`-bit integers, O(b^1.58) in CPython;
`math.gcd()` and long division are O(b²). While the parts fit in a machine word every term in `b`
is O(1); the bounds matter because exact arithmetic makes the parts grow. `L` is a
`max_denominator`, `k` the magnitude of an integer exponent, `s` the length of a string and `p`
the magnitude of `round()`'s digits argument, or a format's precision plus its width.

## Complexity Reference

### Construction

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Fraction(numerator, denominator)` | O(b²) | O(b) | One `gcd` reduces the pair; a zero denominator raises `ZeroDivisionError` |
| `Fraction(n)`, `Fraction(other_fraction)` | O(1) | O(1) | An `int` or `Rational` is taken as already reduced; no `gcd` |
| `Fraction(x)`, `Fraction.from_float(x)` for a float `x` | O(1) | O(1) | Exact binary value from `x.as_integer_ratio()`; its parts never exceed 1,075 bits |
| `Fraction(d)`, `Fraction.from_decimal(d)` for a `Decimal` `d` | O(b²) | O(b) | `b` grows with the Decimal's digits and exponent; `as_integer_ratio()` reduces with a `gcd` |
| `Fraction(string)` | O(s + b²) | O(s + b) | `'3/4'`, `'-1.25'` or `'1e-3'`; a digit run longer than `sys.get_int_max_str_digits()` (4300 by default) raises `ValueError`, an exponent's value is not limited |
| `Fraction.from_number(x)` | O(1) | O(1) | Python 3.14+; an `int`, `Rational` or float, with no `gcd`. A `Decimal` costs its `as_integer_ratio()`, O(b²) time and O(b) space |

### Arithmetic

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `a + b`, `a - b`, `a * b`, `a / b` | O(b²) | O(b) | One or two `gcd` calls keep the result reduced; its parts can have twice the operands' bits. A float operand makes the result a float |
| `a // b`, `a % b`, `divmod(a, b)` | O(b²) | O(b) | `//` returns an `int` without a `gcd`; `%` reduces its `Fraction` result |
| `a ** k` for an integer `k` | O(M(k·b)) | O(k·b) | Raises both parts to the power; no `gcd`, since powers of coprime parts stay coprime. A non-integer exponent returns a float, or a complex for a negative base |
| `-a`, `abs(a)` | O(b) | O(b) | No `gcd`; the parts are already coprime |
| `+a` | O(1) | O(1) | Reuses both stored integers |

### Comparison and hashing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `a == b` | O(b) | O(1) | Compares numerators and denominators; no multiplication. A float is converted exactly first |
| `a < b`, `a <= b`, `a > b`, `a >= b` | O(M(b)) | O(b) | Cross-multiplies `a.numerator * b.denominator` against `a.denominator * b.numerator`; no `gcd` between two fractions |
| `hash(a)` | O(b) | O(b) | Equal to the hash of an equal `int`, float or `Decimal` |
| `bool(a)` | O(1) | O(1) | Tests the numerator |

### Accessors and conversion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Fraction.numerator`, `Fraction.denominator` | O(1) | O(1) | Always in lowest terms, denominator positive |
| `Fraction.as_integer_ratio()` | O(1) | O(1) | A tuple of the two stored integers |
| `Fraction.is_integer()` | O(1) | O(1) | Python 3.12+; tests `denominator == 1` |
| `Fraction.limit_denominator(max_denominator=1000000)` | O(b·log L) | O(b) | For a value with a small integer part; the first step divides the integer part out. The closest fraction with denominator at most `L`, by continued fractions; a denominator that already fits is returned as is |
| `float(a)` | O(b) | O(b) | Correctly rounded |
| `int(a)`, `math.trunc(a)`, `math.floor(a)`, `math.ceil(a)`, `round(a)` | O(b²) | O(b) | One floor division; O(b) when the integer part is small. `round()` rounds half to even |
| `round(a, p)` | O((b + p)²) | O(b + p) | Returns a `Fraction` |
| `str(a)`, `repr(a)` | O(b²) | O(b) | Decimal conversion of both parts; a part longer than `sys.get_int_max_str_digits()` digits raises `ValueError` |
| `format(a, spec)` | O((b + p)²) | O(b + p) | Python 3.12+ for `e`, `f`, `g` and `%`; 3.13+ for fill, alignment, sign, width and thousands separators without a type. `e` and `g` convert both parts to decimal and hit the same digit limit |
| `copy.copy(a)`, `copy.deepcopy(a)` | O(1) | O(1) | A `Fraction` is immutable and returns itself |

## Construction and Reduction

Only the two-argument form and the parsed forms reduce. An `int`, another `Fraction` or a float
is already in lowest terms, so building from one runs no `gcd` at all.

```python
from decimal import Decimal
from fractions import Fraction

reduced = Fraction(6, 8)                # O(b²) - one gcd
assert (reduced.numerator, reduced.denominator) == (3, 4)
assert Fraction(3, -4) == Fraction(-3, 4)  # the sign moves to the numerator

assert Fraction(7) == 7                 # O(1) - no gcd
assert Fraction(reduced) == reduced     # O(1) - no gcd

assert Fraction("3/4") == reduced       # O(s + b²)
assert Fraction("-1.25") == Fraction(-5, 4)
assert Fraction("1e-3") == Fraction(1, 1000)

assert Fraction(Decimal("0.25")) == Fraction(1, 4)  # O(b²)

try:
    Fraction(1, 0)
except ZeroDivisionError as error:
    assert "Fraction(1, 0)" in str(error)
else:
    raise AssertionError("a zero denominator was accepted")
```

### Floats Are Exact, Not Decimal

A float converts to the binary value it actually holds, which is rarely the decimal literal it
was written as. `limit_denominator()` recovers the short fraction, and a string skips the float
entirely.

```python
from fractions import Fraction

exact = Fraction(0.1)                   # O(1)
assert exact == Fraction(3602879701896397, 36028797018963968)
assert exact != Fraction(1, 10)
assert Fraction.from_float(0.1) == exact

assert exact.limit_denominator(1000) == Fraction(1, 10)  # O(b·log L)
assert Fraction("0.1") == Fraction(1, 10)                # O(s + b²)
```

## Arithmetic

### Why the Numbers Grow

Every result is exact and reduced, so it carries whatever denominator exactness requires. Adding
fractions whose denominators are coprime multiplies them together, which makes each later step
work on bigger integers than the one before. Denominators that all divide one fixed denominator stay small.

```python
from fractions import Fraction

primes = [2, 3, 5, 7, 11, 13]

total = Fraction(0)
for prime in primes:
    total += Fraction(1, prime)         # O(b²), and b grows every step
assert total.denominator == 2 * 3 * 5 * 7 * 11 * 13

eighths = Fraction(0)
for _ in range(8):
    eighths += Fraction(1, 8)           # O(b²) with b bounded
assert eighths == 1 and eighths.denominator == 1
```

### Division, Remainders and Powers

```python
from fractions import Fraction

a = Fraction(7, 2)
b = Fraction(2)

assert a / b == Fraction(7, 4)          # O(b²)
assert a // b == 1 and type(a // b) is int  # O(b²) - no gcd
assert a % b == Fraction(3, 2)          # O(b²)
assert divmod(a, b) == (1, Fraction(3, 2))

assert Fraction(2, 3) ** 2 == Fraction(4, 9)    # O(M(k·b)) - no gcd
assert Fraction(2, 3) ** -2 == Fraction(9, 4)   # the parts swap
assert isinstance(Fraction(1, 4) ** Fraction(1, 2), float)  # not an integer exponent
```

### Mixing With float

An `int` joins the exact arithmetic; a float does not. With a float operand the `Fraction` is
converted to float and the result is an ordinary rounded float.

```python
from fractions import Fraction

third = Fraction(1, 3)

assert third + 1 == Fraction(4, 3)      # exact
mixed = third + 0.5                     # O(b) - converts third to float
assert type(mixed) is float
assert mixed == 1 / 3 + 0.5
```

## Comparing and Hashing

Equality compares the stored parts, which are unique because every `Fraction` is reduced.
Ordering has to cross-multiply, so it costs a multiplication of the parts; between two fractions it runs no `gcd`.
Hashes agree with every other numeric type, so a `Fraction` finds an equal `int` or float in a
dict or set.

```python
from fractions import Fraction

half = Fraction(1, 2)

assert half == Fraction(2, 4)           # O(b) - the parts are compared
assert half == 0.5                      # the float is converted exactly
assert half > Fraction(1, 3)            # O(M(b)) - 1*3 against 2*1
assert Fraction(1, 3) < 0.34

prices = {0.5: "half", 2: "two"}
assert prices[half] == "half"           # O(b) hash, equal to hash(0.5)
assert prices[Fraction(4, 2)] == "two"
```

## Approximating With limit_denominator

`limit_denominator(L)` walks the continued fraction of the value until the next convergent's
denominator would pass `L`. Those denominators grow at least as fast as Fibonacci numbers, so
the walk takes at most O(log L) steps, each a division on the remaining parts. The result is the
closest fraction whose denominator is at most `L`, not merely a nearby one.

```python
from fractions import Fraction

pi = Fraction("3.141592653589793")

assert pi.limit_denominator(10) == Fraction(22, 7)      # O(b·log L)
assert pi.limit_denominator(100) == Fraction(311, 99)
assert pi.limit_denominator(1000) == Fraction(355, 113)

# Already within the limit: returned unchanged, O(1)
assert Fraction(22, 7).limit_denominator(10) == Fraction(22, 7)

assert Fraction(1.4142135623).limit_denominator(1000) == Fraction(1393, 985)
```

## Converting and Formatting

`float()` and `int()` are divisions, and `str()` is a decimal conversion of each part. Decimal
conversion of an integer longer than `sys.get_int_max_str_digits()` digits (4300 by default)
raises `ValueError`, so a fraction that grew large can be computed with but not printed until the
limit is raised or the value is approximated.

```python
import math
import sys
from fractions import Fraction

f = Fraction(22, 7)

assert float(f) == 22 / 7               # O(b)
assert int(f) == 3 and int(-f) == -3    # O(b²), truncates toward zero
assert math.floor(-f) == -4 and math.ceil(f) == 4
assert round(Fraction(5, 2)) == 2       # half to even
assert round(f, 3) == Fraction(3143, 1000)  # O((b + p)²)
assert str(f) == "22/7" and repr(f) == "Fraction(22, 7)"  # O(b²)
assert f.as_integer_ratio() == (22, 7)  # O(1)

if sys.version_info >= (3, 12):
    assert format(f, ".3f") == "3.143"  # O((b + p)²)

sys.set_int_max_str_digits(4300)       # the default
huge = Fraction(10**5000, 3)
try:
    str(huge)
except ValueError as error:
    assert "limit" in str(error)
else:
    raise AssertionError("a 5,001-digit numerator was converted")
assert huge.limit_denominator(1).numerator.bit_length() > 16_000  # still usable
```

## Common Patterns

### Exact Accumulation

A float total drifts; a `Fraction` total built from exact inputs does not. Build the inputs from
strings or integer pairs, since a float input already carries its rounding error.

```python
from fractions import Fraction

amounts = ["0.10", "0.20", "0.30"]

float_total = 0.0
for amount in amounts:
    float_total += float(amount)
assert float_total != 0.6               # 0.6000000000000001

exact_total = Fraction(0)
for amount in amounts:
    exact_total += Fraction(amount)     # O(b²), b small: every denominator divides 100
assert exact_total == Fraction(3, 5)
assert float(exact_total) == 0.6        # O(b), rounded once at the end
```

### Keeping Denominators Bounded

When the value only needs a bounded precision, approximate inside the loop so the denominator stays
bounded instead of growing with every step. The numerator then stays bounded as long as the value
does.

```python
from fractions import Fraction

x = Fraction(1, 3)
for _ in range(50):
    x = x * x + Fraction(1, 7)          # exact: b roughly doubles each step
    x = x.limit_denominator(10**12)     # O(b·log L) - caps it again
assert x.denominator <= 10**12
```

## Performance Best Practices

✅ **Do**:

- Build from `int` pairs or strings when the decimal value matters; a float carries its binary rounding in
- Use `limit_denominator()` to cap the denominator when a long computation only needs bounded precision
- Compare with `==` where it answers the question; it compares parts, while ordering multiplies them
- Convert to float once at the end rather than mixing floats in, which silently leaves exact arithmetic

❌ **Avoid**:

- Summing many fractions with unrelated denominators in a hot loop - `b` grows with every step, and so does each step's cost
- `Fraction` where rounding is acceptable - even small-part arithmetic is pure Python calling `gcd`, where a float operation is a single C call
- Printing a fraction whose parts pass `sys.get_int_max_str_digits()` digits - it raises instead

## Version Notes

- **Python 3.11+**: Strings may use underscores between digits, as in `Fraction('1_000')`
- **Python 3.12+**: Added `is_integer()`, and `format()` accepts the `e`, `f`, `g` and `%` presentation types; strings may put spaces around `/`
- **Python 3.13+**: `format()` accepts fill, alignment, sign, width and thousands separators without a presentation type
- **Python 3.14+**: Added `Fraction.from_number()`, and the constructor accepts any object with an `as_integer_ratio()` method

## Related Modules

- **[decimal](decimal.md)** - fixed-precision decimal arithmetic, whose cost does not grow with every operation
- **[math](math.md)** - `gcd()`, the cost behind every reduction here
- **[numbers](numbers.md)** - the `Rational` ABC that `Fraction` implements
- **[statistics](statistics.md)** - `mean()` and `median()` of `Fraction` data stay exact
