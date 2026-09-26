# mmap Module Complexity

The `mmap` module maps a file, or anonymous memory, into the process's address space and exposes
it as a fixed-length byte buffer with a file-like position. By default mapping reads nothing: the
first access to each page faults it in, from the page cache or the disk for a file and as zeros
for anonymous memory, so the cost follows the bytes you touch rather than the length you map.

`n` is the length of the mapping in bytes, `k` is the bytes a call returns, writes or copies,
`l` is the bytes `readline()` returns, `r` is the bytes in a searched range, `s` is the length of
the needle, and `p` is the pages of the mapping the process has touched. Bounds count bytes and
pages in memory; a first touch adds one page fault per page, and reading a page from disk costs
whatever the storage costs, which no row here prices. System calls that take no length, such as
`fstat()`, are priced O(1).

## Complexity Reference

### mmap

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mmap.mmap(fileno, length, flags=MAP_SHARED, prot=PROT_WRITE\|PROT_READ, access=ACCESS_DEFAULT, offset=0, *, trackfd=True)` | O(1) | O(1) | Unix. Touches no page, whatever the length, unless `flags` include `MAP_POPULATE`. `length=0` maps the whole file; a `length` past the end of the file raises `ValueError`. On macOS the file is first flushed to storage |
| `mmap.mmap(fileno, length, tagname=None, access=ACCESS_DEFAULT, offset=0)` | O(1) | O(1) | Windows. A `length` past the end of the file grows the file; `tagname` names the mapping so another map can share it |
| `mmap.mmap(-1, length)` | O(1) | O(1) | Anonymous memory, zero-filled a page at a time as it is touched |
| `mmap.close()`, leaving `with mmap.mmap(...)` | O(p) | O(1) | Unmaps every touched page; the file stays open. Raises `BufferError` while a buffer is exported |
| `mmap.closed` | O(1) | O(1) | |

### Reading and writing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mmap.read([n])` | O(k) | O(k) | k = bytes returned, at most `n`; with no `n`, to the end. A new `bytes` copy |
| `mmap.read_byte()` | O(1) | O(1) | Returns an `int` |
| `mmap.readline()` | O(l) | O(l) | Stops at the first `\n` after the position; the rest of the mapping is not scanned |
| `mmap.write(bytes)` | O(k) | O(1) | Copies in place. The mapping never grows: data that does not fit raises `ValueError` and writes nothing |
| `mmap.write_byte(byte)` | O(1) | O(1) | |
| `mmap.move(dest, src, count)` | O(k) | O(1) | k = `count`; overlapping ranges are safe |
| `mmap.seek(pos[, whence])` | O(1) | O(1) | Returns the new position on Python 3.13+, `None` before |
| `mmap.tell()` | O(1) | O(1) | |
| `mmap.seekable()` | O(1) | O(1) | Always `True`; Python 3.13+ |
| `mm[i]`, `mm[i] = value` | O(1) | O(1) | An `int` in and out |
| `mm[i:j]`, `mm[i:j:step]` | O(k) | O(k) | k = slice length; a new `bytes` copy |
| `mm[i:j] = data` | O(k) | O(1) | `data` must be exactly the slice's length |
| `len(mm)` | O(1) | O(1) | The mapped length, not the file size |
| `memoryview(mm)` | O(1) | O(1) | No copy; `close()` and `resize()` raise `BufferError` until every view is released |
| Iterating an `mmap`, `x in mm` | O(n) | O(1) | Yields one-byte `bytes` objects, so `in` finds a single byte and is `False` for any longer needle; use `find()` |

### Searching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mmap.find(sub[, start[, end]])` | O(r + s) | O(1) | O(r·s) worst case on Python 3.10. Without `start`, searches from the current position, which it does not move |
| `mmap.rfind(sub[, start[, end]])` | O(r·s) worst | O(1) | O(r) on typical input; the same start rule as `find()` |

### Size, resizing and flushing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mmap.size()` | O(1) | O(1) | The size of the file, which can exceed `len(mm)`. On Unix, raises `OSError` for anonymous memory and for a map built with `trackfd=False` |
| `mmap.resize(newsize)` | O(p) | O(1) | Linux remaps without copying the bytes and resizes a mapped file to match. Windows copies anonymous memory, O(min(n, newsize)). Unix without `mremap()`, macOS included, raises `SystemError`. Linux cannot grow shared anonymous memory: Python 3.13+ raises `ValueError`, and earlier versions crash with `SIGBUS` when the new pages are touched |
| `mmap.flush([offset[, size]])` | O(p) | O(1) | Writes the dirty pages in the range back to the file; on Unix it waits for the writes. Does nothing for `ACCESS_READ` and `ACCESS_COPY` |
| `mmap.madvise(option[, start[, length]])` | O(q) | O(1) | q = pages in the advised range; what the kernel does with them depends on `option`. Unix only |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mmap.ACCESS_READ`, `mmap.ACCESS_WRITE`, `mmap.ACCESS_COPY`, `mmap.ACCESS_DEFAULT` | O(1) | O(1) | `ACCESS_COPY` is copy-on-write: writes change memory, never the file |
| `mmap.PAGESIZE`, `mmap.ALLOCATIONGRANULARITY` | O(1) | O(1) | `offset` must be a multiple of `ALLOCATIONGRANULARITY`, which equals `PAGESIZE` on Unix |
| `mmap.MAP_SHARED`, `mmap.MAP_PRIVATE`, `mmap.MAP_ANONYMOUS`, `mmap.MAP_POPULATE`, other `MAP_*` flags | O(1) | O(1) | Unix; the set depends on the OS. `MAP_POPULATE` (Linux) faults in every page at construction, making it O(n) |
| `mmap.PROT_READ`, `mmap.PROT_WRITE`, `mmap.PROT_EXEC` | O(1) | O(1) | Unix |
| `mmap.MADV_NORMAL`, `mmap.MADV_SEQUENTIAL`, `mmap.MADV_WILLNEED`, `mmap.MADV_DONTNEED`, other `MADV_*` options | O(1) | O(1) | Unix; the set depends on the OS |
| `mmap.error` | O(1) | O(1) | Another name for `OSError` |

## Mapping a File

Building the map costs a fixed number of system calls whatever the file's length: no byte is read
until you touch it. The mapped length is fixed for the life of the object, and `size()` asks the file, not the
map.

```python
import mmap
import tempfile

with tempfile.TemporaryFile() as f:
    f.write(b'0123456789' * 1000)
    f.flush()

    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:  # O(1) - reads nothing
        assert len(mm) == 10_000  # O(1)
        assert mm.size() == 10_000  # O(1) - asks the file
        assert mm[0] == ord('0')  # O(1) - the first touch faults one page in

    assert mm.closed  # leaving the block closed the map, not the file
    assert not f.closed
```

### Anonymous Memory

Passing `-1` as the file descriptor maps zero-filled memory with no file behind it. It is still a
fixed-length buffer, and on Unix `size()` has no file to ask.

```python
import mmap
import sys

with mmap.mmap(-1, 4 * mmap.PAGESIZE) as mm:  # O(1) - no page is touched yet
    assert mm[:4] == b'\x00\x00\x00\x00'  # O(k)
    mm.write(b'hello')  # O(k)
    assert mm[:5] == b'hello'

    if sys.platform != 'win32':
        try:
            mm.size()
        except OSError:
            pass
        else:
            raise AssertionError('an anonymous map reported a file size')
```

## Reading and Writing

`read()`, `readline()` and slicing copy the bytes they return into a new `bytes` object; the first
two advance the position and slicing leaves it alone. `readline()` stops at the next newline, so reading a line near
the start of a large mapping costs that line, not the mapping. `write()` copies in place and can
never grow the mapping.

```python
import mmap

with mmap.mmap(-1, 64) as mm:
    mm.write(b'first line\nsecond line\n')  # O(k)
    mm.seek(0)  # O(1)

    assert mm.readline() == b'first line\n'  # O(l)
    assert mm.tell() == 11  # O(1)
    assert mm.read(6) == b'second'  # O(k)
    assert mm.read_byte() == ord(' ')  # O(1)

    assert mm[0:6] == b'first ' and mm.tell() == 18  # O(k) - slicing leaves the position
    mm[0:5] = b'FIRST'  # O(k) - same length only
    mm.move(32, 0, 5)  # O(k) - copies within the map
    assert mm[32:37] == b'FIRST'

    mm.seek(60)
    try:
        mm.write(b'too long')  # 8 bytes into the last 4
    except ValueError as error:
        assert 'out of range' in str(error)
    else:
        raise AssertionError('a write past the end succeeded')
    assert mm[60:] == b'\x00\x00\x00\x00'  # nothing was written
```

### Slices Copy, Views Share

A slice is a new `bytes` object, so it costs its length in time and memory. A `memoryview` over
the map is the same memory: making it and slicing it copy nothing, and a write through the map
shows through the view. While any view is alive the map cannot close or resize.

```python
import mmap

mm = mmap.mmap(-1, mmap.PAGESIZE)
copy = mm[0:4]  # O(k) - a copy
view = memoryview(mm)[0:4]  # O(1) - no copy

mm[0] = 0xFF  # O(1)
assert copy == b'\x00\x00\x00\x00'
assert view[0] == 0xFF  # the same memory

try:
    mm.close()
except BufferError as error:
    assert 'exported' in str(error)
else:
    raise AssertionError('the map closed under a live view')

view.release()
mm.close()  # O(p)
assert mm.closed
```

## Searching

`find()` and `rfind()` search the mapped bytes where they are, on Python 3.11+ with the same
algorithms as `bytes.find()` and `bytes.rfind()`. Without a `start` they begin at the current
position, not at zero. `x in mm` is not a substring test: iteration yields one byte at a time, so
it walks the mapping byte by byte and matches only a single byte. The `re` module accepts a map directly and scans it
without copying.

```python
import mmap
import re

with mmap.mmap(-1, 4096) as mm:
    mm.write(b'header;needle;tail;needle')  # the position is now 25

    assert mm.find(b'needle') == -1  # O(r + s) - from the position, which is at the end
    assert mm.find(b'needle', 0) == 7  # O(r + s)
    assert mm.rfind(b'needle', 0) == 19  # O(r·s) worst, O(r) here
    assert mm.tell() == 25  # searching does not move the position

    assert b'n' in mm  # O(n) - one byte at a time
    assert b'needle' not in mm  # a longer needle never matches

    match = re.search(rb'need(le)', mm)  # O(n) - scans the map in place
    assert match is not None and match.start() == 7
```

## Resizing and Flushing

`resize()` changes the mapping and, for a file, the file's length. On Linux it remaps the pages
rather than copying their bytes; on Unix systems without `mremap()`, macOS among them, it raises
`SystemError`, so portable code closes the map, resizes the file, and maps it again. On Linux,
shared anonymous memory cannot grow at all. `flush()` writes the dirty pages in a range back to
the file, and on Unix waits for them; a copy-on-write map never reaches the file, so flushing it
does nothing.

```python
import mmap
import os
import sys
import tempfile

with tempfile.TemporaryFile() as f:
    f.write(b'abcd' * 1024)
    f.flush()

    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_COPY) as private:
        private[0:4] = b'WXYZ'  # O(k) - changes memory only
        private.flush()  # does nothing for ACCESS_COPY
    assert os.pread(f.fileno(), 4, 0) == b'abcd'

    with mmap.mmap(f.fileno(), 0) as shared:
        shared[0:4] = b'WXYZ'  # O(k)
        shared.flush()  # O(p) - writes the dirty page back
        assert os.pread(f.fileno(), 4, 0) == b'WXYZ'

        if sys.platform == 'linux':
            shared.resize(8192)  # O(p) - no copy of the bytes
            assert len(shared) == 8192 and os.fstat(f.fileno()).st_size == 8192
            assert shared[0:4] == b'WXYZ'
```

## Common Patterns

### Scanning a Large File for Records

Walking a mapped file with `find()` scans it in place: memory holds the slices you take, never a
copy of the file.

```python
import mmap
import tempfile

with tempfile.TemporaryFile() as f:
    f.write(b'noise ' * 100_000 + b'ID=42;' + b'noise ' * 100_000 + b'ID=7;')
    f.flush()

    found = []
    with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:  # O(1)
        position = mm.find(b'ID=', 0)  # O(r + s)
        while position != -1:
            end = mm.find(b';', position)  # O(r + s)
            found.append(int(mm[position + 3:end]))  # O(k) - copies one record
            position = mm.find(b'ID=', end)

    assert found == [42, 7]
```

## Performance Best Practices

✅ **Do**:

- Map a large file you read at random offsets: only the pages you touch are faulted in
- Search with `find()`, `rfind()` or `re` on the map itself, rather than reading it into `bytes`
- Pass `start` to `find()` and `rfind()`, or `seek(0)` first; the default is the current position
- Take a `memoryview` when you need a window without a copy, and release it before `close()`
- Use `ACCESS_COPY` for scratch changes that must never reach the file

❌ **Avoid**:

- `x in mm` to look for a byte string - it walks the whole map and matches single bytes only
- `mm[:]` or `read()` on a large map - each is an O(n) copy into memory
- `resize()` in portable code - it raises where the OS has no `mremap()`
- `flush()` after every small write - each call writes back the dirty pages in its range

## Version Notes

- **Python 3.11+**: `find()` uses the same search as `bytes.find()`, so its worst case drops from
  O(r·s) to O(r + s); `rfind()` stays O(r·s) in the worst case
- **Python 3.13+**: Added `seekable()` and the `trackfd` argument; `seek()` returns the new
  position

## Related Modules

- **[io](io.md)** - Buffered file reads, which copy into memory rather than mapping it
- **[os](os.md)** - `os.pread()` and `os.pwrite()` for positioned I/O without a mapping
- **[re](re.md)** - Patterns that scan a map in place
- **[memoryview](../builtins/memoryview_func.md)** - Zero-copy windows over a map
- **[multiprocessing](multiprocessing.md)** - `shared_memory`, a named block shared between processes
