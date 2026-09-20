# __import__() Function Complexity

`__import__()` is the function the `import` statement calls. The compiler emits one `IMPORT_NAME`
for each module a statement names, and that instruction looks the name `__import__` up in the
executing frame's builtins and calls what it finds - so rebinding `builtins.__import__` changes
every subsequent `import` run with the usual builtins, and deleting it makes `import` raise
`ImportError`. The function itself is the C implementation of the import protocol: a probe of
`sys.modules` first, and only on a miss the search along `sys.meta_path` and the path entries,
then reading, compiling and running the module.

The search and the module body happen once per name that imports successfully and stays in
`sys.modules`; a later call with an empty `fromlist` is the probe alone. That is why the cost of
an import is a property of the program's first run through a line rather than of the line - and
why removing the entry, or reloading, runs the body again. What the function does *not* do is
return what its name suggests: for a dotted name it hands back the head of the name, and only a
non-empty `fromlist` makes it return the module named. That is the reason
[`importlib.import_module()`](../stdlib/importlib.md) exists, and the reason direct use of this
function is rare.

`t` is the finders on `sys.meta_path`, `p` is the entries on the path being searched (`sys.path`,
or a package's `__path__`), `s` is the registered file suffixes, `e` is the directory entries
listed during one search, summed over the path entries whose listing is not cached yet, `n` is
the bytes in a module's source or bytecode, `m` is the time and space the module's body itself
takes, `c` is the components of a dotted name, `f` is the names in `fromlist`, `a` is the names in
a module's `__all__`, and `g` is the names in its namespace. Module names are treated as O(1) to
split, hash and join, and one attribute check or one `find_spec()` call as O(1) - a module
`__getattr__` or a finder of your own costs whatever you wrote. Space in the first table below is
what a call leaves in `sys.modules`, and in the second what the statement binds in the importing
namespace; the directory listings a first search caches belong to the path entry finders either
way, and are priced on the [importlib](../stdlib/importlib.md) page.

## Complexity Reference

### __import__

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `__import__(name, globals=None, locals=None, fromlist=(), level=0)`, resolved name in `sys.modules`, empty `fromlist` | O(1) | O(1) | Cached lookups only, and no finder is consulted. A `None` entry raises `ModuleNotFoundError` rather than returning it. A module another thread is still executing is waited for instead, which this bound does not cover: the wait is that module's body |
| `__import__(name)`, `name` not loaded | O(c·(t + p·s + e) + n + m) | O(n + m) | A find and a load for every component of the dotted name that is missing, top down; each find walks `sys.meta_path` and then the path entries, listing any directory whose contents are not cached yet. `n` and `m` are summed over the modules actually run |
| Return value of a dotted `name` with an empty `fromlist` | O(1) | O(1) | The head of `name`, not the module it asks for: the top-level package for an absolute import, and for `level > 0` the first component of `name` under the anchor. Reaching it costs no search. An undotted `name` returns the module itself |
| `__import__(name, fromlist=names)` on a package | O(f), plus an import per missing name | O(1), plus O(n + m) per name loaded | One attribute check per name, and an import of each name the package lacks - a probe when that submodule is already in `sys.modules`, the row above when it is not, and a full search every call for a name that is neither, whose `ModuleNotFoundError` is swallowed. The module named by `name` is returned instead of the head of the name |
| `__import__(name, fromlist=names)` on a non-package | O(1) | O(1) | No name in the list is checked: only a module with `__path__` reaches the `fromlist` handling |
| `__import__(name, fromlist=["*"])` | O(a), plus an import per missing name | O(1), plus O(n + m) per name loaded | Expands to the package's `__all__` and checks those names on the same terms as the row above; a package without `__all__` costs one check and nothing else |
| `__import__(name, globals, level=k)` | O(1) | O(1) | Resolves `name` against `globals`: `__package__` if set, else `__spec__.parent`, else `__name__` behind an `ImportWarning`. `TypeError` unless `globals` is a `dict` - the default `None` and any other mapping are refused - so a positive `level` needs a dict that names the anchor, not a call from inside a module |
| `locals` | O(1) | O(1) | Never used; the statement passes the frame's locals and the implementation ignores them |
| `builtins.__import__` | O(1) | O(1) | An ordinary module attribute. `IMPORT_NAME` reads it from the frame's builtins every time, so a replacement takes effect at once and is called again on every subsequent import statement |

### The import statement

Every form below names one module and so compiles to one `IMPORT_NAME`, which is the call above.
The costs here are what the statement adds to it.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import pkg.mod` | O(1) | O(1) | An empty `fromlist`, so the call returns `pkg`, which is the name bound |
| `import pkg.mod as name` | O(1) | O(1) | Also an empty `fromlist`, then one attribute load for `mod`, which falls back to `sys.modules['pkg.mod']` when the attribute is not there yet |
| `from pkg.mod import x, y` | O(f) | O(1) | `fromlist` is the names, so the call returns `pkg.mod`; then one attribute load per name, with the same `sys.modules` fallback |
| `from . import x` | O(1) | O(1) | `level` is the number of leading dots and `name` is what follows, so the module's own `globals` resolve it |
| `from pkg import *` | O(a), or O(g) with no `__all__` | O(a), or O(g) with no `__all__` | `fromlist` is `('*',)`, then every name in `__all__` - or, with no `__all__`, every name in the namespace that does not start with `_` - is bound in the importing namespace |

## A Probe Before a Search

The first import of a name pays for the search; a later one with an empty `fromlist` is a
dictionary lookup that consults no finder at all. A finder on `sys.meta_path` that records what
it is asked separates the two without a stopwatch.

```python
import sys

class Recorder:
    """A meta path finder that answers nothing and remembers what it was asked."""

    def __init__(self):
        self.asked = []

    def find_spec(self, fullname, path=None, target=None):
        self.asked.append(fullname)
        return None

recorder = Recorder()
sys.meta_path.insert(0, recorder)
try:
    import base64  # the first import may search
    recorder.asked.clear()

    again = __import__("base64")  # O(1) - a sys.modules probe
    assert again is base64
    assert again is sys.modules["base64"]
    assert recorder.asked == []  # no finder was consulted

    try:
        __import__("no_such_module_anywhere")  # a full search before it fails
    except ModuleNotFoundError as error:
        assert error.name == "no_such_module_anywhere"
    else:
        raise AssertionError("a missing module was imported")
    assert recorder.asked == ["no_such_module_anywhere"]
finally:
    sys.meta_path.remove(recorder)
```

A `None` left in `sys.modules` is not a cached module: the probe finds it and raises instead of
searching, which is how an import is blocked outright.

```python
import sys

sys.modules["blocked_module"] = None
try:
    __import__("blocked_module")  # O(1) - the probe finds None
except ModuleNotFoundError as error:
    assert "None in sys.modules" in str(error)
else:
    raise AssertionError("a blocked module was imported")
finally:
    del sys.modules["blocked_module"]
```

## The Return Value Depends on fromlist

For a dotted name the function returns the *head* of that name - for an absolute import, the
top-level package - because that is the name `import pkg.mod` binds. A non-empty `fromlist`
switches it to the module the name asks for. This is the difference that makes
`importlib.import_module()` the right tool for importing a module whose name is computed.

```python
import importlib

top = __import__("json.decoder")  # O(1) once loaded
assert top.__name__ == "json"  # not json.decoder

named = __import__("json.decoder", fromlist=["JSONDecoder"])  # O(f) on top of the import
assert named.__name__ == "json.decoder"

assert importlib.import_module("json.decoder") is named  # what you usually want
assert top.decoder is named  # the submodule is an attribute of its package
```

## What fromlist Costs

Each name in the list is one attribute check. Only the names the package does not already have
are imported, and a name whose module is already in `sys.modules` costs a probe rather than a
search - so a second call over a list whose names have all become attributes touches no finder.
A name that is neither an attribute nor an importable submodule is the exception: it is searched
for on every call, and the failure is swallowed. A module that is not a package skips the list
entirely, because the handling is reached only through `__path__`.

```python
import sys

assert "email.utils" not in sys.modules

package = __import__("email", fromlist=["utils"])  # one check, then one import
assert package.__name__ == "email"
assert "email.utils" in sys.modules
assert package.utils is sys.modules["email.utils"]

# The second call finds the attribute and imports nothing
before = set(sys.modules)
assert __import__("email", fromlist=["utils"]) is package  # O(f) checks, no import
assert set(sys.modules) == before

# A name that is neither an attribute nor a submodule is searched for every call,
# and says nothing about it
assert __import__("email", fromlist=["no_such_submodule"]) is package
assert not hasattr(package, "no_such_submodule")

# A module without __path__ never reaches the list
import base64

assert not hasattr(base64, "__path__")
assert __import__("base64", fromlist=["no_such_name"]) is base64
```

`'*'` is the same loop over the package's `__all__`. Whether that costs anything depends on what
the names already are: submodules get imported, everything else is already an attribute.

```python
import json
import sys

# json.__all__ is functions and classes, so every name is already an attribute
loaded = set(sys.modules)
assert __import__("json", fromlist=["*"]).__name__ == "json"  # O(a) checks, no import
assert set(sys.modules) == loaded

xml_package = __import__("xml", fromlist=["*"])  # O(a) checks, and four imports
assert xml_package.__all__ == ["dom", "parsers", "sax", "etree"]
assert {"xml.dom", "xml.parsers", "xml.sax", "xml.etree"} <= set(sys.modules)

# A package with no __all__ has nothing to expand
import urllib

assert not hasattr(urllib, "__all__")
assert __import__("urllib", fromlist=["*"]) is urllib  # O(1)
```

## Relative Imports Read globals

`level` counts the leading dots of a relative import, and the anchor comes from the `globals`
passed in - `__package__` when it is set, then `__spec__.parent`, and `__name__` only as a
fallback that warns. It has to be a `dict`: the default `None`, and any other mapping, are
refused before any search happens. Where the dict comes from does not matter, so a hand-built
one works as well as a module's own.

```python
import json.decoder
import sys
import warnings

try:
    __import__("decoder", None, None, ("JSONDecoder",), 1)  # O(1) - no search
except TypeError as error:
    assert "globals must be a dict" in str(error)
else:
    raise AssertionError("a relative import without globals resolved")

# What a module's own globals supply
inside = {"__name__": "json", "__package__": "json", "__spec__": json.__spec__}
assert __import__("decoder", inside, None, ("JSONDecoder",), 1) is json.decoder

# Without __package__ or __spec__, __name__ is used and the fallback warns
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    resolved = __import__("scanner", {"__name__": "json.decoder"}, None, ("x",), 1)

assert resolved is sys.modules["json.scanner"]
assert any(issubclass(w.category, ImportWarning) for w in caught)
```

## Replacing the Function

`IMPORT_NAME` reads `__import__` out of the frame's builtins on every execution, so a replacement
is live immediately and needs no import hook - and a frame given its own `__builtins__` mapping
never sees it. `importlib.__import__` is a separate object, a pure-Python implementation of the
same protocol: the call itself goes nowhere near the builtins entry, though import statements in
a module it loads still read it like any other.

```python
import builtins
import importlib

assert importlib.__import__ is not builtins.__import__

seen = []
original = builtins.__import__

def recording(name, globals=None, locals=None, fromlist=(), level=0):
    seen.append(name)
    return original(name, globals, locals, fromlist, level)

builtins.__import__ = recording  # O(1) - and the next statement uses it
try:
    import sys  # goes through the replacement, already loaded so nothing nests
    importlib.__import__("sys")  # does not
finally:
    builtins.__import__ = original

assert seen == ["sys"]
```

Removing the name entirely leaves the statement with nothing to call.

```python
import builtins

original = builtins.__import__
del builtins.__import__
try:
    import base64
except ImportError as error:
    assert "__import__ not found" in str(error)
else:
    raise AssertionError("import worked without the builtin")
finally:
    builtins.__import__ = original
```

## Common Patterns

### Importing a Computed Name

```python
import importlib

name = "json.decoder"

# Wrong: returns the top-level package
assert __import__(name).__name__ == "json"

# Works, but the fromlist is only there to change the return value
assert __import__(name, fromlist=["JSONDecoder"]).__name__ == name

# What to write instead - O(1) once loaded
assert importlib.import_module(name).__name__ == name
```

## Performance Best Practices

✅ **Do**:

- Call `importlib.import_module()` for a computed name; it returns the module you named rather
  than the head of the name
- Let repeated imports hit `sys.modules` instead of caching modules yourself - the probe is a
  dict lookup and it is what the statement already does
- Import inside a function when a heavy dependency is used on one rare path; the module body
  runs once, on the first call that reaches it

❌ **Avoid**:

- `__import__(name)` for a dotted name: it hands back the head of the name, not the module the
  name asks for, and raises nothing to say so
- A `fromlist` used only to force the return value - that is `import_module()` spelled awkwardly
- `from pkg import *`, which binds every name in `__all__` on each execution and, for a package
  of submodules, imports all of them
- Replacing `builtins.__import__` to change import behaviour; a `sys.meta_path` finder usually
  reaches the same goal without putting a Python call on every `IMPORT_NAME`

## Version Notes

- **Python 3.12+**: a `globals` whose `__package__` disagrees with `__spec__.parent` raises
  `DeprecationWarning` on a relative import; 3.10 and 3.11 raise `ImportWarning`. `__package__`
  wins either way
- **All Python 3**: `locals` is ignored, and `globals` is read only when `level` is positive
- **All Python 3**: a dotted name with an empty `fromlist` returns the head of the name - the
  top-level package for an absolute import, and the first component under the anchor for a
  relative one

## Related Functions

- **[importlib](../stdlib/importlib.md)** - `import_module()`, the search along `sys.meta_path`
  and `sys.path`, and the loaders behind the O(n + m) term
- **[exec()](exec.md)** and **[eval()](eval.md)** - The other builtins that run code supplied at
  run time
- **[compile()](compile.md)** - Where the `IMPORT_NAME` instruction comes from
- **[globals()](globals.md)** - The mapping a relative import resolves its anchor against
