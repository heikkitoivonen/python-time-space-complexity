# List Operations Complexity

The `list` type is a mutable, ordered sequence. It's implemented as a dynamic array in CPython.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | Direct lookup |
| `access[i]` | O(1) | O(1) | Direct indexing |
| `append(x)` | O(1) amortized | O(1) amortized | May resize; worst case O(n) when reallocation needed |
| `insert(0, x)` | O(n) | O(1) | Must shift all elements |
| `insert(i, x)` | O(n-i) | O(1) | Shift elements from index i |
| `remove(x)` | O(n) | O(1) | Must search and shift |
| `pop()` | O(1) | O(1) | Remove last element |
| `pop(0)` | O(n) | O(1) | Shift remaining elements |
| `pop(i)` | O(n-i) | O(1) | Shift elements after i |
| `clear()` | O(n) | O(1) | Deallocate memory |
| `index(x)` | O(n) | O(1) | Linear search |
| `count(x)` | O(n) | O(1) | Linear scan |
| `sort()` | O(n log n) avg/worst, O(n) best | O(n) | Timsort/Powersort; adaptive for partially sorted data |
| `reverse()` | O(n) | O(1) | In-place reversal |
| `copy()` | O(n) | O(n) | Shallow copy |
| `extend(iterable)` | O(k) | O(k) | k = length of iterable; may trigger O(n) resize |
| `in` (membership) | O(n) | O(1) | Linear search |
| `x + y` (concatenation) | O(m+n) | O(m+n) | m, n are lengths |
| `[::2]` (slicing) | O(k) | O(k) | k = slice length |

## Implementation Details

### Dynamic Array Resizing

CPython's list uses a growth factor strategy:

```
If size >= capacity:
    new_capacity = (newsize + newsize // 8 + 6) & ~3  # Aligned to multiple of 4
```

This means:

- Append is O(1) amortized
- You don't resize on every append
- Overallocation reduces resize frequency

### Append Performance

```python
# O(1) amortized
lst = []
for i in range(1000000):
    lst.append(i)  # Resizes ~log(n) times
```

### Insert Performance

```python
# O(n) - must shift all elements after insertion point
lst = [0] * 1000000
lst.insert(0, -1)  # Shifts 1,000,000 elements!
```

## Version Notes

- **Python 3.8+**: Current behavior stable
- **Python 3.11+**: `append()` ~15% faster, list comprehensions 20-30% faster
- **Python 3.12+**: Comprehensions inlined (up to 2x faster)
- **All versions**: Core complexity unchanged since early Python 3.x

## Implementation Comparison

### CPython
Standard reference implementation with dynamic array.

### PyPy
Same complexity characteristics due to JIT optimization.

### Jython
Similar, but may have different resize factors based on Java arrays.

## Best Practices

✅ **Do**:

- Use `append()` for adding items
- Use `extend()` for multiple items
- Append then reverse if you need prepending

❌ **Avoid**:

- `insert(0, x)` for frequent operations - use `collections.deque` instead
- Repeated `pop(0)` - use `deque.popleft()`
- Building large lists using concatenation (`+`) instead of `append()` or `extend()`

## Related Types

- **[Deque](../stdlib/collections.md#deque)** - O(1) append and prepend
- **[Array](../stdlib/array.md)** - More memory efficient for large numeric lists
- **[Tuple](tuple.md)** - Immutable alternative

## Further Reading

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html) -
  Deep dive into CPython's list implementation
