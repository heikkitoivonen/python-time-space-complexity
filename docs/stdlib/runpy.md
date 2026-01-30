# runpy Module

The `runpy` module provides tools to locate and execute Python modules without importing them, useful for script execution.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `run_module()` | O(n) | O(n) | Executes module code; import and I/O costs dominate |
| `run_path()` | O(n) | O(n) | Executes script or package via path; file I/O dominates |

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
