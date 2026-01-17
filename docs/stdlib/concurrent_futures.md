# concurrent.futures Module Complexity

The `concurrent.futures` module provides high-level interfaces for asynchronously executing callables using ThreadPoolExecutor and ProcessPoolExecutor.

## Functions & Classes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ThreadPoolExecutor(max_workers)` | O(w) | O(w) | Create pool, w = worker count |
| `ProcessPoolExecutor(max_workers)` | O(w) | O(w) | Create process pool |
| `executor.submit(fn, *args)` | O(1) | O(1) | Submit task to queue |
| `executor.map(fn, iterable)` | O(n) | O(n) | Submit all tasks, n = item count |
| `Future.result()` | O(1) | O(r) | Get result, r = result size |
| `as_completed(futures)` | O(n log n) | O(n) | Heap-based iteration; yields as each completes |
| `wait(futures)` | O(n) | O(n) | Wait for futures |

## ThreadPoolExecutor

### Creation and Configuration

```python
from concurrent.futures import ThreadPoolExecutor

# Create thread pool: O(w) time and space
# w = number of worker threads
executor = ThreadPoolExecutor(max_workers=4)  # O(w)

# Default: min(32, os.cpu_count() + 4) threads
executor = ThreadPoolExecutor()  # O(w) where w = default count

# Time to create: O(w) to spawn threads
# Space: O(w) for thread objects
```

### Submitting Tasks

#### Time Complexity: O(1) per submit

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

# Submit single task: O(1)
# Just adds to queue, doesn't wait
future = executor.submit(some_function, arg1, arg2)  # O(1)

# Submit many tasks: O(n) total
for item in items:  # n = len(items)
    future = executor.submit(process, item)  # O(1) per submit
    # Total: O(n)
```

#### Space Complexity: O(1) per submit

```python
from concurrent.futures import ThreadPoolExecutor

# Each submit adds to queue: O(1) space
# Queue grows as tasks accumulate
executor = ThreadPoolExecutor(max_workers=2)

for i in range(1000):
    executor.submit(task, i)  # O(1) per submit, O(1000) total space
```

## ProcessPoolExecutor

### Creation and Configuration

```python
from concurrent.futures import ProcessPoolExecutor

# Create process pool: O(w) time and space
executor = ProcessPoolExecutor(max_workers=4)  # O(w)

# Time to create: O(w) to spawn processes (slower than threads)
# Space: O(w) per process (much larger than threads)

# Default: os.cpu_count() processes
executor = ProcessPoolExecutor()  # O(w) where w = CPU count
```

### Submitting Tasks

```python
from concurrent.futures import ProcessPoolExecutor

executor = ProcessPoolExecutor(max_workers=4)

# Submit single task: O(1)
# Serializes arguments (pickle)
future = executor.submit(some_function, arg1, arg2)  # O(1) + pickle time

# Submit many: O(n)
for item in items:
    future = executor.submit(process, item)  # O(1) per submit
```

## Mapping Operations

### map() - Apply Function to Iterable

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

# Map function over items: O(n)
# n = number of items
items = range(1000)
results = list(executor.map(process, items))  # O(n)

# Submits all: O(n) time
# Returns iterator (doesn't wait for all immediately)
```

### Space Complexity

```python
from concurrent.futures import ThreadPoolExecutor

# map() returns iterator
executor = ThreadPoolExecutor(max_workers=4)

# Iterator version: O(1) memory (lazy)
for result in executor.map(func, huge_list):
    process(result)  # Memory: O(1) not O(n)

# list() version: O(n) memory
results = list(executor.map(func, huge_list))  # O(n) memory
```

## Getting Results

### Future.result() - Get Result

```python
from concurrent.futures import ThreadPoolExecutor
import time

executor = ThreadPoolExecutor(max_workers=2)

# Submit task
future = executor.submit(long_running_task)  # O(1)

# Wait and get result: O(1) operation + blocking time
# (actual time depends on task execution)
try:
    result = future.result()  # O(1) operation, blocks until ready
except Exception as e:
    print(f"Task failed: {e}")
```

### Timeout

```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError

executor = ThreadPoolExecutor(max_workers=2)
future = executor.submit(long_task)

# Get result with timeout: O(1) operation
try:
    result = future.result(timeout=5)  # Wait max 5 seconds, O(1) operation
except TimeoutError:
    print("Task didn't complete in time")
```

## Waiting for Results

### as_completed() - Iterate as Futures Complete

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

executor = ThreadPoolExecutor(max_workers=4)

# Submit all tasks: O(n)
futures = [executor.submit(task, i) for i in range(100)]  # O(n)

# Get futures as they complete: O(n log n) for sorting
# (maintains heap of pending futures)
for future in as_completed(futures):  # O(n log n) time
    result = future.result()  # O(1) per future
    process(result)
```

### wait() - Wait for Multiple Futures

```python
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

executor = ThreadPoolExecutor(max_workers=4)

# Submit tasks
futures = set()
for i in range(100):
    futures.add(executor.submit(task, i))  # O(n) total

# Wait for first to complete: O(n)
done, not_done = wait(futures, return_when=FIRST_COMPLETED)  # O(n)

# Wait for all to complete: O(n)
done, not_done = wait(futures)  # O(n)

# Wait with timeout: O(n)
done, not_done = wait(futures, timeout=10)  # O(n)
```

## Common Patterns

### Simple Parallel Processing

```python
from concurrent.futures import ThreadPoolExecutor

def process_items(items):
    """Process items in parallel."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all tasks: O(n)
        futures = [executor.submit(process, item) for item in items]
        
        # Collect results: O(n)
        results = [f.result() for f in futures]
    
    return results
    # Total: O(n) time, O(w) memory for workers + O(n) for results
```

### Process Large Dataset in Batches

```python
from concurrent.futures import ThreadPoolExecutor

def batch_process(items, batch_size=100):
    """Process items in batches."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = []
        
        # Process in batches: O(n/batch_size) iterations
        for i in range(0, len(items), batch_size):
            batch = items[i:i+batch_size]
            # Submit batch: O(batch_size)
            futures = [executor.submit(process, item) for item in batch]
            # Get results: O(batch_size)
            results.extend([f.result() for f in futures])
        
        return results
```

### Map with Exception Handling

```python
from concurrent.futures import ThreadPoolExecutor

def safe_map(func, items, max_workers=4):
    """Map with exception handling."""
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all: O(n)
        futures = {executor.submit(func, item): item for item in items}
        
        # Collect with error handling: O(n)
        for future in futures:
            try:
                result = future.result()
                results.append((futures[future], result))
            except Exception as e:
                results.append((futures[future], None))
    
    return results
    # Total: O(n)
```

### Timeout Pattern

```python
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

def process_with_timeout(items, timeout=30):
    """Process items with per-item timeout."""
    results = []
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all: O(n)
        futures = {executor.submit(task, item): item for item in items}
        
        # Wait with timeout: O(n)
        try:
            for future in as_completed(futures, timeout=timeout):  # O(n log n)
                result = future.result()
                results.append(result)
        except TimeoutError:
            # Some tasks didn't complete
            pass
    
    return results
```

## Performance Characteristics

### ThreadPoolExecutor vs ProcessPoolExecutor

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# ThreadPoolExecutor: For I/O-bound tasks
# - Fast creation: O(w) with light threads
# - Good for network, file I/O
# - Shares GIL, limited by GIL for CPU
executor = ThreadPoolExecutor(max_workers=8)

# ProcessPoolExecutor: For CPU-bound tasks
# - Slower creation: O(w) with heavy processes
# - Good for computation
# - No GIL, true parallelism
executor = ProcessPoolExecutor(max_workers=4)

# Rule: use ProcessPoolExecutor for CPU-bound
# Use ThreadPoolExecutor for I/O-bound
```

### Best Practices

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

# Good: Use context manager for cleanup
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(task, i) for i in range(10)]
    for future in as_completed(futures):
        result = future.result()

# Avoid: Manual shutdown
executor = ThreadPoolExecutor(max_workers=4)
futures = [executor.submit(task, i) for i in range(10)]
executor.shutdown(wait=True)  # Required, easily forgotten

# Good: Use map() for simple function application
results = list(executor.map(process, items))  # O(n)

# Avoid: Manual submit for each item (less efficient)
futures = [executor.submit(process, item) for item in items]

# Good: Limit queue size implicitly
# Tasks submitted faster than executed will wait

# Avoid: Submitting unlimited tasks
# Can exhaust memory if submission >> execution
```

### Worker Count Selection

```python
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import os

# CPU-bound: CPU count
cpu_count = os.cpu_count() or 4
executor = ProcessPoolExecutor(max_workers=cpu_count)

# I/O-bound: higher number (1-2x CPU count)
executor = ThreadPoolExecutor(max_workers=cpu_count * 2)

# Network services: even higher
executor = ThreadPoolExecutor(max_workers=32)
```

## Version Notes

- **Python 3.2+**: concurrent.futures module introduced
- **Python 3.3+**: Enhanced performance
- **Python 3.5+**: Better integration with asyncio
- **Python 3.9+**: ProcessPoolExecutor improvements

## Related Documentation

- [asyncio Module](asyncio.md) - Async/await programming
- [threading Module](threading.md) - Thread-based parallelism
- [multiprocessing Module](multiprocessing.md) - Process-based parallelism
- [queue Module](queue.md) - Thread-safe queues
