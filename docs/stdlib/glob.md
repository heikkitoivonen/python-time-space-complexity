# glob Module Complexity

The `glob` module expands shell-style pathname patterns. Its cost is set by how much of the
filesystem the pattern makes it look at, not by how much it finds: a pattern that matches one file
in a directory of 20,000 still reads all 20,000 names.

Three size variables run through the table. **E** is the entries examined across every directory
the pattern reaches, **e** is the entries in the largest single directory among them, and **m** is
the matches returned.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `glob.glob(pathname, *, root_dir, dir_fd, recursive, include_hidden)` | O(E) | O(e + m) | `list(iglob(...))`; the returned order is undefined |
| `glob.iglob(pathname, ...)` | O(1) to build, O(E) to exhaust | O(e) | Lazy per directory, not per entry: a directory is listed whole before any of its matches are yielded |
| `glob.escape(pathname)` | O(n) | O(n) | n = name length; wraps each metacharacter in a character class |
| `glob.has_magic(s)` | O(n) | O(1) | n = string length; one regex search for `*?[` |
| `glob.translate(pat, *, recursive, include_hidden, seps)` | O(n) | O(n) | Python 3.13+; n = pattern length, producing a regex |
| `glob.glob0(dirname, pattern)` | O(1) | O(1) | Deprecated in 3.14; one `lexists` check, no pattern matching |
| `glob.glob1(dirname, pattern)` | O(e) | O(e + m) | Deprecated in 3.14; lists one directory and filters it |
| `glob.magic_check`, `glob.magic_check_bytes` | O(1) | O(1) | The compiled patterns `has_magic()` and `escape()` use |

!!! warning "The pattern decides the cost, not the result"
    Every wildcard segment lists its whole directory. `*.py` in a directory of 20,000 files reads
    20,000 names whether it matches one file or all of them, and `**` repeats that for every
    directory it descends into — including directories reached through a symbolic link, which is
    how a link back up the tree turns a recursive glob into a very long one.

## Basic Globbing

### Simple Patterns

```python
import glob
import os
import tempfile

with tempfile.TemporaryDirectory() as folder:
    for name in ('script.py', 'test.py', 'notes.txt'):
        open(os.path.join(folder, name), 'w').close()

    # Each pattern lists the directory once - O(E)
    py_files = glob.glob(os.path.join(folder, '*.py'))
    assert sorted(os.path.basename(p) for p in py_files) == ['script.py', 'test.py']

    everything = glob.glob(os.path.join(folder, '*'))
    assert len(everything) == 3
```

### Pattern Wildcards

```python
import glob
import os
import tempfile

# * - any sequence of characters
# ? - one character
# [abc] / [a-z] - one character from the set or range
# ** - zero or more directories, with recursive=True

with tempfile.TemporaryDirectory() as folder:
    for name in ('file1.txt', 'fileA.txt', 'apple.txt', 'zebra.txt'):
        open(os.path.join(folder, name), 'w').close()

    def names(pattern):
        return sorted(os.path.basename(p) for p in glob.glob(os.path.join(folder, pattern)))

    assert names('file?.txt') == ['file1.txt', 'fileA.txt']  # O(E)
    assert names('[a-c]*.txt') == ['apple.txt']              # O(E)
```

### Hidden Names Are Excluded

`*`, `?` and `**` do not match a leading dot. Since Python 3.11 `include_hidden=True` turns that
off; before it, the only way in is to write the dot into the pattern.

```python
import glob
import os
import sys
import tempfile

with tempfile.TemporaryDirectory() as folder:
    open(os.path.join(folder, 'visible.py'), 'w').close()
    open(os.path.join(folder, '.hidden.py'), 'w').close()

    found = glob.glob(os.path.join(folder, '*.py'))
    assert sorted(os.path.basename(p) for p in found) == ['visible.py']

    # An explicit dot reaches it on every version
    dotted = glob.glob(os.path.join(folder, '.*.py'))
    assert [os.path.basename(p) for p in dotted] == ['.hidden.py']

    if sys.version_info >= (3, 11):
        both = glob.glob(os.path.join(folder, '*.py'), include_hidden=True)
        assert len(both) == 2
```

## Iterator vs List

### What iglob Actually Saves

`iglob()` saves you the result *list*. It does not save you the directory listing: each directory
the pattern reaches is read whole, into a list of names, before the first match from it is
yielded. So the iterator's memory follows the largest directory, not the number of matches.

```python
import glob
import os
import tempfile
import tracemalloc

with tempfile.TemporaryDirectory() as folder:
    for index in range(2000):
        open(os.path.join(folder, f'f{index}.dat'), 'w').close()
    open(os.path.join(folder, 'only.py'), 'w').close()

    pattern = os.path.join(folder, '*.py')

    # Building the iterator does nothing - O(1)
    tracemalloc.start()
    iterator = glob.iglob(pattern)
    build_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    # The first step reads the whole directory - O(e)
    tracemalloc.start()
    first = next(iterator)
    step_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    assert os.path.basename(first) == 'only.py'
    assert build_peak < step_peak  # the listing happens on the first step
```

### When the List Is the Problem

Use `iglob()` when the *matches* are many. When one directory is huge and the matches are few,
both forms pay the same O(e) to read it.

```python
import glob
import os
import tempfile

with tempfile.TemporaryDirectory() as folder:
    for index in range(100):
        open(os.path.join(folder, f'log{index}.txt'), 'w').close()

    # O(e + m): the listing plus the whole result list
    everything = glob.glob(os.path.join(folder, '*.txt'))
    assert len(everything) == 100

    # O(e): the listing, but one path at a time out of it
    count = 0
    for path in glob.iglob(os.path.join(folder, '*.txt')):
        count += 1
    assert count == 100
```

## Recursive Globbing

`**` needs `recursive=True`; without it the pattern behaves like a single `*`. With it, every
directory below the anchor is listed, so the cost is the whole subtree's entries.

```python
import glob
import os
import tempfile

with tempfile.TemporaryDirectory() as folder:
    nested = os.path.join(folder, 'src', 'pkg')
    os.makedirs(nested)
    open(os.path.join(folder, 'top.py'), 'w').close()
    open(os.path.join(nested, 'deep.py'), 'w').close()

    # O(E) - every entry in the tree is looked at, not every directory
    found = glob.glob(os.path.join(folder, '**', '*.py'), recursive=True)
    assert sorted(os.path.basename(p) for p in found) == ['deep.py', 'top.py']

    # Without recursive=True, ** is just one level
    shallow = glob.glob(os.path.join(folder, '**', '*.py'))
    assert [os.path.basename(p) for p in shallow] == []
```

!!! warning "Recursive globs follow directory symlinks"
    A `**` walk descends through symbolic links to directories, so the same file can be reported
    under more than one path, and a link pointing back up the tree makes the walk far larger than
    the tree. Use `os.walk(followlinks=False)` when that matters.

## Pattern Escaping

`escape()` wraps each metacharacter in a character class, so a literal name can be used as a
pattern. It is O(n) in the name — nothing next to the directory scan that follows.

```python
import glob
import os
import tempfile

assert glob.escape('test[1].txt') == 'test[[]1].txt'
assert glob.has_magic('a*b') is True
assert glob.has_magic('plain.txt') is False

with tempfile.TemporaryDirectory() as folder:
    awkward = os.path.join(folder, 'data[backup].csv')
    open(awkward, 'w').close()

    # Unescaped, the brackets are a character class and match nothing
    assert glob.glob(awkward) == []
    assert glob.glob(glob.escape(awkward)) == [awkward]
```

## Turning a Pattern Into a Regex

`translate()` (Python 3.13+) gives you the regular expression `glob` would match with, including
the leading-dot rule.

```python
import glob
import re
import sys

if sys.version_info >= (3, 13):
    pattern = glob.translate('*.py')  # O(n) in the pattern
    assert re.match(pattern, 'script.py')
    assert re.match(pattern, '.hidden.py') is None  # the dot rule is baked in
```

## Common Patterns

### Collecting Several Extensions

Each pattern is its own walk, so m extensions over a tree of E entries costs O(m·E). One pass with
a broader pattern and a filter costs O(E).

```python
import glob
import os
import tempfile

with tempfile.TemporaryDirectory() as folder:
    for name in ('a.py', 'b.js', 'c.ts', 'd.md'):
        open(os.path.join(folder, name), 'w').close()

    # Three walks - O(3·E)
    wanted = ('py', 'js', 'ts')
    separately = []
    for extension in wanted:
        separately.extend(glob.glob(os.path.join(folder, f'*.{extension}')))
    assert len(separately) == 3

    # One walk, then a filter - O(E)
    once = [
        path for path in glob.iglob(os.path.join(folder, '*'))
        if path.rsplit('.', 1)[-1] in wanted
    ]
    assert len(once) == 3
```

### The Deprecated Pair

`glob0()` and `glob1()` are left over from an older API and have been deprecated since Python
3.14, which points you at `glob(pattern, root_dir=...)` instead. They are worth a look only
because they show the split the table describes: `glob0` never matches a pattern, and `glob1` is
the one-directory listing that `iglob` is built on.

```python
import glob
import os
import tempfile
import warnings

with tempfile.TemporaryDirectory() as folder:
    open(os.path.join(folder, 'a.py'), 'w').close()

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)

        # glob0 checks one literal name - O(1)
        assert glob.glob0(folder, 'a.py') == ['a.py']
        assert glob.glob0(folder, '*.py') == []

        # glob1 lists the directory and filters it - O(e)
        assert glob.glob1(folder, '*.py') == ['a.py']
```

## Version Notes

- **Python 3.11+**: `include_hidden` on `glob()` and `iglob()`
- **Python 3.13+**: `glob.translate()`
- **Python 3.14**: `glob0()` and `glob1()` are deprecated in favour of `root_dir`; the
  docstring states what was always true — the returned order is undefined

## Limitations

- No filtering by size, type or time; that is a `stat()` per result afterwards
- Patterns are shell-style, not regular expressions
- Nothing is cached between calls, so two globs over one tree read it twice

## Alternatives

```python
import os
import re
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as folder:
    Path(folder, 'pkg').mkdir()
    Path(folder, 'pkg', 'test_one.py').touch()

    # pathlib.Path.glob - the same walk, yielding Path objects
    assert [p.name for p in Path(folder).glob('**/*.py')] == ['test_one.py']

    # os.walk plus re - when the pattern is not shell-shaped
    matched = [
        name
        for _, _, files in os.walk(folder)
        for name in files
        if re.match(r'test_.*\.py$', name)
    ]
    assert matched == ['test_one.py']
```

## Best Practices

✅ **Do**:

- Escape a literal name before using it as a pattern
- Anchor the pattern as deeply as you can, so fewer directories are listed
- Use `iglob()` when the matches are many; it does not help when one directory is
- Cache the result if you will use it twice — nothing else does

❌ **Avoid**:

- Reading `glob()` as O(matches); it is O(entries examined)
- One walk per extension when one walk and a filter will do
- `**` over a tree with directory symlinks you have not checked
- `glob()` as an existence check — `os.path.lexists()` is the O(1) answer

## Related Documentation

- [Fnmatch Module](fnmatch.md)
- [Pathlib Module](pathlib.md)
- [OS Module](os.md)
- [Filecmp Module](filecmp.md)
