# dict() Function Complexity

`dict()` builds a new dictionary from nothing, from a mapping, from an iterable of key-value
pairs, from keyword arguments, or from a positional source and keyword arguments together. It
always builds a new object, and the copy is shallow: keys and values are shared with the source,
not copied. What the resulting dict costs to use is on the [dict](dict.md) page.

`n` is the items the positional argument supplies - the pairs an iterable yields, or the keys of a
mapping - and `m` is the keyword arguments. Times are average case and treat hashing and
comparing a key as O(1), as CPython's own time-complexity table does. When every key hashes to the
same value, each insertion costs O(n) instead, so building from n pairs costs O(n²). Iterating the
argument, and a mapping's own `keys()` and `__getitem__`, cost whatever they cost on top.

## Complexity Reference

### dict()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dict()` | O(1) | O(1) | An empty dict |
| `dict(iterable)` | O(n) | O(n) | Each item must be a two-item iterable; a repeated key keeps its first position and its last value |
| `dict(d)` where `d` is a dict | O(n) | O(n) | Same as `d.copy()`: a source that had most of its items deleted costs its former size (see [dict](dict.md)) |
| `dict(mapping)` where `mapping` is not a dict but has `keys()` | O(n) | O(n) | Calls `keys()` once and `mapping[key]` once per key |
| `dict(**kwargs)` | O(m) | O(m) | Keys must be strings |
| `dict(source, **kwargs)` | O(n + m) | O(n + m) | Keyword arguments are applied after `source` and replace its values for the same key |

## Building a Dictionary

### From Pairs

Any iterable of two-item iterables works, so `zip()` and `enumerate()` feed `dict()` directly. Each
pair is one insertion.

```python
keys = ["a", "b", "c"]
values = [1, 2, 3]

d = dict(zip(keys, values))  # O(n)
assert d == {"a": 1, "b": 2, "c": 3}

assert dict(enumerate("xy")) == {0: "x", 1: "y"}  # O(n)
assert dict([("x", 10), ("y", 20)]) == {"x": 10, "y": 20}
assert dict() == {}  # O(1)
```

A repeated key overwrites the value but keeps the position the key was first inserted at. An item
that does not have exactly two elements raises.

```python
d = dict([("a", 1), ("b", 2), ("a", 3)])  # O(n)
assert d == {"a": 3, "b": 2}
assert list(d) == ["a", "b"]

try:
    dict([("a", 1, 2)])
except ValueError as error:
    assert "2 is required" in str(error)
else:
    raise AssertionError("expected ValueError")

try:
    dict([([1, 2], "value")])  # A list is not hashable
except TypeError as error:
    assert "unhashable" in str(error)
else:
    raise AssertionError("expected TypeError")
```

### From Keyword Arguments

Keyword arguments are applied after the positional source, so they win for a shared key. Their
keys must be strings, and each name can be passed only once.

```python
assert dict(a=1, b=2) == {"a": 1, "b": 2}  # O(m)

base = {"a": 1, "b": 2}
d = dict(base, a=3)  # O(n + m)
assert d == {"a": 3, "b": 2}
assert base == {"a": 1, "b": 2}

try:
    dict(**{1: "one"})
except TypeError as error:
    assert "keywords must be strings" in str(error)
else:
    raise AssertionError("expected TypeError")

try:
    dict(**{"a": 1}, **{"a": 2})
except TypeError as error:
    assert "multiple values" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Copying

### Copying a Dictionary

`dict(d)` costs what `d.copy()` does. The copy is shallow: a mutable value is shared by both
dicts, and `copy.deepcopy()` is the way to get independent values.

```python
import copy

inner = {"x": 1}
outer = {"a": inner}

shallow = dict(outer)  # O(n)
assert shallow == outer and shallow is not outer
assert shallow["a"] is inner
shallow["a"]["x"] = 999
assert outer["a"]["x"] == 999

deep = copy.deepcopy(outer)
assert deep["a"] is not inner
```

### Copying Another Mapping

An object that is not a dict but has a `keys()` method is read as a mapping: `keys()` is called
once, then the object is indexed once per key.

```python
class Mapping:
    def __init__(self, data):
        self.data = data
        self.lookups = 0

    def keys(self):
        return self.data.keys()

    def __getitem__(self, key):
        self.lookups += 1
        return self.data[key]

source = Mapping({"a": 1, "b": 2, "c": 3})
assert dict(source) == {"a": 1, "b": 2, "c": 3}  # O(n)
assert source.lookups == 3
```

## Common Patterns

### Merging Dictionaries

`dict(a, **b)` only works when every key of `b` is a string, and `dict(**a, **b)` also raises on a
key the two share. `a | b` and `{**a, **b}` take any keys, and the right-hand value wins. Each
costs O(len(a) + len(b)).

```python
a = {"x": 1, 1: "one"}
b = {"y": 2, "x": 3}

merged = a | b  # O(len(a) + len(b))
assert merged == {"x": 3, 1: "one", "y": 2}
assert {**a, **b} == merged
assert dict(a, **b) == merged  # Every key of b is a string

try:
    dict(**a, **b)
except TypeError:
    pass  # 1 is not a string, and "x" is in both
else:
    raise AssertionError("expected TypeError")
```

## Performance Best Practices

✅ **Do**:

- Pass `zip()` or a generator straight to `dict()`; a list of pairs built first holds every pair
  as well as the dict
- Copy with `dict(d)` or `d.copy()`; both cost O(n)
- Merge with `a | b` or `{**a, **b}` when keys may not be strings

❌ **Avoid**:

- `dict(**mapping)` to copy: it rejects non-string keys, which `dict(mapping)` accepts
- Relying on `dict()` for independent values: the copy is shallow

## Related Functions

- **[dict](dict.md)** - What the dict you built costs to use, including `dict.fromkeys()`
- **[frozendict](frozendict.md)** - The immutable mapping (Python 3.15+)
- **[list()](list_func.md)** - Convert to list
- **[set()](set_func.md)** - Convert to set
- **[zip()](zip.md)** - Pair up iterables
