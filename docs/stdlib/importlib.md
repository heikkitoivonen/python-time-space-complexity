# Importlib Module

The `importlib` module provides tools for importing modules and working with Python's import system programmatically.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import_module(name)` | Varies | Varies | Depends on cache, meta path, and I/O |
| `importlib.util.find_spec(name)` | Varies | Varies | Depends on finders and file system |
| `reload(module)` | Varies | Varies | Re-executes module code |
| `resources.files(package)` | Varies | Varies | May import package or access loaders |

## Common Operations

### Importing Modules Dynamically

```python
import importlib

# Cost depends on loaders, cache, and filesystem
# Prefer this over __import__()
module = importlib.import_module('os.path')

# Equivalent to: import os.path
import_module('json')
import_module('collections.abc')

# From cached sys.modules if already imported
module = importlib.import_module('json')
module = importlib.import_module('json')  # Second call is cached
```

### Reloading Modules

```python
import importlib
import mymodule

# Re-executes module code
importlib.reload(mymodule)

# Useful for development when module changes
# Note: only reloads that module, not dependencies
```

### Finding Module Loaders

```python
import importlib.util
import sys

spec = importlib.util.find_spec('json')
if spec is not None:
    print(f"Found: {spec.origin}")

# Get loader
loader = spec.loader

# Manual import from spec (executes module code)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
```

### Working with Submodules

```python
import importlib

package = importlib.import_module('email')

# Get submodule
mime = importlib.import_module('email.mime')
text = importlib.import_module('email.mime.text')

# Check if submodule exists after first import
import email.mime.text
print('email.mime.text' in sys.modules)  # O(1)
```

## Common Use Cases

### Conditional Module Imports

```python
import importlib
import sys

def try_import(module_name, default=None):
    """Safely import module; cost depends on cache and loaders."""
    try:
        if module_name in sys.modules:  # Cached
            return sys.modules[module_name]
        
        return importlib.import_module(module_name)
    except ImportError:
        return default

# Usage
numpy = try_import('numpy')
if numpy:
    # Use numpy
    pass
else:
    # Use fallback
    pass
```

### Plugin System

```python
import importlib
import sys

class PluginManager:
    def __init__(self):
        self.plugins = {}
    
    def load_plugin(self, name, module_path):
        """Load plugin module; cost depends on loaders and module code."""
        try:
            module = importlib.import_module(module_path)
            
            # Assume plugin has 'register' function
            if hasattr(module, 'register'):
                plugin = module.register()
                self.plugins[name] = plugin
                return True
        except ImportError:
            pass
        return False
    
    def get_plugin(self, name):
        """Get cached plugin - O(1)"""
        return self.plugins.get(name)

manager = PluginManager()
manager.load_plugin('plugin1', 'plugins.plugin1')
manager.load_plugin('plugin2', 'plugins.plugin2')

# Later access - O(1)
plugin = manager.get_plugin('plugin1')
```

### Module Attribute Inspection

```python
import importlib

module = importlib.import_module('collections')

# hasattr checks __dict__
if hasattr(module, 'deque'):
    Deque = getattr(module, 'deque')
    
# iterate all attributes
for attr_name in dir(module):  # O(n)
    attr = getattr(module, attr_name)
    if callable(attr):
        print(f"{attr_name}: {type(attr)}")
```

### Checking Module Availability

```python
import importlib.util

def module_available(name):
    """Check if module can be imported; cost depends on finders."""
    spec = importlib.util.find_spec(name)
    return spec is not None

# Fast check with caching
available_mods = {}

def is_available(name):
    if name not in available_mods:
        available_mods[name] = module_available(name)
    return available_mods[name]  # Cached
```

## Performance Tips

### Cache Module References

```python
import importlib

# Bad: import each time
def process():
    json = importlib.import_module('json')
    return json.loads(data)

# Good: reuse cached module after first import
json = importlib.import_module('json')

def process():
    return json.loads(data)  # O(n) to parse, O(1) to access module
```

### Use find_spec for Existence Checks

```python
import importlib.util

# Efficient existence check when cached or path-based
if importlib.util.find_spec('numpy'):
    import numpy
    # Use numpy
```

### Batch Import Strategy

```python
import importlib
import sys

def ensure_modules(module_list):
    """Import multiple modules efficiently"""
    loaded = {}
    for name in module_list:
        if name not in sys.modules:  # Cached check
            loaded[name] = importlib.import_module(name)
        else:
            loaded[name] = sys.modules[name]
    return loaded

# Cost depends on module count, loaders, and module code
modules = ensure_modules(['json', 'os', 'sys'])
```

## Version Notes

- **Python 3.x**: `importlib` and `importlib.util` are available

## Related Documentation

- [Sys Module](sys.md) - sys.modules cache
- [Pkgutil Module](pkgutil.md) - Package utilities
- [Runpy Module](runpy.md) - Running modules
