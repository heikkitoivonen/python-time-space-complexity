# profile Module

The `profile` module provides a pure Python profiler for measuring program execution time (superseded by cProfile which is faster).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `profile.run()` | O(n) | O(n) | n = function calls; output size grows with call graph |
| Profiling overhead | implementation-dependent | O(n) | Pure Python; higher overhead than `cProfile` |

## Using profile Module

### Basic Profiling

```python
import profile

def slow_function(n):
    result = 0
    for i in range(n):
        result += i
    return result

# Profile - O(n) with significant overhead
profile.run('slow_function(1000)')
```

## Related Documentation

- [cProfile Module](cprofile.md)
- [pstats Module](pstats.md)
- [timeit Module](timeit.md)
