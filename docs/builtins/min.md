# min() Function Complexity

The `min()` function returns the smallest item of an iterable, or the smallest of two or more
arguments. It makes one pass, comparing each item with the smallest seen so far, and holds only that
item and its key: it never copies or sorts the input.

`n` is the items in the iterable, or the positional arguments. Each comparison is one `<` between
two items, or between two keys when `key` is given, priced at O(1); comparing long strings or tuples
costs up to their length. A `key` function, and the iterable itself when it is a generator or other
lazy iterator, cost what they do on top of the bounds below.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `min(iterable)` | O(n) | O(1) | n - 1 comparisons; on a tie the first smallest item is returned |
| `min(arg1, arg2, *args)` | O(n) | O(1) | The same pass over the arguments |
| `min(iterable, key=func)` | O(n) | O(1) | Plus one `func` call per item; the keys are compared, and the item is returned |
| `min(iterable, default=value)` | O(n) | O(1) | An empty iterable returns `value`; without `default` it raises `ValueError` |
| `min(arg1, arg2, default=value)` | O(1) | O(1) | Raises `TypeError`: `default` needs a single iterable |

## Finding the Minimum

### One Pass Over Any Iterable

`min()` consumes the iterable once, so it works on a generator without building a list, and leaves
an iterator exhausted.

```python
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
assert min(numbers) == 1  # O(n)

assert min(5, 2, 8, 1) == 1  # O(n) - n positional arguments
assert min("python") == "h"  # O(n) - characters compared by code point
assert min(x * x for x in range(-5, 6)) == 0  # O(n) time, O(1) space

it = iter([7, 3, 5])
assert min(it) == 3
assert list(it) == []  # The pass consumed the iterator
```

### Ties Return the First Item

Only a strictly smaller item replaces the current one, so among equal items the first wins.

```python
words = ["pear", "fig", "kiwi", "yam"]
assert min(words, key=len) == "fig"  # "fig" and "yam" tie; the first is returned

pairs = [(1, "b"), (1, "a")]
assert min(pairs, key=lambda p: p[0]) == (1, "b")
assert min(pairs) == (1, "a")  # Without a key, whole tuples are compared
```

## Key Functions

### One Key Call per Item

The key is computed once per item, and the smallest key's item is returned, not the key.

```python
calls = []

def distance(point):
    calls.append(point)
    return point[0] ** 2 + point[1] ** 2

points = [(3, 4), (1, 1), (0, 5)]
closest = min(points, key=distance)  # O(n) - plus 3 key calls

assert closest == (1, 1)
assert calls == points  # Each point's key computed exactly once
```

### Minimum and Its Index

Passing indexes with a key that looks each one up finds the position of the smallest item in the
same single pass.

```python
values = [8, 3, 9, 3, 7]
index = min(range(len(values)), key=values.__getitem__)  # O(n)

assert index == 1  # The first of the two 3s
assert values[index] == 3
```

## Empty and Invalid Input

### Empty Iterables

An empty iterable raises `ValueError` unless `default` is given. `default` cannot be combined with
multiple positional arguments.

```python
try:
    min([])
except ValueError:
    pass
else:
    raise AssertionError("expected ValueError")

assert min([], default=None) is None  # O(1)
assert min([4, 2], default=0) == 2  # default is ignored when there are items

try:
    min(1, 2, default=0)
except TypeError as error:
    assert "default" in str(error)
else:
    raise AssertionError("expected TypeError")
```

### Items That Cannot Be Compared

The comparison raises `TypeError` as soon as the pass meets an item that cannot be ordered against
the current smallest one.

```python
try:
    min([1, "string"])
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## min() vs Sorting

`min()` is O(n). Sorting to take the first item is O(n log n) for unordered input.
`heapq.nsmallest(k, iterable)` is the choice when you need the k smallest.

```python
import heapq
import random

numbers = list(range(10_000))
random.shuffle(numbers)

assert min(numbers) == 0  # O(n)
assert sorted(numbers)[0] == 0  # O(n log n) - sorts everything to read one item
assert heapq.nsmallest(3, numbers) == [0, 1, 2]  # O(n log k) - k = 3
```

## Performance Best Practices

✅ **Do**:

- Pass a generator expression rather than a list comprehension; `min()` needs one item at a time
- Use `key=` instead of building `(key, item)` pairs: the same n key calls, in O(1) space
- Use `min(..., default=value)` for an iterable that may be empty
- Use `heapq.nsmallest(k, ...)` when you need the k smallest items

❌ **Avoid**:

- `sorted(x)[0]` to find the minimum: O(n log n) against O(n)
- Calling `min()` twice on an iterator; the second call sees it empty
- Calling `min()` once per item to repeatedly take the smallest remaining item: O(n²) in total;
  sort once or use `heapq`

## Related Functions

- **[max()](max.md)** - The largest item, with the same single pass
- **[sorted()](sorted.md)** - All items in order, when you need more than the smallest
- **[heapq.nsmallest()](../stdlib/heapq.md)** - The k smallest items, when one is not enough
