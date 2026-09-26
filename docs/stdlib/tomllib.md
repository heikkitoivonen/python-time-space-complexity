# tomllib Module Complexity

The `tomllib` module parses TOML (Tom's Obvious, Minimal Language) into dictionaries, lists and
scalar values. It only reads: there is no writer. The parser is pure Python and makes one pass
over the whole document, which it holds in memory together with the dictionary it builds.
Available in Python 3.11+.

`n` is the characters in the document, and `d` is the parts in the longest key path: a table
header's dotted parts plus those of a dotted key under it, so `[a.b]` followed by `c.d = 1` has
four. Hashing one key part is treated as O(1). Ordinary files keep `d` to a handful, which makes
both parsing functions O(n); the `d` factor is paid by every key under a deep header and by every
long dotted key.

## Complexity Reference

### Parsing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tomllib.loads(s, /, *, parse_float=float)` | O(n·d) | O(n·d) | O(n) for ordinary documents; nesting arrays and inline tables adds nothing beyond their characters |
| `tomllib.load(fp, /, *, parse_float=float)` | O(n·d) | O(n·d) | Reads the whole binary file with one `read()`, decodes it as UTF-8, then parses it as `loads()` does; a text-mode file raises `TypeError` |
| `parse_float` callback | O(f) per float | O(f) per float | f = one call's cost in time and space; called once per float value with its text as written, never for integers; returning a `dict` or `list` raises `ValueError` |

### TOMLDecodeError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tomllib.TOMLDecodeError(msg, doc, pos)` | O(pos) | O(1) | A `ValueError` subclass; the message's line and column are counted from the start of the document. Python 3.14+ signature, and the instance keeps `doc` by reference |
| `TOMLDecodeError.msg`, `TOMLDecodeError.doc`, `TOMLDecodeError.pos`, `TOMLDecodeError.lineno`, `TOMLDecodeError.colno` | O(1) | O(1) | Python 3.14+ |

## Parsing a Document

### From a String

`loads()` takes a `str` and returns a new dictionary. Tables become dictionaries, arrays become
lists, and dates and times become `datetime` objects.

```python
import datetime
import tomllib

document = """
title = "example"
ports = [8001, 8002]
created = 2024-01-16T10:30:00Z

[database]
server = "192.168.1.1"
enabled = true

[[users]]
name = "Alice"

[[users]]
name = "Bob"
"""

config = tomllib.loads(document)  # O(n·d), O(n) here
assert config['database'] == {'server': '192.168.1.1', 'enabled': True}
assert config['ports'] == [8001, 8002]
assert [user['name'] for user in config['users']] == ['Alice', 'Bob']
assert config['created'] == datetime.datetime(
    2024, 1, 16, 10, 30, tzinfo=datetime.timezone.utc
)
```

### From a File

`load()` needs a file opened in binary mode, `open(path, "rb")`, because TOML is always UTF-8.
It reads the whole file at once, so the bytes, the decoded text and the result are all in memory
while it parses.

```python
import io
import tomllib

data = b'name = "myapp"\nversion = "1.0.0"\n'

config = tomllib.load(io.BytesIO(data))  # O(n·d): one read(), then loads()
assert config == {'name': 'myapp', 'version': '1.0.0'}

try:
    tomllib.load(io.StringIO('name = "myapp"'))
except TypeError as error:
    assert 'binary mode' in str(error)
else:
    raise AssertionError('a text-mode file was accepted')
```

## Key Depth

Every key/value pair checks its whole path, header included, against the tables already
declared. A key under `[a.b.c]` therefore pays for three parts before its own, and a dotted key
with p parts pays O(p²). Shallow headers and short keys keep each pair O(1) beyond its
characters.

```python
import tomllib

# The same dictionary, spelled with a header or with dotted keys
headed = tomllib.loads("[server.http]\nport = 80\nhost = 'a'\n")  # d = 3
dotted = tomllib.loads("server.http.port = 80\nserver.http.host = 'a'\n")  # d = 3
assert headed == dotted == {'server': {'http': {'port': 80, 'host': 'a'}}}

# A table cannot be declared twice, which is what the path checks enforce
try:
    tomllib.loads("[server]\nport = 80\n[server]\nhost = 'a'\n")
except tomllib.TOMLDecodeError as error:
    assert 'Cannot declare' in str(error)
else:
    raise AssertionError('a table was declared twice')
```

Nesting arrays and inline tables costs only their characters. They are parsed recursively,
though, so nesting far enough to exhaust the recursion limit raises `RecursionError`.

```python
import tomllib

nested = tomllib.loads("k = [[1, 2], {a = {b = [3]}}]")  # O(n)
assert nested == {'k': [[1, 2], {'a': {'b': [3]}}]}

too_deep = "k = " + "[" * 5000 + "]" * 5000
try:
    tomllib.loads(too_deep)
except RecursionError:
    pass
else:
    raise AssertionError('5,000 nested arrays were parsed')
```

## Exact Floats with parse_float

`parse_float` receives each float's text, underscores included, so `decimal.Decimal` keeps every
digit. It is called once per float and never for an integer, so its cost is added per float
value.

```python
import decimal
import tomllib

calls = []

def exact(text):
    calls.append(text)
    return decimal.Decimal(text)

config = tomllib.loads(
    "price = 1_000.10\nrates = [0.1, 2e3, inf]\ncount = 3\n",
    parse_float=exact,
)  # O(n·d) plus one parse_float call per float

assert config['price'] == decimal.Decimal('1000.10')
assert config['rates'][0] == decimal.Decimal('0.1')
assert config['count'] == 3  # integers never reach parse_float
assert calls == ['1_000.10', '0.1', '2e3', 'inf']
```

## Handling Errors

A document that is not valid TOML raises `TOMLDecodeError`, a `ValueError`, with the position
of the problem in its message. From Python 3.14 the same position is also available as attributes.

```python
import sys
import tomllib

document = "name = 'myapp'\nversion = \n"

try:
    tomllib.loads(document)
except tomllib.TOMLDecodeError as error:
    assert isinstance(error, ValueError)
    assert 'line 2, column 11' in str(error)
    if sys.version_info >= (3, 14):
        assert (error.lineno, error.colno, error.msg) == (2, 11, 'Invalid value')
        assert error.doc[error.pos] == '\n'
else:
    raise AssertionError('an invalid document was parsed')
```

## Common Patterns

### Merging Over Defaults

The result is a plain dictionary, so defaults merge with ordinary dictionary operations. The
merge is shallow: a table in the document replaces the whole default table.

```python
import tomllib

defaults = {'port': 8000, 'debug': False, 'log': {'level': 'info', 'file': None}}
document = "debug = true\n[log]\nlevel = 'debug'\n"

config = {**defaults, **tomllib.loads(document)}  # O(n·d) + O(keys)
assert config['port'] == 8000
assert config['debug'] is True
assert config['log'] == {'level': 'debug'}  # 'file' went with the replaced table
```

## Performance Best Practices

✅ **Do**:

- Open files with `"rb"` and pass them to `load()`, or decode yourself and call `loads()`
- Keep table headers shallow and dotted keys short, so `d` stays a small constant
- Pass `parse_float=decimal.Decimal` when floats must be exact; it costs one call per float

❌ **Avoid**:

- Very long dotted keys or deep headers in generated files: each key pays for its whole path
- Parsing untrusted input without catching `RecursionError` as well as `TOMLDecodeError`
- Re-parsing the same file on every access; parse once and keep the dictionary

## Version Notes

- **Python 3.11+**: `tomllib` added
- **Python 3.11.16, 3.12.14, 3.13.14, 3.14.6+**: a key or table header with more dotted parts
  than the recursion limit in force when `tomllib` was imported raises `RecursionError`
- **Python 3.14+**: `TOMLDecodeError` takes `msg`, `doc` and `pos`, and exposes them with
  `lineno` and `colno`; any other arguments are deprecated

## Related Modules

- **[json](json.md)** - the same shape of result from a JSON document
- **[configparser](configparser.md)** - INI files, with every value a string
- **[decimal](decimal.md)** - exact floats through `parse_float`
