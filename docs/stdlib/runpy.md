# runpy Module

The `runpy` module provides tools to locate and execute Python modules without importing them, useful for script execution.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `run_module()` | O(n) | O(n) | Execute module |
| `run_path()` | O(n) | O(n) | Execute file/dir |
| Module lookup | O(1) avg, O(n) worst | O(1) | Hash-based; O(n) worst case due to hash collisions |

## Running Modules

### Execute Module by Name

```python
import runpy

# Run module - O(n)
runpy.run_module(
    'json.tool',
    run_name='__main__'
)

# Equivalent to: python -m json.tool
```

### Execute Script File

```python
import runpy

# Run file - O(n)
result = runpy.run_path('script.py', run_name='__main__')

# Access module namespace
print(result.get('variable_name'))
```

## Related Documentation

- [importlib Module](importlib.md)
- [sys Module](sys.md)
