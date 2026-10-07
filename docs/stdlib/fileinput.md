# fileinput Module Complexity

The `fileinput` module reads the lines of several files, or standard input, as one stream, and can
rewrite each file in place as it goes. It opens one file at a time and reads it a line at a time:
nothing holds a whole file, and building the iterator opens nothing.

`B` is the bytes read across all files (characters in text mode, decompressed bytes through
`hook_compressed()`), `L` is the longest line, `f` is the files in the list, and `W` is what an
in-place edit writes back. Opening, closing and renaming a file are priced at O(1).

## Complexity Reference

### Module-level functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fileinput.input(files=None, inplace=False, backup='', *, mode='r', openhook=None, encoding=None, errors=None)` | O(f) | O(f) | Builds a `FileInput` and makes it the module's global instance; opens nothing yet. Raises `RuntimeError` while the previous one still has a file open |
| `fileinput.filename()`, `fileinput.lineno()`, `fileinput.filelineno()`, `fileinput.fileno()`, `fileinput.isfirstline()`, `fileinput.isstdin()` | O(1) | O(1) | Ask the global instance; raise `RuntimeError` when there is none |
| `fileinput.nextfile()` | O(1) | O(1) | Closes the current file without reading further lines from it |
| `fileinput.close()` | O(1) | O(1) | Closes the current file and drops the global instance |

### FileInput

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fileinput.FileInput(files=None, inplace=False, backup='', *, mode='r', openhook=None, encoding=None, errors=None)` | O(f) | O(f) | Copies the file list; opens nothing yet. `files=None` reads the names in `sys.argv[1:]`, and `'-'` or an empty list means standard input |
| Iterating a `FileInput`, `FileInput.readline()` | O(B + f²) total | O(L + f) | One line held at a time. Each move to the next file copies the remaining file list, which is the f² term; `readline()` returns `''`, or `b''` in binary mode, at the end instead of raising `StopIteration` |
| `FileInput.filename()`, `FileInput.lineno()`, `FileInput.filelineno()`, `FileInput.fileno()`, `FileInput.isfirstline()`, `FileInput.isstdin()` | O(1) | O(1) | Stored counters and flags; `fileno()` is -1 when no file is open |
| `FileInput.nextfile()` | O(1) | O(1) | No further lines are read from the current file, and the skipped ones do not count towards `lineno()` |
| `FileInput.close()`, leaving `with FileInput(...)` | O(1) | O(1) | Closes the current file and empties the file list |

### In-place editing and open hooks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Iterating with `inplace=True` | O(B + W + f²) total | O(L + f) | Each file is renamed to its backup name, read from there, and rewritten through `print()`; the backup is deleted when the file is finished unless `backup` names an extension |
| `fileinput.hook_encoded(encoding, errors=None)` | O(1) | O(1) | Returns an opener; each file then opens with that encoding |
| `fileinput.hook_compressed(filename, mode, *, encoding=None, errors=None)` | O(1) | O(1) | Opens `.gz` and `.bz2` files through `gzip` and `bz2`, anything else with `open()`; decompression happens as lines are read, inside the O(B) |

## Reading Many Files as One Stream

### Lazy Line Iteration

A `FileInput` holds one line. Building it opens nothing, each step reads one line from the
current file, and the counters it keeps are integers it updates as it goes.

```python
import fileinput
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    first = pathlib.Path(tmp, 'first.txt')
    second = pathlib.Path(tmp, 'second.txt')
    first.write_text('a\nb\n', encoding='utf-8')
    second.write_text('c\n', encoding='utf-8')

    seen = []
    with fileinput.input([first, second], encoding='utf-8') as lines:  # O(f) - opens nothing yet
        for line in lines:  # O(B) over both files, one line held at a time
            seen.append((
                pathlib.Path(fileinput.filename()).name,  # O(1)
                fileinput.lineno(),       # O(1) - across all files
                fileinput.filelineno(),   # O(1) - within this file
                fileinput.isfirstline(),  # O(1)
            ))

    assert seen == [
        ('first.txt', 1, 1, True),
        ('first.txt', 2, 2, False),
        ('second.txt', 3, 1, True),
    ]
```

### Skipping the Rest of a File

`nextfile()` closes the current file where it stands. No further lines are read from it, and the
ones skipped do not count towards `lineno()`.

```python
import fileinput
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    long = pathlib.Path(tmp, 'long.txt')
    short = pathlib.Path(tmp, 'short.txt')
    long.write_text('header\n' + 'body\n' * 10_000, encoding='utf-8')
    short.write_text('header\n', encoding='utf-8')

    headers = []
    with fileinput.FileInput([long, short], encoding='utf-8') as lines:
        for line in lines:
            if lines.isfirstline():
                headers.append(line)
                lines.nextfile()  # O(1) - no further lines are read

    assert headers == ['header\n', 'header\n']
    assert lines.lineno() == 2
```

### Very Long File Lists

Moving to the next file copies the list of files still to come, so a list of f files costs O(f²)
on top of the bytes read. That is negligible for a handful of files and the dominant cost for a
long list of small files. A generator that opens each file in turn
does the same job in O(B + f), without the counters.

```python
import pathlib
import tempfile

def lines_of(paths, encoding='utf-8'):
    for path in paths:  # O(B + f) - no per-file copy of the list
        with open(path, encoding=encoding) as handle:
            yield from handle

with tempfile.TemporaryDirectory() as tmp:
    paths = []
    for index in range(100):
        path = pathlib.Path(tmp, f'{index}.txt')
        path.write_text(f'{index}\n', encoding='utf-8')
        paths.append(path)

    assert sum(1 for _ in lines_of(paths)) == 100
```

### Binary Mode

`mode='rb'` yields `bytes` lines and skips decoding; nothing else about the cost changes.

```python
import fileinput
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    data = pathlib.Path(tmp, 'data.bin')
    data.write_bytes(b'\x00\x01\n\xff\n')

    with fileinput.input(data, mode='rb') as lines:  # O(1) for a single name
        assert list(lines) == [b'\x00\x01\n', b'\xff\n']  # O(B)
```

## In-Place Editing

With `inplace=True`, each file is renamed to a backup, read from there, and rewritten with
whatever the loop prints, since standard output points at the new file while it is open. Reading
and writing are both streamed, so memory still follows the longest line. Opening hooks cannot be
combined with `inplace=True`.

```python
import fileinput
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    config = pathlib.Path(tmp, 'config.txt')
    config.write_text('debug=0\nlevel=1\n', encoding='utf-8')

    with fileinput.input(config, inplace=True, backup='.orig', encoding='utf-8') as lines:
        for line in lines:  # O(B + W)
            print(line.replace('debug=0', 'debug=1'), end='')  # written into config.txt

    assert config.read_text(encoding='utf-8') == 'debug=1\nlevel=1\n'
    assert pathlib.Path(tmp, 'config.txt.orig').read_text(encoding='utf-8') == 'debug=0\nlevel=1\n'
```

### Without a Backup

`backup=''` still renames the file to a `.bak` name while it is being edited; it deletes that
copy when the file is closed, including when an exception closes it. A loop that raises part way
through therefore leaves the file holding only the lines written so far, with nothing to restore
it from.

```python
import fileinput
import os
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    data = pathlib.Path(tmp, 'data.txt')
    data.write_text('1\n2\n3\n', encoding='utf-8')

    try:
        with fileinput.input(data, inplace=True, encoding='utf-8') as lines:
            for line in lines:
                if line == '2\n':
                    raise ValueError('bad line')
                print(line, end='')
    except ValueError as error:
        assert str(error) == 'bad line'
    else:
        raise AssertionError('the loop did not raise')

    assert data.read_text(encoding='utf-8') == '1\n'  # lines 2 and 3 are gone
    assert os.listdir(tmp) == ['data.txt']  # and so is the backup
```

## Encodings and Compressed Input

`encoding=` and the two hooks decide how each file is opened. They add a per-file open, priced at
O(1), and the decoding or decompression of the bytes read, which stays inside O(B).

```python
import bz2
import fileinput
import gzip
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    latin = pathlib.Path(tmp, 'latin.txt')
    latin.write_bytes('café\n'.encode('latin-1'))
    packed = pathlib.Path(tmp, 'log.gz')
    packed.write_bytes(gzip.compress('zipped\n'.encode('utf-8')))
    squeezed = pathlib.Path(tmp, 'log.bz2')
    squeezed.write_bytes(bz2.compress('squeezed\n'.encode('utf-8')))

    opener = fileinput.hook_encoded('latin-1')  # O(1) - builds the opener
    with fileinput.input(latin, openhook=opener) as lines:
        assert list(lines) == ['café\n']

    with fileinput.input([packed, squeezed], openhook=fileinput.hook_compressed,
                         encoding='utf-8') as lines:  # decompressed as read
        assert list(lines) == ['zipped\n', 'squeezed\n']
```

## Common Patterns

### Filter Lines Across Files

```python
import fileinput
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    pathlib.Path(tmp, 'a.log').write_text('ok\nERROR disk\n', encoding='utf-8')
    pathlib.Path(tmp, 'b.log').write_text('ERROR net\nok\n', encoding='utf-8')
    paths = sorted(pathlib.Path(tmp).glob('*.log'))

    errors = []
    with fileinput.input(paths, encoding='utf-8') as lines:
        for line in lines:  # O(B + f²); the iterator holds O(L + f)
            if line.startswith('ERROR'):
                name = pathlib.Path(lines.filename()).name  # O(1)
                errors.append(f'{name}:{lines.filelineno()}: {line.rstrip()}')

    assert errors == ['a.log:2: ERROR disk', 'b.log:1: ERROR net']
```

### Count Lines per File

```python
import fileinput
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    pathlib.Path(tmp, 'a.txt').write_text('1\n2\n3\n', encoding='utf-8')
    pathlib.Path(tmp, 'b.txt').write_text('1\n', encoding='utf-8')
    paths = sorted(pathlib.Path(tmp).glob('*.txt'))

    per_file = {}
    with fileinput.input(paths, encoding='utf-8') as lines:
        for _ in lines:  # O(B + f²)
            per_file[pathlib.Path(lines.filename()).name] = lines.filelineno()  # O(1)

    assert per_file == {'a.txt': 3, 'b.txt': 1}
    assert lines.lineno() == 4
```

## Performance Best Practices

✅ **Do**:

- Iterate the lines instead of collecting them, so memory follows the longest line rather than
  the input
- Use `nextfile()` to stop reading a file early; no further lines are read from it
- Pass `encoding=` explicitly, or text mode decodes with the locale encoding
- Give `inplace=True` a `backup` extension unless losing the file on an error is acceptable
- Use one `FileInput` per stream when you need two at once; the module-level functions share a
  single global instance

❌ **Avoid**:

- `list(fileinput.input(...))` on large files - that is the O(B) memory this module exists to avoid
- `fileinput` over a very long list of files - the per-file list copy makes it O(f²); open each
  file in a generator instead
- Calling the query functions or `nextfile()` before `input()` or after `fileinput.close()` - they
  raise `RuntimeError`

## Version Notes

- **Python 3.10+**: `encoding` and `errors` keyword arguments on `input()`, `FileInput()` and
  `hook_compressed()`
- **Python 3.11+**: `mode` accepts only `'r'` and `'rb'`; the `'U'` modes and indexing a
  `FileInput` are removed
- **All Python 3**: text mode without `encoding` or an `openhook` decodes with the locale encoding

## Related Modules

- **[io](io.md)** - the file objects `fileinput` reads a line at a time
- **[gzip](gzip.md)** and **[bz2](bz2.md)** - what `hook_compressed()` opens
- **[itertools](itertools.md)** - `chain.from_iterable` joins already-open files without the
  per-file list copy
- **[glob](glob.md)** - building the file list
