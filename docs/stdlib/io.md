# io Module Complexity

The `io` module is the stack behind `open()`: a raw layer that makes one system call per sized
read or write, a buffered layer that batches those calls, and a text layer that encodes and decodes.
It also provides `StringIO` and `BytesIO`, which are the same interfaces over a buffer held in
memory. Only `read()` with no size, `readall()`, `readlines()` and `getvalue()` return a whole
stream at once.

`n` is the bytes in a stream, or the characters for `StringIO`, and `k` is the bytes or characters
one call reads, writes or returns; a write past the end also counts the gap it fills. `b` is a
buffered object's buffer size, and `c` is the bytes a
`TextIOWrapper` decoded in its last chunk. A system call is priced at the bytes it moves, and
encoding or decoding at O(1) per character, for a codec whose state clears between characters as
UTF-8, UTF-16 and the single-byte codecs do. An operation that flushes - `close()`, `detach()`,
`seek()`, `truncate()`, and `tell()` or `reconfigure()` on a text stream - first pays up to O(b)
to write out what its buffer holds.

## Complexity Reference

### open

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None)` | O(1) | O(b) | The builtin `open()`: a `FileIO`, then a buffered object unless `buffering=0`, then a `TextIOWrapper` in text mode |
| `io.open_code(path)` | O(1) | O(b) | Opens `path` for reading in binary mode |
| `io.text_encoding(encoding, stacklevel=2)` | O(1) | O(1) | Returns `encoding`, or the default when it is `None`; Python 3.10+ |
| `io.DEFAULT_BUFFER_SIZE` | O(1) | O(1) | The `b` a buffered object gets when none is given |

### IOBase

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.IOBase` | O(1) | O(1) | Base class of every stream; `isinstance(f, io.IOBase)` holds for all of them |
| `IOBase.readline(size=-1)` | O(k) | O(k) | On an object with no `peek()`, such as an unbuffered raw file, one `read(1)` call per byte |
| `IOBase.readlines(hint=-1)`, `list(f)` | O(n) | O(n) | Every remaining line at once, or whole lines until their total passes `hint`; iterate instead to hold one |
| Iterating an `IOBase` | O(k) per line | O(k) | Calls `readline()` |
| `IOBase.writelines(lines)` | O(n) | O(k) | n = total length of `lines`; one `write()` per item, adding no separators |
| `IOBase.seek(offset, whence=os.SEEK_SET)`, `IOBase.tell()` | O(1) | O(1) | Binary streams; see `TextIOWrapper` for text |
| `IOBase.truncate(size=None)` | O(1) | O(1) | On a file, one system call |
| `IOBase.flush()` | O(1) | O(1) | Nothing to do here; a buffered writer writes out what it holds |
| `IOBase.close()`, `IOBase.closed` | O(1) | O(1) | `close()` flushes first |
| `IOBase.fileno()`, `IOBase.isatty()`, `IOBase.readable()`, `IOBase.seekable()`, `IOBase.writable()` | O(1) | O(1) | `fileno()` raises `UnsupportedOperation` on an in-memory stream |

### RawIOBase and FileIO

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.RawIOBase` | O(1) | O(1) | Unbuffered binary streams: each sized read or write is at most one system call |
| `RawIOBase.read(size=-1)` | O(k) | O(k) | May return fewer than `size` bytes; `size=-1` is `readall()` |
| `RawIOBase.readall()` | O(n) | O(n) | Reads until end of file, one system call after another |
| `RawIOBase.readinto(b)` | O(k) | O(1) | Fills a buffer you own, allocating nothing |
| `RawIOBase.write(b)` | O(k) | O(1) | May write fewer bytes than given; check the return value |
| `io.FileIO(name, mode='r', closefd=True, opener=None)` | O(1) | O(1) | One `open` system call; what `open(..., buffering=0)` returns |
| `FileIO.mode`, `FileIO.name` | O(1) | O(1) | Stored at construction |

### BufferedIOBase, BufferedReader, BufferedWriter, BufferedRandom, BufferedRWPair

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.BufferedIOBase` | O(1) | O(1) | Buffered binary streams; also what `BytesIO` implements |
| `io.BufferedReader(raw, buffer_size=DEFAULT_BUFFER_SIZE)` | O(1) | O(b) | What `open(..., 'rb')` returns |
| `io.BufferedWriter(raw, buffer_size=DEFAULT_BUFFER_SIZE)` | O(1) | O(b) | What `open(..., 'wb')` returns |
| `io.BufferedRandom(raw, buffer_size=DEFAULT_BUFFER_SIZE)` | O(1) | O(b) | What `open(..., 'r+b')` returns; one buffer serves reads and writes |
| `io.BufferedRWPair(reader, writer, buffer_size=DEFAULT_BUFFER_SIZE)` | O(1) | O(b) | Two raw streams, one each way, each with its own buffer; not seekable |
| `BufferedIOBase.read(size=-1)`, `BufferedReader.read(size=-1)` | O(k) amortized | O(k) | Small reads come from the buffer, so a run of them costs one raw read per `b` bytes; `size=-1` reads to the end |
| `BufferedIOBase.read1(size=-1)`, `BufferedReader.read1(size=-1)` | O(k) | O(k) | At most one raw read |
| `BufferedReader.peek(size=0)` | O(b) | O(b) | Returns buffered bytes without consuming them, making at most one raw read; the result can be longer or shorter than `size` |
| `BufferedIOBase.readinto(b)`, `BufferedIOBase.readinto1(b)` | O(k) | O(k) | The base implementation reads a `bytes` object and copies it in; `BufferedReader` and `BytesIO` fill your buffer directly, O(1) space |
| `BufferedIOBase.write(b)`, `BufferedWriter.write(b)` | O(k) amortized | O(b) | Copies into the buffer and writes it out when it fills, so a run of small writes costs one raw write per `b` bytes |
| `BufferedWriter.flush()` | O(b) | O(1) | Writes out at most one buffer |
| `BufferedIOBase.detach()` | O(1) | O(1) | Returns the raw stream and leaves this object unusable |
| `BufferedIOBase.raw` | O(1) | O(1) | The underlying raw stream |

### TextIOBase and TextIOWrapper

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.TextIOBase` | O(1) | O(1) | Streams of `str`; `StringIO` and `TextIOWrapper` implement it |
| `io.TextIOWrapper(buffer, encoding=None, errors=None, newline=None, line_buffering=False, write_through=False)` | O(1) | O(1) | What `open()` returns in text mode |
| `TextIOBase.read(size=-1)` | O(k) | O(k) | Decodes what it returns; `size=-1` decodes the rest of the stream |
| `TextIOBase.readline(size=-1)`, iterating | O(k) | O(k) | Decodes the binary buffer a chunk at a time |
| `TextIOBase.write(s)` | O(k) | O(k) | Encodes and hands the bytes to the binary buffer; `line_buffering` flushes on a newline, `write_through` hands them on at once |
| `TextIOWrapper.tell()` | O(c) | O(c) | Re-decodes the last chunk to find the byte position; O(1) after `read()` to the end, a `seek()` or a write. Raises `OSError` inside a `for` loop over the stream |
| `TextIOWrapper.seek(cookie, whence=os.SEEK_SET)` | O(1) | O(1) | Takes 0 or a value `tell()` returned; relative seeks only by 0 |
| `TextIOWrapper.reconfigure(*, encoding=None, errors=None, newline=None, line_buffering=None, write_through=None)` | O(1) | O(1) | |
| `TextIOBase.detach()` | O(1) | O(1) | Flushes, returns the binary buffer, and leaves this object unusable |
| `TextIOBase.buffer`, `TextIOBase.encoding`, `TextIOBase.errors`, `TextIOBase.newlines` | O(1) | O(1) | `newlines` lists the line endings translated so far when `newline=None` |
| `TextIOWrapper.line_buffering`, `TextIOWrapper.write_through` | O(1) | O(1) | Set at construction or by `reconfigure()` |
| `io.IncrementalNewlineDecoder(decoder, translate, errors='strict')` | O(1) | O(1) | `decode(input, final=False)` is O(k); the universal-newline translator that text streams use |

### StringIO

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.StringIO(initial_value='', newline='\n')` | O(n) | O(n) | Copies the initial value |
| `StringIO.write(s)` | O(k) amortized | O(k) | After a run of appends, the first `readline()`, partial `read()`, `truncate()` or write away from the end converts the buffer once, O(n) time and space |
| `StringIO.read(size=-1)`, `StringIO.readline(size=-1)` | O(k) | O(k) | |
| `StringIO.getvalue()` | O(n) | O(n) | |
| `StringIO.seek(pos, whence=os.SEEK_SET)`, `StringIO.tell()` | O(1) | O(1) | Positions are characters; relative seeks only by 0, as for any text stream |
| `StringIO.truncate(size=None)` | O(n) | O(n) | |

### BytesIO

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.BytesIO(initial_bytes=b'')` | O(1) | O(1) | Shares a `bytes` argument instead of copying it; any other buffer is copied, O(n) |
| `BytesIO.write(b)` | O(k) amortized | O(k) | A write to a stream that shares its bytes copies them first, O(n) |
| `BytesIO.read(size=-1)`, `BytesIO.read1(size=-1)`, `BytesIO.readline(size=-1)` | O(k) | O(k) | |
| `BytesIO.readinto(b)` | O(k) | O(1) | |
| `BytesIO.getvalue()` | O(1) | O(1) | Returns the stream's own `bytes` object, which the stream then shares; O(n) while a `getbuffer()` view is open |
| `BytesIO.getbuffer()` | O(1) | O(1) | A writable view of the contents, O(n) if the stream shares its bytes; the stream refuses writes until every view is released |
| `BytesIO.seek(pos, whence=os.SEEK_SET)`, `BytesIO.tell()` | O(1) | O(1) | |
| `BytesIO.truncate(size=None)` | O(n) | O(n) | |

### Reader and Writer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.Reader`, `Reader.read(size=..., /)` | O(1) | O(1) | Python 3.14+; `isinstance(f, io.Reader)` checks for a `read` method, so any file object passes |
| `io.Writer`, `Writer.write(data, /)` | O(1) | O(1) | Python 3.14+; the same check for `write` |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `io.SEEK_SET`, `io.SEEK_CUR`, `io.SEEK_END` | O(1) | O(1) | The `whence` values 0, 1 and 2 |
| `io.UnsupportedOperation` | O(1) | O(1) | Subclass of both `OSError` and `ValueError`; raised by a call the stream does not support |
| `io.BlockingIOError` | O(1) | O(1) | The builtin `BlockingIOError`, raised by a non-blocking stream that would block |

## Choosing a Layer

### Buffered vs Raw Reads

A raw stream makes a system call for every call you make on it. The buffered layer reads `b`
bytes at a time and serves small reads from memory, so a loop of one-byte reads costs one raw
read per buffer instead of one per byte. `readline()` on a raw stream is worse still: with no
`peek()` to look ahead, it reads one byte at a time.

```python
import io

class CountingRaw(io.RawIOBase):
    """An in-memory raw stream that counts the reads made on it."""

    def __init__(self, data):
        self.data, self.pos, self.reads = data, 0, 0

    def readable(self):
        return True

    def readinto(self, buffer):
        self.reads += 1
        chunk = self.data[self.pos:self.pos + len(buffer)]
        buffer[:len(chunk)] = chunk
        self.pos += len(chunk)
        return len(chunk)

line = b"x" * 9_999 + b"\n"

raw = CountingRaw(line)
assert raw.readline() == line  # O(k) calls - one per byte
assert raw.reads == 10_000

raw = CountingRaw(line)
buffered = io.BufferedReader(raw, buffer_size=4096)  # O(b) space
assert buffered.readline() == line  # O(k) - one raw read per 4,096 bytes
assert raw.reads <= 4

raw = CountingRaw(line)
buffered = io.BufferedReader(raw, buffer_size=4096)
while buffered.read(1):  # O(1) amortized, from the buffer
    pass
assert raw.reads <= 4
```

### Buffered Writes

A buffered writer copies into its buffer and writes it out when it fills. Many small writes cost
a few large raw writes, and nothing reaches the raw stream until the buffer fills or you flush.

```python
import io

class CountingSink(io.RawIOBase):
    def __init__(self):
        self.writes, self.data = 0, bytearray()

    def writable(self):
        return True

    def write(self, b):
        self.writes += 1
        self.data += b
        return len(b)

sink = CountingSink()
writer = io.BufferedWriter(sink, buffer_size=4096)

for _ in range(10_000):
    writer.write(b"x")  # O(1) amortized - a copy into the buffer
assert sink.writes <= 3

writer.flush()  # O(b) - writes out what is left
assert bytes(sink.data) == b"x" * 10_000
```

### What open() Builds

`open()` stacks the layers for you, and its arguments decide how many. `buffering=0` stops at the
raw `FileIO`; binary mode stops at the buffered layer; text mode adds a `TextIOWrapper`.

```python
import io
import os
import tempfile

fd, path = tempfile.mkstemp()
os.close(fd)
try:
    with open(path, "w", encoding="utf-8") as f:  # O(1), O(b) for the buffer
        assert isinstance(f, io.TextIOWrapper)
        assert isinstance(f.buffer, io.BufferedWriter)
        assert isinstance(f.buffer.raw, io.FileIO)
        f.write("hello\n")  # O(k)

    with open(path, "rb") as f:
        assert isinstance(f, io.BufferedReader)
        assert f.peek(1).startswith(b"h")  # O(b) - consumes nothing
        assert f.read() == b"hello\n"  # O(n)

    with open(path, "rb", buffering=0) as f:
        assert isinstance(f, io.FileIO)
        assert f.read(5) == b"hello"  # O(k) - one system call
finally:
    os.remove(path)
```

## In-Memory Streams

### Building Text With StringIO

`StringIO.write()` appends in amortized O(k), so building a string of n characters is O(n)
however many pieces it takes. `str.join()` over a list does the same. Repeated `+=` on a `str`
has no such guarantee: CPython can extend the string in place when nothing else refers to it,
but once another reference exists every `+=` copies what came before, and the loop is O(n²).

```python
import io

buffer = io.StringIO()
for index in range(1_000):
    buffer.write(f"row {index}\n")  # O(k) amortized

text = buffer.getvalue()  # O(n)
assert text.count("\n") == 1_000
assert text == "".join(f"row {index}\n" for index in range(1_000))
```

### BytesIO Shares Its Bytes

`BytesIO` built from a `bytes` object keeps that object instead of copying it, and `getvalue()`
hands its own object back. The copy is paid only when a write would change bytes that something
else still refers to. `getbuffer()` gives a view that writes in place; while one is open the
stream refuses `write()`, `truncate()` and `close()`.

```python
import io

data = b"x" * 100_000

stream = io.BytesIO(data)  # O(1) - no copy
assert stream.getvalue() is data  # O(1)

stream.write(b"y")  # O(n) once - `data` is still referenced, so it is copied first
assert data[0:1] == b"x"
assert stream.getvalue()[0:1] == b"y"

view = stream.getbuffer()  # O(1)
view[0] = ord("z")  # writes into the stream
try:
    stream.write(b"z")
except BufferError as error:
    assert "cannot be re-sized" in str(error)
else:
    raise AssertionError("a BytesIO was written while a view was open")
view.release()
assert stream.getvalue().startswith(b"zx")
```

## Text Streams

### tell() and seek()

A text stream's position is not a character count. `tell()` returns an opaque cookie, and to
build it the wrapper re-decodes the chunk it last read: O(c). Handing the cookie back to `seek()`
is O(1). `seek()` takes only such a cookie, 0, or a relative seek of 0. `tell()` is refused
while a `for` loop is iterating the stream; call `readline()` in a loop where you need positions.

```python
import io
import os

raw = io.BytesIO("naïve\ncafé\nüber\n".encode("utf-8"))
text = io.TextIOWrapper(raw, encoding="utf-8")

assert text.readline() == "naïve\n"  # O(k)
cookie = text.tell()  # O(c) - re-decodes the chunk it read
assert text.readline() == "café\n"

text.seek(cookie)  # O(1)
assert text.readline() == "café\n"

text.seek(0, os.SEEK_END)  # O(1)
try:
    text.seek(-3, os.SEEK_CUR)
except io.UnsupportedOperation as error:
    assert "nonzero" in str(error)
else:
    raise AssertionError("a text stream seeked by a character count")

text.seek(0)  # O(1)
try:
    for line in text:
        text.tell()
except OSError as error:
    assert "next() call" in str(error)
else:
    raise AssertionError("tell() worked inside a for loop")
```

### Universal Newlines

With `newline=None`, the default for `open()`, a text stream translates `\r\n` and `\r` to `\n`
as it decodes and records which endings it met in `newlines`.

```python
import io

raw = io.BytesIO(b"one\r\ntwo\rthree\n")
text = io.TextIOWrapper(raw, encoding="ascii", newline=None)

assert text.read() == "one\ntwo\nthree\n"  # O(n)
assert set(text.newlines) == {"\r\n", "\r", "\n"}

decoder = io.IncrementalNewlineDecoder(None, translate=True)
assert decoder.decode("a\r") == "a"  # O(k) - holds the \r in case \n follows
assert decoder.decode("\nb", final=True) == "\nb"
```

## Common Patterns

### Copying in Fixed-Size Chunks

`readinto()` fills a buffer you allocated once, so copying a stream of any size holds one chunk.

```python
import io

source = io.BytesIO(bytes(range(256)) * 1_000)
target = io.BytesIO()

chunk = bytearray(16_384)
view = memoryview(chunk)
while count := source.readinto(chunk):  # O(k) - no new bytes object
    target.write(view[:count])  # O(k) amortized

assert target.getvalue() == source.getvalue()
```

### Decoding a Binary Stream

A `TextIOWrapper` turns any binary stream into lines of text without reading it all first, the
way `open()` does for files.

```python
import io

payload = io.BytesIO("name,city\nAlice,Zürich\nBob,Oslo\n".encode("utf-8"))

with io.TextIOWrapper(payload, encoding="utf-8") as lines:  # O(1)
    header = next(lines)  # O(k)
    rows = [line.rstrip("\n").split(",") for line in lines]  # O(k) per line

assert header == "name,city\n"
assert rows == [["Alice", "Zürich"], ["Bob", "Oslo"]]
```

## Performance Best Practices

✅ **Do**:

- Keep the default buffering: a run of small reads or writes costs one system call per buffer
- Iterate a file for lines instead of `readlines()`, so memory follows the line, not the file
- Read large binary data with `readinto()` and one reused buffer
- Build text with `StringIO` or `str.join()`, and call `getvalue()` once at the end
- Hand `BytesIO` a `bytes` object rather than a `bytearray`: it is shared, not copied
- Treat `tell()` on a text file as a cookie for `seek()`, not an offset to do arithmetic on

❌ **Avoid**:

- `readline()` on an unbuffered (`buffering=0`) file - one system call per byte
- `getvalue()` inside a loop - each `StringIO` call is O(n)
- `tell()` after every line of a large text file when you do not need to come back
- Holding on to a `BytesIO.getvalue()` result while you keep writing - the next write copies

## Version Notes

- **Python 3.10+**: Added `io.text_encoding()` and `EncodingWarning`
- **Python 3.14+**: Added `io.Reader` and `io.Writer`
- **Python 3.14+**: `DEFAULT_BUFFER_SIZE` is 128 KiB, and `open()` buffers by the larger of it and
  the file's block size, counting at most 8 MiB of the block size; earlier versions use 8 KiB,
  and `open()` the block size when the file reports one

## Related Modules

- **[open](../builtins/open.md)** - the builtin that builds these stacks
- **[mmap](mmap.md)** - maps a file into memory for random access without reads
- **[shutil](shutil.md)** - `copyfileobj()` for chunked copying between streams
- **[tempfile](tempfile.md)** - `SpooledTemporaryFile` keeps data in a `BytesIO` until it grows
- **[codecs](codecs.md)** - the incremental decoders a `TextIOWrapper` uses
- **[csv](csv.md)** - reads and writes text streams, including `StringIO`
