# code Module Complexity

The `code` module packages the read-eval-print loop behind Python's interactive prompt.
`InteractiveInterpreter` compiles and runs one piece of source in a namespace you supply;
`InteractiveConsole` adds prompts and a buffer for the lines of an unfinished block; `interact()`
runs a console until its input ends. Deciding whether source is complete, incomplete or invalid is
delegated to [codeop](codeop.md).

A console does not compile incrementally. Every line pushed is appended to the buffer and the
whole buffer is compiled again, so a block entered one line at a time costs more than the same
source compiled once.

`c` is the characters of the source handed to one `runsource()` - for a console, the whole
buffered block - `b` is the lines in that block, `k` is the characters in one line, `f` is the
frames in a traceback, and `x` is the cost of running the compiled code, which the caller
controls. Compiling is priced as linear in `c`, and namespace lookups as O(1). Traceback bounds
hold the exception message and each frame's source line to a fixed length.

## Complexity Reference

### InteractiveInterpreter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `code.InteractiveInterpreter(locals=None)` | O(1) | O(1) | Runs code in the mapping it is given, not a copy; the default is a new dict holding `__name__` and `__doc__` |
| `InteractiveInterpreter.runsource(source, filename="<input>", symbol="single")` | O(c) + x | O(c) | Returns `True` when more input is needed and `False` otherwise, including after reporting a syntax error |
| `InteractiveInterpreter.runcode(code)` | O(x) | O(1) | An exception adds `showtraceback()`; `SystemExit` propagates instead |
| `InteractiveInterpreter.showsyntaxerror(filename=None)` | O(k) | O(k) | k = the offending line; there is no stack to walk |
| `InteractiveInterpreter.showtraceback()` | O(f) | O(f) | Every frame is walked, even where repeated lines collapse in the output |
| `InteractiveInterpreter.write(data)` | O(w) | O(w) | w = characters in `data`; writes to `sys.stderr`, and error output goes through it unless `sys.excepthook` has been replaced |

### InteractiveConsole

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `code.InteractiveConsole(locals=None, filename="<console>", *, local_exit=False)` | O(1) | O(1) | `local_exit` is Python 3.13+ |
| `InteractiveConsole.push(line)` | O(c) + x | O(c) | Recompiles the whole buffered block, so a block of b lines costs O(b·c) over its pushes |
| `InteractiveConsole.resetbuffer()` | O(b) | O(1) | Drops the buffered lines |
| `InteractiveConsole.raw_input(prompt="")` | O(k) | O(k) | Calls `input()`, so it blocks on `sys.stdin`; raises `EOFError` at end of input |
| `InteractiveConsole.interact(banner=None, exitmsg=None)` | O(b·c) + x per block | O(c) | One `push()` per line until `raw_input()` raises `EOFError`; banner and exit message go through `write()` |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `code.interact(banner=None, readfunc=None, local=None, exitmsg=None, local_exit=False)` | O(b·c) + x per block | O(c) | Runs a new `InteractiveConsole`; `readfunc` replaces its `raw_input()`, and `local_exit` is Python 3.13+ |
| `code.compile_command(source, filename="<input>", symbol="single")` | O(c) | O(c) | The [codeop](codeop.md) function; returns `None` for incomplete input and raises `SyntaxError` for invalid input |

## Running Source in a Namespace

An interpreter runs code in the mapping you hand it, so the caller sees every name the code
defines. `runsource()` answers one question for the caller: does this source need more lines?

```python
import code

class Recording(code.InteractiveInterpreter):
    def write(self, data):  # error output arrives here instead of sys.stderr
        self.errors.append(data)

namespace = {'x': 10}
interp = Recording(namespace)  # O(1) - the dict is used, not copied
interp.errors = []
assert interp.locals is namespace

assert interp.runsource('y = x + 5') is False  # O(c) + x - complete, so it ran
assert namespace['y'] == 15

assert interp.runsource('if y:') is True  # O(c) - incomplete, nothing ran

assert interp.runsource('y = = 1') is False  # a syntax error is reported, not raised
assert 'SyntaxError' in interp.errors[-1]

interp.runsource('1 / 0')  # the traceback goes through write() too
assert 'ZeroDivisionError' in interp.errors[-1]
```

### Whole Sources in One Compile

With the default `symbol='single'`, `runsource()` takes one statement, as the prompt does. A source
already known to be complete goes through one `runsource()` call with `symbol='exec'`, which
compiles it a fixed number of times rather than once per line.

```python
import code

interp = code.InteractiveInterpreter({})
source = "def square(n):\n    return n * n\n\nresult = square(12)\n"

assert interp.runsource(source, symbol='exec') is False  # O(c) - one call
assert interp.locals['result'] == 144
```

## Entering Blocks Line by Line

`push()` appends a line to the console's buffer and hands the whole buffer to `runsource()`. While
the block is unfinished, each push compiles everything typed so far, so a block of b lines is
compiled b times: O(b·c) in total, against O(c) for compiling it once.

```python
import code

console = code.InteractiveConsole({})
lines = ["def total(values):", "    s = 0", "    for v in values:", "        s += v", "    return s"]

for line in lines:
    assert console.push(line) is True  # O(c) - recompiles the whole buffer
assert console.buffer == lines

assert console.push('') is False  # the blank line completes the block, which runs
assert console.buffer == []
assert console.locals['total']([1, 2, 3]) == 6

# resetbuffer() abandons an unfinished block
console.push('while True:')
console.resetbuffer()  # O(b)
assert console.buffer == []
```

### Telling Complete From Incomplete Input

`compile_command()` is how an interpreter decides: a code object for complete input, `None` for
input that could still go on, and `SyntaxError` for input no further lines can fix.

```python
import code

assert code.compile_command('x = 1') is not None  # O(c)
assert code.compile_command('if x:') is None      # more lines needed

try:
    code.compile_command('if x')
except SyntaxError:
    pass
else:
    raise AssertionError('invalid input was accepted')
```

## Driving a Console Without a Terminal

`interact()` reads through `raw_input()`, which blocks on `sys.stdin`. Pass `readfunc` to feed it
lines from anywhere else; the session ends when that function raises `EOFError`.

```python
import code
import contextlib
import io

script = iter(['items = [3, 1, 2]', 'items.sort()', 'first = items[0]'])

def readfunc(prompt):
    try:
        return next(script)
    except StopIteration:
        raise EOFError from None

namespace = {}
with contextlib.redirect_stderr(io.StringIO()):
    code.interact(readfunc=readfunc, local=namespace, banner='', exitmsg='')  # O(c) + x per one-line block

assert namespace['first'] == 1
```

### Leaving a Console With exit()

The `exit()` and `quit()` builtins raise `SystemExit`, which `runcode()` lets through, so by
default it propagates out of `interact()` into the caller. From Python 3.13, `local_exit=True`
makes them end only the console.

```python
import code
import contextlib
import io
import sys

lines = iter(['a = 1', 'exit()', 'a = 2'])  # O(c) + x per one-line block

def readfunc(prompt):
    return next(lines)

namespace = {}
with contextlib.redirect_stderr(io.StringIO()):
    if sys.version_info >= (3, 13):
        code.interact(readfunc=readfunc, local=namespace, banner='', exitmsg='', local_exit=True)
    else:
        try:
            code.interact(readfunc=readfunc, local=namespace, banner='', exitmsg='')
        except SystemExit:
            pass

assert namespace['a'] == 1  # the line after exit() was never read
```

## Common Patterns

### An Embedded Console

A subclass that overrides `raw_input()` and `write()` is a console with no terminal at all: input
comes from the application, and the console's own output - tracebacks, syntax errors, banner and
exit message - goes back to it. `print()` and echoed expression values still go to `sys.stdout`.

```python
import code

class EmbeddedConsole(code.InteractiveConsole):
    def __init__(self, lines, namespace):
        super().__init__(namespace)
        self.lines = iter(lines)
        self.output = []

    def raw_input(self, prompt=''):  # O(k) per line
        try:
            return next(self.lines)
        except StopIteration:
            raise EOFError from None

    def write(self, data):
        self.output.append(data)

console = EmbeddedConsole(['n = 4', 'squares = [i * i for i in range(n)]', 'squares[n]'], {})
console.interact(banner='', exitmsg='')  # O(c) + x per one-line block

assert console.locals['squares'] == [0, 1, 4, 9]
assert any('IndexError' in chunk for chunk in console.output)
```

## Performance Best Practices

✅ **Do**:

- Hand a known multi-line source to one `runsource(source, symbol='exec')` call: O(c), not the
  O(b·c) of pushing it a line at a time
- Supply `readfunc`, or override `raw_input()`, whenever input does not come from a person at a
  terminal
- Override `write()` to capture error output rather than redirecting `sys.stderr` for the whole
  process; a replaced `sys.excepthook` receives the errors instead
- Pass the namespace you want to inspect afterwards; it is used, not copied

❌ **Avoid**:

- Pushing a long generated block through `push()` - every line recompiles all the lines before it
- Calling `interact()` without `readfunc` in a service or test - it blocks on `sys.stdin`
- Letting `exit()` run in an embedded console without `local_exit` - the `SystemExit` leaves
  `interact()` and reaches your code

## Version Notes

- **Python 3.13+**: `InteractiveConsole` and `interact()` take `local_exit`, which makes `exit()` and
  `quit()` end only the console

## Related Modules

- **[codeop](codeop.md)** - `compile_command()` and `CommandCompiler`, the compile step behind
  every `runsource()`
- **[traceback](traceback.md)** - the formatting that `showtraceback()` uses
- **[readline](readline.md)** - line editing for `input()` at a console's prompt
- **[cmd](cmd.md)** - an interpreter for a command language of your own rather than Python
