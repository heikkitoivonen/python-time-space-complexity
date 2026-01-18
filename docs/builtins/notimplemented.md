# NotImplemented Constant Complexity

The `NotImplemented` constant is a singleton used to indicate that an operation is not implemented for the given operands. It's distinct from `NotImplementedError` exception.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Comparison | O(1) | O(1) | Identity check with `is` |
| Type check | O(1) | O(1) | `type(NotImplemented)` |
| Return from method | O(1) | O(1) | Signal operation not supported |
| Assignment | O(1) | O(1) | Single object |

## Basic Usage

### Comparison Operations

```python
# O(1) - return NotImplemented for unsupported operations
class MyClass:
    def __eq__(self, other):
        if isinstance(other, MyClass):
            return self.value == other.value
        # O(1) - signal "don't know how to compare"
        return NotImplemented

# O(1) - Python tries reflected operation
obj1 = MyClass()
obj2 = "string"

# obj1 == obj2:
# 1. Calls obj1.__eq__(obj2) -> NotImplemented
# 2. Tries obj2.__eq__(obj1) -> might handle it
# 3. Falls back to identity comparison
result = obj1 == obj2  # False via fallback
```

### Arithmetic Operations

```python
# O(1) - NotImplemented for unsupported types
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __add__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x + other.x, self.y + other.y)
        # O(1) - unsupported operand type
        return NotImplemented

# O(1) - uses NotImplemented
v1 = Vector(1, 2)
v2 = Vector(3, 4)

result = v1 + v2  # Works - Vector(4, 6)

# v1 + "string":
# 1. v1.__add__("string") -> NotImplemented
# 2. "string".__radd__(v1) -> TypeError
# 3. TypeError: unsupported operand type(s)
```

### Reflected Operations

```python
# O(1) - NotImplemented enables fallback
class Number:
    def __init__(self, value):
        self.value = value
    
    def __mul__(self, other):
        if isinstance(other, Number):
            return Number(self.value * other.value)
        return NotImplemented  # O(1)
    
    def __rmul__(self, other):
        # Reflected operation (other * self)
        if isinstance(other, int):
            return Number(other * self.value)
        return NotImplemented  # O(1)

# O(1) - normal operation
n1 = Number(5)
n2 = Number(3)
result = n1 * n2  # Number(15)

# O(1) - reflected operation
result = 10 * n1  # Number(50)
# 1. int.__mul__(Number) -> NotImplemented
# 2. Number.__rmul__(10) -> handles it
```

## Complexity Details

### Singleton Pattern

```python
# O(1) - NotImplemented is a singleton
not_impl1 = NotImplemented
not_impl2 = NotImplemented

# Both refer to same object
print(not_impl1 is not_impl2)  # True - O(1)
print(id(not_impl1) == id(not_impl2))  # True - O(1)

# Type
type(NotImplemented)  # <class 'NotImplementedType'> - O(1)
```

### Comparison with NotImplementedError

```python
# O(1) - NotImplemented is a value, not an error
value = NotImplemented  # O(1)

# NotImplementedError is an exception
try:
    raise NotImplementedError("Not ready")
except NotImplementedError:
    print("Feature not implemented")

# Key difference:
# - NotImplemented: return value from dunder methods
# - NotImplementedError: exception raised for missing features
```

### Operation Resolution

```python
# O(1) - Python's operation resolution order
class A:
    def __eq__(self, other):
        return NotImplemented  # O(1)

class B:
    def __eq__(self, other):
        return True

# O(1) - Python tries both directions
a = A()
b = B()

# a == b:
# 1. a.__eq__(b) -> NotImplemented (O(1))
# 2. b.__eq__(a) -> True (O(1))
# 3. Result: True

result = a == b  # True
```

## Performance Patterns

### Avoiding Type Checking Overhead

```python
# Efficient - return NotImplemented early
class Matrix:
    def __add__(self, other):
        if not isinstance(other, Matrix):  # O(1) type check
            return NotImplemented  # O(1)
        
        # Only execute complex logic for valid types
        return Matrix(...)  # O(n²) for matrix addition

# vs raising error (slower)
class BadMatrix:
    def __add__(self, other):
        if not isinstance(other, BadMatrix):
            raise TypeError("...")  # Exception overhead
        return BadMatrix(...)

# NotImplemented is faster: no exception overhead
```

### Type Coercion Pattern

```python
# O(1) - enable type coercion through NotImplemented
class Currency:
    def __init__(self, amount, currency):
        self.amount = amount
        self.currency = currency
    
    def __add__(self, other):
        if isinstance(other, Currency):
            if self.currency == other.currency:
                return Currency(self.amount + other.amount, 
                              self.currency)
        # O(1) - Python will try other.__radd__(self)
        return NotImplemented

class USD(Currency):
    def __init__(self, amount):
        super().__init__(amount, "USD")
    
    def __radd__(self, other):
        if isinstance(other, (int, float)):
            return USD(other + self.amount)
        return NotImplemented

# O(1) - enables flexible operations
usd = USD(100)
result = 50 + usd  # USD(150)
# 1. int.__add__(USD) -> NotImplemented
# 2. USD.__radd__(50) -> USD(150)
```

## Common Use Cases

### Rich Comparison Methods

```python
# O(n) - implement comparisons properly
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __eq__(self, other):
        if not isinstance(other, Point):  # O(1)
            return NotImplemented  # O(1)
        return self.x == other.x and self.y == other.y  # O(1)
    
    def __lt__(self, other):
        if not isinstance(other, Point):  # O(1)
            return NotImplemented  # O(1)
        return (self.x, self.y) < (other.x, other.y)  # O(1)
    
    def __le__(self, other):
        return self == other or self < other  # O(1)

# O(1) - use comparisons
p1 = Point(1, 2)
p2 = Point(3, 4)
p3 = "not a point"

result = p1 == p2  # False
result = p1 < p2   # True
result = p1 == p3  # False (via NotImplemented)
```

### Container Emulation

```python
# O(n) - implement container protocol
class CustomList:
    def __init__(self, items):
        self.items = items
    
    def __getitem__(self, index):
        if isinstance(index, int):  # O(1)
            return self.items[index]  # O(1)
        if isinstance(index, slice):  # O(1)
            return CustomList(self.items[index])  # O(k) for slice
        # O(1) - unsupported index type
        return NotImplemented
    
    def __setitem__(self, index, value):
        if not isinstance(index, int):  # O(1)
            return NotImplemented  # O(1)
        self.items[index] = value  # O(1)

# O(1) - use container
cl = CustomList([1, 2, 3, 4])
print(cl[0])      # 1
print(cl[1:3])    # CustomList([2, 3])
# cl["key"] would trigger NotImplemented
```

### Operator Overloading

```python
# O(1) - proper operator overloading
class Quantity:
    def __init__(self, value, unit):
        self.value = value
        self.unit = unit
    
    def __mul__(self, scalar):
        if isinstance(scalar, (int, float)):  # O(1)
            return Quantity(self.value * scalar, self.unit)
        return NotImplemented  # O(1)
    
    def __rmul__(self, scalar):
        return self.__mul__(scalar)  # O(1)
    
    def __truediv__(self, scalar):
        if isinstance(scalar, (int, float)):  # O(1)
            return Quantity(self.value / scalar, self.unit)
        return NotImplemented  # O(1)

# O(1) - use operators
qty = Quantity(10, "meters")
result = qty * 2      # Quantity(20, "meters")
result = 3 * qty      # Quantity(30, "meters")
result = qty / 2      # Quantity(5.0, "meters")
```

## Advanced Usage

### Custom Protocol Implementation

```python
# O(1) - implement custom protocols with NotImplemented
class HashableContainer:
    def __hash__(self):
        if self._is_mutable():  # O(1)
            return NotImplemented  # Signal: not hashable
        return hash(tuple(self.items))  # O(n)

class MutableContainer:
    def __hash__(self):
        return NotImplemented  # O(1) - containers are unhashable

# O(1) - Python respects NotImplemented
hashable = HashableContainer()
try:
    my_set = {hashable}  # Works if __hash__ doesn't return NotImplemented
except TypeError:
    print("Object not hashable")
```

### Context Manager Protocol

```python
# O(1) - NotImplemented in context managers
class OptionalContext:
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        return NotImplemented  # O(1) - don't suppress exceptions

class SuppressingContext:
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        return True  # Suppress exceptions

# O(1) - context manager behavior
with OptionalContext():
    raise ValueError("test")  # Exception propagates

with SuppressingContext():
    raise ValueError("test")  # Exception suppressed
```

## Practical Examples

### Flexible Type System

```python
# O(1) - build flexible operations
class Temperature:
    def __init__(self, kelvin):
        self.kelvin = kelvin
    
    def __eq__(self, other):
        if isinstance(other, Temperature):  # O(1)
            return self.kelvin == other.kelvin
        elif isinstance(other, (int, float)):  # O(1)
            return self.kelvin == other
        return NotImplemented  # O(1)
    
    def __add__(self, other):
        if isinstance(other, (int, float)):  # O(1)
            return Temperature(self.kelvin + other)
        return NotImplemented  # O(1)
    
    def __radd__(self, other):
        return self.__add__(other)  # O(1)

# O(1) - flexible operations
temp = Temperature(300)
result = temp == 300      # True
result = temp + 10        # Temperature(310)
result = 10 + temp        # Temperature(310)
```

### Numeric Hierarchy

```python
# O(1) - proper numeric operations
class Fraction:
    def __init__(self, num, denom):
        self.num = num
        self.denom = denom
    
    def __add__(self, other):
        if isinstance(other, Fraction):  # O(1)
            # Add fractions
            return Fraction(
                self.num * other.denom + other.num * self.denom,
                self.denom * other.denom
            )
        elif isinstance(other, int):  # O(1)
            return self + Fraction(other, 1)
        return NotImplemented  # O(1)
    
    def __radd__(self, other):
        return self.__add__(other)  # O(1)

# O(1) - numeric operations
frac = Fraction(1, 2)
result = frac + Fraction(1, 3)  # Fraction(5, 6)
result = frac + 2               # Fraction(5, 2)
result = 2 + frac               # Fraction(5, 2)
```

## Edge Cases

### Truthiness of NotImplemented

```python
# O(1) - NotImplemented is truthy
if NotImplemented:  # O(1)
    print("NotImplemented is truthy!")  # This prints

# Don't use in boolean context!
# Always check with 'is'
if result is NotImplemented:  # O(1) - correct
    print("Not implemented")
```

### NotImplemented in Comparisons

```python
# O(1) - NotImplemented changes behavior
class A:
    def __eq__(self, other):
        return NotImplemented  # O(1)

class B:
    pass

a = A()
b = B()

# a == b uses NotImplemented fallback
# Since B doesn't define __eq__, falls back to identity
result = a == b  # False - identity comparison
```

## Performance Considerations

### Avoid Exception Overhead

```python
# Efficient - return NotImplemented
class Efficient:
    def __add__(self, other):
        if not isinstance(other, Efficient):  # O(1)
            return NotImplemented  # O(1)
        return Efficient(...)

# Inefficient - raise exception
class Inefficient:
    def __add__(self, other):
        try:
            # Might work with any type...
            return Efficient(...)
        except (TypeError, AttributeError):
            # Very slow - exception overhead!
            raise TypeError(...)

# NotImplemented is ~100x faster than exception handling
```

## Best Practices

✅ **Do**:

- Return NotImplemented from dunder methods for unsupported types
- Check with `is NotImplemented` (not equality)
- Use for operator overloading
- Enable Python's operation resolution
- Keep method implementation simple
- Document supported types

❌ **Avoid**:

- Raising NotImplementedError in dunder methods (use NotImplemented)
- Using `== NotImplemented` (use `is NotImplemented`)
- Returning NotImplemented from regular methods
- Assuming NotImplemented is falsy (it's truthy!)
- Complex logic before returning NotImplemented
- Confusing with NotImplementedError exception

## Related Constants

- **[NotImplementedError](https://docs.python.org/3/library/exceptions.html#NotImplementedError)** - Exception for unimplemented features
- **[None](none.md)** - Null value
- **[True](true.md)** - Boolean true
- **[False](false.md)** - Boolean false

## Version Notes

- **Python 2.x**: NotImplemented available, same behavior
- **Python 3.x**: Same behavior, optimized
- **All versions**: Singleton for operation resolution
