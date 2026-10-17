# open() Function Complexity

The `open()` function opens a file and returns a file object: a raw `FileIO`, wrapped in a buffered
reader or writer unless `buffering=0`, wrapped in turn in a `TextIOWrapper` in text mode. Opening
reads nothing, so its cost does not depend on the file's size. Reads and writes cost what they move,
and `read()` with no size and `readlines()` return the rest of the file at once.

`n` is the bytes in the file, or its characters in text mode, `k` is the bytes or characters one
call reads or writes (for `readline()` and line iteration, the length of the line), and `b` is the
buffer size. A system call is priced at the bytes it moves, and text encoding and decoding at O(1)
per character, for a codec whose state clears between characters as UTF-8's does. The filesystem's
own costs, such as resolving the path or freeing blocks when `'w'` truncates a file, are not priced.
Buffered reads and writes are amortized: a call that refills the buffer or writes it out pays up to
O(b) more, once per `b` bytes. Space for reads and writes is in addition to the buffer `open()`
allocates.

## Complexity Reference

### open

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `open(file, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None)` | O(1) | O(b) | Reads nothing from the file; allocates one buffer of `b` bytes, which `buffering` sets |
| `open(file, 'rb', buffering=0)` | O(1) | O(1) | Unbuffered binary only: returns the `FileIO`, so each sized read or write is at most one system call. Text mode raises `ValueError` |
| `open(file, 'w', buffering=1)` | O(1) | O(b) | Line buffering, text mode only: each write containing a newline is flushed |

### Reading

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `f.read()` | O(n) | O(n) | Everything from the current position to the end |
| `f.read(size)` | O(k) amortized | O(size) | Allocates for `size` before it knows how much is left; for a positive `size`, an empty result means end of file |
| `f.readline()` | O(k) amortized | O(k) | On a `buffering=0` file, one system call per byte |
| `f.readlines()` | O(n) | O(n) | Every remaining line at once |
| `for line in f` | O(n) | O(k) | One line at a time; k = the longest line |

### Writing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `f.write(data)` | O(k) amortized | O(k) | Buffered: reaches the file when a write no longer fits in the buffer, or on `flush()` or `close()` |
| `f.writelines(lines)` | O(n) | O(k) | n = total length of `lines`, k = the longest item; one `write()` per item, adding no newlines |
| `f.flush()` | O(b) | O(1) | Writes out what the buffer holds |
| `f.close()`, leaving a `with` block | O(b) | O(1) | Flushes, then closes the file |

### Positioning and attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `f.seek(offset, whence=0)`, binary mode | O(1) | O(1) | Plus O(b) to flush pending writes; the next read costs what it moves |
| `f.tell()`, binary mode | O(1) | O(1) | |
| `f.tell()`, text mode | O(c) | O(c) | c = bytes decoded in the last chunk, plus O(b) to flush pending writes; raises `OSError` inside a `for` loop over the file |
| `f.seek(cookie)`, text mode | O(1) | O(1) | Plus O(b) to flush pending writes; takes a value from `tell()`, `0`, or `seek(0, 2)` for the end |
| `f.truncate(size=None)` | O(b) | O(1) | Flushes first |
| `f.name`, `f.mode`, `f.closed`, `f.encoding`, `f.readable()`, `f.writable()`, `f.seekable()` | O(1) | O(1) | `encoding` exists in text mode only |

## Opening Files

### What open() Returns

The mode decides how many layers `open()` stacks. Building them is O(1) whatever the file holds.

```python
import io
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "data.txt")

    with open(path, "w", encoding="utf-8") as f:  # O(1) - creates or truncates
        assert isinstance(f, io.TextIOWrapper)
        f.write("hello\n")

    with open(path, "rb") as f:  # O(1)
        assert isinstance(f, io.BufferedReader)

    with open(path, "r+b") as f:
        assert isinstance(f, io.BufferedRandom)

    with open(path, "rb", buffering=0) as f:
        assert isinstance(f, io.FileIO)  # No buffer: each sized read is one system call
```

### Modes

`'w'` empties an existing file, `'a'` sends every write to the end, and `'x'` refuses to open a file
that already exists.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "log.txt")

    with open(path, "w", encoding="utf-8") as f:
        f.write("first\n")

    with open(path, "a", encoding="utf-8") as f:
        f.seek(0)
        f.write("second\n")  # Appended, even after seek(0)

    with open(path, encoding="utf-8") as f:
        assert f.read() == "first\nsecond\n"

    try:
        open(path, "x")
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")
```

### Text Encoding

Text mode decodes on read and encodes on write. Without `encoding=`, Python 3.15+ uses UTF-8 unless UTF-8
mode is turned off, and earlier versions use the locale's encoding unless UTF-8 mode is on. Pass `encoding=` for a file
that has to read the same everywhere.

```python
import locale
import os
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "notes.txt")

    with open(path, "w", encoding="utf-8") as f:
        f.write("naïve café")
        assert f.encoding == "utf-8"

    with open(path, "rb") as f:
        assert f.read() == "naïve café".encode("utf-8")  # 2 bytes for each of ï and é

    with open(path) as f:  # The default depends on the version and UTF-8 mode
        assert f.encoding == ("utf-8" if sys.flags.utf8_mode else locale.getencoding())
```

## Reading Files

### Lazy vs Eager Reading

Iterating a file holds one line at a time. `readlines()` and `read()` build the whole file in
memory, which is O(n) space.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "lines.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(f"line {i}\n" for i in range(1_000))  # O(n)

    # LAZY: O(k) memory - one line at a time
    count = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            count += 1
    assert count == 1_000

    # EAGER: O(n) memory - every line in one list
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1_000 and lines[0] == "line 0\n"
```

### Reading in Fixed-Size Chunks

A binary file with no line structure can be read a chunk at a time with `iter()` and a sentinel, so
memory stays at one chunk.

```python
import hashlib
import os
import tempfile
from functools import partial

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "blob.bin")
    with open(path, "wb") as f:
        f.write(bytes(range(256)) * 1_000)

    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(partial(f.read, 65_536), b""):  # O(k) memory per chunk
            digest.update(chunk)

    assert digest.hexdigest() == hashlib.sha256(bytes(range(256)) * 1_000).hexdigest()
```

## Writing Files

### Buffered Writes

A write lands in the buffer, and the file sees it when a later write no longer fits, or on
`flush()` or `close()`, so a run of small writes costs few system calls. An unbuffered binary file makes one
system call per write.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "out.bin")

    with open(path, "wb") as f:
        for _ in range(100):
            f.write(b"x")  # O(1) amortized - copied into the buffer
        assert os.path.getsize(path) == 0  # Nothing written to the file yet
        f.flush()  # O(b)
        assert os.path.getsize(path) == 100

    with open(path, "wb", buffering=0) as f:
        f.write(b"x")  # One system call
        assert os.path.getsize(path) == 1
```

### Buffering Modes

`buffering=0` is for binary files only. `buffering=1` makes a text file flush at each newline,
which suits a log another process is reading.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "app.log")

    with open(path, "w", buffering=1, encoding="utf-8", newline="\n") as f:
        f.write("starting")
        assert os.path.getsize(path) == 0
        f.write(" ... done\n")  # Contains a newline: flushed
        assert os.path.getsize(path) == len("starting ... done\n")

    try:
        open(path, "w", buffering=0)
    except ValueError as error:
        assert "unbuffered text" in str(error)
    else:
        raise AssertionError("expected ValueError")
```

## Positioning

### Binary Seek and Tell

In binary mode a position is a byte offset, and moving to it is O(1) however far it is.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "records.bin")
    with open(path, "wb") as f:
        f.write(b"".join(i.to_bytes(4, "big") for i in range(10_000)))

    with open(path, "rb") as f:
        f.seek(4 * 9_000)  # O(1) - no reading on the way
        assert int.from_bytes(f.read(4), "big") == 9_000  # O(k)
        assert f.tell() == 4 * 9_001  # O(1)

        f.seek(0, os.SEEK_END)  # O(1)
        assert f.tell() == 40_000  # The file's size
```

### Text Seek and Tell

A text file's position is an opaque cookie, not a character count. `tell()` re-decodes the last
chunk to build it, and `seek()` accepts only such a cookie, `0`, or the end. The
[io page](../stdlib/io.md#tell-and-seek) covers the details.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "text.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("naïve\ncafé\n")

    with open(path, encoding="utf-8") as f:
        assert f.readline() == "naïve\n"
        cookie = f.tell()  # O(c)
        assert f.readline() == "café\n"
        f.seek(cookie)  # O(1)
        assert f.readline() == "café\n"

        try:
            f.seek(3, os.SEEK_CUR)
        except OSError as error:
            assert "nonzero" in str(error)
        else:
            raise AssertionError("seeked a text file by a character count")
```

## Common Patterns

### Handling a Missing File

`open()` raises before anything is read.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    try:
        with open(os.path.join(tmp, "missing.txt"), encoding="utf-8") as f:
            f.read()
    except FileNotFoundError as error:
        assert error.filename.endswith("missing.txt")
    else:
        raise AssertionError("expected FileNotFoundError")
```

### Read, Transform, Write

Iterating one file while writing another holds one line from each, whatever the files' sizes.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    source = os.path.join(tmp, "in.txt")
    target = os.path.join(tmp, "out.txt")
    with open(source, "w", encoding="utf-8") as f:
        f.write("alpha\nbeta\ngamma\n")

    with open(source, encoding="utf-8") as src, open(target, "w", encoding="utf-8") as dst:
        for line in src:  # O(n) time, O(k) memory
            dst.write(line.upper())

    with open(target, encoding="utf-8") as f:
        assert f.read() == "ALPHA\nBETA\nGAMMA\n"
```

## Performance Best Practices

✅ **Do**:

- Use `with` so the file is flushed and closed even when an exception is raised
- Iterate a file, or read it in fixed-size chunks, when it can be larger than you want in memory
- Pass `encoding=` in text mode; the default differs between versions and platforms
- Keep the default buffering for runs of small reads and writes

❌ **Avoid**:

- `readlines()` or `read()` on a file that may be large, when you only need one line at a time
- `readline()` on a `buffering=0` file; it makes one system call per byte
- `buffering=0` for many small writes; each one is a system call
- Seeking a text file to a computed character offset; use a cookie from `tell()`, or binary mode

## Version Notes

- **Python 3.15+**: Text mode defaults to UTF-8 when `encoding` is omitted, whatever the locale,
  unless UTF-8 mode is turned off; earlier versions use the locale's encoding unless UTF-8 mode is on

## Related Functions

- **[io](../stdlib/io.md)** - the classes `open()` builds, and what each layer costs
- **[pathlib](../stdlib/pathlib.md)** - `Path.open()`, `read_text()` and `write_text()`
- **[shutil](../stdlib/shutil.md)** - `copyfileobj()` for copying between files in chunks
- **[iter()](iter.md)** - `iter(callable, sentinel)` for chunked reads
