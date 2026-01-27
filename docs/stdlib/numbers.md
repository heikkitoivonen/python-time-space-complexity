# Numbers Module

The `numbers` module provides abstract base classes for numeric types, allowing you to check types and create numeric hierarchies.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `isinstance(obj, Number)` | Varies | O(1) | Depends on ABC cache and MRO length |
| `issubclass(cls, Number)` | Varies | O(1) | Depends on ABC cache and MRO length |
| `register(cls)` | Varies | O(1) | Updates ABC registries |

## Common Operations

### Checking Numeric Types

```python
import numbers

# Check if number (any numeric type)
value = 42
is_number = isinstance(value, numbers.Number)  # True

# Check specific numeric types
is_integral = isinstance(value, numbers.Integral)  # True
is_real = isinstance(value, numbers.Real)  # True
is_complex = isinstance(value, numbers.Complex)  # True
is_rational = isinstance(value, numbers.Rational)  # True

# Works with all numeric types
print(isinstance(3.14, numbers.Real))           # True
print(isinstance(2+3j, numbers.Complex))        # True
print(isinstance(Decimal('1.5'), numbers.Real)) # True
```

### Numeric Type Hierarchy

```python
import numbers
from fractions import Fraction
from decimal import Decimal

# Check class hierarchy
print(issubclass(int, numbers.Integral))       # True
print(issubclass(float, numbers.Real))         # True
print(issubclass(complex, numbers.Complex))    # True
print(issubclass(Fraction, numbers.Rational))  # True
print(issubclass(Decimal, numbers.Real))       # False - not by default

# Type checking cascade
def process_number(value):
    if isinstance(value, numbers.Integral):
        return "Integer operation"
    elif isinstance(value, numbers.Rational):
        return "Rational operation"
    elif isinstance(value, numbers.Real):
        return "Real operation"
    elif isinstance(value, numbers.Complex):
        return "Complex operation"
    return "Unknown"

result = process_number(Fraction(3, 4))  # "Rational operation"
```

## Common Use Cases

### Creating Numeric Types

```python
import numbers

class MyNumber(numbers.Number):
    """Custom numeric type - O(1)"""
    
    def __init__(self, value):
        self.value = value
    
    def __add__(self, other):
        if isinstance(other, numbers.Number):  # O(1) check
            return MyNumber(self.value + float(other))
        return NotImplemented
    
    def __mul__(self, other):
        if isinstance(other, numbers.Number):  # O(1) check
            return MyNumber(self.value * float(other))
        return NotImplemented

# Usage - O(1) type checks
num = MyNumber(5)
print(isinstance(num, numbers.Number))  # True

result = num + 3  # O(1) to check, O(1) to add
print(result.value)  # 8
```

### Function Argument Validation

```python
import numbers

def calculate_average(values):
    """Calculate average with type validation - O(n)"""
    # O(n) where n = number of values
    total = 0
    for value in values:
        # O(1) type check per value
        if not isinstance(value, numbers.Number):
            raise TypeError(f"Expected number, got {type(value)}")
        total += value
    
    return total / len(values) if values else 0

# Usage - O(n)
result = calculate_average([1, 2, 3, 4, 5])  # O(5) = 3.0
result = calculate_average([1, 2, 'three'])  # O(1) raises TypeError
```

### Type-Safe Numeric Operations

```python
import numbers

class Calculator:
    """Type-safe numeric calculator - O(1) per operation"""
    
    def add(self, a, b):
        """Add two numbers with validation - O(1)"""
        # O(1) to check types
        if not isinstance(a, numbers.Number):
            raise TypeError(f"a must be numeric, got {type(a)}")
        if not isinstance(b, numbers.Number):
            raise TypeError(f"b must be numeric, got {type(b)}")
        
        # O(1) to perform operation
        return a + b
    
    def scale(self, value, factor):
        """Scale numeric value - O(1)"""
        if not isinstance(value, numbers.Number):
            raise TypeError("value must be numeric")
        if not isinstance(factor, numbers.Real):  # O(1)
            raise TypeError("factor must be real")
        
        # O(1) to multiply
        return value * factor

# Usage - O(1) per operation
calc = Calculator()
result = calc.add(5, 3)  # 8
result = calc.scale(result, 2)  # 16
```

### Polymorphic Numeric Functions

```python
import numbers
from decimal import Decimal
from fractions import Fraction

def numeric_reciprocal(value):
    """Return reciprocal, preserving type - O(1)"""
    # O(1) type check
    if not isinstance(value, numbers.Number):
        raise TypeError("value must be numeric")
    
    # O(1) conditional based on type
    if isinstance(value, numbers.Integral):
        # Return as fraction to preserve precision
        return Fraction(1, value)
    elif isinstance(value, numbers.Rational):
        return 1 / value
    elif isinstance(value, numbers.Real):
        return 1.0 / float(value)
    else:  # Complex
        return 1 / value

# Usage - O(1) per call
print(numeric_reciprocal(2))           # Fraction(1, 2)
print(numeric_reciprocal(Fraction(3, 4)))  # Fraction(4, 3)
print(numeric_reciprocal(2.5))         # 0.4
print(numeric_reciprocal(2+3j))        # (0.15384615384615385-0.23076923076923078j)
```

### Constraint Validation

```python
import numbers

def validate_range(value, min_val=None, max_val=None):
    """Validate numeric value is in range - O(1)"""
    # O(1) type check
    if not isinstance(value, numbers.Number):
        raise TypeError("value must be numeric")
    
    # O(1) comparisons (for most types)
    if min_val is not None and value < min_val:
        raise ValueError(f"value {value} < minimum {min_val}")
    if max_val is not None and value > max_val:
        raise ValueError(f"value {value} > maximum {max_val}")
    
    return value

# Usage - O(1)
validate_range(5, 1, 10)      # OK
validate_range(15, 1, 10)     # Raises ValueError
```

### Accepting Multiple Numeric Types

```python
import numbers
from decimal import Decimal
from fractions import Fraction

def flexible_divide(numerator, denominator):
    """Accept any numeric types - O(1)"""
    # O(1) type validation for each
    if not isinstance(numerator, numbers.Number):
        raise TypeError("numerator must be numeric")
    if not isinstance(denominator, numbers.Number):
        raise TypeError("denominator must be numeric")
    
    # O(1) - Python handles type coercion
    try:
        return numerator / denominator
    except ZeroDivisionError:
        return None

# Usage - O(1) per call, works with any numeric type
print(flexible_divide(10, 2))              # 5.0
print(flexible_divide(Fraction(10, 3), 2))  # Fraction(5, 3)
print(flexible_divide(Decimal(10), 3))     # Decimal('3.333...')
print(flexible_divide(10+5j, 2))           # (5+2.5j)
```

## Number Hierarchy

```
Number                          # Base - any number
├── Complex                     # Complex numbers
├── Real                        # Real numbers (no imaginary part)
│   └── Rational               # Exact fractions
│       └── Integral           # Whole numbers
```

## Performance Tips

### Cache Type Checks

```python
import numbers

class NumberProcessor:
    """Cache type check results - O(1) lookup"""
    
    def __init__(self):
        self._type_cache = {}
    
    def process(self, value):
        """O(1) cached type check"""
        value_id = id(type(value))
        
        if value_id not in self._type_cache:
            # O(1) first time
            self._type_cache[value_id] = self._determine_type(value)
        
        return self._type_cache[value_id]
    
    def _determine_type(self, value):
        """O(1) type determination"""
        if isinstance(value, numbers.Integral):
            return "integral"
        elif isinstance(value, numbers.Rational):
            return "rational"
        elif isinstance(value, numbers.Real):
            return "real"
        else:
            return "complex"

# Usage - O(1) after first call
processor = NumberProcessor()
for value in [1, 2, 3, 1.5, 2+3j]:
    result = processor.process(value)  # O(1) cached
```

### Batch Type Checking

```python
import numbers

def process_numbers(values):
    """Batch validate - O(n)"""
    # O(n) validation
    if not all(isinstance(v, numbers.Number) for v in values):
        raise TypeError("All values must be numeric")
    
    # O(n) processing
    return sum(values) / len(values)
```

## Version Notes

- **Python 2.6+**: numbers module available
- **Python 3.x**: All classes available
- **Python 3.x**: Decimal and Fraction support

## Related Documentation

- [Decimal Module](decimal.md) - Precise decimal arithmetic
- [Fractions Module](fractions.md) - Rational numbers
- Math Module - Mathematical functions
