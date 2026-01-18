# PyPy Implementation Details

PyPy is an alternative Python implementation written in Python with a JIT (Just-In-Time) compiler. It aims for high performance while maintaining compatibility with CPython.

## JIT Compilation

### Warm-up Period

```python
# PyPy behavior: Initial runs slower (compilation), then faster

# Function definition: not compiled yet
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# First call: slow (interpreter)
result = fibonacci(5)

# Calls 2-100: Profiling happens
for i in range(100):
    result = fibonacci(5)

# Call 101+: JIT compiled and fast
# ~100-1000x faster than CPython for hot loops!
```

### Tracing JIT

PyPy uses trace-based JIT:

```python
# Loop gets compiled to machine code
total = 0
for i in range(1000000):  # This loop gets JIT compiled!
    total += i

print(total)  # Executes in compiled machine code
```

## Performance Characteristics

### Loop Optimization

Tight loops benefit most from JIT:

```python
# PyPy: ~100x faster than CPython
# CPython: O(n) interpreted
# PyPy: O(n) compiled to machine code

def sum_range(n):
    total = 0
    for i in range(n):
        total += i
    return total

# PyPy: 100-1000x faster after warm-up
# CPython: Baseline interpreter speed
```

### Object Allocation

```python
# PyPy optimizes common patterns
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# Creates millions of points
points = [Point(i, i+1) for i in range(1000000)]

# PyPy: Optimizes object allocation in comprehension
# CPython: Normal allocation overhead
```

## Complexity Comparison

### Standard Operations

| Operation | CPython | PyPy | Notes |
|---|---|---|---|
| `list.append()` | O(1) amortized | O(1) amortized | Same algorithm |
| `dict[key]` | O(1) avg, O(n) worst | O(1) avg, O(n) worst | Same hash table |
| `set in` | O(1) avg, O(n) worst | O(1) avg, O(n) worst | Same hash set |
| Loop (tight) | O(n) | O(n)* | PyPy much faster |

*Amortized or constant with much lower constant

## When PyPy Excels

### CPU-Bound Code

```python
# PyPy is 10-100x faster for CPU-bound tasks
# After warm-up period (~100ms-1s)

import time

def heavy_computation():
    total = 0
    for i in range(100000):
        for j in range(100):
            total += i * j
    return total

# CPython: ~seconds
# PyPy: ~milliseconds
```

### Long-Running Servers

PyPy excellent for servers:

- Initial startup slightly slower
- Pays off in hours/days of running
- Can handle 10-50x more requests

### Scientific Computing

For pure Python algorithms without NumPy:

```python
# Pure Python algorithm (no NumPy)
# PyPy: 10-100x faster
# CPython: Slower

def matrix_multiply(a, b):
    size = len(a)
    c = [[0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            for k in range(size):
                c[i][j] += a[i][k] * b[k][j]
    return c
```

## When CPython is Better

### Startup Performance

```python
# Quick scripts: CPython starts faster
# PyPy: 200-500ms startup overhead
# CPython: 50-100ms startup

# For quick scripts, CPython preferred
```

### C Extension Compatibility

```python
# NumPy, pandas, etc. use C extensions
import numpy as np

# NumPy: Requires CPython (no PyPy support)
# PyPy: Limited C extension support
```

### Mixed Workloads

```python
# Quick initialization + short run
# Neither JIT nor startup offset the cost

# CPython better for:
# - Scripts that run once and exit
# - Mixed I/O and CPU work
# - One-off data processing
```

## Memory Behavior

### Allocation Strategy

PyPy uses different GC strategy:

```python
# PyPy: Generational GC (no reference counting overhead)
# CPython: Reference counting + GC

# Creating many temporary objects:
# PyPy may be faster (no ref count updates)
# CPython may have more pause time (GC collection)

for i in range(1000000):
    temp_list = [i]  # Allocate and discard
    # PyPy: GC handles efficiently
    # CPython: Reference count decremented
```

## Practical Recommendations

### Use PyPy When:
- ✅ CPU-bound code with loops
- ✅ Long-running processes (servers)
- ✅ No dependency on C extensions
- ✅ Performance critical

### Use CPython When:
- ✅ Needs C extension libraries (NumPy, pandas, etc.)
- ✅ Quick startup important
- ✅ Third-party packages have poor PyPy support
- ✅ Standard approach expected in team

## Migration from CPython to PyPy

```bash
# Usually just works!
# PyPy aims for 99% compatibility

# Check compatibility
pip install pypy3

# Run code
pypy3 your_script.py

# Some packages may not support PyPy:
pip install package-name  # May fail on PyPy
```

## Version Information

| PyPy Version | Python Version | Performance |
|---|---|---|
| PyPy3.9 | Python 3.9 | Good |
| PyPy3.10 | Python 3.10 | Excellent |
| PyPy3.11 | Python 3.11 | Excellent+ |

Latest versions provide best performance.

## Benchmarking

```python
import time

# Proper PyPy benchmark
def benchmark(func, *args):
    # Warm-up: allow JIT compilation
    for _ in range(100):
        func(*args)
    
    # Timed run
    start = time.time()
    for _ in range(10000):
        func(*args)
    elapsed = time.time() - start
    
    print(f"Time: {elapsed:.3f}s")

# Without warm-up, numbers misleading!
```

## Related Documentation

- [CPython Implementation](cpython.md)
- [Jython Implementation](jython.md)
- [Performance Tuning](../versions/index.md)
