# importlib Module Complexity

The `importlib` package is the import system as a library: the finders that locate a module
along `sys.meta_path` and `sys.path`, the loaders that read, compile and run it, and the
`sys.modules` cache in front of both. Two sibling packages read what ships beside the code:
`importlib.metadata` parses the `.dist-info` directories of installed distributions, and
`importlib.resources` opens data files inside a package. Finding a loaded module is one dictionary
probe; finding an unloaded one is a walk over path entries, each backed by a directory listing that
is cached until the directory changes. Loading is a file read, an unmarshal or a compile, and then
the module's own body.

Names and paths are treated as O(1) to hash, split and join. `p` is the entries on the path being
searched (`sys.path`, or a package's `__path__`), `s` is the registered file suffixes, `e` is the
entries in one directory a finder lists, `n` is the bytes in a module's source or bytecode file,
`m` is the time and space the module's body itself takes, `t` is the finders on `sys.meta_path`, `c`
is the entries in `sys.path_importer_cache`, `b` and `f` are the built-in and frozen module tables of the
build, and `D` is the frames on the call stack. For distributions, `d` is the distributions found on
the path, `h` is the headers in one `METADATA` file, `E` is the entry points read, `F` is the entries
in the file lists read (`RECORD`, or an egg-info `installed-files.txt` or `SOURCES.txt`), summed
over the distributions read, and `q` is the top-level names the distributions declare. Parsing is priced in
headers, treating each header's value and the description body as O(1). For resources, `k` is the
children of a resource directory, summed over the `r` portions of a namespace package, and `z` is
the entries in a zip archive.

## Complexity Reference

### importlib

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `importlib.import_module(name, package=None)` | O(1) | O(1) | Loaded module: a `sys.modules` lookup, and the same object every time. Not loaded: a find, O(t + p·s), and a load, O(n + m), for each missing parent package and then the module |
| `importlib.reload(module)` | O(t + p·s + n + m) | O(n + m) | Finds the spec again and runs the body in the existing namespace; modules it imports are not re-run |
| `importlib.invalidate_caches()` | O(t + c) | O(c) | Every meta path finder, then every path entry finder in `sys.path_importer_cache`, and from Python 3.11 the `importlib.metadata` listings; the next search through each directory relists it, O(e) |
| `importlib.__import__(name, globals=None, locals=None, fromlist=(), level=0)` | O(1) | O(1) | A pure-Python implementation of the built-in `__import__()`, which is the function the `import` statement calls; the same miss cost as `import_module()`, but a dotted name returns the head of that name - the top-level package for an absolute import, the first component under the anchor for a relative one - unless `fromlist` is non-empty. Then one attribute check per `fromlist` name, an import of each one the package lacks, and `'*'` expands to the package's `__all__`; a module without `__path__` skips the list entirely |

### importlib.util

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `importlib.util.find_spec(name, package=None)` | O(1) | O(1) | Loaded module: its own `__spec__`. Otherwise imports the parent package, raising `ModuleNotFoundError` when that is missing, and searches, O(t + p·s); the search itself does not execute the module it finds |
| `importlib.util.module_from_spec(spec)` | O(1) | O(1) | A new empty module with its import attributes set; the loader's `create_module()` runs here, which for an extension module loads the shared library |
| `importlib.util.spec_from_file_location(name, location, *, loader=None, submodule_search_locations=...)` | O(s) | O(s) | Picks the loader by suffix, building each loader's suffix tuple; nothing is read |
| `importlib.util.spec_from_loader(name, loader, *, origin=None, is_package=None)` | O(1) | O(1) | Asks the loader `is_package()` when not told |
| `importlib.util.resolve_name(name, package)` | O(1) | O(1) | Strips one package level per leading dot; raises `ImportError` past the top |
| `importlib.util.cache_from_source(path, debug_override=None, *, optimization=None)`, `importlib.util.source_from_cache(path)` | O(1) | O(1) | Path arithmetic; neither file need exist |
| `importlib.util.decode_source(source_bytes)` | O(n) | O(n) | Detects the encoding from the first two lines, decodes and normalises newlines |
| `importlib.util.source_hash(source_bytes)` | O(n) | O(1) | The 8-byte hash stored in hash-based `.pyc` files |
| `importlib.util.LazyLoader(loader)`, `LazyLoader.factory(loader)` | O(1) | O(1) | Wraps a loader that defines `exec_module()` |
| `LazyLoader.create_module(spec)`, `LazyLoader.exec_module(module)` | O(1) | O(1) | `create_module()` is the wrapped loader's; `exec_module()` copies the module's attributes, a handful on a fresh module, and defers the wrapped loader; the first attribute access then pays O(n + m) once |
| `importlib.util.MAGIC_NUMBER` | O(1) | O(1) | The bytecode magic of this interpreter |
| `importlib.util._incompatible_extension_module_restrictions(*, disable_check)` | O(1) | O(1) | Python 3.12+; a context manager over one flag of a subinterpreter, and `RuntimeError` on entry in the main one |

### importlib.machinery

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `importlib.machinery.ModuleSpec(name, loader, *, origin=None, loader_state=None, is_package=None)` | O(1) | O(1) | |
| `ModuleSpec.name`, `ModuleSpec.loader`, `ModuleSpec.origin`, `ModuleSpec.loader_state`, `ModuleSpec.submodule_search_locations`, `ModuleSpec.has_location`, `ModuleSpec.parent` | O(1) | O(1) | Attributes; `parent` is a split of `name` |
| `ModuleSpec.cached` | O(1) | O(1) | Derived from `origin` on first access and stored |
| `importlib.machinery.PathFinder.find_spec(fullname, path=None, target=None)` | O(p·s) | O(1) | One path entry finder per entry, stopping at the first hit, plus O(e) for each directory listed for the first time or since it changed; a namespace package visits every entry and collects its portions, O(p) |
| `PathFinder.invalidate_caches()` | O(c) | O(c) | Snapshots `sys.path_importer_cache`, drops relative entries and calls each cached finder's `invalidate_caches()` |
| `PathFinder.find_distributions(context)` | O(p + d) | O(d) | Delegates to `importlib.metadata.MetadataPathFinder` below |
| `importlib.machinery.FileFinder(path, *loader_details)` | O(s) | O(s) | Nothing is listed yet |
| `FileFinder.find_spec(fullname, target=None)` | O(s) | O(e) | One `stat()` of the directory, a set probe per suffix and an `isfile()` per candidate the listing holds, or per suffix for the `__init__` of a name that is a directory; O(e) to relist when the directory's mtime changed, and the listing is kept |
| `FileFinder.invalidate_caches()` | O(1) | O(1) | Forgets the mtime, so the next search relists |
| `FileFinder.path_hook(*loader_details)`, `FileFinder.path` | O(1) | O(1) | The hook it returns does one `isdir()` per path entry |
| `importlib.machinery.BuiltinImporter.find_spec(fullname, path=None, target=None)` | O(b) | O(1) | Scans the built-in table |
| `importlib.machinery.FrozenImporter.find_spec(fullname, path=None, target=None)` | O(f) | O(1) | Scans the frozen table |
| `importlib.machinery.SourceFileLoader(fullname, path)`, `importlib.machinery.SourcelessFileLoader(fullname, path)`, `importlib.machinery.ExtensionFileLoader(name, path)` | O(1) | O(1) | Hold the name and path |
| `SourceFileLoader.get_code(fullname)` | O(n) | O(n) | Reads and unmarshals the `.pyc` when the source's recorded mtime and size still match, or, under the default `--check-hash-based-pycs` policy, for a checked hash-based `.pyc` when the source hashes to what it recorded and for an unchecked one always; otherwise reads and compiles the source and writes the cache |
| `SourceFileLoader.exec_module(module)` | O(n + m) | O(n + m) | `get_code()`, then the body |
| `SourceFileLoader.get_source(fullname)`, `SourceFileLoader.get_data(path)` | O(n) | O(n) | The whole file; `get_source()` also decodes it |
| `SourceFileLoader.set_data(path, data)` | O(n) | O(1) | Writes the bytes it is given to a temporary file and renames it into place, creating missing directories |
| `SourceFileLoader.source_to_code(data, path)` | O(n) | O(n) | `compile()` |
| `SourceFileLoader.get_filename(fullname)`, `SourceFileLoader.is_package(fullname)`, `SourceFileLoader.path_stats(path)`, `SourceFileLoader.create_module(spec)`, `SourceFileLoader.get_resource_reader(module)`, `SourceFileLoader.name`, `SourceFileLoader.path` | O(1) | O(1) | `path_stats()` is one `stat()`; `create_module()` returns `None` |
| `SourceFileLoader.load_module(fullname)` | O(n + m) | O(n + m) | Deprecated; `exec_module()` behind a spec |
| `SourcelessFileLoader.get_code(fullname)` | O(n) | O(n) | Reads and unmarshals; there is no source to check against |
| `SourcelessFileLoader.get_source(fullname)`, `SourcelessFileLoader.name`, `SourcelessFileLoader.path` | O(1) | O(1) | `get_source()` is always `None` |
| `ExtensionFileLoader.create_module(spec)`, `ExtensionFileLoader.exec_module(module)` | O(1) | O(1) | Python-side; `create_module()` loads the shared library and runs its init function, `exec_module()` its exec slots |
| `ExtensionFileLoader.get_code(fullname)`, `ExtensionFileLoader.get_source(fullname)`, `ExtensionFileLoader.get_filename(fullname)`, `ExtensionFileLoader.is_package(fullname)`, `ExtensionFileLoader.name`, `ExtensionFileLoader.path` | O(1) | O(1) | `get_code()` and `get_source()` are always `None`; `is_package()` compares the filename against each suffix, O(s) |
| `importlib.machinery.NamespaceLoader` | O(1) | O(1) | Constructing one snapshots the parent path, O(p); `create_module()` and `exec_module()` do nothing; `get_source()` is `''`, `get_code()` compiles it, `is_package()` is `True`; the package's `__path__` is recomputed, O(p·s), whenever `sys.path` or the parent's `__path__` changes |
| `importlib.machinery.WindowsRegistryFinder.find_spec(fullname, path=None, target=None)` | O(s) | O(1) | Windows only: one registry lookup, one `stat()` and a suffix match |
| `importlib.machinery.AppleFrameworkLoader.create_module(spec)`, `AppleFrameworkLoader.name`, `AppleFrameworkLoader.path` | O(1) | O(1) | iOS only, Python 3.13+: `create_module()` reads the `.fwork` redirect, then loads as `ExtensionFileLoader` does |
| `importlib.machinery.all_suffixes()` | O(s) | O(s) | A new list each call |
| `importlib.machinery.SOURCE_SUFFIXES`, `importlib.machinery.BYTECODE_SUFFIXES`, `importlib.machinery.EXTENSION_SUFFIXES` | O(1) | O(1) | Lists fixed at startup |
| `importlib.machinery.DEBUG_BYTECODE_SUFFIXES`, `importlib.machinery.OPTIMIZED_BYTECODE_SUFFIXES` | O(1) | O(1) | Same contents as `BYTECODE_SUFFIXES`; deprecated in Python 3.14 |

### importlib.abc

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `importlib.abc.MetaPathFinder`, `importlib.abc.PathEntryFinder`, `importlib.abc.Loader`, `importlib.abc.ResourceLoader`, `importlib.abc.InspectLoader`, `importlib.abc.ExecutionLoader`, `importlib.abc.FileLoader`, `importlib.abc.SourceLoader` | O(1) | O(1) | Ordinary class creation to subclass; the concrete machinery classes are registered with them, so `isinstance()` and `issubclass()` hold for a `FileFinder` or `SourceFileLoader` |
| `MetaPathFinder.find_spec(fullname, path, target=None)`, `PathEntryFinder.find_spec(fullname, target=None)`, `Loader.exec_module(module)` | Defined by the subclass | Defined by the subclass | The ABCs leave them undefined; the import system pays whatever the subclass does, once per search or load |
| `MetaPathFinder.invalidate_caches()`, `PathEntryFinder.invalidate_caches()`, `Loader.create_module(spec)` | O(1) | O(1) | Default no-ops |
| `Loader.load_module(fullname)`, `InspectLoader.load_module(fullname)`, `FileLoader.load_module(fullname)` | O(n + m) | O(n + m) | Deprecated shim: builds a spec, then `exec_module()`; a `Loader` that defines no `exec_module()` raises `ImportError` instead |
| `ResourceLoader.get_data(path)`, `InspectLoader.get_source(fullname)`, `ExecutionLoader.get_filename(fullname)` | Defined by the subclass | Defined by the subclass | Abstract |
| `InspectLoader.get_code(fullname)`, `ExecutionLoader.get_code(fullname)` | O(n) | O(n) | `get_source()` then `source_to_code()`: a compile on every call, with no bytecode cache at this level |
| `InspectLoader.source_to_code(data, path='<string>')` | O(n) | O(n) | `compile()` |
| `InspectLoader.is_package(fullname)` | O(1) | O(1) | Raises `ImportError` unless overridden |
| `FileLoader.get_data(path)` | O(n) | O(n) | The whole file |
| `FileLoader.get_filename(fullname)`, `FileLoader.get_resource_reader(module)`, `FileLoader.name`, `FileLoader.path` | O(1) | O(1) | |
| `SourceLoader.get_code(fullname)` | O(n) | O(n) | `path_stats()` on the source, `get_data()` on the cache path and then the source, `set_data()` to write the cache; each is the subclass's method |
| `SourceLoader.get_source(fullname)` | O(n) | O(n) | `get_data()` then `decode_source()` |
| `SourceLoader.source_to_code(data, path)` | O(n) | O(n) | `compile()` |
| `SourceLoader.is_package(fullname)`, `SourceLoader.path_mtime(path)`, `SourceLoader.path_stats(path)`, `SourceLoader.set_data(path, data)` | O(1) | O(1) | `path_mtime()` raises `OSError` and `set_data()` does nothing unless overridden; `path_stats()` wraps `path_mtime()` |

### importlib.resources

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `importlib.resources.files(anchor=None)` | O(1) | O(1) | A file-system package; a `str` anchor is imported first, and a namespace package resolves and checks each of its portions. A zip archive is opened and its central directory read, O(z), on every call, and the first probe of the result indexes the names, O(z), once. No anchor (Python 3.12+) walks the whole call stack, O(D), to find the caller's module |
| `importlib.resources.as_file(traversable)` | O(1) | O(1) | A real file is yielded as the same object; a resource inside a zip is copied to a temporary file, O(n), and from Python 3.12 a directory copied whole |
| `Traversable.joinpath(*descendants)` | O(1) | O(1) | For a file-system path. A namespace package's `MultiplexedPath` lists its portions, empty or not, for a segment that spans them, and joins as a plain path once a segment resolves to one directory: at worst O(r + k²) on Python 3.10, which de-duplicates names with a list scan, and O(r + k) on 3.11, both stopping at the first match; O(r + k log k) from 3.12, where the protocol default it now uses sorts every portion to merge them |
| `Traversable.iterdir()` | O(k) | O(k) | A namespace package lists every portion, empty or not, and merges them: O(r + k²) on Python 3.10, O(r + k) on 3.11 and O(r + k log k) from 3.12, which sorts them; a zip archive filters every entry, O(z) |
| `Traversable.read_bytes()`, `Traversable.read_text(encoding=None)` | O(n) | O(n) | The whole resource |
| `Traversable.open(mode='r', *args, **kwargs)`, `Traversable.is_dir()`, `Traversable.is_file()`, `Traversable.name` | O(1) | O(1) | One `stat()` or archive lookup |
| `importlib.resources.read_text(anchor, *path_names, encoding='utf-8', errors='strict')`, `importlib.resources.read_binary(anchor, *path_names)`, `importlib.resources.open_text(anchor, *path_names, encoding='utf-8', errors='strict')`, `importlib.resources.open_binary(anchor, *path_names)`, `importlib.resources.path(anchor, *path_names)`, `importlib.resources.is_resource(anchor, *path_names)` | O(n) | O(n) | `files()` and `joinpath()` again on every call, then the operation; the `open*()` and `is_resource()` forms are O(1) after that |
| `importlib.resources.contents(anchor, *path_names)` | O(k) | O(k) | The names from `iterdir()`, as a list before Python 3.13 and a generator from it; deprecated on 3.11 and again from 3.13 |
| `importlib.resources.Anchor`, `importlib.resources.Package` | O(1) | O(1) | Type aliases for a module or its name; `Anchor` from Python 3.12 |

### importlib.resources.abc

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `importlib.resources.abc.Traversable`, `importlib.resources.abc.ResourceReader`, `importlib.resources.abc.TraversableResources` | O(1) | O(1) | Protocols; their concrete costs are the rows above |
| `ResourceReader.open_resource(resource)`, `ResourceReader.resource_path(resource)`, `ResourceReader.is_resource(path)`, `ResourceReader.contents()`, `TraversableResources.files()` | Defined by the subclass | Defined by the subclass | Abstract |
| `TraversableResources.open_resource(resource)`, `TraversableResources.is_resource(path)`, `TraversableResources.contents()` | O(1) | O(1) | `files().joinpath()` and one operation; `contents()` is O(k) |
| `TraversableResources.resource_path(resource)` | O(1) | O(1) | Always raises `FileNotFoundError`; the file-system path protocol is not offered |

### importlib.metadata

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `importlib.metadata.distributions(**kwargs)`, `Distribution.discover(**kwargs)` | O(p + d) | O(d) | Lazy; consuming it visits every path entry. Each directory is listed once, O(e), and the listing reused until its mtime changes, from a cache that holds 128 path entries |
| `importlib.metadata.distribution(distribution_name)`, `Distribution.from_name(name)` | O(p) | O(1) | A dictionary probe per path entry until the first match, on the same cached listings; no metadata is read |
| `importlib.metadata.version(distribution_name)`, `importlib.metadata.metadata(distribution_name)`, `importlib.metadata.requires(distribution_name)` | O(p + h) | O(h) | Find, then read and parse the whole `METADATA` file |
| `importlib.metadata.files(distribution_name)` | O(p + F) | O(F) | `RECORD` parsed, and from Python 3.12 one `stat()` per listed file, with the missing ones dropped |
| `importlib.metadata.entry_points(**params)` | O(p + d + E) | O(d + E) | Reads the `entry_points.txt` of every distinctly named distribution, whatever the selection; the filter runs afterwards over all of them, after a sort by group on Python 3.10 and 3.11, O(E log E) |
| `importlib.metadata.packages_distributions()` | O(p + d + q·h + F) | O(d + q + h + F) | `top_level.txt` per distribution, or from Python 3.11 its `RECORD` where that is missing, with a `stat()` per file from 3.12; the `METADATA` name is parsed again for every name declared |
| `importlib.metadata.Distribution` | O(1) | O(1) | Abstract; `Distribution.at(path)` wraps a path without reading it |
| `Distribution.metadata`, `Distribution.name`, `Distribution.version`, `Distribution.requires` | O(h) | O(h) | Read and parsed from the file on every access; nothing is kept on the object. `requires` falls back to an egg-info `requires.txt`, linear in its lines |
| `Distribution.origin` | O(n) | O(n) | Parses `direct_url.json` on every access, or `None` without one; Python 3.13+ |
| `Distribution.entry_points` | O(E) | O(E) | Parses `entry_points.txt` on every access |
| `Distribution.files` | O(F) | O(F) | Parses `RECORD`, or the egg-info file list, on every access, with a `stat()` per file from Python 3.12 |
| `Distribution.read_text(filename)` | O(n) | O(n) | One file, or `None` |
| `Distribution.locate_file(path)` | O(1) | O(1) | A path join |
| `importlib.metadata.PackageMetadata` | O(1) | O(1) | Protocol of the parsed `METADATA` file |
| `PackageMetadata.get(name, failobj=None)`, `metadata[key]`, `key in metadata` | O(h) | O(1) | A case-insensitive scan over the headers |
| `PackageMetadata.get_all(name, failobj=None)`, `iter(metadata)` | O(h) | O(h) | The scan, keeping every match or every name |
| `len(metadata)` | O(1) | O(1) | The stored header count |
| `PackageMetadata.json` | O(h²) | O(h) | One scan per header, and a `get_all()` scan for each multi-use key |
| `importlib.metadata.EntryPoint(name, value, group)` | O(1) | O(1) | |
| `EntryPoint.name`, `EntryPoint.value`, `EntryPoint.group`, `EntryPoint.dist`, `EntryPoint.pattern` | O(1) | O(1) | |
| `EntryPoint.module`, `EntryPoint.attr`, `EntryPoint.extras` | O(1) | O(1) | The regex over `value` runs again on every access |
| `EntryPoint.matches(**params)` | O(1) | O(1) | One attribute compare per keyword |
| `EntryPoint.load()` | O(1) | O(1) | `import_module()` and a `getattr()` per dotted attribute; the import's own cost if the module is not loaded |
| `importlib.metadata.EntryPoints(iterable)` | O(E) | O(E) | A tuple from Python 3.12, a list before |
| `EntryPoints.select(**params)`, `EntryPoints.names`, `EntryPoints.groups`, `entry_points[name]` | O(E) | O(E) | Linear scans; subscripting takes a name and is a `select()` rather than a dictionary lookup; a position raises `KeyError` from Python 3.12 |
| `importlib.metadata.PackagePath` | O(1) | O(1) | A `PurePosixPath` with `PackagePath.hash`, `PackagePath.size` and `PackagePath.dist` |
| `PackagePath.read_text(encoding='utf-8')`, `PackagePath.read_binary()` | O(n) | O(n) | The whole file |
| `PackagePath.locate()` | O(1) | O(1) | `dist.locate_file()` |
| `importlib.metadata.PackageNotFoundError`, `PackageNotFoundError.name` | O(1) | O(1) | Raised by every by-name lookup that finds nothing |
| `importlib.metadata.DistributionFinder`, `DistributionFinder.Context(**kwargs)`, `Context.name`, `Context.path` | O(1) | O(1) | `path` defaults to `sys.path` |
| `DistributionFinder.find_distributions(context)` | Defined by the subclass | Defined by the subclass | Abstract |
| `importlib.metadata.MetadataPathFinder.find_distributions(context)` | O(p + d) | O(d) | The `sys.meta_path` finder behind `distributions()` |
| `MetadataPathFinder.invalidate_caches()` | O(1) | O(1) | Drops every cached directory listing; `importlib.invalidate_caches()` calls it from Python 3.11 |
| `importlib.metadata.PathDistribution(path)`, `PathDistribution.read_text(filename)`, `PathDistribution.locate_file(path)` | O(1) | O(1) | The file-system `Distribution`; `read_text()` is O(n) |

## Importing by Name

### The Module Cache

An import of a loaded module is a dictionary lookup, and returns the object already in
`sys.modules`. No finder is consulted, so a finder that counts its calls sees nothing.

```python
import importlib
import json
import sys

class CountingFinder:
    calls = 0

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        cls.calls += 1
        return None

sys.meta_path.insert(0, CountingFinder)
try:
    assert importlib.import_module('json') is json  # O(1) - one sys.modules probe
    assert importlib.import_module('json.decoder') is json.decoder  # O(1)
    assert CountingFinder.calls == 0

    try:
        importlib.import_module('no_such_module_anywhere')  # O(t + p·s) - every finder, every entry
    except ModuleNotFoundError as error:
        assert error.name == 'no_such_module_anywhere'
    else:
        raise AssertionError('a missing module was imported')
    assert CountingFinder.calls == 1
finally:
    sys.meta_path.remove(CountingFinder)
```

### A Miss Walks the Path

A module that is not loaded is searched for one path entry at a time, in order, and the search
stops at the first entry that has it. Each directory entry costs at least one `stat()` and a set probe per
suffix while its listing is current, so a long `sys.path` is paid for on every miss and on every first import.

```python
import importlib
import importlib.util
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    first, second = Path(tmp, 'first'), Path(tmp, 'second')
    first.mkdir()
    second.mkdir()
    (first / 'shadowed.py').write_text('WHERE = "first"\n')
    (second / 'shadowed.py').write_text('WHERE = "second"\n')

    sys.path[:0] = [str(first), str(second)]
    try:
        spec = importlib.util.find_spec('shadowed')  # O(t + p·s) - stops at the first hit
        assert spec.origin == str(first / 'shadowed.py')

        module = importlib.import_module('shadowed')  # O(t + p·s + n + m)
        assert module.WHERE == 'first'
        assert importlib.import_module('shadowed') is module  # O(1) from here on
    finally:
        del sys.path[:2]
        sys.modules.pop('shadowed', None)
        sys.path_importer_cache.pop(str(first), None)
        sys.path_importer_cache.pop(str(second), None)
```

### Directory Listings Are Cached by Mtime

A `FileFinder` lists its directory once, O(e), and keeps the listing while the directory's mtime
is unchanged. A file created without touching the mtime is invisible until
`invalidate_caches()` forgets it, which is why a module written at runtime can fail to import.

```python
import importlib
import os
import tempfile
from importlib.machinery import FileFinder, SourceFileLoader
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    finder = FileFinder(tmp, (SourceFileLoader, ['.py']))  # O(s) - lists nothing yet
    assert finder.find_spec('late') is None  # O(e) - first search lists the directory

    stat = os.stat(tmp)
    Path(tmp, 'late.py').write_text('X = 1\n')
    os.utime(tmp, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # hide the change

    assert finder.find_spec('late') is None  # O(s) - the cached listing is trusted

    finder.invalidate_caches()  # O(1)
    spec = finder.find_spec('late')  # O(e) - relists
    assert spec is not None and spec.origin == str(Path(tmp, 'late.py'))

# importlib.invalidate_caches() does the same for every cached finder - O(t + c)
importlib.invalidate_caches()
```

### Bytecode Caching

The first import of a source module reads and compiles it and writes a `.pyc` beside it. A later
import in another process, or in this one once the module has left `sys.modules`, reads and
unmarshals the `.pyc` instead, and compiles again only when the `.pyc` is missing or invalid or
records an mtime or size the source no longer has.

```python
import importlib
import importlib.util
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp, 'compiled_once.py')
    source.write_text('VALUE = 1\n')
    sys.path.insert(0, tmp)
    try:
        module = importlib.import_module('compiled_once')  # O(n + m) - compiles and caches
        cached = Path(module.__cached__)
        assert cached == Path(importlib.util.cache_from_source(str(source)))  # O(1)
        assert cached.exists()
        assert cached.read_bytes()[:4] == importlib.util.MAGIC_NUMBER

        assert importlib.util.source_from_cache(str(cached)) == str(source)  # O(1)

        del sys.modules['compiled_once']
        again = importlib.import_module('compiled_once')  # O(n + m) - unmarshals the .pyc
        assert again.VALUE == 1
    finally:
        sys.path.remove(tmp)
        sys.modules.pop('compiled_once', None)
        sys.path_importer_cache.pop(tmp, None)
```

## Finding Without Loading

`find_spec()` locates a module and returns its spec without running it, so it is the check to use
when a module must not be executed before it is chosen; only a parent package's own body, which
does run, could import it first. The search is the one a failed import
would pay, and a hit searches again when the import follows. For a loaded module it returns the
module's own `__spec__` in O(1).

```python
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

assert importlib.util.find_spec('json') is json.__spec__  # O(1)
assert importlib.util.find_spec('no_such_module_anywhere') is None  # O(t + p·s)

with tempfile.TemporaryDirectory() as tmp:
    Path(tmp, 'explosive.py').write_text('raise RuntimeError("body ran")\n')
    sys.path.insert(0, tmp)
    try:
        spec = importlib.util.find_spec('explosive')  # O(t + p·s) - found, not executed
        assert spec is not None and spec.origin == str(Path(tmp, 'explosive.py'))
        assert 'explosive' not in sys.modules

        # Building the module is O(1); only exec_module() runs the body
        module = importlib.util.module_from_spec(spec)
        assert module.__name__ == 'explosive' and module.__spec__ is spec
        try:
            spec.loader.exec_module(module)  # O(n + m)
        except RuntimeError as error:
            assert str(error) == 'body ran'
        else:
            raise AssertionError('the body did not run')
    finally:
        sys.path.remove(tmp)
        sys.path_importer_cache.pop(tmp, None)
```

## Lazy Loading

`LazyLoader` makes `exec_module()` free and moves the whole load, O(n + m), to the first attribute
access. Every access counts, including `__dict__`, so the only way to see the module unloaded is
through a side effect its body has not yet had.

```python
import importlib.util
import sys
import tempfile
import types
from pathlib import Path

sentinel = types.ModuleType('lazy_sentinel')
sentinel.RUNS = []
sys.modules['lazy_sentinel'] = sentinel

with tempfile.TemporaryDirectory() as tmp:
    Path(tmp, 'lazy_target.py').write_text(
        'import lazy_sentinel\nlazy_sentinel.RUNS.append(1)\nVALUE = 42\n'
    )
    sys.path.insert(0, tmp)
    try:
        spec = importlib.util.find_spec('lazy_target')  # O(t + p·s)
        spec.loader = importlib.util.LazyLoader(spec.loader)  # O(1)
        module = importlib.util.module_from_spec(spec)  # O(1)
        sys.modules['lazy_target'] = module
        spec.loader.exec_module(module)  # O(1) - nothing has run
        assert sentinel.RUNS == []

        assert module.VALUE == 42  # O(n + m) - the first access loads
        assert sentinel.RUNS == [1]
        assert module.VALUE == 42  # O(1)
        assert sentinel.RUNS == [1]
    finally:
        sys.path.remove(tmp)
        sys.modules.pop('lazy_target', None)
        sys.modules.pop('lazy_sentinel', None)
        sys.path_importer_cache.pop(tmp, None)
```

## Reloading

`reload()` runs one module body again in the module's existing namespace. The modules it imports
are already in `sys.modules`, so their bodies do not run; a change in a dependency needs its own
`reload()`.

```python
import importlib
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    # Each body counts its own runs; the namespace survives a reload
    Path(tmp, 'dep_mod.py').write_text('RUNS = globals().get("RUNS", 0) + 1\n')
    Path(tmp, 'top_mod.py').write_text('import dep_mod\nRUNS = globals().get("RUNS", 0) + 1\n')
    sys.path.insert(0, tmp)
    try:
        top = importlib.import_module('top_mod')  # O(t + p·s + n + m) for each of the two
        dep = importlib.import_module('dep_mod')  # O(1) - loaded by top_mod's body
        assert (top.RUNS, dep.RUNS) == (1, 1)

        assert importlib.reload(top) is top  # O(t + p·s + n + m) - one body
        assert (top.RUNS, dep.RUNS) == (2, 1)  # the dependency did not run again
    finally:
        sys.path.remove(tmp)
        for name in ('top_mod', 'dep_mod'):
            sys.modules.pop(name, None)
        sys.path_importer_cache.pop(tmp, None)
```

## Namespace Packages

A directory with no `__init__.py` becomes a namespace package, unless some entry on the path
supplies a regular module or package of that name, and its `__path__` is every matching directory,
so finding it visits all p entries rather than stopping at the first. The
`__path__` is recomputed, O(t + p·s), whenever `sys.path` changes, so a portion added later is seen.

```python
import importlib
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    for portion in ('one', 'two'):
        Path(tmp, portion, 'nspkg').mkdir(parents=True)
    Path(tmp, 'one', 'nspkg', 'a.py').write_text('')
    Path(tmp, 'two', 'nspkg', 'b.py').write_text('')

    sys.path.insert(0, str(Path(tmp, 'one')))
    try:
        package = importlib.import_module('nspkg')  # O(t + p·s) - every entry is checked
        assert package.__file__ is None
        assert list(package.__path__) == [str(Path(tmp, 'one', 'nspkg'))]

        sys.path.insert(0, str(Path(tmp, 'two')))
        assert len(package.__path__) == 2  # O(t + p·s) - recomputed on the change
        assert importlib.import_module('nspkg.b').__name__ == 'nspkg.b'
    finally:
        del sys.path[:2]
        for name in ('nspkg', 'nspkg.b'):
            sys.modules.pop(name, None)
        for portion in ('one', 'two'):
            sys.path_importer_cache.pop(str(Path(tmp, portion)), None)
```

## Package Resources

### Hold the Result of files()

`files()` on a file-system package is a path object built in O(1). On a package imported from a
zip archive it opens the archive and reads the central directory, O(z), on every call; the result
indexes the archive's names once more on its first probe, after which `joinpath()` and `is_file()`
are O(1) and reading costs the resource's bytes. Resolve the anchor once and keep the `Traversable`.

```python
import importlib.resources
import json
from pathlib import Path

root = importlib.resources.files('json')  # O(1) - the package is already imported
assert isinstance(root, Path)
assert root == Path(json.__file__).parent

resource = root.joinpath('decoder.py')  # O(1) on a file-system package
assert resource.is_file()  # O(1) - one stat
assert 'class JSONDecoder' in resource.read_text(encoding='utf-8')  # O(n)

# The functional API resolves the anchor and the path again on every call
text = importlib.resources.read_text('json', 'decoder.py', encoding='utf-8')  # O(n)
assert text == resource.read_text(encoding='utf-8')
assert importlib.resources.is_resource('json', 'decoder.py')  # O(1)
assert not importlib.resources.is_resource('json', 'missing.py')

names = {child.name for child in root.iterdir()}  # O(k)
assert 'decoder.py' in names
```

### as_file Copies Only What Is Not a File

`as_file()` yields a file-system resource as the very same path object. It copies only when the
resource has no path of its own, such as a file inside a zip archive: O(n) to a temporary file
that is removed on exit, and a whole tree for a directory.

```python
import importlib.resources

resource = importlib.resources.files('json').joinpath('decoder.py')
with importlib.resources.as_file(resource) as path:  # O(1) - no copy
    assert path is resource
```

### Namespace Package Resources

For a namespace package, `files()` returns a `MultiplexedPath` over every portion. It has no
directory of its own, so `joinpath()` lists and merges its portions for a segment that spans them,
where a regular package pays O(1): at worst O(r + k²) on Python 3.10, whose de-duplication scans a
list, and O(r + k) on 3.11, both stopping at the first match, and O(r + k log k) from 3.12, which
sorts every portion first. A segment that resolves to one directory joins the rest as a plain path.

```python
import importlib
import importlib.resources
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    for portion in ('one', 'two'):
        Path(tmp, portion, 'nsdata').mkdir(parents=True)
    Path(tmp, 'one', 'nsdata', 'a.txt').write_text('A')
    Path(tmp, 'two', 'nsdata', 'b.txt').write_text('B')

    sys.path[:0] = [str(Path(tmp, 'one')), str(Path(tmp, 'two'))]
    try:
        root = importlib.resources.files('nsdata')  # O(t + p·s) - imports the package
        assert type(root).__name__ == 'MultiplexedPath'
        assert root.joinpath('b.txt').read_text() == 'B'  # O(r + k log k) on 3.12+ to find, O(n) to read
        assert {child.name for child in root.iterdir()} == {'a.txt', 'b.txt'}  # O(r + k log k) on 3.12+
    finally:
        del sys.path[:2]
        sys.modules.pop('nsdata', None)
        for portion in ('one', 'two'):
            sys.path_importer_cache.pop(str(Path(tmp, portion)), None)
```

## Installed Distributions

### Finding a Distribution

`distribution()` and everything built on it probe the cached listing of each path entry in turn,
so the lookup is O(p) with no metadata read. Reading `version` then parses the whole `METADATA`
file, and parses it again on every access.

```python
import importlib.metadata
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as site:
    info = Path(site, 'demo_dist-1.2.dist-info')
    info.mkdir()
    (info / 'METADATA').write_text(
        'Metadata-Version: 2.1\nName: demo-dist\nVersion: 1.2\nRequires-Dist: other>=1\n'
    )
    (info / 'RECORD').write_text('demo_pkg/__init__.py,,\ndemo_dist-1.2.dist-info/METADATA,,\n')
    Path(site, 'demo_pkg').mkdir()
    Path(site, 'demo_pkg', '__init__.py').write_text('')

    sys.path.insert(0, site)
    try:
        dist = importlib.metadata.distribution('demo-dist')  # O(p) - no file read yet
        assert importlib.metadata.version('demo-dist') == '1.2'  # O(p + h)
        assert dist.metadata['Name'] == 'demo-dist'  # O(h) - parsed on this access
        assert dist.requires == ['other>=1']  # O(h) - parsed again

        files = dist.files  # O(F) - RECORD parsed, and from 3.12 one stat per entry
        assert [str(f) for f in files] == ['demo_pkg/__init__.py', 'demo_dist-1.2.dist-info/METADATA']
        assert files[0].read_text() == ''  # O(n)

        try:
            importlib.metadata.distribution('not-installed')  # O(p)
        except importlib.metadata.PackageNotFoundError as error:
            assert error.name == 'not-installed'
        else:
            raise AssertionError('an absent distribution was found')
    finally:
        sys.path.remove(site)
        importlib.invalidate_caches()
```

### entry_points() Reads Every Distribution

`entry_points()` reads the `entry_points.txt` of every distinctly named distribution before it
applies the selection, so a lookup for one group costs O(p + d + E) however small the group, and
before Python 3.12 a sort by group, O(E log E), on top. Call it
once and keep the `EntryPoints`; `select()` and indexing on that are linear scans of what was
read, not of the file system.

```python
import importlib
import importlib.metadata
import sys
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as site:
    for name in ('alpha', 'beta'):
        info = Path(site, f'{name}-1.0.dist-info')
        info.mkdir()
        (info / 'METADATA').write_text(f'Metadata-Version: 2.1\nName: {name}\nVersion: 1.0\n')
        (info / 'entry_points.txt').write_text(
            f'[demo.plugins]\n{name} = {name}_plugin:register\n'
        )
        Path(site, f'{name}_plugin.py').write_text('def register():\n    return __name__\n')

    sys.path.insert(0, site)
    try:
        plugins = importlib.metadata.entry_points(group='demo.plugins')  # O(p + d + E)
        assert plugins.names == {'alpha', 'beta'}  # O(E)
        assert plugins['alpha'].value == 'alpha_plugin:register'  # O(E) - a scan, not a dict

        beta = plugins.select(name='beta')  # O(E)
        assert [ep.module for ep in beta] == ['beta_plugin']
        assert plugins['beta'].load()() == 'beta_plugin'  # O(E) to find, plus the import once
    finally:
        sys.path.remove(site)
        for name in ('alpha_plugin', 'beta_plugin'):
            sys.modules.pop(name, None)
        importlib.invalidate_caches()
```

## Common Patterns

### Optional Dependency

```python
import importlib
import importlib.util

def load_optional(name):
    """Locate name before importing it; a miss costs the same search a failed import would."""
    try:
        spec = importlib.util.find_spec(name)  # O(1) loaded, O(t + p·s) otherwise
    except ModuleNotFoundError:  # a dotted name whose parent package is missing
        return None
    if spec is None:
        return None
    return importlib.import_module(name)  # O(1) loaded, O(t + p·s + n + m) otherwise

assert load_optional('json') is not None
assert load_optional('no_such_module_anywhere') is None
assert load_optional('no_such_package_anywhere.child') is None
```

### Plugin Registry

```python
import importlib.metadata

class Registry:
    """Read entry points once; look plugins up by name afterwards in O(1)."""

    def __init__(self, group):
        entries = importlib.metadata.entry_points(group=group)  # O(p + d + E), once
        self._by_name = {entry.name: entry for entry in entries}  # O(E)

    def load(self, name):
        return self._by_name[name].load()  # O(1) lookup; the import once

registry = Registry('demo.no_such_group')
assert registry._by_name == {}
```

## Performance Best Practices

✅ **Do**:

- Keep imports at module level, or cache the module object: every later `import_module()` is a dictionary probe
- Check `find_spec()` before an optional import when the module must not run until chosen; the search costs what a failed import would, and a hit searches once more
- Call `entry_points()` once per group and keep the result; the call reads every distinctly named distribution
- Hold the `Traversable` from `files()` when the package lives in a zip archive, where each `files()` call reads the central directory
- Call `invalidate_caches()` after writing a module at runtime; the directory listing is trusted until then

❌ **Avoid**:

- A long `sys.path`: every miss pays a `stat()` per directory entry, and every first import one per entry before the hit
- `dist.version` or `dist.metadata` in a loop; each access parses the `METADATA` file again
- `PackageMetadata.json` on a file with thousands of headers; it is quadratic in them
- `importlib.resources.files()` with no anchor in hot code; it walks the whole call stack to find the caller
- `LazyLoader` for a module whose first use is on a hot path: the load is not avoided, only moved

## Version Notes

- **Python 3.11+**: Added `importlib.resources.abc` and `importlib.machinery.NamespaceLoader`; `packages_distributions()` infers top-level names from `RECORD` when `top_level.txt` is missing; the functional resources API (`read_text()` and friends) and `contents()` warn `DeprecationWarning`, which Python 3.12.10 withdrew
- **Python 3.12+**: Removed `importlib.find_loader()`, `importlib.abc.Finder`, `MetaPathFinder.find_module()`, `PathEntryFinder.find_loader()` and the `importlib.util` decorators `set_package()`, `set_loader()` and `module_for_loader()`; `EntryPoints` is a tuple rather than a list, and `entry_points()` with no selector returns one rather than a dict-like `SelectableGroups`; `files()` takes an `anchor`, which may be a plain module or omitted; added `Anchor`; `Distribution.files` drops entries whose file is missing; added `_incompatible_extension_module_restrictions`
- **Python 3.13+**: The functional resources API accepts several path names, and `contents()` alone is deprecated; added `Distribution.origin` and `AppleFrameworkLoader`; `EntryPoint` is no longer indexable as a tuple
- **Python 3.14+**: Removed `importlib.abc.ResourceReader`, `Traversable` and `TraversableResources`, which live in `importlib.resources.abc`; deprecated `SourceLoader.path_mtime()`, `DEBUG_BYTECODE_SUFFIXES` and `OPTIMIZED_BYTECODE_SUFFIXES`
- **All Python 3**: A timestamp-based `.pyc`, the default, is trusted while the source's mtime and size match what it recorded, so an edit within the same second that keeps the size is not recompiled

## Related Modules

- **[sys](sys.md)** - `sys.modules`, `sys.path`, `sys.meta_path` and `sys.path_importer_cache`, the state every row here reads
- **[__import__()](../builtins/__import__.md)** - The builtin this function reimplements, and what the `import` statement calls
- **[pkgutil](pkgutil.md)** - Walking the modules of a package, built on these finders
- **[zipimport](zipimport.md)** - The path entry finder for zip archives, where `files()` pays O(z)
- **[runpy](runpy.md)** - Running a module as a script through the same find-and-load path
- **[imp](imp.md)** - The pre-`importlib` API, removed in Python 3.12
- **[modulefinder](modulefinder.md)** - Static discovery of what a script imports
