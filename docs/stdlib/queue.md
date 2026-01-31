# queue - Synchronized Queue Data Structures

The `queue` module provides thread-safe queue implementations for coordinating work between multiple producer and consumer threads.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Queue.put()` | O(1) | O(1) | Add item (blocks if full); uses deque internally |
| `Queue.get()` | O(1) | O(1) | Remove item (blocks if empty) |
| `Queue.put_nowait()` | O(1) | O(1) | Add item (raises Full if full) |
| `Queue.get_nowait()` | O(1) | O(1) | Remove item (raises Empty if empty) |
| `Queue.qsize()` | O(1) | O(1) | Approximate size (not reliable under contention) |
| `PriorityQueue.put()` | O(log n) | O(1) amortized | Add with priority (heap push) |
| `PriorityQueue.get()` | O(log n) | O(1) amortized | Remove smallest-priority item (heap pop) |
| `LifoQueue.put()` | O(1) amortized | O(1) | Add item (LIFO); uses list internally |
| `LifoQueue.get()` | O(1) | O(1) | Remove item (LIFO) |
| `SimpleQueue.put()` | O(1) | O(1) | Add item (unbounded, never blocks on size) |
| `SimpleQueue.get()` | O(1) | O(1) | Remove item (blocks if empty) |

## Basic Queue (FIFO)

```python
from queue import Queue
import threading
import time

# Create queue with max size - O(1)
q = Queue(maxsize=5)

# Put items - O(1) amortized
q.put('item1')  # O(1)
q.put('item2')  # O(1)
q.put('item3')  # O(1)

# Get items FIFO - O(1) amortized
print(q.get())  # O(1) - 'item1'
print(q.get())  # O(1) - 'item2'
print(q.get())  # O(1) - 'item3'
```

## Producer-Consumer Pattern

```python
from queue import Queue
import threading
import time

def producer(q, items):
    """Producer thread adds items to queue - O(n)"""
    for item in items:  # O(n)
        print(f"Producing {item}")
        q.put(item)  # O(1) amortized
        time.sleep(0.1)

def consumer(q, count):
    """Consumer thread retrieves items - O(n)"""
    for _ in range(count):  # O(n)
        item = q.get()  # O(1) amortized, blocks if empty
        print(f"Consuming {item}")
        q.task_done()  # O(1) - mark task complete

# Create queue - O(1)
q = Queue()

# Create producer thread - O(1)
prod = threading.Thread(
    target=producer,
    args=(q, ['A', 'B', 'C', 'D', 'E'])
)

# Create consumer thread - O(1)
cons = threading.Thread(
    target=consumer,
    args=(q, 5)
)

# Start threads
prod.start()  # O(1)
cons.start()  # O(1)

# Wait for completion
q.join()  # O(n) - blocks until all tasks done
print("All tasks complete")
```

## Priority Queue

```python
from queue import PriorityQueue

# Create priority queue - O(1)
pq = PriorityQueue()

# Add items with priority - O(log n)
pq.put((1, 'high'))      # O(log 1)
pq.put((3, 'low'))       # O(log 2)
pq.put((2, 'medium'))    # O(log 3)

# Get items by priority (lowest first) - O(log n)
print(pq.get())  # O(log 3) - (1, 'high')
print(pq.get())  # O(log 2) - (2, 'medium')
print(pq.get())  # O(log 1) - (3, 'low')
```

## LIFO Queue (Stack)

```python
from queue import LifoQueue

# Create LIFO queue (stack) - O(1)
lifo = LifoQueue()

# Push items - O(1) amortized
lifo.put('a')  # O(1)
lifo.put('b')  # O(1)
lifo.put('c')  # O(1)

# Pop items (last in, first out) - O(1) amortized
print(lifo.get())  # O(1) - 'c'
print(lifo.get())  # O(1) - 'a'
```

## Simple Queue (Unbounded FIFO)

`SimpleQueue` is a simplified, unbounded FIFO queue available in Python 3.7+. It lacks task tracking (`task_done`/`join`) but is reentrant.

```python
from queue import SimpleQueue

# Create simple queue - O(1)
sq = SimpleQueue()

# Put items - O(1)
sq.put('simple')    # O(1), never blocks
sq.put('fast')      # O(1)

# Get items - O(1)
print(sq.get())     # O(1) - 'simple'
print(sq.qsize())   # O(1) - 1
print(sq.empty())   # O(1) - False
```

## Non-blocking Operations

```python
from queue import Queue, Empty, Full

# Create queue - O(1)
q = Queue(maxsize=2)

try:
    # Put without blocking - O(1)
    q.put_nowait('item1')  # O(1)
    q.put_nowait('item2')  # O(1)
    q.put_nowait('item3')  # Raises Full
except Full:
    print("Queue is full")

try:
    # Get without blocking - O(1)
    print(q.get_nowait())  # O(1) - 'item1'
    print(q.get_nowait())  # O(1) - 'item2'
    print(q.get_nowait())  # Raises Empty
except Empty:
    print("Queue is empty")
```

## Timeout Operations

```python
from queue import Queue, Empty, Full
import time

# Create queue - O(1)
q = Queue()

# Put with timeout - O(1) amortized
try:
    q.put('item', timeout=1.0)  # O(1), waits up to 1 second
    print("Item added")
except Full:
    print("Queue full, timeout expired")

# Get with timeout - O(1) amortized
try:
    item = q.get(timeout=1.0)  # O(1), waits up to 1 second
    print(f"Got: {item}")
except Empty:
    print("Queue empty, timeout expired")
```

## Thread Pool Pattern

```python
from queue import Queue
import threading

class ThreadPool:
    """Simple thread pool using Queue - O(1) operations"""
    
    def __init__(self, num_workers):
        self.task_queue = Queue()  # O(1)
        self.workers = []
        
        # Create worker threads - O(num_workers)
        for _ in range(num_workers):  # O(num_workers)
            worker = threading.Thread(
                target=self._worker,
                daemon=True
            )
            worker.start()  # O(1)
            self.workers.append(worker)  # O(1)
    
    def _worker(self):
        """Worker thread processes tasks - O(n)"""
        while True:  # O(n)
            task, args = self.task_queue.get()  # O(1)
            try:
                task(*args)  # Execute task
            finally:
                self.task_queue.task_done()  # O(1)
    
    def submit(self, task, args=()):
        """Submit task to queue - O(1)"""
        self.task_queue.put((task, args))  # O(1)
    
    def wait(self):
        """Wait for all tasks to complete - O(n)"""
        self.task_queue.join()  # O(n) - blocks until done

# Usage
def work(task_id):
    """Simulate work - O(1)"""
    print(f"Processing task {task_id}")

# Create pool with 3 workers - O(3)
pool = ThreadPool(3)

# Submit 10 tasks - O(10)
for i in range(10):  # O(10)
    pool.submit(work, (i,))  # O(1)

# Wait for completion - O(10)
pool.wait()
print("All tasks done")
```

## Common Patterns

### Work Distribution

```python
from queue import Queue
import threading
import random

# Create queue for work distribution - O(1)
work_queue = Queue()

# Add work items - O(n)
for i in range(100):  # O(100)
    work_queue.put(f"job_{i}")  # O(1)

# Distribute to 4 workers - O(4*n)
def worker(worker_id, queue):
    """Process work items - O(n)"""
    while True:  # O(n)
        try:
            job = queue.get_nowait()  # O(1)
            print(f"Worker {worker_id}: {job}")
            queue.task_done()  # O(1)
        except:
            break

# Start workers
for i in range(4):  # O(4)
    t = threading.Thread(target=worker, args=(i, work_queue))
    t.start()  # O(1)
```

### Rate Limiting

```python
from queue import Queue
import threading
import time

# Create queue with max size for rate limiting - O(1)
rate_limited_queue = Queue(maxsize=10)

def rate_limiter():
    """Control rate of processing - O(n)"""
    interval = 0.1  # Process one item every 100ms
    while True:  # O(n)
        item = rate_limited_queue.get()  # O(1)
        if item is None:  # Sentinel to exit
            break
        print(f"Processing at {time.time()}")
        rate_limited_queue.task_done()  # O(1)
        time.sleep(interval)

# Start rate limiter - O(1)
limiter = threading.Thread(target=rate_limiter, daemon=True)
limiter.start()

# Submit work (blocks if queue is full) - O(n)
for i in range(5):  # O(5)
    rate_limited_queue.put(f"item_{i}")  # O(1), blocks if full
```

## Queue vs Other Structures

```python
from queue import Queue
from collections import deque

# Queue (thread-safe) - O(1) operations
q = Queue()
q.put('item')  # O(1), thread-safe

# deque (not thread-safe) - O(1) operations
d = deque()
d.append('item')  # O(1), NOT thread-safe

# Use Queue for multi-threaded applications
# Use deque for single-threaded applications
```

## Version Notes

- **Python 2.6+**: queue module available
- **Python 3.7+**: `SimpleQueue` added
- **Python 3.x**: Same functionality
- **All versions**: O(1) for standard queue operations

## Related Modules

- **[deque](deque.md)** - Fast double-ended queue (not thread-safe)
- **[collections](collections.md)** - Container data types
- **[threading](threading.md)** - Thread-based parallelism
- **[multiprocessing](../stdlib/multiprocessing.md)** - Process-based parallelism

## Best Practices

✅ **Do**:

- Use Queue for thread-safe work distribution
- Use PriorityQueue for priority-based processing
- Use LifoQueue for stack-like behavior in threads
- Use timeouts to prevent deadlocks
- Call `task_done()` to track completion

❌ **Avoid**:

- Using Queue in single-threaded code (use `deque`)
- Forgetting to call `task_done()`
- Ignoring timeouts (risk of deadlock)
- Creating excessive queues (reuse when possible)
- Assuming thread safety elsewhere (only queue operations are safe)
