# concurrent.interpreters Module Complexity

The `concurrent.interpreters` module, new in Python 3.14, runs code in isolated interpreters
inside the current process, each with its own modules and its own GIL. Objects are not shared: a
value that crosses into an interpreter, or through one of the module's queues, arrives as a copy,
and a value the fast path cannot copy is pickled. Queues themselves and `memoryview` buffers are
the exceptions, crossing as handles to the same underlying data. So the costs are creating an
interpreter, which is large and fixed, and moving data, which is linear in what moves.

`i` is live interpreters, `s` is the size of the data one call moves across - the bytes or
characters of shareable values, or the pickled size of anything else - `k` is names passed to
`prepare_main()`, `p` is the length of source passed to `exec()`, and `m` is the objects an
interpreter holds when it is closed. The bounds exclude the work of the code or callable run
inside the interpreter.

## Complexity Reference

### Module Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `interpreters.create()` | O(1) | O(1) | Fixed but large, far above a small `call()`: a fresh interpreter initialises its own `sys`, builtins and import system, so reuse interpreters |
| `interpreters.list_all()` | O(i) | O(i) | One `Interpreter` per live interpreter, the main one included |
| `interpreters.get_current()`, `interpreters.get_main()` | O(1) | O(1) | |
| `interpreters.is_shareable(obj)` | O(1) | O(1) | Checks the outer type only: a tuple holding a list passes, and sending it still raises `NotShareableError` |
| `interpreters.create_queue(maxsize=0, *, unbounditems=UNBOUND)` | O(1) | O(1) | `maxsize=0` is unbounded |

### Interpreter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Interpreter.id`, `Interpreter.whence` | O(1) | O(1) | Stored id; `whence` names what created it |
| `Interpreter.is_running()` | O(1) | O(1) | Whether an `exec()` or `call()` is running in it now |
| `Interpreter.prepare_main(ns=None, /, **kwargs)` | O(k + s) | O(k + s) | Copies each value into the interpreter's `__main__`; only shareable values, anything else raises `NotShareableError` |
| `Interpreter.exec(code, /)` | O(p) | O(p) | Compiles and runs in the interpreter's `__main__`; an uncaught exception comes back as `ExecutionFailed`, not the exception itself |
| `Interpreter.call(callable, /, *args, **kwargs)` | O(s) | O(s) | Arguments and return value cross by copy, falling back to pickle; blocks the calling thread |
| `Interpreter.call_in_thread(callable, /, *args, **kwargs)` | O(1) | O(1) | Starts a thread that makes the `call()` and discards its result; the thread pays the O(s) |
| `Interpreter.close()` | O(m) | O(1) | Finalises and frees everything the interpreter holds; the object is unusable afterwards |

### Queue

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Queue.put(obj, block=True, timeout=None, *, unbounditems=None)`, `Queue.put_nowait(obj, *, unbounditems=None)` | O(s) | O(s) | Stores a copy, or a pickle of anything not shareable. On a full bounded queue `put()` waits and `put_nowait()` raises `QueueFull` |
| `Queue.get(block=True, timeout=None)`, `Queue.get_nowait()` | O(s) | O(s) | A copy or unpickled reconstruction, not the object put (singletons such as `None` aside); `QueueEmpty` when there is none. The timeout is truncated to whole seconds, so under one second a `get()` does not wait |
| `Queue.qsize()`, `Queue.empty()`, `Queue.full()` | O(1) | O(1) | Counters held by the queue |
| `Queue.id`, `Queue.maxsize`, `Queue.unbounditems` | O(1) | O(1) | The id is what crosses when a queue is sent to another interpreter |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `interpreters.InterpreterError`, `interpreters.InterpreterNotFoundError` | O(1) | O(1) | The second is raised by a method on a closed interpreter |
| `interpreters.ExecutionFailed`, `ExecutionFailed.excinfo` | O(1) | O(1) | A summary of the uncaught exception - its type name, message and traceback text |
| `interpreters.NotShareableError` | O(1) | O(1) | A value `prepare_main()` cannot copy |
| `interpreters.QueueEmpty`, `interpreters.QueueFull` | O(1) | O(1) | Subclasses of `queue.Empty` and `queue.Full` |

## Creating and Reusing Interpreters

An interpreter is a whole Python runtime, so creating one costs far more than a call into one
that exists. Create a few, reuse them for many calls, and `close()` them when done.

```python
import sys

if sys.version_info >= (3, 14):
    from concurrent import interpreters

    interp = interpreters.create()  # O(1), but a whole runtime
    assert interp in interpreters.list_all()  # O(i)
    assert interpreters.get_main().whence == 'runtime init'
    assert interpreters.get_current().id == interpreters.get_main().id  # O(1)

    for value in range(3):
        assert interp.call(pow, value, 2) == value * value  # reused, O(s) each

    thread = interp.call_in_thread(pow, 2, 5)  # O(1) here; the result is discarded
    thread.join()
    assert not interp.is_running()  # O(1)

    interp.close()  # O(m)
    try:
        interp.exec('pass')
    except interpreters.InterpreterNotFoundError:
        pass
    else:
        raise AssertionError('a closed interpreter ran code')
```

## Moving Data Across

### Values Cross as Copies

`prepare_main()`, `call()` and the queues copy what they carry, so each costs the size of the data
and the receiver gets a distinct object; a `memoryview` is the exception, sharing its buffer.
`is_shareable()` looks at the outer type only.

```python
import sys

if sys.version_info >= (3, 14):
    from concurrent import interpreters

    interp = interpreters.create()
    interp.prepare_main(data=b'x' * 1000, label='run')  # O(k + s)
    interp.exec('size = len(data)')  # O(p)
    assert interp.call(len, b'x' * 1000) == 1000  # O(s) each way

    assert interpreters.is_shareable(([],)) is True  # O(1) - the tuple, not its list
    try:
        interp.prepare_main(nested=([],))
    except interpreters.NotShareableError:
        pass
    else:
        raise AssertionError('a list crossed into another interpreter')

    try:
        interp.exec('raise ValueError("boom")')
    except interpreters.ExecutionFailed as error:
        assert error.excinfo.type.__name__ == 'ValueError'
        assert error.excinfo.msg == 'boom'
    else:
        raise AssertionError('the uncaught exception was lost')
    interp.close()
```

### Queues

A queue is shared by id, so passing one to another interpreter is O(1). The items on it are
copies, pickled when they are not shareable, so `get()` returns a reconstruction, not the object
that was put.

```python
import sys

if sys.version_info >= (3, 14):
    from concurrent import interpreters

    queue = interpreters.create_queue(maxsize=1)  # O(1)
    payload = {'rows': [1, 2, 3]}
    queue.put(payload)  # O(s) - pickled, since a dict is not shareable
    assert queue.full() and queue.qsize() == 1  # O(1)

    try:
        queue.put_nowait('more')
    except interpreters.QueueFull:
        pass
    else:
        raise AssertionError('a full queue took another item')

    received = queue.get()  # O(s)
    assert received == payload and received is not payload
    assert queue.empty()

    try:
        queue.get(timeout=0.5)  # truncated to 0 seconds: raises at once
    except interpreters.QueueEmpty:
        pass
    else:
        raise AssertionError('an empty queue returned an item')
```

## Common Patterns

### A Worker Interpreter Fed by a Queue

```python
import sys
import threading

if sys.version_info >= (3, 14):
    from concurrent import interpreters

    tasks = interpreters.create_queue()
    results = interpreters.create_queue()
    interp = interpreters.create()
    interp.prepare_main(tasks=tasks, results=results)  # O(1) per queue: sent by id

    worker = threading.Thread(target=interp.exec, args=('''
while (item := tasks.get()) is not None:
    results.put(item * item)
''',))
    worker.start()

    for item in range(5):
        tasks.put(item)  # O(s)
    tasks.put(None)
    worker.join()

    assert [results.get() for _ in range(5)] == [0, 1, 4, 9, 16]
    interp.close()
```

## Performance Best Practices

✅ **Do**:

- Create interpreters once and reuse them, or use `concurrent.futures.InterpreterPoolExecutor`,
  which keeps one per worker thread
- Send bytes, strings, numbers and tuples of them: they take the copy path, not pickle
- Close interpreters you are done with; `close()` is what frees their memory

❌ **Avoid**:

- An interpreter per task: `create()` costs more than most small tasks
- Large or deeply nested values sent many times; each crossing is O(s) and makes a new copy
- Relying on `is_shareable()` for containers: it does not look inside a tuple
- A sub-second `timeout` on a queue's `get()` or `put()`; it is truncated to zero

## Version Notes

- **Python 3.14+**: Module added

## Related Modules

- **[concurrent.futures](concurrent_futures.md)** - `InterpreterPoolExecutor` runs tasks on a
  pool of these
- **[threading](threading.md)** - `call_in_thread()` returns a `threading.Thread`
- **[multiprocessing](multiprocessing.md)** - Isolation by process instead, with pickling on
  every transfer
- **[pickle](pickle.md)** - The fallback for values that are not shareable
