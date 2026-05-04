# str() Function Complexity

The `str()` function converts objects to string representations.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Convert string | O(1) | O(1) | Return as-is |
| Convert primitive | O(1) | O(1) | int, float, bool |
| Convert container | O(n) | O(n) | n = elements |
| Convert custom object | O(m) | O(m) | m = `__str__()` complexity |

## Basic Usage

### Primitives

```python
# O(1) - simple conversions
str(42)         # "42"
str(3.14)       # "3.14"
str(True)       # "True"
str(False)      # "False"
str(None)       # "None"
```

### Strings

```python
# O(1) - return as-is
str("hello")    # "hello"
x = "test"
str(x)          # "test" (same object)
```

### Collections

```python
# O(n) - where n = number of elements
str([1, 2, 3])           # "[1, 2, 3]"
str({"a": 1, "b": 2})    # "{'a': 1, 'b': 2}"
str({1, 2, 3})           # "{1, 2, 3}"
str((1, 2, 3))           # "(1, 2, 3)"
```

## Complexity Details

### String Representation

```python
# O(n) - builds string representation
short_list = [1, 2]
str(short_list)  # O(2) - "[1, 2]"

long_list = list(range(1000))
str(long_list)   # O(1000) - must convert all items
```

### Custom Objects

```python
# O(m) - depends on __str__() implementation

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __str__(self):
        # O(1) - simple string
        return f"Point({self.x}, {self.y})"

p = Point(1, 2)
str(p)  # O(1) - fast conversion

# Inefficient __str__
class BadPoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __str__(self):
        # O(n) - unnecessary processing
        points = [Point(self.x + i, self.y + i) for i in range(100)]
        return f"BadPoint with {len(points)} nearby: {points}"

bp = BadPoint(1, 2)
str(bp)  # O(n) - slow conversion
```

## Common Patterns

### String Building

```python
# O(n) - convert each item
items = [1, 2, 3, 4, 5]

# Convert to strings
str_items = [str(x) for x in items]
# ["1", "2", "3", "4", "5"]

# Join them - O(n)
result = ", ".join(str_items)  # "1, 2, 3, 4, 5"

# More efficient - one operation
result = ", ".join(map(str, items))  # Same result
```

### User Output

```python
# O(n) - convert for display
def display_items(items):
    for item in items:  # O(k) items
        print(str(item))  # O(n) per item - total O(k*n)

items = [1, 2, 3, 4, 5]
display_items(items)
```

### Logging

```python
# O(n) - convert for logging
import logging

value = {"name": "Alice", "age": 30}
logging.info(f"User: {str(value)}")  # O(n)

# Better - let logging handle it
logging.info(f"User: {value}")  # Same result, more Pythonic
```

## Performance Patterns

### Comparison with repr()

```python
# Both O(n), but different purposes

obj = "hello"

# str() - human readable
str(obj)   # "hello"

# repr() - Python representation
repr(obj)  # "'hello'" (with quotes)

# For containers:
lst = [1, 2, 3]
str(lst)   # "[1, 2, 3]"
repr(lst)  # "[1, 2, 3]" (same for containers)
```

### String Concatenation

```python
# Inefficient - O(n^2)
result = ""
for i in range(100):
    result += str(i)  # Each += rebuilds string!

# Better - O(n)
result = "".join(str(i) for i in range(100))

# Even better - just join
result = "".join(map(str, range(100)))
```

### Formatting vs str()

```python
# All O(n), but different clarity

x = 42
y = 3.14

# Using str()
s = str(x) + " and " + str(y)

# Using format()
s = "{} and {}".format(x, y)

# Using f-strings (Python 3.6+)
s = f"{x} and {y}"

# All have similar complexity
```

## Edge Cases

### None

```python
# O(1)
str(None)  # "None"
```

### Empty Collections

```python
# O(1) - quick
str([])    # "[]"
str({})    # "{}"
str(())    # "()"
str("")    # ""
```

### Large Collections

```python
# O(n) - but can be very slow
huge_list = list(range(100000))
big_str = str(huge_list)  # O(100000) - creates huge string!

# Better approach for large data
print(f"List with {len(huge_list)} items")
```

### Circular References

```python
# O(n) - detected and handled gracefully
lst = [1, 2, 3]
lst.append(lst)

str(lst)  # "[1, 2, 3, [...]]" - shows cycle
```

## Special Methods

### No Encoding

```python
# str() returns unicode string (Python 3)
s = str("hello")  # Unicode string
s = str("café")   # Unicode string with accents

# Not bytes - use encode() for that
b = "hello".encode("utf-8")  # bytes object
```

### vs bytes()

```python
# str() - text
text = str("hello")  # "hello"

# bytes() - binary data
binary = bytes("hello", "utf-8")  # b"hello"

# Converting back
text = str(binary, "utf-8")  # Requires encoding
# or
text = binary.decode("utf-8")  # More explicit
```

## Best Practices

✅ **Do**:

- Define `__str__()` for custom classes (user-friendly)
- Use `str()` for readable output
- Use f-strings for clarity: `f"{value}"`
- Cache str conversions if used multiple times

❌ **Avoid**:

- Using `str()` for non-string types unnecessarily
- Slow `__str__()` implementations
- String concatenation in loops (use join)
- Confusing `str()` with `repr()`

## Related Functions

- **[repr()](repr.md)** - Official representation
- **[format()](format.md)** - Format strings
- **[ascii()](ascii.md)** - ASCII-safe representation
- **[bytes()](bytes_func.md)** - Convert to bytes

## Version Notes

- **Python 2.x**: `str()` returns bytes, `unicode()` returns text
- **Python 3.x**: `str()` returns unicode strings
- **All versions**: Uses `__str__()` method if defined
