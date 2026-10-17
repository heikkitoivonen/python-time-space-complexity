# next() Function Complexity

The `next()` function takes the next item from an iterator by calling its `__next__()` method once.
It adds O(1) work of its own, so the cost of a call is the cost of producing one item, which depends
on the iterator.

`k` is the items a `filter` iterator examines to return one: the items it skips, plus the one it
returns. `m` is the input iterables of a `map` iterator. A user-defined `__next__`, a generator's
body, the function, predicate or callable an iterator calls, taking an item from the input of a
`filter` or `map`, and the `==` comparison with a sentinel cost what they do; the bounds below are
the work `next()` and the built-in iterators add to them.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `next(iterator)` | O(1) | O(1) | Iterators over `list`, `tuple`, `str`, `bytes` and `range`; any other iterator costs what its `__next__` does |
| `next(iterator, default)` | Same as `next(iterator)` | Same as `next(iterator)` | Returns `default` instead of raising `StopIteration` |
| `next()` on a `dict` or `set` iterator | O(1) amortized | O(1) | A full pass is O(n) in the n entries, but deleting single keys (`del d[key]`, `d.pop(key)`, `s.remove(x)`, `s.discard(x)`) does not shrink the table: after deleting most of them a pass costs the table's former size |
| `next()` on a generator | Cost of the body | Cost of the body | Runs the body from where it last stopped to the next `yield` |
| `next()` on a `filter` iterator | O(k) | O(1) | Plus one predicate test per examined item |
| `next()` on a `map` iterator | O(m) | O(m) | One item is taken from each input, plus one call of the function |
| `next()` on `iter(callable, sentinel)` | O(1) | O(1) | Plus one call of the callable and one `==` comparison of its result with `sentinel` |
| `next(iterable)` on a non-iterator | O(1) | O(1) | Raises `TypeError`; call `iter()` on a list or `range` first |

## Taking Items One at a Time

### Getting the Next Item

Each call produces one item. After the last one, `next()` raises `StopIteration`.

```python
it = iter([1, 2, 3])

assert next(it) == 1  # O(1)
assert next(it) == 2  # O(1)
assert next(it) == 3  # O(1)

try:
    next(it)
except StopIteration:
    pass
else:
    raise AssertionError("expected StopIteration")
```

### Using a Default Value

With a second argument, an exhausted iterator returns the default instead of raising.

```python
it = iter([1, 2, 3])
assert [next(it), next(it), next(it)] == [1, 2, 3]

assert next(it, "END") == "END"  # O(1) - no StopIteration
assert next(it, None) is None
```

### next() Needs an Iterator

A list or a `range` is iterable but not an iterator, so `next()` rejects it.

```python
try:
    next([1, 2, 3])
except TypeError as error:
    assert "is not an iterator" in str(error)
else:
    raise AssertionError("expected TypeError")

assert next(iter(range(3))) == 0  # O(1)
```

### Mixing next() and a for Loop

A `for` loop over an iterator continues from where `next()` left it, so `next()` can consume a
header before the loop handles the rest.

```python
it = iter(["name,qty", "apple,3", "pear,5"])
header = next(it)  # O(1)

rows = [line.split(",") for line in it]  # One next() per remaining item
assert header == "name,qty"
assert rows == [["apple", "3"], ["pear", "5"]]
```

## Generators

### next() Runs the Body to the Next yield

A generator computes nothing until `next()` asks for an item, and each call runs only the code
between one `yield` and the next.

```python
steps = []

def count_up(limit):
    i = 0
    while i < limit:
        steps.append(i)
        yield i
        i += 1

gen = count_up(1_000_000)
assert steps == []  # Creating the generator runs no code

assert next(gen) == 0  # Runs up to the first yield
assert next(gen) == 1
assert steps == [0, 1]  # Two items produced, not a million
```

### Finding the First Match

`next()` on a generator expression stops at the first item that passes the test, so the rest of the
input is never examined.

```python
checked = []

def is_even(x):
    checked.append(x)
    return x % 2 == 0

values = [1, 3, 4, 5, 6, 8]
first_even = next((x for x in values if is_even(x)), None)  # Stops at 4

assert first_even == 4
assert checked == [1, 3, 4]
assert next((x for x in [1, 3] if is_even(x)), None) is None  # No match: the default
```

## Built-in Iterators

### filter() and map()

One `next()` on a `filter` iterator examines items until one passes, so it is O(k). One `next()` on
a `map` iterator takes one item from each input and makes one call.

```python
calls = []

def is_big(x):
    calls.append(x)
    return x > 10

big = filter(is_big, [1, 2, 3, 50, 4, 60])
assert next(big) == 50  # O(k) - examines 1, 2, 3 and 50
assert calls == [1, 2, 3, 50]

sums = map(lambda a, b, c: a + b + c, [1, 2], [10, 20], [100, 200])
assert next(sums) == 111  # O(m) - one item from each of the 3 inputs
```

### Dict and Set Iterators After Removal

Deleting single keys (`del d[key]`, `d.pop(key)`, `s.remove(x)`, `s.discard(x)`) does not shrink a
`dict` or `set` table, so `next()` on a fresh iterator
scans any deleted slots ahead of the first surviving entry. Rebuilding the container makes it
compact again.

```python
d = {i: i for i in range(10_000)}
for i in range(9_999):
    del d[i]

assert next(iter(d)) == 9_999  # Scans the deleted slots first
d = dict(d)  # One scan of the old table; the new one is sized for what is left
assert next(iter(d)) == 9_999  # O(1)
```

## Performance Best Practices

✅ **Do**:

- Use `next(iterator, default)` to take one item without handling `StopIteration`
- Use `next()` on a generator expression to find the first match without examining the rest
- Use `next()` to consume a header, then a `for` loop for the rest of the same iterator

❌ **Avoid**:

- Calling `next()` on a list or `range`; it raises `TypeError` until you call `iter()`
- Building a list to take its first element when a generator and `next()` would stop early
- Taking items repeatedly from a `dict` or `set` that lost most of its entries without rebuilding it

## Related Functions

- **[iter()](iter.md)** - Get an iterator to call `next()` on, including `iter(callable, sentinel)`
- **[anext()](anext.md)** - The asynchronous counterpart, for async iterators
- **[filter()](filter.md)** - Iterator whose `next()` skips items that fail a predicate
- **[map()](map.md)** - Iterator whose `next()` calls a function on one item from each input
