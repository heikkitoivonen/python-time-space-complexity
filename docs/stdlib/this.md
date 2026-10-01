# this Module Complexity

The `this` module is an Easter egg. Its body holds the Zen of Python
([PEP 20](https://peps.python.org/pep-0020/)) ROT13-encoded in `this.s`, builds the 52-entry
decoding table `this.d`, and prints the decoded text to `sys.stdout`. That is the module's only
work, and it runs when the module is first imported.

The module takes no input and its text is fixed, so every bound on this page is O(1). Finding and
loading the file is the import system's cost, priced on the [importlib](importlib.md) page; the
bounds here are the module body's.

## Complexity Reference

### Importing the module

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import this`, first in a process | O(1) | O(1) | Decodes the text and prints it with one `print()` to `sys.stdout` |
| `import this`, again | O(1) | O(1) | Found in `sys.modules`; the body does not run again, so nothing is printed |
| `importlib.reload(this)` | O(1) | O(1) | Runs the body again, so the text is printed again; finding and loading the file again is priced on the importlib page |

### Module attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `this.s` | O(1) | O(1) | The Zen, ROT13-encoded; `codecs.decode(this.s, 'rot13')` gives the text without printing |
| `this.d` | O(1) | O(1) | The dictionary mapping each ASCII letter to its ROT13 partner, used to decode `s` |

## Importing the Module

Only the first import prints. Later imports in the same process find the module in `sys.modules`
and run nothing, so redirecting `sys.stdout` around the first one is enough to keep the text off
the console.

```python
import contextlib
import io
import sys

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    import this  # O(1) - decodes and prints the fixed text once

assert buffer.getvalue().startswith('The Zen of Python, by Tim Peters\n\n')
assert 'Readability counts.\n' in buffer.getvalue()

with contextlib.redirect_stdout(io.StringIO()) as again:
    import this  # O(1) - found in sys.modules, prints nothing
assert again.getvalue() == ''
assert sys.modules['this'] is this
```

`importlib.reload()` runs the body again, and the body is the print.

```python
import contextlib
import importlib
import io

with contextlib.redirect_stdout(io.StringIO()):
    import this

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    assert importlib.reload(this) is this  # the body runs again
assert buffer.getvalue().startswith('The Zen of Python')
```

## Reading the Text Without Printing

`this.s` is the encoded text and ROT13 is its own inverse, so the `rot13` text codec turns it back
into the Zen as a string. The import still prints once, so redirect it if that matters.

```python
import codecs
import contextlib
import io

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    import this

zen = codecs.decode(this.s, 'rot13')  # O(1) - the text is fixed
assert zen + '\n' == buffer.getvalue()  # exactly what the import printed
assert zen.splitlines()[-1].startswith('Namespaces are one honking great idea')

assert len(this.d) == 52
assert this.d['a'] == 'n' and this.d['N'] == 'A'
```

## Performance Best Practices

✅ **Do**:

- Read `codecs.decode(this.s, 'rot13')` when you want the Zen as a string
- Redirect `sys.stdout` around the first import in a program or test that must not print

❌ **Avoid**:

- Expecting a second `import this` to print; use `importlib.reload(this)` to run the body again

## Related Modules

- **[antigravity](antigravity.md)** - the other Easter egg that acts when imported
- **[codecs](codecs.md)** - the `rot13` text codec that decodes `this.s`
- **[importlib](importlib.md)** - what finding, loading and reloading a module costs
