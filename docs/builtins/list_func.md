# list() Function Complexity

`list()` builds a new list from nothing or from any iterable. It always builds a new object, even
when the argument is already a list, and the copy is shallow: the new list holds references to the
same elements, not copies of them. What the resulting list costs to use is on the
[list](list.md) page.

`n` is the items the argument yields. The bounds count those items and treat taking one item
from the argument as O(1); iterating a generator, a `map()` or another lazy iterable costs whatever
producing its items costs on top, as CPython's own time-complexity table says for `l.extend(t)`.
Space is the new list's references to those items; the items themselves are shared, not copied.

## Complexity Reference

### list()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `list()` | O(1) | O(1) | An empty list |
| `list(iterable)` | O(n) | O(n) | Takes every item; an iterator or generator is left exhausted |
| `list(lst)` where `lst` is a list or tuple | O(n) | O(n) | A new list holding the same elements; for a list, same as `lst.copy()` or `lst[:]` |
| `list(d)` where `d` is a dict, set or dict view | O(n) | O(n) | Walks the hash table: one that had most of its items removed costs its former size (see [dict](dict.md)) |

## Building a List

### From an Iterable

Any iterable works. A string yields its characters, a dict its keys, and a `range` its numbers;
each item costs one step.

```python
assert list() == []  # O(1)
assert list("abc") == ["a", "b", "c"]  # O(n)
assert list(range(1, 10, 2)) == [1, 3, 5, 7, 9]  # O(n)
assert list((1, 2, 3)) == [1, 2, 3]  # O(n)
assert list({"a": 1, "b": 2}) == ["a", "b"]  # O(n)
assert list({"a": 1, "b": 2}.items()) == [("a", 1), ("b", 2)]  # O(n)
assert sorted(list({3, 1, 2})) == [1, 2, 3]  # A set's order is not defined
```

### From an Iterator

An iterator or generator is consumed: `list()` takes every item, so a second pass over the same
iterator finds nothing. Keep the list, not the iterator, when the items are needed twice.

```python
def squares(limit):
    for x in range(limit):
        yield x * x

gen = squares(5)
assert list(gen) == [0, 1, 4, 9, 16]  # O(n)
assert list(gen) == []  # Already exhausted

numbers = map(int, ["1", "2", "3"])
assert list(numbers) == [1, 2, 3]  # O(n)
assert next(numbers, None) is None
```

## Copying

### Copying a List

`list(lst)`, `lst.copy()`, `lst[:]` and `copy.copy(lst)` all build a new list of the same `n`
references in O(n). The copy is shallow: a mutable element is shared by both lists, and
`copy.deepcopy()` is the way to get independent elements.

```python
import copy

inner = [1, 2, 3]
outer = [inner, [4]]

shallow = list(outer)  # O(n)
assert shallow == outer and shallow is not outer
assert shallow[0] is inner
assert outer.copy() == outer[:] == copy.copy(outer) == shallow

shallow[0][0] = 999
assert inner == [999, 2, 3]  # The element is shared

deep = copy.deepcopy(outer)
assert deep[0] is not inner
```

## Common Patterns

### Taking a Snapshot Before Mutating

Changing a dict's size while iterating it raises `RuntimeError`. Copying its keys with `list()`
first costs O(n) once and lets the loop add and delete keys freely.

```python
stock = {"apples": 0, "pears": 3, "plums": 0}

for name in list(stock):  # O(n) snapshot of the keys
    if stock[name] == 0:
        del stock[name]

assert stock == {"pears": 3}

try:
    for name in stock:
        stock[name + "!"] = 1
except RuntimeError as error:
    assert "changed size during iteration" in str(error)
else:
    raise AssertionError("expected RuntimeError")
```

### Turning Characters Into a List and Back

A string is immutable, so each change made by slicing builds a new string in O(n), and `k` changes
cost O(kn). Converting to a list, assigning in O(1) each and joining once costs O(n + k).

```python
chars = list("hello")  # O(n)
chars[0] = "H"  # O(1)
chars[-1] = "O"
assert "".join(chars) == "HellO"  # O(n)
```

## Performance Best Practices

✅ **Do**:

- Call `list()` on an iterator or generator when the items are needed more than once; the iterator
  itself can be read only once
- Iterate a `range` or generator directly when one pass is enough; `list()` holds all n items
- Snapshot a dict's keys with `list(d)` before deleting from it in a loop

❌ **Avoid**:

- Relying on `list()` for independent elements: the copy is shallow
- `list()` on a dict or set that had most of its items removed, in a loop: each call walks the
  former size

## Related Functions

- **[list](list.md)** - What the list you built costs to use
- **[tuple()](tuple_func.md)** - Convert to tuple
- **[set()](set_func.md)** - Convert to set
- **[dict()](dict_func.md)** - Convert to dictionary
- **[range()](range.md)** - Generate numbers lazily
- **[sorted()](sorted.md)** - Build a new sorted list from an iterable
- **[copy](../stdlib/copy.md)** - Shallow and deep copies
