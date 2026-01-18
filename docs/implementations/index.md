# Python Implementations

Different Python implementations may have varying performance characteristics for the same operations.

## Major Implementations

- **[CPython](cpython.md)** - Reference implementation (C-based)
- **[PyPy](pypy.md)** - JIT compiler (Python-based, fastest for many workloads)
- **[Jython](jython.md)** - Java platform (Java interoperability)
- **[IronPython](ironpython.md)** - .NET platform (.NET interoperability)

## Quick Comparison

| Implementation | Engine | Performance | Use Case |
|---|---|---|---|
| CPython | Bytecode interpreter | Good | General purpose, standard |
| PyPy | JIT compiler | Excellent | Long-running, CPU-bound tasks |
| Jython | Java-based | Good | Java ecosystem integration |
| IronPython | .NET-based | Good | .NET ecosystem integration |

## Complexity Guarantees

While standard operations have similar complexity across implementations, there are differences:

- **CPython**: Baseline, well-tested complexity guarantees
- **PyPy**: Same algorithmic complexity, may be faster in practice
- **Jython**: Uses Java collections, may have different characteristics
- **IronPython**: Uses .NET types, similar to CPython

## Key Differences

### Optimization Strategies

- **CPython**: Static optimizations, caching, string interning
- **PyPy**: Dynamic JIT optimization, guard-based specialization
- **Jython**: Java native performance, GC differences
- **IronPython**: .NET runtime benefits, library integration

### Memory Management

- **CPython**: Reference counting + generational GC
- **PyPy**: Generational GC (no reference counting overhead)
- **Jython**: Java GC (pause times may vary)
- **IronPython**: .NET GC (similar to Jython)

## Detailed Guides

See individual implementation pages for:

- Specific optimizations
- Performance characteristics
- Known differences in complexity
- When to use each implementation

## Related Topics

- [Built-in Types](../builtins/index.md)
- [Standard Library](../stdlib/index.md)
- [Versions](../versions/index.md)
