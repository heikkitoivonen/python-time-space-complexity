# Counter Complexity

`collections.Counter` is a `dict` subclass that maps each element to its count. Lookups and
stores are the inherited `dict` code, so reading or bumping one count is a `dict` operation, and a
counter costs what the `dict` holding the same keys does. A missing key reads as 0 without being
inserted.

`n` is the keys in the counter, zero and negative counts included. `m` is the keys of the other
counter, mapping or keyword arguments an operation takes, `t` is the items a non-mapping iterable
yields, `u` is the keys an operation adds to the counter, `k` is the argument to `most_common()`,
and `e` is the elements `elements()` yields, the sum of the positive counts. Bounds treat hashing
a key, comparing keys or counts, and rendering or pickling one key and count as O(1).

## Complexity Reference

### Counter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Counter(iterable=None, /, **kwds)` | O(t + m) | O(n) | Counts an iterable's items, or copies a mapping's counts; memory follows the distinct keys, not the items |
| `c[key]` | O(1) | O(1) | A missing key reads as 0 and is not inserted |
| `c[key] = count`, `c[key] += 1` | O(1) amortized | O(1) amortized | |
| `del c[key]` | O(1) | O(1) | A missing key is not an error |
| `Counter.update(iterable=None, /, **kwds)` | O(t + m) amortized | O(u) amortized | Adds counts; a mapping adds its values rather than counting its keys |
| `Counter.subtract(iterable=None, /, **kwds)` | O(t + m) amortized | O(u) amortized | A key the counter lacks is created at minus the count subtracted; zero and negative counts are kept |
| `Counter.total()` | O(n) | O(1) | Sums every count, zero and negative ones included |
| `Counter.most_common()` | O(n log n) | O(n) | Sorts every item |
| `Counter.most_common(k)` | O(n log k) | O(k) | Keeps a heap of the k largest; `k == 1` is one `max()` pass and `k >= n` sorts all n |
| `Counter.elements()` | O(1) to create, O(n + e) to exhaust | O(1) | Lazy; skips keys whose count is zero or negative |
| `Counter.copy()`, `copy.copy(c)` | O(n) | O(n) | Shallow; the copy has the counter's class |
| `Counter.fromkeys(iterable, v=None)` | O(1) | O(1) | Always raises `NotImplementedError` |
| `repr(c)`, `str(c)` | O(n log n) | O(n) | Sorts the items with `most_common()`; counts that cannot be ordered are listed in insertion order instead |
| `pickle.dumps(c)` | O(n) | O(n) | Pickled as the class and a plain `dict` of counts |

### Multiset operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `c + other`, `c - other`, `c \| other` | O(n + m) | O(n + m) | A new `Counter` of sums, differences or maxima; keys whose result is not positive are left out |
| `c & other` | O(n) | O(min(n, m)) | Walks only the left operand, looking each key up in `other` |
| `+c`, `-c` | O(n) | O(n) | `+c` keeps the positive counts, `-c` negates the negative ones |
| `c += other`, `c -= other`, `c \|= other` | O(n + m) | O(n + m) | Updates `c`, then scans all of it to delete non-positive counts |
| `c &= other` | O(n) | O(n) | Walks `c`, looking each key up in `other`, then deletes non-positive counts |
| `c == other`, `c != other` | O(n + m) | O(1) | Against a `Counter`, a missing key counts as zero; against a plain `dict` it is `dict` equality |
| `c <= other`, `c < other`, `c >= other`, `c > other` | O(n + m) | O(1) | Multiset inclusion; a missing key counts as zero |

### Inherited from dict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `key in c`, `c.get(key, default=None)` | O(1) | O(1) | A key with count 0 is still `in` the counter; `get()` returns `None` for a missing key |
| `len(c)`, `c.keys()`, `c.values()`, `c.items()` | O(1) | O(1) | `len()` counts keys, not elements; views are live and iterating one is O(n) |

The other `dict` methods are inherited unchanged and cost what they cost on a
[dict](../builtins/dict.md).

## Counting

Building a counter and `update()` take one item at a time, so memory follows the distinct keys,
not the input: counting a generator never holds its items. A mapping argument adds its values as
counts instead of counting its keys, and keyword arguments are a mapping.

```python
from collections import Counter

c = Counter('mississippi')  # O(t), t = 11 letters
assert c == {'i': 4, 's': 4, 'p': 2, 'm': 1}

c.update('miss')    # O(t) - adds to the existing counts
c.update({'m': 2})  # O(m) - adds 2, does not count the key once
c.update(z=1)       # O(m)
assert c['m'] == 4 and c['s'] == 6 and c['z'] == 1

digits = Counter(x % 10 for x in range(10_000))  # O(t) time, O(n) space - ten keys
assert len(digits) == 10 and digits[3] == 1_000
```

## Reading and Removing Counts

A missing key reads as 0 and is not inserted. A count that reaches zero stays in the counter -
`in`, `len()` and iteration still see it - until it is deleted, and deleting a missing key is not
an error. `get()` is the inherited `dict` method, so it returns `None` for a missing key.

```python
from collections import Counter

c = Counter(a=2)
assert c['missing'] == 0  # O(1) - not inserted
assert 'missing' not in c and len(c) == 1
assert c.get('missing') is None  # the dict method

c['a'] -= 2  # O(1) - the key stays, at zero
assert 'a' in c and c['a'] == 0 and len(c) == 1

del c['a']  # O(1)
del c['a']  # O(1) - already gone, not an error
assert len(c) == 0
```

## Subtracting Can Grow the Counter

`subtract()` keeps zero and negative counts, and creates every key it subtracts that the counter
lacks, so the counter grows by the keys subtracted. The `-` operator drops what is not positive
instead.

```python
from collections import Counter

c = Counter(a=1)
c.subtract(a=3, b=2)  # O(m) - 'b' is created at -2
assert dict(c) == {'a': -2, 'b': -2}

assert Counter(a=1) - Counter(a=3, b=2) == Counter()  # O(n + m) - nothing positive survives
assert +c == Counter()  # O(n) - unary plus drops the non-positive counts
```

## Top k With most_common

`most_common()` with no argument sorts all n items. Given k, it keeps a heap of the k largest
counts seen so far; each further item is compared with the smallest of them, and only one that
beats it pays a log k replacement. Counts that rise in iteration order beat it every time, which
is the O(n log k) worst case; counts that fall never do. `k == 1` is a single `max()` pass, and
`k >= n` sorts everything. Equal counts keep the order the keys were first inserted.

```python
from collections import Counter

c = Counter('abracadabra')
assert c.most_common(2) == [('a', 5), ('b', 2)]  # O(n log k)
assert c.most_common(1) == [('a', 5)]  # O(n) - one max() pass
assert c.most_common() == [('a', 5), ('b', 2), ('r', 2), ('c', 1), ('d', 1)]  # O(n log n)
assert c.most_common()[:-3:-1] == [('d', 1), ('c', 1)]  # least common: still a full sort

# repr() lists the items in most_common() order, so printing a counter sorts it
assert repr(c) == "Counter({'a': 5, 'b': 2, 'r': 2, 'c': 1, 'd': 1})"  # O(n log n)
```

## Multiset Arithmetic

The binary operators build a new `Counter` and leave out every key whose result is not positive.
`+`, `-` and `|` walk both operands. `&` walks only its left operand and looks each key up in the
right, so put the smaller counter on the left; the result is the same either way.

```python
from collections import Counter

a = Counter(x=3, y=1)
b = Counter(x=1, y=2, z=4)

assert a + b == Counter(x=4, y=3, z=4)  # O(n + m)
assert a - b == Counter(x=2)  # O(n + m) - y would be -1, so it is left out
assert a | b == Counter(x=3, y=2, z=4)  # O(n + m) - the larger count
assert a & b == Counter(x=1, y=1)  # O(n) - walks a only
assert b & a == Counter(x=1, y=1)  # O(m) - walks b, same result

assert a <= a + b and not a <= b  # O(n + m) - multiset inclusion
assert Counter(x=1, y=0) == Counter(x=1)  # O(n + m) - a missing key counts as zero
assert Counter(x=1, y=0) != {'x': 1}  # a plain dict compares as a dict
```

### In-place Operators Rescan the Counter

`+=`, `-=`, `|=` and `&=` update the counter and then scan all of it to delete the counts that
are not positive, so each scans all n keys however small `other` is. `update()` and `subtract()` cost
only the size of their argument and keep those counts.

```python
from collections import Counter

totals = Counter(a=1, b=-1)
totals.update(c=2)  # O(m) - b stays at -1
assert dict(totals) == {'a': 1, 'b': -1, 'c': 2}

totals += Counter(c=1)  # O(n + m) - scans all of totals, deleting b
assert dict(totals) == {'a': 1, 'c': 3}
```

## Elements, Totals and Copies

```python
from collections import Counter

c = Counter(a=3, b=0, c=-1)
assert c.total() == 2  # O(n) - zero and negative counts included
assert list(c.elements()) == ['a', 'a', 'a']  # O(n + e) - zero and negative counts skipped

copied = c.copy()  # O(n), shallow
assert copied == c and copied is not c

try:
    Counter.fromkeys('ab')
except NotImplementedError as error:
    assert 'Counter(iterable)' in str(error)
else:
    raise AssertionError('fromkeys() built a counter')
```

## Common Patterns

### Word Frequency

```python
from collections import Counter

text = "the quick brown fox jumps over the lazy dog the fox"
freq = Counter(text.split())  # O(t)

assert freq.most_common(2) == [('the', 3), ('fox', 2)]  # O(n log k)
assert [word for word, count in freq.items() if count > 1] == ['the', 'fox']  # O(n)
```

### Anagrams

```python
from collections import Counter

def are_anagrams(first, second):
    return Counter(first) == Counter(second)  # O(t) for each word

assert are_anagrams('listen', 'silent')
assert not are_anagrams('hello', 'world')
```

## Performance Best Practices

✅ **Do**:

- Count an iterator directly; memory follows the distinct keys, not the items
- Pass k to `most_common()` for the top few; it holds k items instead of sorting all n
- Add counts in a loop with `update()` or `subtract()`, which cost the size of their argument
- Put the smaller counter on the left of `&`
- Delete counts that reach zero, or take `+c` once, when the counter has to stay small

❌ **Avoid**:

- `c += small` in a loop over a large counter: every one rescans all of `c`
- `most_common()[:k]` for the top k: it sorts all n
- `repr()` or `print()` of a large counter on a hot path: it sorts every item
- Expecting `subtract()` to shrink the counter: it adds every key it subtracts

## Version Notes

- **Python 3.3+**: Unary `+` and `-`, and the in-place `+=`, `-=`, `|=` and `&=`
- **Python 3.7+**: Keys keep insertion order, so equal counts in `most_common()` keep it too
- **Python 3.10+**: `total()` and the `<`, `<=`, `>`, `>=` operators; `==` treats a missing key as
  a zero count

## Related Modules

- **[dict](../builtins/dict.md)** - the base type, and the cost of every inherited operation
- **[heapq](heapq.md)** - `nlargest()`, which `most_common(k)` uses
- **[defaultdict](defaultdict.md)** - `defaultdict(int)` counts too, but a missed read inserts the key
- **[collections](collections.md)** - the module `Counter` belongs to
