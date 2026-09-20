# bytearray() Function Complexity

The `bytearray()` function builds a mutable sequence of bytes: one resizable buffer, edited in
place. It has the search, split and transform methods of `bytes`, none of which touch the
buffer - the splits and transforms build new objects from it, the searches and predicates only
read it - and the mutators of `list`: `append()`, `extend()`, `insert()`, `pop()`, `remove()`,
`clear()`, `reverse()` and slice assignment.

The buffer is overallocated when it grows, so appending is amortized O(1), and it records where
its contents start, so removing a prefix moves that offset rather than the tail, whether with
`del` or by assigning a shorter slice at the front - which still costs the bytes it copies in.
A change of length anywhere else shifts everything after it. Growing past the buffer copies
the contents into a larger one; so does falling below half of it, which compacts them into a
smaller one. Those are the two places a change of length allocates.

`n` is the bytes in the bytearray, `k` is the bytes in the other operand (the data copied in,
the slice covered, or the items of an iterable), `m` is the bytes in a pattern (`sub`, `prefix`,
`suffix`, `sep`), `p` is the parts handed to `join()`, and `w` is the bytes in the result where
that differs from `n`. An item of an iterable is an `int` in `range(256)`, read at O(1), and
the encoding rows assume a codec and error handler whose cost and output are proportional to
their input, as the byte-oriented codecs are. A structured codec can cost more.

## Complexity Reference

### Construction

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bytearray()` | O(1) | O(1) | Empty, with no buffer allocated |
| `bytearray(count)` | O(n) | O(n) | n = count zero bytes; a negative count raises `ValueError` |
| `bytearray(bytes_like)` | O(k) | O(k) | Copies the buffer of a `bytes`, `bytearray`, `memoryview` or `array.array`; the copy is independent of its source |
| `bytearray(iterable)` | O(k) | O(k) | One byte per item, growing as it goes; an item outside `range(256)` raises `ValueError` |
| `bytearray(string, encoding, errors='strict')` | O(k) | O(k) | Encodes to a `bytes` and copies it in; k = characters in the string, which the encoder walks whatever it emits. A `str` without an encoding raises `TypeError` |
| `bytearray.fromhex(string)` | O(k) | O(k) | k = characters, one byte per pair; whitespace between pairs is skipped. Class method |

### Sequence operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(ba)` | O(1) | O(1) | |
| `ba[i]`, `ba[i] = v` | O(1) | O(1) | An `int` in `range(256)` either way |
| `ba[a:b]`, `ba[a:b:step]` | O(k) | O(k) | A new `bytearray` of the k bytes covered; `memoryview(ba)` is the O(1) alternative |
| `ba[a:b] = data` | O(n + k) | O(k), O(n) when the buffer grows or compacts | O(k) when the slice keeps its length; a change of length shifts the tail, except when it shortens a slice at the front, where the start offset moves instead. `data` is copied to a temporary unless it is another `bytearray` |
| `del ba[i]`, `del ba[a:b]` | O(n) | O(1), O(n) on compaction | Shifts the tail; deleting a prefix advances the start offset instead, amortized O(1) |
| `x in ba` | O(n + m) | O(1) | `x` is an `int` or bytes-like |
| `ba + other` | O(n + k) | O(n + k) | A new `bytearray` |
| `ba += other` | O(k) amortized | O(k) amortized | In place; `other` is any bytes-like |
| `ba * count`, `ba *= count` | O(n·count), O(n) when count ≤ 0 | O(n·count) | The result's length either way; `*=` grows in place, and empties the buffer for a count of 0 or less, releasing it as `clear()` does |
| `ba == other`, `ba != other` | O(n) | O(1) | O(1) when the lengths differ; `<` and the other orderings walk to the first difference |
| `for x in ba` | O(n) | O(1) | One `int` per byte; `iter(ba)` on its own is O(1) |
| `hash(ba)` | O(1) | O(1) | Raises `TypeError`; a bytearray is not hashable |
| `bytes(ba)` | O(n) | O(n) | An immutable copy |
| `memoryview(ba)` | O(1) | O(1) | Shares the buffer and pins its length: any resize raises `BufferError` until the view is released |

### Mutation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `append(x)` | O(1) amortized | O(1) amortized | The buffer overallocates by an eighth when it grows, and the append that grows it allocates the whole new buffer |
| `extend(iterable)` | O(k) amortized | O(k) amortized | A bytes-like operand is copied in one step; any other iterable is gathered into a temporary `bytearray` first |
| `insert(i, x)` | O(n) | O(1) amortized | Shifts the tail |
| `pop()`, `pop(-1)` | O(1) amortized | O(1), O(n) on compaction | The buffer is compacted once the contents fall below half of it, which copies the remainder |
| `pop(i)` | O(n) | O(1), O(n) on compaction | Shifts the tail, including for i = 0; `del ba[0]` does not |
| `remove(x)` | O(n) | O(1), O(n) on compaction | Finds the first occurrence and shifts the tail; `ValueError` when absent |
| `clear()` | O(n) | O(1) | Frees the buffer |
| `copy()` | O(n) | O(n) | |
| `reverse()` | O(n) | O(1) | In place |
| `resize(size)` | O(n + size) | O(size) | Python 3.14+. Added bytes are zeros, and dropped ones are released, so shrinking costs the buffer it gives back; a negative size raises `ValueError` |

### Searching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `find(sub, start, end)`, `index(sub, start, end)` | O(n + m) | O(1) | `sub` is bytes-like or an `int`; `index()` raises `ValueError` when absent |
| `rfind(sub, start, end)`, `rindex(sub, start, end)` | O(n·m) | O(1) | Worst case, absent patterns included: the reverse search has no linear-time fallback, where the forward one does |
| `count(sub, start, end)` | O(n + m) | O(1) | Non-overlapping occurrences |
| `startswith(prefix, start, end)`, `endswith(suffix, start, end)` | O(m + q) | O(1) | Independent of n. Either accepts a tuple of q candidates, and then m is their total length |

### Transforming

Every method here builds a new object, whether or not anything changed; none of them touch the
receiver.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `replace(old, new, count=-1)` | O(n + w) | O(w) | w = result length |
| `translate(table, /, delete=b'')` | O(n + d) | O(n) | `table` is a 256-byte table from `maketrans()`, or `None`; d = bytes in `delete`, each marked in a table before the pass |
| `bytearray.maketrans(from, to)` | O(k) | O(1) | A 256-byte `bytes` whatever k is; the two arguments must be the same length. Static method |
| `upper()`, `lower()`, `capitalize()`, `title()`, `swapcase()` | O(n) | O(n) | ASCII letters only |
| `strip(chars)`, `lstrip(chars)`, `rstrip(chars)` | O(n + (s + 1)·c) | O(n) | s = bytes stripped, c = bytes in `chars`, which is searched once per stripped byte and once more to stop. A copy even when nothing is stripped |
| `removeprefix(prefix)`, `removesuffix(suffix)` | O(n) | O(n) | A copy even when the prefix or suffix is absent |
| `center(width, fillbyte)`, `ljust(width, fillbyte)`, `rjust(width, fillbyte)`, `zfill(width)` | O(w) | O(w) | w = max(n, width): a width below n still copies n bytes |
| `expandtabs(tabsize=8)` | O(n + w) | O(w) | Reads every byte and writes w; a `tabsize` below 1 drops the tabs, so w can be smaller than n |

### Splitting and joining

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `split(sep=None, maxsplit=-1)` | O(n + m) | O(n) | A list of new bytearrays holding at most n bytes between them; separators and skipped whitespace are dropped |
| `splitlines(keepends=False)` | O(n) | O(n) | |
| `partition(sep)` | O(n + m) | O(n) | Three new bytearrays copying all n bytes, hit or miss |
| `rsplit(sep=None, maxsplit=-1)`, `rpartition(sep)` | O(n·m) | O(n) | Worst case: a multi-byte `sep` is searched backwards, with the `rfind()` worst case at each match. `None`, and a one-byte `sep`, scan |
| `join(iterable)` | O(p + w) | O(p + w) | Every part must be bytes-like, and each costs a buffer descriptor whatever its length, so p parts have a cost of their own |

### Predicates and conversion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `isalnum()`, `isalpha()`, `isascii()`, `isdigit()`, `islower()`, `isspace()`, `istitle()`, `isupper()` | O(n) | O(1) | Stop at the first byte that settles the answer |
| `decode(encoding='utf-8', errors='strict')` | O(n) | O(n) | |
| `hex(sep, bytes_per_sep)` | O(n) | O(n) | Two characters per byte |

## Growing a Bytearray

A modest increase overallocates the buffer by about an eighth, and a large one takes exactly
what it asks for, so a run of `append()` or `+=` calls stays linear in the bytes added, however
it is split into calls. Concatenating `bytes` copies the whole accumulated value every time
instead.

```python
import sys

buffer = bytearray()
sizes = set()
for value in range(1000):
    buffer.append(value % 256)  # O(1) amortized
    sizes.add(sys.getsizeof(buffer))

assert len(buffer) == 1000
assert len(sizes) < 50  # the buffer was reallocated a few dozen times, not 1000

buffer += b"tail"  # O(k) amortized - copied onto the end in place
buffer.extend([1, 2, 3])  # O(k) - gathered into a temporary, then copied in
assert buffer[-7:] == bytearray(b"tail\x01\x02\x03")
```

## Removing From the Front

A bytearray records where its contents start inside the buffer. Deleting a prefix with
`del ba[:k]` moves that start rather than the bytes, and the buffer is compacted only once the
remainder falls below half of it, so draining a buffer from the front costs O(n) in total.
`pop(0)` and `insert(0, x)` shift every remaining byte instead, O(n) each.

```python
buffer = bytearray(b"header:payload:trailer")

del buffer[:7]  # O(1) amortized - the start offset advances
assert buffer == bytearray(b"payload:trailer")

first = buffer.pop(0)  # O(n) - every remaining byte shifts left
assert first == ord("p")

buffer.insert(0, ord("P"))  # O(n) - every byte shifts right
assert buffer.startswith(b"Payload")  # O(m)

del buffer[-8:]  # O(1) amortized - nothing after it to shift
assert buffer == bytearray(b"Payload")
```

## Slices Copy, Views Do Not

A slice is a new `bytearray` holding the bytes it covers. A `memoryview` shares the buffer, and
while it is alive the bytearray cannot change length.

```python
data = bytearray(b"abcdefgh")

piece = data[2:5]  # O(k) - a new bytearray of the 3 bytes covered
piece[0] = ord("X")
assert data == bytearray(b"abcdefgh")  # the original is untouched

view = memoryview(data)  # O(1) - shares the buffer
view[0] = ord("A")
assert data[:1] == bytearray(b"A")

try:
    data.append(0)  # the view pins the length
except BufferError as error:
    assert "cannot be re-sized" in str(error)
else:
    raise AssertionError("a bytearray was resized under a live memoryview")

view.release()
data.append(0)  # O(1) amortized again
assert len(data) == 9
```

### Slice Assignment

Replacing a slice with the same number of bytes copies them into place. Replacing it with more
or fewer shifts everything after the slice, unless the shorter one starts at the front: that
moves the start offset instead, as `del` does.

```python
data = bytearray(b"0123456789")

data[2:4] = b"AB"  # O(k) - same length, copied into place
assert data == bytearray(b"01AB456789")

data[2:4] = b"abcd"  # O(n + k) - longer, the tail shifts right
assert data == bytearray(b"01abcd456789")

data[2:6] = b""  # O(n) - shorter, the tail shifts left
assert data == bytearray(b"01456789")

data[:2] = b""  # O(1) - shorter at the front, so the start offset moves
assert data == bytearray(b"456789")
```

## Searching

`find()` is linear even in the worst case. `rfind()` searches backwards with a simpler
algorithm that can compare most of the pattern at every position, and so can cost the pattern's
length at each of the buffer's. `rsplit()` and `rpartition()` search the same way.

```python
haystack = bytearray(b"a" * 10_000)
needle = b"ab" + b"a" * 98  # mismatches only at its second byte

assert haystack.find(needle) == -1  # O(n + m) - linear in the worst case
assert haystack.rfind(needle) == -1  # O(n·m) - m comparisons at each of n positions
assert haystack.count(b"aa") == 5_000  # O(n + m) - non-overlapping
assert haystack.startswith(b"aaa")  # O(m) - the prefix's length, not the buffer's
assert 97 in haystack  # O(n) - an int is a byte value

try:
    haystack.index(b"b")  # O(n + m)
except ValueError as error:
    assert "not found" in str(error)
else:
    raise AssertionError("index() found a byte that is not there")
```

## Transforming Methods Return New Objects

Nothing in the `bytes` method family edits the buffer, and each of the transforming methods
allocates a new `bytearray` of its result, even when that result is identical to the input. So
testing a buffer with `strip()` or `replace()` costs a copy that `startswith()`, `find()` or a
predicate does not.

```python
data = bytearray(b"  Hello  ")

assert data.strip() == bytearray(b"Hello")  # O(n) - a new bytearray
assert data.strip(b"x") is not data  # O(n) - a copy even when nothing is stripped
assert data.replace(b"z", b"y") is not data  # O(n + w) - likewise
assert data.upper() == bytearray(b"  HELLO  ")  # O(n)
assert data.isspace() is False  # O(n) - stops at the first byte that settles it

table = bytearray.maketrans(b"lo", b"01")  # O(k) - always a 256-byte table
assert len(table) == 256
assert data.translate(table, delete=b" ") == bytearray(b"He001")  # O(n)
```

## Common Patterns

### Consuming a Stream Buffer

```python
buffer = bytearray()
chunks = [b"GET / HTTP/1.1\r\nHost: ex", b"ample\r\n\r\nbody"]
lines = []

for chunk in chunks:
    buffer += chunk  # O(k) amortized
    while (end := buffer.find(b"\r\n")) != -1:  # O(n + m)
        lines.append(bytes(buffer[:end]))  # O(k)
        del buffer[: end + 2]  # O(1) amortized - the start offset advances

assert lines == [b"GET / HTTP/1.1", b"Host: example", b""]
assert buffer == bytearray(b"body")
```

### Building a Message

```python
payload = b"payload"

message = bytearray()
message.append(1)  # O(1) amortized - a message type
message += len(payload).to_bytes(2, "big")  # O(k) amortized
message += payload  # O(k) amortized
message.append(0)  # O(1) amortized

assert bytes(message) == b"\x01\x00\x07payload\x00"  # O(n) - freeze it once, at the end
```

## Performance Best Practices

✅ **Do**:

- Build with `append()`, `+=` or `extend()` and call `bytes()` once at the end; the total stays linear, where `bytes + bytes` copies everything already accumulated every time
- Drop a consumed prefix with `del buffer[:k]`, which is amortized O(1); `pop(0)` in a loop shifts the whole buffer every time
- Read a region through `memoryview(ba)` when it does not need to be copied; a slice copies its k bytes
- Prefer the forward `find()`, `index()`, `split()` and `partition()` to their `r` counterparts on input you do not control; only the forward search is linear in the worst case

❌ **Avoid**:

- `insert(0, x)` and `pop(0)` in loops - each shifts every byte after the edit
- `strip()`, `replace()` or `upper()` to test a buffer - each copies all n bytes even when nothing changes; `startswith()`, `find()` and the predicates do not
- Resizing while a `memoryview` of the buffer is alive - it raises `BufferError` rather than copying
- Using a bytearray as a dictionary key - it is unhashable, and `bytes(ba)` is an O(n) copy

## Version Notes

- **Python 3.14+**: Added `resize()`; `fromhex()` accepts bytes-like input as well as `str`
- **All Python 3**: A bytearray is unhashable, and a live `memoryview` of it blocks every change of length with `BufferError`

## Related Functions

- **[bytes()](bytes_func.md)** - The immutable counterpart, built the same ways
- **[Bytes and Bytearray operations](bytes.md)** - The two types' methods side by side
- **[memoryview()](memoryview_func.md)** - O(1) views over a bytearray's buffer
- **[str](str.md)** - `encode()` produces the bytes that `bytearray(text, encoding)` copies in
- **[list](list.md)** - The same mutator API over arbitrary objects, without the amortized O(1) front deletion
