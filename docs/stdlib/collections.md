# Collections Module Complexity

The `collections` module provides specialized data structures optimized for specific use cases.

## Deque (Double-Ended Queue)

```python
from collections import deque
```

### Time Complexity

| Operation | Time |
|-----------|------|
| `append(x)` | O(1) |
| `appendleft(x)` | O(1) |
| `pop()` | O(1) |
| `popleft()` | O(1) |
| `access[i]` | O(n) | <!-- VERIFY: deque indexing may be O(n) for middle elements due to block structure -->
| `extend(iterable)` | O(k) for k items |
| `rotate(n)` | O(n) or O(k) for small rotations |
| `clear()` | O(n) |
| `in` (membership) | O(n) |

### Space Complexity

- Storage: O(n) for n items
- Operations: O(1) for append/pop operations

### Use Cases

```python
# Process items from both ends - very efficient
queue = deque([1, 2, 3])
queue.appendleft(0)  # O(1) - add to front
queue.pop()  # O(1) - remove from back

# Much faster than list for this pattern:
# list.insert(0, x) is O(n)
# list.pop(0) is O(n)
```

## DefaultDict

```python
from collections import defaultdict
```

### Time Complexity

Same as `dict`:

| Operation | Time |
|-----------|------|
| `d[key]` | O(1) avg | Returns default if missing; O(n) worst case due to hash collisions |
| `d[key] = value` | O(1) avg | O(n) worst case due to hash collisions |
| `del d[key]` | O(1) avg | O(n) worst case due to hash collisions |
| Other dict ops | Same as dict |

### Space Complexity

- O(n) for n key-value pairs
- Default factory called only when key accessed

### Use Cases

```python
# Avoid: Manual checking
from collections import defaultdict

data = defaultdict(list)
data['key'].append('value')  # Key auto-created as empty list

# Avoid: Clunky dict.get()
count = d.get('key', 0)
count += 1

# Better: defaultdict with int
from collections import defaultdict
count = defaultdict(int)
count['key'] += 1
```

## Counter

```python
from collections import Counter
```

### Time Complexity

| Operation | Time | Notes |
|-----------|------|-------|
| `Counter(iterable)` | O(n) | n = iterable length |
| `c[item]` | O(1) avg | Returns 0 if missing; O(n) worst case due to hash collisions |
| `c.most_common(k)` | O(n log k) | Heap-based, k = count |
| `c.update(iterable)` | O(n) | n = iterable length |
| `c + c2` | O(n) | Combines counters |
| `c - c2` | O(n) | Keeps positive counts |

### Use Cases

```python
from collections import Counter

# Count items
words = ['apple', 'banana', 'apple', 'cherry', 'apple']
c = Counter(words)
# Counter({'apple': 3, 'banana': 1, 'cherry': 1})

# Most common items
top_3 = c.most_common(3)  # [('apple', 3), ('banana', 1), ('cherry', 1)]

# Arithmetic
c1 = Counter('aab')
c2 = Counter('abc')
c1 + c2  # Counter({'a': 3, 'b': 2, 'c': 1})
```

## NamedTuple

```python
from collections import namedtuple
```

### Time Complexity

Same as tuple for all operations:

| Operation | Time |
|-----------|------|
| Creation | O(1) |
| Access by index | O(1) |
| Access by name | O(1) |
| Iteration | O(n) |

### Use Cases

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])
p = Point(11, y=22)

# Better than plain tuple
print(p.x)  # More readable than p[0]

# Create from dict
d = {'x': 1, 'y': 2}
p = Point(**d)

# Replace values
p2 = p._replace(x=5)
```

## OrderedDict

```python
from collections import OrderedDict
```

### Time Complexity

| Operation | Time |
|-----------|------|
| Same as dict | O(1) |
| Order preservation | Guaranteed |

### Notes

- **Python 3.6+**: Regular `dict` preserves order, so `OrderedDict` mainly useful for:
  - Compatibility with older code
  - `move_to_end()` method for reordering
  - Explicit intent in code

```python
from collections import OrderedDict

# Useful method: move_to_end()
od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
od.move_to_end('a')  # O(1) - moves 'a' to end
```

## ChainMap

```python
from collections import ChainMap
```

### Time Complexity

| Operation | Time | Notes |
|-----------|------|-------|
| `access[key]` | O(n) | n = number of maps; searches until found |
| `set[key]` | O(1) avg | Sets in first map; O(m) worst case where m = first map size |
| `del[key]` | O(1) avg | Deletes from first map; O(m) worst case where m = first map size |
| `len()` | O(n) | Must check all maps |
| `in` | O(n) | Checks all maps |

### Use Cases

```python
from collections import ChainMap

# Layer multiple dicts
defaults = {'timeout': 30, 'retries': 3}
user_config = {'timeout': 60}

config = ChainMap(user_config, defaults)
print(config['timeout'])  # 60 (from user_config)
print(config['retries'])  # 3 (from defaults)

# View layered configuration without merging
```

## Performance Comparison

| Operation | dict | defaultdict | Counter | OrderedDict |
|-----------|------|-------------|---------|------------|
| `d[key]` | O(1) | O(1) | O(1) | O(1) |
| `d[key] = value` | O(1) | O(1) | O(1) | O(1) |
| Special methods | - | `__missing__` | `most_common()` | `move_to_end()` |
| Memory | Baseline | +small | +counter storage | +order tracking |

## Related Documentation

- [Built-in Dict](../builtins/dict.md)
- [Built-in Tuple](../builtins/tuple.md)
- [Heapq Module](heapq.md)
