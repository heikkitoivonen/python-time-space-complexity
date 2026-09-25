# types Module Complexity

The `types` module names the interpreter's types that have no builtin name - functions, generators,
modules, frames, descriptors - and adds a few utilities: `SimpleNamespace`, the read-only
`MappingProxyType`, and helpers that create classes the way a `class` statement does. Using a type
name is an attribute read; the costs on this page are in the utilities and the constructors.

`n` is the entries in a namespace or mapping, and `m` the entries in the other operand of `|` or
the changes passed to `copy.replace()`. `d` is the length of `type(obj).__mro__`, `c` is a
function's closure cells, and `k` is the size of a function's code object. `b` is the bases given to
the class-creation helpers or the bases `__mro_entries__` turns them into, whichever is more; each
base replaced by more or fewer than one adds another O(b) to `resolve_bases()` and `new_class()`.
Key hashing and key and value comparison count as O(1), as do class keyword arguments. Proxy bounds
assume the proxied mapping is a `dict`; the proxy adds O(1) to whatever its mapping costs.

## Complexity Reference

### Type names

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `types.FunctionType`, `types.LambdaType`, `types.MethodType`, `types.CodeType`, `types.CellType` | O(1) | O(1) | Functions written in Python and their parts; `LambdaType` is `FunctionType` |
| `types.GeneratorType`, `types.CoroutineType`, `types.AsyncGeneratorType` | O(1) | O(1) | What calling a generator, `async def` or asynchronous generator function returns |
| `types.BuiltinFunctionType`, `types.BuiltinMethodType`, `types.WrapperDescriptorType`, `types.MethodWrapperType`, `types.MethodDescriptorType`, `types.ClassMethodDescriptorType` | O(1) | O(1) | Callables written in C; `BuiltinMethodType` is `BuiltinFunctionType` |
| `types.GetSetDescriptorType`, `types.MemberDescriptorType` | O(1) | O(1) | The descriptors behind attributes of types written in C |
| `types.ModuleType`, `types.TracebackType`, `types.FrameType` | O(1) | O(1) | |
| `types.NoneType`, `types.EllipsisType`, `types.NotImplementedType` | O(1) | O(1) | The types of the three singletons |
| `types.GenericAlias`, `types.UnionType` | O(1) | O(1) | What `list[int]` and `int \| str` build; `UnionType` is `typing.Union` from Python 3.14 |
| `types.CapsuleType` | O(1) | O(1) | Python 3.13+ |
| `isinstance(obj, types.FunctionType)`, or any name above | O(d) | O(1) | An exact type match is one comparison; see [isinstance](../builtins/isinstance.md) |

### Constructors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `types.FunctionType(code, globals, name=None, argdefs=None, closure=None)` | O(c) | O(1) | Shares the code, globals, defaults and closure; each closure cell is checked once |
| `types.MethodType(function, instance)` | O(1) | O(1) | Binds a callable to an instance, as attribute lookup does |
| `types.ModuleType(name, doc=None)` | O(1) | O(1) | An empty module: nothing is imported and `sys.modules` is not touched |
| `types.TracebackType(tb_next, tb_frame, tb_lasti, tb_lineno)` | O(1) | O(1) | Links one entry onto an existing chain |
| `types.GenericAlias(t_origin, t_args)` | O(1) | O(1) | Keeps the `t_args` tuple itself |

### SimpleNamespace

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `types.SimpleNamespace(**kwargs)`, `types.SimpleNamespace(mapping_or_iterable, /, **kwargs)` | O(n) | O(n) | Copies the entries into its own dict, even from a dict; the positional form is Python 3.13+ |
| `ns.attr`, `ns.attr = value`, `del ns.attr` | O(1) | O(1) | Average case: one dict operation |
| `vars(ns)`, `ns.__dict__` | O(1) | O(1) | The namespace's own dict, not a copy: writing to it changes the namespace |
| `ns == other` | O(n) | O(1) | Compares the two dicts when both sides are namespaces |
| `repr(ns)` | O(n) | O(n) | Plus each value's `repr()` |
| `copy.replace(ns, **changes)` | O(n + m) | O(n + m) | A new namespace; Python 3.13+ |

### MappingProxyType

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `types.MappingProxyType(mapping)` | O(1) | O(1) | Copies nothing, so later changes to `mapping` show through; a list or tuple is rejected |
| `proxy[key]`, `key in proxy`, `MappingProxyType.get(key, default=None)` | O(1) | O(1) | Average case |
| `len(proxy)` | O(1) | O(1) | |
| `iter(proxy)`, `reversed(proxy)` | O(n) | O(1) | For the full pass |
| `MappingProxyType.keys()`, `MappingProxyType.values()`, `MappingProxyType.items()` | O(1) | O(1) | The mapping's own views, not lists |
| `MappingProxyType.copy()` | O(n) | O(n) | The mapping's `copy()`: a writable `dict` for a dict, not a proxy |
| `proxy \| other`, `other \| proxy` | O(n + m) | O(n + m) | A new `dict`; `\|=` raises `TypeError` |
| `proxy == other` | O(n) | O(1) | Compared as the mapping |

### Dynamic class creation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `types.new_class(name, bases=(), kwds=None, exec_body=None)` | O(b + n) | O(b + n) | n = entries `exec_body` leaves in the namespace; `exec_body`, the metaclass and the MRO cost what they cost in a `class` statement |
| `types.prepare_class(name, bases=(), kwds=None)` | O(b) | O(1) | Picks the most derived metaclass and calls its `__prepare__`; copies `kwds` rather than changing it |
| `types.resolve_bases(bases)` | O(b) | O(b) | Calls `__mro_entries__` where a base defines it; returns `bases` itself when none does |
| `types.get_original_bases(cls, /)` | O(1) | O(1) | The stored `__orig_bases__`, or `__bases__`; Python 3.12+ |

### Coroutines and descriptors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `types.coroutine(gen_func)` | O(k) | O(k) | Returns the same generator function with a coroutine-flagged copy of its code object; a coroutine function comes back unchanged, and any other callable is wrapped |
| `types.DynamicClassAttribute(fget=None, fset=None, fdel=None, doc=None)` | O(1) | O(1) | A `property` on instances; on the class it raises `AttributeError` so the metaclass's `__getattr__` answers, or returns itself if the getter is abstract |

## Checking Types

The names exist for `isinstance()` checks against types that have no builtin name. They answer a
narrower question than `callable()`: a function written in C is not a `FunctionType`.

```python
import types

def plain():
    pass

class Widget:
    def method(self):
        pass

assert isinstance(plain, types.FunctionType)          # exact type: one comparison
assert isinstance(lambda: None, types.LambdaType)     # the same type
assert isinstance(Widget().method, types.MethodType)  # a bound method
assert isinstance(Widget.__dict__['method'], types.FunctionType)  # unbound, it is a function

assert isinstance(len, types.BuiltinFunctionType)     # written in C
assert not isinstance(len, types.FunctionType)
assert callable(len) and callable(plain)

assert isinstance(None, types.NoneType)
assert isinstance(list[int], types.GenericAlias)
```

## SimpleNamespace

### Construction Copies, vars() Does Not

Building a namespace copies its entries into a dict of its own, so it does not follow the dict it
was built from. `vars()` hands back that dict itself, at no cost.

```python
import types

settings = {'host': 'localhost', 'port': 8080}
ns = types.SimpleNamespace(**settings)  # O(n) - copies the entries
settings['port'] = 9090
assert ns.port == 8080                  # the namespace has its own dict

assert vars(ns) is ns.__dict__          # O(1) - no copy
vars(ns)['debug'] = True                # so writing to it changes the namespace
assert ns.debug is True

ns.port = 443                           # O(1)
del ns.host                             # O(1)
assert ns == types.SimpleNamespace(port=443, debug=True)  # O(n)
assert ns != {'port': 443, 'debug': True}                 # a namespace never equals a dict
assert repr(ns) == 'namespace(port=443, debug=True)'      # O(n)
```

## MappingProxyType

### A Live View, Not a Copy

A proxy wraps the mapping it is given, so building one costs nothing and every later change to the
mapping shows through. The two operations that produce something new, `copy()` and `|`, return a
plain `dict`.

```python
import types

registry = {'a': 1, 'b': 2}
view = types.MappingProxyType(registry)  # O(1) - wraps, copies nothing

registry['c'] = 3
assert view['c'] == 3 and len(view) == 3     # O(1) - changes show through
assert list(view.keys()) == ['a', 'b', 'c']  # keys() is O(1); list() is O(n)

try:
    view['d'] = 4
except TypeError as error:
    assert 'does not support item assignment' in str(error)
else:
    raise AssertionError('a proxy accepted an assignment')

snapshot = view.copy()  # O(n) - a plain dict
snapshot['d'] = 4
assert 'd' not in view

merged = view | {'e': 5}  # O(n + m) - also a plain dict
assert type(merged) is dict and 'e' not in view
```

## Building Functions and Classes Dynamically

### FunctionType

A function built from an existing code object shares that code object, its globals and its
closure cells. Two functions built over the same cells see each other's writes.

```python
import types

def scale(x, factor=2):
    return x * factor

clone = types.FunctionType(scale.__code__, scale.__globals__, 'clone', (10,))  # O(c)
assert clone(3) == 30
assert clone.__code__ is scale.__code__  # shared, not copied
assert clone.__name__ == 'clone'

def counter():
    count = 0
    def bump():
        nonlocal count
        count += 1
        return count
    return bump

bump = counter()
twin = types.FunctionType(bump.__code__, bump.__globals__, closure=bump.__closure__)  # O(c)
assert bump() == 1
assert twin() == 2  # the same cell
```

### new_class

`new_class()` is the functional form of a `class` statement. It resolves `__mro_entries__` and calls
the metaclass's `__prepare__` the way the statement does, which a direct call to `type()` does not.

```python
import types

def body(ns):
    ns['greeting'] = 'hello'

Scores = types.new_class('Scores', (list[int],), exec_body=body)  # O(b + n)
assert Scores.__bases__ == (list,)            # list[int] resolved to list
assert Scores.__orig_bases__ == (list[int],)  # the original is kept
assert Scores().greeting == 'hello'

try:
    type('Scores', (list[int],), {})
except TypeError as error:
    assert 'new_class' in str(error)
else:
    raise AssertionError('type() accepted a generic alias base')

meta, ns, kwds = types.prepare_class('Plain', (), {'metaclass': type})  # O(b)
assert meta is type and ns == {} and kwds == {}

bases = (int,)
assert types.resolve_bases(bases) is bases  # O(b) - nothing to resolve, the same tuple
```

## Coroutine Adapters

`types.coroutine()` marks a generator function as awaitable. It changes the function it is given
rather than wrapping it, so the cost is paid once, at decoration.

```python
import types

def ticker():
    yield

marked = types.coroutine(ticker)  # O(k), once
assert marked is ticker           # the same function, now awaitable

async def main():
    await ticker()
    return 'done'

coro = main()
coro.send(None)  # the bare yield suspends main()
try:
    coro.send(None)
except StopIteration as stop:
    assert stop.value == 'done'
else:
    raise AssertionError('main() did not finish')
```

## Common Patterns

### Read-Only Defaults

```python
import types

_DEFAULTS = {'timeout': 30, 'retries': 3}
DEFAULTS = types.MappingProxyType(_DEFAULTS)  # O(1)

def effective(overrides):
    return DEFAULTS | overrides  # O(n + m) - a fresh dict each call

assert effective({'retries': 5}) == {'timeout': 30, 'retries': 5}
assert DEFAULTS['retries'] == 3
```

### Attribute Access over Parsed Data

```python
import json
import types

text = '{"db": {"host": "localhost", "port": 5432}, "debug": false}'
config = json.loads(text, object_hook=lambda d: types.SimpleNamespace(**d))  # O(n) per object

assert config.db.port == 5432  # O(1) per attribute
assert config.debug is False
```

## Performance Best Practices

✅ **Do**:

- Expose a dict read-only with `MappingProxyType`: O(1), and it stays current where `dict(d)` is an
  O(n) snapshot
- Use `vars(ns)` when a namespace is needed as a mapping; it is the namespace's own dict, O(1)
- Use `types.new_class()` when bases or the metaclass are only known at run time; it runs
  `__mro_entries__` and `__prepare__` the way a `class` statement does

❌ **Avoid**:

- `dict(proxy)` or `proxy.copy()` just to read; the proxy already answers lookups in O(1)
- Treating a proxy as a snapshot: it follows every later change to its mapping
- Expecting a namespace built from a dict to track that dict: construction copied it

## Version Notes

- **Python 3.11+**: `types.coroutine()` copies a generator function's bytecode when it swaps the
  code object, O(k); 3.10 shares it
- **Python 3.12+**: Added `get_original_bases()`
- **Python 3.13+**: Added `CapsuleType`; `SimpleNamespace` accepts a mapping or an iterable of
  pairs as a positional argument, and supports `copy.replace()`
- **Python 3.14+**: `UnionType` is `typing.Union`, so `typing.Union[int, str]` is an instance too

## Related Modules

- **[inspect](inspect.md)** - `isfunction()`, `ismethod()` and the other predicates test against
  these types
- **[typing](typing.md)** - annotations; `list[int]` builds a `GenericAlias` and `int | str` a
  `UnionType`
- **[collections.abc](collections.abc.md)** - check for a protocol instead of a concrete type
- **[dataclasses](dataclasses.md)** - a declared record type where `SimpleNamespace` is too loose
