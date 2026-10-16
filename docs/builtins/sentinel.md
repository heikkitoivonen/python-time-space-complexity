# sentinel Type Complexity

The `sentinel` type, new in Python 3.15, makes a unique marker value such as `MISSING`: an object
that stands for "no argument given" where `None` is itself a valid argument. Each call returns a
new object that is equal only to itself, keeps the name it was given for its representation, and
survives copying and pickling as the same object. The object holds three references - its name,
its optional representation, and the name of the module that created it - and copies none of
them.

Almost every operation acts on that one fixed-size object, so most rows have no size variable.
`k` is the characters in the sentinel's module name and qualified name, which pickling writes and
reads back, and `u` is the members of a `typing.Union` built with `|`. Hashing and comparing the
members of a union is treated as O(1).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sentinel(name, /, *, repr=None)` | O(1) | O(1) | Keeps `name` and `repr` themselves, not copies, and records the calling module's name; `name` must be a `str` and `repr` a `str` or `None` |
| `repr(s)`, `str(s)` | O(1) | O(1) | Return the stored `repr` string itself, or the name when no `repr` was given |
| `s is MISSING` | O(1) | O(1) | The intended test; two calls with the same name make two different sentinels |
| `s == other`, `s != other` | O(1) | O(1) | Equal only to itself, unless the other operand's `__eq__` answers, at that method's cost |
| `hash(s)` | O(1) | O(1) | Hashed by identity, so it can be a dict key or a set member |
| `bool(s)` | O(1) | O(1) | Always `True` |
| `s.__name__`, `s.__module__` | O(1) | O(1) | `__name__` is read-only; `__module__` can be reassigned, which changes where pickling looks |
| `copy.copy(s)`, `copy.deepcopy(s)` | O(1) | O(1) | Return `s` itself |
| `pickle.dumps(s)`, `pickle.loads(data)` | O(k) | O(k) | Pickled by reference, as its module and name; loading returns the same object. Only a sentinel stored under its own name at module level, or under its qualified name in a class, can be pickled; loading imports its module first if nothing has, at that import's cost |
| `s \| t`, `t \| s` | O(u) | O(u) | A `typing.Union` of both operands' members, hashed to drop duplicates; `s \| s` is `s` |
| `type(s)`, `isinstance(x, sentinel)` | O(1) | O(1) | The type cannot be subclassed |

## Marking a Missing Argument

A sentinel is the default that no caller can pass by accident. Testing for it is one identity
comparison, and the object prints as the name it was given.

```python
MISSING = sentinel('MISSING')  # O(1)

def lookup(table, key, default=MISSING):
    value = table.get(key, MISSING)  # O(1) average
    if value is MISSING:             # O(1) - identity
        if default is MISSING:
            raise KeyError(key)
        return default
    return value

assert lookup({'a': None}, 'a') is None  # None is a real value here
assert lookup({}, 'a', 0) == 0
try:
    lookup({}, 'a')
except KeyError as error:
    assert error.args == ('a',)
else:
    raise AssertionError('a missing key was found')

assert repr(MISSING) == 'MISSING'           # O(1) - the name it was given
assert sentinel('MISSING') is not MISSING   # every call makes a new one
assert MISSING != sentinel('MISSING')
assert bool(MISSING) is True

NOT_SET = sentinel('NOT_SET', repr='<not set>')
assert repr(NOT_SET) == '<not set>'          # O(1) - the stored string
assert NOT_SET.__name__ == 'NOT_SET'
```

## Copying and Pickling

Copies are the object itself, and pickling stores a reference rather than a value: the module and
name are written, and loading looks them up again, so `is` still holds afterwards. That lookup is
why a sentinel must be reachable under its own name - one made inside a function and kept there
cannot be pickled.

```python
import copy
import pickle

PICKLABLE = sentinel('PICKLABLE')

assert copy.copy(PICKLABLE) is PICKLABLE       # O(1)
assert copy.deepcopy(PICKLABLE) is PICKLABLE   # O(1)
assert pickle.loads(pickle.dumps(PICKLABLE)) is PICKLABLE  # O(k)

class Config:
    UNSET = sentinel('Config.UNSET')  # the qualified name, for pickling

assert pickle.loads(pickle.dumps(Config.UNSET)) is Config.UNSET

def make():
    return sentinel('LOCAL')

try:
    pickle.dumps(make())
except pickle.PicklingError as error:
    assert 'LOCAL' in str(error)
else:
    raise AssertionError('a sentinel no module can find was pickled')
```

## Sentinels in Type Hints

`|` builds a `typing.Union`, as it does for classes, so a sentinel can appear in an annotation.
Building the union hashes each member to drop duplicates, which is the O(u).

```python
import typing

MISSING = sentinel('MISSING')

def next_value(default: int | MISSING = MISSING) -> int:
    return 0 if default is MISSING else default

hint = int | MISSING  # O(u)
assert typing.get_args(hint) == (int, MISSING)
assert MISSING | MISSING is MISSING
assert next_value() == 0 and next_value(5) == 5

try:
    class Special(sentinel):
        pass
except TypeError as error:
    assert 'not an acceptable base type' in str(error)
else:
    raise AssertionError('sentinel was subclassed')
```

## Performance Best Practices

✅ **Do**:

- Compare with `is`: it is one pointer comparison, and `==` can be answered by the other operand
- Define a sentinel once at module level under its own name, so it pickles and every import sees
  the same object
- Give a class-level sentinel its qualified name, `sentinel('Cls.NAME')`, if it has to be pickled

❌ **Avoid**:

- Calling `sentinel()` where a shared marker is meant - each call is a new object that compares
  unequal to the last
- `object()` as a marker where the value is printed or pickled - it has no name, and a pickled copy
  is a different object

## Version Notes

- **Python 3.15+**: Added as a built-in type (PEP 661)

## Related Types

- **[None](none.md)** - the usual default, when `None` is not itself a valid value
- **[object()](object_func.md)** - the older marker idiom, with no name and no identity across
  pickling
- **[Ellipsis](ellipsis.md)** - another singleton that is truthy and compared by identity
