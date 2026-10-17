# map() Function Complexity

The `map()` function returns an iterator that calls a function on one item from each input iterable
and yields the result. It is lazy: building it reads no items and does not call the function, and each `next()`
produces one result, so the results never have to exist at once unless you collect them.

`n` is the results a `map` yields, which is the length of its shortest input, and `m` is the input
iterables. The function and the inputs' own iterators cost what they do; the bounds below are the
work `map()` adds to them.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `map(function, iterable, *iterables)` | O(m) | O(m) | Calls `iter()` on each input; reads no item and does not call `function` |
| `next()` on a `map` | O(m) | O(m) | Takes one item from each input, then makes one call of `function` |
| Iterating a `map` to the end | O(n·m) | O(m) | Plus n calls of `function`; stops at the first input that runs out |
| `list(map(...))` | O(n·m) | O(n + m) | Plus n calls of `function`; the list holds every result |
| Iterating a `map(..., strict=True)` to the end | O(n·m) | O(m) | Python 3.14+; raises `ValueError` if the inputs' lengths differ, taking at most one more item from each input to find out |

## Lazy Evaluation

### No Items Read Until Consumed

Building a `map` costs the same for a ten-item input and a billion-item `range`; the function
runs once per item taken.

```python
from itertools import islice

calls = []

def square(x):
    calls.append(x)
    return x * x

squares = map(square, range(10**9))  # O(1) - one input, nothing called yet
assert calls == []

first_five = list(islice(squares, 5))  # O(5) - five calls
assert first_five == [0, 1, 4, 9, 16]
assert calls == [0, 1, 2, 3, 4]
```

### A map Is Used Up Once

A `map` is an iterator, so a second pass yields nothing. Collect the results with `list()` if you
need them more than once.

```python
doubled = map(lambda x: 2 * x, [1, 2, 3])

assert list(doubled) == [2, 4, 6]  # O(n)
assert list(doubled) == []  # Already exhausted
```

### Chaining Without Intermediate Lists

Each `map` in a chain pulls one item at a time from the one before it, so a chain of maps over a
stream holds one item per stage rather than a list per stage.

```python
numbers = range(1_000_000)

result = map(lambda x: x + 1, map(lambda x: x * x, numbers))  # O(1) - two iterators
assert sum(result) == sum(x * x + 1 for x in numbers)  # O(n) time, no list built
```

## Multiple Iterables

### Shortest Input Wins

With several inputs, `function` receives one item from each, and the `map` stops when any input
runs out. When an input other than the first runs out, the items already taken from the inputs
before it in that step are discarded.

```python
sums = list(map(lambda a, b, c: a + b + c, [1, 2, 3], [10, 20, 30], [100, 200, 300]))
assert sums == [111, 222, 333]  # O(n·m) - m = 3 inputs

longer = iter([1, 2, 3])
pairs = list(map(lambda a, b: (a, b), longer, [10, 20]))
assert pairs == [(1, 10), (2, 20)]  # Stops at the shorter input
assert list(longer) == []  # 3 was taken from the first input, then discarded
```

### Checking Lengths With strict

From Python 3.14, `strict=True` raises `ValueError` when the inputs have different lengths instead
of stopping silently. The check happens when the first input runs out.

```python
import sys

if sys.version_info >= (3, 14):
    assert list(map(pow, [2, 3], [5, 2], strict=True)) == [32, 9]

    try:
        list(map(pow, [2, 3, 4], [5, 2], strict=True))
    except ValueError as error:
        assert "shorter" in str(error)
    else:
        raise AssertionError("expected ValueError")
```

## Comparison with Alternatives

### map vs List Comprehension

`list(map(f, items))` and `[f(x) for x in items]` are both O(n) time and O(n) space, plus n calls
of `f`. `map()` alone is lazy, like a generator expression; a list comprehension builds the whole
list at once.

```python
words = ["1", "22", "333"]

assert list(map(len, words)) == [len(w) for w in words]  # Both O(n)

lazy = map(len, words)  # O(1) - nothing computed
eager = [len(w) for w in words]  # O(n) - all computed now
assert next(lazy) == eager[0]
```

### Arguments Already in Tuples

`map()` passes one argument per input. When each item is already a tuple of arguments,
`itertools.starmap()` unpacks it instead, at the same O(n) cost.

```python
from itertools import starmap

pairs = [(2, 5), (3, 2), (10, 3)]
assert list(starmap(pow, pairs)) == [32, 9, 1000]  # O(n)
assert list(map(pow, *zip(*pairs))) == [32, 9, 1000]  # Same result from m = 2 inputs
```

## Common Patterns

### Type Conversion and Attribute Extraction

```python
from operator import attrgetter

assert list(map(int, ["1", "2", "3"])) == [1, 2, 3]  # O(n)

class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

people = [Person("Alice", 30), Person("Bob", 25)]
assert list(map(attrgetter("name"), people)) == ["Alice", "Bob"]  # O(n)
```

## Performance Best Practices

✅ **Do**:

- Use `map()` over a large or unbounded input when you consume the results once, in order
- Chain maps over a stream instead of building a list at each step
- Pass `strict=True` on Python 3.14+ when inputs of different lengths are a bug

❌ **Avoid**:

- Iterating a `map` twice; the second pass is empty
- `list(map(...))` when you only need the first few results; take them with `next()` or `islice()`
- Passing an iterator you will keep reading ahead of a shorter input in a multi-input `map`: the
  item taken from it in the last step is lost

## Version Notes

- **Python 3.14+**: `map()` accepts `strict=True`, which raises `ValueError` when the inputs have
  different lengths.

## Related Functions

- **[filter()](filter.md)** - Lazy iterator that keeps the items passing a predicate
- **[zip()](zip.md)** - Combines inputs into tuples, with the same shortest-input rule and `strict`
- **[next()](next.md)** - Takes one result from a `map`
- **[iter()](iter.md)** - The iterator protocol a `map` follows
- **[itertools.starmap()](../stdlib/itertools.md)** - `map()` for arguments already in tuples
- **[functools.reduce()](../stdlib/functools.md#reduce)** - Folds results into one value
