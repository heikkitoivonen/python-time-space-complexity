# bisect Module Complexity

The `bisect` module finds positions in a sequence the caller keeps sorted. It never sorts and
never checks the order: each search halves the range it was given, reading one element per step,
in constant extra memory. The insert functions pair that search with the sequence's own
`insert()`, and for a list the insert, not the search, is what costs.

`n` is the length of the sequence. The search bounds count probes: one element read, one `key`
call when a key is given, and one `<` comparison each, all priced O(1). A key or a comparison that
does more work multiplies the search by its cost. Indexing is O(1), as it is for a list. Two items
are equal here when neither is `<` the other, comparing keys when a `key` is given.

## Complexity Reference

### Searching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bisect.bisect_left(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | Position before any run of items equal to `x`; `key` is applied to each probed item, never to `x` |
| `bisect.bisect_right(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | Position after any run of items equal to `x` |
| `bisect.bisect(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | The same function as `bisect_right` |

### Inserting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bisect.insort_left(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | O(log n) search, then `a.insert()`, which for a list shifts the tail; `key` is applied to `x` once |
| `bisect.insort_right(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | Inserts after any run of items equal to `x` |
| `bisect.insort(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | The same function as `insort_right` |

## Searching a Sorted List

### Left and Right

The two searches differ only in where they land on a run of equal items: `bisect_left` before
it, `bisect_right` after it. Each still halves the range, so searching a run of duplicates is
O(log n) like any other search, and the pair of them brackets the run however long it is.

```python
import bisect

values = [1, 3, 3, 3, 5, 7, 9]

left = bisect.bisect_left(values, 3)    # O(log n)
right = bisect.bisect_right(values, 3)  # O(log n)
assert (left, right) == (1, 4)
assert values[left:right] == [3, 3, 3]
assert right - left == 3                # occurrences counted without a scan

def contains(sorted_list, x):
    i = bisect.bisect_left(sorted_list, x)  # O(log n), against O(n) for `x in sorted_list`
    return i < len(sorted_list) and sorted_list[i] == x

assert contains(values, 5)
assert not contains(values, 4)
```

### Narrowing With lo and hi

`lo` and `hi` bound the slice that is searched, and a search costs O(log(hi - lo)), whatever the
length of the sequence. An insort still pays for the whole list's insert. A negative `lo` raises
`ValueError`.

```python
import bisect

values = list(range(0, 1_000, 2))

assert bisect.bisect_left(values, 100, lo=40, hi=60) == 50  # O(log 20)

try:
    bisect.bisect_left(values, 100, lo=-1)
except ValueError as error:
    assert 'lo must be non-negative' in str(error)
else:
    raise AssertionError('a negative lo was accepted')
```

### Searching by Key

`key` is called once per probe, on the item probed, so a keyed search makes O(log n) key calls
and needs no parallel list. It is not called on `x`: the searches take `x` as a key value
already. `insort` is the exception - it inserts the record itself, so it calls `key(x)` once to
find where.

```python
import bisect

records = [('a', 1), ('b', 3), ('c', 5)]
by_count = lambda record: record[1]

pos = bisect.bisect_right(records, 4, key=by_count)  # O(log n) key calls; x is the key value
assert pos == 2

bisect.insort(records, ('d', 4), key=by_count)  # O(n); key(x) is called here
assert records == [('a', 1), ('b', 3), ('d', 4), ('c', 5)]
```

A parallel list of keys is the alternative when many searches share one list: it costs O(n) to
build and must be kept in step with every insert, but each search then makes no key calls.

```python
import bisect

records = [('a', 1), ('b', 3), ('c', 5)]
keys = [record[1] for record in records]  # O(n) once

pos = bisect.bisect_right(keys, 4)  # O(log n), no key calls
records.insert(pos, ('d', 4))       # O(n)
keys.insert(pos, 4)                 # O(n) - keys must follow every insert
assert keys == [record[1] for record in records] == [1, 3, 4, 5]
```

### Unsorted Input

Nothing checks that the slice is sorted. On unsorted input the search still returns a position
without raising, but nothing guarantees it is the right one: inserting there can leave the list out
of order.

```python
import bisect

unsorted = [3, 1, 4, 1, 5]

pos = bisect.bisect(unsorted, 2)  # O(log n), no error
result = unsorted[:pos] + [2] + unsorted[pos:]
assert result != sorted(result)
```

## Keeping a List Sorted

### One Insert or a Batch

Each `insort` on a list is O(n), so k inserts into a list of n items cost O(k·(n + k)).
When the inserts arrive together with no searches between them, appending them and sorting once
costs O((n + k) log(n + k)) instead. `insort` is the right tool when searches and inserts
interleave.

```python
import bisect

values = [1, 3, 5, 7]
bisect.insort(values, 4)  # O(n) - the tail shifts
assert values == [1, 3, 4, 5, 7]

# Many inserts at once: O(k·(n + k)) one at a time
one_at_a_time = [1, 3, 5, 7, 9]
for item in [8, 2, 6, 4]:
    bisect.insort(one_at_a_time, item)  # O(n) each

# ... or O((n + k) log(n + k)) as one sort
batch = [1, 3, 5, 7, 9]
batch.extend([8, 2, 6, 4])
batch.sort()
assert batch == one_at_a_time
```

## Common Patterns

### Mapping a Score to a Band

```python
import bisect

breakpoints = [60, 70, 80, 90]
grades = 'FDCBA'

def grade(score):
    return grades[bisect.bisect(breakpoints, score)]  # O(log b), b = breakpoints

assert [grade(score) for score in (33, 60, 77, 89, 90, 100)] == list('FDCBAA')
```

### Events in a Time Window

```python
import bisect
from datetime import datetime

events = [
    (datetime(2024, 1, 1, 10), 'event1'),
    (datetime(2024, 1, 1, 12), 'event2'),
    (datetime(2024, 1, 1, 15), 'event3'),
    (datetime(2024, 1, 1, 18), 'event4'),
]
when = lambda event: event[0]

start = bisect.bisect_left(events, datetime(2024, 1, 1, 11), key=when)  # O(log n)
end = bisect.bisect_right(events, datetime(2024, 1, 1, 15), key=when)   # O(log n)
assert [name for _, name in events[start:end]] == ['event2', 'event3']  # O(m), m = matches
```

## Performance Best Practices

✅ **Do**:

- Use `bisect_left` plus one comparison for membership in a sorted list, instead of an O(n) `in`
- Use `bisect_right - bisect_left` to count a run of equal items in O(log n)
- Pass `lo` and `hi` when the answer is known to lie in part of the list
- Use `key` for an occasional search over records; keep a parallel key list when many searches
  share it

❌ **Avoid**:

- Building a key list for a single search - that is O(n) for an O(log n) answer
- Repeated `insort` to load a batch into a list - extend and sort once
- Searching a list you have not kept sorted - the answer is unreliable, and nothing raises

## Version Notes

- **Python 3.10+**: Added the `key` argument to all six functions

## Related Modules

- **[heapq](heapq.md)** - O(log n) push and pop when only the smallest item is needed, not a
  sorted list
- **[list](../builtins/list.md)** - `insert()` and `sort()`, the costs `insort` and a batch sort
  rest on
