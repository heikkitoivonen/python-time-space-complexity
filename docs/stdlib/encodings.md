# encodings Module Complexity

The `encodings` package holds the standard codec modules (`encodings.utf_8`, `encodings.latin_1`
and the rest) and the search function the `codecs` registry calls to find them. The package's own
work is name handling: it normalizes an encoding name, maps it through the alias table, and imports
the matching codec module the first time a name asks for it. Encoding and decoding happen in the
codec a lookup returns.

`k` is the characters in an encoding name, `n` is the characters or bytes one encode or decode call
is given, and `i` is the time and memory of importing one codec module, or of failing to find one.
A dictionary lookup keyed by a name is priced at O(k): hashing and comparing a name are passes over
it.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `encodings.normalize_encoding(encoding)` | O(k) | O(k) | Expects an ASCII name, as `str` or `bytes`; each run of characters other than letters, digits and `.` becomes one `_`, with none at either end; case is kept |
| `encodings.search_function(encoding)` | O(k + i) first call per name, O(k) after | O(k + i) first call per name, O(1) after | Cached by the exact string given; a name no codec matches is cached too, as `None`, and nothing evicts entries. Expects the lowercased name `codecs.lookup()` passes it, so call that instead |
| `encodings.win32_code_page_search_function(encoding)` | O(k) | O(k) | Windows only, Python 3.14+; answers `cp` + number for code pages Windows supports, `None` for anything else |

### Alias table

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `encodings.aliases.aliases` | O(k) per lookup | O(1) | A plain `dict` from normalized alias to codec module name, consulted by `search_function()` after it normalizes |

### Encoding and decoding

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `str.encode(encoding, errors='strict')`, `bytes.decode(encoding, errors='strict')` | O(n) | O(n) | The conversion, once the codec is found; for the standard text codecs, UTF-8, ASCII and Latin-1 among them, with `'strict'`, `'ignore'` or `'replace'`; `punycode` is the exception, see [codecs](codecs.md#punycode) |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `encodings.CodecRegistryError` | O(1) | O(1) | Raised by `search_function()` for a codec module whose `getregentry()` returns a tuple of the wrong length or with codec functions that are not callable; a subclass of `LookupError` and `SystemError` |

## Looking Up a Codec

The `codecs` registry normalizes a name the same way, lowercases it, and calls `search_function()`
the first time it sees the result; after that, `codecs.lookup()` answers from its own cache and the
package is not asked again. The first call is the expensive one, because it imports the codec
module.

```python
import codecs
import encodings
from encodings.aliases import aliases

# The package normalizes a name, then maps it through the alias table
assert encodings.normalize_encoding('Latin -- 1') == 'Latin_1'  # O(k) - case is kept
assert encodings.normalize_encoding(b'utf-8') == 'utf_8'
assert aliases['l1'] == 'latin_1'  # O(k) dict lookup

# codecs.lookup() lowercases the name before the package sees it
info = codecs.lookup('L1')  # O(k + i) the first time any code asks for 'l1'
assert info.name == 'iso8859-1'
assert codecs.lookup('l1') is info  # answered by the registry's cache

# Called directly, the search function expects that lowercased name
assert encodings.search_function('l1').name == 'iso8859-1'  # O(k)
assert encodings.search_function('L1') is None
```

### Unknown Names

A name no codec module matches is cached as `None`, so the package tries its imports once per name.
The registry does not cache a failure, so every distinct unknown name passes through to the package
and stays in its cache.

```python
import codecs

try:
    codecs.lookup('no-such-codec')  # O(k + i) once, then O(k) per retry
except LookupError as error:
    assert 'unknown encoding' in str(error)
else:
    raise AssertionError('an unknown encoding was found')
```

## Encoding and Decoding

Each call is one pass over its input, and the error handlers the example uses keep it that way.

```python
text = 'Hello, 世界'
utf8 = text.encode('utf-8')  # O(n)
assert utf8.decode('utf-8') == text  # O(n)

assert 'Café'.encode('latin-1') == b'Caf\xe9'  # O(n)

try:
    'Bad café'.encode('ascii')
except UnicodeEncodeError as error:
    assert (error.start, error.end) == (7, 8)
else:
    raise AssertionError('a non-ASCII character was encoded')

assert 'Bad café'.encode('ascii', errors='ignore') == b'Bad caf'  # O(n)
assert 'Bad café'.encode('ascii', errors='replace') == b'Bad caf?'  # O(n)
```

## Performance Best Practices

✅ **Do**:

- Look codecs up through `codecs.lookup()`, `str.encode()` or `bytes.decode()`: the registry caches
  each name it finds after one search
- Check an encoding name that arrives from outside against the ones you support before looking it
  up, since each distinct unknown name stays in the package's cache

❌ **Avoid**:

- Calling `search_function()` directly: it misses mixed-case names such as `'UTF-8'`, and it is the
  registry's job

## Version Notes

- **Python 3.14+**: Added `win32_code_page_search_function()`, on Windows only

## Related Modules

- **[codecs](codecs.md)** - the registry that calls this package, and the cost of each codec
- **[unicodedata](unicodedata.md)** - normalizing text itself, not encoding names
- **[stringprep](stringprep.md)** - the tables behind the `idna` codec's nameprep
