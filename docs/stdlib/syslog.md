# syslog Module Complexity

The `syslog` module wraps the C library's `syslog(3)` routines. Each `syslog()` call hands one
message to the C library, which adds a header and sends it to the system logger. The module holds
only the identity string set by `openlog()`; the priority mask lives in the C library and applies
to the whole process.

!!! warning "Unix-only module"
    On Windows `import syslog` raises `ModuleNotFoundError`. `logging.handlers.SysLogHandler`
    talks to a syslog server from pure Python instead.

`n` is the characters in one message; the identity and every other argument count as O(1). The
bounds price the work done in the process: converting the message and formatting it. Delivering it -
the write to the logger, and whatever the logger then does with it - is outside every bound.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `syslog.openlog([ident[, logoption[, facility]]])` | O(1) | O(1) | Sets the identity, options and default facility for later messages; `ident` defaults to `sys.argv[0]` without its directory, and `facility` to `LOG_USER` |
| `syslog.syslog([priority,] message)` | O(n) | O(n) | `priority` defaults to `LOG_INFO`; a facility ORed into it overrides `openlog()`'s for this message. Opens the log as `openlog()` with no arguments if it is not open |
| `syslog.closelog()` | O(1) | O(1) | Closes the log and forgets the identity; the next `syslog()` opens it again with the defaults |
| `syslog.setlogmask(maskpri)` | O(1) | O(1) | Sets the priority mask and returns the previous one; a mask of `0` leaves it unchanged, so `setlogmask(0)` reads it. The C library drops a filtered message after `syslog()` has converted it |
| `syslog.LOG_MASK(pri)` | O(1) | O(1) | The mask bit for one priority, `1 << pri` |
| `syslog.LOG_UPTO(pri)` | O(1) | O(1) | The mask for every priority from `LOG_EMERG` down to and including `pri` |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `syslog.LOG_EMERG`, `syslog.LOG_ALERT`, `syslog.LOG_CRIT`, `syslog.LOG_ERR`, `syslog.LOG_WARNING`, `syslog.LOG_NOTICE`, `syslog.LOG_INFO`, `syslog.LOG_DEBUG` | O(1) | O(1) | Priority levels 0 to 7, most severe first |
| `syslog.LOG_KERN`, `syslog.LOG_USER`, `syslog.LOG_MAIL`, `syslog.LOG_DAEMON`, `syslog.LOG_AUTH`, `syslog.LOG_LPR`, `syslog.LOG_NEWS`, `syslog.LOG_UUCP`, `syslog.LOG_CRON`, `syslog.LOG_SYSLOG`, `syslog.LOG_LOCAL0`, `syslog.LOG_LOCAL1`, `syslog.LOG_LOCAL2`, `syslog.LOG_LOCAL3`, `syslog.LOG_LOCAL4`, `syslog.LOG_LOCAL5`, `syslog.LOG_LOCAL6`, `syslog.LOG_LOCAL7` | O(1) | O(1) | Facilities. Their bits do not overlap the priority levels', so one ORs into a priority |
| `syslog.LOG_AUTHPRIV` | O(1) | O(1) | A facility, where the platform's `<syslog.h>` defines it |
| `syslog.LOG_FTP`, `syslog.LOG_NETINFO`, `syslog.LOG_REMOTEAUTH`, `syslog.LOG_INSTALL`, `syslog.LOG_RAS`, `syslog.LOG_LAUNCHD` | O(1) | O(1) | Facilities, Python 3.13+, each where the platform's `<syslog.h>` defines it |
| `syslog.LOG_PID`, `syslog.LOG_CONS`, `syslog.LOG_NDELAY` | O(1) | O(1) | `openlog()` options, combined with `\|` |
| `syslog.LOG_ODELAY`, `syslog.LOG_NOWAIT`, `syslog.LOG_PERROR` | O(1) | O(1) | `openlog()` options, where the platform's `<syslog.h>` defines them |

## Sending Messages

Every `syslog()` call converts its message and hands it to the C library, so each costs its own
length. The first call opens the log if `openlog()` has not, and `closelog()` makes the next one
open it again with the defaults.

```python
import syslog

syslog.openlog(ident='myapp', logoption=syslog.LOG_PID, facility=syslog.LOG_LOCAL0)  # O(1)

syslog.syslog('Started up')  # O(n) - LOG_INFO, from facility LOG_LOCAL0
syslog.syslog(syslog.LOG_ERR, 'Something went wrong')  # O(n)

# A facility ORed into the priority applies to this message only
login_failed = syslog.LOG_WARNING | syslog.LOG_AUTH
assert login_failed & 0x07 == syslog.LOG_WARNING  # the low bits are the level
syslog.syslog(login_failed, 'Login failed')  # O(n)

syslog.closelog()  # O(1) - the next syslog() opens the log with the defaults
```

## Priority Masks

The mask decides which priorities reach the logger, and it is the C library's: one mask for the
whole process. `syslog()` still converts a filtered message before the C library drops it.

```python
import syslog

everything = syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_WARNING))  # O(1) - returns the old mask
assert everything == syslog.LOG_UPTO(syslog.LOG_DEBUG)  # by default every priority passes

mask = syslog.setlogmask(0)  # O(1) - 0 reads the mask without changing it
assert mask & syslog.LOG_MASK(syslog.LOG_ERR)
assert not mask & syslog.LOG_MASK(syslog.LOG_INFO)

syslog.syslog(syslog.LOG_INFO, 'Filtered')  # still O(n)
syslog.syslog(syslog.LOG_ERR, 'Sent')  # O(n)

syslog.setlogmask(everything)  # O(1) - restore
```

## Common Patterns

### Skipping Expensive Messages

A filtered message is built and converted before it is dropped. Reading the mask first costs O(1)
and skips both.

```python
import syslog

def log_debug(build_message):
    if syslog.setlogmask(0) & syslog.LOG_MASK(syslog.LOG_DEBUG):  # O(1)
        syslog.syslog(syslog.LOG_DEBUG, build_message())  # O(n)

built = []

def describe_state():
    built.append(True)
    return 'state: ' + ', '.join(map(str, range(10_000)))

previous = syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_INFO))
log_debug(describe_state)
assert built == []  # filtered before it was built

syslog.setlogmask(previous)
log_debug(describe_state)
assert built == [True]
```

## Performance Best Practices

✅ **Do**:

- Call `openlog()` once at startup; its identity and default facility hold until `closelog()`
- Check `setlogmask(0)` before building a costly message at a priority the mask may filter

❌ **Avoid**:

- Counting on the mask to make a costly message free - it is built and converted before it is
  dropped
- Calling `closelog()` between messages - the next `syslog()` opens the log again with the
  default identity and facility

## Version Notes

- **Python 3.12+**: A message containing a null character raises `ValueError`; earlier versions
  pass on only the text before it

## Related Modules

- **[logging](logging.md)** - levels, handlers and formatting; `logging.handlers.SysLogHandler`
  sends to a syslog server without this module
