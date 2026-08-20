# spwd Module

⚠️ **REMOVED IN PYTHON 3.13**: The `spwd` module was deprecated in Python 3.11 and removed in Python 3.13.

The `spwd` module provides access to the Unix shadow password database
(`/etc/shadow`), where hashed passwords and account-ageing fields are stored.
Reading it normally requires root privileges.

Throughout, `n` is the number of entries in the database.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getspnam(name)` | O(n) | O(1) | Linear scan of the database for one user |
| `getspall()` | O(n) | O(n) | Returns every entry as a list |

The underlying C library walks the file sequentially, so there is no index to
exploit. Both functions are linear.

### Entry Fields

Each record is a tuple-like object with attribute access, all O(1):

| Attribute | Meaning |
|-----------|---------|
| `sp_namp` | Login name |
| `sp_pwdp` | Hashed password |
| `sp_lstchg` | Date of last change (days since epoch) |
| `sp_min` | Minimum days between changes |
| `sp_max` | Maximum days the password is valid |
| `sp_warn` | Days before expiry to warn |
| `sp_inact` | Days after expiry until the account is disabled |
| `sp_expire` | Account expiry date |
| `sp_flag` | Reserved |

## Looking Up One Account

```python
import spwd

# O(n) - scans until the name matches
entry = spwd.getspnam("alice")
print(entry.sp_namp, entry.sp_max)   # O(1) attribute access
```

`getspnam()` raises `KeyError` if the user does not exist, and
`PermissionError` if the process cannot read the shadow file.

## Scanning Every Account

```python
import spwd

# O(n) time and O(n) space - the whole database is materialized
expiring = [
    e.sp_namp
    for e in spwd.getspall()
    if e.sp_max != -1
]
```

Calling `getspnam()` inside a loop over many users is O(n*m); read the database
once with `getspall()` and build a dict instead:

```python
import spwd

# One O(n) pass, then O(1) lookups
by_name = {e.sp_namp: e for e in spwd.getspall()}
for name in names_to_check:
    entry = by_name.get(name)     # O(1)
```

!!! warning "Removed in Python 3.13"
    There is no standard-library replacement. Use a third-party library such as
    `python-pam` for authentication, or read the database through the
    platform's own tooling.

!!! warning "Requires privileges"
    The shadow database is readable only by root on most systems. Design around
    delegating authentication rather than reading hashes directly.

## Version Notes

- **Python 3.11**: deprecated (PEP 594)
- **Python 3.13**: removed
- **Before 3.13**: Unix-only; not available on Windows
- **All versions**: both lookups are linear scans

## Related Documentation

- [Pwd Module](pwd.md)
- [Grp Module](grp.md)
- [Crypt Module](crypt.md)
- [OS Module](os.md)
