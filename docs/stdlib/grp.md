# grp Module Complexity

The `grp` module reads the Unix group database through the C library, which hands each query to
whatever backend the system's name-service switch configures: a local file such as `/etc/group`,
a directory server, or a cache in front of either. Every call asks the backend again and builds
fresh entry objects; nothing is cached in Python.

It is Unix-only. On Windows `import grp` raises `ModuleNotFoundError`.

`g` is the entries the database enumerates, `m` is the member names in one entry, and `t` is the
member names across all enumerated entries. A name counts as one item; its characters are not
priced. The bounds price the work on the Python side of each call. What the backend spends
answering - reading a file, a network round trip, a cache hit - is outside every bound, so O(m)
means constant work per member, not that the call returns promptly.

## Complexity Reference

### Lookups

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `grp.getgrgid(id)` | O(m) | O(m) | Asks the backend; `KeyError` if no entry has the id, `TypeError` for a float or a string |
| `grp.getgrnam(name)` | O(m) | O(m) | Asks the backend; `KeyError` if no entry has the name |
| `grp.getgrall()` | O(g + t) | O(g + t) | Enumerates the whole database into a new list, in arbitrary order |

### struct_group

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `grp.struct_group` | O(1) | O(1) | The type of every entry: a 4-tuple whose items also have names |
| `struct_group.gr_name`, `struct_group.gr_passwd`, `struct_group.gr_gid` | O(1) | O(1) | The name, the password field, and the integer id |
| `struct_group.gr_mem` | O(1) | O(1) | The list of m member names, built with the entry; `user in entry.gr_mem` is O(m) |
| `struct_group.n_fields`, `struct_group.n_sequence_fields`, `struct_group.n_unnamed_fields` | O(1) | O(1) | 4, 4 and 0 |

## Looking Up a Group

A lookup by id or by name asks the backend for one entry. The entry comes back as a new object on every
call, so a loop that looks up the same group repeatedly pays the backend every time.

```python
import grp

root = grp.getgrgid(0)  # O(m) - asks the backend
assert root.gr_gid == 0
assert root == (root.gr_name, root.gr_passwd, root.gr_gid, root.gr_mem)

same = grp.getgrnam(root.gr_name)  # O(m) - another query
assert same == root and same is not root  # a fresh entry, not a cached one

taken = {entry.gr_gid for entry in grp.getgrall()}  # O(g + t)
unlisted = next(gid for gid in range(1_999_999_999, 0, -1) if gid not in taken)
try:
    grp.getgrgid(unlisted)  # missing wherever every group is enumerated, as in a local file
except KeyError as error:
    assert 'gid not found' in str(error)
else:
    raise AssertionError('a missing gid was found')
```

## Enumerating Every Group

`getgrall()` walks the whole database and builds an entry for each group, so it costs every
group and every member name at once. For many lookups, build a dictionary from one call and
look up in that: O(g + t) once, then O(1) per lookup instead of a trip to the backend.

A backend need not enumerate everything it can answer. A directory service may have enumeration
turned off, and a `+` or `-` entry in a local file is likely a NIS reference rather than a group. Fall
back to a lookup when the dictionary misses.

```python
import grp

groups = grp.getgrall()  # O(g + t) time and memory
by_name = {entry.gr_name: entry for entry in groups}  # O(g)

def group(name):
    entry = by_name.get(name)  # O(1)
    if entry is None:
        entry = grp.getgrnam(name)  # O(m) - not enumerated, ask the backend
    return entry

root_name = grp.getgrgid(0).gr_name
assert group(root_name).gr_name == root_name
```

## Finding a User's Groups

`gr_mem` lists only the users named in the group's own record. A user whose primary group it is
is usually not among them, so scanning `getgrall()` for a user name both costs O(g + t) and can
miss a group. `os.getgrouplist()` asks the backend for the user's groups and always includes the
group you pass it - normally the user's primary group from the password database.

```python
import grp
import os
import pwd

user = pwd.getpwuid(0)
groups = os.getgrouplist(user.pw_name, user.pw_gid)  # the backend answers
assert user.pw_gid in groups

# The group passed in is always in the result, listed anywhere or not
groups = grp.getgrall()  # O(g + t)
taken = {g.gr_gid for g in groups}
unlisted = next(gid for gid in range(1_999_999_999, 0, -1) if gid not in taken)
assert unlisted in os.getgrouplist(user.pw_name, unlisted)

# The scan pays for every group and every member name, and sees only
# the memberships written into the group records themselves
listed = [g.gr_gid for g in groups if user.pw_name in g.gr_mem]  # O(g + t)
assert unlisted not in listed
```

## Performance Best Practices

✅ **Do**:

- Look up a single group with `getgrgid()` or `getgrnam()`: it costs one entry, not the database
- Build a dictionary from one `getgrall()` call when you need many groups, and fall back to a
  lookup on a miss
- Use `os.getgrouplist()` to find a user's groups

❌ **Avoid**:

- Calling `getgrgid()` in a loop over many records that share a few groups - each call asks
  the backend again; keep the entries you have already fetched
- Scanning `getgrall()` for one group or one user - O(g + t) for what a lookup answers directly
- Treating `getgrall()` as complete when the system uses a directory service

## Related Modules

- **[pwd](pwd.md)** - The user database, with the same lookup-or-enumerate shape
- **[os](os.md)** - `os.getgrouplist()`, `os.getgroups()` and the process's own group ids
