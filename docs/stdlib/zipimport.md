# zipimport Module Complexity

The `zipimport` module imports `.py` and `.pyc` modules and packages from a ZIP archive. The
import system builds a `zipimporter` for every `sys.path` entry that names an archive, so the
module is usually used without being imported; the class also works directly as the finder and
loader for one archive.

Two things are read. The archive's central directory is read once per archive path and kept in a
cache that every importer on that archive shares. A member is read from disk each time it is asked
for: nothing caches member data or compiled code, and nothing writes bytecode back into the
archive.

`n` is the entries in the archive's central directory, and `b` is the size of the one member being
read, compressed and inflated. Entry names are priced at O(1), and compiling or unmarshalling a
member at O(b); running a module's body is the module's own cost and is not priced here.

## Complexity Reference

### zipimporter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zipimport.zipimporter(archivepath)` | O(n) | O(n) | The first importer for an archive reads its central directory, not its member data; later ones reuse the cached directory, O(1). A subpath such as `app.zip/lib` sets `prefix` |
| `zipimporter.find_spec(fullname, target=None)` | O(b) | O(b) | A miss is O(1): a few name lookups. A module or package it holds is read and decoded to learn its file name |
| `zipimporter.create_module(spec)` | O(1) | O(1) | Returns `None`, asking for the default module object |
| `zipimporter.exec_module(module)` | O(b) | O(b) | Reads and decodes the member again through `get_code()`, then runs the module body |
| `zipimporter.get_code(fullname)` | O(b) | O(b) | Tries `__init__.pyc`, `__init__.py`, `.pyc` and `.py` in that order; a `.py` member it falls back to is compiled on every call |
| `zipimporter.get_filename(fullname)` | O(b) | O(b) | Reads and decodes the member exactly as `get_code()` does, to report which member it would use |
| `zipimporter.get_source(fullname)` | O(b) | O(b) | Reads the `.py` member; `None` when the archive holds only bytecode for the module |
| `zipimporter.get_data(pathname)` | O(b) | O(b) | Opens the archive and reads the member on every call; `OSError` if there is no such member |
| `zipimporter.is_package(fullname)` | O(1) | O(1) | Name lookups only; raises `ZipImportError` if the module is not in the archive |
| `zipimporter.load_module(fullname)` | O(b) | O(b) | Deprecated, and warns; reads and decodes the member once, then runs the module body |
| `zipimporter.invalidate_caches()` | O(1) | O(1) | Drops the cached directory, and the next lookup rereads it, O(n). Python 3.10-3.12 reread it here, O(n) |
| `zipimporter.get_resource_reader(fullname)` | O(1) | O(1) | Each `files()` call on the reader opens the archive with `zipfile` and reads its central directory again, O(n) |
| `zipimporter.archive`, `zipimporter.prefix` | O(1) | O(1) | The archive's path, and the subpath inside it: `''`, or ending in a separator |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `zipimport.ZipImportError` | O(1) | O(1) | A subclass of `ImportError`, raised for an unreadable archive or a module it does not hold |

## Importing from an Archive on sys.path

The first import through an archive path builds its `zipimporter`, O(n), and the import system
keeps it in `sys.path_importer_cache`. Each module imported after that costs `find_spec()` plus
`exec_module()`, which read and decode the member twice. An import that the archive cannot satisfy
still asks it, but a miss is a few name lookups.

```python
import os
import sys
import tempfile
import zipfile
import zipimport

with tempfile.TemporaryDirectory() as tmp:
    archive = os.path.join(tmp, 'lib.zip')
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('greeting.py', 'MESSAGE = "hello"\n')

    sys.path.insert(0, archive)  # O(1) - nothing is read yet
    try:
        import greeting  # O(n) once for the directory, then O(b) twice for the member

        assert greeting.MESSAGE == 'hello'
        assert greeting.__file__ == os.path.join(archive, 'greeting.py')
        assert isinstance(sys.path_importer_cache[archive], zipimport.zipimporter)
    finally:
        sys.path.remove(archive)
        sys.path_importer_cache.pop(archive, None)
        sys.modules.pop('greeting', None)
```

## Using a zipimporter Directly

### Lookups vs Reads

`is_package()` and a `find_spec()` that misses look names up in the cached directory. Every call
that returns member contents, or the name of the member it would load, reads that member from disk.

```python
import os
import tempfile
import zipfile
import zipimport

with tempfile.TemporaryDirectory() as tmp:
    archive = os.path.join(tmp, 'app.zip')
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('lib/pkg/__init__.py', '')
        zf.writestr('lib/pkg/util.py', 'VALUE = 42\n')
        zf.writestr('lib/data.txt', 'payload')

    importer = zipimport.zipimporter(os.path.join(archive, 'lib'))  # O(n)
    assert importer.archive == archive
    assert importer.prefix == 'lib' + os.sep

    assert importer.is_package('pkg') is True  # O(1)
    assert importer.find_spec('missing') is None  # O(1)

    spec = importer.find_spec('pkg')  # O(b) - reads the member for its file name
    assert spec.submodule_search_locations == [os.path.join(archive, 'lib', 'pkg')]

    assert importer.get_source('pkg') == ''  # O(b)
    assert importer.get_data('lib/data.txt') == b'payload'  # O(b), from disk each call

    try:
        importer.is_package('missing')
    except zipimport.ZipImportError as error:
        assert "can't find module" in str(error)
    else:
        raise AssertionError('a module outside the archive was found')
```

### Ship Bytecode Beside the Source

`zipimport` looks for a `.pyc` next to each `.py`, not in `__pycache__`, and never writes one
into the archive. With bytecode there that still matches the source, an import unmarshals it;
without it, an import compiles the source, once in `find_spec()` and again in `exec_module()`. `compileall` writes the layout it
looks for with `legacy=True`, and `get_filename()` reports which member it chose.

```python
import compileall
import os
import tempfile
import zipfile
import zipimport

with tempfile.TemporaryDirectory() as tmp:
    source = os.path.join(tmp, 'fast.py')
    with open(source, 'w') as f:
        f.write('ANSWER = 42\n')
    assert compileall.compile_file(source, legacy=True, quiet=1)  # writes fast.pyc

    with_bytecode = os.path.join(tmp, 'with.zip')
    with zipfile.ZipFile(with_bytecode, 'w') as zf:
        zf.write(source, 'fast.py')
        zf.write(source + 'c', 'fast.pyc')

    source_only = os.path.join(tmp, 'without.zip')
    with zipfile.ZipFile(source_only, 'w') as zf:
        zf.write(source, 'fast.py')

    # O(b) either way; only the member it decodes differs
    assert zipimport.zipimporter(with_bytecode).get_filename('fast').endswith('fast.pyc')
    assert zipimport.zipimporter(source_only).get_filename('fast').endswith('fast.py')
```

### Refreshing After the Archive Changes

The directory is read once per archive path, so an importer does not see members added after it
was built. `invalidate_caches()` drops the cached directory, and the next lookup reads it again.

```python
import os
import tempfile
import zipfile
import zipimport

with tempfile.TemporaryDirectory() as tmp:
    archive = os.path.join(tmp, 'plugins.zip')
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('first.py', '')

    importer = zipimport.zipimporter(archive)  # O(n) - reads the directory
    with zipfile.ZipFile(archive, 'a') as zf:
        zf.writestr('second.py', '')

    assert importer.find_spec('second') is None  # the cached directory is unchanged
    importer.invalidate_caches()  # O(1); O(n) on Python 3.10-3.12
    assert importer.find_spec('second') is not None  # O(n) to reread, then O(b)
```

## Performance Best Practices

✅ **Do**:

- Pack a `.pyc` beside each `.py` (`compileall` with `legacy=True`), so an import unmarshals
  bytecode instead of compiling the source twice
- Call `invalidate_caches()`, or `importlib.invalidate_caches()` for importers on `sys.path`,
  after changing an archive in place

❌ **Avoid**:

- Calling `get_filename()`, or `find_spec()` for a module the archive holds, as a cheap check -
  both decode the member; `is_package()` is the lookup-only question
- Packing bytecode only under `__pycache__` - `zipimport` does not look there, so every import
  compiles
- Reading the same member repeatedly with `get_data()` - nothing caches it

## Version Notes

- **Python 3.12+**: `zipimporter.find_loader()` and `zipimporter.find_module()` were removed; use
  `find_spec()`
- **Python 3.13+**: `invalidate_caches()` drops the cached directory in O(1) and the next lookup
  rereads it; 3.10-3.12 reread it inside the call
- **Python 3.13+**: Modules can be imported from ZIP64 archives, such as one with more than 65,535
  entries
- **Python 3.14+**: A directory that has no entry of its own in the archive is found as a
  namespace package

## Related Modules

- **[importlib](importlib.md)** - The import machinery that calls `find_spec()` and
  `exec_module()`, and `importlib.resources` for data inside an archive
- **[zipfile](zipfile.md)** - Reading and writing the archives themselves
- **[zipapp](zipapp.md)** - Building runnable archives that `zipimport` executes
- **[compileall](compileall.md)** - Writing the `.pyc` files an archive should carry
