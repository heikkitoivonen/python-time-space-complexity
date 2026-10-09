# breakpoint() Function Complexity

The `breakpoint()` function calls `sys.breakpointhook()`, passing its arguments straight through,
and returns what the hook returns. Its own work is O(1); what a call costs is the hook's. The
default hook reads the `PYTHONBREAKPOINT` environment variable on every call and either returns at
once, calls the function the variable names, or enters [pdb](../stdlib/pdb.md).

`d` is frames on the stack at the call and `c` is files in the `linecache` cache. A function named
by `PYTHONBREAKPOINT` or installed as the hook costs whatever it does, added on top; importing its
module the first time is a one-time cost the bounds leave out.

## Complexity Reference

### breakpoint and sys.breakpointhook

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `breakpoint(*args, **kws)` | O(1) plus the hook | O(1) plus the hook | Calls `sys.breakpointhook(*args, **kws)` and returns its result; raises the `builtins.breakpoint` audit event first |
| `sys.breakpointhook = hook` | O(1) | O(1) | `breakpoint()` then calls `hook`, and `PYTHONBREAKPOINT` is not read |
| `sys.__breakpointhook__` | O(1) | O(1) | The default hook, kept so a replacement can be undone |

### The default hook

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `PYTHONBREAKPOINT` unset or empty | O(c + d) | O(c + d) | Calls `pdb.set_trace()` and waits for a command; the [pdb page](../stdlib/pdb.md) prices it, including the `Pdb` it builds |
| `PYTHONBREAKPOINT=0` | O(1) | O(1) | Returns `None` without importing anything |
| `PYTHONBREAKPOINT=module.function` | O(1) plus the function | O(1) plus the function | Imports `module` and returns `function(*args, **kws)`; a name with no dot is a builtin, such as `int` |
| `PYTHONBREAKPOINT` naming a missing module or attribute | O(1) | O(1) | Emits a `RuntimeWarning` and returns `None` |

## Replacing the Hook

Assigning `sys.breakpointhook` routes every `breakpoint()` call to the new function, arguments
and return value included. `PYTHONBREAKPOINT` is no longer consulted, so a test can intercept
breakpoints whatever the environment says.

```python
import sys

calls = []

def record(*args, **kws):
    calls.append((args, kws))
    return 'recorded'

previous = sys.breakpointhook
sys.breakpointhook = record
try:
    result = breakpoint('here', depth=3)  # O(1) plus record()
finally:
    sys.breakpointhook = previous

assert result == 'recorded'
assert calls == [(('here',), {'depth': 3})]
```

## Choosing a Hook With PYTHONBREAKPOINT

The default hook reads `PYTHONBREAKPOINT` each time it is called, so changing `os.environ` takes
effect on the next `breakpoint()`. `0` makes every call an O(1) no-op that returns `None`.

```python
import os

os.environ['PYTHONBREAKPOINT'] = '0'
assert breakpoint() is None  # O(1): no debugger, no import
```

Any other value names a callable by its dotted path. The module part is imported, and the
callable gets `breakpoint()`'s arguments and supplies its return value.

```python
import os

os.environ['PYTHONBREAKPOINT'] = 'json.dumps'
assert breakpoint([1, 2]) == '[1, 2]'  # O(1) plus json.dumps([1, 2])

os.environ['PYTHONBREAKPOINT'] = 'int'
assert breakpoint('42') == 42  # no dot: the builtin int
```

A module that does not exist, or one without that attribute, is not an error: the call warns and
does nothing.

```python
import os
import warnings

os.environ['PYTHONBREAKPOINT'] = 'no_such_module.hook'
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    assert breakpoint() is None  # O(1): warns, no debugger

assert caught[0].category is RuntimeWarning
assert 'no_such_module.hook' in str(caught[0].message)
```

`python -E` and `python -I` ignore `PYTHONBREAKPOINT`, as they do the other `PYTHON*` variables,
so under either a `breakpoint()` left in the code enters pdb even when the variable is `0`.

## Entering pdb

With `PYTHONBREAKPOINT` unset, `breakpoint()` is `pdb.set_trace()` at the call site: entering
costs O(c + d), and the stop waits for input. After `continue`
the program runs under the debugger's trace hook, or untraced if no breakpoints are set; the
[pdb page](../stdlib/pdb.md) prices both, and how they differ between the `'settrace'` and
`'monitoring'` backends.

## Performance Best Practices

✅ **Do**:

- Set `PYTHONBREAKPOINT=0` where a stray `breakpoint()` must not stop the program: each call
  becomes O(1) and imports nothing
- Replace `sys.breakpointhook` to intercept breakpoints in tests, saving the previous hook to
  restore; `sys.__breakpointhook__` is the default
- `continue` with no breakpoints set when you are done, so the rest of the program runs untraced

❌ **Avoid**:

- Relying on `PYTHONBREAKPOINT=0` under `python -E` or `-I`, which ignore it
- Passing positional arguments to `breakpoint()` while `PYTHONBREAKPOINT` is unset:
  `pdb.set_trace()` accepts none and raises `TypeError`

## Version Notes

- **Python 3.14+**: the default hook's `pdb.set_trace()` reuses the last `Pdb` whose `set_trace()`
  ran, and otherwise builds one on the `'monitoring'` backend; earlier releases build a new `Pdb`
  on every call

## Related Modules

- **[pdb](../stdlib/pdb.md)** - what the default hook enters, and the cost of running between stops
- **[sys](../stdlib/sys.md)** - `sys.breakpointhook()` and `sys.__breakpointhook__`
- **[bdb](../stdlib/bdb.md)** - the trace events a debugger receives, priced per event
