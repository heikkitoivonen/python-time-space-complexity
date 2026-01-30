# pty Module

The `pty` module provides pseudo-terminal utilities for Unix systems, enabling control of terminal-like processes.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fork()` | O(1) | O(1) | Create pseudo-terminal |
| I/O handling | O(n) | O(n) | n = data size |

## Pseudo-Terminal Operations

### Spawning Terminal Process

```python
import pty
import subprocess
import sys

# Spawn interactive process - O(1)
pty.spawn(['bash'])

# Equivalent to:
# bash shell with full terminal support
```

### Fork with PTY

```python
import os
import pty
import sys

# Fork with pseudo-terminal - O(1)
pid, master_fd = pty.fork()

if pid == 0:
    # Child process - O(1)
    os.execv('/bin/bash', ['/bin/bash'])
else:
    # Parent process - O(n)
    while True:
        try:
            data = os.read(master_fd, 1024)
            sys.stdout.buffer.write(data)
        except OSError:
            break
    
    os.close(master_fd)
    os.waitpid(pid, 0)
```

## Related Documentation

- [tty Module](tty.md)
- [subprocess Module](subprocess.md)
