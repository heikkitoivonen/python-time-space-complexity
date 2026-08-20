# nis Module

⚠️ **REMOVED IN PYTHON 3.13**: The `nis` module was deprecated in Python 3.11 and removed in Python 3.13.

The `nis` module provides read access to Sun's NIS (Network Information
Service, formerly Yellow Pages) — a directory service for distributing user,
group, and host maps across a network.

Every call goes to an NIS server, so wall-clock time is dominated by network
latency rather than by local computation.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `match(key, mapname, domain=None)` | O(1) + network | O(v) | Server-side hash lookup; v = value size |
| `cat(mapname, domain=None)` | O(n) + network | O(n) | Whole map as a dict; n = entries |
| `maps(domain=None)` | O(m) + network | O(m) | List of map names; m = map count |
| `get_default_domain()` | O(1) | O(1) | Local call, no network |

`match()` is the cheap one: the server indexes the map, so a single lookup does
not scan. `cat()` transfers the entire map.

## Looking Up a Single Key

```python
import nis

# O(1) server-side lookup plus one network round trip
try:
    entry = nis.match("alice", "passwd.byname")
    print(entry)
except nis.error as exc:
    print(f"lookup failed: {exc}")
```

## Reading a Whole Map

```python
import nis

# O(n) - transfers and materializes every entry
users = nis.cat("passwd.byname")
print(len(users))

# Which maps does this domain serve? - O(m)
print(nis.maps())
```

## Choosing Between match() and cat()

The tradeoff is round trips versus transfer size:

| Access pattern | Prefer | Why |
|----------------|--------|-----|
| A few known keys | `match()` | O(1) per key, small payloads |
| Most of the map | `cat()` | One round trip instead of n |
| Repeated lookups of the same keys | `cat()` once, then a local dict | Amortizes the network cost |

```python
import nis

# Bad: n round trips
for name in many_names:
    entry = nis.match(name, "passwd.byname")

# Better: one transfer, then O(1) local lookups
table = nis.cat("passwd.byname")     # O(n), one round trip
for name in many_names:
    entry = table.get(name)          # O(1), no network
```

!!! warning "Removed in Python 3.13"
    There is no standard-library replacement. Modern deployments use LDAP
    (via a third-party client) or the system name-service switch through
    `pwd` and `grp`, which consult NIS transparently where it is configured.

!!! warning "Unix only"
    `nis` was never available on Windows, and is absent from builds compiled
    without NIS support even on Unix.

## Version Notes

- **Python 3.11**: deprecated (PEP 594)
- **Python 3.13**: removed
- **Before 3.13**: Unix-only, and only when the interpreter was built with NIS
  support
- **All versions**: `match()` is a constant-time server lookup; `cat()` is
  linear in map size

## Related Documentation

- [Pwd Module](pwd.md)
- [Grp Module](grp.md)
- [Socket Module](socket.md)
- [OS Module](os.md)
