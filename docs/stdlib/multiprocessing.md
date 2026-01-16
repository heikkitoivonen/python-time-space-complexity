# multiprocessing Module Complexity

The `multiprocessing` module provides process-based parallelism for CPU-bound tasks, bypassing the Global Interpreter Lock (GIL).

## Classes & Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Process(target)` | O(1) | O(1) | Create process object |
| `process.start()` | O(w) | O(w) | Start process, w = process overhead |
| `process.join()` | O(1) | O(1) | Wait for process |
| `Queue()` | O(1) | O(1) | Create queue |
| `queue.put(item)` | O(1) | O(1) | Add to queue |
| `queue.get()` | O(1) | O(1) | Remove from queue |
| `Pool(processes)` | O(w) | O(w) | Create pool, w = process count |
| `pool.map(fn, items)` | O(n) | O(n) | Map over items, n = item count |

## Process Creation

### Time Complexity: O(w)

Where w = process startup overhead.

```python
from multiprocessing import Process

def worker(name):
    print(f"Worker {name}")

# Create process: O(1)
p = Process(target=worker, args=("A",))  # O(1) to create object

# Start process: O(w)
# w = startup overhead (fork, initialization)
p.start()  # O(w)

# Join process: O(1) operation (wait for completion)
p.join()  # O(1) operation, blocks until done
```

### Space Complexity: O(w)

```python
from multiprocessing import Process

# Each process uses significant memory
# w = memory per process (typically 10-50MB)

processes = []
for i in range(10):
    p = Process(target=task, args=(i,))
    p.start()
    processes.append(p)  # O(10w) total memory

for p in processes:
    p.join()  # O(1) per join

# Note: Start fewer processes than you think!
# 4-8 usually sufficient for CPU-bound (use CPU count)
```

## Queues

### Queue Operations

```python
from multiprocessing import Queue

# Create queue: O(1)
q = Queue()  # O(1)

# Put item: O(1) amortized
# Adds to internal buffer
q.put("item")  # O(1)

# Get item: O(1) amortized
# Removes from internal buffer
item = q.get()  # O(1)

# Block until available: O(1) operation
# Time depends on when item arrives
item = q.get(timeout=5)  # O(1) operation
```

### Space Complexity

```python
from multiprocessing import Queue

q = Queue(maxsize=100)  # O(1) to create

# Space grows as items accumulate
for i in range(100):
    q.put(i)  # O(1) per put, O(100) total space

# Space reduces as items consumed
while not q.empty():
    item = q.get()  # O(1) per get
```

## Pool

### Pool Creation

```python
from multiprocessing import Pool
import os

# Create pool: O(w) time
# w = number of worker processes
pool = Pool(processes=4)  # O(w) to create

# Default: os.cpu_count() processes
pool = Pool()  # O(w) where w = CPU count

# Each process has significant overhead
# Time: 10-100ms per process to start
# Space: 10-50MB per process
```

### Pool.map() - Apply Function to Items

```python
from multiprocessing import Pool

def square(x):
    return x * x

pool = Pool(processes=4)

# Map: O(n) to submit tasks
# n = number of items
items = range(1000)
results = pool.map(square, items)  # O(n)

# Collects all results (blocks until done)
# Returns list in original order
```

### Pool.map_async() - Non-blocking Map

```python
from multiprocessing import Pool

pool = Pool(processes=4)

# Submit: O(n) to queue tasks
items = range(1000)
result_async = pool.map_async(square, items)  # O(n)

# Returns immediately: O(1)
# Get results later: O(1) operation
results = result_async.get()  # Blocks until done

# Get with timeout: O(1) operation
try:
    results = result_async.get(timeout=5)  # O(1)
except TimeoutError:
    pass
```

### Pool.apply_async() - Single Task

```python
from multiprocessing import Pool

pool = Pool(processes=4)

# Submit single task: O(1)
result_async = pool.apply_async(compute, (args,))  # O(1)

# Get result: O(1) operation
result = result_async.get()  # O(1), blocks until ready
```

### Pool.imap() - Lazy Iterator

```python
from multiprocessing import Pool

pool = Pool(processes=4)

# Create iterator: O(1)
# Processes items lazily
results_iter = pool.imap(process, items)  # O(1) to create

# Iterate: O(n) total for all items
for result in results_iter:  # O(n log n) due to task scheduling
    process_result(result)  # O(1) per iteration
```

### Shutdown

```python
from multiprocessing import Pool

pool = Pool(processes=4)

# Submit tasks
results = pool.map(task, items)  # O(n)

# Close: O(1)
# Prevents new tasks
pool.close()  # O(1)

# Join: O(w)
# Wait for all tasks to complete
pool.join()  # O(w) to wait for w processes

# Or use context manager
with Pool(processes=4) as pool:
    results = pool.map(task, items)  # Automatically cleaned up
```

## Pipes

### Pipe Communication

```python
from multiprocessing import Pipe, Process

# Create pipe: O(1)
parent_conn, child_conn = Pipe()  # O(1)

# Send: O(1) amortized
parent_conn.send("message")  # O(1)

# Receive: O(1) operation
msg = child_conn.recv()  # O(1), blocks until available

# Bidirectional: both ends can send/receive
child_conn.send("reply")  # O(1)
reply = parent_conn.recv()  # O(1)
```

## Common Patterns

### Simple Parallel Processing

```python
from multiprocessing import Pool

def process_item(item):
    """Process single item."""
    return item * 2

def parallel_map(items):
    """Process items in parallel."""
    with Pool() as pool:
        # Submit all: O(n)
        results = pool.map(process_item, items)  # O(n)
    
    return results
    # Total: O(n) time, O(w) processes
```

### Producer-Consumer with Queues

```python
from multiprocessing import Queue, Process

def producer(q, items):
    """Produce items."""
    for item in items:  # O(n)
        q.put(item)  # O(1) per put
    q.put(None)  # Signal end

def consumer(q):
    """Consume items."""
    results = []
    while True:
        item = q.get()  # O(1) per get
        if item is None:
            break
        results.append(process(item))  # O(m) per item
    return results

# Create queue and processes
q = Queue()
producer_p = Process(target=producer, args=(q, items))
consumer_p = Process(target=consumer, args=(q,))

producer_p.start()
consumer_p.start()

producer_p.join()  # O(1)
consumer_p.join()  # O(1)
```

### Parallel Computation with Results

```python
from multiprocessing import Pool, Queue

def compute(data_chunk):
    """Compute on data chunk."""
    return sum(data_chunk) * 2

def parallel_compute(data, num_processes=4):
    """Compute across processes."""
    # Chunk data
    chunk_size = len(data) // num_processes
    chunks = [
        data[i:i+chunk_size]
        for i in range(0, len(data), chunk_size)
    ]
    
    # Process chunks: O(n)
    with Pool(processes=num_processes) as pool:
        results = pool.map(compute, chunks)  # O(n)
    
    return sum(results)  # Aggregate
```

### Pipe Communication

```python
from multiprocessing import Pipe, Process

def worker(conn, task_id):
    """Worker receives and sends."""
    msg = conn.recv()  # O(1)
    result = process_message(msg)
    conn.send(result)  # O(1)

# Create communication channel
parent_conn, child_conn = Pipe()  # O(1)

# Start worker process
p = Process(target=worker, args=(child_conn, 1))
p.start()

# Parent sends task
parent_conn.send(("task_data",))  # O(1)

# Parent receives result
result = parent_conn.recv()  # O(1)

p.join()  # O(1)
```

## Performance Characteristics

### Process Overhead

```python
from multiprocessing import Pool, Process

# Process creation is expensive
# Startup time: 10-100ms per process
# Memory: 10-50MB per process

# Rule: Use Pool for multiple tasks
# Creates workers once, reuses them

# Good: Reuse pool for multiple operations
with Pool(processes=4) as pool:
    results1 = pool.map(task1, items)  # O(n1)
    results2 = pool.map(task2, items)  # O(n2)

# Avoid: Creating new pool each time
for items_batch in batches:
    pool = Pool(processes=4)  # O(w) overhead each time!
    results = pool.map(task, items_batch)
    pool.close()
    pool.join()
```

### Best Practices

```python
from multiprocessing import Pool, cpu_count

# Good: Use CPU count for CPU-bound tasks
num_processes = cpu_count()
with Pool(processes=num_processes) as pool:
    results = pool.map(cpu_intensive_task, items)

# Avoid: Using too many processes
# More processes = more overhead, context switching
with Pool(processes=64) as pool:  # Way too many!
    results = pool.map(task, items)

# Good: Use context manager for cleanup
with Pool(processes=4) as pool:
    results = pool.map(task, items)
    # Automatically closed and joined

# Avoid: Manual cleanup
pool = Pool(processes=4)
results = pool.map(task, items)
pool.close()  # Easy to forget!
pool.join()

# Good: Use chunksize for large datasets
results = pool.map(task, large_items, chunksize=100)

# Avoid: Default chunksize for large datasets
results = pool.map(task, 1000000_items)  # chunksize=1 is slow
```

### When to Use multiprocessing

```python
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor

# CPU-bound: Use multiprocessing
# - Heavy computation
# - No I/O waiting
# - True parallelism
with Pool(processes=4) as pool:
    results = pool.map(cpu_bound_task, items)

# I/O-bound: Use concurrent.futures.ThreadPoolExecutor
# - Network requests
# - File I/O
# - Database queries
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(io_task, item) for item in items]
    results = [f.result() for f in futures]
```

## Version Notes

- **Python 2.6+**: multiprocessing module introduced
- **Python 3.0+**: Enhanced API
- **Python 3.4+**: Better integration with concurrent.futures
- **Python 3.13+**: Better IPC mechanisms

## Differences from Threading

```python
# Threading (I/O-bound):
# - Lightweight
# - Shared memory
# - GIL prevents true parallelism
# - Good for I/O operations

# Multiprocessing (CPU-bound):
# - Heavy overhead
# - Separate memory space
# - True parallelism
# - Good for CPU-intensive operations
```

## Related Documentation

- [concurrent.futures Module](concurrent_futures.md) - High-level executor interface
- [threading Module](threading.md) - Thread-based parallelism
- [asyncio Module](asyncio.md) - Async/await programming
- [queue Module](queue.md) - Thread-safe queues
