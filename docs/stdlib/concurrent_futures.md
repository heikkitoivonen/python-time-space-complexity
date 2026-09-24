# concurrent.futures Module Complexity

The `concurrent.futures` module runs callables on a pool of threads, processes or (from Python
3.14) interpreters, and hands back a `Future` for each call. The pool's own bookkeeping is cheap
and mostly O(1) per task; what costs is starting workers, moving arguments and results across a
process or interpreter boundary, and waiting on many futures at once.

`n` is tasks submitted, or futures passed to `wait()` and `as_completed()`; `w` is the pool's
`max_workers`; `q` is tasks queued but not yet started; `b` is `map()`'s `buffersize`; `c` is
callbacks registered on one future; `a` is the pickled size of one task's arguments and result.
The bounds price the module's work, not the callable's: time a task spends running, and time a
caller spends blocked waiting for it, belong to the task. The few `wait()` and `as_completed()`
calls watching one future at a time are treated as O(1).

## Complexity Reference

### ThreadPoolExecutor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ThreadPoolExecutor(max_workers=None, thread_name_prefix='', initializer=None, initargs=())` | O(1) | O(1) | Starts no threads; `max_workers` defaults to `min(32, CPUs + 4)` |
| `ThreadPoolExecutor.submit(fn, /, *args, **kwargs)` | O(1) | O(1) | Queues one work item and starts at most one thread: only when no worker is idle and fewer than w are running. Arguments are passed by reference |
| `ThreadPoolExecutor.map(fn, *iterables, timeout=None, chunksize=1, buffersize=None)` | O(n) | O(n) | Consumes every input and submits every task before it returns; with `buffersize` (3.14+), O(b) space and b tasks submitted up front, one more as each result is taken. `chunksize` is ignored |
| `ThreadPoolExecutor.shutdown(wait=True, *, cancel_futures=False)` | O(w + q) | O(1) | Joins the threads after the queue drains; `cancel_futures=True` cancels the q queued tasks instead of running them |

### ProcessPoolExecutor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ProcessPoolExecutor(max_workers=None, mp_context=None, initializer=None, initargs=(), max_tasks_per_child=None)` | O(1) | O(1) | Starts no processes; `max_workers` defaults to the CPU count |
| `ProcessPoolExecutor.submit(fn, /, *args, **kwargs)` | O(1), O(w) process starts on the first call with `fork` | O(1) | With the `fork` start method the first submit starts all w workers; with `spawn` or `forkserver` each submit starts at most one, when none is idle. Arguments are pickled later, on a feeder thread, in O(a) |
| `ProcessPoolExecutor.map(fn, *iterables, timeout=None, chunksize=1, buffersize=None)` | O(n) | O(n) | Sends ⌈n / chunksize⌉ tasks, each pickling its chunk, so a larger `chunksize` means fewer round trips; with `buffersize` (3.14+), b chunks are in flight |
| `ProcessPoolExecutor.shutdown(wait=True, *, cancel_futures=False)` | O(w + q) | O(w) | Joins the manager thread, which joins the workers |
| `ProcessPoolExecutor.terminate_workers()`, `ProcessPoolExecutor.kill_workers()` | O(w) | O(w) | Python 3.14+: one signal per live worker, after a `shutdown(wait=False, cancel_futures=True)`; the pool cannot be used afterwards |

### InterpreterPoolExecutor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `InterpreterPoolExecutor(max_workers=None, thread_name_prefix='', initializer=None, initargs=())` | O(1) | O(1) | Python 3.14+. A `ThreadPoolExecutor` whose threads each run their own interpreter; creates none yet |
| `InterpreterPoolExecutor.submit(fn, /, *args, **kwargs)` | O(1) | O(1) | As `ThreadPoolExecutor.submit`. The worker then pays O(a) to copy or pickle the callable, arguments and result across, and a new worker first creates a whole interpreter |

### Executor

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Executor` | O(1) | O(1) | Abstract base; a subclass supplies `submit()` and inherits `map()`, `shutdown()` and the context manager |
| `Executor.submit(fn, /, *args, **kwargs)`, `Executor.map(...)`, `Executor.shutdown(...)` | as the subclass | as the subclass | `with executor:` calls `shutdown(wait=True)` on exit |

### Future

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Future()` | O(1) | O(1) | Pending; executors create these, and tests may too |
| `Future.result(timeout=None)` | O(1) | O(1) | Returns the stored object itself, not a copy; blocks until done, and raises the task's exception, `CancelledError` or `TimeoutError` |
| `Future.exception(timeout=None)` | O(1) | O(1) | The stored exception, or `None` |
| `Future.done()`, `Future.running()`, `Future.cancelled()` | O(1) | O(1) | |
| `Future.cancel()` | O(c) | O(1) | Runs the callbacks when it succeeds; returns `False` once the task is running or finished, and `True` again on a cancelled future without rerunning them |
| `Future.add_done_callback(fn)` | O(1) | O(1) | Appends; on a future already done it calls `fn` at once, in the calling thread |
| `Future.set_result(result)`, `Future.set_exception(exception)` | O(c) | O(1) | For executor implementations: stores, wakes waiters, runs the c callbacks; `InvalidStateError` if already done |
| `Future.set_running_or_notify_cancel()` | O(1) | O(1) | For executor implementations: `False` when the future was cancelled |

### Waiting on Futures

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `concurrent.futures.wait(fs, timeout=None, return_when=ALL_COMPLETED)` | O(n log n) | O(n) | Sorts the futures by `id()` to lock them in a fixed order, then returns `(done, not_done)` sets |
| `concurrent.futures.as_completed(fs, timeout=None)` | O(n log n) | O(n) | The same sort once, then yields each distinct future once: those already finished first, then the rest in completion order |
| `concurrent.futures.FIRST_COMPLETED`, `FIRST_EXCEPTION`, `ALL_COMPLETED` | O(1) | O(1) | String constants for `return_when` |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `concurrent.futures.CancelledError`, `concurrent.futures.InvalidStateError` | O(1) | O(1) | Raised by `result()` on a cancelled future, and by `set_result()` on a finished one |
| `concurrent.futures.TimeoutError` | O(1) | O(1) | The builtin `TimeoutError` from Python 3.11 |
| `concurrent.futures.BrokenExecutor` | O(1) | O(1) | Base of `thread.BrokenThreadPool`, `process.BrokenProcessPool` and `interpreter.BrokenInterpreterPool` (3.14+), raised once a worker fails to start or dies |

## Submitting Work

### Workers Start on Demand

Building a pool starts nothing. `ThreadPoolExecutor.submit()` starts a thread only when no
worker has marked itself idle, so a pool whose worker is idle when each task arrives reuses one
thread however large `max_workers` is.

```python
import threading
from concurrent.futures import ThreadPoolExecutor

before = threading.active_count()
executor = ThreadPoolExecutor(max_workers=8)  # O(1) - no threads yet
assert threading.active_count() == before

release = threading.Event()
futures = [executor.submit(release.wait) for _ in range(3)]  # O(1) each
assert threading.active_count() == before + 3  # one new thread per busy task

futures += [executor.submit(release.wait) for _ in range(20)]
assert threading.active_count() == before + 8  # capped at max_workers

release.set()
executor.shutdown()  # O(w + q)
assert all(future.result() is True for future in futures)
```

### map() Submits Everything at Once

`Executor.map()` is not lazy on its input: it takes every item and submits every task before
it returns, so it holds n futures however the results are consumed. From Python 3.14,
`buffersize` keeps about that many tasks in flight, submitting one more as each result is taken.

```python
import sys
from concurrent.futures import ThreadPoolExecutor

taken = []

def items():
    for index in range(100):
        taken.append(index)
        yield index

with ThreadPoolExecutor(max_workers=2) as executor:
    results = executor.map(abs, items())  # O(n) - the whole input is consumed here
    assert len(taken) == 100
    assert list(results) == list(range(100))  # in input order

if sys.version_info >= (3, 14):
    taken.clear()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = executor.map(abs, items(), buffersize=4)  # O(b) in flight
        assert len(taken) == 4
        assert next(results) == 0
        assert list(results) == list(range(1, 100))
```

### Results in Input Order vs Completion Order

`map()` yields results in input order, so one slow early task holds back every later result
that is already done. `as_completed()` yields futures as they finish.

```python
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed

gate = threading.Event()

def task(index):
    if index == 0:
        gate.wait()
    return index

with ThreadPoolExecutor(max_workers=4) as executor:
    try:
        ordered = executor.map(task, range(4), timeout=0.5)
        try:
            next(ordered)  # waits for task 0, although 1, 2 and 3 finish at once
        except TimeoutError:
            pass
        else:
            raise AssertionError('the first result arrived before task 0 finished')

        futures = [executor.submit(task, index) for index in range(1, 4)]
        finished = {future.result() for future in as_completed(futures)}  # O(n log n)
        assert finished == {1, 2, 3}
    finally:
        gate.set()
```

## Process Pools

### Starting Workers

With the `fork` start method, the default on Linux before Python 3.14, the first `submit()`
forks all w workers at once. With `spawn`, and `forkserver`, the Linux default from 3.14, each
`submit()` starts at most one. Either way `max_tasks_per_child` (3.11+) makes a worker exit and
be replaced after that many tasks, and needs a start method other than `fork`.

```python
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

if __name__ == '__main__':
    for method, started in (('fork', 4), ('spawn', 1)):
        context = multiprocessing.get_context(method)
        with ProcessPoolExecutor(max_workers=4, mp_context=context) as executor:  # O(1)
            assert multiprocessing.active_children() == []
            assert executor.submit(pow, 2, 10).result() == 1024
            assert len(multiprocessing.active_children()) == started
```

### Pickling Happens Later

A process pool pickles each task on a feeder thread, not in `submit()`. So `submit()` does not
pay for large arguments, and an argument that cannot be pickled is reported through its future
rather than by `submit()`.

```python
from concurrent.futures import ProcessPoolExecutor

class Unpicklable:
    def __reduce__(self):
        raise TypeError('cannot pickle this')

if __name__ == '__main__':
    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(abs, Unpicklable())  # O(1) - returns at once
        try:
            future.result()
        except TypeError as error:
            assert 'cannot pickle' in str(error)
        else:
            raise AssertionError('an unpicklable argument was sent')

        # chunksize=5 sends 4 tasks for 20 items: fewer round trips
        assert list(executor.map(abs, range(-20, 0), chunksize=5)) == list(range(20, 0, -1))
```

## Futures

### Reading a Result

`result()` hands back the object the task returned, without copying it, and a future that is
already done answers at once. A cancelled future raises `CancelledError`.

```python
from concurrent.futures import CancelledError, Future, InvalidStateError

payload = list(range(1000))
future = Future()
future.set_result(payload)  # O(c) - no callbacks here
assert future.done() and not future.running()
assert future.result() is payload  # O(1) - the same object
assert future.exception() is None

try:
    future.set_result(None)
except InvalidStateError:
    pass
else:
    raise AssertionError('a finished future accepted a second result')

pending = Future()
assert pending.cancel() is True  # O(c)
try:
    pending.result()
except CancelledError:
    pass
else:
    raise AssertionError('a cancelled future returned a result')
```

### Done Callbacks

A callback added before completion runs in whichever thread completes the future; one added
afterwards runs immediately, in the thread that adds it.

```python
import threading
from concurrent.futures import Future

seen = []
future = Future()
future.add_done_callback(lambda done: seen.append(('early', done.result())))  # O(1)

worker = threading.Thread(target=future.set_result, args=(42,))
worker.start()
worker.join()
assert seen == [('early', 42)]

future.add_done_callback(lambda done: seen.append(('late', threading.current_thread())))
assert seen[1] == ('late', threading.current_thread())  # ran here, at once
```

## Waiting on Many Futures

`wait()` and `as_completed()` each take a set of the futures and sort it by `id()` so that
their locks are always taken in the same order, which is the log factor. They collapse
duplicates, and a `wait()` whose condition already holds returns without blocking.

```python
from concurrent.futures import (
    ALL_COMPLETED, FIRST_COMPLETED, FIRST_EXCEPTION, Future, as_completed, wait,
)

done_ok, failed, pending = Future(), Future(), Future()
done_ok.set_result('ok')
failed.set_exception(ValueError('bad'))

done, not_done = wait([done_ok, pending], return_when=FIRST_COMPLETED)  # O(n log n)
assert done == {done_ok} and not_done == {pending}

done, not_done = wait([done_ok, failed, pending], return_when=FIRST_EXCEPTION)
assert failed in done and pending in not_done

done, not_done = wait([done_ok, pending], timeout=0.01, return_when=ALL_COMPLETED)
assert not_done == {pending}

assert len(list(as_completed([done_ok, done_ok, failed]))) == 2  # duplicates collapse
```

## Common Patterns

### Fan Out, Collect as Finished

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def work(item):
    return item * item

items = range(20)
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(work, item): item for item in items}  # O(n)
    results = {}
    for future in as_completed(futures):  # O(n log n), then one per completion
        results[futures[future]] = future.result()  # O(1)

assert results == {item: item * item for item in items}
```

### Bounded Submission

A loop that submits faster than the pool runs grows the queue without limit. Holding at most a
fixed number of futures in flight keeps memory at that number.

```python
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

limit = 8
total = 0
with ThreadPoolExecutor(max_workers=4) as executor:
    in_flight = set()
    for item in range(100):
        if len(in_flight) >= limit:
            done, in_flight = wait(in_flight, return_when=FIRST_COMPLETED)  # O(limit log limit)
            total += sum(future.result() for future in done)
        in_flight.add(executor.submit(abs, -item))  # O(1)
    total += sum(future.result() for future in in_flight)

assert total == sum(range(100))
```

## Performance Best Practices

✅ **Do**:

- Use a `with` block, so `shutdown(wait=True)` joins the workers even when an exception escapes
- Pass `buffersize` to `map()` (3.14+) or bound submission yourself when the input is large or
  endless: without it every task is submitted, and every future held, before the first result
- Use `as_completed()` when any finished result is useful; `map()` waits on each in input order
- Raise `chunksize` on `ProcessPoolExecutor.map()` for many small tasks, to cut the round trips
- Reuse one pool; with `fork` its first `submit()` starts every worker

❌ **Avoid**:

- `ProcessPoolExecutor` for tasks smaller than their pickled arguments and result: the O(a)
  transfer each way is paid on top of the work
- Calling `wait(return_when=FIRST_COMPLETED)` on the whole pending set once per finished task:
  each call sorts everything still pending, O(n² log n) in all, where `as_completed()` sorts once
- `shutdown(wait=False)` when you then rely on the results being there; nothing has been joined

## Version Notes

- **Python 3.11+**: `concurrent.futures.TimeoutError` is the builtin `TimeoutError`;
  `ProcessPoolExecutor` takes `max_tasks_per_child`
- **Python 3.13+**: the default `max_workers` of both pools follows `os.process_cpu_count()`
- **Python 3.14+**: Added `InterpreterPoolExecutor`, `map(buffersize=...)`,
  `terminate_workers()` and `kill_workers()`; the default start method on Linux is
  `forkserver`, so the first `submit()` no longer starts every worker there

## Related Modules

- **[concurrent.interpreters](concurrent.interpreters.md)** - The interpreters behind
  `InterpreterPoolExecutor`, and what crossing into one costs
- **[multiprocessing](multiprocessing.md)** - `Pool`, start methods, and the queues a process pool
  pickles through
- **[threading](threading.md)** - The threads and locks under `ThreadPoolExecutor`
- **[asyncio](asyncio.md)** - `run_in_executor()` and `wrap_future()` bridge these futures
- **[queue](queue.md)** - Bounded queues for producer-consumer work without futures
