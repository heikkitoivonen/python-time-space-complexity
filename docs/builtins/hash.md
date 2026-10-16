# hash() Function Complexity

The `hash()` function returns an object's hash value, the integer that dictionaries and sets use to
find a key. It calls the type's `__hash__`, so its cost is that method's cost: some built-in types
compute the value once and keep it on the object, others compute it on every call.

`n` is the length of a `str` or `bytes`, or the number of items in a `tuple` or `frozenset`. `m` is
the number of 30-bit digits in an `int`. `h` is the cost of a class's own `__hash__`, and `k` is the
cost of hashing one item of a tuple. `c` is the number of entries in a dict or set. Space bounds
exclude what a class's own `__hash__` allocates, and dict and set bounds price one key comparison
at O(1).

## Complexity Reference

### hash

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hash(object)` | O(h) | O(1) | Calls `type(object).__hash__`; the rows below give h for the built-in types |
| `hash()` of an `int` | O(m) | O(1) | Recomputed on every call |
| `hash()` of a `float` | O(1) | O(1) | An integral float hashes like the equal `int` |
| `hash()` of a `str` or `bytes` | O(n) first call, O(1) after | O(1) | Kept on the object; an equal object built separately is hashed again |
| `hash()` of a `tuple` | O(n·k) first call | O(1) | Hashes every item; O(1) after the first call on 3.14+, O(n·k) on every call before |
| `hash()` of a `frozenset` | O(n) first call, O(1) after | O(1) | Combines the item hashes the set already stores; no item is hashed again |
| `hash()` of `None`, a `bool`, or a plain instance | O(1) | O(1) | An instance whose class inherits `object.__hash__` hashes by its identity |
| `hash()` of an instance with its own `__hash__` | O(h) | O(1) | Called on every `hash()`, dict lookup and set test; nothing is kept |
| `hash()` of a `list`, `dict`, `set` or `bytearray` | O(1) | O(1) | Raises `TypeError`, as does a class that defines `__eq__` without `__hash__` |

### Hashing in dict and set

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `d[key]`, `key in d`, `key in s` | O(1) avg, O(c) worst | O(1) | Plus one hash of `key`; the worst case is every key's hash colliding |
| Building a dict or set of c keys | O(c) avg, O(c²) worst | O(c) | Plus one hash of each key; copying a dict or set reuses its stored hashes |
| `s1 & s2` on two sets | O(min(len(s1), len(s2))) avg | O(min(len(s1), len(s2))) | Reuses the hashes both sets store; `\|`, `-`, `^` and comparisons between sets do too |

## Hashing Built-in Types

### Numbers

An `int` is hashed digit by digit on every call. Numbers that compare equal hash equal across types,
so `1`, `1.0` and `True` are the same dict key.

```python
import sys

assert hash(0) == 0
assert hash(256) == 256          # O(m) - a small int hashes to itself
assert hash(-1) == -2            # -1 is reserved, so it maps to -2

big = 10**100
assert hash(big) == hash(big)    # O(m) on each call

assert hash(1.0) == hash(1) == hash(True)     # O(1)
assert {1: "one"}[1.0] == "one"

modulus = sys.hash_info.modulus
assert hash(modulus + 5) == hash(5)    # ints are reduced modulo a fixed prime
```

### Strings and Bytes

A `str` or `bytes` reads every character the first time it is hashed and keeps the result. Equal
strings hash equal whether or not they are the same object, but a string built separately has not
been hashed yet.

```python
text = "ab" * 50_000

first = hash(text)                    # O(n) - reads all 100,000 characters
assert hash(text) == first            # O(1) - the kept value

rebuilt = "".join(["ab"] * 50_000)    # equal, but a new object
assert rebuilt is not text
assert hash(rebuilt) == first         # O(n) again, for the new object

assert hash(b"hello") == hash(bytes([104, 101, 108, 108, 111]))
```

### Tuples and Frozensets

A tuple hashes each item, so its cost is the sum of its items' hash costs, and a tuple that holds an
unhashable item raises. A frozenset stores its items' hashes when it is built, and its own hash
combines those stored values.

```python
point = (1, 2, 3)
assert hash(point) == hash((1, 2, 3))      # O(n·k) - hashes all three items

nested = ((1, 2), ("a", "b"))
assert hash(nested) == hash(((1, 2), ("a", "b")))    # hashes the inner tuples too

try:
    hash((1, [2, 3]))
except TypeError as exc:
    assert "unhashable type: 'list'" in str(exc)
else:
    raise AssertionError("a tuple holding a list was hashed")

tags = frozenset(["x", "y", "z"])
assert hash(tags) == hash(frozenset(["z", "y", "x"]))    # O(n) first call, order-free
```

## Hashing Your Own Classes

A class that inherits `__eq__` and `__hash__` from `object` hashes by identity in O(1). Defining `__eq__`
alone makes instances unhashable. A `__hash__` you write is called on every `hash()`, every dict
lookup and every set test, so hash a tuple of the fields that `__eq__` compares.

```python
class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    def __eq__(self, other):
        return (self.x, self.y) == (other.x, other.y)

    def __hash__(self):
        return hash((self.x, self.y))      # hashes a 2-tuple of the fields


assert hash(Point(1, 2)) == hash(Point(1, 2))
assert {Point(1, 2): "a"}[Point(1, 2)] == "a"


class EqOnly:
    def __eq__(self, other):
        return True


assert EqOnly.__hash__ is None
try:
    hash(EqOnly())
except TypeError as exc:
    assert "unhashable type" in str(exc)
else:
    raise AssertionError("a class with only __eq__ was hashed")

plain = object()
assert hash(plain) == hash(plain)          # O(1) - from the object's identity
```

## Hash Collisions

A lookup compares the stored hash first and calls `__eq__` only when the hashes match, so distinct
hashes keep lookups O(1). When every key has the same hash, each insert compares the new key with
the keys already there, and building a set or dict of c keys does O(c²) comparisons.

```python
class Collides:
    comparisons = 0

    def __init__(self, value):
        self.value = value

    def __hash__(self):
        return 42                          # every instance collides

    def __eq__(self, other):
        Collides.comparisons += 1
        return self.value == other.value


items = {Collides(i) for i in range(1_000)}     # O(c²) comparisons
assert len(items) == 1_000
assert Collides.comparisons >= 1_000 * 999 // 2
```

`str` and `bytes` hashes are salted with a per-process random value, so unless `PYTHONHASHSEED`
fixes the salt, their colliding inputs cannot be chosen in advance. `int` hashes are not salted:
non-negative ints that differ by a multiple of `sys.hash_info.modulus` always collide.

```python
import sys

modulus = sys.hash_info.modulus
keys = [i * modulus for i in range(1, 6)]
assert len({hash(key) for key in keys}) == 1    # five keys, one hash
assert len(set(keys)) == 5                      # still distinct keys
```

## Set Operations Reuse Stored Hashes

A set keeps each element's hash next to it, so operations between two sets or frozensets - `&`,
`|`, `-`, `^`, comparisons and copies - look elements up without calling `__hash__` again. An
operand that is not a set, such as a list passed to `intersection()`, is hashed item by item.

```python
class Counted:
    hashes = 0

    def __init__(self, value):
        self.value = value

    def __hash__(self):
        Counted.hashes += 1
        return hash(self.value)

    def __eq__(self, other):
        return self.value == other.value


left = {Counted(i) for i in range(100)}         # 100 hashes
right = {Counted(i) for i in range(50, 300)}    # 250 hashes
Counted.hashes = 0

common = left & right                           # O(min(len(left), len(right)))
assert len(common) == 50
assert Counted.hashes == 0                      # no element hashed again

left.intersection(list(right))                  # the list's 250 items are hashed
assert Counted.hashes == 250
```

## Common Patterns

### Memoization with Hashable Keys

Each lookup in a cache dict hashes the key, so the key's hash cost from the table above is part of
every cache hit.

```python
calls = []

def do_expensive_work(arg):
    calls.append(arg)
    return len(arg)

cache = {}

def expensive_function(arg):
    if arg in cache:                    # O(1) avg, plus one hash of arg
        return cache[arg]
    result = do_expensive_work(arg)
    cache[arg] = result                 # O(1) avg, plus one hash of arg
    return result

assert expensive_function(("data", 1)) == 2      # computed
assert expensive_function(("data", 1)) == 2      # from the cache
assert calls == [("data", 1)]
```

### Deduplicating Unhashable Values

Lists cannot go into a set, so convert each one to a tuple first. That hashes every item of every
list once.

```python
data = [[1, 2], [1, 2], [3, 4]]

unique = {tuple(row) for row in data}    # O(rows + total items)
assert unique == {(1, 2), (3, 4)}
```

## Performance Best Practices

✅ **Do**:

- Reuse the same `str` or `bytes` object as a key - its hash is computed once
- Hash a tuple of the fields `__eq__` compares, so equal objects hash equal and unequal ones rarely collide
- Use set operations between sets - they reuse stored hashes instead of calling `__hash__`

❌ **Avoid**:

- A `__hash__` that returns a constant or few distinct values - a dict or set of c keys becomes O(c²)
- An expensive `__hash__` on a class used as a key - it runs on every lookup, and nothing keeps its result
- Integer keys chosen by an untrusted party - int hashes are not salted, so collisions can be forced

## Version Notes

- **Python 3.3+**: `str` and `bytes` hashes vary between processes unless `PYTHONHASHSEED` is set to a number; `int` hashes do not
- **Python 3.14+**: a tuple keeps its hash, so hashing the same tuple again is O(1)

## Related Functions

- **[id()](id.md)** - Object identity (different from hash)
- **[set()](set.md)** - Uses hash for membership
- **[dict](dict.md)** - Uses hash for key lookup
