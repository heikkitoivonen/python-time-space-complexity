# faulthandler Module Complexity

The `faulthandler` module writes Python tracebacks straight to a file descriptor: on demand, when
the interpreter receives a fatal signal (`SIGSEGV`, `SIGFPE`, `SIGABRT`, `SIGBUS`, `SIGILL`),
after a timeout, or on a user signal. It is the tool for hangs and hard crashes, where a normal
exception traceback never gets a chance to print. A dump is written a line at a time as it walks
the stacks, so it holds nothing but the line in hand.

The bounds are for the default build, with the GIL. `t` is the Python threads a dump covers -
every thread in the interpreter, or only the calling one with `all_threads=False` - and `d` is
the frames dumped per thread. A dump stops after 100 threads and after 100 frames per thread, and
cuts each filename and function name at 500 characters, so every frame line is O(1) and `t·d`
never exceeds 10,000 lines. `m` is the entries in `sys.modules`, which only the crash path walks.

## Complexity Reference

### Fatal-signal handler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `faulthandler.enable(file=sys.stderr, all_threads=True, c_stack=True)` | O(1) | O(1) | Installs the fatal-signal handlers; `c_stack` is Python 3.14+ |
| `faulthandler.disable()` | O(1) | O(1) | Restores the previous handlers; returns whether it was enabled |
| `faulthandler.is_enabled()` | O(1) | O(1) | Reads a flag |
| A fatal signal while enabled | O(t·d + m) | O(1) | The dump, then a scan of `sys.modules` for extension modules to name; the previous handler then runs, which by default ends the process |

### Dumping on demand

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `faulthandler.dump_traceback(file=sys.stderr, all_threads=True)` | O(t·d) | O(1) | One line per frame, written as it is walked |
| `faulthandler.dump_c_stack(file=sys.stderr)` | O(1) | O(1) | Python 3.14+; at most 32 C frames |

### Watchdog timer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `faulthandler.dump_traceback_later(timeout, repeat=False, file=sys.stderr, exit=False)` | O(1) | O(1) | Starts one watchdog thread, replacing any armed before; each expiry dumps every thread, O(t·d) |
| `faulthandler.cancel_dump_traceback_later()` | O(1) | O(1) | Stops the watchdog thread and waits for it to finish |

### User signals

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `faulthandler.register(signum, file=sys.stderr, all_threads=True, chain=False)` | O(1) | O(1) | Not on Windows; each delivery of `signum` dumps, O(t·d), and the process carries on |
| `faulthandler.unregister(signum)` | O(1) | O(1) | Not on Windows; returns whether `signum` was registered |

## Enabling the Handler

Enabling installs signal handlers: no trace hook, no thread, no work until a fatal signal
arrives. That is why it is safe to leave on in production. The `-X faulthandler`
option and the `PYTHONFAULTHANDLER` environment variable enable it at startup.

```python
import faulthandler
import subprocess
import sys

faulthandler.enable()  # O(1) - installs the fatal-signal handlers
assert faulthandler.is_enabled()
assert faulthandler.disable() is True   # O(1)
assert faulthandler.disable() is False  # already off

# The same without touching code
result = subprocess.run(
    [sys.executable, '-X', 'faulthandler', '-c',
     'import faulthandler; print(faulthandler.is_enabled())'],
    capture_output=True, text=True, check=True,
)
assert result.stdout.strip() == 'True'
```

!!! warning "Not a substitute for exception handling"
    `faulthandler` reports the interpreter state at the moment of a fault; it does not recover
    from it. Once the dump is written the previous handler runs, and by default the process dies.

## What a Dump Costs

A dump prints one line per frame and stops at 100 frames and 100 threads, so its cost follows
the stacks up to those limits and no further. `all_threads=False` restricts it to the calling
thread, O(d).

```python
import faulthandler
import tempfile

def recurse(n, out):
    if n == 0:
        faulthandler.dump_traceback(out, all_threads=False)  # O(d)
    else:
        recurse(n - 1, out)

with tempfile.TemporaryFile() as out:
    recurse(10, out)
    out.seek(0)
    shallow = out.read().decode().count('File "')

    out.seek(0)
    out.truncate()
    recurse(500, out)
    out.seek(0)
    deep = out.read().decode().count('File "')

assert shallow == 12   # module, recurse() eleven times
assert deep == 100     # the rest of the stack is not dumped
```

## Diagnosing a Hang

`dump_traceback_later()` starts a watchdog thread: if the timeout elapses before it is cancelled,
every thread's stack is dumped, and `exit=True` then ends the process with status 1. Arming it
is O(1); only an expiry pays for a dump.

```python
import faulthandler
import tempfile
import time

with tempfile.TemporaryFile() as log:
    # Dump all thread stacks if the work below takes over 30 seconds - O(1) to arm
    faulthandler.dump_traceback_later(30, file=log)
    try:
        total = sum(range(1_000))
    finally:
        faulthandler.cancel_dump_traceback_later()  # O(1)
    log.seek(0)
    assert log.read() == b''  # finished in time, so nothing was dumped

    # A timeout that does expire writes a header and every thread's stack
    faulthandler.dump_traceback_later(0.01, file=log)
    deadline = time.monotonic() + 10
    while log.tell() == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
        log.seek(0, 2)
    faulthandler.cancel_dump_traceback_later()
    log.seek(0)
    assert log.read().startswith(b'Timeout (0:00:00.010000)!')
```

## Dumping on a User Signal

`register()` keeps a handler installed for a signal of your choice, so an operator can ask a
running process for its stacks without stopping it. It is not available on Windows.

```python
import faulthandler
import os
import signal
import tempfile

with tempfile.TemporaryFile() as log:
    faulthandler.register(signal.SIGUSR1, file=log, all_threads=False)  # O(1)
    os.kill(os.getpid(), signal.SIGUSR1)  # dumps, O(d), and the process carries on
    assert faulthandler.unregister(signal.SIGUSR1) is True   # O(1)
    assert faulthandler.unregister(signal.SIGUSR1) is False  # nothing left to remove
    log.seek(0)
    assert log.read().startswith(b'Stack (most recent call first):')
```

## Performance Best Practices

✅ **Do**:

- Leave the handler enabled in long-running services: it costs nothing until a fatal signal
- Arm `dump_traceback_later()` around work that might hang, and cancel it when the work ends
- Pass `all_threads=False` when only the calling thread matters: O(d) instead of O(t·d)
- Keep the `file` you pass open for as long as the handler, timer or signal registration lasts:
  the module holds its file descriptor, not a path

❌ **Avoid**:

- Relying on a dump for deep recursion or a crowded process: it shows the innermost 100 frames of
  at most 100 threads
- Registering a signal the application already uses without `chain=True`: the dump replaces its
  handler

## Version Notes

- **Python 3.3+**: Module introduced
- **Python 3.5+**: `file` may be a file descriptor as well as a file object
- **Python 3.7+**: `dump_traceback_later()` is always available
- **Python 3.14+**: Added `dump_c_stack()` and `enable(c_stack=True)`, which adds the C stack to
  a fatal-signal dump

## Related Modules

- **[traceback](traceback.md)** - formatting and printing tracebacks from Python code
- **[signal](signal.md)** - Python-level signal handlers, and the signal numbers `register()` takes
- **[threading](threading.md)** - the threads a dump walks
- **[sys](sys.md)** - `sys.modules`, walked on the crash path
