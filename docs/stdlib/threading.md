# threading Module Complexity

The `threading` module runs Python code in operating-system threads and provides the locks, conditions, semaphores, events and barriers that coordinate them. Every blocking call costs the time it spends blocked, written w below; the notes say what an operation does on top of that wait.

## Complexity Reference

Size variables: t = operating-system thread start latency, w = time spent blocked, W = threads waiting on the primitive, T = live threads, p = barrier parties, s = thread stack size, f = the caller's own function, whose time and space are its own. A wait given a timeout that expires also removes itself from the primitive's waiter queue, which is the O(W) term in the wait rows.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Thread()` | O(1) | O(1) | Builds the object; nothing runs, and `enumerate()` does not list it, until `start()` |
| `Thread.start()` | O(t) | O(s) | Returns once the new thread has started and stored its `ident`; s is set by `stack_size()` |
| `Thread.run()` | O(f) | O(f) | Calls the target once, or nothing without one; `start()` runs it in the new thread, a direct call in the caller's |
| `Thread.join()` | O(w) | O(1) | Immediate on a finished thread; a timeout returns with the thread still alive |
| `Thread.is_alive()` | O(1) | O(1) | |
| `Thread.name/ident/native_id/daemon` | O(1) | O(1) | `ident` and `native_id` are None until started |
| `Thread.getName()/setName()/isDaemon()/setDaemon()` | O(1) | O(1) | Deprecated aliases; each call also emits a DeprecationWarning |
| `Timer()` | O(1) | O(1) | A `Thread` subclass; `start()` spawns the thread |
| `Timer.run()` | O(w + f) | O(f) | Waits the interval, then calls the function once |
| `Timer.cancel()` | O(1) | O(1) | Sets an event; a timer still waiting ends at once instead of after the interval, one already in its function finishes it |
| `Lock()` / `RLock()` | O(1) | O(1) | |
| `Lock.acquire()` | O(w) | O(1) | Immediate when free; w = wait for the holder or the timeout |
| `Lock.release()` | O(1) | O(1) | Raises RuntimeError when the lock is not held |
| `Lock.locked()` | O(1) | O(1) | |
| `RLock.acquire()` | O(w) | O(1) | Immediate for the owner, which only increments a count |
| `RLock.release()` | O(1) | O(1) | Frees the lock only when the count returns to zero |
| `RLock.locked()` | O(1) | O(1) | Python 3.14+ |
| `Condition()` | O(1) | O(1) | Wraps the lock given, or a new `RLock` |
| `Condition.acquire()` / `Condition.release()` | O(w) | O(1) | The underlying lock's own methods |
| `Condition.locked()` | O(1) | O(1) | Python 3.14+; the underlying lock's |
| `Condition.wait()` | O(w + W) | O(1) | Releases the lock, waits, re-acquires |
| `Condition.wait_for()` | O(w + W + c·f) | O(f) | c = predicate calls, one before waiting and one per wakeup |
| `Condition.notify()` | O(n) | O(1) | Wakes the n oldest waiters, n = 1 by default |
| `Condition.notify_all()` | O(W) | O(1) | |
| `Condition.notifyAll()` | O(W) | O(1) | Deprecated alias, plus a DeprecationWarning |
| `Semaphore()` / `BoundedSemaphore()` | O(1) | O(1) | |
| `Semaphore.acquire()` | O(w + W) | O(1) | Immediate while the counter is positive |
| `Semaphore.release()` | O(n) | O(1) | Adds n to the counter and wakes up to n waiters |
| `BoundedSemaphore.release()` | O(n) | O(1) | As `Semaphore.release()`, but raises ValueError past the initial value |
| `Event()` | O(1) | O(1) | |
| `Event.set()` | O(W) | O(1) | Wakes every waiter |
| `Event.clear()` | O(1) | O(1) | |
| `Event.is_set()` | O(1) | O(1) | |
| `Event.isSet()` | O(1) | O(1) | Deprecated alias, plus a DeprecationWarning |
| `Event.wait()` | O(w + W) | O(1) | Immediate once set |
| `Barrier()` | O(1) | O(1) | |
| `Barrier.wait()` | O(w + W + p + f) | O(f) | The last of p parties runs the action, f, and wakes the others; a timeout that expires breaks the barrier |
| `Barrier.reset()` / `Barrier.abort()` | O(w + W) | O(1) | Wake every waiter; a party still waiting for the barrier to fill raises BrokenBarrierError. w = a running action, which holds the barrier's lock |
| `Barrier.parties/n_waiting/broken` | O(1) | O(1) | |
| `local()` | O(1) | O(1) | |
| `local` attribute access | O(1) | O(a) per thread | Each thread that touches the object gets its own dict of a attributes; the first access in a thread also re-runs a subclass's `__init__` with the original arguments, at that `__init__`'s own cost |
| `current_thread()` | O(1) | O(1) | One dict lookup |
| `main_thread()` | O(1) | O(1) | |
| `active_count()` | O(1) | O(1) | Two dict lengths |
| `enumerate()` | O(T) | O(T) | A new list of every live thread |
| `get_ident()` / `get_native_id()` | O(1) | O(1) | |
| `activeCount()` / `currentThread()` | O(1) | O(1) | Deprecated aliases, plus a DeprecationWarning |
| `settrace()` / `setprofile()` | O(1) | O(1) | Stores the hook for threads started afterwards; running threads are not touched |
| `settrace_all_threads()` / `setprofile_all_threads()` | O(T) | O(1) | Python 3.12+; also installs the hook in every running thread |
| `gettrace()` / `getprofile()` | O(1) | O(1) | |
| `stack_size()` | O(1) | O(1) | Returns the previous size and sets the one for threads started afterwards; no argument means the platform default, and 1 to 32 KiB raises ValueError |
| `excepthook()` | O(b) | O(b) | Called once per unhandled exception in a thread; b = the size of the traceback it prints |
| `ExceptHookArgs()` | O(1) | O(1) | Four-field record |
| `TIMEOUT_MAX` | O(1) | O(1) | The largest timeout a wait that blocks accepts; larger values raise OverflowError |
| `ThreadError` / `BrokenBarrierError` | O(1) | O(1) | `ThreadError` is `RuntimeError`; `BrokenBarrierError` subclasses it |

## Basic Threading

```python
import threading
import time

# Define function - O(1)
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

# Create threads - O(n) total
threads = []
for i in range(5):
    t = threading.Thread(target=task, args=(i,))  # O(1)
    threads.append(t)
    t.start()  # O(t)

# Wait all - O(n + sum of waits)
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

# Safe - O(1) lock operations when uncontended
def increment_safe():
    global counter
    with lock:  # O(w) - acquire, immediate when free
        counter += 1
    # O(1) - release on exit

def repeat(func, times):
    for _ in range(times):
        func()

threads = [threading.Thread(target=repeat, args=(increment_safe, 10_000)) for _ in range(4)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(counter)  # 40000
```

## Coordinating Threads

```python
import threading

ready = threading.Event()
slots = threading.Semaphore(2)
finish = threading.Barrier(3)
order = []

def worker(name):
    ready.wait()  # O(w) - immediate once set
    with slots:  # O(w) - at most two workers inside at once
        order.append(name)
    finish.wait()  # O(w + p) - the last arrival wakes the other two

threads = [threading.Thread(target=worker, args=(n,)) for n in "abc"]
for t in threads:
    t.start()

ready.set()  # O(W) - wakes every worker already waiting; later ones pass straight through
for t in threads:
    t.join()
print(sorted(order))  # ['a', 'b', 'c']
```

## Thread-Local Data

```python
import threading

class Context(threading.local):
    def __init__(self, user):
        self.user = user  # runs again in each thread that touches the object

context = Context("default")

def show():
    print(context.user)  # default - this thread's own copy
    context.user = "worker"

thread = threading.Thread(target=show)
thread.start()
thread.join()
print(context.user)  # default - the worker's assignment stayed in its thread
```

## Version Notes

- **Python 3.10+**: `activeCount()`, `currentThread()`, `notifyAll()`, `isSet()`, `getName()`, `setName()`, `isDaemon()` and `setDaemon()` emit DeprecationWarning
- **Python 3.12+**: `settrace_all_threads()` and `setprofile_all_threads()` added
- **Python 3.13+**: the optional free-threaded build runs Python code in parallel without the GIL; the default build still holds the GIL while running bytecode, so only native code that releases it runs in parallel
- **Python 3.14+**: `RLock.locked()` added; passing arguments to `RLock()` is deprecated

## Best Practices

✅ **Do**:

- Use locks for shared resources
- Use context managers for locks
- Set daemon=True for background threads

❌ **Avoid**:

- Sharing mutable objects without locks
- CPU-bound tasks (use multiprocessing)
- Deadlocks (acquire locks in order)
