# list() Function Complexity

The `list()` function creates lists from iterables or creates empty lists.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Empty list | O(1) | O(1) | list() |
| From iterable | O(n) | O(n) | n = iterable length |
| From string | O(n) | O(n) | n = string length |
| From range | O(n) | O(n) | n = range size |
| Shallow copy | O(n) | O(n) | n = list length |

## Basic Usage

### Create Empty List

```python
# O(1)
lst = list()  # []
```

### From String

```python
# O(n) - where n = string length
lst = list("hello")  # ['h', 'e', 'l', 'l', 'o']
lst = list("abc")    # ['a', 'b', 'c']
```

### From Range

```python
# O(n) - where n = range size
lst = list(range(5))           # [0, 1, 2, 3, 4]
lst = list(range(1, 10, 2))    # [1, 3, 5, 7, 9]
lst = list(range(10, 0, -1))   # [10, 9, 8, ..., 1]
```

### From Other Iterables

```python
# O(n) - where n = number of items
lst = list([1, 2, 3])          # [1, 2, 3] (copy)
lst = list((1, 2, 3))          # [1, 2, 3] (from tuple)
lst = list({1, 2, 3})          # [1, 2, 3] (from set - unordered)
lst = list({"a": 1, "b": 2})   # ['a', 'b'] (dict keys)
lst = list(map(str, [1, 2]))   # ['1', '2'] (from generator)
```

### From Generator

```python
# O(n) - consumes generator
def gen():
    yield 1
    yield 2
    yield 3

lst = list(gen())  # [1, 2, 3] - O(n)
```

## Complexity Details

### Iterating and Copying

```python
# O(n) - must iterate to copy
original = [1, 2, 3, 4, 5]
copy = list(original)  # O(5) - shallow copy

# Each element is accessed once
for item in iterable:  # O(n)
    append to list

# vs slicing - also O(n)
copy = original[:]  # O(n) - same complexity
```

### From String

```python
# O(n) - linear in string length
short = list("ab")     # O(2) - ["a", "b"]
long = list("a" * 1000)  # O(1000)

# Each character becomes one list item
```

### From Range

```python
# O(n) - must materialize all values
small = list(range(5))     # O(5)
large = list(range(10**6))  # O(10^6) - slow!

# range() is lazy, list() forces evaluation
r = range(10**9)           # O(1) - just create range
lst = list(r)              # O(10^9) - materialize all!
```

## Common Patterns

### Convert Iterable to List

```python
# O(n) - general conversion
def process_items(items):
    items_list = list(items)  # O(n) - ensure it's a list
    # Now can index, slice, etc.
    return items_list[0]  # O(1)

# Useful for generators
gen = (x for x in range(5))
lst = list(gen)  # [0, 1, 2, 3, 4]
```

### String Manipulation

```python
# O(n) - convert string to list of characters
text = "hello"
chars = list(text)  # ['h', 'e', 'l', 'l', 'o']

# Modify
chars[0] = 'H'

# Convert back
result = "".join(chars)  # "Hello"
```

### List Comprehension Alternative

```python
# Both O(n), but comprehensions often faster
data = range(1000)

# Using list() with generator
lst = list(x * 2 for x in data)  # O(n)

# Using list comprehension
lst = [x * 2 for x in data]      # O(n) - often faster
```

## Performance Patterns

### Copying Lists

```python
# All O(n), different ways
original = [1, 2, 3, 4, 5]

# Using list()
copy1 = list(original)      # O(n)

# Using slicing
copy2 = original[:]         # O(n)

# Using copy.copy()
import copy
copy3 = copy.copy(original) # O(n)

# All have same complexity
```

### vs List Literal

```python
# O(n) - both create list with items
lst1 = [1, 2, 3, 4, 5]      # Literal - O(n) to parse
lst2 = list([1, 2, 3, 4, 5])  # O(n) to copy

# Literal is usually faster (no copying)
```

### From Generator Expression

```python
# O(n) - materialize all values
nums = (x**2 for x in range(100))
lst = list(nums)  # O(100) - consume generator

# vs list comprehension
lst = [x**2 for x in range(100)]  # O(100)

# Comprehensions often faster
```

## Practical Examples

### Parse CSV

```python
# O(n) - convert strings to list of values
csv_line = "1,2,3,4,5"
values = csv_line.split(",")  # ['1', '2', '3', '4', '5']

# Convert to integers
numbers = list(map(int, values))  # O(n)
```

### Remove Duplicates (Preserve Order)

```python
# O(n) - convert to set then back
items = [1, 2, 2, 3, 3, 3, 4]
unique = list(dict.fromkeys(items))  # [1, 2, 3, 4] - O(n)

# Preserves first occurrence order
```

### Flatten Nested Lists

```python
# O(n) - flatten one level
nested = [[1, 2], [3, 4], [5, 6]]
flat = []
for sublist in nested:
    flat.extend(sublist)  # O(n) total

# Using list concatenation
flat = sum(nested, [])  # O(n) - but slower due to copying

# Better - list comprehension
flat = [x for sublist in nested for x in sublist]  # O(n)
```

### Read File Lines

```python
# O(n) - read all lines
with open("file.txt") as f:
    lines = list(f)  # O(n) - each line is one item
    # lines = ["line1\n", "line2\n", ...]

# vs
with open("file.txt") as f:
    lines = f.readlines()  # O(n) - same result
```

## Edge Cases

### Empty Iterable

```python
# O(1)
lst = list("")            # []
lst = list([])            # []
lst = list(set())         # []
lst = list(range(0))      # []
```

### Single Item

```python
# O(1)
lst = list("a")       # ['a']
lst = list([1])       # [1]
lst = list(range(1))  # [0]
```

### Very Large Iterable

```python
# O(n) - allocates large list
huge_range = range(10**9)
lst = list(huge_range)  # O(10^9) - very slow and memory-intensive!

# Better - process items without materializing
for item in huge_range:  # Doesn't create list
    process(item)
```

### Nested Lists

```python
# O(n) - shallow copy
inner = [1, 2, 3]
outer = [[inner]]

copied = list(outer)  # O(1) shallow copy
copied[0][0][0] = 999  # Affects original!
# inner is now [999, 2, 3]

# For deep copy
import copy
deep = copy.deepcopy(outer)  # O(n) - true independent copy
```

## String Conversion

```python
# Different from str() to list
text = "hello"

str_to_list = list(text)      # ['h', 'e', 'l', 'l', 'o'] - O(n)
split_text = text.split("")   # ValueError!
split_text = list(text)       # Only way with empty separator

# Split on delimiter
words = text.split("l")       # ['he', '', 'o']
```

## Memory Considerations

```python
# list() uses more memory than range()
small_range = range(10**6)    # Minimal memory - O(1)
small_list = list(range(10))  # Small but uses memory - O(10)

# Materialize only if needed
# Don't do:
lst = list(range(10**9))  # ~40GB of memory!

# Instead:
for item in range(10**9):  # Iterates without storing
    process(item)
```

## Best Practices

✅ **Do**:

- Use list() to convert iterables to lists when indexing needed
- Use list comprehensions instead of list(map(...))
- Avoid materializing huge ranges unnecessarily
- Use slicing for copying: `copy = lst[:]`

❌ **Avoid**:

- list(range(10**9)) - materializes huge list
- Assuming list() is faster than `[...]` literal
- Deep nesting without deepcopy when needed
- Creating list of lists without understanding shallow copy

## Related Functions

- **[tuple()](index.md)** - Convert to tuple
- **[set()](index.md)** - Convert to set
- **[dict()](dict_func.md)** - Convert to dictionary
- **[range()](range.md)** - Generate numbers (lazy)

## Version Notes

- **Python 2.x**: Works with iterables and old-style classes
- **Python 3.x**: Works with all iterables (generators, etc.)
- **All versions**: Creates shallow copy by default
