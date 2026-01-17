# profile Module

The `profile` module provides a pure Python profiler for measuring program execution time (superseded by cProfile which is faster).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `profile.run()` | O(n) | O(n) | n = function calls |
| Profiling overhead | ~20x slowdown | O(n) | Pure Python; use cProfile for ~2-3x overhead |

## Using profile Module

### Basic Profiling

```python
import profile

def slow_function(n):
    result = 0
    for i in range(n):
        result += i
    return result

# Profile - O(n) with 20x overhead
profile.run('slow_function(1000)')
```

## Related Documentation

- [cProfile Module](cprofile.md)
- [pstats Module](pstats.md)
- [timeit Module](timeit.md)
