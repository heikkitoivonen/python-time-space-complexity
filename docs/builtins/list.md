# List Operations Complexity

The `list` type is a mutable, ordered sequence. CPython implements it as a dynamic array of
references: it holds a reference to each element and over-allocates so that growing at the end
rarely has to resize.

`n` is the list's length, `k` is the value of a numeric argument (an index or a repeat count),
`i:j` are slice bounds, and `len(t)` is the length of the other operand. A slice with a step `s`
selects `m` elements, and its `i` is the lowest index it selects. Indices are counted after
negative values are normalized. Comparing two elements and calling a `key` function count as O(1);
iterating an operand that is not already a list or tuple adds its own cost. "Amortized" means an
individual call may occasionally pay an O(n) resize, spread over the calls that preceded it.

## Complexity Reference

### list

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(l)` | O(1) | O(1) | The length is stored in the list, not counted |
| `l[k]` | O(1) | O(1) | Direct indexing |
| `l[k] = x` | O(1) | O(1) | Replaces one slot |
| `del l[k]` | O(n-k) | O(1) | Shifts the elements after k one slot left |
| `l.append(x)` | O(1) amortized | O(1) amortized | |
| `l.insert(0, x)` | O(n) | O(1) amortized | Every element moves one slot right |
| `l.insert(k, x)` | O(n-k) amortized | O(1) amortized | Shifts the elements from k onwards one slot right |
| `l.remove(x)` | O(n) | O(1) | Searches from the front, then shifts the elements after the match |
| `l.pop()` | O(1) amortized | O(1) | Removes the last element; nothing is shifted |
| `l.pop(0)` | O(n) | O(1) | Every remaining element moves one slot left |
| `l.pop(k)` | O(n-k) amortized | O(1) | Shifts the elements after k one slot left |
| `l.clear()` | O(n) | O(1) | Releases every element |
| `l.index(x)` | O(n) | O(1) | Linear search; `l.index(x, i, j)` searches only `l[i:j]`, O(j-i) |
| `l.count(x)` | O(n) | O(1) | Linear scan |
| `l.sort(key=None, reverse=False)` | O(n log n) | O(n) | Sorted or reverse-sorted input takes only O(n) comparisons; `key` is called once per element |
| `l.reverse()` | O(n) | O(1) | In place |
| `l.copy()` | O(n) | O(n) | Shallow copy |
| `l.extend(t)` | O(len(t)) amortized | O(len(t)) | Plus the cost of iterating t |
| `l += t` | O(len(t)) amortized | O(len(t)) | Same as `l.extend(t)`; the list stays the same object |
| `l[i:j]` (slicing) | O(j-i) | O(j-i) | With a step, O(m) |
| `l[i:j] = t` | O(j-i) if len(t) == j-i, otherwise O(n-i+len(t)) amortized | O(j-i+len(t)) | Equal lengths overwrite in place; otherwise everything after j moves |
| `l[i:j:s] = t` (s ≠ 1) | O(m) | O(m) | t must have exactly m elements, so nothing moves |
| `del l[i:j]` | O(n-i) | O(j-i) | Everything after j moves left |
| `del l[i:j:s]` | O(n-i) | O(m) | Everything after i closes up |
| `l1 + l2` (concatenation) | O(len(l1)+len(l2)) | O(len(l1)+len(l2)) | A new list |
| `l * k` (repetition) | O(nk) | O(nk) | A new list of n·k references; k ≤ 0 gives an empty list |
| `l *= k` | O(nk) | O(nk) | In place; k ≤ 0 clears the list in O(n) |
| `l1 == l2` | O(n) | O(1) | O(1) when the lengths differ; otherwise stops at the first unequal pair |
| `l1 < l2`, `<=`, `>`, `>=` | O(min(len(l1), len(l2))) | O(1) | Stops at the first unequal pair |
| `for x in l` (iteration) | O(n) | O(1) | O(1) per step |
| `reversed(l)` | O(1) | O(1) | A lazy iterator; walking it is O(n) |
| `x in l` (membership) | O(n) | O(1) | Linear search |
| `min(l)`, `max(l)` | O(n) | O(1) | n-1 comparisons |

## Growing at the End

`append()` is O(1) amortized because a resize reserves room for later appends, so most appends
write into space the list already owns.

```python
import sys

lst = []
resizes = 0
size = sys.getsizeof(lst)
for i in range(10_000):
    lst.append(i)  # O(1) amortized
    if sys.getsizeof(lst) != size:
        resizes += 1
        size = sys.getsizeof(lst)

assert len(lst) == 10_000
assert resizes < 100
```

## Working at the Front

Inserting or removing at index 0 moves every other element, so each call is O(n), and a loop of
them is O(n²). A `collections.deque` adds and removes at both ends in O(1).

```python
from collections import deque

lst = list(range(10_000))
lst.insert(0, -1)  # O(n): every element moves one slot right
assert lst[0] == -1 and len(lst) == 10_001
assert lst.pop(0) == -1  # O(n): every element moves back

queue = deque(range(10_000))
queue.appendleft(-1)  # O(1)
assert queue.popleft() == -1  # O(1)
```

## Slice Assignment

Replacing a slice with the same number of elements overwrites it in place. Any other length opens
or closes a gap, so everything after the slice moves. An extended slice (a step other than 1) only
accepts exactly as many elements as it selects.

```python
lst = list(range(10))
lst[2:5] = ["a", "b", "c"]  # O(j-i): same length, overwritten in place
assert lst == [0, 1, "a", "b", "c", 5, 6, 7, 8, 9]

lst[2:5] = ["x"]  # O(n-i+len(t)): the tail moves left to close the gap
assert lst == [0, 1, "x", 5, 6, 7, 8, 9]

lst[::2] = "ABCD"  # O(m)
assert lst == ["A", 1, "B", 5, "C", 7, "D", 9]

try:
    lst[::2] = "AB"
except ValueError as exc:
    assert "sequence of size 2 to extended slice of size 4" in str(exc)
else:
    raise AssertionError("expected ValueError")
```

## Building a List

`l + t` builds a new list, so `l = l + t` in a loop copies everything built so far on every step.
`l += t` and `extend()` add to the existing list in O(len(t)) amortized.

```python
parts = [[i] for i in range(1_000)]

slow = []
for part in parts:
    slow = slow + part  # O(len(slow)): copies the list each time

fast = []
for part in parts:
    fast += part  # O(len(part)) amortized

assert slow == fast == list(range(1_000))
```

## Sorting

`sort()` is stable and adaptive: input that is already sorted, or reverse-sorted, takes only O(n)
comparisons. A `key` function is called once per element, not once per comparison.

```python
calls = 0


def key(word):
    global calls
    calls += 1
    return word.lower()


words = ["pear", "Apple", "fig", "banana"]
words.sort(key=key)  # O(n log n)
assert words == ["Apple", "banana", "fig", "pear"]
assert calls == len(words)
```

## Performance Best Practices

✅ **Do**:

- Add at the end with `append()` or `extend()`: O(1) amortized per element
- Build a list in reverse by appending, then call `reverse()` once: O(n) in total
- Overwrite a run with `l[i:j] = t` where `len(t) == j - i`: nothing after it moves
- Pass `key=` to `sort()` rather than a `functools.cmp_to_key()` comparison: the key runs n times,
  a comparison function once per comparison

❌ **Avoid**:

- `insert(0, x)` or `pop(0)` in a loop: O(n) each - use `collections.deque`
- `l = l + [x]` in a loop: each step copies the list, O(n²) in total
- `x in l` inside another loop: O(n) per test - build a [set](set.md) once for O(1) average lookups

## Related Types

- **[Deque](../stdlib/collections.md#deque)** - O(1) append and pop at both ends
- **[Array](../stdlib/array.md)** - More memory efficient for large numeric lists
- **[Tuple](tuple.md)** - Immutable alternative
- **[list()](list_func.md)** - Building a list from an iterable

## Further Reading

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's list implementation
