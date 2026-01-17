# Sys Module

The `sys` module provides access to interpreter variables and functions related to Python runtime behavior.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.exc_info()` | O(1) | O(1) | Get exception info |
| `sys.exit()` | O(1) | O(1) | Terminate program |
| `sys.getrecursionlimit()` | O(1) | O(1) | Get limit |
| `sys.setrecursionlimit(n)` | O(1) | O(1) | Set limit |
| `sys.getsizeof(obj)` | O(1) | O(1) | Get object size |
| `len(sys.path)` | O(1) | O(1) | List length is cached |
| `sys.modules` lookup | O(1) avg, O(n) worst | O(n) | Dict lookup; O(n) worst case due to hash collisions |

## Common Operations

### Exception Information

```python
import sys

try:
    x = undefined
except:
    # O(1) time - returns current exception info
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    # exc_type: exception class
    # exc_value: exception instance
    # exc_traceback: traceback object
    
    print(f"Type: {exc_type}")
    print(f"Value: {exc_value}")
    print(f"Traceback: {exc_traceback}")
```

### Accessing Command-Line Arguments

```python
import sys

# O(1) access to list of arguments
# sys.argv[0] is script name
print(sys.argv)  # ['script.py', 'arg1', 'arg2']

# O(1) to access individual arguments
script_name = sys.argv[0]
first_arg = sys.argv[1] if len(sys.argv) > 1 else None
```

### Module Management

```python
import sys

# O(1) access to loaded modules dictionary
# sys.modules is dict-like with ~200+ entries typically
loaded_modules = sys.modules  # {'os': <module>, 'sys': <module>, ...}

# O(1) lookup - fast dict access
if 'numpy' in sys.modules:
    numpy = sys.modules['numpy']

# O(n) to iterate all modules where n = module count
module_count = len(sys.modules)
for module_name in sys.modules:
    module = sys.modules[module_name]
```

### Paths and Import Control

```python
import sys

# O(n) where n = path entries (usually ~10-20)
for path in sys.path:
    print(path)

# Insert at front - O(n) due to shifting elements
sys.path.insert(0, '/custom/path')  # O(n)

# Better: append at end - O(1) amortized
sys.path.append('/custom/path')  # O(1) amortized

# Check if path is set - O(n) linear search
if '/some/path' not in sys.path:  # O(n)
    sys.path.append('/some/path')
```

### Recursion Limit

```python
import sys

# O(1) to get limit
current_limit = sys.getrecursionlimit()  # Default: 1000

# O(1) to set limit
sys.setrecursionlimit(5000)

# Check recursion depth - O(1)
def recursive_func(depth=0):
    if depth > sys.getrecursionlimit() - 100:
        print("Approaching recursion limit!")
    if depth < 100:
        return recursive_func(depth + 1)
    return depth
```

### Memory Information

```python
import sys

class MyClass:
    def __init__(self, data):
        self.data = data

# O(1) - get object size in bytes
obj = MyClass([1, 2, 3])
size = sys.getsizeof(obj)  # Size of object itself
data_size = sys.getsizeof(obj.data)  # Size of list

# Note: getsizeof doesn't include referenced objects
# For deep size, use:
import sys

def get_deep_size(obj, seen=None):
    """Get size including all referenced objects - O(n)"""
    if seen is None:
        seen = set()
    
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    
    if isinstance(obj, dict):
        for k, v in obj.items():
            size += get_deep_size(k, seen)
            size += get_deep_size(v, seen)
    elif hasattr(obj, '__dict__'):
        size += get_deep_size(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        for item in obj:
            size += get_deep_size(item, seen)
    
    return size
```

### Platform and Version Information

```python
import sys

# O(1) - constant information
print(sys.platform)     # 'linux', 'win32', 'darwin'
print(sys.version)      # Version string
print(sys.version_info) # (3, 11, 2, 'final', 0)
print(sys.executable)   # Path to Python executable
```

### Stream Control

```python
import sys

# O(1) - direct assignment
original_stdout = sys.stdout

# Redirect stdout - O(1)
import io
buffer = io.StringIO()
sys.stdout = buffer

# Your code that prints here captures output
print("This goes to buffer")

# Restore - O(1)
sys.stdout = original_stdout

# Get captured output - O(n) where n = buffer size
output = buffer.getvalue()
```

## Performance Tips

### Avoid Repeated Module Lookups

```python
import sys

# Bad: O(n) lookup each time
for i in range(1000):
    if 'json' in sys.modules:
        # use json module

# Good: O(1) lookup once
json_loaded = 'json' in sys.modules
for i in range(1000):
    if json_loaded:
        # use json module
```

### Pre-allocate Path List Modifications

```python
import sys

# Bad: Multiple O(n) inserts at position 0
for path in paths:
    sys.path.insert(0, path)  # O(n) each time

# Good: Extend at once - O(k) where k = paths to add
sys.path = paths + sys.path  # Rebuild list
# Or: O(k) amortized
for path in reversed(paths):
    sys.path.insert(0, path)  # Reverse to maintain order
```

### Use sys.modules for Import Caching

```python
import sys

def get_module_cached(name):
    """Fast lookup - O(1) if already imported"""
    if name in sys.modules:
        return sys.modules[name]
    
    # Only import if not cached
    import importlib
    return importlib.import_module(name)
```

## Version Notes

- **Python 2.6+**: Most operations available
- **Python 3.x**: All standard operations available
- **Python 3.11+**: Enhanced error messages with better tracebacks

## Related Documentation

- [Traceback Module](traceback.md) - Exception formatting
- [Os Module](os.md) - OS-level operations
- [Logging Module](logging.md) - Logging configuration
