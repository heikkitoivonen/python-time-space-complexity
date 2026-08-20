# exit() and quit() Functions

The `exit()` and `quit()` objects terminate the Python interpreter. They are
`_sitebuiltins.Quitter` instances installed into builtins by the `site` module,
intended for interactive use. In scripts, use
[`sys.exit()`](../stdlib/sys.md) instead.

Both do exactly two things when called: close `sys.stdin`, then raise
`SystemExit(code)`. Everything about their cost follows from that.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `exit` / `quit` (bare name) | O(1) | O(1) | Returns a fixed hint string from `__repr__` |
| `exit()` / `quit()` (the call) | O(1) | O(1) | Closes `sys.stdin`, raises `SystemExit` |
| Resulting stack unwinding | O(d) | O(1) | d = frames with `finally` or `__exit__` to run |
| Resulting `atexit` handlers | O(h) + handlers | O(1) | h = registered handlers |
| `exit(code)` with an int | O(1) | O(1) | Stored on the exception, becomes exit status |
| `exit(message)` with a string | O(n) | O(n) | n = message length, written to `stderr`; status 1 |

The call itself is constant time. What follows it is not: raising `SystemExit`
unwinds the stack and runs the interpreter's normal shutdown, so the real cost
is dominated by whatever cleanup your program has registered.

## What exit and quit Are

```python
# O(1) - type lookups
print(type(exit))    # O(1) - <class '_sitebuiltins.Quitter'>
print(type(quit))    # O(1) - <class '_sitebuiltins.Quitter'>

# The bare name prints a hint rather than exiting - O(1)
print(repr(exit))    # Use exit() or Ctrl-D (i.e. EOF) to exit
print(repr(quit))    # Use quit() or Ctrl-D (i.e. EOF) to exit
```

The two objects are identical apart from the name they print. Neither is a
function; both are callable instances.

## Availability

They are installed by the `site` module, so they do not exist under `-S`:

```
$ python -c "exit(7)"; echo $?
7

$ python -S -c "exit(7)"
NameError: name 'exit' is not defined
```

This is the main reason they do not belong in a script.

## Calling Them

### Exit Status

`exit()` passes its argument straight to `SystemExit`, so it accepts the same
values as any exit status.

```python
# All O(1) - the value is stored on the exception
exit()      # status 0
exit(0)     # status 0 - success
exit(1)     # status 1 - general error
exit(2)     # status 2 - misuse
```

```
$ python -c "exit(7)"; echo $?
7
```

### Passing a String

A non-integer argument is printed to `stderr` and the status becomes `1`.

```python
# O(n) - n = length of the message written to stderr; status is 1
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
    print(sys.stdin.closed)    # O(1) - True
```

## What Calling Them Triggers

`SystemExit` propagates like any other exception, so cleanup still runs before
the process ends.

```python
import atexit
import sys

atexit.register(lambda: print("3. atexit handler"))   # O(1) to register

class Resource:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        print("2. __exit__")                          # O(1)
        return False

try:
    with Resource():
        try:
            exit(3)                                   # O(1) to raise
        finally:
            print("1. finally")                       # O(1)
except SystemExit as e:
    print("caught, code =", e.code)                   # O(1) - 3

# Output order: 1. finally, 2. __exit__, caught, then 3. atexit handler
```

Total cost of the exit is therefore O(d + h) plus whatever those handlers do.
`exit()` is only "immediate" in the sense that the call returns nothing.

## Interactive Use

```python
# In the REPL, calling either one ends the session - O(1) to raise
exit()
quit()

# Ctrl-D (Unix/macOS) or Ctrl-Z then Enter (Windows) does the same
```

Typing the bare name is the common mistake: it prints the hint instead of
exiting, which is exactly what `__repr__` is there for.

## Best Practices

✅ **Do**:

- Treat `exit()` and `quit()` as REPL conveniences
- Pass an integer for the exit status, or a string to report an error
- Remember they raise `SystemExit`, so `finally` and `atexit` still run

❌ **Avoid**:

- Using them in scripts - they are absent under `-S`, and they close
  `sys.stdin`. Use [`sys.exit()`](../stdlib/sys.md)
- Calling either from a library - raise an exception and let the caller decide
- Assuming the exit is instantaneous - unwinding and handlers run first

## Related Modules

- [sys Module](../stdlib/sys.md) - `sys.exit()`, the form to use in scripts
- [Atexit Module](../stdlib/atexit.md) - Handlers that run when `SystemExit` propagates
- [OS Module](../stdlib/os.md) - `os._exit()` for termination that skips all cleanup
- [Signal Module](../stdlib/signal.md) - Signal handling
- [Interpreter Info](interpreter_info.md) - The other REPL-only builtins from `site`
