# imp Module

⚠️ **REMOVED IN PYTHON 3.12**: The `imp` module was deprecated since Python 3.4 and removed in Python 3.12.

The `imp` module provided functions for importing modules.

## Removal Notice

```python
# ❌ DON'T: Use imp module (deprecated, removed in 3.12)
import imp
module = imp.load_source('name', 'path.py')

# ✅ DO: Use importlib (modern replacement)
import importlib.util
spec = importlib.util.spec_from_file_location('name', 'path.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
```

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `load_source()` | O(n) | O(n) | n = file size |
| `load_compiled()` | O(n) | O(n) | Load .pyc |
| `find_module()` | O(1) | O(1) | Find module file |

## Legacy Functions (Deprecated)

### load_source

```python
# ❌ DEPRECATED: Use importlib instead
import imp

# Load module from source file - O(n)
module = imp.load_source('mymodule', '/path/to/mymodule.py')
```

### load_compiled

```python
# ❌ DEPRECATED: Use importlib instead
import imp

# Load compiled module from .pyc - O(n)
module = imp.load_compiled('mymodule', '/path/to/mymodule.pyc')
```

### find_module

```python
# ❌ DEPRECATED: Use importlib instead
import imp

# Find module location - O(1)
file, pathname, description = imp.find_module('mymodule')
if file:
    file.close()
```

## Modern Alternatives

### Using importlib.util

```python
# ✅ RECOMMENDED: Modern approach
import importlib.util

# Load module from file - O(n)
spec = importlib.util.spec_from_file_location('mymodule', '/path/to/mymodule.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Use module
result = module.my_function()
```

### Using importlib.import_module

```python
# ✅ RECOMMENDED: For standard library modules
import importlib

# Import module by name - O(n)
module = importlib.import_module('json')

# Works with nested modules
module = importlib.import_module('xml.etree.ElementTree')
```

### Complete Example

```python
import importlib.util
from pathlib import Path

def load_module_from_file(module_name, file_path):
    """
    Load a Python module from a file path.
    Modern replacement for imp.load_source()
    
    Time: O(n) where n = file size
    Space: O(n)
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"{file_path} not found")
    
    # Create spec - O(1)
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {file_path}")
    
    # Create module - O(1)
    module = importlib.util.module_from_spec(spec)
    
    # Execute module - O(n)
    spec.loader.exec_module(module)
    
    return module

# Usage
mymodule = load_module_from_file('custom', '/path/to/custom.py')
print(mymodule.some_function())
```

## Dynamic Import Pattern

### Conditional Module Loading

```python
import importlib
from importlib import util

def try_import(module_name, fallback=None):
    """
    Try to import a module, with optional fallback.
    
    Time: O(n) where n = module size
    Space: O(n)
    """
    try:
        return importlib.import_module(module_name)
    except ImportError:
        if fallback:
            print(f"Falling back to {fallback}")
            return importlib.import_module(fallback)
        raise

# Try to import numpy, fall back to array
try:
    np = try_import('numpy', 'array')
except ImportError:
    print("Neither numpy nor array available")
```

## Finding Modules

### Using importlib.machinery

```python
# ✅ RECOMMENDED: Modern module finding
import importlib.machinery
import importlib.util
import sys

def find_module(module_name):
    """
    Find module location (modern replacement for imp.find_module()).
    
    Time: O(1) per path in sys.path
    Space: O(1)
    """
    # Search sys.path - O(p) where p = path count
    finder = importlib.machinery.PathFinder()
    spec = finder.find_spec(module_name)
    
    if spec and spec.origin:
        return spec.origin
    
    return None

# Usage
location = find_module('json')
print(f"json module at: {location}")
```

## Complete Migration Example

### Before (imp - Deprecated)

```python
import imp

# ❌ DEPRECATED
def load_config(config_file):
    module = imp.load_source('config', config_file)
    return module

config = load_config('/etc/app/config.py')
print(config.DATABASE_URL)
```

### After (importlib - Modern)

```python
import importlib.util

# ✅ RECOMMENDED
def load_config(config_file):
    spec = importlib.util.spec_from_file_location('config', config_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

config = load_config('/etc/app/config.py')
print(config.DATABASE_URL)
```

## Related Modules

- [importlib Module](importlib.md) - Modern import machinery
- [sys Module](sys.md) - System module list
- [importlib Module](importlib.md) - Utility functions (`importlib.util`)
- [pathlib Module](pathlib.md) - File path handling
