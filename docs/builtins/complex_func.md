# complex() Function Complexity

The `complex()` function creates a complex number from a string, from one number, or from
a real and an imaginary part. A complex number holds two C doubles, so every result is
the same size whatever the input.

`n` is the number of characters in a string argument.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| `complex()` | O(1) | O(1) | `0j` |
| From two numbers | O(1) | O(1) | `complex(real, imag)` with ints or floats |
| From complex | O(1) | O(1) | An exact `complex` is returned as the same object |
| From int/float | O(1) | O(1) | An int too large for a float raises `OverflowError` |
| From string | O(n) | O(n) | No copy for an ASCII string without underscores |
| Object with `__complex__`, `__float__` or `__index__` | method + O(1) | method + O(1) | `__complex__` is tried first |

## Basic Usage

### From Real and Imaginary Parts

```python
# O(1)
assert complex(3, 4) == 3 + 4j
assert complex(1.5, -2.5) == 1.5 - 2.5j
assert complex(0, 1) == 1j          # purely imaginary
assert complex(real=3, imag=4) == 3 + 4j
assert complex() == 0j
```

### From Single Number

```python
# O(1)
assert complex(3) == 3 + 0j
assert complex(3.14) == 3.14 + 0j
assert complex(0) == 0j

# An int must fit in a float
try:
    complex(10**400)
except OverflowError as e:
    assert "too large to convert to float" in str(e)
else:
    raise AssertionError("expected OverflowError")
```

### From Complex Number

```python
# O(1) - an exact complex comes back unchanged
original = complex(3, 4)
c = complex(original)
assert c is original
```

### From String

```python
# O(n) - n = string length
assert complex("3+4j") == 3 + 4j
assert complex("-1-2j") == -1 - 2j
assert complex("5j") == 5j
assert complex("10") == 10 + 0j

# Surrounding whitespace and parentheses are allowed, as are underscores in digits
assert complex(" (3+4j) ") == 3 + 4j
assert complex("1_000+2j") == 1000 + 2j
```

## Complexity Details

### String Parsing

Parsing is linear in the string length. An ASCII string is parsed in place; a string with
non-ASCII digits or whitespace, or with underscores, is first copied, so it takes O(n)
extra space.

```python
# O(n) - linear in string length
short = complex("3+4j")
long = complex("1" * 1000 + "+" + "2" * 1000 + "j")
assert short == 3 + 4j
assert long.real == float("1" * 1000)

# O(n) space - non-ASCII digits are converted to ASCII first
assert complex("٣+4j") == 3 + 4j  # ARABIC-INDIC DIGIT THREE
```

### Mathematical Operations

```python
# O(1) - two doubles in, two doubles out
c1 = complex(3, 4)
c2 = complex(1, 2)

assert c1 + c2 == 4 + 6j
assert c1 * c2 == -5 + 10j
assert c1 / c2 == (2.2 - 0.4j)
assert c1**2 == -7 + 24j
assert abs(c1) == 5.0
```

## Performance Patterns

### Literal vs complex()

A literal such as `3 + 4j` is folded into a constant when the code is compiled;
`complex(3, 4)` is a call made every time it runs. Use `complex()` for values
computed at run time, such as parsing user input.

```python
c = 3 + 4j              # constant
d = complex(3, 4)       # O(1) call
e = complex("3+4j")     # O(n) parse
assert c == d == e
```

### vs Tuple Representation

```python
# Both O(1) to build and read
c = complex(3, 4)
assert (c.real, c.imag) == (3.0, 4.0)

coords = (3, 4)
assert coords[0] == 3 and coords[1] == 4

# Complex numbers have arithmetic; tuples need it written out
c1, c2 = complex(3, 4), complex(1, 2)
assert c1 + c2 == 4 + 6j

coords1, coords2 = (3, 4), (1, 2)
assert (coords1[0] + coords2[0], coords1[1] + coords2[1]) == (4, 6)
```

## Edge Cases

### Conjugate

```python
# O(1) - flip sign of imaginary part
c = complex(3, 4)
assert c.conjugate() == 3 - 4j
assert (c * c.conjugate()).real == 25.0
```

### From String Errors

```python
# O(n) - the whole string is checked
for text in ["3 + 4j", "3+4j+5j"]:
    try:
        complex(text)  # spaces inside, or a third term
    except ValueError as e:
        assert "malformed string" in str(e)
    else:
        raise AssertionError(f"expected ValueError for {text!r}")

# A string cannot be combined with an imaginary part
try:
    complex("1", 2)
except TypeError:
    pass
else:
    raise AssertionError("expected TypeError")
```

## Mathematical Functions

```python
# O(1) - each cmath function works on two doubles
import cmath
import math

c = complex(3, 4)

assert cmath.sqrt(-1) == 1j
assert cmath.isclose(cmath.exp(cmath.log(c)), c)
assert cmath.isclose(cmath.sin(c) ** 2 + cmath.cos(c) ** 2, 1)
assert cmath.phase(c) == math.atan2(4, 3)

# The math module does not accept complex numbers
try:
    math.sqrt(c)
except TypeError:
    pass
else:
    raise AssertionError("expected TypeError")
```

## Methods

| Method | Time | Space | Notes |
|--------|------|-------|-------|
| `conjugate()` | O(1) | O(1) | Return complex conjugate (flip sign of imaginary) |
| `from_number(x)` | O(1) | O(1) | Class method; convert a number, not a string, to complex (Python 3.14+); plus `__complex__`, `__float__` or `__index__` for other types |

## Attributes

| Attribute | Time | Notes |
|-----------|------|-------|
| `real` | O(1) | Real part as float |
| `imag` | O(1) | Imaginary part as float |

## Attributes and Methods Examples

```python
import sys

# O(1) - access properties
c = complex(3, 4)
assert c.real == 3.0
assert c.imag == 4.0
assert c.conjugate() == 3 - 4j

if sys.version_info >= (3, 14):
    assert complex.from_number(3.14) == 3.14 + 0j
    try:
        complex.from_number("3+4j")
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")
```

## Best Practices

✅ **Do**:

- Write constants as literals, `3 + 4j`: they are built once, at compile time
- Use `complex()` to parse strings, O(n) in their length
- Use `cmath` for complex math functions

❌ **Avoid**:

- Passing complex numbers as the `real` or `imag` argument; it is deprecated from Python 3.14
- Calling `math` functions on complex numbers: they raise `TypeError`

## Related Functions

- **[abs()](abs.md)** - Magnitude of complex number
- **[float()](float_func.md)** - Real-number conversion
- **[cmath](../stdlib/cmath.md)** - Complex math functions

## Version Notes

- **Python 3.14+**: `complex.from_number()` added
- **Python 3.14+**: A complex number as the `real` or `imag` argument emits `DeprecationWarning`, and a string passed as `real=` raises `TypeError`
- **All Python 3**: Both parts are C doubles

## Further Reading

- [CPython Internals: complex](https://zpoint.github.io/CPython-Internals/BasicObject/complex/complex.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's complex implementation
