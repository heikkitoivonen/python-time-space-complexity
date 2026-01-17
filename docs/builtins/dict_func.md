# dict() Function Complexity

The `dict()` function creates dictionaries from various sources.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Empty dict | O(1) | O(1) | dict() |
| From keyword arguments | O(n) | O(n) | n = number of kwargs |
| From list of pairs | O(n) | O(n) | n = number of pairs |
| From another dict | O(n) | O(n) | n = dict size |
| From iterable of pairs | O(n) | O(n) | n = number of pairs |

## Basic Usage

### Create Empty Dictionary

```python
# O(1)
d = dict()  # {}
```

### From Keyword Arguments

```python
# O(n) - where n = number of kwargs
d = dict(a=1, b=2, c=3)
# {'a': 1, 'b': 2, 'c': 3}

d = dict(name="Alice", age=30, city="NYC")
# {'name': 'Alice', 'age': 30, 'city': 'NYC'}
```

### From List of Pairs

```python
# O(n) - where n = number of pairs
d = dict([("a", 1), ("b", 2), ("c", 3)])
# {'a': 1, 'b': 2, 'c': 3}

d = dict([("x", 10), ("y", 20)])
# {'x': 10, 'y': 20}
```

### From Another Dictionary

```python
# O(n) - where n = dict size
original = {"a": 1, "b": 2}
copy = dict(original)  # {'a': 1, 'b': 2} - shallow copy

# Copy entire dict
d = dict({"x": 10, "y": 20})
# {'x': 10, 'y': 20}
```

### From zip() of Keys and Values

```python
# O(n) - combine two iterables
keys = ["a", "b", "c"]
values = [1, 2, 3]

d = dict(zip(keys, values))
# {'a': 1, 'b': 2, 'c': 3}
```

## Complexity Details

### Hashing and Insertion

```python
# O(n) - insert n key-value pairs
# Each pair requires:
# 1. Hash the key - O(1) average
# 2. Store the pair - O(1) average
# Total: O(n)

pairs = [("a", 1), ("b", 2), ("c", 3), ("d", 4)]
d = dict(pairs)  # O(4) - hash and store each pair
```

### Collision Handling

```python
# O(n) - collisions don't affect overall complexity
# Even with hash collisions, dict() is still O(n)

# worst case - all keys hash to same value
# Still O(n) due to Python's implementation

pairs = [(i, i*10) for i in range(1000)]
d = dict(pairs)  # O(1000) - even with collisions
```

### Keyword Arguments

```python
# O(n) - where n = number of kwargs
# Each keyword becomes a key-value pair

d = dict(a=1, b=2, c=3, d=4, e=5)  # O(5)

# More kwargs = slower
many = dict(**{f"key_{i}": i for i in range(100)})  # O(100)
```

## Common Patterns

### Convert Pairs to Dictionary

```python
# O(n) - general conversion
pairs = [("Alice", 25), ("Bob", 30), ("Charlie", 35)]
ages = dict(pairs)
# {'Alice': 25, 'Bob': 30, 'Charlie': 35}

# From enumerate
items = ["a", "b", "c"]
indexed = dict(enumerate(items))
# {0: 'a', 1: 'b', 2: 'c'}
```

### Combine Lists into Dictionary

```python
# O(n) - using zip
names = ["Alice", "Bob", "Charlie"]
scores = [85, 92, 78]

results = dict(zip(names, scores))
# {'Alice': 85, 'Bob': 92, 'Charlie': 78}
```

### Dictionary Copying

```python
# All O(n) - shallow copy
original = {"a": 1, "b": 2}

copy1 = dict(original)          # O(n)
copy2 = original.copy()         # O(n) - same
copy3 = {**original}            # O(n) - unpacking

# All create shallow copies
```

### Merge Dictionaries

```python
# O(n + m) - where n, m = dict sizes
dict1 = {"a": 1, "b": 2}
dict2 = {"c": 3, "d": 4}

merged = dict(**dict1, **dict2)  # O(n+m)
# {'a': 1, 'b': 2, 'c': 3, 'd': 4}

# Or using update - also O(n+m)
merged = dict(dict1)
merged.update(dict2)
```

## Performance Patterns

### Keyword Arguments vs Pairs

```python
# Both O(n), but different syntax

# Keyword arguments - limited to valid identifiers
d1 = dict(a=1, b=2, c=3)  # O(3)

# List of pairs - any hashable key
d2 = dict([("a", 1), ("b", 2), ("c", 3)])  # O(3)

# Speed similar, but pairs allow any key
d3 = dict([(1, "a"), (2, "b"), (None, "c")])  # O(3)
```

### From Multiple Sources

```python
# O(n) - combine kwargs and pairs
pairs = [("x", 10), ("y", 20)]
d = dict(pairs, z=30)  # O(3) - combine both
# {'x': 10, 'y': 20, 'z': 30}
```

### Batch Creation

```python
# O(n) - create all at once is faster than gradual

# Fast - O(n)
data = dict([(f"key_{i}", i) for i in range(100)])

# Slower - O(n) with overhead
data = {}
for i in range(100):
    data[f"key_{i}"] = i

# Preferably use dict() or comprehension
data = {f"key_{i}": i for i in range(100)}  # O(n)
```

## Practical Examples

### Parse Configuration

```python
# O(n) - convert pairs to config dict
config_pairs = [
    ("timeout", 30),
    ("retries", 3),
    ("debug", True),
]

config = dict(config_pairs)
# {'timeout': 30, 'retries': 3, 'debug': True}
```

### Map Names to Values

```python
# O(n) - create mapping
names = ["Alice", "Bob", "Charlie"]
values = [1, 2, 3]

mapping = dict(zip(names, values))
# {'Alice': 1, 'Bob': 2, 'Charlie': 3}

# Useful for CSV data
headers = ["name", "age", "city"]
row = ["Alice", 30, "NYC"]
record = dict(zip(headers, row))
# {'name': 'Alice', 'age': 30, 'city': 'NYC'}
```

### Create Lookup Table

```python
# O(n) - build lookup from data
items = ["apple", "banana", "cherry"]
lookup = dict(enumerate(items))
# {0: 'apple', 1: 'banana', 2: 'cherry'}

# Or reverse
reverse_lookup = {v: k for k, v in lookup.items()}
# {'apple': 0, 'banana': 1, 'cherry': 2}
```

### Initialize with Defaults

```python
# O(n) - create with initial values
keys = ["a", "b", "c", "d"]
initial_value = 0

# Using dict comprehension
defaults = {k: initial_value for k in keys}  # O(n)

# Or with dict() - but requires pairs
defaults = dict((k, initial_value) for k in keys)  # O(n)

# defaultdict is O(1) for access, but setup is similar
from collections import defaultdict
defaults = defaultdict(int)  # O(1) setup, O(1) per access
```

## Edge Cases

### Empty Dictionary

```python
# O(1)
d = dict()       # {}
d = dict([])     # {}
d = dict({})     # {}
```

### Single Pair

```python
# O(1)
d = dict([("a", 1)])   # {'a': 1}
d = dict(a=1)          # {'a': 1}
```

### Duplicate Keys

```python
# O(n) - last value wins
pairs = [("a", 1), ("a", 2), ("a", 3)]
d = dict(pairs)  # {'a': 3} - last value

# Same with kwargs
d = dict(a=1, b=2, a=3)  # {'a': 3, 'b': 2}
```

### Non-hashable Keys

```python
# O(n) - error for non-hashable keys
try:
    pairs = [([1, 2], "value")]  # Lists not hashable
    d = dict(pairs)  # TypeError
except TypeError:
    pass
```

### Large Dictionaries

```python
# O(n) - scales linearly
pairs = [(i, i*10) for i in range(10**6)]
d = dict(pairs)  # O(10^6) - creates large dict
```

## Dictionary Comprehension Alternative

```python
# All O(n), but different syntax

# Using dict()
d1 = dict([("a", 1), ("b", 2), ("c", 3)])

# Using dict comprehension - often preferred
d2 = {k: v for k, v in [("a", 1), ("b", 2), ("c", 3)]}

# Using dict() with zip
keys = ["a", "b", "c"]
values = [1, 2, 3]
d3 = dict(zip(keys, values))

# All O(n), comprehension often cleaner
```

## Shallow vs Deep Copy

```python
# dict() creates shallow copy
inner = {"x": 1}
outer = {"a": inner}

copied = dict(outer)
copied["a"]["x"] = 999  # Affects original!
# outer['a']['x'] is now 999

# For deep copy
import copy
deep = copy.deepcopy(outer)  # Doesn't affect original
```

## Best Practices

✅ **Do**:
- Use dict comprehensions for clarity: `{k: v for ...}`
- Use dict() with zip() for pairs: `dict(zip(keys, values))`
- Specify all data upfront if possible
- Use keyword arguments for simple dicts

❌ **Avoid**:
- Building dicts gradually with assignments
- Assuming dict() is faster than `{}` (similar)
- Confusing shallow and deep copies
- Using non-hashable keys

## Related Functions

- **[list()](list_func.md)** - Convert to list
- **[set()](builtins/index.md)** - Convert to set
- **[zip()](zip.md)** - Pair up iterables
- **[dict.fromkeys()](dict.md)** - Create dict with default values

## Version Notes

- **Python 2.x**: dict() works with iterables
- **Python 3.x**: Preserves insertion order (3.7+)
- **All versions**: Shallow copy by default
