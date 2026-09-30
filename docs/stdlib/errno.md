# errno Module Complexity

The `errno` module is a table of the platform's error numbers: one integer constant per symbolic
name, plus `errorcode`, a dictionary from number back to name. Both are built once, when the module
is imported, and nothing in the module does work after that.

`v` is the distinct error numbers the platform defines, which is the number of entries in
`errorcode`. The numbers themselves differ between operating systems, and a name the platform
does not define is not an attribute at all.

## Complexity Reference

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `errno.ENOENT`, `errno.EACCES`, and every other `errno.E*` name | O(1) | O(1) | Module attribute lookup; a name the platform lacks raises `AttributeError` |
| `errno.WSAE*` names | O(1) | O(1) | Windows only; the socket names such as `ECONNRESET` take these Winsock values there |

### errorcode

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `errno.errorcode` | O(1) | O(1) | The same dictionary on every access |
| `errno.errorcode[code]` | O(1) | O(1) | Dict lookup; one name per number, so aliases such as `EWOULDBLOCK` and `EAGAIN` share an entry where their numbers match |
| Iterating `errno.errorcode` | O(v) | O(1) | Numbers, not names; iterate `.values()` for one name per number |

### Matching an OSError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `exc.errno == errno.ENOENT` | O(1) | O(1) | Integer comparison |
| `OSError(code, strerror)` | O(1) | O(1) | A dict lookup on `code` picks the subclass, such as `FileNotFoundError` for `ENOENT` |

## Checking an OSError

An `OSError` raised by a failing system call carries the number in `.errno` (one built by hand
may hold `None`), and comparing it with a constant is an integer compare. Compare against the constant, never a literal: the same name has a different number on
different systems.

```python
import errno
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    missing = os.path.join(directory, "missing.txt")
    try:
        with open(missing, "r") as handle:
            handle.read()
    except OSError as exc:
        assert exc.errno == errno.ENOENT  # O(1)
    else:
        raise AssertionError("a missing file was opened")
```

### Exception Subclasses Instead of Codes

`OSError` picks its subclass from the number when it is built, so catching `FileNotFoundError` is
the same test as comparing with `ENOENT`, and `BlockingIOError` covers `EAGAIN` and
`EWOULDBLOCK` whether or not the platform gives them one number. Codes with no subclass, such as
`EIO` or `ENOSPC`, still need the comparison.

```python
import errno

error = OSError(errno.ENOENT, "No such file or directory")  # O(1) - dict lookup on the code
assert type(error) is FileNotFoundError
assert error.errno == errno.ENOENT

assert type(OSError(errno.EWOULDBLOCK, "busy")) is BlockingIOError
assert type(OSError(errno.EAGAIN, "busy")) is BlockingIOError
assert type(OSError(errno.EIO, "I/O error")) is OSError  # no subclass for EIO
```

## Mapping a Code to Its Name

`errorcode` holds one name per number. Where two names share a number, as `EWOULDBLOCK` and
`EAGAIN` do on Linux and macOS, the dictionary keeps only one of them, so a name read back from it
is not always the name the code was raised under.

```python
import errno
import os

assert errno.errorcode[errno.ENOENT] == "ENOENT"  # O(1)
assert os.strerror(errno.ENOENT) == "No such file or directory"

# Aliases share an entry: the name that comes back is one of them
name = errno.errorcode[errno.EWOULDBLOCK]  # O(1)
assert getattr(errno, name) == errno.EWOULDBLOCK
assert name in {"EWOULDBLOCK", "EAGAIN", "WSAEWOULDBLOCK"}

# Every defined name, aliases included, is an attribute; errorcode has one per number
names = [name for name in dir(errno) if name.startswith(("E", "WSA"))]
assert len(errno.errorcode) == len({getattr(errno, name) for name in names})
```

## Performance Best Practices

✅ **Do**:

- Compare `exc.errno` with a constant, or catch the `OSError` subclass; both are O(1)
- Catch `BlockingIOError` rather than comparing with `EAGAIN` and `EWOULDBLOCK` by hand; it also
  catches `EALREADY` and `EINPROGRESS`
- Use `getattr(errno, name, None)` for a name that only some platforms define

❌ **Avoid**:

- Hard-coding a number such as `11` for `EAGAIN`: it is right on some systems only
- Rebuilding a reverse map from `dir(errno)`; `errorcode` already is one

## Version Notes

- **All Python 3**: Constant values and the set of defined names follow the operating system;
  `EAGAIN`, for one, has different numbers on Linux and macOS

## Related Modules

- **[os](os.md)** - `os.strerror()` turns a number into its message
- **[socket](socket.md)** - network errors such as `ECONNRESET` and `ETIMEDOUT`
- **[Exceptions](../builtins/exceptions.md)** - the `OSError` subclasses each number maps to
