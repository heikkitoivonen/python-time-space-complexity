# dataclasses Module Complexity

The `dataclasses` decorator writes the methods a data-holding class needs — `__init__`, `__repr__`,
`__eq__` and optionally the ordering four — as Python source, compiles them, and attaches them to
the class. All of that happens once, when the module is imported. What is left at run time is
ordinary attribute access.

Two sizes matter. **n** is the fields on one class. **N** is the values a recursive walk reaches,
which is what `asdict()` and `astuple()` actually pay for — a flat class with 400 fields and a
chain of 400 nested one-field objects both cost their node count, not fields times depth.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `@dataclasses.dataclass` | O(n) | O(n) | n = fields; the generated methods are compiled once per class, at import |
| `dataclasses.field(...)` | O(1) | O(1) | Records the options; `default_factory` is called per instance, not here |
| `dataclasses.Field` | O(1) | O(1) | What `field()` returns and `fields()` hands back |
| Attribute access on an instance | O(1) | O(1) | An ordinary instance `__dict__` lookup; no descriptor is involved |
| Generated `__init__(...)` | O(n) | O(n) | The space is the fields it stores; `slots=True` keeps that O(n) at a smaller per-field constant. Factory and `__post_init__` costs are additional |
| Generated `__repr__()` | O(n) | O(n) | Formats every field into one string |
| Generated `__eq__(other)` | O(n) | O(n) | Compares the fields as two tuples; from 3.13 those are not materialized, making it O(1) |
| Generated `__lt__`/`__le__`/`__gt__`/`__ge__` | O(n) | O(n) | With `order=True`, the same tuple comparison |
| Generated `__hash__()` | O(n) | O(n) | Only with `frozen=True, eq=True`; `eq=True` alone sets `__hash__` to `None` |
| `dataclasses.replace(obj, **changes)` | O(n) | O(n) | Re-runs `__init__`, and therefore `__post_init__`; rejects an `init=False` field, with `ValueError` before 3.13 and `TypeError` from 3.13 |
| `dataclasses.asdict(obj)` | O(N) | O(N) | N = values reached; recurses into dataclasses, lists, tuples and dicts, and deep-copies what it finds |
| `dataclasses.astuple(obj)` | O(N) | O(N) | The same walk into a tuple |
| `dataclasses.fields(obj)` | O(n) | O(n) | Builds a fresh tuple each call; nothing is cached |
| `dataclasses.is_dataclass(obj)` | O(1) | O(1) | One attribute check, true for a class and for its instances |
| `dataclasses.make_dataclass(name, fields)` | O(n) | O(n) | Builds the class at run time, then applies the decorator |
| `dataclasses.InitVar[T]` | O(1) | O(1) | Marks a parameter that reaches `__post_init__` and is not stored |
| `dataclasses.KW_ONLY` | O(1) | O(1) | A marker in the field order; every field after it is keyword-only |
| `dataclasses.MISSING` | O(1) | O(1) | The sentinel for "no default", distinct from `None` |
| `dataclasses.FrozenInstanceError` | O(1) | O(1) | An `AttributeError`, raised by a frozen instance's `__setattr__` |

## Basic Dataclass

### Simple Definition

```python
from dataclasses import dataclass

# Generating the methods is O(n) in fields, and happens once at import
@dataclass
class Point:
    x: float
    y: float

# Creating an instance is O(n): one assignment per field
point = Point(1.0, 2.0)

assert point.x == 1.0            # O(1) - an ordinary attribute lookup
assert repr(point) == 'Point(x=1.0, y=2.0)'   # O(n)
assert point == Point(1.0, 2.0)  # O(n)
```

### Defaults and Factories

A plain default is stored on the class once. A `default_factory` is a callable invoked inside
`__init__`, so it costs whatever it costs — per instance, not per class.

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    name: str
    retries: int = 3                          # evaluated once, at class creation
    tags: list = field(default_factory=list)  # called on every instance

first, second = Config('a'), Config('b')

assert first.retries == 3
assert first.tags == [] and first.tags is not second.tags
```

!!! warning "A mutable default is rejected, not shared"
    `tags: list = []` raises `ValueError` when the class is created. That is the module refusing
    the shared-mutable-default bug rather than letting you write it.

## Equality, Ordering and Hashing

The generated `__eq__` compares the fields as two tuples, so it is O(n) — and it is also what
decides whether the class can go in a set.

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

# eq=True (the default) replaces __hash__ with None: the class becomes unhashable
assert Mutable.__hash__ is None
try:
    {Mutable(1)}
except TypeError as error:
    assert 'unhashable' in str(error)

# frozen=True with eq=True gets a generated __hash__ - O(n) over the fields
assert len({Frozen(1), Frozen(1)}) == 1

# eq=False keeps object identity, and with it the inherited __hash__
assert Identity(1) != Identity(1)
assert len({Identity(1), Identity(1)}) == 2
```

### Ordering

`order=True` generates the four comparison methods, each an O(n) tuple comparison over the fields
in declaration order.

```python
from dataclasses import dataclass

@dataclass(order=True)
class Version:
    major: int
    minor: int

assert Version(1, 2) < Version(1, 10)        # O(n)
assert sorted([Version(2, 0), Version(1, 5)])[0] == Version(1, 5)
```

## Frozen Instances

`frozen=True` installs a `__setattr__` that raises. It also changes `__init__`: each field is
assigned through `object.__setattr__` rather than directly, which is why constructing a frozen
instance costs a little more than a mutable one.

```python
from dataclasses import FrozenInstanceError, dataclass

@dataclass(frozen=True)
class Point:
    x: float
    y: float

point = Point(1.0, 2.0)

try:
    point.x = 5.0
except FrozenInstanceError as error:
    assert 'cannot assign' in str(error)

# It is an AttributeError, so ordinary attribute handling still catches it
assert issubclass(FrozenInstanceError, AttributeError)
```

## Init-Only Fields and Post-Init

`InitVar` parameters reach `__post_init__` and are never stored. `replace()` re-runs `__init__`,
so `__post_init__` runs again — which is the behaviour to know, because a derived field is
recomputed rather than copied.

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

# replace() rebuilds through __init__, so scaled is recomputed - O(n)
assert replace(first, value=4).scaled == 8

# and a field it cannot pass to __init__ is refused outright.
# The exception is ValueError before 3.13 and TypeError from 3.13.
try:
    replace(first, scaled=99)
except (TypeError, ValueError) as error:
    assert 'init=False' in str(error)
```

## Keyword-Only Fields

`KW_ONLY` is a marker in the field order rather than a field of its own: everything declared after
it becomes keyword-only in the generated `__init__`.

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

# The marker leaves no field behind
assert [f.name for f in fields(Request)] == ['url', 'timeout']
```

## Converting to dict and tuple

`asdict()` and `astuple()` are the expensive operations here, and not because of the field count.
Both walk recursively and **deep-copy** what they find, so their cost is the number of values
reached — a nested structure costs its whole size, not the top class's field count.

```python
import copy
from dataclasses import asdict, astuple, dataclass

@dataclass
class Inner:
    values: list

@dataclass
class Outer:
    inner: Inner
    label: str

outer = Outer(Inner([1, 2, 3]), 'x')

converted = asdict(outer)  # O(N) in values reached
assert converted == {'inner': {'values': [1, 2, 3]}, 'label': 'x'}

# The list is a copy, not the original
assert converted['inner']['values'] is not outer.inner.values

assert astuple(outer) == (([1, 2, 3],), 'x')  # O(N), same walk

# Access the existing instance dictionary - O(1) time and space
attributes = vars(outer)
assert attributes is outer.__dict__
assert attributes == {'inner': outer.inner, 'label': 'x'}

# A separate shallow dictionary copy - O(n) time and space
shallow = attributes.copy()
assert shallow == attributes and shallow is not attributes
assert shallow['inner'] is outer.inner
```

!!! note "asdict() is not a cheap projection"
    For ordinary non-slotted instances, `vars(obj)` and `obj.__dict__` return the existing
    instance dictionary in O(1) time and space. Use `vars(obj).copy()` for a separate shallow
    dictionary in O(n) time and space, or `asdict()` for the recursive copy in O(N).

## Introspection

```python
from dataclasses import MISSING, Field, dataclass, field, fields, is_dataclass

@dataclass
class Point:
    x: float
    y: float = 0.0

# fields() builds a fresh tuple every call - O(n), nothing is cached
assert fields(Point) == fields(Point)
assert fields(Point) is not fields(Point)

first = fields(Point)[0]
assert isinstance(first, Field)
assert first.name == 'x'
assert first.default is MISSING       # the sentinel, not None
assert fields(Point)[1].default == 0.0

# is_dataclass answers for the class and for an instance - O(1)
assert is_dataclass(Point) and is_dataclass(Point(1.0))
assert not is_dataclass(object())
```

## Building a Dataclass at Run Time

`make_dataclass()` is the decorator plus a `type()` call, so it costs the same O(n) — but at run
time rather than import time, and every call builds a new class.

```python
from dataclasses import dataclass, fields, make_dataclass

Point = make_dataclass('Point', [('x', float), ('y', float)])  # O(n)

assert [f.name for f in fields(Point)] == ['x', 'y']
assert Point(1.0, 2.0) == Point(1.0, 2.0)

# Two calls give two unrelated classes
assert make_dataclass('P', [('x', int)]) is not make_dataclass('P', [('x', int)])
```

## Inheritance

Fields are collected across the MRO in reverse order, so a subclass costs the total across its
bases, and a base's defaults constrain what the subclass may declare without one.

```python
from dataclasses import dataclass, fields

@dataclass
class Base:
    a: int

@dataclass
class Derived(Base):
    b: int

assert [f.name for f in fields(Derived)] == ['a', 'b']  # O(total fields)
assert Derived(1, 2).a == 1

# A field with a default cannot be followed by one without
try:
    @dataclass
    class Broken(Base):
        c: int = 0
        d: int
except TypeError as error:
    assert 'non-default argument' in str(error)
```

## Version Notes

- **Python 3.10+**: `KW_ONLY`, `kw_only`, `match_args` and `slots` on the decorator
- **Python 3.13+**: the generated `__eq__` no longer materializes the two tuples it compares, so
  its space drops from O(n) to O(1); `replace()` raises `TypeError` rather than `ValueError`
  for an `init=False` field

## Related Documentation

- **[typing](typing.md)** - the annotations a dataclass reads its fields from
- **[collections](collections.md)** - `namedtuple`, the immutable alternative
- **[copy](copy.md)** - what `asdict()` does to the containers it finds

## Best Practices

✅ **Do**:

- Use `frozen=True` when you want the instance in a set or dict; `eq=True` alone makes it
  unhashable
- Use `vars(obj)` for a top-level view and `asdict()` only when you want the deep copy
- Use `field(default_factory=...)` for anything mutable
- Keep `__post_init__` cheap: `replace()` runs it again

❌ **Avoid**:

- Reading `asdict()` as O(fields); it is O(values reached), and it copies them
- Calling `fields()` in a loop — it rebuilds its tuple every time
- Very wide dataclasses in hot import paths; every field is compiled into the generated methods
- Assuming a dataclass is hashable
