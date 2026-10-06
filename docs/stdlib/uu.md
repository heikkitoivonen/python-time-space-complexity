# uu Module Complexity

The `uu` module converts binary data to and from uuencoding, a text format of lines of up to 61
characters framed by a `begin` line carrying a file name and permission bits and an `end` line.
Both functions stream: `encode()` reads 45 bytes and writes one line, and `decode()` reads and
writes a line at a time, so neither holds the data. The per-line conversion is `binascii`'s.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The page covers the module
    as it is on Python 3.10 to 3.12; the examples need 3.10.12+, 3.11.4+ or 3.12.
    `binascii.b2a_uu()` and `binascii.a2b_uu()`, which convert one line, remain.

`n` is the bytes of binary data, `m` is the bytes `decode()` reads, from the start of its input
through the `end` line, and `l` is the longest of the lines it reads. The header's file name is
treated as short. Space is what the module holds, not the output, which the caller's file keeps.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `uu.encode(in_file, out_file, name=None, mode=None, *, backtick=False)` | O(n) | O(1) | Reads 45 bytes at a time and writes one line per read. Both files are binary. A path is opened and closed for you, and `'-'` is standard input or output. `name` and `mode` default to the input path's base name and permission bits, or to `-` and `0o666` otherwise. `backtick=True` writes zeros as `` ` `` instead of spaces |
| `uu.decode(in_file, out_file=None, mode=None, quiet=False)` | O(m) | O(l) | Reads a line at a time, skipping lines until a valid `begin` line, and stops at `end`: nothing after it is read. `encode()` writes data lines of at most 62 bytes, but a long line before `begin` is held whole. Without `out_file` it writes to the header's name, relative to the current directory, or to standard output for `-`. `mode`, or the header's, is applied only when the output is a path |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `uu.Error` | O(1) | O(1) | Raised by `decode()` for input with no `begin` line or no `end` line, and for a header name it refuses to write; a data line that is corrupt within its own length raises `binascii.Error` instead |

## Encoding and Decoding

Both directions need binary file objects, and go a line at a time.

```python
import io
import uu

data = bytes(range(256)) * 4
encoded = io.BytesIO()
uu.encode(io.BytesIO(data), encoded, name='data.bin', mode=0o644)  # O(n)

lines = encoded.getvalue().splitlines()
assert lines[0] == b'begin 644 data.bin'
assert lines[1][:1] == b'M'  # length character: 45 bytes on a full line
assert lines[-2:] == [b' ', b'end']
full, rest = divmod(len(data), 45)
assert len(lines) == 1 + full + (rest > 0) + 2  # header, data lines, ' ' and 'end'

decoded = io.BytesIO()
encoded.seek(0)
uu.decode(encoded, decoded)  # O(m) time, O(l) memory
assert decoded.getvalue() == data

try:
    uu.encode(io.BytesIO(data), io.StringIO())
except TypeError:
    pass
else:
    raise AssertionError('a text-mode output was accepted')
```

### Finding the Data

`decode()` reads every line before the `begin` line, such as the headers of a mail message, and
nothing after the `end` line, so trailing text costs nothing. Each line it reads is held whole
while it is checked.

```python
import io
import uu

encoded = io.BytesIO()
uu.encode(io.BytesIO(b'payload'), encoded, name='p.bin')

message = io.BytesIO(
    b'Subject: attachment\n\n' + encoded.getvalue() + b'-- \nsignature\n'
)
decoded = io.BytesIO()
uu.decode(message, decoded)  # O(m) - the headers, then the data, then stops
assert decoded.getvalue() == b'payload'
assert message.read() == b'-- \nsignature\n'  # left unread
```

## Decoding to the Header's File Name

Without `out_file`, `decode()` creates the file the header names, relative to the current
directory, and sets its permission bits from the header; the name `-` means standard output. It
refuses a name that exists, one starting with a path separator, and one containing `../`, raising
`uu.Error` before it writes anything.

```python
import io
import os
import tempfile
import uu

def encoded(name):
    out = io.BytesIO()
    uu.encode(io.BytesIO(b'hello'), out, name=name, mode=0o600)
    out.seek(0)
    return out

previous = os.getcwd()
with tempfile.TemporaryDirectory() as directory:
    os.chdir(directory)
    try:
        uu.decode(encoded('hello.txt'))  # O(m)
        with open('hello.txt', 'rb') as f:
            assert f.read() == b'hello'

        for name in ('hello.txt', os.sep + 'new.txt', '../new.txt'):
            try:
                uu.decode(encoded(name))
            except uu.Error as error:
                assert name in str(error)
            else:
                raise AssertionError(f'{name} was written')
        assert os.listdir() == ['hello.txt']
    finally:
        os.chdir(previous)
```

## Malformed Input

Input with no `begin` line raises `uu.Error` once all of it has been read. Input that ends before
the `end` line raises `uu.Error` too, but only after writing every line it decoded, so an output
file is left partly written. A line with characters past the length its first character gives
that `binascii` rejects, as some broken encoders write, is decoded to that length with a warning
on standard error unless `quiet=True`. A line that is corrupt within that length, such as one with
a character outside the encoding's alphabet, raises `binascii.Error`.

```python
import binascii
import io
import uu

try:
    uu.decode(io.BytesIO(b'no data here\n'), io.BytesIO())  # O(m), reads it all
except uu.Error as error:
    assert 'No valid begin line' in str(error)
else:
    raise AssertionError('input with no begin line was accepted')

encoded = io.BytesIO()
uu.encode(io.BytesIO(b'x' * 100), encoded)
truncated = encoded.getvalue().replace(b' \nend\n', b'')
partial = io.BytesIO()
try:
    uu.decode(io.BytesIO(truncated), partial)
except uu.Error as error:
    assert 'Truncated' in str(error)
else:
    raise AssertionError('input with no end line was accepted')
assert partial.getvalue() == b'x' * 100  # everything before the end was written

padded = binascii.b2a_uu(b'hi').rstrip(b'\n') + b'xyz\n'
recovered = io.BytesIO()
uu.decode(io.BytesIO(b'begin 644 f\n' + padded + b' \nend\n'), recovered, quiet=True)
assert recovered.getvalue() == b'hi'

try:
    uu.decode(io.BytesIO(b'begin 644 f\nM' + b'\x7f' * 60 + b'\n \nend\n'), io.BytesIO())
except binascii.Error:
    pass
else:
    raise AssertionError('a corrupt line was decoded')
```

## Performance Best Practices

✅ **Do**:

- Hand `decode()` the whole message, headers and all - it skips to the `begin` line and stops at
  `end`, holding one line at a time
- Write `binascii.b2a_uu()` and `binascii.a2b_uu()` loops, or use `base64`, in code that has to run
  on Python 3.13 or later

❌ **Avoid**:

- Reading the whole input into memory first - `decode()` needs only a line at a time
- Decoding input whose `end` line may be missing straight into the final file - a truncated input
  leaves it partly written
- `uu` in new code - it does not exist from Python 3.13

## Version Notes

- **Python 3.10.12+, 3.11.4+**: `decode()` without `out_file` refuses a header name that starts
  with a path separator or contains `../`
- **Python 3.11+**: `import uu` emits a `DeprecationWarning`
- **Python 3.13+**: Removed by PEP 594; `import uu` raises `ModuleNotFoundError`

## Related Modules

- **[binascii](binascii.md)** - `b2a_uu()` and `a2b_uu()`, the one-line conversions `uu` loops over,
  available on every version
- **[base64](base64.md)** - the modern alternative for carrying binary data as text
- **[io](io.md)** - `BytesIO` for encoding and decoding in memory
