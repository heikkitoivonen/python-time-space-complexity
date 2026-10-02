# namedtuple - Tuple with Named Fields Complexity

`collections.namedtuple()` is a class factory: each call builds a new tuple subclass whose fields
can be read by name as well as by position. The class is the expensive part. Its instances are
tuples with no per-instance `__dict__`, so they cost what a tuple of the same length costs.

`f` is the fields of a named tuple class, `k` is the keyword arguments in one call, and `n` is the
items an iterable yields. Field names and values are priced at O(1) each: a value's own `repr`,
comparison or hash is the caller's cost, not the class's. Bounds are for calls that succeed.

## Complexity Reference

### namedtuple

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `collections.namedtuple(typename, field_names, *, rename=False, defaults=None, module=None)` | O(f) | O(f) | Builds a new class with one accessor per field; each call returns a distinct class, so call it once per record type, not per record |

### Creating Instances

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Point(*values)` | O(f) | O(f) | The instance is a tuple of f items; omitted trailing fields take their `defaults` |
| `Point(**fields)` | O(f·k) | O(f) | For k ≥ 1; each keyword is matched against the parameter list by a scan, so passing every field by name is O(f²) |
| `Point._make(iterable)` | O(n) | O(n) | Builds the tuple from all n items first, then raises `TypeError` unless n equals f |

### Reading Fields

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `p.x`, attribute access by field name | O(1) | O(1) | A class-level descriptor that reads one tuple slot by index |
| `p[i]`, `len(p)` | O(1) | O(1) | Plain tuple operations |
| Iterating `p` | O(f) | O(1) | Plain tuple iteration |
| Unpacking `x, y = p` | O(f) | O(f) | One reference per target |
| `p == q`, `p < q`, `hash(p)` | O(f) | O(1) | Tuple semantics: field names and the class are not compared, so a named tuple equals a plain tuple with the same items |
| `repr(p)` | O(f) | O(f) | `Point(x=1, y=2)`, plus each value's own `repr` |

### Methods and Class Attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `p._asdict()` | O(f) | O(f) | A new `dict` on every call |
| `p._replace(**kwargs)` | O(f) | O(f) | A new instance with every field copied, however few change |
| `copy.replace(p, **kwargs)` | O(f) | O(f) | Python 3.13+; calls `_replace()` |
| `copy.copy(p)` | O(f) | O(f) | Builds a new instance, where a plain tuple is returned as is |
| `Point._fields` | O(1) | O(1) | The class's tuple of field names, not a copy |
| `Point._field_defaults` | O(1) | O(1) | The class's dict of field name to default, not a copy |
| `Point.__match_args__` | O(1) | O(1) | The field names, so `case Point(x, y)` matches by position |

## Defining a Named Tuple

`namedtuple()` checks every name, generates the constructor and builds a class with one
accessor per field. That is O(f) work on every call, and each call produces a new class: instances of two calls with the same arguments are not the same type.

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])  # O(f)

# A string of names separated by spaces or commas is the same thing
assert namedtuple('Point', 'x y')._fields == ('x', 'y')
assert namedtuple('Point', 'x, y')._fields == ('x', 'y')

# Every call builds a fresh class
Again = namedtuple('Point', ['x', 'y'])
assert Again is not Point
assert not isinstance(Again(1, 2), Point)
```

### Defaults and Renaming

`defaults` apply to the rightmost fields. `rename=True` replaces an invalid or duplicate name with
an underscore and its position instead of raising.

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y', 'z'], defaults=[0, 0])  # O(f)
assert Point(1) == (1, 0, 0)  # O(f)
assert Point._field_defaults == {'y': 0, 'z': 0}  # O(1) - the class's own dict

Row = namedtuple('Row', ['id', 'def', 'id'], rename=True)  # O(f)
assert Row._fields == ('id', '_1', '_2')

try:
    namedtuple('Row', ['id', 'def'])
except ValueError as error:
    assert 'keyword' in str(error)
else:
    raise AssertionError('a keyword was accepted as a field name')
```

## Instances Are Tuples

An instance holds its fields in tuple slots and nothing else, so it is the size of a plain tuple
of the same length. Reading a field by name is one indexed slot read, the same at any position.
Comparison and hashing are the tuple's, which ignore the field names.

```python
import sys
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])
p = Point(3, 4)  # O(f)

assert p.x == p[0] == 3  # O(1) either way
x, y = p  # O(f)
assert (x, y) == (3, 4)

assert sys.getsizeof(p) == sys.getsizeof((3, 4))  # no per-instance dict
assert not hasattr(p, '__dict__')

assert p == (3, 4)  # O(f) - the field names are not compared
assert hash(p) == hash((3, 4))
```

### Keyword Arguments vs _make

Positional arguments and `_make()` fill the tuple in one pass. Keyword arguments are matched by
name against the constructor's parameter list, and each match scans it, so building a wide
record from a dict with `**` costs O(f²).

```python
from collections import namedtuple

Record = namedtuple('Record', ['id', 'name', 'score'])
data = {'id': 1, 'name': 'Ada', 'score': 9.5}

by_keyword = Record(**data)  # O(f·k)
by_position = Record._make(data[name] for name in Record._fields)  # O(f)
assert by_keyword == by_position == (1, 'Ada', 9.5)

# _make builds the tuple first and checks its length afterwards
try:
    Record._make([1, 'Ada'])
except TypeError as error:
    assert 'Expected 3 arguments, got 2' in str(error)
else:
    raise AssertionError('a short iterable was accepted')
```

## Converting and Replacing

`_asdict()` and `_replace()` each build a new object of f entries. `_replace()` copies every
field into a new instance even when it changes one, so updating a field in a loop is O(f) per
update.

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])
p = Point(3, 4)

d = p._asdict()  # O(f) - a new dict
assert d == {'x': 3, 'y': 4}
assert p._asdict() is not d

moved = p._replace(x=5)  # O(f) - a new instance
assert moved == (5, 4) and p == (3, 4)

assert p._fields is Point._fields  # O(1) - the class's tuple

try:
    p._replace(z=1)
except (TypeError, ValueError) as error:  # TypeError from 3.13, ValueError before
    assert 'unexpected field names' in str(error)
else:
    raise AssertionError('an unknown field was replaced')
```

## Pattern Matching

`__match_args__` is the field names, so a class pattern can match a named tuple positionally.

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])

def describe(p):
    match p:
        case Point(0, 0):
            return 'origin'
        case Point(x, 0):
            return f'on the x axis at {x}'
        case _:
            return 'elsewhere'

assert Point.__match_args__ == ('x', 'y')
assert describe(Point(0, 0)) == 'origin'
assert describe(Point(2, 0)) == 'on the x axis at 2'
assert describe(Point(1, 1)) == 'elsewhere'
```

## Common Patterns

### Rows as Records

Define the class once, then build one instance per row with `_make()`.

```python
import csv
import io
from collections import namedtuple

source = io.StringIO("id,name,score\n1,Ada,9.5\n2,Grace,8.0\n")
reader = csv.reader(source)

Row = namedtuple('Row', next(reader))  # O(f), once
rows = [Row._make(fields) for fields in reader]  # O(f) per row

assert rows[1].name == 'Grace'
assert sum(float(row.score) for row in rows) == 17.5  # O(n)
```

## Performance Best Practices

✅ **Do**:

- Define each named tuple class once, at module level; `namedtuple()` builds a whole class
- Use `_make()` or positional arguments for wide records; keyword arguments cost O(f) each
- Use a named tuple where a dict per record would do, when the fields are fixed: it is the size of a tuple

❌ **Avoid**:

- Calling `namedtuple()` inside a loop or a function called per record
- `Point(**d)` for records with hundreds of fields - that is O(f²)
- Repeated `_replace()` to update one field at a time; each call copies all f fields

## Version Notes

- **Python 3.7+**: Added the `defaults` parameter and `_field_defaults`
- **Python 3.13+**: `copy.replace()` works on named tuples, and `_replace()` with an unknown field raises `TypeError` instead of `ValueError`

## Related Modules

- **[typing.NamedTuple](typing.md)** - the same kind of class, declared with annotations
- **[dataclasses](dataclasses.md)** - records with methods, mutable fields and per-field options
- **[tuple](../builtins/tuple.md)** - the operations every named tuple inherits
- **[copy](copy.md)** - `copy.replace()` and what copying a record costs
