# pipes Module

The `pipes` module provides a way to run shell pipelines from Python, managing command sequences with input/output redirection.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Create template | O(1) | O(1) | Build command |
| Execute pipeline | O(n) + subprocess | O(n) | n = data size; subprocess execution dominates |

## Building and Running Pipelines

### Simple Pipeline

```python
import pipes
import os

# Create template - O(1)
t = pipes.Template()

# Build pipeline - O(1) per command
t.append('cat', pipes.STDIN)         # Read from stdin
t.append('grep "pattern"', '')       # Filter
t.append('sort', pipes.STDOUT)       # Output to stdout

# Run - O(n)
t.makefile('input.txt', 'output.txt')
```

### Transform File

```python
import pipes

# Create pipeline - O(1)
t = pipes.Template()
t.append('cat', pipes.STDIN)
t.append('tr a-z A-Z', pipes.STDOUT)

# Apply to file - O(n)
t.makefile('input.txt', 'output.txt')
```

## Related Documentation

- [subprocess Module](subprocess.md)
- [shlex Module](shlex.md)
