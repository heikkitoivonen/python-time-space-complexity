# graphlib Module Complexity

The `graphlib` module provides a topological sort implementation for resolving dependencies between tasks, useful for build systems, task scheduling, and dependency resolution.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TopologicalSorter()` init | O(1) | O(1) | Create sorter |
| `add(node, *predecessors)` | O(k) | O(k) | Add node with k predecessors |
| `prepare()` | O(v + e) | O(v) | Prepare sort, v = vertices, e = edges. Up to 3.13 it may be called only once; 3.14 allows repeated calls until the first `get_ready()`. `static_order()` calls it for you on every version |
| `get_ready()` | O(k) | O(k) | Returns all ready nodes as a tuple, k = ready count. O(1) amortized per node over the whole sort |
| `done(node)` | O(d) | O(1) | Mark done, d = node degree |
| `static_order()` | O(v + e) | O(v + e) | Complete topological sort |
| `CycleError` | O(1) | O(1) | Exception raised on cycles |

## Basic Topological Sort

### Simple Dependency Order

```python
from graphlib import TopologicalSorter

# Create sorter - O(1)
ts = TopologicalSorter()

# Add dependencies - O(k) for k predecessors
# format: add(node, *predecessors)
ts.add('lunch', 'cook')    # lunch depends on cook
ts.add('cook', 'shop')     # cook depends on shop
ts.add('shop')              # shop has no dependencies

# Get nodes in dependency order - O(v + e)
# static_order() calls prepare() itself. Do not call prepare() first: up to
# 3.13 that raises ValueError, and 3.14 only tolerates it
for task in ts.static_order():
    print(task)

# Output:
# shop
# cook
# lunch
```

## Dynamic Topological Sort

### Process While Sorting

```python
from graphlib import TopologicalSorter

# Create sorter - O(1)
ts = TopologicalSorter()

# Add tasks and dependencies
ts.add('compile', 'preprocess')
ts.add('preprocess', 'download')
ts.add('download')
ts.add('test', 'compile')
ts.add('package', 'test')

# Prepare - O(v + e)
ts.prepare()

# Process nodes dynamically - O(v + e) total
processed = []
while ts.is_active():
    # Get all ready nodes - O(k) for the k returned, O(1) amortized each
    ready = ts.get_ready()  # Returns tuple of ready nodes
    
    if not ready:
        break
    
    # Process each ready node
    for node in ready:
        print(f"Processing: {node}")
        processed.append(node)
        # Mark as done - O(d) for degree d
        ts.done(node)

print(f"Processed: {processed}")
```

## Graph Structure

### Complex Dependencies

```python
from graphlib import TopologicalSorter

# Build dependency graph - O(v + e)
ts = TopologicalSorter()

# Task graph with multiple dependencies
ts.add('main.o', 'main.c', 'defs.h')
ts.add('util.o', 'util.c', 'util.h', 'defs.h')
ts.add('prog', 'main.o', 'util.o')

# Add files with no dependencies
for file in ['main.c', 'util.c', 'util.h', 'defs.h']:
    ts.add(file)

# Get execution order - O(v + e); static_order() prepares the sorter itself
order = list(ts.static_order())
print(order)

# Output: source files first, then object files, then executable
```

## Static vs Dynamic Sort

### Static Order

```python
from graphlib import TopologicalSorter

# Static sort - simpler, complete result
ts = TopologicalSorter()

ts.add('D', 'B', 'C')
ts.add('B', 'A')
ts.add('C', 'A')
ts.add('A')

# Get complete order - O(v + e) returns list
order = ts.static_order()
print(list(order))  # ['A', 'B', 'C', 'D'] or valid permutation
```

### Dynamic Processing

```python
from graphlib import TopologicalSorter

# Dynamic sort - process nodes as they become available
ts = TopologicalSorter()

ts.add('compile', 'preprocess')
ts.add('preprocess', 'download')
ts.add('download')
ts.add('test', 'compile')

ts.prepare()

# Process dynamically - each get_ready() is O(k) in what it returns
while ts.is_active():
    ready = ts.get_ready()  # Returns tuple of ready nodes
    for node in ready:
        print(f"Processing {node}")
        # Do work...
        ts.done(node)
```

## Error Detection

### Cycle Detection

```python
from graphlib import TopologicalSorter, CycleError

ts = TopologicalSorter()

# Add cyclic dependencies
ts.add('A', 'B')
ts.add('B', 'C')
ts.add('C', 'A')  # Creates cycle: A -> B -> C -> A

# Detect cycle when preparing - O(v + e)
try:
    ts.prepare()
except CycleError as e:
    print(f"Cycle detected: {e}")
    print(f"Nodes in cycle: {e.args[1]}")
```

## Common Patterns

### Build System

```python
from graphlib import CycleError, TopologicalSorter

class BuildSystem:
    """Simple build system with dependency resolution"""
    
    def __init__(self):
        # Keep the graph, not a sorter: a sorter cannot be traversed twice,
        # so a stored one could serve only a single caller. (Up to 3.13 even
        # a second prepare() raises; 3.14 allows that but still not a second
        # traversal.)
        self.targets = {}
    
    # Add build target with dependencies
    def add_target(self, target, *dependencies):
        """Register build target - O(k)"""
        self.targets[target] = dependencies
    
    def _sorter(self):
        """Build a fresh sorter from the graph - O(v + e)"""
        sorter = TopologicalSorter()
        for target, dependencies in self.targets.items():
            sorter.add(target, *dependencies)
        return sorter
    
    # Get build order
    def get_build_order(self):
        """Get topological order - O(v + e)"""
        try:
            # static_order() prepares internally - do not call prepare() too
            return list(self._sorter().static_order())
        except CycleError:
            return None
    
    # Build targets
    def build(self):
        """Build all targets in order - O(v + e)"""
        sorter = self._sorter()
        sorter.prepare()

        built = set()
        while sorter.is_active():
            # get_ready() returns a tuple of ready nodes
            ready = sorter.get_ready()
            if not ready:
                break

            for target in ready:
                # Skip already built
                if target in built:
                    sorter.done(target)
                    continue

                print(f"Building {target}...")
                # Simulate build
                built.add(target)
                sorter.done(target)

        return built

# Usage
build = BuildSystem()
build.add_target('main.o', 'main.c', 'defs.h')
build.add_target('util.o', 'util.c', 'defs.h')
build.add_target('prog', 'main.o', 'util.o')
build.add_target('main.c')
build.add_target('util.c')
build.add_target('defs.h')

print("Build order:", build.get_build_order())
build.build()
```

### Task Scheduler

```python
from graphlib import TopologicalSorter
import time

class TaskScheduler:
    """Schedule tasks respecting dependencies"""
    
    def __init__(self):
        self.sorter = TopologicalSorter()
        self.tasks = {}
    
    # Register task with dependencies
    def add_task(self, name, func, *dependencies):
        """Register task - O(k)"""
        self.sorter.add(name, *dependencies)
        self.tasks[name] = func
    
    # Execute all tasks in order
    def execute(self):
        """Execute tasks in dependency order - O(v + e)"""
        try:
            self.sorter.prepare()
        except Exception as e:
            print(f"Dependency error: {e}")
            return False
        
        executed = {}
        start_time = time.time()
        
        while self.sorter.is_active():
            # Get all ready tasks - O(k) for the k returned
            ready = self.sorter.get_ready()
            if not ready:
                break

            for task_name in ready:
                # Execute task - O(?)
                if task_name in self.tasks:
                    print(f"Executing {task_name}...")
                    start = time.time()
                    result = self.tasks[task_name]()
                    elapsed = time.time() - start
                    executed[task_name] = (result, elapsed)
                    print(f"  Completed in {elapsed:.3f}s")

                # Mark done - O(d)
                self.sorter.done(task_name)
        
        total = time.time() - start_time
        print(f"Total execution time: {total:.3f}s")
        return executed

# Usage
scheduler = TaskScheduler()

def download():
    time.sleep(0.1)
    return "downloaded"

def process():
    time.sleep(0.1)
    return "processed"

def upload():
    time.sleep(0.1)
    return "uploaded"

scheduler.add_task('download', download)
scheduler.add_task('process', process, 'download')
scheduler.add_task('upload', upload, 'process')

results = scheduler.execute()
```

### Package Dependency Resolver

```python
from graphlib import CycleError, TopologicalSorter

class DependencyResolver:
    """Resolve package installation order"""
    
    def __init__(self):
        # The graph, not a sorter - see BuildSystem above for why.
        self.packages = {}
    
    # Add package with dependencies
    def add_package(self, name, version='latest', *dependencies):
        """Add package - O(k)"""
        self.packages[(name, version)] = dependencies
    
    # Get installation order
    def get_install_order(self):
        """Get topological order - O(v + e)"""
        sorter = TopologicalSorter()
        for package, dependencies in self.packages.items():
            sorter.add(package, *dependencies)
        try:
            # static_order() prepares internally
            return list(sorter.static_order())
        except CycleError as e:
            # Catch CycleError specifically: a bare except here would report
            # any mistake, including a misuse of the API, as a cycle
            print(f"Circular dependency: {e}")
            return None

# Usage
resolver = DependencyResolver()

# Typical dependency graph
resolver.add_package('flask', '2.0')
resolver.add_package('werkzeug', '2.0', ('flask', '2.0'))
resolver.add_package('jinja2', '3.0', ('flask', '2.0'))
resolver.add_package('itsdangerous', '2.0')
resolver.add_package('click', '8.0', ('flask', '2.0'))

order = resolver.get_install_order()
print("Install order:")
for pkg, ver in order:
    print(f"  {pkg} {ver}")
```

## Performance Characteristics

### Time Complexity
- **Initialization**: O(1)
- **Adding nodes**: O(k) for k predecessors
- **prepare()**: O(v + e) where v = vertices, e = edges
- **Complete sort**: O(v + e)
- **Dynamic iteration**: O(v + e) total for all operations

### Space Complexity
- **Graph storage**: O(v + e) for v nodes and e edges
- **Cycle tracking**: O(v + e) during prepare

### Scalability

```python
from graphlib import TopologicalSorter
import time

# Performance test
def benchmark_sort_size(num_nodes):
    ts = TopologicalSorter()
    
    # Create linear dependency chain
    for i in range(1, num_nodes):
        ts.add(i, i-1)
    ts.add(0)
    
    start = time.time()
    list(ts.static_order())  # prepares internally
    elapsed = time.time() - start
    
    return elapsed

# Test various sizes
for size in [100, 1000, 10000]:
    time_taken = benchmark_sort_size(size)
    print(f"Nodes: {size}, Time: {time_taken:.4f}s")
```

## Best Practices

### Do's
- Use for dependency resolution
- Detect cycles before processing
- Use static_order() when you need complete result
- Use dynamic approach for large graphs or concurrent processing

### Avoid's
- Don't assume order within independent nodes
- Don't modify graph during iteration
- Don't rely on specific order of equally-ranked nodes

## Limitations

- Only handles DAGs (Directed Acyclic Graphs)
- No weights on edges
- No path finding between nodes
- Cannot represent "soft" dependencies

## Alternatives

### For Complex Graph Processing

```python
# networkx - full graph library
# pip install networkx

import networkx as nx

G = nx.DiGraph()
G.add_edges_from([('A', 'B'), ('B', 'C')])
order = list(nx.topological_sort(G))

# For constraint solving
# Use PuLP, OR-Tools, or similar for optimization
```

## Related Documentation

- [Collections Module](collections.md)
- [Itertools Module](itertools.md)
- [Heapq Module](heapq.md)
