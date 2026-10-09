# Ellipsis (...) Constant Complexity

The `Ellipsis` constant, also spelled `...`, is a singleton: both spellings name one object,
and nothing creates another. A type that receives it in a subscript, a type hint that contains
it, or a function that uses it as a sentinel gives it a meaning.

Every operation in the reference acts on that one object, so its rows have no size variable.
Where `...` is passed to someone else's code - a `__getitem__`, an `__eq__` - the cost is that
code's.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Ellipsis`, `...` | O(1) | O(1) | Both spellings name the same object |
| `x is ...` | O(1) | O(1) | Identity check; no method of `x` is called |
| `x == ...` | O(1) | O(1) | `ellipsis` defines no `__eq__`, so this is identity unless the other operand's `__eq__` answers |
| `type(...)`, `types.EllipsisType` | O(1) | O(1) | The type; it cannot be subclassed |
| `type(...)()` | O(1) | O(1) | Returns the existing singleton; any argument raises `TypeError` |
| `hash(...)` | O(1) | O(1) | Hashable, so it can be a dict key or a set member |
| `bool(...)` | O(1) | O(1) | Always `True` |
| `repr(...)`, `str(...)` | O(1) | O(1) | `'Ellipsis'` |
| `copy.copy(...)`, `copy.deepcopy(...)`, a `pickle` round trip | O(1) | O(1) | Return the singleton itself, so `is ...` still holds afterwards |
| `obj[...]` on an instance | O(1) | O(1) | Hands the singleton to `type(obj).__getitem__`; that method decides cost and meaning |

## The Singleton

```python
import copy
import pickle
import types

assert ... is Ellipsis                      # O(1) - one object, two spellings
assert type(...) is types.EllipsisType      # O(1)
assert type(...)() is ...                   # O(1) - "constructing" returns the singleton
assert copy.deepcopy(...) is ...            # O(1)
assert pickle.loads(pickle.dumps(...)) is ...

assert bool(...) is True                    # O(1) - always truthy
assert repr(...) == 'Ellipsis'

try:
    type('MyEllipsis', (types.EllipsisType,), {})
except TypeError as error:
    assert 'not an acceptable base type' in str(error)
else:
    raise AssertionError('the ellipsis type was subclassed')
```

## Subscripting With Ellipsis

On an instance, `obj[...]` passes the singleton to `obj.__getitem__` and nothing more, so the
receiving type decides what it means and what it costs. Instances of `list`, `tuple`, `str`,
`bytes` and `range` reject it;
a type that opts in can treat it as "everything", or, inside a tuple subscript, as "every leading
dimension".

```python
data = [[1, 2, 3], [4, 5, 6]]

try:
    data[...]
except TypeError as error:
    assert 'list indices must be integers or slices' in str(error)
else:
    raise AssertionError('a list accepted Ellipsis')


class Grid:
    """Rows of values; `...` stands for every row."""

    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, key):
        if key is ...:                                   # O(1) - identity check
            return self.rows
        if isinstance(key, tuple) and key[0] is ...:     # grid[..., j]
            return [row[key[1]] for row in self.rows]    # O(r), r = rows
        return self.rows[key]


grid = Grid(data)
assert grid[...] is data           # O(1) - the rows themselves, not a copy
assert grid[..., 0] == [1, 4]      # O(r) - column 0 of every row
assert grid[1] == [4, 5, 6]        # O(1)
```

## Placeholder Bodies

A body of `...` is a no-op expression statement, so a stub written with it returns `None`, the
same as one written with `pass`. In an abstract method, `@abstractmethod` is what blocks
instantiation; the body only has to be valid syntax.

```python
from abc import ABC, abstractmethod


def not_written_yet():
    ...


assert not_written_yet() is None  # O(1)


class DataStore(ABC):
    @abstractmethod
    def save(self, data):
        ...


class MemoryStore(DataStore):
    def __init__(self):
        self.items = []

    def save(self, data):
        super().save(data)       # runs the `...` body: returns None
        self.items.append(data)  # O(1) amortized


try:
    DataStore()
except TypeError as error:
    assert 'abstract' in str(error)
else:
    raise AssertionError('an abstract class was instantiated')

store = MemoryStore()
store.save('x')
assert store.items == ['x']
```

## Type Hints

In a type hint, `...` has two meanings. `tuple[int, ...]` is a tuple of any length whose items
are all `int`, and `Callable[..., int]` is a callable whose arguments are not checked. Either
way the hint keeps `Ellipsis` as an argument.

```python
from collections.abc import Callable
from typing import get_args

Row = tuple[int, ...]       # any number of ints
Pair = tuple[int, int]      # exactly two


def widen(row: Row) -> Row:
    return tuple(v * 2 for v in row)  # O(n), n = items


assert widen((1, 2, 3)) == (2, 4, 6)
assert get_args(Row) == (int, Ellipsis)                   # O(1)
assert get_args(Pair) == (int, int)
assert get_args(Callable[..., int]) == (Ellipsis, int)    # O(1)
```

## Ellipsis as a Sentinel

`None` is the usual "no value" marker, which makes it ambiguous when `None` is itself a
legitimate argument. `...` is a distinct singleton, so it can mean "not supplied" while `None`
stays an ordinary value, and the check is one identity test. That holds only while `...` is
reserved for that meaning: a caller who passes `...` explicitly is treated as passing nothing.

```python
MISSING = ...


def get(mapping, key, default=MISSING):
    """Look up a key, distinguishing 'no default' from 'default is None'."""
    if key in mapping:            # O(1) average
        return mapping[key]       # O(1) average
    if default is MISSING:        # O(1) - identity check
        raise KeyError(key)
    return default


data = {'a': 1, 'b': None}
assert get(data, 'b') is None         # the stored value
assert get(data, 'z', None) is None   # the supplied default

for missing in ((), (...,)):     # an explicit ... counts as no default
    try:
        get(data, 'z', *missing)
    except KeyError:
        pass
    else:
        raise AssertionError('a missing key with no default returned a value')
```

## Comparing With Ellipsis

`x is ...` asks only whether `x` is the singleton. `x == ...` asks `x` too: the `ellipsis` type
has no `__eq__` of its own, so whichever operand defines one decides the answer. Ordering
comparisons are not defined.

```python
class EqualsEverything:
    def __eq__(self, other):
        return True


value = EqualsEverything()
assert (value == ...) is True     # O(1) - value.__eq__ answered
assert (value is ...) is False    # O(1) - identity cannot be overridden
assert (... == ...) is True
assert (... == None) is False

try:
    ... < ...
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError('Ellipsis supported ordering')
```

## Performance Best Practices

✅ **Do**:

- Test with `x is ...`: one identity check, and no operand's `__eq__` can change the answer
- Use `...` as a "not supplied" sentinel where `None` is a legitimate value
- Write `tuple[int, ...]` for a homogeneous tuple of any length, and `Callable[..., R]` when the
  arguments are not checked

❌ **Avoid**:

- `x == ...` as a test for the singleton: an operand's `__eq__` can answer `True`
- Returning `...` from a binary operator method to mean "unsupported": it becomes the result,
  where `NotImplemented` lets Python try the other operand's reflected method
- Subscripting a `list`, `tuple`, `str`, `bytes` or `range` with `...`: they raise `TypeError`

## Version Notes

- **Python 3.10+**: `types.EllipsisType` names the type of `...`

## Related Constants

- **[None](none.md)** - the usual sentinel, when `None` is not itself a valid value
- **[NotImplemented](notimplemented.md)** - what a binary operator method returns to defer to the other operand
- **[True](true.md)** - Boolean true
- **[False](false.md)** - Boolean false
