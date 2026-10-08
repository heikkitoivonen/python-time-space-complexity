# threading Module Complexity

The `threading` module runs Python code in operating-system threads and provides the locks,
conditions, semaphores, events and barriers that coordinate them. Starting a thread costs an OS
thread and its stack. `Event`, `Semaphore` and `Barrier` are built on a `Condition`, which keeps a
queue of the threads waiting on it.

Every blocking call costs the time it spends blocked, `w`: the wait for another thread, or the
timeout. `u` is the operating system's thread start-up latency, `s` is the stack size of a new
thread, `q` is the number of threads queued on the primitive, `T` is the number of live threads,
`n` is the count passed to `notify(n)` or `release(n)`, and `f` is a function the caller supplies,
whose time and space are its own. A wait whose timeout expires removes itself from the
primitive's waiter queue, which is the O(q) term in the wait rows.

## Complexity Reference

### Thread

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Thread(group=None, target=None, name=None, args=(), kwargs=None, *, daemon=None)` | O(1) | O(1) | Nothing runs, and `enumerate()` does not list it, until `start()` |
| `Thread.start()` | O(u) | O(s) | Returns once the new thread is running and has stored its `ident` |
| `Thread.run()` | O(f) | O(f) | Calls the target once, or nothing without one; `start()` runs it in the new thread, a direct call in the caller's |
| `Thread.join(timeout=None)` | O(w) | O(1) | Immediate on a finished thread; a timeout that expires returns with the thread still alive |
| `Thread.is_alive()` | O(1) | O(1) | |
| `Thread.name`, `Thread.ident`, `Thread.native_id`, `Thread.daemon` | O(1) | O(1) | `ident` and `native_id` are None until started |
| `Thread.getName()`, `Thread.setName()`, `Thread.isDaemon()`, `Thread.setDaemon()` | O(1) | O(1) | Deprecated aliases; each call emits a DeprecationWarning |

### Timer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Timer(interval, function, args=None, kwargs=None)` | O(1) | O(1) | A `Thread` subclass; `start()` spawns the thread |
| `Timer.run()` | O(w + f) | O(f) | Waits the interval, then calls the function once |
| `Timer.cancel()` | O(1) | O(1) | A timer still waiting ends at once instead of after the interval; one already in its function finishes it |

### Lock and RLock

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Lock()`, `RLock()` | O(1) | O(1) | |
| `Lock.acquire(blocking=True, timeout=-1)` | O(w) | O(1) | Immediate when free |
| `Lock.release()` | O(1) | O(1) | Raises RuntimeError when the lock is not held |
| `Lock.locked()` | O(1) | O(1) | |
| `RLock.acquire(blocking=True, timeout=-1)` | O(w) | O(1) | Immediate for the owner, which only increments a count |
| `RLock.release()` | O(1) | O(1) | Frees the lock only when the count returns to zero |
| `RLock.locked()` | O(1) | O(1) | Python 3.14+ |

### Condition

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Condition(lock=None)` | O(1) | O(1) | Wraps the lock given, or a new `RLock` |
| `Condition.acquire()`, `Condition.release()` | O(w) | O(1) | The underlying lock's own methods |
| `Condition.locked()` | O(1) | O(1) | Python 3.14+; the underlying lock's |
| `Condition.wait(timeout=None)` | O(w + q) | O(1) | Releases the lock, waits, re-acquires |
| `Condition.wait_for(predicate, timeout=None)` | O(w + q + c·f) | O(f) | c = predicate calls: one before waiting and one per wakeup |
| `Condition.notify(n=1)` | O(n) | O(1) | Wakes the n oldest waiters |
| `Condition.notify_all()` | O(q) | O(1) | |
| `Condition.notifyAll()` | O(q) | O(1) | Deprecated alias; each call emits a DeprecationWarning |

### Semaphore and BoundedSemaphore

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Semaphore(value=1)`, `BoundedSemaphore(value=1)` | O(1) | O(1) | |
| `Semaphore.acquire(blocking=True, timeout=None)` | O(w + q) | O(1) | Immediate while the counter is positive |
| `Semaphore.release(n=1)` | O(n) | O(1) | Adds n to the counter and wakes up to n waiters |
| `BoundedSemaphore.release(n=1)` | O(n) | O(1) | As `Semaphore.release()`, but raises ValueError past the initial value |

### Event

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Event()` | O(1) | O(1) | |
| `Event.set()` | O(q) | O(1) | Wakes every waiter |
| `Event.clear()` | O(1) | O(1) | |
| `Event.is_set()` | O(1) | O(1) | |
| `Event.isSet()` | O(1) | O(1) | Deprecated alias; each call emits a DeprecationWarning |
| `Event.wait(timeout=None)` | O(w + q) | O(1) | Immediate once set |

### Barrier

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Barrier(parties, action=None, timeout=None)` | O(1) | O(1) | |
| `Barrier.wait(timeout=None)` | O(w + q + f) | O(f) | The last of the parties runs the action, f, and wakes the others; a timeout that expires breaks the barrier |
| `Barrier.reset()`, `Barrier.abort()` | O(w + q) | O(1) | Wake every waiter; a party still waiting for the barrier to fill raises BrokenBarrierError. w includes a running action, which holds the barrier's lock |
| `Barrier.parties`, `Barrier.n_waiting`, `Barrier.broken` | O(1) | O(1) | |

### local

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `local()` | O(1) | O(1) | |
| `local` attribute access | O(1) | O(1) | Each thread that touches the object gets its own attribute dict; the first access in a thread also re-runs a subclass's `__init__` with the original arguments, at that `__init__`'s own cost |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `current_thread()` | O(1) | O(1) | |
| `main_thread()` | O(1) | O(1) | |
| `active_count()` | O(1) | O(1) | |
| `enumerate()` | O(T) | O(T) | A new list of every live thread |
| `get_ident()`, `get_native_id()` | O(1) | O(1) | |
| `activeCount()`, `currentThread()` | O(1) | O(1) | Deprecated aliases; each call emits a DeprecationWarning |
| `settrace(func)`, `setprofile(func)` | O(1) | O(1) | Stores the hook for threads started afterwards; running threads are not touched |
| `settrace_all_threads(func)`, `setprofile_all_threads(func)` | O(T) | O(1) | Python 3.12+; also installs the hook in every running thread |
| `gettrace()`, `getprofile()` | O(1) | O(1) | |
| `stack_size([size])` | O(1) | O(1) | Returns the previous size and sets the one for threads started afterwards; no argument means the platform default, and a size below the platform's minimum, never less than 32 KiB, raises ValueError |
| `excepthook(args)` | O(b) | O(b) | Called once per unhandled exception in a thread; b = the size of the traceback it prints |

### ExceptHookArgs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ExceptHookArgs` | O(1) | O(1) | The four-field record `excepthook()` receives |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TIMEOUT_MAX` | O(1) | O(1) | The largest timeout a lock acquire or a `Condition`, `Event`, `Semaphore` or `Barrier` wait accepts; larger values raise OverflowError |
| `ThreadError`, `BrokenBarrierError` | O(1) | O(1) | `ThreadError` is `RuntimeError`; `BrokenBarrierError` subclasses it |

## Starting and Joining Threads

Building a `Thread` starts nothing. `start()` pays for an OS thread and its
stack and returns once the thread is running; `join()` costs only the wait, and returns at once
when the thread has already finished.

```python
import threading

results = []

def task(name):
    results.append(name)

threads = [threading.Thread(target=task, args=(i,)) for i in range(5)]  # O(1) each
assert threads[0].ident is None  # nothing has started yet

for thread in threads:
    thread.start()  # O(u) - returns once the thread is running
for thread in threads:
    thread.join()   # O(w) - immediate once the thread has finished

assert sorted(results) == [0, 1, 2, 3, 4]
assert not any(thread.is_alive() for thread in threads)  # O(1) each
```

### Timers

A `Timer` is a thread that waits before calling its function. Cancelling one that is still waiting
ends its thread at once, so a long interval does not keep `join()` waiting.

```python
import threading

fired = []
timer = threading.Timer(60, fired.append, args=['late'])  # O(1)
timer.start()   # O(u)
timer.cancel()  # O(1) - the waiting thread wakes and exits
timer.join()    # O(w) - no 60-second wait

assert fired == []
assert not timer.is_alive()
```

## Locks

An uncontended `acquire()` returns at once; a contended one waits for the holder, or for its
timeout. A `with` block releases the lock even when the body raises. An `RLock` lets its owner
acquire it again without waiting.

```python
import threading

counter = 0
lock = threading.Lock()

def increment(times):
    global counter
    for _ in range(times):
        with lock:  # O(w) - immediate when free; released on exit in O(1)
            counter += 1

threads = [threading.Thread(target=increment, args=(10_000,)) for _ in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
assert counter == 40_000

lock.acquire()
assert lock.acquire(timeout=0.01) is False  # O(w) - gives up after the timeout
lock.release()

rlock = threading.RLock()
with rlock:
    with rlock:  # O(1) - the owner only increments a count
        pass
```

## Waiting and Waking

A `Condition` keeps a queue of its waiters. `notify(n)` wakes the n oldest and costs O(n);
`notify_all()` wakes all q. A wait whose timeout expires removes itself from that queue, which is
O(q): `Event`, `Semaphore` and `Barrier` are built on a `Condition`, so their timed waits pay the
same.

```python
import threading

condition = threading.Condition()
items = []
taken = []

def consumer():
    with condition:
        condition.wait_for(lambda: items)  # O(w + q + c) - the predicate runs once per wakeup
        taken.append(items.pop())

threads = [threading.Thread(target=consumer) for _ in range(3)]
for thread in threads:
    thread.start()

for value in range(3):
    with condition:
        items.append(value)
        condition.notify()  # O(1) - wakes the oldest waiter only

for thread in threads:
    thread.join()
assert sorted(taken) == [0, 1, 2]

with condition:
    assert condition.wait(timeout=0.01) is False  # O(w + q) - expires and leaves the queue
```

### Event, Semaphore and Barrier

```python
import threading

ready = threading.Event()
slots = threading.Semaphore(2)
finish = threading.Barrier(3)
order = []

def worker(name):
    ready.wait()  # O(w + q) - immediate once set
    with slots:  # O(w + q) - at most two workers inside at once
        order.append(name)
    finish.wait()  # O(w + q) - the last arrival wakes the other two

threads = [threading.Thread(target=worker, args=(name,)) for name in "abc"]
for thread in threads:
    thread.start()

ready.set()  # O(q) - wakes every worker already waiting; later ones pass straight through
for thread in threads:
    thread.join()
assert sorted(order) == ['a', 'b', 'c']
assert finish.n_waiting == 0 and not finish.broken  # O(1)
```

## Thread-Local Data

A `local` gives each thread its own attribute dict. For a subclass, the first access from a
thread runs `__init__` again with the arguments the object was built with, so that cost is paid
once per thread that touches it.

```python
import threading

inits = []

class Context(threading.local):
    def __init__(self, user):
        inits.append(user)  # runs again in each thread that touches the object
        self.user = user

context = Context("default")
seen = []

def show():
    seen.append(context.user)  # O(1) - this thread's own copy, from a fresh __init__
    context.user = "worker"

thread = threading.Thread(target=show)
thread.start()
thread.join()

assert seen == ["default"]
assert context.user == "default"  # the worker's assignment stayed in its thread
assert inits == ["default", "default"]
```

## Common Patterns

### A Background Worker With a Stop Event

`Event.wait(timeout)` doubles as an interruptible sleep: it returns `True` as soon as the event is
set, so the worker stops without finishing its current interval.

```python
import threading

stop = threading.Event()
ticks = []

def heartbeat():
    while not stop.wait(0.001):  # O(w + q) - returns True as soon as stop is set
        ticks.append(1)

worker = threading.Thread(target=heartbeat, daemon=True)
worker.start()
stop.set()  # O(q)
worker.join(timeout=5)  # O(w)

assert not worker.is_alive()
```

## Performance Best Practices

✅ **Do**:

- Reuse a fixed set of threads, or a `concurrent.futures.ThreadPoolExecutor`, for many short tasks:
  every `start()` pays for an OS thread and its stack
- Hold locks with `with`, so the release runs even when the body raises
- Wake with `notify(n)` when only n waiters can proceed; `notify_all()` wakes all q, and each
  must then re-acquire the lock in turn
- Call `active_count()` when the count is all you need: `len(enumerate())` builds an O(T) list
- Block in `join()` or `wait()` rather than polling `is_alive()` or `is_set()` in a loop: a
  blocked thread uses no CPU while it waits

❌ **Avoid**:

- Pure-Python CPU-bound work in threads on the default build: one thread runs bytecode at a time,
  so threads add start-up cost without a parallel speed-up; use `multiprocessing`, or the
  free-threaded build

## Version Notes

- **Python 3.10+**: `activeCount()`, `currentThread()`, `notifyAll()`, `isSet()`, `getName()`,
  `setName()`, `isDaemon()` and `setDaemon()` emit DeprecationWarning
- **Python 3.12+**: `settrace_all_threads()` and `setprofile_all_threads()` added
- **Python 3.13+**: the optional free-threaded build runs Python code in parallel without the GIL;
  the default build still runs bytecode in one thread at a time
- **Python 3.14+**: `RLock.locked()` added; passing arguments to `RLock()` is deprecated

## Related Modules

- **[queue](queue.md)** - Thread-safe FIFO, LIFO and priority queues for handing work between
  threads
- **[concurrent.futures](concurrent_futures.md)** - Thread and process pools that reuse their
  workers
- **[multiprocessing](multiprocessing.md)** - Processes instead of threads, for CPU-bound Python
  code on the default build
- **[contextvars](contextvars.md)** - Context-local state that also follows asyncio tasks
- **[asyncio](asyncio.md)** - Many concurrent I/O tasks on one thread
