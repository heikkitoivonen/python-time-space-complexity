# bdb Module Complexity

The `bdb` module is the machinery under `pdb`. `Bdb` installs a trace function, receives the
events it asks for, and decides at each one whether to stop and hand control to a subclass's
`user_*` method. A debugged program pays per event, so which events arrive, not the size of the
program, is what the cost turns on.

Breakpoints live in two class-level registries on `Breakpoint`, shared by every `Bdb` in the
process. Each `Bdb` also keeps, per file, a list of the lines holding a breakpoint.

`e` is the trace events delivered while the debugged code runs, `d` is frames on the stack, `p`
is skip patterns, `b` is lines holding a breakpoint in the file being checked, `k` is breakpoints
at one line, `L` is file:line locations holding a breakpoint across all files, `B` is breakpoint
numbers ever assigned, deleted ones included, and `c` is files in the `linecache` cache. File
names, module names, source lines and breakpoint conditions are priced at O(1); evaluating a
condition costs whatever its expression does, and a subclass's `user_*` methods cost whatever
they do. One-time cache fills are left out of the bounds: `linecache` reading a whole file the
first time a line of it is needed, `canonic()` resolving a new file name, and on 3.14+
`break_anywhere()` recording a code object's line numbers the first time it sees it. Bounds are
for the default `'settrace'` backend.

## Complexity Reference

### Bdb

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bdb.Bdb(skip=None, backend='settrace')` | O(p + L·b) | O(p + L) | Copies every breakpoint location already registered, by any instance, checking each against its file's lines so far; `backend` is 3.14+ |
| `Bdb.run(cmd, globals=None, locals=None)`, `Bdb.runeval(expr, globals=None, locals=None)`, `Bdb.runctx(cmd, globals, locals)` | O(c + e·(p + b + k)) | O(c) | Plus the code's own cost; a string is compiled first, and `BdbQuit` ends the run quietly |
| `Bdb.runcall(func, /, *args, **kwds)` | O(c + e·(p + b + k)) | O(c) | Plus the call's own cost; returns what `func` returns |
| `Bdb.reset()` | O(c) | O(c) | Revalidates every file in `linecache`; the `run*` methods and `set_trace()` call it |
| `Bdb.set_trace(frame=None)` | O(c + d) | O(c + d) | Hooks every frame on the stack; 3.13+ stops at once and keeps each frame's trace flags until a `set_continue()` with no breakpoints set |
| `Bdb.start_trace()`, `Bdb.stop_trace()` | O(1) | O(1) | 3.14+; install or remove the trace function |
| `Bdb.canonic(filename)` | O(1) | O(1) | Cached per name in `fncache`; a name in angle brackets such as `<string>` comes back unchanged |

### Bdb event dispatch

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Bdb.trace_dispatch(frame, event, arg)` | O(p + b + k) | O(1) | One event, handed to the matching `dispatch_*` method |
| `Bdb.dispatch_line(frame)` | O(p + b + k) | O(1) | The k term and the conditions evaluated come from `effective()`, on a line holding breakpoints |
| `Bdb.dispatch_call(frame, arg)` | O(p + b) | O(1) | Returns `None` for a frame that cannot stop, so its lines raise no events |
| `Bdb.dispatch_return(frame, arg)`, `Bdb.dispatch_exception(frame, arg)` | O(p) | O(1) | |
| `Bdb.stop_here(frame)`, `Bdb.is_skipped_module(module_name)` | O(p) | O(1) | One `fnmatch` per skip pattern, up to the first that matches |
| `Bdb.break_here(frame)` | O(b + k) | O(1) | Checks the line, then the function's first line for a breakpoint set by function name |
| `Bdb.break_anywhere(frame)` | O(b) | O(1) | 3.14+ looks for the file's breakpoint lines in the frame's code, caching each code object's lines on first use; earlier it is O(1), and any breakpoint in the file counts |
| `Bdb.user_call(frame, argument_list)`, `Bdb.user_line(frame)`, `Bdb.user_return(frame, return_value)`, `Bdb.user_exception(frame, exc_info)` | O(1) | O(1) | Do nothing; a subclass overrides them, and their cost is added at every stop |
| `Bdb.do_clear(arg)` | O(1) | O(1) | Raises `NotImplementedError`; a subclass supplies it to delete a temporary breakpoint once hit |
| `Bdb.disable_current_event()`, `Bdb.restart_events()` | O(1) | O(1) | 3.14+; do nothing under the `'settrace'` backend |

### Bdb stepping

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Bdb.set_step()`, `Bdb.set_next(frame)`, `Bdb.set_return(frame)`, `Bdb.set_until(frame, lineno=None)` | O(1) | O(1) | Record where to stop next; on 3.13+ the first of these or `set_continue()` after `set_trace()` walks the stack, O(d), to end instruction stepping |
| `Bdb.set_continue()` | O(1) | O(1) | With no breakpoints set it removes tracing, O(d), and the code runs on untraced |
| `Bdb.set_quit()` | O(1) | O(1) | The dispatch that called it raises `BdbQuit` |

### Bdb breakpoints

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Bdb.set_break(filename, lineno, temporary=False, cond=None, funcname=None)` | O(b + d·b) | O(1) | Returns an error string for a line that does not exist; during a stop, 3.12+ also runs `break_anywhere()` on every frame of the stack |
| `Bdb.clear_break(filename, lineno)` | O(b + k²) | O(k) | Each deletion shifts the rest of that line's list |
| `Bdb.clear_bpbynumber(arg)` | O(b + k) | O(1) | |
| `Bdb.clear_all_file_breaks(filename)` | O(b·k²) | O(1) | At a line holding several breakpoints, every second one survives in `Breakpoint.bplist` |
| `Bdb.clear_all_breaks()` | O(B·k) | O(1) | Walks every number ever assigned, deleted ones included |
| `Bdb.get_bpbynumber(arg)` | O(1) | O(1) | Raises `ValueError` for a non-numeric, unknown or deleted number |
| `Bdb.get_break(filename, lineno)` | O(b) | O(1) | |
| `Bdb.get_breaks(filename, lineno)` | O(b) | O(1) | The registry's own list, not a copy |
| `Bdb.get_file_breaks(filename)` | O(1) | O(1) | The instance's own list of lines, not a copy |
| `Bdb.get_all_breaks()` | O(1) | O(1) | The instance's own dict, not a copy |

### Bdb stack inspection

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Bdb.get_stack(f, t)` | O(d + t) | O(d + t) | t = traceback entries; returns `(frame, lineno)` pairs and the index of `f` |
| `Bdb.format_stack_entry(frame_lineno, lprefix=': ')` | O(1) | O(1) | Plus `reprlib.repr()` of a return value: it shortens the text, but sorts a dict's or set's keys first |

### Breakpoint

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bdb.Breakpoint(file, line, temporary=False, cond=None, funcname=None)` | O(1) | O(1) | Takes the next number and joins the class-level `bpbynumber` and `bplist` |
| `Breakpoint.deleteMe()` | O(k) | O(1) | Leaves `None` at its number: numbers are never reused |
| `Breakpoint.enable()`, `Breakpoint.disable()` | O(1) | O(1) | A disabled breakpoint is passed over without counting a hit |
| `Breakpoint.bpformat()`, `Breakpoint.bpprint(out=None)` | O(1) | O(1) | `bpprint()` writes `bpformat()` to `out`, `sys.stdout` by default |
| `Breakpoint.file`, `Breakpoint.line`, `Breakpoint.temporary`, `Breakpoint.cond`, `Breakpoint.funcname`, `Breakpoint.enabled`, `Breakpoint.ignore`, `Breakpoint.hits` | O(1) | O(1) | Plain attributes; `effective()` updates `hits` and `ignore` |
| `Breakpoint.bpbynumber`, `Breakpoint.bplist` | O(1) | O(1) | The shared registries: a list indexed by number and a dict of lists keyed by `(file, line)` |

### Module functions and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bdb.effective(file, line, frame)` | O(k) | O(1) | Plus each condition it evaluates; returns the first enabled breakpoint whose condition holds and whose ignore count is spent, or whose condition raises |
| `bdb.checkfuncname(b, frame)` | O(1) | O(1) | |
| `bdb.set_trace()` | O(c + d + L·b) | O(c + d + L) | Builds a `Bdb` and calls its `set_trace()` |
| `bdb.BdbQuit` | O(1) | O(1) | Raised to end a run; the `run*` methods catch it |

## Writing a Debugger

A subclass overrides the `user_*` methods and, at each stop, calls one of the `set_*` methods to
say where to stop next. A run starts by stopping at the first line, so a `set_step()` at every
stop visits every line event.

```python
import bdb

class Recorder(bdb.Bdb):
    def __init__(self):
        super().__init__()
        self.stops = []

    def user_line(self, frame):  # called at every stop
        self.stops.append(frame.f_lineno - work.__code__.co_firstlineno)
        self.set_step()  # O(1) - stop again at the next line

def work():
    total = 0
    for i in range(3):
        total += i
    return total

debugger = Recorder()
assert debugger.runcall(work) == 3  # O(c + e·(p + b + k)), plus work's own cost
assert set(debugger.stops) == {1, 2, 3, 4}  # every line of work, some of them repeatedly
```

## What Gets Traced

With the `'settrace'` backend, every call raises a call event, and `dispatch_call()` returns
`None` for a frame that cannot stop, so that frame raises no line events. A frame already being
traced, such as the one a stop happened in, raises one per line executed, at O(p + b) each away
from breakpoints. `set_continue()` with no breakpoints set removes tracing altogether.

```python
import bdb

class Counter(bdb.Bdb):
    def __init__(self):
        super().__init__()
        self.line_events = 0

    def dispatch_line(self, frame):
        self.line_events += 1
        return super().dispatch_line(frame)

    def user_line(self, frame):
        self.set_continue()  # O(1) - run on to the next breakpoint

def loop(n):
    total = 0
    for i in range(n):
        total += i
    return total

def caller(n):
    return loop(n)

def line_events(func, n, with_breakpoint):
    bdb.Breakpoint.clearBreakpoints()  # the registry is shared by every Bdb
    debugger = Counter()
    if with_breakpoint:
        # A breakpoint in another file, in a function that never runs
        line = bdb.effective.__code__.co_firstlineno + 1
        assert debugger.set_break(bdb.__file__, line) is None
    debugger.runcall(func, n)
    return debugger.line_events

# No breakpoints: continuing removes tracing, so only the first stop counts
assert line_events(loop, 10_000, with_breakpoint=False) == 1

# A breakpoint elsewhere: loop() cannot stop, so its lines raise no events
assert line_events(caller, 10_000, with_breakpoint=True) == 1

# The frame the stop happened in keeps raising them, once per line: O(n)
assert line_events(loop, 10_000, with_breakpoint=True) > 10_000
```

On 3.13 and earlier, `dispatch_call()` treats any breakpoint in a frame's file as a reason to
trace it, so while running on to a breakpoint every function called in that file raises line
events. From 3.14 only a function whose code holds the breakpoint does, and `Bdb(backend='monitoring')` goes further: it can switch off a line
event that cannot stop, rather than receive it on every execution.

### Skipping Modules

`skip` takes glob patterns for module names. Stepping never stops in a frame from a matching
module, but an event can pay O(p) to match the frame's module against the patterns.

```python
import bdb
import json

class Stepper(bdb.Bdb):
    def __init__(self, skip=None):
        super().__init__(skip=skip)  # O(p) to store the patterns
        self.modules = set()

    def user_line(self, frame):
        self.modules.add(frame.f_globals.get('__name__'))
        self.set_step()

def work():
    return json.dumps([1, 2])

stepper = Stepper()
stepper.runcall(work)
assert 'json.encoder' in stepper.modules

skipping = Stepper(skip=['json', 'json.*'])
skipping.runcall(work)
assert skipping.modules == {'__main__'}
```

## Managing Breakpoints

Each `Bdb` keeps its breakpoint lines in one list per file, so finding a line is O(b). The
`Breakpoint` objects themselves live in the shared registries: a `Bdb` built later sees every
location registered so far, and a deleted breakpoint leaves `None` at its number for good.

```python
import bdb

bdb.Breakpoint.clearBreakpoints()  # start from an empty registry
first = bdb.Bdb()
filename = first.canonic(bdb.__file__)  # O(1) once cached
line = bdb.effective.__code__.co_firstlineno + 1

assert first.set_break(filename, line) is None  # O(b) outside a stop
assert first.set_break(filename, line, cond='False') is None
assert len(first.get_breaks(filename, line)) == 2  # O(b)
assert first.get_file_breaks(filename) == [line]  # O(1)
assert first.set_break(filename, 10**6) == f'Line {filename}:1000000 does not exist'

# A Bdb built later copies every registered location - O(L·b)
second = bdb.Bdb()
assert second.get_break(filename, line)  # O(b)

# Deleting by number leaves None behind: numbers are never reused
assert first.clear_bpbynumber('1') is None  # O(b + k)
assert bdb.Breakpoint.bpbynumber[1] is None
try:
    first.get_bpbynumber('1')  # O(1)
except ValueError as error:
    assert 'already deleted' in str(error)
else:
    raise AssertionError('a deleted breakpoint was found')

assert first.clear_all_breaks() is None  # O(B·k), deleted numbers included
assert first.get_all_breaks() == {}
```

### Choosing the Active Breakpoint

`effective()` walks the k breakpoints at a line in the order they were set. It passes over a
disabled one without counting a hit, and one set on a function name unless this is the function's
first line; every other one it reaches counts a hit. The first whose condition holds and whose
ignore count is spent is the one that stops, and so is one whose condition raises.

```python
import bdb
import sys

def here():
    return sys._getframe()

frame = here()
file, line = frame.f_code.co_filename, frame.f_lineno

bdb.Breakpoint.clearBreakpoints()
off = bdb.Breakpoint(file, line)  # O(1)
off.disable()
never = bdb.Breakpoint(file, line, cond='False')
second_hit = bdb.Breakpoint(file, line)
second_hit.ignore = 1

assert bdb.effective(file, line, frame) == (None, None)  # O(k), ignore count spent
assert bdb.effective(file, line, frame) == (second_hit, True)
assert (off.hits, never.hits, second_hit.hits) == (0, 2, 2)
```

### Clearing a File's Breakpoints

`clear_all_file_breaks()` deletes breakpoints from a line's list while iterating over it, so at a
line holding several, every second one survives. The instance forgets the file anyway, but the
survivors stay in `Breakpoint.bplist`, and a `Bdb` built later picks them up again.
`clear_break()` iterates over a copy and removes them all.

```python
import bdb

bdb.Breakpoint.clearBreakpoints()
debugger = bdb.Bdb()
filename = debugger.canonic(bdb.__file__)
line = bdb.effective.__code__.co_firstlineno + 1
for _ in range(4):
    debugger.set_break(filename, line)

assert debugger.clear_all_file_breaks(filename) is None  # O(b·k²)
assert debugger.get_file_breaks(filename) == []
assert len(bdb.Breakpoint.bplist[filename, line]) == 2

later = bdb.Bdb()  # O(L·b) - sees the survivors
assert later.clear_break(filename, line) is None  # O(b + k²)
assert (filename, line) not in bdb.Breakpoint.bplist
```

## Inspecting the Stack

`get_stack()` walks the stack and then the traceback, collecting `(frame, lineno)` pairs.
`format_stack_entry()` formats one of them; a return value is cut short by `reprlib`, so a long
list costs no more than a short one.

```python
import bdb
import sys

def depth(n):
    return depth(n - 1) if n else sys._getframe()

def returns_big():
    __return__ = list(range(100_000))
    return sys._getframe()

debugger = bdb.Bdb()
debugger.reset()  # O(c)

frame = depth(50)
stack, index = debugger.get_stack(frame, None)  # O(d + t)
assert stack[-1][0] is frame and index == len(stack) - 1
assert len(stack) > 50

frame = returns_big()
entry = debugger.format_stack_entry((frame, frame.f_lineno))  # O(1)
assert '->[0, 1, 2, 3, 4, 5, ...]' in entry
```

## Common Patterns

### Logging a Conditional Breakpoint

A debugger that records a value each time a conditional breakpoint fires and runs on. Only the
frame the run first stopped in is traced, so each of its lines costs O(p + b), and the breakpoint
line adds O(k) and its condition.

```python
import bdb

class HitLogger(bdb.Bdb):
    def __init__(self):
        super().__init__()
        self.seen = []

    def user_line(self, frame):
        if self.get_break(frame.f_code.co_filename, frame.f_lineno):  # O(b)
            self.seen.append(frame.f_locals['i'])
        self.set_continue()  # O(1) while a breakpoint is set

def work(n):
    total = 0
    for i in range(n):
        total += i
    return total

bdb.Breakpoint.clearBreakpoints()
logger = HitLogger()
line = work.__code__.co_firstlineno + 3
assert logger.set_break(__file__, line, cond='i % 25 == 0') is None
assert logger.runcall(work, 100) == 4950
assert logger.seen == [0, 25, 50, 75]
```

## Performance Best Practices

✅ **Do**:

- Call `set_continue()` when nothing is left to stop at: with no breakpoints it removes tracing
  and the code runs at full speed
- Put breakpoints in the functions you are debugging; on 3.13 and earlier, running on to one traces
  every function called in its file line by line
- Use `Bdb(backend='monitoring')` on 3.14+ for long runs between stops
- Clear breakpoints with `clear_break()` or `clear_all_breaks()`, which remove every one at a line

❌ **Avoid**:

- Stepping with `set_step()` through code you do not need to see; every line event outside a
  skipped module reaches `user_line()`
- Long `skip` lists: an event matches the frame's module against every pattern until one fits
- `clear_all_file_breaks()` on a line holding several breakpoints; every second one survives

## Version Notes

- **Python 3.14+**: `Bdb(backend='monitoring')` runs on `sys.monitoring`; `start_trace()`,
  `stop_trace()`, `disable_current_event()` and `restart_events()` added
- **Python 3.14+**: `break_anywhere()` looks for a breakpoint in the frame's own code, so while
  running on to a breakpoint only a called function holding one raises line events; earlier, every
  function in its file did
- **Python 3.13+**: `set_trace()` stops at once, on the next instruction, rather than on the next
  line
- **Python 3.12+**: `set_break()` during a stop re-checks every frame on the stack

## Related Modules

- **[pdb](pdb.md)** - the interactive debugger built on `Bdb`
- **[sys](sys.md)** - `sys.settrace()` and `sys.monitoring`, the two tracing backends
- **[linecache](linecache.md)** - the source-line cache that `reset()` revalidates
