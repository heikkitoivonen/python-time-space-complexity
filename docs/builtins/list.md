# List Operations Complexity

The `list` type is a mutable, ordered sequence. It's implemented as a dynamic array in CPython.

## Time Complexity

| Operation | Time | Notes |
|-----------|------|-------|
| `len()` | O(1) | Direct lookup |
| `access[i]` | O(1) | Direct indexing |
| `append(x)` | O(1) amortized | May resize; worst case O(n) when reallocation needed |
| `insert(0, x)` | O(n) | Must shift all elements |
| `insert(i, x)` | O(n-i) | Shift elements from index i |
| `remove(x)` | O(n) | Must search and shift |
| `pop()` | O(1) | Remove last element |
| `pop(0)` | O(n) | Shift remaining elements |
| `pop(i)` | O(n-i) | Shift elements after i |
| `clear()` | O(n) | Deallocate memory |
| `index(x)` | O(n) | Linear search |
| `count(x)` | O(n) | Linear scan |
| `sort()` | O(n log n) | Timsort algorithm |
| `reverse()` | O(n) | In-place reversal |
| `copy()` | O(n) | Shallow copy |
| `extend(iterable)` | O(k) | k = length of iterable |
| `in` (membership) | O(n) | Linear search |
| `x + y` (concatenation) | O(m+n) | m, n are lengths |
| `[::2]` (slicing) | O(k) | k = slice length |

## Space Complexity

| Operation | Space |
|-----------|-------|
| `append()` | O(1) amortized; O(n) worst case on resize |
| `extend()` | O(k); may trigger O(n) resize |
| `sort()` | O(n) auxiliary |
| `copy()` | O(n) |
| `slice` | O(k) for new list |

## Implementation Details

### Dynamic Array Resizing

CPython's list uses a growth factor strategy:

```
If size >= capacity:
    new_capacity = (size * 9) // 8 + 6  # Growth formula
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
