# bytes Type Complexity

The `bytes` type is an immutable sequence of bytes: one fixed buffer, never resized or edited
after it is built. Its searches and predicates only read that buffer, and the operations that
produce bytes copy what they return - except that, because nothing can change it, an exact
`bytes` returns itself from most operations whose result would be an equal copy: a full slice,
a strip that strips nothing, a `replace()` that finds nothing. For the mutable counterpart, which always
copies, see [bytearray](bytearray.md).

`n` is the bytes in the receiver, `k` is the bytes in the other operand (the data concatenated,
the slice covered, or the characters of a hex string), `m` is the bytes in a pattern (`sub`,
`old`, `prefix`, `suffix`, `sep`), `p` is the parts handed to `join()`, and `w` is the bytes in
the result where that differs from `n`. Reading one byte, or one item of a `bytes`, is O(1). The
`decode()` row assumes a codec and error handler whose cost and output are proportional to their
input, as the byte-oriented codecs are, and the `%` row assumes values whose formatting costs
what it emits.

## Complexity Reference

### Sequence operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(b)` | O(1) | O(1) | |
| `b[i]` | O(1) | O(1) | An `int` in `range(256)`; `b[i] = v` raises `TypeError` |
| `b[i:j]`, `b[i:j:step]` | O(k) | O(k) | A copy of the k bytes covered; a step-1 slice covering all of `b` is `b` itself, O(1). `memoryview(b)` is the O(1) alternative |
| `x in b` | O(n + m) | O(1) | `x` is an `int` or bytes-like |
| `b + other`, `b += other` | O(n + k) | O(n + k) | `other` is any bytes-like. `+=` cannot grow `b` in place, so a loop of them copies everything accumulated each time |
| `b * count` | O(n·count) | O(n·count) | O(1) for a count of 1, which returns `b` itself, and for a count of 0 or less, which returns `b''` |
| `b == other`, `b != other` | O(n) | O(1) | O(1) when the lengths differ; `<` and the other orderings walk to the first difference |
| `for x in b` | O(n) | O(1) | One `int` per byte; `iter(b)` on its own is O(1) |
| `hash(b)` | O(n) the first time, then O(1) | O(1) | Cached on the object; an equal `bytes` built separately hashes its n bytes again |
| `b % values` | O(n + w) | O(n + w) | w = result length |
| `memoryview(b)` | O(1) | O(1) | A read-only view of the same buffer; slicing the view is O(1) as well |

### Searching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `find(sub, start, end)`, `index(sub, start, end)` | O(n + m) | O(1) | `sub` is bytes-like or an `int`; `index()` raises `ValueError` when absent |
| `rfind(sub, start, end)`, `rindex(sub, start, end)` | O(n·m) | O(1) | Worst case, absent patterns included: the reverse search has no linear-time fallback, where the forward one does |
| `count(sub, start, end)` | O(n + m) | O(1) | Non-overlapping occurrences |
| `startswith(prefix, start, end)`, `endswith(suffix, start, end)` | O(m + q) | O(1) | Independent of n. Either accepts a tuple of q candidates, and then m is their total length |

### Transforming

Where the Notes say `b` itself, a call that changes nothing returns the receiver rather than a
copy; the others always build a new object.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `replace(old, new, count=-1)` | O(n + w) | O(w) | w = result length. `b` itself, in O(1) space, when `old` does not occur |
| `translate(table, /, delete=b'')` | O(n + d) | O(n) | `table` is a 256-byte table from `maketrans()`, or `None`; d = bytes in `delete`. `b` itself when no byte changes, though the n-byte result is built before that is known |
| `bytes.maketrans(from, to)` | O(k) | O(1) | A 256-byte `bytes` whatever k is; the two arguments must be the same length. Static method |
| `upper()`, `lower()`, `capitalize()`, `title()`, `swapcase()` | O(n) | O(n) | ASCII letters only. A new object even when nothing changes |
| `strip(chars)`, `lstrip(chars)`, `rstrip(chars)` | O(n + (s + 1)·c) | O(n) | s = bytes stripped, c = bytes in `chars`, which is searched once per stripped byte and once more to stop; without `chars`, c is O(1). `b` itself when nothing is stripped, which costs only that O(c) search and O(1) space |
| `removeprefix(prefix)`, `removesuffix(suffix)` | O(n) | O(n) | `b` itself when the prefix or suffix is absent: O(m) time and O(1) space |
| `center(width, fillbyte)`, `ljust(width, fillbyte)`, `rjust(width, fillbyte)`, `zfill(width)` | O(width) | O(width) | `b` itself, O(1), when width ≤ n |
| `expandtabs(tabsize=8)` | O(n + w) | O(w) | A new object even with no tabs; a `tabsize` below 1 drops the tabs, so w can be smaller than n |

### Splitting and joining

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `split(sep=None, maxsplit=-1)` | O(n + m) | O(n) | A list of new `bytes` holding at most n bytes between them; `[b]` holding `b` itself when no separator occurs |
| `rsplit(sep=None, maxsplit=-1)` | O(n·m) | O(n) | Worst case: a multi-byte `sep` is searched backwards, with the `rfind()` worst case at each match. `None`, and a one-byte `sep`, scan. `[b]` when no separator occurs |
| `splitlines(keepends=False)` | O(n) | O(n) | `[b]` holding `b` itself when there is no line break |
| `partition(sep)` | O(n + m) | O(n) | A hit copies the bytes either side of `sep`; a miss returns `(b, b'', b'')` with `b` itself, in O(1) space |
| `rpartition(sep)` | O(n·m) | O(n) | Worst case, as for `rfind()`. A miss returns `(b'', b'', b)` with `b` itself |
| `join(iterable)` | O(p + w) | O(p + w) | Every part must be bytes-like, and each costs a buffer descriptor whatever its length. A lone part that is an exact `bytes` is returned itself |

### Predicates and conversion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `isalnum()`, `isalpha()`, `isascii()`, `isdigit()`, `islower()`, `isspace()`, `istitle()`, `isupper()` | O(n) | O(1) | Stop at the first byte that settles the answer |
| `decode(encoding='utf-8', errors='strict')` | O(n) | O(n) | |
| `hex(sep, bytes_per_sep)` | O(n) | O(n) | Two characters per byte, plus any separators |
| `bytes.fromhex(string)` | O(k) | O(k) | k = characters, one byte per pair; whitespace between pairs is skipped. Class method |

## Unchanged Results Are the Receiver

A `bytes` cannot change, so handing back the same object is as good as a copy. Where a method
finds nothing to do, an exact `bytes` usually returns itself instead of copying, which a
`bytearray` never does. The case-changing methods and `expandtabs()` are the exceptions: they
always build a new object.

```python
data = b"Hello"

assert data[:] is data  # O(1) - the whole buffer, step 1
assert bytes(data) is data  # O(1) - see bytes()
assert data.strip() is data  # O(1) - nothing to strip, only the ends are read
assert data.replace(b"z", b"y") is data  # O(n) to search, O(1) space
assert data.removeprefix(b"z") is data  # O(m)
assert data.center(3) is data  # O(1) - width <= n
assert data.split(b",")[0] is data  # O(n + m) - no separator, so no copy
assert data.partition(b",")[0] is data  # O(n + m)

assert data.upper() is not data  # O(n) - always a new object
assert data.upper().upper() == b"HELLO"
mutable = bytearray(data)
assert mutable.strip() is not mutable  # a bytearray always copies


class Packet(bytes):
    pass


packet = Packet(b"Hello")
assert packet.strip() is not packet  # a subclass gets a copy
assert type(packet.strip()) is bytes
```

## Building Bytes Incrementally

`b += other` cannot extend `b` in place: once `b` is non-empty, each non-empty `other` builds
a new object holding both, so a loop that accumulates p chunks copies everything gathered so far on every pass,
O(w·p) in total. Collect the parts and `join()` them once, O(p + w), or grow a
[bytearray](bytearray.md) and convert it at the end.

```python
chunks = [b"header", b":", b"payload", b"\n"] * 3

# QUADRATIC: every += copies the whole accumulated value
slow = b""
for chunk in chunks:
    slow += chunk  # O(len(slow) + len(chunk))

# LINEAR: one pass to measure, one to copy
fast = b"".join(chunks)  # O(p + w)

# LINEAR: an amortized O(k) append per chunk, one copy at the end
buffer = bytearray()
for chunk in chunks:
    buffer += chunk  # O(k) amortized
built = bytes(buffer)  # O(w)

assert slow == fast == built
assert len(fast) == 3 * len(b"header:payload\n")
assert b"".join([fast]) is fast  # a single bytes part is returned itself
```

## Hashing and Dictionary Keys

A `bytes` computes its hash the first time it is asked and keeps it, so a key used many times
hashes its bytes once. The cache belongs to the object: a fresh slice or concatenation that
produces an equal `bytes` is a new object, and hashing it reads every byte again. A successful
lookup with a distinct but equal key also compares the two, reading all k bytes of the key.

```python
routes = {b"GET /": "index", b"GET /health": "health"}

request = b"GET /health HTTP/1.1"
key = request.partition(b" HTTP/")[0]  # O(n + m) - a new 11-byte object

assert routes[key] == "health"  # O(k) to hash the new key, O(k) to compare it
assert routes[key] == "health"  # O(k) - the hash is cached, the comparison is not
assert hash(key) == hash(b"GET /health")  # equal bytes, equal hashes

try:
    hash(bytearray(key))
except TypeError as error:
    assert "unhashable" in str(error)
else:
    raise AssertionError("a bytearray was hashed")
```

## Slices Copy, Views Do Not

A slice copies the k bytes it covers. A `memoryview` shares the buffer, and so
does every slice of the view, so parsing a large message field by field through a view copies
only what is finally converted.

```python
message = b"\x00\x05hello world"

length = int.from_bytes(message[:2], "big")  # O(k) - a 2-byte copy
assert length == 5

view = memoryview(message)  # O(1)
body = view[2 : 2 + length]  # O(1) - no bytes copied
assert body.tobytes() == b"hello"  # O(k) - the one copy, when it is needed
assert bytes(body) == b"hello"  # O(k) likewise

try:
    view[0] = 1  # the view is read-only, as the bytes is
except TypeError as error:
    assert "read-only" in str(error)
else:
    raise AssertionError("a view of a bytes was written to")
view.release()
```

## Searching

`find()` is linear even in the worst case. `rfind()` searches backwards with a simpler algorithm
that can compare most of the pattern at every position, and so can cost the pattern's length at
each of the receiver's. `rsplit()`, `rpartition()` and `rindex()` search the same way.

```python
haystack = b"a" * 10_000
needle = b"ab" + b"a" * 98  # mismatches only at its second byte

assert haystack.find(needle) == -1  # O(n + m) - linear in the worst case
assert haystack.rfind(needle) == -1  # O(n·m) - m comparisons at each of n positions
assert haystack.count(b"aa") == 5_000  # O(n + m) - non-overlapping
assert haystack.startswith(b"aaa")  # O(m) - the prefix's length, not the receiver's
assert 97 in haystack  # O(n) - an int is a byte value

try:
    haystack.index(b"b")  # O(n + m)
except ValueError as error:
    assert "not found" in str(error)
else:
    raise AssertionError("index() found a byte that is not there")
```

## Common Patterns

### Splitting Records

```python
data = b"alice,30\nbob,25\ncara,41\n"

rows = []
for line in data.splitlines():  # O(n)
    name, _, age = line.partition(b",")  # O(n + m), n = this line's length
    rows.append((name.decode("ascii"), int(age)))  # O(n)

assert rows == [("alice", 30), ("bob", 25), ("cara", 41)]
```

### Normalising Without Copying

Normalising input that is usually clean makes no copies of the clean inputs, since each step
returns its receiver when it has nothing to do.

```python
def normalise(field):
    return field.strip().removeprefix(b"0x")  # no copy when nothing changes


clean = b"ff00"
assert normalise(clean) is clean  # no copies made
assert normalise(b" 0xff00 ") == b"ff00"  # two copies, each O(n)
assert bytes.fromhex(normalise(b" 0xff00 ").decode("ascii")) == b"\xff\x00"  # O(k)
```

## Performance Best Practices

✅ **Do**:

- Build output with `b"".join(parts)` or a `bytearray`, not `+=`; both stay linear in the bytes produced
- Slice through `memoryview(b)` when parsing a large buffer field by field; each `bytes` slice copies its k bytes
- Reuse one `bytes` object as a repeated dictionary key; its hash is computed once and cached
- Prefer the forward `find()`, `index()`, `split()` and `partition()` to their `r` counterparts on input you do not control; only the forward search is linear in the worst case

❌ **Avoid**:

- `b += chunk` in a loop - each pass copies everything accumulated so far
- Copying a `bytes` to protect it, with `b[:]` or `bytes(b)` - it cannot change, and both return `b` itself
- Calling `upper()`, `lower()` or `expandtabs()` to test the contents - they always copy, where `isupper()`, `find()` and `startswith()` do not
- `rfind()`, `rsplit()` or `rpartition()` with a long pattern on untrusted input - O(n·m) in the worst case

## Version Notes

- **Python 3.14+**: `bytes.fromhex()` accepts bytes-like input as well as `str`

## Related Types

- **[bytes()](bytes_func.md)** - Every way of building a `bytes`, and what each costs
- **[bytearray](bytearray.md)** - The mutable counterpart: the same methods, plus amortized O(1) appends, but every transform copies
- **[bytearray()](bytearray_func.md)** - Building a `bytearray`, the linear way to accumulate bytes
- **[memoryview()](memoryview_func.md)** - O(1) views and slices over a `bytes` buffer
- **[str](str.md)** - Text; `str.encode()` and `bytes.decode()` convert between the two in O(n)

## Further Reading

- [CPython Internals: bytes](https://zpoint.github.io/CPython-Internals/BasicObject/bytes/bytes.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's bytes implementation
