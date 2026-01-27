# idlelib Module

The `idlelib` module provides the Python IDLE editor library, used to build the IDLE integrated development environment.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Editor initialization | Varies | Varies | Depends on Tk setup and platform |
| Syntax highlighting | Varies | Varies | Depends on highlighter and text size processed |

## IDLE Components

### IDLE as a Library

```python
# IDLE is primarily used as an IDE, not a library
# But can be extended for custom editors

from idlelib.colorizer import ColorDelegator
from idlelib.rpc import RpcServer

# Syntax highlighter - O(n)
highlighter = ColorDelegator(None)

# IDLE runs as:
# python -m idlelib [file]
```

## Related Documentation

- [tkinter Module](tkinter.md)
- [code Module](code.md)
