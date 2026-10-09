# bytes() Function Complexity

The `bytes()` constructor builds an immutable sequence of bytes from a count, a bytes-like
object, an iterable of integers, a string with an encoding, or an object's `__bytes__()`
method. An exact `bytes` is immutable, so `bytes(b)` returns `b` itself; every other source is
copied or converted.

`n` is the count passed to `bytes(count)`, `k` is the length of the source - the bytes in a
bytes-like object, the items of an iterable, or the characters in a string - and `f` is the
time and space a `__bytes__()` method takes. An item of an iterable is an `int` in
`range(256)`, read at O(1), and the encoding row assumes a codec and error handler whose cost
and output are proportional to their input, as the byte-oriented codecs are. A structured
codec can cost more.

## Complexity Reference

### Construction

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bytes()` | O(1) | O(1) | The shared empty `bytes`; `bytes(0)` returns it too |
| `bytes(count)` | O(n) | O(n) | n zero bytes |
| `bytes(b)` where `b` is a `bytes` | O(1) | O(1) | Returns `b` itself. An instance of a `bytes` subclass is copied, O(k) |
| `bytes(bytes_like)` | O(k) | O(k) | Copies the buffer of a `bytearray`, `memoryview` or `array.array`; the copy keeps its value when the source changes |
| `bytes(iterable)` | O(k) | O(k) | One byte per item |
| `bytes(string, encoding, errors='strict')` | O(k) | O(k) | The encoder `str.encode(string, encoding, errors)` runs; k = characters in the string, which it walks whatever it emits |
| `bytes(obj)` where `obj` defines `__bytes__()` | O(f) | O(f) | Takes precedence over the other forms; a result that is not a `bytes` raises `TypeError` |

### Errors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bytes(count)` with a negative count | O(1) | O(1) | `ValueError`, before anything is allocated |
| `bytes(iterable)` with an item outside `range(256)` | O(k) | O(k) | `ValueError` at the first such item; no item after it is read |
| `bytes(string)` without an encoding | O(1) | O(1) | `TypeError`, before the string is read; so is `errors` without an encoding |
| `bytes(obj, encoding)` where `obj` is not a `str` | O(1) | O(1) | `TypeError`, before `obj` is read |

## Copying and Sharing

A `bytes` cannot change, so converting one to `bytes` hands back the same object. A mutable
source is copied, and the copy keeps its value when the source changes; `memoryview()` views a
buffer in O(1) without copying it.

```python
data = b"payload"
assert bytes(data) is data  # O(1) - an exact bytes is returned as it is

buffer = bytearray(b"payload")
frozen = bytes(buffer)  # O(k) - a copy
buffer[0] = ord("P")
assert frozen == b"payload"  # the copy kept its value

view = memoryview(buffer)  # O(1) - shares the buffer instead
assert bytes(view[:3]) == b"Pay"  # O(k) - copies only the 3 bytes the view covers
```

## Integers Are Counts

An `int` argument is a length, not a value: `bytes(5)` is five zero bytes, and `bytes(n)`
allocates n of them however large n is. `int.to_bytes()` encodes the value instead. An
iterable of integers supplies one byte per item.

```python
assert bytes(5) == b"\x00\x00\x00\x00\x00"  # O(n) - five zero bytes, not the number 5
assert (5).to_bytes(1, "big") == b"\x05"  # O(length) - the value

assert bytes([72, 105]) == b"Hi"  # O(k) - one byte per item
assert bytes(range(3)) == b"\x00\x01\x02"  # O(k) - any iterable of ints

try:
    bytes(-1)
except ValueError as error:
    assert "negative count" in str(error)
else:
    raise AssertionError("a negative count was accepted")

try:
    bytes([65, 256])
except ValueError as error:
    assert "range(0, 256)" in str(error)
else:
    raise AssertionError("an item outside range(256) was accepted")
```

## Encoding Text

`bytes(text, encoding)` runs the same encoder as `str.encode()`, at O(k) in the
characters. A `str` without an encoding is rejected before it is read, as is an encoding
given for anything that is not a `str`. Hex digits are not an encoding: `bytes.fromhex()`
reads them.

```python
text = "café"

encoded = bytes(text, "utf-8")  # O(k) - k = characters
assert encoded == text.encode("utf-8") == b"caf\xc3\xa9"
assert len(encoded) == 5  # é takes two bytes in UTF-8

assert bytes(text, "ascii", "replace") == b"caf?"  # O(k)
assert bytes.fromhex("63 61 66") == b"caf"  # O(k) - two hex digits per byte

try:
    bytes(text, "ascii")  # errors='strict'
except UnicodeEncodeError as error:
    assert error.start == 3
else:
    raise AssertionError("é was encoded as ASCII")

try:
    bytes(text)  # O(1) - rejected before it is read
except TypeError as error:
    assert "without an encoding" in str(error)
else:
    raise AssertionError("a str was converted without an encoding")

try:
    bytes(b"cafe", "utf-8")  # O(1)
except TypeError as error:
    assert "encoding without a string" in str(error)
else:
    raise AssertionError("an encoding was applied to bytes")
```

## Objects That Define `__bytes__`

`bytes(obj)` calls `obj.__bytes__()` when it exists, ahead of the buffer, count and iterable
forms, and returns its result. The cost is the method's own.

```python
class Packet:
    def __init__(self, payload):
        self.payload = payload

    def __bytes__(self):
        return len(self.payload).to_bytes(2, "big") + self.payload


packet = Packet(b"data")
assert bytes(packet) == b"\x00\x04data"  # O(f) - whatever __bytes__ costs
```

## Common Patterns

### Building Then Freezing

```python
buffer = bytearray()
for value in range(5):
    buffer.append(value)  # O(1) amortized

frozen = bytes(buffer)  # O(k) - one copy, at the end
assert frozen == b"\x00\x01\x02\x03\x04"
assert bytes(frozen) is frozen  # O(1) - converting it again copies nothing
```

## Performance Best Practices

✅ **Do**:

- Build changing data in a `bytearray` and call `bytes()` once at the end; concatenating `bytes` copies everything accumulated every time
- Normalise an argument with `bytes(x)` freely when it is usually a `bytes` already; that case is O(1)
- Take part of a large buffer as a `memoryview()` slice, which is O(1); `bytes(view)` then copies only the bytes the view covers

❌ **Avoid**:

- `bytes(n)` to convert an integer - it allocates n zero bytes; `n.to_bytes(length, byteorder)` encodes the value
- Converting a `bytearray` you keep changing with `bytes()` after every change - each call copies all of it

## Related Functions

- **[bytes](bytes.md)** - The type's operations and methods, including `decode()` and the `bytes.fromhex()` alternate constructor
- **[bytearray()](bytearray_func.md)** - The mutable counterpart, built from a count, a buffer, an iterable or a string
- **[bytearray](bytearray.md)** - The mutable type's methods, for building data before freezing it with `bytes()`
- **[str](str.md)** - `str.encode()`, the encoder `bytes(text, encoding)` runs
- **[memoryview()](memoryview_func.md)** - O(1) views over a buffer, where `bytes()` copies it
