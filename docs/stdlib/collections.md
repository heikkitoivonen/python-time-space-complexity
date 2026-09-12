# Collections Module Complexity

The `collections` module provides specialized data structures optimized for specific use cases.

## deque

See [deque](deque.md) for operations, complexity and examples.

## DefaultDict

See [defaultdict](defaultdict.md) for operations, complexity and examples.

## Counter

See [Counter](counter.md) for operations, complexity and examples.

## NamedTuple

See [namedtuple](namedtuple.md) for operations, complexity and examples.

## OrderedDict

See [OrderedDict](ordereddict.md) for operations, complexity and examples.

## ChainMap

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
