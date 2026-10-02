# nturl2path Module Complexity

The `nturl2path` module converts between Windows file system paths and the path part of a
`file:` URL. It is pure Python and imports on every platform, so it converts Windows paths on
Linux and macOS too.

!!! warning "Deprecated in Python 3.14"
    Importing the module emits a `DeprecationWarning` from Python 3.14, and it is slated for
    removal in Python 3.19. The warning points to `urllib.request`, whose `url2pathname()` and
    `pathname2url()` convert for the platform they run on.

`n` is the characters in the argument, and `c` is the path components in it, the pieces between
its separators.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nturl2path.url2pathname(url)` | O(n) | O(n) | Accepts a colon or the older pipe after a drive letter, and decodes `%XX` escapes. O(n·c) on 3.10, 3.11, 3.12.0-3.12.7 and 3.13.0 when the URL has a drive letter |
| `nturl2path.pathname2url(p)` | O(n) | O(n) | A drive path becomes `///C:/...`, with an empty authority, and unsafe characters become `%XX` escapes. O(n·c) on 3.10, 3.11, 3.12.0-3.12.7 and 3.13.0 when the path has a drive letter |

## Converting Paths

### Drive Paths

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)  # Python 3.14+
    import nturl2path

url = nturl2path.pathname2url('C:\\My Files\\café.txt')  # O(n)
assert url == '///C:/My%20Files/caf%C3%A9.txt'

path = nturl2path.url2pathname(url)  # O(n)
assert path == 'C:\\My Files\\café.txt'

# The older pipe spelling of the drive is accepted too
assert nturl2path.url2pathname('/C|/Users/Alice/file.txt') == 'C:\\Users\\Alice\\file.txt'
```

### Network Shares

A URL path whose authority names a server becomes a UNC path.

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)  # Python 3.14+
    import nturl2path

path = nturl2path.url2pathname('//server/share/file.txt')  # O(n)
assert path == '\\\\server\\share\\file.txt'
```

## The Deprecation

The warning fires when the module is first imported in a process; calling its functions does
not warn.

```python
import sys
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    import nturl2path  # O(1) - defines two functions

deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
assert bool(deprecated) == (sys.version_info >= (3, 14))

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    nturl2path.url2pathname('/C:/x')

assert caught == []
```

## Performance Best Practices

✅ **Do**:

- Call `urllib.request.url2pathname()` and `urllib.request.pathname2url()` on Windows, which is
  what the deprecation asks for

❌ **Avoid**:

- Importing `nturl2path` in new code: it warns from 3.14 and is slated for removal in 3.19
- Converting paths with thousands of components before 3.12.8 and 3.13.1, where a drive path
  costs O(n·c) rather than O(n)

## Version Notes

- **Python 3.12.8+ and 3.13.1+**: Drive paths and URLs convert in O(n), not O(n·c)
- **Python 3.14+**: Importing the module emits a `DeprecationWarning`; removal is slated for
  Python 3.19

## Related Modules

- **[urllib](urllib.md)** - `url2pathname()` and `pathname2url()` for the running platform, the
  replacement the deprecation points to
- **[ntpath](ntpath.md)** - splits and joins Windows paths on any platform
