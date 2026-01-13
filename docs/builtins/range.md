# Range Operations Complexity

The `range` type is an immutable sequence of numbers used for iteration. It generates values lazily without storing all numbers in memory.

## Time Complexity

| Operation | Time | Notes |
|-----------|------|-------|
| `range(stop)` | O(1) | Create range object |
| `range(start, stop)` | O(1) | Create range object |
| `range(start, stop, step)` | O(1) | Create range object |
| `len()` | O(1) | Calculated, not stored |
| `access[i]` | O(1) | Direct calculation |
| `in` (membership) | O(1) | Math check, not scan |
| `index(value)` | O(1) | Solve equation |
| `count(value)` | O(1) | Single check |
| `iteration` | O(n) | n = number of items |
| `copy()` | O(1) | Shallow copy |
| `reversed()` | O(1) | Iterator, not materialized |
| `list(range(...))` | O(n) | Convert to list |

## Space Complexity

| Operation | Space |
|-----------|-------|
| Range object | O(1) | Fixed overhead |
| Iteration | O(1) | No buffering |
| `list()` conversion | O(n) | Creates list |
| `reversed()` iterator | O(1) | No materialization |

## Implementation Details

### Lazy Evaluation

```python
# Range is lazy - no values stored
r = range(1000000)  # O(1) - very fast

# Size is O(1)
len(r)              # O(1) - calculated

# Iteration is still O(n) for each item
for i in r:         # O(n) total
    print(i)
```

### Efficient Membership Testing

```python
# Membership check is O(1) - solves equation
r = range(10, 100, 5)
50 in r             # O(1) - True (10 + 5*k = 50)
51 in r             # O(1) - False (no integer k works)

# Much faster than list
lst = list(range(10, 100, 5))
50 in lst           # O(n) - linear search
```

### Direct Access

```python
# Access any element in O(1)
r = range(1000000)
r[500000]           # O(1) - calculated: start + step*index

# Using formula: value = start + step * index
r = range(10, 100, 5)
r[0]                # 10
r[5]                # 35 (10 + 5*5)
r[10]               # 60 (10 + 5*10)
```

## Common Use Cases

### Iteration

```python
# Efficient iteration
for i in range(1000000):  # O(n) iteration, O(1) per item
    process(i)

# More efficient than
for i in list(range(1000000)):  # Uses O(n) memory
    process(i)
```

### Loop Counting

```python
# Standard range for loops
for i in range(10):
    print(i)  # 0 to 9

# With start and step
for i in range(10, 100, 5):
    print(i)  # 10, 15, 20, ..., 95

# Reverse iteration
for i in range(100, 10, -5):
    print(i)  # 100, 95, 90, ..., 15
```

### Indexing

```python
# Works with enumerate
for idx, val in enumerate(items):
    print(idx, val)

# Or explicit range
for i in range(len(items)):
    print(i, items[i])
```

## Performance Characteristics

### Range vs List

```python
import sys

# Range: O(1) memory
r = range(1000000)
print(sys.getsizeof(r))  # ~48 bytes - fixed size!

# List: O(n) memory
lst = list(range(1000000))
print(sys.getsizeof(lst))  # ~8MB+ - proportional to size
```

### Membership Testing

```python
# Range: O(1)
r = range(10000000)
9999999 in r  # O(1) - instant

# List: O(n)
lst = list(range(10000000))
9999999 in lst  # O(n) - might take milliseconds
```

### Iteration

```python
# Both O(n) for full iteration
r = range(1000000)
for i in r:  # O(1) per item, O(n) total
    pass

# But range doesn't use O(n) memory
lst = list(range(1000000))
for i in lst:  # O(1) per item, O(n) total, but O(n) memory
    pass
```

## Edge Cases

### Empty Range

```python
r = range(0)     # Empty
len(r)           # 0
list(r)          # []

r = range(5, 5)  # Empty
len(r)           # 0

r = range(10, 5)  # Empty (reversed with positive step)
len(r)           # 0
```

### Negative Steps

```python
r = range(10, 0, -1)
list(r)          # [10, 9, 8, ..., 1]

r = range(10, 0, -2)
list(r)          # [10, 8, 6, 4, 2]
```

### Large Ranges

```python
# Safe - never materializes all values
r = range(10**18)  # Huge range, still O(1) memory
len(r)             # 10^18
r[0]               # 0
r[999999999999999] # 999999999999999
```

## Version Notes

- **All Python 3.x**: Core complexity unchanged
- **Python 2.x**: Had `xrange` for lazy evaluation (now built-in)

## Related Operations

- **[List](list.md)** - For materialized sequences
- **Iteration** - For looping
- **Enumerate** - For indexed iteration
