# Timeit Module Complexity

The `timeit` module provides utilities for measuring execution time of Python code snippets, useful for performance profiling and optimization.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `timeit(stmt, setup)` | O(n*m) | O(1) | Time statement execution |
| `Timer(stmt, setup)` | O(1) | O(1) | Create timer |
| `Timer.timeit(n)` | O(n*m) | O(1) | Time n repetitions |
| `Timer.repeat(n, r)` | O(r*n*m) | O(r) | Repeat timing |

## Basic Timing

### timeit() Function

#### Time Complexity: O(n*m)

Where n = number of repetitions, m = statement complexity.

```python
from timeit import timeit

# Time a simple statement: O(n*m)
time = timeit('x = 1', number=1000000)  # O(1000000)
print(f"Time: {time:.6f} seconds")

# Time with setup: O(m) setup + O(n*m) execution
time = timeit(
    stmt='x.append(1)',
    setup='x = []',
    number=100000
)  # O(setup) + O(100000 * append)

# Compare two approaches: O(n1*m1 + n2*m2)
time1 = timeit('x = [i for i in range(10)]', number=1000)
time2 = timeit('x = list(range(10))', number=1000)
print(f"List comprehension: {time1:.6f}")
print(f"list(): {time2:.6f}")
```

#### Space Complexity: O(1)

```python
from timeit import timeit

# Only stores timing result
time = timeit('x = 1', number=1000000)  # O(1) space
```

## Timer Class

### Creating and Using Timers

#### Time Complexity: O(1) init, O(n*m) timeit

```python
from timeit import Timer

# Create timer: O(1)
timer = Timer(
    stmt='sum(range(10))',
    setup='pass'
)  # O(1)

# Time once: O(n*m)
time = timer.timeit(number=1000000)  # O(1000000)

# Time multiple: O(r*n*m)
times = timer.repeat(repeat=3, number=1000000)
# [time1, time2, time3] - O(3*1000000)

# Get minimum (best run)
best = min(times)
```

#### Space Complexity: O(1)

```python
from timeit import Timer

timer = Timer('x = 1')  # O(1)
time = timer.timeit(1000000)  # O(1) space
```

## Common Patterns

### Compare Performance

```python
from timeit import timeit

def compare_methods():
    """Compare two implementations: O(n)"""
    setup = 'x = list(range(100))'
    
    # Method 1: O(n1)
    time1 = timeit(
        'sum(x)',
        setup=setup,
        number=100000
    )
    
    # Method 2: O(n2)
    time2 = timeit(
        'x.__class__.__bases__[0].__init__(x)',
        setup=setup,
        number=100000
    )
    
    print(f"Method 1: {time1:.6f}")
    print(f"Method 2: {time2:.6f}")
    
    return time1 < time2

compare_methods()  # O(total) total time
```

### Find Optimal Parameters

```python
from timeit import Timer

def find_optimal_approach():
    """Test different implementations: O(k*n)"""
    implementations = {
        'append': 'x.append(1)',
        'extend': 'x.extend([1])',
        'list': 'x = [1] + x',
    }
    
    results = {}
    
    for name, stmt in implementations.items():  # O(k)
        timer = Timer(stmt, setup='x = []')
        time = timer.timeit(number=10000)  # O(n)
        results[name] = time
    
    best = min(results, key=results.get)
    print(f"Best: {best}")
    return results
```

### Profile Complex Function

```python
from timeit import Timer

def profile_function():
    """Time a function: O(n*m)"""
    setup = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''
    
    timer = Timer('fibonacci(10)', setup=setup)
    time = timer.timeit(number=10000)  # O(10000 * fib_time)
    print(f"Fibonacci(10) x 10000: {time:.6f} seconds")
```

### Benchmark with Multiple Runs

```python
from timeit import Timer
import statistics

def benchmark(stmt, setup='pass', number=1000, repeat=5):
    """Run benchmark with statistics: O(repeat*number*m)"""
    timer = Timer(stmt, setup=setup)
    
    times = timer.repeat(repeat=repeat, number=number)  # O(repeat*number*m)
    
    return {
        'mean': statistics.mean(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times),
        'times': times,
    }

# Usage
result = benchmark('x = [i*2 for i in range(100)]', number=10000)
print(f"Mean: {result['mean']:.6f}s")
print(f"Stdev: {result['stdev']:.6f}s")
```

## Command Line Usage

```python
# Command line timing
# python -m timeit 'x = 1'
# Time repeated execution automatically

# With setup
# python -m timeit -s 'x = []' 'x.append(1)'

# Specific number of repetitions
# python -m timeit -n 1000 'x = list(range(10))'

# Multiple repetitions
# python -m timeit -r 5 'x = 1'
```

## Performance Tips

### Best Practices

```python
from timeit import timeit, Timer

# Good: Use sufficient repetitions
time = timeit('x = 1', number=1000000)  # Enough data
# O(1000000) but gives stable result

# Good: Multiple runs for variability
timer = Timer('x = 1')
times = timer.repeat(repeat=3)
best = min(times)  # Use best run

# Avoid: Too few repetitions
time = timeit('x = 1', number=10)  # Too little data
# May be affected by system noise

# Good: Disable optimization checks
import sys
old_check = sys.flags.optimize
# Time with/without optimization
```

### Avoiding Overhead

```python
from timeit import timeit

# Good: Time just the operation
time = timeit('x.append(1)', setup='x = []', number=1000000)

# Avoid: Including setup in timed code
time = timeit('x = []; x.append(1)', number=1000000)
# Setup overhead counted!

# Good: Minimal setup
setup = 'x = []'  # Just what's needed

# Avoid: Complex setup
setup = 'import numpy as np; x = np.array([...])'  # Counted!
```

## Comparison with cProfile

```python
from timeit import timeit
import cProfile

# timeit (simple, statements)
timeit('x = 1', number=1000000)  # Quick measurement

# cProfile (detailed, functions)
cProfile.run('function_call()')  # Full profiling

# Use timeit for quick micro-benchmarks
# Use cProfile for detailed function analysis
```

## Version Notes

- **Python 3.x**: Full timeit support
- **Python 3.5+**: Command-line options improvements

## Related Documentation

- [Profile Module](profile.md) - Profiling
- [Sys Module](sys.md) - System parameters
