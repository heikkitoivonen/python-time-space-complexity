# linecache Module

The `linecache` module allows efficient retrieval of individual lines from Python source files, caching lines to avoid repeated file I/O.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getline()` first access | O(n) | O(n) | Loads entire file into cache; n = file lines |
| `getline()` cached | O(1) | O(1) | Returns cached line |
| `checkcache()` | O(k) | O(1) | k = cached files; checks mtime for invalidation |
| `clearcache()` | O(k) | O(1) | k = cached files; clears entries |

## Getting Lines from Files

### Retrieve Single Lines

```python
import linecache

# Get line - O(1) after caching
line = linecache.getline('myfile.py', 5)
print(line)

# Get multiple lines - O(k) where k = lines
for i in range(1, 4):
    print(linecache.getline('myfile.py', i))
```

## Cache Management

### Clearing Cache

```python
import linecache

# Clear entire cache - O(k)
linecache.clearcache()

# Invalidate cache entries if files changed
linecache.checkcache()
```

## Related Documentation

- [inspect Module](inspect.md)
- [traceback Module](traceback.md)
