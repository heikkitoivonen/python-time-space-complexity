# contextvars Module Complexity

The `contextvars` module gives each thread and each asyncio task its own values for shared
variables. A `Context` is a read-only mapping from `ContextVar` objects to values, backed by an
immutable hash array mapped trie (HAMT): setting a variable builds a new trie that shares
everything but one path with the old one, so copying a context never copies its contents.

`n` is the variables set in the context being read, written or copied. Keys are always
`ContextVar` objects, which cannot be subclassed, so no user code runs during a lookup. Context
equality compares values, and prices each comparison at O(1).

## Complexity Reference

### ContextVar

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `contextvars.ContextVar(name, *, default)` | O(1) | O(1) | A variable set in a context stays a key there until a reset unsets it, so create variables once, at module level |
| `ContextVar.get([default])` | O(log n) | O(1) | Falls back to `default`, then the variable's own default, then raises `LookupError` |
| `ContextVar.set(value)` | O(log n) | O(log n) | Returns a `Token`; the mapping it replaces is left intact |
| `ContextVar.reset(token)` | O(log n) | O(log n) | Only in the context the token came from, and only once |
| `ContextVar.name` | O(1) | O(1) | Names do not identify variables: two variables with one name are two keys |

### Token

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Token.var`, `Token.old_value` | O(1) | O(1) | `old_value` is `Token.MISSING` if the variable was unset |
| `Token.MISSING` | O(1) | O(1) | Marker object |
| `with var.set(value):` | O(log n) | O(log n) | Python 3.14+; resets the variable on exit |

### Context

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `contextvars.copy_context()` | O(1) | O(1) | Shares the current mapping; neither side sees the other's later sets |
| `contextvars.Context()` | O(1) | O(1) | An empty context |
| `Context.copy()` | O(1) | O(1) | Same as `copy_context()`, for any context |
| `Context.run(callable, *args, **kwargs)` | O(1) + callable | O(1) + callable | Does not copy: sets made by the callable stay in the context. Raises `RuntimeError` if the context is already entered |
| `ctx[var]`, `Context.get(var, default=None)`, `var in ctx` | O(log n) | O(1) | |
| `len(ctx)` | O(1) | O(1) | The count is stored |
| `iter(ctx)`, `Context.keys()`, `Context.values()`, `Context.items()` | O(1) to create, O(n) to exhaust | O(1) | One-shot iterators, not lists; the order is not the order the variables were set |
| `ctx == other` | O(n log n) | O(1) | |

## Setting and Reading Variables

A set does not overwrite anything: it builds a new trie that copies the O(log n) path down to
the variable's slot, and the `Token` it returns remembers the value it replaced.

```python
from contextvars import ContextVar, Token

request_id = ContextVar('request_id')
user = ContextVar('user', default='anonymous')

try:
    request_id.get()  # O(log n)
except LookupError:
    pass
else:
    raise AssertionError('an unset variable with no default was read')
assert request_id.get('none') == 'none'
assert user.get() == 'anonymous'

token = request_id.set('req-1')  # O(log n)
assert token.var is request_id and token.old_value is Token.MISSING
assert request_id.get() == 'req-1'  # O(log n)

request_id.reset(token)  # O(log n) - back to unset
assert request_id.get('none') == 'none'
```

## Copying a Context

`copy_context()` takes a reference to the current mapping instead of duplicating it, so its cost
does not depend on how many variables are set. The copy and the original then diverge one path
at a time as either side sets variables.

```python
from contextvars import ContextVar, copy_context

setting = ContextVar('setting', default='default')
setting.set('outer')

ctx = copy_context()  # O(1), whatever n is
assert ctx[setting] == 'outer'  # O(log n)

ctx.run(setting.set, 'inner')  # O(log n) - changes the copy only
assert ctx[setting] == 'inner'
assert setting.get() == 'outer'
```

## Running Code in a Context

`Context.run()` switches the thread's current context for the duration of the call. It does not
copy: anything the callable sets is still in the context afterwards, and a context can be entered
by only one call at a time.

```python
from contextvars import Context, ContextVar

counter = ContextVar('counter', default=0)
ctx = Context()  # O(1) - empty

def bump():
    counter.set(counter.get() + 1)  # O(log n)
    return counter.get()

assert ctx.run(bump) == 1  # O(1) + bump
assert ctx.run(bump) == 2  # the first call's set is still there
assert counter.get() == 0  # the caller's context is untouched

try:
    ctx.run(ctx.run, bump)
except RuntimeError as error:
    assert 'already entered' in str(error)
else:
    raise AssertionError('a context was entered twice')
```

## Inspecting a Context

A `Context` is a read-only mapping keyed by variables. `len()` is stored; iteration walks the
trie lazily, so `keys()`, `values()` and `items()` are one-shot iterators rather than lists, in
hash order rather than the order the variables were set.

```python
from contextvars import Context, ContextVar

a = ContextVar('a')
b = ContextVar('b')
ctx = Context()
ctx.run(a.set, 1)
ctx.run(b.set, 2)

assert len(ctx) == 2  # O(1)
assert a in ctx and ctx.get(b) == 2  # O(log n)

keys = ctx.keys()  # O(1) - nothing is walked yet
assert set(keys) == {a, b}  # O(n)
assert list(keys) == []  # already exhausted
assert dict(ctx.items()) == {a: 1, b: 2}  # O(n)
```

## Common Patterns

### Request-Scoped Values

```python
from contextvars import ContextVar

request_id = ContextVar('request_id', default=None)  # once, at module level

def log(message):
    return f'[{request_id.get()}] {message}'  # get() is O(log n)

def handle(rid):
    token = request_id.set(rid)  # O(log n)
    try:
        return log('handled')
    finally:
        request_id.reset(token)  # O(log n)

assert handle('req-7') == '[req-7] handled'
assert request_id.get() is None
```

### Asyncio Tasks

Each task runs in a copy of the context that was current when it was created, unless a `context`
argument (3.11+) supplies one. The copy is O(1), so this costs the same however many variables
are set.

```python
import asyncio
from contextvars import ContextVar

task_name = ContextVar('task_name', default='main')

async def worker(name):
    task_name.set(name)  # O(log n), in this task's copy only
    await asyncio.sleep(0)
    return task_name.get()

async def main():
    task_name.set('parent')
    results = await asyncio.gather(worker('a'), worker('b'))
    assert results == ['a', 'b']
    assert task_name.get() == 'parent'

asyncio.run(main())
```

### Threads

Unless `sys.flags.thread_inherit_context` is set or a `context` argument (3.14+) is passed, a new
thread starts in an empty context. To carry values across either way, run the thread's target in
a copy of the caller's context.

```python
import sys
import threading
from contextvars import ContextVar, copy_context

request_id = ContextVar('request_id', default=None)
seen = {}

def worker(key):
    seen[key] = request_id.get()

request_id.set('req-9')

bare = threading.Thread(target=worker, args=('bare',))
carried = threading.Thread(target=copy_context().run, args=(worker, 'carried'))  # O(1) copy
for thread in (bare, carried):
    thread.start()
    thread.join()

inherits = getattr(sys.flags, 'thread_inherit_context', 0)
assert seen == {'bare': 'req-9' if inherits else None, 'carried': 'req-9'}
```

## Performance Best Practices

✅ **Do**:

- Create each `ContextVar` once, at module level
- Pair every `set()` with a `reset()` in a `finally`, or on 3.14+ a `with` block, so a context
  does not keep values it no longer needs
- Copy a context whenever you need isolation: `copy_context()` is O(1)

❌ **Avoid**:

- Creating variables inside a function that runs repeatedly: every new variable set in a
  long-lived context is a new key it keeps, so n grows with each call
- Reusing one context with `Context.run()` when each call needs a fresh start - changes made by
  earlier calls stay in it; run each call in a new `copy_context()` instead
- Materialising `list(ctx.items())` just to read one variable - that is O(n) against O(log n)

## Version Notes

- **Python 3.14+**: `Token` is a context manager, and `with var.set(value):` resets on exit
- **Python 3.14+**: `threading.Thread` takes a `context` argument; with
  `sys.flags.thread_inherit_context` set, the default on free-threaded builds, a new thread
  starts in a copy of the caller's context instead of an empty one

## Related Modules

- **[asyncio](asyncio.md)** - every task and scheduled callback captures a context
- **[threading](threading.md)** - each thread has its own current context
- **[concurrent.futures](concurrent_futures.md)** - submit `copy_context().run` to carry values into a worker
