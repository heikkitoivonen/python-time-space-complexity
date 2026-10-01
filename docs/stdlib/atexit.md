# atexit Module Complexity

The `atexit` module keeps one registry of handlers and calls them, newest
first, when the interpreter shuts down normally. Each entry holds the function and the
arguments it was registered with, and keeps them alive until the handlers run.

`n` is the handlers currently registered. On Python 3.13 and earlier it also counts every
handler unregistered since the handlers last ran, because an unregistered handler's slot is not
reclaimed until then. `k` is the handlers one `unregister()` call removes. The arguments stored
with a handler and one `==` comparison are priced at O(1), and the handlers' own running time is
not part of any bound.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `atexit.register(func, *args, **kwargs)` | O(n) on Python 3.14+; O(1) before, when `realloc()` grows the array in place | O(1) per handler | Returns `func`, so it works as a decorator; raises `TypeError` at once if `func` is not callable |
| `atexit.unregister(func)` | O(n·(k + 1)) on Python 3.14+, O(n) before | O(1) | Compares `func` with every handler using `==` and removes all that match; does nothing if none does |

### Running the handlers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Running the handlers at exit | O(n) | O(n) on Python 3.14+, O(1) before | Newest first. A handler that raises is reported to `sys.unraisablehook`, and the rest still run |

!!! warning "When handlers run"
    Handlers run when the interpreter shuts down normally: the main module finishes,
    `sys.exit()` is called, or an exception nobody catches ends the program. They do not run
    after `os._exit()`, a Python fatal error, or a signal Python does not handle, such as
    `SIGKILL`.

## Registering Handlers

The most recently registered handler runs first, so a module that registers its handler at
import time is cleaned up after the modules imported later. Extra arguments to `register()` are
stored and passed to the handler at exit.

```python
import subprocess
import sys

program = '''
import atexit

atexit.register(print, "registered first")

@atexit.register
def registered_last():
    print("registered last")

assert callable(registered_last)  # register() returned the function
'''

result = subprocess.run(
    [sys.executable, "-c", program], capture_output=True, text=True, check=True
)
assert result.stdout.splitlines() == ["registered last", "registered first"]
```

## Unregistering Handlers

`unregister()` compares its argument with every registered handler, so even a call that
matches nothing costs O(n). Equality, not identity, decides a match: each `obj.close`
is a new bound-method object, and it still unregisters a handler registered as `obj.close`.

```python
import subprocess
import sys

program = '''
import atexit

class Resource:
    def close(self):
        print("closed")

resource = Resource()
atexit.register(resource.close)
atexit.register(resource.close)

assert resource.close is not resource.close  # a new bound method each time
atexit.unregister(resource.close)  # O(n); removes both, because they compare equal
'''

result = subprocess.run(
    [sys.executable, "-c", program], capture_output=True, text=True, check=True
)
assert result.stdout == ""
```

### A Handler Keeps Its Object Alive

The registry holds a strong reference to each handler and its arguments. Registering a bound
method therefore keeps its object alive until exit, however long ago the rest of the program
let it go. `weakref.finalize()` runs a cleanup at exit too, but holds its object weakly.

```python
import atexit
import gc
import weakref

class Resource:
    def close(self):
        pass

resource = Resource()
alive = weakref.ref(resource)
atexit.register(resource.close)  # holds resource through the bound method
del resource
gc.collect()
assert alive() is not None

atexit.unregister(alive().close)  # O(n)
gc.collect()
assert alive() is None

closed = []
resource = Resource()
weakref.finalize(resource, closed.append, "closed")  # no reference to resource
del resource
gc.collect()
assert closed == ["closed"]
```

## Exceptions and Abrupt Exits

A handler that raises does not stop the others or change the exit status: the exception is
reported through `sys.unraisablehook`, which prints it to stderr by default. `os._exit()` skips
the handlers entirely.

```python
import subprocess
import sys

program = '''
import atexit

atexit.register(print, "still ran")

@atexit.register
def broken():
    raise ValueError("broken handler")
'''

result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True)
assert result.returncode == 0
assert result.stdout == "still ran\n"
assert "ValueError: broken handler" in result.stderr

skipped = subprocess.run(
    [sys.executable, "-c", program + "import os; os._exit(0)"],
    capture_output=True,
    text=True,
)
assert skipped.returncode == 0
assert skipped.stdout == ""
```

## Common Patterns

### One Handler for Many Resources

Registering a handler per object makes each `unregister()` O(n), and each `register()` too on
Python 3.14+; before 3.14 an unregistered handler's slot also stays until exit. One handler
over a set of open objects keeps the registry at one entry, and forgetting an object is O(1).

```python
import atexit

class Connection:
    live = set()

    def __init__(self):
        Connection.live.add(self)      # O(1)

    def close(self):
        Connection.live.discard(self)  # O(1)

@atexit.register  # registered once
def close_all():
    for connection in list(Connection.live):
        connection.close()

first, second = Connection(), Connection()
first.close()
assert Connection.live == {second}

close_all()  # what shutdown does
assert Connection.live == set()
```

## Performance Best Practices

✅ **Do**:

- Register one handler that closes a collection of objects, rather than one handler per object
- Use `weakref.finalize()` for per-object cleanup, so the registry does not keep the object
  alive
- Install a `signal` handler that calls `sys.exit()` if handlers must run on `SIGTERM`

❌ **Avoid**:

- Registering and unregistering in a loop - each `unregister()` is O(n), each `register()`
  too on 3.14+, and before 3.14 every unregistered slot stays until exit
- Registering a bound method of a short-lived object - the object lives until exit
- Relying on handlers for work that must survive `os._exit()` or `SIGKILL`

## Version Notes

- **Python 3.14+**: `register()` is O(n); `unregister()` is O(n·(k + 1)) and reclaims the
  slot; running the handlers takes an O(n) copy of the registry first

## Related Modules

- **[sys](sys.md)** - `sys.exit()` runs the handlers; `sys.unraisablehook` receives their
  exceptions
- **[signal](signal.md)** - a handled signal that calls `sys.exit()` runs the handlers; an
  unhandled one does not
- **[weakref](weakref.md)** - `finalize()` for cleanup that does not keep its object alive
