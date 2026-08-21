# builtins Module

The `builtins` module provides direct access to the namespace that holds every
built-in function, type, exception, and constant. Python consults it last when
resolving a name, after the local, enclosing, and global scopes.

Most code never imports it: `len`, `dict`, and `ValueError` are already visible
because of that lookup chain. You reach for `builtins` explicitly when you need
to inspect the namespace, or to shadow or restore a name deliberately.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `builtins.name` (attribute access) | O(1) | O(1) | Module `__dict__` lookup |
| `getattr(builtins, name)` | O(1) | O(1) | Same dict lookup |
| `setattr(builtins, name, value)` | O(1) | O(1) | Affects every module in the process |
| `hasattr(builtins, name)` | O(1) | O(1) | Dict membership test |
| `dir(builtins)` | O(n log n) | O(n) | n = names; sorted result |
| `vars(builtins)` | O(1) | O(1) | Returns the existing `__dict__` |
| Unqualified name lookup (`len`) | O(1) | O(1) | Only after local/enclosing/global miss |

## Name Resolution Cost

Built-in names are found last, so each reference pays for the misses ahead of
it. All the steps are O(1) dict lookups, but there are more of them:

```python
import builtins

# Global scope: LOAD_GLOBAL checks globals, then builtins - two lookups
value = len([1, 2, 3])

# Hot loops can bind the name locally to get a LOAD_FAST instead
def count_all(rows):
    _len = len            # one builtins lookup, up front
    return sum(_len(r) for r in rows)   # LOAD_FAST per iteration
```

This is a constant-factor optimization, not a complexity change. Reach for it
only in measured hot paths.

## Inspecting the Namespace

```python
import builtins

# O(1) membership test
print(hasattr(builtins, "len"))       # True

# O(n log n) - dir() sorts
names = dir(builtins)
print(len(names))

# O(n) scan over the module dict
exceptions = [
    name for name, obj in vars(builtins).items()
    if isinstance(obj, type) and issubclass(obj, BaseException)
]
```

## Shadowing Built-ins

Assigning to `builtins` changes the name for **every** module in the process,
not just the one doing the assignment.

```python
import builtins

original = builtins.len          # keep a reference - O(1)
builtins.len = lambda obj: 42    # process-wide, O(1)
try:
    print(len([1, 2, 3]))        # 42
finally:
    builtins.len = original      # always restore
```

!!! warning "Process-wide side effect"
    Patching `builtins` is global state. Prefer shadowing a name in the local
    or module scope, which is cheaper to reason about and cannot leak into
    unrelated code.

## Version Notes

- **All Python 3 versions**: `builtins` replaced Python 2's `__builtin__`
- **All versions**: name resolution order (local, enclosing, global, builtins)
  is unchanged; every step is an O(1) dict lookup

## Related Documentation

- [Builtins](../builtins/index.md)
- [Globals](../builtins/globals.md)
- [Locals](../builtins/locals_func.md)
- [Vars](../builtins/vars.md)
