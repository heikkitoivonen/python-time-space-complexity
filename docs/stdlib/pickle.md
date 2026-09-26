# pickle Module Complexity

The `pickle` module turns a graph of Python objects into bytes and back. Pickling walks the graph
once, recording the objects it writes in a memo so that a shared or cyclic reference is written as
a short back-reference. Both directions are linear in the pickle they produce or read. Pickling
recurses once per level of nesting, so a structure nested deeply enough, such as a long linked
list, raises `RecursionError`.

`b` is the length of the pickle in bytes, which grows with the object references in the graph and
with the characters, bytes and digits they carry; buffers handed out of band are not part of it.
`m` is the entries in the memo: one for each distinct string, bytes object, container, class,
function and instance written, and none for ints, floats, `None`, booleans or the empty tuple. `s` is the encoded size of the
largest single string or int in the graph. The bounds exclude the user code pickling calls:
`__reduce__`, `__getstate__`, `__setstate__`, a reducer, `persistent_id` or `find_class` adds its
own cost, and a callable that rebuilds an object can allocate as much as it likes. Inserting a key
while rebuilding a dict or set is treated as O(1). Unpickling bounds are for pickles this module
wrote; a hand-crafted pickle can cost more, and can run arbitrary code anyway.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickle.dumps(obj, protocol=None, *, fix_imports=True, buffer_callback=None)` | O(b) | O(b) | The whole pickle is built as one `bytes` object |
| `pickle.dump(obj, file, protocol=None, *, fix_imports=True, buffer_callback=None)` | O(b) | O(m + s) for protocol 4+; O(b) for protocols 0-3 | Protocol 4+ writes the pickle in frames of about 64 KB as it goes; protocols 0-3 hold all of it until the end. At protocol 4 each `bytearray` is copied to a `bytes` object that the memo keeps to the end, so their sizes add to the space |
| `pickle.loads(data, /, *, fix_imports=True, encoding='ASCII', errors='strict', buffers=None)` | O(b) | O(b) | The rebuilt objects |
| `pickle.load(file, *, fix_imports=True, encoding='ASCII', errors='strict', buffers=None)` | O(b) | O(b) | Stops after one pickle, so pickles written one after another come back from one `load()` each; `EOFError` at the end of the file |

### Pickler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickle.Pickler(file, protocol=None, *, fix_imports=True, buffer_callback=None)` | O(1) | O(1) | Needs only a `write()` method |
| `Pickler.dump(obj)` | O(b) | As `pickle.dump` | The memo survives the call: an object this pickler has already written is written again as a back-reference, and stays alive until `clear_memo()` |
| `Pickler.clear_memo()` | O(m) | O(1) | m = the most entries the memo has held; forgets every object written so far, so the next `dump()` is self-contained |
| `Pickler.persistent_id(obj)` | O(1) per call | O(1) | Called once for every reference written, repeats and ints included; a non-`None` result is written in place of the object |
| `Pickler.dispatch_table` | O(1) | O(1) | A per-pickler mapping from type to reduction function, used instead of `copyreg.dispatch_table` |
| `Pickler.reducer_override(obj)` | O(1) per call | O(1) | Called once for each object not yet in the memo, except `None`, booleans and exact ints, floats, strings, bytes, bytearrays, lists, tuples, dicts, sets, frozensets and `PickleBuffer` objects |
| `Pickler.fast` | O(1) | O(1) | Deprecated. Turns the memo off: a shared object is written once per reference, comes back as separate copies, and a cycle raises `ValueError` |

### Unpickler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickle.Unpickler(file, *, fix_imports=True, encoding='ASCII', errors='strict', buffers=None)` | O(1) | O(1) | Needs `read()` and `readline()` |
| `Unpickler.load()` | O(b) | O(b) | As `pickle.load` |
| `Unpickler.find_class(module, name)` | O(1) per call | O(1) | Called at most once for each distinct class or function the pickle names, not once per instance, unless it was written with `Pickler.fast`; imports `module` when it is not loaded yet |
| `Unpickler.persistent_load(pid)` | O(1) per call | O(1) | Called once for each persistent ID in the pickle |

### PickleBuffer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickle.PickleBuffer(buffer)` | O(1) | O(1) | Wraps any buffer without copying it |
| `PickleBuffer.raw()` | O(1) | O(1) | A `memoryview` of the same memory |
| `PickleBuffer.release()` | O(1) | O(1) | Releases the underlying buffer; `raw()` then raises `ValueError` |
| Pickling a `PickleBuffer` with `buffer_callback` (protocol 5) | O(1) | O(1) | When the callback returns a false value such as `None`, the buffer is handed to it instead of copied; `loads(..., buffers=...)` rebuilds from the objects passed in without copying them |
| Pickling a `PickleBuffer` in band (protocol 5) | O(b) | O(b) | Copied into the pickle like `bytes`, so its bytes count in b; protocols below 5 raise `PicklingError` |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickle.HIGHEST_PROTOCOL` | O(1) | O(1) | 5 |
| `pickle.DEFAULT_PROTOCOL` | O(1) | O(1) | 4 before Python 3.14, 5 from 3.14 |
| `pickle.PickleError` | O(1) | O(1) | Base class of the two below |
| `pickle.PicklingError` | O(1) | O(1) | Raised for a function or class that cannot be found by its qualified name, such as a lambda at module level; many unpicklable instances raise `TypeError` instead |
| `pickle.UnpicklingError` | O(1) | O(1) | Raised for a corrupt pickle and by a `find_class` that refuses a name; a truncated pickle can raise `EOFError` instead |

## Pickling and Unpickling

### Round Trips

```python
import pickle

data = {'name': 'Alice', 'scores': [95, 87, 92], 'tags': ('a', 'b')}

pickled = pickle.dumps(data)      # O(b)
assert isinstance(pickled, bytes)

restored = pickle.loads(pickled)  # O(b)
assert restored == data
assert restored is not data
```

### Files Hold One Pickle After Another

`load()` reads one pickle and stops, so several objects written to the same file come back one
`load()` at a time, and reading past the last one raises `EOFError`.

```python
import os
import pickle
import tempfile

fd, path = tempfile.mkstemp()
os.close(fd)
try:
    with open(path, 'wb') as f:
        pickle.dump([1, 2, 3], f)      # O(b)
        pickle.dump({'x': 1}, f)

    with open(path, 'rb') as f:
        assert pickle.load(f) == [1, 2, 3]  # O(b)
        assert pickle.load(f) == {'x': 1}
        try:
            pickle.load(f)
        except EOFError:
            pass
        else:
            raise AssertionError('a third pickle was read from a two-pickle file')
finally:
    os.remove(path)
```

### dump() Streams From Protocol 4

From protocol 4 the pickle is cut into frames of about 64 KB, and `dump()` writes each frame to
the file as soon as it is full, so its memory is the memo rather than the output. Protocols 0-3
have no frames: `dump()` builds the whole pickle and writes it once at the end, no better than
`dumps()`. A string or int is still encoded whole, so one huge value costs its own size either way.

```python
import pickle

class CountingSink:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(len(data))
        return len(data)

numbers = list(range(100_000))

framed = CountingSink()
pickle.dump(numbers, framed, protocol=5)  # O(b) time, O(m + s) memory
assert len(framed.writes) > 1
assert max(framed.writes) < 70_000

whole = CountingSink()
pickle.dump(numbers, whole, protocol=2)   # O(b) time and memory
assert len(whole.writes) == 1
assert whole.writes[0] > 300_000
```

## The Memo

### Shared and Cyclic References

The pickler writes each memoized object once; every later reference to it is a back-reference of
a few bytes. That keeps a shared object shared after the round trip, and it is what lets a cycle
terminate.

```python
import pickle

text = 'x' * 10_000
shared = pickle.dumps([text] * 100)  # O(b): the string is written once
assert len(shared) < 11_000

restored = pickle.loads(shared)
assert all(item is restored[0] for item in restored)

node = {'name': 'A'}
node['self'] = node                  # a cycle
again = pickle.loads(pickle.dumps(node))
assert again['self'] is again
```

### Reusing a Pickler

A `Pickler` keeps its memo between `dump()` calls. Writing the same object twice to one pickler
costs a back-reference the second time, and the second pickle cannot be loaded on its own. The memo
also keeps every object written alive. Call `clear_memo()` between unrelated objects.

```python
import io
import pickle

record = [str(i) for i in range(1_000)]
buffer = io.BytesIO()
pickler = pickle.Pickler(buffer)

pickler.dump(record)        # O(b)
first = buffer.tell()
pickler.dump(record)        # a back-reference to the memo
second = buffer.tell() - first
assert second < 20 < first

pickler.clear_memo()        # O(m)
pickler.dump(record)        # written in full again
third = buffer.tell() - first - second
assert third == first
```

## Custom Serialization

### __getstate__ and __setstate__

An instance is pickled as its class plus the state `__getstate__` returns, so the cost is the
state's, and `__setstate__` receives it back on load.

```python
import pickle

class Session:
    def __init__(self, user, token):
        self.user = user
        self.token = token  # not worth persisting

    def __getstate__(self):
        state = self.__dict__.copy()  # O(attributes)
        del state['token']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)   # O(attributes)
        self.token = None

restored = pickle.loads(pickle.dumps(Session('alice', 'secret')))  # O(b)
assert restored.user == 'alice'
assert restored.token is None
```

### __reduce__

`__reduce__` returns a callable and its arguments. Unpickling calls that callable once per object
written, not once per reference, and its cost is added to `loads()`.

```python
import pickle

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __reduce__(self):
        return (Point, (self.x, self.y))

restored = pickle.loads(pickle.dumps(Point(3, 4)))  # O(b) plus one Point() call
assert (restored.x, restored.y) == (3, 4)
```

### dispatch_table and reducer_override

A `Pickler` can carry its own reductions without touching the class: `dispatch_table` maps a type
to a reduction function for that pickler only, and `reducer_override` is asked about every object
not yet in the memo that is not a plain built-in.

```python
import copyreg
import io
import pickle

class Temperature:
    def __init__(self, celsius):
        self.celsius = celsius

def reduce_temperature(t):
    return (Temperature, (round(t.celsius, 1),))

buffer = io.BytesIO()
pickler = pickle.Pickler(buffer)
pickler.dispatch_table = copyreg.dispatch_table.copy()  # O(entries), once
pickler.dispatch_table[Temperature] = reduce_temperature
pickler.dump(Temperature(21.456))

assert pickle.loads(buffer.getvalue()).celsius == 21.5
assert pickle.loads(pickle.dumps(Temperature(21.456))).celsius == 21.456

class Rounding(pickle.Pickler):
    def reducer_override(self, obj):
        if isinstance(obj, Temperature):
            return reduce_temperature(obj)
        return NotImplemented

buffer = io.BytesIO()
Rounding(buffer).dump([Temperature(1.26), 7])
assert pickle.loads(buffer.getvalue())[0].celsius == 1.3
```

## Persistent References

`persistent_id` lets a pickle refer to objects that live elsewhere, such as rows in a database, by
an ID instead of their contents. It is called for every reference the pickler writes, so it must
be cheap; `persistent_load` is called once for each ID when the pickle is read.

```python
import io
import pickle

class Record:
    def __init__(self, key):
        self.key = key

store = {'r1': Record('r1'), 'r2': Record('r2')}

class ByKey(pickle.Pickler):
    def persistent_id(self, obj):   # O(1), once per reference
        if isinstance(obj, Record):
            return obj.key
        return None

class FromStore(pickle.Unpickler):
    def persistent_load(self, pid):  # O(1), once per ID
        return store[pid]

buffer = io.BytesIO()
ByKey(buffer).dump({'owner': store['r1'], 'backup': store['r2']})

restored = FromStore(io.BytesIO(buffer.getvalue())).load()
assert restored['owner'] is store['r1']
assert restored['backup'] is store['r2']
```

## Restricting What Loads

!!! warning "Never unpickle untrusted data"
    Unpickling can call any callable the pickle names, so loading a pickle from an untrusted source
    can run arbitrary code. Overriding `find_class` narrows what a pickle can name, but it is not
    a security boundary to rely on; use a data-only format such as JSON for untrusted input.

`find_class` is called at most once for each distinct class or function a pickle names, not once
per instance (unless the pickle was written with `Pickler.fast`), so an allow-list check adds a
constant per name.

```python
import io
import pickle
from collections import OrderedDict

class AllowList(pickle.Unpickler):
    allowed = {('collections', 'OrderedDict')}

    def find_class(self, module, name):  # O(1), once per distinct global
        if (module, name) in self.allowed:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f'forbidden: {module}.{name}')

good = pickle.dumps([OrderedDict(a=1) for _ in range(100)])
assert AllowList(io.BytesIO(good)).load()[99] == {'a': 1}

bad = pickle.dumps(print)
try:
    AllowList(io.BytesIO(bad)).load()
except pickle.UnpicklingError as error:
    assert 'forbidden: builtins.print' in str(error)
else:
    raise AssertionError('a forbidden global was loaded')
```

## Out-of-Band Buffers

With protocol 5, a `PickleBuffer` can travel out of band: when `buffer_callback` returns a false
value, as `list.append` does, it keeps the buffer and the pickle gets no copy; `loads()` takes the
buffers back through `buffers=`. The pickle stays a few bytes however large the buffer, and here the
object handed to `loads()` is the one that comes back.

```python
import pickle

payload = bytearray(1_000_000)

buffers = []
data = pickle.dumps(pickle.PickleBuffer(payload), protocol=5,
                    buffer_callback=buffers.append)  # O(1), no copy
assert len(data) < 100

restored = pickle.loads(data, buffers=[payload])  # O(1), no copy
assert restored is payload

in_band = pickle.dumps(pickle.PickleBuffer(payload), protocol=5)  # O(b), copied
assert len(in_band) > 1_000_000

view = pickle.PickleBuffer(payload)
assert view.raw().nbytes == 1_000_000  # O(1)
view.release()                         # O(1)
```

## Protocols

Every protocol is O(b); they differ in encoding, not in growth. Protocol 4 adds framing, which is
what lets `dump()` stream, and protocol 5 adds out-of-band buffers.

```python
import pickle
import sys

assert pickle.HIGHEST_PROTOCOL == 5
assert pickle.DEFAULT_PROTOCOL == (5 if sys.version_info >= (3, 14) else 4)

obj = {'a': 1, 'b': [2, 3, 4]}
for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
    assert pickle.loads(pickle.dumps(obj, protocol=protocol)) == obj  # O(b)

# A reader on an older Python needs a protocol it knows
assert pickle.dumps(obj, protocol=4)[1] == 4
```

## Common Patterns

### An Append-Only Record File

```python
import os
import pickle
import tempfile

fd, path = tempfile.mkstemp()
os.close(fd)
try:
    for event in ({'id': 1}, {'id': 2}, {'id': 3}):
        with open(path, 'ab') as f:
            pickle.dump(event, f)  # O(b) per record

    events = []
    with open(path, 'rb') as f:
        while True:
            try:
                events.append(pickle.load(f))  # O(b) per record
            except EOFError:
                break
    assert [e['id'] for e in events] == [1, 2, 3]
finally:
    os.remove(path)
```

## Performance Best Practices

✅ **Do**:

- Use `dump()` with protocol 4 or higher for a large graph; it writes frames as it goes instead of
  holding the whole pickle
- Call `clear_memo()` on a reused `Pickler` between unrelated objects, so each pickle loads on its
  own
- Hand large buffers out of band with protocol 5 and `buffer_callback` rather than copying them
  into the pickle
- Keep `persistent_id` cheap; it runs once for every reference, not once per distinct object

❌ **Avoid**:

- Unpickling data from an untrusted source
- Expecting `dump()` with protocol 0-3 to save memory over `dumps()`; both hold the whole pickle
- `Pickler.fast`: it drops the memo, so shared objects are duplicated and cycles fail

## Version Notes

- **Python 3.14+**: `DEFAULT_PROTOCOL` is 5 (it was 4)
- **Python 3.14+**: Pickling a nested function or class raises `PicklingError`; earlier versions
  raise `AttributeError`
- **All Python 3**: Unpickling can run arbitrary code; never load an untrusted pickle

## Related Modules

- **[copyreg](copyreg.md)** - The global reduction table `dispatch_table` overrides per pickler
- **[pickletools](pickletools.md)** - Disassemble and optimize a pickle
- **[shelve](shelve.md)** - A persistent dictionary of pickled values
- **[copy](copy.md)** - Uses the same reduction protocol to copy in memory
- **[json](json.md)** - A data-only format, safe for untrusted input
- **[marshal](marshal.md)** - The interpreter's internal format for code objects
