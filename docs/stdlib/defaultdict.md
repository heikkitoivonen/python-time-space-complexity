# defaultdict - Dictionary with Default Values Complexity

The `defaultdict` class from `collections` provides a dictionary that returns a default value for missing keys instead of raising KeyError.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `defaultdict()` | O(1) | O(1) | Create dict |
| Lookup existing key | O(1) avg | O(1) | O(n) worst case due to hash collisions |
| Lookup missing key | O(1) avg | O(1) | Creates default; O(n) worst case |
| Insert | O(1) avg | O(1) | O(n) worst case due to hash collisions |
| Delete | O(1) avg | O(1) | O(n) worst case due to hash collisions |

## Basic Usage

```python
from collections import defaultdict

# Create with default factory - O(1)
dd = defaultdict(list)  # O(1)

# Missing key returns default - O(1)
dd['key'].append(1)  # O(1) - creates empty list

# Regular dict behavior for existing keys - O(1)
dd['key'].append(2)  # O(1) - appends to list

# Access - O(1)
print(dd['key'])  # [1, 2]
print(dd['missing'])  # []
```

## Default Factories

### Common Factories

```python
from collections import defaultdict

# Default to list - O(1)
dd_list = defaultdict(list)
dd_list['items'].append('a')  # Creates []

# Default to int - O(1)
dd_int = defaultdict(int)
dd_int['count'] += 1  # Creates 0, then += 1

# Default to set - O(1)
dd_set = defaultdict(set)
dd_set['members'].add('alice')  # Creates set()

# Default to dict - O(1)
dd_dict = defaultdict(dict)
dd_dict['nested']['key'] = 'value'  # Creates {}
```

### Custom Factories

```python
from collections import defaultdict

# Lambda function - O(1)
dd_lambda = defaultdict(lambda: 'default')
print(dd_lambda['missing'])  # 'default'

# Callable returning list - O(1)
def default_list():
    return []

dd_custom = defaultdict(default_list)
dd_custom['items'].append(1)

# Callable with arguments (use lambda) - O(1)
dd_tuple = defaultdict(lambda: (0, 0))
print(dd_tuple['point'])  # (0, 0)
```

## Common Patterns

### Counting Items

```python
from collections import defaultdict

# Count occurrences - O(n)
words = ['apple', 'banana', 'apple', 'cherry', 'banana', 'apple']

word_count = defaultdict(int)
for word in words:  # O(n)
    word_count[word] += 1  # O(1)

print(word_count)  # {'apple': 3, 'banana': 2, 'cherry': 1}

# Compare with regular dict - more code
word_count_dict = {}
for word in words:  # O(n)
    if word in word_count_dict:  # O(1)
        word_count_dict[word] += 1
    else:
        word_count_dict[word] = 1
```

### Grouping Items

```python
from collections import defaultdict

# Group by key - O(n)
students = [
    ('Alice', 'A'),
    ('Bob', 'B'),
    ('Charlie', 'A'),
    ('David', 'C'),
]

grades = defaultdict(list)
for name, grade in students:  # O(n)
    grades[grade].append(name)  # O(1)

print(grades)  # {'A': ['Alice', 'Charlie'], 'B': ['Bob'], 'C': ['David']}
```

### Building Graphs

```python
from collections import defaultdict

# Build adjacency list - O(E)
edges = [('A', 'B'), ('B', 'C'), ('A', 'C')]

graph = defaultdict(list)
for u, v in edges:  # O(E)
    graph[u].append(v)  # O(1)

print(graph)  # {'A': ['B', 'C'], 'B': ['C']}
```

### Inverse Mapping

```python
from collections import defaultdict

# One-to-many mapping - O(n)
data = {'a': 1, 'b': 2, 'c': 1, 'd': 3, 'e': 2}

inverse = defaultdict(list)
for key, value in data.items():  # O(n)
    inverse[value].append(key)  # O(1)

print(inverse)  # {1: ['a', 'c'], 2: ['b', 'e'], 3: ['d']}
```

## Compared to Regular Dict

```python
from collections import defaultdict

# Regular dict - KeyError on missing key
d = {'a': 1}
# d['missing']  # KeyError!

# defaultdict - returns default
dd = defaultdict(int)
dd['missing']  # Returns 0

# Or handle in regular dict
value = d.get('missing', 0)  # Same result, more verbose
```

## Counter vs defaultdict(int)

```python
from collections import defaultdict, Counter

# defaultdict(int) - O(n)
dd = defaultdict(int)
for x in [1, 2, 2, 3, 3, 3]:  # O(n)
    dd[x] += 1
# Result: {1: 1, 2: 2, 3: 3}

# Counter - O(n) but with more methods
c = Counter([1, 2, 2, 3, 3, 3])  # O(n)
# Same result, but Counter has most_common(), etc.

# Use Counter for frequency counting
# Use defaultdict(int) for general counting
```

## When to Use defaultdict

### Good For:
- Counting occurrences
- Grouping items
- Building graphs/networks
- Nested structures
- Avoiding KeyError checks

### Not Good For:
- One-to-one mappings (use dict)
- Frequency counting only (use Counter)
- When default creation has side effects
- Performance critical code (dict is slightly faster)

## Performance Comparison

```python
from collections import defaultdict
import time

# Regular dict with get - O(n)
d = {}
start = time.time()
for i in range(1000000):
    d[i % 1000] = d.get(i % 1000, 0) + 1  # O(1)
dict_time = time.time() - start

# defaultdict - O(n)
dd = defaultdict(int)
start = time.time()
for i in range(1000000):
    dd[i % 1000] += 1  # O(1)
dd_time = time.time() - start

# defaultdict is typically faster due to C optimization
```

## Version Notes

- **Python 2.x**: Available in collections
- **Python 3.x**: Same functionality
- **All versions**: O(1) average dict operations

## Related Modules

- **[dict](../builtins/dict.md)** - Regular dictionary
- **[Counter](counter.md)** - Specialized counter
- **[OrderedDict](ordereddict.md)** - Insertion-order dict

## Best Practices

✅ **Do**:

- Use for grouping/counting
- Use for nested structures
- Use with appropriate default factory
- Provide default factory explicitly

❌ **Avoid**:

- Complex default factory logic
- Side effects in default factory
- When regular dict with get() is clearer
- When Counter is more appropriate
