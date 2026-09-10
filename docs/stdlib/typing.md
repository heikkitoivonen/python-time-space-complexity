# typing Module Complexity

The `typing` module is where a program's type hints are built. Almost none of it does work at call
time — the cost lands when a module is imported, when a generic is parameterized, and when
something asks about the types afterwards.

Three sizes matter. **k** is the annotations on an object, **p** is the parameters in a
subscription, and **m** is the members of a protocol. Subscription bounds assume ordinary
type arguments with constant-time hashing and equality; **p** counts flattened arguments for unions.

The two operations worth knowing before you write anything: parameterizing a `typing` generic is
memoized, so a cache hit reuses `List[int]`; and `isinstance()` against a runtime-checkable
`Protocol` can walk its members even after earlier checks succeeded. From 3.12, successful
class-level structural checks have a constant-time cached path; instance data checks do not.

## Complexity Reference

### Introspection and helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.get_type_hints(obj)` | O(k·s) | O(k) | k = annotations, s = the source of each; string annotations are `eval`'d, and a class walks its whole MRO |
| `typing.get_origin(tp)` | O(1) | O(1) | Reads the origin of an already-built alias |
| `typing.get_args(tp)` | O(p) for explicit `Callable` parameters or `Annotated` metadata; otherwise O(1) | O(p) for those allocating cases; otherwise O(1) | Reconstructs a parameter list or origin-and-metadata tuple; ordinary aliases reuse their argument tuple |
| `typing.cast(typ, val)` | O(1) | O(1) | Returns `val` itself; the type is never looked at |
| `typing.is_typeddict(tp)`, `typing.is_protocol(tp)` | O(1) | O(1) | `is_protocol` is 3.13+ |
| `typing.get_protocol_members(tp)` | O(m) | O(m) | Python 3.13+; builds the member set |
| `typing.get_overloads(func)`, `typing.clear_overloads()` | O(v) | O(v) | Python 3.11+; v = registered variants |
| `typing.assert_type(val, typ)`, `typing.reveal_type(val)` | O(1) | O(1) | Python 3.11+; both return the value, `reveal_type` also writes to stderr |
| `typing.assert_never(arg)` | O(1) | O(1) | Python 3.11+; always raises |
| `typing.evaluate_forward_ref(ref)` | Depends on evaluation and resolved type | Depends on evaluation and resolved type | Python 3.14+; evaluates the expression and recursively traverses the resulting hint; source length alone gives no bound |
| `typing.no_type_check(arg)`, `typing.no_type_check_decorator(dec)` | O(a) | O(1) | a = attributes on a class, each marked in turn |

### Building parameterized types

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.List[X]`, `typing.Dict[K, V]`, `typing.Type[X]` | O(1) | O(1) | Fixed arity; a cache hit reuses the alias |
| `typing.Tuple[...]` | O(p), including hits with fresh parameter tuples | O(p) on construction; O(1) auxiliary on a hit with an existing parameter tuple | From 3.14, reusing the same already-hashed tuple permits O(1) hits |
| `typing.Optional[X]`, `typing.Union[X, Y]` | O(p) expected | O(p) | Ordinary hashable types use hash-based deduplication; from 3.14 the result is `X \| Y` and no longer memoized |
| `typing.Literal[...]`, `typing.Annotated[X, ...]` | O(p) | O(p) | `Literal` deduplicates its values, `Annotated` keeps its metadata verbatim |
| `typing.Callable[[...], R]`, `typing.Concatenate[...]` | O(p) | O(p) | p = parameter types |
| `typing.ClassVar[X]`, `typing.Final[X]`, `typing.Required[X]`, `typing.NotRequired[X]`, `typing.ReadOnly[X]` | O(1) | O(1) | `Required`/`NotRequired` are 3.11+, `ReadOnly` 3.13+ |
| `typing.TypeGuard[X]`, `typing.TypeIs[X]`, `typing.Unpack[X]` | O(1) | O(1) | `TypeIs` is 3.13+, `TypeGuard` 3.10+, `Unpack` 3.11+ |

### Declaring types

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.TypeVar(...)`, `typing.TypeVarTuple(...)`, `typing.ParamSpec(...)` | O(c) | O(c) | c = constraints or bounds; `TypeVarTuple` is 3.11+ |
| `typing.ParamSpecArgs`, `typing.ParamSpecKwargs` | O(1) | O(1) | The `.args` and `.kwargs` of a `ParamSpec` |
| `typing.NewType(name, tp)` | O(1) | O(1) | The result is a callable that returns its argument unchanged |
| `typing.NamedTuple`, `typing.TypedDict` | O(k) | O(k) | k = fields; one class is built per declaration, at import time |
| `typing.Generic`, `typing.Protocol` | O(p) | O(p) | Subclassing costs its parameters; see the protocol note below |
| `typing.TypeAlias`, `typing.TypeAliasType` | O(1) | O(1) | `TypeAliasType` is 3.12+ and evaluates its value lazily |
| `typing.ForwardRef(arg)` | Compilation cost on 3.10–3.13; O(1) from 3.14 | Compilation storage on 3.10–3.13; O(1) auxiliary from 3.14 | Older versions eagerly compile the source (at least a scan of its length); 3.14 retains the string and defers compilation |

### Decorators

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.overload(func)` | O(1) | O(1) | Registers the variant and returns a stub that raises if called |
| `typing.final(f)`, `typing.override(m)` | O(1) | O(1) | Sets one attribute; `override` is 3.12+ |
| `typing.runtime_checkable(cls)` | O(1) before 3.12.2; O(m) from 3.12.2 | O(1) before 3.12.2; up to O(m) from 3.12.2 | Newer versions classify and retain non-method member names |
| `typing.dataclass_transform(...)` | O(1) | O(1) | Python 3.11+; sets one attribute for the type checker |

### Markers with no parameters

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.Any`, `typing.AnyStr`, `typing.NoReturn`, `typing.Never`, `typing.Self`, `typing.LiteralString`, `typing.NoDefault` | O(1) | O(1) | Module singletons; `Never`, `Self` and `LiteralString` are 3.11+, `NoDefault` 3.13+ |
| `typing.TYPE_CHECKING` | O(1) | O(1) | `False` at runtime, always |

### Aliases of concrete and abstract collections

The collection aliases below are available at import time. Unparameterized aliases such as
`List` and `Mapping` support `isinstance()`; their parameterized forms, such as `List[int]`
and `Mapping[str, int]`, raise `TypeError` in runtime checks.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `typing.List`, `typing.Dict`, `typing.Set`, `typing.FrozenSet`, `typing.Tuple`, `typing.Type`, `typing.Text` | O(1) | O(1) | Deprecated since 3.9 in favour of `list`, `dict`, and friends |
| `typing.Deque`, `typing.DefaultDict`, `typing.OrderedDict`, `typing.ChainMap`, `typing.Counter` | O(1) | O(1) | The `collections` equivalents |
| `typing.AbstractSet`, `typing.MutableSet`, `typing.Mapping`, `typing.MutableMapping`, `typing.Sequence`, `typing.MutableSequence`, `typing.ByteString` | O(1) | O(1) | The `collections.abc` equivalents |
| `typing.MappingView`, `typing.ItemsView`, `typing.KeysView`, `typing.ValuesView` | O(1) | O(1) | The view types a mapping returns |
| `typing.Iterable`, `typing.Iterator`, `typing.Generator`, `typing.Reversible`, `typing.Container`, `typing.Collection`, `typing.Hashable`, `typing.Sized` | O(1) | O(1) | |
| `typing.Awaitable`, `typing.Coroutine`, `typing.AsyncIterable`, `typing.AsyncIterator`, `typing.AsyncGenerator`, `typing.ContextManager`, `typing.AsyncContextManager` | O(1) | O(1) | |
| `typing.Match`, `typing.Pattern` | O(1) | O(1) | The `re` result types |
| `typing.IO`, `typing.TextIO`, `typing.BinaryIO` | O(1) | O(1) | Generic classes rather than aliases |
| `typing.SupportsAbs`, `typing.SupportsBytes`, `typing.SupportsComplex`, `typing.SupportsFloat`, `typing.SupportsIndex`, `typing.SupportsInt`, `typing.SupportsRound` | O(1) | O(1) | One-method runtime-checkable protocols |

## Subscription Is Memoized

For cacheable subscriptions such as `List[int]`, a cache hit returns the same alias. Variable-arity
`Tuple[...]` still costs O(p) on a hit with a fresh parameter tuple. From 3.14, reusing
the same already-hashed tuple permits O(1) hits. The builtin generics — `list[int]`,
`dict[str, int]` — do not share that cache and build a fresh alias each time.

```python
from typing import Dict, List

# The same object, not merely an equal one
assert List[int] is List[int]                 # O(1) after the first
assert Dict[str, int] is Dict[str, int]

# The builtin form is not cached
assert list[int] is not list[int]
assert list[int] == list[int]
```

## Union Flattens and Deduplicates

`Union` is not a plain container of its arguments: nested unions are flattened and duplicates
removed. For ordinary hashable types this takes expected O(p) time and O(p) space. Hash
collisions can require quadratic work; that is separate from the normal hash-based bound.

```python
from typing import Optional, Union, get_args

assert Union[int, str, int] == Union[int, str]           # deduplicated
assert Union[int, Union[str, float]] == Union[int, str, float]  # flattened
assert Optional[int] == Union[int, None]

assert set(get_args(Union[int, str])) == {int, str}      # O(1) to read back
```

!!! note "Unions changed shape in Python 3.14"
    From 3.14, `Union[int, str]` produces the same object as `int | str` — a `types.UnionType`
    rather than a `typing.Union` alias — and it is no longer memoized, so two identical unions are
    equal but not identical. Compare unions with `==`, never with `is`.

## Runtime Protocol Checks

`runtime_checkable` lets `isinstance()` work against a `Protocol`. On Python 3.10 and 3.11 each
check walks the protocol's members with `hasattr`, so a wide protocol costs more than a narrow one.
From 3.12, a cached successful class-level structural check takes O(1). Protocols with instance
data members still inspect up to m attributes on each check, and unsuccessful class-level
checks can fall through to that member walk. These bounds assume constant-cost attribute access
and fixed inheritance depth.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...

class Handle:
    def close(self) -> None: ...

assert isinstance(Handle(), Closeable)  # O(m) before 3.12, O(1) cached from 3.12
assert not isinstance(object(), Closeable)

# Only a protocol marked runtime_checkable can be used this way
class Unmarked(Protocol):
    def close(self) -> None: ...

try:
    isinstance(Handle(), Unmarked)
except TypeError as error:
    assert 'runtime_checkable' in str(error)

# A data member is not covered by that cache: the check reads the instance,
# so its cost follows the member count on every version
@runtime_checkable
class Sized2D(Protocol):
    width: int
    height: int

class Box:
    def __init__(self):
        self.width = self.height = 1

assert isinstance(Box(), Sized2D)   # O(m), cached or not
```

!!! warning "isinstance checks members, not signatures"
    A runtime protocol check asks only whether the attributes exist. A `close` taking the wrong
    arguments still passes, and `issubclass()` against a protocol with non-method members raises
    `TypeError`.

## Annotations Are Not Free Before 3.14

An annotation is an expression, and on Python 3.10 through 3.13 it is evaluated when the `def`
runs. A function with three parameterized hints costs about fifteen times a bare one to define —
once, at import. From 3.14, annotations are evaluated lazily and that gap nearly closes.

```python
from typing import Dict, List, Optional

# Evaluated at definition time before 3.14, lazily from 3.14
def transform(rows: Dict[str, List[int]], limit: Optional[int]) -> List[int]:
    return []

# Either way, calling it checks nothing
assert transform("not a dict", "not an int") == []
```

The two ways to avoid the definition-time cost on every supported version:

```python
from __future__ import annotations  # every annotation becomes a string

from typing import TYPE_CHECKING

# Imports needed only by hints can be skipped at runtime entirely
assert TYPE_CHECKING is False
if TYPE_CHECKING:
    import decimal  # never imported when the program runs
```

## Reading Hints Back

`get_type_hints()` is the expensive introspection: it resolves every annotation, evaluating string
ones, and for a class it merges the annotations of the whole MRO.

```python
from typing import Dict, List, get_args, get_origin, get_type_hints

def transform(rows: Dict[str, List[int]], limit: int) -> List[int]:
    return []

hints = get_type_hints(transform)  # O(k·s)
assert hints['limit'] is int
assert hints['return'] == List[int]

# Origin and ordinary-alias arguments are O(1); Callable/Annotated get_args can copy
assert get_origin(Dict[str, int]) is dict
assert get_args(Dict[str, int]) == (str, int)
```

## Declaring Types

`NamedTuple` and `TypedDict` build a class per declaration, costing their field count once at
import. `NewType` is cheaper than it looks — the result is a function that returns its argument.

```python
from typing import NamedTuple, NewType, TypedDict, is_typeddict

class Point(NamedTuple):     # O(k) in fields, once at import
    x: float
    y: float

class Config(TypedDict):     # O(k) in fields, once at import
    name: str
    retries: int

UserId = NewType('UserId', int)  # O(1)

assert Point(1.0, 2.0).x == 1.0
assert is_typeddict(Config) is True
assert is_typeddict(Point) is False
assert UserId(7) == 7  # the call returns its argument unchanged
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

## Version Notes

- **Python 3.11+**: `Self`, `Never`, `LiteralString`, `Required`, `NotRequired`, `TypeVarTuple`,
  `Unpack`, `assert_type`, `assert_never`, `reveal_type`, `dataclass_transform`, `get_overloads`,
  `clear_overloads`
- **Python 3.12+**: `override`, `TypeAliasType`, and a constant-time path for cached successful
  class-level protocol checks
- **Python 3.13+**: `TypeIs`, `ReadOnly`, `NoDefault`, `is_protocol`, `get_protocol_members`
- **Python 3.14+**: `evaluate_forward_ref`; annotations are evaluated lazily, and `Union[X, Y]`
  produces `X | Y` and is no longer memoized

## Related Modules

- **[dataclasses](dataclasses.md)** - annotations that do build something at import
- **[collections](collections.md)** - what the collection aliases point at
- **[abc](abc.md)** - the registration mechanism behind `isinstance` on an ABC

## Best Practices

✅ **Do**:

- Compare types with `==`, not `is` — the memoization is an implementation detail, and 3.14 drops
  it for unions
- Keep hint-only imports behind `TYPE_CHECKING`
- Call `get_type_hints()` once and keep the result if you need it repeatedly
- Use the builtin generics (`list[int]`) in new code; the `typing` aliases are deprecated

❌ **Avoid**:

- Repeated protocol checks in a hot loop when they must inspect members: on 3.10–3.11,
  and for instance data checks on newer versions too
- Treating a runtime protocol check as a signature check; it only looks for the names
- `get_type_hints()` inside a request path — it re-resolves the whole MRO every call
- Assuming annotations are free before 3.14
