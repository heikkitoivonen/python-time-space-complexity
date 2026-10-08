# enum Module Complexity

The `enum` module binds symbolic names to constant values. Most of its work happens once, when the
class body runs: the metaclass creates every member, checks each value against the ones before it,
and indexes the members by name and by value. After that, lookups are dictionary reads.

`n` is the members of one enum class, aliases included, and `b` is the bits set in one flag value.
Values are hashed and compared in O(1), and flag values are machine-word integers, so a bitwise
operation on one is O(1). `auto()` bounds assume the values before each one ascend, as `auto()`
alone makes them. Hooks a class overrides - `_missing_()`, `_generate_next_value_()`, a custom
`__new__` or `__init__` - add their own cost.

## Complexity Reference

### EnumType

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `class C(enum.Enum)`, running the class body | O(n²) | O(n) | Each value is checked against the values before it, and each `auto()` is handed a copy of them; O(n) on 3.11 to 3.13.0 when every value is explicit and hashable |
| `enum.Enum(value, names, ...)`, the functional API | O(n²) | O(n) | Builds the same class; names given as a string or a list are numbered the way `auto()` numbers them |
| `enum.EnumType`, `enum.EnumMeta` | O(n²) | O(n) | The metaclass; calling it builds a class, as above. `EnumType` is the 3.11+ name, and `EnumMeta` stays an alias |
| `C.NAME`, `C['NAME']` | O(1) | O(1) | Name lookup; aliases resolve to their canonical member |
| `C(value)` | O(1) expected; O(n) for an unhashable value | O(1) | Hashable values are indexed; a value with no member calls `_missing_()`, then raises `ValueError` |
| `iter(C)`, `reversed(C)` | O(n) | O(1) | Canonical members in definition order; aliases are skipped |
| `len(C)` | O(1) | O(1) | Canonical members only |
| `value in C` | O(1) for a member; for a raw value, O(1) expected on 3.12 to 3.13.2 and O(n) from 3.13.3 | O(1) | A raw value raises `TypeError` before 3.12, and an unhashable one until 3.12.10; an unhashable one is O(n) wherever it is answered, and on 3.12 a hashable one with no member also scans any unhashable values |
| `C.__members__` | O(1) | O(1) | A read-only live view of the name index, aliases included; copying it is O(n) |
| `dir(C)` | O(n log n) | O(n) | Sorted; includes the canonical member names, not aliases |

### Enum

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enum.Enum`, `member.name`, `member.value` | O(1) | O(1) | Stored on the member |
| `Enum._name_`, `Enum._value_` | O(1) | O(1) | The attributes behind `name` and `value`; a custom `__new__` sets `_value_` |
| `enum.auto()` | O(1) | O(1) | A placeholder; its value is generated while the class body runs, at the cost in the first row |
| `Enum._generate_next_value_(name, start, count, last_values)` | O(n) | O(n) | Called once per `auto()` with a fresh list of the values so far |
| `Enum._missing_(value)` | O(1) | O(1) | Called when `C(value)` finds no member; the default returns `None` |
| `Enum._ignore_` | O(i) | O(i) | i = names listed; they are dropped from the class body |
| `Enum._order_` | O(n²) | O(n) | Checked once, when the class is built: each name is looked for in the list of canonical member names; O(n) on 3.10 |
| `Enum._add_alias_(name)`, `Enum._add_value_alias_(value)` | O(1) expected; O(n) for an unhashable value | O(1) | Python 3.13+; add a name or a value that leads to an existing member |
| `enum.member(obj)`, `enum.nonmember(obj)` | O(1) | O(1) | Python 3.11+; mark a class-body name as a member or not |
| `enum.property` | O(1) | O(1) | Python 3.11+; the descriptor behind `name` and `value`, so a member may have either name |

### EnumDict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enum.EnumDict` | O(1) | O(1) | Python 3.13+; the namespace the class body runs in |
| `EnumDict.member_names` | O(n) | O(n) | Python 3.13+; a fresh list on every access, aliases included |
| `EnumDict.update(members, **more_members)` | O(k) | O(k) | Python 3.13+; k = items given, assigned one at a time, an `auto()` among them priced as in the class body |

### IntEnum, StrEnum and ReprEnum

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enum.IntEnum`, `enum.StrEnum` | O(1) | O(1) | Members are `int`s and `str`s, so they compare, hash and format as one; `StrEnum` is 3.11+ |
| `enum.ReprEnum` | O(1) | O(1) | Python 3.11+; keeps the mixed-in type's `str()` and `format()` |

### Flag

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enum.Flag`, `enum.IntFlag` | O(1) | O(1) | Members are bits or named combinations of them; other combinations are made on demand |
| `a \| b`, `a & b`, `a ^ b` | O(1) expected; O(n) the first time a value is made, O(n log n) on 3.10 | O(1); O(n) the first time | A new combination is built once and cached on the class for as long as the class lives |
| `~flag` | O(n); O(n²) on 3.10 | O(n) | Python 3.11+ caches the result on the operand, so a repeat is O(1); 3.10 recomputes it on every call |
| `member in flag` | O(1) | O(1) | A bitwise test |
| `iter(flag)` | O(b) | O(1) | Python 3.11+; the members whose bits are set. A class whose members are defined out of value order sorts them first: O(b log b) time, O(b) space |
| `len(flag)`, `bool(flag)` | O(1) | O(1) | `len()` is 3.11+ and counts the bits set |
| `Flag._numeric_repr_` | O(1) | O(1) | Python 3.11+; formats the bits no member names |
| `enum.FlagBoundary`, `enum.STRICT`, `enum.CONFORM`, `enum.EJECT`, `enum.KEEP` | O(1) | O(1) | Python 3.11+; what a flag does with bits no member claims |
| `enum.show_flag_values(value)` | O(b) | O(b) | Python 3.11+; the powers of two in `value`, ascending |
| `enum.bin(num, max_bits=None)` | O(w) | O(w) | Python 3.11+; w = digits in the result, at least `max_bits`; the leading digit is the sign |

### Validation and global helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `enum.unique(cls)` | O(n) | O(a) | a = aliases found; raises `ValueError` naming them |
| `enum.verify(*checks)` | O(n + r) | O(n + r) | Python 3.11+; r = the span from the smallest value to the largest, which `CONTINUOUS` walks on an `Enum`; `UNIQUE` and `NAMED_FLAGS` are O(n) |
| `enum.EnumCheck`, `enum.UNIQUE`, `enum.CONTINUOUS`, `enum.NAMED_FLAGS` | O(1) | O(1) | Python 3.11+; the checks `verify()` applies |
| `enum.global_enum(cls, update_str=False)` | O(n) | O(n) | Python 3.11+; copies every member, aliases included, into the defining module |
| `enum.global_str(self)`, `enum.global_enum_repr(self)` | O(1) | O(1) | Python 3.11+; the `str()` and `repr()` that `global_enum()` installs |
| `enum.global_flag_repr(self)` | O(b) | O(b) | Python 3.11+; module-qualifies each name in a combination's name |
| `enum.pickle_by_global_name(self, proto)`, `enum.pickle_by_enum_name(self, proto)` | O(1) | O(1) | Python 3.11+; `__reduce_ex__` implementations |

## Defining Enums

### Creating an Enum

The class body is where the cost is. Each value is checked against the values before it, and each
`auto()` is handed a copy of them, so build an enum once, at module level, and look members up
afterwards.

```python
from enum import Enum, auto

class Color(Enum):  # O(n²) once, when the class body runs
    RED = auto()
    GREEN = auto()
    BLUE = auto()

assert [c.value for c in Color] == [1, 2, 3]  # O(n) - auto() counts from 1
assert Color.RED.name == 'RED'                # O(1)
assert str(Color.RED) == 'Color.RED'
```

### The Functional API

`Enum(name, names)` builds the same class the `class` statement would, at the same cost.

```python
from enum import Enum

Color = Enum('Color', 'RED GREEN BLUE')  # O(n²) - numbered like auto()
assert Color.RED.value == 1
assert len(Color) == 3                   # O(1)

# A mapping gives explicit values
Status = Enum('Status', {'OK': 200, 'MISSING': 404})
assert Status(404) is Status.MISSING     # O(1) expected
```

## Looking Members Up

### By Name and by Value

Names and hashable values are both indexed. An unhashable value cannot be, so looking one up
compares it with the member values one at a time.

```python
from enum import Enum

class Status(Enum):
    PENDING = 'pending'
    DONE = 'done'

assert Status['DONE'] is Status.DONE  # O(1) - by name
assert Status('done') is Status.DONE  # O(1) expected - hashable value

Lists = Enum('Lists', {'FIRST': [1], 'SECOND': [2]})
assert Lists([2]) is Lists.SECOND     # O(n) - unhashable value

try:
    Status('missing')                 # O(1), then _missing_()
except ValueError as error:
    assert 'is not a valid Status' in str(error)
else:
    raise AssertionError('a value with no member was found')
```

### Aliases

A second name for the same value is an alias. It is reachable by name and appears in
`__members__`, but iteration and `len()` see only the canonical members.

```python
from enum import Enum

class Color(Enum):
    RED = 1
    CRIMSON = 1  # an alias for RED
    GREEN = 2

assert Color.CRIMSON is Color.RED
assert [c.name for c in Color] == ['RED', 'GREEN']  # O(n), aliases skipped
assert len(Color) == 2                              # O(1)
assert list(Color.__members__) == ['RED', 'CRIMSON', 'GREEN']  # O(n) to list the view
```

## Membership

A member is found in its class in O(1). A raw value is a different question: before 3.12 it raises
`TypeError`, and from 3.13.3 it may be answered by scanning the member values. `C(value)` reaches
the value index on every version, so it is the constant-time test for a hashable value.

```python
import sys
from enum import Enum

class Color(Enum):
    RED = 1
    GREEN = 2

assert Color.RED in Color  # O(1) - a member

def has_value(cls, value):
    try:
        cls(value)         # O(1) expected - the value index
    except ValueError:
        return False
    return True

assert has_value(Color, 2)
assert not has_value(Color, 99)

if sys.version_info >= (3, 12):
    assert 2 in Color      # O(n) from 3.13.4 - a raw value
    assert 99 not in Color
```

!!! warning "`value in C` depends on the version"
    On 3.10 and 3.11 a raw value raises `TypeError`, with a `DeprecationWarning` announcing the
    change. On 3.12.0 to 3.12.9 a hashable value is answered and an unhashable one still raises
    `TypeError`; 3.12.10 and 3.13 answer both.

## Flags

Combining flags is integer arithmetic, but the result is a member too. The first time a value is
made it is built and cached on the class, so the same combination is the same object afterwards,
and every distinct value made stays cached for as long as the class lives.

```python
import sys
from enum import Flag, auto

class Permission(Flag):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()

combined = Permission.READ | Permission.WRITE         # O(n) once, then O(1)
assert combined is Permission.READ | Permission.WRITE  # one object per value

assert Permission.READ in combined                    # O(1) - a bitwise test
assert Permission.EXECUTE not in combined
assert (combined & Permission.READ) is Permission.READ

if sys.version_info >= (3, 11):
    assert len(combined) == 2                                # O(1)
    assert [p.name for p in combined] == ['READ', 'WRITE']  # O(b)
```

## Validation

`unique()` walks the members once and refuses aliases. `verify()` (3.11+) generalises it; its
`CONTINUOUS` check walks every integer between the smallest and largest value, so it suits values
that are close together.

```python
import sys
from enum import Enum, unique

try:
    @unique  # O(n)
    class Duplicated(Enum):
        A = 1
        B = 1
except ValueError as error:
    assert 'duplicate values' in str(error)
else:
    raise AssertionError('an alias passed unique()')

if sys.version_info >= (3, 11):
    from enum import CONTINUOUS, verify

    try:
        @verify(CONTINUOUS)  # O(n + r), r = largest value - smallest
        class Gapped(Enum):
            A = 1
            C = 3
    except ValueError as error:
        assert 'missing values 2' in str(error)
    else:
        raise AssertionError('a gap passed verify(CONTINUOUS)')
```

## Integer and String Enums

`IntEnum` and `StrEnum` members *are* `int`s and `str`s, so they work with code that has never
heard of the enum, at the price of comparing equal to a bare value.

```python
import sys
from enum import Enum, IntEnum

class Priority(IntEnum):
    LOW = 1
    HIGH = 3

assert Priority.HIGH > Priority.LOW  # O(1) - an int comparison
assert Priority.HIGH == 3
assert sorted(Priority) == [Priority.LOW, Priority.HIGH]

class Plain(Enum):
    HIGH = 3

assert Plain.HIGH != 3               # a plain member is not its value

if sys.version_info >= (3, 11):
    from enum import StrEnum

    class Mode(StrEnum):
        READ = 'r'

    assert Mode.READ == 'r' and f'{Mode.READ}' == 'r'
```

## Performance Best Practices

✅ **Do**:

- Define enums once, at module level, so the O(n²) class body runs once
- Test whether a hashable value has a member with `C(value)` and `ValueError`; it is an index
  lookup on every version
- Compare members with `is`; there is exactly one object per member, and per flag value

❌ **Avoid**:

- Building an enum inside a function that runs often
- Iterating to find a member by value - O(n), where `C(value)` is O(1)
- Unhashable member values: every lookup by value compares them one at a time
- `verify(CONTINUOUS)` on values far apart; it walks the whole span between them
- Making flags from arbitrary integers - each distinct value is cached on the class for good

## Version Notes

- **Python 3.11+**: `StrEnum`, `ReprEnum`, `EnumType`, `verify` with `EnumCheck`, `FlagBoundary`,
  `member`/`nonmember`, `enum.property`, `show_flag_values`, `enum.bin`, and the `global_*` and
  `pickle_by_*` helpers; a combined `Flag` became sized and iterable, and `~flag` is cached.
  Building indexes explicit hashable values, O(n) where 3.10 is O(n²)
- **Python 3.12+**: `value in C` answers for a raw hashable value instead of raising `TypeError`;
  unhashable values are answered from 3.12.10
- **Python 3.13+**: `EnumDict`, `_add_alias_()` and `_add_value_alias_()`
- **Python 3.13.1+**: Building checks each value against a list of the values before it, O(n²)
- **Python 3.13.3+**: `value in C` with a raw value scans the member values, O(n); on 3.13.3 only
  a value with no member is scanned

## Related Modules

- **[dataclasses](dataclasses.md)** - another class whose behaviour is built from its body at definition time
- **[typing](typing.md)** - `Literal` when the names need no runtime object at all
- **[collections](collections.md)** - `namedtuple` for a fixed record rather than a fixed set
