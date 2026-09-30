# quopri Module Complexity

The `quopri` module converts bytes to and from quoted-printable, the MIME transfer encoding that
leaves printable ASCII and line breaks readable and writes most other bytes as `=XX`. The work is
done in C by `binascii.b2a_qp()` and `binascii.a2b_qp()`, and both are linear in their input.

Nothing streams. `encode()` and `decode()` take file objects, but they read the whole input with
one `read()` and hand the whole result to one `write()`, so they hold the whole input and output in
memory, as the string functions do.

`n` is the length in bytes of the input to the call: the raw data when encoding, the encoded data
when decoding. The `quotetabs` and `header` flags change which bytes are escaped, not the bound.

## Complexity Reference

### Encoding

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `quopri.encodestring(s, quotetabs=False, header=False)` | O(n) | O(n) | An escaped byte becomes three, so the output is up to about three times n |
| `quopri.encode(input, output, quotetabs, header=False)` | O(n) | O(n) | Reads all of `input`, then makes one `output.write()` |

### Decoding

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `quopri.decodestring(s, header=False)` | O(n) | O(n) | |
| `quopri.decode(input, output, header=False)` | O(n) | O(n) | Reads all of `input`, then makes one `output.write()` |

## Encoding and Decoding

### Round Trip

Most printable ASCII passes through unchanged and an escaped byte costs three, so the growth
depends on the data: plain English text barely grows, and bytes above 126 roughly triple.

```python
import quopri

text = "Hello World! Special: éàü".encode()

encoded = quopri.encodestring(text)  # O(n)
assert encoded == b"Hello World! Special: =C3=A9=C3=A0=C3=BC"

decoded = quopri.decodestring(encoded)  # O(n)
assert decoded == text

# Bytes above 126 are always escaped: three output bytes each
binary = bytes(range(128, 148))
assert len(quopri.encodestring(binary)) == 3 * len(binary)
```

### Flags

`quotetabs` escapes every space and tab, not just those at the end of a line. `header` writes an
embedded space as `_` when `quotetabs` is off, the RFC 1522 form for message headers, and decoding
with `header=True` turns `_` back into a space.

```python
import quopri

assert quopri.encodestring(b"a b\tc") == b"a b\tc"
assert quopri.encodestring(b"a b\tc", quotetabs=True) == b"a=20b=09c"

assert quopri.encodestring(b"a b_c", header=True) == b"a_b=5Fc"
assert quopri.decodestring(b"a_b=5Fc", header=True) == b"a b_c"
```

### Soft Line Breaks

Encoding splits a long input line with `=` soft breaks, so encoded lines stay short however long
the input line is, and decoding joins the pieces again.

```python
import quopri

encoded = quopri.encodestring(b"x" * 200)  # O(n)
lines = encoded.split(b"\n")
assert len(lines) == 3
assert all(len(line) <= 76 for line in lines)
assert lines[0].endswith(b"=")

assert quopri.decodestring(encoded) == b"x" * 200  # O(n)
```

## Working With Files

`encode()` and `decode()` are the string functions behind a file interface. They read the whole
input before converting any of it, so a file costs its full size in memory, input and output both.

```python
import io
import quopri

source = io.BytesIO("naïve café\n".encode() * 3)
target = io.BytesIO()

quopri.encode(source, target, quotetabs=False)  # O(n) time and memory
assert target.getvalue() == b"na=C3=AFve caf=C3=A9\n" * 3

back = io.BytesIO()
quopri.decode(io.BytesIO(target.getvalue()), back)  # O(n) time and memory
assert back.getvalue() == "naïve café\n".encode() * 3
```

### Encoding a Large File in Pieces

Quoted-printable is line-oriented, so in a file with one line-ending style, pieces that end on a
newline encode independently: joined, they are the same bytes as encoding the file in one call, and
memory follows the piece rather than the file.

```python
import io
import quopri

data = b"".join(b"line %d \t with trailing space \n" % i for i in range(1_000))
source = io.BytesIO(data)
target = io.BytesIO()

while True:
    piece = b"".join(source.readline() for _ in range(100))  # up to 100 whole lines
    if not piece:
        break
    target.write(quopri.encodestring(piece))  # memory follows the piece

assert target.getvalue() == quopri.encodestring(data)
```

## Performance Best Practices

✅ **Do**:

- Encode a large file in pieces that end on a newline, so memory follows the piece

❌ **Avoid**:

- Passing a large file to `encode()` or `decode()` expecting it to stream - both read all of it
- Quoted-printable for data that is mostly not printable ASCII - it approaches three times the
  size, where `base64` adds about a third

## Related Modules

- **[binascii](binascii.md)** - `b2a_qp()` and `a2b_qp()`, the C functions that do the work
- **[base64](base64.md)** - the denser encoding for binary data
- **[codecs](codecs.md)** - the `quopri` codec, which encodes with `quotetabs=True`
- **[email](email.md)** - applies quoted-printable as a Content-Transfer-Encoding
