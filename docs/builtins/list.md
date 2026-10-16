# List Operations Complexity

The `list` type is a mutable, ordered sequence. It's implemented as a dynamic array in CPython.

`n` is the list's length, `k` is an index or a repeat count, `i:j` are slice bounds, and `len(t)`
is the length of the other operand. Comparing two elements counts as O(1).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(l)` | O(1) | O(1) | The length is stored in the list, not counted |
| `l[k]` | O(1) | O(1) | Direct indexing |
| `l[k] = x` | O(1) | O(1) | Replaces one slot |
| `del l[k]` | O(n-k) | O(1) | Shifts the elements after k one slot left |
| `append(x)` | O(1) amortized | O(1) amortized | May resize; worst case O(n) when reallocation needed |
| `insert(0, x)` | O(n) | O(1) amortized | Must shift all elements |
| `insert(k, x)` | O(n-k) amortized | O(1) amortized | Shifts the elements from k onwards one slot right |
| `remove(x)` | O(n) | O(1) | Must search and shift |
| `pop()` | O(1) amortized | O(1) | Remove last element; nothing is shifted |
| `pop(0)` | O(n) | O(1) | Shift remaining elements |
| `pop(k)` | O(n-k) amortized | O(1) | Shifts the elements after k one slot left |
| `clear()` | O(n) | O(1) | Deallocate memory |
| `index(x)` | O(n) | O(1) | Linear search |
| `count(x)` | O(n) | O(1) | Linear scan |
| `sort()` | O(n log n) worst, O(n) on sorted or reverse-sorted input | O(n) | Timsort/Powersort; adaptive, so already ordered runs cost fewer comparisons |
| `reverse()` | O(n) | O(1) | In-place reversal |
| `copy()` | O(n) | O(n) | Shallow copy |
| `extend(t)` | O(len(t)) amortized | O(len(t)) | Plus the cost of iterating t; may trigger O(n) resize |
| `l[i:j]` (slicing) | O(j-i) | O(j-i) | With a step, O(length of the result) |
| `l[i:j] = t` | O(j-i) if len(t) == j-i, otherwise O(n-i+len(t)) amortized | O(j-i+len(t)) | Equal lengths overwrite in place; otherwise everything after j moves |
| `del l[i:j]` | O(n-i) | O(j-i) | Everything after j moves left |
| `l1 + l2` (concatenation) | O(len(l1)+len(l2)) | O(len(l1)+len(l2)) | A new list |
| `l * k` (repetition) | O(nk) | O(nk) | A new list of n·k references |
| `for x in l` (iteration) | O(n) | O(1) | O(1) per step |
| `x in l` (membership) | O(n) | O(1) | Linear search |
| `min(l)`, `max(l)` | O(n) | O(1) | n-1 comparisons |

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
assert len(lst) == 1000000
```

### Insert Performance

```python
# O(n) - must shift all elements after insertion point
lst = [0] * 1000000
lst.insert(0, -1)  # Shifts 1,000,000 elements!
assert lst[0] == -1 and len(lst) == 1000001
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

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's list implementation
