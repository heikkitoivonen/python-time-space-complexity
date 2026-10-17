# locals() Function Complexity

The `locals()` function returns the current local namespace. At module or class scope, and in
code run by `exec()` or `eval()`, it returns the namespace mapping itself. Inside a function it
returns a snapshot dict of the function's variables, built on every call.

`m` is the names a function's frame holds: its parameters and local variables, plus the cell and
free variables it shares with nested functions, bound or not. Lookups in the returned dict are
average-case O(1), treating name hashing as O(1).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `locals()` at module or class scope | O(1) | O(1) | The namespace itself, or the locals mapping passed to `exec()`; writes reach it |
| `locals()` in a function | O(m²) from Python 3.13, O(m) before | O(m) | A snapshot of the bound names, free variables included; writes do not reach the function |
| Looking up a name in the result | O(1) avg | O(1) | Dict lookup, where the namespace is a dict |

## Function Scope

Each call copies the frame's bound variables into a dict, so the cost is paid again on every
call: quadratic in `m` from Python 3.13, linear before.

### A Snapshot of the Bound Names

```python
def outer():
    x = 'outer'

    def inner():
        y = 'inner'
        snapshot = locals()  # O(m²) from Python 3.13, O(m) before
        assert x == 'outer'  # inner reads x, so x is one of its free variables
        return snapshot

    return inner(), locals()

inner_names, outer_names = outer()
assert inner_names == {'y': 'inner', 'x': 'outer'}  # snapshot is bound after the call
assert set(outer_names) == {'x', 'inner'}
```

### Writes Do Not Reach the Function

```python
def modify_attempt():
    x = 10
    snapshot = locals()
    snapshot['x'] = 20  # O(1) - changes the dict, not the variable
    return x, snapshot['x']

assert modify_attempt() == (10, 20)
```

### Two Calls in One Frame

From Python 3.13 each call returns a new, independent dict. Before 3.13 every call refreshes and
returns the frame's one dict, so an earlier result changes under you.

```python
import sys

def two_snapshots():
    value = 1
    first = locals()
    value = 2
    second = locals()
    return first, second

first, second = two_snapshots()
if sys.version_info >= (3, 13):
    assert first is not second and first['value'] == 1
else:
    assert first is second and first['value'] == 2
assert second['value'] == 2
```

## Module and Class Scope

```python
x = 10
assert locals() is globals()  # O(1) - the module namespace itself

class Config:
    locals()['timeout'] = 30  # O(1) - the class namespace being built

assert Config.timeout == 30

namespace = {}
exec("locals()['added'] = 1", {}, namespace)  # O(1) - the mapping passed in
assert namespace == {'added': 1}
```

## Calling locals() Repeatedly

The snapshot is rebuilt on every call, so take it once and look names up in the result.

```python
def connection_string(host, port, user):
    names = locals()  # O(m²) from Python 3.13, O(m) before - once
    return '{user}@{host}:{port}'.format(**names)  # O(1) per lookup

assert connection_string('db', 5432, 'admin') == 'admin@db:5432'

def slow_sum(a, b, c):
    return locals()['a'] + locals()['b'] + locals()['c']  # three snapshots

def fast_sum(a, b, c):
    return a + b + c  # direct access, no snapshot

assert slow_sum(1, 2, 3) == fast_sum(1, 2, 3) == 6
```

## Performance Best Practices

✅ **Do**:

- Call `locals()` once and reuse the dict when you need several names from it
- Keep `locals()` for debugging and introspection, where the snapshot is built once
- Read variables by name in code, and keep values looked up by string key in a dict of your own

❌ **Avoid**:

- Calling `locals()` in a loop or once per name; each call rebuilds the snapshot
- Writing to `locals()` in a function to create or change variables; the function never sees it
- Holding a function's `locals()` result across later calls in the same frame before Python 3.13;
  each call refreshes the same dict

## Version Notes

- **Python 3.13+**: PEP 667: in a function, `locals()` returns a fresh, independent snapshot on
  every call, built in O(m²). Earlier versions refresh and return the frame's one dict in O(m), so
  two calls in the same frame return the same object and the earlier result shows later values
- **All Python 3**: At module and class scope, `locals()` is the namespace itself

## Related Functions

- **[globals()](globals.md)** - The module namespace, always O(1); also covers `frame.f_locals`
- **[vars()](vars.md)** - With no argument it is `locals()`; with one, the object's `__dict__`
- **[dir()](dir.md)** - Sorted list of the names in scope
