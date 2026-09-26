# reprlib Module Complexity

The `reprlib` module produces size-limited representations: a list shows its first few items, a
string its two ends, and nested containers stop after a fixed depth. What those limits bound is
the output. How much of the input is read depends on the type: sequences and strings stop at the
limit, dicts and sets sort everything first, and a type `Repr` has no method for is rendered in
full by its own `repr()` and then trimmed.

`n` is the elements of the container, or the characters of the string, handed to one call, and
`k` is the limit that applies to it (`maxlist`, `maxdict`, `maxstring` and so on). `d` is the
digits of an int, and `r` is the length of the ordinary `repr()` of an object `Repr` has no
method for, which prices a user-defined `__repr__` at the characters it returns. Each bound
covers one container level: the elements shown are rendered by the same rules one level deeper,
until `maxlevel` runs out, and their cost adds to the row. Hashing and comparing elements are
treated as O(1).

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `reprlib.repr(obj)` | As `Repr.repr` | As `Repr.repr` | The bound `repr` method of `reprlib.aRepr` |
| `reprlib.aRepr` | O(1) | O(1) | The shared `Repr` instance with default limits; changing its attributes changes `reprlib.repr` for every caller |
| `reprlib.recursive_repr(fillvalue='...')` | O(1) | O(1) | Decorator for a `__repr__` method |
| Calling a `recursive_repr`-decorated `__repr__` | O(1) plus the wrapped call | O(1) per call in progress | A call re-entered for the same object in the same thread returns `fillvalue` at once |

### Repr

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `reprlib.Repr(*, maxlevel=6, maxtuple=6, maxlist=6, ...)` | O(1) | O(1) | Keyword arguments for every limit are Python 3.12+; earlier versions set the attributes after construction |
| `Repr.repr(obj)` | As the type's row below | As the type's row below | `repr1(obj, maxlevel)` |
| `Repr.repr1(obj, level)` | O(1) plus the type's row | As the type's row | Dispatches to a `repr_<typename>` method by the name of `type(obj)`, falling back to `repr_instance`; a subclass of a built-in type under a name of its own falls back too |
| `Repr.maxlevel` | O(1) | O(1) | Depth limit, 6 by default; a non-empty container at that depth shows only `fillvalue` and its contents are not rendered |
| `Repr.maxtuple`, `Repr.maxlist`, `Repr.maxarray`, `Repr.maxdict`, `Repr.maxset`, `Repr.maxfrozenset`, `Repr.maxdeque` | O(1) | O(1) | Element limits: 6, 6, 5, 4, 6, 6 and 6 by default |
| `Repr.maxstring`, `Repr.maxlong`, `Repr.maxother` | O(1) | O(1) | Character limits: 30, 40 and 30 by default |
| `Repr.fillvalue` | O(1) | O(1) | Python 3.11+; the marker for omitted content, `'...'` by default |
| `Repr.indent` | O(1) | O(1) | Python 3.12+; `None` keeps one line, a string or a number of spaces puts each element on its own indented line |

### Repr rendering by type

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Repr.repr_tuple`, `Repr.repr_list`, `Repr.repr_deque`, `Repr.repr_array` | O(min(n, k)) | O(min(n, k)) | Reads only the elements it shows, so a fixed limit costs the same for any n |
| `Repr.repr_str` | O(min(n, k)) | O(min(n, k)) | Slices to `maxstring` before quoting |
| `Repr.repr_dict` | O(n log n); O(n) when the keys already iterate in ascending order | O(n) | Sorts every key before showing `maxdict` of them; keys that cannot be compared are shown in iteration order; not sorted at the depth where `maxlevel` shows only `{...}` |
| `Repr.repr_set`, `Repr.repr_frozenset` | O(n log n); O(n) when already in ascending order | O(n) | Sorts every element, even at the depth where `maxlevel` shows only `{...}` |
| `Repr.repr_int` | O(d²) | O(d) | Converts every digit before trimming to `maxlong`; beyond `sys.get_int_max_str_digits()` it returns a placeholder on Python 3.13.6+ and raises `ValueError` before |
| `Repr.repr_instance` | O(r) | O(r) | Every other type, `float`, `bytes` and subclasses of built-in types under their own names included: the whole `repr()` is built before `maxother` trims it; a `repr()` that raises an `Exception` gives `<Type instance at 0x...>` |

## Truncating Output

### Sequences and Strings Stop at the Limit

A list, tuple, deque or array is read only as far as its limit, and a string is sliced to
`maxstring` before it is quoted, so a fixed limit costs the same however large the input.

```python
import reprlib

short = reprlib.Repr()  # O(1)
short.maxlist = 3
short.maxstring = 20

# O(min(n, k)): only the first maxlist items are read
assert short.repr(list(range(100))) == '[0, 1, 2, ...]'
assert short.repr(list(range(100_000))) == '[0, 1, 2, ...]'

# O(min(n, k)): sliced before quoting, then cut in the middle
assert short.repr('x' * 1000) == "'xxxxxxx...xxxxxxxx'"
assert short.repr('abc') == "'abc'"
```

### Dicts and Sets Sort Everything First

The limit on a dict or set trims what is shown, not what is read: every key is sorted first, so
the output is ordered but the cost is the whole container's.

```python
import reprlib

squares = {i: i**2 for i in range(1000)}
# All 1,000 keys are sorted before four are shown - O(n) here, since they
# already ascend; O(n log n) in general
assert reprlib.repr(squares) == '{0: 0, 1: 1, 2: 4, 3: 9, ...}'

# The sort orders the output, whatever the insertion order
assert reprlib.repr({3: 'c', 1: 'a', 2: 'b'}) == "{1: 'a', 2: 'b', 3: 'c'}"
assert reprlib.repr(frozenset({'b', 'a'})) == "frozenset({'a', 'b'})"

# Keys that cannot be compared are shown in iteration order instead
assert reprlib.repr({1: 'int', 'a': 'str'}) == "{1: 'int', 'a': 'str'}"
```

### Types Without a Method Are Rendered in Full

`Repr` finds its method by the name of the object's type. Anything without one, including
`bytes` and a subclass of a built-in container under a name of its own, goes to `repr_instance`,
which builds the object's complete `repr()` and only then cuts it to `maxother`.

```python
import reprlib

payload = bytes(100_000)
# O(r): the whole 400,003-character repr() is built, then cut to maxother
shown = reprlib.repr(payload)
assert len(shown) == reprlib.aRepr.maxother
assert shown.startswith("b'\\x00")

class Rows(list):
    pass

rows = Rows(range(100_000))
# A subclass of list is not dispatched as a list: O(r) for all of it
assert reprlib.repr(rows).endswith('99998, 99999]')
assert reprlib.repr(list(rows)) == '[0, 1, 2, 3, 4, 5, ...]'  # O(min(n, k))
```

### Adding a Type

A `Repr` subclass can add a `repr_<typename>` method, which `repr1()` then finds by name. That is
how to give a type rendered in full a bound of its own.

```python
import reprlib

class ShortBytes(reprlib.Repr):
    def repr_bytes(self, obj, level):
        # O(min(n, k)): slice before calling the built-in repr()
        head = repr(obj[:self.maxstring])
        return head + '...' if len(obj) > self.maxstring else head

short = ShortBytes()
assert short.repr(bytes(100_000)).endswith("\\x00'...")
assert short.repr(b'abc') == "b'abc'"
assert short.repr([b'abc']) == "[b'abc']"  # elements dispatch the same way
```

### Nesting and maxlevel

Non-empty containers deeper than `maxlevel` are shown as `fillvalue` without rendering their
contents, so a structure of lists, tuples, deques and strings costs the same however deep or long
it is. A set at that depth is the exception: it is sorted in full before being shown as `{...}`.

```python
import reprlib

nested = [[[[[[[['deep']]]]]]]]
# Six levels are rendered; the seventh shows only the fillvalue
assert reprlib.repr(nested) == '[[[[[[[...]]]]]]]'

shallow = reprlib.Repr()
shallow.maxlevel = 2
assert shallow.repr([[1, [2]], {'a': {'b': 1}}]) == "[[1, [...]], {'a': {...}}]"
```

### Large Integers

An int is converted to decimal in full before `maxlong` trims it, at O(d²). Past
`sys.get_int_max_str_digits()` (4,300 by default) the conversion is refused: Python 3.13.6+ shows
a placeholder, and earlier versions raise `ValueError`.

```python
import reprlib

big = 7 ** 1000  # 846 digits
shown = reprlib.repr(big)  # O(d²): every digit is converted, then 40 are kept
assert len(shown) == reprlib.aRepr.maxlong
assert shown.startswith(str(big)[:18]) and shown.endswith(str(big)[-19:])
```

## Guarding Against Recursive Structures

`recursive_repr` wraps a `__repr__` so that a call re-entered for the same object in the same
thread returns `fillvalue` at once. It costs one set entry per call in progress, and it bounds
cycles only: a long acyclic chain still recurses to the end.

```python
import reprlib


class Node:
    def __init__(self):
        self.child = None

    @reprlib.recursive_repr('<...>')  # O(1) per call, plus the method itself
    def __repr__(self):
        return f'Node({self.child!r})'


node = Node()
node.child = node  # a cycle: without the decorator, RecursionError
assert repr(node) == 'Node(<...>)'

leaf = Node()
assert repr(leaf) == 'Node(None)'
```

## Common Patterns

### A Bounded __repr__ for a Large Container

```python
import reprlib


class Batch:
    def __init__(self, items):
        self.items = items

    def __repr__(self):
        # O(min(n, k)) for a list, however large the batch grows
        return f'Batch({reprlib.repr(self.items)})'


assert repr(Batch(list(range(100_000)))) == 'Batch([0, 1, 2, 3, 4, 5, ...])'
```

## Performance Best Practices

✅ **Do**:

- Use `reprlib.repr()` for lists, tuples, deques, arrays and strings in log messages and
  `__repr__` methods: the cost stays at the limit however large the value
- Subclass `Repr` and add a `repr_<typename>` method for a type that would otherwise be rendered
  in full, such as `bytes` or your own container
- Build your own `Repr` instance to change limits, rather than changing `reprlib.aRepr`, which
  every other caller of `reprlib.repr()` shares
- Decorate a container's `__repr__` with `recursive_repr` when it can contain itself

❌ **Avoid**:

- Expecting `maxdict` or `maxset` to bound the work - a large dict or set is sorted in full
- Expecting `maxother` or `maxlong` to bound the work - the full `repr()` is built first
- Passing a subclass of `list` or `dict` and expecting the container limits to apply

## Version Notes

- **Python 3.11+**: Added `Repr.fillvalue`
- **Python 3.12+**: `Repr()` accepts every limit as a keyword argument; added `Repr.indent`
- **Python 3.13.6+**: An int with more digits than `sys.get_int_max_str_digits()` renders as a
  placeholder instead of raising `ValueError`

## Related Modules

- **[pprint](pprint.md)** - full, formatted output of the whole object
- **[sys](sys.md)** - `get_int_max_str_digits()`, the limit on int-to-string conversion
