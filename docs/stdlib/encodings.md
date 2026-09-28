# encodings Module Complexity

The `encodings` package holds the standard codec modules (`encodings.utf_8`, `encodings.latin_1`
and the rest) and the search function the `codecs` registry calls to find them. The package's own
work is name handling: it normalizes an encoding name, maps it through the alias table, and imports
the matching codec module the first time a name asks for it. Encoding and decoding happen in the
codec a lookup returns. Three codec modules have documented APIs of their own and are priced here:
`encodings.idna`, `encodings.utf_8_sig` and the Windows-only `encodings.mbcs`. The rest are priced
by codec on the [codecs](codecs.md) page.

`k` is the characters in an encoding name, `n` is the characters or bytes one encode or decode call
is given, `c` is the characters or bytes given to one incremental call, and `i` is the time and
memory of importing one codec module, or of failing to find one. `m` is the characters in one
domain label and `u` the distinct non-ASCII characters in it after nameprep.
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
| `str.encode(encoding, errors='strict')`, `bytes.decode(encoding, errors='strict')` | O(n) | O(n) | The conversion, once the codec is found; for the standard text codecs, UTF-8, ASCII and Latin-1 among them, with `'strict'`, `'ignore'` or `'replace'`; `punycode` is the exception, see [codecs](codecs.md#punycode), and `idna` calls it for each non-ASCII label, see `encodings.idna` |

### encodings.idna

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `str.encode('idna')`, `bytes.decode('idna')` | O(n) plus one `ToASCII()` or `ToUnicode()` per label | O(n) | The `encodings.idna` codec (RFC 3490). An ASCII name is encoded as-is, its labels only length-checked, and an ASCII name without `xn--` is decoded as-is. `'strict'` errors only: any other handler raises `UnicodeError` |
| `encodings.idna.ToASCII(label)` | O(m) for a label that is ASCII or that nameprep leaves ASCII, O(m·u) otherwise | O(m) | Nameprep, then punycode unless nameprep left the label ASCII, then the 63-octet check on the result, so an over-long label pays for the conversion before it is rejected. An ASCII label is only length-checked, not lowercased |
| `encodings.idna.ToUnicode(label)` | O(m) without an `xn--` prefix, O(m²) with one | O(m) | With the prefix, a punycode decode then a `ToASCII()` round-trip check. Python 3.12+ rejects a label over 1,024 characters before decoding it. A non-ASCII `str` must nameprep to ASCII or it raises |
| `encodings.idna.nameprep(label)` | O(m) | O(m) | RFC 3491: map, NFKC-normalize, then check prohibited characters and bidi; see [stringprep](stringprep.md). O(m) needs a security-patched CPython, see [unicodedata](unicodedata.md) |

### encodings.utf_8_sig

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `str.encode('utf-8-sig')` | O(n) | O(n) | UTF-8 after a BOM (`codecs.BOM_UTF8`), which every call writes, even for an empty string |
| `bytes.decode('utf-8-sig')` | O(n) | O(n) | Skips one leading BOM if there is one; a second BOM, or one further in, decodes as `'\ufeff'` |
| Incremental encoder `encode(input, final=False)` | O(c) | O(c) | From `codecs.getincrementalencoder('utf-8-sig')`; writes the BOM on the first call only, and again after `reset()` |
| Incremental decoder `decode(input, final=False)` | O(c) | O(c) | From `codecs.getincrementaldecoder('utf-8-sig')`; holds back a first one or two bytes that could begin a BOM until it can decide, skips a BOM only at the start of the stream, and starts over after `reset()` |

### encodings.mbcs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `str.encode('mbcs')`, `bytes.decode('mbcs')` | O(n) | O(n) | Windows only: the ANSI code page (`CP_ACP`), converted by the Windows API; aliases `ansi` and `dbcs`. Elsewhere the name is an unknown encoding and importing `encodings.mbcs` raises `ImportError` |

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

## Internationalized Domain Names

The `idna` codec converts a name one label at a time, and each label that is not plain ASCII goes
through nameprep and, unless that leaves it ASCII, punycode. The 63-octet limit applies to the
`xn--` form and is checked last, so a long non-ASCII label pays for its whole conversion before
it is rejected.

```python
from encodings import idna

assert 'bücher.example'.encode('idna') == b'xn--bcher-kva.example'  # O(n) plus a ToASCII per label
assert b'xn--bcher-kva.example'.decode('idna') == 'bücher.example'
assert 'Example.COM'.encode('idna') == b'Example.COM'  # O(n) - ASCII is only length-checked

assert idna.nameprep('Bücher') == 'bücher'  # O(m)
assert idna.ToASCII('bücher') == b'xn--bcher-kva'  # O(m·u)
assert idna.ToUnicode(b'xn--bcher-kva') == 'bücher'  # O(m²)

# 63 characters, but the xn-- form is longer than 63 octets
try:
    idna.ToASCII('ü' * 63)
except UnicodeError as error:
    assert 'too long' in str(error)
else:
    raise AssertionError('an over-long label was encoded')
```

## Byte Order Marks with utf-8-sig

`utf-8-sig` is UTF-8 with a BOM written in front and, when decoding, one leading BOM skipped. Its
incremental decoder decides whether a stream starts with a BOM before it returns any text, so a
first chunk of one or two bytes that could begin one yields nothing yet.

```python
import codecs

data = 'hello'.encode('utf-8-sig')  # O(n)
assert data == codecs.BOM_UTF8 + b'hello'
assert ''.encode('utf-8-sig') == codecs.BOM_UTF8
assert data.decode('utf-8-sig') == 'hello'  # O(n)
assert b'hello'.decode('utf-8-sig') == 'hello'  # the BOM is optional
assert (codecs.BOM_UTF8 * 2).decode('utf-8-sig') == '\ufeff'  # only one is skipped

decoder = codecs.getincrementaldecoder('utf-8-sig')()
assert decoder.decode(data[:2]) == ''  # O(c) - could still be a BOM
assert decoder.decode(data[2:]) == 'hello'
assert decoder.decode(codecs.BOM_UTF8) == '\ufeff'  # past the start, a BOM is text

encoder = codecs.getincrementalencoder('utf-8-sig')()
assert encoder.encode('he') + encoder.encode('llo') == data  # O(c) - one BOM, on the first call
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
- IDNA-encoding a long name from outside without checking its length first: each label's 63-octet
  limit is enforced only after its conversion, O(m·u) for a label that stays non-ASCII

## Version Notes

- **Python 3.12+**: `encodings.idna.ToUnicode()` rejects a label over 1,024 characters before
  decoding it
- **Python 3.14+**: Added `win32_code_page_search_function()`, on Windows only

## Related Modules

- **[codecs](codecs.md)** - the registry that calls this package, and the cost of each codec
- **[unicodedata](unicodedata.md)** - normalizing text itself, not encoding names
- **[stringprep](stringprep.md)** - the tables behind the `idna` codec's nameprep
