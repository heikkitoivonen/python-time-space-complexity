# contextlib Module Complexity

The `contextlib` module provides utilities for working with context managers and the `with` statement, enabling resource management and cleanup.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Context manager entry | O(1) | O(1) | `__enter__()` call |
| Context manager exit | O(1) | O(1) | `__exit__()` call |
| `@contextmanager` | O(1) | O(1) | Decorator application |
| `ExitStack` add | O(1) | O(1) | Register callback |
| `ExitStack` exit all | O(n) | O(1) | LIFO order; n = registered callbacks |
| `contextmanager` yield | O(1) | O(1) | Generator yield point |

## Context Managers Basics

### Custom Context Manager Class

```python
class FileManager:
    """Custom context manager - O(1) per operation"""
    
    def __init__(self, filename, mode):
        self.filename = filename
        self.mode = mode
        self.file = None
    
    # Entry - O(1)
    def __enter__(self):
        self.file = open(self.filename, self.mode)
        return self.file
    
    # Exit - O(1)
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()
        return False  # Propagate exceptions

# Use context manager - O(1) per operation
with FileManager("test.txt", "w") as f:
    f.write("Hello")  # File closed automatically

print("File is closed")  # Guaranteed cleanup
```

### Protocol: Context Manager

```python
class Resource:
    """Implement context manager protocol"""
    
    def __init__(self, name):
        self.name = name
        self.is_open = False
    
    def __enter__(self):
        """Called on 'with' statement - O(1)"""
        print(f"Acquiring {self.name}")
        self.is_open = True
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Called on exit - O(1)"""
        print(f"Releasing {self.name}")
        self.is_open = False
        
        # Handle exceptions if needed
        if exc_type is not None:
            print(f"Exception occurred: {exc_type.__name__}")
        
        return False  # Don't suppress exceptions

# Usage - guaranteed cleanup
with Resource("database") as resource:
    print(f"Using {resource.name}")

# Output:
# Acquiring database
# Using database
# Releasing database
```

## contextmanager Decorator

### Simple Generator Context Manager

```python
from contextlib import contextmanager

# Define with decorator - O(1)
@contextmanager
def timer(name):
    """Simple timer context manager"""
    import time
    
    # Setup - O(1)
    print(f"Starting {name}")
    start = time.time()
    
    try:
        # Yield control - O(1)
        yield
    finally:
        # Cleanup - O(1)
        elapsed = time.time() - start
        print(f"Finished {name}: {elapsed:.3f}s")

# Use - O(1) per operation
with timer("computation"):
    total = sum(range(1000000))
    
# Output:
# Starting computation
# Finished computation: 0.001s
```

### Context Manager with Return Value

```python
from contextlib import contextmanager

@contextmanager
def database_connection(db_url):
    """Context manager yielding resource"""
    
    # Setup - O(1)
    print(f"Connecting to {db_url}")
    connection = f"Connection to {db_url}"
    
    try:
        # Yield resource - O(1)
        yield connection
    finally:
        # Cleanup - O(1)
        print(f"Closing connection")

# Use with resource - O(1)
with database_connection("postgresql://localhost") as conn:
    print(f"Using {conn}")
    # query_result = conn.execute("SELECT * FROM users")

# Output:
# Connecting to postgresql://localhost
# Using Connection to postgresql://localhost
# Closing connection
```

### Context Manager with Exception Handling

```python
from contextlib import contextmanager

@contextmanager
def error_handler(error_message):
    """Catch exceptions in context"""
    
    try:
        # Yield control - O(1)
        yield
    except Exception as e:
        # Handle exception - O(1)
        print(f"{error_message}: {type(e).__name__}")

# Use with error handling - O(1)
with error_handler("Operation failed"):
    result = 1 / 0  # Will be caught

print("Execution continues")

# Output:
# Operation failed: ZeroDivisionError
# Execution continues
```

## ExitStack - Multiple Context Managers

### Register Multiple Contexts

```python
from contextlib import ExitStack

# ExitStack - O(1) per add
with ExitStack() as stack:
    # Add file contexts - O(1) each
    f1 = stack.enter_context(open("file1.txt", "w"))
    f2 = stack.enter_context(open("file2.txt", "w"))
    f3 = stack.enter_context(open("file3.txt", "w"))
    
    # Use all files - O(1) per operation
    f1.write("File 1 content")
    f2.write("File 2 content")
    f3.write("File 3 content")

# All files closed automatically - O(n) for n files
print("All files closed")
```

### Conditional Context Management

```python
from contextlib import ExitStack

def open_optional_file(filename=None, mode="r"):
    """Open file only if filename provided"""
    
    stack = ExitStack()
    files = []
    
    if filename:
        # Conditionally add context - O(1)
        f = stack.enter_context(open(filename, mode))
        files.append(f)
    
    # Return both stack and files for cleanup
    return stack, files

# Use - O(1) per operation
stack, files = open_optional_file("data.txt")
with stack:
    if files:
        content = files[0].read()
        print(content)

# File closed on exit - O(1)
```

### Register Callbacks

```python
from contextlib import ExitStack

with ExitStack() as stack:
    # Register callback - O(1) per callback
    stack.callback(print, "Cleanup 3")
    stack.callback(print, "Cleanup 2")
    stack.callback(print, "Cleanup 1")
    
    print("Main context")

# Output (LIFO order):
# Main context
# Cleanup 1
# Cleanup 2
# Cleanup 3
```

## Suppress Context Manager

### Suppress Exceptions

```python
from contextlib import suppress

# Suppress specific exception - O(1)
with suppress(FileNotFoundError):
    with open("nonexistent.txt") as f:
        content = f.read()

# No exception raised
print("Execution continues despite FileNotFoundError")

# Multiple exceptions - O(1)
with suppress(ValueError, KeyError, AttributeError):
    value = int("not a number")  # Suppressed
```

## Redirect Context Managers

### Redirect Output

```python
from contextlib import redirect_stdout, redirect_stderr
import io

# Capture stdout - O(1) setup
output = io.StringIO()
with redirect_stdout(output):
    print("This goes to StringIO")
    print("Not to console")

captured = output.getvalue()
print(f"Captured: {captured}")

# Capture stderr - O(1) setup
errors = io.StringIO()
with redirect_stderr(errors):
    import sys
    sys.stderr.write("Error message")

print(f"Errors: {errors.getvalue()}")
```

## nullcontext - No-op Context

### Placeholder Context Manager

```python
from contextlib import nullcontext

# nullcontext - O(1), does nothing
with nullcontext() as nothing:
    print("Nothing is:", nothing)

# Return value
with nullcontext("default value") as value:
    print("Value is:", value)

# Conditional context manager
def optional_context(condition, context_manager):
    """Use context manager only if condition is true"""
    if condition:
        return context_manager
    return nullcontext()

# Usage
config = {'debug': True}

with optional_context(config.get('debug'), suppress(RuntimeError)):
    if config['debug']:
        raise RuntimeError("Debug error")
```

## Asyncio Context Managers

### Async Context Manager

```python
from contextlib import asynccontextmanager
import asyncio

# Define async context manager - O(1)
@asynccontextmanager
async def async_timer(name):
    """Async context manager"""
    
    # Setup - O(1)
    print(f"Starting {name}")
    import time
    start = time.time()
    
    try:
        # Yield control - O(1)
        yield
    finally:
        # Cleanup - O(1)
        elapsed = time.time() - start
        print(f"Finished {name}: {elapsed:.3f}s")

# Use async context - O(?) based on async operations
async def main():
    async with async_timer("async operation"):
        await asyncio.sleep(0.1)

# asyncio.run(main())
```

## Common Patterns

### Resource Pool Management

```python
from contextlib import contextmanager

class ConnectionPool:
    """Simple connection pool"""
    
    def __init__(self, size=5):
        self.pool = [f"Connection-{i}" for i in range(size)]
        self.available = set(self.pool)
    
    @contextmanager
    def acquire(self):
        """Acquire connection from pool - O(1) amortized"""
        
        # Get connection - O(1)
        conn = self.available.pop()
        
        try:
            yield conn
        finally:
            # Return to pool - O(1)
            self.available.add(conn)

# Use pool - O(1) per operation
pool = ConnectionPool(3)

with pool.acquire() as conn:
    print(f"Using {conn}")
    # Simulate work

# Connection returned - O(1)
print(f"Available: {len(pool.available)}")
```

### Temporary Changes

```python
from contextlib import contextmanager
import sys

@contextmanager
def temporary_setting(obj, name, value):
    """Temporarily change object attribute - O(1)"""
    
    # Save original - O(1)
    old_value = getattr(obj, name)
    setattr(obj, name, value)
    
    try:
        yield
    finally:
        # Restore original - O(1)
        setattr(obj, name, old_value)

class Config:
    debug = False

# Use - O(1)
with temporary_setting(Config, 'debug', True):
    print(f"Debug: {Config.debug}")  # True

print(f"Debug: {Config.debug}")  # False
```

## Performance Notes

### Time Complexity
- **Context entry/exit**: O(1) for simple cases
- **ExitStack operations**: O(1) per add, O(n) to exit all
- **Multiple contexts**: O(n) total where n = number of contexts

### Space Complexity
- **Context manager**: O(1) for simple cases
- **ExitStack**: O(n) for n registered callbacks/contexts
- **Output redirection**: O(n) for captured output

### Best Practices
- Use context managers for resource cleanup
- Use ExitStack for multiple resources
- Use suppresses sparingly for expected errors
- Use try/finally for custom cleanup

## Related Documentation

- [IO Module](io.md)
- [With Statement](../builtins/index.md)
- [Typing Module](typing.md)
- [Asyncio Module](asyncio.md)
