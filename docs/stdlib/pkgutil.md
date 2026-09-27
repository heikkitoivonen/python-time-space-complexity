# pkgutil Module Complexity

The `pkgutil` module finds the modules and packages on a search path, walks package trees, and
reads data files that ship inside a package. Its unit of work is a directory listing: discovering
modules means listing directories, and nothing is cached between calls except the finders the
import system itself caches.

Discovery is lazy, but it is not free of side effects. `walk_packages()` imports every package it
finds in order to read its `__path__`, and `get_data()` imports the package whose data it reads.
Those imports run the package's own code, which no bound on this page can price.

`e` is the directory entries listed - every file and subdirectory in each directory searched, plus
every entry of each subdirectory checked for an `__init__` - and `w` is the entries in the largest
single directory listed. `m` is the module names one search yields - from one path, or one
package's `__path__` - `d` is package nesting depth, and `p` is the packages imported. `s` is the entries on a search path (`sys.path`, or a package's
`__path__`), `r` is the entries in the path `extend_path()` returns, `b` is the bytes in a data
file, and `a` is the dotted parts of a name. Bounds are for directories on the file system, the
common case; `sys.meta_path` and `sys.path_hooks` hold a handful of entries and count as O(1), and
the search bounds take the import system's finder caches as already filled.

## Complexity Reference

### Discovering modules

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pkgutil.iter_modules(path=None, prefix='')` | O(e log e) | O(w + m) | Lazy; each directory is listed and sorted when iteration reaches it, and each subdirectory without a dot in its name is listed in full, package or not. `path=None` searches `sys.path` |
| `pkgutil.walk_packages(path=None, prefix='', onerror=None)` | O(e log e) plus importing p packages | O(d·(w + m)) plus p packages | Lazy; imports each package it yields, never a plain module, and the imports stay in `sys.modules`. `path=None` walks everything on `sys.path` |
| `pkgutil.ModuleInfo(module_finder, name, ispkg)` | O(1) | O(1) | A named tuple; what both functions above yield |
| `ModuleInfo.module_finder`, `ModuleInfo.name`, `ModuleInfo.ispkg` | O(1) | O(1) | Tuple fields |

### Finders and loaders

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pkgutil.get_importer(path_item)` | O(1) | O(1) | A `sys.path_importer_cache` hit; on a miss it tries each path hook and caches the finder it gets |
| `pkgutil.iter_importers(fullname='')` | O(s) | O(1) | Lazy; one `get_importer()` per entry. A dotted name imports its parent package to read `__path__` |
| `pkgutil.get_loader(module_or_name)` | O(1) imported, O(s) otherwise | O(1) | Python 3.10-3.13; an imported module's `__loader__`, otherwise `find_loader()` |
| `pkgutil.find_loader(fullname)` | O(s) | O(1) | Python 3.10-3.13; one `importlib.util.find_spec()` search |
| `pkgutil.ImpImporter(dirname=None)`, `pkgutil.ImpLoader(fullname, file, filename, etc)` | O(1) | O(1) | Python 3.10-3.11; deprecated emulations of the `imp` module that store their arguments |

### Package paths and data

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pkgutil.extend_path(path, name)` | O(s·r) | O(r) | One finder lookup per directory on the search path; each portion found is checked against the list being built. Returns a copy. Reading `<name>.pkg` files is not priced here |
| `pkgutil.get_data(package, resource)` | O(s + b) | O(b) | Reads the whole file into one `bytes`; imports the package first if it is not imported yet |
| `pkgutil.resolve_name(name)` | O(a) imports | O(a) | `'pkg.mod:obj.attr'` is one import; without the colon, one import attempt per dotted part until one fails |

## Listing Modules

`iter_modules()` builds nothing until it is iterated. When it reaches a directory it lists and
sorts the whole directory, and lists every dot-free subdirectory to decide whether it is a
package, so a large data directory beside the modules is paid for even though it yields nothing.
Each result is a `ModuleInfo` naming the finder that found it.

```python
import os
import pkgutil
import tempfile

with tempfile.TemporaryDirectory() as root:
    for name in ('alpha.py', 'beta.py', 'notes.txt'):
        open(os.path.join(root, name), 'w').close()
    os.mkdir(os.path.join(root, 'gamma'))
    open(os.path.join(root, 'gamma', '__init__.py'), 'w').close()
    os.mkdir(os.path.join(root, 'data'))  # listed, yields nothing

    modules = pkgutil.iter_modules([root])  # O(1) - nothing listed yet
    found = list(modules)                   # O(e log e)

    assert [info.name for info in found] == ['alpha', 'beta', 'gamma']
    assert [info.ispkg for info in found] == [False, False, True]  # O(1) field reads
    assert found[0].module_finder.path == root
```

With several directories on the path, a name found in an earlier one hides the same name in a
later one, as it would for `import`.

```python
import os
import pkgutil
import tempfile

with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
    open(os.path.join(first, 'shared.py'), 'w').close()
    open(os.path.join(second, 'shared.py'), 'w').close()
    open(os.path.join(second, 'extra.py'), 'w').close()

    found = list(pkgutil.iter_modules([first, second], prefix='plugins.'))  # O(e log e)

    assert [info.name for info in found] == ['plugins.shared', 'plugins.extra']
    assert found[0].module_finder.path == first
```

## Walking a Package Tree

`walk_packages()` has to import a package to learn where its submodules live, so walking a tree
runs the `__init__.py` of every package not imported yet and leaves those packages in
`sys.modules`. Plain modules are listed, not imported. For each level of the current descent it
holds one directory listing and the names that level has yielded, not the whole tree.

```python
import os
import pkgutil
import sys
import tempfile

with tempfile.TemporaryDirectory() as root:
    top = os.path.join(root, 'walkdemo')
    os.makedirs(os.path.join(top, 'sub'))
    for name in ('__init__.py', 'mod.py', 'sub/__init__.py', 'sub/leaf.py'):
        open(os.path.join(top, name), 'w').close()
    sys.path.insert(0, root)
    try:
        names = [info.name for info in pkgutil.walk_packages([top], 'walkdemo.')]
        # O(e log e) plus importing p packages

        assert names == ['walkdemo.mod', 'walkdemo.sub', 'walkdemo.sub.leaf']
        assert 'walkdemo.sub' in sys.modules      # imported to read its __path__
        assert 'walkdemo.mod' not in sys.modules  # modules are only listed
    finally:
        sys.path.remove(root)
```

A package that fails to import is reported to `onerror` if you pass one; without it an
`ImportError` is skipped silently and any other exception stops the walk.

```python
import os
import pkgutil
import sys
import tempfile

with tempfile.TemporaryDirectory() as root:
    top = os.path.join(root, 'brokendemo')
    os.makedirs(os.path.join(top, 'bad'))
    open(os.path.join(top, '__init__.py'), 'w').close()
    with open(os.path.join(top, 'bad', '__init__.py'), 'w') as f:
        f.write('import no_such_module_anywhere\n')
    sys.path.insert(0, root)
    try:
        failed = []
        names = [info.name for info in
                 pkgutil.walk_packages([top], 'brokendemo.', onerror=failed.append)]

        assert names == ['brokendemo.bad']  # yielded, then its import failed
        assert failed == ['brokendemo.bad']
    finally:
        sys.path.remove(root)
```

## Reading Package Data

`get_data()` locates the package, imports it if it is not imported yet, and reads the whole
resource into one `bytes` object. An unknown top-level package gives `None` rather than an
exception, and a missing resource raises `FileNotFoundError`.

```python
import os
import pkgutil
import sys
import tempfile

with tempfile.TemporaryDirectory() as root:
    top = os.path.join(root, 'datademo')
    os.makedirs(os.path.join(top, 'files'))
    open(os.path.join(top, '__init__.py'), 'w').close()
    with open(os.path.join(top, 'files', 'config.json'), 'w') as f:
        f.write('{"debug": true}')
    sys.path.insert(0, root)
    try:
        data = pkgutil.get_data('datademo', 'files/config.json')  # O(s + b)
        assert data == b'{"debug": true}'
        assert 'datademo' in sys.modules  # imported to find the file

        assert pkgutil.get_data('no_such_package_here', 'x.txt') is None
        try:
            pkgutil.get_data('datademo', 'missing.txt')
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('a missing resource was read')
    finally:
        sys.path.remove(root)
```

## Resolving Dotted Names

`resolve_name()` turns a string into an object. With a colon, the part before it is the module
and there is one import. Without one, the module boundary is unknown, so it tries an import for
each dotted part until one fails and walks the rest as attributes.

```python
import pkgutil
from collections import OrderedDict

assert pkgutil.resolve_name('collections:OrderedDict') is OrderedDict  # one import
assert pkgutil.resolve_name('collections.OrderedDict') is OrderedDict  # O(a) import attempts
assert pkgutil.resolve_name('os.path:join.__name__') == 'join'

try:
    pkgutil.resolve_name('not a name')
except ValueError as error:
    assert 'invalid format' in str(error)
else:
    raise AssertionError('a malformed name was resolved')
```

## Finders

`get_importer()` is the path-entry half of the import system: a hit in `sys.path_importer_cache`
returns the cached finder, and a miss asks each path hook and caches the answer.
`iter_importers()` yields the finders `import` would consult, one entry at a time.

```python
import pkgutil
import sys
import tempfile

with tempfile.TemporaryDirectory() as root:
    finder = pkgutil.get_importer(root)  # O(1) - a miss runs the path hooks once
    assert sys.path_importer_cache[root] is finder
    assert pkgutil.get_importer(root) is finder  # O(1) - cached

    del sys.path_importer_cache[root]

finders = pkgutil.iter_importers()  # O(1) - lazy
assert next(finders) is sys.meta_path[0]  # meta path finders first, then sys.path
```

## Extending a Package Path

`extend_path()` is the pre-PEP 420 way to split one package across several directories. It asks
the finder for each directory on the search path whether it holds a portion of the package, and
appends each portion it has not seen, which is a scan of the list built so far. The input list
is copied, not changed.

```python
import os
import pkgutil
import sys
import tempfile

with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
    for base in (one, two):
        os.makedirs(os.path.join(base, 'splitdemo'))
    original = [os.path.join(one, 'splitdemo')]
    sys.path[:0] = [one, two]
    try:
        extended = pkgutil.extend_path(original, 'splitdemo')  # O(s·r)

        assert extended == [os.path.join(one, 'splitdemo'), os.path.join(two, 'splitdemo')]
        assert original == [os.path.join(one, 'splitdemo')]  # the input is untouched
    finally:
        del sys.path[:2]
```

## Common Patterns

### Discovering Plugins Without Importing Them

List the plugin package once, and import each plugin only when it is asked for. The listing costs
the directory; each import costs that plugin's own code.

```python
import importlib
import os
import pkgutil
import sys
import tempfile

with tempfile.TemporaryDirectory() as root:
    top = os.path.join(root, 'plugindemo')
    os.makedirs(top)
    open(os.path.join(top, '__init__.py'), 'w').close()
    for name in ('csv_export', 'json_export'):
        with open(os.path.join(top, name + '.py'), 'w') as f:
            f.write(f'NAME = {name!r}\n')
    sys.path.insert(0, root)
    try:
        package = importlib.import_module('plugindemo')
        available = {
            info.name: f'plugindemo.{info.name}'
            for info in pkgutil.iter_modules(package.__path__)  # O(e log e)
            if not info.ispkg
        }
        assert sorted(available) == ['csv_export', 'json_export']
        assert 'plugindemo.json_export' not in sys.modules  # nothing imported yet

        plugin = importlib.import_module(available['json_export'])  # on demand
        assert plugin.NAME == 'json_export'
    finally:
        sys.path.remove(root)
```

## Performance Best Practices

✅ **Do**:

- Pass `iter_modules()` or `walk_packages()` a package's `__path__`, so only that package's
  directories are listed
- Use `iter_modules()` when one level is enough; it imports nothing
- Keep bulky data directories out of the directories you scan: each subdirectory without a dot in
  its name is listed in full to check for an `__init__`
- Write `'module:attribute'` for `resolve_name()`, which needs one import instead of one per part

❌ **Avoid**:

- `walk_packages()` with no path - it lists all of `sys.path` and imports every package there
- Calling `get_data()` for a large file you only need part of - it reads the whole file
- Rescanning a plugin directory on every lookup; keep the list the first scan produced

## Version Notes

- **Python 3.12+**: `ImpImporter` and `ImpLoader` are removed; `get_loader()` and `find_loader()`
  are deprecated in favour of `importlib.util.find_spec()`
- **Python 3.14+**: `get_loader()` and `find_loader()` are removed

## Related Modules

- **[importlib](importlib.md)** - `find_spec()` and `import_module()`, which `pkgutil` is built on
- **[zipimport](zipimport.md)** - the finder `iter_modules()` uses for a zip archive on the path
- **[sys](sys.md)** - `sys.path`, `sys.path_hooks` and `sys.path_importer_cache`
