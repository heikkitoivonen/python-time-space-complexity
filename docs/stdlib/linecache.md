# linecache Module

The `linecache` module allows efficient retrieval of individual lines from Python source files, caching lines to avoid repeated file I/O.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getline()` | O(n) first access, O(1) cached | O(n) | n = file lines, file is cached on first access |
| `checkcache()` | O(1) | O(1) | Invalidate cache |
| First access | O(n) | O(n) | Load entire file |

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

# Clear cache - O(1)
linecache.checkcache()

# Clear specific file - O(1)
linecache.checkcache('myfile.py')
```

## Related Documentation

- [inspect Module](inspect.md)
- [traceback Module](traceback.md)
