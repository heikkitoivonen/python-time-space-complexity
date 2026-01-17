# CPython Implementation Details

CPython is the reference implementation of Python, written primarily in C. It's the most widely used Python implementation.

## Optimization Techniques

### String Interning

```python
# Small strings are cached
s1 = "hello"
s2 = "hello"
print(s1 is s2)  # True - same object

# Large strings are not interned
s3 = "x" * 1000
s4 = "x" * 1000
print(s3 is s4)  # False - different objects
```

### Integer Caching

```python
# Small integers cached (-5 to 256)
a = 256
b = 256
print(a is b)  # True

c = 257
d = 257
print(c is d)  # False - different objects created
```

### List Pre-allocation

Lists use dynamic arrays with growth factor ~1.125x:

```python
# When list grows beyond capacity, new capacity = (n * 9) // 8 + 6
# This reduces reallocation frequency while managing memory
```

### Dict Optimization (Python 3.6+)

```python
# Compact dict representation
# Keys stored in insertion order
# Reduced memory footprint vs Python 3.5

d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
# Order guaranteed: a, b, c
```

## Memory Management

### Reference Counting

Every object has a reference count:

```python
import sys

a = []
print(sys.getrefcount(a))  # 2 (one for 'a', one for getrefcount parameter)

b = a
print(sys.getrefcount(a))  # 3 (now 'a' and 'b')

del b
print(sys.getrefcount(a))  # 2 (back to 2)
```

### Generational Garbage Collection

```python
import gc

# Automatic collection of circular references
# Objects tracked in 3 generations by age
# Newer objects collected less frequently

# Disable automatic collection for testing
gc.disable()

# Force collection
gc.collect()  # O(n) where n = tracked objects
```

## Specific Complexity Notes

### List Operations

| Operation | CPython Notes |
|-----------|---|
| `append()` | O(1) amortized with growth factor ~1.125x |
| `insert(0)` | O(n) - no special optimization |
| `pop()` | O(1) |
| `pop(0)` | O(n) |
| `sort()` | O(n log n) using Timsort |

### Dict Operations

| Operation | CPython Notes |
|-----------|---|
| `d[key]` | O(1) avg, O(n) worst (hash collisions) |
| Hash randomization | Prevents intentional DoS attacks |
| `del` | O(1) leaves tombstones in hash table |

### String Operations

| Operation | CPython Notes |
|-----------|---|
| `in` (substring) | O(n*m) worst, but highly optimized |
| `split()` | O(n) with specialized fast path |
| `replace()` | O(n) with careful copying |

## Performance Features

### Inline Caching

CPython 3.11+ uses inline caching for attributes and method calls:

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
# First access: cache miss, lookup in dict
print(p.x)

# Repeated accesses: uses inline cache (much faster)
for _ in range(1000000):
    print(p.x)  # Cached after first access
```

### Adaptive Specialization (3.11+)

Automatically specializes bytecode for observed types:

```python
# CPython 3.11+: Specializes for int operations
def add_numbers(a, b):
    return a + b

# First calls: generic
# After ~100 calls with ints: specialized to int operations
# Result: faster arithmetic

for i in range(10000):
    result = add_numbers(i, i + 1)
```

## Versions and Optimizations

| Version | Major Optimizations |
|---|---|
| 3.8 | Assignment expressions (walrus) |
| 3.9 | Better dict unpacking, new parser |
| 3.10 | Match statements, structural pattern matching |
| 3.11 | Inline caching, 10-60% speedup |
| 3.12 | Adaptive specialization improvements |

## Memory Usage

### Object Overhead

Every Python object has overhead:

```python
import sys

# Object size includes:
# - Reference count (8 bytes)
# - Type pointer (8 bytes)
# - Additional type-specific data

print(sys.getsizeof([]))  # ~56 bytes for empty list
print(sys.getsizeof({}))  # ~240 bytes for empty dict (larger due to hash table)
print(sys.getsizeof(set()))  # ~216 bytes for empty set
```

### String Interning Impact

```python
import sys

# Interned strings: shared memory
s1 = "hello"
s2 = "hello"
print(id(s1) == id(s2))  # True - same object

# Saves memory for repeated small strings
# But don't rely on this for correctness!
```

## Known Limitations

!!! warning "GIL - Global Interpreter Lock"
    CPython uses GIL which prevents true parallel execution of Python code in threads.
    
    - Threads excellent for I/O-bound work
    - Processes needed for CPU-bound parallelism
    - Use `multiprocessing` module for parallelism

!!! warning "Performance Scaling"
    CPython interpreter has overhead that limits single-threaded performance.
    
    - For CPU-heavy work: PyPy may be faster
    - For I/O work: CPython fine, use async or threads

## Comparison with Other Implementations

| Feature | CPython | PyPy | Jython | IronPython |
|---|---|---|---|---|
| Startup time | Good | Higher | Higher | Similar |
| Long-run perf | Good | Excellent | Good | Good |
| C extensions | Yes | Partial | No | No |
| Standard libs | Complete | Complete | Complete | Complete |

## Related Documentation

- [PyPy Implementation](pypy.md)
- [Built-in Types](../builtins/index.md)
- [Standard Library](../stdlib/index.md)
