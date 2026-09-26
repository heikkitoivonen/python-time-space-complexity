# typing Module Complexity

The `typing` module is where a program's type hints are built. Almost none of it does work when
the annotated code runs: the cost lands when a hint is evaluated, when a generic is parameterized,
and when something reads the hints back.

`k` is the annotations on an object, or the fields of a declared class; `p` is the type arguments
in one subscription, counted after flattening for a union; `m` is the members of a protocol,
inherited ones included; and `a` is the attributes defined on a class and on its bases. Bounds
treat hashing and comparing a type argument, reading an attribute and evaluating one ordinary
annotation as O(1).

## Complexity Reference

### Introspection helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.get_type_hints(obj, globalns=None, localns=None, include_extras=False)` | O(k) for a function or module; O(k + a) for a class | O(k) for a function or module; O(k + a) for a class | For a class, the namespace of every class on the MRO is copied to evaluate its hints; nothing is cached, so string annotations are evaluated again on every call |
| `typing.get_origin(tp)` | O(1) | O(1) | Reads the origin of an already-built alias |
| `typing.get_args(tp)` | O(1); O(p) for `Callable` with a parameter list and for `Annotated` | O(1); O(p) for `Callable` with a parameter list and for `Annotated` | An ordinary alias hands back its stored argument tuple; `Callable` rebuilds its parameter list and `Annotated` prepends its origin |
| `typing.cast(typ, val)` | O(1) | O(1) | Returns `val` itself; the type is never looked at |
| `typing.is_typeddict(tp)`, `typing.is_protocol(tp)` | O(1) | O(1) | `is_protocol` is 3.13+ |
| `typing.get_protocol_members(tp)` | O(m) | O(m) | Python 3.13+; copies the member set into a new `frozenset` |
| `typing.get_overloads(func)` | O(v) | O(v) | Python 3.11+; v = variants registered for `func` |
| `typing.clear_overloads()` | O(o) | O(1) | Python 3.11+; o = variants registered for every function in the process |
| `typing.assert_type(val, typ)`, `typing.reveal_type(val)` | O(1) | O(1) | Python 3.11+; both return the value, `reveal_type` also writes its type's name to stderr |
| `typing.assert_never(arg)` | O(r) | O(r) | Python 3.11+; always raises. r = length of `repr(arg)`, built in full before the message is cut short |
| `typing.evaluate_forward_ref(forward_ref, *, owner=None, globals=None, locals=None, type_params=None, format=None)` | O(e + t) | O(e + t) | Python 3.14+; e = the cost of evaluating the expression, t = the size of the type it resolves to, which is walked to resolve nested forward references |
| `typing.no_type_check(arg)` | O(a log a) | O(a) | Visits every name `dir()` lists for a class, inherited ones included, and recurses into nested classes; on 3.10 only the class's own attributes |
| `typing.no_type_check_decorator(decorator)` | O(1) | O(1) | Wraps `decorator`; deprecated since 3.13 |

### Building parameterized types

A subscription goes through a cache, so repeating one returns the alias already built. The cache
keeps only recent subscriptions, which is why identity is not guaranteed.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.List[X]`, `typing.Dict[K, V]`, `typing.Type[X]` | O(1) | O(1) | Fixed arity; a cache hit reuses the alias |
| `typing.Tuple[...]` | O(p) | O(p) | A cache hit still hashes the p arguments of a freshly built argument tuple |
| `typing.Optional[X]`, `typing.Union[X, Y, ...]` | O(p) | O(p) | Flattens nested unions and drops duplicates; from 3.14 the result is `X \| Y` and is not cached |
| `typing.Literal[...]`, `typing.Annotated[X, ...]` | O(p) | O(p) | `Literal` drops duplicate values, `Annotated` keeps its metadata verbatim |
| `typing.Callable[[...], R]`, `typing.Concatenate[...]` | O(p) | O(p) | p = parameter types |
| `typing.ClassVar[X]`, `typing.Final[X]`, `typing.Required[X]`, `typing.NotRequired[X]`, `typing.ReadOnly[X]` | O(1) | O(1) | `Required`/`NotRequired` are 3.11+, `ReadOnly` 3.13+ |
| `typing.TypeGuard[X]`, `typing.TypeIs[X]`, `typing.Unpack[X]` | O(1) | O(1) | `Unpack` is 3.11+, `TypeIs` 3.13+ |

### Declaring types

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.TypeVar(name, *constraints, bound=None, ...)` | O(c) | O(c) | c = constraints |
| `typing.TypeVarTuple(name)`, `typing.ParamSpec(name)` | O(1) | O(1) | `TypeVarTuple` is 3.11+ |
| `typing.NewType(name, tp)` | O(1) | O(1) | Builds a callable that returns its argument unchanged |
| `typing.NamedTuple`, `typing.TypedDict` | O(k) | O(k) | k = fields, inherited ones included; one class per declaration, built when the `class` statement runs |
| `class C(typing.Generic[T, ...])` | O(p) | O(p) | Collects the type parameters of its bases, on top of what the class body costs |
| `class P(typing.Protocol)` | O(p + m) | O(p + m) | From 3.12 the m member names are also collected and kept for runtime checks |
| `typing.TypeAlias` | O(1) | O(1) | A marker for the type checker |
| `typing.TypeAliasType(name, value, *, type_params=())` | O(1) | O(1) | Python 3.12+; what a `type` statement builds |
| `typing.ForwardRef(arg)` | Compiles `arg` before 3.14; O(1) from 3.14 | Holds the compiled code before 3.14; O(1) from 3.14 | From 3.14 the string is kept and compiled only when evaluated |

### TypeVar, ParamSpec and TypeVarTuple

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TypeVar.has_default()`, `ParamSpec.has_default()`, `TypeVarTuple.has_default()` | O(1) | O(1) | Python 3.13+; does not evaluate a lazily defined default |
| `TypeVar.evaluate_bound`, `TypeVar.evaluate_constraints`, `TypeVar.evaluate_default`, `ParamSpec.evaluate_default`, `TypeVarTuple.evaluate_default` | O(1) | O(1) | Python 3.14+; `None`, or a function that evaluates the value; calling it costs what the expression costs |
| `ParamSpec.args`, `ParamSpec.kwargs` | O(1) | O(1) | `typing.ParamSpecArgs` and `typing.ParamSpecKwargs` instances, for `*args: P.args` and `**kwargs: P.kwargs` |

### TypeAliasType

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TypeAliasType.__value__` | O(e) on first access, then O(1) | O(e) | Python 3.12+; e = evaluating the value. A `type` statement defers it to the first read and keeps the result |
| `TypeAliasType.evaluate_value` | O(1) | O(1) | Python 3.14+; the function that evaluates the value |

### Decorators

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.overload(func)` | O(1) | O(1) | Returns a stub that raises if called; from 3.11 also registers the variant for `get_overloads` |
| `typing.final(f)`, `typing.override(m)` | O(1) | O(1) | Sets one attribute; `override` is 3.12+ |
| `typing.runtime_checkable(cls)` | O(1) before 3.12.2; O(m) from 3.12.2 | O(1) before 3.12.2; O(m) from 3.12.2 | From 3.12.2 it records which members are not methods |
| `typing.dataclass_transform(...)` | O(1) | O(1) | Python 3.11+; records its arguments for the type checker |

### Markers with no parameters

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.Any`, `typing.AnyStr`, `typing.NoReturn`, `typing.Never`, `typing.Self`, `typing.LiteralString`, `typing.NoDefault` | O(1) | O(1) | Module singletons; `Never`, `Self` and `LiteralString` are 3.11+, `NoDefault` 3.13+ |
| `typing.TYPE_CHECKING` | O(1) | O(1) | `False` at runtime, always |

### Aliases of concrete and abstract collections

The unparameterized aliases, such as `List` and `Mapping`, work with `isinstance()`; their
parameterized forms, such as `List[int]` and `Mapping[str, int]`, raise `TypeError` there.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.List`, `typing.Dict`, `typing.Set`, `typing.FrozenSet`, `typing.Tuple`, `typing.Type`, `typing.Text` | O(1) | O(1) | Deprecated in favour of `list`, `dict` and friends |
| `typing.Deque`, `typing.DefaultDict`, `typing.OrderedDict`, `typing.ChainMap`, `typing.Counter` | O(1) | O(1) | The `collections` equivalents |
| `typing.AbstractSet`, `typing.MutableSet`, `typing.Mapping`, `typing.MutableMapping`, `typing.Sequence`, `typing.MutableSequence`, `typing.ByteString` | O(1) | O(1) | The `collections.abc` equivalents |
| `typing.MappingView`, `typing.ItemsView`, `typing.KeysView`, `typing.ValuesView` | O(1) | O(1) | The view types a mapping returns |
| `typing.Iterable`, `typing.Iterator`, `typing.Generator`, `typing.Reversible`, `typing.Container`, `typing.Collection`, `typing.Hashable`, `typing.Sized` | O(1) | O(1) | |
| `typing.Awaitable`, `typing.Coroutine`, `typing.AsyncIterable`, `typing.AsyncIterator`, `typing.AsyncGenerator`, `typing.ContextManager`, `typing.AsyncContextManager` | O(1) | O(1) | |
| `typing.Match`, `typing.Pattern` | O(1) | O(1) | The `re` result types |
| `typing.IO`, `typing.TextIO`, `typing.BinaryIO` | O(1) | O(1) | Generic classes rather than aliases |
| `typing.SupportsAbs`, `typing.SupportsBytes`, `typing.SupportsComplex`, `typing.SupportsFloat`, `typing.SupportsIndex`, `typing.SupportsInt`, `typing.SupportsRound` | O(1) | O(1) | One-method runtime-checkable protocols |

## Parameterized Types

### Subscription Is Cached

Repeating a subscription such as `List[int]` returns the alias already built. The cache holds only
recent subscriptions, so an alias can be rebuilt later: compare types with `==`. The builtin
generics, `list[int]` and `dict[str, int]`, are not cached and build a fresh alias each time.

```python
from typing import Dict, List

# The same object, not merely an equal one
assert List[int] is List[int]                 # O(1) on a cache hit
assert Dict[str, int] is Dict[str, int]

# The builtin form is not cached
assert list[int] is not list[int]
assert list[int] == list[int]
```

### Union Flattens and Deduplicates

A union is not a plain container of its arguments: nested unions are flattened and duplicates
removed, in O(p) through hashing.

```python
from typing import Optional, Union, get_args

assert Union[int, str, int] == Union[int, str]           # deduplicated, O(p)
assert Union[int, Union[str, float]] == Union[int, str, float]  # flattened
assert Optional[int] == Union[int, None]

assert set(get_args(Union[int, str])) == {int, str}      # O(1) to read back
```

!!! note "Unions changed shape in Python 3.14"
    From 3.14, `Union[int, str]` produces the same object as `int | str` — a `types.UnionType`
    rather than a `typing.Union` alias — and it is not cached, so two identical unions are
    equal but not identical. Compare unions with `==`, never with `is`.

## Runtime Protocol Checks

`runtime_checkable` lets `isinstance()` work against a `Protocol`. On 3.10 and 3.11 every check
walks the protocol's m members. From 3.12, a class that has already passed is answered from a
cache in O(1); a check that fails, or a protocol with data members, still reads up to m
attributes of the instance each time.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...

class Handle:
    def close(self) -> None: ...

assert isinstance(Handle(), Closeable)  # O(m) before 3.12; O(1) once Handle has passed from 3.12
assert not isinstance(object(), Closeable)  # up to O(m)

# Only a protocol marked runtime_checkable can be used this way
class Unmarked(Protocol):
    def close(self) -> None: ...

try:
    isinstance(Handle(), Unmarked)
except TypeError as error:
    assert 'runtime_checkable' in str(error)
else:
    raise AssertionError('an unmarked protocol was checked')

# A data member lives on the instance, so the check reads it every time
@runtime_checkable
class Sized2D(Protocol):
    width: int
    height: int

class Box:
    def __init__(self):
        self.width = self.height = 1

assert isinstance(Box(), Sized2D)  # O(m) on every version
```

!!! warning "isinstance checks members, not signatures"
    A runtime protocol check asks only whether the attributes exist. A `close` taking the wrong
    arguments still passes, and `issubclass()` against a protocol with non-method members raises
    `TypeError`.

## Annotations and Definition Time

An annotation is an expression. On 3.10 through 3.13 it is evaluated when the `def` or `class`
statement runs, so every hint is paid for at import. From 3.14 annotations are evaluated lazily,
on the first read of `__annotations__`, and the result is kept.

```python
from typing import Dict, List, Optional

# Evaluated at definition time before 3.14, lazily from 3.14
def transform(rows: Dict[str, List[int]], limit: Optional[int]) -> List[int]:
    return []

# Either way, calling it checks nothing
assert transform("not a dict", "not an int") == []
```

Two ways to avoid the definition-time cost on every supported version:

```python
from __future__ import annotations  # every annotation becomes a string

from typing import TYPE_CHECKING

# Imports needed only by hints can be skipped at runtime entirely
assert TYPE_CHECKING is False
if TYPE_CHECKING:
    import decimal  # never imported when the program runs
```

## Reading Hints Back

`get_type_hints()` is the expensive introspection. It evaluates string annotations every time it is
called, and for a class it visits the whole MRO, copying each class's namespace to evaluate in —
so a class with few hints but many methods still pays for the methods.

```python
from typing import Dict, List, get_args, get_origin, get_type_hints

def transform(rows: Dict[str, List[int]], limit: 'int') -> List[int]:
    return []

hints = get_type_hints(transform)  # O(k); the string 'int' is evaluated here
assert hints['limit'] is int
assert hints['return'] == List[int]

class Base:
    base_field: int

class Derived(Base):
    own_field: str

assert get_type_hints(Derived) == {'base_field': int, 'own_field': str}  # O(k + a)

# Origin and ordinary arguments are O(1) reads
assert get_origin(Dict[str, int]) is dict
assert get_args(Dict[str, int]) == (str, int)
```

## Declaring Types

`NamedTuple` and `TypedDict` build a class per declaration, costing their field count once, when
the `class` statement runs. `NewType` is cheaper than it looks: calling the result returns its
argument unchanged.

```python
from typing import NamedTuple, NewType, TypedDict, is_typeddict

class Point(NamedTuple):     # O(k) in fields, once
    x: float
    y: float

class Config(TypedDict):     # O(k) in fields, once
    name: str
    retries: int

UserId = NewType('UserId', int)  # O(1)

assert Point(1.0, 2.0).x == 1.0
assert is_typeddict(Config) is True
assert is_typeddict(Point) is False
value = 7
assert UserId(value) is value  # the call returns its argument unchanged
```

## Casting Is a No-Op

`cast()` exists for the type checker. At runtime it returns the object it was given, without
looking at the type at all.

```python
from typing import List, cast

values = [1, 2, 3]

assert cast(List[str], values) is values  # O(1), and no conversion happens
assert cast('anything at all', values) is values
```

## Common Patterns

### Resolving Hints Once

Code that reads hints repeatedly, such as a serializer that looks up a class's fields per object,
should resolve them once per class and keep the result.

```python
from functools import cache
from typing import get_type_hints

@cache
def fields_of(cls):
    return get_type_hints(cls)  # O(k + a), once per class

class Row:
    name: str
    count: int

assert fields_of(Row) == {'name': str, 'count': int}
assert fields_of(Row) is fields_of(Row)  # O(1) after the first call
```

## Performance Best Practices

✅ **Do**:

- Compare types with `==`, not `is`: the subscription cache holds only recent entries, and from 3.14
  unions are not cached at all
- Keep hint-only imports behind `TYPE_CHECKING`, so the import is never paid at runtime
- Call `get_type_hints()` once per class and keep the result

❌ **Avoid**:

- Repeated protocol checks in a hot loop when they must read members: on 3.10–3.11 always, and on
  newer versions for failing checks and data-member protocols
- Treating a runtime protocol check as a signature check; it only looks for the names
- `get_type_hints()` on a request path: it re-evaluates string hints and copies every namespace on
  the MRO on each call
- Assuming annotations are free before 3.14: each one is evaluated at definition time

## Version Notes

- **Python 3.11+**: `Self`, `Never`, `LiteralString`, `Required`, `NotRequired`, `TypeVarTuple`,
  `Unpack`, `assert_type`, `assert_never`, `reveal_type`, `dataclass_transform`, `get_overloads`,
  `clear_overloads`
- **Python 3.12+**: `override`, `TypeAliasType`; a runtime protocol check a class has already
  passed is answered from a cache in O(1)
- **Python 3.13+**: `TypeIs`, `ReadOnly`, `NoDefault`, `is_protocol`, `get_protocol_members`,
  `has_default()`
- **Python 3.14+**: `evaluate_forward_ref`; annotations are evaluated lazily, `ForwardRef` no
  longer compiles its string when built, and `Union[X, Y]` produces `X | Y` and is not cached

## Related Modules

- **[annotationlib](annotationlib.md)** - reading lazily evaluated annotations from 3.14
- **[dataclasses](dataclasses.md)** - annotations that do build something at class creation
- **[collections](collections.md)** - what the collection aliases point at
- **[abc](abc.md)** - the registration mechanism behind `isinstance` on an ABC
