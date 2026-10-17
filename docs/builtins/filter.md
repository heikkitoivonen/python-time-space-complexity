# filter() Function Complexity

The `filter(function, iterable)` function returns an iterator over the items of `iterable` for
which `function(item)` is true. It is lazy: building it calls `iter(iterable)` and takes no items,
and each step takes items from that iterator, testing each with `function`, until one passes.

`n` is the number of items taken from the underlying iterator, `k` is the cost of one call to
`function`, and `m` is the number of items kept. Getting the iterator, and each item from it, is
priced at O(1), as it is for lists, tuples, strings and ranges; an iterable that does more work
adds that cost to construction or to every step. The truth test of an item or of a predicate's
result is priced at O(1), as it is for the built-in types, so with `None` or `bool` as the
function k is O(1).

## Complexity Reference

### filter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `filter(function, iterable)` | O(1) | O(1) | Calls `iter(iterable)` once and takes no items; `function` is not called yet, and a non-iterable raises `TypeError` here |
| `filter(None, iterable)` | O(1) | O(1) | Keeps the truthy items; `filter(bool, iterable)` gives the same result |
| `next()` on a filter object | O(s·k) | O(1) | s = items taken to reach the next kept item; when none is left, the whole rest of the input is taken before `StopIteration` |
| Iterating a filter object | O(n·k) | O(1) | Kept items are handed out one at a time, not accumulated |
| `list(filter(function, iterable))` | O(n·k) | O(m) | Holds the m kept items |

## Basic Usage

### Filtering with a Function

```python
numbers = [1, 2, 3, 4, 5]

evens = filter(lambda x: x % 2 == 0, numbers)    # O(1) - nothing is tested yet
assert list(evens) == [2, 4]                     # O(n·k) time, O(m) space

kept = []
for num in filter(lambda x: x > 2, numbers):     # O(n·k)
    kept.append(num)
assert kept == [3, 4, 5]
```

### Filtering with None

`None` in place of a function keeps the items that are truthy. It removes every falsy value -
`0`, `False`, `""`, `[]` and `None` alike - so it is not the same as removing `None`.

```python
values = [0, 1, False, 2, None, 3, "", 4, []]

assert list(filter(None, values)) == [1, 2, 3, 4]     # O(n)
assert list(filter(bool, values)) == [1, 2, 3, 4]     # the same result

maybe = [1, None, 0, 2]
assert list(filter(None, maybe)) == [1, 2]                     # drops 0 too
assert [x for x in maybe if x is not None] == [1, 0, 2]        # drops only None
```

## Lazy, Single-Pass Iteration

Building a filter object calls no predicate and takes no item. A loop that
stops early pays only for the items it took, which includes every rejected item before the last
match. The object is its own iterator, so it can be consumed once.

```python
tested = []

def is_multiple_of_1000(x):
    tested.append(x)
    return x % 1000 == 0

matches = filter(is_multiple_of_1000, range(10**9))    # O(1) - nothing is tested yet
assert tested == []

first = [next(matches) for _ in range(3)]               # O(s·k) per next()
assert first == [0, 1000, 2000]
assert len(tested) == 2001          # every rejected item before the third match was tested

assert next(matches) == 3000        # resumes where it stopped
```

```python
evens = filter(lambda x: x % 2 == 0, [1, 2, 3, 4])
assert iter(evens) is evens
assert list(evens) == [2, 4]
assert list(evens) == []            # already exhausted

try:
    len(filter(None, [1, 2]))
except TypeError as exc:
    assert "has no len()" in str(exc)
else:
    raise AssertionError("len() did not raise")
```

### A Single next() Can Scan the Whole Input

`next()` returns only when it finds a kept item, so one call can take any number of items. When
nothing matches, the first `next()` takes every item before it raises `StopIteration`.

```python
tested = []

def never(x):
    tested.append(x)
    return False

none_kept = filter(never, range(10_000))
assert next(none_kept, None) is None    # O(n·k) - one call tests all 10,000 items
assert len(tested) == 10_000
```

## Predicate Cost

The predicate runs once for every item taken, so its cost multiplies the item count. Trial
division does O(√v) work on an item of value v, so over values up to v it makes k = O(√v) and the
whole pass O(n·√v).

```python
def is_prime(v):                     # O(√v)
    if v < 2:
        return False
    for i in range(2, int(v**0.5) + 1):
        if v % i == 0:
            return False
    return True

primes = filter(is_prime, range(1, 100))        # O(1)
assert list(primes)[:5] == [2, 3, 5, 7, 11]     # O(n·√v)
```

## filter() vs Comprehensions

`filter()`, a list comprehension and an explicit loop are all O(n·k). They differ in when the work
happens and what is held. A list comprehension is eager and builds the whole O(m) list; a generator
expression is lazy, like `filter()`.

```python
numbers = [1, 2, 3, 4, 5]

by_filter = list(filter(lambda x: x > 2, numbers))       # O(n) time, O(m) space
by_listcomp = [x for x in numbers if x > 2]              # O(n) time, O(m) space

by_loop = []
for x in numbers:                                        # O(n) time, O(m) space
    if x > 2:
        by_loop.append(x)

assert by_filter == by_listcomp == by_loop == [3, 4, 5]

lazy = (x for x in numbers if x > 2)                     # O(1) - like filter()
assert next(lazy) == 3
```

## Common Patterns

### Filtering Objects by an Attribute

```python
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

people = [Person("Alice", 30), Person("Bob", 15), Person("Charlie", 25)]

def is_adult(person):
    return person.age >= 18

adults = list(filter(is_adult, people))      # O(n)
assert [p.name for p in adults] == ["Alice", "Charlie"]
```

### Filtering by Type

```python
mixed = [1, "two", 3, "four", 5, "six"]

integers = list(filter(lambda x: isinstance(x, int), mixed))    # O(n)
assert integers == [1, 3, 5]
```

### Summing Without a List

Passing the filter object straight to a consumer such as `sum()` keeps the space O(1).

```python
total = sum(filter(lambda x: x % 3 == 0, range(1_000)))      # O(n) time, O(1) space
assert total == sum(range(0, 1_000, 3))
```

## Edge Cases

```python
assert list(filter(lambda x: x > 5, [])) == []
assert list(filter(lambda x: x > 0, [1, 2, 3])) == [1, 2, 3]       # all kept
assert list(filter(lambda x: x > 100, [1, 2, 3])) == []            # all tested, none kept

try:
    filter(None, 42)
except TypeError as exc:      # raised when the object is built, not when it is iterated
    assert "not iterable" in str(exc)
else:
    raise AssertionError("filter(None, 42) did not raise")

try:
    filter(None, iterable=[1])
except TypeError as exc:
    assert "takes no keyword arguments" in str(exc)
else:
    raise AssertionError("a keyword argument did not raise")
```

## Performance Best Practices

✅ **Do**:

- Use `filter(None, iterable)` to drop falsy values in one O(n) pass
- Feed the filter object straight to `sum()`, `any()`, a loop or `next()` - O(1) space
- Stop early with `next()` or `break` when you need only the first matches - only the items taken are paid for

❌ **Avoid**:

- `filter(None, ...)` when only `None` should go - it drops `0`, `""` and other falsy values too
- `list(filter(...))` when one pass over the kept items is enough - O(m) space for nothing
- Expecting `next()` on a filter object to be O(1) - it takes every rejected item before the next match
- Iterating an exhausted filter object again - the second pass is empty

## Version Notes

- **All Python 3**: `filter()` is lazy and single-pass, and its bounds are the same on every supported version

## Related Functions

- **[map()](map.md)** - Apply function to all items
- **[zip()](zip.md)** - Combine iterables
- **[any()](any.md)** - Check if any item passes condition
- **[all()](all.md)** - Check if all items pass condition
- **[itertools.filterfalse()](../stdlib/itertools.md)** - Opposite of filter
