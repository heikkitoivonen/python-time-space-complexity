# Python Version Guides

Different Python versions have made various optimizations and changes that affect complexity characteristics.

## Version Overview

| Version | Release | Status | Notes |
|---------|---------|--------|-------|
| 3.15 | Oct 2026 | Bugfix | Lazy imports, frozendict, UTF-8 default |
| 3.14 | Oct 2025 | Bugfix | Max-heap support |
| 3.13 | Oct 2024 | Security | Free-threading (experimental) |
| 3.12 | Oct 2023 | Security | Better specialization |
| 3.11 | Oct 2022 | Security | Inline caching, 10-60% faster |
| 3.10 | Oct 2021 | End of life | Pattern matching |

## Quick Links

- **[Python 3.15](py315.md)** - Latest: lazy imports, frozendict, sentinel, UTF-8 by default
- **[Python 3.14](py314.md)** - Max-heap functions in heapq
- **[Python 3.13](py313.md)** - Experimental free-threading, JIT compiler
- **[Python 3.12](py312.md)** - Comprehension inlining, type parameters
- **[Python 3.11](py311.md)** - Significant performance improvements (inline caching)
- **[Python 3.10](py310.md)** - Pattern matching additions (end of life)

## Key Changes by Version

### Python 3.15 (October 2026)

Lazy imports and new built-in types:

```python
lazy import json                      # O(1): loaded on first use

config = frozendict(host="localhost")  # O(n) to build, hashable
cache = {config: "connection"}         # usable as a dict key

data = bytearray(b"payload")
payload = data.take_bytes()            # O(1): no copy, data left empty
```

### Python 3.14 (October 2025)

New max-heap support and optimizations:

```python
import heapq

# Native max-heap functions (new!)
data = [3, 1, 4, 1, 5, 9]
heapq.heapify_max(data)        # O(n) - max-heap transform
heapq.heappush_max(data, 10)   # O(log n)
max_val = heapq.heappop_max(data)  # O(log n)
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

## Compatibility Considerations

### End of Life Dates

| Version | EOL Date |
|---------|----------|
| 3.15 | Oct 2031 |
| 3.14 | Oct 2030 |
| 3.13 | Oct 2029 |
| 3.12 | Oct 2028 |
| 3.11 | Oct 2027 |
| 3.10 | Oct 2026 (reached) |

Plan upgrades before EOL.

### Breaking Changes

Generally minimal between minor versions, but check:

- [Python 3.15 What's New](https://docs.python.org/3.15/whatsnew/)
- [Python 3.14 What's New](https://docs.python.org/3.14/whatsnew/)
- [Python 3.13 What's New](https://docs.python.org/3.13/whatsnew/)
- [Python 3.12 What's New](https://docs.python.org/3.12/whatsnew/)
- [Python 3.11 What's New](https://docs.python.org/3.11/whatsnew/)
- [Python 3.10 What's New](https://docs.python.org/3.10/whatsnew/)

## Performance Recommendations

### Upgrade Path

```
Python 3.10 → Python 3.11  10-60% faster (significant!)
Python 3.11 → Python 3.12  5-10% faster
Python 3.12 → Python 3.13  Similar (experimental features)
Python 3.13 → Python 3.14  New heapq max-heap functions
Python 3.14 → Python 3.15  Lazy imports, frozendict, Base32/Base85 in C
```

**Recommendation**: Use Python 3.11+ for performance, 3.14+ for heapq max-heap functions, 3.15+ for lazy imports and `frozendict`.

## Feature by Version

| Feature | Version | Status |
|---------|---------|--------|
| Walrus operator | All | Stable |
| Type hints (generic) | All | Stable |
| Pattern matching | 3.10+ | Stable |
| Inline caching | 3.11+ | Stable |
| Exception groups | 3.11+ | Stable |
| Type parameters | 3.12+ | Stable |
| Comprehension inlining | 3.12+ | Stable |
| Free-threading | 3.13+ | Experimental |
| JIT compiler | 3.13+ | Experimental |
| Max-heap (heapq) | 3.14+ | Stable |
| Incremental GC | 3.14.0-3.14.4 | Reverted in 3.14.5 |
| Lazy imports | 3.15+ | Stable |
| frozendict, sentinel | 3.15+ | Stable |
| Unpacking in comprehensions | 3.15+ | Stable |
| UTF-8 default encoding | 3.15+ | Stable |

## Complexity Characteristics by Version

### Dict Operations

| Version | Behavior | Complexity |
|---------|----------|-----------|
| 3.5 | Unordered | O(1) lookup |
| 3.6 (CPython) | Ordered (implementation detail) | O(1) lookup |
| 3.7+ | Ordered (language guarantee) | O(1) lookup |
| 3.10+ | Optimized | O(1) lookup (faster) |

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
uv python install 3.12
uv run --python 3.12 python -m unittest discover  # Run tests

# Check for deprecations
uv run --python 3.12 python -W all your_script.py
```

### Gradual Adoption

```bash
# Pin version for this project
echo "3.11" > .python-version
uv sync  # Installs Python 3.11 and dependencies

# Use different version for one-off commands
uv run --python 3.12 python script.py
```

## Related Documentation

- [CPython Implementation](../implementations/cpython.md)
- [Builtins](../builtins/index.md)
- [Standard Library](../stdlib/index.md)
