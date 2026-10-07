# dataclasses Module Complexity

The `dataclasses` decorator reads a class's annotations, writes the methods a data-holding class
needs — `__init__`, `__repr__`, `__eq__` and optionally ordering and hashing — as Python source,
compiles them, and attaches them to the class. That work happens once, when the class statement
runs; after it, an instance is an ordinary object, and the generated `__init__`, `__repr__`,
comparisons and `__hash__` each cost O(n) in its fields.

`asdict()` and `astuple()` are the exception. They walk everything an instance reaches and copy
it, so their cost follows the whole structure rather than the class.

`n` is the fields of one class, inherited fields included, and `N` is the values `asdict()` or
`astuple()` visits: every field, container element and dictionary key under the instance, with a
value reached by two paths counted twice. Each field's own `==`, `<`, `hash()` and `repr()`, a
`default_factory`, `__post_init__`, a `dict_factory` or `tuple_factory`, and the `copy.deepcopy()`
of a value `asdict()` does not recurse into are priced at O(1). The bounds assume a hierarchy a few
dataclasses deep: decorating a class also reads the field table of every dataclass base.

## Complexity Reference

### Defining a dataclass

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `@dataclasses.dataclass(cls=None, /, *, init=True, repr=True, eq=True, order=False, unsafe_hash=False, frozen=False, ...)` | O(n) | O(n) | Runs once per class statement; the generated methods are compiled then |
| `dataclasses.field(*, default=MISSING, default_factory=MISSING, init=True, repr=True, ...)` | O(1) | O(1) | Records the options; `default_factory` is called by `__init__`, not here |
| `dataclasses.make_dataclass(cls_name, fields, *, bases=(), namespace=None, ...)` | O(n) | O(n) | Builds the class, then applies the decorator; every call makes a new class |

### Generated methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Generated `__init__(...)` | O(n) | O(n) | Assigns the fields; `slots=True` stores them more compactly at the same bound |
| Attribute access on an instance | O(1) | O(1) | An instance `__dict__` lookup, or a slot descriptor with `slots=True` |
| Generated `__repr__()` | O(n) | O(n) | Formats every field with `repr=True`, the default, into one string |
| Generated `__eq__(other)` | O(n) | O(n), O(1) from 3.13 | Before 3.13 it builds a tuple of each side's fields; from 3.13 it compares field by field |
| Generated `__lt__`, `__le__`, `__gt__`, `__ge__` | O(n) | O(n) | With `order=True`; each builds a tuple of each side's fields on every version |
| Generated `__hash__()` | O(n) | O(n) | Hashes a tuple of the fields; generated for `eq=True, frozen=True` or `unsafe_hash=True`, while `eq=True` alone sets `__hash__` to `None` unless the class defines one |
| Generated `__setattr__`, `__delattr__` | O(1) | O(1) | With `frozen=True`; raise `FrozenInstanceError` on an instance of the decorated class |

### Field

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dataclasses.Field` | O(1) | O(1) | What `field()` returns and `fields()` hands back |
| `Field.name`, `Field.type`, `Field.default`, `Field.default_factory`, `Field.init`, `Field.repr`, `Field.hash`, `Field.compare`, `Field.kw_only` | O(1) | O(1) | Plain attributes recorded when the class is decorated |
| `Field.metadata` | O(1) | O(1) | A read-only view of the mapping passed to `field()`, not a copy |
| `Field.doc` | O(1) | O(1) | Python 3.14+ |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dataclasses.fields(class_or_instance)` | O(n) | O(n) | Builds the tuple on every call, nothing is cached; `InitVar` and `ClassVar` pseudo-fields are left out |
| `dataclasses.asdict(obj, *, dict_factory=dict)` | O(N) | O(N) | Recurses into dataclasses, lists, tuples and dicts and deep-copies anything else |
| `dataclasses.astuple(obj, *, tuple_factory=tuple)` | O(N) | O(N) | The same walk, into tuples |
| `dataclasses.replace(obj, /, **changes)` | O(n) | O(n) | Calls `__init__`, and so `__post_init__`; an `init=False` field in `changes` raises |
| `dataclasses.is_dataclass(obj)` | O(1) | O(1) | True for a dataclass and for its instances |

### Markers, constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dataclasses.InitVar[T]`, `InitVar.type` | O(1) | O(1) | A parameter that reaches `__post_init__` and is not stored; `.type` is `T` |
| `dataclasses.KW_ONLY` | O(1) | O(1) | A marker in the field order; fields after it default to keyword-only |
| `dataclasses.MISSING` | O(1) | O(1) | The sentinel for "no default", distinct from `None` |
| `dataclasses.FrozenInstanceError` | O(1) | O(1) | An `AttributeError`, raised by a frozen instance's `__setattr__` and `__delattr__` |

## Defining a Dataclass

### Simple Definition

```python
from dataclasses import dataclass

@dataclass  # O(n) - once, when the class statement runs
class Point:
    x: float
    y: float

point = Point(1.0, 2.0)  # O(n) - one assignment per field

assert point.x == 1.0                        # O(1)
assert repr(point) == 'Point(x=1.0, y=2.0)'  # O(n)
assert point == Point(1.0, 2.0)              # O(n)
```

### Defaults and Factories

A plain default is evaluated once, when the class is created. A `default_factory` is called
inside `__init__` whenever the field is omitted, so its cost is paid per instance, not per
class.

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    name: str
    retries: int = 3                          # evaluated once, at class creation
    tags: list = field(default_factory=list)  # called when tags is omitted

first, second = Config('a'), Config('b')

assert Config.retries == 3
assert first.retries == 3
assert first.tags == [] and first.tags is not second.tags
```

!!! warning "A mutable default is rejected, not shared"
    `tags: list = []` raises `ValueError` when the class is created. From Python 3.11 that
    applies to any default whose class sets `__hash__` to `None`; 3.10 rejects only `list`, `dict`
    and `set`.

## Equality, Ordering and Hashing

The generated comparisons are O(n) in the fields. `__eq__` also decides whether instances can go
in a set: the default `eq=True`, without `frozen=True` or `unsafe_hash=True`, leaves the class
unhashable.

```python
from dataclasses import dataclass

@dataclass
class Mutable:
    a: int

@dataclass(frozen=True)
class Frozen:
    a: int

@dataclass(eq=False)
class Identity:
    a: int

# eq=True (the default) replaces __hash__ with None
assert Mutable.__hash__ is None
try:
    {Mutable(1)}
except TypeError as error:
    assert 'unhashable' in str(error)
else:
    raise AssertionError('an eq=True dataclass was hashed')

# frozen=True with eq=True gets a generated __hash__ - O(n)
assert len({Frozen(1), Frozen(1)}) == 1

# eq=False keeps object identity, and with it the inherited __hash__
assert Identity(1) != Identity(1)
assert len({Identity(1), Identity(1)}) == 2
```

### Ordering

`order=True` generates the four comparison methods, each comparing the fields in declaration
order as a tuple would.

```python
from dataclasses import dataclass

@dataclass(order=True)
class Version:
    major: int
    minor: int

assert Version(1, 2) < Version(1, 10)  # O(n)
assert sorted([Version(2, 0), Version(1, 5)])[0] == Version(1, 5)  # O(n) per comparison
```

## Frozen Instances

`frozen=True` installs a `__setattr__` and `__delattr__` that raise for a field. The generated
`__init__` goes around them, so construction stays O(n).

```python
from dataclasses import FrozenInstanceError, dataclass

@dataclass(frozen=True)
class Point:
    x: float
    y: float

point = Point(1.0, 2.0)  # O(n)

try:
    point.x = 5.0
except FrozenInstanceError as error:
    assert 'cannot assign' in str(error)
else:
    raise AssertionError('a frozen field was assigned')

# It is an AttributeError, so ordinary attribute handling still catches it
assert issubclass(FrozenInstanceError, AttributeError)
```

## Init-Only Fields and Post-Init

`InitVar` parameters reach `__post_init__` and are never stored. `replace()` builds the new
instance through `__init__`, so `__post_init__` runs again and a derived field is recomputed
rather than copied.

```python
from dataclasses import InitVar, dataclass, field, replace

@dataclass
class Measurement:
    value: int
    scale: InitVar[int] = 2
    scaled: int = field(init=False, default=0)

    def __post_init__(self, scale):
        self.scaled = self.value * scale

first = Measurement(3)
assert (first.value, first.scaled) == (3, 6)

assert replace(first, value=4).scaled == 8  # O(n), and __post_init__ again

# A field __init__ does not accept is refused:
# ValueError before Python 3.13, TypeError from 3.13
try:
    replace(first, scaled=99)
except (TypeError, ValueError) as error:
    assert 'init=False' in str(error)
else:
    raise AssertionError('an init=False field was replaced')
```

## Keyword-Only Fields

`KW_ONLY` is a marker in the field order rather than a field: fields declared after it become
keyword-only in the generated `__init__` unless they say `field(kw_only=False)`.

```python
from dataclasses import KW_ONLY, dataclass, fields

@dataclass
class Request:
    url: str
    _: KW_ONLY
    timeout: int = 30

assert Request('http://x', timeout=5).timeout == 5
try:
    Request('http://x', 5)
except TypeError as error:
    assert 'positional' in str(error)
else:
    raise AssertionError('a keyword-only field was passed by position')

# The marker leaves no field behind
assert [f.name for f in fields(Request)] == ['url', 'timeout']  # O(n)
```

## Converting to dict and tuple

`asdict()` and `astuple()` are the expensive operations here, and not because of the field count.
Both recurse and copy what they find, so their cost is the values reached: a nested structure
costs its whole size, and an object referenced twice is converted twice.

```python
from dataclasses import asdict, astuple, dataclass

@dataclass
class Inner:
    values: list

@dataclass
class Outer:
    inner: Inner
    label: str

outer = Outer(Inner([1, 2, 3]), 'x')

converted = asdict(outer)  # O(N)
assert converted == {'inner': {'values': [1, 2, 3]}, 'label': 'x'}
assert converted['inner']['values'] is not outer.inner.values  # a copy

assert astuple(outer) == (([1, 2, 3],), 'x')  # O(N), the same walk

# One instance referenced twice comes back as two dictionaries
shared = Inner([1])
pair = asdict(Outer(Inner([shared, shared]), 'y'))  # O(N)
first, second = pair['inner']['values']
assert first == second and first is not second
```

!!! note "asdict() is not a cheap projection"
    For an instance without `slots=True`, `vars(obj)` returns the existing instance dictionary
    in O(1). Use `vars(obj).copy()` for a separate shallow dictionary in O(n), and `asdict()`
    only when you want the recursive copy.

```python
from dataclasses import dataclass

@dataclass
class Outer:
    inner: list
    label: str

outer = Outer([1, 2], 'x')

attributes = vars(outer)  # O(1) - the instance's own dictionary
assert attributes is outer.__dict__

shallow = attributes.copy()  # O(n)
assert shallow == attributes and shallow is not attributes
assert shallow['inner'] is outer.inner  # values are shared, not copied
```

## Introspection

```python
from dataclasses import MISSING, Field, InitVar, dataclass, field, fields, is_dataclass

@dataclass
class Point:
    x: float
    y: float = field(default=0.0, metadata={'unit': 'm'})
    scale: InitVar[int] = 1

# fields() builds its tuple on every call - O(n), nothing is cached
assert fields(Point) == fields(Point)
assert fields(Point) is not fields(Point)
assert [f.name for f in fields(Point)] == ['x', 'y']  # the InitVar is left out

first, second = fields(Point)
assert isinstance(first, Field)
assert first.default is MISSING          # the sentinel, not None
assert second.metadata['unit'] == 'm'    # O(1)

# is_dataclass answers for the class and for an instance - O(1)
assert is_dataclass(Point) and is_dataclass(Point(1.0))
assert not is_dataclass(object())
```

## Building a Dataclass at Run Time

`make_dataclass()` costs the same O(n) as the decorator, but it is an ordinary call: every call
builds a new class, so cache the result rather than calling it per use.

```python
from dataclasses import fields, make_dataclass

Point = make_dataclass('Point', [('x', float), ('y', float)])  # O(n)

assert [f.name for f in fields(Point)] == ['x', 'y']
assert Point(1.0, 2.0) == Point(1.0, 2.0)

# Two calls give two unrelated classes
assert make_dataclass('P', [('x', int)]) is not make_dataclass('P', [('x', int)])
```

## Inheritance

A subclass's generated methods cover its bases' fields too, base fields first, so `n` is the
total. A base's defaults also constrain what the subclass may declare without one.

```python
from dataclasses import dataclass, fields

@dataclass
class Base:
    a: int

@dataclass
class Derived(Base):
    b: int

assert [f.name for f in fields(Derived)] == ['a', 'b']  # O(n), inherited fields included
assert Derived(1, 2) != Derived(9, 2)  # __eq__ compares the base's field too

# A field with a default cannot be followed by one without
try:
    @dataclass
    class Broken(Base):
        c: int = 0
        d: int
except TypeError as error:
    assert 'non-default argument' in str(error)
else:
    raise AssertionError('a non-default field followed a default')
```

## Performance Best Practices

✅ **Do**:

- Use `frozen=True` when you want instances in a set or as dict keys; `eq=True` alone makes them
  unhashable
- Use `vars(obj)` for a top-level view and `asdict()` only when you want the recursive copy
- Use `field(default_factory=...)` for anything mutable
- Keep `__post_init__` cheap: `replace()` runs it again
- Call `make_dataclass()` once and keep the class

❌ **Avoid**:

- Reading `asdict()` as O(fields); it is O(values reached), and it copies them
- Calling `fields()` in a loop; it rebuilds its tuple every time
- Assuming a dataclass is hashable

## Version Notes

- **Python 3.10+**: `KW_ONLY`, and `kw_only`, `match_args` and `slots` on the decorator
- **Python 3.11+**: a default whose class sets `__hash__` to `None` is rejected, not only
  `list`, `dict` and `set`
- **Python 3.13+**: the generated `__eq__` compares field by field instead of building two
  tuples, so its space drops from O(n) to O(1); `replace()` raises `TypeError` rather than
  `ValueError` for an `init=False` field; `copy.replace()` accepts a dataclass instance

## Related Modules

- **[typing](typing.md)** - the annotations a dataclass reads its fields from
- **[collections](collections.md)** - `namedtuple`, the tuple-based alternative
- **[copy](copy.md)** - the deep copy `asdict()` applies to values it does not recurse into
