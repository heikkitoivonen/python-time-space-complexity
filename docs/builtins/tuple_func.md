# tuple() Function Complexity

`tuple()` builds a tuple from nothing or from any iterable. When the argument is already an exact
`tuple`, it returns that same object in O(1): a tuple cannot change, so there is nothing to copy.
Every other argument, including an instance of a `tuple` subclass, is iterated into an exact
`tuple`, and the copy is shallow: it holds references to the items the argument yields, not copies
of them. What the resulting tuple
costs to use is on the [tuple](tuple.md) page.

`n` is the items the argument yields. The bounds count those items and treat taking one item
from the argument as O(1); iterating a generator, a `map()` or another lazy iterable costs whatever
producing its items costs on top, as CPython's own time-complexity table says for `l.extend(t)`.
Space is the new tuple's references to those items; the items themselves are shared, not copied.

## Complexity Reference

### tuple()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tuple()` | O(1) | O(1) | An empty tuple |
| `tuple(t)` where `t` is an exact tuple | O(1) | O(1) | Returns `t` itself |
| `tuple(iterable)` | O(n) | O(n) | Takes every item; an iterator or generator is left exhausted |
| `tuple(lst)` where `lst` is a list, or a tuple subclass instance | O(n) | O(n) | An exact tuple of the items it yields |
| `tuple(d)` where `d` is a dict, set or dict view | O(n) | O(n) | Walks the hash table: one that had most of its items removed costs its former size (see [dict](dict.md)) |

## Building a Tuple

### From an Iterable

Any iterable works. A string yields its characters, a dict its keys, and a `range` its numbers;
each item costs one step.

```python
assert tuple() == ()  # O(1)
assert tuple("abc") == ("a", "b", "c")  # O(n)
assert tuple([1, 2, 3]) == (1, 2, 3)  # O(n)
assert tuple(range(1, 10, 2)) == (1, 3, 5, 7, 9)  # O(n)
assert tuple({"a": 1, "b": 2}) == ("a", "b")  # O(n)
assert tuple({"a": 1, "b": 2}.items()) == (("a", 1), ("b", 2))  # O(n)
assert sorted(tuple({3, 1, 2})) == [1, 2, 3]  # A set's order is not defined
```

### From an Iterator

An iterator or generator is consumed: `tuple()` takes every item, so a second pass over the same
iterator finds nothing.

```python
def squares(limit):
    for x in range(limit):
        yield x * x

gen = squares(5)
assert tuple(gen) == (0, 1, 4, 9, 16)  # O(n)
assert tuple(gen) == ()  # Already exhausted
```

## Copying

### An Exact Tuple Is Returned As Is

`tuple(t)` on an exact tuple returns the same object, so it costs O(1) at any size. A list, or an
instance of a `tuple` subclass, is copied element by element in O(n); the result is always an
exact `tuple`. The copy is shallow either way: a mutable element is shared, and `copy.deepcopy()`
is the way to get independent elements.

```python
class Point(tuple):
    pass

t = (1, [2, 3])
assert tuple(t) is t  # O(1)

p = Point(t)
copied = tuple(p)  # O(n)
assert copied == t and copied is not p
assert type(copied) is tuple

items = [[1], [2]]
frozen = tuple(items)  # O(n)
assert frozen[0] is items[0]  # The element is shared
items.append([3])
assert frozen == ([1], [2])  # The tuple's length does not follow the list
```

## Common Patterns

### Making a Hashable Key From a List

A list cannot be a dict key or a set member; a tuple of hashable items can. Converting costs O(n),
and hashing the new tuple the first time costs O(n) on top, plus each element's own hash.

```python
seen = set()
for row in ([1, 2], [2, 1], [1, 2]):
    seen.add(tuple(row))  # O(n) to build, O(n) to hash

assert seen == {(1, 2), (2, 1)}
```

### A Literal of Constants Is Built Once

A parenthesised tuple whose items are all constants is folded into a single constant when the code
is compiled, so evaluating it costs O(1) and returns the same object each time. `tuple([...])`
builds a list and then a tuple on every call.

```python
def literal():
    return (1, 2, 3)

def converted():
    return tuple([1, 2, 3])

assert literal() is literal()  # Built once, when compiled
assert converted() == literal() and converted() is not converted()
```

## Performance Best Practices

✅ **Do**:

- Pass a tuple straight through: `tuple(t)` on an exact tuple is free, so there is no cost in
  normalising an argument that is already a tuple
- Write a literal such as `(1, 2, 3)` for a fixed set of constants; it is built once
- Call `tuple()` on an iterator or generator when the items are needed more than once

❌ **Avoid**:

- Relying on `tuple()` for independent elements: the copy is shallow
- `tuple()` on a dict or set that had most of its items removed, in a loop: each call walks the
  former size

## Related Functions

- **[tuple](tuple.md)** - What the tuple you built costs to use
- **[list()](list_func.md)** - Convert to list
- **[set()](set_func.md)** - Convert to set
- **[dict()](dict_func.md)** - Convert to dictionary
- **[zip()](zip.md)** - Create tuples from iterables
- **[copy](../stdlib/copy.md)** - Shallow and deep copies
