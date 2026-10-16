# help() Function Complexity

`help` is the interactive documentation browser. It is a `_sitebuiltins._Helper` instance that
the `site` module installs into builtins; calling it imports [pydoc](../stdlib/pydoc.md) the
first time and hands the request to `pydoc.help`. That renders the page from the live object
every time - nothing is cached - and sends it to a pager: one such as `less` on a terminal, plain
text to `sys.stdout` otherwise. `help()` returns `None`.

`w` is the characters of documentation produced, counting the full `repr()` of any value that is
built and then cut short. **D** is the cost of documenting one object, which
the [pydoc page](../stdlib/pydoc.md) prices in full: O(w) for a function, method or value; for a
class, O(a log a + a·d² + w) plus O(s log s), where `a` is its attributes, inherited ones
included, `d` the classes in its method resolution order and `s` its direct subclasses; for a
module of `M` names, at least O(M log M + w) plus the cost of each class it documents. An object without a docstring can add O(F) to read its
source file of `F` characters. `x` is the dotted parts of a name given as a string. Names count as O(1) characters, and the import system's
own work - finding a module and running it - is not counted.

## Complexity Reference

### help

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `help` (the bare name) | O(1) | O(1) | `repr()` is a hint naming `help()` and `help(object)` |
| `help(object)` | O(D) | O(M + a + s + w) | Renders and pages the object's documentation; an instance is documented through its class |
| `help('name')` | O(x² + D) | O(M + a + s + w) | A string is a name to look up, not a value: each dotted prefix that is a module is imported, then attributes are followed. A name that finds nothing prints `No Python documentation found` |
| `help('if')` and other keywords, symbols and topics | O(T) the first time, then O(z) | O(T), then O(z) | The text from [pydoc_data](../stdlib/pydoc_data.md), imported on first use; T = all topic text, z = this topic's |
| `help('keywords')`, `help('symbols')`, `help('topics')` | O(1) | O(1) | Fixed lists of under a hundred names each |
| `help('modules')` | O(N log N) plus importing every package | O(N) | N = files and directories on `sys.path`; lists the top-level module names |
| `help('modules key')` | O(N + S) plus importing every package | O(N + y) | Every module whose name or synopsis contains `key`; S = the characters of all the modules' source, y = the largest |
| `help()` | O(t) per line, plus each request | O(t) | The interactive helper, reading `sys.stdin`; t = characters in one line |

## What help Is

`help` is a callable instance, not a function. Its `repr()` is the hint the interactive prompt
prints for the bare name.

```python
import types

assert type(help).__name__ == '_Helper'                    # O(1)
assert not isinstance(help, types.FunctionType)
assert repr(help).startswith('Type help() for interactive help')
```

The `site` module installs it, so it does not exist under `-S`:

```
$ python -S -c "help(len)"
NameError: name 'help' is not defined
```

## Where the Output Goes

The text goes to the pager `pydoc` picks on first use. When standard input or output is not a
terminal that is the plain pager, which writes to `sys.stdout`; on a terminal it is a program
such as `less`, which waits for keys. The call returns `None`, so code that needs the text calls
`pydoc.render_doc()` instead, which returns the same page as a string.

```python
import contextlib
import io
import pydoc

captured = io.StringIO()
with contextlib.redirect_stdout(captured):  # not a terminal, so the plain pager
    result = help(len)  # O(w)

assert result is None
assert captured.getvalue().startswith('Help on built-in function len in module builtins')

text = pydoc.render_doc(len, renderer=pydoc.plaintext)  # O(w) - the page as a string
assert 'len(obj, /)' in text
```

For just the docstring, read `__doc__`. A function or class written in Python returns the string
it stores, in O(1); a built-in one builds a new string from its C docstring on each read, linear
in that string's length. Neither renders a page.

```python
def area(r):
    """Area of a circle of radius r."""

assert area.__doc__ is area.__doc__  # O(1) - the stored string
assert len.__doc__ == len.__doc__  # a new string on each read
```

## What a Request Costs

### Objects

Documenting a class lists every attribute, inherited ones included, and finds where each is
defined by walking the method resolution order. An instance gets its class's page. Every call
renders the page again.

```python
import contextlib
import io

class Base:
    def method(self):
        """Do something."""

class Child(Base):
    pass

captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    help(Child)  # O(a log a + a·d² + w) - inherited members are listed too
    help(Child())  # the same page again, rendered again

page = captured.getvalue()
assert page.count('Methods inherited from Base') == 2
assert 'Help on Child in module __main__ object' in page
```

### Strings Are Names

A non-empty string is looked up as a name - a keyword, a topic, or a dotted path to a module or an
object - rather than documented as a `str`. A module name is imported, so its code runs.

```python
import contextlib
import io
import sys

assert 'colorsys' not in sys.modules

captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    help('hello')  # not a name anything has
    help('colorsys')  # O(x² + D) - imports the module, then documents it
    help('if')  # O(T) the first time - the language reference's text for `if`

answer = captured.getvalue()
assert "No Python documentation found for 'hello'" in answer
assert 'colorsys' in sys.modules
assert 'The "if" statement' in answer
```

`help('modules')` and `help('modules key')` walk every module on `sys.path` and import every
package to look inside it, as `pydoc`'s [module search](../stdlib/pydoc.md#searching-modules)
does.

## The Interactive Helper

`help()` with no argument prints an introduction and then reads one request per line at a
`help>` prompt, until `q`, `quit` or `exit`, or the end of input. Each line costs what the same
string passed to `help()` would. An empty line leaves the helper before Python 3.13.12 and 3.14.3,
and returns to the prompt from those releases.

```python
import contextlib
import io
import sys

saved = sys.stdin
sys.stdin = io.StringIO('len\nkeywords\nq\n')  # stands in for typing at the prompt
captured = io.StringIO()
try:
    with contextlib.redirect_stdout(captured):
        help()  # O(t) per line, plus each request
finally:
    sys.stdin = saved

answer = captured.getvalue()
assert answer.count('\nhelp> ') == 3  # one prompt per line read
assert 'Help on built-in function len in module builtins' in answer
assert 'nonlocal' in answer  # from the keyword list
```

## Performance Best Practices

✅ **Do**:

- Pass the object rather than its name when you have it: no lookup and no import
- Call `pydoc.render_doc()` when code needs the text; `help()` returns `None`
- Read `__doc__` when the docstring is all you need: no page is rendered

❌ **Avoid**:

- Calling `help()` from a program: on a terminal it waits in a pager, and it is absent under `-S`
- `help('modules')` where importing an untrusted package would be unsafe
- Passing a string to see a string's methods: `help('text')` looks up a name; pass `str`

## Version Notes

- **Python 3.13+**: `exit` leaves the interactive helper, as `q` and `quit` do
- **Python 3.13.12+, 3.14.3+**: an empty line at the `help>` prompt returns to the prompt instead
  of leaving the helper

## Related Modules

- **[pydoc](../stdlib/pydoc.md)** - The renderer, pagers and module search behind `help()`
- **[pydoc_data](../stdlib/pydoc_data.md)** - The keyword and topic texts `help('if')` shows
- **[inspect](../stdlib/inspect.md)** - Signatures, docstrings and members as values
- **[dir()](dir.md)** - The attribute names without their documentation
- **[Interpreter Info](interpreter_info.md)** - The other REPL builtins installed by `site`
