# imp Module Complexity

`imp` is the pre-`importlib` API for finding and loading modules by hand.

## Complexity Reference

Here, p is the number of directories searched, s the number of recognised
suffixes (the length of `get_suffixes()`), n the size in bytes of the file or
frozen code being loaded, L the length of a path string, b the number of
modules compiled into the interpreter, and f the number of frozen modules.
Loading a module also executes its body; that cost belongs to the module and is
not counted below. Space is auxiliary memory, excluding the module created.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `find_module(name, path=None)` | O(p × s) | O(s) | Probes directories in order until one matches; `path=None` adds the O(b + f) table checks and searches all of `sys.path`; returns an open file after reading only its encoding lines |
| `load_source(name, pathname, file=None)` | O(n) | O(n) | Reads the whole file; a valid `__pycache__` entry skips compilation |
| `load_compiled(name, pathname, file=None)` | O(n) | O(n) | Reads and unmarshals the whole `.pyc` |
| `load_package(name, path)` | O(n) | O(n) | Executes `__init__` only; n is its size |
| `load_module(name, file, filename, details)` | O(1) | O(1) | Dispatches on the type code in `details`, then costs what that loader costs |
| `load_dynamic(name, path, file=None)` | O(1) | O(1) | Python-side work; `dlopen` and the extension's init function are the real cost |
| `reload(module)` | O(n) | O(n) | Plus the finders' cost: it re-finds the module through the import system, so one loaded from a directory it cannot see raises `ModuleNotFoundError` |
| `new_module(name)` | O(1) | O(1) | An empty module, not entered into `sys.modules` |
| `init_builtin(name)` | O(b) | O(1) | Scans the built-in table, then runs the module's init function |
| `init_frozen(name)` | O(f + n) | O(n) | Scans the frozen tables, then unmarshals the frozen code |
| `is_builtin(name)` | O(b) | O(1) | Scans the built-in table |
| `is_frozen(name)` | O(f) | O(1) | Scans the frozen tables |
| `get_magic()` / `get_tag()` | O(1) | O(1) | Return existing objects |
| `get_suffixes()` | O(s) | O(s) | Builds a fresh list on every call |
| `cache_from_source(path)` / `source_from_cache(path)` | O(L) | O(L) | String work only; the files need not exist |
| `lock_held()` / `acquire_lock()` / `release_lock()` | O(1) | O(1) | The global import lock; `acquire_lock()` blocks while another thread holds it |
| `NullImporter(path)` | O(1) | O(1) | One `isdir` check; its `find_module()` always returns `None` |
| `SEARCH_ERROR`, `PY_SOURCE`, `PY_COMPILED`, `C_EXTENSION`, `PY_RESOURCE`, `PKG_DIRECTORY`, `C_BUILTIN`, `PY_FROZEN`, `PY_CODERESOURCE`, `IMP_HOOK` | O(1) | O(1) | Module type codes 0 to 9 |

!!! warning "Removed in Python 3.12"
    Deprecated in Python 3.4 and removed in Python 3.12. This page covers the
    API documented for Python 3.11 plus the undocumented `load_source()`,
    `load_compiled()` and `load_package()` loaders. The `_imp` re-exports
    `create_dynamic`, `get_frozen_object` and `is_frozen_package`, the
    re-exported `SourcelessFileLoader`, and the modules `imp` imports are
    outside its scope.

## Finding a Module

`find_module()` stats each directory for a package and for every suffix
before moving to the next, so its cost is set by the search path rather than
by the module. Pass the package's `__path__` or a short list as `path` instead
of letting it walk all of `sys.path`. Without `path`, the built-in and frozen
tables are consulted first and a hit there probes no directories.

## Loading Source

`load_source()` runs the same `SourceFileLoader` code path as a normal import:
the first load compiles the source and, unless bytecode writing is disabled,
writes a `.pyc` under `__pycache__`; a later load whose cache is still valid
reads the bytecode instead of compiling. `load_compiled()` starts from the
`.pyc` directly and never compiles.

Run this example on Python 3.10 or 3.11.

```python
import imp
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as directory:
    Path(directory, "greeting.py").write_text("MESSAGE = 'hello'\n")
    file, pathname, details = imp.find_module("greeting", [directory])  # O(p * s)
    with file:
        module = imp.load_module("greeting", file, pathname, details)  # O(n)
    assert module.MESSAGE == "hello"
    again = imp.load_source("greeting", pathname)  # O(n), from the .pyc
    assert again is module
```

## Modern Replacement

`importlib.util` does the same linear work without the deprecated API and runs
on every supported version.

```python
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as directory:
    path = Path(directory, "greeting.py")
    path.write_text("MESSAGE = 'hello'\n")
    spec = importlib.util.spec_from_file_location("greeting", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # O(n)
    assert module.MESSAGE == "hello"
```

## Related Documentation

- [importlib](importlib.md)
- [sys](sys.md)
- [Python 3.11 imp documentation](https://docs.python.org/3.11/library/imp.html)
- [CPython 3.11 implementation](https://github.com/python/cpython/blob/3.11/Lib/imp.py)
- [Python 3.12 removal notice](https://docs.python.org/3.12/whatsnew/3.12.html#imp)
