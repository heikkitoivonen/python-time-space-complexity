# exit() and quit() Functions Complexity

The `exit()` and `quit()` objects terminate the Python interpreter. They are
`_sitebuiltins.Quitter` instances installed into builtins by the `site` module,
intended for interactive use. In scripts, use
[`sys.exit()`](../stdlib/sys.md) instead.

Both do exactly two things when called: close `sys.stdin`, ignoring any error
the close raises, then raise `SystemExit(code)`. The call is O(1); the exit it starts is not, because the
exception unwinds the stack and the interpreter then runs its shutdown.

`d` is the frames `SystemExit` passes through between the call and the code
that handles it, which is the top of the program when nothing does. `h` is the
registered `atexit` handlers, and `m` is the length of an exit message. The
`finally` blocks, `__exit__` methods and handlers that run cost whatever they
do, on top of these bounds.

## Complexity Reference

### exit and quit

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `exit` / `quit` (the bare name) | O(1) | O(1) | `repr()` is a hint naming the call and the EOF key |
| `exit(code=None)` / `quit(code=None)` | O(1) | O(1) | Closes `sys.stdin`, ignoring errors, then raises `SystemExit(code)` |
| `exit(code)` with `None` or an int | O(1) | O(1) | The exit status; `None` means 0 |
| `exit(message)` with a string | O(m) | O(m) | Written to `stderr` at exit; the status is 1 |

### What the call starts

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Unwinding to the handler | O(d) | O(d) | One traceback entry per frame; `finally` and `__exit__` run on the way |
| `atexit` handlers | O(h) plus the handlers | O(1) plus the handlers | Run when the interpreter exits |

## What exit and quit Are

The two objects are callable instances of one class, not functions, and differ
only in the name their hint prints. The hint names the platform's EOF key,
`Ctrl-D (i.e. EOF)` on Unix and macOS and `Ctrl-Z plus Return` on Windows.

```python
import types

assert type(exit) is type(quit)                    # O(1)
assert type(exit).__name__ == 'Quitter'
assert not isinstance(exit, types.FunctionType)

assert repr(exit).startswith('Use exit() or ')     # O(1) - the bare name's hint
assert repr(quit).startswith('Use quit() or ')
```

## Availability

They are installed by the `site` module, so they do not exist under `-S`:

```
$ python -c "exit(7)"; echo $?
7

$ python -S -c "exit(7)"
NameError: name 'exit' is not defined
```

`sys.exit()` does not depend on `site`, which is one reason scripts use it.

## Calling Them

### Exit Status

`exit()` passes its argument straight to `SystemExit`, which carries it as
`code`. `None`, the default, and `0` report success; any other int is handed
to the operating system as the exit status.

```python
for code in (None, 0, 1, 2):
    try:
        exit(code)               # O(1) - the value is stored on the exception
    except SystemExit as e:
        assert e.code == code
    else:
        raise AssertionError('exit() returned')
```

### Passing a String

Any other argument, such as a string, is written to `stderr` when the exception
reaches the top of the program, and the status becomes `1`.

```python
# O(m) - m = length of the message written to stderr; status is 1
exit("error: config.json not found")
```

### The stdin Side Effect

Before raising, `Quitter` closes `sys.stdin`. `sys.exit()` does not do this,
and it can surprise code that still expects to read input.

```python
import sys

try:
    exit()                     # O(1) - closes sys.stdin, then raises
except SystemExit:
    assert sys.stdin.closed    # O(1)
else:
    raise AssertionError('exit() returned')
```

## What Calling Them Triggers

`SystemExit` propagates like any other exception. It gains a traceback entry
for every frame it leaves, so unwinding is O(d) in time and space.

```python
def nested(depth):
    if depth == 0:
        exit(1)
    nested(depth - 1)

try:
    nested(100)
except SystemExit as e:
    tb, entries = e.__traceback__, 0
    while tb is not None:
        tb, entries = tb.tb_next, entries + 1
    assert entries > 100       # O(d) - one entry per frame unwound
```

Cleanup runs on the way out: `finally` blocks and `__exit__` methods as the
exception passes them, then `atexit` handlers when the interpreter exits.

```python
import atexit

atexit.register(print, 'atexit handler')   # runs last, at interpreter exit

events = []

class Resource:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        events.append('__exit__')
        return False

try:
    with Resource():
        try:
            exit(3)                        # O(1) to raise
        finally:
            events.append('finally')
except SystemExit as e:
    events.append(('caught', e.code))

assert events == ['finally', '__exit__', ('caught', 3)]
```

The exit therefore costs O(d + h) plus whatever those blocks and handlers do,
on top of the interpreter's own shutdown, which is the same however it is
reached. The call never returns, but the process ends only after all of it has
run.

## Interactive Use

At the interactive prompt, `exit()` or `quit()` ends the session, and so does
the EOF key: Ctrl-D on Unix and macOS, Ctrl-Z then Enter on Windows.

From Python 3.13 the default REPL also takes a line holding only `exit` or
`quit` as a command and exits, unless a variable of that name has been
defined. The basic REPL - the only one before 3.13, and the one
`PYTHON_BASIC_REPL=1` selects - evaluates the bare name like any other
expression, so it prints the hint from `__repr__` instead of exiting.

## Performance Best Practices

✅ **Do**:

- Use [`sys.exit()`](../stdlib/sys.md) in scripts: it is there under `-S`
  and leaves `sys.stdin` open
- Pass an integer for the exit status, or a message to report an error
- Remember they raise `SystemExit`, so `finally`, `__exit__` and `atexit`
  still run, at O(d + h) plus their own cost

❌ **Avoid**:

- Using them in scripts - they are absent under `-S`, and they close
  `sys.stdin`
- Calling either from a library - raise an exception and let the caller decide
- Assuming the exit is instantaneous - unwinding and handlers run first

## Version Notes

- **Python 3.13+**: the default interactive REPL exits on a line holding only
  `exit` or `quit`; the basic REPL prints the hint

## Related Modules

- **[sys](../stdlib/sys.md)** - `sys.exit()`, the form to use in scripts
- **[atexit](../stdlib/atexit.md)** - handlers that run when the interpreter exits
- **[os](../stdlib/os.md)** - `os._exit()` for termination that skips all cleanup
- **[signal](../stdlib/signal.md)** - signal handling
- **[Interpreter Info](interpreter_info.md)** - the other REPL-only builtins from `site`
