# False Constant Complexity

`False` is one of the two instances of `bool`, and nothing creates another: `bool()` and every
false built-in comparison hand back this same object. It is a keyword, so the compiler stores the
object as a constant - reading `False` looks up no name, and it cannot be assigned or shadowed.

`bool` is a subclass of `int`, so `False` also behaves as the integer `0`: it equals `0` and
`0.0`, hashes like them, and counts as `0` in arithmetic. Every row below acts on that one object
and has no size variable. Where `False` meets another operand - `x == False`, `bool(x)`,
`False or y` - that operand's own method or evaluation costs extra. In the examples, `n` is the
items in an iterable.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `False` | O(1) | O(1) | A constant load; assigning to it is a `SyntaxError` |
| `x is False` | O(1) | O(1) | Identity: true only for `False` itself, not `0`, `None` or `""` |
| `x == False` | O(1) | O(1) | Also true for `0` and `0.0`; an operand's own `__eq__` can answer |
| `not x` | O(1) | O(1) | `True` for every falsy built-in value; costs `x`'s truth test |
| `bool()`, `bool(x)` | O(1) | O(1) | `bool()` is `False`; the result is always one of the two singletons |
| `type(False)`, `isinstance(False, int)` | O(1) | O(1) | `bool`, a subclass of `int` |
| `int(False)`, `False + False` | O(1) | O(1) | Counts as `0`; arithmetic returns an `int`, not a `bool` |
| `hash(False)` | O(1) | O(1) | `0`, so `False`, `0` and `0.0` are one dict key or set member |
| `str(False)`, `repr(False)` | O(1) | O(1) | `'False'` |
| `False and y` | O(1) | O(1) | Returns `False`; `y` is not evaluated |
| `False or y` | O(1) | O(1) | Evaluates `y` and returns it unchanged, whatever its type |
| `~False` | O(1) | O(1) | Returns the int `-1`, not `True`; deprecated since 3.12 |

## The Singleton

```python
import builtins

assert bool() is False                      # O(1) - no argument gives False
assert bool(0) is False                     # O(1) - the singleton, not a new object
assert bool([]) is False
assert (1 > 2) is False                     # comparisons return it too
assert type(False) is bool
assert isinstance(False, int)

try:
    compile('False = 1', '<example>', 'exec')
except SyntaxError as error:
    assert 'cannot assign to False' in str(error)
else:
    raise AssertionError('False was assigned')

# A keyword, not a builtin name: replacing builtins.False changes nothing
namespace = {'__builtins__': {'False': 'shadow'}}
exec('result = False', namespace)
assert namespace['result'] is False
assert getattr(builtins, 'False') is False
```

## Testing for False

`not x`, `x is False` and `x == False` answer three different questions, and each is one O(1)
test on built-in values. `not x` is true for every falsy value, `x is False` only for the
`False` object, and `x == False` for `False` and the numeric zeros `0` and `0.0`.

```python
values = [False, 0, 0.0, None, '', []]

falsy = [v for v in values if not v]                # O(n)
is_false = [v for v in values if v is False]        # O(n)
equals_false = [v for v in values if v == False]    # O(n)

assert falsy == values                              # all of them are falsy
assert is_false == [False]                          # only False itself
assert equals_false == [False, 0, 0.0]              # False and the zeros
```

## False as an Integer

`False` is the integer `0` to arithmetic and to hashing. That makes it useful for counting, and
a trap for a dict or set that mixes it with `0`: the two are one key, the first key inserted
is kept, and the last value wins.

```python
data = [3, -1, 4, -1, 5]

assert False + False == 0                   # O(1)
assert type(False + False) is int           # the result is an int
assert sum(x < 0 for x in data) == 2        # O(n) - each False adds 0

table = {False: 'no', 0: 'zero'}            # O(1) - one key, not two
assert len(table) == 1
assert table == {False: 'zero'}             # first key kept, last value wins
assert len({False, 0, 0.0}) == 1

assert (not False) is True                  # negate with not
assert ~int(False) == -1                    # bitwise inversion on the int
```

## Short-Circuiting

`False and y` stops at `False` and never evaluates `y`, so a guard placed first saves the
expensive operand. `False or y` always evaluates `y` and returns it as it is, without converting
it to a `bool`.

```python
calls = 0


def expensive():
    global calls
    calls += 1
    return [1, 2, 3]


assert (False and expensive()) is False     # O(1) - expensive() is not called
assert calls == 0

result = False or expensive()               # expensive() is called
assert calls == 1
assert result == [1, 2, 3]                  # y itself, not True
```

## Performance Best Practices

✅ **Do**:

- Use `not x` when every falsy value means "no"
- Use `x is False` when only the `False` object should match, for example to tell it from `0`
  or `None`
- Put the cheap condition first in `a and b`, so a `False` skips the expensive one
- Count matches with `sum(predicate(x) for x in items)`: each `False` adds `0`

❌ **Avoid**:

- `x == False` as a test for `False`: it is also true for `0` and `0.0`
- Mixing `False` with `0` or `0.0` as dict keys or set members: they are one key
- `~flag` to negate a flag: it returns `-1` or `-2` and warns from 3.12; use `not flag`

## Version Notes

- **Python 3.12+**: `~False` emits a `DeprecationWarning`; it still returns `-1`
- **All Python 3**: `False` is a keyword; assigning to it is a `SyntaxError`

## Related Constants

- **[True](true.md)** - the other `bool` instance
- **[None](none.md)** - also falsy, but `None == False` is false
- **[NotImplemented](notimplemented.md)** - another built-in constant
- **[bool type](bool.md)** - the operators on both `bool` values
- **[bool()](bool_func.md)** - what the truth test costs for each kind of object
