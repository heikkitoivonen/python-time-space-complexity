# Bisect Module Complexity

The `bisect` module provides binary search operations for sorted lists.

## Operations

| Operation | Time | Notes |
|-----------|------|-------|
| `bisect_left(a, x)` | O(log n) | Find leftmost position |
| `bisect_right(a, x)` | O(log n) | Find rightmost position |
| `bisect(a, x)` | O(log n) | Alias for bisect_right |
| `insort_left(a, x)` | O(n) | O(log n) search + O(n) insert |
| `insort_right(a, x)` | O(n) | O(log n) search + O(n) insert |
| `insort(a, x)` | O(n) | Alias for insort_right |

## Space Complexity

- Binary search operations: O(1) additional space
- Insert operations: O(n) due to list shifting

## Implementation Details

### Binary Search Guarantee

```python
import bisect

# Must be sorted!
sorted_list = [1, 3, 3, 3, 5, 7, 9]

# bisect_left: leftmost insertion point
pos = bisect.bisect_left(sorted_list, 3)  # pos = 1
# Insert here to keep list sorted (before all 3's)

# bisect_right: rightmost insertion point
pos = bisect.bisect_right(sorted_list, 3)  # pos = 4
# Insert here to keep list sorted (after all 3's)
```

### Finding Elements

```python
import bisect

sorted_list = [1, 3, 5, 7, 9]

# Check if element exists
def exists(sorted_list, x):
    pos = bisect.bisect_left(sorted_list, x)
    return pos < len(sorted_list) and sorted_list[pos] == x

exists(sorted_list, 5)  # True - O(log n)
exists(sorted_list, 4)  # False - O(log n)
```

## Common Use Cases

### Sorted Insert

```python
import bisect

sorted_list = [1, 3, 5, 7]

# Insert while maintaining order - O(n) overall
# (O(log n) search + O(n) shift)
bisect.insort(sorted_list, 4)  # [1, 3, 4, 5, 7]

# Better for many insertions: use list, then sort
# Multiple inserts: O(n log n) with sort
# vs O(n²) with repeated insort
```

### Finding Ranges

```python
import bisect

# Find all equal elements
sorted_list = [1, 3, 3, 3, 5, 7, 9]
target = 3

left = bisect.bisect_left(sorted_list, target)
right = bisect.bisect_right(sorted_list, target)

equals = sorted_list[left:right]  # All 3's - O(log n) search
```

### Finding Insertion Point for Range

```python
import bisect

# Find where range [a, b] fits in sorted list
sorted_list = [1, 5, 10, 15, 20]
target_range = (7, 12)

# Position to insert start of range
start_pos = bisect.bisect_right(sorted_list, target_range[0])

# Position to insert end of range
end_pos = bisect.bisect_left(sorted_list, target_range[1])

print(f"Insert range {target_range} at positions {start_pos}-{end_pos}")
```

## Performance Comparison

### Searching in Sorted Data

```python
import bisect

data = sorted(range(1000000))

# Bad: Linear search - O(n)
found = 500000 in data  # Scans linearly

# Good: Binary search - O(log n)
pos = bisect.bisect_left(data, 500000)  # Much faster!
found = pos < len(data) and data[pos] == 500000
```

### Maintaining Sorted Lists

```python
import bisect

# Many insertions scenario
sorted_list = [1, 3, 5, 7, 9]

# Bad: Multiple insort - O(n²)
for item in [2, 4, 6, 8]:
    bisect.insort(sorted_list, item)  # O(n) each

# Better: Collect, sort once - O(n log n)
sorted_list.extend([2, 4, 6, 8])
sorted_list.sort()  # Single O(n log n) operation
```

## Detailed Examples

### Grade Ranges

```python
import bisect

# Map scores to grades
grade_breaks = [60, 70, 80, 90]
grades = ['F', 'D', 'C', 'B', 'A']

def get_grade(score):
    i = bisect.bisect(grade_breaks, score)
    return grades[i]

print(get_grade(85))  # 'B' - O(log n)
print(get_grade(95))  # 'A' - O(log n)
```

### Timestamp Lookup

```python
import bisect
from datetime import datetime, timedelta

# Find events in a time range
events = [
    (datetime(2024, 1, 1, 10), 'event1'),
    (datetime(2024, 1, 1, 12), 'event2'),
    (datetime(2024, 1, 1, 15), 'event3'),
    (datetime(2024, 1, 1, 18), 'event4'),
]

timestamps = [e[0] for e in events]

# Find events after specific time
target = datetime(2024, 1, 1, 14)
idx = bisect.bisect_right(timestamps, target)
later_events = events[idx:]  # O(log n) search

print(later_events)  # Events at 3pm and 6pm
```

## Advanced: Custom Key Functions

```python
import bisect
from bisect import bisect_right

# Custom objects - compare by second element
data = [('a', 1), ('b', 3), ('c', 5)]
keys = [x[1] for x in data]

# Find position for ('d', 4)
pos = bisect_right(keys, 4)
data.insert(pos, ('d', 4))
```

## Important Notes

!!! warning "Sorted Data Requirement"
    The input list MUST be sorted for binary search to work correctly.
    
    ```python
    # Wrong: Data not sorted
    unsorted = [3, 1, 4, 1, 5]
    pos = bisect.bisect(unsorted, 2)  # Incorrect result!
    ```

!!! tip "Amortized Efficiency"
    For many insertions:

    - Multiple `insort()` calls: O(n²) overall
    - Collect then single `sort()`: O(n log n) overall
    
    Choose based on your access patterns.

## Related Documentation

- [Heapq Module](heapq.md)
- [Collections Module](collections.md)
- [List Methods](../builtins/list.md)
