# distutils Module

⚠️ **REMOVED IN PYTHON 3.12**: The `distutils` package was deprecated in Python 3.10 and removed in Python 3.12.

The `distutils` module provided tools for building and distributing Python packages.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Build distribution | O(n) | O(n) | n = files |
| Compile extensions | O(k) | O(k) | k = C files |

## Building Distributions

### Setup Script

```python
# Legacy example (Python <= 3.11)
from distutils.core import setup

setup(
    name='mypackage',
    version='1.0.0',
    description='My package',
    author='Your Name',
    py_modules=['mymodule'],
    scripts=['bin/myscript'],
)

# Run:
# python setup.py build
# python setup.py install
# python setup.py sdist
```

## Related Documentation

- [setuptools Library](https://pypi.org/project/setuptools/)
- [venv Module](venv.md)
