# sys Module Complexity

The `sys` module provides access to interpreter variables and functions related to Python runtime behavior.

## Complexity Reference

Most of `sys` reads or writes one interpreter field and is constant time. The
rows worth knowing are the handful that are not: walking frames, interning a
string, and anything that visits every thread or every hook.

Throughout, `d` is a frame depth, `t` the number of live threads, `h` the
number of installed audit hooks, `m` the number of entries in `sys.modules`,
and `e` the number of entries in `sys.path`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.exc_info()` | O(1) | O(1) | Builds a 3-tuple from the thread's current exception |
| `sys.exception()` | O(1) | O(1) | The exception itself, with no tuple built; Python 3.11+ |
| `sys.exit(code)` | O(1) | O(1) | Raises `SystemExit`, so this is the cost of the raise, not of the shutdown that follows |
| `sys._getframe(d)` | O(d) | O(1) | Follows the frame chain one link at a time |
| `sys._current_frames()` | O(t) | O(t) | One entry per live thread |
| `sys.getrecursionlimit()` | O(1) | O(1) | Reads one interpreter field |
| `sys.setrecursionlimit(n)` | O(t) | O(1) | Writes through to every thread state (Python 3.11+) |
| `sys.getsizeof(obj)` | O(1) | O(1) | Calls `obj.__sizeof__()`; O(1) for builtin types, and whatever a custom `__sizeof__` costs otherwise |
| `sys.getrefcount(obj)` | O(1) | O(1) | Reads the refcount field |
| `sys.intern(s)` | O(len(s)) | O(1) | Hashes and looks up the string; O(1) when `s` is already interned. The table holds no reference of its own, so keep the result alive or the entry goes with it |
| `sys.audit(event, *args)` | O(h) | O(1) | Every installed hook is called |
| `sys.addaudithook(hook)` | O(1) | O(1) | Hooks cannot be removed once added |
| `sys.settrace(fn)` / `sys.setprofile(fn)` | O(1) | O(1) | Constant to install; while installed, every traced event calls `fn`, which is where the cost lands |
| `sys.modules[name]`, `name in sys.modules` | O(1) avg | O(1) | An ordinary dict, so O(m) in the worst case if every key collides |
| iterating `sys.modules` | O(m) | O(1) | |
| `sys.path.append(p)` | O(1) amortized | O(1) | O(e) on the resize |
| `sys.path.insert(0, p)` | O(e) | O(1) | Shifts every existing entry |
| `p in sys.path` | O(e) | O(1) | Linear scan |
| `sys.getdefaultencoding()`, `sys.getswitchinterval()`, `sys.is_finalizing()`, and the other simple getters | O(1) | O(1) | One field read each |
| `sys.platform`, `sys.version`, `sys.maxsize`, and the other data attributes | O(1) | O(1) | Plain attribute reads, computed once at startup |

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
# sys.modules is a real dict: a few dozen entries at startup, more as you import
loaded_modules = sys.modules  # {'os': <module>, 'sys': <module>, ...}

# O(1) lookup - fast dict access
if 'numpy' in sys.modules:
    numpy = sys.modules['numpy']

# O(m) to iterate all modules where m = module count
module_count = len(sys.modules)
for module_name in sys.modules:
    module = sys.modules[module_name]
```

### Paths and Import Control

```python
import sys

# O(e) where e = path entries
for path in sys.path:
    print(path)

# Insert at front - O(e) due to shifting elements
sys.path.insert(0, '/custom/path')  # O(e)

# Better: append at end - O(1) amortized
sys.path.append('/custom/path')  # O(1) amortized

# Check if path is set - O(e) linear search
if '/some/path' not in sys.path:  # O(e)
    sys.path.append('/some/path')
```

### Recursion Limit

```python
import sys

# O(1) to get limit
current_limit = sys.getrecursionlimit()  # Default: 1000

# O(t) to set limit
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

hits = 0

# Repeated lookups are O(1) average, but hoisting avoids the dict hit each time
for i in range(1000):
    if 'json' in sys.modules:  # O(1) average, a thousand times
        hits += 1

# Good: one lookup, then a local check
json_loaded = 'json' in sys.modules  # O(1) once
for i in range(1000):
    if json_loaded:
        hits += 1
```

### Pre-allocate Path List Modifications

```python
import sys

paths = ['/one', '/two', '/three']  # k entries to prepend

# Bad: k inserts at position 0, each shifting every entry - O(k * e)
for path in paths:
    sys.path.insert(0, path)  # O(e) each time

# Good: build the new list once - O(e + k)
sys.path = paths + sys.path

# Also O(e + k), and it keeps sys.path the same list object
sys.path[:0] = paths
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
- **Python 3.10.7+**: `sys.set_int_max_str_digits()` added, backported from 3.11
- **Python 3.11+**: `sys.exception()` added; `sys.setrecursionlimit()` began
  writing through to every thread state
- **Python 3.12+**: `sys.monitoring` and `sys.getunicodeinternedsize()` added
- **Python 3.12**: and only 3.12, `sys.intern()` makes the string immortal, so
  interning many distinct strings there never gives the memory back
- **Python 3.13+**: interned strings are mortal again, as they were before 3.12
- **Python 3.14+**: `sys._clear_type_cache()` is deprecated in favour of
  `sys._clear_internal_caches()`

## Related Documentation

- [Traceback Module](traceback.md) - Exception formatting
- [os Module](os.md) - OS-level operations
- [Logging Module](logging.md) - Logging configuration
