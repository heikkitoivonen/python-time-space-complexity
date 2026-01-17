# pstats Module

The `pstats` module analyzes profiler output from cProfile or profile modules, providing tools for sorting and filtering statistics.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Stats()` initialization | O(n) | O(n) | n = profile entries |
| `sort_stats()` | O(n log n) | O(n) | Sorting profile entries; may require O(n) space |
| `print_stats()` | O(k) | O(k) | k = functions printed |

## Analyzing Profile Data

### Loading and Sorting

```python
import pstats
import cProfile

# Profile and save
cProfile.run('expensive_function()', 'profile_output')

# Load stats - O(n)
stats = pstats.Stats('profile_output')

# Sort by cumulative time - O(n log n)
stats.sort_stats('cumulative')

# Print top 10 - O(k)
stats.print_stats(10)
```

### Multiple Sorting

```python
import pstats

# Load - O(n)
stats = pstats.Stats('profile_output')

# Sort by multiple keys - O(n log n)
stats.sort_stats('time', 'cumulative')

# Strip directory paths - O(n)
stats.strip_dirs()

# Print specific functions - O(k)
stats.print_stats('.*function_name.*')
```

## Related Documentation

- [cProfile Module](cprofile.md)
- [profile Module](profile.md)
