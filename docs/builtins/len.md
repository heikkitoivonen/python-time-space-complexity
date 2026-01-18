# len() Function Complexity

The `len()` function returns the number of items in a container object.

## Complexity by Type

| Type | Time | Space | Notes |
|------|------|-------|-------|
| `list` | O(1) | O(1) | Direct length attribute |
| `tuple` | O(1) | O(1) | Immutable, cached |
| `dict` | O(1) | O(1) | Maintains size |
| `set` | O(1) | O(1) | Maintains size |
| `str` | O(1) | O(1) | Immutable, cached |
| `bytes` | O(1) | O(1) | Immutable, cached |
| `range` | O(1) | O(1) | Computed, not stored |
| `deque` | O(1) | O(1) | Maintains size |
| `defaultdict` | O(1) | O(1) | Inherits from dict |
| `OrderedDict` | O(1) | O(1) | Maintains size |

## Built-in Container Types

All built-in container types cache their length and return it in constant time:

```python
# All O(1)
lst = [1, 2, 3, 4, 5]
length = len(lst)  # O(1) - stored length

tpl = (1, 2, 3)
length = len(tpl)  # O(1) - immutable

dct = {'a': 1, 'b': 2}
length = len(dct)  # O(1) - maintains size

s = "hello"
length = len(s)    # O(1) - immutable string
```

## Custom Objects

For custom classes, `len()` calls the `__len__()` method:

```python
class MyContainer:
    def __init__(self, items):
        self.items = items
    
    def __len__(self):
        # Your implementation determines complexity
        return len(self.items)  # O(1) if efficient

# Usage
obj = MyContainer([1, 2, 3])
length = len(obj)  # O(1) - delegates to cached length

# Inefficient implementation
class BadContainer:
    def __init__(self, items):
        self.items = items
    
    def __len__(self):
        # Recomputes from scratch - O(n)!
        return sum(1 for _ in self.items)

obj = BadContainer([1, 2, 3])
length = len(obj)  # O(n) - iterates through items
```

## Generator Expressions and Iterators

`len()` does NOT work with generators/iterators:

```python
# Works - list has cached length
lst = [1, 2, 3, 4, 5]
length = len(lst)  # O(1)

# Fails - generators don't have length
gen = (x for x in range(5))
# length = len(gen)  # TypeError: object of type 'generator' has no len()

# Must consume iterator to count
count = sum(1 for x in gen)  # O(n) - must iterate
```

## Common Patterns

### Checking if Container is Empty

```python
# Correct - O(1), doesn't create list
if len(container) > 0:
    process(container)

# Also correct - O(1), more Pythonic
if container:
    process(container)

# Inefficient - creates a list
if len(list(generator)) > 0:  # O(n) - forces evaluation
    process(generator)
```

### Size Validation

```python
def process_list(items):
    if len(items) == 0:      # O(1)
        raise ValueError("Empty list")
    if len(items) > 1000:    # O(1)
        raise ValueError("Too large")
    
    # Process items
    for item in items:
        pass
```

### Comparing Container Sizes

```python
# All O(1)
if len(list1) > len(list2):
    smaller = list2
    larger = list1
else:
    smaller = list1
    larger = list2

# More efficient than computing actual difference
if len(list1) != len(list2):
    print("Different sizes")
```

## Performance Notes

### Length Operations in Loops

```python
# O(n) - good, length is O(1)
for i in range(len(items)):
    process(items[i])

# Also O(n) - length check is O(1) per iteration
count = 0
while count < len(items):
    process(items[count])
    count += 1
```

### Pre-computing Length

```python
items = get_large_list()

# Don't do this - wastes a variable
length = len(items)
for i in range(length):  # length already O(1)
    process(items[i])

# Instead - directly use len() which is O(1)
for i in range(len(items)):
    process(items[i])
```

## Special Cases

### Range Objects

```python
# Range length is O(1), not O(n)
r = range(10**1000)
length = len(r)  # O(1) - computed from start, stop, step

# This is computed, not stored
# So even huge ranges have O(1) length
```

### String Encoding

```python
# All string types have O(1) length
s = "hello"
length = len(s)  # O(1) - character count

b = b"hello"
length = len(b)  # O(1) - byte count

# Note: len(str) counts characters, not bytes
s = "café"
print(len(s))      # 4 - four characters
print(len(s.encode('utf-8')))  # 5 - five bytes
```

## Version Notes

- **Python 2.x**: `len()` works on built-in types, custom `__len__` method
- **Python 3.x**: Same behavior, more consistent
- **All versions**: O(1) for built-in containers (they cache length)

## Related Functions

- **[all()](all.md)** - Check if all items are true
- **[any()](any.md)** - Check if any item is true
- **[max()](max.md)** - Find maximum value
- **[min()](min.md)** - Find minimum value
- **[sum()](sum.md)** - Sum all items

## Best Practices

✅ **Do**:

- Use `len()` to check if container is empty (it's O(1))
- Use `if container:` for truthiness checks
- Cache length only if used multiple times in tight loops

❌ **Avoid**:

- `len(list(generator))` to count generator items (O(n))
- Recomputing length in `__len__` (should be cached)
- Assuming generators have length (they don't)
