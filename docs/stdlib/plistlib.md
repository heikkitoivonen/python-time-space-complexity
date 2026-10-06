# plistlib Module Complexity

The `plistlib` module reads and writes Apple property lists in two formats: XML, and a compact
binary format. Reading always builds the whole value; XML reaches
the expat parser from the file in chunks, and binary reading seeks from object to object. Writing
XML emits each element to the file as it reaches it, while writing binary first tables every
object in the value so that equal scalars are stored once.

`n` is the bytes of the serialized plist, read or written. `v` is the size of the value being
written: its objects plus the characters and bytes of its strings and data. `m` is the objects
alone, counting every container, key and scalar each time it occurs. `d` is the keys in one
dictionary, and `s` is the bytes of the largest single string or data value. Binary output can be
far smaller than v, because equal strings, `bytes`, numbers and dates of the same type are
written once. Key comparison under `sort_keys` is
treated as O(1).

## Complexity Reference

### Reading

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `plistlib.load(fp, *, fmt=None, dict_type=dict, aware_datetime=False)` | O(n) | O(n) | Space is the returned value, not the file; `fmt=None` reads 32 bytes to detect the format and seeks back, so `fp` must be seekable unless `fmt=FMT_XML` is given. `dict_type` is called once per dictionary |
| `plistlib.loads(data, *, fmt=None, dict_type=dict, aware_datetime=False)` | O(n) | O(n) | `load()` over a `BytesIO`; from 3.13 `data` may also be a `str` of XML |

### Writing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `plistlib.dump(value, fp, *, fmt=FMT_XML, sort_keys=True, skipkeys=False, aware_datetime=False)` | O(n) | O(s) | Writes each element to `fp` as it reaches it, so the document is never held; plus the key sort below |
| `plistlib.dump(value, fp, fmt=FMT_BINARY)` | O(v) | O(m + s) | Tables every object before writing any, and hashes every scalar to store equal ones once; a `bytearray` is tabled by identity |
| `plistlib.dumps(value, *, fmt=FMT_XML, skipkeys=False, sort_keys=True, aware_datetime=False)` | O(n) XML, O(v) binary | O(n) | `dump()` into a `BytesIO`; the whole plist is returned as one `bytes` |
| `sort_keys=True` | O(d log d) per dictionary | O(d) per open dictionary | The default: each dictionary's items are sorted before it is written. `sort_keys=False` writes insertion order and skips the sort |
| `skipkeys=True` | O(1) per skipped key | Unchanged | A key that is not a `str` is skipped instead of raising `TypeError`; older versions require `sort_keys=False` for mixed key types (see Version Notes) |
| `aware_datetime=True` | O(1) per date | O(1) | Python 3.13+: dates are read as UTC-aware `datetime`s, and aware ones are converted to UTC when written |

### UID

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `plistlib.UID(data)` | O(1) | O(1) | Wraps an `int` with `0 <= data < 2**64`: another int raises `ValueError`, a non-int `TypeError`; binary format only, the XML writer raises `TypeError` |
| `UID.data` | O(1) | O(1) | The wrapped `int` |

### Formats and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `plistlib.FMT_XML`, `plistlib.FMT_BINARY` | O(1) | O(1) | Members of the `plistlib.PlistFormat` enum; `FMT_XML` is the writers' default |
| `plistlib.InvalidFileException` | O(1) | O(1) | A `ValueError` subclass, raised for an unrecognised header, a malformed binary plist, or an XML entity declaration. Malformed XML raises `xml.parsers.expat.ExpatError` instead |

## Reading Plists

### Loading from Bytes

`loads()` detects the format from the first bytes, so the same call reads XML and binary.

```python
import plistlib

plist_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Name</key>
  <string>John Doe</string>
  <key>Age</key>
  <integer>30</integer>
</dict>
</plist>"""

data = plistlib.loads(plist_bytes)  # O(n)
assert data == {'Name': 'John Doe', 'Age': 30}

binary = plistlib.dumps(data, fmt=plistlib.FMT_BINARY)
assert plistlib.loads(binary) == data  # O(n) - detected as binary
```

### Loading from a File

`load()` needs a binary file object. Without `fmt`, it reads the first 32 bytes to detect the
format and then seeks back, so a stream that cannot seek must pass `fmt=FMT_XML`. The binary
format needs a seekable stream either way.

```python
import io
import plistlib

xml_bytes = plistlib.dumps({'version': 2})

with io.BytesIO(xml_bytes) as f:
    assert plistlib.load(f) == {'version': 2}  # O(n)

class NoSeek(io.RawIOBase):
    """A pipe-like stream: readable, not seekable."""

    def __init__(self, data):
        self._data = io.BytesIO(data)

    def readable(self):
        return True

    def readinto(self, buffer):
        chunk = self._data.read(len(buffer))
        buffer[:len(chunk)] = chunk
        return len(chunk)

try:
    plistlib.load(NoSeek(xml_bytes))
except io.UnsupportedOperation:
    pass
else:
    raise AssertionError('format detection did not seek')

assert plistlib.load(NoSeek(xml_bytes), fmt=plistlib.FMT_XML) == {'version': 2}
```

## Data Types

### What Round-trips

The documented types are `str`, `int`, `float`, `bool`, `bytes`, `datetime.datetime`, `dict`
and `list`, plus `UID` in the binary format.
Writing also accepts `tuple` and `bytearray`, which read back as `list` and `bytes`. Dictionary
keys must be strings. Integers must fit in 64 bits, and XML dates keep whole seconds only.

```python
import datetime
import plistlib

when = datetime.datetime(2024, 1, 2, 3, 4, 5, 678901)
value = {
    'name': 'MyApp',
    'count': 42,
    'ratio': 0.5,
    'enabled': True,
    'items': ('a', 'b'),
    'blob': bytearray(b'\x00\x01'),
    'when': when,
}

restored = plistlib.loads(plistlib.dumps(value))  # O(n) each way
assert restored['items'] == ['a', 'b']       # tuple -> list
assert restored['blob'] == b'\x00\x01'       # bytearray -> bytes
assert restored['when'] == when.replace(microsecond=0)  # XML keeps whole seconds

binary = plistlib.loads(plistlib.dumps(value, fmt=plistlib.FMT_BINARY))
assert binary['when'] == when  # binary stores float seconds: microseconds kept here

for bad, error in (({1: 'a'}, TypeError), ({'a': {1, 2}}, TypeError), (2**64, OverflowError)):
    try:
        plistlib.dumps(bad)
    except error:
        pass
    else:
        raise AssertionError(f'{bad!r} was written')
```

## Writing Plists

### Sorted Keys

`sort_keys=True` is the default, so every dictionary is sorted before it is written: O(d log d)
per dictionary. Pass `sort_keys=False` to keep insertion order and skip the sort.

```python
import plistlib

settings = {'theme': 'dark', 'autosave': True, 'window': [1024, 768]}

sorted_xml = plistlib.dumps(settings)                   # O(n) plus O(d log d)
as_given = plistlib.dumps(settings, sort_keys=False)    # O(n)

assert sorted_xml.index(b'autosave') < sorted_xml.index(b'theme')
assert as_given.index(b'theme') < as_given.index(b'autosave')
assert plistlib.loads(sorted_xml) == plistlib.loads(as_given)

# Disable sorting to skip non-string keys on every supported version
mixed = {'a': 1, 2: 'b'}
assert plistlib.loads(plistlib.dumps(mixed, skipkeys=True, sort_keys=False)) == {'a': 1}
```

### XML vs Binary

The two writers differ in what they hold. XML `dump()` writes each element as it reaches it, so
writing to a file holds one element and the keys being sorted, never the document. The binary
writer tables every object first, which is O(m) memory even when writing to a file, and in return
stores equal scalars once: repeated strings and `bytes` cost one copy in the output, and read back
as one shared object.

```python
import plistlib

# 100 equal payloads, each a separate object
records = [{'status': 'active', 'payload': bytes(1_000)} for _ in range(100)]
assert records[0]['payload'] is not records[99]['payload']

xml_bytes = plistlib.dumps(records, fmt=plistlib.FMT_XML)        # O(n)
binary_bytes = plistlib.dumps(records, fmt=plistlib.FMT_BINARY)  # O(v)

assert len(binary_bytes) < len(xml_bytes) // 50  # one payload instead of 100

loaded = plistlib.loads(binary_bytes)  # O(n)
assert loaded == records
assert loaded[0]['payload'] is loaded[99]['payload']  # stored once, read back shared
```

## UID and Keyed Archives

`UID` is the reference type of `NSKeyedArchiver` archives. It exists only in the binary format.

```python
import plistlib

archive = {'$top': {'root': plistlib.UID(1)}, '$objects': ['$null', 'hello']}

data = plistlib.dumps(archive, fmt=plistlib.FMT_BINARY)  # O(v)
uid = plistlib.loads(data)['$top']['root']
assert uid == plistlib.UID(1) and uid.data == 1  # O(1)

try:
    plistlib.dumps(archive, fmt=plistlib.FMT_XML)
except TypeError as error:
    assert 'UID' in str(error)
else:
    raise AssertionError('the XML writer accepted a UID')

try:
    plistlib.UID(-1)
except ValueError:
    pass
else:
    raise AssertionError('a negative UID was accepted')
```

## Invalid Input

`InvalidFileException` covers input that is not a plist at all and binary plists that do not
parse. Malformed XML is reported by expat.

```python
import plistlib
from xml.parsers.expat import ExpatError

for bad in (b'not a plist', b'bplist00' + bytes(40)):
    try:
        plistlib.loads(bad)
    except plistlib.InvalidFileException:
        pass
    else:
        raise AssertionError(f'{bad!r} was parsed')

assert issubclass(plistlib.InvalidFileException, ValueError)

try:
    plistlib.loads(b'<plist><array></plist>')
except ExpatError as error:
    assert 'mismatched tag' in str(error)
else:
    raise AssertionError('mismatched tags were parsed')
```

## Common Patterns

### Read, Modify, Write

```python
import pathlib
import plistlib
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / 'settings.plist'
    with path.open('wb') as f:
        plistlib.dump({'version': 1, 'recent': []}, f)  # O(n)

    with path.open('rb') as f:
        settings = plistlib.load(f)  # O(n)

    settings['version'] += 1
    settings['recent'].append('/tmp/report.txt')

    with path.open('wb') as f:
        plistlib.dump(settings, f)  # O(n)

    with path.open('rb') as f:
        assert plistlib.load(f) == {'version': 2, 'recent': ['/tmp/report.txt']}
```

## Performance Best Practices

✅ **Do**:

- Use `dump()` to a file for large XML plists: it streams, where `dumps()` holds the whole document
- Pass `sort_keys=False` when key order does not matter, to skip an O(d log d) sort per dictionary
- Use the binary format for values that repeat strings or data: equal ones are stored once
- Pass `fmt=FMT_XML` when reading XML from a stream that cannot seek; binary needs a seekable one

❌ **Avoid**:

- Expecting the binary writer to stream: it tables every object before writing, so it holds O(m)
  even when writing to a file
- Relying on sub-second dates in XML plists; they are truncated to whole seconds

## Version Notes

- **Python 3.13.16+ on the 3.13 line, and 3.14.8+**: `skipkeys=True` skips non-string keys
  before sorting. Earlier versions can raise `TypeError` when sorting mixed key types;
  pass `sort_keys=False` for compatibility
- **Python 3.13+**: `loads()` accepts a `str` holding XML; `load()`, `loads()`, `dump()` and
  `dumps()` take `aware_datetime`
- **All Python 3**: `tuple` and `bytearray` are written as arrays and data, and read back as `list`
  and `bytes`

## Related Modules

- **[json](json.md)** - The same tree of dicts, lists and scalars, as text; no dates, bytes or UIDs
- **[pickle](pickle.md)** - Serializes arbitrary Python objects, not a portable format
- **[xml.etree.ElementTree](xml.etree.elementtree.md)** - For XML that is not a plist
