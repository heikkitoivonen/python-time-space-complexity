# multiprocessing Module Complexity

The `multiprocessing` module runs Python code in separate operating-system processes, each with its own interpreter and memory. Nothing is shared by default: except for what a `fork` child inherits and the shared-memory objects, everything a process, pool, queue, pipe or manager carries crosses a pipe as bytes, pickled unless sent with `send_bytes()`, so the size that governs most rows is the pickled size of what is sent, not the number of calls. Every blocking call also costs the time it spends blocked.

## Complexity Reference

Size variables: a = arguments given to `Process()`, s = the time to start one process (a fork of the caller, for `forkserver` a fork of the warm server, for `spawn` a fresh interpreter; the last two also unpickle what they are sent), w = time spent blocked, b = pickled size of the objects an operation sends and receives, at pickle's cost per byte - a `__getstate__` or `__reduce__` of the caller's own is the caller's, like f - n = items, p = worker processes in a pool, k = child processes started and not yet joined, m = one round trip to a manager's server process, f = the caller's own function, whose time and space are its own, e = elements in a shared array, d = how many times the caller holds a recursive lock, W = processes or threads waiting on a primitive. Under the `spawn` and `forkserver` start methods the first synchronization primitive or queue created, which a `Value()`, `Array()` or `Pool()` includes, also starts the resource tracker process, once, at O(s).

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Process()` | O(a) | O(a) | Copies the a arguments; nothing runs, and `active_children()` does not list it, until `start()` |
| `Process.start()` | O(k + s + b) | O(k + b) | Polls every live child first, through a copy of the list; `fork` sends nothing through Python, `spawn` and `forkserver` pickle the process object, target and arguments included, b bytes, and send it to the child |
| `Process.run()` | O(f) | O(f) | Calls the target once, or nothing without one; `start()` runs it in the child, a direct call in the caller |
| `Process.join()` | O(w) | O(1) | Immediate on a finished process; a timeout returns with the process still alive |
| `Process.is_alive()` | O(1) | O(1) | One non-blocking poll |
| `Process.terminate()` / `Process.kill()` / `Process.interrupt()` | O(1) | O(1) | Send SIGTERM, SIGKILL or SIGINT and return at once; `join()` waits for the exit. `interrupt()` is Python 3.14+ |
| `Process.close()` | O(1) | O(1) | Raises ValueError while the process is alive; afterwards `is_alive()`, `join()`, `exitcode` and `pid` raise ValueError |
| `Process.name/daemon/authkey/pid/ident/exitcode/sentinel` | O(1) | O(1) | `pid`, `ident` and `exitcode` are None and `sentinel` raises ValueError until `start()`; `exitcode` polls |
| `current_process()` / `parent_process()` | O(1) | O(1) | `parent_process()` is None in the main process |
| `active_children()` | O(k) | O(k) | Polls every child and returns a new list of the ones still alive |
| `Pool()` | O(p·(s + k)) | O(p) | Starts p workers, each start polling the children so far, default `os.process_cpu_count()` (`os.cpu_count()` before Python 3.13), and three handler threads |
| `Pool.map()` / `Pool.starmap()` | O(n + b + w) | O(n + b) | Blocks for every result; an iterable without `len()` is first copied to a list. The items go out in chunks of c, default ⌈n / 4p⌉, and f is pickled once per chunk, so `chunksize=1` pickles it n times |
| `Pool.map_async()` / `Pool.starmap_async()` | O(n) | O(n) | Returns once the input is listed and a result slot per item allocated; the chunking, pickling and sending happen in a handler thread |
| `Pool.apply()` | O(b + w) | O(b) | One task, blocked on until its result is back |
| `Pool.apply_async()` | O(1) | O(1) | Queues one task for the handler thread |
| `Pool.imap()` / `Pool.imap_unordered()` | O(1) | O(1) | Consumes the input lazily, chunked by c, default 1, so f is pickled n times unless `chunksize` is passed; each `next()` is O(w + b) for its item |
| `Pool.imap()` iteration | O(n + b + w) | O(n + b) | Results are buffered as they arrive whether or not they are consumed, and `imap()` also holds any that arrive ahead of their turn, so a slow consumer costs O(n) space |
| `AsyncResult.get()` / `AsyncResult.wait()` | O(w) | O(1) | The result was unpickled by the handler thread on arrival; `get(timeout)` raises `multiprocessing.TimeoutError`, which is not the builtin. A callback runs in that handler thread, before `ready()` turns true, so keep it O(1) |
| `AsyncResult.ready()` / `AsyncResult.successful()` | O(1) | O(1) | `successful()` raises ValueError until ready |
| `Pool.close()` | O(1) | O(1) | Refuses new tasks; queued ones still run |
| `Pool.join()` | O(w + p) | O(1) | Raises ValueError unless `close()` or `terminate()` came first |
| `Pool.terminate()` | O(w + p + q + b) | O(b) | Drains and unpickles the q tasks still queued, kills every worker and joins it and the handler threads, w = a callback or input generator one of them is still in. `with Pool() as pool:` calls this on exit, so work still running is lost, not waited for |
| `Queue()` / `JoinableQueue()` / `SimpleQueue()` | O(1) | O(1) | A pipe and its locks; `maxsize` defaults to the largest semaphore value |
| `Queue.put()` / `Queue.put_nowait()` | O(w) | O(1) | Waits for a slot when full, appends to a buffer and returns; a feeder thread pickles and writes it, concurrently with the caller, so the object is pickled as it is when the feeder reaches it, and an unpicklable one fails in that thread, not in `put()` |
| `Queue.get()` / `Queue.get_nowait()` | O(w + b) | O(b) | Reads one message under the reader lock and unpickles it after releasing the lock |
| `Queue.qsize()` / `Queue.empty()` / `Queue.full()` | O(1) | O(1) | `qsize()` counts items put and not yet got, `empty()` polls the pipe, so it stays true until the feeder has written |
| `Queue.close()` / `Queue.cancel_join_thread()` | O(1) | O(1) | `close()` lets the feeder finish what is buffered; a later `put()` or `get()` raises ValueError |
| `Queue.join_thread()` | O(w) | O(1) | Waits for the feeder to flush the buffer; requires `close()` first |
| `JoinableQueue.task_done()` | O(W) | O(1) | Wakes every `join()` when the count reaches zero; one call too many raises ValueError |
| `JoinableQueue.join()` | O(w) | O(1) | |
| `SimpleQueue.put()` | O(b + w) | O(b) | Pickles in the caller and writes under the writer lock; w = the wait for pipe space |
| `SimpleQueue.get()` | O(w + b) | O(b) | |
| `SimpleQueue.empty()` / `SimpleQueue.close()` | O(1) | O(1) | |
| `Pipe()` | O(1) | O(1) | A socket pair, or a one-way pipe with `duplex=False` |
| `Connection.send()` / `Connection.send_bytes()` | O(b + w) | O(b) | `send()` pickles in the caller; w = the wait for the reader once the operating-system buffer is full |
| `Connection.recv()` / `Connection.recv_bytes()` | O(w + b) | O(b) | One whole message; `recv_bytes(maxlength)` raises OSError past the limit |
| `Connection.recv_bytes_into()` | O(w + b) | O(b) | Copied into the caller's buffer from a temporary one; too small a buffer raises BufferTooShort carrying the message |
| `Connection.poll()` | O(w) | O(1) | Immediate by default; a timeout is honoured |
| `Connection.fileno()` / `Connection.close()` / `Connection.closed/readable/writable` | O(1) | O(1) | |
| `Lock()` / `RLock()` / `Semaphore()` / `BoundedSemaphore()` | O(1) | O(1) | One named semaphore each |
| `Lock.acquire()` / `RLock.acquire()` | O(w) | O(1) | Immediate when free, and for an `RLock` owner |
| `Lock.release()` / `RLock.release()` | O(1) | O(1) | `Lock` raises ValueError when not held, `RLock` AssertionError |
| `Lock.locked()` / `RLock.locked()` / `Semaphore.locked()` | O(1) | O(1) | Python 3.14+; true while the count is zero |
| `Semaphore.acquire()` / `Semaphore.release()` | O(w) | O(1) | `release()` is immediate; `BoundedSemaphore` raises ValueError past its initial value |
| `Semaphore.get_value()` | O(1) | O(1) | NotImplementedError on macOS |
| `Condition()` | O(1) | O(1) | An `RLock`, or the lock given, plus three semaphores |
| `Condition.acquire()` / `Condition.release()` | O(w) | O(1) | The underlying lock's |
| `Condition.wait()` | O(w + d) | O(1) | Releases the lock d times, waits, re-acquires it d times |
| `Condition.wait_for()` | O(w + c·(f + d)) | O(f) | c = predicate calls, one before waiting and one per wakeup |
| `Condition.notify()` | O(n + t + w) | O(1) | Wakes up to n sleepers, one by default, and waits for each to acknowledge, so a sleeper killed mid-wait blocks it for good; first clears the bookkeeping of the t waits that timed out since the last notify |
| `Condition.notify_all()` | O(W + t + w) | O(1) | `notify()` for every sleeper, bookkeeping included |
| `Event()` | O(1) | O(1) | |
| `Event.set()` | O(W + t + w) | O(1) | Wakes every waiter, as `notify_all()` |
| `Event.clear()` / `Event.is_set()` | O(w) | O(1) | Both take the event's lock |
| `Event.wait()` | O(w) | O(1) | Immediate once set |
| `Barrier()` | O(1) | O(1) | Two shared integers and a `Condition` |
| `Barrier.wait()` | O(w + W + f) | O(f) | The last of the parties runs the action, f, and wakes the others; a timeout that expires breaks the barrier |
| `Barrier.reset()` / `Barrier.abort()` | O(W + w) | O(1) | Wake every waiter with BrokenBarrierError |
| `Barrier.parties/n_waiting/broken` | O(1) | O(1) | |
| `RawValue()` / `Value()` | O(z) | O(z) | One block of shared memory, z = the type's size in bytes, zeroed; `Value()` adds an `RLock` unless `lock=False`, which returns the raw ctypes object |
| `RawArray()` / `Array()` | O(e·z) | O(e·z) | e elements of z bytes of shared memory, zeroed or copied from the sequence; the memory is shared with children, not copied to them |
| `Value.value` | O(w) | O(1) | Under the wrapper's lock, w = the wait for it; a `c_char` array's `value` copies its bytes, O(z) |
| `Array[i]` | O(w) | O(1) | Under the lock |
| `len(Array)` | O(1) | O(1) | Takes no lock |
| `Array[i:j]` | O(w + j − i) | O(j − i) | A new list, or bytes for a `c` array and str for a `u` array, under the lock |
| `Value.get_lock()/get_obj()/acquire()/release()` | O(w) | O(1) | The wrapper's `RLock` and raw object; only `acquire()` waits, and `with value:` holds the lock |
| `Manager()` | O(k + s + m) | O(k) | `Process.start()` for a server process, then waits for its address |
| `Manager.list()/dict()/set()/Namespace()/Value()/Array()/Queue()/JoinableQueue()/Lock()/RLock()/Semaphore()/BoundedSemaphore()/Condition()/Event()/Barrier()/Pool()` | O(m + b + f) | O(b) | Creates the object in the server, at its constructor's own cost f - `Pool()` there starts its workers - and returns a proxy; the initial value crosses as b bytes. `set()` is Python 3.14+ |
| Proxy method call | O(m + b + f) | O(b) | Every call is a round trip, and a thread's first call opens its connection with another: the arguments are pickled, the server runs the method, f, and the result is pickled back, a result that is itself a proxy costing further trips. Iterating a list or dict proxy is at least a round trip per element; `proxy[:]` on a list and `copy()`, `keys()`, `values()` or `items()` on a dict copy it in one |
| `Manager.start()` | O(k + s + m + b) | O(k + b) | Already called by `Manager()`; a second call raises ProcessError. b = the registry, the initializer and its arguments, pickled under `spawn` and `forkserver` |
| `Manager.connect()` | O(m) | O(1) | Reaches a server another process started; nothing is spawned |
| `Manager.shutdown()` / `Manager.join()` | O(w) | O(1) | `shutdown()` exists only once started; `with manager:` calls it on exit |
| `Manager.register()` | O(R) | O(R) | A classmethod adding a type to the manager class; the first call on a subclass first copies the R types it inherits |
| `Manager.get_server()` / `Manager.address` | O(1) | O(1) | |
| `cpu_count()` | O(1) | O(1) | `os.cpu_count()`, raising NotImplementedError where it is None |
| `get_context()` / `get_start_method()` / `set_start_method()` / `get_all_start_methods()` | O(1) | O(1) | A second `set_start_method()` raises RuntimeError unless `force=True`; `get_all_start_methods()` is a new list each call |
| `get_logger()` / `log_to_stderr()` | O(1) | O(1) | One logger, created on first use; every `log_to_stderr()` call adds another handler |
| `freeze_support()` / `set_executable()` / `allow_connection_pickling()` | O(1) | O(1) | Store a setting, or do nothing outside a frozen executable |
| `set_forkserver_preload()` | O(r) | O(1) | Checks that each of the r names is a str and keeps the list; the forkserver imports them when it starts |
| `ProcessError` / `BufferTooShort` / `TimeoutError` / `AuthenticationError` | O(1) | O(1) | The last three subclass `ProcessError` |
| `SUBDEBUG` / `SUBWARNING` | O(1) | O(1) | Logging levels 5 and 25 |
| `reducer` | O(1) | O(1) | The `reduction` module, whose `ForkingPickler` every object transfer uses |

Submodules reached only by import, such as `multiprocessing.shared_memory` and `multiprocessing.connection`'s `Listener`, `Client` and `wait()`, are not covered here.

## Starting Processes

```python
from multiprocessing import Process, current_process

def work(n):
    print(f"{current_process().name} squares {n}: {n * n}")

if __name__ == "__main__":
    p = Process(target=work, args=(7,), name="worker")  # O(a) - nothing runs yet
    p.start()  # O(k + s + b) - under spawn or forkserver the args are pickled
    p.join()  # O(w)
    print(p.exitcode)  # 0
```

The `if __name__ == "__main__":` guard is required under `spawn` and `forkserver`, which import the main module in each child. One of the two is the default everywhere from Python 3.14, and on macOS and Windows before it.

## Pool

```python
from multiprocessing import Pool

def square(n):
    return n * n

if __name__ == "__main__":
    with Pool(processes=2) as pool:  # O(p·s)
        total = sum(pool.map(square, range(1000)))  # O(n + b + w) - 8 chunks
        first = next(pool.imap(square, range(1000)))  # O(w + b) per item
        print(total, first)  # 332833500 0
```

`map()` pickles the function once per chunk. With the default chunk size that is about 4p times; with `chunksize=1` it is n times, so a function that is expensive to pickle, such as a bound method of a large object or a `functools.partial` holding one, pays for that on every item.

## Queues

```python
from multiprocessing import Process, Queue

def produce(queue, items):
    for item in items:
        queue.put(item)  # O(w) - the feeder thread pickles it
    queue.put(None)

if __name__ == "__main__":
    queue = Queue()
    producer = Process(target=produce, args=(queue, range(5)))
    producer.start()
    received = []
    while (item := queue.get()) is not None:  # O(w + b) each
        received.append(item)
    producer.join()
    print(received)  # [0, 1, 2, 3, 4]
```

## Pipes

```python
from multiprocessing import Pipe, Process

def respond(conn):
    request = conn.recv()  # O(w + b)
    conn.send(request.upper())  # O(b + w)
    conn.close()

if __name__ == "__main__":
    parent_end, child_end = Pipe()  # O(1)
    worker = Process(target=respond, args=(child_end,))
    worker.start()
    parent_end.send("ping")  # O(b + w) - pickled here, in the caller
    print(parent_end.recv())  # PING
    worker.join()
```

A `send()` larger than the operating-system buffer blocks until the other end reads, so two processes that each send before they receive deadlock.

## Shared Memory

```python
from multiprocessing import Array, Process, Value

def fill(counter, cells):
    with counter.get_lock():  # O(w)
        counter.value += 1  # O(1)
    for i in range(len(cells)):  # O(e) - written in place, no copy
        cells[i] = i * 10

if __name__ == "__main__":
    counter = Value("i", 0)  # O(1)
    cells = Array("i", 5)  # O(e) - zeroed shared memory
    child = Process(target=fill, args=(counter, cells))
    child.start()
    child.join()
    print(counter.value, cells[:])  # 1 [0, 10, 20, 30, 40]
```

## Managers

```python
from multiprocessing import Manager

if __name__ == "__main__":
    with Manager() as manager:  # O(s + m)
        shared = manager.list(range(5))  # O(m + b)
        shared.append(5)  # O(m + b) - one round trip
        copied = shared[:]  # O(m + b) - one round trip for the whole list
        doubled = [x * 2 for x in shared]  # O(n·m) - a round trip per element
        print(copied, doubled)  # [0, 1, 2, 3, 4, 5] [0, 2, 4, 6, 8, 10]
```

## Version Notes

- **Python 3.12+**: `fork` emits a DeprecationWarning when the parent has more than one thread
- **Python 3.13+**: `Pool()` defaults to `os.process_cpu_count()` workers
- **Python 3.14+**: the default start method on POSIX other than macOS is `forkserver`, not `fork`; `Process.interrupt()`, `Lock.locked()`, `RLock.locked()`, `Semaphore.locked()` and `Manager.set()` added; `get_all_start_methods()` lists the default first

## Related Documentation

- [concurrent.futures Module](concurrent_futures.md) - High-level executor interface
- [threading Module](threading.md) - Thread-based parallelism
- [asyncio Module](asyncio.md) - Async/await programming
- [queue Module](queue.md) - Thread-safe queues
- [pickle Module](pickle.md) - What every transfer costs
