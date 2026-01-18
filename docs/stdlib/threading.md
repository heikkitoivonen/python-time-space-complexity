# threading Module Complexity

The `threading` module enables building multi-threaded applications using threads for concurrent execution within a single process.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Thread()` | O(1) | O(1) | Create thread object |
| `start()` | O(t) | O(s) | t = thread startup, s = stack |
| `join()` | O(w) | O(1) | w = wait time |
| Lock operations | O(1) | O(1) | Mutex acquire/release; may block waiting for lock |

## Basic Threading

```python
import threading
import time

# Define function - O(n)
def worker():
    print("Worker running")
    time.sleep(1)  # O(1) - sleep

# Create thread - O(1)
thread = threading.Thread(target=worker)

# Start thread - O(t)
thread.start()  # O(t) - thread startup

# Wait for completion - O(w)
thread.join()  # O(w) - wait
```

## Multiple Threads

```python
import threading

def task(name):
    print(f"Task {name}")

# Create threads - O(n)
threads = []
for i in range(5):
    t = threading.Thread(target=task, args=(i,))  # O(1)
    threads.append(t)
    t.start()  # O(t)

# Wait all - O(n*w)
for t in threads:
    t.join()  # O(w) each
```

## Thread Safety with Locks

```python
import threading

# Shared resource
counter = 0
lock = threading.Lock()

# Unsafe
def increment_unsafe():
    global counter
    counter += 1  # Race condition!

# Safe - O(1) lock operations
def increment_safe():
    global counter
    with lock:  # O(1) - acquire
        counter += 1
    # O(1) - release on exit
```

## Version Notes

- **Python 2.x**: threading available
- **Python 3.x**: Same with improvements
- **Note**: GIL limits true parallelism for CPU tasks

## Best Practices

✅ **Do**:

- Use locks for shared resources
- Use context managers for locks
- Use Thread objects
- Set daemon=True for background threads

❌ **Avoid**:

- Sharing mutable objects without locks
- CPU-bound tasks (use multiprocessing)
- Deadlocks (acquire locks in order)
