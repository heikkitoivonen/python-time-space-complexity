# Quick Reference - Python Complexity Cheat Sheet

## Common Operations

### Lists
| Operation | Time | Notes |
|-----------|------|-------|
| `append()` | O(1)* | Amortized |
| `insert(i)` | O(n) | Shifts elements |
| `pop()` | O(1) | Last element |
| `pop(0)` | O(n) | First element |
| `in` | O(n) | Linear search |
| `sort()` | O(n log n) | Timsort |

**Pro tip:** Use `deque.appendleft()` for O(1) prepend instead of `list.insert(0)`.

### Dictionaries & Sets
| Operation | Time |
|-----------|------|
| `d[key]` | O(1) avg |
| `d[key] = v` | O(1) avg |
| `key in d` | O(1) avg |
| `d.keys()` / `.values()` / `.items()` | O(1) view; O(n) iterate |
| `set.add()` | O(1) avg |
| `x in set` | O(1) avg |

**Pro tip:** Use sets for fast membership testing, not lists.

### Strings
| Operation | Time |
|-----------|------|
| `len()` | O(1) |
| `s[i]` | O(1) |
| `in` (substring) | O(n) avg |
| `split()` / `join()` | O(n) |
| `replace()` | O(n) |
| `find()` | O(n) avg |

**Pro tip:** Use `"".join(list)` not `+=` in loops.

### Standard Library

#### Deque (from collections)
| Operation | Time |
|-----------|------|
| `append()` / `appendleft()` | O(1) |
| `pop()` / `popleft()` | O(1) |
| `access[i]` | O(n) |

**Use deque for:** Queue, stack, fast prepend operations

#### Heapq
| Operation | Time |
|-----------|------|
| `heapify()` | O(n) |
| `heappush()` | O(log n) |
| `heappop()` | O(log n) |
| `nlargest(k)` | O(n log k) |

**Use heapq for:** Priority queues, top-k problems

#### Bisect
| Operation | Time |
|-----------|------|
| `bisect_left/right()` | O(log n) |
| `insort()` | O(n) |

**Use bisect for:** Sorted list searches, binary search

## Design Patterns

### Fast Membership Testing
```python
# ❌ Bad: O(n) for each check
if item in list:
    pass

# ✅ Good: O(1) for each check
if item in set:
    pass
```

### Building Strings
```python
# ❌ Bad: O(n²)
result = ""
for item in items:
    result += item

# ✅ Good: O(n)
result = "".join(items)
```

### Prepending to Collections
```python
# ❌ Bad: O(n) each time
lst.insert(0, item)

# ✅ Good: O(1) each time
from collections import deque
dq = deque()
dq.appendleft(item)
```

### Frequent Insertions into Sorted List
```python
# ❌ Bad: O(n²) total for k insertions
for item in items:
    bisect.insort(sorted_list, item)

# ✅ Good: O(n log n)
sorted_list.extend(items)
sorted_list.sort()
```

## Python Versions

### Performance Tier
```
Python 3.9      ← Baseline
Python 3.10     ← +5% improvements
Python 3.11     ← +10-60% improvements (inline caching!)
Python 3.12     ← +5-10% improvements
Python 3.13     ← Similar (experimental free-threading)
Python 3.14     ← Better GC pauses, new heapq max-heap
```

**Recommendation:** Use Python 3.11+ for performance-critical code.

### Features by Version
```
3.9:  Type hints without imports (list[int])
3.10: Pattern matching (match/case)
3.11: Inline caching (2-4x faster attribute access)
3.12: Comprehension inlining, type parameters
3.13: Free-threading (experimental), JIT (experimental)
3.14: heapq max-heap functions, annotationlib, compression.zstd
```

## Implementation Comparison

| Implementation | Use Case | Speed | GIL |
|---|---|---|---|
| CPython | Default, standard | Good | Yes |
| PyPy | CPU-bound loops | Excellent* | No |
| Jython | Java integration | Good | No |
| IronPython | .NET integration | Good | No |

*PyPy faster after warm-up (~100ms)

## Memory Overhead

```
Empty list     ~56 bytes
Empty dict     ~240 bytes
Empty set      ~216 bytes
Integer        ~28 bytes
String (5 chars) ~54 bytes
```

Use compact types when storing millions of objects.

## Complexity Classes (for reference)

| O() | Examples | Speed for 1M items |
|---|---|---|
| O(1) | List access, dict lookup | Instant |
| O(log n) | Binary search | ~20 operations |
| O(n) | Linear search, sort check | ~1M operations |
| O(n log n) | Good sorts (Timsort) | ~20M operations |
| O(n²) | Bubble sort, nested loops | ~1T operations (slow!) |
| O(2ⁿ) | Recursive enumeration | Unusable |

## When to Upgrade Data Structures

### From List to Deque
- Frequent `insert(0)` or `pop(0)` operations
- Implement queue or double-ended queue
- Frequent operations at both ends

### From List to Set
- Only care about membership testing
- Order doesn't matter
- Adding/removing items frequently

### From Dict to DefaultDict
- Repeatedly access missing keys
- Creating groups/buckets
- Counting items

### From List to Heapq
- Need min/max element frequently
- Priority queue needed
- Top-k problems

## Common Mistakes

```python
# ❌ Finding item in list O(n) times
for item in haystack:
    if item in large_list:  # O(n) - slow!
        process(item)

# ✅ Use set for O(1) lookup
haystack_set = set(haystack)
for item in haystack:
    if item in haystack_set:  # O(1) - fast!
        process(item)

# ❌ Concatenating strings in loop
result = ""
for word in words:
    result += word  # O(n²) total

# ✅ Use join
result = "".join(words)  # O(n) total

# ❌ Relying on dict order before 3.6
d = {}
# In Python 3.5: order not guaranteed

# ✅ Python 3.6+ guarantees order
d = {}  # Order preserved!
```

## Performance Tips

1. **Choose right data structure first** - Algorithm choice beats optimization
2. **Use sets for membership** - 100x faster than lists for large collections
3. **Use join for strings** - Not += in loops
4. **Use PyPy for loops** - 10-100x faster for CPU-bound code
5. **Upgrade to Python 3.11+** - 10-60% faster automatically
6. **Profile first** - Don't optimize guesses
7. **Amortized O(1)** - append() is fast, don't optimize it

## Resources

- **Docs:** Included in this repository
- **Reference:** https://wiki.python.org/moin/TimeComplexity
- **Official Docs:** https://docs.python.org/3/
- **CPython Source:** https://github.com/python/cpython

---

**Full documentation in `/docs` - See README.md to get started!**
