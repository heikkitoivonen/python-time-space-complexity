# sysconfig Module

The `sysconfig` module provides access to Python's configuration information and compile-time variables.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `get_config_var()` | O(1) avg | O(1) | Cached lookup |
| `get_paths()` | O(1) avg | O(1) | Cached paths |

## Getting Configuration Information

### System Paths

```python
import sysconfig

# Get installation paths - O(1)
paths = sysconfig.get_paths()
print(paths['stdlib'])      # Standard library path
print(paths['platstdlib'])  # Platform-specific stdlib
print(paths['purelib'])     # Pure Python modules
print(paths['platlib'])     # Platform-specific modules

# Get specific path - O(1)
site_packages = sysconfig.get_path('purelib')
```

### Configuration Variables

```python
import sysconfig

# Get config variable - O(1)
version = sysconfig.get_config_var('PY_VERSION')
print(f"Python version: {version}")

# Get multiple variables
config = sysconfig.get_config_vars()
print(config['SO'])  # Shared object extension
```

## Related Documentation

- [sys Module](sys.md)
- [site Module](site.md)
