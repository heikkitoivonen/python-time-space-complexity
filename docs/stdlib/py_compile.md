# py_compile Module

The `py_compile` module compiles Python source files to bytecode (.pyc files), useful for precompilation and optimization.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compile()` | O(n) | O(n) | n = source length |
| Write bytecode | O(n) | O(n) | n = bytecode size |

## Compiling Python Files

### Basic Compilation

```python
import py_compile

# Compile file - O(n)
py_compile.compile('module.py')

# Creates a version-tagged .pyc in __pycache__ (PEP 3147)

# Compile with custom output
py_compile.compile('module.py', cfile='module.pyc')
```

### Batch Compilation

```python
import py_compile

# Compile multiple files - O(k*n)
files = ['script1.py', 'script2.py', 'module.py']
for f in files:
    py_compile.compile(f)  # O(n) per file
```

## Related Documentation

- [ast Module](ast.md)
- [compileall Module](compileall.md)
