# print() Function Complexity

The `print()` function outputs text to standard output.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Print single argument | O(n)* | O(n) | n = string length; * I/O dominates |
| Print multiple arguments | O(n + m) | O(n + m) | n = total string length |
| Print with formatting | O(n) | O(n) | String conversion cost |
| Print to file | O(n) | O(n) | Same as stdout |

## Basic Usage

### Single Argument

```python
# O(n) - where n is string length
print("hello")              # Output: hello
print(42)                   # Output: 42
print([1, 2, 3])           # Output: [1, 2, 3]
```

### Multiple Arguments

```python
# O(n + m) - total string length of all arguments
print("Hello", "World")     # Output: Hello World
print("x =", 42)           # Output: x = 42
print(1, 2, 3, 4, 5)       # Output: 1 2 3 4 5
```

### Custom Separators and Terminators

```python
# O(n) - separator/end parameters affect output only
print("a", "b", "c", sep=", ")  # Output: a, b, c
print("no newline", end="")     # No trailing newline
print("x", "y", sep="-", end="!\n")  # Output: x-y!
```

## Complexity Details

### String Conversion

Each argument must be converted to string (if not already):

```python
# O(1) - string argument, just write
print("hello")

# O(1) - integer to string conversion
print(42)

# O(n) - list conversion, where n = number of elements
items = [1, 2, 3, 4, 5]
print(items)  # O(n) - builds string representation

# O(n) - dictionary conversion
data = {"a": 1, "b": 2}
print(data)   # O(n) - string representation
```

### Multiple Arguments

```python
# O(n + m) - time to convert and write both
print("Count:", 42)  # O(2) approximately

# O(k * n) - k arguments, each of size ~n
args = [str(i) for i in range(100)]
print(*args)  # O(100) - 100 conversions + writes
```

## Performance Patterns

### Repeated Printing

```python
# O(n * k) - n = string length, k = iterations
for i in range(1000):
    print(f"Iteration {i}")  # O(1000) total

# Accumulate then print once - better if massive
lines = []
for i in range(1000):
    lines.append(f"Iteration {i}")
print("\n".join(lines))  # O(n) single write
```

### Writing Many Values

```python
# O(n) - each item is O(1) conversion + write
values = list(range(10))
for val in values:
    print(val)  # O(10) total - constant per item

# More efficient - collect then print
print(*values)  # O(n) - single operation
```

### Formatted Output

```python
# O(n) - string formatting cost
print(f"Value: {42}")      # O(1) - simple format
print(f"Value: {large_list}")  # O(n) - depends on list size

# String format method
print("Value: {}".format(value))  # O(n) - conversion cost
print("Value: %s" % value)        # O(n) - conversion cost
```

## I/O Considerations

### Output Buffering

```python
# I/O overhead dominates over string computation
import sys

# Unbuffered output
for i in range(1000):
    print(i, flush=True)  # Forces write immediately
    # Slower due to I/O flushing

# Buffered output (default)
for i in range(1000):
    print(i)  # Buffered, faster overall
```

### Writing to Files

```python
# O(n) - same complexity as stdout
output_file = open("output.txt", "w")

# Time = string conversion + I/O write time
print("Line 1", file=output_file)
print("Line 2", file=output_file)

output_file.close()

# Batch writing - more efficient
with open("output.txt", "w") as f:
    for i in range(1000):
        print(f"Line {i}", file=f)  # O(n) total
```

## Comparison with Alternatives

### String Concatenation vs Print

```python
# Inefficient - builds intermediate strings
output = ""
for i in range(1000):
    output += f"Item {i}\n"  # O(n^2) - string concatenation
print(output)

# Better - collect then print
items = []
for i in range(1000):
    items.append(f"Item {i}")
print("\n".join(items))  # O(n) - single join + print

# Best - print directly
for i in range(1000):
    print(f"Item {i}")  # O(n) - direct output
```

### sys.stdout.write() vs print()

```python
import sys

# print() adds overhead for argument handling
print("hello world")  # Slightly slower

# Direct write - O(n) same complexity, less overhead
sys.stdout.write("hello world\n")  # O(n), minimal overhead

# For many small writes, print() convenience vs write() speed
# Difference is negligible in practice
```

## Edge Cases

### Empty Print

```python
# O(1) - just writes newline
print()  # Output: \n
```

### None and Special Values

```python
# O(1) - conversion to string "None"
print(None)  # Output: None

# O(1) - boolean conversion
print(True)  # Output: True
print(False)  # Output: False
```

### Circular References

```python
# O(n) - detects circular references gracefully
lst = []
lst.append(lst)
print(lst)  # Output: [[...]] - handles circular refs
```

## Best Practices

✅ **Do**:

- Use `print()` for simple output (it's designed for this)
- Collect strings then print once for massive output
- Use `end=""` or `sep=""` to control formatting
- Print to file with `file=` parameter

❌ **Avoid**:

- Building large strings with `+=` before printing (O(n²))
- Calling `flush=True` unless you need immediate output
- Printing inside tight loops without buffering considerations
- Complex string formatting when simple concatenation suffices

## Related Functions

- **[str()](str.md)** - Convert object to string
- **[format()](format.md)** - Format strings
- **[input()](input.md)** - Read from input
- **[open()](open.md)** - File I/O operations

## Version Notes

- **Python 2.x**: `print` is a statement, not a function
- **Python 3.x**: `print()` is a function with keyword arguments
- **All versions**: I/O complexity dominated by actual write time, not computation
