# Python Exceptions

Complete reference for Python's built-in exception hierarchy, including all exception classes, warnings, and best practices for exception handling.

## Exception Hierarchy

### Complete Exception Tree

```
BaseException (O(1) to raise and catch)
├── SystemExit - Program exit (exit code)
├── KeyboardInterrupt - User interrupt (Ctrl+C)
├── GeneratorExit - Generator cleanup
└── Exception (base for most exceptions)
    ├── ArithmeticError
    │   ├── FloatingPointError - Float operation error
    │   ├── OverflowError - Number too large
    │   └── ZeroDivisionError - Division by zero
    ├── AssertionError - Assertion failed
    ├── AttributeError - Attribute not found
    ├── BufferError - Buffer operation failed
    ├── EOFError - End of file reached
    ├── ExceptionGroup - Multiple exceptions
    ├── ImportError
    │   └── ModuleNotFoundError - Module not found
    ├── LookupError
    │   ├── IndexError - Index out of range
    │   └── KeyError - Key not found
    ├── MemoryError - Out of memory
    ├── NameError
    │   └── UnboundLocalError - Local variable not bound
    ├── OSError (IO-related)
    │   ├── FileNotFoundError - File not found
    │   ├── FileExistsError - File exists
    │   ├── IsADirectoryError - Is directory
    │   ├── NotADirectoryError - Not a directory
    │   ├── PermissionError - Permission denied
    │   ├── ProcessLookupError - Process not found
    │   ├── TimeoutError - Operation timeout
    │   ├── InterruptedError - Interrupted
    │   ├── BlockingIOError - Blocking operation
    │   ├── ChildProcessError - Child process error
    │   ├── BrokenPipeError - Broken pipe
    │   ├── ConnectionError - Connection error
    │   │   ├── BrokenPipeError
    │   │   ├── ConnectionAbortedError
    │   │   ├── ConnectionRefusedError
    │   │   └── ConnectionResetError
    │   ├── EnvironmentError - Environment error
    │   └── IOError - I/O error
    ├── ReferenceError - Weak reference deleted
    ├── RuntimeError - Generic runtime error
    ├── RecursionError - Max recursion exceeded
    ├── StopIteration - Iterator exhausted
    ├── StopAsyncIteration - Async iterator exhausted
    ├── SyntaxError
    │   ├── IndentationError - Indentation error
    │   └── TabError - Tab/space mixing
    ├── SystemError - Internal interpreter error
    ├── TypeError - Wrong type
    ├── ValueError - Wrong value
    │   └── UnicodeError
    │       ├── UnicodeDecodeError - Decode failed
    │       ├── UnicodeEncodeError - Encode failed
    │       └── UnicodeTranslateError - Translate failed
    ├── NotImplementedError - Not implemented
    └── Warning (warnings don't stop execution)
        ├── DeprecationWarning - Feature deprecated
        ├── PendingDeprecationWarning - Future deprecation
        ├── FutureWarning - Future language change
        ├── UserWarning - User code warning
        ├── SyntaxWarning - Syntax warning
        ├── RuntimeWarning - Runtime issue
        ├── ImportWarning - Import issue
        ├── UnicodeWarning - Unicode issue
        ├── BytesWarning - Bytes issue
        ├── EncodingWarning - Encoding issue
        └── ResourceWarning - Resource issue
```

## Core Exception Reference

### Base Exceptions - Time: O(1)

#### `BaseException`
Root of all exceptions. Don't catch this - catch `Exception` instead.

```python
# ❌ DON'T: Catch BaseException
try:
    code()
except BaseException:
    pass  # Catches KeyboardInterrupt, SystemExit, etc!

# ✅ DO: Catch Exception
try:
    code()
except Exception:
    pass  # Safer - lets SystemExit, KeyboardInterrupt through
```

#### `SystemExit` - Program Exit
Raised by `sys.exit()`. Not caught by `except Exception`.

```python
import sys

try:
    sys.exit(1)
except SystemExit as e:
    print(f"Exit code: {e.code}")  # 1
```

#### `KeyboardInterrupt` - User Interrupt
Raised by Ctrl+C. Not caught by `except Exception`.

```python
try:
    while True:
        process()
except KeyboardInterrupt:
    print("User cancelled")
    sys.exit(0)
```

#### `GeneratorExit` - Generator Cleanup
Raised when generator is closed.

```python
def my_generator():
    try:
        yield 1
        yield 2
    except GeneratorExit:
        print("Cleaning up")
        raise  # Must re-raise

gen = my_generator()
next(gen)  # Get 1
gen.close()  # Triggers GeneratorExit
```

### Arithmetic Errors - Time: O(1)

#### `ZeroDivisionError` - Division by Zero
```python
try:
    result = 10 / 0
except ZeroDivisionError:
    print("Cannot divide by zero")
```

#### `FloatingPointError` - Float Operation Error
```python
import warnings
warnings.simplefilter("error", FloatingPointError)

try:
    result = float('inf') - float('inf')  # NaN
except FloatingPointError:
    print("Invalid float operation")
```

#### `OverflowError` - Number Too Large
```python
import sys

try:
    large = sys.maxsize + 1
    power = 10 ** 1000000  # May overflow in some contexts
except OverflowError:
    print("Number too large")
```

#### `ArithmeticError` - Base Arithmetic Error
Parent class for arithmetic errors.

```python
try:
    result = 10 / 0
except ArithmeticError as e:
    print(f"Arithmetic: {type(e).__name__}")
```

### Lookup Errors - Time: O(1)

#### `KeyError` - Dictionary Key Not Found
```python
data = {'a': 1, 'b': 2}

try:
    value = data['c']  # Key doesn't exist
except KeyError as e:
    print(f"Key not found: {e}")
```

#### `IndexError` - Index Out of Range
```python
items = [1, 2, 3]

try:
    item = items[10]  # Index too large
except IndexError:
    print("Index out of range")
```

#### `LookupError` - Base Lookup Error
Parent class for KeyError and IndexError.

```python
try:
    data = [1, 2, 3]
    value = data[99]
except LookupError:
    print("Item not found")
```

### Type and Value Errors - Time: O(1)

#### `TypeError` - Wrong Type
```python
try:
    result = "string" + 5  # Can't add str + int
except TypeError:
    print("Type mismatch")
```

#### `ValueError` - Wrong Value
```python
try:
    number = int("not a number")
except ValueError:
    print("Invalid value")
```

#### `AttributeError` - Attribute Not Found
```python
class MyClass:
    def __init__(self):
        self.x = 1

obj = MyClass()

try:
    value = obj.y  # Attribute doesn't exist
except AttributeError:
    print("Attribute not found")
```

#### `NameError` - Name Not Found
```python
try:
    print(undefined_variable)
except NameError:
    print("Name not defined")
```

#### `UnboundLocalError` - Local Variable Not Bound
Subclass of NameError. Raised when referencing local variable before assignment.

```python
def func():
    try:
        print(x)  # x referenced before assignment
        x = 5
    except UnboundLocalError:
        print("Local variable not bound")

func()
```

### Unicode Errors - Time: O(n) where n = string length

#### `UnicodeError` - Unicode Problem
Base class for unicode errors.

```python
try:
    bytes_data = b'\x80\x81'
    text = bytes_data.decode('ascii')
except UnicodeError:
    print("Unicode problem")
```

#### `UnicodeDecodeError` - Decoding Failed
```python
try:
    bytes_data = b'\xff\xfe'
    text = bytes_data.decode('utf-8')
except UnicodeDecodeError as e:
    print(f"Can't decode: {e.reason}")
```

#### `UnicodeEncodeError` - Encoding Failed
```python
try:
    text = "Hello 世界"
    bytes_data = text.encode('ascii')  # Can't encode Chinese
except UnicodeEncodeError as e:
    print(f"Can't encode: {e.reason}")
```

#### `UnicodeTranslateError` - Translation Failed
```python
# Raised during str.translate() with invalid mapping
try:
    text = "hello"
    result = text.translate({0: "x"})  # Bad mapping
except UnicodeTranslateError:
    print("Translation failed")
```

### I/O and OS Errors - Time: O(1)

#### `OSError` - Operating System Error
Base class for OS-related errors. Includes all file/network errors.

```python
try:
    with open("nonexistent.txt") as f:
        data = f.read()
except OSError as e:
    print(f"OS error: {e}")
```

#### `FileNotFoundError` - File Not Found
```python
try:
    with open("missing.txt") as f:
        content = f.read()
except FileNotFoundError:
    print("File not found")
```

#### `FileExistsError` - File Already Exists
```python
import os

try:
    os.makedirs("existing_dir")
except FileExistsError:
    print("Directory already exists")
```

#### `IsADirectoryError` - Expected File, Got Directory
```python
try:
    with open("/tmp") as f:  # /tmp is a directory
        data = f.read()
except IsADirectoryError:
    print("Path is a directory")
```

#### `NotADirectoryError` - Expected Directory, Got File
```python
try:
    os.listdir("file.txt")  # file.txt is a file, not directory
except NotADirectoryError:
    print("Path is not a directory")
```

#### `PermissionError` - Permission Denied
```python
try:
    with open("/root/secret.txt") as f:
        data = f.read()
except PermissionError:
    print("Permission denied")
```

#### `TimeoutError` - Operation Timeout
```python
import socket

try:
    socket.create_connection(("example.com", 80), timeout=0.001)
except TimeoutError:
    print("Connection timeout")
```

#### `BlockingIOError` - Operation Would Block
```python
import os

try:
    os.set_blocking(fd, False)
    os.read(fd, 1024)
except BlockingIOError:
    print("Would block")
```

#### `InterruptedError` - Operation Interrupted
```python
try:
    # Interrupted system call
    result = os.read(fd, 1024)
except InterruptedError:
    print("Operation interrupted")
```

#### `ChildProcessError` - Child Process Error
```python
try:
    os.waitpid(-1, 0)  # No child processes
except ChildProcessError:
    print("No child process")
```

#### `BrokenPipeError` - Broken Pipe
```python
import socket

try:
    socket.send(data)  # Pipe/socket closed
except BrokenPipeError:
    print("Pipe broken")
```

#### `ConnectionError` - Connection Error
Base class for connection errors.

```python
try:
    socket.connect(("unreachable.host", 80))
except ConnectionError:
    print("Connection failed")
```

#### `ConnectionRefusedError` - Connection Refused
```python
try:
    socket.connect(("localhost", 12345))  # No server listening
except ConnectionRefusedError:
    print("Server refused connection")
```

#### `ConnectionAbortedError` - Connection Aborted
```python
try:
    socket.recv(1024)  # Connection aborted
except ConnectionAbortedError:
    print("Connection aborted")
```

#### `ConnectionResetError` - Connection Reset
```python
try:
    socket.send(data)  # Peer reset connection
except ConnectionResetError:
    print("Connection reset")
```

#### `ProcessLookupError` - Process Not Found
```python
import os

try:
    os.kill(999999, signal.SIGTERM)  # PID doesn't exist
except ProcessLookupError:
    print("Process not found")
```

#### `EnvironmentError` - Environment Error
Old name for OSError. Still exists for compatibility.

```python
try:
    file_operation()
except EnvironmentError:  # Same as OSError
    print("Environment error")
```

#### `IOError` - I/O Error
Old name for OSError. Still exists for compatibility.

```python
try:
    with open("file.txt") as f:
        data = f.read()
except IOError:  # Same as OSError
    print("I/O error")
```

#### `EOFError` - End of File
```python
try:
    value = input()  # User sends EOF (Ctrl+D)
except EOFError:
    print("End of input")
```

### Import Errors - Time: O(n) where n = import chain

#### `ImportError` - Import Failed
```python
try:
    import nonexistent_module
except ImportError:
    print("Cannot import module")
```

#### `ModuleNotFoundError` - Module Not Found
Subclass of ImportError. More specific error.

```python
try:
    import pandas
except ModuleNotFoundError:
    print("Module not installed")
```

### Iteration Errors - Time: O(1)

#### `StopIteration` - Iterator Exhausted
Raised when iterator has no more items.

```python
iterator = iter([1, 2, 3])

try:
    while True:
        value = next(iterator)
        print(value)
except StopIteration:
    print("Iterator exhausted")
```

#### `StopAsyncIteration` - Async Iterator Exhausted
```python
async def async_iter():
    for i in range(3):
        yield i
    # Implicitly raises StopAsyncIteration

async def main():
    async_gen = async_iter()
    try:
        while True:
            value = await async_gen.__anext__()
            print(value)
    except StopAsyncIteration:
        print("Async iterator exhausted")
```

### Reference and Memory Errors - Time: O(1)

#### `ReferenceError` - Weak Reference Deleted
```python
import weakref

class MyClass:
    pass

obj = MyClass()
weak_ref = weakref.ref(obj)

del obj  # Delete original object

try:
    obj_again = weak_ref()
    if obj_again is None:
        raise ReferenceError("Object was garbage collected")
except ReferenceError:
    print("Weak reference no longer valid")
```

#### `MemoryError` - Out of Memory
```python
try:
    huge_list = [0] * (10 ** 100)  # Impossible to allocate
except MemoryError:
    print("Out of memory")
```

### System Errors - Time: O(1)

#### `RuntimeError` - Generic Runtime Error
Catch-all for runtime problems.

```python
def risky_operation():
    raise RuntimeError("Something went wrong")

try:
    risky_operation()
except RuntimeError:
    print("Runtime error occurred")
```

#### `RecursionError` - Max Recursion Exceeded
```python
import sys

def infinite_recursion():
    return infinite_recursion()

try:
    infinite_recursion()
except RecursionError:
    print(f"Max recursion depth: {sys.getrecursionlimit()}")
```

#### `SystemError` - Internal Interpreter Error
Indicates Python interpreter bug.

```python
# Very rare - indicates CPython bug
try:
    pass  # SystemError won't normally occur
except SystemError:
    print("Python interpreter error - report as bug!")
```

#### `BufferError` - Buffer Operation Failed
```python
try:
    memoryview(5)  # Can't create memoryview of int
except BufferError:
    print("Invalid buffer operation")
```

### Syntax and Assertion Errors - Time: O(1)

#### `SyntaxError` - Syntax Error
Raised at parse time for invalid syntax.

```python
try:
    compile("if True", "<string>", "exec")  # Missing colon
except SyntaxError as e:
    print(f"Syntax error: {e.msg} at line {e.lineno}")
```

#### `IndentationError` - Indentation Error
Subclass of SyntaxError for indentation issues.

```python
try:
    compile("if True:\npass", "<string>", "exec")  # Bad indent
except IndentationError:
    print("Indentation error")
```

#### `TabError` - Tab/Space Mixing
Subclass of IndentationError. Mixing tabs and spaces.

```python
try:
    compile("if True:\n\tpass\n    pass", "<string>", "exec")
except TabError:
    print("Mixed tabs and spaces")
```

#### `AssertionError` - Assertion Failed
```python
try:
    assert False, "Assertion message"
except AssertionError as e:
    print(f"Assertion failed: {e}")
```

#### `NotImplementedError` - Not Implemented
```python
class Base:
    def operation(self):
        raise NotImplementedError("Subclasses must implement")

class Derived(Base):
    def operation(self):
        return "implemented"

try:
    Base().operation()
except NotImplementedError:
    print("Method not implemented")
```

### Exception Groups - Time: O(n) where n = exceptions

#### `ExceptionGroup` - Multiple Exceptions
```python
try:
    raise ExceptionGroup("Multiple errors", [
        ValueError("Error 1"),
        TypeError("Error 2"),
    ])
except ExceptionGroup as eg:
    for exc in eg.exceptions:
        print(f"- {type(exc).__name__}: {exc}")
```

#### `BaseExceptionGroup` - Base Exception Group
```python
try:
    raise BaseExceptionGroup("Critical errors", [
        SystemExit(1),
        KeyboardInterrupt(),
    ])
except BaseExceptionGroup as eg:
    print(f"Multiple critical errors: {len(eg.exceptions)}")
```

## Warning Classes - Time: O(1) to raise

Warnings don't stop execution unless converted to errors.

### Common Warnings

```python
import warnings

# DeprecationWarning - Feature deprecated
warnings.warn("Use new_func() instead", DeprecationWarning)

# PendingDeprecationWarning - Future deprecation
warnings.warn("Will be removed in 3.15", PendingDeprecationWarning)

# FutureWarning - Language change coming
warnings.warn("Behavior will change in Python 4.0", FutureWarning)

# UserWarning - User-issued warning (default)
warnings.warn("Check your input data")

# SyntaxWarning - Syntax issue
warnings.warn("Ambiguous syntax", SyntaxWarning)

# RuntimeWarning - Runtime issue
warnings.warn("Unusual runtime condition", RuntimeWarning)

# ImportWarning - Import issue
warnings.warn("Can't import module", ImportWarning)

# UnicodeWarning - Unicode issue
warnings.warn("Unicode handling", UnicodeWarning)

# BytesWarning - Bytes issue
warnings.warn("Bytes behavior issue", BytesWarning)

# EncodingWarning - Encoding assumption
warnings.warn("Encoding not specified", EncodingWarning)

# ResourceWarning - Resource leak
warnings.warn("Resource not closed", ResourceWarning)
```

### Converting Warnings to Errors

```python
import warnings

# Make DeprecationWarning raise an error
warnings.filterwarnings("error", category=DeprecationWarning)

try:
    warnings.warn("Deprecated", DeprecationWarning)
except DeprecationWarning:
    print("Caught as error")
```

## Exception Handling Best Practices

### Catch Specific Exceptions - Time: O(1)

```python
# ✅ DO: Catch specific exceptions
try:
    data = json.loads(user_input)
except json.JSONDecodeError:
    print("Invalid JSON")
except ValueError:
    print("Invalid value")

# ❌ DON'T: Catch Exception or BaseException
try:
    data = json.loads(user_input)
except:  # Catches everything including KeyboardInterrupt!
    print("Error")
```

### Use Exception Chaining - Time: O(1)

```python
try:
    result = 10 / 0
except ZeroDivisionError as e:
    # Preserve original exception
    raise ValueError("Invalid calculation") from e
```

### Custom Exception Hierarchy - Time: O(1)

```python
class AppError(Exception):
    """Base exception for app"""
    pass

class ValidationError(AppError):
    """Validation failed"""
    pass

class DatabaseError(AppError):
    """Database operation failed"""
    pass

try:
    validate_data(user_input)
except ValidationError:
    print("Validation failed")
except DatabaseError:
    print("Database error")
except AppError:
    print("Application error")
```

### Finally Block - Time: O(1)

```python
try:
    resource = acquire_resource()
    use_resource(resource)
except Exception as e:
    print(f"Error: {e}")
else:
    print("Success")
finally:
    # Always executes
    cleanup_resource(resource)
```

### Context Managers - Time: O(1)

```python
# ✅ Preferred: Context managers handle cleanup
with open("file.txt") as f:
    data = f.read()
# File automatically closed, even if error occurs
```

## Exception Information - Time: O(1)

```python
import traceback
import sys

try:
    result = 10 / 0
except ZeroDivisionError:
    # Get exception info
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    # Print traceback
    traceback.print_exc()
    
    # Get detailed traceback
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    print("".join(tb_lines))
    
    # Format current exception
    tb_str = traceback.format_exc()
    print(tb_str)
```

## Related Modules

- [warnings Module](../stdlib/warnings.md) - Warning filtering
- [traceback Module](../stdlib/traceback.md) - Traceback manipulation
- [sys Module](../stdlib/sys.md) - Exception info
