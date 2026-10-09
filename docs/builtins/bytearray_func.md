# bytearray() Function Complexity

The `bytearray()` function builds a mutable sequence of bytes from a count, a bytes-like object,
an iterable of ints or a string, and `bytearray.fromhex()` builds one from hexadecimal digits.
Every form that takes data copies it: the new buffer shares nothing with its source, so the
cost is the size of that source. The type's own operations are covered on
[Bytearray Type](bytearray.md).

`n` is the count passed to `bytearray(count)`, and `k` is the size of the source: bytes in a
bytes-like object, items in an iterable, characters in a string. An item of an iterable is an
`int` in `range(256)`, read at O(1), and the encoding row assumes a codec and error handler
whose cost and output are proportional to their input, as the byte-oriented codecs are. A
structured codec can cost more.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bytearray()` | O(1) | O(1) | Empty, with no buffer allocated |
| `bytearray(count)` | O(n) | O(n) | n = count zero bytes; a negative count raises `ValueError` |
| `bytearray(bytes_like)` | O(k) | O(k) | Copies the buffer of a `bytes`, `bytearray`, `memoryview` or `array.array`; the copy is independent of its source |
| `bytearray(iterable)` | O(k) | O(k) | One byte per item; an item outside `range(256)` raises `ValueError` |
| `bytearray(string, encoding, errors='strict')` | O(k) | O(k) | Encodes to a `bytes` and copies it in; k = characters in the string, which the encoder walks whatever it emits. A `str` without an encoding raises `TypeError` |
| `bytearray.fromhex(string)` | O(k) | O(k) | k = characters, one byte per pair; whitespace between pairs is skipped. Class method |

## Every Source Is Copied

A bytes-like source is copied in one step, and an iterable is read an item at a time; either
way the result is a buffer of its own, and changing it leaves the source alone. A
`memoryview` is the O(1) way to work on an existing buffer without copying it.

```python
import array

source = b"hello"
copy = bytearray(source)  # O(k) - a buffer of its own
copy[0] = ord("j")
assert source == b"hello" and copy == bytearray(b"jello")

assert bytearray(array.array("B", [1, 2])) == bytearray(b"\x01\x02")  # O(k)
assert bytearray(value * 2 for value in range(3)) == bytearray(b"\x00\x02\x04")  # O(k)

view = memoryview(copy)  # O(1) - shares the buffer instead
view[0] = ord("y")
assert copy == bytearray(b"yello")
view.release()

try:
    bytearray([0, 256])
except ValueError as error:
    assert "range(0, 256)" in str(error)
else:
    raise AssertionError("an item above 255 was accepted")
```

### A Count Is a Size, Not a Value

An `int` argument is the length of a zero-filled buffer, so `bytearray(count)` costs O(n) and
`bytearray([count])` is the one-byte bytearray holding that value.

```python
zeros = bytearray(4)  # O(n) - n zero bytes
assert zeros == bytearray(b"\x00\x00\x00\x00")

one_byte = bytearray([4])  # O(1) - a single item
assert one_byte == bytearray(b"\x04")

try:
    bytearray(-1)
except ValueError as error:
    assert "negative count" in str(error)
else:
    raise AssertionError("a negative count was accepted")
```

## Text and Hexadecimal Sources

A `str` needs an encoding, and is encoded to a `bytes` that is then copied in. `fromhex()`
reads two hexadecimal digits per byte and skips the whitespace between pairs.

```python
assert bytearray("café", "utf-8") == bytearray(b"caf\xc3\xa9")  # O(k)
assert bytearray("é" * 3, "ascii", "ignore") == bytearray()  # O(k) - nothing emitted, all read

try:
    bytearray("café")
except TypeError as error:
    assert "without an encoding" in str(error)
else:
    raise AssertionError("a str was accepted without an encoding")

assert bytearray.fromhex("48 65 6c") == bytearray(b"Hel")  # O(k)
assert bytearray(b"Hel").hex() == "48656c"  # the inverse
```

## Common Patterns

### Preallocating a Read Buffer

`bytearray(count)` pays for its zero-fill once. `readinto()` then writes each chunk into that
same buffer, and a `memoryview` reads the chunk in place.

```python
import io

stream = io.BytesIO(b"0123456789")
buffer = bytearray(4)  # O(n) - allocated once
view = memoryview(buffer)  # O(1) - its slices copy nothing
total = 0

while size := stream.readinto(buffer):  # O(k) - fills the existing buffer
    total += sum(view[:size])  # O(k) - reads the chunk in place

assert total == sum(b"0123456789")
view.release()
```

## Performance Best Practices

✅ **Do**:

- Pass a bytes-like source when you have one; it is copied in one step, where an iterable is read an item at a time
- Take a `memoryview` of an existing buffer when you do not need an independent copy; `bytearray(source)` copies all k bytes
- Preallocate with `bytearray(count)` and refill it with `readinto()` or same-length slice assignment, rather than building a new buffer per chunk

❌ **Avoid**:

- `bytearray(count)` when you mean a one-byte bytearray holding `count` - it allocates count zero bytes; use `bytearray([count])`
- `bytearray(text)` without an encoding - it raises `TypeError`

## Version Notes

- **Python 3.14+**: `fromhex()` accepts bytes-like input as well as `str`

## Related Functions

- **[Bytearray Type](bytearray.md)** - The operations and methods of the bytearray this builds
- **[bytes()](bytes_func.md)** - The immutable counterpart, built the same ways
- **[memoryview()](memoryview_func.md)** - O(1) views over an existing buffer
- **[str](str.md)** - `encode()` produces the bytes that `bytearray(text, encoding)` copies in
