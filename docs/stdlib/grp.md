# grp Module

The `grp` module provides access to the Unix group database (e.g., `/etc/group`). It is Unix-only.

!!! warning "Unix-only"
    The `grp` module is not available on Windows and may not be available on some Python builds.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `grp.getgrnam(name)` | O(n) | O(1) | Linear scan of group database in many implementations |
| `grp.getgrgid(gid)` | O(n) | O(1) | Linear scan of group database in many implementations |
| `grp.getgrall()` | O(n) | O(n) | Reads all group entries |

## Common Operations

### Lookup a Group by Name

```python
import grp

# Lookup group by name - O(n)
group = grp.getgrnam('staff')
print(group.gr_name, group.gr_gid)
```

### Lookup a Group by GID

```python
import grp

# Lookup group by id - O(n)
group = grp.getgrgid(20)
print(group.gr_name, group.gr_mem)
```

### List All Groups

```python
import grp

# List all groups - O(n)
for entry in grp.getgrall():
    print(entry.gr_name)
```

## Related Modules

- [pwd Module](pwd.md) - Unix password database
- [os Module](os.md) - Process and user information
