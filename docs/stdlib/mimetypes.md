# mimetypes Module Complexity

The `mimetypes` module maps filename extensions to MIME types and back. Its database is a few
dictionaries: guessing a type splits the extension off the name and looks it up, so the cost
follows the name you pass in, not the size of the database. The expensive work happens once, when
the database is built from the built-in tables and the system's `mime.types` files.

`p` is the characters in the path or URL passed in, `e` is the extensions registered for one MIME
type, `b` is the entries in the built-in tables (fixed per release, a couple of hundred), `f` is the
characters in the `mime.types` files read, and `r`, on Windows, is the keys under
`HKEY_CLASSES_ROOT`. A MIME type or a single extension is treated as short: hashing, lowering and
comparing one is O(1), and `suffix_map` entries do not chain, as the built-in ones do not. Reading a
file prices each registration at O(1), since a real type has a handful of extensions; `add_type()`
shows the O(e) scan behind it.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mimetypes.guess_type(url, strict=True)` | O(p) | O(p) | Parses `url` as a URL, then splits off its extensions; the first module-level guess or `add_type()` runs `init()` |
| `mimetypes.guess_file_type(path, *, strict=True)` | O(p) | O(p) | Python 3.13+; a path, not a URL |
| `mimetypes.guess_all_extensions(type, strict=True)` | O(e) | O(e) | Returns a new list; `strict=False` merges the non-standard list by membership scans, O(e²) |
| `mimetypes.guess_extension(type, strict=True)` | O(e) | O(e) | The first entry of `guess_all_extensions()`, which it builds in full; O(e²) with `strict=False` |
| `mimetypes.add_type(type, ext, strict=True)` | O(e) | O(1) | Scans the type's extension list before appending; a known extension is re-pointed to the new type |
| `mimetypes.init(files=None)` | O(b + f) | O(b + f) | Builds a new database from the built-in tables, every `knownfiles` entry that exists and `files`, dropping earlier `add_type()` calls; with `files` given once a database exists, reads only those files into it, O(f). On Windows it also reads the registry, O(r) |
| `mimetypes.read_mime_types(filename)` | O(b + f) | O(b + f) | Parses into a throwaway `MimeTypes`, so the result holds the built-in types as well as the file's; nothing is registered in the module database, and an unreadable file returns `None` |

### Module data

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mimetypes.inited` | O(1) | O(1) | `True` once `init()` has run |
| `mimetypes.knownfiles` | O(1) | O(1) | The `mime.types` paths `init()` tries; a missing one is skipped |
| `mimetypes.types_map`, `mimetypes.common_types` | O(1) | O(1) | Extension to type, strict and non-standard; after `init()`, the module database's own dicts, so an edit changes later guesses |
| `mimetypes.encodings_map`, `mimetypes.suffix_map` | O(1) | O(1) | Extension to encoding (`.gz` to `gzip`), and extension to extensions (`.tgz` to `.tar.gz`); the same live dicts after `init()` |

### MimeTypes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mimetypes.MimeTypes(filenames=(), strict=True)` | O(b + f) | O(b + f) | Copies the built-in tables, not the module database, then reads `filenames`; runs `init()` first if the module has not |
| `MimeTypes.guess_type(url, strict=True)`, `MimeTypes.guess_file_type(path, *, strict=True)` | O(p) | O(p) | As the module functions, on this instance's tables; `guess_file_type` is Python 3.13+ |
| `MimeTypes.guess_all_extensions(type, strict=True)`, `MimeTypes.guess_extension(type, strict=True)` | O(e) | O(e) | As the module functions; O(e²) with `strict=False` |
| `MimeTypes.add_type(type, ext, strict=True)` | O(e) | O(1) | As the module function |
| `MimeTypes.read(filename, strict=True)`, `MimeTypes.readfp(fp, strict=True)` | O(f) | O(f) | A line at a time |
| `MimeTypes.read_windows_registry(strict=True)` | O(r) | O(r) | Windows; returns at once on other platforms |
| `MimeTypes.types_map`, `MimeTypes.types_map_inv` | O(1) | O(1) | Pairs of dicts, non-standard first and strict second; `types_map_inv` maps a type to its extension list |
| `MimeTypes.encodings_map`, `MimeTypes.suffix_map` | O(1) | O(1) | This instance's own copies |

## Guessing a Type

A guess splits the extension off the name and looks it up, so it costs the length of the name and
never the size of the database. `guess_type()` takes a URL and parses it first; `guess_file_type()` takes a path.
Encoding suffixes such as `.gz` are peeled off before the type is looked up, and `suffix_map`
expands shorthands such as `.tgz` first.

```python
import mimetypes
import sys

db = mimetypes.MimeTypes()  # O(b) - the built-in tables; init() too on first use

assert db.guess_type('report.pdf') == ('application/pdf', None)  # O(p)
assert db.guess_type('https://example.com/img/logo.png') == ('image/png', None)
assert db.guess_type('backup.tar.gz') == ('application/x-tar', 'gzip')
assert db.guess_type('backup.tgz') == ('application/x-tar', 'gzip')  # via suffix_map
assert db.guess_type('README') == (None, None)

# A data: URL carries its own type
assert db.guess_type('data:text/csv;base64,YSxi') == ('text/csv', None)

if sys.version_info >= (3, 11):
    # The query string is not part of the extension
    assert db.guess_type('https://example.com/logo.png?v=2') == ('image/png', None)

if sys.version_info >= (3, 13):
    assert db.guess_file_type('/srv/files/report.pdf') == ('application/pdf', None)  # O(p)
```

### From a Type to Extensions

The reverse direction looks the type up in `types_map_inv` and copies its extension list, so
`guess_extension()` costs the whole list even though it returns one entry. Strict extensions come
before non-standard ones, and within each the first one registered wins.

```python
import mimetypes

db = mimetypes.MimeTypes()

extensions = db.guess_all_extensions('image/jpeg')  # O(e)
assert extensions[0] == db.guess_extension('image/jpeg')  # O(e)
assert '.jpeg' in extensions and '.jpg' in extensions

assert db.guess_extension('application/x-unknown') is None
```

## The Module Database

The module functions share one database, built on first use by `init()`. Building it costs the
built-in tables plus every `mime.types` file in `knownfiles` that exists, so the first guess in a
process pays for all of it and later guesses do not. Calling `init()` again rebuilds it from
scratch, which drops anything registered with `add_type()`.

```python
import mimetypes

mimetypes.add_type('application/x-pydemo', '.pydemo')  # O(e); builds the database first if needed
assert mimetypes.inited
assert mimetypes.guess_type('file.pydemo') == ('application/x-pydemo', None)  # O(p)
assert mimetypes.guess_extension('application/x-pydemo') == '.pydemo'  # O(e)

mimetypes.init()  # O(b + f) - a new database
assert mimetypes.guess_type('file.pydemo') == (None, None)
```

### Registering Types

`add_type()` makes an extension point at a type, replacing whatever it pointed at, and appends the
extension to the type's list unless it is already there. `strict=False` puts the mapping in the
non-standard table, which a guess consults only when asked to.

```python
import mimetypes

db = mimetypes.MimeTypes()

db.add_type('application/x-notes', '.notes', strict=False)  # O(e)
assert db.guess_type('a.notes') == (None, None)
assert db.guess_type('a.notes', strict=False) == ('application/x-notes', None)

db.add_type('application/x-notes-v2', '.notes', strict=False)  # re-points the extension
assert db.guess_type('a.notes', strict=False) == ('application/x-notes-v2', None)
```

## Private Databases

A `MimeTypes` instance starts from the built-in tables, not from the module database, so it does
not see the system's `mime.types` files or anything `add_type()` put there. That makes its answers
the same on every machine running one Python release. Building one registers every built-in entry,
so build it once and keep it.

```python
import io
import mimetypes

mimetypes.add_type('application/x-module-only', '.modonly')

db = mimetypes.MimeTypes()  # O(b)
assert db.guess_type('a.modonly') == (None, None)  # the module database is not copied

db.readfp(io.StringIO("# comment\napplication/x-custom  cstm pycust\n"))  # O(f)
assert db.guess_type('file.pycust') == ('application/x-custom', None)
assert db.guess_all_extensions('application/x-custom') == ['.cstm', '.pycust']
assert mimetypes.guess_type('file.pycust') == (None, None)  # only this instance changed
```

### Reading a mime.types File

`read_mime_types()` parses a file into a throwaway `MimeTypes` and returns its strict table, so the
dictionary it hands back includes the built-in types, and the file's types are not registered in the
module database.

```python
import mimetypes
import os
import tempfile

with tempfile.NamedTemporaryFile('w', suffix='.types', delete=False) as handle:
    handle.write("application/x-example  pyexample\n")

try:
    table = mimetypes.read_mime_types(handle.name)  # O(b + f)
    assert table['.pyexample'] == 'application/x-example'
    assert table['.pdf'] == 'application/pdf'  # the built-in types come along
    assert mimetypes.guess_type('file.pyexample') == (None, None)  # not registered
finally:
    os.remove(handle.name)

assert mimetypes.read_mime_types(handle.name) is None  # unreadable file
```

## Common Patterns

### A Content-Type Header

```python
import mimetypes

def content_headers(filename):
    mime_type, encoding = mimetypes.guess_type(filename)  # O(p)
    headers = {'Content-Type': mime_type or 'application/octet-stream'}
    if encoding is not None:
        headers['Content-Encoding'] = encoding
    return headers

assert content_headers('index.html') == {'Content-Type': 'text/html'}
assert content_headers('dump.sql.gz')['Content-Encoding'] == 'gzip'
assert content_headers('noextension') == {'Content-Type': 'application/octet-stream'}
```

## Performance Best Practices

✅ **Do**:

- Keep one `MimeTypes` instance, or use the module functions, rather than building a database per
  request: each build registers every built-in entry
- Use `guess_file_type()` for paths on Python 3.13+; it skips the URL parse
- Use a `MimeTypes` instance when answers must not depend on the machine's `mime.types` files

❌ **Avoid**:

- Calling `init()` to "refresh" the database - it rebuilds it and drops every `add_type()`
- `read_mime_types()` to register a file's types - it returns a table and registers nothing; use
  `init([filename])` or `MimeTypes.read()`
- Registering thousands of extensions under one type; each `add_type()` scans the type's list

## Version Notes

- **Python 3.11+**: `guess_type()` ignores a URL's query string and fragment; on 3.10 they stay in
  the name the extension is taken from and can change the result
- **Python 3.13+**: Added `guess_file_type()`; passing a path to `guess_type()` is soft deprecated
- **Python 3.14+**: `add_type()` with an extension not starting with `.` emits `DeprecationWarning`
- **All Python 3**: The module functions include the system's `mime.types` files, so their answers
  vary by machine; a `MimeTypes` instance does not read them

## Related Modules

- **[urllib](urllib.md)** - `urllib.parse`, which `guess_type()` uses to split a URL
- **[http](http.md)** - `http.server` answers `Content-Type` from `mimetypes`
- **[email](email.md)** - MIME messages that carry those types
