# slice() Function Complexity

The `slice()` function creates a slice object that specifies how to extract a subsequence from a sequence (list, tuple, string, etc.).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Creating slice object | O(1) | O(1) | Just stores indices |
| Using slice with sequence | O(k) | O(k) | Where k is slice length |
| Using slice with indexing `seq[s]` | O(k) | O(k) | Creates new sequence |

## Creating Slice Objects

### Basic Slice Creation

```python
# Creating slice objects - all O(1)
s1 = slice(5)              # start=None, stop=5, step=None
s2 = slice(2, 5)           # start=2, stop=5, step=None
s3 = slice(1, 10, 2)       # start=1, stop=10, step=2
s4 = slice(None, None, -1) # Reverse slice

# Attributes - O(1)
print(s2.start)  # 2
print(s2.stop)   # 5
print(s2.step)   # None
```

## Using Slices with Sequences

### Slicing Lists

```python
# Slice object creation - O(1)
s = slice(2, 5)

# Applying slice to list - O(k) where k=3 elements
lst = [0, 1, 2, 3, 4, 5, 6]
result = lst[s]  # [2, 3, 4] - O(3)

# Direct slicing syntax - also O(k)
result = lst[2:5]  # [2, 3, 4] - O(3)
```

### Slicing Strings

```python
# Slice object - O(1)
s = slice(1, 4)

# Apply to string - O(k)
text = "Hello World"
result = text[s]  # "ell" - O(3)

# Both equivalent in complexity
result = text[1:4]  # "ell" - O(3)
```

### Slicing with Step

```python
# Create slice with step - O(1)
s = slice(0, 10, 2)  # Every 2nd element

# Apply to sequence - O(k)
lst = list(range(20))
result = lst[s]  # [0, 2, 4, 6, 8] - O(5 elements)

# Negative step reverses - O(k)
s_rev = slice(None, None, -1)
result = lst[s_rev]  # Reversed list - O(n)
```

## Common Patterns

### Extracting Subsequences

```python
# Define reusable slice objects - O(1) each
FIRST_THREE = slice(3)
MIDDLE = slice(25, 75)
LAST_FIVE = slice(-5, None)

# Using slices - complexity depends on slice size
data = list(range(100))

first = data[FIRST_THREE]    # O(3)
middle = data[MIDDLE]        # O(50)
last = data[LAST_FIVE]       # O(5)
```

### Stride Operations

```python
# Every nth element - O(1) to create, O(n/step) to apply
def get_every_nth_slice(n):
    return slice(None, None, n)

s = get_every_nth_slice(3)
lst = list(range(30))

result = lst[s]  # [0, 3, 6, 9, ..., 27] - O(10)
```

### Reversing Sequences

```python
# Create reverse slice - O(1)
reverse_slice = slice(None, None, -1)

# Apply to sequence - O(n)
lst = [1, 2, 3, 4, 5]
result = lst[reverse_slice]  # [5, 4, 3, 2, 1] - O(5)

# Equivalent to:
result = lst[::-1]  # O(n)
```

## Advanced Usage

### Slice Objects in Custom Classes

```python
class MySequence:
    def __init__(self, data):
        self.data = data
    
    def __getitem__(self, key):
        if isinstance(key, slice):
            # Handle slice object - O(k)
            start, stop, step = key.indices(len(self.data))
            return [self.data[i] for i in range(start, stop, step)]
        else:
            # Handle single index - O(1)
            return self.data[key]

# Usage
seq = MySequence([10, 20, 30, 40, 50])
result = seq[slice(1, 4)]  # [20, 30, 40] - O(3)
```

### indices() Method

```python
# Get concrete start, stop, step for sequence length
s = slice(1, 10, 2)
start, stop, step = s.indices(5)
# start=1, stop=5, step=2

# Useful for custom sequences
# Time: O(1)
```

### Using Slices in Loops

```python
# Slice and iterate - O(k) to create slice, O(k) to iterate
s = slice(2, 8, 2)  # O(1)
lst = list(range(10))

for item in lst[s]:  # O(3) - creates [2, 4, 6], then iterates
    print(item)

# More efficient: use indices() directly
start, stop, step = s.indices(len(lst))
for i in range(start, stop, step):  # O(3) - no intermediate list
    print(lst[i])
```

## Performance Notes

### Slice Creation vs Application

```python
# Creating slice objects is cheap - O(1)
slices = [slice(i, i+10) for i in range(100)]  # O(100)

# Applying slices is costly - depends on slice size
lst = list(range(1000))

# Creating all results - O(100 * 10) = O(1000)
results = [lst[s] for s in slices]

# More efficient: use indices() and iterate
results = []
for s in slices:
    start, stop, step = s.indices(len(lst))
    results.append(lst[start:stop:step])  # Same complexity but clearer
```

### Slice vs Iteration

```python
# Slicing creates new sequence - O(k)
first_100 = data[slice(100)]  # O(100)

# Iteration doesn't create copy - O(1) per item
for item in itertools.islice(data, 100):  # O(1) each iteration
    process(item)

# For single use, iteration is better
# For reuse, slicing is fine
```

## Comparison with Alternatives

```python
data = list(range(1000))

# Using slice object - O(k)
s = slice(100, 200)
result = data[s]  # O(100)

# Using indexing - O(k)
result = data[100:200]  # O(100) - equivalent

# Using itertools.islice - O(1) per element
result = list(itertools.islice(data, 100, 200))  # O(100) when consumed

# Slice object is most readable
```

## Version Notes

- **Python 2.x and 3.x**: `slice()` function available in all versions
- **Extended slices**: `a[1:2, 3:4]` returns tuple of slices
- **Custom `__getitem__`**: Can receive slice objects directly

## Related Functions

- **[Indexing and slicing syntax](list.md)** - Direct slicing with `[]`
- **[itertools.islice()](../stdlib/itertools.md)** - Lazy slicing for iterators
- **[range()](range.md)** - Generate sequences to slice

## Best Practices

✅ **Do**:

- Create reusable slice objects for repeated patterns
- Use slice objects with custom `__getitem__` methods
- Understand that slicing creates new sequences (O(k))

❌ **Avoid**:

- Assuming slicing is O(1) (it's O(k) where k is slice size)
- Creating unnecessary intermediate slices
- Over-slicing before iteration (use `itertools.islice` for lazy evaluation)
