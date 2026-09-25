# linecache Module Complexity

The `linecache` module returns single lines of Python source files by number, and is what
`traceback` and `inspect` use to show source. It reads a file whole the first time any line of it
is asked for, keeps every line in a module-level cache, and answers later calls from memory
without touching the file again.

`n` is the characters in one source file, `f` is the files in the cache, `t` is the lines held
across all of them, and `p` is the entries on `sys.path`. Cache lookups by file name and each
`os.stat()` call are priced at O(1). Source that comes from a module loader rather than a file
also costs whatever the loader's `get_source()` costs, which is not priced here.

## Complexity Reference

### Reading lines

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `linecache.getline(filename, lineno, module_globals=None)`, first call for a file | O(p + n) | O(n) | Reads and keeps the whole file, whichever line is asked for; `p` applies only to a relative name not found as given, which is then searched for along `sys.path` |
| `linecache.getline(...)` for a cached file | O(1) | O(1) | No I/O and no `os.stat()`: a file changed on disk keeps returning its old lines until `checkcache()` |
| `linecache.getline(...)` for a file it cannot find | O(p) | O(1) | Returns `''`; a miss is not cached, so every call repeats the search. Names such as `'<string>'` return `''` in O(1) without one |
| `linecache.lazycache(filename, module_globals)` | O(1) | O(1) | Records the module loader's `get_source`; nothing is fetched until the first `getline()` for that name |

### Cache management

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `linecache.checkcache()` | O(f) | O(f) | Snapshots the cache's keys, then one `os.stat()` per entry read from a file; drops an entry whose size or modification time changed or whose file is gone. Entries from `lazycache()` or a loader are never checked |
| `linecache.checkcache(filename)` | O(1) | O(1) | The same check for one entry |
| `linecache.clearcache()` | O(f + t) | O(1) | Drops every entry and frees every cached line; the next `getline()` for each file reads it again |

## Reading Lines

### The First Call Reads the Whole File

Asking for one line costs the whole file once, and after that any line of it is a list index. The
cache does not notice a file changing or disappearing; it keeps answering from the copy it read.

```python
import linecache
import os
import tempfile

with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as handle:
    handle.write(''.join(f'x{i} = {i}\n' for i in range(1, 1001)))
path = handle.name

try:
    assert linecache.getline(path, 1) == 'x1 = 1\n'  # O(n) - reads all 1,000 lines
    assert linecache.getline(path, 1000) == 'x1000 = 1000\n'  # O(1) - already cached
    assert linecache.getline(path, 5000) == ''  # O(1) - out of range, never raises
finally:
    os.remove(path)

# The file is gone, but the cached copy still answers
assert linecache.getline(path, 500) == 'x500 = 500\n'  # O(1)

linecache.checkcache(path)  # O(1) - the stat fails, so the entry is dropped
assert linecache.getline(path, 500) == ''
```

### Misses Are Not Cached

A name that resolves to nothing is looked for again on every call. For a relative name that means
one `os.stat()` per `sys.path` entry each time, so repeated lookups of a missing file cost O(p)
apiece rather than O(1).

```python
import linecache

assert linecache.getline('no_such_module_here.py', 1) == ''  # O(p) - searches sys.path
assert linecache.getline('no_such_module_here.py', 1) == ''  # O(p) again - nothing cached

# '<string>' names source that never had a file; it is rejected without a search
assert linecache.getline('<string>', 1) == ''  # O(1)
```

### Source Without a File

`lazycache()` lets a module whose source comes from its loader - a zip import, a custom importer -
be read later without keeping its globals around. Registering reads nothing; the first `getline()`
calls `get_source()` once and caches the result like a file's lines.

```python
import linecache

calls = []

class Loader:
    def get_source(self, name):
        calls.append(name)
        return 'first = 1\nsecond = 2\n'

name = '/virtual/generated_module.py'  # no such file on disk
module_globals = {'__name__': 'generated_module', '__loader__': Loader()}

assert linecache.lazycache(name, module_globals) is True  # O(1)
assert calls == []  # nothing fetched yet

assert linecache.getline(name, 2) == 'second = 2\n'  # get_source() runs now
assert linecache.getline(name, 1) == 'first = 1\n'  # O(1) - cached
assert calls == ['generated_module']

# Already cached, so there is nothing left to register
assert linecache.lazycache(name, module_globals) is False
linecache.clearcache()
```

## Keeping the Cache Fresh

`checkcache()` is the only thing that notices an edited file, and it does so by comparing the size
and modification time recorded when the file was read. Pass a file name to check one entry instead
of statting every file in the cache.

```python
import linecache
import os
import tempfile

with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as handle:
    handle.write('value = 1\n')
path = handle.name

try:
    assert linecache.getline(path, 1) == 'value = 1\n'  # O(n) - read and cached

    with open(path, 'w') as edited:
        edited.write('value = 2  # edited\n')

    assert linecache.getline(path, 1) == 'value = 1\n'  # O(1) - stale copy

    linecache.checkcache(path)  # O(1) - size changed, entry dropped
    assert linecache.getline(path, 1) == 'value = 2  # edited\n'  # O(n) - read again

    linecache.checkcache()  # O(f) - one stat per cached file
    linecache.clearcache()  # O(f + t) - drops every entry and line
finally:
    os.remove(path)
```

## Common Patterns

### Reading a Range of Lines

Several lines from one file cost one read, however many are taken.

```python
import linecache
import os
import tempfile

with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as handle:
    handle.write(''.join(f'line {i}\n' for i in range(1, 101)))
path = handle.name

try:
    # O(n) for the first line, O(1) for each after it
    context = [linecache.getline(path, number) for number in range(40, 45)]
finally:
    os.remove(path)
    linecache.checkcache(path)

assert context == [f'line {i}\n' for i in range(40, 45)]
```

## Performance Best Practices

✅ **Do**:

- Take many lines from the same file through `getline()`: only the first call reads it
- Call `checkcache(filename)` for the file you care about rather than `checkcache()`, which stats
  every cached file
- Call `clearcache()` when you are done with large files; the cache holds them whole until then
- Use `lazycache()` for loader-backed source, so nothing is fetched unless a line is asked for

❌ **Avoid**:

- `getline()` for one line of a large file you will not read again - it reads and keeps the whole
  file; iterate the file with `itertools.islice` instead
- Calling `getline()` repeatedly for a name that does not resolve - each call repeats the O(p)
  search
- Expecting `getline()` to see a file's edits without a `checkcache()` in between

## Version Notes

- **Python 3.14+**: `getline()` reads a `<frozen ...>` module's source through
  `module_globals['__file__']`; earlier versions return `''` for those names

## Related Modules

- **[traceback](traceback.md)** - formats stack frames with source lines read through this cache
- **[inspect](inspect.md)** - `getsource()` and friends read source through the same cache
- **[tokenize](tokenize.md)** - `tokenize.open()` detects the encoding `getline()` reads a file with
- **[itertools](itertools.md)** - `islice()` takes a line range from a file without caching it
