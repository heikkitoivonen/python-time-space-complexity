# traceback Module Complexity

The `traceback` module turns a traceback or a live stack into a `StackSummary` of
`FrameSummary` records, and turns those, together with the exception, into text. Every function
that prints or formats a traceback extracts all of it before it writes or returns a line, so
nothing here streams frames: the cost is the frames walked, paid up front.

`d` is the frames in one traceback or stack. `F` is the exceptions and frames across everything a
formatted exception includes: itself and its traceback, each `__cause__` and `__context__` it chains
to, and every member of an exception group, with theirs. `e` is the exceptions alone, `n` is a
`limit`, `s` is the characters in a source file, and `a` is the names searched for a "Did you mean"
suggestion, which has a row of its own and is left out of the others. A frame's source line, an
exception's message and its notes are priced O(1). Source lines come from `linecache`, which reads a
whole file the first time a line from it is needed, O(s), and serves later lookups from its cache.
Finding a stack frame's line number, and on Python 3.11+ a traceback frame's position, scans its
code object's location table up to the instruction being run: O(1) for an ordinary function, but in
proportion to that offset in a very long one, such as generated code.

## Complexity Reference

### Extracting frames

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `traceback.extract_tb(tb, limit=None)` | O(d) | O(d) | A `StackSummary`, oldest frame first; each frame's source line is read now |
| `traceback.extract_stack(f=None, limit=None)` | O(d) | O(d) | The stack above `f` (default: the caller), oldest first; stack frames carry no column positions |
| `traceback.walk_tb(tb)` | O(1) per step | O(1) | Generator of `(frame, lineno)` pairs following `tb_next` |
| `traceback.walk_stack(f)` | O(1) per step | O(1) | Generator following `f_back`, newest first |
| `limit=n` with `n >= 0` | O(n) | O(n) | The walk stops after `n` entries: the oldest `n` of a traceback, the newest `n` of a stack |
| `limit=-n` | O(d) | O(n) | Walks every entry and keeps the last `n` |
| `sys.tracebacklimit` | O(1) | O(1) | Used as `limit` when none is passed; a negative value there means no frames, not the last ones |
| `tb.tb_next`, `tb.tb_frame`, `tb.tb_lineno`, `tb.tb_lasti` | O(1) | O(1) | A traceback is a linked list with one node per frame |
| `traceback.clear_frames(tb)` | O(d) | O(1) | Clears the locals of every frame in the traceback, skipping one that is still executing |

### Formatting and printing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `traceback.format_tb(tb, limit=None)`, `traceback.print_tb(tb, limit=None, file=None)` | O(d) | O(d) | `extract_tb` then `StackSummary.format()`; printing holds the whole summary |
| `traceback.format_stack(f=None, limit=None)`, `traceback.print_stack(f=None, limit=None, file=None)` | O(d) | O(d) | `extract_stack` then format |
| `traceback.format_list(extracted_list)`, `traceback.print_list(extracted_list, file=None)` | O(d) | O(d) | Accepts `FrameSummary` objects or `(filename, lineno, name, line)` tuples |
| `traceback.format_exception(exc, /, value, tb, limit=None, chain=True)` | O(F) | O(F) | Builds a `TracebackException`; `limit` applies to each traceback in the chain |
| `traceback.print_exception(exc, /, value, tb, limit=None, file=None, chain=True)` | O(F) | O(F) | The same `TracebackException`, written a line at a time |
| `traceback.format_exc(limit=None, chain=True)`, `traceback.print_exc(limit=None, file=None, chain=True)` | O(F) | O(F) | The exception being handled |
| `traceback.print_last(limit=None, file=None, chain=True)` | O(F) | O(F) | The last exception that went unhandled, which the interpreter records; `ValueError` if there is none |
| `traceback.format_exception_only(exc, /, value, *, show_group=False)` | O(F) | O(F) | Skips the exception's own traceback but still builds its causes, contexts and group members, tracebacks included; for an exception with none of those, O(1). Prints the message and notes, plus the source line of a `SyntaxError`; `show_group=True` (3.13+) adds every nested group member |

### StackSummary and FrameSummary

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `traceback.StackSummary.extract(frame_gen, *, limit=None, lookup_lines=True, capture_locals=False)` | O(d) | O(d) | From `walk_tb()` or `walk_stack()` pairs; `lookup_lines=False` defers each source read to the line's first use |
| `capture_locals=True` | O(d + v) | O(d + v) | v = locals across the frames, each stored as its `repr()`, whose cost the caller's objects decide |
| `StackSummary.from_list(a_list)` | O(d) | O(d) | Wraps tuples as `FrameSummary`; keeps `FrameSummary` objects as they are |
| `StackSummary.format()` | O(d) | O(d) | One string per frame; a run of more than three identical frames prints three and a `[Previous line repeated k more times]` line |
| `StackSummary.format_frame_summary(frame_summary)` | O(1) | O(1) | Python 3.11+; override it to change how one frame renders, or return `None` to drop it |
| `traceback.FrameSummary(filename, lineno, name, *, lookup_line=True, locals=None, line=None)` | O(1) | O(1) | `lookup_line=True` reads the source line now; `line` supplies it instead |
| `FrameSummary.line` | O(1) | O(1) | Read from `linecache` on first access if it was deferred, then kept |
| `FrameSummary.filename`, `FrameSummary.lineno`, `FrameSummary.name`, `FrameSummary.locals` | O(1) | O(1) | Stored fields |
| `FrameSummary.end_lineno`, `FrameSummary.colno`, `FrameSummary.end_colno` | O(1) | O(1) | Python 3.11+; the columns are `None` for a frame from a stack rather than a traceback |

### TracebackException

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `traceback.TracebackException(exc_type, exc_value, exc_traceback, *, limit=None, lookup_lines=True, capture_locals=False, compact=False, max_group_width=15, max_group_depth=10)` | O(F) | O(F) | Extracts every traceback in the chain and every group member now, then holds no frame |
| `TracebackException.from_exception(exc, *, limit=None, ...)` | O(F) | O(F) | The constructor with type, value and traceback taken from `exc` |
| `TracebackException.format(*, chain=True)` | O(F) | O(F) | A generator; `chain=False` leaves out causes and contexts, not group members |
| `TracebackException.print(*, file=None, chain=True)` | O(F) | O(d + e) | Python 3.11+; writes each line as it is formatted, so only one traceback's lines are held at a time |
| `TracebackException.format_exception_only(*, show_group=False)` | O(1) | O(1) | A generator; `show_group=True` (3.13+) adds every nested group member, O(e) |
| `max_group_width`, `max_group_depth` | O(1) | O(1) | Cap the group members and nesting that are printed, not the ones extracted |
| `TracebackException.stack` | O(1) | O(1) | The `StackSummary` built with the object |
| `TracebackException.__cause__`, `TracebackException.__context__`, `TracebackException.__suppress_context__`, `TracebackException.__notes__` | O(1) | O(1) | Captured at construction; the chained ones are `TracebackException` objects; `__notes__` is Python 3.11+ |
| `TracebackException.exceptions` | O(1) | O(1) | Python 3.11+; the group's members as `TracebackException` objects, or `None` |
| `TracebackException.exc_type_str` | O(1) | O(1) | Python 3.13+; `exc_type` holds the class and is deprecated from 3.13 |
| `TracebackException.filename`, `TracebackException.lineno`, `TracebackException.end_lineno`, `TracebackException.text`, `TracebackException.offset`, `TracebackException.end_offset`, `TracebackException.msg` | O(1) | O(1) | Set for a `SyntaxError` only |
| "Did you mean" suggestion | O(d + a log a) | O(a) | Python 3.12+, at construction, for a `NameError`, an `AttributeError` or an `ImportError` from `from ... import`: a = the names in the raising frame's scopes, the object's attributes, or the module's names; d = the traceback followed to that frame, whatever the `limit` |

## Extracting vs Formatting

Both are linear in the frames. `format_tb()` and `print_tb()` extract and then render, so each
call pays for both; extract once and format from the summary rather than formatting the same
traceback twice.

```python
import traceback

def level_3():
    return 1 / 0

def level_2():
    return level_3()

def level_1():
    return level_2()

try:
    level_1()
except ZeroDivisionError as exc:
    error = exc

summary = traceback.extract_tb(error.__traceback__)  # O(d)
assert [frame.name for frame in summary] == ['<module>', 'level_1', 'level_2', 'level_3']
assert summary[-1].line == 'return 1 / 0'  # read from linecache during extraction

lines = summary.format()  # O(d) - one string per frame
assert len(lines) == 4
assert lines[-1].startswith('  File ')

text = ''.join(traceback.format_exception(error))  # O(F)
assert text.startswith('Traceback (most recent call last):\n')
assert text.endswith('ZeroDivisionError: division by zero\n')
```

## Limiting Depth

A non-negative `limit` stops the walk, so it bounds the time as well as the output. A negative
one keeps the last `n` entries, and the only way to find those is to walk them all.

```python
import traceback

def recurse(depth):
    if depth == 0:
        raise ValueError('bottom')
    recurse(depth - 1)

try:
    recurse(50)
except ValueError as exc:
    error = exc

full = traceback.extract_tb(error.__traceback__)  # O(d)
assert len(full) == 52

oldest = traceback.extract_tb(error.__traceback__, limit=3)  # O(n) - stops after 3
assert [frame.name for frame in oldest] == ['<module>', 'recurse', 'recurse']

newest = traceback.extract_tb(error.__traceback__, limit=-3)  # O(d) walk, O(n) kept
assert [frame.line for frame in newest][-1] == "raise ValueError('bottom')"

text = ''.join(traceback.format_exception(error, limit=3))  # O(F) with n per traceback
assert text.count('  File ') == 3
```

## Recursion in the Output

A run of identical frames - the same file, line and function, as deep recursion produces - is
printed three times followed by one summary line. The output stays short; every frame is still
extracted, so the time is still O(d).

```python
import traceback

def recurse(depth):
    if depth == 0:
        raise ValueError('bottom')
    recurse(depth - 1)

try:
    recurse(200)
except ValueError as exc:
    error = exc

summary = traceback.extract_tb(error.__traceback__)  # O(d)
assert len(summary) == 202

lines = summary.format()  # O(d) time, short output
assert len(lines) < 10
assert any('[Previous line repeated 197 more times]' in line for line in lines)
```

## Chains and Exception Groups

A formatted exception includes the exceptions it chains to, each with its own traceback, so `F`
counts all of them. `chain=False` prints the outer exception alone, after building the whole chain.
An exception group is extracted whole at construction; `max_group_width` and `max_group_depth` only
cap what is printed.

```python
import traceback

try:
    try:
        {}['missing']
    except KeyError as inner:
        raise RuntimeError('lookup failed') from inner
except RuntimeError as exc:
    error = exc

chained = ''.join(traceback.format_exception(error))  # O(F) - both tracebacks
assert 'KeyError' in chained and 'direct cause' in chained

alone = ''.join(traceback.format_exception(error, chain=False))  # builds O(F), prints d
assert 'KeyError' not in alone

group = ExceptionGroup('batch', [ValueError(index) for index in range(100)])
summary = traceback.TracebackException.from_exception(group, max_group_width=5)  # O(F)
assert len(summary.exceptions) == 100  # every member was extracted

text = ''.join(summary.format())  # prints five
assert 'and 95 more exceptions' in text
```

## Source Lines and linecache

A frame's source line comes from `linecache`. The first line needed from a file reads the whole
file; every later one, in this traceback or the next, is a cache hit while the file is unchanged.
`lookup_lines=False` defers the read until something asks for the line, which is worth it when a
summary may never be rendered.

```python
import traceback

def fail():
    raise ValueError('boom')

try:
    fail()
except ValueError as exc:
    error = exc

frames = traceback.walk_tb(error.__traceback__)  # O(1) - a generator
summary = traceback.StackSummary.extract(frames, lookup_lines=False)  # O(d), no reads
assert [frame.name for frame in summary] == ['<module>', 'fail']

assert summary[-1].line == "raise ValueError('boom')"  # read on first access, then kept

# A summary can also be rebuilt from plain tuples
rebuilt = traceback.StackSummary.from_list([('app.py', 10, 'main', 'run()')])  # O(d)
assert rebuilt.format() == ['  File "app.py", line 10, in main\n    run()\n']
```

## Suggestions for Name and Attribute Errors

On Python 3.12+, building a `TracebackException` for a `NameError` or `AttributeError` searches
the names in scope, or the object's attributes, for a close match and adds a "Did you mean"
hint. That search is linear in those names, and sorting an object's attributes makes it
O(a log a), so formatting such an error costs more on an object with many attributes or in a
module with many globals.

```python
import traceback

class Config:
    timeout = 5

try:
    Config().timeuot
except AttributeError as exc:
    error = exc

message = traceback.format_exception_only(error)[-1]  # O(a log a) for the suggestion
assert message.startswith("AttributeError: 'Config' object has no attribute 'timeuot'")
assert "Did you mean: 'timeout'?" in message
```

## Keeping a Failure Without Its Frames

A traceback keeps every frame on it alive, and with them every local variable. A
`TracebackException` copies out the text it needs and holds no frame, so it is the way to keep a
failure around; `clear_frames()` releases the locals of a traceback you still hold.

```python
import traceback
import weakref

class Payload:
    pass

refs = []

def fail():
    payload = Payload()
    refs.append(weakref.ref(payload))
    raise ValueError('boom')

try:
    fail()
except ValueError as exc:
    error = exc

assert refs[0]() is not None  # the traceback keeps fail()'s locals alive

summary = traceback.TracebackException.from_exception(error)  # O(F)
traceback.clear_frames(error.__traceback__)  # O(d)
assert refs[0]() is None

assert ''.join(summary.format()).endswith('ValueError: boom\n')
```

## Common Patterns

### Collecting Failures From a Batch

```python
import traceback

def process(item):
    if item % 3 == 0:
        raise ValueError(f'bad item {item}')
    return item * 2

failures = []
for item in range(10):
    try:
        process(item)
    except ValueError as exc:
        # O(F) now; holds no frames, so the batch keeps no locals alive
        failures.append(traceback.TracebackException.from_exception(exc, limit=5))

assert len(failures) == 4
report = ''.join(''.join(failure.format()) for failure in failures)  # O(F) each
assert report.count('Traceback (most recent call last):') == 4
assert 'ValueError: bad item 9' in report
```

### Recording the Current Exception

```python
import io
import traceback

log = io.StringIO()

try:
    int('not a number')
except ValueError:
    details = traceback.format_exc(limit=10)  # O(F), n = 10 per traceback
    log.write(details)
    traceback.print_exc(file=log)  # O(F) again - reuse `details` instead

assert log.getvalue().count("invalid literal for int() with base 10: 'not a number'") == 2
```

## Performance Best Practices

✅ **Do**:

- Pass a non-negative `limit` when you only need the outermost frames: it stops the walk
- Keep a `TracebackException` rather than the exception when a failure must outlive its handler
- Extract once and format from the `StackSummary`, rather than calling `format_*` and `print_*`
  on the same traceback
- Use `lookup_lines=False` when a summary may never be rendered

❌ **Avoid**:

- `capture_locals=True` outside debugging: it calls `repr()` on every local of every frame
- Relying on `max_group_width` to make a huge exception group cheap: every member is still
  extracted
- A negative `limit` on a deep traceback to save time: it walks every frame to find the last `n`
- Holding exceptions in a long-lived list: each keeps its whole stack of frames and locals alive

## Version Notes

- **Python 3.11+**: Tracebacks mark the failing expression, `FrameSummary` gains `end_lineno`,
  `colno` and `end_colno`, exception groups are formatted, and
  `StackSummary.format_frame_summary()` and `TracebackException.print()` are added
- **Python 3.12+**: `TracebackException` adds "Did you mean" suggestions for `NameError`,
  `AttributeError` and `ImportError`, and `print_last()` reads `sys.last_exc`
- **Python 3.13+**: `format_exception_only()` takes `show_group`, and
  `TracebackException.exc_type_str` replaces the deprecated `exc_type`

## Related Modules

- **[linecache](linecache.md)** - where source lines come from, and what caching them costs
- **[sys](sys.md)** - `sys.exception()`, `sys.tracebacklimit` and `sys.last_exc`
- **[logging](logging.md)** - `logger.exception()` formats the current traceback for you
- **[faulthandler](faulthandler.md)** - dumps tracebacks on a crash, without Python-level formatting
- **[inspect](inspect.md)** - frame and stack inspection beyond what a summary keeps
- **[Exceptions](../builtins/exceptions.md)** - chaining, notes and exception groups
