# Python Version Guides

Different Python versions have made various optimizations and changes that affect complexity characteristics.

## Version Overview

| Version | Release | Status | Notes |
|---------|---------|--------|-------|
| 3.8 | Oct 2019 | EOL | Assignment expressions (walrus) |
| 3.9 | Oct 2020 | Security fixes | Type hints, new parsers |
| 3.10 | Oct 2021 | Security fixes | Pattern matching |
| 3.11 | Oct 2022 | Bugfix | Inline caching, 10-60% faster |
| 3.12 | Oct 2023 | Current | Better specialization |
| 3.13 | Oct 2024 | Current | Free-threading (experimental) |
| 3.14 | Oct 2025 | Current | Max-heap support, incremental GC |

## Quick Links

- **[Python 3.14](py314.md)** - Latest: max-heap functions, better GC pauses
- **[Python 3.13](py313.md)** - Experimental free-threading, JIT compiler
- **[Python 3.12](py312.md)** - Comprehension inlining, type parameters
- **[Python 3.11](py311.md)** - Significant performance improvements (inline caching)
- **[Python 3.10](py310.md)** - Pattern matching additions
- **[Python 3.9](py39.md)** - Type hints and parser improvements

## Key Changes by Version

### Python 3.14 (October 2025)

New max-heap support and optimizations:

```python
import heapq

# Native max-heap functions (new!)
data = [3, 1, 4, 1, 5, 9]
heapq.heapify_max(data)        # O(n) - max-heap transform
heapq.heappush_max(data, 10)   # O(log n)
max_val = heapq.heappop_max(data)  # O(log n)

# Incremental GC: 10x better pause times for large heaps
# uuid4(): ~30% faster
```

### Python 3.13 (October 2024)

Experimental features and optimizations:

```python
# Experimental free-threading (no GIL)
# Build with: --disable-gil

# Experimental JIT compiler
# Enable with: PYTHON_JIT=1

# textwrap.indent(): 30% faster for large input
```

### Python 3.12 (October 2023)

New features and optimizations:

```python
# Improved error messages
"test"[999]  # IndexError with better message

# Type parameter syntax (PEP 695)
def greet[T: str](x: T) -> T:
    return x

# Performance: 5-10% faster on average
```

### Python 3.11 (October 2022)

Major performance improvements:

```python
# Exception groups and except* syntax
try:
    ...
except ExceptionGroup as eg:
    raise eg.derive(...)

# Inline caching for attributes
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
# First access: cache miss
print(p.x)
# Repeated access: uses inline cache (much faster)

# 10-60% performance improvement overall
```

### Python 3.10 (October 2021)

Pattern matching:

```python
# Structural pattern matching
match value:
    case 1:
        print("one")
    case 2:
        print("two")
    case _:
        print("other")
```

### Python 3.9 (October 2020)

Type hints and flexibility:

```python
# Type hints without import
def add(a: list[int], b: list[int]) -> list[int]:
    return [x + y for x, y in zip(a, b)]

# Dictionary operations
d1 = {'a': 1}
d2 = {'b': 2}
d3 = d1 | d2  # {' a': 1, 'b': 2}
d1 |= d2  # Update in place
```

### Python 3.8 (October 2019)

Assignment expressions:

```python
# Walrus operator :=
if (n := len(a)) > 10:
    print(f"List too long ({n} elements)")

# Positional-only parameters
def func(x, /, y):
    # x is positional-only, y can be keyword
    pass
```

## Compatibility Considerations

### End of Life Dates

| Version | EOL Date |
|---------|----------|
| 3.8 | Oct 2024 (EOL) |
| 3.9 | Oct 2025 |
| 3.10 | Oct 2026 |
| 3.11 | Oct 2027 |
| 3.12 | Oct 2028 |
| 3.13 | Oct 2029 |
| 3.14 | Oct 2030 |

Plan upgrades before EOL.

### Breaking Changes

Generally minimal between minor versions, but check:

- [Python 3.14 What's New](https://docs.python.org/3.14/whatsnew/)
- [Python 3.13 What's New](https://docs.python.org/3.13/whatsnew/)
- [Python 3.12 What's New](https://docs.python.org/3.12/whatsnew/)
- [Python 3.11 What's New](https://docs.python.org/3.11/whatsnew/)
- [Python 3.10 What's New](https://docs.python.org/3.10/whatsnew/)

## Performance Recommendations

### Upgrade Path

```
Python 3.8 → Python 3.9    Incremental improvements
Python 3.9 → Python 3.10   Minor improvements
Python 3.10 → Python 3.11  10-60% faster (significant!)
Python 3.11 → Python 3.12  5-10% faster
Python 3.12 → Python 3.13  Similar (experimental features)
Python 3.13 → Python 3.14  Better GC pauses, new heapq functions
```

**Recommendation**: Use Python 3.11+ for performance, 3.14+ for new heapq max-heap functions.

## Feature by Version

| Feature | Version | Status |
|---------|---------|--------|
| Walrus operator | 3.8+ | Stable |
| Type hints (generic) | 3.9+ | Stable |
| Pattern matching | 3.10+ | Stable |
| Inline caching | 3.11+ | Stable |
| Exception groups | 3.11+ | Stable |
| Type parameters | 3.12+ | Stable |
| Comprehension inlining | 3.12+ | Stable |
| Free-threading | 3.13+ | Experimental |
| JIT compiler | 3.13+ | Experimental |
| Max-heap (heapq) | 3.14+ | New |
| Incremental GC | 3.14+ | New |

## Complexity Characteristics by Version

### Dict Operations

| Version | Behavior | Complexity |
|---------|----------|-----------|
| 3.5 | Unordered | O(1) lookup |
| 3.6+ | Ordered | O(1) lookup |
| 3.9+ | Optimized | O(1) lookup (faster) |

### List Operations

| Version | Append | Insert | Notes |
|---------|--------|--------|-------|
| All 3.x | O(1)* | O(n) | Consistent |

### String Operations

| Version | Lookup | Contains | Notes |
|---------|--------|----------|-------|
| 3.3+ | O(1) | O(n + m) worst for long strings, O(n*m) worst for pathological cases | Flexible representation |
| 3.11+ | O(1) | O(n + m) worst for long strings, O(n*m) worst for pathological cases* | Faster due to inline caching |

## Upgrading Python

### Check Compatibility

```bash
# Test with newer version
pyenv install 3.12.0
pyenv shell 3.12.0
python -m pytest  # Run tests

# Check for deprecations
python -W all your_script.py
```

### Gradual Adoption

```bash
# Keep older version
pyenv install 3.11.0
pyenv local 3.11.0  # Use 3.11 for this project
pyenv global 3.12.0  # Use 3.12 everywhere else
```

## Related Documentation

- [CPython Implementation](../implementations/cpython.md)
- [Built-in Types](../builtins/index.md)
- [Standard Library](../stdlib/index.md)
