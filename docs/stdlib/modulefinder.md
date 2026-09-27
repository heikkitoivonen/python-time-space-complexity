# modulefinder Module Complexity

The `modulefinder` module works out which modules a script imports without running it. It
compiles each module it finds, reads the import statements out of the bytecode, and follows them
depth-first, searching the path once per new name. Every module it finds stays in memory with its
compiled code until the finder is discarded. Running `python -m modulefinder script.py` does the
same from the command line and prints the report.

`u` is the distinct module names looked up, found or missing; `c` is the code loaded across the
modules found - characters of source compiled, or bytes of a bytecode-only `.pyc` - plus the names
star imports copy between them; `n` is the modules found; `b` is the (missing name, importing
module) pairs recorded, and `m` the distinct names among them. `p` is the directories the process
holds a cached path finder for: the search path, plus every package directory searched so far, in
this finder or any other. `e` is the entries in the directories the analysis lists. `excludes` and
`replace_paths` are treated as short lists, and name hashing as O(1).

## Complexity Reference

### ModuleFinder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `modulefinder.ModuleFinder(path=None, debug=0, excludes=None, replace_paths=None)` | O(1) | O(1) | Keeps `path` by reference, `sys.path` itself when omitted; nothing is searched yet |
| `ModuleFinder.run_script(pathname)` | O(c + u·(p + e)) | O(c + u + b + p + e) | Records the script as `__main__`; never executes any of the code it reads |
| `ModuleFinder.load_file(pathname)` | O(c + u·(p + e)) | O(c + u + b + p + e) | As `run_script()`, with the module named after the file |
| `ModuleFinder.import_hook(name, caller=None, fromlist=None, level=-1)` | O(c + u·(p + e)) | O(c + u + b + p + e) | Starts from a module name; if that name is not found it raises `ImportError` rather than recording it, so a second call searches again. `fromlist=['*']` on a package also imports every module file directly in its directories |
| `ModuleFinder.modules` | O(1) | O(1) | The finder's own dict of name to `Module`, not a copy |
| `ModuleFinder.badmodules` | O(1) | O(1) | The finder's own dict of each name that failed to import to the modules that tried |
| `ModuleFinder.any_missing()` | O(m log m) | O(m) | The sorted `any_missing_maybe()` lists joined, leaving out `excludes` |
| `ModuleFinder.any_missing_maybe()` | O(m log m) | O(m) | Splits missing names into certain and maybe: a maybe is a name under a package that did a star import it could not resolve; a name another module imports from a package that binds it as a global is in neither |
| `ModuleFinder.report()` | O(n log n + b log b) | O(n + b) | Prints every module found, then the missing ones with their importers, each sorted |

### Module

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `modulefinder.Module` | O(1) | O(1) | The values in `ModuleFinder.modules` |
| `Module.__name__`, `Module.__file__`, `Module.__path__` | O(1) | O(1) | `__file__` is `None` for a builtin module; `__path__` is `None` unless it is a package |
| `Module.__code__` | O(1) | O(1) | The compiled code, kept for the finder's lifetime; `None` for a builtin or extension module, whose imports are never read |
| `Module.globalnames`, `Module.starimports` | O(1) | O(1) | Dicts of the global names the module binds, and of the star imports it could not resolve |

### Package path hooks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `modulefinder.AddPackagePath(pkg_name, path)` | O(1) | O(1) | Adds a directory to that package's `__path__` for every finder in the process that loads it later |
| `modulefinder.ReplacePackage(oldname, newname)` | O(1) | O(1) | Every finder in the process then records package `oldname` as `newname` |
| `modulefinder.packagePathMap`, `modulefinder.replacePackageMap` | O(1) | O(1) | The dicts those two functions write; there is no function to remove an entry, so undo one by editing the dict |

## Finding Imports Without Running Code

The finder compiles a module and reads its import statements; it does not execute anything. So it
sees every `import` the compiler keeps, in every code path - inside functions that are never
called, and inside a `try` whose `except ImportError` would have caught the failure - and it does
not see one under `if False:`, which the compiler drops, or a module chosen at run time with
`importlib.import_module()` or `__import__()`.

```python
import pathlib
import tempfile
from modulefinder import ModuleFinder

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'helper.py').write_text("VALUE = 1\n")
    (root / 'app.py').write_text(
        "import helper\n"
        "def never_called():\n"
        "    import lazy_dep\n"
        "try:\n"
        "    import optional_dep\n"
        "except ImportError:\n"
        "    optional_dep = None\n"
        "if False:\n"
        "    import dropped\n"
        "import importlib\n"
        "plugin = importlib.import_module('plugin')\n"
        "raise SystemExit('the script ran')\n"
    )

    finder = ModuleFinder(path=[tmp])  # O(1)
    finder.run_script(str(root / 'app.py'))  # O(c + u·(p + e)); app.py never runs

    assert set(finder.modules) == {'__main__', 'helper'}
    assert set(finder.badmodules) == {'lazy_dep', 'optional_dep', 'importlib'}
    assert 'plugin' not in finder.badmodules  # chosen at run time, so never seen
    assert 'dropped' not in finder.badmodules  # removed by the compiler
```

## Every New Name Searches the Path

A name already in `modules` or `badmodules` is a dict lookup. A new name is a search of the path,
and the finder invalidates the process's import caches before each one, so the directories that
search probes are listed again every time rather than once per run. The invalidation walks every
cached path finder, and each package directory the finder searches adds one, so a large analysis
pays for the packages already found on every later lookup. A short `path` is cheaper as well as
narrower: a name it does not reach goes to `badmodules` instead of into the analysis.

```python
import pathlib
import tempfile
from modulefinder import ModuleFinder

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'app.py').write_text("import json\nimport json\nimport sys\n")

    narrow = ModuleFinder(path=[tmp])
    narrow.run_script(str(root / 'app.py'))  # one search for json, not two

    assert narrow.badmodules == {'json': {'__main__': 1}}
    assert narrow.modules['sys'].__file__ is None  # builtin: found without a search

    full = ModuleFinder()  # sys.path: json and everything it imports are compiled too
    full.run_script(str(root / 'app.py'))
    assert 'json.decoder' in full.modules
    assert len(full.modules) > len(narrow.modules)
```

## Deep Import Chains

The search is recursive: each first-time import adds several Python frames under the one that
reached it, so stack depth follows the longest chain of first-time imports. A long enough chain
exhausts the default recursion limit, and the `RecursionError` propagates out of `run_script()`
rather than being recorded as a missing module.

```python
import pathlib
import sys
import tempfile
from modulefinder import ModuleFinder

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    depth = 400
    for index in range(depth):
        body = f"import m{index + 1}\n" if index + 1 < depth else "x = 1\n"
        (root / f'm{index}.py').write_text(body)
    (root / 'app.py').write_text("import m0\n")

    limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(1_000)  # the default
        try:
            ModuleFinder(path=[tmp]).run_script(str(root / 'app.py'))
        except RecursionError:
            pass
        else:
            raise AssertionError('a 400-module chain fit in the default recursion limit')

        sys.setrecursionlimit(20_000)
        finder = ModuleFinder(path=[tmp])
        finder.run_script(str(root / 'app.py'))
    finally:
        sys.setrecursionlimit(limit)
    assert len(finder.modules) == depth + 1
```

## Reporting Missing Modules

`badmodules` records every name that failed and which modules asked for it. `any_missing_maybe()`
sorts those names into the certainly missing and the ones that might be a global the package
defines instead, and `report()` prints both after the modules found. A name in `excludes` is not
searched or analysed, and neither `any_missing()` nor `report()` lists it.

```python
import contextlib
import io
import pathlib
import tempfile
from modulefinder import ModuleFinder

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'heavy.py').write_text("import something_else\n")
    (root / 'app.py').write_text("import heavy\nimport absent\n")

    finder = ModuleFinder(path=[tmp], excludes=['heavy'])
    finder.run_script(str(root / 'app.py'))

    assert 'heavy' not in finder.modules  # excluded, so its imports were never read
    assert finder.badmodules['absent'] == {'__main__': 1}
    assert finder.any_missing_maybe() == (['absent'], [])  # O(m log m)
    assert finder.any_missing() == ['absent']

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        finder.report()  # O(n log n + b log b)
    assert '? absent imported from __main__' in out.getvalue()
```

## Packages the Finder Cannot Follow

A package that extends its own `__path__` at run time, or installs itself under another name, does
it by running code the finder never runs. `AddPackagePath()` and `ReplacePackage()` tell it
instead. Both write to module-level tables, so they affect every finder in the process from then
on, not just the next one.

```python
import pathlib
import tempfile
import modulefinder

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'pkg').mkdir()
    (root / 'pkg' / '__init__.py').write_text("")
    (root / 'extra').mkdir()
    (root / 'extra' / 'plugin.py').write_text("")
    (root / 'app.py').write_text("from pkg import plugin\n")

    before = modulefinder.ModuleFinder(path=[tmp])
    before.run_script(str(root / 'app.py'))
    assert 'pkg.plugin' in before.badmodules

    modulefinder.AddPackagePath('pkg', str(root / 'extra'))  # O(1)
    after = modulefinder.ModuleFinder(path=[tmp])
    after.run_script(str(root / 'app.py'))
    assert 'pkg.plugin' in after.modules
    assert after.modules['pkg'].__path__ == [str(root / 'pkg'), str(root / 'extra')]
    modulefinder.packagePathMap.pop('pkg')  # undo, or later finders keep the path
```

## Performance Best Practices

✅ **Do**:

- Pass a `path` holding only the directories you mean to analyse; every new name searches it
- Put large dependencies you do not need to trace in `excludes`, so none of their imports are read
- Read `modules` and `badmodules` directly; they are the finder's own dicts, not copies
- Drop the finder when done: it holds every module's compiled code until then

❌ **Avoid**:

- Expecting `run_script()` to find imports chosen at run time; it reads statements, not behaviour
- Analysing a script with a very deep chain of first-time imports under the default recursion
  limit
- Calling `AddPackagePath()` or `ReplacePackage()` for one analysis and leaving the entry behind;
  every later finder in the process uses it

## Related Modules

- **[importlib](importlib.md)** - The import system whose path search every lookup repeats
- **[dis](dis.md)** - The bytecode the finder reads import statements from
- **[pkgutil](pkgutil.md)** - Walk the modules a package or path provides, without reading their imports
- **[pyclbr](pyclbr.md)** - Another reader of source that never runs it, for classes and functions
