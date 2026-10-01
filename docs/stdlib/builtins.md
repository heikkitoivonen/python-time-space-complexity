# builtins Module Complexity

The `builtins` module is the namespace that holds every built-in function, type, exception and
constant. Name resolution falls back to it last, after the local, enclosing and global scopes, and
it does so each time the code runs, so most code never imports it. Importing it is for inspecting
that namespace or for replacing a name in it deliberately.

`n` is the names in the module's namespace. Bounds treat hashing and comparing a name as O(1).

## Complexity Reference

### Reading and writing names

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `builtins.name`, `getattr(builtins, name[, default])` | O(1) | O(1) | |
| `hasattr(builtins, name)` | O(1) | O(1) | A missing name returns `False` |
| `setattr(builtins, name, value)`, `builtins.name = value` | O(1) amortized | O(1) amortized | Every later lookup in the interpreter sees it, unless a local, enclosing or global binding of the same name shadows it |
| `delattr(builtins, name)`, `del builtins.name` | O(1) | O(1) | A later unqualified use raises `NameError` unless a local, enclosing or global binding of the name shadows it |
| Unqualified name lookup (`len`) | O(1) | O(1) | A module global of the same name is found first; neither namespace's size matters |

### Inspecting the namespace

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dir(builtins)` | O(n log n) | O(n) | A new sorted list of the names |
| `vars(builtins)`, `builtins.__dict__` | O(1) | O(1) | The live namespace dict, not a copy |
| Iterating `vars(builtins).items()` | O(n) | O(1) | |

## Name Resolution

A name a function neither assigns nor inherits from an enclosing function is looked up in the
module's globals and then in `builtins`, every time the line runs. Both steps are O(1). Because
globals come first, a module global of the same name shadows the built-in for that module alone,
and deleting it lets the lookup fall through again.

```python
import builtins

def size(obj):
    return len(obj)  # O(1) - globals, then builtins

assert size("abc") == 3

len = lambda obj: -1  # a module global shadows the built-in for this module only
assert size("abc") == -1
assert builtins.len("abc") == 3  # the built-in itself is untouched

del len  # the lookup falls through to builtins again
assert size("abc") == 3
```

## Inspecting the Namespace

`vars(builtins)` hands back the module's own dict, so reading it is O(1) and scanning it is one pass.
`dir(builtins)` copies the names into a new list and sorts it.

```python
import builtins

assert hasattr(builtins, "len")       # O(1)
assert not hasattr(builtins, "nope")  # O(1) - a miss is False, not an error

names = dir(builtins)  # O(n log n) - a new sorted list
assert names == sorted(names) and "len" in names

namespace = vars(builtins)  # O(1) - the live dict, not a copy
assert namespace is builtins.__dict__

exceptions = [  # O(n) - one pass over the namespace
    name for name, obj in namespace.items()
    if isinstance(obj, type) and issubclass(obj, BaseException)
]
assert "ValueError" in exceptions and "len" not in exceptions
```

## Replacing a Built-in

Assigning to `builtins` is O(1), and it changes the name for **every** module in the
interpreter where the name is not shadowed, including modules imported before the assignment:
their next lookup finds the new object. Code that `exec()` runs with its own `__builtins__` dict
searches that dict instead, and does not see the change.

```python
import builtins

original = builtins.len        # keep a reference - O(1)
builtins.len = lambda obj: 42  # O(1) - interpreter-wide
try:
    assert len([1, 2, 3]) == 42
finally:
    builtins.len = original    # always restore - O(1)

assert len([1, 2, 3]) == 3
```

!!! warning "Interpreter-wide side effect"
    Patching `builtins` is interpreter-wide state. Prefer shadowing a name in the local or
    module scope, which cannot leak into unrelated code, or a patch that restores itself.

## Common Patterns

### Patching a Built-in in a Test

`unittest.mock.patch` makes the same O(1) assignment and undoes it when the block exits, even
on an exception.

```python
import builtins
from unittest import mock

original = builtins.open
with mock.patch("builtins.open", mock.mock_open(read_data="a\nb\n")) as fake:  # O(1)
    with open("any/path") as handle:
        assert handle.read() == "a\nb\n"

fake.assert_called_once_with("any/path")
assert builtins.open is original  # restored on exit
```

## Performance Best Practices

✅ **Do**:

- Shadow a built-in with a module global when only one module needs a different one; the lookup
  stays O(1) and nothing else sees it
- Use `unittest.mock.patch("builtins.name")` in tests, so the interpreter-wide assignment is
  always undone
- Read `vars(builtins)` when you need the namespace itself; `dir(builtins)` sorts a copy

❌ **Avoid**:

- Assigning to `builtins` in library code - every module in the interpreter sees it
- Reading `__builtins__` instead of importing `builtins` - in an imported Python module it is
  the module's dict, not the module

## Version Notes

- **All Python 3**: `__builtins__` is a CPython implementation detail; in an imported Python
  module it is `builtins.__dict__`, not the module

## Related Modules

- **[Built-in functions and types](../builtins/index.md)** - the cost of each name this module
  holds
- **[globals() and locals()](../builtins/globals.md)** - the namespaces searched before this one
- **[vars()](../builtins/vars.md)** - why `vars(module)` is O(1) and `vars()` in a function is not
- **[gettext](gettext.md)** - `install()` puts `_` into this namespace
- **[site](site.md)** - adds `help`, `exit`, `quit`, `copyright`, `credits` and `license` at
  startup
