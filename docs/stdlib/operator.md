# Operator Module Complexity

The `operator` module provides function equivalents for Python's operators, useful for functional programming and avoiding lambda expressions.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `add(a, b)` | Varies | Varies | Same as `a + b` |
| `mul(a, b)` | Varies | Varies | Same as `a * b` |
| `itemgetter(key)` | O(1) | O(1) | Get item function |
| `attrgetter(name)` | O(1) | O(1) | Get attribute function |
| `methodcaller(name)` | O(1) | O(1) | Call method function |

## Arithmetic Operators

### Basic Operations

#### Time Complexity: Varies by operand type

```python
import operator

# Arithmetic: same as a + b, etc.
result = operator.add(5, 3)      # 8
result = operator.sub(10, 4)     # 6
result = operator.mul(6, 7)      # 42
result = operator.truediv(10, 2) # 5.0
result = operator.floordiv(10, 3) # 3
result = operator.mod(10, 3)     # 1
result = operator.pow(2, 8)      # 256

# Using with map: O(n)
numbers = [1, 2, 3, 4, 5]
doubled = list(map(operator.mul, numbers, [2] * len(numbers)))  # O(n)
```

#### Space Complexity: Varies by operand type

```python
import operator

result = operator.add(a, b)  # Same as a + b
```

## Comparison Operators

### Time Complexity: Varies by operand type

```python
import operator

# Comparisons: same as a == b, a < b, etc.
operator.eq(5, 5)    # True
operator.ne(5, 3)    # True
operator.lt(3, 5)    # True
operator.le(3, 5)    # True
operator.gt(5, 3)    # True
operator.ge(5, 3)    # True

# With sorted: O(n log n)
items = [(5,), (2,), (8,), (1,), (9,)]
sorted_items = sorted(items, key=operator.itemgetter(0))  # O(n log n)
```

### Space Complexity: O(1)

```python
import operator

result = operator.eq(a, b)  # Same as a == b
```

## Item and Attribute Access

### itemgetter()

#### Time Complexity: Depends on the called method

```python
import operator

# Get item: O(1) per access
getter = operator.itemgetter(1)  # Get index 1
result = getter([10, 20, 30])  # 20 - O(1)

# Multiple items: O(k) where k = keys
getter = operator.itemgetter('name', 'age')
result = getter({'name': 'Alice', 'age': 30})  # ('Alice', 30) - O(k)

# Extract from list of dicts: O(n*k)
data = [
    {'name': 'Alice', 'age': 30},
    {'name': 'Bob', 'age': 25},
    {'name': 'Charlie', 'age': 35},
]
names = list(map(operator.itemgetter('name'), data))  # O(n)
# Result: ['Alice', 'Bob', 'Charlie']
```

#### Space Complexity: O(k)

```python
import operator

getter = operator.itemgetter('name', 'age')  # O(k) space for result tuple
```

### attrgetter()

#### Time Complexity: O(1)

```python
import operator

class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

# Get attribute: O(1)
getter = operator.attrgetter('name')
person = Person('Alice', 30)
result = getter(person)  # 'Alice' - O(1)

# Multiple attributes: O(k)
getter = operator.attrgetter('name', 'age')
result = getter(person)  # ('Alice', 30) - O(k)

# From list of objects: O(n)
people = [Person('Alice', 30), Person('Bob', 25)]
names = list(map(operator.attrgetter('name'), people))  # O(n)
# Result: ['Alice', 'Bob']
```

#### Space Complexity: O(k)

```python
import operator

getter = operator.attrgetter('name', 'age')  # O(k) space for result tuple
```

### methodcaller()

#### Time Complexity: O(1)

```python
import operator

# Call method: O(m) where m = method complexity
caller = operator.methodcaller('upper')
result = caller('hello')  # 'HELLO' - O(n) for string

# With arguments: still depends on method complexity
caller = operator.methodcaller('replace', 'a', 'b')
result = caller('banana')  # 'bbnbnb' - O(n) for string

# Call on list of objects: O(n*m)
strings = ['hello', 'world', 'python']
uppers = list(map(operator.methodcaller('upper'), strings))  # O(n*m)
# Result: ['HELLO', 'WORLD', 'PYTHON']
```

#### Space Complexity: Depends on the called method

```python
import operator

caller = operator.methodcaller('upper')  # O(1) space for method ref
result = caller(string)  # Same as string.upper()
```

## In-Place Operations

### Time Complexity: O(1)

```python
import operator

# In-place operations: O(1) typically
x = 10
x = operator.iadd(x, 5)  # x += 5, returns 15 - O(1)

x = [1, 2, 3]
x = operator.iadd(x, [4, 5])  # x += [4, 5] - O(n) for list
# Result: [1, 2, 3, 4, 5]

# In-place multiply
x = 3
x = operator.imul(x, 4)  # x *= 4 - O(1)
```

### Space Complexity: O(1)

```python
import operator

x = operator.iadd(x, y)  # O(1) extra space (modifies in-place)
```

## Common Patterns

### Sort by Attribute

```python
import operator

class Student:
    def __init__(self, name, grade):
        self.name = name
        self.grade = grade

students = [
    Student('Alice', 85),
    Student('Bob', 92),
    Student('Charlie', 78),
]

# Sort by grade: O(n log n)
sorted_students = sorted(students, key=operator.attrgetter('grade'))  # O(n log n)
```

### Extract Multiple Values

```python
import operator

data = [
    ('Alice', 30, 'NY'),
    ('Bob', 25, 'LA'),
    ('Charlie', 35, 'SF'),
]

# Get names and ages: O(n)
getter = operator.itemgetter(0, 1)
results = list(map(getter, data))  # O(n)
# [('Alice', 30), ('Bob', 25), ('Charlie', 35)]
```

### Functional Programming

```python
import operator
from functools import reduce

# Sum with reduce: O(n)
numbers = [1, 2, 3, 4, 5]
total = reduce(operator.add, numbers)  # 15 - O(n)

# Product: O(n)
product = reduce(operator.mul, numbers)  # 120 - O(n)

# Logical operations: O(n)
bools = [True, True, False]
all_true = reduce(operator.and_, bools)  # False - O(n)
any_true = reduce(operator.or_, bools)   # True - O(n)
```

### Filter and Map Operations

```python
import operator

# Count with operator: O(n)
items = [5, 2, 8, 1, 9]
count_gt_5 = sum(map(operator.gt, items, [5] * len(items)))  # O(n)

# Apply to sequences: O(n)
data = {'a': 1, 'b': 2, 'c': 3}
values = list(map(operator.itemgetter(1), data.items()))  # O(n)
```

## Performance Characteristics

### Best Practices

```python
import operator

# Good: Use operator functions instead of lambdas
sorted(data, key=operator.itemgetter('age'))  # Efficient, clear

# Good: Use attrgetter for objects
names = map(operator.attrgetter('name'), objects)  # Clear intent

# Avoid: Complex lambdas when operator works
sorted(data, key=lambda x: x[0])  # Works, but less clear

# Better: Use itemgetter
sorted(data, key=operator.itemgetter(0))  # Clear and efficient
```

### Functional Composition

```python
import operator
from functools import reduce

# Good: Compose with reduce
result = reduce(operator.add, list_of_numbers)  # O(n)

# Avoid: Manual loop (same complexity, more code)
total = 0
for num in numbers:
    total += num
```

## Operator vs Lambda

```python
import operator

# operator module (C-implemented, faster)
sorted(data, key=operator.itemgetter('name'))  # Optimized

# lambda (Python-implemented, slower)
sorted(data, key=lambda x: x['name'])  # Interpreted

# Both O(n log n), but operator is faster in practice
```

## Version Notes

- **Python 3.x**: All operators have functional equivalents
- **Python 2.6+**: operator module well-established

## Related Documentation

- [Functools Module](functools.md) - Function utilities
- [Itertools Module](itertools.md) - Iterator functions
