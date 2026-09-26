# contextlib Module Complexity

The `contextlib` module builds context managers: from a generator function, from a stack of
callbacks assembled at run time, or ready-made for one job such as suppressing an exception or
redirecting output. What it adds is a constant amount of work per entry, exit and registered
callback; the work of setup and cleanup is whatever the code you hand it does.

`k` is the callbacks registered on an `ExitStack` or `AsyncExitStack`, and `g` is the exceptions
in an exception group, nested groups included. The work a callback, an `__enter__` or `__exit__`
method, or a generator's code before and after its `yield` does of its own is priced O(1), and so
is matching an exception against the few types given to `suppress()` and each `os.getcwd()` or
`os.chdir()` call `chdir()` makes: the rows price what `contextlib` adds around that work.

## Complexity Reference

### contextmanager and asynccontextmanager

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `@contextlib.contextmanager`, `@contextlib.asynccontextmanager` | O(1) | O(1) | Wraps the generator function; nothing runs yet |
| Calling the decorated function | O(1) | O(1) | Builds a new generator and its wrapper; the function body does not start |
| Entering the `with` or `async with` | O(1) | O(1) | Runs the generator to its `yield` |
| Leaving the `with` or `async with` | O(1) | O(1) | Resumes the generator, throwing in the exception if there is one. Each object is single use: a second `with` on it raises |
| Using the returned object as a decorator | O(1) per call | O(1) | Builds a fresh generator for every call of the decorated function |

### ExitStack

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `contextlib.ExitStack()` | O(1) | O(1) | An empty stack of callbacks |
| `ExitStack.enter_context(cm)` | O(1) | O(1) | Calls `cm.__enter__()`, then pushes its `__exit__`; returns what `__enter__` returned |
| `ExitStack.push(exit)` | O(1) | O(1) | Pushes an `__exit__`-style callable, or the `__exit__` of an object that has one; either can suppress the exception |
| `ExitStack.callback(callback, /, *args, **kwds)` | O(1) | O(1) | Pushes a call that ignores the exception and cannot suppress it |
| `ExitStack.pop_all()` | O(1) | O(1) | Moves the whole stack to a new `ExitStack` without copying it and leaves this one empty |
| `ExitStack.close()`, leaving the `with` | O(k) | O(1) | Calls every callback once, last pushed first, and empties the stack; a callback that suppresses hides the exception from the ones below it. Space excludes exceptions the callbacks raise |
| Unwinding when every exit raises while handling the exception before it | O(k²) | O(k) | A `@contextmanager` whose cleanup raises does this: each raise walks the context chain of the exception it is handling, which grows by one per exit |

### AsyncExitStack

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `contextlib.AsyncExitStack()` | O(1) | O(1) | Takes synchronous and asynchronous callbacks on one stack |
| `AsyncExitStack.enter_async_context(cm)` | O(1) | O(1) | Awaits `cm.__aenter__()`, then pushes its `__aexit__` |
| `AsyncExitStack.push_async_exit(exit)` | O(1) | O(1) | As `push()`, for an `__aexit__`-style coroutine function or an object with `__aexit__` |
| `AsyncExitStack.push_async_callback(callback, /, *args, **kwds)` | O(1) | O(1) | As `callback()`, awaiting the coroutine it returns |
| `AsyncExitStack.enter_context(cm)`, `push(exit)`, `callback(...)`, `pop_all()` | O(1) | O(1) | The synchronous forms, as on `ExitStack` |
| `AsyncExitStack.aclose()`, leaving the `async with` | O(k) | O(1) | As `ExitStack.close()`, awaiting the asynchronous callbacks; the same O(k²) when every exit raises while handling the exception before it |

### Single-purpose context managers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `contextlib.closing(thing)` | O(1) | O(1) | Calls `thing.close()` once on the way out, whether or not the block raised |
| `contextlib.aclosing(thing)` | O(1) | O(1) | Python 3.10+; awaits `thing.aclose()` once on the way out |
| `contextlib.nullcontext(enter_result=None)` | O(1) | O(1) | Returns `enter_result` and does nothing else; usable with `async with` from Python 3.10 |
| `contextlib.suppress(*exceptions)` | O(1) | O(1) | An exception matching one of the types ends the block and execution continues after it |
| Leaving `suppress` with an exception group | O(g) | O(g) | Python 3.12+: the group is split, the matching exceptions are dropped and the rest re-raised as a new group |
| `contextlib.redirect_stdout(new_target)`, `contextlib.redirect_stderr(new_target)` | O(1) | O(1) | Replaces `sys.stdout` or `sys.stderr` for the block, for every thread in the process; the same object can be nested in itself |
| `contextlib.chdir(path)` | O(1) | O(1) | Python 3.11+; changes the working directory of the whole process for the block; the same object can be nested in itself |

### Base classes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `contextlib.ContextDecorator`, `contextlib.AsyncContextDecorator` | O(1) per call | O(1) | A subclass instance used as a decorator wraps each call in `with` on that same instance. `AsyncContextDecorator` is Python 3.10+ |
| `contextlib.AbstractContextManager`, `contextlib.AbstractAsyncContextManager` | O(1) | O(1) | `__enter__` and `__aenter__` return `self`; an `isinstance()` check looks for the methods through the class's MRO the first time and is cached per class after that |

## Generator-Based Context Managers

`@contextmanager` turns a generator into a context manager. The decorator itself does no work.
Every call of the decorated function builds a new generator, which runs to its `yield` on entry
and past it on exit, so a generator-based context manager is single use: build a new one for each
`with`.

```python
from contextlib import contextmanager

events = []

@contextmanager  # O(1) - wraps the function
def tag(name):
    events.append(f"open {name}")
    try:
        yield name
    finally:
        events.append(f"close {name}")

manager = tag("a")  # O(1) - builds a generator; the body has not started
assert events == []

with manager as value:  # O(1) - runs to the yield
    assert value == "a"
    assert events == ["open a"]
assert events == ["open a", "close a"]  # O(1) - resumed after the yield

try:
    with manager:  # the generator is spent
        pass
except AttributeError:
    pass
else:
    raise AssertionError("a spent @contextmanager object was entered twice")
```

### Exceptions Inside the Block

An exception raised in the block is thrown into the generator at the `yield`. The generator can
catch it, which suppresses it, or let it through.

```python
from contextlib import contextmanager

@contextmanager
def swallow(kind):
    try:
        yield
    except kind:
        pass

with swallow(ZeroDivisionError):  # O(1) - the exception is thrown in at the yield
    1 / 0

try:
    with swallow(ZeroDivisionError):
        raise KeyError("missing")
except KeyError as error:
    assert error.args == ("missing",)
else:
    raise AssertionError("a KeyError was swallowed")
```

### As a Decorator

The object a `@contextmanager` function returns can also decorate a function. Each call of the
decorated function then builds a fresh generator, so the setup runs once per call.

```python
from contextlib import contextmanager

calls = []

@contextmanager
def counted():
    calls.append("enter")
    yield

@counted()
def work(x):
    return x * 2

assert [work(n) for n in range(3)] == [0, 2, 4]  # O(1) per call
assert calls == ["enter", "enter", "enter"]  # a new generator for every call
```

## Exit Stacks

### Unwinding Order

An `ExitStack` is a list of pending cleanups that grows at run time. Each registration is O(1);
leaving the `with`, or calling `close()`, runs all k of them once, last registered first, as k
nested `with` statements would.

```python
from contextlib import ExitStack, closing

order = []

class Resource:
    def __init__(self, name):
        self.name = name

    def close(self):
        order.append(self.name)

with ExitStack() as stack:  # O(1)
    for name in ["a", "b", "c"]:
        stack.enter_context(closing(Resource(name)))  # O(1) each
    stack.callback(order.append, "callback")  # O(1)
    assert order == []

assert order == ["callback", "c", "b", "a"]  # O(k) - last registered first
```

### Suppressing From the Stack

`push()` registers an `__exit__`-style callable, which sees the exception and can suppress it by
returning true. Callbacks below it in the stack then see no exception. `callback()` ignores the
exception and cannot suppress it.

```python
from contextlib import ExitStack

seen = []

def record(exc_type, exc, tb):
    seen.append(exc_type)
    return False

def swallow(exc_type, exc, tb):
    seen.append(exc_type)
    return True  # suppress

with ExitStack() as stack:
    stack.push(record)  # O(1) - runs last
    stack.push(swallow)  # O(1) - runs first
    raise ValueError("handled by the stack")

assert seen == [ValueError, None]  # the callback below the suppressor saw nothing
```

### Transferring Ownership With pop_all()

`pop_all()` hands the whole stack to a new `ExitStack` in O(1). The usual use is to acquire
several resources and keep them only if every acquisition succeeded.

```python
from contextlib import ExitStack

closed = []

def acquire(names):
    with ExitStack() as stack:
        for name in names:
            if name == "bad":
                raise OSError(name)
            stack.callback(closed.append, name)  # O(1)
        return stack.pop_all()  # O(1) - nothing is closed on the way out

keeper = acquire(["a", "b"])
assert closed == []
keeper.close()  # O(k)
assert closed == ["b", "a"]

try:
    acquire(["c", "bad"])
except OSError:
    assert closed == ["b", "a", "c"]  # a failed acquisition released what it held
else:
    raise AssertionError("acquire() did not raise")
```

### Exceptions During Unwinding

When a cleanup raises, its exception replaces the one in flight. Unwinding stays O(k) when the
cleanups that raise do so without handling the exception they are handed. It becomes O(k²) when
each one raises while handling it - a `@contextmanager` whose `finally` raises is the common case -
because every raise walks the context chain of the exception being handled, and here that chain
holds every earlier cleanup's exception.

```python
from contextlib import ExitStack, contextmanager

@contextmanager
def fails_on_cleanup(n):
    try:
        yield
    finally:
        raise RuntimeError(n)

try:
    with ExitStack() as stack:
        for n in range(3):
            stack.enter_context(fails_on_cleanup(n))  # O(1)
        raise KeyError("body")
except RuntimeError as error:  # O(k²) for k failing cleanups
    chain = []
    while error is not None:
        chain.append(error.args[0])
        error = error.__context__
    assert chain == [0, 1, 2, "body"]
else:
    raise AssertionError("the cleanups did not raise")
```

## Async Context Managers

`@asynccontextmanager`, `AsyncExitStack`, `aclosing()` and `nullcontext()` mirror their
synchronous forms with the same bounds. An `AsyncExitStack` takes both kinds of callback on one
stack and unwinds them in one LIFO pass.

```python
import asyncio
from contextlib import AsyncExitStack, aclosing, asynccontextmanager, nullcontext

order = []

@asynccontextmanager
async def connection(name):
    order.append(f"open {name}")
    try:
        yield name
    finally:
        order.append(f"close {name}")

async def numbers():
    try:
        for n in range(10):
            yield n
    finally:
        order.append("generator closed")

async def main():
    async with AsyncExitStack() as stack:  # O(1)
        conn = await stack.enter_async_context(connection("db"))  # O(1)
        stack.callback(order.append, "sync callback")  # O(1)
        assert conn == "db"

    async with aclosing(numbers()) as agen:  # O(1)
        async for n in agen:
            if n == 2:
                break  # aclose() still runs on the way out

    async with nullcontext("value") as value:  # O(1)
        assert value == "value"

asyncio.run(main())
assert order == ["open db", "sync callback", "close db", "generator closed"]
```

## Suppressing Exceptions

`suppress()` is `try`/`except`/`pass` as a context manager: a matching exception ends the block
and execution resumes after it. From Python 3.12 it also accepts an exception group, splitting it
in O(g): the matching exceptions are dropped, and any others are raised as a new group.

```python
import sys
from contextlib import suppress

with suppress(KeyError, IndexError):  # O(1)
    {}["missing"]
    raise AssertionError("not reached")

if sys.version_info >= (3, 12):
    with suppress(ValueError):  # O(g) - every exception in the group matched
        raise ExceptionGroup("all values", [ValueError(1), ValueError(2)])

    try:
        with suppress(ValueError):
            raise ExceptionGroup("mixed", [ValueError(1), KeyError(2)])
    except ExceptionGroup as group:
        assert [type(e) for e in group.exceptions] == [KeyError]
    else:
        raise AssertionError("the KeyError was suppressed")
```

## Redirecting Output and the Working Directory

`redirect_stdout()`, `redirect_stderr()` and `chdir()` each swap one piece of process-wide state
for the block and restore it after, in O(1). Process-wide means every thread sees the change, so
none of them is a way to capture one thread's output or give one thread its own directory.

```python
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

buffer = io.StringIO()
with redirect_stdout(buffer):  # O(1) - swaps sys.stdout
    print("captured")
assert buffer.getvalue() == "captured\n"
assert sys.stdout is sys.__stdout__

errors = io.StringIO()
with redirect_stderr(errors):  # O(1)
    sys.stderr.write("warning\n")
assert errors.getvalue() == "warning\n"

if sys.version_info >= (3, 11):
    from contextlib import chdir

    start = os.getcwd()
    with tempfile.TemporaryDirectory() as target:
        with chdir(target):  # O(1) - one os.chdir() each way
            assert os.path.samefile(os.getcwd(), target)
        assert os.getcwd() == start
```

## Common Patterns

### A Variable Number of Files

`ExitStack` is the way to hold n files open at once when n is only known at run time. Each file
costs one registration, and all of them are closed even if a later `open()` fails.

```python
import os
import tempfile
from contextlib import ExitStack

with tempfile.TemporaryDirectory() as directory:
    names = [os.path.join(directory, f"part{n}.txt") for n in range(3)]
    for n, name in enumerate(names):
        with open(name, "w") as f:
            f.write(f"line {n}\n")

    with ExitStack() as stack:
        files = [stack.enter_context(open(name)) for name in names]  # O(1) each
        merged = [f.readline() for f in files]

    assert merged == ["line 0\n", "line 1\n", "line 2\n"]
    assert all(f.closed for f in files)  # O(k) on the way out
```

### An Optional Context Manager

`nullcontext()` stands in when a context manager is needed only some of the time, so the `with`
statement does not have to be written twice.

```python
import threading
from contextlib import nullcontext

def update(counter, lock=None):
    with lock if lock is not None else nullcontext():  # O(1)
        counter["n"] += 1

counter = {"n": 0}
update(counter)
update(counter, threading.Lock())
assert counter == {"n": 2}
```

## Performance Best Practices

✅ **Do**:

- Use `ExitStack` when the number of resources is only known at run time; each one is an O(1)
  registration and unwinding is one O(k) pass
- Use `pop_all()` to keep resources past the `with` only once every acquisition succeeded
- Build a fresh `@contextmanager` object for each `with`; the generator inside is single use
- Use `nullcontext()` rather than duplicating a block for the case with no context manager

❌ **Avoid**:

- Cleanups that routinely raise while handling the exception in flight, on a long stack - each
  raise walks the chain the earlier ones built, which makes unwinding O(k²)
- `redirect_stdout()`, `redirect_stderr()` or `chdir()` in threaded code - they change state for
  every thread, not just the one inside the `with`
- `suppress()` around more code than the one statement expected to fail - everything after the
  failing line in the block is skipped

## Version Notes

- **Python 3.10+**: Added `aclosing()` and `AsyncContextDecorator`; `nullcontext()` works with
  `async with`
- **Python 3.11+**: Added `chdir()`
- **Python 3.12+**: `suppress()` handles exception groups

## Related Modules

- **[asyncio](asyncio.md)** - runs the `async with` forms on this page
- **[io](io.md)** - `StringIO`, the usual target for `redirect_stdout()` and `redirect_stderr()`
- **[os](os.md)** - `os.chdir()` and `os.getcwd()`, which `chdir()` wraps
- **[tempfile](tempfile.md)** - temporary files and directories that are themselves context
  managers
