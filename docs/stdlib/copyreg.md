# copyreg Module Complexity

The `copyreg` module holds the registries that `pickle` and `copy` consult: `dispatch_table`,
which maps a type to the function that reduces its instances, and the extension-code tables,
which let a pickle name a global by a small integer instead of its module and name. Every
registry is a dict, so registering, removing and looking up an entry each take a fixed number of
dict operations.

Hashing a type or a `(module, name)` key is treated as O(1). `c` is the objects in the extension
cache. A registered reduction function's own cost is the caller's and is not priced here: `pickle`
adds one call to it per distinct object of its type.

## Complexity Reference

### Reduction functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copyreg.pickle(type, function)` | O(1) | O(1) | One `dispatch_table` entry for exactly `type`; raises `TypeError` unless `function` is callable |
| `copyreg.constructor(object)` | O(1) | O(1) | Only checks that `object` is callable; it registers nothing |
| `copyreg.dispatch_table` | O(1) | O(1) | The dict itself; `pickle` and `copy` read this same object, so editing it registers or unregisters |

### Extension codes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copyreg.add_extension(module, name, code)` | O(1) | O(1) | Two dict entries; `ValueError` if `code` is outside 1 to 2³¹ - 1 or either side is registered to something else |
| `copyreg.remove_extension(module, name, code)` | O(1) | O(1) | Also drops the cached object; `ValueError` unless that exact pair is registered |
| `copyreg.clear_extension_cache()` | O(c) | O(1) | c = cached objects; the next unpickle of each code looks its global up again |

### Built-in reducers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copyreg.pickle_complex(obj)` | O(1) | O(1) | Registered for `complex` |
| `copyreg.pickle_union(obj)` | O(1) | O(1) | Registered for `X \| Y` unions; returns the union's own `__args__` tuple |
| `copyreg.pickle_super(obj)` | O(1) | O(1) | Python 3.14+; registered for `super` |

## Registering a Reducer

A reduction function returns a callable and its arguments, which is what the pickle stores and
what unpickling calls. Registering one is a dict entry. `pickle` then calls it once for each
distinct object of that type, because it memoizes an object it has already written; `copy`
consults the same table.

```python
import copy
import copyreg
import pickle

class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

calls = []

def reduce_point(point):
    calls.append(point)
    return Point, (point.x, point.y)

copyreg.pickle(Point, reduce_point)  # O(1) - one dispatch_table entry
assert copyreg.dispatch_table[Point] is reduce_point

point = Point(1, 2)
restored = pickle.loads(pickle.dumps([point, point]))  # one reducer call for both
assert len(calls) == 1
assert restored[0] is restored[1] and (restored[0].x, restored[0].y) == (1, 2)

clone = copy.deepcopy(point)  # copy consults the same table
assert len(calls) == 2 and clone.y == 2

del copyreg.dispatch_table[Point]  # O(1) - unregister
```

### What the Registry Does Not Reach

The lookup is by exact type, so a subclass needs its own entry. A `Pickler` given its own
`dispatch_table` uses that instead of `copyreg.dispatch_table`, not as well as it. And `int`,
`str`, `list`, `dict` and the other types `pickle` writes directly never reach the table.

```python
import copyreg
import io
import pickle

class Base:
    pass

class Derived(Base):
    pass

calls = []

def reduce_base(obj):
    calls.append(obj)
    return Base, ()

copyreg.pickle(Base, reduce_base)

pickle.dumps(Base())
assert len(calls) == 1
pickle.dumps(Derived())  # not looked up under Base
assert len(calls) == 1

pickler = pickle.Pickler(io.BytesIO())
pickler.dispatch_table = {}  # a private table replaces the global one
pickler.dump(Base())
assert len(calls) == 1

copyreg.pickle(list, reduce_base)
assert pickle.loads(pickle.dumps([1, 2])) == [1, 2]  # written directly, entry ignored
assert len(calls) == 1
del copyreg.dispatch_table[list], copyreg.dispatch_table[Base]
```

## Extension Codes

With protocol 2 or later, a global that has an extension code is written as that code rather than
as its module and name. Unpickling looks the code up and caches the object it resolves to, so a
repeated code costs one dict lookup. The registry is process-wide and both sides of a pickle must
agree on it; codes 240 to 255 are reserved for private use.

```python
import collections
import copyreg
import pickle

by_name = pickle.dumps(collections.OrderedDict, protocol=2)

copyreg.add_extension('collections', 'OrderedDict', 240)  # O(1)
by_code = pickle.dumps(collections.OrderedDict, protocol=2)
assert len(by_code) < len(by_name)
assert pickle.loads(by_code) is collections.OrderedDict  # resolved, then cached

copyreg.add_extension('collections', 'OrderedDict', 240)  # same pair again: no-op
try:
    copyreg.add_extension('collections', 'deque', 240)
except ValueError as error:
    assert 'already in use' in str(error)
else:
    raise AssertionError('a code was registered twice')

copyreg.clear_extension_cache()  # O(c)
assert pickle.loads(by_code) is collections.OrderedDict  # looked up again

copyreg.remove_extension('collections', 'OrderedDict', 240)  # O(1)
try:
    pickle.loads(by_code)
except ValueError as error:
    assert 'unregistered extension code' in str(error)
else:
    raise AssertionError('an unregistered code was resolved')
```

## The Built-in Reducers

The module registers reducers of its own when it is imported. Each returns the callable and
arguments that rebuild its object.

```python
import copyreg

assert copyreg.dispatch_table[complex] is copyreg.pickle_complex
assert copyreg.pickle_complex(1 + 2j) == (complex, (1.0, 2.0))  # O(1)

union = int | str
assert copyreg.dispatch_table[type(union)] is copyreg.pickle_union
assert copyreg.pickle_union(union)[1][-1] is union.__args__  # O(1) - not a copy
```

## Performance Best Practices

✅ **Do**:

- Give a `Pickler` its own `dispatch_table` when one serializer needs custom reduction; the global
  table changes `pickle` and `copy` for the whole process
- Register a subclass as well as its base when both should use the reducer
- Keep a reduction function cheap: it runs once per distinct object pickled

❌ **Avoid**:

- `copyreg.constructor()` as a registration step - it only checks that its argument is callable
- Registering a reducer for `list`, `dict`, `int` or `str` - `pickle` never consults it
- Assigning an extension code that the unpickling process does not also register

## Version Notes

- **Python 3.14+**: Added `pickle_super`, so `super` objects can be pickled and copied

## Related Modules

- **[pickle](pickle.md)** - The serializer that consults these registries; `Pickler.dispatch_table`
  overrides the global one
- **[copy](copy.md)** - `copy()` and `deepcopy()` consult `dispatch_table` too
- **[pickletools](pickletools.md)** - Disassemble a pickle to see an extension code in place of a name
