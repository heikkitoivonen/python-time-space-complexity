# enum Module Complexity

The `enum` module binds symbolic names to constant values. Almost everything it does costs once,
when the class body runs: the metaclass builds the members, indexes them by name and by value, and
freezes the result.

After that, both lookups are dict lookups. **n** is the members of an enum; the only operations
that pay it are the class definition itself and anything that walks the members.

!!! note "Lookup by value is a dict, not a scan"
    `Color(1)` goes through `_value2member_map_`, so it is O(1) — the last member declared costs
    the same as the first, whether the enum has ten members or a thousand. Only a value the map
    does not hold falls through to `_missing_()`.

## Complexity Reference

### Building an enum

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `class C(enum.Enum)` — the class body | O(n) | O(n) | n = members; each is instantiated and indexed by name and by value |
| `enum.Enum(name, names)` — the functional API | O(n) | O(n) | Builds the same class at run time |
| `enum.auto()` | O(1) | O(1) | A sentinel resolved by `_generate_next_value_` when the class is built |
| `enum.member(obj)`, `enum.nonmember(obj)` | O(1) | O(1) | Python 3.11+; force a class-body name to be, or not be, a member |
| `enum.property` | O(1) | O(1) | Python 3.11+; the descriptor behind `.name` and `.value`, which shadows a member of the same name |
| `enum.EnumDict` | O(1) | O(1) | Python 3.13+; the mapping the class body is executed in |

### Looking members up

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `C.MEMBER` | O(1) | O(1) | An attribute lookup on the class |
| `C['MEMBER']` | O(1) | O(1) | `_member_map_`, a dict keyed by name |
| `C(value)` | O(1) | O(1) | `_value2member_map_`, a dict keyed by value; a miss calls `_missing_()` |
| `member.name`, `member.value` | O(1) | O(1) | Stored on the member |
| `len(C)` | O(1) | O(1) | The canonical member list's length |
| `iter(C)` | O(n) | O(1) | Canonical members only — aliases are skipped |
| `C.__members__` | O(1) | O(n) | A mapping proxy including aliases; building the view is O(1), reading it all is O(n) |
| `x in C` | O(1) | O(1) | A non-member value raises `TypeError` before 3.12 and answers `True`/`False` from 3.12 |

### Variants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enum.IntEnum`, `enum.StrEnum` | O(1) | O(1) | Members are `int`s and `str`s, so they compare and format as one; `StrEnum` is 3.11+ |
| `enum.ReprEnum` | O(1) | O(1) | Python 3.11+; the base that keeps the mixed-in type's `__str__` and `__format__` |
| `enum.Flag`, `enum.IntFlag` | O(1) | O(1) | Members are powers of two, so `\|` and `&` are single integer operations |
| Iterating or `len()` on a combined flag | O(b) | O(1) | b = bits set; Python 3.11+, where a combination became sized and iterable |
| `enum.EnumMeta`, `enum.EnumType` | O(n) | O(n) | The metaclass that does the building; `EnumType` is the 3.11+ name for the same object |

### Validation and helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enum.unique(cls)` | O(n) | O(a) | a = aliases found; raises `ValueError` if there are any |
| `enum.verify(*checks)` | O(n) | O(n) | Python 3.11+; a class decorator running the `EnumCheck` constraints |
| `enum.EnumCheck` — `enum.UNIQUE`, `enum.CONTINUOUS`, `enum.NAMED_FLAGS` | O(1) | O(1) | Python 3.11+; the constraints `verify()` applies |
| `enum.FlagBoundary` — `enum.STRICT`, `enum.CONFORM`, `enum.EJECT`, `enum.KEEP` | O(1) | O(1) | Python 3.11+; what a flag does with bits no member claims |
| `enum.global_enum(cls)`, `enum.global_str(self)` | O(n) | O(n) | Python 3.11+; copies the members into the defining module's namespace |
| `enum.global_enum_repr(self)`, `enum.global_flag_repr(self)` | O(1) | O(1) | Python 3.11+; the `repr` that names the module rather than the class |
| `enum.pickle_by_global_name(self, proto)`, `enum.pickle_by_enum_name(self, proto)` | O(1) | O(1) | Python 3.11+; `__reduce_ex__` implementations |

## Enum Basics

### Creating an Enum

```python
from enum import Enum

# The class body runs once - O(n) in members
class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

assert Color.RED.name == 'RED'    # O(1)
assert Color.RED.value == 1       # O(1)
assert str(Color.RED) == 'Color.RED'
```

### Both Lookups Are Dict Lookups

```python
from enum import Enum

class Status(Enum):
    PENDING = 'pending'
    ACTIVE = 'active'
    DONE = 'done'

assert Status.ACTIVE is Status['ACTIVE']    # O(1) - by name
assert Status.ACTIVE is Status('active')    # O(1) - by value

# A value with no member raises, having consulted the map and then _missing_
try:
    Status('missing')
except ValueError as error:
    assert 'is not a valid Status' in str(error)
```

### Members Are Singletons

There is exactly one object per member, so `is` is the right comparison and identity checks cost
nothing.

```python
from enum import Enum

class Color(Enum):
    RED = 1

assert Color(1) is Color.RED
assert Color(1) is Color['RED']
assert Color.RED == Color.RED and Color.RED is Color.RED

# An Enum member is not its value
assert Color.RED != 1
```

### Iteration Skips Aliases

A second name for the same value is an alias. It is reachable by name and appears in
`__members__`, but iteration and `len()` see only the canonical members.

```python
from enum import Enum

class Color(Enum):
    RED = 1
    CRIMSON = 1   # an alias for RED
    GREEN = 2

assert Color.CRIMSON is Color.RED

assert [c.name for c in Color] == ['RED', 'GREEN']   # O(n), aliases skipped
assert len(Color) == 2                                # O(1)
assert list(Color.__members__) == ['RED', 'CRIMSON', 'GREEN']  # aliases included
```

## Membership

```python
import sys
from enum import Enum

class Color(Enum):
    RED = 1

assert Color.RED in Color   # O(1) on every version

# For a plain value the answer changed in 3.12
if sys.version_info >= (3, 12):
    assert (1 in Color) is True
    assert (99 in Color) is False
```

!!! warning "`value in EnumClass` raised before Python 3.12"
    On 3.10 and 3.11 testing a non-member raises `TypeError` (with a `DeprecationWarning` saying
    the behaviour will change). Write `value in EnumClass._value2member_map_` if you must support
    those versions, or catch the `TypeError`.

## Integer and String Enums

`IntEnum` and `StrEnum` members *are* `int`s and `str`s, so they interoperate with code that has
never heard of the enum — at the cost of comparing equal to a bare value.

```python
from enum import IntEnum

class Priority(IntEnum):
    LOW = 1
    HIGH = 3

assert Priority.HIGH > Priority.LOW    # O(1) - an int comparison
assert Priority.HIGH == 3              # unlike a plain Enum
assert Priority.HIGH + 1 == 4
assert sorted(Priority) == [Priority.LOW, Priority.HIGH]
```

## Flags

`Flag` members are powers of two, so combining and testing them are single integer operations. A
combination is iterable and sized from Python 3.11.

```python
import sys
from enum import Flag, auto

class Permission(Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()

combined = Permission.READ | Permission.WRITE   # O(1)

assert Permission.READ in combined              # O(1) - a bitwise test
assert Permission.EXECUTE not in combined
assert combined & Permission.READ == Permission.READ

# A combination is looked up by value like any other member
assert Permission(combined.value) is combined

if sys.version_info >= (3, 11):
    assert len(combined) == 2                        # O(b) in bits set
    assert {p.name for p in combined} == {'READ', 'WRITE'}
```

## Validation

`unique()` walks the members once and refuses aliases. `verify()` (3.11+) generalizes that to the
other constraints.

```python
import sys
from enum import Enum, unique

# unique() rejects an alias - O(n)
try:
    @unique
    class Duplicated(Enum):
        A = 1
        B = 1
except ValueError as error:
    assert 'duplicate values' in str(error)

if sys.version_info >= (3, 11):
    from enum import CONTINUOUS, verify

    # CONTINUOUS refuses a gap in the values - O(n)
    try:
        @verify(CONTINUOUS)
        class Gapped(Enum):
            A = 1
            C = 3
    except ValueError as error:
        assert 'invalid enum' in str(error) or 'are missing' in str(error)
```

## The Functional API

`Enum(name, names)` builds the same class the `class` statement would, at the same O(n) — just
later.

```python
from enum import Enum

Color = Enum('Color', ['RED', 'GREEN', 'BLUE'])   # O(n)

assert Color.RED.value == 1        # auto-numbered from 1
assert len(Color) == 3
assert Color(1) is Color.RED       # O(1) - by value, like any other enum

# A mapping gives explicit values
Status = Enum('Status', {'OK': 200, 'MISSING': 404})
assert Status(404) is Status.MISSING   # O(1)
```

## Methods on an Enum

Methods and non-member attributes live on the class, not among the members, so adding them does
not change any bound.

```python
from enum import Enum

class Planet(Enum):
    MERCURY = (3.303e23, 2.4397e6)
    EARTH = (5.976e24, 6.37814e6)

    def __init__(self, mass, radius):
        self.mass = mass
        self.radius = radius

    @property
    def surface_gravity(self):
        return 6.67300E-11 * self.mass / (self.radius * self.radius)

assert len(Planet) == 2                     # the property is not a member
assert round(Planet.EARTH.surface_gravity, 2) == 9.80
```

## Version Notes

- **Python 3.11+**: `StrEnum`, `ReprEnum`, `EnumType`, `verify` with `EnumCheck`, `FlagBoundary`,
  `member`/`nonmember`, `enum.property`, the `global_*` and `pickle_by_*` helpers; a combined
  `Flag` became sized and iterable
- **Python 3.12+**: `value in EnumClass` answers `True`/`False` instead of raising `TypeError`
- **Python 3.13+**: `EnumDict`, the class-body mapping, became public

## Related Documentation

- **[dataclasses](dataclasses.md)** - the other decorator that builds methods at import
- **[typing](typing.md)** - `Literal` as the alternative when you want no runtime object at all
- **[collections](collections.md)** - `namedtuple` for a fixed record rather than a fixed set

## Best Practices

✅ **Do**:

- Look up by value with `C(value)` — it is a dict lookup, not a scan
- Compare members with `is`; there is exactly one object per member
- Use `IntEnum` or `StrEnum` only where the value has to cross an API that wants a plain int or str
- Reach for `unique()` when the values come from somewhere you do not control

❌ **Avoid**:

- Building an enum inside a function that runs often — the class body is the O(n) part
- Iterating to find a member by value
- Assuming `__members__` and iteration agree; aliases appear in one and not the other
- `value in EnumClass` if you still support 3.10 or 3.11
