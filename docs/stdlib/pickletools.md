# pickletools Module Complexity

The `pickletools` module looks inside a pickle without loading it: it iterates the opcodes, prints
a disassembly, or rewrites the pickle without its unused memo stores. None of it builds the
pickled objects. Each function walks the byte stream once, opcode by opcode, from the current
position through the first `STOP`; `optimize()` then copies what it keeps.

`n` is the bytes in the pickle, `p` is its opcodes (never more than `n`), `a` is the bytes of one
opcode with its argument, and `d` is the MARK nesting depth at an opcode, the MARKs pushed and not
yet consumed. Decoding an argument is priced by its bytes, and printing an offset as O(1). That
holds for integers while `sys.get_int_max_str_digits()` caps their decimal conversion, which it does
by default; with the limit lifted, converting a large integer costs more than its bytes.

## Complexity Reference

### genops

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickletools.genops(pickle)` | O(1) | O(1) | A generator over bytes or a binary file; nothing is read until it is iterated |
| Iterating `genops()` | O(a) per opcode, O(n) in all | O(a) | Yields `(opcode, arg, pos)`; stops after the first `STOP`, leaving a file just past it. `pos` is `None` for a file without `tell()` |

### dis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickletools.dis(pickle, out=None, memo=None, indentlevel=4, annotate=0)` | O(n + p·d) | O(p + a) | One line per opcode to `out` (stdout by default), indented `indentlevel` spaces per open MARK, so `indentlevel=0` drops the p·d term. Raises `ValueError` on a truncated pickle, an unknown opcode, a stack or memo mismatch, and an integer argument longer than `sys.get_int_max_str_digits()` digits |
| `dis(..., memo=memo)` | O(n + p·d) | O(p + a) | A dict shared across calls lets a pickle read memo entries stored by an earlier one from the same pickler |

### optimize

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickletools.optimize(picklestring)` | O(n) | O(n) | Takes bytes, not a file. Drops the stores to memo keys no `GET` reads, renumbers the rest, and rebuilds protocol 4+ frames |

### Command line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python -m pickletools file [file ...]` | O(n + p·d) per file | O(p + a) | `dis()` on each file; `-m` shares one memo across the files, so it holds their entries together; `-l` sets the indent, `-a` annotates each line, `-o` writes to a file |

## Iterating Opcodes

`genops()` is lazy: each step reads one opcode and its argument, and nothing else. It stops at the
first `STOP`, so several pickles written back to back in one stream are read one per call.

```python
import io
import pickle
import pickletools

data = pickle.dumps({'name': 'Alice', 'age': 30}, protocol=4)

ops = pickletools.genops(data)  # O(1) - nothing read yet
opcode, arg, pos = next(ops)    # O(a)
assert (opcode.name, arg, pos) == ('PROTO', 4, 0)

names = [op.name for op, arg, pos in pickletools.genops(data)]  # O(n)
assert names[-1] == 'STOP' and names.count('SHORT_BINUNICODE') == 3

# Two pickles in one stream: each pass stops after its own STOP
stream = io.BytesIO(pickle.dumps(1, protocol=2) + pickle.dumps(2, protocol=2))
first = [arg for op, arg, pos in pickletools.genops(stream)]
assert first == [2, 1, None] and stream.tell() == 5
second = [arg for op, arg, pos in pickletools.genops(stream)]
assert second == [2, 2, None]
```

## Disassembling a Pickle

`dis()` prints one line per opcode, with the byte offset, the opcode and its decoded argument.
It emulates the unpickler's stack and memo with placeholders rather than objects, which is
where its O(p) space goes, and checks that each opcode finds what it needs there.

```python
import io
import pickle
import pickletools

data = pickle.dumps({'name': 'Alice', 'age': 30}, protocol=4)

out = io.StringIO()
pickletools.dis(data, out=out)  # O(n + p·d)
lines = out.getvalue().splitlines()

assert lines[0].split() == ['0:', '\\x80', 'PROTO', '4']
assert lines[2].split() == ['11:', '}', 'EMPTY_DICT']
assert lines[5].split() == ['14:', '\\x8c', 'SHORT_BINUNICODE', "'name'"]
assert lines[-1] == 'highest protocol among opcodes = 4'

# A truncated pickle raises after printing what it could read
try:
    pickletools.dis(data[:-1], out=io.StringIO())
except ValueError as error:
    assert 'pickle exhausted before seeing STOP' in str(error)
else:
    raise AssertionError('a pickle without STOP was accepted')
```

### Indentation Follows MARK Depth

Every line is indented `indentlevel` spaces for each MARK still open, so the output of a deeply
nested pickle grows with p·d rather than with its bytes. Pass `indentlevel=0` when only the
opcodes matter.

```python
import io
import pickle
import pickletools

nested = (1, 2, 3, 4)
for _ in range(50):
    nested = (nested, 1, 2, 3)  # tuples of four are built between MARK and TUPLE
data = pickle.dumps(nested, protocol=4)

indented = io.StringIO()
pickletools.dis(data, out=indented)  # O(n + p·d)
flat = io.StringIO()
pickletools.dis(data, out=flat, indentlevel=0)  # O(n)

assert 'K    ' + ' ' * 4 * 51 + 'BININT1' in indented.getvalue()  # inside 51 MARKs
assert 'K    BININT1' in flat.getvalue()
assert len(indented.getvalue()) > 4 * len(flat.getvalue())
```

### Sharing a Memo Across Pickles

A `Pickler` keeps its memo between `dump()` calls, so a later pickle may `GET` an entry an earlier
one stored. Disassembling that later pickle alone fails; passing the same `memo` dict to each
call follows the entries across them.

```python
import io
import pickle
import pickletools

stream = io.BytesIO()
pickler = pickle.Pickler(stream, protocol=4)
shared = ['shared']
pickler.dump(shared)
pickler.dump(shared)  # the second pickle is just a GET of memo entry 0

stream.seek(0)
memo = {}
pickletools.dis(stream, out=io.StringIO(), memo=memo)  # O(n + p·d)
out = io.StringIO()
pickletools.dis(stream, out=out, memo=memo)
assert 'BINGET     0' in out.getvalue()

stream.seek(0)
pickletools.dis(stream, out=io.StringIO())  # the first pickle, with a fresh memo
try:
    pickletools.dis(stream, out=io.StringIO())
except ValueError as error:
    assert 'memo key 0 has never been stored into' in str(error)
else:
    raise AssertionError('a GET of an unknown memo key was accepted')
```

### Integers Past the Digit Limit

`dis()` prints an integer argument in decimal, so one longer than `sys.get_int_max_str_digits()`
digits raises `ValueError` there, as converting it to `str` would. `genops()` decodes a binary
integer from its bytes and reads it without complaint.

```python
import io
import pickle
import pickletools
import sys

data = pickle.dumps(10 ** 5000, protocol=4)

assert len(list(pickletools.genops(data))) == 4  # O(n)

try:
    pickletools.dis(data, out=io.StringIO())
except ValueError as error:
    assert 'integer string conversion' in str(error)
else:
    raise AssertionError('an integer over the digit limit was printed')

previous = sys.get_int_max_str_digits()
sys.set_int_max_str_digits(0)  # no limit
try:
    pickletools.dis(data, out=io.StringIO())
finally:
    sys.set_int_max_str_digits(previous)
```

## Optimizing a Pickle

The pickler memoizes strings and containers so that shared references survive, whether or not
anything is shared, and a store that no `GET` reads back only takes space. `optimize()` finds which entries a `GET` reads, then copies the pickle without the
other stores. The result loads to an equal object.

```python
import pickle
import pickletools

data = pickle.dumps({'name': 'Alice', 'age': 30}, protocol=4)
smaller = pickletools.optimize(data)  # O(n)

names = [op.name for op, arg, pos in pickletools.genops(smaller)]
assert 'MEMOIZE' not in names
assert len(smaller) < len(data)
assert pickle.loads(smaller) == {'name': 'Alice', 'age': 30}

# An entry that is read back keeps its store
shared = [1]
kept = pickletools.optimize(pickle.dumps([shared, shared], protocol=4))
names = [op.name for op, arg, pos in pickletools.genops(kept)]
assert names.count('MEMOIZE') == 1 and names.count('BINGET') == 1
restored = pickle.loads(kept)
assert restored[0] is restored[1]
```

## Common Patterns

### Counting Opcodes Without Loading

```python
import pickle
import pickletools
from collections import Counter

data = pickle.dumps([{'id': i} for i in range(3)], protocol=4)

counts = Counter(op.name for op, arg, pos in pickletools.genops(data))  # O(n)
assert counts['EMPTY_DICT'] == 3
assert counts['STOP'] == 1
```

## Performance Best Practices

✅ **Do**:

- Iterate `genops()` when only the opcodes matter: it holds one argument, where `dis()` also
  emulates the stack and memo and formats a line per opcode
- Pass `indentlevel=0` to `dis()` for a deeply nested pickle
- Pass one `memo` dict to `dis()` for pickles a single pickler wrote in sequence

❌ **Avoid**:

- Collecting a large pickle's `dis()` output in memory when `out` could be a file
- Calling `optimize()` on a file object - read it into bytes first

## Version Notes

- **Python 3.14+**: `dis()` accepts a pickle that stores into the same memo key twice; earlier
  versions raise `ValueError`

## Related Modules

- **[pickle](pickle.md)** - Writes and loads the pickles this module inspects
- **[marshal](marshal.md)** - The interpreter's own serialization format for code objects
- **[dis](dis.md)** - The same idea for Python bytecode
