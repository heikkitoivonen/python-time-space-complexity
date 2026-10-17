# max() Function Complexity

The `max()` function returns the largest item of an iterable, or the largest of two or more
arguments. It makes one pass, consumes an iterable lazily, and holds only the best item so far and
its key, so it never builds a copy of its input.

`n` is the items in the iterable, or the positional arguments. Comparing two items with `>` and
calling the key function are each priced at O(1) unless a row says otherwise; with a `key`, `k` is
the cost of one key call. Comparisons whose operands are long strings or tuples cost what those
comparisons cost.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `max(iterable)` | O(n) | O(1) | n - 1 comparisons; items are taken one at a time and only the largest so far is kept |
| `max(arg1, arg2, *args)` | O(n) | O(1) | n = arguments |
| `max(iterable, key=func)` | O(n·k) | O(1) | `func` is called once per item; only the best item and its key are kept |
| `max(iterable, default=value)` | O(n) | O(1) | An empty iterable returns `value` |
| `max(empty_iterable)` | O(1) | O(1) | Raises `ValueError` |
| `max(range_object)` | O(n) | O(1) | Iterates the range; the endpoints are not used as a shortcut |

Among equal largest items, `max()` returns the first one it meets.

## Finding the Largest Item

### Any Iterable

Every item is compared, so the cost is O(n) whatever the container: a sorted `list` or a `range` is
scanned like any other iterable.

```python
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
assert max(numbers) == 9  # O(n)

assert max((1, 2, 3)) == 3
assert max({1, 2, 3}) == 3
assert max("abc") == "c"
assert max(range(1_000)) == 999  # O(n) - iterates the range
assert max(iter([1, 2, 3])) == 3
```

### Multiple Arguments

```python
assert max(5, 2, 8, 1) == 8  # O(n) in the arguments
assert max(3.14, 2.71, 1.41) == 3.14
```

### Generators Hold One Item at a Time

`max()` takes items one by one, so a generator expression keeps memory at O(1), where a list
comprehension first builds all n items.

```python
largest = max(x for x in range(100_000) if x % 7 == 0)  # O(n) time, O(1) space
assert largest == 99_995

largest = max([x for x in range(100_000) if x % 7 == 0])  # O(n) space for the list
assert largest == 99_995
```

## Key Functions

### One Key Call per Item

The key is called once for each item, and `max()` keeps the key of the best item rather than
calling the key again, so a key costing `k` gives O(n·k).

```python
calls = []

def length(word):
    calls.append(word)
    return len(word)

words = ["apple", "pie", "banana", "cat"]
assert max(words, key=length) == "banana"  # O(n·k)
assert calls == words  # Each word once
```

### The Key With the Largest Value

With `key=d.get`, each key call is one dictionary lookup, so finding the key of the largest value is
O(n) in the entries.

```python
scores = {"alice": 82, "bob": 95, "carol": 77}
assert max(scores, key=scores.get) == "bob"  # O(n)
```

### Attributes and Tuple Fields

```python
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

people = [Person("Alice", 30), Person("Bob", 25), Person("Charlie", 35)]
assert max(people, key=lambda p: p.age).name == "Charlie"  # O(n)

coords = [(1, 5), (3, 2), (2, 8)]
assert max(coords) == (3, 2)  # Tuples compare by first element, then the next
assert max(coords, key=lambda c: c[1]) == (2, 8)
```

### Ties Return the First Item

`max()` only replaces its best item with one that compares strictly larger, so among equals the
first wins.

```python
words = ["pear", "plum", "fig"]
assert max(words, key=len) == "pear"  # "plum" is as long, but comes later
```

## Comparison with Sorting

`max()` is O(n) time and O(1) space. Sorting to take the last element is O(n log n) time and O(n)
space for the new list, and `heapq.nlargest(k, iterable)` is the choice when you need the k largest
items.

```python
import heapq

numbers = [(i * 7919) % 10_007 for i in range(10_000)]

assert max(numbers) == 10_006  # O(n)
assert sorted(numbers)[-1] == 10_006  # O(n log n), and a full copy
assert heapq.nlargest(3, numbers) == [10_006, 10_005, 10_004]  # O(n log k)
```

## Edge Cases

### Empty Iterables

An empty iterable raises `ValueError` unless `default` is given. `default` is accepted only with a
single iterable argument.

```python
try:
    max([])
except ValueError as error:
    assert "empty" in str(error)
else:
    raise AssertionError("expected ValueError")

assert max([], default=0) == 0  # O(1)
assert max([4, 7], default=0) == 7  # The default is unused when there are items

try:
    max(1, 2, default=0)
except TypeError:
    pass
else:
    raise AssertionError("expected TypeError")
```

### A Single Non-Iterable Argument

One argument must be an iterable; `max()` does not treat a lone value as its own maximum.

```python
try:
    max(42)
except TypeError as error:
    assert "not iterable" in str(error)
else:
    raise AssertionError("expected TypeError")

assert max([42]) == 42
```

### Items That Cannot Be Compared

```python
try:
    max([1, "string"])
except TypeError as error:
    assert "'>' not supported" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Performance Best Practices

✅ **Do**:

- Use `max()` rather than sorting when you need only the largest item
- Pass a generator expression rather than a list comprehension, to keep memory O(1)
- Pass `default=` when the iterable may be empty

❌ **Avoid**:

- `sorted(items)[-1]`: O(n log n) time and an O(n) copy for one item
- `max(*items)` on a list or other non-tuple collection: unpacking builds a tuple of all n items first

## Related Functions

- **[min()](min.md)** - Find the smallest item, with the same costs
- **[sorted()](sorted.md)** - Sort all items, O(n log n)
- **[sum()](sum.md)** - Another single O(n) pass over an iterable
- **[heapq.nlargest()](../stdlib/heapq.md)** - Find the k largest items in O(n log k)
