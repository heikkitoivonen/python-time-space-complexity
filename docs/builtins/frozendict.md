# frozendict Type Complexity

A `frozendict` is an immutable mapping, new in Python 3.15. It is the same hash table as a
[`dict`](dict.md), keeps insertion order the same way, and answers lookups at the same cost, but
nothing can be added, changed or removed once it is built. It is not a subclass of `dict`. It is
hashable when every value is, and it computes that hash once and caches it.

`n` is the number of items in the frozendict, and `m` is the number of items in the other operand:
the mapping or iterable it is built from, or the right-hand side of `|`. Key hashing and comparison
are treated as O(1), and so are hashing and comparing a value: a value that is itself a large
container adds its own cost to `hash(fd)` and `==`. As with `dict`, the O(1) lookups are average
cases: if every key hashes to the same value, each one instead takes O(n).

## Complexity Reference

### frozendict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `frozendict()` | O(1) | O(1) | Empty |
| `frozendict(mapping)`, `frozendict(iterable)`, `frozendict(**kwargs)` | O(m) | O(m) | One insertion per pair; a repeated key keeps the last value. A `dict` that had most of its items deleted costs its former size (see [dict](dict.md)) |
| `frozendict(fd)` | O(1) | O(1) | Returns `fd` itself when both are exact `frozendict`s |
| `frozendict.fromkeys(iterable, value=None)` | O(m) | O(m) | Every key maps to the same `value` object |
| `fd[key]`, `fd.get(key, default=None)` | O(1) avg, O(n) worst | O(1) | `fd[key]` raises `KeyError` for a missing key |
| `key in fd` | O(1) avg, O(n) worst | O(1) | |
| `len(fd)` | O(1) | O(1) | The count is stored |
| Iterating `fd`, `reversed(fd)` | O(n) | O(1) | Insertion order, or its reverse |
| `fd.keys()`, `fd.values()`, `fd.items()` | O(1) | O(1) | Views; iterating one is O(n) |
| `fd.copy()` | O(1) | O(1) | Returns `fd` itself; an instance of a subclass is copied in O(n) |
| `hash(fd)` | O(n) first call, O(1) after | O(1) | Hashes every value once and caches the result; raises `TypeError` if a value is unhashable |
| `fd == other`, `fd != other` | O(n) | O(1) | Equal to a `dict` with the same items; order is ignored. O(1) when the lengths differ |
| `fd \| other` | O(n + m) | O(n + m) | `other` must be a `dict` or `frozendict`; the result is a `frozendict`, while `dict \| fd` is a `dict` |
| `fd \|= other` | O(n + m) | O(n + m) | Not in place: rebinds the name to `fd \| other`, and the original object never changes |
| `dict(fd)` | O(n) | O(n) | A mutable copy |
| `fd[key] = value`, `del fd[key]` | O(1) | O(1) | Raise `TypeError`; there is no `update()`, `pop()`, `setdefault()` or `clear()` |

## Building a frozendict

Construction copies every pair once, the same as building a `dict`. Passing a frozendict that is
already exact costs nothing, because the constructor and `copy()` both hand back the same
object.

```python
settings = frozendict({'host': 'localhost', 'port': 8080})  # O(m)
assert settings['port'] == 8080                               # O(1)

assert frozendict(settings) is settings  # O(1) - no copy
assert settings.copy() is settings       # O(1) - no copy

flags = frozendict.fromkeys(['debug', 'verbose'], False)  # O(m)
assert flags == {'debug': False, 'verbose': False}        # O(n), equal to a dict

try:
    settings['port'] = 9090
except TypeError as error:
    assert 'does not support item assignment' in str(error)
else:
    raise AssertionError('a frozendict cannot be changed')
```

## Hashing

`hash(fd)` combines the hash of every key and value, so the first call is O(n). The result is
stored on the object and every later call returns it in O(1), so a frozendict used repeatedly as
a dictionary key or set member pays the O(n) once. The hash ignores insertion order, as equality
does.

```python
a = frozendict(x=1, y=2)
b = frozendict(y=2, x=1)

assert a == b                  # O(n) - order is ignored
assert hash(a) == hash(b)      # O(n) each, the first time
cache = {a: 'computed'}        # O(1) - the hash is already cached
assert cache[b] == 'computed'  # O(1) hash, then an O(n) equality check

try:
    hash(frozendict(tags=['a', 'b']))  # a list value is unhashable
except TypeError as error:
    assert 'unhashable' in str(error)
else:
    raise AssertionError('an unhashable value must make hash() fail')
```

## Merging With |

`|` copies the left operand and then inserts every item of the right, so it is O(n + m) whichever
side is larger. The result has the left operand's type. A frozendict has no in-place update, so
`|=` falls back to `|`: it builds a new frozendict and rebinds the name, and any other reference
still sees the original.

```python
defaults = frozendict(color='red', size=10)
overrides = {'size': 12}

merged = defaults | overrides  # O(n + m)
assert type(merged) is frozendict and merged['size'] == 12
assert type(overrides | defaults) is dict  # the left operand decides

current = defaults
current |= overrides           # O(n + m) - a new object, not an update
assert current is not defaults
assert defaults['size'] == 10
```

## Common Patterns

### Caching on a Mapping Argument

A `dict` cannot be a cache key, but a frozendict can, and its cached hash keeps repeated lookups
from rehashing it.

```python
from functools import lru_cache

calls = 0

@lru_cache(maxsize=128)
def render(options):
    global calls
    calls += 1
    return ', '.join(f'{k}={v}' for k, v in sorted(options.items()))  # O(n log n)

options = frozendict(width=80, indent=2)
assert render(options) == 'indent=2, width=80'  # computed once
assert render(options) == 'indent=2, width=80'  # O(1) cache hit
assert calls == 1
```

## Performance Best Practices

✅ **Do**:

- Pass a frozendict where an immutable mapping is wanted: `frozendict(fd)` and `fd.copy()` are
  free, where a defensive `dict` copy is O(n)
- Use a frozendict as a dictionary key or set member when the key is naturally a mapping; its
  hash is computed once

❌ **Avoid**:

- Building a frozendict up with repeated `|=` - each step copies everything so far, so k
  additions cost O(k²); build a `dict` and freeze it once
- Hashing a frozendict whose values are unhashable - the `TypeError` comes at `hash()` time, not
  when the frozendict is built

## Version Notes

- **Python 3.15+**: `frozendict` added ([PEP 814](https://peps.python.org/pep-0814/){ target="_blank" rel="noopener" }:material-open-in-new:)

## Related Types

- **[dict](dict.md)** - The mutable mapping with the same lookup costs
- **[frozenset](frozenset.md)** - The immutable set, which also returns itself from `copy()`
- **[types.MappingProxyType](../stdlib/types.md)** - A read-only view of a
  mapping that can still change underneath, in O(1) without a copy
