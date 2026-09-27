# struct Module Complexity

The `struct` module converts between Python values and packed binary records described by a
format string such as `'<4sIh'`. The work is C, done in one pass over a compiled list of field
codes: packing writes one record into a bytes object or a buffer you supply, unpacking reads one
record into a tuple. Nothing is held between calls except compiled formats.

`m` is the characters in the format string, `k` is the fields in one record (values packed or
unpacked; a repeat count on `s` or `p` makes one field, pad bytes `x` make none), `B` is the
record's size in bytes (`calcsize()`), `t` is the bytes in its `s` fields, and `n` is the records
in a buffer. Converting one value is priced at O(1): integers and floats are fixed width, and a
`p` field returns at most 255 bytes. The module-level functions look the format up in a cache of
compiled formats first. The rows assume a hit on the same string object, such as a literal
reused in a loop, whose lookup is O(1); an equal string built fresh for each call costs O(m) to
hash and compare, and a miss adds the O(m) compile.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `struct.pack(format, v1, v2, ...)` | O(k + B) | O(B) | Every byte of the output is written, pad bytes included |
| `struct.pack_into(format, buffer, offset, v1, v2, ...)` | O(k + B) | O(1) | Writes B bytes at `offset` in a writable buffer; allocates no output |
| `struct.unpack(format, buffer)` | O(k + t) | O(k + t) | The buffer must be exactly B bytes; pad bytes are skipped, not read |
| `struct.unpack_from(format, /, buffer, offset=0)` | O(k + t) | O(k + t) | Unpacks the B-byte record at `offset`; the rest of the buffer is not copied |
| `struct.iter_unpack(format, buffer)` | O(1) | O(1) | Exports the buffer instead of copying it; its length must be a multiple of B |
| Iterating an `iter_unpack()` iterator | O(k + t) per record | O(k + t) per record | O(n·(k + t)) for the whole buffer, one tuple at a time |
| `struct.calcsize(format)` | O(1) | O(1) | Reads B from the compiled format |

### Struct

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `struct.Struct(format)` | O(m) | O(m) | Compiles once; a repeat count is stored, not expanded, so `'1000i'` compiles to one code |
| `Struct.pack(v1, v2, ...)` | O(k + B) | O(B) | Same as `struct.pack()` without the cache lookup |
| `Struct.pack_into(buffer, offset, v1, v2, ...)` | O(k + B) | O(1) | |
| `Struct.unpack(buffer)` | O(k + t) | O(k + t) | |
| `Struct.unpack_from(buffer, offset=0)` | O(k + t) | O(k + t) | |
| `Struct.iter_unpack(buffer)` | O(1) | O(1) | Records are unpacked as the iterator is advanced |
| `Struct.format` | O(m) | O(m) | Built from the stored format on each access |
| `Struct.size` | O(1) | O(1) | B, computed when the format was compiled |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `struct.error` | O(1) | O(1) | Raised for a bad format, a wrong number of values, a value out of range, or a buffer of the wrong size; the count and size checks run before any value is converted |

## Packing and Unpacking

Packing allocates the whole record and writes every byte of it; unpacking builds one tuple element
per field. A format's prefix picks the byte order and whether native alignment inserts padding:
it changes the layout, not the bound.

```python
import struct

data = struct.pack('<ihd', 1, 2, 3.5)  # O(k + B)
assert len(data) == struct.calcsize('<ihd') == 14  # O(1) on a cache hit
assert struct.unpack('<ihd', data) == (1, 2, 3.5)  # O(k + t)

# Byte order changes where the bytes go, not how many there are
assert struct.pack('>I', 1) == b'\x00\x00\x00\x01'
assert struct.pack('<I', 1) == b'\x01\x00\x00\x00'

# Native mode ('@', the default) aligns fields; the standard modes do not
assert struct.calcsize('=ci') == 5
assert struct.calcsize('@ci') > struct.calcsize('=ci')

# A repeat count packs several values of one type
values = struct.unpack('>10H', struct.pack('>10H', *range(10)))  # O(k)
assert values == tuple(range(10))
```

### Pad Bytes and Byte Strings

A pad byte costs `pack()` a write, because the output is zero-filled, and costs `unpack()`
nothing, because no value is built for it. An `s` field is the opposite of a number: its bytes are
copied on the way in and out, which is the `t` in the unpack bound. An argument longer than its
field is truncated, so it costs the field's width, not its own length.

```python
import struct

record = struct.Struct('4x2s')
data = record.pack(b'ok')  # O(B) - four zero bytes, then the field
assert data == b'\x00\x00\x00\x00ok'
assert record.unpack(data) == (b'ok',)  # O(k + t) - the pad bytes are skipped

# A short argument is padded with zeros, a long one truncated to the field
assert struct.pack('5s', b'ab') == b'ab\x00\x00\x00'
assert struct.pack('2s', b'abcdef') == b'ab'  # O(2), not O(6)
```

## Reusing a Compiled Format

`struct.Struct(format)` parses the format once. The module-level functions keep a cache of the
formats they have compiled, keyed by the format string, so a format used repeatedly is not
re-parsed either way; a `Struct` saves the lookup. The cache holds 100 formats in CPython and is
emptied when it fills, so a program that uses more than 100 formats in turn compiles on every
call. Build `Struct` objects where the rest of your constants are built; building one
for a format used once pays the same compile the module call would have.

```python
import struct

HEADER = struct.Struct('<4sIH')  # O(m), once

packed = HEADER.pack(b'DATA', 1024, 7)  # O(k + B), no cache lookup
assert len(packed) == HEADER.size == 10  # O(1)
assert HEADER.unpack(packed) == (b'DATA', 1024, 7)  # O(k + t)

assert HEADER.format == '<4sIH'  # O(m) - built on each access

# The module-level call compiles and caches its own copy on first use
assert struct.unpack('<4sIH', packed) == HEADER.unpack(packed)
```

## Buffers and Offsets

`pack_into()` writes into memory you already own and `unpack_from()` reads a record at an offset
without slicing the buffer, so neither copies the rest of the buffer. `iter_unpack()` walks a
buffer of back-to-back records one tuple at a time. The iterator holds an export of the buffer
until it is exhausted, so a `bytearray` cannot be resized while one is open.

```python
import struct

point = struct.Struct('<hh')
buffer = bytearray(point.size * 3)

for index, (x, y) in enumerate([(1, 2), (3, 4), (5, 6)]):
    point.pack_into(buffer, index * point.size, x, y)  # O(k + B), no output allocated

assert point.unpack_from(buffer, 4) == (3, 4)  # O(k + t), no slice
assert struct.unpack_from('<h', buffer, offset=8) == (5,)

records = point.iter_unpack(buffer)  # O(1) - exports the buffer
try:
    buffer.extend(b'\x00\x00\x00\x00')
except BufferError as error:
    assert 're-sized' in str(error)
else:
    raise AssertionError('the buffer was resized under an open iterator')

assert list(records) == [(1, 2), (3, 4), (5, 6)]  # O(n·(k + t))
buffer.extend(b'\x00\x00\x00\x00')  # the export is released at exhaustion
```

## Errors

Size and count checks run against the compiled format before any value is converted, so a
mismatch is rejected in O(1) once the format is compiled.

```python
import struct

try:
    struct.unpack('<i', b'AB')  # O(1) - the length check comes first
except struct.error as error:
    assert '4 bytes' in str(error)
else:
    raise AssertionError('a short buffer was unpacked')

try:
    struct.pack('<hh', 1)  # O(1) - wrong number of values
except struct.error as error:
    assert 'expected 2 items' in str(error)
else:
    raise AssertionError('a missing value was packed')

try:
    struct.pack('<h', 70000)  # out of range for a short
except struct.error as error:
    assert 'format requires' in str(error)
else:
    raise AssertionError('an out-of-range value was packed')

try:
    struct.calcsize('z')  # rejected while compiling
except struct.error as error:
    assert 'bad char' in str(error)
else:
    raise AssertionError('an unknown format character was accepted')
```

## Common Patterns

### Reading a Header and a Table of Records

```python
import io
import struct

HEADER = struct.Struct('<4sI')  # magic, record count
RECORD = struct.Struct('<Hf')   # id, score

stream = io.BytesIO()
stream.write(HEADER.pack(b'SCOR', 3))
for record_id, score in [(1, 0.5), (2, 1.5), (3, 2.5)]:
    stream.write(RECORD.pack(record_id, score))  # O(k + B) per record

data = stream.getvalue()
magic, count = HEADER.unpack_from(data)  # O(k + t)
assert (magic, count) == (b'SCOR', 3)

body = memoryview(data)[HEADER.size:]  # O(1) - no copy of the records
scores = {rid: score for rid, score in RECORD.iter_unpack(body)}  # O(n·(k + t))
assert scores == {1: 0.5, 2: 1.5, 3: 2.5}
```

### Length-Prefixed Messages

```python
import struct

LENGTH = struct.Struct('!I')  # network byte order

def frame(payload):
    return LENGTH.pack(len(payload)) + payload  # O(len(payload))

def unframe(data):
    (length,) = LENGTH.unpack_from(data)  # O(1)
    return data[LENGTH.size:LENGTH.size + length]  # O(length) - a slice copies

message = frame(b'hello')
assert message == b'\x00\x00\x00\x05hello'
assert unframe(message) == b'hello'
```

## Performance Best Practices

✅ **Do**:

- Build a `Struct` once for a format you use repeatedly, alongside your other constants
- Use `pack_into()` to fill a preallocated buffer, so no output bytes object is allocated per record
- Use `unpack_from()` or a `memoryview` rather than slicing bytes, which copies the slice
- Use `iter_unpack()` for a buffer of fixed-size records instead of a loop of slices

❌ **Avoid**:

- Building a `Struct` for a format used once - it pays the same compile the module call would
- Using more than 100 formats in turn through the module-level functions: every call compiles
- Resizing a `bytearray` while an `iter_unpack()` iterator over it is still open

## Version Notes

- **Python 3.14+**: Added the `F` and `D` format characters for complex numbers
- **All Python 3**: Native mode (`@`, the default) uses the platform's sizes and alignment; the
  standard modes do not

## Related Modules

- **[array](array.md)** - a homogeneous sequence of one C type, when every field has the same type
- **[memoryview](../builtins/memoryview_func.md)** - zero-copy slices to pass to `unpack_from()`
  and `iter_unpack()`
- **[ctypes](ctypes.md)** - C structures with named fields, when a record is shared with C code
- **[io](io.md)** - `BytesIO` for assembling and reading binary streams in memory
