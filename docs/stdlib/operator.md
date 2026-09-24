# operator Module Complexity

The `operator` module exposes Python's operators as functions, plus three factories -
`itemgetter`, `attrgetter` and `methodcaller` - that build small callables for use as keys and
callbacks. All of it is implemented in C. An operator function adds one call to the operator it
names and nothing else, so the cost that matters is the operator's own.

`f` is the cost of the operation a function dispatches to on the operands it is given: the
special method (`__add__`, `__lt__`, `__getitem__`, `__len__`) or the method a caller invokes.
It is O(1) for small integers and a dict lookup, and linear in both lengths for adding two lists.
`k` is the lookups a getter performs - one per key for `itemgetter`, one per dotted component for
`attrgetter` - and `a` is the arguments a call passes on. `n` is the items in an iterable and `i`
is the position of the first match. Comparing two items, and the length of a key or attribute
name, are priced at O(1).

## Complexity Reference

### Comparison and identity

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `operator.lt(a, b)`, `operator.le(a, b)`, `operator.eq(a, b)`, `operator.ne(a, b)`, `operator.ge(a, b)`, `operator.gt(a, b)` | O(f) | O(f) | As `a < b` and the rest: O(1) for small integers, up to the shorter length for two sequences |
| `operator.is_(a, b)`, `operator.is_not(a, b)` | O(1) | O(1) | Identity; no method is called |
| `operator.is_none(a)`, `operator.is_not_none(a)` | O(1) | O(1) | Python 3.14+ |
| `operator.not_(obj)`, `operator.truth(obj)` | O(f) | O(1) | As `not obj` and `bool(obj)`: `__bool__`, else `__len__` |

### Arithmetic and bitwise

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `operator.add(a, b)`, `operator.sub(a, b)`, `operator.mul(a, b)`, `operator.matmul(a, b)` | O(f) | O(f) | `add` on two lists, strings or tuples copies both: O(len(a) + len(b)) |
| `operator.truediv(a, b)`, `operator.floordiv(a, b)`, `operator.mod(a, b)`, `operator.pow(a, b)` | O(f) | O(f) | As `/`, `//`, `%` and `**` |
| `operator.neg(obj)`, `operator.pos(obj)`, `operator.abs(obj)` | O(f) | O(f) | As `-obj`, `+obj` and `abs(obj)` |
| `operator.lshift(a, b)`, `operator.rshift(a, b)`, `operator.and_(a, b)`, `operator.or_(a, b)`, `operator.xor(a, b)` | O(f) | O(f) | `and_` and `or_` are the bitwise operators, not `and` and `or`, and never short-circuit |
| `operator.inv(obj)`, `operator.invert(obj)` | O(f) | O(f) | As `~obj`; two names for one operation |
| `operator.index(a)` | O(f) | O(f) | As `a.__index__()`; raises `TypeError` for a `float` |

### In-place operators

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `operator.iadd(a, b)`, `operator.isub(a, b)`, `operator.imul(a, b)`, `operator.imatmul(a, b)` | O(f) | O(f) | As `a += b` and the rest, returning the result; a list target is extended in place at amortized O(len(b)) |
| `operator.itruediv(a, b)`, `operator.ifloordiv(a, b)`, `operator.imod(a, b)`, `operator.ipow(a, b)` | O(f) | O(f) | As `a /= b`, `a //= b`, `a %= b` and `a **= b` |
| `operator.ilshift(a, b)`, `operator.irshift(a, b)`, `operator.iand(a, b)`, `operator.ior(a, b)`, `operator.ixor(a, b)` | O(f) | O(f) | A set target is updated in place |
| `operator.iconcat(a, b)` | O(f) | O(f) | `a` must be a sequence; a list is extended in place at amortized O(len(b)) |

An immutable target - an `int`, `str` or `tuple` - is not changed. The function returns what the
plain operator returns, at the plain operator's cost (O(len(a) + len(b)) for a string or tuple),
and the result must be assigned.

### Sequence and container operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `operator.concat(a, b)` | O(len(a) + len(b)) | O(len(a) + len(b)) | As `a + b` for built-in sequences; raises `TypeError` if `a` is not a sequence |
| `operator.contains(a, b)` | O(f) | O(1) | As `b in a`: O(n) for a list, O(1) average for a set or dict |
| `operator.countOf(a, b)` | O(n) | O(1) | Walks the whole iterable, even after a match |
| `operator.indexOf(a, b)` | O(i) | O(1) | Stops at the first match; O(n), then `ValueError`, when there is none |
| `operator.getitem(a, b)`, `operator.setitem(a, b, c)`, `operator.delitem(a, b)` | O(f) | O(f) | As `a[b]`, `a[b] = c` and `del a[b]`; slices are accepted |
| `operator.length_hint(obj, default=0)` | O(f) | O(1) | `len(obj)`, else `obj.__length_hint__()`, else `default`; never iterates, so O(1) for built-in containers and iterators |

### itemgetter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `operator.itemgetter(item, /, *items)` | O(k) | O(k) | Keeps the keys |
| Calling an `itemgetter` | O(k·f) | O(k·f) | One `__getitem__` per key; one key returns the value itself, several return a k-tuple |

### attrgetter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `operator.attrgetter(attr, /, *attrs)` | O(k) | O(k) | k counts every dotted component: `'a.b.c'` is three |
| Calling an `attrgetter` | O(k·f) | O(k·f) | One attribute lookup per component; one name returns the value itself, several return a tuple |

### methodcaller and call

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `operator.methodcaller(name, /, *args, **kwargs)` | O(a) | O(a) | Keeps the method name and the arguments |
| Calling a `methodcaller` | O(a + f) | O(a + f) | One method lookup on the object, then one call with the kept arguments |
| `operator.call(obj, /, *args, **kwargs)` | O(a + f) | O(a + f) | As `obj(*args, **kwargs)`; Python 3.11+ |

### Dunder aliases

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `operator.__add__`, `operator.__lt__`, `operator.__getitem__` and the other double-underscore names | O(1) | O(1) | The same function objects as the plain names; `operator.__call__` is Python 3.11+ |

## Key Functions

`itemgetter`, `attrgetter` and `methodcaller` do not change the bound of the sort, `max` or
`groupby` they are handed to. What they change is the call: a C callable runs without a Python
frame, where a `lambda` starts one for every element. The exception is a lookup that runs
Python code itself, such as a property.

```python
import operator

rows = [('bob', 25), ('alice', 30), ('carol', 25)]

by_age = sorted(rows, key=operator.itemgetter(1))  # O(n log n), one key call per row
assert by_age == [('bob', 25), ('carol', 25), ('alice', 30)]

# Several keys build a tuple, so the sort compares age, then name
by_age_then_name = sorted(rows, key=operator.itemgetter(1, 0))  # O(n log n)
assert by_age_then_name[0] == ('bob', 25)

oldest = max(rows, key=operator.itemgetter(1))  # O(n)
assert oldest == ('alice', 30)
```

### One Key Is Not a Tuple

A getter built with one key returns the value; with two or more it returns a tuple. Code that
builds a getter from a list of keys has to allow for the list having one entry.

```python
import operator

record = {'name': 'alice', 'age': 30, 'city': 'Oslo'}

assert operator.itemgetter('name')(record) == 'alice'  # O(1) - the value itself
assert operator.itemgetter('name', 'age')(record) == ('alice', 30)  # O(k) - a k-tuple

keys = ['name']
assert operator.itemgetter(*keys)(record) == 'alice'  # not ('alice',)
```

### Dotted Attribute Paths

`attrgetter` follows a dotted name one attribute at a time, so `'a.b.c'` is three lookups.

```python
import operator

class Node:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent

root = Node('root')
leaf = Node('leaf', Node('branch', root))

grandparent = operator.attrgetter('parent.parent.name')  # O(k), k = 3 components
assert grandparent(leaf) == 'root'  # O(k) - three lookups

both = operator.attrgetter('name', 'parent.name')
assert both(leaf) == ('leaf', 'branch')
```

### Calling a Method on Each Item

`methodcaller` keeps its arguments and passes them on every call. The method's own cost is
still paid each time.

```python
import operator

split_once = operator.methodcaller('split', ',', maxsplit=1)  # O(a)
assert split_once('a,b,c') == ['a', 'b,c']  # O(a + f), f = the split

words = ['Oslo', 'bergen', 'Tromsø']
assert sorted(words, key=operator.methodcaller('casefold')) == ['bergen', 'Oslo', 'Tromsø']
```

## Counting and Searching

`countOf` has to see every item to count them. `indexOf` returns at the first match, so its
cost depends on where the match is, and it pays for the whole walk only to raise.

```python
import operator

values = [3, 1, 4, 1, 5, 9, 2, 6]

assert operator.countOf(values, 1) == 2  # O(n) - always the whole list
assert operator.indexOf(values, 4) == 2  # O(i) - three comparisons
assert operator.contains(values, 9)      # O(n) for a list, as `9 in values`

try:
    operator.indexOf(values, 7)  # O(n), then raises
except ValueError:
    pass
else:
    raise AssertionError('a missing value was found')

# Both take any iterable, not only a sequence
assert operator.countOf((c for c in 'banana'), 'a') == 3
```

## In-Place Operators

`iadd` and its siblings do what the augmented assignment does, which depends on the target. A
list is extended where it stands and returned. A tuple or string is left alone and the result
comes back as the return value, so the caller has to use it.

```python
import operator

items = [1, 2]
result = operator.iadd(items, [3])  # amortized O(len(b)) - extends the list in place
assert result is items and items == [1, 2, 3]

pair = (1, 2)
result = operator.iadd(pair, (3,))  # O(len(a) + len(b)) - builds the combined tuple
assert pair == (1, 2) and result == (1, 2, 3)

tags = {'a'}
assert operator.ior(tags, {'b'}) is tags  # a set is updated in place
```

## Folding With reduce

`reduce(operator.add, parts)` over lists or tuples builds a new, longer object at every step,
copying everything accumulated so far: O(p·t) for p parts holding t items in total, which is
quadratic when the parts are small. `iconcat` on a list extends one accumulator instead, which
is O(p + t). Give it a fresh `[]` as the start value, or it extends the first part in place.

```python
import operator
from functools import reduce

parts = [[1, 2], [3], [4, 5]]

flat = reduce(operator.add, parts)  # O(p·t) - every step copies the prefix
assert flat == [1, 2, 3, 4, 5]

flat = reduce(operator.iconcat, parts, [])  # O(p + t) - one list, extended
assert flat == [1, 2, 3, 4, 5]
assert parts[0] == [1, 2]  # the start value was extended, not a part

numbers = [1, 2, 3, 4, 5]
assert reduce(operator.mul, numbers) == 120  # O(n) for small integers
```

## Common Patterns

### Sorting Records by Several Fields

```python
import operator

class Student:
    def __init__(self, name, grade):
        self.name = name
        self.grade = grade

students = [Student('bob', 92), Student('alice', 85), Student('carol', 92)]

# O(n log n): grade descending, then name ascending, in two stable sorts
ordered = sorted(students, key=operator.attrgetter('name'))
ordered.sort(key=operator.attrgetter('grade'), reverse=True)
assert [s.name for s in ordered] == ['bob', 'carol', 'alice']
```

### Grouping

```python
import operator
from itertools import groupby

rows = [('fruit', 'apple'), ('veg', 'kale'), ('fruit', 'pear'), ('veg', 'leek')]

kind = operator.itemgetter(0)
rows.sort(key=kind)  # O(n log n) - groupby needs equal keys adjacent
groups = {key: [name for _, name in group] for key, group in groupby(rows, key=kind)}  # O(n)
assert groups == {'fruit': ['apple', 'pear'], 'veg': ['kale', 'leek']}
```

### A Dispatch Table

```python
import operator

OPERATORS = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.truediv}

def evaluate(left, symbol, right):
    return OPERATORS[symbol](left, right)  # O(1) lookup, then O(f)

assert evaluate(6, '*', 7) == 42
assert evaluate(1, '/', 4) == 0.25
```

## Performance Best Practices

✅ **Do**:

- Use `itemgetter` and `attrgetter` as sort and `max` keys: the same O(n log n) or O(n), with
  no Python frame per element
- Use `indexOf` or `contains` when you only need to find one match; `countOf` always walks it all
- Use `reduce(operator.iconcat, parts, [])`, or `itertools.chain`, to join many lists
- Assign the result of an in-place function; for an immutable target it is the only result

❌ **Avoid**:

- `reduce(operator.add, parts)` over lists or tuples - O(p·t), quadratic for many small parts
- Building an `itemgetter` from a key list without handling the one-key case, which returns
  a value rather than a tuple
- Expecting `operator.and_` or `operator.or_` to short-circuit - they are the bitwise operators

## Version Notes

- **Python 3.11+**: Added `operator.call`
- **Python 3.14+**: Added `operator.is_none` and `operator.is_not_none`

## Related Modules

- **[functools](functools.md)** - `reduce` and `partial`, the usual partners of these functions
- **[itertools](itertools.md)** - `groupby`, `accumulate` and `chain` take operator functions as keys and callbacks
