# faulthandler Module

The `faulthandler` module dumps Python tracebacks when the interpreter crashes
on a fatal signal (`SIGSEGV`, `SIGFPE`, `SIGABRT`, `SIGBUS`, `SIGILL`), on a
timeout, or on a user signal. It is the tool for diagnosing hangs and hard
crashes, where a normal exception traceback never gets a chance to print.

The handlers write directly to a file descriptor using pre-allocated buffers,
so dumping is async-signal-safe and allocates no memory.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enable(file=sys.stderr, all_threads=True)` | O(1) | O(1) | Installs signal handlers |
| `disable()` | O(1) | O(1) | Removes handlers |
| `is_enabled()` | O(1) | O(1) | Flag check |
| `dump_traceback(file, all_threads=True)` | O(t*d) | O(1) | t = threads, d = stack depth |
| `dump_traceback_later(timeout, repeat=False)` | O(1) | O(1) | Starts a watchdog thread |
| `cancel_dump_traceback_later()` | O(1) | O(1) | Stops the watchdog |
| `register(signum, file, all_threads=True)` | O(1) | O(1) | Handler for a user signal |
| `unregister(signum)` | O(1) | O(1) | Removes that handler |

Dump cost is proportional to what is printed: one line per frame, across the
threads selected. With `all_threads=False` it is O(d) for the current thread.

## Enabling the Handler

```python
import faulthandler

# O(1) - installs handlers for the fatal signals
faulthandler.enable()

# Equivalent, without touching code:
#   python -X faulthandler script.py
#   PYTHONFAULTHANDLER=1 python script.py
```

## Diagnosing a Hang

`dump_traceback_later()` starts a watchdog: if the timeout elapses before it is
cancelled, every thread's stack is dumped. This is how you find out where a
process is stuck.

```python
import faulthandler

# Dump all thread stacks if the work below takes over 30 seconds - O(1) to arm
faulthandler.dump_traceback_later(30, exit=True)
try:
    do_slow_work()
finally:
    faulthandler.cancel_dump_traceback_later()   # O(1)
```

## Dumping on Demand

```python
import faulthandler
import signal

# Send SIGUSR1 to the process to print all stacks without stopping it
faulthandler.register(signal.SIGUSR1)   # O(1)

# Or dump immediately - O(threads * depth)
faulthandler.dump_traceback()
```

!!! warning "Not a substitute for exception handling"
    `faulthandler` reports the interpreter state at the moment of a fault; it
    does not recover from it. After a fatal signal the process still dies.

!!! tip "Cheap to leave on"
    Enabling the handler costs one signal-handler installation and nothing per
    operation afterwards, so there is no steady-state overhead in production.

## Version Notes

- **Python 3.3+**: module introduced
- **Python 3.5+**: handlers are installed with `SA_ONSTACK` where available, so
  stack-overflow crashes can still be dumped
- **Python 3.6+**: `dump_traceback_later()` is available on all platforms with
  threads
- **All versions**: dumping allocates no memory and is signal-safe

## Related Documentation

- [Traceback Module](traceback.md)
- [Signal Module](signal.md)
- [Threading Module](threading.md)
- [Sys Module](sys.md)
