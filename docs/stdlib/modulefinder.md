# modulefinder Module

The `modulefinder` module finds all modules that a Python script imports, useful for analyzing dependencies and creating standalone applications.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Find dependencies | Varies | Varies | Depends on code paths and import hooks |
| Build import graph | Varies | Varies | Depends on modules discovered |

## Analyzing Module Dependencies

### Finding Imported Modules

```python
from modulefinder import ModuleFinder

# Create finder - O(1)
mf = ModuleFinder()

# Analyze script - cost depends on imports and code paths
mf.run_script('myapp.py')

# Get results - O(1)
print("Modules:", mf.modules)
print("Bad imports:", mf.badimports)

# Report - cost depends on number of modules
mf.report()
```

## Related Documentation

- [importlib Module](importlib.md)
- [ast Module](ast.md)
