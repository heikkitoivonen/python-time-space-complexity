# NotImplemented Constant Complexity

`NotImplemented` is a singleton that a binary or comparison special method returns to decline an
operand it does not handle. The interpreter then gives the other operand its turn, and only if
every method declines does it raise `TypeError` or, for `==` and `!=`, fall back to identity. It is
not the `NotImplementedError` exception. Besides operator dispatch, only a few hooks, such as
`__length_hint__` and an ABC's `__subclasshook__`, read it as declining.

Reading and testing the constant is O(1). The cost of an operator that meets it is counted in
special-method calls: at most two for a binary operator or a comparison, and three for an in-place
operator. Each method costs what its own body does; the bounds below are the work dispatch adds.

## Complexity Reference

### NotImplemented

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `NotImplemented` | O(1) | O(1) | A builtin name bound to one object |
| `result is NotImplemented` | O(1) | O(1) | The way to test for it |
| `type(NotImplemented)()` | O(1) | O(1) | Returns the same singleton; the type is `types.NotImplementedType` |
| `bool(NotImplemented)` | O(1) | O(1) | Python 3.14+: raises `TypeError`; 3.11-3.13: `True` with a `DeprecationWarning` |

### Operator Dispatch

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `a + b` and the other binary operators | O(1) | O(1) | Plus up to two calls: `a.__add__(b)`, then `b.__radd__(a)` if it declined and `type(b)` differs from `type(a)`; `TypeError` if both decline |
| `a + b` where `type(b)` subclasses `type(a)` and overrides `__radd__` | O(1) | O(1) | Plus up to two calls, `b.__radd__(a)` first |
| `a += b` and the other in-place operators | O(1) | O(1) | Plus up to three calls: `__iadd__`, then `__add__` and `__radd__` as for `a + b` |
| `a == b` | O(1) | O(1) | Plus up to two calls: `a.__eq__(b)`, then `b.__eq__(a)`, even for one type, and `b`'s first when `type(b)` is a strict subclass of `type(a)`; if both decline, the answer is `a is b` |
| `a != b` | O(1) | O(1) | The same through `__ne__`, whose default inverts `__eq__`'s answer and passes `NotImplemented` on; if both decline, the answer is `a is not b` |
| `a < b`, `a <= b`, `a > b`, `a >= b` | O(1) | O(1) | Plus up to two calls: `a.__lt__(b)`, then the reflected `b.__gt__(a)`, which goes first when `type(b)` is a strict subclass of `type(a)`; `TypeError` if both decline |

## Returning NotImplemented from Operators

### Binary Operators and Their Reflection

Returning `NotImplemented` hands the operation to the right operand's reflected method. Two
operands of the same type get no second chance, so declining one of them raises `TypeError`.

```python
calls = []

class Vector:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __add__(self, other):
        calls.append("Vector.__add__")
        if not isinstance(other, Vector):
            return NotImplemented  # O(1) - let the other operand try
        return Vector(self.x + other.x, self.y + other.y)

class Offset:
    def __radd__(self, other):
        calls.append("Offset.__radd__")
        return Vector(other.x + 1, other.y + 1)

v = Vector(1, 2) + Vector(3, 4)
assert (v.x, v.y) == (4, 6)

calls.clear()
moved = Vector(1, 2) + Offset()  # Two calls: __add__ declines, __radd__ answers
assert (moved.x, moved.y) == (2, 3)
assert calls == ["Vector.__add__", "Offset.__radd__"]

try:
    Vector(1, 2) + "text"  # Both decline
except TypeError as error:
    assert "unsupported operand type(s) for +" in str(error)
else:
    raise AssertionError("expected TypeError")
```

### Subclasses Go First

When the right operand's type is a subclass of the left's and overrides the reflected method, that
method is called first, so a subclass can take over an operation its base class would otherwise
answer.

```python
calls = []

class Money:
    def __init__(self, amount):
        self.amount = amount

    def __add__(self, other):
        calls.append("Money.__add__")
        return Money(self.amount + other.amount)

    def __radd__(self, other):
        return NotImplemented

class Euros(Money):
    def __radd__(self, other):
        calls.append("Euros.__radd__")
        return Euros(self.amount + other.amount)

total = Money(5) + Euros(10)
assert type(total) is Euros
assert calls == ["Euros.__radd__"]  # Money.__add__ was never called
```

### In-Place Operators Fall Back to Binary Ones

An `__iadd__` that returns `NotImplemented` falls back to `__add__` and then the other operand's
`__radd__`, so `a += b` makes up to three calls.

```python
calls = []

class Counter:
    def __init__(self, n):
        self.n = n

    def __iadd__(self, other):
        calls.append("__iadd__")
        return NotImplemented  # Decline to update in place

    def __add__(self, other):
        calls.append("__add__")
        if not isinstance(other, int):
            return NotImplemented
        return Counter(self.n + other)

c = Counter(1)
original = c
c += 2  # __iadd__ declines, __add__ builds a new object
assert c.n == 3 and c is not original
assert calls == ["__iadd__", "__add__"]
```

## Comparisons

### Equality Falls Back to Identity

When both `__eq__` methods decline, `==` compares identity rather than raising. The reflected
`__eq__` is tried even when both operands have the same type.

```python
calls = []

class Opaque:
    def __eq__(self, other):
        calls.append("__eq__")
        return NotImplemented

    __hash__ = object.__hash__

a, b = Opaque(), Opaque()
assert (a == b) is False  # a is b
assert (a == a) is True
assert (a != b) is True   # a is not b
calls.clear()
a == b
assert calls == ["__eq__", "__eq__"]  # a.__eq__(b), then b.__eq__(a)
```

### Ordering Raises TypeError

The ordering operators have no identity fallback. `a < b` tries `a.__lt__(b)` and the reflected
`b.__gt__(a)`, the reflected one first when `b`'s type is a subclass of `a`'s, and raises when both
decline.

```python
from functools import total_ordering

@total_ordering
class Version:
    def __init__(self, major, minor):
        self.key = (major, minor)

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self.key == other.key

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented  # O(1) - checked before any comparison work
        return self.key < other.key

assert Version(3, 11) < Version(3, 14)
assert Version(3, 14) >= Version(3, 11)  # Filled in by total_ordering
assert Version(3, 14) != "3.14"          # Equality falls back to identity

try:
    Version(3, 14) < "3.14"
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Checking for NotImplemented

### Test It with is

Use `is NotImplemented`. Its truth value is an error from Python 3.14 and deprecated before that,
so `if result:` cannot stand in for the check.

```python
import sys
import warnings

result = (1).__add__("text")  # Calling the method directly returns the marker
assert result is NotImplemented  # O(1)

if sys.version_info >= (3, 14):
    try:
        bool(NotImplemented)
    except TypeError as error:
        assert "boolean context" in str(error)
    else:
        raise AssertionError("expected TypeError")
else:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert bool(NotImplemented) is True
    assert caught[0].category is DeprecationWarning
```

### Other Special Methods

A few hooks besides the operators read `NotImplemented` as declining: `operator.length_hint()` falls
back to its default when `__length_hint__` returns it, and `issubclass()` runs its normal check when
an ABC's `__subclasshook__` returns it. Elsewhere it is an ordinary object. Returned from
`__getitem__` it is the item; returned from `__hash__` it raises `TypeError`, because a hash must be
an integer. To make instances unhashable, set `__hash__ = None`.

```python
import operator

class NoHint:
    def __length_hint__(self):
        return NotImplemented  # Decline to estimate

assert operator.length_hint(NoHint(), 10) == 10  # The default is used

class Lookup:
    def __getitem__(self, key):
        return NotImplemented

assert Lookup()["anything"] is NotImplemented  # Returned as the value

class BadHash:
    def __hash__(self):
        return NotImplemented

try:
    hash(BadHash())
except TypeError as error:
    assert "should return an integer" in str(error)
else:
    raise AssertionError("expected TypeError")

class Unhashable:
    __hash__ = None

try:
    {Unhashable()}
except TypeError as error:
    assert "unhashable type" in str(error)
else:
    raise AssertionError("expected TypeError")
```

### NotImplemented Is Not NotImplementedError

`NotImplementedError` is an exception for a method a subclass must still provide. Raising it from
an operator method stops dispatch, so the other operand never gets its turn.

```python
class Strict:
    def __add__(self, other):
        raise NotImplementedError("only Strict + Strict")

class Accepting:
    def __radd__(self, other):
        return "handled"

try:
    Strict() + Accepting()  # Accepting.__radd__ is never reached
except NotImplementedError:
    pass
else:
    raise AssertionError("expected NotImplementedError")

assert NotImplemented is not NotImplementedError
assert issubclass(NotImplementedError, RuntimeError)
```

## Performance Best Practices

✅ **Do**:

- Return `NotImplemented` from a binary or comparison method for an operand type it does not
  handle, before doing any work, so dispatch moves on after one cheap check
- Test a direct call's result with `is NotImplemented`
- Set `__hash__ = None` to make a class unhashable

❌ **Avoid**:

- Raising `TypeError` or `NotImplementedError` from an operator method for an unknown operand: the
  other operand's reflected method is never called
- Using `NotImplemented` in a boolean context: `TypeError` from Python 3.14
- Returning `NotImplemented` from `__getitem__`, `__hash__`, `__exit__` or another method whose
  caller does not document it; there it is not read as declining

## Version Notes

- **Python 3.14+**: `bool(NotImplemented)` raises `TypeError`; on 3.11-3.13 it returns `True` and
  emits a `DeprecationWarning`. An `__exit__` returning `NotImplemented` while an exception is
  propagating therefore raises on 3.14+ and suppresses the exception on 3.11-3.13.

## Related Constants

- **[NotImplementedError](exceptions.md)** - The exception for a method that is not written yet
- **[None](none.md)** - The other built-in singleton most often tested with `is`
- **[Ellipsis](ellipsis.md)** - Another built-in singleton constant
