# pdb Module Complexity

The `pdb` module is Python's interactive debugger. It is a command loop on top of
[`bdb`](bdb.md): entering it hooks every frame on the stack, each stop builds a list of the
frames and waits for commands, and between stops the program runs under a trace hook that decides
which calls and lines the debugger has to look at. What a debugging session costs is mostly that
last part, and it depends on the tracing backend and on where the breakpoints are.

`d` is frames on the stack at a stop, or traceback entries in a post-mortem session, `c` is files
in the `linecache` cache, `r` is lines in the `.pdbrc` files, `x` is `display` expressions in the
current frame, `n` is source lines a listing prints, `e` is chained exceptions, `b` is lines
holding a breakpoint in one file, `k` is breakpoints at one line, `L` is file:line locations
holding a breakpoint anywhere in the process, and `B` is breakpoint numbers ever assigned. File
names, source lines and command words are priced at O(1); evaluating an expression, a condition
or a `display` costs whatever that expression does, and is added on top. One-time cache fills
are left out of the bounds, as on the [bdb page](bdb.md): `linecache` reading a whole file the
first time a line of it is shown. Rows about running between stops count the trace events the
debugger receives, each priced on the bdb page.

## Complexity Reference

### Entering the debugger

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pdb.set_trace(*, header=None, commands=None)`, `breakpoint()` | O(c + d) | O(c + d) | Hooks every frame on the stack, then stops; `commands` is 3.14+. From 3.14 it reuses the last `Pdb` whose `set_trace()` ran, and otherwise builds one on the `'monitoring'` backend |
| `Pdb.set_trace(frame=None, *, commands=None)` | O(c + d) | O(c + d) | The same, starting from `frame` rather than the caller; `commands` is 3.14+ |
| `pdb.set_trace_async(*, header=None, commands=None)`, `Pdb.set_trace_async(frame=None, *, commands=None)` | O(c + d) | O(c + d) | 3.14+; awaited in a coroutine |
| `pdb.run(statement, globals=None, locals=None)`, `pdb.runctx(statement, globals, locals)`, `Pdb.run(cmd, globals=None, locals=None)` | O(c) | O(c) | Plus compiling a string; stops before the first line, then the statement runs under the debugger |
| `pdb.runeval(expression, globals=None, locals=None)`, `Pdb.runeval(expr, globals=None, locals=None)` | O(c) | O(c) | As `run()`, and returns the expression's value |
| `pdb.runcall(function, *args, **kwds)`, `Pdb.runcall(func, /, *args, **kwds)` | O(c) | O(c) | Stops on entering `function` and returns what it returns |
| `pdb.post_mortem(t=None)` | O(c + d + e) | O(c + d + e) | An exception object is accepted from 3.13, and its chain of e becomes browsable with `exceptions` |
| `pdb.pm()` | O(c + d + e) | O(c + d + e) | `post_mortem()` on the last uncaught exception, `sys.last_exc` from 3.12 |
| `pdb.Pdb(completekey='tab', stdin=None, stdout=None, skip=None, nosigint=False, readrc=True, mode=None, backend=None, colorize=False)` | O(r + L·b) | O(r + L) | Reads `~/.pdbrc` and `./.pdbrc` whole unless `readrc=False`, and copies the breakpoint locations already registered; `mode`, `backend` and `colorize` are 3.14+ |
| `pdb.set_default_backend(backend)`, `pdb.get_default_backend()` | O(1) | O(1) | 3.14+; `'settrace'` or `'monitoring'`, used by a `Pdb` built without `backend` |

`run()`, `runctx()`, `runeval()`, `runcall()`, `post_mortem()` and `pm()` build a new `Pdb` on
every call, so each also pays its O(r + L·b). So do `set_trace()` and `breakpoint()` before 3.14;
from 3.14 they, and `set_trace_async()`, build one only when no `Pdb` has run `set_trace()` yet.

### Running between stops

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `continue` with no breakpoints set | O(d) | O(1) | Removes the trace hook: the program runs untraced until the next `set_trace()` |
| `continue`, `next`, `until`, `return` on the `'settrace'` backend | O(1) event per Python call, one per line in a traced frame | O(1) | Frames on the stack at the stop keep raising line events, and so does a called function holding a breakpoint; before 3.14, any function in a file holding one |
| `continue`, `next`, `until`, `return` on the `'monitoring'` backend | O(1) event per function that cannot stop, then none until the next stop | O(1) | 3.14+; a function holding a breakpoint still raises an event on every call, and its breakpoint line on every run |
| `step` | O(1) events | O(1) | Stops at the next line, in whatever frame runs it |

### Commands at a stop

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Each stop | O(d + x) | O(d) | Builds the list of frames, then re-evaluates the current frame's `display` expressions |
| `where`, `w`, `bt` | O(d) | O(d) | One entry per frame |
| `up [count]`, `down [count]` | O(1) | O(1) | Moves through the list the stop built |
| `list [first[, last]]`, `longlist`, `ll` | O(n·b) | O(n) | `list` prints 11 lines by default; `longlist` prints the whole current function. Each line is looked up in the file's list of breakpoint lines |
| `p expression`, `pp expression`, `!statement` | O(1) | O(1) | Plus the expression and its `repr()` |
| `display expression`, `undisplay [expression]` | O(1) | O(1) | `display` evaluates once now, and again at every later stop in this frame |
| `display` | O(x) | O(1) | Lists the current frame's expressions with their last values |
| `interact` | O(g + l) | O(g + l) | g, l = names in the frame's globals and locals, copied into a new namespace: assignments there do not reach the frame |
| `exceptions [number]` | O(d + e) | O(d + e) | 3.13+, post-mortem on an exception; listing is O(e), and choosing one rebuilds the stack for its traceback |
| `break [[filename:]lineno \| function[, condition]]`, `tbreak ...` | O(d·b) | O(1) | During a stop, 3.12.9+ and 3.13.1+ re-check every frame so the breakpoint takes effect in functions already running; before, O(b). With no argument, `break` lists every breakpoint, O(B). A `function` that does not evaluate in the current frame is looked up by reading its source file, which this bound leaves out |
| `clear bpnumber [bpnumber ...]` | O(b + k) per number | O(1) | |
| `clear` | O(B·k) | O(B) | Clears every breakpoint, walking every number ever assigned, and keeps a list of them to report |
| `disable bpnumber`, `enable bpnumber`, `ignore bpnumber [count]`, `condition bpnumber [condition]` | O(1) per number | O(1) | Breakpoints are looked up by number |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pdb.Restart` | O(1) | O(1) | Raised by `restart` to rerun a script under `python -m pdb` |
| `Pdb.MAX_CHAINED_EXCEPTION_DEPTH` | O(1) | O(1) | 3.13+; 999, the most chained exceptions `exceptions` lists |

## Entering the Debugger

Entering the debugger hooks every frame already on the stack, so it costs the stack's depth, and
the stop that follows builds a list of the same frames. A `Pdb` given its own `stdin` and
`stdout` takes commands from them, which is how a session can be scripted.

```python
import io
import pdb

def descend(depth):
    if depth:
        return descend(depth - 1)
    commands = io.StringIO('p depth\nwhere\ncontinue\n')
    out = io.StringIO()
    debugger = pdb.Pdb(stdin=commands, stdout=out, readrc=False, nosigint=True)
    debugger.set_trace()  # O(c + d) - hooks every frame on the stack
    return out.getvalue()

transcript = descend(20)
assert '(Pdb) 0' in transcript  # p depth, in the innermost frame
assert transcript.count('descend()') >= 21  # where: one entry per frame, O(d)
```

### Post-Mortem Debugging

`post_mortem()` starts a session on a traceback that has already unwound: the stack it shows is
the traceback's entries, and nothing runs afterwards. It reads commands from `sys.stdin`, which
the example below swaps for scripted input.

```python
import contextlib
import io
import pdb
import sys

def fail(depth):
    if depth:
        return fail(depth - 1)
    raise ValueError('bad input')

try:
    fail(10)
except ValueError as error:
    traceback = error.__traceback__

out = io.StringIO()
sys.stdin = io.StringIO('p depth\nwhere\nquit\n')
try:
    with contextlib.redirect_stdout(out):
        pdb.post_mortem(traceback)  # O(c + d), d = traceback entries
finally:
    sys.stdin = sys.__stdin__

assert '(Pdb) 0' in out.getvalue()
assert out.getvalue().count('fail()') >= 11
```

### Chained Exceptions

From 3.13 `post_mortem()` also takes the exception itself. Its `__cause__` and `__context__`
chain, up to `Pdb.MAX_CHAINED_EXCEPTION_DEPTH`, is then listed by `exceptions`, and
`exceptions number` moves the session to another link's traceback.

```python
import contextlib
import io
import pdb
import sys

def parse(text):
    try:
        return int(text)
    except ValueError as error:
        raise RuntimeError('config is broken') from error

try:
    parse('seven')
except RuntimeError as error:
    caught = error

if sys.version_info >= (3, 13):
    out = io.StringIO()
    sys.stdin = io.StringIO('exceptions\nexceptions 0\np text\nquit\n')
    try:
        with contextlib.redirect_stdout(out):
            pdb.post_mortem(caught)  # O(c + d + e)
    finally:
        sys.stdin = sys.__stdin__
    assert "0 ValueError(\"invalid literal for int() with base 10: 'seven'\")" in out.getvalue()
    assert ">   1 RuntimeError('config is broken')" in out.getvalue()  # the current one
    assert "(Pdb) 'seven'" in out.getvalue()  # the ValueError's frame
```

## What Runs Traced

`continue` with no breakpoints set removes the trace hook, and the program runs at full speed.
With a breakpoint set it keeps the hook, and on the `'settrace'` backend every Python call raises
an event. Lines raise events only in frames that were on the stack at the stop, and in called
functions that could stop: from 3.14 those holding a breakpoint, before 3.14 every function in a
file that holds one. A breakpoint elsewhere in the same module therefore traces a hot loop line
by line on 3.13 and earlier.

```python
import io
import pdb
from collections import Counter

class CountingPdb(pdb.Pdb):
    def __init__(self, commands, **kwargs):
        super().__init__(stdin=io.StringIO(commands), stdout=io.StringIO(),
                         readrc=False, nosigint=True, **kwargs)
        self.events = Counter()

    def trace_dispatch(self, frame, event, arg):
        if frame.f_code is step.__code__:
            self.events[event] += 1
        return super().trace_dispatch(frame, event, arg)

def step(value):
    doubled = value * 2
    return doubled

def hot_loop(count):
    return sum(step(i) for i in range(count))

def elsewhere():
    return 'never called'

def events(commands, **kwargs):
    debugger = CountingPdb(commands, **kwargs)
    debugger.set_trace()
    hot_loop(1_000)
    return debugger.events

# No breakpoints: continuing removes the hook
assert events('continue\n') == {}

# A breakpoint in this file, but not in step(): one call event per call
line = elsewhere.__code__.co_firstlineno + 1
counted = events(f'break {line}\ncontinue\n')
assert counted['call'] == 1_000
assert counted['line'] in (0, 2_000)  # 0 from 3.14; before, every line of step()
```

### The Monitoring Backend

From 3.14 a `Pdb` can run on `sys.monitoring` instead of `sys.settrace()`. It switches off a
function once it has seen that the function cannot stop, until the next stop turns it back on, so
a function called a thousand times raises one event. A function holding a breakpoint is not
switched off. `pdb.set_trace()`, `breakpoint()` and `python -m pdb` use it; a `Pdb` built
directly uses the default backend, `'settrace'` unless `set_default_backend()` changes it.

```python
import io
import pdb
import sys

class CallCounter(pdb.Pdb):
    calls = 0

    def trace_dispatch(self, frame, event, arg):
        if event == 'call' and frame.f_code is square.__code__:
            CallCounter.calls += 1
        return super().trace_dispatch(frame, event, arg)

def square(value):
    return value * value

def unrelated():
    return None

if sys.version_info >= (3, 14):
    assert pdb.get_default_backend() == 'settrace'  # O(1)
    line = unrelated.__code__.co_firstlineno + 1
    for backend, expected in (('settrace', 1_000), ('monitoring', 1)):
        CallCounter.calls = 0
        debugger = CallCounter(stdin=io.StringIO(f'break {line}\ncontinue\n'),
                               stdout=io.StringIO(), readrc=False, nosigint=True,
                               backend=backend)
        debugger.set_trace()
        for i in range(1_000):
            square(i)
        sys.settrace(None)
        assert CallCounter.calls == expected, (backend, CallCounter.calls)
```

## Breakpoints and Displays

A breakpoint's condition is evaluated every time its line runs, and a `display` expression is
re-evaluated at every stop in its frame, so both add their expression's cost that many times.

```python
import io
import pdb

evaluations = []

def watched(label):
    evaluations.append(label)
    return len(evaluations)

def countdown():
    debugger = pdb.Pdb(
        stdin=io.StringIO(f'break {line}, i == 3\ncontinue\n'
                          'display watched("stop")\np i\nnext\nnext\ncontinue\n'),
        stdout=io.StringIO(), readrc=False, nosigint=True)
    debugger.set_trace()
    total = 0
    for i in range(5):
        total += i
    return debugger.stdout.getvalue()

line = countdown.__code__.co_firstlineno + 8  # total += i
transcript = countdown()
assert '(Pdb) 3' in transcript  # stopped where the condition first held
assert evaluations == ['stop', 'stop', 'stop']  # once when set, then at each of two stops
```

## Common Patterns

### Scripting a Session

`Pdb(stdin=..., stdout=...)` and `runcall()` make a debugging session repeatable: the commands
come from a string, and the output is text to assert on.

```python
import io
import pdb

def average(values):
    total = sum(values)
    return total / len(values)

out = io.StringIO()
debugger = pdb.Pdb(stdin=io.StringIO('next\np total\ncontinue\n'),
                   stdout=out, readrc=False, nosigint=True)
assert debugger.runcall(average, [2, 4, 6]) == 4  # O(c), then the call runs under the debugger
assert '(Pdb) 12' in out.getvalue()
```

## Performance Best Practices

✅ **Do**:

- `continue` with no breakpoints left when you are done: the rest of the program runs untraced
- Put breakpoints in the functions you are debugging; on 3.13 and earlier one anywhere in a file
  traces every function of that file line by line while the program runs on
- Use the `'monitoring'` backend on 3.14+ for long runs between stops
- Keep `display` expressions and breakpoint conditions cheap: a display runs at every stop in its
  frame, a condition every time its line runs

❌ **Avoid**:

- `step` through code you do not need to see; `next` and `until` run a call without stopping in it
- Leaving a conditional breakpoint on a hot line: its condition is evaluated each time the line
  runs, on either backend

## Version Notes

- **Python 3.14+**: `set_default_backend()`, `get_default_backend()`, `Pdb(backend=...)` and the
  `'monitoring'` backend, which `pdb.set_trace()`, `breakpoint()` and `python -m pdb` use
- **Python 3.14+**: `set_trace_async()` and `set_trace(commands=...)` added; `pdb.set_trace()`
  reuses the last `Pdb` whose `set_trace()` ran
- **Python 3.14+**: while running on to a breakpoint, only functions holding one are traced line
  by line; earlier, every function in its file was
- **Python 3.13+**: `post_mortem()` accepts an exception, and the `exceptions` command browses its
  chain
- **Python 3.12.9+, 3.13.1+**: `break` during a stop re-checks every frame on the stack
- **Python 3.12+**: `pm()` reads `sys.last_exc`

## Related Modules

- **[bdb](bdb.md)** - the tracing and breakpoint machinery `Pdb` is built on, priced per event
- **[sys](sys.md)** - `sys.settrace()`, `sys.monitoring` and `sys.breakpointhook()`
- **[traceback](traceback.md)** - formatting a traceback without stopping on it
- **[inspect](inspect.md)** - frames and source lines outside a debugger
