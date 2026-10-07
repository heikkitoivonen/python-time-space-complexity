# pwd Module Complexity

The `pwd` module reads the Unix user account database through the C library, which hands each
query to whatever backend the system's name-service switch configures: a local file such as
`/etc/passwd`, a directory server, or a cache in front of either. Every call asks the backend
again and builds fresh entry objects; nothing is cached in Python.

It is Unix-only. On Windows `import pwd` raises `ModuleNotFoundError`.

`u` is the entries the database enumerates. Every entry has the same seven fields, and a field
counts as one item; the characters in a name, a home directory or a shell are not priced. The
bounds price the work on the Python side of each call. What the backend spends answering -
reading a file, a network round trip, a cache hit - is outside every bound, so O(1) means one
query and one entry built, not that the call returns promptly.

## Complexity Reference

### Lookups

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pwd.getpwuid(uid)` | O(1) | O(1) | Asks the backend; `KeyError` if no entry has the uid, `TypeError` for a float or a string |
| `pwd.getpwnam(name)` | O(1) | O(1) | Asks the backend; `KeyError` if no entry has the name, `TypeError` for bytes |
| `pwd.getpwall()` | O(u) | O(u) | Enumerates the whole database into a new list, in arbitrary order |

### struct_passwd

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pwd.struct_passwd` | O(1) | O(1) | The type of every entry: a 7-tuple whose items also have names |
| `struct_passwd.pw_name`, `struct_passwd.pw_passwd`, `struct_passwd.pw_uid`, `struct_passwd.pw_gid` | O(1) | O(1) | The login name, the password field, and the integer user and primary group ids |
| `struct_passwd.pw_gecos`, `struct_passwd.pw_dir`, `struct_passwd.pw_shell` | O(1) | O(1) | The comment (usually the real name), the home directory and the login shell |
| `struct_passwd.n_fields`, `struct_passwd.n_sequence_fields`, `struct_passwd.n_unnamed_fields` | O(1) | O(1) | 7, 7 and 0 |

## Looking Up a User

A lookup by uid or by name asks the backend for one entry. The entry comes back as a new object
on every call, so a loop that looks up the same user repeatedly pays the backend every time.

```python
import pwd

root = pwd.getpwuid(0)  # O(1) - asks the backend
assert root.pw_uid == 0
assert root[0] == root.pw_name and root[5] == root.pw_dir

same = pwd.getpwnam(root.pw_name)  # O(1) - another query
assert same.pw_uid == root.pw_uid and same.pw_name == root.pw_name
assert same is not root  # a fresh entry, not a cached one

try:
    pwd.getpwuid(2**32)  # beyond a 32-bit uid_t, so no entry can have it
except KeyError as error:
    assert 'uid not found' in str(error)
else:
    raise AssertionError('a missing uid was found')
```

## Enumerating Every User

`getpwall()` walks the whole database and builds an entry for each account, so it costs every
user at once. For many lookups, build a dictionary from one call and look up in that: O(u) once,
then O(1) per lookup instead of a trip to the backend.

A backend need not enumerate everything it can answer. A directory service may have enumeration
turned off, so fall back to a lookup when the dictionary misses.

```python
import pwd

users = pwd.getpwall()  # O(u) time and memory
by_uid = {entry.pw_uid: entry for entry in users}  # O(u)

def user(uid):
    entry = by_uid.get(uid)  # O(1)
    if entry is None:
        entry = by_uid[uid] = pwd.getpwuid(uid)  # O(1) - not enumerated, ask once
    return entry

assert user(0).pw_uid == 0
```

## Performance Best Practices

✅ **Do**:

- Look up a single user with `getpwuid()` or `getpwnam()`: it costs one entry, not the database
- Build a dictionary from one `getpwall()` call when you need many users, and fall back to a
  lookup on a miss

❌ **Avoid**:

- Calling `getpwuid()` in a loop over many records owned by a few users - each call asks the
  backend again; keep the entries you have already fetched
- Scanning `getpwall()` for one user - O(u) for what a lookup answers directly
- Treating `getpwall()` as complete when the system uses a directory service

## Related Modules

- **[grp](grp.md)** - The group database, with the same lookup-or-enumerate shape
- **[os](os.md)** - `os.getuid()` for the uid to look up; `os.path.expanduser('~name')` asks
  `getpwnam()` for the home directory on every call
