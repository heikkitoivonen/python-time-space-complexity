# contextvars Module Complexity

The `contextvars` module provides context variables for managing state in concurrent and async code while maintaining isolation between execution contexts.

## Classes & Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ContextVar(name)` | O(1) | O(1) | Create context variable |
| `ContextVar.set(value)` | O(1) | O(1) | Returns token for reset |
| `ContextVar.get()` | O(1) | O(1) | Returns default if not set |
| `copy_context()` | O(n) | O(n) | Copy context, n = variable count |
| `Context.run(fn, *args)` | O(1) | O(1) | Run function in context |

## Creating Context Variables

### Time Complexity: O(1)

```python
from contextvars import ContextVar

# Create variable: O(1)
request_id = ContextVar('request_id')  # O(1)

# With default value: O(1)
user_id = ContextVar('user_id', default=None)  # O(1)

# Each variable is a singleton
# Multiple references to same name share state
request_id2 = ContextVar('request_id')  # Different object, shares context value
```

### Space Complexity: O(1)

```python
from contextvars import ContextVar

# Variable object is small: O(1)
request_id = ContextVar('request_id')  # O(1) space
```

## Setting and Getting Values

### Time Complexity: O(1)

```python
from contextvars import ContextVar

request_id = ContextVar('request_id')

# Set value in context: O(1)
token = request_id.set('req-123')  # O(1)

# Get value from context: O(1)
current_id = request_id.get()  # O(1)

# Get with default: O(1)
default_id = request_id.get('no-id')  # O(1)

# Reset to previous: O(1)
request_id.reset(token)  # O(1)
```

### Space Complexity: O(1)

```python
from contextvars import ContextVar

# Each set stores one value: O(1)
request_id = ContextVar('request_id')
request_id.set('req-1')  # O(1) space
request_id.set('req-2')  # O(1) space (replaces)
```

## Context Copying

### Time Complexity: O(n)

Where n = number of context variables set.

```python
from contextvars import ContextVar, copy_context

request_id = ContextVar('request_id')
user_id = ContextVar('user_id')
session_id = ContextVar('session_id')

# Set values: O(1) per set
request_id.set('req-123')  # O(1)
user_id.set('user-456')  # O(1)
session_id.set('sess-789')  # O(1)

# Copy context: O(n) where n = 3 variables
ctx = copy_context()  # O(n)

# Space: O(n) for copy
# Copying is relatively cheap, O(n) where n is usually small
```

### Space Complexity: O(n)

```python
from contextvars import copy_context

# Copying creates new context with all values
ctx = copy_context()  # O(n) space for n variables
```

## Running in Contexts

### Time Complexity: O(1)

```python
from contextvars import ContextVar, copy_context

request_id = ContextVar('request_id')

# Set in current context
request_id.set('req-main')

# Copy context: O(n)
ctx = copy_context()  # O(n)

# Run function in copied context: O(1) to switch
def task():
    current_id = request_id.get()  # O(1)
    return current_id

# Run in context: O(1) operation
# (function execution time is separate)
result = ctx.run(task)  # O(1) + function time
```

### Space Complexity: O(1) for switching

```python
from contextvars import copy_context

# No additional space to switch contexts
# O(1) operation
ctx = copy_context()  # O(n) space for context
result = ctx.run(some_function)  # O(1) switching space
```

## Common Patterns

### Request Context in Web Applications

```python
from contextvars import ContextVar
from datetime import datetime

# Define context variables
request_id = ContextVar('request_id')
user_id = ContextVar('user_id', default=None)
request_time = ContextVar('request_time')

# In request handler
def handle_request(request):
    """Handle HTTP request."""
    # Set context variables: O(1) each
    request_id.set(request.id)  # O(1)
    user_id.set(request.user_id)  # O(1)
    request_time.set(datetime.now())  # O(1)
    
    # Call business logic
    result = process_request(request)  # Can access context vars
    
    return result

def process_request(request):
    """Business logic that accesses context."""
    # Get current request_id: O(1)
    current_req_id = request_id.get()
    
    # Log with context
    log(f"Processing {current_req_id}")
    
    # Call other functions that can access context
    validate(request)  # Can use request_id without passing it
    
    return result

def validate(request):
    """Access context variables implicitly."""
    # Get from context without parameter passing: O(1)
    req_id = request_id.get()
    print(f"Validating {req_id}")
```

### Async Task Context

```python
import asyncio
from contextvars import ContextVar

task_id = ContextVar('task_id')

async def process_task(task_data):
    """Process async task."""
    # Set context for this task: O(1)
    task_id.set(task_data['id'])
    
    # Each await preserves context automatically
    result = await fetch_data()  # Context preserved
    
    return process_result(result)  # Can access task_id: O(1)

async def fetch_data():
    """Access context in async function."""
    # Context is inherited from caller: O(1)
    current_task_id = task_id.get()
    
    # Async operations preserve context
    await asyncio.sleep(1)
    
    return {"result": "data"}

async def main():
    """Run multiple tasks with separate contexts."""
    tasks = [
        asyncio.create_task(process_task({"id": f"task-{i}"}))
        for i in range(5)
    ]
    
    # Each task has separate context automatically
    results = await asyncio.gather(*tasks)  # O(n)
```

### Thread Context Isolation

```python
from contextvars import ContextVar
from threading import Thread

# Note: contextvars are isolated per thread/async task
# Not inherited by default in threads
request_id = ContextVar('request_id')

def thread_worker(task_id):
    """Worker function in thread."""
    # Set in thread context: O(1)
    # This does NOT affect main thread context
    request_id.set(f"thread-{task_id}")
    
    # Get from thread context: O(1)
    current_id = request_id.get()
    print(f"Worker: {current_id}")

def main():
    """Main thread context."""
    # Set in main: O(1)
    request_id.set('main-thread')
    
    # Create and start thread
    thread = Thread(target=thread_worker, args=(1,))
    thread.start()
    
    # Main thread context unchanged: O(1) to get
    current_id = request_id.get()
    print(f"Main: {current_id}")  # Still 'main-thread'
    
    thread.join()
```

### Context Propagation to Threads

```python
from contextvars import ContextVar, copy_context
from threading import Thread

request_id = ContextVar('request_id')

def thread_worker(ctx, task_id):
    """Worker runs in provided context."""
    # Run in copied context: O(1) switch
    def work():
        # Now can access context: O(1)
        current_id = request_id.get()
        print(f"Worker {task_id}: {current_id}")
        return f"result-{task_id}"
    
    return ctx.run(work)  # O(1) to switch context

def main():
    """Set up context and run in thread."""
    # Set main context: O(1)
    request_id.set('main-request')
    
    # Copy context: O(n)
    ctx = copy_context()
    
    # Pass context to thread
    thread = Thread(target=thread_worker, args=(ctx, 1))
    thread.start()
    thread.join()
```

## Performance Characteristics

### Context Variable Access

```python
from contextvars import ContextVar

var = ContextVar('var')

# Set is fast: O(1)
var.set('value')  # O(1)

# Get is fast: O(1)
value = var.get()  # O(1)

# No performance overhead vs global variable
# (except for isolation benefit)
```

### Context Copying

```python
from contextvars import copy_context, ContextVar

# Copying has cost: O(n)
ctx = copy_context()  # O(n) where n = variables set

# But only needed occasionally (not per operation)
# Usually done once per request/task

# Usually n is small (< 10 variables)
# So O(n) is acceptable
```

### Best Practices

```python
from contextvars import ContextVar

# Good: Create variables at module level
request_id = ContextVar('request_id')
user_id = ContextVar('user_id')  # O(1) at import time

# Avoid: Creating variables in functions
def handle_request():
    # Creating in function: inefficient
    temp_var = ContextVar('temp')  # O(1) but wasteful
    temp_var.set('value')

# Good: Set once per request/task
def handle_request(request):
    request_id.set(request.id)  # O(1)
    # Don't set repeatedly

# Avoid: Setting repeatedly in loop
def process_items(items):
    for item in items:
        request_id.set(item.id)  # O(n) sets, inefficient
        process(item)

# Good: Copy context for new execution path
async def task():
    ctx = copy_context()  # O(n) once
    result = ctx.run(function)  # O(1) to switch

# Avoid: Copying context repeatedly
for i in range(1000):
    ctx = copy_context()  # O(n*1000) - wasteful!
    ctx.run(function)
```

### Async vs Threading

```python
from contextvars import ContextVar
import asyncio
from threading import Thread

var = ContextVar('var')

async def async_task():
    """Async tasks share context efficiently."""
    var.set('value-1')
    
    # Create subtask: context inherited automatically
    subtask = asyncio.create_task(async_subtask())
    
    result = await subtask
    return result
    # Total: O(1) context operations

async def async_subtask():
    """Access parent context: O(1)."""
    value = var.get()  # O(1) - inherits from parent
    return value

def thread_task():
    """Threads require explicit context passing."""
    from contextvars import copy_context
    
    var.set('value-1')
    
    # Must copy context: O(n)
    ctx = copy_context()
    
    # Pass to thread
    thread = Thread(target=thread_subtask, args=(ctx,))
    thread.start()
    thread.join()
    
    # Total: O(n) for copying

def thread_subtask(ctx):
    """Must run in copied context."""
    result = ctx.run(lambda: var.get())  # O(1) to access
    return result
```

## Version Notes

- **Python 3.7+**: contextvars module introduced
- **Python 3.11+**: Enhanced performance
- **Python 3.13+**: Additional features

## Related Documentation

- [asyncio Module](asyncio.md) - Async/await with context support
- [threading Module](threading.md) - Threading (context not automatic)
- [concurrent.futures Module](concurrent_futures.md) - Executors
