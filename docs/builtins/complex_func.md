# complex() Function Complexity

The `complex()` function creates complex numbers from numeric values or strings.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| From two numbers | O(1) | O(1) | real + imaginary |
| From complex | O(1) | O(1) | Copy or identity |
| From string | O(n) | O(1) | n = string length |
| From int/float | O(1) | O(1) | Direct conversion for floats and small ints; O(n) for arbitrary precision ints |

## Basic Usage

### From Real and Imaginary Parts

```python
# O(1)
c = complex(3, 4)        # (3+4j)
c = complex(1.5, -2.5)   # (1.5-2.5j)
c = complex(0, 1)        # 1j (purely imaginary)
```

### From Single Number

```python
# O(1)
c = complex(3)      # (3+0j)
c = complex(3.14)   # (3.14+0j)
c = complex(0)      # 0j
```

### From Complex Number

```python
# O(1)
original = complex(3, 4)
c = complex(original)  # (3+4j) - returns the same object
```

### From String

```python
# O(n) - where n = string length
c = complex("3+4j")      # (3+4j)
c = complex("-1-2j")     # (-1-2j)
c = complex("5j")        # 5j
c = complex("10")        # (10+0j)
```

## Complexity Details

### Numeric Conversion

```python
# O(1) - just type conversion
int_val = 5
float_val = 3.14

c1 = complex(int_val)       # O(1) - (5+0j)
c2 = complex(float_val)     # O(1) - (3.14+0j)
c3 = complex(int_val, float_val)  # O(1) - (5+3.14j)
```

### String Parsing

```python
# O(n) - linear in string length
short = complex("3+4j")         # O(5)
long = complex("123+456j")      # O(10)

# Each character must be parsed
```

### Mathematical Operations

```python
# O(1) - all operations constant time
c1 = complex(3, 4)
c2 = complex(1, 2)

# Arithmetic - all O(1)
result = c1 + c2       # (4+6j)
result = c1 * c2       # (-5+10j)
result = c1 / c2       # (2.2-0.4j)
result = c1 ** 2       # (-7+24j)
```

## Common Patterns

### Creating Complex Numbers

```python
# O(1) - create from components
real = 3.0
imag = 4.0
c = complex(real, imag)  # (3+4j)

# Using j literal
c = 3 + 4j  # Direct syntax (no function call)

# From string
c = complex("3+4j")  # O(5)
```

## Performance Patterns

### vs Tuple Representation

```python
# Both O(1), but complex is specialized
# Complex
c = complex(3, 4)
real_part = c.real      # 3
imag_part = c.imag      # 4

# Tuple (if you need to store both)
coords = (3, 4)
real_part = coords[0]   # 3
imag_part = coords[1]   # 4

# Complex has mathematical operations
c1 = complex(3, 4)
c2 = complex(1, 2)
result = c1 + c2  # (4+6j) - direct addition

# Tuples need manual computation
coords1 = (3, 4)
coords2 = (1, 2)
result = (coords1[0] + coords2[0], coords1[1] + coords2[1])
```

### String vs Direct

```python
# Direct - O(1)
c = 3 + 4j

# From string - O(n)
c = complex("3+4j")  # O(5)

# For constants, use direct notation
# For user input, use complex()
```

## Edge Cases

### Zero Complex

```python
# O(1)
c = complex(0, 0)  # 0j
c = complex(0)     # 0j
c = 0 + 0j         # 0j
```

### Pure Real

```python
# O(1) - imaginary part is zero
c = complex(5, 0)  # (5+0j)
c = complex(5.5)   # (5.5+0j)
```

### Pure Imaginary

```python
# O(1) - real part is zero
c = complex(0, 3)  # 3j
c = 3j             # Direct notation
```

### Conjugate

```python
# O(1) - flip sign of imaginary part
c = complex(3, 4)     # (3+4j)
conj = c.conjugate()  # (3-4j)

# Useful in calculations
magnitude_sq = (c * c.conjugate()).real  # 9 + 16 = 25.0
```

### From String Errors

```python
# O(n) - parsing errors
try:
    c = complex("3 + 4j")  # ValueError - spaces not allowed
except ValueError:
    pass

try:
    c = complex("3+4j+5j")  # ValueError - invalid format
except ValueError:
    pass
```

## Mathematical Functions

```python
# O(1) - all mathematical operations
import cmath

c = complex(3, 4)

# Trigonometric
sin_c = cmath.sin(c)      # O(1)
cos_c = cmath.cos(c)      # O(1)

# Logarithm
log_c = cmath.log(c)      # O(1)

# Square root
sqrt_c = cmath.sqrt(c)    # O(1)

# Exponential
exp_c = cmath.exp(c)      # O(1)
```

## Methods

| Method | Time | Space | Notes |
|--------|------|-------|-------|
| `conjugate()` | O(1) | O(1) | Return complex conjugate (flip sign of imaginary) |
| `from_number(x)` | O(1) | O(1) | Class method; convert number to complex (Python 3.14+) |

## Attributes

| Attribute | Time | Notes |
|-----------|------|-------|
| `real` | O(1) | Real part as float |
| `imag` | O(1) | Imaginary part as float |

## Attributes and Methods Examples

```python
# O(1) - access properties
c = complex(3, 4)

real_part = c.real        # 3.0
imag_part = c.imag        # 4.0
conj = c.conjugate()      # (3-4j)

# Magnitude
magnitude = abs(c)        # 5.0

# Phase angle
import cmath
phase = cmath.phase(c)    # atan2(4, 3)

# From number (Python 3.14+)
c = complex.from_number(3.14)  # (3.14+0j)
```

## Best Practices

✅ **Do**:

- Use complex literal notation: `3 + 4j`
- Use `complex()` for string parsing: `complex("3+4j")`
- Use `cmath` module for complex math functions
- Use `.real` and `.imag` for components

❌ **Avoid**:

- Assuming complex() is faster than literal (it's not)
- Using complex for 2D vectors (not designed for that)
- Forgetting j suffix when typing imaginary literals
- Missing the `cmath` module (regular math won't work)

## Related Functions

- **[abs()](abs.md)** - Magnitude of complex number
- **[cmath](https://docs.python.org/3/library/cmath.html)** - Complex math functions
- **[complex.conjugate()](index.md)** - Complex conjugate

## Version Notes

- **Python 2.x**: Complex numbers available
- **Python 3.x**: Same behavior, integrated well
- **All versions**: 64-bit floating-point components

## Further Reading

- [CPython Internals: complex](https://zpoint.github.io/CPython-Internals/BasicObject/complex/complex.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's complex implementation
