# cgitb Module Complexity

The `cgitb` module formats a traceback as a detailed HTML or plain-text report: for every frame it
shows the surrounding source lines and the values of the names on the failing line. Installing it
costs nothing; the whole cost lands when an exception is formatted, and the report is built as one
string before it is written.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The examples that import it
    need Python 3.10, 3.11 or 3.12; new code should use `traceback` and `logging`.

`d` is the frames in the traceback and `c` is the source lines shown per frame (`context`, 5 by
default, at least 1). The bounds count frames and lines, pricing one source line, each frame's
failing statement with the names in it, and the exception message as O(1). They exclude the
`repr()` of the values shown, which is your objects' cost, and the first read of each source file,
which `linecache` then keeps.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cgitb.enable(display=1, logdir=None, context=5, format="html")` | O(1) | O(1) | Replaces `sys.excepthook` with a `Hook` writing to the current `sys.stdout`; nothing is formatted until an uncaught exception reaches it |
| `cgitb.handler(info=None)` | O(d·c) | O(d·c) | Reports `info`, or `sys.exc_info()` when omitted, as HTML to the `sys.stdout` that was current when `cgitb` was imported |
| `cgitb.html(info, context=5)` | O(d·c) | O(d·c) | Returns the HTML report as a string and writes nothing |
| `cgitb.text(info, context=5)` | O(d·c) | O(d·c) | Returns the plain-text report as a string and writes nothing |

### Hook

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cgitb.Hook(display=1, logdir=None, context=5, file=None, format="html")` | O(1) | O(1) | `file` defaults to the `sys.stdout` current when the hook is built |
| `Hook.handle(info=None)` | O(d·c) | O(d·c) | Builds the whole report even with `display=0`, which only stops it being written to `file`; with `logdir`, each call writes it to a new file there |
| Calling a `Hook(etype, evalue, etb)` | O(d·c) | O(d·c) | The `sys.excepthook` signature; calls `handle()` and returns `None` |

## Installing the Handler

`enable()` only swaps `sys.excepthook`. An exception you catch never reaches the hook; one that
escapes the script does, and that is when the report is formatted.

```python
import contextlib
import io
import sys

import cgitb  # Python 3.10-3.12 only

out = io.StringIO()
original = sys.excepthook
with contextlib.redirect_stdout(out):
    cgitb.enable(format='text')  # O(1) - the hook keeps the sys.stdout current now
assert isinstance(sys.excepthook, cgitb.Hook)

try:
    1 / 0
except ZeroDivisionError:
    pass  # caught: the hook never sees it
assert out.getvalue() == ''

# What the interpreter does with an uncaught exception
try:
    1 / 0
except ZeroDivisionError:
    sys.excepthook(*sys.exc_info())  # O(d·c)
assert 'ZeroDivisionError' in out.getvalue()

sys.excepthook = original
```

## Formatting a Caught Exception

`html()` and `text()` return the report and write nothing. `Hook.handle()` writes it to the hook's
`file`; `cgitb.handler()` is the same method on a hook built at import time, so it writes to that
`sys.stdout` even after you redirect it.

```python
import io
import sys

import cgitb  # Python 3.10-3.12 only

def parse(value):
    return int(value)

try:
    parse('not a number')
except ValueError:
    info = sys.exc_info()

page = cgitb.html(info)  # O(d·c) - one string, nothing written
assert '<body' in page and 'ValueError' in page

report = cgitb.text(info, context=1)  # O(d·c)
assert "value = 'not a number'" in report

out = io.StringIO()
hook = cgitb.Hook(file=out, format='text')  # O(1)
assert hook.handle(info) is None  # O(d·c) - the report goes to file
assert 'invalid literal' in out.getvalue()
```

## Traceback Depth and Context

Every frame gets up to `c` lines of source, where its file has them, and a dump of the names on its
failing line, so the report grows with the stack and with `context`.

```python
import re
import sys

import cgitb  # Python 3.10-3.12 only

def recurse(depth):
    if depth == 0:
        raise ValueError('bottom')
    recurse(depth - 1)

def report(depth, context):
    try:
        recurse(depth)
    except ValueError:
        return cgitb.text(sys.exc_info(), context)  # O(d·c)

def source_lines(text):
    return sum(1 for line in text.splitlines() if re.match(r' *[0-9]+ ', line))

assert source_lines(report(100, 1)) - source_lines(report(10, 1)) == 90  # one per extra frame
assert source_lines(report(10, 3)) == 3 * source_lines(report(10, 1))  # c per frame
```

## Logging Reports to a Directory

With `logdir`, each handled exception becomes a new file there. `display=0` keeps the report off
`file`, but it is still built in full, so it saves the writing, not the formatting.

```python
import io
import os
import tempfile

import cgitb  # Python 3.10-3.12 only

with tempfile.TemporaryDirectory() as logdir:
    out = io.StringIO()
    hook = cgitb.Hook(display=0, logdir=logdir, file=out, format='text')  # O(1)

    for _ in range(2):
        try:
            1 / 0
        except ZeroDivisionError:
            hook.handle()  # O(d·c) - formatted, then written to a new file

    names = os.listdir(logdir)
    assert len(names) == 2 and all(name.endswith('.txt') for name in names)
    assert 'ZeroDivisionError' not in out.getvalue()
    assert 'contains the description of this error' in out.getvalue()
```

## Replacing cgitb

From Python 3.13 there is no `cgitb`. `traceback.format_exception()` shows each frame's failing
source but no variable values, and `html.escape()` makes it safe to put in a page.

```python
import html
import traceback

def render_error(error):
    text = ''.join(traceback.format_exception(error))  # O(d)
    return '<pre>' + html.escape(text) + '</pre>'

try:
    {}['missing']
except KeyError as error:
    page = render_error(error)

assert page.startswith('<pre>Traceback') and 'KeyError: &#x27;missing&#x27;' in page
```

## Performance Best Practices

✅ **Do**:

- Install with `enable()` at the top of a script: it costs nothing until an exception escapes
- Lower `context` for deep stacks; the report grows with frames times context lines
- Use `html()` or `text()` when you want the report as a string rather than written out

❌ **Avoid**:

- `display=0` as a way to save work - the report is still built, only not written
- `cgitb.handler()` after redirecting `sys.stdout` - it writes to the stream current at import
- Showing reports to users: they include local variable values

## Version Notes

- **Python 3.11+**: Importing the module emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import cgitb` raises `ModuleNotFoundError`

## Related Modules

- **[traceback](traceback.md)** - the replacement; formats a traceback without variable values
- **[logging](logging.md)** - `logging.exception()` writes the traceback to a log rather than to the page
- **[linecache](linecache.md)** - the source-line cache the reports read from
- **[cgi](cgi.md)** - the CGI module removed alongside it
