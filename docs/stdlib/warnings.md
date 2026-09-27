# warnings Module Complexity

The `warnings` module decides, for each warning issued, whether to show it, ignore it or raise it.
`warn()` walks up the stack to find the line the warning belongs to, checks that module's registry
of warnings already shown, and on a miss scans the filter list front to back until the first
filter that matches. Apart from the filter list, the state it keeps is a registry per module of
the warnings already shown.

`f` is the entries in the active filter list, `k` is the frames `warn()` walks to find the
warning's location (`stacklevel`, plus any frames it skips), `d` is the entries in one module's
`__warningregistry__`, `b` is the size of the source file a warning points into, and `w` is the
warnings a `catch_warnings(record=True)` block has recorded. Bounds treat a warning's text and
its source line as short strings and matching one filter as O(1); a `message` or `module` pattern is a regular
expression run against the text or module name, so a pattern that scans the whole string adds
that length per filter it is tried on.

## Complexity Reference

### Issuing Warnings

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `warnings.warn(message, category=None, stacklevel=1, source=None, *, skip_file_prefixes=())` | O(k + f) | O(1) | Frame walk, registry lookup, then the filter scan, which stops at the first match |
| `warn()` - a repeat already in the registry | O(k) | O(1) | `"default"`, `"module"` and `"once"` record what they show, so a repeat skips the filter scan; `"ignore"` and `"always"` record nothing and scan every time |
| `warn()` - the first warning in a module after any filter change | O(k + f + d) | O(1) | Changing the filters bumps a version number; each registry is cleared when its module next warns |
| `warnings.warn_explicit(message, category, filename, lineno, module=None, registry=None, module_globals=None, source=None)` | O(f); O(b + f) with `module_globals` | O(1); O(b) with `module_globals` | No frame walk. Without a `registry`, `"default"` and `"module"` show every call and `"once"` uses `onceregistry`; a supplied registry is checked and cleared as `warn()`'s is. When the loader in `module_globals` has `get_source()`, the module's whole source is fetched and split on every call, before the filters are consulted |
| Showing a warning | O(b) for the first from a file, then O(1) | O(b) | The default formatter reads the warning's source line through `linecache`, which loads and keeps the whole file |

### Filters

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `warnings.filterwarnings(action, message='', category=Warning, module='', lineno=0, append=False)` | O(f) | O(1) | Compiles `message` and `module` as patterns, removes an equal filter, then inserts at the front; with `append=True` it adds at the end only if no equal filter exists |
| `warnings.simplefilter(action, category=Warning, lineno=0, append=False)` | O(f) | O(1) | `filterwarnings()` with no patterns |
| `warnings.resetwarnings()` | O(f) | O(1) | Empties the list and bumps the version, so every warning takes the `"default"` action |
| `warnings.filters` | O(1) | O(1) | The list itself, of `(action, message, category, module, lineno)` tuples; editing it in place does not bump the version, so a warning already in a registry stays suppressed |
| `warnings.onceregistry` | O(1) | O(1) | The registry for `"once"` warnings issued through `warn_explicit()` without a `registry` |

### catch_warnings

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `warnings.catch_warnings(*, record=False, module=None, action=None, category=Warning, lineno=0, append=False)` | O(1) | O(1) | Nothing is saved until the block is entered |
| Entering `catch_warnings` | O(f) | O(f) | Copies the filter list (into a context variable under context-aware warnings, 3.14+) and bumps the version; `action` then applies one `simplefilter()` |
| Leaving `catch_warnings` | O(1) | O(1) | Puts the saved list back and bumps the version, so each registry is cleared when its module next warns |
| `catch_warnings(record=True)` | O(1) amortized per warning shown | O(w) | Each shown warning is appended to the returned list instead of printed |
| `warnings.WarningMessage` | O(1) | O(1) | The recorded object: `message`, `category`, `filename`, `lineno`, `file`, `line`, `source` |

### Formatting and Display

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `warnings.formatwarning(message, category, filename, lineno, line=None)` | O(b) for the first from a file, then O(1) | O(b) | With `line` omitted, reads the source line through `linecache`; passing `line` skips the file |
| `warnings.showwarning(message, category, filename, lineno, file=None, line=None)` | as `formatwarning()` | as `formatwarning()` | Formats, then writes once to `file` or `sys.stderr`; replacing it replaces the whole display step |

### deprecated

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `warnings.deprecated(message, /, *, category=DeprecationWarning, stacklevel=1)` | O(1) | O(1) | Python 3.13+. Wraps a function once, or patches a class's `__new__` and `__init_subclass__` |
| Calling a deprecated function, instantiating or subclassing a deprecated class | O(k + f) | O(1) | One `warn()` per use, then the original; `category=None` returns the object unwrapped and never warns |

### Warning Categories

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Warning`, `UserWarning`, `DeprecationWarning`, `PendingDeprecationWarning`, `SyntaxWarning`, `RuntimeWarning`, `FutureWarning`, `ImportWarning`, `UnicodeWarning`, `BytesWarning`, `ResourceWarning`, `EncodingWarning` | O(1) | O(1) | Built-in exception classes; a filter matches a category and all its subclasses |

## Issuing Warnings

### The Filter Scan

A warning that is not a repeat is checked against the filters in order, and the first one that
matches decides. Filters after it are never consulted, so the scan is O(f) at worst.

```python
import warnings

with warnings.catch_warnings(record=True) as caught:  # O(f) - copies the filters
    warnings.simplefilter("always")                     # O(f)
    warnings.warn("disk almost full", ResourceWarning)  # O(k + f)
    warnings.warn("use new_api()", DeprecationWarning)

assert [w.category for w in caught] == [ResourceWarning, DeprecationWarning]
assert str(caught[0].message) == "disk almost full"
```

### Repeats Skip the Scan

The `"default"` action shows a warning once per location and records it in the module's
`__warningregistry__`, so the next identical warning from that line is a dictionary lookup.
`"ignore"` records nothing: a suppressed warning in a hot loop pays for the frame walk and the scan
on every call.

```python
import warnings

def check(value):
    warnings.warn("value is negative", RuntimeWarning)

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("default")  # O(f)
    for value in range(5):
        check(value)                   # O(k + f) once, then O(k) per repeat

assert len(caught) == 1
registry = check.__globals__["__warningregistry__"]
assert ("value is negative", RuntimeWarning, check.__code__.co_firstlineno + 1) in registry
```

### Varying Messages Fill the Registry

The registry key is the message text, the category and the line number. A message that embeds a
changing value is a new key every time, so it is shown every time and each one adds an entry until
the next filter change clears it.

```python
import warnings

def check(value):
    warnings.warn(f"value {value} is negative", RuntimeWarning)

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("default")
    for value in range(100):
        check(value)  # a new registry entry per distinct text

assert len(caught) == 100
registry = check.__globals__["__warningregistry__"]
assert len(registry) > 100  # one per message, plus the version marker
```

### Pointing at the Caller

`stacklevel` picks the frame to blame - 1 is the line calling `warn()`, 2 is its caller - and
`warn()` walks up to it, O(k). `skip_file_prefixes`
(Python 3.12+) skips every frame whose file name starts with one of the prefixes on the way, so a
library can blame the first frame outside itself.

```python
import warnings

def old_api():
    warnings.warn("old_api() is deprecated", DeprecationWarning, stacklevel=2)  # O(k)

def caller():
    old_api()  # the warning names this line, not the one inside old_api()

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    caller()

assert caught[0].lineno == caller.__code__.co_firstlineno + 1
```

## Filtering Warnings

### Installing Filters

`filterwarnings()` and `simplefilter()` scan the list to remove an equal filter before inserting
the new one at the front, so installing the same filter twice leaves one copy. Either call also
invalidates every registry, which is what makes a new filter apply to warnings already shown.

```python
import warnings

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="old_api", category=DeprecationWarning)  # O(f)
    count = len(warnings.filters)
    warnings.filterwarnings("ignore", message="old_api", category=DeprecationWarning)  # O(f)
    assert len(warnings.filters) == count  # the duplicate was removed first

    warnings.simplefilter("error", RuntimeWarning)  # O(f) - goes to the front
    assert warnings.filters[0][:1] == ("error",)

    try:
        warnings.warn("overflow", RuntimeWarning)
    except RuntimeWarning as error:
        assert str(error) == "overflow"
    else:
        raise AssertionError("the error filter did not raise")
```

### Editing the List Directly

`warnings.filters` is an ordinary list, but changing it in place does not tell the registries.
A warning that has already been shown under `"default"` stays suppressed even after an `"error"`
filter is inserted by hand; `filterwarnings()` and `simplefilter()` do not have that problem.

```python
import warnings

def check():
    warnings.warn("stale", UserWarning)

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("default")
    check()
    warnings.filters.insert(0, ("error", None, Warning, None, 0))  # no version bump
    check()  # still answered by the registry: neither raised nor shown
    assert len(caught) == 1

    warnings.simplefilter("error")  # bumps the version
    try:
        check()
    except UserWarning:
        pass
    else:
        raise AssertionError("the new filter was not applied")
```

## Capturing Warnings

`catch_warnings()` copies the filter list on entry, O(f), and puts the saved one back on exit.
The example shows the default mode; under context-aware warnings (3.14+, see Version Notes) the
copy lives in a context variable and `warnings.filters` itself is left alone.
With `record=True` each shown warning becomes a `WarningMessage` in the returned list instead of
being printed, so the list grows with the warnings shown in the block. From Python 3.11 the
`action` argument applies one `simplefilter()` on entry.

```python
import warnings

before = warnings.filters
with warnings.catch_warnings(record=True) as caught:  # O(f)
    assert warnings.filters is not before  # a copy, restored on exit
    warnings.simplefilter("always")  # or action="always" on Python 3.11+
    for attempt in range(3):
        warnings.warn("retrying", UserWarning)  # "always" records nothing to skip

assert warnings.filters is before
assert len(caught) == 3  # O(w) memory
assert caught[0].category is UserWarning and str(caught[0].message) == "retrying"
```

## Formatting and Display

The default display reads the warning's source line through `linecache`, which loads the whole
file the first time and keeps it. Passing `line` to `formatwarning()` skips the file entirely.

```python
import linecache
import os
import tempfile
import warnings

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, "module.py")
    with open(path, "w") as file:
        file.write("x = 1\ny = 2\n")

    text = warnings.formatwarning("check y", UserWarning, path, 2, line="y = 2")  # O(1)
    assert path not in linecache.cache
    assert text.endswith("UserWarning: check y\n  y = 2\n")

    text = warnings.formatwarning("check y", UserWarning, path, 2)  # O(b) - reads the file
    assert path in linecache.cache
    assert text.endswith("  y = 2\n")
    linecache.clearcache()
```

## Deprecating an API

`@warnings.deprecated` (Python 3.13+) does its work once, when it decorates; each later call is one
`warn()` followed by the original. The message is also stored as `__deprecated__` for type
checkers.

```python
import warnings

@warnings.deprecated("use add() instead")  # O(1) - wraps once
def plus(a, b):
    return a + b

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    assert plus(1, 2) == 3  # O(k + f) - one warn() per call

assert caught[0].category is DeprecationWarning
assert plus.__deprecated__ == "use add() instead"

def quiet():
    return 1

assert warnings.deprecated("gone soon", category=None)(quiet) is quiet  # no wrapper
```

## Warning Categories

```text
Warning
├── UserWarning (warn()'s default)
├── DeprecationWarning
├── PendingDeprecationWarning
├── SyntaxWarning
├── RuntimeWarning
├── FutureWarning
├── ImportWarning
├── UnicodeWarning
├── BytesWarning
├── ResourceWarning
└── EncodingWarning
```

A filter's category matches that class and every subclass, so `simplefilter("error", Warning)`
turns every category into an exception.

## Performance Best Practices

✅ **Do**:

- Keep a warning's text constant, so repeats hit the registry instead of adding entries to it
- Install filters with `filterwarnings()` or `simplefilter()`, which also reset the registries
- Pass `line` to `formatwarning()` when the caller already has it, to avoid reading the file
- Use `catch_warnings()` in tests; it costs one O(f) copy and restores the filters on exit

❌ **Avoid**:

- Issuing a warning inside a hot loop that a filter ignores: every call pays O(k + f)
- Editing `warnings.filters` in place - warnings already shown stay suppressed
- `warn_explicit(..., module_globals=...)` in a hot path: it reads the module's source on every call

## Version Notes

- **Python 3.11+**: `catch_warnings()` accepts `action`, `category`, `lineno` and `append`
- **Python 3.12+**: `warn()` accepts `skip_file_prefixes`
- **Python 3.13+**: Added `warnings.deprecated`
- **Python 3.14+**: Added the `"all"` action, an alias for `"always"`; with context-aware warnings
  (`-X context_aware_warnings`, the default on free-threaded builds) `catch_warnings()` copies the
  filters into a context variable and leaves `warnings.filters` untouched

## Related Modules

- **[logging](logging.md)** - `logging.captureWarnings()` routes warnings to a logger
- **[linecache](linecache.md)** - The cache that holds source files a warning has been shown from
- **[contextvars](contextvars.md)** - Where context-aware `catch_warnings()` keeps its filters
