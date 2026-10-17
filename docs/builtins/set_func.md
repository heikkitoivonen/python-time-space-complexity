# set() Function Complexity

`set()` builds a new, mutable hash set from an iterable, keeping one reference per distinct
element. It consumes the iterable one item at a time without copying it first, and it always
returns a new set, even when the argument is already a set. The operations on the result are on
the [set page](set.md).

`n` is the number of items the argument yields, and `u` is the number of distinct elements among
them, so `u ≤ n`. Hashing and comparing one element is treated as O(1), and the argument is
assumed to be an exact built-in type unless a row names a subclass, as in CPython's own
time-complexity table.

## Complexity Reference

### set

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `set()` | O(1) | O(1) | A new, empty set |
| `set(iterable)` | O(n) avg, O(n²) worst | O(u) | Hashes each item once; the worst case is every hash colliding |
| `set(s)`, `s` a set, frozenset, subclass of either, dict or frozendict | O(n) avg | O(n) | Reuses the hashes stored in `s`, so no element is hashed again. One that had most of its elements removed costs its former size (see [set](set.md)), but the result is compact |

A dict subclass and a dict view such as `d.keys()` are ordinary iterables: each of their elements
is hashed again. frozendict exists from Python 3.15.

## Building a Set

### From Any Iterable

Each item is hashed and inserted as it arrives, so duplicates take no space in the result and a
generator is never turned into a list first.

```python
letters = set("mississippi")                 # O(n) - n = 11 characters
assert letters == {"m", "i", "s", "p"}       # u = 4

repeated = set([7] * 1_000)                  # O(n) time, O(u) space
assert len(repeated) == 1

squares = set(i * i for i in range(10))      # Consumed item by item
assert 81 in squares and len(squares) == 10

assert set() == set([]) == set("")           # O(1) - empty
```

### From a Set or Dict

A set, a frozenset, a dict and a frozendict already store each element's hash, so building from
one copies those hashes instead of calling `__hash__` again. Building from a list of the same
elements hashes every one of them.

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
as_frozenset, as_dict = frozenset(keys), dict.fromkeys(keys)

Key.hash_calls = 0
assert set(as_frozenset) == set(as_dict)     # O(n) - no element rehashed
assert Key.hash_calls == 0

set(keys)                                    # O(n) - hashes every element
assert Key.hash_calls == 100

set(as_dict.keys())                          # A view is an ordinary iterable
assert Key.hash_calls == 200
```

### Copying a Set

`set(s)` is a shallow copy, the same as `s.copy()`: a new set holding the same element objects.
Unlike `frozenset(fs)`, it never hands back its argument.

```python
original = {(1, 2), (3, 4)}
copied = set(original)                       # O(n) - a new set
assert copied == original and copied is not original

copied.add((5, 6))
assert (5, 6) not in original

fs = frozenset(range(10))
assert type(set(fs)) is set                  # O(n) - a mutable copy
```

### Unhashable Elements

Every element must be hashable; an unhashable item raises `TypeError`. A frozenset is hashable,
so it can stand in for a nested set.

```python
try:
    set([(1, 2), [3, 4]])
except TypeError as error:
    assert "unhashable" in str(error)
else:
    raise AssertionError("expected TypeError")

nested = set([frozenset({1, 2}), frozenset({3, 4})])
assert frozenset({2, 1}) in nested
```

## Common Patterns

### Removing Duplicates

`set()` keeps one of each distinct element in O(n), but not their order. When the first-seen order
matters, `dict.fromkeys()` keeps it at the same O(n) cost.

```python
items = [3, 1, 3, 2, 1]

assert set(items) == {1, 2, 3}                    # O(n), order not kept
assert list(dict.fromkeys(items)) == [3, 1, 2]    # O(n), first-seen order
assert len(set(items)) == 3                       # Count the distinct items
```

## Performance Best Practices

✅ **Do**:

- Pass a generator rather than building a list first; the items are consumed one at a time
- Pass a set, frozenset or dict directly; its stored hashes are reused
- Build a set once and reuse it for repeated membership tests, rather than calling `set()` per test

❌ **Avoid**:

- `set(list(s))` for a set `s`, which copies it once and then hashes every element again
- `set(d.keys())` where `set(d)` will do; the view's elements are hashed again
- Expecting `set()` to keep insertion order; use `dict.fromkeys()` for that

## Related Functions

- **[set](set.md)** - The operations on a set once it is built
- **[frozenset()](frozenset_func.md)** - The immutable counterpart, built in the same O(n)
- **[dict()](dict_func.md)** - Builds a mapping from pairs or keyword arguments
- **[list()](list_func.md)** - Builds a list, keeping order and duplicates
