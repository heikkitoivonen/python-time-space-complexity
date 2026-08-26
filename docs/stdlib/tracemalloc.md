# tracemalloc Module

The `tracemalloc` module traces memory allocations in Python, tracking where memory is being allocated to help identify memory leaks and optimize memory usage.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `start()` | O(1) | O(1) | Enables tracing; subsequent allocations are tracked |
| `take_snapshot()` | O(n) | O(n) | n = active allocations |
| `get_traced_memory()` | O(1) | O(1) | Current snapshot |
| Snapshot comparison | O(n log n) | O(n) | n = allocations |

## Basic Usage

### Starting Memory Tracing

```python
import tracemalloc

# Start tracing - O(1)
tracemalloc.start()

# Memory-intensive operation
data = [i ** 2 for i in range(1000000)]

# Get current memory usage - O(1)
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.1f} MB")
print(f"Peak: {peak / 1024 / 1024:.1f} MB")

tracemalloc.stop()
```

## Taking Snapshots

### Memory Snapshots

```python
import tracemalloc

tracemalloc.start()

# Snapshot 1 - O(n)
snapshot1 = tracemalloc.take_snapshot()

# Allocate memory
big_list = [0] * (10 ** 6)

# Snapshot 2 - O(n)
snapshot2 = tracemalloc.take_snapshot()

# Compare snapshots - O(n log n)
top_stats = snapshot2.compare_to(snapshot1, 'lineno')

# Display top memory increases
for stat in top_stats[:3]:
    print(stat)

tracemalloc.stop()
```

## Memory Analysis

### Top Allocations

```python
import tracemalloc

tracemalloc.start()

# Create data structures
dicts = [{'key': i} for i in range(100000)]
lists = [[0] * 1000 for _ in range(1000)]

# Take snapshot - O(n)
snapshot = tracemalloc.take_snapshot()

# Top allocations by size - O(n log n)
top_stats = snapshot.statistics('lineno')

# Display top 10 - O(1) per stat
for stat in top_stats[:10]:
    print(f"{stat.size / 1024 / 1024:.1f} MB - {stat.filename}:{stat.lineno}")

tracemalloc.stop()
```

### Memory by File

```python
import tracemalloc

tracemalloc.start()

# Allocate memory
data = {'key': [0] * 100000}

# Statistics by filename - O(n)
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('filename')

# Show largest files
for stat in top_stats[:5]:
    print(f"{stat.size / 1024 / 1024:.1f} MB - {stat.filename}")

tracemalloc.stop()
```

## Finding Memory Leaks

### Memory Growth Tracking

```python
import tracemalloc
import time

tracemalloc.start()

snapshots = []

for iteration in range(5):
    # Do some work that might leak
    data = [i ** 2 for i in range(1000000)]
    
    # Take snapshot - O(n)
    snapshot = tracemalloc.take_snapshot()
    snapshots.append((iteration, snapshot))
    
    current, peak = tracemalloc.get_traced_memory()
    print(f"Iteration {iteration}: {current / 1024 / 1024:.1f} MB")

# Compare first and last
top_stats = snapshots[-1][1].compare_to(snapshots[0][1], 'lineno')

# Show differences
for stat in top_stats[:10]:
    print(stat)

tracemalloc.stop()
```

### Detailed Leak Detection

```python
import tracemalloc

class MemoryLeakDetector:
    def __init__(self):
        tracemalloc.start()
        self.baseline = None
    
    def set_baseline(self):
        # O(n)
        self.baseline = tracemalloc.take_snapshot()
    
    def report_growth(self, top=10):
        # O(n log n)
        if self.baseline is None:
            raise ValueError("No baseline set")
        
        current = tracemalloc.take_snapshot()
        top_stats = current.compare_to(self.baseline, 'lineno')
        
        print(f"Top {top} memory growth:")
        for stat in top_stats[:top]:
            print(f"  {stat.size_diff / 1024:.1f} KB - {stat.filename}:{stat.lineno}")
    
    def stop(self):
        tracemalloc.stop()

# Usage
detector = MemoryLeakDetector()
detector.set_baseline()

# Do operations
data = [list(range(1000)) for _ in range(10000)]

detector.report_growth()
detector.stop()
```

## Filtering Traces

### Include/Exclude Modules

```python
import tracemalloc

# Include only user code - O(1)
tracemalloc.start()
tracemalloc.reset_peak()

# Filter to specific modules - O(n)
snapshot = tracemalloc.take_snapshot()

# Keep only main module
filters = (tracemalloc.Filter(False, '<frozen *'),
           tracemalloc.Filter(False, '<unknown>'))
filtered = snapshot.filter_traces(filters)

for stat in filtered.statistics('filename')[:5]:
    print(stat)

tracemalloc.stop()
```

## Context Manager Pattern

### Automatic Cleanup

```python
import tracemalloc

def memory_tracker(func):
    """Decorator to track memory usage - O(n)"""
    def wrapper(*args, **kwargs):
        tracemalloc.start()
        
        # Get baseline
        current, _ = tracemalloc.get_traced_memory()
        
        # Run function
        result = func(*args, **kwargs)
        
        # Get final memory
        final, peak = tracemalloc.get_traced_memory()
        
        print(f"Memory used: {(final - current) / 1024 / 1024:.1f} MB")
        print(f"Peak: {peak / 1024 / 1024:.1f} MB")
        
        tracemalloc.stop()
        return result
    
    return wrapper

@memory_tracker
def process_data():
    data = [i ** 2 for i in range(1000000)]
    return sum(data)

result = process_data()
```

## Best Practices

```python
import tracemalloc

# ✅ DO: Start/stop in context
tracemalloc.start()
try:
    # Do work
    pass
finally:
    tracemalloc.stop()

# ✅ DO: Use snapshots for comparison
snap1 = tracemalloc.take_snapshot()
# operations
snap2 = tracemalloc.take_snapshot()
differences = snap2.compare_to(snap1, 'lineno')

# ✅ DO: Check peak memory
current, peak = tracemalloc.get_traced_memory()

# ❌ DON'T: Leave tracemalloc running indefinitely
# It has overhead - enable only when needed
```

## Related Modules

- [gc Module](gc.md) - Garbage collection control
- [sys Module](sys.md) - Memory information
- [resource Module](resource.md) - Resource limits
- [cProfile Module](cprofile.md) - CPU profiling
