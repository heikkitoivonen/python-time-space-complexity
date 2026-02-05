# Collections Module Complexity

The `collections` module provides specialized data structures optimized for specific use cases.

## deque

### Deque (Double-Ended Queue)

```python
from collections import deque
```

### Time Complexity

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `append(x)` | O(1) | O(1) | Add to right end |
| `appendleft(x)` | O(1) | O(1) | Add to left end |
| `pop()` | O(1) | O(1) | Remove from right end |
| `popleft()` | O(1) | O(1) | Remove from left end |
| `access[i]` | O(1) ends, O(n) middle | O(1) | Ends (d[0], d[-1]) are O(1); middle elements O(n) due to block structure |
| `extend(iterable)` | O(k) | O(k) | k = iterable length |
| `extendleft(iterable)` | O(k) | O(k) | k = iterable length; note: reverses order |
| `rotate(n)` | O(k) | O(1) | k = min(n, len(d) - n) |
| `clear()` | O(n) | O(1) | Remove all elements |
| `copy()` | O(n) | O(n) | Shallow copy |
| `count(x)` | O(n) | O(1) | Count occurrences of x |
| `index(x)` | O(n) | O(1) | Find first occurrence of x |
| `insert(i, x)` | O(n) | O(1) | Insert x at position i |
| `remove(x)` | O(n) | O(1) | Remove first occurrence of x |
| `reverse()` | O(n) | O(1) | Reverse in place |
| `in` (membership) | O(n) | O(1) | Linear search |

### Attributes

| Attribute | Notes |
|-----------|-------|
| `maxlen` | Maximum size (None if unbounded); read-only |

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

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `d[key]` | O(1) avg | O(1) | Returns default if missing; O(n) worst case due to hash collisions |
| `d[key] = value` | O(1) avg | O(1) | O(n) worst case due to hash collisions |
| `del d[key]` | O(1) avg | O(1) | O(n) worst case due to hash collisions |
| `copy()` | O(n) | O(n) | Shallow copy |
| Other dict ops | Same as dict | - | |

### Attributes

| Attribute | Notes |
|-----------|-------|
| `default_factory` | Callable that provides default values; can be None |

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

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Counter(iterable)` | O(n) | O(k) | n = iterable length, k = unique items |
| `c[item]` | O(1) avg | O(1) | Returns 0 if missing; O(n) worst case due to hash collisions |
| `c.most_common(k)` | O(n log k) | O(k) | Heap-based; O(n log n) if k is None |
| `c.update(iterable)` | O(n) | O(k) | n = iterable length |
| `c.subtract(iterable)` | O(n) | O(1) | Subtract counts; keeps negative values |
| `c.total()` | O(n) | O(1) | Sum of all counts (Python 3.10+) |
| `c.elements()` | O(1) init, O(total) iter | O(1) | Iterator over elements repeating each count times |
| `c.copy()` | O(n) | O(n) | Shallow copy |
| `c.fromkeys(iterable)` | N/A | - | Not useful for Counter; inherited from dict |
| `c + c2` | O(n) | O(n) | Combines counters; keeps positive counts |
| `c - c2` | O(n) | O(n) | Subtracts; keeps positive counts |

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

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Creation | O(1) | O(1) | Fixed number of fields |
| Access by index | O(1) | O(1) | Same as tuple |
| Access by name | O(1) | O(1) | Same as tuple |
| Iteration | O(n) | O(1) | n = number of fields |

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

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Same as dict | O(1) | O(1) | All dict operations |
| `move_to_end(key)` | O(1) | O(1) | Move key to end |

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

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `access[key]` | O(n) | O(1) | n = number of maps; searches until found |
| `set[key]` | O(1) avg | O(1) | Sets in first map; O(m) worst case where m = first map size |
| `del[key]` | O(1) avg | O(1) | Deletes from first map; O(m) worst case where m = first map size |
| `len()` | O(N) | O(N) | N = total keys across all maps; builds set union internally |
| `in` | O(n) | O(1) | Checks all maps |

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

## UserDict

`UserDict` wraps a standard dict with a user-customizable class.

### Time Complexity

Same as `dict` for most operations:

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `d[key]` | O(1) avg | O(1) | O(n) worst case due to hash collisions |
| `d[key] = value` | O(1) avg | O(1) | O(n) worst case |
| `del d[key]` | O(1) avg | O(1) | O(n) worst case |
| Iteration | O(n) | O(1) | n = number of items |

## UserList

`UserList` wraps a standard list with a user-customizable class.

### Time Complexity

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Indexing | O(1) | O(1) | Access by index |
| Append | O(1) amortized | O(1) | O(n) worst case on resize |
| Insert/Delete | O(n) | O(1) | Shift elements |
| Iteration | O(n) | O(1) | n = list length |

## UserString

`UserString` wraps a standard string with a user-customizable class.

### Time Complexity

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Indexing | O(1) | O(1) | Access by index |
| Concatenation | O(n) | O(n) | n = total length |
| Slicing | O(k) | O(k) | k = slice length |
| Iteration | O(n) | O(1) | n = length |

## Related Documentation

- [Built-in Dict](../builtins/dict.md)
- [Built-in Tuple](../builtins/tuple.md)
- [Heapq Module](heapq.md)
