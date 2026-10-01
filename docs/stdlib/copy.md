# copy Module Complexity

The `copy` module makes shallow copies, which build one new container holding the same objects, and
deep copies, which walk everything reachable from the original and copy each object at most once.
Neither copies a string, a number or a bytes object: they are returned as they are.

For `copy.copy()`, `n` is the items in the object's top level: the elements of a list, dict, set or
bytearray, or the attributes of an instance. For `copy.deepcopy()`, `v` is the distinct objects
reachable from the original, and `e` is the references it follows to reach them: every element,
key, value and attribute of every copied object, so an object referenced from ten places counts
once in `v` and ten times in `e`. Hashing and dictionary lookups are treated as O(1). The instance
bounds are for the default pickle reduction; a custom `__copy__`, `__deepcopy__`,
`__reduce_ex__`, `__getstate__` or `__setstate__`, or a `copyreg` reducer, adds whatever it costs.

## Complexity Reference

### copy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copy.copy(x)`, list, dict, set or bytearray | O(n) | O(n) | A new container holding the same elements |
| `copy.copy(x)`, instance of a class | O(n) | O(n) | n = attributes; a new instance whose attributes are the same objects, built without calling `__init__` |
| `copy.copy(x)`, immutable | O(1) | O(1) | `str`, `bytes`, `tuple`, `frozenset`, numbers, functions and classes are returned unchanged |

### deepcopy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copy.deepcopy(x, memo=None)` | O(v + e) | O(v + e) | Each reachable object is copied once, so shared references and cycles survive; the memo holds every copied object. A shared tuple can cost more, below |
| `copy.deepcopy(x)`, immutable leaf | O(1) | O(1) | `str`, `bytes`, numbers, functions and classes are returned unchanged |
| `copy.deepcopy(x)`, tuple | O(k) per reference | O(k) | k = the tuple's length, plus its elements' own copying. When nothing inside needed copying the original is returned and not memoized, so each reference to it scans it again |

### replace

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copy.replace(obj, /, **changes)` | O(r) | O(r) | Python 3.13+; r = cost of the type's `__replace__`. Named tuples and dataclasses build the new object from every field, not only the changed ones |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copy.Error`, `copy.error` | O(1) | O(1) | `error` is an alias; raised only for an object with no `__reduce_ex__` or `__reduce__`. Locks, generators and other objects whose reduction refuses raise `TypeError` instead |

## Shallow vs Deep Copy

### Shallow Copy

A shallow copy is one new container. The objects inside it are the original's, so mutating a
nested list through the copy changes the original too.

```python
import copy

original = [[1, 2], [3, 4]]

shallow = copy.copy(original)  # O(n), n = 2 top-level elements

assert shallow is not original
assert shallow[0] is original[0]  # the nested lists are shared

shallow[0][0] = 999
assert original == [[999, 2], [3, 4]]
```

### Deep Copy

A deep copy visits every object reachable from the original. Its cost is the size of the whole
structure, not the length of the top level.

```python
import copy

original = [[1, 2], [3, 4]]

deep = copy.deepcopy(original)  # O(v + e) - every list and every reference

assert deep[0] is not original[0]  # the nested lists are new

deep[0][0] = 999
assert original == [[1, 2], [3, 4]]
assert deep == [[999, 2], [3, 4]]
```

## Immutable Objects

`copy.copy()` returns a string, bytes, tuple, frozenset, number, function or class as it is, at
O(1) whatever its size, and `copy.deepcopy()` does the same for all of them but tuples and
frozensets. A deep copy returns a tuple unchanged when nothing inside it needed copying, but it has
to look at every element to find that out, and it does so again at every reference to that tuple.

```python
import copy

text = "x" * 1_000_000
assert copy.copy(text) is text      # O(1) - no characters are copied
assert copy.deepcopy(text) is text  # O(1)

point = (1, 2, 3)
assert copy.copy(point) is point      # O(1)
assert copy.deepcopy(point) is point  # O(k) - checks each element first

nested = ([1], 2)
copied = copy.deepcopy(nested)  # the list inside forces a new tuple
assert copied is not nested and copied[0] is not nested[0]
```

## Object Graphs

### Shared References and Cycles

`deepcopy()` keeps a memo of every object it has copied during the call. An object
reached twice is copied once and the copy is reused, so sharing in the original is preserved in the
copy, and a cycle ends at the second visit instead of recursing forever.

```python
import copy

inner = [1, 2]
outer = [inner, inner]

deep = copy.deepcopy(outer)  # O(v + e): inner is copied once
assert deep[0] is deep[1]
assert deep[0] is not inner

circular = [1, 2, 3]
circular.append(circular)

deep = copy.deepcopy(circular)  # terminates: the memo finds the list on the second visit
assert deep[3] is deep
```

### Nesting Depth

Deep copying recurses once per level of nesting. A structure nested a few hundred levels deep
raises `RecursionError` at the default recursion limit, however few objects it holds.

```python
import copy

shallow_nest = []
for _ in range(100):
    shallow_nest = [shallow_nest]
copy.deepcopy(shallow_nest)  # O(v + e), v = 101

deep_nest = []
for _ in range(2_000):
    deep_nest = [deep_nest]

try:
    copy.deepcopy(deep_nest)
except RecursionError:
    pass
else:
    raise AssertionError('2,000 levels of nesting were deep copied')
```

## Custom Objects

### Instances

An instance without copy hooks is copied through the pickle protocol: `copy.copy()` builds a new
instance and fills it with the original's attributes, which is O(n) in the attribute count.
`copy.deepcopy()` then deep copies each attribute.

```python
import copy

class Person:
    def __init__(self, name, tags):
        self.name = name
        self.tags = tags

original = Person("Alice", ["admin"])

shallow = copy.copy(original)  # O(n), n = 2 attributes
assert shallow is not original
assert shallow.tags is original.tags  # the attribute values are shared

deep = copy.deepcopy(original)  # O(v + e)
assert deep.tags == ["admin"] and deep.tags is not original.tags
```

### Copy Hooks

A class can define `__copy__` and `__deepcopy__` to decide what is copied. `__deepcopy__` receives
the memo and must pass it on to any `deepcopy()` it calls, or objects shared inside the object are
copied more than once.

```python
import copy

class Document:
    def __init__(self, body, cache=None):
        self.body = body
        self.cache = cache if cache is not None else {}

    def __copy__(self):
        return Document(self.body)  # O(1): the cache is not carried over

    def __deepcopy__(self, memo):
        return Document(copy.deepcopy(self.body, memo))  # passes the memo on

doc = Document(["intro", "summary"], cache={'rendered': '...'})

shallow = copy.copy(doc)
assert shallow.body is doc.body and shallow.cache == {}

deep = copy.deepcopy(doc)
assert deep.body == doc.body and deep.body is not doc.body
```

### Objects That Cannot Be Copied

An object without copy hooks is copied through its pickle reduction. Where that refuses, as it
does for locks and generators, the error is the reduction's `TypeError`, not `copy.Error`.

```python
import copy
import threading

try:
    copy.deepcopy({'lock': threading.Lock()})
except TypeError as error:
    assert 'lock' in str(error)
else:
    raise AssertionError('a lock was copied')
```

## Replacing Fields

`copy.replace()` (Python 3.13+) builds a new object with some fields changed, for any type that
defines `__replace__`: named tuples, dataclasses, `datetime` objects and
`types.SimpleNamespace` among them. A named tuple or dataclass builds the new object from every
field, so the cost follows the field count, not the number of changes.

```python
import copy
from collections import namedtuple
from dataclasses import dataclass

Point = namedtuple('Point', ['x', 'y'])
p = Point(1, 2)
assert copy.replace(p, x=10) == Point(10, 2)  # O(r) - rebuilds both fields

@dataclass(frozen=True)
class Config:
    timeout: int
    retries: int

config = Config(timeout=30, retries=3)
updated = copy.replace(config, retries=5)  # O(r)
assert updated == Config(timeout=30, retries=5) and config.retries == 3

try:
    copy.replace([1, 2])
except TypeError as error:
    assert 'does not support list' in str(error)
else:
    raise AssertionError('a list was replaced')
```

## Common Patterns

### Copying a Configuration Before Changing It

A copy of a nested configuration needs to be deep when the nested parts will change. Copying only
the part you change keeps the cost to that part.

```python
import copy

defaults = {'timeout': 30, 'retry': {'count': 3, 'backoff': [1, 2, 4]}}

# Deep: O(v + e) over the whole configuration
custom = copy.deepcopy(defaults)
custom['retry']['backoff'].append(8)
assert defaults['retry']['backoff'] == [1, 2, 4]

# Targeted: copy the top level and the one branch that changes
targeted = copy.copy(defaults)                     # O(n)
targeted['retry'] = copy.deepcopy(defaults['retry'])  # O(v + e) of that branch only
targeted['retry']['count'] = 5
assert defaults['retry']['count'] == 3
```

### Shallow Copy Without the Module

For a list, `copy.copy()`, `list.copy()`, the `list()` constructor and slicing all make the same
O(n) shallow copy.

```python
import copy

data = [1, 2, 3]

assert copy.copy(data) == data.copy() == list(data) == data[:]  # each O(n)
assert copy.copy(data) is not data
```

## Performance Best Practices

✅ **Do**:

- Use a shallow copy when the nested objects are immutable or will not change: it costs the top level only
- Deep copy only the branch you are about to change, rather than the whole structure
- Pass `memo` on to `deepcopy()` from a custom `__deepcopy__`, so shared objects are still copied once

❌ **Avoid**:

- Copying a string, tuple or other built-in immutable to protect it - `copy.copy()` returns the same object
- `deepcopy()` on deeply nested data - it recurses once per level and raises `RecursionError` a few hundred levels down
- Calling `deepcopy()` repeatedly on a large structure that never changes; share it instead

## Version Notes

- **Python 3.13+**: Added `copy.replace()` and the `__replace__` protocol

## Related Modules

- **[copyreg](copyreg.md)** - `copyreg.pickle()` registers a reduction function that `copy()` and `deepcopy()` also use
- **[pickle](pickle.md)** - The protocol `copy` falls back on for instances without copy hooks
- **[dataclasses](dataclasses.md)** - `dataclasses.replace()` and `__replace__` for `copy.replace()`
