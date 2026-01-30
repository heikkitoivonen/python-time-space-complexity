# cmath Module Complexity

The `cmath` module provides complex-number versions of many mathematical
functions. All scalar operations are O(1) time and O(1) space per call.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Trig: `sin`, `cos`, `tan` | O(1) | O(1) | Complex trig functions |
| Hyperbolic: `sinh`, `cosh`, `tanh` | O(1) | O(1) | Complex hyperbolic |
| Inverse trig: `asin`, `acos`, `atan` | O(1) | O(1) | Complex inverse trig |
| Inverse hyperbolic: `asinh`, `acosh`, `atanh` | O(1) | O(1) | Complex inverse hyperbolic |
| Exponentials: `exp` | O(1) | O(1) | Complex exponential |
| Logs: `log`, `log10` | O(1) | O(1) | Complex logarithms |
| Roots: `sqrt` | O(1) | O(1) | Principal square root |
| Conversions: `polar`, `rect`, `phase` | O(1) | O(1) | Between polar/rect |
| Predicates: `isfinite`, `isinf`, `isnan`, `isclose` | O(1) | O(1) | Complex checks |
| Constants: `pi`, `tau`, `e`, `inf`, `nan`, `infj`, `nanj` | O(1) | O(1) | Scalar constants |

## Examples

### Complex Trigonometry

```python
import cmath

z = 1 + 2j
value = cmath.sin(z)  # O(1)
```

### Polar and Rectangular Forms

```python
import cmath

z = 3 + 4j
r, phi = cmath.polar(z)  # O(1)
back = cmath.rect(r, phi)  # O(1)
```

### Predicates

```python
import cmath

z = complex('nan')
assert cmath.isnan(z)  # O(1)
```

## Related Documentation

- [math Module](math.md)
- [complex() Function](../builtins/complex_func.md)
