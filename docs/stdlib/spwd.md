# spwd Module Complexity

The `spwd` module reads the Unix shadow password database, which holds each account's password
hash and password-ageing fields. Both functions go through the C library, so the host's
name-service configuration, such as `/etc/nsswitch.conf`, decides where the entries come from;
with the usual `files` backend that is `/etc/shadow`, which normally only root can read.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The page covers the module
    as it is on Python 3.10 to 3.12 on Unix; the examples also need privileges to read the
    database and an entry for `root` in it.

`n` is the entries in the database. The bounds are those of the `files` backend, and treat one
entry as short - a line of `/etc/shadow` - so reading or decoding it is O(1). Another backend sets
its own lookup cost.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `spwd.getspnam(name)` | O(n) | O(1) | Reads the database in order until the name matches. Raises `KeyError` when no entry matches, or an `OSError` such as `PermissionError` when a backend reports a failure; which one an unprivileged process gets depends on the backend |
| `spwd.getspall()` | O(n) | O(n) | A list of the entries the backends enumerate. Without privileges that may be fewer than `getspnam()` finds, or none, rather than an error |

### struct_spwd

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `spwd.struct_spwd` | O(1) | O(1) | The entry type: a 9-item tuple whose items are also attributes |
| `struct_spwd.sp_namp` | O(1) | O(1) | Index 0: login name |
| `struct_spwd.sp_pwdp` | O(1) | O(1) | Index 1: password hash |
| `struct_spwd.sp_lstchg` | O(1) | O(1) | Index 2: date of the last password change, in days since 1970-01-01 |
| `struct_spwd.sp_min` | O(1) | O(1) | Index 3: minimum days between changes |
| `struct_spwd.sp_max` | O(1) | O(1) | Index 4: maximum days between changes |
| `struct_spwd.sp_warn` | O(1) | O(1) | Index 5: days before the password expires to warn the user |
| `struct_spwd.sp_inact` | O(1) | O(1) | Index 6: days after the password expires until the account is disabled |
| `struct_spwd.sp_expire` | O(1) | O(1) | Index 7: date the account expires, in days since 1970-01-01 |
| `struct_spwd.sp_flag` | O(1) | O(1) | Index 8: reserved |

## Looking Up One Account

`getspnam()` reads the database until it finds the name, so one lookup costs up to the whole
database. The entry it returns is a tuple, read by index or by attribute name.

```python
import spwd

entry = spwd.getspnam('root')  # O(n)
assert entry.sp_namp == 'root'  # O(1)
assert entry[0] == entry.sp_namp  # O(1) - index 0 is the login name
assert len(entry) == 9

try:
    spwd.getspnam('no such user')
except KeyError:
    pass
else:
    raise AssertionError('a missing name returned an entry')
```

## Reading Every Account

`getspall()` reads the database once and keeps every entry. For more than a few names, that and a
`dict` beat a `getspnam()` call per name, each of which reads the database again.

```python
import spwd

entries = spwd.getspall()  # O(n) time and space
by_name = {entry.sp_namp: entry for entry in entries}  # O(n)

wanted = ['root', 'no such user']
found = {name: by_name[name] for name in wanted if name in by_name}  # O(1) per name
assert found['root'] == spwd.getspnam('root')
assert 'no such user' not in found
```

## Performance Best Practices

✅ **Do**:

- Call `getspnam()` for one or a few names
- Read the database once with `getspall()` and look names up in a `dict` when you need many
- Use `pwd` for names, user IDs and home directories; it needs no privileges and outlives this
  module

❌ **Avoid**:

- Calling `getspnam()` in a loop over many names - each call reads the database again
- Reading an empty `getspall()` as an empty database - without privileges it may return nothing
  rather than raise

## Version Notes

- **Python 3.11+**: `import spwd` emits a `DeprecationWarning`
- **Python 3.13+**: The module is removed; `import spwd` raises `ModuleNotFoundError`

## Related Modules

- **[pwd](pwd.md)** - the password database without the hashes, readable without privileges
- **[grp](grp.md)** - the group database
- **[crypt](crypt.md)** - hashing a password to compare with `sp_pwdp`, removed in Python 3.13 as
  well
