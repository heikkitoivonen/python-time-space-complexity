# help() Function Complexity

The `help()` function displays documentation for Python objects, modules, and topics.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Get docstring | O(1) | O(m) | m = docstring length |
| Format help text | O(m) | O(m) | m = documentation size |
| Display help | O(m) | O(m) | I/O operation |
| Introspect object | O(n) | O(n) | n = number of attributes |

## Basic Usage

### Help for Objects

```python
# O(m) - retrieve and display docstring
help(str)              # Help for str class
help(list.append)      # Help for list.append method
help(42)               # Help for int
help("hello")          # Help for str instance
```

### Interactive Mode

```python
# O(m) - enter pager for documentation
# In interactive Python shell:
help()  # Enter help system
# Type module name or function name for help

# Type 'quit' to exit help system
```

### Help for Modules

```python
import os
# O(n) - introspect module
help(os)  # Shows module docstring and all members
help(os.path)  # Help for specific submodule
```

## Complexity Details

### Docstring Retrieval

```python
# O(m) - m = docstring length
def my_function():
    """This is documentation."""
    pass

# Retrieve docstring
doc = my_function.__doc__  # O(1)

# help() formats and displays it - O(m)
help(my_function)
```

### Object Introspection

```python
# O(n) - where n = number of members
# help() uses dir() and getattr() internally

class MyClass:
    attribute1 = 10
    attribute2 = 20
    
    def method1(self):
        """First method."""
        pass
    
    def method2(self):
        """Second method."""
        pass

# help() will introspect all members
help(MyClass)  # O(n) - n = 4 members
```

## Performance Patterns

### vs Manual Inspection

```python
# help() is comprehensive but slow
help(str)  # O(n) - introspects everything

# vs direct access (fast)
print(str.__doc__)  # O(1) - just docstring

# For performance-critical code, use direct access
# For interactive exploration, use help()
```

## Common Use Cases

### Interactive Exploration

```python
# In Python interpreter
# O(m) - displays formatted help

help(list)
# Shows all list methods and documentation

help(list.sort)
# Shows help for specific method

help()
# Interactive help mode
```

### Module Discovery

```python
# O(n) - explore module contents
import json

help(json)  # Show all JSON module functions

# Or get quick summary
import pydoc
pydoc.getdoc(json)  # O(n) - get formatted docs
```

### Method Signatures

```python
# O(m) - get signature information
help(str.format)
# Shows parameters, return value, examples

# vs inspect module (more detailed)
import inspect
sig = inspect.signature(str.format)
# O(m) - get signature object
```

## Alternatives

### Direct Attribute Access

```python
# O(1) - faster, but less formatted
obj = [1, 2, 3]
docstring = obj.__doc__

# vs help
help(obj)  # O(m) - slower but formatted
```

### pydoc Module

```python
import pydoc

# O(n) - more control
docs = pydoc.getdoc(str)  # Get formatted documentation
pydoc.render_doc(str)     # Get as HTML

# Server mode - browse documentation
pydoc.start_server(port=8000)
```

### inspect Module

```python
import inspect

# O(1) - fast attribute access
signature = inspect.signature(my_func)
source = inspect.getsource(my_func)
members = inspect.getmembers(obj)  # O(n)

# More programmatic than help()
```

## Interactive Help System

```python
# help() without arguments
# Starts interactive help system

# help()
# Then type:
# >>> list.append    (shows help for list.append)
# >>> modules        (shows all available modules)
# >>> keywords       (shows Python keywords)
# >>> topics         (shows special topics)
# >>> quit           (exits help)
```

## Practical Examples

### Documentation Lookup

```python
# O(m) - find how to use a function
def understand_function(func):
    help(func)

# Examples:
understand_function(len)
understand_function(str.split)
understand_function(dict.get)
```

### Debugging Unknown Objects

```python
# O(n) - understand what you're working with
def analyze(obj):
    print(f"Type: {type(obj)}")
    help(obj)  # See what methods available
    print(f"Dir: {dir(obj)}")

data = {"key": "value"}
analyze(data)  # Shows dict documentation
```

### Learning Python Features

```python
# O(m) - look up language features
help("if")      # Help on if statement
help("for")     # Help on for loops
help("class")   # Help on class definition
help("print")   # Help on print function
```

## Performance Considerations

### Startup Time

```python
# help() can be slow on first call (module imports)
import time

start = time.time()
help(str)  # First call slower
first = time.time() - start

start = time.time()
help(int)  # Subsequent calls faster (modules cached)
second = time.time() - start

# second < first (due to module caching)
```

### vs Inline Documentation

```python
# For frequently called functions, cache docs
HELP_CACHE = {}

def get_help(obj):
    key = id(obj)
    if key not in HELP_CACHE:
        HELP_CACHE[key] = obj.__doc__  # O(1)
    return HELP_CACHE[key]

# Faster than calling help() repeatedly
```

## Advanced Usage

### Programmatic Documentation Access

```python
# O(m) - get docs without printing
import pydoc

docs = pydoc.render_doc(str, title="String Documentation")
# Returns formatted HTML string

# Use in web server, etc.
```

### Documentation Server

```python
import pydoc

# Start local documentation server
# pydoc.start_server(port=8000)
# Then visit http://localhost:8000

# Or generate HTML
pydoc.writedoc(str, outdir="/tmp/docs")
# Creates HTML documentation file
```

## Edge Cases

### Objects Without Docstrings

```python
# O(1) - returns "no documentation"
class Empty:
    pass

help(Empty)  # "no documentation available"
```

### Built-in C Objects

```python
# O(m) - limited docstrings for C objects
help(len)  # C function, limited help
help(dict)  # Built-in type, has docstring
```

### Lambda Functions

```python
# O(1) - minimal help
func = lambda x: x ** 2
help(func)  # Shows minimal info (no docstring)

# Add docstring
func.__doc__ = "Square a number"
help(func)  # Shows custom docstring
```

## Best Practices

✅ **Do**:

- Use `help()` for interactive exploration
- Use `help(topic)` to learn about Python features
- Check `__doc__` attribute directly in code
- Use `inspect` module for programmatic access
- Write clear docstrings for your functions

❌ **Avoid**:

- Using `help()` in tight loops (call once, cache result)
- Assuming `help()` output format is stable
- Using `help()` for production code (direct access faster)
- Forgetting to write docstrings

## Related Functions

- **[dir()](dir.md)** - List object attributes
- **[callable()](callable.md)** - Check if object is callable
- **type()** - Get object type
- **[inspect](https://docs.python.org/3/library/inspect.html)** - Advanced introspection

## Version Notes

- **Python 2.x**: `help()` available in interactive mode
- **Python 3.x**: Same functionality, improved formatting
- **All versions**: Works on all objects with `__doc__` attribute
