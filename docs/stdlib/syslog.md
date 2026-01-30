# syslog Module

The `syslog` module provides a thin wrapper around the system logger for writing
messages to the Unix syslog service.

!!! warning "Unix-only module"
    `syslog` is only available on Unix-like systems. On Windows, use `logging`
    (or a platform-specific event log integration).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `openlog()` | O(1) | O(1) | Configure syslog identity/options |
| `syslog()` | O(n) + I/O | O(1) | n = message length; I/O dominates |
| `setlogmask()` | O(1) | O(1) | Set priority mask |
| `closelog()` | O(1) | O(1) | Reset to defaults |

## Basic Usage

```python
import syslog

# Configure identity and facility - O(1)
syslog.openlog(ident="myapp", logoption=syslog.LOG_PID, facility=syslog.LOG_USER)

# Log messages - O(n) + I/O
syslog.syslog(syslog.LOG_INFO, "Started up")
syslog.syslog(syslog.LOG_ERR, "Something went wrong")

# Reset to defaults - O(1)
syslog.closelog()
```

## Priority Masks

```python
import syslog

# Allow only WARNING and above - O(1)
mask = syslog.LOG_MASK(syslog.LOG_WARNING) | syslog.LOG_MASK(syslog.LOG_ERR)
old = syslog.setlogmask(mask)

syslog.syslog(syslog.LOG_INFO, "Ignored")
syslog.syslog(syslog.LOG_ERR, "Logged")

# Restore previous mask - O(1)
syslog.setlogmask(old)
```

## Logging Helpers

```python
import syslog

def log_exception(msg):
    """Log error with exception info - O(n) + I/O"""
    try:
        raise RuntimeError("boom")
    except Exception as exc:
        syslog.syslog(syslog.LOG_ERR, f"{msg}: {exc}")

log_exception("Operation failed")
```

## Related Documentation

- [logging Module](logging.md) - Higher-level, cross-platform logging
- [os Module](os.md) - OS interfaces
