# xdrlib Module Complexity

The `xdrlib` module converts values to and from XDR (External Data Representation, RFC 1014), the
big-endian, 4-byte-aligned encoding used by Sun RPC and NFS. A `Packer` appends each value to an
in-memory buffer, and an `Unpacker` reads values from a bytes-like object it holds by reference,
keeping only a read position.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The page covers the module
    as it is on Python 3.10 to 3.12. `struct` with a `>` format packs the fixed-width types on
    every version.

`n` is the bytes in the buffer a `Packer` has built or an `Unpacker` reads, `m` is the length of
one string or opaque value, and `k` is the items in one list or array. List and array rows exclude
the `k` calls to the item function the caller passes, and integers are treated as fixed-width.
A `Packer` row's space is the bytes it adds to the buffer, `get_buffer()`'s is its result, and
`Packer` times are amortized over the buffer's growth.

## Complexity Reference

### Packer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xdrlib.Packer()` | O(1) | O(1) | An empty buffer |
| `Packer.reset()` | O(1) | O(1) | Discards everything packed so far |
| `Packer.get_buffer()`, `Packer.get_buf()` | O(n) | O(n) | The packed bytes. Call it once packing is done: packing more while the result is still referenced copies the whole buffer on the next write |
| `Packer.pack_int(x)`, `Packer.pack_uint(x)`, `Packer.pack_enum(x)` | O(1) amortized | O(1) | 4 bytes. A value outside the signed or unsigned 32-bit range raises `ConversionError` |
| `Packer.pack_bool(x)` | O(1) amortized | O(1) | 4 bytes, 1 for a true value and 0 otherwise |
| `Packer.pack_hyper(x)`, `Packer.pack_uhyper(x)` | O(1) amortized | O(1) | 8 bytes. The same function: any integer is reduced modulo 2**64 without an error |
| `Packer.pack_float(x)`, `Packer.pack_double(x)` | O(1) amortized | O(1) | 4 and 8 bytes. `pack_float()` of a value too large for single precision raises `OverflowError` |
| `Packer.pack_fstring(n, s)`, `Packer.pack_fopaque(n, s)` | O(m) | O(m) | m = `n`. Writes `s` cut or zero-padded to `n` bytes, then padded to a multiple of 4; no length is written |
| `Packer.pack_string(s)`, `Packer.pack_opaque(s)`, `Packer.pack_bytes(s)` | O(m) | O(m) | m = `len(s)`. The length, then the bytes padded to a multiple of 4; a `str` raises `TypeError` |
| `Packer.pack_list(list, pack_item)` | O(k) | O(k) | Writes 1 before each item and 0 after the last, so the length need not be known up front |
| `Packer.pack_farray(n, list, pack_item)` | O(k) | O(1) | No length is written; `ValueError` unless `len(list) == n` |
| `Packer.pack_array(list, pack_item)` | O(k) | O(1) | The length, then the items |

### Unpacker

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xdrlib.Unpacker(data)` | O(1) | O(1) | Holds `data` without copying it: `bytes`, `bytearray`, or a `memoryview` of bytes |
| `Unpacker.reset(data)` | O(1) | O(1) | Starts over on new data at position 0 |
| `Unpacker.get_buffer()` | O(1) | O(1) | The object passed in, not a copy |
| `Unpacker.get_position()`, `Unpacker.set_position(position)` | O(1) | O(1) | A byte offset; `set_position()` does not check it |
| `Unpacker.done()` | O(1) | O(1) | Raises `xdrlib.Error` if any bytes remain unread |
| `Unpacker.unpack_int()`, `Unpacker.unpack_uint()`, `Unpacker.unpack_enum()` | O(1) | O(1) | `EOFError` if fewer than 4 bytes remain |
| `Unpacker.unpack_bool()` | O(1) | O(1) | Any nonzero value is `True` |
| `Unpacker.unpack_hyper()`, `Unpacker.unpack_uhyper()` | O(1) | O(1) | Signed and unsigned 64-bit |
| `Unpacker.unpack_float()`, `Unpacker.unpack_double()` | O(1) | O(1) | |
| `Unpacker.unpack_fstring(n)`, `Unpacker.unpack_fopaque(n)` | O(m) | O(m) | m = `n`. A slice of the data, so from a `memoryview` it is a view and costs O(1) |
| `Unpacker.unpack_string()`, `Unpacker.unpack_opaque()`, `Unpacker.unpack_bytes()` | O(m) | O(m) | m = the length read from the data; as `unpack_fstring()` |
| `Unpacker.unpack_list(unpack_item)` | O(k) | O(k) | Reads a 1 or 0 before each item; any other value raises `ConversionError` |
| `Unpacker.unpack_farray(n, unpack_item)` | O(k) | O(k) | k = `n` |
| `Unpacker.unpack_array(unpack_item)` | O(k) | O(k) | k = the length read from the data |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xdrlib.Error` | O(1) | O(1) | Raised by `Unpacker.done()`; the message is in `.msg` |
| `xdrlib.ConversionError` | O(1) | O(1) | A subclass of `Error`, raised for a value of the wrong type or out of range for it, and for a list marker other than 0 or 1 |

## Packing and Unpacking

Values are written and read in the same order, with no type information in the data, so the
reading side must call the matching `unpack_*` method for each `pack_*`.

```python
import xdrlib

p = xdrlib.Packer()
p.pack_int(42)  # O(1)
p.pack_string(b'hello')  # O(m)
p.pack_list([1, 2, 3], p.pack_int)  # O(k)
data = p.get_buffer()  # O(n)
assert data[:8] == b'\x00\x00\x00\x2a\x00\x00\x00\x05'
assert len(data) == 4 + (4 + 8) + (3 * 8 + 4)  # 'hello' is padded to 8 bytes

u = xdrlib.Unpacker(data)  # O(1) - no copy
assert u.unpack_int() == 42
assert u.unpack_string() == b'hello'
assert u.unpack_list(u.unpack_int) == [1, 2, 3]
u.done()  # O(1) - raises xdrlib.Error if anything is left
```

### Lists and Arrays

`pack_array()` writes the length first, and `pack_list()` writes a marker before each item, so a
list costs 4 more bytes per item but can be written by a producer that does not know its length.

```python
import xdrlib

p = xdrlib.Packer()
p.pack_array([7, 8, 9], p.pack_uint)  # O(k)
array_size = len(p.get_buffer())
p.reset()
p.pack_list([7, 8, 9], p.pack_uint)  # O(k)
assert array_size == 4 + 3 * 4
assert len(p.get_buffer()) == 3 * 8 + 4

u = xdrlib.Unpacker(p.get_buffer())
assert u.unpack_list(u.unpack_uint) == [7, 8, 9]

try:
    bad = xdrlib.Unpacker(b'\x00\x00\x00\x02')
    bad.unpack_list(bad.unpack_uint)
except xdrlib.ConversionError as error:
    assert '0 or 1 expected' in str(error)
else:
    raise AssertionError('a bad list marker was accepted')
```

## Reading Without Copying

An `Unpacker` slices the object it was given. From `bytes`, `unpack_string()` and
`unpack_opaque()` return a copy of the value; from a `memoryview`, a view onto the same memory.

```python
import xdrlib

p = xdrlib.Packer()
p.pack_opaque(b'x' * 100_000)
data = p.get_buffer()

u = xdrlib.Unpacker(data)
assert u.get_buffer() is data  # O(1) - the same object
assert type(u.unpack_opaque()) is bytes  # O(m) - a copy

u = xdrlib.Unpacker(memoryview(data))
value = u.unpack_opaque()  # O(1) - a view
assert type(value) is memoryview and value.obj is data
```

## Errors

Out-of-range 32-bit values raise `ConversionError`, but 64-bit values wrap silently, and reading
past the end raises `EOFError`, not an `xdrlib` exception.

```python
import xdrlib

p = xdrlib.Packer()
try:
    p.pack_int(2**31)
except xdrlib.ConversionError:
    pass
else:
    raise AssertionError('an out-of-range int was packed')

p.pack_hyper(2**64 + 5)  # no error: reduced modulo 2**64
assert xdrlib.Unpacker(p.get_buffer()).unpack_uhyper() == 5

u = xdrlib.Unpacker(b'\x00\x00')
try:
    u.unpack_int()
except EOFError:
    pass
else:
    raise AssertionError('a short read succeeded')

try:
    xdrlib.Unpacker(b'\x00' * 8).done()
except xdrlib.Error as error:
    assert error.msg == 'unextracted data remains'
else:
    raise AssertionError('unread data was not reported')
```

## Performance Best Practices

✅ **Do**:

- Pack everything, then call `get_buffer()` once - each fixed-width write is then amortized O(1)
- Give an `Unpacker` a `memoryview` when the data holds large opaque values you only pass on
- Call `done()` after unpacking a message to catch bytes the reader did not consume
- Use `struct` with a `>` format, padding strings to a multiple of 4 yourself, in code that has to
  run on Python 3.13 or later

❌ **Avoid**:

- Taking `get_buffer()` after every value while holding the results - each next write copies the
  whole buffer, so the packing becomes quadratic
- Relying on `pack_hyper()` to reject a value that does not fit in 64 bits
- `xdrlib` in new code - it does not exist from Python 3.13

## Version Notes

- **Python 3.11+**: `import xdrlib` emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import xdrlib` raises `ModuleNotFoundError`

## Related Modules

- **[struct](struct.md)** - packs the same fixed-width big-endian values, available on every
  version
- **[pickle](pickle.md)** - Python's own serialization, with type information in the data
- **[io](io.md)** - `BytesIO`, the buffer a `Packer` appends to
