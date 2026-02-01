# Dictionary Operations Complexity

The `dict` type is a mutable mapping that stores key-value pairs. It's implemented as a hash table in CPython.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Direct count |
| `access[key]` | O(1) avg, O(n) worst | O(1) | Hash lookup; worst case with collisions |
| `set[key] = value` | O(1) amortized | O(1) | Hash insertion; may trigger resize |
| `del[key]` | O(1) avg, O(n) worst | O(1) | Hash deletion |
| `key in dict` | O(1) avg, O(n) worst | O(1) | Hash lookup |
| `get(key)` | O(1) avg, O(n) worst | O(1) | Hash lookup |
| `pop(key)` | O(1) avg, O(n) worst | O(1) | Hash deletion |
| `clear()` | O(n) | O(1) | Must deallocate all entries |
| `keys()` | O(1) | O(1) | View object (O(n) to iterate) |
| `values()` | O(1) | O(1) | View object (O(n) to iterate) |
| `items()` | O(1) | O(1) | View object (O(n) to iterate) |
| `copy()` | O(n) | O(n) | Shallow copy of all pairs |
| `update(other)` | O(k) | O(1) | k = len(other), amortized; modifies in place |
| `setdefault(key, val)` | O(1) avg | O(1) | Hash lookup + insert |
| `fromkeys(keys)` | O(k) | O(k) | k = len(keys) |
| `popitem()` | O(1) | O(1) | Remove last inserted pair (LIFO since 3.7) |

*Note: O(1) average case assumes good hash distribution. Worst case O(n) occurs with pathological hash collisions, which is rare with Python's randomized hashing.*

## Implementation Details

### Hash Table Structure

CPython uses a hash table with:

- **Hash function**: SipHash13 for `str`/`bytes` (default since Python 3.11); other types use type-specific hashing
- **Collision handling**: Open addressing with probing
- **Growth factor**: ~2-4x when load factor exceeded
- **Python 3.6+**: Insertion order preserved (compact dict design)

### Hash Collision Impact

```python
# Best case: perfect hashing (O(1))
d = {i: i for i in range(1000)}
value = d[500]  # O(1)

# Worst case: hash collisions (degraded, but very rare)
# CPython mitigates this with randomized hashing
```

### Insertion Order Guarantee

```python
# Python 3.6+ guarantees insertion order
d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
# Iteration order: a, b, c (guaranteed)
```

## Version Notes

| Version | Change |
|---------|--------|
| Python 3.6+ | Insertion order preserved |
| Python 3.9+ | Dict merge & update operators (`\|`, `\|=`) |
| Python 3.10+ | Pattern matching with dicts |
| Python 3.11+ | 23% smaller when all keys are Unicode strings |

## Implementation Comparison

### CPython
Standard hash table implementation, very optimized.

### PyPy
Similar complexity, JIT compilation may provide further optimization.

### Jython
Uses underlying Java HashMap, same O(1) characteristics.

### IronPython
Similar hash table implementation as CPython.

## Best Practices

✅ **Do**:

- Use dict for key-value lookups
- Leverage dict comprehensions: `{k: v for k, v in items}`
- Use `setdefault()` for conditional insertion

❌ **Avoid**:

- Don't rely on order in Python < 3.6
- Unhashable types as keys (lists, dicts, sets)
- Extremely large dicts with poor hash functions

## Hash Function Considerations

```python
# Hashable types work as keys
d = {
    (1, 2): 'tuple_key',
    'string': 'str_key',
    42: 'int_key',
    frozenset([1, 2]): 'frozen_key'
}

# Unhashable types will fail
# d[[1, 2]] = 'fails'  # TypeError
# d[{1, 2}] = 'fails'  # TypeError
```

## Related Types

- **[Set](set.md)** - Unordered unique items
- **[Defaultdict](../stdlib/collections.md#defaultdict)** - Auto-default values
- **[OrderedDict](../stdlib/collections.md#ordereddict)** - Explicit ordering (pre-3.6)
- **[ChainMap](../stdlib/collections.md#chainmap)** - Multiple dict views

## Further Reading

- [CPython Internals: dict](https://zpoint.github.io/CPython-Internals/BasicObject/dict/dict.html) -
  Deep dive into CPython's dict implementation
