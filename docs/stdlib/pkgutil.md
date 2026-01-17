# Pkgutil Module

The `pkgutil` module provides utilities for working with packages and module search paths.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `iter_modules(path)` | O(n) | O(n) | n = modules in path |
| `walk_packages()` | O(n) | O(n) | n = all subpackages |
| `find_loader(name)` | O(1) | O(1) | Check sys.modules |
| `get_data(name)` | O(n) | O(n) | n = file size |
| `extend_path()` | O(n) | O(n) | n = path entries |

## Common Operations

### Finding Modules in a Path

```python
import pkgutil

# O(n) where n = modules in directory
for importer, modname, ispkg in pkgutil.iter_modules(['./plugins']):
    print(f"{'Package' if ispkg else 'Module'}: {modname}")
    
    # ispkg = True if subpackage, False if module
    # importer = loader for the module
```

### Walking Package Tree

```python
import pkgutil
import sys

# O(n) where n = all subpackages/modules recursively
for importer, modname, ispkg in pkgutil.walk_packages(
    path=['./mypackage'], 
    prefix='mypackage.'
):
    print(modname)
    
# Example output:
# mypackage.module1
# mypackage.module2
# mypackage.subpkg
# mypackage.subpkg.module3
```

### Getting Package Data Files

```python
import pkgutil

# O(n) where n = file size
data = pkgutil.get_data('mypackage', 'data.txt')
# Returns bytes

# Can also work with nested paths - O(n)
data = pkgutil.get_data('mypackage.subpackage', 'resource.json')

# Example: loading JSON data
import json
try:
    raw_data = pkgutil.get_data('myapp', 'config.json')
    config = json.loads(raw_data)  # O(n) to parse
except (ImportError, FileNotFoundError):
    config = {}
```

## Common Use Cases

### Discovering Plugins

```python
import pkgutil
import importlib

def load_plugins(plugin_package):
    """Load all modules in plugin package - O(n*m)"""
    plugins = {}
    
    # O(n) to iterate modules
    for importer, modname, ispkg in pkgutil.iter_modules(
        plugin_package.__path__
    ):
        if not ispkg:  # Skip sub-packages
            # O(m) to import each module
            full_name = f"{plugin_package.__name__}.{modname}"
            module = importlib.import_module(full_name)
            
            # Assume each plugin has a 'Plugin' class
            if hasattr(module, 'Plugin'):
                plugins[modname] = module.Plugin()
    
    return plugins

# Usage - O(n*m) where n = plugins, m = avg module size
import plugins as plugin_package
loaded = load_plugins(plugin_package)
```

### Checking Package Contents

```python
import pkgutil

def get_submodules(package_name):
    """Get list of submodules - O(n)"""
    import importlib
    package = importlib.import_module(package_name)
    
    submodules = []
    
    # O(n) where n = direct submodules
    for importer, modname, ispkg in pkgutil.iter_modules(
        package.__path__
    ):
        submodules.append(modname)
    
    return submodules

# Usage
modules = get_submodules('email')
print(modules)  # ['mime', 'parser', 'generator', ...]
```

### Extending Path for Namespace Packages

```python
import pkgutil
import sys

# Extend path for namespace packages - O(n)
extended = pkgutil.extend_path(
    __path__,  # Current package path
    __name__   # Current package name
)

# Allows finding modules in multiple locations
# Useful for plugin directories
```

### Gathering Metadata

```python
import pkgutil
import importlib

def analyze_package(package_name):
    """Analyze package structure - O(n)"""
    import importlib
    package = importlib.import_module(package_name)
    
    analysis = {
        'modules': [],
        'subpackages': [],
        'module_count': 0,
        'has_init': hasattr(package, '__file__')
    }
    
    # O(n) to iterate
    for importer, modname, ispkg in pkgutil.iter_modules(
        package.__path__
    ):
        if ispkg:
            analysis['subpackages'].append(modname)
        else:
            analysis['modules'].append(modname)
        analysis['module_count'] += 1
    
    return analysis

# Usage
info = analyze_package('collections')
print(f"Modules: {info['module_count']}")
print(f"Subpackages: {info['subpackages']}")
```

## Performance Tips

### Cache pkgutil Results

```python
import pkgutil
import importlib

class PackageCache:
    def __init__(self):
        self._cache = {}
    
    def get_modules(self, package_name):
        """Get modules with caching - O(1) after first call"""
        if package_name not in self._cache:
            # O(n) first time
            package = importlib.import_module(package_name)
            modules = []
            for _, modname, _ in pkgutil.iter_modules(package.__path__):
                modules.append(modname)
            self._cache[package_name] = modules
        
        # O(1) subsequent calls
        return self._cache[package_name]

# Usage
cache = PackageCache()
modules = cache.get_modules('email')  # O(n)
modules = cache.get_modules('email')  # O(1)
```

### Lazy Load Heavy Modules

```python
import pkgutil
import importlib

def lazy_load_plugins(plugin_package):
    """Return loader dict instead of loading - O(n)"""
    import importlib
    package = importlib.import_module(plugin_package)
    
    loaders = {}
    
    # O(n) to setup loaders, O(1) per load
    for importer, modname, ispkg in pkgutil.iter_modules(
        package.__path__
    ):
        full_name = f"{plugin_package}.{modname}"
        
        # Store loader, don't import yet
        loaders[modname] = lambda fn=full_name: importlib.import_module(fn)
    
    return loaders

# Usage - O(n) setup, O(1) per lazy load
plugins = lazy_load_plugins('myapp.plugins')

# Load only when needed - O(m) for each plugin
plugin1 = plugins['plugin1']()  # Loads on demand
plugin2 = plugins['plugin2']()  # Loads on demand
```

### Limit Walk Depth for Large Trees

```python
import pkgutil
import importlib

def walk_packages_limited(package_name, max_depth=2):
    """Walk package tree with depth limit - O(n)"""
    package = importlib.import_module(package_name)
    
    def walk(path, prefix, depth):
        if depth > max_depth:
            return
        
        # O(k) at each depth
        for _, modname, ispkg in pkgutil.iter_modules(path):
            yield f"{prefix}.{modname}"
            if ispkg:
                subpackage = importlib.import_module(
                    f"{prefix}.{modname}"
                )
                yield from walk(
                    subpackage.__path__,
                    f"{prefix}.{modname}",
                    depth + 1
                )
    
    return list(walk(package.__path__, package_name, 0))
```

## Version Notes

- **Python 2.6+**: Basic functionality
- **Python 3.3+**: Namespace packages support
- **Python 3.9+**: Enhanced path handling
- **Python 3.10+**: Various optimizations

## Related Documentation

- [Importlib Module](importlib.md) - Dynamic importing
- [Sys Module](sys.md) - sys.path management
- [Pathlib Module](pathlib.md) - Path operations
