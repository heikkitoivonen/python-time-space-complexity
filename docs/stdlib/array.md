# array Module Complexity

The `array` module provides one mutable sequence type, `array.array`, that stores its items as
packed C values of a single type chosen by a type code. The buffer is contiguous and
over-allocated the way a list's is, so indexing, appending and shifting cost what they cost on a
list. What changes is storage: each item takes `itemsize` bytes instead of a pointer plus a
separate Python object, and each read converts the stored value to a Python object.

`n` is the items in the array, `k` is the items in the other operand - the initializer, the
iterable or array being added, the slice, the bytes or string being converted - and `i` is an
index. Bounds count items; an item is a fixed `itemsize` bytes, so bytes and items differ only by
a constant. Comparing one stored value with another object is priced O(1). Every call that adds
items is amortized the way `append()` is: the call that reallocates can also move the n items
already there.

## Complexity Reference

### array

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `array.array(typecode[, initializer])` | O(k) | O(k) | Any iterable of values; `bytes` is taken as machine values |
| `array.ArrayType` | O(1) | O(1) | Another name for `array.array` |
| `array.typecodes` | O(1) | O(1) | A string of the type codes this build supports |
| `array.typecode`, `array.itemsize` | O(1) | O(1) | Fixed for the array's lifetime |
| `array.buffer_info()` | O(1) | O(1) | `(address, length)` of the buffer |
| `len(a)` | O(1) | O(1) | |

### Access and search

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `a[i]` | O(1) | O(1) | Converts the stored value to a Python object |
| `a[i] = x` | O(1) | O(1) | For an integer type code, a value outside its range raises `OverflowError` |
| `a[start:stop:step]` | O(k) | O(k) | k = items in the slice; a new array, not a view |
| Iterating an `array` | O(1) per item | O(1) | Each step converts one stored value to a Python object |
| `x in a`, `array.index(x[, start[, stop]])` | O(n) | O(1) | Stops at the first match |
| `array.count(x)` | O(n) | O(1) | Always compares every item |
| `a == b`, `a < b` | O(n) | O(1) | `==` between arrays of different lengths is O(1) |

### Adding and removing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `array.append(x)` | O(1) amortized | O(1) | O(n) on the append that reallocates |
| `array.extend(iterable)` | O(k) | O(k) | An array argument must have the same type code; a bad item stops it with earlier items kept |
| `a += b` | O(k) | O(k) | `b` must be an array of the same type code |
| `array.insert(i, x)` | O(n) | O(1) | Shifts the items after `i` |
| `array.pop([i])` | O(n) | O(1) | O(1) for the last item |
| `array.remove(x)` | O(n) | O(1) | Scans for the first match, then shifts the items after it |
| `del a[i]`, `del a[start:stop]` | O(n) | O(1) | Shifts the items after the deleted range |
| `a[start:stop] = b` | O(n + k) | O(k) | `b` must be an array of the same type code |
| `array.clear()` | O(1) | O(1) | Python 3.13+ |
| `array.reverse()` | O(n) | O(1) | In place |
| `array.byteswap()` | O(n) | O(1) | In place |
| `a + b` | O(n + k) | O(n + k) | A new array |
| `a * m`, `a *= m` | O(n·m) | O(n·m) | m = repeat count |
| `copy.copy(a)`, `copy.deepcopy(a)` | O(n) | O(n) | The items are plain values, so a deep copy is the same buffer copy |

### Conversions and files

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `array.tolist()` | O(n) | O(n) | One Python object per item |
| `array.fromlist(list)` | O(k) | O(k) | Accepts only a list; a bad item leaves the array unchanged |
| `array.tobytes()` | O(n) | O(n) | A copy of the buffer |
| `array.frombytes(buffer)` | O(k) | O(k) | The length must be a multiple of `itemsize` |
| `array.tofile(f)` | O(n) | O(1) | Writes in fixed-size blocks, so the extra memory is one block, not the array |
| `array.fromfile(f, k)` | O(k) | O(k) | One `read()` of `k·itemsize` bytes |
| `array.tounicode()` | O(n) | O(n) | `'u'` and `'w'` arrays only |
| `array.fromunicode(s)` | O(k) | O(k) | `'u'` and `'w'` arrays only |
| `memoryview(a)` | O(1) | O(1) | Shares the buffer; while a view exists, anything that resizes the array raises `BufferError` |

## Type Codes

The type code fixes the bytes per item. The integer codes map to C types, whose sizes are fixed
only as minimums, so `'i'` and `'l'` in particular vary by platform. `array.typecodes` lists what
this build has.

```python
import array

assert array.array('b').itemsize == 1  # signed char
assert array.array('B').itemsize == 1  # unsigned char
assert array.array('h').itemsize >= 2  # signed short
assert array.array('q').itemsize >= 8  # signed long long
assert array.array('f').itemsize == 4  # float
assert array.array('d').itemsize == 8  # double
assert array.array('i').itemsize >= 2  # C int: 4 on common platforms

# Values are checked against the type code on the way in
values = array.array('b', [-128, 0, 127])  # O(k)
try:
    values[0] = 128  # O(1)
except OverflowError as error:
    assert 'maximum' in str(error)
else:
    raise AssertionError('128 fit in a signed char')

assert set('bBhHiIlLqQfd') <= set(array.typecodes)  # O(1)
```

## Memory Compared with a List

Both are O(n). A list's `sys.getsizeof()` counts one pointer per item and none of the objects the
pointers reach, while an array's counts its whole buffer at `itemsize` bytes per item. So
`getsizeof()` alone flatters the list: the per-item objects only the list has are left out.

```python
import array
import sys

values = list(range(1_000, 11_000))  # above the small-int cache: distinct objects
packed = array.array('i', values)    # O(k)

assert sys.getsizeof(packed) < sys.getsizeof(values)  # 4-byte items against 8-byte pointers

# getsizeof() of the list leaves out the ints themselves
reachable = sys.getsizeof(values) + sum(sys.getsizeof(v) for v in values)  # O(n)
assert reachable > 2 * sys.getsizeof(values)

# The array's storage is its items times itemsize, plus the header
payload = sys.getsizeof(packed) - sys.getsizeof(array.array('i'))
assert payload >= len(packed) * packed.itemsize
```

## Reading Items

An array holds raw values, not objects. Indexing, iteration, `in`, `index()`, `count()` and
`tolist()` each build a Python object from the stored value, so the saving is in storage, not in
element access. `in` and `index()` stop at the first match; `count()` always walks every item.

```python
import array

readings = array.array('q', [10**12, 2 * 10**12, 3 * 10**12])

first = readings[0]  # O(1)
assert first == 10**12
assert readings[0] is not first  # a new object on every read

assert 2 * 10**12 in readings              # O(n), stops at the match
assert readings.index(3 * 10**12) == 2     # O(n)
assert readings.count(10**12) == 1         # O(n), every item
assert readings.tolist() == [10**12, 2 * 10**12, 3 * 10**12]  # O(n)

# A slice is a new array
window = readings[1:]  # O(k)
window[0] = 0
assert readings[1] == 2 * 10**12
```

## Adding and Removing Items

### Growth and Shrinking

The buffer grows in steps, so most appends only fill a spare slot and the occasional one
reallocates. Removing items one at a time never gives memory back: the buffer shrinks only when a
single call removes a run of items at once, such as a slice deletion or `clear()`.

```python
import array
import sys

values = array.array('i')
for n in range(1_000):
    values.append(n)  # O(1) amortized
assert len(values) == 1_000

full = sys.getsizeof(values)
for _ in range(900):
    values.pop()  # O(1) at the end
assert sys.getsizeof(values) == full  # the buffer was kept

del values[10:]  # O(n) - one call removes the run
assert sys.getsizeof(values) < full
```

### Inserting in the Middle

`insert()`, `pop(i)`, `remove()` and slice deletion shift every item after the position, as on a
list. Only the end of the array is cheap.

```python
import array

values = array.array('i', [1, 2, 3, 4, 5])

values.insert(0, 0)  # O(n) - shifts five items
assert values[0] == 0

assert values.pop() == 5   # O(1)
assert values.pop(0) == 0  # O(n) - shifts the rest back

values.remove(3)  # O(n) - scan, then shift
assert values.tolist() == [1, 2, 4]
```

### Extending

`extend()` takes any iterable and converts one item at a time, so a bad item stops it with the
earlier ones already appended. `fromlist()` accepts only a list and leaves the array unchanged on
a bad item. `+=` and slice assignment accept only an array of the same type code.

```python
import array

values = array.array('i', [1])

try:
    values.extend([2, 'x'])  # O(k)
except TypeError:
    assert values.tolist() == [1, 2]  # 2 was kept
else:
    raise AssertionError('a str was stored in an int array')

try:
    values.fromlist([3, 'x'])  # O(k)
except TypeError:
    assert values.tolist() == [1, 2]  # nothing was kept
else:
    raise AssertionError('a str was stored in an int array')

values += array.array('i', [3, 4])  # O(k)
try:
    values += [5]
except TypeError as error:
    assert 'array' in str(error)
else:
    raise AssertionError('+= accepted a list')

assert values.tolist() == [1, 2, 3, 4]
```

## Bytes, Files and Buffers

### Converting to and from Bytes

`tobytes()` and `frombytes()` copy the buffer as machine values, in native byte order.
`byteswap()` converts in place when the other side uses the opposite order.

```python
import array

values = array.array('h', [1, 256])
raw = values.tobytes()  # O(n) - a copy
assert len(raw) == len(values) * values.itemsize

restored = array.array('h')
restored.frombytes(raw)  # O(k)
assert restored == values

restored.byteswap()  # O(n), in place
assert restored.tolist() == [256, 1]
```

### Files

`tofile()` writes the buffer in fixed-size blocks, so it needs no copy of the whole array.
`fromfile()` asks for all `k` items in one `read()` call; when the file holds fewer whole items,
it appends those and raises `EOFError`.

```python
import array
import io

values = array.array('d', [0.5] * 1_000)
stream = io.BytesIO()
values.tofile(stream)  # O(n) time, one block of extra memory

stream.seek(0)
loaded = array.array('d')
loaded.fromfile(stream, 1_000)  # O(k)
assert loaded == values

# Asking for more than the file holds appends what was there, then raises
stream.seek(0)
short = array.array('d')
try:
    short.fromfile(stream, 2_000)
except EOFError:
    assert len(short) == 1_000
else:
    raise AssertionError('fromfile read past the end')
```

### Sharing the Buffer

`memoryview()` exposes the array's buffer without copying it. While a view is alive the array
cannot resize, so appends, removals and `clear()` raise `BufferError` until the view is released.

```python
import array

values = array.array('i', [1, 2, 3])
view = memoryview(values)  # O(1) - no copy
values[0] = 10
assert view[0] == 10  # the same memory

try:
    values.append(4)
except BufferError as error:
    assert 'exporting buffers' in str(error)
else:
    raise AssertionError('the array resized under a live view')

view.release()
values.append(4)  # O(1) amortized again
assert len(values) == 4
```

## Common Patterns

### Accumulating Numeric Samples

```python
import array
import io

samples = array.array('d')
for step in range(10_000):
    samples.append(step * 0.5)  # O(1) amortized, 8 bytes per item

total = sum(samples)  # O(n) - one float object per item, built as it goes
assert total == 0.5 * sum(range(10_000))

sink = io.BytesIO()
samples.tofile(sink)  # O(n)
assert len(sink.getvalue()) == len(samples) * samples.itemsize
```

## Performance Best Practices

✅ **Do**:

- Use an array for large collections of one numeric type, where packed storage saves memory
- Append and pop at the end; only the end is O(1)
- Move binary data with `frombytes()`, `tobytes()`, `fromfile()` and `tofile()`, which copy
  machine values without building an object per item
- Use `tofile()` for a large array: it writes without a copy of the whole buffer
- Delete a slice, or call `clear()` on 3.13+, to give memory back; popping item by item keeps
  the buffer

❌ **Avoid**:

- An array for speed of element access - every read builds a Python object
- `insert(0, x)` or `pop(0)` in a loop - each is O(n); use `collections.deque` for a queue
- Holding a `memoryview` longer than needed - the array cannot resize while it exists

## Version Notes

- **Python 3.13+**: Added `clear()` and the `'w'` type code (a 4-byte Unicode character); the
  `'u'` type code emits `DeprecationWarning`
- **All Python 3**: `tofile()` and `tobytes()` write native byte order; call `byteswap()` for the
  other order

## Related Modules

- **[list](../builtins/list.md)** - Any object per slot, at a pointer plus the object per item
- **[struct](struct.md)** - Pack mixed-type records rather than runs of one type
- **[memoryview](../builtins/memoryview_func.md)** - Zero-copy views of an array's buffer
- **[collections](collections.md)** - `deque` for O(1) appends and pops at both ends
