# decimal Module Complexity

The `decimal` module provides support for decimal floating point arithmetic with arbitrary precision, avoiding binary floating point rounding errors.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Decimal(value)` | O(n) | O(n) | n = digits in value |
| `Decimal.from_float(f)` | O(1) | O(1) | Convert from float |
| Addition/Subtraction | O(n) | O(n) | n = max digits |
| Multiplication | O(n²) | O(n) | Grade-school; Python uses Karatsuba for large n |
| Division | O(n²) | O(n) | Long division algorithm |
| `quantize()` | O(n) | O(n) | Round to precision |
| Comparison | O(n) | O(1) | n = digits to compare |

## Creating Decimal Objects

### Basic Creation

```python
from decimal import Decimal

# Create from string - O(n) where n = string length
d1 = Decimal('3.14')    # O(4)
d2 = Decimal('0.1')     # O(3)
d3 = Decimal('123456')  # O(6)

# Create from integer - O(n)
d4 = Decimal(42)        # O(2)

# Create from float (caution) - O(1)
d5 = Decimal(0.1)       # O(1) but inaccurate!
# Result: Decimal('0.1000000000000000055511151231257827021181583404541015625')
```

### Why Not Floats?

```python
from decimal import Decimal

# Float rounding error
print(0.1 + 0.2)  # 0.30000000000000004

# Decimal avoids this - O(n) for each operation
d1 = Decimal('0.1')
d2 = Decimal('0.2')
result = d1 + d2  # O(1 + 1) = O(1) - perfect precision
# Result: Decimal('0.3')
```

## Arithmetic Operations

### Basic Operations

```python
from decimal import Decimal

# Addition - O(n) where n = max digits
a = Decimal('10.5')
b = Decimal('20.3')
result = a + b  # Decimal('30.8') - O(4)

# Subtraction - O(n)
result = b - a  # Decimal('9.8') - O(4)

# Multiplication - O(n²) for grade-school multiply
a = Decimal('123')  # 3 digits
b = Decimal('456')  # 3 digits
result = a * b  # O(9) - quadratic
# Result: Decimal('56088')

# Division - O(n²)
a = Decimal('100')
b = Decimal('3')
result = a / b  # O(n²) where n = precision
# Result: Decimal('33.33333333333333333333333333')
```

### Setting Precision

```python
from decimal import Decimal, getcontext

# Get current context
ctx = getcontext()
print(ctx.prec)  # Default: 28 digits

# Set precision - affects all operations
ctx.prec = 10

# Now operations use 10 digits - O(n)
result = Decimal('1') / Decimal('3')
print(result)  # Decimal('0.3333333333')

# Restore
ctx.prec = 28
```

## Common Operations

### Rounding

```python
from decimal import Decimal, ROUND_HALF_UP

# Create decimal
d = Decimal('2.675')

# Quantize to 2 decimal places - O(n)
rounded = d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
# Result: Decimal('2.68')

# Different rounding modes
from decimal import ROUND_DOWN, ROUND_UP, ROUND_CEILING, ROUND_FLOOR

d.quantize(Decimal('0.01'), rounding=ROUND_DOWN)      # 2.67
d.quantize(Decimal('0.01'), rounding=ROUND_UP)        # 2.68
d.quantize(Decimal('0.01'), rounding=ROUND_CEILING)   # 2.68
d.quantize(Decimal('0.01'), rounding=ROUND_FLOOR)     # 2.67
```

### String Formatting

```python
from decimal import Decimal

# Format decimal - O(n)
d = Decimal('3.14159265')

# Using format() - O(n)
formatted = format(d, '.2f')  # '3.14' - O(4)

# Using f-string - O(n)
formatted = f"{d:.2f}"  # '3.14'

# As string - O(n)
s = str(d)  # '3.14159265'
```

### Money Calculations

```python
from decimal import Decimal, ROUND_HALF_UP

# Prices with Decimal
price = Decimal('19.99')
quantity = 3

# Multiplication - O(n²)
total = price * quantity  # Decimal('59.97')

# Tax calculation - O(n²)
tax_rate = Decimal('0.08')
tax = (total * tax_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
# tax = Decimal('4.80')

final = total + tax
# final = Decimal('64.77')
```

## Performance Considerations

### Decimal vs Float

```python
import time
from decimal import Decimal

# Float operations (fast but imprecise)
start = time.time()
result = 0.0
for _ in range(100000):
    result += 0.1
end = time.time()
print(f"Float time: {end - start}")  # Very fast
print(result)  # 10000.000000000002

# Decimal operations (slower but precise)
start = time.time()
result = Decimal('0')
for _ in range(100000):
    result += Decimal('0.1')
end = time.time()
print(f"Decimal time: {end - start}")  # Slower - O(n²)
print(result)  # Decimal('10000')
```

### Precision Impact

```python
from decimal import Decimal, getcontext

# Higher precision = slower operations
ctx = getcontext()

# Low precision (faster)
ctx.prec = 10
result = Decimal('1') / Decimal('3')  # O(10)

# High precision (slower)
ctx.prec = 100
result = Decimal('1') / Decimal('3')  # O(100)

# Each digit added increases computation
```

### Caching Decimals

```python
from decimal import Decimal

# Pre-compute common values - O(n) once
TAX_RATE = Decimal('0.08')
SHIPPING = Decimal('5.99')
DISCOUNT = Decimal('0.10')

# Reuse in loop - O(n) per operation, not O(n²)
prices = [Decimal(str(p)) for p in [10, 20, 30]]

for price in prices:
    total = price * (1 - DISCOUNT) + SHIPPING  # O(n)
    # Use tax_rate
```

## Comparisons

```python
from decimal import Decimal

# Equality - O(n) where n = digits
a = Decimal('10.00')
b = Decimal('10.0')
a == b  # True - O(4)

# Less than - O(n)
a < b   # False - O(4)

# Comparison with string (must convert) - O(n)
a == Decimal('10')  # True

# Comparison with float (works but imprecise)
a == 10.0  # True (generally, but be careful)
```

## Context Management

### Local Context

```python
from decimal import Decimal, localcontext

# Global precision
getcontext().prec = 28

with localcontext() as ctx:
    # Local precision change
    ctx.prec = 10
    result = Decimal('1') / Decimal('3')  # O(10)
    print(result)  # Decimal('0.3333333333')

# Global precision restored
result = Decimal('1') / Decimal('3')
print(result)  # More digits - O(28)
```

## Financial Calculations

### Invoice Calculation

```python
from decimal import Decimal, ROUND_HALF_UP, localcontext

def calculate_invoice(items, tax_rate):
    """Calculate invoice total with tax"""
    with localcontext() as ctx:
        ctx.prec = 10  # Sufficient for money
        
        # Sum items - O(n * m) where n = items, m = digits
        subtotal = sum((Decimal(str(price)) * qty for price, qty in items),
                      Decimal('0'))
        
        # Apply tax - O(m)
        tax = (subtotal * Decimal(str(tax_rate))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Total - O(m)
        total = (subtotal + tax).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return subtotal, tax, total

# Usage - O(n * m)
items = [(19.99, 1), (5.50, 2), (100, 0.5)]
subtotal, tax, total = calculate_invoice(items, 0.08)
```

## String Representations

```python
from decimal import Decimal

d = Decimal('123.456')

# As string - O(n)
str(d)          # '123.456'

# With engineering notation - O(n)
d.to_eng_string()  # '123.456'

# As tuple (sign, digits, exponent) - O(1)
d.as_tuple()    # DecimalTuple(sign=0, digits=(1,2,3,4,5,6), exponent=-3)
```

## Special Values

```python
from decimal import Decimal

# Special values
Decimal('Infinity')    # Positive infinity
Decimal('-Infinity')   # Negative infinity
Decimal('NaN')         # Not a number

# Create from float
import math
Decimal(math.inf)      # Decimal('Infinity')

# Operations with special values
d = Decimal('10')
d / Decimal('0')       # Raises InvalidOperation

Decimal('Infinity') + 5  # Decimal('Infinity')
Decimal('NaN') + 5       # Decimal('NaN')
```

## Version Notes

- **Python 2.x**: Decimal module available (limited support)
- **Python 3.x**: Full Decimal support with many rounding modes
- **Python 3.8+**: Improved performance and new operations

## Related Modules

- **[fractions](fractions.md)** - Rational number arithmetic (exact but slower)
- **[math](math.md)** - Mathematical functions (uses floats)
- **[numbers](numbers.md)** - Numeric abstract base classes

## Best Practices

✅ **Do**:
- Use Decimal for financial calculations (exact results)
- Create Decimal from strings, not floats
- Set appropriate precision for your domain
- Use `quantize()` for rounding money
- Cache common Decimal values

❌ **Avoid**:
- Mixing Decimal and float operations (convert both to Decimal)
- Creating Decimal from float: `Decimal(0.1)` ❌ use `Decimal('0.1')` ✅
- Excessive precision (slower without benefit)
- Using Decimal for scientific computation (use float)
- Forgetting that multiplication is O(n²)
