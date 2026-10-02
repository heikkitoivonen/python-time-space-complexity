# mailcap Module Complexity

The `mailcap` module reads mailcap files (RFC 1524), which map MIME types to the shell commands
that view, edit, compose or print them. `getcaps()` parses every mailcap file it can find into
one dictionary, and `findmatch()` picks an entry from that dictionary and fills in its command
line. Nothing is cached: each `getcaps()` call opens and parses the files again.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The examples need
    Python 3.10, 3.11 or 3.12.

`L` is the characters across the mailcap files read, and `e` is the entries for the requested
MIME type plus those for its `type/*` wildcard, in a dictionary `getcaps()` built. The bounds
assume what mailcap files and calls look like in practice: a handful of files, entries a line or
two long, a short filename and a short parameter list, so substituting into one command is O(1).
A non-empty `test` command is run through `os.system()`, one shell process per entry tested,
and that process is priced on top of the bound.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailcap.getcaps()` | O(L) | O(L) | Reads the files named by `MAILCAPS`, or `~/.mailcap`, `/etc/mailcap`, `/usr/etc/mailcap` and `/usr/local/etc/mailcap`, skipping any that cannot be opened. Returns a new dictionary on every call |
| `mailcap.findmatch(caps, MIMEtype, key='view', filename='/dev/null', plist=[])` | O(e) plus one shell process per `test` run | O(e) | Returns `(command, entry)`, or `(None, None)`. Takes the first entry, in file order, that has `key`, whose `test` command is empty or exits 0, and whose command substitutes safely. `MIMEtype` is matched as given, against the lowercased keys `getcaps()` stores |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailcap.UnsafeMailcapInput` | O(1) | O(1) | `Warning` subclass, issued when `findmatch()` refuses a filename, MIME type or parameter holding shell metacharacters |

## Reading the Database

`getcaps()` parses every line of every file it reads, and keeps a dictionary per entry.
Each call does it all again, so call it once and pass the result to every `findmatch()`.

```python
import mailcap
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    first = os.path.join(directory, 'first')
    second = os.path.join(directory, 'second')
    with open(first, 'w') as f:
        f.write('text/plain; cat %s; copiousoutput\n')
    with open(second, 'w') as f:
        f.write('Text/Plain; less %s\nimage/*; display %s\n')
    missing = os.path.join(directory, 'missing')
    os.environ['MAILCAPS'] = os.pathsep.join([first, missing, second])

    caps = mailcap.getcaps()  # O(L) - every file, every line

    # Keys are lowercased, and entries from later files follow earlier ones
    assert [e['view'] for e in caps['text/plain']] == ['cat %s', 'less %s']
    assert caps['text/plain'][0]['copiousoutput'] == ''
    assert mailcap.getcaps() is not caps  # O(L) again - nothing is cached
```

## Finding a Handler

`findmatch()` looks up the exact type and its `type/*` wildcard, and returns the first entry in
file order that has the requested key and passes its test. It returns the filled-in command and the entry dictionary,
not a flag.

```python
import mailcap
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'mailcap')
    with open(path, 'w') as f:
        f.write('image/*; display %s\n'
                'image/png; pngview %s\n'
                'text/plain; cat %s; edit=vi %s\n')
    os.environ['MAILCAPS'] = path
    caps = mailcap.getcaps()  # O(L)

command, entry = mailcap.findmatch(caps, 'image/png', filename='a.png')  # O(e)
assert command == 'display a.png'  # the wildcard comes first in the file
assert entry['lineno'] == 0

command, entry = mailcap.findmatch(caps, 'text/plain', key='edit', filename='notes.txt')
assert command == 'vi notes.txt'

# Keys were lowercased when read; the type you pass is not
assert mailcap.findmatch(caps, 'Text/Plain') == (None, None)
assert mailcap.findmatch(caps, 'video/mp4') == (None, None)
```

### Test Commands Run a Shell

An entry with a non-empty `test` field is accepted only if that command exits 0, and
`findmatch()` runs it with `os.system()` as soon as it reaches the entry. A type with several tested entries can start
several shells for one lookup. Use `%t` in a `test` field for the filename: `%s` there raises
`TypeError`.

```python
import mailcap

caps = {'text/html': [
    {'view': 'remote-browser %s', 'test': 'exit 1', 'lineno': 0},
    {'view': 'lynx %s', 'test': 'exit 0', 'lineno': 1},
]}

# Two shell processes: the first test fails, the second passes
command, entry = mailcap.findmatch(caps, 'text/html', filename='index.html')
assert command == 'lynx index.html'
```

### Unsafe Input

A filename holding anything but word characters, `@+=:,./-` and characters from U+00A1 up - a
space or a `;`, say - is refused before any test runs. So is such a MIME type substituted by `%t`, or
such a parameter substituted by `%{name}`.

```python
import mailcap
import warnings

caps = {'text/plain': [{'view': 'cat %s', 'lineno': 0}]}

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    result = mailcap.findmatch(caps, 'text/plain', filename='x; rm -rf ~')

assert result == (None, None)
assert caught[0].category is mailcap.UnsafeMailcapInput
```

## Performance Best Practices

✅ **Do**:

- Call `getcaps()` once and reuse the dictionary; every call reparses every file
- Lowercase the MIME type before `findmatch()`, since that is how the keys are stored
- Pass a plain temporary filename, not one built from untrusted input

❌ **Avoid**:

- Calling `findmatch()` in a loop over types whose entries carry `test` fields - each test is a
  shell process
- `%s` in a `test` field - it raises `TypeError` instead of naming the file

## Version Notes

- **Python 3.10.8+**: `findmatch()` refuses unsafe filenames, MIME types and parameters with
  `UnsafeMailcapInput`
- **Python 3.11+**: Importing the module emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import mailcap` raises `ModuleNotFoundError`

## Related Modules

- **[mimetypes](mimetypes.md)** - maps filenames to MIME types, the replacement the deprecation
  points to
- **[subprocess](subprocess.md)** - runs a command list without a shell, unlike `os.system()`
