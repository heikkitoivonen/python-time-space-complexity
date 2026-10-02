# nis Module Complexity

The `nis` module reads maps from Sun's NIS (Network Information Service, formerly Yellow Pages),
a directory service that distributes user, group and host tables across a network. Every call but
`get_default_domain()` makes requests to an NIS server; what a call controls is how many requests
it makes and how much it brings back.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 by PEP 594. The page covers the module
    as it is on Python 3.10 to 3.12 on Unix, in an interpreter built with NIS support; the
    examples also need a machine bound to an NIS domain that serves a non-empty `passwd.byname`.

`n` is the entries in one map and `m` is the maps a domain serves. The bounds treat a key or value
as short - a line of a system table - so decoding one is O(1). `match()`, `cat()` and `maps()`
take the domain as a string and default to `get_default_domain()` when it is left out; `None` is
not accepted. Pass the map name
by position, as its keyword is `map` rather than `mapname`. A map name may be a
nickname - `passwd`, `group`, `hosts`, `networks`, `protocols`, `services`, `ethers` or
`aliases` - which is turned into the full name, such as `passwd.byname`, without a request.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nis.match(key, mapname, domain=default_domain)` | O(1) plus one request | O(1) | Returns the value as a `str`, or raises `nis.error` when the key or map is missing |
| `nis.cat(mapname, domain=default_domain)` | O(n) plus one request | O(n) | Returns the whole map as a new `dict` of `str` to `str`, streamed over one connection |
| `nis.maps(domain=default_domain)` | O(m) plus several requests | O(m) | Returns a `list` of map names. Asks for the master server of each nickname's map until one answers, then connects to that master |
| `nis.get_default_domain()` | O(1) | O(1) | Reads the host's domain name; no request |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nis.error` | O(1) | O(1) | Raised when a call fails, such as for a missing key or map |

## Looking Up Keys

`match()` costs one request whatever the map's size. `cat()` transfers every entry in one
request, so it is the wrong call for one key, and the right one for most of the map: n calls to
`match()` are n round trips, where one `cat()` and a local `dict` lookup per key are one.

```python
import nis

users = nis.cat('passwd')  # O(n) - every entry, over one connection
name, line = next(iter(users.items()))
assert nis.match(name, 'passwd') == line  # O(1) plus one request

try:
    nis.match('no such user', 'passwd.byname')
except nis.error as error:
    assert str(error)  # the NIS library's message
else:
    raise AssertionError('a missing key returned a value')
```

## Listing a Domain's Maps

`get_default_domain()` asks the local host, not a server. `maps()` makes several requests: it
looks for the master server of the standard maps one nickname at a time, then connects to that
master for the list.

```python
import nis

domain = nis.get_default_domain()  # O(1) - no request
maps = nis.maps(domain)  # O(m) plus several requests
assert 'passwd.byname' in maps
```

## Performance Best Practices

✅ **Do**:

- Use `match()` for a few keys; each is one request whatever the map's size
- Call `cat()` once and look keys up in the `dict` when you need most of a map, or the same keys
  repeatedly
- Use `pwd` and `grp` for users and groups; through the C library's name service they consult
  NIS where the host is configured for it, and they outlive this module

❌ **Avoid**:

- Calling `match()` in a loop over a whole map - one round trip per key
- Calling `cat()` to read one key - it transfers every entry
- Passing `domain=None` - it raises `TypeError`; leave the argument out instead

## Version Notes

- **Python 3.11+**: `import nis` emits a `DeprecationWarning`
- **Python 3.13+**: The module is removed; `import nis` raises `ModuleNotFoundError`

## Related Modules

- **[pwd](pwd.md)** - the user database, which reads NIS through the C library where it is
  configured
- **[grp](grp.md)** - the group database, likewise
