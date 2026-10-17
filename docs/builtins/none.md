# None Constant Complexity

`None` is Python's null value: the single instance of `NoneType`, returned by any function that
ends without a `return` value. Every operation on `None` itself is O(1), because there is only one
`None` and nothing to scan. What varies is what the *other* operand does when you compare with it.

`n` is the items in a collection. A user-defined `__eq__` costs what it does; the bounds below are
the work the comparison adds to it.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `x is None`, `x is not None` | O(1) | O(1) | Compares identity; never calls a method on `x` |
| `x == None`, `None == x` | O(1) | O(1) | Plus one call of `x.__eq__` when `x`'s class has a custom one, which can make the answer `True` |
| `bool(None)`, `if None:` | O(1) | O(1) | Always `False` |
| `type(None)`, `types.NoneType` | O(1) | O(1) | Returns the class, which has no other instances |
| `type(None)()` | O(1) | O(1) | Returns the same `None`; raises `TypeError` if given arguments |
| `hash(None)` | O(1) | O(1) | |
| Returning from a function without a value | O(1) | O(1) | The result is `None` |
| `None in seq`, `seq.count(None)` on a list | O(n) | O(1) | Compares each item until a match, or all of them for `count` |

## Checking for None

### is vs ==

`is` compares identity, so its answer cannot be changed by the other object. `==` calls the other
object's `__eq__`, which can claim to equal `None` and costs whatever it does.

```python
eq_calls = []

class AlwaysEqual:
    def __eq__(self, other):
        eq_calls.append(other)
        return True

value = AlwaysEqual()

assert value is not None   # O(1) - identity, no method called
assert eq_calls == []

assert value == None       # O(1) plus __eq__ - which answers True
assert None == value       # None defers to value.__eq__ as well
assert eq_calls == [None, None]
```

### Truthiness

`None` is falsy, as are `0`, `""` and empty containers, so `not value` cannot tell them apart. Use
`is None` when the empty value is a valid answer.

```python
assert not None  # O(1)

for empty in (0, "", [], {}):
    assert not empty
    assert empty is not None

def describe(items):
    if items is None:  # O(1)
        return "missing"
    if not items:
        return "empty"
    return f"{len(items)} items"

assert describe(None) == "missing"
assert describe([]) == "empty"
assert describe([1, 2]) == "2 items"
```

## The Singleton

There is exactly one `None`. Calling its type returns it rather than a new object, and the name
cannot be rebound, because `None` is a keyword.

```python
import types

assert type(None) is types.NoneType  # O(1)
assert type(None)() is None          # O(1) - the same object, not a new one

def no_return():
    pass

assert no_return() is None

try:
    type(None)(1)
except TypeError as error:
    assert "takes no arguments" in str(error)
else:
    raise AssertionError("expected TypeError")

try:
    compile("None = 1", "<example>", "exec")
except SyntaxError as error:
    assert "cannot assign to None" in error.msg
else:
    raise AssertionError("expected SyntaxError")
```

### None in Collections

`None` can be stored like any other value. Finding or counting it in a list is a scan, the same as
for any other value.

```python
items = [1, None, 3, None, 5]

assert items.count(None) == 2       # O(n)
assert None in items                # O(n) - stops at the first match
assert items.index(None) == 1       # O(n)
assert [x for x in items if x is not None] == [1, 3, 5]  # O(n)
```

## Common Patterns

### Default Arguments

A default value is evaluated once, when the function is defined, so a mutable default is shared
between calls. `None` as the default, replaced inside the function, gives each call its own object.

```python
def append_shared(item, target=[]):
    target.append(item)
    return target

assert append_shared(1) == [1]
assert append_shared(2) == [1, 2]  # The same list as the first call

def append_to(item, target=None):
    if target is None:  # O(1)
        target = []
    target.append(item)
    return target

assert append_to(1) == [1]
assert append_to(2) == [2]  # A fresh list, not [1, 2]

shared = []
assert append_to(3, shared) is shared
```

### Lazy Initialization

`None` marks a value that has not been computed yet. The first access pays for the computation, and
later ones cost one identity check.

```python
class Report:
    def __init__(self):
        self._rows = None
        self.loads = 0

    @property
    def rows(self):
        if self._rows is None:  # O(1)
            self.loads += 1
            self._rows = [i * i for i in range(1_000)]  # Computed once
        return self._rows

report = Report()
assert report.loads == 0

assert report.rows[3] == 9
assert report.rows[4] == 16
assert report.loads == 1
```

### Missing Keys vs None Values

`dict.get()` returns `None` for a missing key, which is indistinguishable from a key whose value
is `None`. Use `in`, or pass a sentinel object as the default, when both can occur.

```python
data = {"a": 1, "b": None}

assert data.get("b") is None   # O(1) - present, value None
assert data.get("z") is None   # O(1) - missing
assert "b" in data             # O(1)
assert "z" not in data

MISSING = object()
assert data.get("b", MISSING) is None
assert data.get("z", MISSING) is MISSING
```

### JSON null

`json` maps `None` to `null` and back.

```python
import json

text = json.dumps({"name": "Alice", "email": None})  # Linear in the output
assert text == '{"name": "Alice", "email": null}'

assert json.loads(text)["email"] is None
```

## Performance Best Practices

✅ **Do**:

- Use `is None` and `is not None`: they never call a method on the other object
- Use `None` as the default for an argument that would otherwise be a mutable object
- Use `is None` rather than `not value` when `0`, `""` or an empty container is a valid value
- Use a sentinel object as the `dict.get()` default when `None` can be a stored value

❌ **Avoid**:

- `== None`: it calls the other object's `__eq__`, which can cost anything and can claim to equal `None`
- A mutable default such as `[]` or `{}`; it is created once and shared between calls

## Version Notes

- **Python 3.10+**: `types.NoneType` names the class of `None`; earlier versions use `type(None)`.

## Related Constants

- **[True](true.md)** - Boolean true value
- **[False](false.md)** - Boolean false value
- **[NotImplemented](notimplemented.md)** - Returned by a comparison method that cannot handle its operand
- **[Ellipsis](ellipsis.md)** - The `...` object, another singleton
