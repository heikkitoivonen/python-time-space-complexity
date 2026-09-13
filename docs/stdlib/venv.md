# venv Module

The `venv` module creates isolated Python virtual environments, allowing separate package installations for different projects.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Create venv | O(n) | O(n) | Copy/link files; I/O bound |
| Activate | O(1) | O(1) | Update PATH |

## Creating Virtual Environments

### Create and Use Virtual Environment

```python
import venv
import os

# Create venv - O(n)
venv.create('myenv')

# Or from command line:
# python -m venv myenv

# Activate (shell commands):
# source myenv/bin/activate  # Unix/Mac
# myenv\\Scripts\\activate     # Windows

# Install packages in venv
# pip install ./my_project
```

### Programmatic Creation

```python
import venv

# Create with custom context - O(n)
builder = venv.EnvBuilder(with_pip=True)
builder.create('my_venv')

# Setup context
context = builder.ensure_directories('another_venv')
```

## Related Documentation

- [site Module](site.md)
- [sysconfig Module](sysconfig.md)
