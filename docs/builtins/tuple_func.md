# tuple() Function Complexity

The `tuple()` function creates tuples from iterables or creates empty tuples.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Empty tuple | O(1) | O(1) | tuple() |
| From iterable | O(n) | O(n) | n = iterable length |
| From string | O(n) | O(n) | n = string length |
| From tuple (exact) | O(1) | O(1) | Returns same object |
| From list | O(n) | O(n) | Creates new tuple |

## Basic Usage

### Create Empty Tuple

```python
# O(1)
t = tuple()  # ()
```

### From List

```python
# O(n) - where n = list length
t = tuple([1, 2, 3])      # (1, 2, 3)
t = tuple([1, 2, 3, 4])   # (1, 2, 3, 4)
```

### From String

```python
# O(n) - where n = string length
t = tuple("hello")   # ('h', 'e', 'l', 'l', 'o')
t = tuple("abc")     # ('a', 'b', 'c')
```

### From Other Iterables

```python
# O(n) - where n = iterable length
t = tuple((1, 2, 3))         # (1, 2, 3)
t = tuple({1, 2, 3})         # Order depends on set iteration
t = tuple(range(5))          # (0, 1, 2, 3, 4)
t = tuple(map(str, [1, 2]))  # ('1', '2')
```

### From Dictionary

```python
# O(n) - uses dict keys
d = {"a": 1, "b": 2, "c": 3}
t = tuple(d)  # ('a', 'b', 'c') - keys in insertion order
```

## Complexity Details

### Iterating and Copying

```python
# O(n) - must iterate to create tuple
original = [1, 2, 3, 4, 5]
t = tuple(original)  # O(5) - creates (1, 2, 3, 4, 5)

# Each element is accessed once
for item in iterable:  # O(n)
    add to tuple
```

### From String

```python
# O(n) - linear in string length
short = tuple("ab")        # O(2) - ('a', 'b')
long = tuple("a" * 1000)   # O(1000)

# Each character becomes one tuple item
```

### From Range

```python
# O(n) - must materialize all values
small = tuple(range(5))      # O(5) - (0, 1, 2, 3, 4)
large = tuple(range(10**6))  # O(10^6) - slow!

# range() is lazy, tuple() forces evaluation
```

## Common Patterns

### Convert Iterable to Tuple

```python
# O(n) - general conversion
def process_items(items):
    items_tuple = tuple(items)  # O(n) - ensure immutable
    # Now can hash, use in set, etc.
    return items_tuple[0]  # O(1)

# Useful for generators
gen = (x for x in range(5))
t = tuple(gen)  # (0, 1, 2, 3, 4)
```

### Create Tuple from List

```python
# O(n) - copy to immutable
lst = [1, 2, 3]
t = tuple(lst)  # (1, 2, 3)

# Safe - can't be modified
# lst.append(4)  # OK - modifies list
# t.append(4)    # AttributeError - tuple immutable
```

### Unpacking Tuple

```python
# O(1) - unpack is fast
t = (1, 2, 3)

# Unpacking
a, b, c = t  # O(1) - constant time
x, *rest = t  # O(1) - unpacking

# Useful with tuple()
items = tuple(range(3))
x, y, z = items  # O(1)
```

## Performance Patterns

### Tuple Literal vs tuple()

```python
# Both O(n) but different syntax

# Literal - faster, no function call
t1 = (1, 2, 3, 4, 5)  # O(n)

# Function - more flexible
t2 = tuple([1, 2, 3, 4, 5])  # O(n)
t3 = tuple(range(5))  # O(n)

# Literal usually preferred for constants
```

### Tuple as Cache Key

```python
# O(n) - create tuple for caching
from functools import lru_cache

@lru_cache(maxsize=128)
def compute(values):
    return sum(values)

# Convert to tuple before caching (hashable)
result = compute(tuple([1, 2, 3]))  # O(3)
result = compute((1, 2, 3))  # O(1) - cache hit
```

### Batch Conversion

```python
# O(n * m) - n items, m = avg iterable length
data = [[1, 2], [3, 4], [5, 6]]
tuples = [tuple(item) for item in data]  # O(n*m)

# Using map
tuples = list(map(tuple, data))  # O(n*m)
```

## Practical Examples

### Function Return Values

```python
# O(n) - return multiple values
def get_coordinates():
    x, y, z = 1, 2, 3
    return (x, y, z)  # O(1) - literal

# or
    return tuple([x, y, z])  # O(3) - function
```

### Dictionary Keys

```python
# O(n) - tuples as keys
locations = {
    (0, 0): "origin",
    (1, 2): "point A",
    (3, 4): "point B",
}

# Can use tuple() to create key
coord = (1, 2)
location = locations.get(coord)  # O(1)
```

### Sequence of Pairs

```python
# O(n) - zip creates iterator of tuples
names = ["Alice", "Bob", "Charlie"]
ages = [25, 30, 35]

pairs = list(zip(names, ages))  # O(n)
# [('Alice', 25), ('Bob', 30), ('Charlie', 35)]

# Convert to tuples explicitly
pairs = [tuple(pair) for pair in ...]  # O(n)
```

### Named Tuple-like Structure

```python
# O(n) - create tuple with labels
def make_person(name, age, email):
    return (name, age, email)

person = make_person("Alice", 25, "alice@example.com")
name, age, email = person  # O(1) unpacking

# vs named tuple (more overhead)
from collections import namedtuple
Person = namedtuple("Person", ["name", "age", "email"])
p = Person("Alice", 25, "alice@example.com")
```

### Immutable State

```python
# O(n) - create immutable snapshot
class DataSnapshot:
    def __init__(self, data):
        self._data = tuple(data)  # O(n)
    
    def get_data(self):
        return self._data  # O(1) - safe to return
    
    def __hash__(self):
        return hash(self._data)  # O(1) - hashable

snapshot = DataSnapshot([1, 2, 3])
data = snapshot.get_data()  # (1, 2, 3)
# Can't modify
```

## Edge Cases

### Empty Tuple

```python
# O(1)
t = tuple()       # ()
t = tuple([])     # ()
t = tuple("")     # ()
```

### Single Item

```python
# O(1) - must use trailing comma for single item
t = (1,)  # (1,) - tuple
x = (1)   # 1 - just int!

# tuple() handles this
t = tuple([1])  # (1,)
```

### Very Large Tuple

```python
# O(n) - allocates large tuple
huge_range = range(10**9)
t = tuple(huge_range)  # O(10^9) - very slow and memory-intensive!

# Better - keep as range
for item in huge_range:  # No allocation
    process(item)
```

### Nested Tuples

```python
# O(n) - contains other tuples
inner1 = (1, 2)
inner2 = (3, 4)
outer = (inner1, inner2)  # ((1, 2), (3, 4))

# Shallow copy
copied = tuple(outer)  # Still contains references to inner tuples
```

### Immutability

```python
# O(1) - immutable, cannot modify
t = (1, 2, 3)

# Cannot change
# t[0] = 10  # TypeError - tuple doesn't support item assignment
# t.append(4)  # AttributeError - no append method

# But contents can be mutable
t_with_list = ([1, 2], [3, 4])
t_with_list[0][0] = 999  # OK - modifies inner list
```

## Tuple Unpacking

```python
# O(1) - unpacking is very fast
t = (1, 2, 3)

# Single assignment
a, b, c = t  # O(1)

# With unpacking operator
x, *rest = t  # O(1)

# Extended unpacking
a, *middle, z = t  # O(1)
```

## Best Practices

✅ **Do**:

- Use tuple() to convert iterables to immutable
- Use tuples for hashable sequences (dict keys, set members)
- Use tuple unpacking for readability
- Use tuple literal (1, 2, 3) for constants

❌ **Avoid**:

- Using tuple() when you need to modify items (use list)
- Creating tuples from very large iterables (memory)
- Forgetting trailing comma for single-item tuple: (1) vs (1,)
- Assuming tuple is always faster (usually similar to list)

## Related Functions

- **[list()](list_func.md)** - Convert to list
- **[set()](set_func.md)** - Convert to set
- **[dict()](dict_func.md)** - Convert to dictionary
- **[zip()](zip.md)** - Create tuples from iterables

## Version Notes

- **Python 2.x**: tuple() available, creates tuples
- **Python 3.x**: Same behavior
- **All versions**: Immutable, hashable sequences
