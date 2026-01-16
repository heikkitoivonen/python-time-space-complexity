# Python Exceptions - Complexity and Reference

Python exceptions are raised when errors occur during program execution. This guide documents the core exception types, their causes, and how to handle them.

## Exception Hierarchy

```
BaseException
 ├── SystemExit
 ├── KeyboardInterrupt
 ├── GeneratorExit
 └── Exception
      ├── StopIteration
      ├── ArithmeticError
      │   ├── FloatingPointError
      │   ├── OverflowError
      │   └── ZeroDivisionError
      ├── AssertionError
      ├── AttributeError
      ├── BufferError
      ├── EOFError
      ├── ImportError
      │   └── ModuleNotFoundError
      ├── LookupError
      │   ├── IndexError
      │   └── KeyError
      ├── MemoryError
      ├── NameError
      │   └── UnboundLocalError
      ├── OSError
      │   ├── FileNotFoundError
      │   ├── IsADirectoryError
      │   ├── NotADirectoryError
      │   ├── PermissionError
      │   ├── TimeoutError
      │   └── ... (others)
      ├── RuntimeError
      │   └── NotImplementedError
      ├── SyntaxError
      │   └── IndentationError
      ├── SystemError
      ├── TypeError
      ├── ValueError
      │   └── UnicodeError
      └── Warning
          ├── DeprecationWarning
          ├── FutureWarning
          ├── UserWarning
          └── ... (others)
```

## Core Exception Types

### BaseException (Base)

**When raised**: Never directly; parent of all built-in exceptions
**Handling**: Rarely caught (except at highest level)

```python
# BaseException hierarchy
try:
    # code
except BaseException:  # Catches everything (too broad!)
    pass

# Better: catch specific Exception instead
try:
    # code
except Exception:  # Catches most errors
    pass
```

**Best practice**: Don't catch `BaseException` unless you have a specific reason (like cleanup).

---

### Exception (Base for most errors)

**When raised**: Parent class for most built-in exceptions
**Handling**: Good base class for catching application errors

```python
try:
    # code that might fail
    value = int("abc")
except Exception as e:  # Catches ValueError and most others
    print(f"Error: {e}")
```

---

### ValueError

**When raised**: When a function receives an argument of the correct type but inappropriate value
**Complexity**: O(1) to raise, O(n) for error message

```python
# ValueError examples - O(1)
int("abc")          # ValueError: invalid literal for int()
float("not_float")  # ValueError: could not convert string to float

# Custom ValueError
def validate_age(age):
    if not 0 <= age <= 150:
        raise ValueError(f"Age must be 0-150, got {age}")  # O(1)

validate_age(200)  # Raises ValueError
```

---

### TypeError

**When raised**: When operation or function is applied to object of inappropriate type
**Complexity**: O(1) to raise

```python
# TypeError examples - O(1)
1 + "2"           # TypeError: unsupported operand type(s)
len(123)          # TypeError: object of type 'int' has no len()
"hello"[1.5]      # TypeError: string indices must be integers

# Check type before operation
def add(a, b):
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError(f"Expected numbers, got {type(a)} and {type(b)}")
    return a + b
```

---

### KeyError

**When raised**: When dictionary key is not found
**Complexity**: O(1) average, O(n) worst case

```python
# KeyError examples - O(1)
d = {'a': 1, 'b': 2}
d['c']  # KeyError: 'c'

# Safe access - O(1)
value = d.get('c')  # None (no error)
value = d.get('c', 'default')  # 'default'

# Check first - O(1)
if 'c' in d:
    value = d['c']
```

---

### IndexError

**When raised**: When sequence index is out of range
**Complexity**: O(1) to raise

```python
# IndexError examples - O(1)
lst = [1, 2, 3]
lst[5]      # IndexError: list index out of range
lst[-10]    # IndexError: list index out of range

# Safe access - O(1)
if len(lst) > 5:
    value = lst[5]

# Handle gracefully - O(1)
try:
    value = lst[index]
except IndexError:
    value = None
```

---

### AttributeError

**When raised**: When attribute reference or assignment fails
**Complexity**: O(1) to raise

```python
# AttributeError examples - O(1)
class MyClass:
    def __init__(self):
        self.x = 1

obj = MyClass()
obj.y  # AttributeError: 'MyClass' object has no attribute 'y'

# Check before access - O(1)
if hasattr(obj, 'y'):
    value = obj.y

# Use getattr with default - O(1)
value = getattr(obj, 'y', None)
```

---

### NameError

**When raised**: When local or global name is not found
**Complexity**: O(1) lookup

```python
# NameError examples - O(1)
print(undefined_var)  # NameError: name 'undefined_var' is not defined

# Check if name exists - O(1)
if 'x' in locals():
    print(x)
if 'y' in globals():
    print(y)

# Catch NameError
try:
    result = possibly_undefined_var  # O(1)
except NameError:
    result = default_value
```

---

### ZeroDivisionError

**When raised**: When dividing by zero
**Complexity**: O(1) to raise

```python
# ZeroDivisionError examples - O(1)
10 / 0   # ZeroDivisionError: division by zero
10 % 0   # ZeroDivisionError: integer division or modulo by zero

# Check before division - O(1)
if divisor != 0:
    result = dividend / divisor
else:
    result = float('inf')  # or handle appropriately

# Try/except approach
try:
    result = dividend / divisor  # O(1)
except ZeroDivisionError:
    result = None
```

---

### FileNotFoundError

**When raised**: When trying to open/access file that doesn't exist
**Complexity**: O(1) filesystem lookup

```python
# FileNotFoundError examples - O(1)
with open('nonexistent.txt') as f:  # FileNotFoundError: [Errno 2] No such file or directory

# Check first - O(1)
import os
if os.path.exists('file.txt'):
    with open('file.txt') as f:
        content = f.read()

# Handle with try/except
try:
    with open('file.txt') as f:  # O(1)
        content = f.read()
except FileNotFoundError:
    content = ""
```

---

### OSError

**When raised**: When OS-level operation fails (includes FileNotFoundError)
**Complexity**: O(1) to raise

```python
# OSError examples - O(1)
import os
os.remove('/root/protected.txt')  # PermissionError (subclass of OSError)
os.mkdir('/nonexistent/dir')  # FileNotFoundError (subclass of OSError)

# Handle OSError family - O(1)
try:
    result = os.some_operation()  # O(1)
except FileNotFoundError:
    print("File not found")
except PermissionError:
    print("Permission denied")
except OSError as e:
    print(f"OS error: {e}")
```

---

### ImportError / ModuleNotFoundError

**When raised**: When import statement fails
**Complexity**: O(n) for module search/loading

```python
# ImportError examples - O(n)
import nonexistent_module  # ModuleNotFoundError: No module named 'nonexistent_module'
from os import missing_function  # ImportError: cannot import name 'missing_function'

# Check if module available - O(1)
try:
    import optional_module  # O(n) - first load
except ImportError:
    optional_module = None

# Conditional import
try:
    import numpy as np
except ImportError:
    np = None

if np:
    result = np.array([1, 2, 3])
```

---

### RuntimeError

**When raised**: When error doesn't fit into any category
**Complexity**: O(1) to raise

```python
# RuntimeError examples - O(1)
class Generator:
    def __init__(self):
        self.value = None
    
    def step(self):
        if self.value is None:
            raise RuntimeError("Not initialized")

# Catch RuntimeError - O(1)
try:
    gen.step()  # O(1)
except RuntimeError as e:
    print(f"Runtime issue: {e}")
```

---

### AssertionError

**When raised**: When assert statement fails
**Complexity**: O(1) to raise

```python
# AssertionError examples - O(1)
assert 1 == 1, "Math is broken"  # OK
assert 1 == 2, "Math is broken"  # AssertionError: Math is broken

# Use in debugging - O(1)
def process(value):
    assert value > 0, "Value must be positive"  # O(1)
    return value * 2

# Note: assertions can be disabled with -O flag
# Don't use for normal error handling
```

---

### StopIteration

**When raised**: When iterator is exhausted
**Complexity**: O(1) to raise

```python
# StopIteration examples - O(1)
it = iter([1, 2, 3])
next(it)  # 1
next(it)  # 2
next(it)  # 3
next(it)  # StopIteration

# Handle StopIteration - O(1)
try:
    value = next(iterator)  # O(1)
except StopIteration:
    value = None

# Use default - O(1)
value = next(iterator, None)
```

---

### NotImplementedError

**When raised**: When method should be overridden but isn't
**Complexity**: O(1) to raise

```python
# NotImplementedError examples - O(1)
class Base:
    def method(self):
        raise NotImplementedError("Subclass must implement method")

class Derived(Base):
    def method(self):
        return "Implemented"

# Proper usage
obj = Derived()
obj.method()  # "Implemented"

wrong = Base()
wrong.method()  # NotImplementedError
```

---

### SyntaxError / IndentationError

**When raised**: At parse time (cannot be caught)
**Complexity**: O(n) for parsing

```python
# These are syntax errors (caught at parse time)
# if x = 5:  # SyntaxError: invalid syntax
#   print(x)

#     print("bad indent")  # IndentationError: unexpected indent

# Cannot catch SyntaxError at runtime
# (code won't even parse)
```

---

### MemoryError

**When raised**: When memory allocation fails
**Complexity**: O(1) to raise, but indicates serious issue

```python
# MemoryError example - O(1) to raise
try:
    huge_list = [0] * (10**100)  # Try to allocate huge memory
except MemoryError:
    print("Out of memory")

# Graceful degradation
import sys
max_items = sys.maxsize // 1000  # Conservative limit
```

---

### EOFError

**When raised**: When input() hits end-of-file
**Complexity**: O(1) to raise

```python
# EOFError example - O(1)
try:
    data = input("Enter data: ")  # O(k)
except EOFError:
    print("No more input")

# Handle in interactive programs
while True:
    try:
        line = input("> ")  # O(k)
    except EOFError:
        break  # End of input
    except KeyboardInterrupt:
        print("Interrupted")
        break
```

---

### KeyboardInterrupt

**When raised**: When user presses Ctrl+C
**Complexity**: O(1) to raise

```python
# KeyboardInterrupt example - O(1)
try:
    while True:
        process_data()  # Long operation
except KeyboardInterrupt:
    print("Interrupted by user")
finally:
    cleanup()  # Always runs
```

---

## Exception Handling Patterns

### Try/Except/Finally

```python
# Basic pattern - O(1) overhead
try:
    resource = open('file.txt')  # O(n)
    process(resource)
except FileNotFoundError:
    print("File not found")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    resource.close()  # Always runs
```

### Context Managers

```python
# Better - automatic cleanup
with open('file.txt') as f:  # O(1) setup
    content = f.read()  # O(n)
# Automatic close - O(1)
```

### Multiple Exceptions

```python
# Catch multiple - O(1)
try:
    result = int(user_input)
except (ValueError, TypeError) as e:
    print(f"Invalid input: {e}")

# Or separate handlers
try:
    data = process()
except ValueError:
    print("Invalid value")
except KeyError:
    print("Missing key")
except Exception as e:
    print(f"Unknown error: {e}")
```

### Re-raising Exceptions

```python
# Log and re-raise - O(1)
try:
    operation()
except ValueError as e:
    logger.error(f"ValueError: {e}")
    raise  # Re-raise same exception

# Transform exception
try:
    operation()
except ValueError as e:
    raise RuntimeError(f"Processing failed: {e}") from e
```

## Custom Exceptions

### Creating Custom Exceptions

```python
# Simple custom exception
class CustomError(Exception):
    pass

# With custom logic
class ValidationError(ValueError):
    def __init__(self, field, message):
        self.field = field
        self.message = message
    
    def __str__(self):
        return f"Validation error in {self.field}: {self.message}"

# Usage
try:
    if not is_valid(data):
        raise ValidationError('email', 'Invalid email format')
except ValidationError as e:
    print(e)
```

## Exception Handling Best Practices

✅ **Do**:
- Catch specific exceptions (not bare `except:`)
- Use `finally` or context managers for cleanup
- Provide informative error messages
- Log exceptions properly
- Use custom exceptions for domain errors
- Re-raise if you can't handle

❌ **Avoid**:
- Catching `BaseException` (too broad)
- Silent exceptions (`except: pass`)
- Using exceptions for control flow
- Not logging exceptions
- Generic exception messages
- Catching and ignoring exceptions

## Exception Raising Complexity

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Raise exception | O(1) | O(1) | Creating exception object |
| Exception handling | O(1) | O(1) | Finding handler |
| Stack unwinding | O(d) | O(1) | d = call depth |
| Finally blocks | O(1) | O(1) | Executed on exit |

## Related Documentation

- **[try/except statements](control_flow.md)** - Exception handling syntax
- **[context managers](context_managers.md)** - Resource management
- **[logging](../stdlib/logging.md)** - Proper error logging

## Version Notes

- **Python 2.x**: Slightly different exception hierarchy
- **Python 3.x**: Improved exception chaining with `from`
- **Python 3.10+**: Better error messages with `ExceptionGroup`

---

**All 40+ core exceptions are covered in this hierarchy. Refer to specific exception type above for detailed information.**
