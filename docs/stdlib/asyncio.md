# asyncio Module Complexity

The `asyncio` module provides infrastructure for writing single-threaded concurrent code using async/await, managing coroutines and event loops.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.run()` | O(1) | O(n) | n = event loop state |
| `await coroutine` | O(1) | O(1) | Suspend execution |
| Task creation | O(1) | O(1) | Wrap coroutine |
| `asyncio.gather()` | O(1) | O(n) | n = number of tasks |
| `asyncio.wait()` | O(n) | O(n) | n = tasks waiting |
| Event queue operation | O(log n) | O(1) | Heap-based scheduling; n = pending events |

## Async Basics

### Simple Coroutine

```python
import asyncio

# Define coroutine - O(1)
async def greet(name):
    print(f"Hello {name}")
    await asyncio.sleep(1)  # Non-blocking wait - O(1)
    print(f"Goodbye {name}")

# Run coroutine - O(1) setup, O(?) execution
asyncio.run(greet("Alice"))

# Output:
# Hello Alice
# (1 second pause)
# Goodbye Alice
```

### Multiple Concurrent Tasks

```python
import asyncio

async def task(name, duration):
    """Async task - O(1) execution"""
    print(f"Task {name} starting")
    await asyncio.sleep(duration)
    print(f"Task {name} complete")

async def main():
    # Create tasks - O(1) each
    task1 = asyncio.create_task(task("A", 2))
    task2 = asyncio.create_task(task("B", 1))
    task3 = asyncio.create_task(task("C", 3))
    
    # Wait for all - O(n) where n = number of tasks
    await asyncio.gather(task1, task2, task3)

# Run - total time = max(2, 1, 3) = 3 seconds
asyncio.run(main())

# Output:
# Task A starting
# Task B starting
# Task C starting
# Task B complete
# Task A complete
# Task C complete
```

## Async/Await

### Async Function Basics

```python
import asyncio

# Async function definition
async def fetch_data(url):
    """Fetch data from URL - O(1) per await"""
    
    print(f"Fetching {url}")
    
    # Simulate async I/O - O(1) context switch
    await asyncio.sleep(2)
    
    return {"data": f"Content from {url}"}

async def main():
    # Await coroutine - O(1) suspension
    result = await fetch_data("http://example.com")
    print(result)

# Run event loop
asyncio.run(main())
```

### Sequential vs Concurrent

```python
import asyncio
import time

async def task(name, duration):
    await asyncio.sleep(duration)
    return f"{name} done"

async def sequential():
    """Sequential execution - O(t1 + t2 + t3)"""
    
    # Each task waits for previous
    r1 = await task("Task1", 1)  # 1 second
    r2 = await task("Task2", 1)  # 1 second
    r3 = await task("Task3", 1)  # 1 second
    
    return [r1, r2, r3]  # Total: 3 seconds

async def concurrent():
    """Concurrent execution - O(max(t1, t2, t3))"""
    
    # All tasks run concurrently
    results = await asyncio.gather(
        task("Task1", 1),   # 
        task("Task2", 1),   # All parallel
        task("Task3", 1)    #
    )
    
    return results  # Total: 1 second

# Sequential: 3 seconds
start = time.time()
asyncio.run(sequential())
print(f"Sequential: {time.time() - start:.1f}s")

# Concurrent: 1 second
start = time.time()
asyncio.run(concurrent())
print(f"Concurrent: {time.time() - start:.1f}s")
```

## Tasks and Coroutines

### Creating Tasks

```python
import asyncio

async def background_task():
    """Background task - O(1) per iteration"""
    for i in range(5):
        print(f"Background: {i}")
        await asyncio.sleep(0.5)

async def main():
    # Create task (scheduled immediately) - O(1)
    task = asyncio.create_task(background_task())
    
    # Do other work while task runs
    for i in range(3):
        print(f"Main: {i}")
        await asyncio.sleep(1)
    
    # Wait for task - O(1)
    await task

asyncio.run(main())

# Output interleaves:
# Main: 0
# Background: 0
# Background: 1
# Main: 1
# ...
```

### Task Result and Exceptions

```python
import asyncio

async def might_fail(should_fail):
    """Task that might raise exception"""
    if should_fail:
        raise ValueError("Task failed")
    return "Success"

async def main():
    # Create task - O(1)
    task = asyncio.create_task(might_fail(False))
    
    # Wait and get result - O(1)
    try:
        result = await task
        print(f"Result: {result}")
    except ValueError as e:
        print(f"Error: {e}")
    
    # Check task state - O(1)
    print(f"Done: {task.done()}")
    print(f"Result: {task.result()}")
```

## Gathering and Waiting

### Gather Multiple Tasks

```python
import asyncio

async def fetch_url(url):
    await asyncio.sleep(1)
    return f"Data from {url}"

async def main():
    # Create multiple coroutines - O(1) each
    urls = [
        "http://example.com/1",
        "http://example.com/2",
        "http://example.com/3"
    ]
    
    # Gather - O(1) setup, concurrent execution
    results = await asyncio.gather(
        *[fetch_url(url) for url in urls]
    )
    
    # Results in order - O(1) per result
    for url, result in zip(urls, results):
        print(f"{url}: {result}")

asyncio.run(main())
```

### Wait with Conditions

```python
import asyncio

async def task(name, duration):
    await asyncio.sleep(duration)
    return f"{name} done"

async def main():
    # Create tasks - O(1) each
    tasks = [
        asyncio.create_task(task("A", 1)),
        asyncio.create_task(task("B", 2)),
        asyncio.create_task(task("C", 3))
    ]
    
    # Wait for first - O(n) check, ~O(min(durations))
    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_COMPLETED
    )
    
    print(f"Done: {len(done)}")  # 1
    print(f"Pending: {len(pending)}")  # 2
    
    # Wait for others
    for task in pending:
        await task

asyncio.run(main())
```

## Event Loop

### Manual Event Loop

```python
import asyncio

async def coro():
    print("Coroutine execution")
    await asyncio.sleep(0.1)
    return "Done"

# Create event loop - O(1)
loop = asyncio.new_event_loop()

try:
    # Run coroutine - O(1) setup
    result = loop.run_until_complete(coro())
    print(f"Result: {result}")
finally:
    # Close loop - O(1)
    loop.close()
```

### Running in Event Loop

```python
import asyncio

async def main():
    # Get current event loop - O(1)
    loop = asyncio.get_running_loop()
    
    # Schedule callback - O(1)
    loop.call_soon(print, "Scheduled immediately")
    
    # Schedule delayed callback - O(log n)
    loop.call_later(0.5, print, "Scheduled in 0.5s")
    
    # Wait - O(1)
    await asyncio.sleep(1)

asyncio.run(main())
```

## Locks and Synchronization

### Lock for Mutual Exclusion

```python
import asyncio

lock = asyncio.Lock()
counter = 0

async def increment():
    """Increment with lock - O(1) per operation"""
    global counter
    
    async with lock:  # O(1) acquire
        temp = counter
        await asyncio.sleep(0.001)  # Simulate work
        counter = temp + 1

async def main():
    # Run concurrent increments - O(1) per task
    tasks = [increment() for _ in range(10)]
    
    # Wait for all - O(n) where n = tasks
    await asyncio.gather(*tasks)
    
    print(f"Counter: {counter}")  # Correctly 10

asyncio.run(main())
```

### Event Synchronization

```python
import asyncio

async def waiter(event):
    """Wait for event - O(1)"""
    print("Waiting for event")
    await event.wait()
    print("Event received!")

async def notifier(event):
    """Notify event - O(n)"""
    await asyncio.sleep(1)
    print("Setting event")
    event.set()

async def main():
    event = asyncio.Event()
    
    # Create tasks - O(1) each
    task1 = asyncio.create_task(waiter(event))
    task2 = asyncio.create_task(notifier(event))
    
    # Wait for all - O(n)
    await asyncio.gather(task1, task2)

asyncio.run(main())
```

### Semaphore for Rate Limiting

```python
import asyncio

semaphore = asyncio.Semaphore(2)  # Allow 2 concurrent

async def limited_task(name):
    """Task with limited concurrency - O(1) per operation"""
    async with semaphore:  # O(1) acquire
        print(f"{name} acquired semaphore")
        await asyncio.sleep(1)
        print(f"{name} released semaphore")

async def main():
    # Create 5 tasks, only 2 can run concurrently
    tasks = [limited_task(f"Task-{i}") for i in range(5)]
    
    # Run with rate limiting - O(1) scheduling
    await asyncio.gather(*tasks)

asyncio.run(main())
```

## Common Patterns

### Timeout Handling

```python
import asyncio

async def slow_operation():
    await asyncio.sleep(10)
    return "Done"

async def main():
    try:
        # Wait with timeout - O(1) timeout check
        result = await asyncio.wait_for(
            slow_operation(),
            timeout=1.0
        )
    except asyncio.TimeoutError:
        print("Operation timed out")

asyncio.run(main())
```

### Retry with Backoff

```python
import asyncio

async def unreliable_api(attempt=1):
    """API that fails occasionally"""
    if attempt < 3:
        raise ConnectionError("API unavailable")
    return "Success"

async def retry_with_backoff(coro, max_retries=3, backoff=1):
    """Retry with exponential backoff - O(1) per retry"""
    
    for attempt in range(1, max_retries + 1):
        try:
            return await coro(attempt)
        except Exception as e:
            if attempt == max_retries:
                raise
            
            wait_time = backoff ** (attempt - 1)
            print(f"Retry {attempt} after {wait_time}s")
            await asyncio.sleep(wait_time)

async def main():
    result = await retry_with_backoff(unreliable_api)
    print(f"Result: {result}")

asyncio.run(main())
```

### Queue Processing

```python
import asyncio

async def producer(queue):
    """Produce items - O(1) per item"""
    for i in range(5):
        print(f"Producing {i}")
        await queue.put(i)
        await asyncio.sleep(0.5)

async def consumer(queue, name):
    """Consume items - O(1) per item"""
    while True:
        item = await queue.get()
        print(f"{name} processing {item}")
        await asyncio.sleep(1)
        queue.task_done()

async def main():
    queue = asyncio.Queue()
    
    # Create producer and consumers - O(1) each
    tasks = [
        asyncio.create_task(producer(queue)),
        asyncio.create_task(consumer(queue, "Consumer-1")),
        asyncio.create_task(consumer(queue, "Consumer-2"))
    ]
    
    # Wait for production to complete
    await asyncio.sleep(5)
    
    # Cancel consumers
    for task in tasks[1:]:
        task.cancel()

asyncio.run(main())
```

## Performance Notes

### Concurrency vs Parallelism
- **Concurrency**: Multiple tasks, one thread (asyncio)
- **Parallelism**: Multiple tasks, multiple threads (threading)
- **asyncio**: Better for I/O-bound operations
- **threading**: Better for CPU-bound operations

### Time Complexity
- **Task scheduling**: O(log n) for n tasks
- **Event loop iteration**: O(n) for n ready tasks
- **Synchronization**: O(1) per acquire/release

### Space Complexity
- **Event loop**: O(n) for n tasks
- **Task state**: O(m) for m coroutine frames
- **Queues**: O(n) for n items

## Related Documentation

- [Threading Module](threading.md)
- [Concurrent Futures Module](concurrent.md)
- [Contextlib Module](contextlib.md)
- [Queue Module](queue.md)
