# Traceback Module

The `traceback` module provides utilities for extracting, formatting, and printing exception tracebacks.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `print_exc()` | O(n) | O(n) | n = traceback depth |
| `format_exc()` | O(n) | O(n) | Returns formatted string |
| `extract_tb()` | O(n) | O(n) | Extracts traceback frames |
| `format_tb()` | O(n) | O(n) | Formats traceback list |
| `print_tb()` | O(n) | O(1) | Prints to file |
| `clear_frames()` | O(n) | O(1) | n = frame count |

## Common Operations

### Printing Exceptions

```python
import traceback
import sys

try:
    1 / 0
except ZeroDivisionError:
    # O(n) time, O(n) space where n = traceback depth
    traceback.print_exc()
    
    # Get as string instead - O(n) time/space
    error_str = traceback.format_exc()
    print(error_str)
    
    # Print just the exception - O(1) time/space
    traceback.print_exception(type, value, traceback)
```

### Extracting Traceback Information

```python
import traceback
import sys

try:
    def level_3():
        return 1 / 0
    
    def level_2():
        return level_3()
    
    def level_1():
        return level_2()
    
    level_1()
except:
    # O(n) where n = depth of call stack
    tb_list = traceback.extract_tb(sys.exc_info()[2])
    
    # Each frame: FrameSummary with filename, lineno, name, line
    for frame in tb_list:
        print(f"{frame.filename}:{frame.lineno} in {frame.name}")
        print(f"  {frame.line}")
```

### Formatting Tracebacks

```python
import traceback
import sys

try:
    x = undefined_variable
except NameError:
    # Get all lines of formatted traceback - O(n) time/space
    formatted = traceback.format_tb(sys.exc_info()[2])
    
    # Each line is a string
    for line in formatted:
        print(repr(line))
    
    # Or get entire formatted exception - O(n) time/space
    exc_type, exc_value, exc_tb = sys.exc_info()
    full_format = traceback.format_exception(exc_type, exc_value, exc_tb)
```

### Stack Traces (Current Execution)

```python
import traceback

def function_a():
    function_b()

def function_b():
    function_c()

def function_c():
    # Print current call stack - O(n) time/space
    traceback.print_stack()
    
    # Get as formatted list - O(n) time/space  
    stack = traceback.format_stack()
```

## Performance Tips

### Use format_exc() for Logging

```python
import traceback

try:
    risky_operation()
except Exception:
    # Good: Get string once - O(n) time/space
    error_details = traceback.format_exc()
    logger.error(error_details)
```

### Clear Frames to Release Memory

```python
import traceback
import sys

try:
    problematic_code()
except:
    exc_info = sys.exc_info()
    # Extract what you need first - O(n) time/space
    tb_list = traceback.extract_tb(exc_info[2])
    
    # Clear traceback to break reference cycles - O(n) time
    traceback.clear_frames(exc_info[2])
    # Or: exc_info = (None, None, None)
```

### Limit Traceback Depth for Large Stacks

```python
import traceback
import sys

try:
    deeply_nested()
except:
    exc_type, exc_value, exc_tb = sys.exc_info()
    
    # O(n) where n = depth, limited to 10 frames
    formatted = traceback.format_exception(
        exc_type, exc_value, exc_tb, limit=10
    )
```

## Version Notes

- **Python 2.6+**: Basic functionality available
- **Python 3.5+**: `walk_tb()` for iterating tracebacks
- **Python 3.10+**: Various improvements
- **Python 3.13+**: Enhanced error messages

## Related Documentation

- [Exceptions Guide](builtins/exceptions.md) - Exception types
- [Sys Module](sys.md) - sys.exc_info()
- [Logging Module](logging.md) - Logging tracebacks
