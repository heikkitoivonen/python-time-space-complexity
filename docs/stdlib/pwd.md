# pwd Module

The `pwd` module provides access to the Unix password database (user accounts).
It is only available on Unix-like platforms.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getpwnam(name)` | O(1) + syscall | O(1) | Name lookup via system NSS/config |
| `getpwuid(uid)` | O(1) + syscall | O(1) | UID lookup via system NSS/config |
| `getpwall()` | O(n) + syscall | O(n) | n = number of user records |

## Basic Lookup

```python
import pwd

entry = pwd.getpwnam("root")
print(entry.pw_uid)
print(entry.pw_dir)

entry = pwd.getpwuid(0)
print(entry.pw_name)
```

## Listing All Users

```python
import pwd

for entry in pwd.getpwall():  # O(n)
    print(entry.pw_name, entry.pw_uid)
```

## Notes

- Lookups are mediated by the system's name service (NSS), so latency can vary.
- On some systems, remote directory services may impact performance.

## Related Modules

- [grp Module](grp.md) - Unix group database
- [os Module](os.md) - OS interfaces
