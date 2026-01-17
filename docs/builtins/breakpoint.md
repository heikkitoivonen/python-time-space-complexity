# breakpoint() Function

The `breakpoint()` function drops into the Python debugger (pdb by default) for interactive debugging.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `breakpoint()` | O(1) | O(1) | Pauses execution |
| Debugger session | O(n) | O(n) | n = time spent debugging |

## Basic Usage

### Simple Breakpoint

```python
def process_data(data):
    print(f"Input: {data}")
    breakpoint()  # Drop into debugger
    print(f"Processed: {data.upper()}")

process_data("hello")

# At debugger:
# (Pdb) data
# 'hello'
# (Pdb) continue
```

### Conditional Breakpoint

```python
def find_error(items):
    for i, item in enumerate(items):
        if item < 0:
            print(f"Found negative at index {i}")
            breakpoint()  # Debug only on error
        print(item)

find_error([1, 2, -3, 4])
```

### Debugging Inside Function

```python
def calculate(a, b, c):
    result = a + b
    breakpoint()  # Inspect variables
    result *= c
    return result

value = calculate(1, 2, 3)

# At debugger:
# (Pdb) result
# 3
# (Pdb) a, b, c
# (1, 2, 3)
# (Pdb) continue
```

## Debugger Commands

### Common PDB Commands

```python
value = 42
breakpoint()

# Commands at (Pdb) prompt:
# l (list) - Show source code
# n (next) - Execute next line
# s (step) - Step into function
# c (continue) - Resume execution
# u (up) - Go up stack frame
# d (down) - Go down stack frame
# p variable - Print variable
# pp variable - Pretty print
# h (help) - Show help
# q (quit) - Exit debugger
```

### Example Debugging Session

```python
def buggy_function(x, y):
    result = x + y
    breakpoint()  # Stop here
    result *= 2
    return result

buggy_function(10, 20)

# Session output:
# > /path/to/file.py:4in buggy_function()
# -> result *= 2
# (Pdb) x
# 10
# (Pdb) y
# 20
# (Pdb) result
# 30
# (Pdb) continue
```

## Custom Debugger

### Using Different Debugger

```python
import pdb

# Use custom debugger instead of default pdb
def custom_debugger():
    debugger = pdb.Pdb()
    debugger.set_trace()

custom_debugger()
```

### Disabling Breakpoints

```python
import sys

# Disable all breakpoints
def no_breakpoint(*args, **kwargs):
    pass

# PYTHONBREAKPOINT=0 environment variable also disables

# Or set in code
sys.__breakpointhook__ = no_breakpoint
breakpoint()  # Does nothing
```

## Environment Control

### Disable Via Environment

```bash
# Disable all breakpoints
export PYTHONBREAKPOINT=0
python script.py

# Use custom debugger
export PYTHONBREAKPOINT=mymodule.debugger
python script.py
```

### Programmatic Control

```python
import sys

# Custom breakpoint handler
def my_breakpoint(*args, **kwargs):
    print("Breakpoint hit!")
    # Custom logic
    import pdb
    pdb.set_trace(*args, **kwargs)

sys.breakpointhook = my_breakpoint

breakpoint()  # Uses custom handler
```

## Best Practices

```python
# ✅ DO: Use for development debugging
def complex_calculation(data):
    processed = preprocess(data)
    breakpoint()  # Inspect intermediate result
    return postprocess(processed)

# ❌ DON'T: Leave breakpoints in production
# Use logging instead for production debugging

import logging
logging.debug(f"Value: {x}")

# ✅ DO: Remove before committing
# Use version control to track breakpoints

# ✅ DO: Use conditional breakpoints
if condition:
    breakpoint()

# ✅ DO: Use logging for production
try:
    operation()
except Exception as e:
    logging.exception("Operation failed")
```

## Debugging Techniques

### Inspect Call Stack

```python
def level3():
    breakpoint()

def level2():
    level3()

def level1():
    level2()

level1()

# At breakpoint:
# (Pdb) bt  # Backtrace - show call stack
# > /path/file.py:2in level3()
# > /path/file.py:5in level2()
# > /path/file.py:8in level1()
# > /path/file.py:11in <module>()
```

### Watch Variables

```python
def process_list(items):
    total = 0
    for i, item in enumerate(items):
        total += item
        if total > 10:
            breakpoint()  # When threshold reached
            # (Pdb) total
            # (Pdb) i, item
            # (Pdb) pp items

process_list([1, 2, 3, 4, 5, 6])
```

### Execute Code in Debugger

```python
def debug_example():
    x = 10
    y = 20
    breakpoint()
    # At (Pdb), you can:
    # (Pdb) z = x + y
    # (Pdb) z
    # 30
    # (Pdb) import json
    # (Pdb) json.dumps({'x': x})

debug_example()
```

## Related Modules

- [pdb Module](../stdlib/pdb.md) - Python debugger
- [sys Module](../stdlib/sys.md) - System functions (breakpointhook)
- [logging Module](../stdlib/logging.md) - Production debugging
