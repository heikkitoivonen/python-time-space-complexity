# numbers Module Complexity

The `numbers` module defines the numeric tower as abstract base classes: `Number`, then
`Complex`, `Real`, `Rational` and `Integral`, each a subclass of the one before. It does two
jobs. Its ABCs answer `isinstance()` and `issubclass()` for any numeric type, through inheritance
or `register()`, never by looking for methods. And they carry mixin methods: a `Real` subclass
gets `divmod()`, `complex()` and `.real` for free, each built from the abstract methods it
supplies.

Mixins are priced in calls to the abstract methods a subclass supplies, each counted as O(1).
For the runtime checks, `L` is the length of the checked class's MRO, and `S` and `R` are the
subclasses and the registered classes a check can reach from the ABC, counted transitively
through both. `register(cls)` is priced for a `cls` that is not itself an ABC.
`d` is the digits in a rational's numerator and denominator.

## Complexity Reference

### Runtime checks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `isinstance(x, numbers.Real)`, `issubclass(cls, numbers.Integral)` and the other ABCs, on a class already checked | O(1) | O(1) | Both outcomes are cached per ABC, keyed by class; a `register()` that adds a new relationship, on any ABC anywhere, stales every negative cache, so the next negative answer from each ABC is walked for again |
| First check of a class against an ABC | O(L·(1 + R + S)) | O(R + S) | No structural hook: the MRO, then every registered class, then every subclass recursively, each of them rescanning the MRO, stopping at a match |
| `Number.register(cls)`, and the same on each ABC | O(L·(1 + R + S)) | O(R + S) | Two `issubclass()` checks, then one weak-set entry; a new relationship bumps the token that stales every negative cache, and a class that already is a subclass is a no-op |

### Number

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `numbers.Number` | O(1) | O(1) | The root; no methods, abstract or mixin. It sets `__hash__ = None`, so a subclass is unhashable until it defines `__hash__`. `Decimal` is registered here and on no lower ABC |

### Complex

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Complex.real`, `Complex.imag`, `Complex.conjugate()`, `__complex__`, `__add__`, `__mul__`, `__truediv__`, `__pow__`, their reflected forms, `__neg__`, `__pos__`, `__abs__`, `__eq__` | O(1) | O(1) | Abstract: the subclass supplies them. `complex` is registered here |
| `bool(z)` (`Complex.__bool__()`) | O(1) | O(1) | One `self != 0`, which is one `__eq__` unless the subclass defines `__ne__` |
| `z - w` (`Complex.__sub__()`), `w - z` (`Complex.__rsub__()`) | O(1) | O(1) | One negation and one addition: `self + -other` and `-self + other` |

### Real

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `__float__`, `__trunc__`, `__floor__`, `__ceil__`, `__round__`, `__floordiv__`, `__mod__`, their reflected forms, `__lt__`, `__le__` | O(1) | O(1) | Abstract, on top of `Complex`'s arithmetic. `float` is registered here |
| `Real.real`, `Real.conjugate()` | O(1) | O(1) | One `+self` |
| `Real.imag` | O(1) | O(1) | The constant `0` |
| `complex(x)` (`Real.__complex__()`) | O(1) | O(1) | One `__float__` |
| `divmod(x, y)` (`Real.__divmod__()`, `Real.__rdivmod__()`) | O(1) | O(1) | One `//` and one `%`; override it where both come from one computation |

### Rational

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Rational.numerator`, `Rational.denominator` | O(1) | O(1) | Abstract properties, expected in lowest terms with a positive denominator |
| `float(q)` (`Rational.__float__()`) | O(d) | O(d) | One read of each term, then an integer true division of the whole numerator by the whole denominator; `Fraction` inherits it |

### Integral

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `__int__`, `__pow__(exponent, modulus=None)`, `__lshift__`, `__rshift__`, `__and__`, `__xor__`, `__or__`, their reflected forms, `__invert__` | O(1) | O(1) | Abstract, on top of `Real`'s. `int` is registered here, which covers `bool` |
| `operator.index(i)` (`Integral.__index__()`) | O(1) | O(1) | One `__int__` |
| `float(i)` (`Integral.__float__()`) | O(1) | O(1) | One `__int__`, then `float()` of the result |
| `Integral.numerator` | O(1) | O(1) | One `+self` |
| `Integral.denominator` | O(1) | O(1) | The constant `1` |

## Checking Against the Tower

None of the ABCs looks for methods. A class is numeric here because it inherits from one of
them or is registered with one: `int` on `Integral`, `float` on `Real`, `complex` on `Complex`,
and `Decimal` on `Number` alone, so a `Decimal` is not a `Real`. The first check of a class walks
the ABC's registry and subclasses, stopping at a match, and caches the answer; later checks of
the same class are O(1) cache lookups, whether the answer was yes or no, until a new
registration stales the negative answers.

```python
import numbers
from decimal import Decimal
from fractions import Fraction

assert isinstance(42, numbers.Integral)  # O(L·(1 + R + S)) the first time, then O(1)
assert isinstance(True, numbers.Integral)  # bool inherits int's registration
assert isinstance(3.14, numbers.Real) and not isinstance(3.14, numbers.Rational)
assert isinstance(2 + 3j, numbers.Complex) and not isinstance(2 + 3j, numbers.Real)
assert isinstance(Fraction(1, 3), numbers.Rational)  # a subclass, not a registration

# Decimal is registered with Number and nothing below it
assert isinstance(Decimal('1.5'), numbers.Number)
assert not isinstance(Decimal('1.5'), numbers.Real)

# A miss is cached too
assert not isinstance('42', numbers.Number)  # walks the tower once
assert not isinstance('43', numbers.Number)  # O(1) - same class, negative cache
```

### Dispatching on the Tower

Each ABC is a subclass of the one above it, so a cascade must test the narrowest first. Every
branch is a cached check, so the cascade is O(1) per call once each class has been seen.

```python
import numbers
from decimal import Decimal
from fractions import Fraction

def kind(value):
    if isinstance(value, numbers.Integral):   # O(1) once the class is cached
        return 'integral'
    if isinstance(value, numbers.Rational):
        return 'rational'
    if isinstance(value, numbers.Real):
        return 'real'
    if isinstance(value, numbers.Complex):
        return 'complex'
    if isinstance(value, numbers.Number):
        return 'number'
    return 'not a number'

assert kind(7) == 'integral'
assert kind(Fraction(3, 4)) == 'rational'
assert kind(2.5) == 'real'
assert kind(2 + 3j) == 'complex'
assert kind(Decimal('2.5')) == 'number'
assert kind('7') == 'not a number'
```

### Registering a Type

`register()` makes a class a virtual subclass: it passes the check but inherits no mixins. A
registration that adds a new relationship bumps the ABC cache token, which stales the negative
cache of every ABC in the process, so each later miss walks its tree again. Register once, at
import time.

```python
import numbers
from abc import get_cache_token

class Meters(float):
    pass

class Opaque:
    pass

assert isinstance(Meters(1.0), numbers.Real)  # a float subclass needs nothing

token = get_cache_token()
numbers.Real.register(Opaque)  # O(L·(1 + R + S)) - and every negative cache goes stale
assert get_cache_token() != token
assert isinstance(Opaque(), numbers.Real)
assert not hasattr(Opaque, 'conjugate')  # registered, so no mixins

token = get_cache_token()
numbers.Real.register(Meters)  # already a subclass: a no-op
assert get_cache_token() == token
```

## Writing a Numeric Type

Subclass the narrowest ABC that fits and implement its abstract methods; instantiating a subclass
that leaves one out raises `TypeError`. `Number` has none, so any subclass of it can be built,
but it inherits `__hash__ = None`.

```python
import numbers

class Scalar(numbers.Number):
    def __init__(self, value):
        self.value = value

    def __add__(self, other):
        if isinstance(other, numbers.Real):  # O(1) after the first check of each class
            return Scalar(self.value + other)
        return NotImplemented

total = Scalar(5) + 3
assert isinstance(total, numbers.Number) and total.value == 8

try:
    hash(total)
except TypeError as error:
    assert 'unhashable' in str(error)
else:
    raise AssertionError('a Number subclass without __hash__ was hashable')

class Partial(numbers.Real):
    def __float__(self):
        return 0.0

try:
    Partial()
except TypeError as error:
    assert 'abstract' in str(error)
else:
    raise AssertionError('a Real with abstract methods left was instantiated')
```

### The Rational Float Conversion

`Rational.__float__()` divides the whole numerator by the whole denominator, so it costs their
length rather than a constant. `Fraction` does not override it: `float()` of a fraction with
large terms is linear in its digits.

```python
import numbers
from fractions import Fraction

assert Fraction.__float__ is numbers.Rational.__float__

third = Fraction(1, 3)
assert float(third) == 1 / 3  # O(d)

huge = Fraction(10**400 + 1, 3 * 10**400)
assert float(huge) == 1 / 3  # O(d) - both terms are divided whole
```

## Common Patterns

### Validating Arguments

A check per value is O(1) once each class has been seen, so validating n values of a few types
is O(n).

```python
import numbers
from fractions import Fraction

def mean(values):
    for value in values:  # O(n)
        if not isinstance(value, numbers.Real):  # O(1) per value after its class's first check
            raise TypeError(f'expected a real number, got {type(value).__name__}')
    return sum(values) / len(values)

assert mean([1, 2, 3, 4, 5]) == 3
assert mean([Fraction(1, 2), Fraction(3, 2)]) == 1

try:
    mean([1, 2, 'three'])
except TypeError as error:
    assert 'str' in str(error)
else:
    raise AssertionError('a string passed as a real number')
```

## Performance Best Practices

✅ **Do**:

- Call `isinstance()` directly rather than caching its answer yourself; the ABC already caches both answers per class, so the first-check walk is paid once per class either way, until a new registration
- Register classes once, at import time; each new registration stales every ABC's negative cache
- Override `__divmod__` on a `Real` subclass that computes quotient and remainder together; the mixin makes one `//` and one `%` call

❌ **Avoid**:

- `register()` inside a loop or a hot path: each new relationship makes every following miss walk the registry and subclass tree again
- `float()` of a `Fraction` or other `Rational` with huge terms in a hot loop; the inherited conversion divides the whole numerator by the whole denominator

## Version Notes

- **All Python 3**: `Decimal` is registered with `Number` only, so `isinstance(d, numbers.Real)` is `False` for a `Decimal`
- **All Python 3**: the negative cache of every ABC is invalidated by any `register()` call that adds a new relationship, through the token `abc.get_cache_token()` exposes

## Related Modules

- **[fractions](fractions.md)** - `Fraction`, the standard library's `Rational` subclass
- **[decimal](decimal.md)** - `Decimal`, registered as a `Number` but not a `Real`
- **[abc](abc.md)** - the metaclass, its caches and `register()`
- **[collections.abc](collections.abc.md)** - the container ABCs, checked by the same machinery
