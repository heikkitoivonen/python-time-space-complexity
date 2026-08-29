# array Module Complexity

The `array` module provides an efficient array type for storing homogeneous data with lower memory overhead than lists.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `array.array()` | O(n) | O(n) | Create array |
| `append()` | O(1) amortized | O(1) | O(n) worst case when resizing |
| `extend()` | O(k) | O(k) | Add multiple |
| Indexing | O(1) | O(1) | Access by index |
| Search | O(n) | O(1) | Linear search |
| Insert | O(n) | O(1) | Insert at position |
| Remove | O(n) | O(1) | Remove element |
| `typecodes` | O(1) | O(1) | String of supported type codes |

## Basic Usage

```python
import array

# Create array - O(n)
arr = array.array('i', [1, 2, 3, 4, 5])  # O(5) - integer type

# Type codes: 'i' = int, 'f' = float, 'd' = double, 'b' = byte
arr_float = array.array('f', [1.0, 2.5, 3.14])  # O(3)

# Append - O(1) amortized
arr.append(6)  # O(1)

# Access - O(1)
value = arr[0]  # O(1)

# Length - O(1)
length = len(arr)  # O(1)
```

## Array Operations

### Creation Methods

```python
import array

# From iterable - O(n)
arr = array.array('i', range(10))  # O(10)

# From bytes - O(n)
arr = array.array('i')
arr.frombytes(b'\x01\x00\x00\x00\x02\x00\x00\x00')  # O(n)

# From list - O(n)
arr.fromlist([1, 2, 3])  # O(3)
```

### Modification

```python
import array

arr = array.array('i', [1, 2, 3, 4, 5])

# Insert - O(n)
arr.insert(2, 99)  # O(5) - shift elements

# Remove - O(n)
arr.remove(99)  # O(5) - shift elements

# Pop - O(1) at end, O(n) elsewhere
arr.pop()  # O(1) - remove last
arr.pop(0)  # O(5) - remove first, shift rest
```

### Conversion

```python
import array

arr = array.array('i', [1, 2, 3])

# To list - O(n)
lst = arr.tolist()  # O(3)

# To bytes - O(n)
bytes_data = arr.tobytes()  # O(3)
```

## Performance Comparison

```python
import array
import sys

# An array's header is larger - 80 bytes against a list's 56 - so for a
# handful of elements the array is the bigger object. The saving arrives at
# a few dozen, and grows from there.
lst = [1, 2, 3, 4, 5]
arr = array.array('i', [1, 2, 3, 4, 5])
print(sys.getsizeof(lst), sys.getsizeof(arr))  # too close to call at n=5

# List of references (8 bytes each) vs packed elements (4 for 'i', 8 for 'd')
lst = list(range(10_000))
arr = array.array('i', range(10_000))
print(sys.getsizeof(lst), sys.getsizeof(arr))  # 80056 vs 40420 bytes

# But that 2x understates it. getsizeof() counts the list's pointers, not
# the int objects they point at - 28 bytes each, and only small ints are
# shared. Counting those, the list holds 360056 bytes against 40420.
deep = sys.getsizeof(lst) + sum(sys.getsizeof(x) for x in lst)
print(deep // sys.getsizeof(arr))  # 8x, not 2x
```

## Type Codes

```python
import array

# Every constructor below is O(n) in the number of items; the type code
# fixes the bytes per item, which is what array buys over list
# Available type codes
# 'b' = signed byte (1 byte)
arr_b = array.array('b', [-128, 0, 127])

# 'B' = unsigned byte (1 byte)
arr_B = array.array('B', [0, 128, 255])

# 'i' = signed integer (2-4 bytes)
arr_i = array.array('i', [-1000, 0, 1000])

# 'I' = unsigned integer (2-4 bytes)
arr_I = array.array('I', [0, 1000, 2000])

# 'f' = float (4 bytes)
arr_f = array.array('f', [1.0, 2.5, 3.14])

# 'd' = double (8 bytes)
arr_d = array.array('d', [1.0, 2.5, 3.14])
```

## When to Use Array

### Good For:
- Large collections of numeric data
- Memory-constrained environments
- Binary file I/O with numeric data
- Raw byte operations

### Not Good For:
- Mixed types (use list or tuple)
- Complex objects (use list)
- Frequent insertions (use list)
- Type flexibility needed

## Version Notes

- **Python 2.x**: array available
- **Python 3.x**: Same functionality
- **All versions**: O(n) memory savings vs lists

## Related Modules

- **[list](../builtins/list.md)** - Flexible container
- **[struct](struct.md)** - Binary data packing

## Best Practices

✅ **Do**:

- Use for numeric data collections
- Use for memory efficiency
- Convert to list for type mixing

❌ **Avoid**:

- Mixed types in array
- Frequent insertions/deletions
- When flexibility needed
