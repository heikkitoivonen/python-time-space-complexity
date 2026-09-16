# asyncio Module Complexity

`asyncio` runs many coroutines on one thread. A single event loop holds two
schedules - a queue of callbacks ready now and a heap of callbacks due later -
and drains them in a loop, so nothing in this module costs what a thread would
cost, and nothing in it runs in parallel with anything else.

That shape sets what the bounds below measure. Almost every call here is O(1):
it appends one entry to a schedule and returns. The costs worth knowing are
the ones that are not - the calls linear in the awaitables you hand them, the
heap operations that make a timer dearer than an immediate callback, the
broadcasts that touch every waiter on a primitive, and the snapshots that build
a fresh container of everything the loop is tracking.

No bound here prices the coroutine's own work, or the I/O it waits on. An
`await` that resolves after a network round trip costs a round trip; what
`asyncio` contributes is the scheduling around it.

## Complexity Reference

Size variables: n = awaitables passed to one call; t = unfinished tasks alive
in the process and still registered, which is the population a task snapshot
filters; g = live async generators the loop is tracking; r = callbacks already
in the ready queue; s = timers on the loop's heap; u = timers that come due in
one iteration; x = cancelled timers sitting at the head of the heap; k = done
callbacks on one future; w = tasks waiting on one synchronization primitive; q =
items in a queue; b = bytes read or written; d = the longest separator
`readuntil` is given; j = how many it is given; c = frames one task's stack
exposes; f = frames and awaited tasks in a captured call graph; e = entries in
one `writelines` iterable; a = addresses a host name resolved to; v = argument
and environment bytes handed to a child process.

Bounds marked "+ round trip" do local work in the stated bound and then wait
for a peer, the operating system, or the clock. The wait is not priced.

### Running asyncio programs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.run(coro)` | O(t + g + r + s) + the coroutine | O(t + g) | Creates a loop and runs `coro`; everything but the coroutine is the shutdown, which cancels every unfinished task, closes the g live async generators, and clears the ready queue and the timer heap |
| `asyncio.Runner(...)` | O(1) | O(1) | Python 3.11+; defers loop creation to the first `run()` |
| `asyncio.Runner.run(coro)` | O(1) + the coroutine | O(t + s) | As `run()` without the shutdown, which `close()` does once for the runner's whole lifetime |
| `asyncio.Runner.get_loop()` | O(1) | O(1) | Creates the loop if this is the first call, then returns the stored one |
| `asyncio.Runner.close()` | O(t + g + r + s) | O(t + g) | Snapshots the unfinished tasks into a set and cancels them, snapshots and closes the generators, waits for the default executor, and clears both schedules |

### Event loop references

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.get_running_loop()` | O(1) | O(1) | Reads the thread's running-loop slot; raises `RuntimeError` outside a loop |
| `asyncio.get_event_loop()` | O(1) | O(1) | Returns the running loop inside one, or the loop `set_event_loop()` installed for this thread. With neither, Python 3.14 raises `RuntimeError`; earlier versions create one and warn, but only on the main thread and only before a loop has been set or cleared there - elsewhere they raise too |
| `asyncio.new_event_loop()` | O(1) | O(1) | Opens the selector and the self-pipe; the loop starts with empty schedules |
| `asyncio.set_event_loop(loop)` | O(1) | O(1) | Stores the loop for this thread |
| `asyncio.get_event_loop_policy()` | O(1) | O(1) | Deprecated in Python 3.14, for removal in 3.16 |
| `asyncio.set_event_loop_policy(policy)` | O(1) | O(1) | Deprecated in Python 3.14, for removal in 3.16 |
| `asyncio.EventLoop` | O(1) | O(1) | Python 3.13+; the platform's loop class, `SelectorEventLoop` on Unix |
| `asyncio.AbstractEventLoop` | - | - | The interface the loop classes implement; defines no bounds of its own |

### AbstractEventLoop scheduling

The ready queue is a deque and the timer schedule is a heap, which is the whole
difference between the two rows below.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `loop.call_soon(cb, *args)` | O(1) | O(1) | Appends one `Handle` to the ready deque |
| `loop.call_soon_threadsafe(cb, *args)` | O(1) | O(1) | As `call_soon`, plus one byte written to the self-pipe to wake the loop |
| `loop.call_later(delay, cb, *args)` | O(log s) | O(1) | Pushes a `TimerHandle` onto the timer heap |
| `loop.call_at(when, cb, *args)` | O(log s) | O(1) | As `call_later`, with an absolute deadline on the loop's clock |
| `loop.time()` | O(1) | O(1) | A monotonic clock reading |
| One loop iteration | O((u + x) log s + r), plus O(s) on a sweep | O(s) while sweeping, else O(1) | Pops the u due timers off the heap and the x cancelled entries sitting at its head, then runs every callback the deque held when the iteration began. The bulk sweep replaces both: it rebuilds the heap in a new list when it holds more than 100 timers with over half cancelled, whether or not a timer is due |
| `loop.run_forever()` | O(1) + the callbacks | O(1) | Iterates until `stop()` |
| `loop.run_until_complete(future)` | O(1) + the future | O(1) | Adds a done callback that stops the loop, then runs it |
| `loop.stop()` | O(1) | O(1) | Sets a flag the current iteration checks |
| `loop.is_running()`, `loop.is_closed()` | O(1) | O(1) | Flag reads |
| `loop.close()` | O(r + s) | O(1) | Clears both schedules and closes the selector |

### AbstractEventLoop tasks, futures and executors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `loop.create_future()` | O(1) | O(1) | A bare `Future` bound to this loop |
| `loop.create_task(coro)` | O(1) | O(1) | Wraps `coro` in a `Task` and schedules its first step. An eager factory instead runs the coroutine until its first suspension before returning |
| `loop.set_task_factory(factory)`, `loop.get_task_factory()` | O(1) | O(1) | Stores or reads one callable |
| `loop.run_in_executor(executor, fn, *args)` | O(1) + `fn` | O(1) | Submits to a thread pool and wraps the `concurrent.futures.Future`; `fn` runs off the loop thread |
| `loop.set_default_executor(executor)` | O(1) | O(1) | Stores one executor |
| `loop.shutdown_default_executor()` | O(1) + the pool | O(1) | Waits for the pool's threads to finish |
| `loop.shutdown_asyncgens()` | O(g) | O(g) | Snapshots the live async generators and closes each |
| `loop.get_debug()`, `loop.set_debug(enabled)` | O(1) | O(1) | Flag access |
| `loop.set_exception_handler(handler)`, `loop.get_exception_handler()` | O(1) | O(1) | Stores or reads one callable |
| `loop.call_exception_handler(context)`, `loop.default_exception_handler(context)` | O(k log k) | O(k) | The default handler sorts the context dict's keys before formatting each into the log message |

### AbstractEventLoop networking

Every row below does bounded local work and then waits on the network or the
operating system. The local bound is what is stated; the wait is not.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `loop.getaddrinfo(host, port)`, `loop.getnameinfo(sockaddr)` | O(1) + round trip | O(a) | Runs the blocking resolver in the default executor |
| `loop.create_connection(factory, host, port)` | O(a) + round trip | O(a) | Holds the resolved address list, and the errors from the failed attempts, while trying each until one connects |
| `loop.create_server(factory, host, port)` | O(a) | O(a) | Binds one listening socket per resolved address |
| `loop.create_unix_connection(...)`, `loop.create_unix_server(...)` | O(1) + round trip | O(1) | Unix builds only; no resolution step |
| `loop.create_datagram_endpoint(factory, ...)` | O(a) + round trip | O(a) | Resolves the local and remote names, pairs them into a candidate list, and tries each until one socket binds |
| `loop.connect_accepted_socket(factory, sock)` | O(1) | O(1) | Wraps an already-accepted socket in a transport |
| `loop.connect_read_pipe(factory, pipe)`, `loop.connect_write_pipe(factory, pipe)` | O(1) | O(1) | Registers one pipe with the selector |
| `loop.start_tls(transport, protocol, context)` | O(1) + round trip | O(1) | Handshake over an open transport |
| `loop.sendfile(transport, file)`, `loop.sock_sendfile(sock, file)` | O(b) + round trip | O(1) | Uses the kernel's `sendfile` where available, so the bytes need not pass through Python |
| `loop.add_signal_handler(sig, cb)`, `loop.remove_signal_handler(sig)` | O(1) | O(1) | Unix builds only |

### Handle and TimerHandle

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Handle.cancel()` | O(1) | O(1) | Clears the callback; the loop skips the entry when it reaches it, rather than removing it now |
| `Handle.cancelled()` | O(1) | O(1) | Flag read |
| `Handle.get_context()` | O(1) | O(1) | Python 3.12+; the `contextvars.Context` captured at scheduling time |
| `TimerHandle.when()` | O(1) | O(1) | The stored deadline |
| `TimerHandle.cancel()` | O(1) | O(1) | As `Handle.cancel()`, and increments the loop's cancelled-timer count |

### Future

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.Future(loop=...)` | O(1) | O(1) | Starts pending with no callbacks |
| `Future.result()`, `Future.exception()` | O(1) | O(1) | Returns the stored object; raises `InvalidStateError` while pending |
| `Future.set_result(value)`, `Future.set_exception(exc)` | O(k) | O(k) | Each of the k done callbacks is scheduled with `call_soon`, so the ready queue grows by k handles rather than the callbacks running here |
| `Future.done()`, `Future.cancelled()` | O(1) | O(1) | State reads |
| `Future.cancel(msg=None)` | O(k) | O(k) | Marks cancelled and schedules the same k callbacks |
| `Future.add_done_callback(cb)` | O(1) | O(1) | Appends; on an already-done future, schedules `cb` instead |
| `Future.remove_done_callback(cb)` | O(k) | O(k) | Rebuilds the callback list without `cb` |
| `Future.get_loop()` | O(1) | O(1) | The stored loop |
| `await future` | O(1) | O(1) | Suspends the awaiting task and registers one done callback |

### Task

`Task` is a `Future`, with two exceptions: `set_result()` and
`set_exception()` raise `RuntimeError`, because a task's result comes from its
coroutine. Every other `Future` row applies. These are the additions.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.Task(coro, loop=...)` | O(1) | O(1) | Registers the task with the loop and schedules the first step |
| `Task.get_coro()`, `Task.get_name()` | O(1) | O(1) | Stored attributes |
| `Task.get_context()` | O(1) | O(1) | Python 3.12+; the `contextvars.Context` the task runs its steps in |
| `Task.set_name(value)` | O(1) | O(1) | `str(value)` is stored |
| `Task.cancel(msg=None)` | O(1) plus the awaited future's own `cancel()` | O(1) | Arranges for `CancelledError` at the task's next step, or cancels the future it is currently waiting on. That future's cancel is not always O(1): a task suspended on `gather()` cancels each of its n children here, synchronously. The coroutine still handles the error later |
| `Task.cancelling()`, `Task.uncancel()` | O(1) | O(1) | Python 3.11+; read and decrement the cancellation counter `TaskGroup` and `timeout()` use |
| `Task.get_stack(limit=None)` | O(c) | O(c) | A suspended task exposes the single frame it is suspended in, however deep the coroutines below it; a task that raised exposes its traceback's frames |
| `Task.print_stack(limit=None, file=None)` | O(c) | O(c) | Formats the same frames |
| `Task.result()`, `Task.exception()`, `Task.cancelled()` | O(1) | O(1) | `Future`'s, unchanged |
| `Task.add_done_callback(cb)`, `Task.remove_done_callback(cb)` | O(1), O(k) | O(1), O(k) | `Future`'s, unchanged |

### Extending Task and Future

These four hooks let an alternative `Task` implementation keep `all_tasks()`
and `current_task()` accurate. They are documented for that purpose and are not
part of ordinary use.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio._register_task(task)` | O(1) | O(1) | Adds the task to the set `all_tasks()` snapshots |
| `asyncio._unregister_task(task)` | O(1) | O(1) | Removes it |
| `asyncio._enter_task(loop, task)` | O(1) | O(1) | Sets the loop's current-task slot; raises `RuntimeError` if one is already running |
| `asyncio._leave_task(loop, task)` | O(1) | O(1) | Clears it, raising `RuntimeError` if `task` is not the one entered |

### Coroutine and task functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.create_task(coro, name=None)` | O(1) | O(1) | Requires a running loop; delegates to `loop.create_task` |
| `asyncio.ensure_future(obj)` | O(1) | O(1) | Returns a `Future` unchanged, wraps a coroutine in a `Task`, and wraps any other awaitable in a task around it |
| `asyncio.current_task(loop=None)` | O(1) | O(1) | Reads the loop's current-task slot |
| `asyncio.all_tasks(loop=None)` | O(t) | O(t) | Scans the process-wide task registry, not just this loop's tasks, and builds a new `set` of the ones belonging to `loop` on every call. Before Python 3.14 a finished task stays registered while anything still references it, so keeping completed tasks around makes every call dearer |
| `asyncio.sleep(0)` | O(1) | O(1) | Yields to the loop once without scheduling a timer |
| `asyncio.sleep(delay)` | O(log s) | O(1) | One timer on the heap for a positive delay |
| `asyncio.iscoroutine(obj)`, `asyncio.isfuture(obj)` | O(1) | O(1) | Type checks |
| `asyncio.iscoroutinefunction(fn)` | O(1) | O(1) | Deprecated in Python 3.14, for removal in 3.16; use `inspect.iscoroutinefunction` |
| `asyncio.eager_task_factory(loop, coro, ...)` | O(1) + the coroutine's first step | O(1) | Python 3.12+; runs the coroutine until it first suspends, and returns a finished task if it never does |
| `asyncio.create_eager_task_factory(task_class)` | O(1) | O(1) | Python 3.12+; builds such a factory for a `Task` subclass |

### Running awaitables concurrently

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.gather(*aws)` | O(n) setup, O(n) on completion | O(n) | Wraps each awaitable and adds a done callback; assembles the results list in argument order once all n finish |
| `asyncio.wait(aws, timeout=None, return_when=...)` | O(n) | O(n) | Adds a callback to each, then partitions them into the `done` and `pending` sets. A `timeout` adds one timer. From Python 3.11 the awaitables must already be tasks or futures; a bare coroutine raises `TypeError` |
| `asyncio.as_completed(aws, timeout=None)` | O(n) setup | O(n) | Yields n results in completion order. Python 3.13+ also supports `async for`, which hands back each input that was already a task or future, and the wrapping task for an input that was a bare coroutine; earlier versions yield wrapper coroutines that must be awaited for the result |
| `asyncio.TaskGroup()` | O(1) | O(1) | Python 3.11+ |
| `TaskGroup.create_task(coro)` | O(1) | O(1) | Adds the task to the group's set |
| `async with TaskGroup()` exit | O(n) | O(n) | n = tasks created in the group; waits for all, and on failure cancels the rest and collects an `ExceptionGroup` |
| `asyncio.shield(aw)` | O(1) | O(1) | One outer future; cancelling it leaves the inner awaitable running |
| `asyncio.wait_for(aw, timeout)` | O(log s) | O(1) | One timer around one awaitable |
| `asyncio.timeout(delay)`, `asyncio.timeout_at(when)` | O(1) | O(1) | Python 3.11+; the context manager object. Entering it schedules one timer |
| `Timeout.when()`, `Timeout.expired()` | O(1) | O(1) | Stored deadline and flag |
| `Timeout.reschedule(when)` | O(log s) | O(1) | Cancels the pending timer and pushes a new one |
| `asyncio.to_thread(fn, *args)` | O(1) + `fn` | O(1) | Runs `fn` on the default thread pool with the caller's context copied |
| `asyncio.run_coroutine_threadsafe(coro, loop)` | O(1) | O(1) | Schedules the coroutine on another thread's loop; returns a `concurrent.futures.Future` |
| `asyncio.wrap_future(future, loop=None)` | O(1) | O(1) | Bridges a `concurrent.futures.Future` to an `asyncio.Future` |

### Call graph introspection

Python 3.14+. `capture_call_graph()` walks the awaited-by links a task records.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.capture_call_graph(future=None, depth=0, limit=None)` | O(f) | O(f) | Walks the frames of the target and the tasks awaiting it |
| `asyncio.format_call_graph(...)`, `asyncio.print_call_graph(...)` | O(f·h) | O(f·h) | h = the depth of the awaited-by chain; each line is indented one level per step, so a deep chain renders more text than a wide graph with the same f |
| `asyncio.future_add_to_awaited_by(fut, waiter)` | O(1) | O(1) | Records one awaiter on the future |
| `asyncio.future_discard_from_awaited_by(fut, waiter)` | O(1) | O(1) | Removes it |
| `asyncio.FutureCallGraph`, `asyncio.FrameCallGraphEntry` | O(1) | O(1) | The named tuples a capture is built from |

### Queue, LifoQueue and PriorityQueue

The three differ only in the container behind them: a deque, a list used as a
stack, and a heap.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.Queue(maxsize=0)` | O(1) | O(1) | Unbounded by default |
| `Queue.put_nowait(item)`, `Queue.get_nowait()` | O(1) | O(1) | Raises `QueueFull` or `QueueEmpty` rather than waiting. `PriorityQueue` is O(log q) for both |
| `Queue.put(item)` | O(1) | O(1) | Waits only when the queue is full; `PriorityQueue` is O(log q) |
| `Queue.get()` | O(1) | O(1) | Waits only when the queue is empty; `PriorityQueue` is O(log q) |
| `Queue.qsize()`, `Queue.empty()`, `Queue.full()` | O(1) | O(1) | Length and bound comparisons |
| `Queue.maxsize` | O(1) | O(1) | The stored limit; 0 means unbounded |
| `Queue.task_done()` | O(1), O(w) at zero | O(1), O(w) at zero | Decrements the unfinished count; the call that brings it to zero wakes every `join()` waiter, queueing w callbacks |
| `Queue.join()` | O(1) | O(1) | Returns at once when nothing is unfinished |
| `Queue.shutdown(immediate=False)` | O(w); immediate adds O(q), or O(q log q) for `PriorityQueue` | O(w) | Python 3.13+; wakes every waiter blocked in `get()` or `put()` so each raises `QueueShutDown`. With `immediate`, also drains the q queued items one at a time through the queue's own `get` - a heap pop for `PriorityQueue` - and releases the `join()` waiters; without it they keep waiting until `task_done()` balances the outstanding work |
| `asyncio.LifoQueue`, `asyncio.PriorityQueue` | as above | O(q) | Last-in-first-out over a list, and lowest-first over a heap |

### Lock, Semaphore, BoundedSemaphore, Event, Condition and Barrier

Each primitive keeps a deque of waiter futures. Acquiring and releasing touch
one; the broadcasts touch all w. A waiter that gives up removes its own future
from that deque, which is O(1) at either end and O(w) from the middle - so a
cancelled waiter deep in a long queue is the one case where an otherwise
constant-time wait is not.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Lock.acquire()` | O(1), O(w) past cancelled waiters | O(1) | Uncontended with no queue, sets a flag. Contended, appends one future and waits. The uncontended path scans the queue when one exists, to check that every waiter in it was cancelled |
| `Lock.release()` | O(1) | O(1) | Clears the flag and wakes the first queued waiter, unless that waiter is already done |
| `Lock.locked()` | O(1) | O(1) | Flag read |
| `Semaphore(value)`, `Semaphore.acquire()`, `Semaphore.release()` | O(1), O(w) past done waiters | O(1) | A counter and the same waiter deque. `release()` scans from the front for the first waiter that is not already done |
| `Semaphore.locked()` | O(w) | O(1) | True when the counter is exhausted, and also while any queued waiter is uncancelled, which FIFO order requires it to scan for |
| `BoundedSemaphore(value)` | O(1) | O(1) | As `Semaphore`, but `release()` past the initial value raises `ValueError` |
| `Event.set()` | O(w) | O(w) | Resolves every waiter's future, which queues w callbacks on the loop |
| `Event.clear()`, `Event.is_set()` | O(1) | O(1) | Flag access |
| `Event.wait()` | O(1) | O(1) | Returns immediately when the flag is set |
| `Condition(lock=None)` | O(1) | O(1) | Wraps a `Lock` |
| `Condition.wait()` | O(1) | O(1) | Releases the lock, waits, then reacquires it |
| `Condition.wait_for(predicate)` | O(p) per wake | O(1) | p = the predicate's own cost; re-evaluated after each notification until it is true |
| `Condition.notify(n=1)` | O(w) | O(n) | Walks the waiter deque until n of them have been woken, skipping any already done, so it is O(n) only when the front of the queue is live |
| `Condition.notify_all()` | O(w) | O(w) | `notify(len(waiters))` |
| `Barrier(parties)` | O(1) | O(1) | Python 3.11+ |
| `Barrier.wait()` | O(1), O(w) twice a cycle | O(1), O(w) twice a cycle | The arrival that fills the barrier wakes every participant, and the last of them to leave wakes whoever is queued for the next cycle. Both are broadcasts; every other arrival and departure is constant |
| `Barrier.parties`, `Barrier.n_waiting`, `Barrier.broken` | O(1) | O(1) | Counter and flag reads |
| `Barrier.reset()`, `Barrier.abort()` | O(w) | O(w) | Both wake every waiter; `abort()` leaves the barrier broken so later arrivals raise `BrokenBarrierError` |

### Streams

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.open_connection(host, port, limit=65536)` | O(a) + round trip | O(limit) | a = resolved addresses; the reader's buffer grows to `limit` before `readuntil` refuses |
| `asyncio.open_unix_connection(path, ...)` | O(1) + round trip | O(limit) | Unix builds only |
| `asyncio.start_server(cb, host, port, ...)` | O(a) | O(a) | One listening socket per resolved address |
| `asyncio.start_unix_server(cb, path, ...)` | O(1) | O(1) | Unix builds only |

### StreamReader and StreamWriter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `StreamReader.read(n=-1)` | O(b) | O(b) | `n = -1` reads to EOF and holds the whole stream in memory; a positive `n` returns at most n bytes |
| `StreamReader.readline()` | O(b + d) | O(b) | `readuntil(b'\n')`, but returns the partial line at EOF rather than raising `IncompleteReadError`. Over the stream's limit it raises `ValueError`, and unlike `readuntil` it drops the oversized data from the buffer |
| `StreamReader.readuntil(separator=b'\n')` | O(j log j + j(b + d)) | O(b + j) | j = separators, 1 unless a tuple is passed, which Python 3.13+ is what accepts at all; they are sorted by length first, so the shortest match wins. The buffer is scanned once per separator. The scan resumes from a remembered offset, re-examining only the last d - 1 bytes so a separator straddling two chunks is still found. Raises `LimitOverrunError` past the stream's limit and `IncompleteReadError` at EOF |
| `StreamReader.readexactly(n)` | O(n) | O(n) | Raises `IncompleteReadError` if EOF arrives first |
| `StreamReader.at_eof()` | O(1) | O(1) | True once the buffer is empty and EOF was fed |
| `StreamReader.feed_eof()` | O(1) | O(1) | Marks the end and wakes a waiting read |
| `async for line in reader` | O(b + d) per line | O(b) | `readline()` until it returns empty |
| `StreamWriter.write(data)` | O(b + e) | O(b) | Buffers on the transport without waiting for the socket, then checks whether to pause writing - which sums the e chunks already buffered |
| `StreamWriter.writelines(data)` | O(b + e) | O(b) | e = items in the iterable. The transport's default implementation concatenates them and writes the result; the socket transport overrides it to buffer one `memoryview` per item instead, making it O(e) with no copy of the bytes |
| `StreamWriter.drain()` | O(1) + round trip | O(1) | Returns at once unless the transport's buffer is over its high-water mark |
| `StreamWriter.write_eof()`, `StreamWriter.can_write_eof()` | O(1) | O(1) | Half-close support |
| `StreamWriter.close()`, `StreamWriter.is_closing()` | O(1) | O(1) | Flushes what is buffered, then closes |
| `StreamWriter.wait_closed()` | O(1) + the flush | O(1) | Waits for the transport to finish closing |
| `StreamWriter.transport` | O(1) | O(1) | The stored transport |
| `StreamWriter.get_extra_info(name, default=None)` | O(1) | O(1) | One dict lookup on the transport |
| `StreamWriter.start_tls(context)` | O(1) + round trip | O(1) | Python 3.11+ |
| `asyncio.StreamReaderProtocol` | O(1) | O(1) | The protocol wiring a reader and writer to a transport |

### Server

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Server.sockets` | O(k) | O(k) | k = listening sockets; a fresh tuple each call |
| `Server.is_serving()` | O(1) | O(1) | Flag read |
| `Server.start_serving()`, `Server.serve_forever()` | O(k) | O(k) | Registers an accept callback per listening socket; `serve_forever()` then waits |
| `Server.close()` | O(k) | O(1) | Stops accepting; open connections continue |
| `Server.close_clients()`, `Server.abort_clients()` | O(m) | O(m) | Python 3.13+; m = open connections; both copy the connection set before closing them gracefully or at once |
| `Server.wait_closed()` | O(1) + the connections | O(1) | Waits for the sockets and the remaining handlers |
| `Server.get_loop()` | O(1) | O(1) | The stored loop |
| `asyncio.AbstractServer` | - | - | The interface `Server` implements |

### Subprocesses

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.create_subprocess_exec(program, *args)` | O(v) + the spawn | O(v) | v = the argument list and the environment passed to the child, both copied on the way to `fork` and `exec` |
| `asyncio.create_subprocess_shell(cmd)` | O(v) + the spawn | O(v) | v is the command string and the environment; a shell is spawned to parse `cmd` |
| `Process.pid`, `Process.returncode` | O(1) | O(1) | Stored values; `returncode` is `None` until exit |
| `Process.stdin`, `Process.stdout`, `Process.stderr` | O(1) | O(1) | The stream objects, or `None` for a pipe that was not requested |
| `Process.wait()` | O(1) + the child | O(1) | Waits for exit. Deadlocks if the child fills a pipe nobody is draining |
| `Process.communicate(input=None)` | O(b) | O(b) | Writes `input`, drains both output pipes concurrently, and returns them whole |
| `Process.send_signal(sig)`, `Process.terminate()`, `Process.kill()` | O(1) | O(1) | One signal to the child |

### Transports

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BaseTransport.close()`, `BaseTransport.is_closing()` | O(1) | O(1) | Flushes what is buffered, then closes |
| `BaseTransport.get_extra_info(name, default=None)` | O(1) | O(1) | One dict lookup |
| `BaseTransport.get_protocol()`, `BaseTransport.set_protocol(p)` | O(1) | O(1) | Attribute access |
| `ReadTransport.is_reading()`, `ReadTransport.pause_reading()`, `ReadTransport.resume_reading()` | O(1) | O(1) | Adds or removes the socket's read registration |
| `WriteTransport.write(data)` | O(b + e) | O(b) | Writes what the socket accepts now, buffers the rest, then runs the flow-control check over the e buffered chunks |
| `WriteTransport.writelines(data)` | O(b + e) | O(b) | The base implementation joins the items and calls `write()`. A transport may override it: the socket one buffers a `memoryview` per item and writes them vectored, which avoids the copy |
| `WriteTransport.write_eof()`, `WriteTransport.can_write_eof()` | O(1) | O(1) | Half-close |
| `WriteTransport.abort()` | O(1) | O(1) | Closes at once and discards the buffer |
| `WriteTransport.get_write_buffer_size()` | O(e) | O(1) | e = chunks currently buffered; the socket transport sums their lengths rather than keeping a running total, and the flow-control check that decides whether to pause writing calls it on every write |
| `WriteTransport.get_write_buffer_limits()` | O(1) | O(1) | The stored watermarks behind `pause_writing` and `drain()` |
| `WriteTransport.set_write_buffer_limits(high, low)` | O(e) | O(1) | Stores the watermarks and re-runs the flow-control check against them |
| `DatagramTransport.sendto(data, addr=None)` | O(b) | O(b) | One datagram |
| `DatagramTransport.abort()` | O(1) | O(1) | Closes without flushing |
| `SubprocessTransport.get_pid()`, `SubprocessTransport.get_returncode()` | O(1) | O(1) | Stored values |
| `SubprocessTransport.get_pipe_transport(fd)` | O(1) | O(1) | One dict lookup |
| `SubprocessTransport.send_signal(sig)`, `SubprocessTransport.terminate()`, `SubprocessTransport.kill()` | O(1) | O(1) | One signal |
| `asyncio.Transport` | - | - | `ReadTransport` and `WriteTransport` together |

### Protocols

Protocol methods are callbacks the loop invokes; their cost is the
application's. The bounds below are what `asyncio` does around each call.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BaseProtocol.connection_made(transport)`, `BaseProtocol.connection_lost(exc)` | O(1) | O(1) | Called once each |
| `BaseProtocol.pause_writing()`, `BaseProtocol.resume_writing()` | O(1) | O(1) | Called as the write buffer crosses its watermarks |
| `Protocol.data_received(data)` | O(1) | O(b) | Called with each chunk the socket produced; `asyncio` does not reassemble them |
| `Protocol.eof_received()` | O(1) | O(1) | Return true to keep the transport open |
| `BufferedProtocol.get_buffer(sizehint)`, `BufferedProtocol.buffer_updated(nbytes)`, `BufferedProtocol.eof_received()` | O(1) | O(1) | The socket reads into the protocol's own buffer, so no per-chunk `bytes` object is allocated |
| `DatagramProtocol.datagram_received(data, addr)`, `DatagramProtocol.error_received(exc)` | O(1) | O(b) | One call per datagram |
| `SubprocessProtocol.pipe_data_received(fd, data)`, `SubprocessProtocol.pipe_connection_lost(fd, exc)`, `SubprocessProtocol.process_exited()` | O(1) | O(b) | One call per chunk or event |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `asyncio.CancelledError` | O(1) | O(1) | Inherits `BaseException`, not `Exception`, so `except Exception` does not swallow a cancellation |
| `asyncio.TimeoutError` | O(1) | O(1) | The builtin `TimeoutError` from Python 3.11 on; a distinct class before that |
| `asyncio.InvalidStateError` | O(1) | O(1) | Result or exception set on a done future, or read from a pending one |
| `asyncio.IncompleteReadError` | O(1) | O(1) | `IncompleteReadError.partial` holds the bytes read, `IncompleteReadError.expected` the number wanted |
| `asyncio.LimitOverrunError` | O(1) | O(1) | `LimitOverrunError.consumed` says how far the scan got; the data stays in the buffer |
| `asyncio.QueueEmpty`, `asyncio.QueueFull`, `asyncio.QueueShutDown` | O(1) | O(1) | `QueueShutDown` is Python 3.13+ |
| `asyncio.BrokenBarrierError` | O(1) | O(1) | Python 3.11+ |
| `asyncio.SendfileNotAvailableError` | O(1) | O(1) | The platform has no usable `sendfile` for this pair |

## Two Schedules, Two Costs

The loop holds ready callbacks in a deque and timers in a heap. An immediate
callback is an append; a delayed one is a heap push. `sleep(0)` is the special
case: it yields to the loop without becoming a timer at all.

```python
import asyncio
import asyncio.base_events
import heapq

pushes = 0
real_heappush = heapq.heappush


def counting_heappush(heap, item):
    global pushes
    pushes += 1
    return real_heappush(heap, item)


async def main():
    global pushes
    loop = asyncio.get_running_loop()
    asyncio.base_events.heapq.heappush = counting_heappush
    try:
        # O(1): straight onto the ready deque
        pushes = 0
        loop.call_soon(lambda: None)
        assert pushes == 0

        # O(log s): onto the timer heap
        pushes = 0
        handle = loop.call_later(10, lambda: None)
        assert pushes == 1
        handle.cancel()

        # sleep(0) yields without scheduling a timer
        pushes = 0
        await asyncio.sleep(0)
        assert pushes == 0

        # any positive delay does
        pushes = 0
        await asyncio.sleep(0.001)
        assert pushes == 1
    finally:
        asyncio.base_events.heapq.heappush = real_heappush


asyncio.run(main())
```

Cancelling a timer does not remove it from the heap: `TimerHandle.cancel()`
clears the callback and leaves the entry in place. The loop drops the dead
entries in two ways, and which one applies decides how long they are carried.
Cancelled entries at the head are popped on the next iteration, so cancelling
the *soonest* timeout reclaims it promptly. An entry behind a live one is
carried until either it reaches the head in its turn or the bulk sweep runs,
and that sweep needs the heap to hold more than 100 timers with over half of
them cancelled. A loop that keeps a long-lived timer in front of many cancelled
ones therefore holds on to them.

## gather and wait Are Linear in Their Awaitables

`gather()` wraps every awaitable before the first one runs, so its setup grows
with n even though each individual wrap is O(1), and it then assembles a result
list in argument order. `wait()` does not wrap: from Python 3.11 it requires
tasks or futures and refuses a bare coroutine. Its n is the callback it adds to
each, and the two sets it partitions them into.

```python
import asyncio


async def value(x):
    return x


async def main():
    # gather: n wraps up front, one list of n results in argument order
    results = await asyncio.gather(*[value(i) for i in range(5)])
    assert results == [0, 1, 2, 3, 4]

    # wait: one callback added per task, two sets out
    tasks = [asyncio.create_task(value(i)) for i in range(5)]
    done, pending = await asyncio.wait(tasks)
    assert len(done) == 5
    assert pending == set()

    # FIRST_COMPLETED returns as soon as one finishes - the rest stay pending
    slow = [asyncio.create_task(asyncio.sleep(10)) for _ in range(3)]
    quick = asyncio.create_task(value(1))
    done, pending = await asyncio.wait(
        [*slow, quick], return_when=asyncio.FIRST_COMPLETED
    )
    assert quick in done
    assert len(pending) == 3
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


asyncio.run(main())
```

`asyncio.TaskGroup` costs the same n, charged one task at a time: each
`create_task()` is O(1), and the `async with` exit waits for whatever the group
accumulated. Unlike `gather()`, a failure there cancels the siblings and raises
an `ExceptionGroup`.

## all_tasks Builds a Fresh Set

`current_task()` reads one slot. `all_tasks()` filters every task the loop is
tracking and returns a new `set`, so it is O(t) in both time and space each
time it is called - it is a snapshot, not a view.

```python
import asyncio


async def main():
    tasks = [asyncio.create_task(asyncio.sleep(10)) for _ in range(4)]
    await asyncio.sleep(0)

    first = asyncio.all_tasks()
    second = asyncio.all_tasks()

    # Equal contents, but a new set each call - O(t), not a stored one
    assert first == second
    assert first is not second

    # The caller's own task is in the snapshot; current_task() is the O(1) way
    assert asyncio.current_task() in first
    assert len(first) == len(tasks) + 1

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


asyncio.run(main())
```

## A Broadcast Touches Every Waiter

Acquiring and releasing a lock or semaphore touches one waiter. `Event.set()`,
`Condition.notify_all()` and a barrier's final arrival touch all w of them, so
those are the rows where the waiter count reaches the bound.

```python
import asyncio


async def main():
    event = asyncio.Event()
    waiters = [asyncio.create_task(event.wait()) for _ in range(8)]
    await asyncio.sleep(0)

    # All eight are queued on the one event
    assert len(event._waiters) == 8

    # O(w): set() resolves every one of them
    event.set()
    assert await asyncio.gather(*waiters) == [True] * 8

    # Once set, waiting is O(1) and never queues
    assert event.is_set()
    await event.wait()
    assert not event._waiters

    condition = asyncio.Condition()
    woken = []
    waiting = [asyncio.create_task(_wait_on(condition, woken, i)) for i in range(5)]
    while len(condition._waiters) < 5:
        await asyncio.sleep(0)

    # notify(2) wakes exactly two, however many are queued
    async with condition:
        condition.notify(2)
    for _ in range(8):
        await asyncio.sleep(0)
    assert len(woken) == 2

    # notify_all() wakes whatever is left
    async with condition:
        condition.notify_all()
    await asyncio.gather(*waiting)
    assert len(woken) == 5


async def _wait_on(condition, woken, index):
    async with condition:
        await condition.wait()
        woken.append(index)


asyncio.run(main())
```

## A Queue's Cost Is Its Container

`Queue` is a deque and `LifoQueue` is a list used as a stack, so both move an
item in O(1). `PriorityQueue` is a heap, which buys ordering for O(log q).

```python
import asyncio


async def main():
    fifo = asyncio.Queue()
    lifo = asyncio.LifoQueue()
    prio = asyncio.PriorityQueue()

    for i in (3, 1, 2):
        fifo.put_nowait(i)   # O(1) deque append
        lifo.put_nowait(i)   # O(1) list append
        prio.put_nowait(i)   # O(log q) heap push

    assert [fifo.get_nowait() for _ in range(3)] == [3, 1, 2]
    assert [lifo.get_nowait() for _ in range(3)] == [2, 1, 3]
    assert [prio.get_nowait() for _ in range(3)] == [1, 2, 3]

    # qsize() is a length, not a walk
    bounded = asyncio.Queue(maxsize=2)
    await bounded.put("a")
    await bounded.put("b")
    assert bounded.qsize() == 2 and bounded.full()

    # A full queue refuses rather than growing
    try:
        bounded.put_nowait("c")
    except asyncio.QueueFull:
        pass
    else:
        raise AssertionError("expected QueueFull")

    # join() returns at once when nothing is outstanding
    bounded.get_nowait()
    bounded.get_nowait()
    bounded.task_done()
    bounded.task_done()
    await bounded.join()


asyncio.run(main())
```

## An Eager Task Runs Before create_task Returns

The default factory schedules a task's first step and returns; the coroutine
body does not run until the loop next iterates. An eager factory runs the body
until its first suspension inside `create_task()`, which skips a loop iteration
for coroutines that never suspend.

```python
import asyncio
import sys


async def main():
    loop = asyncio.get_running_loop()
    order = []

    async def record(tag):
        order.append(tag)

    # Default: the body runs after create_task() returns
    task = asyncio.create_task(record("body"))
    order.append("after create_task")
    await task
    assert order == ["after create_task", "body"]

    if sys.version_info < (3, 12):
        return

    # Eager: the body runs during create_task()
    order.clear()
    loop.set_task_factory(asyncio.eager_task_factory)
    task = asyncio.create_task(record("body"))
    order.append("after create_task")
    assert order == ["body", "after create_task"]
    assert task.done()   # never suspended, so it finished eagerly
    await task
    loop.set_task_factory(None)


asyncio.run(main())
```

## Cancellation Is a Request

`Task.cancel()` does not run the cancellation: it arranges for
`CancelledError` to be raised at the task's next step, and the task decides
what happens then. The call itself is O(1), but it forwards
to whatever future the task is suspended on, and that future's `cancel()` is
charged here: a plain future schedules its k done callbacks, and a `gather()`
cancels each of its n children there and then. `shield()`
lets an outer cancellation resolve without reaching the inner work at all.

```python
import asyncio


async def main():
    async def work():
        try:
            await asyncio.sleep(0.05)
            return "finished"
        except asyncio.CancelledError:
            return "caught"

    inner = asyncio.create_task(work())
    outer = asyncio.shield(inner)
    await asyncio.sleep(0)

    # Cancelling the shield does not cancel what it wraps
    outer.cancel()
    try:
        await outer
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("expected the shield to cancel")

    assert await inner == "finished"
    assert not inner.cancelled()

    # CancelledError is not an Exception, so a bare except Exception misses it
    assert issubclass(asyncio.CancelledError, BaseException)
    assert not issubclass(asyncio.CancelledError, Exception)


asyncio.run(main())
```

## asyncio Is for Waiting, Not for Computing

One loop runs on one thread, so a coroutine that computes without awaiting
blocks every other task until it returns. Concurrency here comes from tasks
being *suspended*, which helps when they are waiting on something external and
does nothing when they are not.

Threads are not the answer to that either: CPython's global interpreter lock
lets one thread at a time execute bytecode, so moving pure-Python computation
onto threads leaves the same single core doing the same work. Use
`multiprocessing` or `concurrent.futures.ProcessPoolExecutor` for CPU-bound
work; use `asyncio.to_thread()` to keep the loop responsive across a *blocking*
call, which releases the lock while it waits.

```python
import asyncio
import time


def blocking_call():
    """Stands in for a library that has no async form."""
    time.sleep(0.05)
    return "done"


async def main():
    # One call, to measure what three of them would cost in sequence
    start = time.perf_counter()
    await asyncio.to_thread(blocking_call)
    one = time.perf_counter() - start

    # The same three waits, overlapped on the default thread pool
    start = time.perf_counter()
    results = await asyncio.gather(
        asyncio.to_thread(blocking_call),
        asyncio.to_thread(blocking_call),
        asyncio.to_thread(blocking_call),
    )
    three = time.perf_counter() - start

    assert results == ["done", "done", "done"]
    # Overlapped, not summed: nothing like 3x one call
    assert three < 2 * one


asyncio.run(main())
```

## Version Notes

- **Python 3.11+**: `TaskGroup`, `timeout()`, `timeout_at()`, `Runner`, `Barrier` and `BrokenBarrierError`; `Task.cancelling()` and `Task.uncancel()`; `asyncio.TimeoutError` becomes the builtin `TimeoutError`; `StreamWriter.start_tls()`
- **Python 3.12+**: `eager_task_factory` and `create_eager_task_factory()`; `Handle.get_context()` and `Task.get_context()`; the child watcher API is deprecated
- **Python 3.13+**: `asyncio.EventLoop`; `Queue.shutdown()` and `QueueShutDown`; `as_completed()` supports `async for`, handing back each task or future it was given; `readuntil()` accepts a tuple of separators; `Server.close_clients()` and `Server.abort_clients()`
- **Python 3.14+**: `capture_call_graph()`, `format_call_graph()`, `print_call_graph()`, `future_add_to_awaited_by()` and `future_discard_from_awaited_by()`; `get_event_loop()` raises `RuntimeError` when no loop is running and none was set for the thread, instead of creating one - a loop installed with `set_event_loop()` is still returned; a finished task is dropped from the registry `all_tasks()` scans, where earlier versions keep it while it is referenced; the child watcher API and `get_child_watcher()` are removed; `iscoroutinefunction()`, `get_event_loop_policy()` and `set_event_loop_policy()` are deprecated for removal in 3.16

## Related Documentation

- [Threading Module](threading.md) - The same primitives with real preemption, and the lock that limits them
- [Concurrent.futures Module](concurrent_futures.md) - The pools behind `to_thread()` and `run_in_executor()`
- [Multiprocessing Module](multiprocessing.md) - Where CPU-bound work belongs
- [Queue Module](queue.md) - The blocking queues `asyncio.Queue` mirrors
- [Heapq Module](heapq.md) - The heap under the timer schedule and `PriorityQueue`
- [Socket Module](socket.md) - What the transports are built on
- [Contextvars Module](contextvars.md) - The context a task and a `Handle` capture
