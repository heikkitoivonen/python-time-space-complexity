# fnmatch Module Complexity

The `fnmatch` module matches strings against Unix shell-style wildcards (`*`, `?`, `[seq]`,
`[!seq]`). It works on strings only and does no I/O. Every pattern is translated to a regular
expression and compiled once; the compiled matcher is kept in a module-level cache, so a pattern
costs its compilation the first time and a single regex match after that.

`n` is the characters in a name (the longest one, for a filter), `p` the characters in a pattern,
`k` the names passed to a filter and `r` the names it returns. Matching bounds are for a pattern
already in the cache; the first use of a pattern adds the compilation row below. On Python 3.10
each match also takes O(p) space, a capture group per interior `*`, and so does every row that
matches.

## Complexity Reference

### Matching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fnmatch.fnmatchcase(name, pat)` | O(n·p) | O(1) | Case always counts. O(n) for patterns such as `*.txt`; the worst case needs a long run after a `*` that keeps almost matching. Wildcards never backtrack into each other, so no pattern is exponential |
| `fnmatch.fnmatch(name, pat)` | O(n·p) | O(1) | Applies `os.path.normcase` to both arguments first: unchanged on POSIX (macOS included), so case counts there; case-normalized copies on Windows, O(n + p) space. Otherwise as `fnmatchcase()` |
| First use of a pattern | O(p) | O(p) | `translate()` plus `re.compile()`; the matcher stays in an LRU cache of 32,768 patterns (256 on Python 3.10) shared by `fnmatch`, `fnmatchcase`, `filter` and `filterfalse` |

### Filtering

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fnmatch.filter(names, pat)` | O(k·n·p) | O(r) | One cache lookup, then one match per name; `names` may be any iterable and is consumed once. On Windows each name is also case-normalized, adding O(n + p) space |
| `fnmatch.filterfalse(names, pat)` | O(k·n·p) | O(r) | Python 3.14+; returns the names that do not match |

### translate

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fnmatch.translate(pat)` | O(p) | O(p) | Returns the regex source as a string; neither compiles nor caches it |

## Matching One Name

`fnmatchcase()` gives the same answer on every platform. `fnmatch()` first passes both arguments
through `os.path.normcase`, which lowercases them on Windows and leaves them alone everywhere else,
including macOS with its case-insensitive file system.

```python
import fnmatch
import os

assert fnmatch.fnmatchcase('report.txt', '*.txt')      # O(n·p)
assert not fnmatch.fnmatchcase('report.TXT', '*.txt')  # case always counts

# fnmatch() is case-insensitive only where normcase lowercases (Windows)
assert fnmatch.fnmatch('report.TXT', '*.txt') == (os.name == 'nt')  # O(n·p)
```

### Wildcards

```python
import fnmatch

assert fnmatch.fnmatchcase('file.txt', 'f*.txt')         # * - any run, even empty
assert fnmatch.fnmatchcase('file1.txt', 'file?.txt')     # ? - exactly one character
assert not fnmatch.fnmatchcase('file12.txt', 'file?.txt')
assert fnmatch.fnmatchcase('file7.txt', 'file[0-9].txt')  # [seq] - one of the set
assert fnmatch.fnmatchcase('fileA.txt', 'file[!0-9].txt')  # [!seq] - one not in the set
assert fnmatch.fnmatchcase('.bashrc', '*rc')             # a leading dot is not special
assert fnmatch.fnmatchcase('a*b', 'a[*]b')               # brackets are the only quoting
assert not fnmatch.fnmatchcase('axb', 'a[*]b')
```

### When Matching Is Not Linear

A pattern like `*.txt` matches in time linear in the name. The `n·p` worst case needs a long run
after a `*` - literal characters, `?` or brackets - that keeps almost matching: the `*` scans
forward for that run, retrying it at each position. Wildcards do not backtrack into one another, so adding them cannot make
a match exponential the way a hand-written regex can.

```python
import fnmatch

name = 'a' * 1_000

# O(n) - a short literal tail
assert not fnmatch.fnmatchcase(name, '*.txt')

# O(n·p) - the 50-character run is retried at almost every position
assert not fnmatch.fnmatchcase(name, '*' + 'a' * 50 + 'b*')

# Twenty stars are still one forward pass per run, not exponential
assert not fnmatch.fnmatchcase(name, '*a' * 20 + '*b')
```

## Filtering Lists

`filter()` looks the pattern up once and then matches each name; the result holds only the names
returned. `names` is read once, so a generator works.

```python
import fnmatch

names = ['test.py', 'data.csv', 'script.py', 'config.json', 'readme.txt']

assert fnmatch.filter(names, '*.py') == ['test.py', 'script.py']  # O(k·n·p)
assert fnmatch.filter((n.upper() for n in names), 'README.*') == ['README.TXT']
```

`filterfalse()` (Python 3.14+) is its complement:

```python
import fnmatch
import sys

names = ['main.py', 'main.pyc', 'util.py', 'util.pyc']

if sys.version_info >= (3, 14):
    assert fnmatch.filterfalse(names, '*.pyc') == ['main.py', 'util.py']  # O(k·n·p)
else:
    assert [n for n in names if not fnmatch.fnmatch(n, '*.pyc')] == ['main.py', 'util.py']
```

## The Pattern Cache

The cache is keyed on the pattern, so the cost of compiling is paid once per
distinct pattern, not per call. A program that cycles through more distinct patterns than the
cache holds - 32,768, or 256 on Python 3.10 - pays the O(p) compilation again each time an
evicted pattern returns.

```python
import fnmatch

names = [f'log{i}.txt' for i in range(1_000)]

# One pattern: compiled on the first call, a cache hit on the other 999
hits = [n for n in names if fnmatch.fnmatchcase(n, 'log9*.txt')]  # O(p) once, then O(n·p)
assert len(hits) == 111
```

## Translating to a Regular Expression

`translate()` returns a regex source string anchored at the end but not the start, so use it with
`match()` rather than `search()`. It does not compile or cache anything; compile it yourself when
you want a regex object, for example to use with `re` flags.

```python
import fnmatch
import re

source = fnmatch.translate('*.py')  # O(p)
assert isinstance(source, str)

regex = re.compile(source, re.IGNORECASE)  # O(p), once
assert regex.match('setup.PY')
assert regex.match('setup.pyc') is None  # anchored at the end

literal = re.compile(fnmatch.translate('a.py'))
assert literal.search('data.py')        # nothing anchors the start...
assert literal.match('data.py') is None  # ...so use match()
```

## Common Patterns

### Matching Several Patterns

One pass with `any()` tries each name against the patterns until one matches, and works on a
one-shot iterator.
One `filter()` per pattern makes a pass per pattern and lists a name twice when two patterns match
it.

```python
import fnmatch

names = ['app.py', 'test_app.py', 'app_test.py', 'notes.md']
patterns = ['test_*.py', '*_test.py']

tests = [n for n in names if any(fnmatch.fnmatchcase(n, p) for p in patterns)]
assert tests == ['test_app.py', 'app_test.py']  # O(k·m·n·p), m = patterns
```

### Excluding Names

```python
import fnmatch

names = ['main.py', 'main.py~', 'build.log', 'README.md']
ignore = ['*~', '*.log']

kept = [n for n in names if not any(fnmatch.fnmatchcase(n, p) for p in ignore)]
assert kept == ['main.py', 'README.md']
```

## Performance Best Practices

✅ **Do**:

- Use `fnmatchcase()` when the answer must not depend on the platform; `fnmatch()` is
  case-insensitive on Windows only
- Reuse a fixed set of patterns; each is compiled once and served from the cache afterwards
- Use [glob](glob.md) or `os.scandir()` to list a directory; `fnmatch` only matches strings

❌ **Avoid**:

- Generating more distinct patterns than the cache holds, which pays O(p) compilation on every
  return of an evicted pattern
- Long runs after a `*` against long names, the O(n·p) case
- Relying on `fnmatch()` to ignore case on macOS: `normcase` leaves names unchanged there

## Version Notes

- **Python 3.11+**: The compiled-pattern cache holds 32,768 patterns, and a regex match takes O(1)
  space; Python 3.10 holds 256 and takes O(p)
- **Python 3.14+**: Added `filterfalse()`

## Related Modules

- **[glob](glob.md)** - lists a directory and matches the same wildcards against each entry
- **[re](re.md)** - what `translate()` produces; use it directly for patterns wildcards cannot express
- **[pathlib](pathlib.md)** - `PurePath.match()` and `Path.glob()` for path-aware matching
- **[os](os.md)** - `os.scandir()` to list names to filter, and `os.path.normcase()`
