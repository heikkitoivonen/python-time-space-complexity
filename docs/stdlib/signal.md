# signal Module Complexity

The `signal` module installs handlers for operating-system signals and controls timers and
signal masks. Almost every call is a system call or two and an entry in a fixed-size table, so
it is O(1); the calls that return a set of signals build it by scanning every signal number.

A Python handler does not run inside the C-level signal handler. That handler sets a flag, and
the main thread runs the Python handler the next time it checks: between bytecodes, or inside a
C call that checks for signals, as blocking calls do. Two costs follow: a C loop that never
checks delays the handler until it returns, and several deliveries of one signal before the
check produce a single handler call.

`N` is `signal.NSIG`, one more than the highest signal number, fixed per platform. `m` is the
items in a mask or set argument, duplicates included. The blocking calls - `pause()`, `sigwait()`,
`sigwaitinfo()` and `sigtimedwait()` - are priced by their own work; the wait itself lasts until
a signal arrives or the timeout expires. A handler's own cost is not included in any bound.

## Complexity Reference

### Handlers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `signal.signal(signalnum, handler)` | O(1) | O(1) | Main thread of the main interpreter only, or `ValueError`; returns the previous handler. On Windows only `SIGABRT`, `SIGBREAK`, `SIGFPE`, `SIGILL`, `SIGINT`, `SIGSEGV` and `SIGTERM` are accepted |
| `signal.getsignal(signalnum)` | O(1) | O(1) | The handler `signal()` would return: a callable, `SIG_DFL` or `SIG_IGN`, or `None` for one not installed from Python |
| `signal.default_int_handler(signalnum, frame)` | O(1) | O(1) | The handler Python installs for `SIGINT`; raises `KeyboardInterrupt` |
| `signal.set_wakeup_fd(fd, *, warn_on_full_buffer=True)` | O(1) | O(1) | Main thread only; `fd` must be non-blocking; each handled delivery writes one byte to it and still calls the handler; returns the previous fd, and -1 disables |
| `signal.siginterrupt(signalnum, flag)` | O(1) | O(1) | Unix; with `flag` false a restartable system call, such as a read from a pipe, restarts in the kernel, so the handler waits until the call completes |

### Sending Signals

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `signal.raise_signal(signum)` | O(1) | O(1) | From the main thread, for an unblocked signal, the handler has run before the next statement |
| `signal.pthread_kill(thread_id, signalnum)` | O(1) | O(1) | Unix; targets one thread, but a Python handler still runs in the main thread |
| `signal.pidfd_send_signal(pidfd, sig, siginfo=None, flags=0)` | O(1) | O(1) | Linux 5.1+; `pidfd` comes from `os.pidfd_open()` |

### Timers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `signal.alarm(time)` | O(1) | O(1) | Unix; whole seconds of wall-clock time, then `SIGALRM`; returns the seconds left on the previous alarm, and 0 cancels |
| `signal.setitimer(which, seconds, interval=0.0)` | O(1) | O(1) | Unix; fractional seconds, repeating every `interval` if non-zero; returns the previous `(delay, interval)`, and 0 cancels |
| `signal.getitimer(which)` | O(1) | O(1) | Unix; the current `(delay, interval)` |
| `signal.ItimerError` | O(1) | O(1) | `OSError` subclass raised by `setitimer()` and `getitimer()` |

### Masks and Waiting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `signal.pthread_sigmask(how, mask)` | O(m + N) | O(N) | Unix; changes the calling thread's mask only; reads every item of `mask`, then returns the previous mask as a new set; called from the main thread, a pending signal it unblocks has had its handler run by the time it returns |
| `signal.sigpending()` | O(N) | O(N) | Unix; blocked signals waiting for delivery, as a new set |
| `signal.sigwait(sigset)` | O(m) | O(1) | Unix; waits for a blocked signal and consumes it, so its handler never runs |
| `signal.sigwaitinfo(sigset)` | O(m) | O(1) | Unix except macOS; as `sigwait()`, returning a `struct_siginfo` |
| `signal.sigtimedwait(sigset, timeout)` | O(m) | O(1) | Unix except macOS; as `sigwaitinfo()`, or `None` once `timeout` seconds pass; a timeout of 0 polls |
| `signal.pause()` | O(1) | O(1) | Unix; sleeps until a signal with a handler arrives, and returns after the handler has run |
| `signal.valid_signals()` | O(N) | O(N) | A new set on every call: `Signals` members where one exists, plain ints for the rest |
| `signal.strsignal(signalnum)` | O(1) | O(1) | The system's description, or `None`; `ValueError` for a number outside 1 to `NSIG - 1` |
| `signal.struct_siginfo` | O(1) | O(1) | `si_signo`, `si_code`, `si_errno`, `si_pid`, `si_uid`, `si_status`, `si_band` |

### Constants and Enums

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `signal.Signals`, `signal.Handlers`, `signal.Sigmasks` | O(1) | O(1) | `IntEnum` classes for signal numbers, `SIG_DFL`/`SIG_IGN`, and the `pthread_sigmask()` operations (Unix) |
| `signal.SIG_DFL`, `signal.SIG_IGN` | O(1) | O(1) | The default action, and ignoring the signal; Python starts with `SIGPIPE` ignored |
| `signal.SIGINT`, `signal.SIGTERM`, `signal.SIGALRM`, `signal.SIGUSR1`, other `SIG*` names | O(1) | O(1) | `Signals` members; the set depends on the platform, and `SIGBREAK` is Windows-only |
| `signal.CTRL_C_EVENT`, `signal.CTRL_BREAK_EVENT` | O(1) | O(1) | Windows; for `os.kill()` to a console process group |
| `signal.NSIG` | O(1) | O(1) | One more than the highest signal number: the `N` above |
| `signal.ITIMER_REAL`, `signal.ITIMER_VIRTUAL`, `signal.ITIMER_PROF` | O(1) | O(1) | Wall-clock time (`SIGALRM`), user CPU time (`SIGVTALRM`), user plus system CPU time (`SIGPROF`) |
| `signal.SIG_BLOCK`, `signal.SIG_UNBLOCK`, `signal.SIG_SETMASK` | O(1) | O(1) | `Sigmasks` members, the `how` of `pthread_sigmask()` |

## Handling Signals

### Installing a Handler

Installing a handler is one table entry and one system call. The call returns the handler it
replaced, so it can be put back.

```python
import signal

received = []

def handler(signum, frame):
    received.append(signal.Signals(signum).name)

previous = signal.signal(signal.SIGUSR1, handler)  # O(1)
assert previous is signal.SIG_DFL
assert signal.getsignal(signal.SIGUSR1) is handler  # O(1)

signal.raise_signal(signal.SIGUSR1)  # O(1); the handler has run by the next line
assert received == ['SIGUSR1']

signal.signal(signal.SIGUSR1, previous)  # O(1) - restore
assert signal.getsignal(signal.SIGINT) is signal.default_int_handler
assert signal.getsignal(signal.SIGPIPE) is signal.SIG_IGN
```

### When a Handler Runs

The Python handler runs in the main thread, the next time it checks. A C loop that runs no
Python code and does not check for signals, such as `sum()` over a C iterator, runs to
completion first, so no handler, and no timeout built on one, can interrupt it. Blocking calls
such as `time.sleep()` and I/O do check. Here a timer fires a millisecond into a `sum()` over
twenty million items, and the handler sees the counter already exhausted.

```python
import itertools
import signal

counter = itertools.count()
seen = []
signal.signal(signal.SIGVTALRM, lambda signum, frame: seen.append(repr(counter)))

signal.setitimer(signal.ITIMER_VIRTUAL, 0.001)  # O(1) - after 1 ms of CPU time
total = sum(itertools.islice(counter, 20_000_000))  # one C call
assert seen == ['count(20000000)']  # the handler ran only after sum() returned

signal.signal(signal.SIGVTALRM, signal.SIG_DFL)
```

A signal sent from another thread still runs its handler in the main thread, and only the main
thread may install one.

```python
import os
import signal
import threading

ran_in = []
signal.signal(signal.SIGUSR1, lambda signum, frame: ran_in.append(threading.current_thread()))

sender = threading.Thread(target=os.kill, args=(os.getpid(), signal.SIGUSR1))
sender.start()
sender.join()
assert ran_in == [threading.main_thread()]

errors = []

def install():
    try:
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)
    except ValueError as error:
        errors.append(str(error))

worker = threading.Thread(target=install)
worker.start()
worker.join()
assert errors and 'main thread' in errors[0]

signal.signal(signal.SIGUSR1, signal.SIG_DFL)
```

### Several Deliveries, One Call

A handler is not a counter. Deliveries of one signal that arrive before its handler runs
collapse into one call - even for real-time signals, which the kernel queues. To count events,
have the sender use a pipe or socket instead of signals.

```python
import os
import signal

calls = []
signal.signal(signal.SIGUSR1, lambda signum, frame: calls.append(signum))

signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})  # O(m + N)
for _ in range(5):
    os.kill(os.getpid(), signal.SIGUSR1)
assert signal.sigpending() == {signal.SIGUSR1}  # O(N)

signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGUSR1})  # the handler runs here
assert calls == [signal.SIGUSR1]  # five sends, one call

signal.signal(signal.SIGUSR1, signal.SIG_DFL)
```

## Timeouts

`alarm()` counts whole seconds; `setitimer()` takes fractions and can repeat. Either delivers a
signal whose handler raises, which ends a blocking call such as `time.sleep()` - but not a C
loop that never checks for signals, which finishes first (see
[When a Handler Runs](#when-a-handler-runs)).

```python
import signal
import time

def with_timeout(func, seconds):
    def expire(signum, frame):
        raise TimeoutError(f'gave up after {seconds}s')

    previous = signal.signal(signal.SIGALRM, expire)  # O(1)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)  # O(1)
        return func()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)  # O(1) - cancel
        signal.signal(signal.SIGALRM, previous)

assert with_timeout(lambda: 'quick', 1.0) == 'quick'

try:
    with_timeout(lambda: time.sleep(10), 0.05)
except TimeoutError as error:
    assert '0.05' in str(error)
else:
    raise AssertionError('the sleep was not interrupted')

assert signal.alarm(30) == 0  # O(1) - no alarm was pending
assert 29 <= signal.alarm(0) <= 30  # cancel; returns the seconds that were left
```

## Waiting for a Signal

`pause()` returns only once a signal arrives after it has started. A signal that lands between
arming it and calling `pause()` has already been handled, and the wait lasts until another one
comes; a repeating timer, as here, is one way to avoid depending on that window.

```python
import signal

ticks = []
signal.signal(signal.SIGALRM, lambda signum, frame: ticks.append(signum))
signal.setitimer(signal.ITIMER_REAL, 0.01, 0.01)  # O(1) - every 10 ms

signal.pause()  # O(1) - returns after the handler has run
assert ticks

signal.setitimer(signal.ITIMER_REAL, 0)
signal.signal(signal.SIGALRM, signal.SIG_DFL)
```

The race-free form blocks the signal first, so it stays pending until it is waited for.
`sigwait()` and its relatives consume it: the handler is never called.

```python
import os
import signal

calls = []
signal.signal(signal.SIGUSR1, lambda signum, frame: calls.append(signum))
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})

assert signal.sigtimedwait({signal.SIGUSR1}, 0) is None  # O(m) - nothing pending

os.kill(os.getpid(), signal.SIGUSR1)
info = signal.sigtimedwait({signal.SIGUSR1}, 1.0)  # O(m)
assert info.si_signo == signal.SIGUSR1 and info.si_pid == os.getpid()

os.kill(os.getpid(), signal.SIGUSR1)
assert signal.sigwait({signal.SIGUSR1}) == signal.SIGUSR1  # O(m)

signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGUSR1})
assert calls == []  # both deliveries were consumed by the waits
signal.signal(signal.SIGUSR1, signal.SIG_DFL)
```

## Deferring Signals Over a Critical Section

Blocking a signal with `pthread_sigmask()` holds its delivery until it is unblocked; called from
the main thread, the handler then runs before `pthread_sigmask()` returns. The mask belongs to
the calling thread, and a signal sent to the process can reach any thread that does not block
it, so block it before starting other threads, which inherit the mask.

`siginterrupt(signalnum, False)` is not a way to defer a handler. It makes a restartable system
call, such as a read from a pipe, restart in the kernel instead of returning, so the handler
waits for that call to finish; elsewhere the handler runs as it would anyway.

```python
import os
import signal

calls = []
signal.signal(signal.SIGUSR1, lambda signum, frame: calls.append(signum))

previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})  # O(m + N)
os.kill(os.getpid(), signal.SIGUSR1)
assert calls == []  # held while blocked
signal.pthread_sigmask(signal.SIG_SETMASK, previous)
assert calls == [signal.SIGUSR1]

signal.signal(signal.SIGUSR1, signal.SIG_DFL)
```

## Waking an Event Loop

`set_wakeup_fd()` makes every handled delivery also write the signal number, as one byte, to a
non-blocking descriptor, so a `select()` or `poll()` loop wakes up. The handler still runs. The
reader has to drain the descriptor: once its buffer is full, further bytes are dropped.
`asyncio`'s `loop.add_signal_handler()` is built on it.

```python
import os
import selectors
import signal
import socket

receiver, sender = socket.socketpair()
receiver.setblocking(False)
sender.setblocking(False)

handled = []
signal.signal(signal.SIGUSR1, lambda signum, frame: handled.append(signum))
previous = signal.set_wakeup_fd(sender.fileno())  # O(1)
assert previous == -1

selector = selectors.DefaultSelector()
selector.register(receiver, selectors.EVENT_READ)
signal.raise_signal(signal.SIGUSR1)

assert selector.select(timeout=1.0)  # woken by the byte
assert receiver.recv(16) == bytes([signal.SIGUSR1])  # drain it
assert handled == [signal.SIGUSR1]  # and the handler ran as well

signal.set_wakeup_fd(previous)
signal.signal(signal.SIGUSR1, signal.SIG_DFL)
selector.close()
receiver.close()
sender.close()

read_end, write_end = os.pipe()  # blocking by default
try:
    signal.set_wakeup_fd(write_end)
except ValueError as error:
    assert 'non-blocking' in str(error)
else:
    raise AssertionError('a blocking descriptor was accepted')
os.close(read_end)
os.close(write_end)
```

## Inspecting Signals

`valid_signals()` and `sigpending()` build a new set by scanning all `N` signal numbers, so call
them once rather than in a loop. `strsignal()` and the enums are lookups.

```python
import signal

valid = signal.valid_signals()  # O(N)
assert signal.SIGINT in valid
assert max(valid) < signal.NSIG  # O(N)
assert signal.valid_signals() is not valid  # a new set each call

assert signal.Signals(2) is signal.SIGINT  # O(1)
assert signal.SIGINT.name == 'SIGINT'
assert isinstance(signal.strsignal(signal.SIGINT), str)  # O(1)

try:
    signal.strsignal(0)
except ValueError as error:
    assert 'out of range' in str(error)
else:
    raise AssertionError('signal 0 has a description')
```

## Common Patterns

### Graceful Shutdown

A handler that sets a flag, and a loop that checks it, keeps the handler to O(1) and leaves the
clean-up to ordinary code.

```python
import os
import signal

class Worker:
    def __init__(self):
        self.stopping = False
        self.done = 0
        signal.signal(signal.SIGTERM, self.request_stop)  # O(1)

    def request_stop(self, signum, frame):
        self.stopping = True  # O(1) - no clean-up in the handler

    def run(self):
        while not self.stopping:
            self.done += 1
            if self.done == 3:
                os.kill(os.getpid(), signal.SIGTERM)  # stands in for an outside sender
        return self.done

assert Worker().run() == 3
signal.signal(signal.SIGTERM, signal.SIG_DFL)
```

## Performance Best Practices

✅ **Do**:

- Keep handlers to setting a flag; they run between arbitrary bytecodes of the main thread,
  which may be holding a lock the handler would need
- Block a signal with `pthread_sigmask()` around code that must not see its handler, in every
  thread that could receive it, and put the previous mask back
- Use `sigwait()` or `sigtimedwait()` on a blocked signal when a thread should wait for it
- Use `set_wakeup_fd()`, or `loop.add_signal_handler()` in `asyncio`, to wake a loop that is
  waiting on descriptors
- Restore the handler `signal()` returned when a handler is only needed for a while

❌ **Avoid**:

- Relying on a signal-based timeout to stop a long C loop that runs no Python code and never
  checks for signals - its handler runs only when the loop returns
- Counting signals by counting handler calls - deliveries before the handler runs merge
- `siginterrupt(signalnum, False)` - it does not defer a handler, only delays it until a restartable
  system call completes
- `valid_signals()` or `sigpending()` in a hot loop - each call scans all `N` signal numbers and
  builds a new set
- `pause()` after arming a one-shot timer - a signal that arrives first leaves it waiting for the
  next one

## Version Notes

- **All Python 3**: Python handlers run in the main thread of the main interpreter, between
  bytecodes; only that thread may install them

## Related Modules

- **[asyncio](asyncio.md)** - `loop.add_signal_handler()` runs a callback on the event loop
- **[threading](threading.md)** - Python handlers run only in the main thread; use an `Event`
  between threads
- **[os](os.md)** - `os.kill()` sends a signal to a process
- **[selectors](selectors.md)** - the loop a wakeup fd wakes
- **[faulthandler](faulthandler.md)** - reports `SIGSEGV` and other fatal signals, which a Python
  handler cannot recover from
- **[subprocess](subprocess.md)** - `send_signal()`, `terminate()` and `kill()` on a child
