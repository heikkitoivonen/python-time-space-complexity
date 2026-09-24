# multiprocessing Module Complexity

The `multiprocessing` module runs Python code in separate operating-system processes, each with
its own interpreter and memory. Nothing is shared by default: apart from what a `fork` child
inherits and the shared-memory objects, everything a process, pool, queue, pipe or manager carries
crosses a pipe or socket as bytes, pickled unless it is sent with `send_bytes()`.

So the size that governs most rows is the pickled size of what is sent, not the number of calls,
and every call that can block also costs the time it spends blocked.

`s` is the time to start one process: a fork of the caller under the `fork` start method, a fork
of an already running server under `forkserver`, a fresh interpreter under `spawn`. The last two
also unpickle what they are sent, and the first `forkserver` start launches the server itself.
`w` is time spent blocked, `b` is the pickled size of what an operation sends and receives, `k` is
child processes started and not yet joined, `n` is items handed to a pool call, `p` is worker
processes in a pool, `m` is one round trip to a manager's server process, `f` is the caller's own
function, callback or constructor, `z` is bytes of shared memory, `e` is items in a
`ShareableList`, `v` is processes or threads waiting on a primitive, `d` is how many times the
caller holds a recursive lock, and `r` is types registered on a manager class. Pickling is priced
per byte of output; a `__reduce__` or `__getstate__` the caller wrote is part of f. Under `spawn`
and `forkserver` the first lock, semaphore or queue a process creates - `Value()`, `Array()` and
`Pool()` each create one - starts the resource tracker process, once, at O(s); under every start
method the first tracked `SharedMemory` or the first `SharedMemoryManager` does.

The rows describe POSIX systems. On Windows only `spawn` exists, `terminate()` and `kill()` both
call `TerminateProcess()` and `interrupt()` is unavailable, there is no resource tracker, and a
`SharedMemory` block lasts until its last handle closes, `unlink()` doing nothing.

## Complexity Reference

### Process

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Process(group=None, target=None, name=None, args=(), kwargs={}, *, daemon=None)` | O(a) | O(a) | a = arguments, which it copies; nothing runs, and `active_children()` does not list it, until `start()` |
| `Process.start()` | O(k + s + b) | O(k + b) | Reaps finished children first; `spawn` and `forkserver` pickle the process object, target and arguments included, while `fork` pickles nothing |
| `Process.run()` | O(f) | O(f) | Calls the target once, in whichever process calls `run()`; `start()` calls it in the child |
| `Process.join(timeout=None)` | O(w) | O(1) | Immediate on a finished process; a timeout returns with the process still alive |
| `Process.is_alive()` | O(1) | O(1) | One non-blocking poll |
| `Process.terminate()`, `Process.kill()`, `Process.interrupt()` | O(1) | O(1) | Send SIGTERM, SIGKILL or SIGINT and return without waiting; `join()` waits for the exit. `interrupt()` is Python 3.14+ |
| `Process.close()` | O(1) | O(1) | Raises `ValueError` while the process is alive; afterwards `is_alive()`, `join()`, `exitcode` and `pid` raise it |
| `Process.name`, `Process.daemon`, `Process.authkey`, `Process.pid`, `Process.ident`, `Process.exitcode`, `Process.sentinel` | O(1) | O(1) | `pid`, `ident` and `exitcode` are `None` until `start()`, and `sentinel` raises `ValueError`; `exitcode` polls the child |

### Contexts and module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.current_process()`, `multiprocessing.parent_process()` | O(1) | O(1) | `parent_process()` is `None` in the main process |
| `multiprocessing.active_children()` | O(k) | O(k) | Reaps finished children and returns a new list of the live ones |
| `multiprocessing.cpu_count()` | O(1) | O(1) | `os.cpu_count()`, raising `NotImplementedError` where that is `None` |
| `multiprocessing.get_context(method=None)` | O(1) | O(1) | The module's API bound to one start method; raises `ValueError` for an unknown one |
| `multiprocessing.get_start_method(allow_none=False)`, `multiprocessing.set_start_method(method, force=False)` | O(1) | O(1) | A second `set_start_method()` raises `RuntimeError` unless `force=True` |
| `multiprocessing.get_all_start_methods()` | O(1) | O(1) | A new list each call |
| `multiprocessing.get_logger()`, `multiprocessing.log_to_stderr(level=None)` | O(1) | O(1) | One logger, created on first use; every `log_to_stderr()` call adds another handler |
| `multiprocessing.freeze_support()`, `multiprocessing.set_executable(executable)`, `multiprocessing.allow_connection_pickling()` | O(1) | O(1) | Store a setting, or do nothing outside a frozen executable |
| `multiprocessing.set_forkserver_preload(module_names)` | O(len(module_names)) | O(1) | Checks that each name is a str and keeps the list; the server imports them when it starts |

### Pool

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Pool(processes=None, initializer=None, initargs=(), maxtasksperchild=None)` | O(p·(s + k)) | O(p) | Starts p workers, by default `os.process_cpu_count()` (`os.cpu_count()` before Python 3.13), and three handler threads |
| `Pool.map(func, iterable, chunksize=None)`, `Pool.starmap(func, iterable, chunksize=None)` | O(n + b + w) | O(n + b) | Blocks for every result and returns them in input order; an iterable without `len()` is listed first. Items go out in chunks of ⌈n / 4p⌉ by default and `func` is pickled once per chunk, so `chunksize=1` pickles it n times |
| `Pool.map_async(...)`, `Pool.starmap_async(...)` | O(n) | O(n) | Lists an input without `len()` and allocates a slot per result in the caller, then returns; a handler thread chunks, pickles and sends the items |
| `Pool.apply(func, args=(), kwds={})` | O(b + w) | O(b) | One task, blocked on until its result is back |
| `Pool.apply_async(func, args=(), kwds={}, callback=None, error_callback=None)` | O(1) | O(1) | Queues one task for the handler thread |
| `Pool.imap(func, iterable, chunksize=1)`, `Pool.imap_unordered(func, iterable, chunksize=1)` | O(1) | O(1) | Returns at once; a handler thread then reads the whole input as fast as the workers take it, whether or not anyone consumes the results. With the default `chunksize` of 1, `func` is pickled n times |
| Iterating an `imap()` or `imap_unordered()` result | O(w) per item | O(n + b) | Results are unpickled and buffered as they arrive, consumed or not, so a slow consumer ends up holding all n; `imap()` also holds any that arrive ahead of their turn |
| `Pool.close()` | O(1) | O(1) | Refuses new tasks; queued ones still run |
| `Pool.join()` | O(w + p) | O(1) | Raises `ValueError` unless `close()` or `terminate()` came first |
| `Pool.terminate()` | O(w + p + q + b) | O(b) | q = tasks still queued, which it discards; kills every worker and waits for it. `with Pool() as pool:` calls this on exit, so work still running is lost, not waited for |
| `multiprocessing.pool.ThreadPool(processes=None, initializer=None, initargs=())` | O(p) | O(p) | The same API on p threads of this process: tasks and results are passed by reference, so no row above pays b. A thread cannot be killed, so `terminate()` returns while a running task carries on |

### AsyncResult

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `AsyncResult.get(timeout=None)`, `AsyncResult.wait(timeout=None)` | O(w) | O(1) | The pool's result thread has already unpickled the result; `get(timeout)` raises `multiprocessing.TimeoutError`, which is not the builtin |
| `AsyncResult.ready()`, `AsyncResult.successful()` | O(1) | O(1) | `successful()` raises `ValueError` until ready |
| `callback`, `error_callback` of the `_async` methods | O(f) | O(f) | Run in a pool handler thread, normally the one delivering results, before `ready()` turns true, so a slow one holds up every result behind it |

### Queue, JoinableQueue and SimpleQueue

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Queue(maxsize=0)`, `multiprocessing.JoinableQueue(maxsize=0)`, `multiprocessing.SimpleQueue()` | O(1) | O(1) | A pipe and its locks |
| `Queue.put(obj, block=True, timeout=None)`, `Queue.put_nowait(obj)` | O(w) | O(1) | Waits only for a slot in a full queue. A feeder thread pickles and writes the object later, so it is sent as it is then, and an unpicklable one fails in that thread, not in `put()` |
| `Queue.get(block=True, timeout=None)`, `Queue.get_nowait()` | O(w + b) | O(b) | Reads one message, then unpickles it after releasing the reader lock |
| `Queue.qsize()`, `Queue.empty()`, `Queue.full()` | O(1) | O(1) | `qsize()` counts items put and not yet got, and raises `NotImplementedError` on macOS; `empty()` polls the pipe, so it stays true until the feeder has written |
| `Queue.close()`, `Queue.cancel_join_thread()` | O(1) | O(1) | After `close()` the feeder still writes what is buffered, and a later `put()` or `get()` raises `ValueError` |
| `Queue.join_thread()` | O(w) | O(1) | Waits for the feeder to flush the buffer; requires `close()` first |
| `JoinableQueue.task_done()` | O(v + w) | O(1) | Wakes every `join()` when the count reaches zero; one call too many raises `ValueError` |
| `JoinableQueue.join()` | O(w) | O(1) | Returns once every item put has had its `task_done()` |
| `SimpleQueue.put(obj)` | O(b + w) | O(b) | Pickles in the caller, then writes under the writer lock |
| `SimpleQueue.get()` | O(w + b) | O(b) | |
| `SimpleQueue.empty()`, `SimpleQueue.close()` | O(1) | O(1) | |

### Pipe and Connection

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Pipe(duplex=True)` | O(1) | O(1) | A socket pair, or a one-way pipe with `duplex=False` |
| `Connection.send(obj)`, `Connection.send_bytes(buf, offset=0, size=None)` | O(b + w) | O(b) | `send()` pickles in the caller; once the operating-system buffer is full, the call blocks until the other end reads |
| `Connection.recv()`, `Connection.recv_bytes(maxlength=None)` | O(w + b) | O(b) | One whole message; one longer than `maxlength` raises `OSError` |
| `Connection.recv_bytes_into(buf, offset=0)` | O(w + b) | O(b) | Too small a buffer raises `BufferTooShort` carrying the message |
| `Connection.poll(timeout=0.0)` | O(w) | O(1) | Immediate by default |
| `Connection.fileno()`, `Connection.close()`, `Connection.closed`, `Connection.readable`, `Connection.writable` | O(1) | O(1) | |

### Listener and Client

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.connection.Listener(address=None, family=None, backlog=1, authkey=None)` | O(1) | O(1) | Binds and listens on a socket, or a named pipe on Windows |
| `Listener.accept()` | O(w) | O(1) | Waits for a client; with an `authkey`, the two sides then run `deliver_challenge()` and `answer_challenge()` |
| `Listener.close()`, `Listener.address`, `Listener.last_accepted` | O(1) | O(1) | `last_accepted` is `None` until a client connects |
| `multiprocessing.connection.Client(address, family=None, authkey=None)` | O(w) | O(1) | Connects and authenticates as `accept()` does; with no `authkey` on either side, nothing is checked |
| `multiprocessing.connection.wait(object_list, timeout=None)` | O(len(object_list) + w) | O(len(object_list)) | Registers every object on each call and returns a new list of the ready ones, empty after a timeout |
| `multiprocessing.connection.deliver_challenge(connection, authkey)`, `multiprocessing.connection.answer_challenge(connection, authkey)` | O(w) | O(1) | An HMAC exchange of fixed-size messages; a mismatched key raises `AuthenticationError` on both sides |

### Lock, RLock, Semaphore and BoundedSemaphore

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Lock()`, `multiprocessing.RLock()`, `multiprocessing.Semaphore(value=1)`, `multiprocessing.BoundedSemaphore(value=1)` | O(1) | O(1) | One named operating-system semaphore each |
| `Lock.acquire(block=True, timeout=None)`, `RLock.acquire(block=True, timeout=None)` | O(w) | O(1) | Immediate when free, and for an `RLock` its owner |
| `Lock.release()`, `RLock.release()` | O(1) | O(1) | An unheld `Lock` raises `ValueError`, an unheld `RLock` `AssertionError` |
| `Lock.locked()`, `RLock.locked()`, `Semaphore.locked()` | O(1) | O(1) | Python 3.14+ |
| `Semaphore.acquire(block=True, timeout=None)` | O(w) | O(1) | Immediate while the count is above zero |
| `Semaphore.release()` | O(1) | O(1) | `BoundedSemaphore` raises `ValueError` past its initial value; on macOS it checks only an initial value of 1 |
| `Semaphore.get_value()` | O(1) | O(1) | Raises `NotImplementedError` on macOS |

### Condition

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Condition(lock=None)` | O(1) | O(1) | A new `RLock` unless given a lock |
| `Condition.acquire()`, `Condition.release()` | O(w) | O(1) | The underlying lock's |
| `Condition.wait(timeout=None)` | O(w + d) | O(1) | Releases a lock held d times all the way, waits, and takes it back d times |
| `Condition.wait_for(predicate, timeout=None)` | O(w + c·(f + d)) | O(f) | c = predicate calls, one before waiting and one per wakeup |
| `Condition.notify(n=1)` | O(u + t + w) | O(1) | u = sleepers it wakes, t = waits that timed out since the last notify, whose bookkeeping it clears first. It waits for every woken sleeper to acknowledge, so a sleeper killed mid-wait blocks it for good |
| `Condition.notify_all()` | O(v + t + w) | O(1) | `notify()` for every sleeper |

### Event

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Event()` | O(1) | O(1) | |
| `Event.set()` | O(v + t + w) | O(1) | Wakes every waiter through `notify_all()`, killed-sleeper hang included |
| `Event.clear()`, `Event.is_set()` | O(w) | O(1) | Both take the event's lock |
| `Event.wait(timeout=None)` | O(w) | O(1) | Immediate once set |

### Barrier

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Barrier(parties, action=None, timeout=None)` | O(1) | O(1) | |
| `Barrier.wait(timeout=None)` | O(w + v + f) | O(f) | The last of the parties runs `action`, f, and wakes the others; a timeout that expires breaks the barrier |
| `Barrier.reset()`, `Barrier.abort()` | O(v + w) | O(1) | Every waiter raises `BrokenBarrierError`; `abort()` leaves the barrier broken, `reset()` does not |
| `Barrier.parties`, `Barrier.n_waiting`, `Barrier.broken` | O(1) | O(1) | |

### Value and Array

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.RawValue(typecode_or_type, *args)`, `multiprocessing.Value(typecode_or_type, *args, lock=True)` | O(z) | O(z) | z = the type's size, zeroed and then initialised; `Value()` wraps it with an `RLock`, or returns the raw ctypes object with `lock=False` |
| `multiprocessing.RawArray(typecode_or_type, size_or_initializer)`, `multiprocessing.Array(typecode_or_type, size_or_initializer, *, lock=True)` | O(z) | O(z) | z = the whole array, zeroed or copied from the sequence. A child given it through `Process()` shares the memory rather than copying it; as a pool task argument, this and every object in this table raises `RuntimeError` |
| `multiprocessing.sharedctypes.synchronized(obj, lock=None, ctx=None)` | O(1) | O(1) | The wrapper `Value()` and `Array()` return, put around an existing ctypes object without copying it; the wrapper class for a `Structure` type is built once, costing its field count |
| `Value.value` | O(w) | O(1) | Under the wrapper's lock; a `c_char` array's `value` is a new bytes object, O(z) |
| `Array[i]`, `Array[i] = x` | O(w) | O(1) | Under the lock |
| `Array[i:j]` | O(w + j − i) | O(j − i) | A new list, or bytes for a `'c'` array and str for a `'u'` array, under the lock |
| `len(Array)` | O(1) | O(1) | Takes no lock |
| `Value.get_lock()`, `Value.get_obj()`, `Value.acquire()`, `Value.release()` | O(w) | O(1) | The wrapper's lock and raw object; only `acquire()` waits, and `with value:` holds the lock |

### SharedMemory

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.shared_memory.SharedMemory(name=None, create=False, size=0, *, track=True)` | O(1) | O(z) | z = `size`; creating it and attaching to it by `name` both register the block with the resource tracker, which unlinks any block still registered when the program exits; `track=False` (Python 3.13+) opts out |
| `SharedMemory.buf` | O(1) | O(1) | The same `memoryview` on every access; slicing it copies nothing |
| `SharedMemory.name`, `SharedMemory.size` | O(1) | O(1) | |
| `SharedMemory.close()` | O(1) | O(1) | Unmaps this process's view, leaving the block; raises `BufferError` while a slice of `buf` is still alive |
| `SharedMemory.unlink()` | O(1) | O(1) | Destroys the block; call it once, from one process |

### ShareableList

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.shared_memory.ShareableList(sequence=None, *, name=None)` | O(z) | O(z) | Packs every item into a new block of z bytes, which grows with the item count and the str and bytes lengths; attaching by `name` is O(e) |
| `ShareableList[i]`, `ShareableList[i] = x` | O(1) | O(1) | A str or bytes slot costs its size, fixed when the list is built at the next multiple of 8 above the item's encoded length; a longer value raises `ValueError`. The list's length is fixed |
| `len(ShareableList)` | O(1) | O(1) | |
| `ShareableList.count(value)`, `ShareableList.index(value)` | O(z) | O(1) | Read the items one at a time, `index()` up to the first match |
| `ShareableList.format` | O(e) | O(e) | A new string of every item's struct format |
| `ShareableList.shm` | O(1) | O(1) | The `SharedMemory` holding the list |

### SyncManager

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.Manager()` | O(k + s + m) | O(k) | Starts a `SyncManager`'s server process and waits for its address |
| `SyncManager.list()`, `SyncManager.dict()`, `SyncManager.set()`, `SyncManager.Namespace()`, `SyncManager.Value()`, `SyncManager.Array()`, `SyncManager.Queue()`, `SyncManager.JoinableQueue()`, `SyncManager.Lock()`, `SyncManager.RLock()`, `SyncManager.Semaphore()`, `SyncManager.BoundedSemaphore()`, `SyncManager.Condition()`, `SyncManager.Event()`, `SyncManager.Barrier()`, `SyncManager.Pool()` | O(m + b + f) | O(b) | Builds the object in the server, at its constructor's cost f, and returns a proxy; initial contents cross as b bytes. `set()` is Python 3.14+ |
| Calling a proxy method | O(m + b + f) | O(b) | Every call is a round trip, and a thread's first call also opens its connection. Iterating a list or dict proxy costs a round trip per element; `proxy[:]` on a list and `copy()`, `keys()`, `values()` or `items()` on a dict copy it in one |

### BaseManager

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.managers.BaseManager(address=None, authkey=None, serializer='pickle', ...)` | O(1) | O(1) | Nothing starts until `start()` or `connect()` |
| `BaseManager.start(initializer=None, initargs=())` | O(k + s + m + b) | O(k + b) | Starts the server process; b = the registry, initializer and arguments, pickled under `spawn` and `forkserver`. A second call raises `ProcessError`; `with manager:` shuts it down on exit |
| `BaseManager.connect()` | O(m) | O(1) | Reaches a server another process started; nothing is spawned |
| `BaseManager.get_server()` | O(1) | O(1) | A server to run in this process with `serve_forever()`; raises `ProcessError` once started |
| `BaseManager.shutdown()`, `BaseManager.join(timeout=None)` | O(w) | O(1) | `shutdown()` exists only once started |
| `BaseManager.register(typeid, callable=None, proxytype=None, ...)` | O(r) | O(r) | A classmethod: the first call on a subclass copies the r registrations it inherits, and later ones are O(1) |
| `BaseManager.address` | O(1) | O(1) | |

### BaseProxy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BaseProxy._callmethod(methodname, args=(), kwds={})` | O(m + b + f) | O(b) | The round trip behind every proxy method |
| `BaseProxy._getvalue()` | O(m + b) | O(b) | One round trip returning a copy of the referent |

### SharedMemoryManager

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.managers.SharedMemoryManager(address=None, authkey=None)` | O(1) | O(1) | A `BaseManager`; `start()` costs what it does there |
| `SharedMemoryManager.SharedMemory(size)` | O(m) | O(z) | Creates the block in the caller and registers it with the server in one round trip |
| `SharedMemoryManager.ShareableList(sequence)` | O(m + z) | O(z) | The same, for a `ShareableList` |
| `SharedMemoryManager.shutdown()` | O(g² + w) | O(g) | g = blocks it registered; it unlinks each one and removes its name from the front of a list |

### multiprocessing.dummy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.dummy` | O(1) | O(1) | The same API on threads: `Process` is a `threading.Thread`, `Queue` is `queue.Queue`, `Pool()` is a `ThreadPool`, `Pipe()` passes objects by reference and `Manager()` returns the module itself. Nothing is pickled, so b drops out of every bound |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `multiprocessing.ProcessError`, `multiprocessing.BufferTooShort`, `multiprocessing.TimeoutError`, `multiprocessing.AuthenticationError` | O(1) | O(1) | The last three subclass `ProcessError` |
| `multiprocessing.SUBDEBUG`, `multiprocessing.SUBWARNING` | O(1) | O(1) | Logging levels 5 and 25 |
| `multiprocessing.reducer` | O(1) | O(1) | The `reduction` module, whose `ForkingPickler` pickles every transfer |

## Starting Processes

Starting a process costs a fork or a new interpreter, s, and under `spawn` and `forkserver` it
also pickles the target and its arguments. `join()` costs only the wait.

```python
from multiprocessing import Pipe, Process, current_process

def report(conn, n):
    conn.send((current_process().name, n * n))
    conn.close()

if __name__ == "__main__":
    parent_end, child_end = Pipe()
    p = Process(target=report, args=(child_end, 7), name="worker")  # O(a) - nothing runs yet
    assert p.pid is None
    p.start()  # O(k + s + b) - under spawn or forkserver the args are pickled
    assert parent_end.recv() == ("worker", 49)
    p.join()  # O(w)
    assert p.exitcode == 0
```

### Start Methods

The `if __name__ == "__main__":` guard is required under `spawn` and `forkserver`, which import
the main module in a fresh interpreter: every child under `spawn`, the server under `forkserver`. One of the two is the default everywhere from Python 3.14, and on
macOS and Windows before it. A context pins a start method without changing the global one.

```python
import multiprocessing

def square(n):
    return n * n

if __name__ == "__main__":
    methods = multiprocessing.get_all_start_methods()  # O(1)
    assert "spawn" in methods
    context = multiprocessing.get_context("spawn")  # O(1)
    with context.Pool(1) as pool:  # O(p·(s + k)) - spawn starts a fresh interpreter
        assert pool.apply(square, (6,)) == 36  # O(b + w)
    assert context.get_start_method() == "spawn"
```

## Pools

### Chunking

`map()` pickles the function once per chunk. With the default chunk size that is about 4p times;
with `chunksize=1` it is n times, so a function that is expensive to pickle, such as a bound
method of a large object or a `functools.partial` holding one, pays for that on every item.
`imap()` and `imap_unordered()` default to `chunksize=1`.

```python
from multiprocessing import Pool

def square(n):
    return n * n

if __name__ == "__main__":
    with Pool(processes=2) as pool:  # O(p·(s + k))
        results = pool.map(square, range(1000))  # O(n + b + w) - 8 chunks of 125
        assert sum(results) == 332833500
        chunked = pool.imap(square, range(1000), chunksize=100)  # O(1) - 10 chunks
        assert next(chunked) == 0  # O(w) per item
        assert sum(chunked) == 332833500
```

### imap and Backpressure

`imap()` returns without waiting for a result, but a handler thread then feeds the whole input to
the workers, and the results pile up in the iterator whether or not anything consumes them. It saves
the wait for the first result, not the memory for the rest.

```python
import time
from multiprocessing import Pool

def identity(n):
    return n

if __name__ == "__main__":
    consumed = []

    def numbers():
        for n in range(100):
            consumed.append(n)
            yield n

    with Pool(2) as pool:
        results = pool.imap(identity, numbers())  # O(1) - returns at once
        deadline = time.monotonic() + 10
        while len(consumed) < 100 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(consumed) == 100  # read to the end with no next() called
        assert list(results) == list(range(100))
```

### Threads Instead of Processes

A `ThreadPool` has the same API and pickles nothing, so it suits work that releases the GIL, such
as I/O. Its results are the objects the function returned.

```python
from multiprocessing.pool import ThreadPool

def first(items):
    return items[0]

if __name__ == "__main__":
    shared = [object()]
    with ThreadPool(2) as pool:  # O(p) - threads, not processes
        (result,) = pool.map(first, [shared])  # no b term - nothing is pickled
    assert result is shared[0]
```

## Queues and Pipes

`Queue.put()` hands the object to a feeder thread and returns; the pickling happens later, in that
thread. `Connection.send()` and `SimpleQueue.put()` pickle in the caller.

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
    assert received == [0, 1, 2, 3, 4]
```

A `send()` larger than the operating-system buffer blocks until the other end reads, so two
processes that each send a large message before they receive deadlock.

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
    assert parent_end.recv() == "PING"
    worker.join()
```

## Sharing State

### Value and Array

A `Value` or `Array` lives in shared memory, so a child writes into the parent's copy. Each read
and each write takes the wrapper's lock separately, so `counter.value += 1` takes the lock twice and
releases it in between; hold `get_lock()` across a read-modify-write.

```python
from multiprocessing import Array, Process, Value

def fill(counter, cells):
    with counter.get_lock():  # O(w)
        counter.value += 1  # O(1) - read and write under the held lock
    for i in range(len(cells)):  # O(z) - written in place, no copy
        cells[i] = i * 10

if __name__ == "__main__":
    counter = Value("i", 0)  # O(z)
    cells = Array("i", 5)  # O(z) - zeroed shared memory
    child = Process(target=fill, args=(counter, cells))
    child.start()
    child.join()
    assert counter.value == 1
    assert cells[:] == [0, 10, 20, 30, 40]  # O(w + j − i)
```

### SharedMemory and ShareableList

A `SharedMemory` block is raw bytes that any process can attach to by name, at O(1) whatever its
size. A `ShareableList` packs numbers, str, bytes and `None` into one; its length is fixed and a
str or bytes item cannot outgrow the slot it was built with.

```python
from multiprocessing import shared_memory

block = shared_memory.SharedMemory(create=True, size=1024)  # O(1) time, O(z) memory
try:
    block.buf[:5] = b"hello"  # O(5) - a write into the shared bytes
    attached = shared_memory.SharedMemory(name=block.name)  # O(1) - no copy
    assert bytes(attached.buf[:5]) == b"hello"
    attached.close()
finally:
    block.close()
    block.unlink()  # once, from one process

items = shared_memory.ShareableList([1, 2.5, "text", None])  # O(z)
try:
    items[0] = 42  # O(1)
    assert items[0] == 42 and len(items) == 4
    assert items.index(None) == 3  # O(z) - reads item by item
    try:
        items[2] = "x" * 100
    except ValueError as error:
        assert "exceeds available storage" in str(error)
    else:
        raise AssertionError("a str grew past its allocation")
finally:
    items.shm.close()
    items.shm.unlink()
```

### Managers

A manager keeps the object in its own server process, and every proxy operation is a round trip
to it. Copy a whole list or dict in one call rather than iterating the proxy.

```python
from multiprocessing import Manager

if __name__ == "__main__":
    with Manager() as manager:  # O(k + s + m)
        shared = manager.list(range(5))  # O(m + b)
        shared.append(5)  # O(m + b) - one round trip
        copied = shared[:]  # O(m + b) - one round trip for the whole list
        doubled = [x * 2 for x in shared]  # O(m) per element - a round trip each
        assert copied == [0, 1, 2, 3, 4, 5]
        assert doubled == [0, 2, 4, 6, 8, 10]
```

## Connecting Unrelated Processes

`Listener` and `Client` give two processes that did not start one another a `Connection`. With an
`authkey` on both ends, each connection runs a fixed-size challenge before any data moves.

```python
from multiprocessing import Process
from multiprocessing.connection import Client, Listener

def call(address):
    with Client(address, authkey=b"secret") as conn:  # O(w) - connect and authenticate
        conn.send([1, 2, 3])  # O(b + w)
        assert conn.recv() == 6

if __name__ == "__main__":
    with Listener(authkey=b"secret") as listener:  # O(1)
        caller = Process(target=call, args=(listener.address,))
        caller.start()
        with listener.accept() as conn:  # O(w)
            conn.send(sum(conn.recv()))  # O(w + b)
        caller.join()
    assert caller.exitcode == 0
```

## Common Patterns

### Fan Out, Collect as Completed

`imap_unordered()` with an explicit chunk size pickles the function once per chunk and hands back
each chunk's results as soon as that chunk finishes, whatever the order, so the parent works on
early results while slow chunks are still running.

```python
from multiprocessing import Pool

def score(word):
    return word, sum(map(ord, word))

if __name__ == "__main__":
    words = ["alpha", "beta", "gamma", "delta"] * 250
    totals = {}
    with Pool(2) as pool:
        for word, value in pool.imap_unordered(score, words, chunksize=50):  # O(w) each
            totals[word] = value  # O(1) amortized
    assert totals == {word: sum(map(ord, word)) for word in set(words)}
```

## Performance Best Practices

✅ **Do**:

- Pass `chunksize` to `imap()` and `imap_unordered()`, whose default of 1 pickles the function once per item
- Send small arguments and results; b is paid in both directions on every task
- Copy a manager list or dict in one call (`proxy[:]`, `copy()`, `items()`) instead of iterating the proxy
- Hold a `Value`'s lock across a read-modify-write
- Put large data every pool task reads in `SharedMemory` and pass the block, which pickles as its name
- Close a `Pool` and `join()` it when the queued work must finish; the `with` block terminates it

❌ **Avoid**:

- `imap()` over a huge or endless input as a way to bound memory; the pool reads it all and buffers every result
- Iterating a manager proxy in a loop; each element is a round trip
- Slow callbacks on the `_async` methods; they hold up every later result
- Two processes that both send large messages before either receives
- A process `Pool` for I/O-bound work; a `ThreadPool` pickles nothing

## Version Notes

- **Python 3.12+**: The `fork` start method emits a `DeprecationWarning` when the parent has more than one thread
- **Python 3.13+**: `Pool()` defaults to `os.process_cpu_count()` workers; `SharedMemory` takes `track=False`
- **Python 3.14+**: The default start method on POSIX other than macOS is `forkserver`, not `fork`; `Process.interrupt()`, `Lock.locked()`, `RLock.locked()`, `Semaphore.locked()` and `SyncManager.set()` added

## Related Modules

- **[concurrent.futures](concurrent_futures.md)** - `ProcessPoolExecutor`, a process pool behind a futures interface
- **[threading](threading.md)** - the thread primitives `multiprocessing.dummy` and `ThreadPool` are built on
- **[queue](queue.md)** - the in-process queues `multiprocessing.dummy` uses
- **[pickle](pickle.md)** - what every transfer costs
- **[asyncio](asyncio.md)** - concurrency without processes or threads
