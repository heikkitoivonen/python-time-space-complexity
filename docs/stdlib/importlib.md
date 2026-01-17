# Importlib Module

The `importlib` module provides tools for importing modules and working with Python's import system programmatically.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import_module(name)` | O(n) | O(n) | n = import depth |
| `find_loader(name)` | O(1) | O(1) | Check sys.modules |
| `reload(module)` | O(n) | O(n) | n = module size |
| `import_module(package)` | O(n+m) | O(n+m) | n = submodules |
| `resources.files()` | O(1) | O(1) | Get resource path |

## Common Operations

### Importing Modules Dynamically

```python
import importlib

# O(n) where n = import depth/module size
# Prefer this over __import__()
module = importlib.import_module('os.path')

# Equivalent to: import os.path
import_module('json')  # O(n)
import_module('collections.abc')  # O(n)

# From cached sys.modules if already imported - O(1)
module = importlib.import_module('json')
module = importlib.import_module('json')  # Second call is O(1)
```

### Reloading Modules

```python
import importlib
import mymodule

# O(n) where n = module size
# Re-executes module code
importlib.reload(mymodule)

# Useful for development when module changes
# Note: only reloads that module, not dependencies
```

### Finding Module Loaders

```python
import importlib.util
import sys

# O(1) - check if module is cached
spec = importlib.util.find_spec('json')
if spec is not None:
    print(f"Found: {spec.origin}")  # O(1)

# Get loader - O(1) if cached, O(n) if needs import
loader = spec.loader

# Manual import from spec - O(n)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)  # O(n)
```

### Working with Submodules

```python
import importlib

# O(n) where n = total submodules
package = importlib.import_module('email')

# Get submodule - O(m) where m = submodule size
mime = importlib.import_module('email.mime')
text = importlib.import_module('email.mime.text')

# Check if submodule exists - O(1) after first import
import email.mime.text
print('email.mime.text' in sys.modules)  # O(1)
```

## Common Use Cases

### Conditional Module Imports

```python
import importlib
import sys

def try_import(module_name, default=None):
    """Safely import module - O(n) or O(1)"""
    try:
        if module_name in sys.modules:  # O(1) check
            return sys.modules[module_name]
        
        return importlib.import_module(module_name)  # O(n)
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
        """Load plugin module - O(n) where n = module size"""
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

# Usage - O(n) per plugin
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

# O(1) - hasattr checks __dict__
if hasattr(module, 'deque'):
    Deque = getattr(module, 'deque')
    
# O(n) - iterate all attributes where n = module size
for attr_name in dir(module):  # O(n)
    attr = getattr(module, attr_name)
    if callable(attr):
        print(f"{attr_name}: {type(attr)}")
```

### Checking Module Availability

```python
import importlib.util

def module_available(name):
    """Check if module can be imported - O(1) cache or O(n) search"""
    spec = importlib.util.find_spec(name)
    return spec is not None

# Fast check with caching
available_mods = {}

def is_available(name):
    if name not in available_mods:
        available_mods[name] = module_available(name)  # O(n) first time
    return available_mods[name]  # O(1) after cached
```

## Performance Tips

### Cache Module References

```python
import importlib

# Bad: O(n) import each time
def process():
    json = importlib.import_module('json')
    return json.loads(data)

# Good: O(1) after first import
json = importlib.import_module('json')

def process():
    return json.loads(data)  # O(n) to parse, O(1) to access module
```

### Use find_spec for Existence Checks

```python
import importlib.util

# Efficient existence check - O(1) if cached or path-based
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
        if name not in sys.modules:  # O(1) check
            loaded[name] = importlib.import_module(name)  # O(n)
        else:
            loaded[name] = sys.modules[name]  # O(1)
    return loaded

# O(k*n) where k = module count, n = avg module size
modules = ensure_modules(['json', 'os', 'sys'])
```

## Version Notes

- **Python 2.7**: Limited support
- **Python 3.1+**: importlib added
- **Python 3.4+**: importlib.util for detailed control
- **Python 3.7+**: Simplified import machinery

## Related Documentation

- [Sys Module](sys.md) - sys.modules cache
- [Pkgutil Module](pkgutil.md) - Package utilities
- [Runpy Module](runpy.md) - Running modules
