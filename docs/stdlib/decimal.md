# decimal Module Complexity

The `decimal` module implements the General Decimal Arithmetic specification: base-10 floating
point with a precision you choose, where `Decimal('0.1')` is exactly one tenth and every rounding
is defined rather than inherited from the hardware. CPython's implementation is libmpdec, in C. A
`Decimal` holds a coefficient of decimal digits and a bounded exponent, so it is the digit count
and not the magnitude that costs: `Decimal('1E+999999')` is a one-digit coefficient and an
exponent.

The context precision decides how many digits an operation keeps, and raising it is not free.
Addition stays linear in the digits it reads, multiplication is quadratic until coefficients run
to thousands of digits, and `exp()`, `ln()` and `log10()` grow faster still. The constructor is
the exception: it does not round to the precision, and keeps every digit it is given.

`p` is the context precision, `getcontext().prec` — the digits an arithmetic result keeps. `n` and
`m` are the digits in the coefficients of the operands, `len(x.as_tuple().digits)`, which `p` does
not bound because the constructor does not round. `r` is the digits a rounding operation keeps and
`L` the characters a conversion reads or writes. `g` is the gap between two operands' exponents.

An exponent is one integer, bounded by the module's own `MIN_ETINY` and `MAX_EMAX` rather than by
anything the context says: a literal may carry an exponent the context would overflow on, and the
first arithmetic operation is where `Emin` and `Emax` come in — as limits on a result's adjusted
exponent, which a subnormal result is allowed below. Reading or adjusting an exponent is O(1). It
becomes a size, written `e` for its magnitude, only where an operation has to write out the digits
it stands for: positional formatting, `int()`, `round(d)` and `as_integer_ratio()`. Addition is
the other place an exponent turns into work, and there the precision caps it.

## Complexity Reference

### Decimal construction and conversion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Decimal(value)` from a string | O(L) | O(L) | L = characters read, which leading zeros and an exponent make larger than n. Parsing is base 10 and linear, unlike `int(str)`, and the precision is not consulted |
| `Decimal(value)` from an int | O(n²) | O(n) | Binary to decimal base conversion; n = digits of the result |
| `Decimal(value)` from a float, `Decimal.from_float(f)` | O(1) | O(1) | The exact expansion of a double is at most 767 digits whatever the value. `Decimal(float)` raises where `FloatOperation` is trapped; `from_float()` is the explicit spelling and does not |
| `Decimal(value)` from a `Decimal` | O(1) | O(1) | Returns that same object; a `Decimal` is immutable, so there is nothing to copy |
| `Decimal(value)` from a `DecimalTuple` or a plain tuple | O(n) | O(n) | n = digits supplied |
| `Decimal.from_number(x)` | As the matching row above | | Python 3.14+; takes a float, an int or a `Decimal` and nothing else |
| `Decimal.as_tuple()` | O(n) | O(n) | Builds a fresh `DecimalTuple` holding one int per digit |
| `int(d)` | O((n + e)²) | O(n + e) | Decimal to binary conversion of the value written out in full, so a large positive exponent is paid for in digits |
| `float(d)` | O(n) | O(n) | Reads the coefficient through a textual conversion; the result is a double whatever it was |
| `Decimal.as_integer_ratio()` | O((n + e)²) | O(n + e) | That conversion for both halves: `Decimal('1E-1000')` has a denominator of 10¹⁰⁰⁰ |
| `str(d)`, `repr(d)`, `Decimal.to_eng_string()` | O(n) | O(n) | Every digit of the coefficient, and an exponent that stays an exponent |
| `format(d, spec)` | O(n + L) | O(L) | L = characters written. A precision in the spec rounds first, so L follows the spec rather than n — but a positional type writes the exponent out as zeros, and a field width pads to it |

### Decimal arithmetic

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `+a`, `-a`, `abs(a)` | O(n + p) | O(n + p) | Rounds to the context, which is what makes `+value` the idiom for applying it to a value the constructor left wide |
| `a + b`, `a - b` | O(n + m + min(g, p)) | O(n + m + min(g, p)) | Aligning the operands materialises the gap between their exponents, but only as far as the precision will keep it: past that the far operand only decides the rounding |
| `a * b` | O(n·m) | O(n + m) | Schoolbook for short coefficients; libmpdec switches to Karatsuba and then a number-theoretic transform, so coefficients of thousands of digits cost less than n·m |
| `a / b` | O(n + p·m) | O(n + p) | The quotient stops at p digits, so the divisor's length is multiplied by the precision rather than by the dividend's length |
| `a // b`, `a % b`, `divmod(a, b)`, `Decimal.remainder_near(other)` | O(n + p·m) | O(n + m + p) | The division above, keeping the integer quotient or the remainder; a quotient wider than p signals `InvalidOperation` |
| `a ** k` for integer k | O(log \|k\|) multiplications | O(p) | Binary exponentiation at the working precision |
| `a ** b` for non-integer b, `Context.power(x, y)` | Superquadratic in p | O(p) | Evaluated as `exp(b * ln(a))`, so it costs both |
| `pow(a, b, modulo)` | O(log b) multiplications | O(p) | Integer operands only; modular exponentiation, exact rather than rounded |
| `Decimal.sqrt()` | O(p²) | O(p) | Newton iteration at the working precision, correctly rounded |
| `Decimal.exp()`, `Decimal.ln()`, `Decimal.log10()` | Superquadratic in p | O(p) | Series evaluation at the working precision, outgrowing the quadratic `sqrt()` as p rises |
| `Decimal.fma(other, third)` | O(n·m + k + p) | O(n + m + k + p) | One multiplication and one addition — with that addition's alignment — rounded once at the end instead of twice; k = digits of `third` |
| `Decimal.compare(other)`, `Decimal.compare_signal(other)`, `a == b`, `a < b` | O(n + m) | O(1) | Compared from the most significant digit, so a difference there ends it — but whether a longer operand has a non-zero tail is what decides equality, and that tail is read. `compare()` returns a `Decimal`; `compare_signal()` signals on a NaN operand |
| `Decimal.compare_total(other)`, `Decimal.compare_total_mag(other)` | O(n + m) | O(1) | Total ordering, so NaNs and differing exponents order instead of signalling |
| `Decimal.max(other)`, `Decimal.min(other)`, `Decimal.max_mag(other)`, `Decimal.min_mag(other)` | O(n + m + p) | O(p) | Compares, then returns the winner rounded to the context |
| `Decimal.logb()`, `Decimal.adjusted()` | O(1) | O(1) | Read from the stored exponent |
| `Decimal.scaleb(other)` | O(n) | O(p) | Adjusts the exponent and copies the coefficient |

### Decimal rounding and digit manipulation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Decimal.quantize(exp)`, `round(d, k)` | O(r + n) | O(r) | r = digits the result keeps, and the result is built at that width whatever n is; the discarded digits are scanned for the `Inexact` flag, stopping at the first non-zero. A result wider than p signals `InvalidOperation` |
| `round(d)` | O((n + e)²) | O(n + e) | Not the same call: it returns an `int`, so it pays the conversion `int(d)` pays, and it rounds halves to even whatever the context's rounding mode says |
| `Decimal.to_integral_value()`, `Decimal.to_integral_exact()`, `Decimal.to_integral()` | O(r + n) | O(r) | Rounds to an integer without `quantize()`'s precision check, so a value with more digits than p comes back rather than signalling. `to_integral_exact()` signals `Inexact` and `Rounded`; the other two do not |
| `Decimal.normalize()` | O(n) | O(p) | Walks the coefficient to strip trailing zeros |
| `Decimal.shift(other)`, `Decimal.rotate(other)` | O(n + p) | O(p) | The coefficient is taken to p digits first, so the result is at most p digits wide |
| `Decimal.logical_and(other)`, `Decimal.logical_or(other)`, `Decimal.logical_xor(other)`, `Decimal.logical_invert()` | O(n + m + p) | O(p) | Digit-wise over p digits, after validating every digit of both operands: they must be non-negative with an exponent of 0 and digits of 0 or 1 |
| `Decimal.next_plus()`, `Decimal.next_minus()` | O(n + p) | O(p) | The adjacent representable value at the current precision |
| `Decimal.next_toward(other)` | O(n + m + p) | O(p) | The neighbour in the direction of `other`, so it compares the two first |
| `Decimal.copy_abs()`, `Decimal.copy_negate()`, `Decimal.copy_sign(other)` | O(n) | O(n) | Copies the coefficient unrounded; the context is not consulted and no signal is raised |
| `Decimal.canonical()`, `Decimal.conjugate()`, `Decimal.real` | O(1) | O(1) | Each returns the same object, not a copy |
| `Decimal.imag` | O(1) | O(1) | `Decimal(0)` |
| `Decimal.radix()`, `Decimal.number_class()`, `Decimal.same_quantum(other)` | O(1) | O(1) | `radix()` is always `Decimal(10)`; `same_quantum()` compares exponents |
| `Decimal.is_canonical()`, `Decimal.is_finite()`, `Decimal.is_infinite()`, `Decimal.is_nan()`, `Decimal.is_normal()`, `Decimal.is_qnan()`, `Decimal.is_signed()`, `Decimal.is_snan()`, `Decimal.is_subnormal()`, `Decimal.is_zero()` | O(1) | O(1) | Flag and exponent tests |

### Context

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `decimal.getcontext()` | O(1) | O(1) | The active context is per-thread, and per-coroutine where `HAVE_CONTEXTVAR` |
| `decimal.setcontext(c)` | O(1) | O(1) | The three pre-made contexts are copied; any other context is installed as it stands, so later changes to it are live |
| `decimal.localcontext(ctx=None, **kwargs)` | O(1) | O(1) | Copies a context when the manager is built — not when the `with` is entered — and restores the previous one on exit. Keyword attributes are Python 3.11+ |
| `decimal.Context(prec=None, rounding=None, Emin=None, Emax=None, capitals=None, clamp=None, flags=None, traps=None)` | O(1) | O(1) | Fixed number of fields; omitted ones come from `DefaultContext` |
| `Context.copy()` | O(1) | O(1) | A fixed number of fields |
| `Context.copy_decimal(num)` | O(1) | O(1) | For a `Decimal`, which is what the O(1) is about: it returns that same object, unrounded. An int pays `Decimal(int)`; a float or a string raises `TypeError` |
| `Context.prec`, `Context.rounding`, `Context.Emin`, `Context.Emax`, `Context.capitals`, `Context.clamp` | O(1) | O(1) | Assignment validates the value and raises `ValueError` outside the module's limits |
| `Context.flags`, `Context.traps` | O(1) | O(1) | The same mapping object on every access, keyed by signal class |
| `Context.clear_flags()`, `Context.clear_traps()` | O(1) | O(1) | A fixed set of signals |
| `Context.Etiny()`, `Context.Etop()` | O(1) | O(1) | Derived from `Emin`, `Emax` and `prec` |
| `Context.create_decimal(num)` | As `Decimal(num)`, then O(n + p) | As `Decimal(num)`, then O(n + p) | Builds the value exactly, as the constructor does — so a string argument carries its O(L) too — then rounds to p and signals, where `Decimal(num)` keeps everything. The rounding still reads the digits it drops |
| `Context.create_decimal_from_float(f)` | O(1) | O(p) | The 767-digit bound above, then rounding. It is the explicit spelling, so a trapped `FloatOperation` does not reach it |
| `Context.add(x, y)`, `Context.subtract(x, y)`, `Context.multiply(x, y)`, `Context.divide(x, y)`, `Context.divide_int(x, y)`, `Context.divmod(x, y)`, `Context.remainder(x, y)`, `Context.remainder_near(x, y)`, `Context.power(x, y, modulo=None)`, `Context.fma(x, y, z)`, `Context.sqrt(x)`, `Context.exp(x)`, `Context.ln(x)`, `Context.log10(x)` | As the operator or `Decimal` method above | | The context is supplied instead of looked up; the arithmetic is the same |
| `Context.abs(x)`, `Context.minus(x)`, `Context.plus(x)`, `Context.normalize(x)`, `Context.quantize(x, y)`, `Context.rotate(x, y)`, `Context.scaleb(x, y)`, `Context.shift(x, y)`, `Context.logical_and(x, y)`, `Context.logical_invert(x)`, `Context.logical_or(x, y)`, `Context.logical_xor(x, y)`, `Context.next_minus(x)`, `Context.next_plus(x)`, `Context.next_toward(x, y)`, `Context.to_integral(x)`, `Context.to_integral_exact(x)`, `Context.to_integral_value(x)`, `Context.copy_abs(x)`, `Context.copy_negate(x)`, `Context.copy_sign(x, y)` | As the `Decimal` method above | | `plus()` and `minus()` are unary `+` and `-`, which round where `copy_*` does not |
| `Context.compare(x, y)`, `Context.compare_signal(x, y)`, `Context.compare_total(x, y)`, `Context.compare_total_mag(x, y)` | O(n + m) | O(1) | The comparisons above |
| `Context.max(x, y)`, `Context.max_mag(x, y)`, `Context.min(x, y)`, `Context.min_mag(x, y)` | O(n + m + p) | O(p) | Compares, then rounds the winner |
| `Context.canonical(x)`, `Context.radix()`, `Context.logb(x)`, `Context.number_class(x)`, `Context.same_quantum(x, y)`, `Context.is_canonical(x)`, `Context.is_finite(x)`, `Context.is_infinite(x)`, `Context.is_nan(x)`, `Context.is_normal(x)`, `Context.is_qnan(x)`, `Context.is_signed(x)`, `Context.is_snan(x)`, `Context.is_subnormal(x)`, `Context.is_zero(x)` | O(1) | O(1) | Flag, exponent and identity tests |
| `Context.to_sci_string(x)`, `Context.to_eng_string(x)` | O(n) | O(n) | Renders every digit |
| `decimal.DefaultContext`, `decimal.BasicContext`, `decimal.ExtendedContext` | O(1) | O(1) | Module-level `Context` objects. `setcontext()` copies these three, so installing one does not hand out the original; `DefaultContext`'s attributes are what a bare `Context()` inherits |
| `decimal.IEEEContext(bits)` | O(1) | O(1) | Python 3.14+; `bits` must be a multiple of 32 below `decimal.IEEE_CONTEXT_MAX_BITS` |

### DecimalTuple

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `decimal.DecimalTuple(sign, digits, exponent)` | O(1) | O(1) | The named tuple `as_tuple()` returns; it stores the digit tuple it is handed |
| `DecimalTuple.sign`, `DecimalTuple.digits`, `DecimalTuple.exponent` | O(1) | O(1) | Field reads, as on any `namedtuple` |
| `DecimalTuple.count(value)`, `DecimalTuple.index(value)` | O(n) | O(1) | At most three comparisons, one of them against the whole digit tuple |

### Signals, exceptions and constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `decimal.DecimalException`, `decimal.Clamped`, `decimal.DivisionByZero`, `decimal.Inexact`, `decimal.InvalidOperation`, `decimal.Overflow`, `decimal.Rounded`, `decimal.Subnormal`, `decimal.Underflow`, `decimal.FloatOperation` | O(1) | O(1) | Signal classes used as keys in `Context.flags` and `Context.traps`; raised only where trapped |
| `decimal.ConversionSyntax`, `decimal.DivisionImpossible`, `decimal.DivisionUndefined`, `decimal.InvalidContext` | O(1) | O(1) | Conditions under `InvalidOperation`; they name a cause and are never raised on their own |
| `decimal.ROUND_CEILING`, `decimal.ROUND_DOWN`, `decimal.ROUND_FLOOR`, `decimal.ROUND_HALF_DOWN`, `decimal.ROUND_HALF_EVEN`, `decimal.ROUND_HALF_UP`, `decimal.ROUND_UP`, `decimal.ROUND_05UP` | O(1) | O(1) | String constants; they change which digit the rounding keeps, not the bound |
| `decimal.MAX_PREC`, `decimal.MAX_EMAX`, `decimal.MIN_EMIN`, `decimal.MIN_ETINY` | O(1) | O(1) | The ceilings a `Context` attribute is validated against |
| `decimal.HAVE_THREADS`, `decimal.HAVE_CONTEXTVAR`, `decimal.IEEE_CONTEXT_MAX_BITS` | O(1) | O(1) | Build flags; `IEEE_CONTEXT_MAX_BITS` is Python 3.14+ |

## Creating Decimals

### The Constructor Does Not Round

`Decimal(value)` is an exact conversion: it does not consult the context's precision or rounding
mode and does not signal `Inexact`, so a 50-digit literal becomes a 50-digit coefficient however
small the precision is. The context is not ignored altogether — a bad literal signals
`InvalidOperation` and a float argument signals `FloatOperation` where that is trapped — but
nothing about the value's width comes from it. Rounding arrives with the first arithmetic,
including unary `+`, which is the idiom for applying the context to a value you already hold.

```python
from decimal import Decimal, Inexact, localcontext

with localcontext() as ctx:
    ctx.prec = 5

    exact = Decimal('1' * 50)                    # O(L) - every digit kept
    assert len(exact.as_tuple().digits) == 50
    assert ctx.flags[Inexact] is False

    rounded = +exact                             # O(n + p) - now the context applies
    assert len(rounded.as_tuple().digits) == 5
    assert ctx.flags[Inexact] is True

    # create_decimal() reads all n digits, then rounds to p
    assert len(ctx.create_decimal('1' * 50).as_tuple().digits) == 5
```

### Strings, Integers and Floats

Four sources, four bounds. A decimal string is read character by character, so it is linear in
what you hand it rather than in the digits that survive. An integer has to be converted from
binary, which is quadratic — the same conversion that makes `str(int)` expensive. A float's exact
value is at most 767 digits whatever it is, so building a `Decimal` from one is bounded. A
`Decimal` is immutable, so building one from a `Decimal` hands the same object back.

```python
import sys
from decimal import Decimal

text = Decimal('1.' + '9' * 99)          # O(L) - linear in the characters read
assert len(text.as_tuple().digits) == 100

padded = Decimal('0' * 1000 + '1')       # O(L) with L = 1001, and n = 1
assert len(padded.as_tuple().digits) == 1

assert Decimal(text) is text             # O(1) - nothing to copy

whole = Decimal(10 ** 100)               # O(n²) - binary to decimal
assert whole == Decimal('1' + '0' * 100)

# A float carries its exact binary value across, not the literal you typed
binary = Decimal(0.1)                    # O(1) - bounded by the float format
assert binary != Decimal('0.1')
assert str(binary).startswith('0.1000000000000000055511151231257827')
assert Decimal.from_float(0.1) == binary

largest_denormal = sys.float_info.min - 5e-324
assert len(Decimal(largest_denormal).as_tuple().digits) == 767   # O(1), and the widest there is
assert len(Decimal(sys.float_info.max).as_tuple().digits) == 309
```

### Digits, Not Magnitude

The exponent is stored as one integer. A number with a huge exponent holds no more digits than its
coefficient, and it stays that way until something has to write those digits out — `int()`,
`as_integer_ratio()`, positional formatting, or an addition at a precision wide enough to align
across the gap.

```python
from decimal import Decimal, getcontext, localcontext

huge = Decimal('1E+999999')              # O(1) - one digit and an exponent
assert huge.as_tuple() == (0, (1,), 999999)
assert len(str(huge)) < 20               # O(n) on the coefficient, not the magnitude

# At the default precision the gap is wider than anything that would be kept
tiny = Decimal('1E-999999')
assert huge + tiny == huge               # O(n + m + min(g, p)), and p is the smaller
assert len((huge + tiny).as_tuple().digits) <= getcontext().prec

# Widen the precision and the same addition has to align across the gap
with localcontext() as ctx:
    ctx.prec = 3000
    assert len((Decimal(1) + Decimal('1E-2000')).as_tuple().digits) == 2001  # O(g)

# Writing the exponent out is where the magnitude finally costs
assert len(str(int(Decimal('1E+1000')))) == 1001   # O((n + e)²)
```

## Arithmetic

### Precision Governs the Cost

Every arithmetic operation rounds its result to `p` digits, and that is what makes precision the
main dial on this page. Addition is linear in the digits it reads. Multiplication computes the
whole product before rounding, so it is quadratic in the operands. Division stops at `p` quotient
digits, so raising the precision costs it directly.

```python
from decimal import Decimal, localcontext

a = Decimal('1.' + '9' * 49)
b = Decimal('2.' + '7' * 49)

with localcontext() as ctx:
    ctx.prec = 10
    assert len((a / b).as_tuple().digits) == 10   # O(n + p·m)

with localcontext() as ctx:
    ctx.prec = 60
    assert len((a / b).as_tuple().digits) == 60   # six times the quotient digits

# The product is exact before rounding: 50 digits times 50 digits needs 99
with localcontext() as ctx:
    ctx.prec = 200
    assert len((a * b).as_tuple().digits) == 99   # O(n·m)
```

### Integer and Non-Integer Powers

An integer exponent is binary exponentiation: `O(log |k|)` multiplications, so a large `k` costs
little more than a small one. A non-integer exponent goes through `exp(b * ln(a))` and pays for
both, so it grows with the precision the way those two do.

```python
from decimal import Decimal, localcontext

with localcontext() as ctx:
    ctx.prec = 28

    assert Decimal(2) ** 10 == Decimal(1024)          # O(log |k|) multiplications
    assert Decimal(2) ** 1000 > Decimal('1E+301')     # 100x the exponent, a few more steps

    root = Decimal(2) ** Decimal('0.5')               # exp(b * ln(a)) - superquadratic in p
    assert str(root).startswith('1.41421356')
    assert root == Decimal(2).sqrt()                  # O(p²) and correctly rounded

# pow() with a modulus is exact integer arithmetic, not a rounded power
assert pow(Decimal(2), Decimal(1000), Decimal(7)) == Decimal(2)
```

## Rounding and Formatting

### Rounding Is Priced by the Result

`quantize()` builds a result of `r` digits whatever the operand holds: rounding a 100,000-digit
value to two decimal places produces a three-digit coefficient and allocates nothing wider.
What it still has to do with the discarded digits is scan them, so that it can set `Inexact` —
and that scan stops at the first non-zero one. `round(d, k)` is the same operation; `round(d)`
with no second argument is not, because it returns an `int` and rounds halves to even whatever
the context says. `to_integral_value()` rounds to an integer as well, but without `quantize()`'s
check that the result fits in `p` digits.

```python
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_UP, localcontext

with localcontext() as ctx:
    ctx.prec = 200000
    wide = Decimal('1.' + '9' * 99999)

    cents = wide.quantize(Decimal('0.01'))          # O(r + n) - r = 3 digits kept
    assert cents == Decimal('2.00')
    assert len(cents.as_tuple().digits) == 3

    assert round(wide, 2) == cents                  # the same operation
    assert wide.to_integral_value() == Decimal(2)   # O(r + n), rounding to an integer

# The rounding mode picks the digit, and costs the same either way
assert Decimal('2.675').quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) == Decimal('2.68')
assert Decimal('2.675').quantize(Decimal('0.01')) == Decimal('2.68')  # ROUND_HALF_EVEN

# to_integral_value() has no precision check, where quantize() does
with localcontext() as ctx:
    ctx.prec = 2
    assert Decimal('123').to_integral_value() == Decimal('123')
    try:
        Decimal('123').quantize(Decimal(1))
    except InvalidOperation:
        pass
    else:
        raise AssertionError('a 3-digit result was quantized at prec 2')

# round() with no second argument is an int, and ignores the context's mode
with localcontext() as ctx:
    ctx.rounding = ROUND_UP
    assert round(Decimal('2.5')) == 2                       # ties to even
    assert Decimal('2.5').quantize(Decimal(1)) == Decimal(3)  # ROUND_UP
```

### Rendering Every Digit, or Only the Ones You Ask For

`str()`, `repr()` and `to_eng_string()` render the whole coefficient and leave the exponent as an
exponent. A format spec that names a precision rounds first, so it writes what it keeps rather
than what it was given — but a positional type writes the exponent out as zeros, and a field width
pads to whatever it asks for, so the cost follows the output.

```python
from decimal import Decimal, localcontext

with localcontext() as ctx:
    ctx.prec = 200000
    wide = Decimal('1.' + '9' * 99999)

    assert len(str(wide)) == 100001                 # O(n) - every digit
    assert format(wide, '.2f') == '2.00'            # rounds first, then renders 3

d = Decimal('1.23456E+7')
assert str(d) == '1.23456E+7'                       # O(n) - scientific notation
assert d.to_eng_string() == '12.3456E+6'            # O(n) - exponent a multiple of 3
assert format(d, '.2f') == '12345600.00'            # O(n + L) - L is what the spec asks for
assert len(format(Decimal(1), '1000000.0f')) == 1000000   # O(L) with n = 1
```

## Contexts

### Local Contexts

`localcontext()` takes its copy when the manager object is built and restores the previous context
on exit, both O(1). Changing `prec` inside it changes the cost of everything in the block, not just
its accuracy.

```python
from decimal import Decimal, getcontext, localcontext

assert getcontext().prec == 28                # the default

with localcontext() as ctx:                   # O(1) - a copy
    ctx.prec = 10
    assert str(Decimal(1) / Decimal(3)) == '0.3333333333'

assert getcontext().prec == 28                # O(1) - restored
assert len(str(Decimal(1) / Decimal(3))) == 30

# The copy is taken when the manager is built, not when the `with` is entered
manager = localcontext()                      # O(1) - captures prec 28 here
getcontext().prec = 5
with manager as ctx:
    assert ctx.prec == 28
getcontext().prec = 28
```

### Flags and Traps

Every signal has a flag and a trap. The flag records that the condition happened and stays set
until `clear_flags()`; the trap decides whether it is raised instead. Both are the same mapping
object on every access, so reading them costs nothing.

```python
from decimal import Decimal, DivisionByZero, Inexact, InvalidOperation, localcontext

with localcontext() as ctx:
    ctx.prec = 5
    assert ctx.flags is ctx.flags                  # O(1) - not rebuilt per access

    _ = Decimal(1) / Decimal(3)
    assert ctx.flags[Inexact] is True              # recorded, not raised
    ctx.clear_flags()                              # O(1)
    assert ctx.flags[Inexact] is False

    ctx.traps[Inexact] = True
    try:
        _ = Decimal(1) / Decimal(3)
    except Inexact:
        pass
    else:
        raise AssertionError('a trapped signal was not raised')

# Division by zero and 0/0 are different conditions, trapped by default
try:
    Decimal(10) / Decimal(0)
except DivisionByZero:
    pass
else:
    raise AssertionError('10/0 did not signal DivisionByZero')

try:
    Decimal(0) / Decimal(0)
except InvalidOperation:
    pass
else:
    raise AssertionError('0/0 did not signal InvalidOperation')
```

### The Pre-Made Contexts

`DefaultContext`, `BasicContext` and `ExtendedContext` are module-level objects, and `setcontext()`
copies those three rather than installing them, so nothing you do to the active context reaches
them. Any other context is installed as it stands, and later changes to that object are live.

```python
from decimal import (
    BasicContext, Context, DefaultContext, ExtendedContext,
    InvalidOperation, getcontext, setcontext,
)

assert DefaultContext.prec == 28
assert BasicContext.prec == 9 and ExtendedContext.prec == 9
assert BasicContext.traps[InvalidOperation] is True
assert ExtendedContext.traps[InvalidOperation] is False

previous = getcontext()
setcontext(BasicContext)                      # O(1) - the pre-made three are copied
assert getcontext() is not BasicContext
assert getcontext().prec == 9

mine = Context(prec=11)
setcontext(mine)                              # O(1) - anything else is installed as it stands
assert getcontext() is mine
setcontext(previous)

fresh = Context(prec=12)                      # O(1) - unset fields come from DefaultContext
assert fresh.prec == 12 and fresh.rounding == DefaultContext.rounding
assert fresh.copy() is not fresh              # O(1)
```

## Special Values

An infinity carries no digits at all, so an operation that propagates one skips the digit
arithmetic entirely and is O(1) whatever the precision. That is about propagating an infinity you
already have: arithmetic that overflows to one has already done its work, and an operation that
turns one back into a finite value, such as `next_minus()`, still builds its p digits. A NaN is
O(1) the same way until you give it a diagnostic payload, which is a coefficient like any other
and is propagated like one.

```python
import math
from decimal import Decimal, InvalidOperation

infinity = Decimal('Infinity')
assert infinity.as_tuple().digits == (0,)
assert (infinity + 5) == infinity          # O(1) - no digits to add
assert Decimal(math.inf) == infinity       # O(1)

assert (Decimal('NaN') + 5).is_nan()       # O(1) - propagates
assert Decimal('NaN') != Decimal('NaN')    # a NaN equals nothing, itself included

# A signalling NaN raises instead of propagating
try:
    Decimal('sNaN') + 5
except InvalidOperation:
    pass
else:
    raise AssertionError('sNaN propagated quietly')

assert Decimal('Infinity').number_class() == '+Infinity'   # O(1)
assert Decimal('NaN').is_nan() and not Decimal('NaN').is_finite()

# A NaN payload is digits, and they travel
payload = Decimal('NaN123')
assert payload.as_tuple().digits == (1, 2, 3)              # O(n) to carry
```

## Common Patterns

### Money

Money is the case the module exists for: parse from strings, do the arithmetic at a precision
wide enough for the intermediates, and `quantize()` once at the end.

```python
from decimal import Decimal, ROUND_HALF_UP, localcontext

def invoice(items, tax_rate):
    """items is (unit_price, quantity) with both as strings."""
    with localcontext() as ctx:
        ctx.prec = 28
        cents = Decimal('0.01')
        subtotal = sum(
            (Decimal(price) * Decimal(quantity) for price, quantity in items),
            Decimal(0),
        )                                                    # O(n·m) per product
        tax = (subtotal * Decimal(tax_rate)).quantize(cents, rounding=ROUND_HALF_UP)
        return subtotal.quantize(cents, rounding=ROUND_HALF_UP), tax  # O(r + n) each

subtotal, tax = invoice([('19.99', '1'), ('5.50', '2'), ('100', '0.5')], '0.08')
assert subtotal == Decimal('80.99')
assert tax == Decimal('6.48')
assert subtotal + tax == Decimal('87.47')
```

### Decimal and float Do Not Mix in Arithmetic

Comparison across the two types works and is exact. Arithmetic does not: it raises rather than
silently converting, which is what stops a binary rounding error entering a decimal calculation.

```python
from decimal import Decimal

assert Decimal('10.00') == 10.0          # O(n + m) - exact comparison
assert Decimal(1) < 1.5

try:
    Decimal('19.99') * 3.0
except TypeError as error:
    assert 'unsupported operand' in str(error)
else:
    raise AssertionError('Decimal * float was accepted')

assert Decimal('19.99') * 3 == Decimal('59.97')       # int is fine
assert Decimal('19.99') * Decimal('3.0') == Decimal('59.970')
```

## Performance Best Practices

✅ **Do**:

- Build `Decimal` values from strings: the parse is linear where `Decimal(int)` is quadratic
- Set the precision to what the result needs — division, `sqrt()` and `exp()` all scale with it
- Round once at the end with `quantize()`, which is priced by the digits it keeps
- Hoist constants such as a tax rate out of the loop; each construction is a fresh parse
- Use `+value` to apply the context to a value the constructor left unrounded

❌ **Avoid**:

- `Decimal(0.1)` where `Decimal('0.1')` was meant — it is bounded but it is not one tenth
- `ln()`, `log10()` and non-integer `**` at a precision you do not need — they are
  superquadratic in it
- Feeding a large `int` to `Decimal()` in a loop — that conversion is the quadratic one
- `int()` and `as_integer_ratio()` on a value with a large exponent — both write it out in full
- Mutating `getcontext()` to change precision temporarily; `localcontext()` restores it for you

## Version Notes

- **Python 3.11+**: `localcontext()` takes context attributes as keyword arguments, so
  `localcontext(prec=42)` replaces a copy followed by an assignment
- **Python 3.14+**: added `Decimal.from_number()`, `decimal.IEEEContext()` and
  `decimal.IEEE_CONTEXT_MAX_BITS`
- **All Python 3**: `Decimal(value)` does not round to the context's precision; the first
  arithmetic operation, `+value` included, is what rounds

## Related Modules

- **[fractions](fractions.md)** - exact rational arithmetic, with no precision to set
- **[math](math.md)** - float mathematics, constant-time per operation but binary
- **[numbers](numbers.md)** - the abstract base classes `Decimal` registers with
