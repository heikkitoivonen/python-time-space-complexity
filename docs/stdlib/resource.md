# resource Module

The `resource` module provides access to per-process resource usage information and limits. It is intended for Unix-like systems.

!!! warning "Unix-only"
    The `resource` module is not available on Windows and may not be available on some Python builds.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `resource.getrusage(who)` | O(1) | O(1) | System call; returns usage snapshot |
| `resource.getrlimit(resource)` | O(1) | O(1) | System call; returns (soft, hard) limits |
| `resource.setrlimit(resource, limits)` | O(1) | O(1) | System call; may require privileges |
| `resource.getpagesize()` | O(1) | O(1) | Cached system value |
| `resource.prlimit(pid, resource, limits=None)` | O(1) | O(1) | Linux-only; query or set another process's limits |

## Common Operations

### Read Resource Usage

```python
import resource

# Get current process usage - O(1)
usage = resource.getrusage(resource.RUSAGE_SELF)

print(usage.ru_utime)  # User CPU time
print(usage.ru_stime)  # System CPU time
```

### Read and Set Limits

```python
import resource

# Read current limits - O(1)
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
print(soft, hard)

# Raise soft limit up to hard limit - O(1)
resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
```

### Enforce CPU Time Limit

```python
import resource
import time

# Limit CPU time to 1 second - O(1)
resource.setrlimit(resource.RLIMIT_CPU, (1, 1))

# Busy loop to trigger CPU limit
while True:
    pass
```

### Query Another Process (Linux)

```python
import resource

# Query limits for a process ID - O(1)
limits = resource.prlimit(1234, resource.RLIMIT_NOFILE)
```

## Notes on Limits

- Soft limits are enforced; hard limits cap the soft limit.
- Lowering hard limits typically cannot be undone without privileges.
- `prlimit()` is only available on Linux.

## Related Modules

- [os Module](os.md) - Process and resource-related utilities
- [signal Module](signal.md) - Process signals
- [subprocess Module](subprocess.md) - Launching processes
