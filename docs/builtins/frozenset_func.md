# frozenset() Function Complexity

`frozenset()` builds an immutable hash set from an iterable, keeping one reference per distinct
element. It consumes the iterable one item at a time without copying it first, and an argument that
is already an exact `frozenset` is returned unchanged. The operations on the result are on the
[frozenset page](frozenset.md).

`n` is the number of items the argument yields, and `u` is
the number of distinct elements among them, so `u ≤ n`. Hashing and comparing one element is
treated as O(1), and the argument is assumed to be an exact built-in type unless a row names a
subclass, as in CPython's own time-complexity table.

## Complexity Reference

### frozenset

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `frozenset()` | O(1) | O(1) | |
| `frozenset(iterable)` | O(n) avg, O(n²) worst | O(u) | Hashes each item once; the worst case is every hash colliding |
| `frozenset(s)`, `s` a set, frozenset subclass, dict or frozendict | O(n) avg | O(n) | Reuses the hashes stored in `s`, so no element is hashed again. One that had most of its elements removed costs its former size (see [set](set.md)) |
| `frozenset(fs)`, `fs` an exact frozenset | O(1) | O(1) | Returns `fs` itself |

## Building a Frozenset

### From Any Iterable

Each item is hashed and inserted as it arrives, so duplicates take no space in the result and a
generator is never turned into a list first.

```python
words = frozenset("mississippi")              # O(n) - n = 11 characters
assert words == {"m", "i", "s", "p"}          # u = 4

repeated = frozenset([7] * 1_000)             # O(n) time, O(u) space
assert len(repeated) == 1

squares = frozenset(i * i for i in range(10))  # Consumed item by item
assert 81 in squares and len(squares) == 10

assert frozenset() == frozenset([]) == frozenset("")  # O(1) - empty
```

### From a Set or Dict

A set, a frozenset subclass, a dict and a frozendict (Python 3.15+) already store each element's
hash, so building from one
copies those hashes instead of calling `__hash__` again. Building from a list of the same elements
hashes every one of them.

```python
class Key:
    hash_calls = 0

    def __init__(self, value):
        self.value = value

    def __hash__(self):
        Key.hash_calls += 1
        return hash(self.value)

    def __eq__(self, other):
        return isinstance(other, Key) and self.value == other.value

keys = [Key(i) for i in range(100)]
as_set, as_dict = set(keys), dict.fromkeys(keys)

Key.hash_calls = 0
assert frozenset(as_set) == frozenset(as_dict)  # O(n) - no element rehashed
assert Key.hash_calls == 0

frozenset(keys)                                 # O(n) - hashes every element
assert Key.hash_calls == 100
```

### From a Frozenset

A frozenset cannot change, so `frozenset(fs)` hands back `fs` itself. An instance of a subclass is
copied into a new, plain frozenset.

```python
fs = frozenset(range(1_000))
assert frozenset(fs) is fs                     # O(1) - the same object

class Tagged(frozenset):
    pass

tagged = Tagged(range(1_000))
plain = frozenset(tagged)                      # O(n) - a new frozenset
assert plain is not tagged and plain == tagged
assert type(plain) is frozenset
```

### Unhashable Elements

Every element must be hashable; an unhashable item raises `TypeError`.

```python
try:
    frozenset([(1, 2), [3, 4]])
except TypeError as error:
    assert "unhashable" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Common Patterns

### Keys for Unordered Collections

A frozenset compares equal to any other frozenset with the same elements, whatever order they were
given in, which makes it a key for grouping unordered collections. Each frozenset computes its hash
in O(u) on first use and stores it, so reusing the same key object does not hash it again.

```python
orders = [["tea", "milk"], ["milk", "tea"], ["coffee"], ["tea", "milk", "tea"]]

counts = {}
for items in orders:
    key = frozenset(items)                     # O(n) per order
    counts[key] = counts.get(key, 0) + 1       # O(u) hash on first use

assert counts == {frozenset({"tea", "milk"}): 3, frozenset({"coffee"}): 1}
```

## Performance Best Practices

✅ **Do**:

- Pass a generator rather than building a list first; the items are consumed one at a time
- Pass a set or dict directly; its stored hashes are reused
- Pass an existing frozenset freely; `frozenset(fs)` is O(1) and returns `fs`

❌ **Avoid**:

- `frozenset(list(s))` for a set `s`, which copies it once and then hashes every element again
- Expecting `frozenset()` of a frozenset subclass instance to be free; it is copied in O(n)

## Related Functions

- **[frozenset](frozenset.md)** - The operations on a frozenset once it is built
- **[set()](set_func.md)** - The mutable counterpart, built in the same O(n)
- **[set](set.md)** - Hash table behaviour shared by both types
- **[hash()](hash.md)** - What hashing a frozenset costs
