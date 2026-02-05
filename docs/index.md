# Python Time & Space Complexity Reference

Welcome to the comprehensive guide for Python operation complexity. This resource documents the time and space complexity of Python's built-in operations, standard library functions, and their behavior across different Python versions and implementations.

## Quick Start

- **[Built-in Types](builtins/index.md)** - Complexity analysis for lists, dicts, sets, strings, and tuples
- **[Standard Library](stdlib/index.md)** - Modules like collections, heapq, bisect, and more
- **[Implementations](implementations/index.md)** - CPython, PyPy, Jython, and other implementation details
- **[Versions](versions/index.md)** - Changes and optimizations by Python version

## Why This Matters

Understanding complexity helps you:

- Write performant Python code
- Choose the right data structure for your use case
- Predict how your code scales with larger inputs
- Optimize algorithms effectively

## Example: List Operations

The complexity of list operations varies:

| Operation | Time Complexity | Space |
|-----------|-----------------|-------|
| `append()` | O(1) amortized | - |
| `insert(0, x)` | O(n) | - |
| `pop()` | O(1) | - |
| `pop(0)` | O(n) | - |
| `in` (search) | O(n) | - |
| `sort()` | O(n log n) | O(n) |

See [Built-in Types](builtins/list.md) for detailed analysis.

## How to Use This Guide

1. **Search** - Use the search bar to find specific operations
2. **Browse** - Navigate by type or module
3. **Filter** - Select Python version or implementation
4. **Check Notes** - Read implementation-specific considerations

## Coverage

- **Python Versions**: 3.9-3.14
- **Implementations**: CPython, PyPy, Jython, IronPython
- **Operations**: 2,200+ built-in and stdlib operations
- **Updates**: Regularly updated with new Python releases

## Why Trust This Documentation?

This documentation has been reviewed and refined by multiple AI coding agents (Amp, Claude, Gemini CLI, Kiro, Copilot, Codex) and models (Opus 4.(5|6), Sonnet 4.5, Gemini 3 Pro, gpt-5.(2|3)-codex, ...) working alongside human contributors. Each agent brings different perspectives and catches different issues, resulting in thorough cross-validation. A growing unit test suite validates complexity claims against actual Python behavior.

It's also **fully open source**—anyone can review the content, [file issues](https://github.com/heikkitoivonen/python-time-space-complexity/issues), or [submit improvements](https://github.com/heikkitoivonen/python-time-space-complexity/pulls). All sources are cited, and claims are based on official Python documentation and CPython source code.

## Contributing

Found an inaccuracy or want to add content? See our [Contributing Guidelines](https://github.com/heikkitoivonen/python-time-space-complexity/blob/main/CONTRIBUTING.md).

## Sources

- [Python Official Documentation](https://docs.python.org/3/)
- [TimeComplexity Wiki](https://wiki.python.org/moin/TimeComplexity)
- [CPython source code](https://github.com/python/cpython) and implementation details
- [Performance testing](https://github.com/heikkitoivonen/python-time-space-complexity/tree/main/tests) and benchmarking

---

**Disclaimer**: While we strive for accuracy, complexity characteristics may vary based on specific contexts, input sizes, and implementation details. Always verify with benchmarks for performance-critical code.
