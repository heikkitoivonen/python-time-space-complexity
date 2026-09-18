# json Module Complexity

The `json` module turns Python objects into JSON text and JSON text back into objects. Both
directions are a single pass: encoding walks the object tree once and parsing walks the text once,
in C. The exceptions are `dump()` and `iterencode()`, which run a pure-Python encoder so the output
can leave in chunks; each chunk is relayed up through every open container, so their cost grows
with depth as well as size. Nothing here streams input. `load()` reads the whole file before it
parses any of it, and there is no incremental parser.

Characters are the unit throughout. `n` is the characters of JSON text: the output when encoding,
the input when decoding. `d` is the nesting depth, `k` is the keys in one object, `s` is the
characters of the longest encoded scalar, `v` is the characters of one value, `p` is the character
position of a parse error, and `h` is the cost of one call to a caller-supplied hook. Hook rows
price the hook on top of the pass that calls it, and what a hook returns is the caller's to hold.
Key comparison under `sort_keys` is treated as O(1). Numbers are treated as fixed width: unless the
limit has been disabled, an `int` longer than `sys.get_int_max_str_digits()` digits raises
`ValueError` in either direction rather than costing more.

## Complexity Reference

### Encoding

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `json.dumps(obj, *, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, cls=None, indent=None, separators=None, default=None, sort_keys=False)` | O(n) | O(n) | The C encoder (before 3.13, only without `indent`); the whole string exists before it is returned |
| `json.dump(obj, fp, ...)` | O(n·d) | O(d + s) | The pure-Python encoder, handing `fp.write()` a chunk per scalar relayed up through every open container; the object tree itself is still whole in memory |
| `indent` | Unchanged | O(d²) extra under `dump()` | n grows: every level repeats its indentation, so a d-deep chain prints O(d²) characters from O(d) of input. `dump()` also holds the indentation of every open level; before 3.13 `dumps()` takes `dump()`'s O(n·d) path here |
| `sort_keys=True` | O(k log k) per object | O(k) per object | Sorts each object's items before writing them |
| `ensure_ascii=True` | Unchanged | Unchanged | The default; n grows, since a non-ASCII code point becomes 6 output characters, or 12 outside the BMP. `ensure_ascii=False` writes it as itself |
| `default=fn` | O(h) per unsupported value | O(h) | Called once per occurrence of a value the encoder cannot serialize, never for a key; what it returns is encoded in that value's place |
| `check_circular=False` | Unchanged | Unchanged | Drops the marker dict that names the containers on the current path; a cycle then ends in `RecursionError` instead of `ValueError` |
| `skipkeys=True` | O(skipped keys) extra | Unchanged | Every key is still examined; one that is not `str`, `int`, `float`, `bool` or `None` writes nothing instead of raising `TypeError`. `sort_keys` sorts first, so an unorderable key still raises there |
| `allow_nan=False` | Unchanged | Unchanged | `nan` and `inf` raise `ValueError` instead of printing as `NaN` and `Infinity` |
| `separators=(item, key)` | Unchanged | Unchanged | Changes what is written between elements, not how often |

### JSONEncoder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `json.JSONEncoder(*, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, sort_keys=False, indent=None, separators=None, default=None)` | O(1) | O(1) | Stores the options |
| `JSONEncoder.encode(o)` | O(n) | O(n) | What `dumps()` calls, with the same `indent` caveat before 3.13 |
| `JSONEncoder.iterencode(o)` | O(n·d) to exhaust | O(d + s) | A generator: nothing is encoded until it is iterated. What `dump()` writes from |
| `JSONEncoder.default(o)` | O(1) | O(1) | Raises `TypeError`; override it to return a serializable stand-in |
| `JSONEncoder.item_separator`, `JSONEncoder.key_separator` | O(1) | O(1) | `', '` and `': '`; `separators` sets both, and `indent` alone drops the space after the comma |

### Decoding

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `json.loads(s, *, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None)` | O(n) | O(n) | Space is the object tree; `bytes` are decoded to a `str` first, an O(n) copy. Keys repeated within one document share one `str` object |
| `json.load(fp, ...)` | O(n) | O(n) | One unsized `fp.read()`, then `loads()`: the text and the tree are in memory together |
| `json.detect_encoding(b)` | O(1) | O(1) | Looks at the first four bytes; what `loads()` uses on `bytes` |
| `object_hook=fn` | O(h) per object | O(h) | Called with each decoded `dict` once its k pairs are in it, innermost object first |
| `object_pairs_hook=fn` | O(k + h) per object | O(k + h) per object | Called with a list of `(key, value)` pairs instead of a `dict`; takes priority over `object_hook` |
| `parse_int=fn`, `parse_float=fn`, `parse_constant=fn` | O(h) per number | O(h) | Called with the literal's text; `parse_int` is how an integer past the digit limit can still be read |

### JSONDecoder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `json.JSONDecoder(*, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, strict=True, object_pairs_hook=None)` | O(1) | O(1) | Stores the hooks; `strict=False` lets control characters through inside strings |
| `JSONDecoder.decode(s)` | O(n) | O(n) | What `loads()` calls; anything but whitespace after the value raises |
| `JSONDecoder.raw_decode(s, idx=0)` | O(v) | O(v) | Parses the one value starting at `idx` and returns it with the index after it, ignoring what follows, so concatenated documents cost their own length each; a malformed value pays the error's O(p) |

### JSONDecodeError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `json.JSONDecodeError(msg, doc, pos)` | O(p + len(msg)) | O(len(msg)) | Counts the newlines before `pos` to fill `lineno` and `colno`, which any parse that raises it pays, and formats `msg` into the message; keeps a reference to `doc`, not a copy. A `ValueError` subclass |
| `JSONDecodeError.msg`, `JSONDecodeError.doc`, `JSONDecodeError.pos`, `JSONDecodeError.lineno`, `JSONDecodeError.colno` | O(1) | O(1) | Set when the error is built |

### Command Line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python -m json.tool [infile] [outfile]` | O(n + m) | O(n + d²) | n = input, m = output: `load()` then `dump(indent=4)`, so the whole input is parsed before anything is written and the output is indented, with `dump()` holding the indentation of every open level. `--json-lines` parses and prints one line at a time; from 3.13.14 and 3.14.5 it reads every line into memory first, so only the trees arrive one at a time |

## Writing Output

### dump vs dumps

`dumps()` builds the whole string in the C encoder and returns it; before 3.13 that holds only
without `indent`. `dump()` runs the pure-Python encoder instead, handing `fp.write()` one chunk per scalar, so its memory follows the depth and the
largest scalar rather than the output. The price is time: the pass is slower per element, and each
chunk is relayed up through the generator of every open container, so it grows with depth as well.
When the output fits in memory and `dumps()` has the C encoder, writing the string it returns is
faster on a tree of many elements; a lone large string costs the same either way, since both go
through the same string encoder.

```python
import io
import json

class CountingSink:
    def __init__(self):
        self.writes = 0

    def write(self, chunk):
        self.writes += 1

data = {'items': list(range(1000))}

sink = CountingSink()
json.dump(data, sink)  # O(n·d) time, O(d + s) memory
assert sink.writes > 1000  # one chunk per scalar, not one string

text = json.dumps(data)  # O(n) time and memory, the C encoder
buffer = io.StringIO()
buffer.write(text)
assert buffer.getvalue() == text

# iterencode() is the generator dump() writes from
chunks = json.JSONEncoder().iterencode(data)  # O(1) - nothing encoded yet
assert ''.join(chunks) == text                # O(n·d) to exhaust
```

### Nesting Depth

Both directions use recursion guards, but there is no portable maximum JSON nesting depth.
The C encoder and decoder's limits depend on the Python version, build and available stack.
`dump()` and `iterencode()` hold one Python frame per level, so `sys.getrecursionlimit()`
bounds the depth they can write.

```python
import io
import json
import sys

root = node = {}
for _ in range(sys.getrecursionlimit() * 2):
    node['child'] = {}
    node = node['child']
try:
    json.dump(root, io.StringIO())  # one Python frame per level
except RecursionError as error:
    assert 'recursion' in str(error).lower()
else:
    raise AssertionError('dump() serialized past the recursion limit')
```

## Pretty Printing

`indent` makes the output longer, and n is the output. Every level repeats its whole indentation
on every line, so nested data prints far more whitespace than data. `sort_keys` adds a sort per
object to the pass: each object's items are ordered before they are written.

```python
import json

data = {'key': 'value', 'nested': {'a': 1, 'b': 2}}

compact = json.dumps(data)                          # O(n)
pretty = json.dumps(data, indent=2)                 # a larger n; O(n·d) before 3.13
assert len(pretty) > len(compact)
assert json.loads(pretty) == data

ordered = json.dumps(data, sort_keys=True)          # O(k log k) per object
assert ordered == '{"key": "value", "nested": {"a": 1, "b": 2}}'
assert json.dumps({'b': 1, 'a': 2}, sort_keys=True) == '{"a": 2, "b": 1}'

tight = json.dumps(data, separators=(',', ':'))     # O(n), the smallest n
assert tight == '{"key":"value","nested":{"a":1,"b":2}}'
```

## Escaping

With `ensure_ascii` at its default, every non-ASCII code point is written as a `\uXXXX` escape:
six characters in the Basic Multilingual Plane, twelve beyond it. That is the largest expansion
the encoder makes; control characters, quotes and backslashes are escaped whatever `ensure_ascii`
is.

```python
import json

assert json.dumps('é') == '"\\u00e9"'              # 6 characters for the one code point
assert json.dumps('😀') == '"\\ud83d\\ude00"'      # 12 for a code point outside the BMP
assert json.dumps('😀', ensure_ascii=False) == '"😀"'  # the code point itself
assert json.dumps('\x00', ensure_ascii=False) == '"\\u0000"'  # control characters regardless
assert json.loads('"\\ud83d\\ude00"') == '😀'      # O(n) to unescape either way
```

## Custom Types

### Encoding with default

`default` is called once for every occurrence of a value the encoder cannot serialize, never for
a key, and its return value is encoded in that value's place. Return something small: the stand-in is walked
like any other value, and a stand-in that contains the original is a circular reference.

```python
import json
from datetime import datetime

calls = 0

def default(obj):  # O(h) per object the encoder cannot serialize
    global calls
    calls += 1
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f'{type(obj).__name__} is not JSON serializable')

stamp = datetime(2024, 1, 12, 12, 0)
text = json.dumps({'first': stamp, 'second': stamp}, default=default)  # O(n)
assert calls == 2  # once per occurrence, even of the same object
assert text == '{"first": "2024-01-12T12:00:00", "second": "2024-01-12T12:00:00"}'

class Encoder(json.JSONEncoder):
    def default(self, o):  # the same hook as a method
        if isinstance(o, set):
            return sorted(o)
        return super().default(o)

assert json.dumps({'tags': {'b', 'a'}}, cls=Encoder) == '{"tags": ["a", "b"]}'
```

### Decoding with Hooks

`object_hook` receives each decoded object as a finished `dict`, innermost first, so a hook that
inspects every key costs O(k) on top of the parse. `object_pairs_hook` receives the pairs as a
list before any `dict` is built and wins when both are given.

```python
import json
from datetime import datetime
from decimal import Decimal

def revive(dct):  # walks all k keys and parses each matching value
    for key, value in dct.items():
        if key.endswith('_at') and isinstance(value, str):
            dct[key] = datetime.fromisoformat(value)
    return dct

text = '{"created_at": "2024-01-12T12:00:00", "inner": {"n": 1}}'
data = json.loads(text, object_hook=revive)  # O(n), plus the hook per object
assert data['created_at'] == datetime(2024, 1, 12, 12, 0)

pairs = json.loads('{"b": 1, "a": 2}', object_pairs_hook=list)  # O(k) per object
assert pairs == [('b', 1), ('a', 2)]

assert json.loads('1.10', parse_float=Decimal) == Decimal('1.10')  # O(h) per number
```

## Parsing Concatenated Documents

`raw_decode()` parses one value and returns the index where it ended, leaving what follows
unconsumed. `decode()` and `loads()` insist on a single document and raise on anything else that
is not whitespace.

```python
import json

decoder = json.JSONDecoder()
stream = '{"id": 1}{"id": 2}[3]'

documents = []
position = 0
while position < len(stream):
    value, position = decoder.raw_decode(stream, position)  # O(v) - the one value
    documents.append(value)
assert documents == [{'id': 1}, {'id': 2}, [3]]

try:
    decoder.decode(stream)
except json.JSONDecodeError as error:
    assert error.msg == 'Extra data'
else:
    raise AssertionError('two documents were decoded as one')
```

## Decoding Errors

Building a `JSONDecodeError` costs the characters before the error, scanned to count its newlines,
which is how it knows the line and column. The exception keeps a reference to the document, so
holding on to the error holds on to the text.

```python
import json

text = '[1, 2,\n 3, oops]'
try:
    json.loads(text)
except json.JSONDecodeError as error:  # O(p) - counts the newlines before pos
    assert (error.lineno, error.colno, error.pos) == (2, 5, 11)
    assert error.msg == 'Expecting value'
    assert error.doc is text  # a reference, not a copy
    assert isinstance(error, ValueError)
else:
    raise AssertionError('malformed JSON was parsed')
```

## Repeated Keys

Within one document, every object key with the same text is the same `str` object: the decoder
memoizes keys as it goes, so a list of records with a shared schema holds each key once rather than
once per record.

```python
import json

records = json.loads('[{"identifier": 1}, {"identifier": 2}]')  # O(n)
first, second = (next(iter(record)) for record in records)
assert first is second  # one str object for both keys
```

## Common Patterns

### One Record per Line

For data too large to hold as one document, JSON Lines keeps one document per line. Each
`loads()` then costs that line, and only that line's tree is held.

```python
import io
import json

lines = io.StringIO('{"id": 1}\n{"id": 2}\n{"id": 3}\n')

total = 0
for line in lines:                       # one record parsed at a time
    total += json.loads(line)['id']      # O(n) for that line's n characters
assert total == 6
```

### Round Trip Through a File Object

```python
import io
import json

data = {'key': 'value', 'items': list(range(100))}

buffer = io.StringIO()
json.dump(data, buffer)          # O(n·d) time, O(d + s) encoder memory; the buffer holds the output
buffer.seek(0)
assert json.load(buffer) == data  # O(n): reads it all, then parses it all
```

## Performance Best Practices

✅ **Do**:

- Write the string `dumps()` returns when the output fits in memory; it is the C encoder
- Use `dump()` or `iterencode()` when it does not; memory then follows depth and the largest
  scalar, not the output, and time grows with depth
- Keep one record per line for data you cannot hold at once, so `loads()` costs one line
- Walk concatenated documents with `raw_decode()`; each call costs its own value
- Return a small stand-in from `default`; it is encoded in full in the object's place

❌ **Avoid**:

- `load()` on a file you cannot hold twice: the text and the tree are in memory together
- `indent` for output only a machine will read; the whitespace is characters you pay to write and
  parse, and every line repeats its depth
- `sort_keys=True` where the order does not matter; it is a sort per object
- Keeping `JSONDecodeError` instances from large documents; each one keeps its whole document alive

## Version Notes

- **Python 3.13+**: `indent` no longer sends `dumps()` through the pure-Python encoder and its
  O(n·d) relay; pretty-printed and compact output are the same C pass
- **Python 3.13.14+ and 3.14.5+**: `python -m json.tool --json-lines` reads the whole input
  before parsing its first line; earlier releases read one line at a time
- **Python 3.10.7+**: unless the limit is disabled, an integer longer than
  `sys.get_int_max_str_digits()` digits raises `ValueError` when parsed or written; `parse_int`
  can read one as something other than `int`
- **All Python 3**: `dump()` and `iterencode()` are bounded by `sys.getrecursionlimit()`;
  the C encoder and decoder have no portable maximum nesting depth

## Related Modules

- **[pickle](pickle.md)** - Python objects beyond the JSON types
- **[csv](csv.md)** - Flat rows, one row at a time, without holding the file
- **[io](io.md)** - `StringIO` for in-memory JSON processing
