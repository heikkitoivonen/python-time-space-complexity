# marshal Module Complexity

The `marshal` module reads and writes Python values in the binary format of `.pyc` files. Both
directions are C, and from format version 3 an object reached twice is written once and referenced
after that. It is not a general persistence format: the format may change between Python versions,
a code object is only valid on the version that wrote it, and the reader is not hardened against
malicious data. Use [pickle](pickle.md) or [json](json.md) to store or exchange data.

`n` is the length of the serialized data in bytes. It grows linearly with the objects written and
their payload: the characters of a `str`, the bytes of a bytes-like object, and the digits of an
`int`. `s` is the elements of one `set` or `frozenset`. The bounds assume no set is nested inside
another: from Python 3.11 each level of such nesting doubles the cost of writing what is inside it.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `marshal.dumps(value, version=marshal.version, /, *, allow_code=True)` | O(n) | O(n) | A `set` or `frozenset` adds an O(s log s) sort of its elements (3.11+); an unsupported type raises `ValueError` |
| `marshal.dump(value, file, version=marshal.version, /, *, allow_code=True)` | O(n) | O(n) | Builds the whole bytes object, as `dumps()` does, then makes one `file.write()` call |
| `marshal.loads(bytes, /, *, allow_code=True)` | O(n) | O(n) | Reads one value; bytes after it are ignored |
| `marshal.load(file, /, *, allow_code=True)` | O(n) | O(n) | Reads exactly one value, with small `file.readinto()` calls for every item, and leaves the file just past it |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `marshal.version` | O(1) | O(1) | The default format: 4, and 5 from Python 3.14 |

## Serializing Values

### Round Trips

`dumps()` and `loads()` work on bytes; `dump()` and `load()` on a binary file. `load()` reads
only the bytes of one value, so several values written one after another read back in order.

```python
import io
import marshal

data = {'name': 'Alice', 'scores': [90, 85], 'tags': ('a', 'b')}

serialized = marshal.dumps(data)      # O(n)
assert marshal.loads(serialized) == data  # O(n)

# Bytes after the value are ignored
assert marshal.loads(serialized + b'trailing') == data

# Several values in one stream
stream = io.BytesIO()
marshal.dump(data, stream)  # O(n) - one write of the whole value
marshal.dump(42, stream)
stream.seek(0)
assert marshal.load(stream) == data  # O(n)
assert marshal.load(stream) == 42
assert stream.read() == b''
```

### Supported Types

Only built-in values whose meaning does not depend on the running process are supported: `None`,
`bool`, `int`, `float`, `complex`, `str`, `bytes`, `tuple`, `list`, `dict`, `set`, `frozenset`,
`Ellipsis`, `StopIteration` and code objects, plus `slice` from format version 5. Other bytes-like
objects, `bytes` subclasses included, come back as `bytes`; anything else, including a subclass of
any other supported type, raises `ValueError`.

```python
import marshal

assert marshal.loads(marshal.dumps(bytearray(b'ab'))) == b'ab'  # becomes bytes
assert marshal.loads(marshal.dumps(10**100)) == 10**100  # O(digits)

class Config(dict):
    pass

try:
    marshal.dumps(Config(debug=True))
except ValueError as error:
    assert 'unmarshallable' in str(error)
else:
    raise AssertionError('a dict subclass was marshalled')
```

## Shared and Recursive Objects

From format version 3, the default since Python 3.4, `dumps()` records each object it writes that
is referenced from elsewhere and writes a reference the next time it meets it, and `loads()`
rebuilds the sharing. Below version 3 every path to an object writes it again, so a structure
that shares sub-objects can serialize to exponentially more bytes than it holds, and a structure
that contains itself raises `ValueError`.

```python
import marshal

shared = []
for _ in range(16):
    shared = [shared, shared]  # 17 lists; all but the outermost referenced twice

compact = marshal.dumps(shared)       # version 4 or 5: each list once
expanded = marshal.dumps(shared, 2)   # version 2: 2**16 copies of the innermost list
assert len(expanded) > 1000 * len(compact)

restored = marshal.loads(compact)
assert restored[0] is restored[1]  # sharing survives the round trip

loop = []
loop.append(loop)
restored_loop = marshal.loads(marshal.dumps(loop))  # works from version 3
assert restored_loop[0] is restored_loop

try:
    marshal.dumps(loop, 2)
except ValueError as error:
    assert 'deeply nested' in str(error)
else:
    raise AssertionError('version 2 wrote a recursive list')
```

## Nesting Limit

Nesting is capped by a fixed limit of `marshal`'s own: 1,000 levels on Windows and 2,000 on Linux
and macOS. Writing or reading anything nested deeper raises `ValueError`, and raising
`sys.setrecursionlimit()` does not change that.

```python
import marshal

nested = []
for _ in range(10_000):
    nested = [nested]

try:
    marshal.dumps(nested)
except ValueError as error:
    assert 'too deeply nested' in str(error)
else:
    raise AssertionError('10,000 levels were marshalled')
```

## Code Objects and Untrusted Data

Code objects are what `marshal` exists for, but their format changes with every Python release,
and a loaded code object runs whatever bytecode the data held. From Python 3.13, `allow_code=False`
rejects code objects in both directions; it does not make malformed data safe to load.

```python
import marshal
import sys

code = compile('x * 2', '<expr>', 'eval')
assert eval(marshal.loads(marshal.dumps(code)), {'x': 21}) == 42

if sys.version_info >= (3, 13):
    try:
        marshal.loads(marshal.dumps(code), allow_code=False)
    except ValueError as error:
        assert 'code objects is disallowed' in str(error)
    else:
        raise AssertionError('a code object loaded with allow_code=False')
```

## Common Patterns

### Caching Compiled Code

Compiling is far dearer than unmarshalling the result, which is what `.pyc` files rely on. A
cache written by the same interpreter can do the same.

```python
import marshal

source = 'total = sum(range(10))'
cached = marshal.dumps(compile(source, '<cached>', 'exec'))  # O(n)

namespace = {}
exec(marshal.loads(cached), namespace)  # O(n) to load, no compile
assert namespace['total'] == 45
```

## Performance Best Practices

✅ **Do**:

- Read a file holding one large value with `loads(f.read())`: `load()` makes a method call per
  item to read exactly that value
- Keep the default `version`, so shared objects are written once and recursive ones work at all
- Pass `allow_code=False` (3.13+) when the data should hold no code objects

❌ **Avoid**:

- `marshal` for data another Python version or another program will read - use `pickle` or `json`
- Loading marshal data from an untrusted source, with or without `allow_code=False`
- A `version` below 3 for anything with shared sub-objects - its size can grow exponentially

## Version Notes

- **Python 3.11+**: `set` and `frozenset` elements are written sorted by their serialized form,
  so the same set built in a different order gives identical bytes
- **Python 3.13+**: Added the `allow_code` parameter to all four functions
- **Python 3.14+**: Format version 5, the new default, adds `slice`
- **All Python 3**: A code object is only valid on the Python version that wrote it

## Related Modules

- **[pickle](pickle.md)** - a stable, version-independent format for far more types
- **[json](json.md)** - text interchange with other programs
- **[py_compile](py_compile.md)** - writes `.pyc` files, a marshalled code object behind a header
- **[importlib](importlib.md)** - reads `.pyc` files back through the same format
